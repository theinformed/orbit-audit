#!/usr/bin/env python3
"""Space-Track ingest. Runs ONLY on the designated host, under a personal identity.

ENTITY SEPARATION - read this before changing anything here
-----------------------------------------------------------
This installation deliberately splits upstream access across two legal
identities, and the split is not a preference:

  CelesTrak   -> fetched ONLY from the VPS, which operates under the LLC.
                 See ingest/celestrak_mirror.py.
  space-track -> fetched ONLY from the designated host, using a personal
                 space-track.org account held by a serving officer.

The publishing server must never contact space-track.org. Doing so would put a personal
credential behind a commercial entity. The hostname guard below exists to make
that mistake impossible rather than merely discouraged, and it runs before
anything reads a credential or opens a socket.

Credentials
-----------
Never in this repository, never in a systemd unit, never synced anywhere. The
file lives on bigmem only:

    ~/.config/space-track/credentials      (mode 0600)
        SPACETRACK_IDENTITY=you@example.mil
        SPACETRACK_PASSWORD=...

Rate limits, quoted from their API Use Guidelines
-------------------------------------------------
Global ceiling:
    "Limit API queries to less than 30 requests per 1 minute(s) and 300 requests
     per 1 hour(s)"

Per dataset, from their published table. Exceeding these is the specific thing
that gets an account suspended: "do not exceed the following data retrieval rates
for your automated scripts or your account may be suspended".

    GP (aka TLEs)  1 / hour   "Please randomly choose a minute that is not at the
                               top or bottom of the hour for your hourly scripts
                               to send this query. Add
                               /decay_date/null-val/epoch/%3Enow-10/ to the URL to
                               ensure that you only retrieve propagable
                               ephemerides for on-orbit objects."
    SATCAT         1 / day    "Once per day after 1700 (UTC) for SATCAT data."

All three are honoured below: the GP query is exactly their recommended form,
SATCAT is gated on a 24-hour interval AND the 1700Z boundary, and the systemd
timer fires at a randomised off-peak minute rather than on the hour.

They also say: "Do not use multiple space-track.org user accounts simultaneously
to circumvent our API guidelines." One account, one machine, one session per run.

As with the CelesTrak mirror, any non-200 halts the run and reports to a human.
Nothing here retries in a loop.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar
from pathlib import Path

# ---------------------------------------------------------------------------
# The boundary. Do not relax without an explicit decision to change the rule.
# ---------------------------------------------------------------------------
SPACETRACK_HOST = "bigmem-PC"


def enforce_entity_boundary() -> None:
    host = socket.gethostname()
    if host != SPACETRACK_HOST:
        raise SystemExit(
            f"REFUSING TO RUN on host {host!r}. space-track.org is queried only from "
            f"{SPACETRACK_HOST}, under Sean's personal account. The VPS operates under "
            "the LLC and must never contact space-track. If you are on the VPS and want "
            "orbital data, you want ingest/celestrak_mirror.py instead."
        )


ROOT = Path(__file__).resolve().parents[1]
MIRROR = ROOT / "runtime" / "spacetrack-mirror"
STATE = ROOT / "runtime" / "spacetrack-state"
HALT_MARKER = STATE / "HALTED.json"
CREDENTIALS = Path.home() / ".config" / "space-track" / "credentials"

BASE = "https://www.space-track.org"
LOGIN = f"{BASE}/ajaxauth/login"
LOGOUT = f"{BASE}/ajaxauth/logout"
# Bulk queries only, exactly as their documentation asks. One request each.
# Exactly the form space-track's own guidance recommends for hourly GP polling.
GP_QUERY = (
    f"{BASE}/basicspacedata/query/class/gp"
    "/decay_date/null-val/epoch/%3Enow-10"
    "/orderby/norad_cat_id/format/json"
)
SATCAT_QUERY = f"{BASE}/basicspacedata/query/class/satcat/DECAY/null-val/CURRENT/Y/orderby/NORAD_CAT_ID/format/json"

GP_INTERVAL = 60 * 60           # their published GP rate is 1 / hour
SATCAT_INTERVAL = 24 * 60 * 60  # their published SATCAT rate is 1 / day
SATCAT_EARLIEST_UTC_HOUR = 17   # "once per day after 1700 (UTC)"
POLITE_GAP = 5.0
USER_AGENT = "theinformed.org-space-teaching-aid/1.0 (non-commercial teaching site)"


def log(message: str) -> None:
    print(f"{dt.datetime.now(dt.timezone.utc):%Y-%m-%dT%H:%M:%SZ} {message}", flush=True)


class Halted(RuntimeError):
    """Raised the moment space-track answers with anything other than 200."""


def load_credentials() -> tuple[str, str]:
    if not CREDENTIALS.exists():
        raise SystemExit(
            f"No space-track credentials at {CREDENTIALS}.\n"
            "Create it yourself (this tool will never write it, and it must never enter git):\n"
            "  mkdir -p ~/.config/space-track\n"
            "  printf 'SPACETRACK_IDENTITY=%s\\nSPACETRACK_PASSWORD=%s\\n' 'you@example.mil' 'secret' \\\n"
            "    > ~/.config/space-track/credentials\n"
            "  chmod 600 ~/.config/space-track/credentials"
        )
    mode = CREDENTIALS.stat().st_mode & 0o777
    if mode & 0o077:
        raise SystemExit(
            f"{CREDENTIALS} is mode {mode:o}; refusing to read a credential other users can see. "
            "Run: chmod 600 " + str(CREDENTIALS)
        )
    values: dict[str, str] = {}
    for line in CREDENTIALS.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip()
    identity, password = values.get("SPACETRACK_IDENTITY"), values.get("SPACETRACK_PASSWORD")
    if not identity or not password:
        raise SystemExit(f"{CREDENTIALS} must define SPACETRACK_IDENTITY and SPACETRACK_PASSWORD")
    return identity, password


def halted_reason() -> dict | None:
    if not HALT_MARKER.exists():
        return None
    try:
        return json.loads(HALT_MARKER.read_text())
    except (OSError, json.JSONDecodeError):
        return {"note": "unreadable halt marker"}


def halt(status: int | str, url: str) -> None:
    STATE.mkdir(parents=True, exist_ok=True)
    # Never record the query string: it is harmless here, but keeping the habit
    # means a future authenticated URL can't leak into a log file.
    HALT_MARKER.write_text(json.dumps({
        "at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "status": status,
        "endpoint": urllib.parse.urlsplit(url).path,
        "note": "A human must investigate and clear this with --clear-halt.",
    }, indent=2) + "\n")
    log(f"HALT: {urllib.parse.urlsplit(url).path} returned {status}. All queries stopped.")


def age_seconds(path: Path) -> float:
    return float("inf") if not path.exists() else time.time() - path.stat().st_mtime


def run(force: bool = False) -> int:
    marker = halted_reason()
    if marker:
        log(f"still halted since {marker.get('at')} ({marker.get('status')}); not querying")
        return 0

    gp_path, satcat_path = MIRROR / "gp-active.json", MIRROR / "satcat-active.json"
    want_gp = force or age_seconds(gp_path) >= GP_INTERVAL
    # SATCAT is published once a day after 1700Z. Asking earlier just costs them
    # a query and returns yesterday's catalog.
    after_publication = dt.datetime.now(dt.timezone.utc).hour >= SATCAT_EARLIEST_UTC_HOUR
    want_satcat = force or (age_seconds(satcat_path) >= SATCAT_INTERVAL and after_publication)
    if not (want_gp or want_satcat):
        log("nothing due; not logging in")
        return 0

    identity, password = load_credentials()
    MIRROR.mkdir(parents=True, exist_ok=True)
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(CookieJar())
    )
    opener.addheaders = [("User-Agent", USER_AGENT)]

    def request(url: str, data: bytes | None = None) -> bytes:
        try:
            with opener.open(urllib.request.Request(url, data=data), timeout=180) as response:
                if response.status != 200:
                    halt(response.status, url)
                    raise Halted(f"HTTP {response.status}")
                body = response.read()
                # This log has always reported RECORDS, which is the useful
                # number for "did the ingest work" and no use at all for "what
                # did it cost". A GP pull is about 93 MB. Recorded on the raw
                # basis: len() after urllib has decoded the response is not
                # what came off the socket.
                try:
                    from ops import bandwidth  # noqa: PLC0415 - optional, never load-bearing

                    bandwidth.record_fetch(
                        len(body), family="space-track",
                        source="urllib response.read() length (decoded)",
                        run="spacetrack-ingest")
                except Exception:  # noqa: BLE001 - measurement must never break a fetch
                    pass
                return body
        except urllib.error.HTTPError as error:
            halt(error.code, url)
            raise Halted(f"HTTP {error.code}") from error
        except urllib.error.URLError as error:
            halt(f"transport: {error.reason}", url)
            raise Halted(str(error.reason)) from error

    fetched = 0
    try:
        request(LOGIN, urllib.parse.urlencode(
            {"identity": identity, "password": password}
        ).encode())
        log("authenticated")
        try:
            for due, url, destination, label in (
                (want_gp, GP_QUERY, gp_path, "GP"),
                (want_satcat, SATCAT_QUERY, satcat_path, "SATCAT"),
            ):
                if not due:
                    continue
                time.sleep(POLITE_GAP)
                body = request(url, None)
                records = json.loads(body)
                if not isinstance(records, list) or not records:
                    halt("empty or unexpected payload", url)
                    raise Halted(f"{label} payload unusable")
                temporary = destination.with_suffix(".next")
                temporary.write_bytes(body)
                temporary.replace(destination)
                fetched += 1
                log(f"{label}: {len(records):,} records -> {destination.name}")
        finally:
            # Always release the session, even on failure. Leaving sessions open
            # is one of the behaviours their API guidance asks callers to avoid.
            try:
                opener.open(urllib.request.Request(LOGOUT), timeout=60).close()
                log("logged out")
            except Exception:  # noqa: BLE001
                log("logout failed (session will expire on its own)")
    except Halted as error:
        log(f"run stopped: {error}")
        return 2

    log(f"run complete; {fetched} dataset(s) refreshed")
    return 0


def main() -> int:
    enforce_entity_boundary()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--clear-halt", action="store_true")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--check-credentials", action="store_true",
                        help="verify the credential file without contacting space-track")
    args = parser.parse_args()

    if args.clear_halt:
        if HALT_MARKER.exists():
            HALT_MARKER.unlink()
            print("halt cleared")
        else:
            print("no halt in place")
        return 0
    if args.check_credentials:
        identity, _ = load_credentials()
        print(f"credential file OK; identity {identity[:3]}***{identity[-12:]}")
        return 0
    if args.status:
        print(f"host: {socket.gethostname()} (allowed)")
        print(f"halted: {bool(halted_reason())}")
        print(f"credentials present: {CREDENTIALS.exists()}")
        for path in sorted(MIRROR.glob("*.json")) if MIRROR.exists() else []:
            print(f"  {path.name:24s} {age_seconds(path)/3600:6.1f} h old  {path.stat().st_size:>11,} bytes")
        return 0
    return run(force=args.force)


if __name__ == "__main__":
    sys.exit(main())
