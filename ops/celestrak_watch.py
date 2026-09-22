#!/usr/bin/env python3
"""Count what we actually asked CelesTrak for, and shout if it looks impolite.

WHY THIS EXISTS
---------------
This installation was banned from CelesTrak once, on 2026-08-07, because group
queries that had never succeeded retried on every five-minute publish cycle
forever. Dr Kelso runs that server himself on donations, and access has to be
asked back personally, so "we are within policy" must be a number someone can
read, not an assurance.

WHAT IT DOES
------------
Counts requests from the mirror's own journal over a rolling window and compares
them against a ceiling. Nothing here is a judgement call and no language model is
involved: a prior incident on this stack had a model write an all-clear health
report over 105 real warnings, so health is decided by arithmetic only.

It is deliberately quiet. It alerts on an anomaly and is otherwise silent, so it
does not become another ignored cron notification.

WHAT COUNTS AS AN ANOMALY
-------------------------
1. A halt marker present. The mirror stops on any non-200 and waits for a human;
   if it is halted, the catalog is quietly ageing and someone must look.
2. Requests over the ceiling in the window. The mirror can run only every six
   hours. One daily directory check plus the weekly-group rotation makes five
   attempts the normal daily maximum; the ceiling of seven leaves rolling-
   window tolerance without normalising an accidental second request per slot.
3. A group name CelesTrak says does not exist. It answers those with HTTP 200
   and a plain-text "Invalid query", so nothing used to notice: five such names
   were requested weekly for an unknown length of time. The mirror now writes
   each one to ingest/state/invalid-groups.json and stops asking; this is where
   a human finds out that it happened.
4. A configured group list that cannot work at all -- a malformed name, a
   duplicate, or one of the five names measured absent. Checked offline, from
   the mirror's own constants. Nothing here queries celestrak.org.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SERVICE = "celestrak-mirror.service"
ROOT = Path("/root/space-teaching-aid")

# WHERE THE HALT MARKER IS, AND WHY THIS IS NOT A CONSTANT ANY MORE
# -----------------------------------------------------------------
# This file shipped on 2026-08-07 with the marker path written out by hand as
# runtime/celestrak-state/HALTED.json. The mirror actually computes it as
# `Path(__file__).resolve().parent / "state"`, which lands in ingest/state/.
# The two never agreed, so `halted` was ALWAYS None and this check was blind to
# the single condition it exists for. It was caught the next day, with a real
# halt in place since 23:25Z and this script cheerfully reporting "no halt
# marker is in place now" in the same sentence as the halt it had just found in
# the journal.
#
# So the path is no longer typed here. It is imported from the mirror, which is
# the thing that writes it. If the mirror moves its state directory, this
# follows automatically instead of quietly going blind again.
def _mirror_module():
    """The mirror module, or None. Never let an import failure hide a finding."""
    try:
        sys.path.insert(0, str(ROOT))
        from ingest import celestrak_mirror  # noqa: PLC0415
        return celestrak_mirror
    except Exception:  # noqa: BLE001
        return None


def _halt_marker() -> Path:
    try:
        sys.path.insert(0, str(ROOT))
        from ingest.celestrak_mirror import HALT_MARKER as marker  # noqa: PLC0415
        return Path(marker)
    except Exception:  # noqa: BLE001 - never let an import failure hide a halt
        # Last-resort literal, deliberately the mirror's REAL layout rather than
        # the wrong one this file used to carry.
        return ROOT / "ingest" / "state" / "HALTED.json"


HALT_MARKER = _halt_marker()

# The six-hour outbound gate provides four opportunities/day. One daily SATCAT
# directory request plus at most one category request in each opportunity makes
# five attempts the normal maximum. Seven permits a rolling-window boundary.
DEFAULT_CEILING = 7
DEFAULT_WINDOW_HOURS = 24

# The mirror logs this before opening each socket, so failed attempts count.
REQUEST_LINE = re.compile(r"REQUEST START (\d+)/(\d+) dataset=([^ ]+)")
RUN_LINE = re.compile(r"run complete; (\d+) request\(s\) made")

# Count only the mirror's canonical event, not prose that happens to mention a
# status.  The former broad matcher treated all three of these as new refusals:
# "still halted" (a deliberately socket-free timer run), "halt cleared", and a
# WASTED REQUEST explanation containing the historical words "HTTP 403".  A
# real refusal always calls halt(), which emits one uppercase ``HALT status=``
# line (or ``HALT:`` in the pre-2026-08-27 format) before the marker is written.
REFUSAL = re.compile(r"(?:^|\s)HALT(?:\s+status=|:\s)")
HALT_CLEARED_LINE = re.compile(
    r"\bhalt cleared by operator after recorded investigation:\s", re.IGNORECASE
)
SUCCESSFUL_REQUEST_RUN = re.compile(r"\brun complete; ([1-9]\d*) request\(s\) made\b")

# Counted and reported, because a 304 is the cheapest good outcome this lane has
# and an operator should be able to see it happening.
NOT_MODIFIED_LINE = re.compile(r"HTTP 304 Not Modified", re.IGNORECASE)


def journal_lines(window_hours: int) -> list[str]:
    result = subprocess.run(
        ["journalctl", "-u", SERVICE, "--since", f"-{window_hours}h", "--no-pager"],
        capture_output=True, text=True, check=False,
    )
    return result.stdout.splitlines()


def invalid_group_state() -> dict:
    """The quarantine ledger and the offline shape check, from the mirror itself.

    Read through the mirror module rather than from a path typed here. This
    file already went blind once, on 2026-08-07, because it carried a
    hand-written copy of the halt-marker path that never matched the one the
    mirror actually writes.
    """
    mirror = _mirror_module()
    if mirror is None:
        return {"ledger": {}, "configProblems": [], "read": False}
    try:
        from ingest.celestrak_groups import read_ledger  # noqa: PLC0415
        ledger = read_ledger(mirror.STATE)
    except Exception:  # noqa: BLE001
        ledger = {}
    problems = [list(row) for row in getattr(mirror, "GROUP_LIST_PROBLEMS", [])]
    return {"ledger": ledger, "configProblems": problems, "read": True}


def survey(window_hours: int) -> dict:
    lines = journal_lines(window_hours)
    attempt_rows = [m.groups() for line in lines if (m := REQUEST_LINE.search(line))]
    attempts = [row[2] for row in attempt_rows]
    # A refusal that was explicitly cleared and followed by a successful
    # request-bearing run is recovered history, not a present incident. Keep it
    # visible in JSON for audit, but never page a human about it again. Conversely,
    # a HALT event whose marker vanished without that sequence is a real
    # inconsistency and remains an alarm.
    halt_events = [(index, line) for index, line in enumerate(lines) if REFUSAL.search(line)]
    clear_indexes = [index for index, line in enumerate(lines) if HALT_CLEARED_LINE.search(line)]
    success_indexes = [
        index for index, line in enumerate(lines) if SUCCESSFUL_REQUEST_RUN.search(line)
    ]
    recovered: list[str] = []
    unreconciled: list[str] = []
    for halt_index, line in halt_events:
        clear_index = next((index for index in clear_indexes if index > halt_index), None)
        resumed = clear_index is not None and any(index > clear_index for index in success_indexes)
        (recovered if resumed else unreconciled).append(line)
    not_modified = [line for line in lines if NOT_MODIFIED_LINE.search(line)]
    halted = None
    if HALT_MARKER.exists():
        try:
            halted = json.loads(HALT_MARKER.read_text())
        except (OSError, json.JSONDecodeError):
            halted = {"note": "halt marker present but unreadable"}
    groups = invalid_group_state()
    return {
        "invalidGroups": groups["ledger"],
        "groupConfigProblems": groups["configProblems"],
        "groupStateRead": groups["read"],
        "windowHours": window_hours,
        "runs": sum(1 for ordinal, _limit, _dataset in attempt_rows if ordinal == "1"),
        "requests": len(attempts),
        "requestDatasets": attempts,
        "busiestRun": max((int(row[0]) for row in attempt_rows), default=0),
        # Backward-compatible name: downstream code already reads refusalLines.
        # It now means only refusal events that have not completed the audited
        # clear -> successful-request sequence.
        "refusalLines": unreconciled[-5:],
        "haltEventLines": [line for _index, line in halt_events][-5:],
        "recoveredHaltEvents": len(recovered),
        "notModified": len(not_modified),
        "halted": halted,
        "checkedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def verdict(state: dict, ceiling: int) -> tuple[bool, str]:
    """Return (ok, human sentence). Arithmetic only - never a model's opinion."""
    if state["halted"]:
        marker = state["halted"]
        return False, (
            f"The CelesTrak mirror is HALTED since {marker.get('at', 'an unknown time')} "
            f"(status {marker.get('status', 'unknown')}). It stopped on a non-200 exactly as "
            "their usage policy requires and is waiting for a human. Orbital elements continue "
            "from Space-Track; only cached CelesTrak metadata is ageing. Any later clearance "
            "must include a recorded --reason."
        )
    if state.get("groupConfigProblems"):
        detail = "; ".join(f"{name} {reason}" for name, reason in state["groupConfigProblems"])
        return False, (
            "The CelesTrak group list is misconfigured and the mirror is REFUSING to "
            f"query anything until it is fixed: {detail}. This was decided offline, from "
            "the list itself; no request was made to find out. Edit GROUPS in "
            "ingest/celestrak_mirror.py."
        )
    if state.get("invalidGroups"):
        names = ", ".join(sorted(state["invalidGroups"]))
        return False, (
            f"CelesTrak REJECTED {len(state['invalidGroups'])} configured group name(s) as "
            f"non-existent: {names}. It answers those with HTTP 200 and a plain-text "
            "\"Invalid query\", which is why five such names once went unnoticed for weeks. "
            "Each is quarantined and will not be requested again. Remove the name from "
            "GROUPS in ingest/celestrak_mirror.py, then: python3 "
            "/root/space-teaching-aid/ingest/celestrak_mirror.py --clear-invalid-groups"
        )
    if state["requests"] > ceiling:
        return False, (
            f"CelesTrak requests are above the ceiling: {state['requests']} in the last "
            f"{state['windowHours']}h across {state['runs']} runs, ceiling {ceiling}. "
            "The design maximum is eight/day. Check for a retry loop before "
            "CelesTrak notices, not after."
        )
    if state["refusalLines"]:
        return False, (
            f"CelesTrak logged {len(state['refusalLines'])} HALT event(s) in the last "
            f"{state['windowHours']}h, but no halt marker and no later audited clearance plus "
            "successful request run reconcile them. Inspect the journal and halt archive."
        )
    return True, (
        f"CelesTrak: {state['requests']} request(s) in {state['windowHours']}h across "
        f"{state['runs']} run(s), busiest run {state['busiestRun']}, "
        f"{state.get('notModified', 0)} answered 304 Not Modified (nothing re-downloaded), "
        f"{state.get('recoveredHaltEvents', 0)} earlier halt event(s) recovered, "
        "no unreconciled refusals, not halted, no rejected group names."
    )


def alert(message: str) -> None:
    """Page a human through the notification channel. A failed alert must never mask the finding."""
    try:
        subprocess.run(
            [
                "docker", "exec", "openclaw-openclaw-gateway-1", "openclaw", "cron", "create",
                "--at", "+1m", "--delete-after-run", "--announce",
                "--channel", "discord", "--to", "user:432502319473754112",
                "--name", "celestrak-rate-watch",
                "--message", message,
            ],
            check=False, capture_output=True, timeout=60,
        )
    except Exception as error:  # noqa: BLE001 - alerting must never hide the finding
        print(f"ALERT FAILED (the finding still stands): {error}", file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--window-hours", type=int, default=DEFAULT_WINDOW_HOURS)
    parser.add_argument("--ceiling", type=int, default=DEFAULT_CEILING)
    parser.add_argument("--json", action="store_true", help="machine-readable, never alerts")
    parser.add_argument("--quiet", action="store_true",
                        help="print nothing when healthy (for timer use)")
    args = parser.parse_args()

    state = survey(args.window_hours)
    ok, sentence = verdict(state, args.ceiling)

    if args.json:
        print(json.dumps({**state, "ok": ok, "verdict": sentence}, indent=2))
        return 0 if ok else 1

    if ok:
        if not args.quiet:
            print(sentence)
        return 0

    print(sentence, file=sys.stderr)
    alert(sentence)
    return 1


if __name__ == "__main__":
    sys.exit(main())
