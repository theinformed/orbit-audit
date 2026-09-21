#!/usr/bin/env python3
"""SuperMAG auroral-electrojet index ingest. Runs ONLY on bigmem-PC.

WHAT THIS IS FOR
----------------
SuperMAG (JHU/APL) combines ~500 ground magnetometers into the SME/SML/SMU
auroral electrojet indices - the standard measure of how hard the auroral
current system is being driven. `docs/gannon-storm-module-design.md` wants them
for chain link 5, and nothing else serves an equivalent global index for
May 2024.

    SML   the westward electrojet, the strongly negative one. The substorm index.
    SMU   the eastward electrojet.
    SME   SMU - SML, the total envelope.

Measured on the real service: over the Gannon storm week SML runs about
-163 nT on the quiet day of 9 May 2024 and reaches **-4,057.6 nT at
2024-05-10T19:48Z**, with SME peaking at **4,691.6 nT** at the same minute. That
is a factor of twenty-five, and it is why this source is worth the care below.

*(Corrected 2026-08-19. This block previously read -3,565 nT at 19:20Z and SME
4,171 nT. Both numbers are real values from this same mirror -- -3,564.98 nT is
exactly what 19:20Z holds -- but neither is the extremum, and quoting a sample
as a peak understates the storm by half a thousand nanotesla. Reproduce with
`published_series(..., cadence_minutes=1)` and take `min` over `sml`.)*

ENTITY BOUNDARY
---------------
Same guard, same reason as `ingest/spacetrack_ingest.py`: the SuperMAG account
is registered to Sean personally, so it is used only from his own machine. The
VPS operates under the LLC and must never carry a personal registration. Note
this is the opposite of `ingest/celestrak_mirror.py`, which is VPS-only.

WHAT MAY BE PUBLISHED, WHICH IS NOT WHAT THE RULES OF THE ROAD FIRST SUGGEST
---------------------------------------------------------------------------
SuperMAG's published Rules of the Road say derived products "cannot be
redistributed", and an earlier reading of that in
`docs/gannon-storm-module-design.md` excluded the source outright. Sean then
checked with a contact at JHU/APL and the actual position is narrower:

    Derived VISUALISATION is cleared. Dataset REDISTRIBUTION is not.

That is the same shape as the USSPACECOM position on orbital elements, and the
same lesson: the conservative reading of a licence is not automatically the
correct one, and the data owner is the authority on it. So:

    ALLOWED    a plotted SME/SML curve on the site, with citation.
    NOT        shipping these files, or an endpoint that re-serves the series.

`published_series()` exists to make the allowed thing easy and the disallowed
thing require deliberate effort: it decimates to a plotting cadence and returns
values, not the mirror. The raw mirror stays on /mnt/d and never enters git,
never reaches the VPS, and never becomes a published artifact.

CREDENTIAL
----------
There is no password. The userid IS the entire credential, sent as `logon=`:

    ~/.config/supermag/credentials     (mode 0600, bigmem only)
        SUPERMAG_LOGON=<your-userid>

Because it travels in the query string, no URL with a query is ever logged or
written into the halt marker.

HTTP 200 IS NOT SUCCESS
-----------------------
`docs/gannon-storm-module-design.md` §4.1.1 lists this service by name in its
"200 is not success" catalogue: SuperMAG answers **200 with a body of
`ERROR: Invalid username`**. The first real run of this module added a second
case that catalogue did not have - **200 with a PHP
`<b>Warning</b>: shell_exec(): Unable to execute ...` HTML page** when their
backend hiccups. Every check here is therefore on CONTENT, and the one rule
that keeps this project out of an upstream's firewall applies as it does to
CelesTrak: halt on anything unexpected and tell a human, never retry in a loop.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Sequence

# ---------------------------------------------------------------------------
# The boundary. Do not relax without Sean's explicit instruction.
# ---------------------------------------------------------------------------
SUPERMAG_HOST = "bigmem-PC"


def enforce_entity_boundary(host: str | None = None) -> None:
    current = host if host is not None else socket.gethostname()
    if current != SUPERMAG_HOST:
        raise SystemExit(
            f"REFUSING TO RUN on host {current!r}. SuperMAG is queried only from "
            f"{SUPERMAG_HOST}, under Sean's personal registration. The VPS operates "
            "under the LLC and must never carry it."
        )


ROOT = Path(__file__).resolve().parents[1]
BASE = "https://supermag.jhuapl.edu/services"
INDICES = f"{BASE}/indices.php"
CREDENTIALS = Path.home() / ".config" / "supermag" / "credentials"

USER_AGENT = "theinformed.org-space-teaching-aid/1.0 (non-commercial teaching site)"

# Everything on /mnt/d, never the SSD. Same rule as the orbit archive.
DEFAULT_ROOT = Path("/mnt/d/space-supermag")
HALT_NAME = "HALTED.json"

# One request per calendar day of the window. Their `extent` is in seconds; a
# day is a natural chunk, keeps any single response small, and means an
# interrupted run resumes at a day boundary rather than re-fetching a week.
CHUNK_SECONDS = 86_400
POLITE_GAP = 5.0
REQUEST_TIMEOUT = 120.0

# The three indices the Gannon module needs. `indices=` takes a comma list.
WANTED = ("sme", "sml", "smu")

# SuperMAG's fill number for "no value here". It arrives as an ordinary JSON
# float, so it is invisible to a null check and enormous to a min/max — an
# unguarded consumer plots a 999999 nT electrojet.
FILL_VALUE = 999_999.0


def is_fill(value: Any) -> bool:
    """True for null and for the fill number, the two shapes of 'no value'."""
    if value is None:
        return True
    try:
        return abs(float(value)) >= FILL_VALUE
    except (TypeError, ValueError):
        return True

# The Gannon storm, with a quiet day either side so a reader can see the
# baseline the storm departs from. Dates from the module design document.
GANNON_START = dt.datetime(2024, 5, 7, tzinfo=dt.timezone.utc)
GANNON_END = dt.datetime(2024, 5, 14, tzinfo=dt.timezone.utc)


class Halted(RuntimeError):
    """Raised the moment SuperMAG answers with anything unexpected.

    `transient` separates a fault on their side from a fault in what we asked
    for, and the distinction decides whether a retry is allowed at all. Seen on
    the very first real run: their backend answered 200 with a PHP
    `Warning: shell_exec(): Unable to execute ...` HTML page for 2024-05-09, and
    served the same day perfectly five seconds later.

    A rejected userid, or a well-formed response carrying no measurement, is not
    transient. Retrying those is precisely the behaviour that got this project
    banned from CelesTrak - a query that had never succeeded, repeated forever.
    """

    def __init__(self, reason: str, *, transient: bool = False) -> None:
        super().__init__(reason)
        self.transient = transient


def log(message: str) -> None:
    print(f"{dt.datetime.now(dt.timezone.utc):%Y-%m-%dT%H:%M:%SZ} {message}", flush=True)


def data_root(root: Path | None = None) -> Path:
    if root is not None:
        return root
    override = os.environ.get("SPACE_EXPLORER_SUPERMAG_ROOT")
    return Path(override) if override else DEFAULT_ROOT


# ---------------------------------------------------------------------------
# Credential
# ---------------------------------------------------------------------------
def load_logon(path: Path | None = None) -> str:
    """Read the userid. Refuses a file other users can read."""
    target = path if path is not None else CREDENTIALS
    if not target.exists():
        raise SystemExit(
            f"No SuperMAG credential at {target}.\n"
            "Create it yourself (this tool will never write it, and it must never "
            "enter git):\n"
            "  mkdir -p ~/.config/supermag\n"
            "  printf 'SUPERMAG_LOGON=%s\\n' 'your-userid' > ~/.config/supermag/credentials\n"
            "  chmod 600 ~/.config/supermag/credentials"
        )
    mode = target.stat().st_mode & 0o777
    if mode & 0o077:
        raise SystemExit(
            f"{target} is mode {mode:o}; refusing to read a credential other users "
            "can see. Run: chmod 600 " + str(target)
        )
    for line in target.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        if key.strip() == "SUPERMAG_LOGON" and value.strip():
            return value.strip()
    raise SystemExit(f"{target} must define SUPERMAG_LOGON")


# ---------------------------------------------------------------------------
# The halt. One rule: stop and tell a human.
# ---------------------------------------------------------------------------
def halt_marker(root: Path) -> Path:
    return root / HALT_NAME


def halted_reason(root: Path) -> dict | None:
    marker = halt_marker(root)
    if not marker.exists():
        return None
    try:
        return json.loads(marker.read_text())
    except (OSError, json.JSONDecodeError):
        return {"reason": "unreadable halt marker"}


def halt(root: Path, reason: str, *, endpoint: str = INDICES) -> None:
    root.mkdir(parents=True, exist_ok=True)
    # Path only, never the query string: the userid travels in the query and a
    # halt marker is exactly the sort of file that gets pasted into a chat.
    halt_marker(root).write_text(
        json.dumps(
            {
                "at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                "reason": reason,
                "endpoint": urllib.parse.urlsplit(endpoint).path,
                "note": "A human must investigate and clear this with --clear-halt.",
            },
            indent=2,
        )
        + "\n"
    )
    log(f"HALT: {urllib.parse.urlsplit(endpoint).path}: {reason}. All queries stopped.")


# ---------------------------------------------------------------------------
# Content validation - the whole point
# ---------------------------------------------------------------------------
def validate_payload(body: bytes) -> list[dict]:
    """Turn a response body into records, or say precisely what is wrong.

    Status is not consulted anywhere in here on purpose. SuperMAG returns 200
    with `ERROR: Invalid username`, and a fetcher that trusts the status code
    stores that string as if it were data.
    """
    if not body.strip():
        raise Halted("empty body", transient=True)
    head = body[:200].decode("utf-8", "replace").strip()
    if head.upper().startswith("ERROR"):
        # Their documented failure shape, including a bad or unregistered userid.
        raise Halted(f"service returned an error body: {head[:120]!r}")
    try:
        payload = json.loads(body)
    except (json.JSONDecodeError, ValueError) as error:
        # An HTML or PHP-warning body is their server failing, not our query.
        raise Halted(
            f"unparseable body ({error}); starts {head[:80]!r}", transient=True
        ) from None
    if not isinstance(payload, list):
        raise Halted(
            f"expected a JSON array, got {type(payload).__name__}", transient=True
        )
    if not payload:
        raise Halted("no records for the requested window")
    missing = [key for key in ("tval", "SME", "SML", "SMU") if key not in payload[0]]
    if missing:
        raise Halted(f"records are missing {', '.join(missing)}")
    # An all-null series is the USGS `type=definitive` failure in another
    # costume: a well-formed response carrying no measurement at all.
    if all(record.get("SME") is None for record in payload):
        raise Halted("every SME value is null")
    # Third entry in this service's "200 is not success" catalogue, and the
    # quietest of the three. For a window SuperMAG has not processed yet it
    # answers 200 with a full-length, correctly-shaped JSON array in which every
    # value is the fill number. Measured 2026-08-12: 1,440 of 1,440 records
    # filled for 2026-07-25 and 2026-08-01, against 0 of 1,440 for 2024-05-10.
    # Nothing above catches it, so without this the mirror silently fills with
    # 999999 and every consumer downstream reads it as a real quiet day.
    if all(is_fill(record.get("SME")) for record in payload):
        raise Halted(
            f"every SME value is the {FILL_VALUE:.0f} fill: SuperMAG has not "
            "processed this window yet"
        )
    return payload


def fetch_window(
    logon: str, start: dt.datetime, extent_seconds: int, *, opener=None
) -> list[dict]:
    """One request. Any surprise raises `Halted` rather than returning."""
    query = urllib.parse.urlencode(
        {
            "nohead": "",
            "fmt": "json",
            "logon": logon,
            "start": start.strftime("%Y-%m-%dT%H:%M:%S"),
            "extent": int(extent_seconds),
            "indices": ",".join(WANTED),
        }
    )
    url = f"{INDICES}?{query}"
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        get = opener.open if opener is not None else urllib.request.urlopen
        with get(request, timeout=REQUEST_TIMEOUT) as response:
            if response.status != 200:
                raise Halted(f"HTTP {response.status}", transient=response.status >= 500)
            body = response.read()
    except urllib.error.HTTPError as error:
        raise Halted(f"HTTP {error.code}", transient=error.code >= 500) from None
    except urllib.error.URLError as error:
        raise Halted(f"transport: {error.reason}", transient=True) from None
    return validate_payload(body)


# ---------------------------------------------------------------------------
# Mirror
# ---------------------------------------------------------------------------
def day_path(root: Path, day: dt.date) -> Path:
    return root / "indices" / f"sme-{day.isoformat()}.json"


def ingest_range(
    start: dt.datetime,
    end: dt.datetime,
    *,
    root: Path | None = None,
    logon: str | None = None,
    force: bool = False,
    opener=None,
    gap_seconds: float = POLITE_GAP,
) -> dict:
    """Mirror whole UTC days of SME/SML/SMU. Resumable, and halts on surprise.

    A day already on disk is never re-fetched. That is the CelesTrak lesson
    applied before it is needed: the way to be a good guest on a research
    service is to ask once.
    """
    base = data_root(root)
    marker = halted_reason(base)
    if marker and not force:
        log(f"still halted since {marker.get('at')} ({marker.get('reason')}); not querying")
        return {"halted": marker, "days": [], "recordsWritten": 0}

    who = logon if logon is not None else load_logon()
    (base / "indices").mkdir(parents=True, exist_ok=True)

    report: dict[str, Any] = {"days": [], "skipped": [], "recordsWritten": 0}
    day = start.date()
    first = True
    while day < end.date():
        destination = day_path(base, day)
        if destination.exists() and not force:
            report["skipped"].append(day.isoformat())
            day += dt.timedelta(days=1)
            continue
        if not first:
            time.sleep(gap_seconds)
        first = False
        midnight = dt.datetime.combine(day, dt.time(), tzinfo=dt.timezone.utc)
        try:
            records = fetch_window(who, midnight, CHUNK_SECONDS, opener=opener)
        except Halted as error:
            # ONE retry, and only for a fault on their side. Their backend
            # served a PHP warning page for 2024-05-09 and the same day
            # perfectly five seconds later, so halting the whole window on a
            # single hiccup is too brittle - and retrying a rejected userid
            # forever is how this project lost CelesTrak. One, then stop.
            if not error.transient:
                halt(base, str(error))
                report["halted"] = {"day": day.isoformat(), "reason": str(error)}
                return report
            log(f"{day.isoformat()}: {error} - retrying once")
            report.setdefault("retried", []).append(
                {"day": day.isoformat(), "reason": str(error)}
            )
            time.sleep(gap_seconds)
            try:
                records = fetch_window(who, midnight, CHUNK_SECONDS, opener=opener)
            except Halted as second:
                halt(base, f"{second} (after one retry)")
                report["halted"] = {
                    "day": day.isoformat(),
                    "reason": f"{second} (after one retry)",
                }
                return report
        # Written whole, then moved: a torn file would look like a fetched day
        # and would never be retried.
        temporary = destination.with_suffix(".json.next")
        temporary.write_text(json.dumps(records))
        os.replace(temporary, destination)
        report["days"].append({"day": day.isoformat(), "records": len(records)})
        report["recordsWritten"] += len(records)
        log(f"{day.isoformat()}: {len(records):,} minutes")
        day += dt.timedelta(days=1)
    return report


# ---------------------------------------------------------------------------
# The one thing that may be published
# ---------------------------------------------------------------------------
def published_series(
    start: dt.datetime,
    end: dt.datetime,
    *,
    root: Path | None = None,
    cadence_minutes: int = 5,
) -> dict:
    """A decimated SME/SML curve for plotting, with its citation attached.

    This is the *derived visualisation* JHU/APL cleared, and deliberately not
    the mirror: it thins to a plotting cadence and carries the attribution that
    is the condition of use. Publishing `indices/*.json` instead would be
    dataset redistribution, which is the thing that is not cleared.
    """
    base = data_root(root)
    samples: list[dict] = []
    day = start.date()
    while day < end.date():
        path = day_path(base, day)
        if path.exists():
            for record in json.loads(path.read_text()):
                stamp = record.get("tval")
                if stamp is None:
                    continue
                when = dt.datetime.fromtimestamp(float(stamp), dt.timezone.utc)
                if not (start <= when < end):
                    continue
                if when.minute % cadence_minutes:
                    continue
                # Fill becomes null HERE, at the one boundary that publishes.
                # A 999999 that reaches a plot is a 999999 nT electrojet, and a
                # gap drawn as a gap is the only honest thing to draw.
                samples.append(
                    {
                        "t": when.isoformat().replace("+00:00", "Z"),
                        "sme": None if is_fill(record.get("SME")) else record.get("SME"),
                        "sml": None if is_fill(record.get("SML")) else record.get("SML"),
                        "smu": None if is_fill(record.get("SMU")) else record.get("SMU"),
                    }
                )
        day += dt.timedelta(days=1)
    samples.sort(key=lambda row: row["t"])
    lows = [s["sml"] for s in samples if s["sml"] is not None]
    return {
        "index": "SuperMAG SME/SML/SMU",
        "unit": "nT",
        "cadenceMinutes": cadence_minutes,
        "samples": samples,
        "peakSml": min(lows) if lows else None,
        "citation": (
            "Auroral electrojet indices from SuperMAG (Gjerloev, J. W., 2012, "
            "J. Geophys. Res., doi:10.1029/2012JA017683). We gratefully "
            "acknowledge the SuperMAG collaborators and the ground magnetometer "
            "operators whose stations make these indices possible."
        ),
        "usage": (
            "Derived visualisation, published with citation. The underlying "
            "SuperMAG series is not redistributed."
        ),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Mirror SuperMAG SME/SML/SMU indices. bigmem-PC only."
    )
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument("--start", default=None, help="UTC date, YYYY-MM-DD")
    parser.add_argument("--end", default=None, help="UTC date, exclusive")
    parser.add_argument(
        "--gannon",
        action="store_true",
        help="the storm window the module needs: 2024-05-07 to 2024-05-14",
    )
    parser.add_argument("--force", action="store_true", help="re-fetch days already held")
    parser.add_argument("--clear-halt", action="store_true")
    parser.add_argument("--status", action="store_true")
    parser.add_argument(
        "--series", action="store_true", help="print the publishable decimated curve"
    )
    args = parser.parse_args(argv)

    enforce_entity_boundary()
    base = data_root(args.root)

    if args.clear_halt:
        halt_marker(base).unlink(missing_ok=True)
        log("halt cleared")
        return 0

    if args.status:
        held = sorted(p.name for p in (base / "indices").glob("sme-*.json")) if (
            base / "indices"
        ).exists() else []
        print(json.dumps({
            "root": str(base),
            "daysHeld": len(held),
            "first": held[0] if held else None,
            "last": held[-1] if held else None,
            "halted": halted_reason(base),
        }, indent=2))
        return 0

    if args.gannon:
        start, end = GANNON_START, GANNON_END
    elif args.start and args.end:
        start = dt.datetime.fromisoformat(args.start).replace(tzinfo=dt.timezone.utc)
        end = dt.datetime.fromisoformat(args.end).replace(tzinfo=dt.timezone.utc)
    else:
        parser.error("give --gannon, or both --start and --end")

    if args.series:
        print(json.dumps(published_series(start, end, root=args.root), indent=2)[:4000])
        return 0

    report = ingest_range(start, end, root=args.root, force=args.force)
    print(json.dumps(report, indent=2))
    return 1 if report.get("halted") else 0


if __name__ == "__main__":
    raise SystemExit(main())
