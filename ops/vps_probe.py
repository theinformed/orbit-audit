#!/usr/bin/env python3
"""Read-only state of the VPS half of the Space Environment Explorer.

This file is streamed to the VPS over ssh and executed there by
``ops/watchdog.py``. It prints one JSON object on stdout and changes nothing.

Three properties are load-bearing:

1. **It makes no request to celestrak.org.** It reads the mirror's cache
   directory, its halt marker, and its own systemd journal. The watchdog page
   is meant to be refreshed as often as anyone likes, and that is only safe if
   refreshing it costs the upstream nothing. The one import it takes from the
   mirror module is for its interval CONSTANTS; ``celestrak_mirror`` calls
   ``enforce_entity_boundary()`` inside ``main()``, not at import, and opens no
   socket at import time.
2. **It reads the schedule from the VPS's own copy of the fetcher**, not from a
   list typed into this file. If the VPS is running a different cadence than
   the repository believes, the page shows the VPS's number and flags the
   difference, instead of confidently drawing the wrong grid.
3. **No imports outside the standard library, and no local imports of its own.**
   It is executed as ``ssh host python3 -`` with this source on stdin, so there
   is nothing to install on the VPS and nothing to keep in sync.

Anything it cannot measure comes back ``null``. The watchdog treats a null as
"unknown", never as "fine" — a check that could not run has not passed.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time

ROOT = "/root/space-teaching-aid"
CACHE = f"{ROOT}/ingest/cache"
# The mirror computes this as `Path(__file__).resolve().parent / "state"`, so it
# lands beside the script in ingest/, NOT under runtime/. Getting this path
# wrong is not hypothetical: the daily politeness check shipped looking under
# runtime/celestrak-state and was therefore blind to every halt it existed for.
HALT_MARKER = f"{ROOT}/ingest/state/HALTED.json"
DATA = f"{ROOT}/runtime/data"
MIRROR_LOG = "/var/log/celestrak-mirror.log"
JOURNAL_HOURS = 50

# The host's telemetry spine. Every watchdog on that stack drops its latest
# observation here as one JSON file per lane, and the METOC lanes are read from
# it rather than from a second transport of their own: this probe is already a
# single ssh that changes nothing, and adding a second leg to the same machine
# would mean two things to keep working instead of one.
OBSERVATIONS = "/root/.openclaw/workspace/telemetry/observations"


def stat_file(path):
    try:
        info = os.stat(path)
    except OSError:
        return None
    return {"path": path, "bytes": info.st_size, "mtime": info.st_mtime}


def stat_dir(path):
    total = count = 0
    newest = None
    for base, _dirs, files in os.walk(path):
        for name in files:
            try:
                info = os.stat(os.path.join(base, name))
            except OSError:
                continue
            total += info.st_size
            count += 1
            if newest is None or info.st_mtime > newest:
                newest = info.st_mtime
    if count == 0 and not os.path.isdir(path):
        return None
    return {"path": path, "bytes": total, "files": count, "newest": newest}


def read_json(path):
    try:
        with open(path) as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return None


def sha256(path):
    try:
        with open(path, "rb") as handle:
            return hashlib.sha256(handle.read()).hexdigest()
    except OSError:
        return None


def unit(name):
    """systemd's own facts about one unit. Never a judgement, just the fields."""
    fields = [
        "LoadState", "ActiveState", "SubState", "UnitFileState", "Result",
        "ExecMainStatus", "TimeoutStartUSec", "InactiveExitTimestamp",
        "NextElapseUSecRealtime", "LastTriggerUSec", "TimersCalendar",
        "TimersMonotonic",
    ]
    try:
        done = subprocess.run(
            ["systemctl", "show", name, "--no-pager"] + [f"--property={f}" for f in fields],
            capture_output=True, text=True, timeout=30, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    out = {}
    for line in done.stdout.splitlines():
        key, _, value = line.partition("=")
        # systemd repeats a property once per timer entry; joining rather than
        # overwriting keeps every OnCalendar / OnUnitActiveSec it printed.
        out[key] = (out[key] + " " + value) if key in out else value
    return out or None


def journal(service, hours=JOURNAL_HOURS):
    """Raw journal lines. Bucketing and colouring happen in ops/schedule.py."""
    try:
        done = subprocess.run(
            ["journalctl", "-u", service, "--since", f"-{hours}h", "--no-pager",
             "-o", "short-iso", "--utc"],
            capture_output=True, text=True, timeout=90, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout.splitlines()


def mirror_constants():
    """The cadence the VPS is ACTUALLY running, read from the VPS's own file."""
    sys.path.insert(0, ROOT)
    try:
        from ingest import celestrak_mirror as mirror  # noqa: PLC0415
    except Exception:  # noqa: BLE001 - a missing/changed module must not break the probe
        return None
    return {
        "DIR_INTERVAL": getattr(mirror, "DIR_INTERVAL", None),
        "GROUP_INTERVAL": getattr(mirror, "GROUP_INTERVAL", None),
        "GROUPS_PER_RUN": getattr(mirror, "GROUPS_PER_RUN", None),
        "MAX_REQUESTS_PER_RUN": getattr(mirror, "MAX_REQUESTS_PER_RUN", None),
        "GROUPS": list(getattr(mirror, "GROUPS", [])),
        "sha256": sha256(f"{ROOT}/ingest/celestrak_mirror.py"),
    }


def wireguard():
    """The WireGuard peer counters, as an INDEPENDENT check on the publish leg.

    ``wg show <iface> transfer`` prints ``<peer key>\\t<rx>\\t<tx>``, where rx is
    what this machine has RECEIVED from that peer. bigmem is the only peer, so
    rx is the publish traffic arriving — measured by the kernel, entirely
    separately from rsync's own count of what it thinks it sent.

    These are counters since the interface came up, NOT totals for any period.
    Whoever consumes this must difference two samples and must handle the
    counter going backwards on a restart. ``ops/bandwidth.record_wireguard``
    does both; nothing else should read this field.

    Being kernel-level, rx also includes the SSH and TCP framing that rsync
    does not count, plus every other packet over the tunnel. It is expected to
    read slightly HIGH against rsync, and a large gap means something is using
    the tunnel that nobody wrote down -- which is the reason to keep both
    numbers rather than to pick one.
    """
    for interface in ("wg0",):
        try:
            done = subprocess.run(["wg", "show", interface, "transfer"],
                                  capture_output=True, text=True, timeout=20,
                                  check=False)
        except (OSError, subprocess.SubprocessError):
            continue
        if done.returncode != 0:
            continue
        peers = []
        for line in done.stdout.splitlines():
            parts = line.split("\t")
            if len(parts) != 3:
                continue
            try:
                peers.append({"peer": parts[0], "rx": int(parts[1]), "tx": int(parts[2])})
            except ValueError:
                continue
        if peers:
            return {"interface": interface, "peers": peers, "at": time.time()}
    return None


# ``"<request>" <status> <bytes>`` in nginx's combined format. Matched by shape
# rather than by field position: a request line containing a space shifts every
# column after it, and a byte total that silently counts the wrong column is
# exactly the kind of number this page is not allowed to print.
ACCESS_LINE = re.compile(r'"[^"]*"\s+(\d{3})\s+(\d+)\s')


def origin_egress(container="space-teaching-aid-web-1"):
    """Bytes nginx has served since this container started, and how many requests.

    This is an UPPER BOUND on what left the VPS, not the figure itself. Caddy
    strips Accept-Encoding on the way in and compresses on the way out, so what
    nginx reports is the UNCOMPRESSED size of what it handed Caddy. Measured on
    2026-08-08, one cold visit was 13.97 MB decoded against 1.71 MB on the
    wire, so this over-reports by roughly eightfold.

    An upper bound is still a fact, and it can only ever make an allowance look
    tighter than it is, which is the safe direction to be wrong in. The exact
    figure needs Caddy's own access log, which is not currently enabled.

    Monotonic between container restarts and log rotations; the consumer
    differences it and re-bases when it goes backwards.
    """
    try:
        done = subprocess.run(["docker", "logs", container],
                              capture_output=True, text=True, timeout=120, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    if done.returncode != 0:
        return None
    total = requests = 0
    for line in done.stdout.splitlines():
        match = ACCESS_LINE.search(line)
        if not match:
            continue
        requests += 1
        total += int(match.group(2))
    return {"container": container, "bytes": total, "requests": requests,
            "basis": "nginx $body_bytes_sent, UNCOMPRESSED at the origin",
            "at": time.time()}


def invalid_groups():
    """The mirror's quarantine ledger: group names CelesTrak says do not exist.

    Read, never written, and never verified against the live service. Same
    reason the halt marker is imported rather than typed: the mirror owns the
    path, so it cannot drift out from under this probe.
    """
    try:
        sys.path.insert(0, ROOT)
        from ingest import celestrak_mirror  # noqa: PLC0415
        from ingest.celestrak_groups import read_ledger  # noqa: PLC0415
        return {
            "ledger": read_ledger(celestrak_mirror.STATE),
            "configProblems": [list(row) for row in celestrak_mirror.GROUP_LIST_PROBLEMS],
        }
    except Exception:  # noqa: BLE001 - a probe must never take the page down
        return None


def celestrak_watch():
    """Ask the daily politeness check for its numbers. --json never alerts."""
    script = f"{ROOT}/ops/celestrak_watch.py"
    if not os.path.isfile(script):
        return None
    try:
        done = subprocess.run(
            ["python3", script, "--json", "--window-hours", "24"],
            capture_output=True, text=True, timeout=90, check=False,
        )
        return json.loads(done.stdout)
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def metoc_observations(prefix="metoc-"):
    """Every METOC lane's latest observation, exactly as the spine holds it.

    Read-only, local files, no judgement: the states here are the lanes' own
    words (``healthy`` / ``problem`` / ``unknown``) and the grading happens on
    the other end. ``observedAt`` is EPOCH MILLISECONDS in this schema, and the
    file's own mtime comes back beside it so a lane that stopped WRITING is
    distinguishable from a lane that wrote a stale answer.

    A lane that has been retired leaves no file. That is not a missing lane and
    nothing here invents one -- the caller holds the retirement list.
    """
    try:
        names = sorted(os.listdir(OBSERVATIONS))
    except OSError as error:
        return {"error": str(error)[:200], "lanes": None}
    lanes = {}
    for name in names:
        if not name.startswith(prefix) or not name.endswith(".json"):
            continue
        path = os.path.join(OBSERVATIONS, name)
        body = read_json(path)
        if body is None:
            continue
        body["fileMtime"] = (stat_file(path) or {}).get("mtime")
        lanes[name[: -len(".json")]] = body
    return {"error": None, "lanes": lanes, "path": OBSERVATIONS}


def main():
    manifest = read_json(f"{DATA}/manifest.json") or {}
    try:
        usage = shutil.disk_usage("/")
        disk = {"total": usage.total, "used": usage.used, "free": usage.free}
    except OSError:
        disk = None

    cache_files = {}
    try:
        for name in sorted(os.listdir(CACHE)):
            entry = stat_file(os.path.join(CACHE, name))
            if entry:
                cache_files[name] = entry
    except OSError:
        cache_files = {}

    print(json.dumps({
        "ok": True,
        "hostname": os.uname().nodename,
        "now": time.time(),
        "journalHours": JOURNAL_HOURS,
        "celestrakCache": cache_files,
        "celestrakHalt": read_json(HALT_MARKER),
        "celestrakHaltPath": HALT_MARKER,
        "celestrakHaltPresent": os.path.exists(HALT_MARKER),
        "celestrakHaltMtime": (stat_file(HALT_MARKER) or {}).get("mtime"),
        "mirrorLog": stat_file(MIRROR_LOG),
        "mirrorConstants": mirror_constants(),
        "celestrakInvalidGroups": invalid_groups(),
        "celestrakWatch": celestrak_watch(),
        "celestrakWatchPath": f"{ROOT}/ops/celestrak_watch.py",
        "celestrakWatchSha256": sha256(f"{ROOT}/ops/celestrak_watch.py"),
        # Bandwidth. Both are DELTA sources -- counters, not period totals --
        # and ops/bandwidth.py is the only thing allowed to turn them into
        # bytes-per-period.
        "wireguard": wireguard(),
        "originEgress": origin_egress(),
        "cadenceRequests": sorted(os.listdir(f"{ROOT}/runtime/cadence-requests"))
                           if os.path.isdir(f"{ROOT}/runtime/cadence-requests") else None,
        "runtimeData": stat_dir(DATA),
        "manifestFile": stat_file(f"{DATA}/manifest.json"),
        "manifestGeneratedAt": manifest.get("generatedAt"),
        "manifestRelease": manifest.get("release"),
        "disk": disk,
        # METOC rides this same probe. weather.theinformed.org is the other
        # tenant of bigmem-PC and its spine observations live here, on the VPS.
        "metocObservations": metoc_observations(),
        "units": {
            name: unit(name) for name in (
                "celestrak-mirror.timer", "celestrak-mirror.service",
                "celestrak-watch.timer", "celestrak-watch.service",
                "metoc-site-health.timer", "metoc-site-health.service",
            )
        },
        "journals": {
            "celestrak-mirror.service": journal("celestrak-mirror.service"),
            "celestrak-watch.service": journal("celestrak-watch.service"),
        },
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
