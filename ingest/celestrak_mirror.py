#!/usr/bin/env python3
"""Conservative CelesTrak mirror for the Space Environment Explorer.

Only the VPS may run this program.  Every other component reads its cache.

The safety contract is deliberately stronger than a timer:

* CelesTrak's large ``GROUP=active`` GP file is never requested.  Space-Track
  already supplies the site's orbital elements, so that download was duplicate
  data and violated the spirit of "only download what you need."
  This is ENFORCED, not merely intended: ``celestrak_groups.FORBIDDEN_GP_GROUPS``
  names it, ``GROUP_LIST_PROBLEMS`` below refuses to start a run that configures
  it, ``gp_url()`` refuses to build the URL, and ``_validate_url()`` refuses to
  open a socket for it however the URL was built.  On 2026-08-26 the previous
  version of this file carried this same paragraph while the code beneath it
  downloaded that file every two hours; a sentence is not a guard.
* SATCAT's small directory is checked at most once per day.  The full SATCAT
  is downloaded only when its published file signature differs from the last
  signature successfully applied locally.  The six-hour global outbound gate
  remains independent, so intervening eligible runs can rotate weekly groups
  without re-asking the directory question.
* Mission-category groups are requested at most weekly, one at a time.
* Every repeat request is CONDITIONAL.  ``ETag`` and ``Last-Modified`` are
  recorded next to each cached body, and the next request for that dataset
  carries ``If-None-Match`` / ``If-Modified-Since``.  HTTP 304 is a first-class
  success: no body is downloaded, the cache's freshness stamp is renewed, and
  nothing halts.  Before 2026-08-27 this program could not receive a 304 at all,
  so a local clock decided when to re-ask and CelesTrak answered the fourth
  identical download of the day with HTTP 403.  An interval is a floor on how
  often we may ask; it was never permission to ask.
* A process can make at most two requests.  There are no retries, redirects,
  proxy routes, or command-line cadence bypasses.
* The first non-200-and-non-304 response, transport error, empty/malformed
  body, or HTTP-200 ``Invalid query`` response writes a permanent halt marker,
  alerts a human, and prevents every later timer run from opening a socket until
  an operator records why the halt is safe to clear.

This follows CelesTrak's current usage policy and its one-download-per-update
enforcement posture.  When in doubt, fetch less and keep serving the validated
last-known-good cache.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import hashlib
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

if str(Path(__file__).resolve().parents[1]) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ingest import celestrak_groups  # noqa: E402
from ingest.celestrak_groups import (  # noqa: E402
    FORBIDDEN_GP_GROUPS,
    GP_PATH,
    ForbiddenCelestrakGroup,
    InvalidCelestrakGroup,
    forbidden_gp_groups,
    forbidden_gp_reason,
    gp_url,
    group_from_url,
    ledger_sentence,
    malformed_group_names,
    quarantined_groups,
    read_ledger,
    record_invalid_group,
    validate_group_body,
)


# Entity boundary: CelesTrak is the LLC/VPS lane.  Space-Track is the personal
# officer-account/bigmem lane.  Crossing them is a legal-identity error.
CELESTRAK_HOST = "openclaw-ash-1"


def enforce_entity_boundary() -> None:
    host = socket.gethostname()
    if host != CELESTRAK_HOST:
        raise SystemExit(
            f"REFUSING TO RUN on host {host!r}. CelesTrak is fetched only from "
            f"the VPS ({CELESTRAK_HOST}), under the LLC identity."
        )


ROOT = Path(__file__).resolve().parent
CACHE = ROOT / "cache"
STATE = ROOT / "state"
HALT_MARKER = STATE / "HALTED.json"
SATCAT_APPLIED = STATE / "satcat-applied-signature.json"
LAST_ATTEMPT = STATE / "last-request-at.json"
# Cache validators live in STATE, not beside the body in CACHE, because STATE is
# 0700/0600 and is where this program's bookkeeping belongs.  They are BOUND to
# the body by sha256, so if the two ever drift -- a restored cache, a hand-edited
# file, a partial rsync -- the binding fails and the next request simply goes out
# unconditionally.  Drift is therefore safe by construction, never a false 304.
VALIDATORS = STATE / "http-validators.json"
VALIDATOR_SCHEMA = 1
LOG = Path("/var/log/celestrak-mirror.log")

CONTACT = "sean@theinformed.org"
USER_AGENT = (
    "theinformed.org-space-teaching-aid/2.0 "
    f"(non-commercial teaching site; contact: {CONTACT})"
)

BASE = "https://celestrak.org"
# NOT the forbidden bulk file. ``GROUP=active`` on satcat/records.php is the
# small operational-status catalogue, which is the one thing CelesTrak gives the
# site that Space-Track cannot: without it about 2,600 spacecraft dead since the
# 1960s displace working ones. The forbidden file is GROUP=active on
# NORAD/elements/gp.php, a different endpoint. Do not conflate them; the
# 2026-08-26 incident was nearly mis-read because the two share a query string.
SATCAT_ACTIVE = f"{BASE}/satcat/records.php?GROUP=active&FORMAT=json"
SATCAT_DIR = f"{BASE}/satcat/jsonDir.php"

# Preserve four evenly-spaced opportunities per day for the nineteen weekly
# category groups, but ask the SATCAT directory question only once per day.
# Both post-hardening 503s (2026-08-30 and 2026-09-02) came from jsonDir.php,
# and 13 of its first 26 replies were byte-identical to what we already held.
# Space-Track remains the sole orbital-elements source, so a daily operational-
# status refresh is sufficient for this teaching site's optional metadata.
OUTBOUND_INTERVAL = 6 * 60 * 60
DIR_INTERVAL = 24 * 60 * 60
GROUP_INTERVAL = 7 * 24 * 60 * 60
GROUPS_PER_RUN = 1
MAX_REQUESTS_PER_RUN = 2
POLITE_GAP = 10.0
MAX_RESPONSE_BYTES = 32 * 1024 * 1024

# Every group below contributes mission evidence not safely derivable from a
# name.  Large constellation groups and duplicate subsets are intentionally
# absent.  These are checked offline before any request is possible.
GROUPS = [
    "science", "geodetic", "amateur", "weather", "resource",
    "engineering", "education", "military", "radar", "cubesat",
    "other-comm", "stations", "gnss", "nnss", "musson", "sarsat",
    "argos", "dmc", "tdrss",
]
# Two different questions, both answered offline before any socket can open:
# malformed_group_names() asks "could CelesTrak possibly serve this name", and
# forbidden_gp_groups() asks "are we entitled to ask for it". A non-empty list
# makes run() log every problem and exit without opening a socket.
GROUP_LIST_PROBLEMS = malformed_group_names(GROUPS) + forbidden_gp_groups(GROUPS)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """Turn every redirect into an HTTP error instead of following it."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001, D401
        return None


# Ignore HTTP(S)_PROXY variables explicitly.  Sean's rule is direct from the
# VPS, and a future environment change must not silently reroute this lane.
DIRECT_OPENER = urllib.request.build_opener(
    urllib.request.ProxyHandler({}),
    NoRedirect(),
)


class Halted(RuntimeError):
    """The permanent halt marker has been written; no more requests are allowed."""


@dataclass
class FetchResult:
    """One completed request.

    ``notModified`` distinguishes the two shapes of success.  On a 304 the body
    is the one we already held on disk, re-read rather than re-downloaded, so
    callers that need to inspect it do not have to care which happened.
    """

    status: int
    body: bytes
    not_modified: bool

    @property
    def downloaded_bytes(self) -> int:
        return 0 if self.not_modified else len(self.body)


@dataclass
class RequestBudget:
    limit: int = MAX_REQUESTS_PER_RUN
    used: int = 0

    @property
    def remaining(self) -> int:
        return max(0, self.limit - self.used)

    def claim(self, dataset: str, url: str) -> None:
        if self.used >= self.limit:
            raise RuntimeError(
                f"offline request-budget guard refused {dataset}: "
                f"{self.used}/{self.limit} requests already claimed"
            )
        self.used += 1
        # Logged before the socket opens, so failed attempts count too.
        _atomic_write(
            LAST_ATTEMPT,
            (json.dumps({
                "at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                "dataset": dataset,
            }, indent=2) + "\n").encode(),
            mode=0o600,
        )
        log(f"REQUEST START {self.used}/{self.limit} dataset={dataset} url={url}")


def log(message: str) -> None:
    line = f"{dt.datetime.now(dt.timezone.utc):%Y-%m-%dT%H:%M:%SZ} {message}"
    print(line, flush=True)
    try:
        with LOG.open("a") as handle:
            handle.write(line + "\n")
    except OSError:
        pass


def _atomic_write(path: Path, body: bytes, *, mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(body)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(temporary)


def alert_human(summary: str, detail: str) -> None:
    """Tell Sean through Bob; alert failure must never mask the halt."""
    message = (
        f"CelesTrak mirror HALTED: {summary}. No further CelesTrak request will be "
        "made until an operator records the investigation and clears the marker. "
        "The space site continues from Space-Track and validated CelesTrak cache. "
        f"Detail: {detail}. Local record: {HALT_MARKER}."
    )
    try:
        subprocess.run(
            [
                "docker", "exec", "openclaw-openclaw-gateway-1", "openclaw", "cron", "create",
                "--at", "+1m", "--delete-after-run", "--announce",
                "--channel", "discord", "--to", "user:432502319473754112",
                "--name", "celestrak-mirror-halt", "--message", message,
            ],
            check=False,
            capture_output=True,
            timeout=60,
        )
    except Exception as error:  # noqa: BLE001
        log(f"ALERT FAILED (halt remains in force): {error}")


def _classify_error_body(body: bytes) -> str:
    text = body[:4096].decode("utf-8", "replace").lower()
    if "has not updated since your last successful" in text:
        return "one-download-per-update: data unchanged since last success"
    if "firewall" in text or "blocked" in text:
        return "access block or firewall notice"
    if text.strip():
        return "unclassified upstream error body"
    return "no upstream error body"


def _safe_excerpt(body: bytes) -> str:
    # Stored only in root-owned state, never printed or copied into Discord.
    return body[:4096].decode("utf-8", "replace").strip()


def halt(status: int | str, url: str, *, response_body: bytes = b"") -> None:
    STATE.mkdir(parents=True, exist_ok=True)
    with contextlib.suppress(OSError):
        STATE.chmod(0o700)
    marker = {
        "at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "status": status,
        "url": url,
        "classification": _classify_error_body(response_body),
        "responseExcerpt": _safe_excerpt(response_body),
        "responseSha256": hashlib.sha256(response_body).hexdigest() if response_body else None,
        "note": (
            "Permanent safety halt. A human must investigate and record a reason before "
            "clearing it. Timer runs remain socket-free while this file exists."
        ),
    }
    _atomic_write(HALT_MARKER, (json.dumps(marker, indent=2) + "\n").encode(), mode=0o600)
    log(
        f"HALT status={status!r} classification={marker['classification']!r} "
        f"url={url}; all later CelesTrak requests stopped"
    )
    alert_human(
        f"{url.split('?')[0]} returned {status}",
        f"classification={marker['classification']}; response sha256={marker['responseSha256']}",
    )


def halted_reason() -> dict[str, Any] | None:
    if not HALT_MARKER.exists():
        return None
    try:
        marker = json.loads(HALT_MARKER.read_text())
    except (OSError, json.JSONDecodeError):
        return {"status": "unreadable halt marker", "note": "do not query"}
    return marker if isinstance(marker, dict) else {"status": "invalid halt marker", "note": "do not query"}


# ---------------------------------------------------------------------------
# Conditional requests.
#
# CelesTrak's rule is one download per update, and since 2026-03-26 it is
# ENFORCED: asking again for a set that has not changed can be answered with
# HTTP 403.  On 2026-08-26 that is exactly what happened here.  The honest way to
# ask "has this changed?" is the one HTTP has always had -- send the validator
# the server gave us last time and let the server answer 304 if it has not.  That
# turns a re-ask from a policy violation into the polite question the policy
# actually wants, and it moves the freshness decision from OUR clock to THEIR
# data.
# ---------------------------------------------------------------------------


def _read_validators() -> dict[str, Any]:
    try:
        payload = json.loads(VALIDATORS.read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    entries = payload.get("datasets")
    return entries if isinstance(entries, dict) else {}


def _write_validators(entries: dict[str, Any]) -> None:
    payload = {"schema": VALIDATOR_SCHEMA, "datasets": entries}
    _atomic_write(
        VALIDATORS,
        (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode(),
        mode=0o600,
    )


def _body_fingerprint(path: Path) -> dict[str, Any] | None:
    """What we hold on disk right now, or None if we hold nothing readable."""
    try:
        raw = path.read_bytes()
    except OSError:
        return None
    if not raw.strip():
        return None
    return {"bodyBytes": len(raw), "bodySha256": hashlib.sha256(raw).hexdigest()}


def _header(headers: Any, name: str) -> str | None:
    """One response header, tolerating a mapping, a Message, or nothing at all."""
    try:
        value = headers.get(name)
    except AttributeError:
        return None
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None


def conditional_headers(dataset: str, destination: Path) -> dict[str, str]:
    """Revalidate only a body we still hold, byte for byte.

    A validator without its body is worse than no validator: a 304 would tell us
    the data is unchanged while we have nothing to serve.  So the sha256 recorded
    with the validator must still match the file on disk, or we ask outright.
    """
    entry = _read_validators().get(dataset)
    if not isinstance(entry, dict):
        return {}
    etag = entry.get("etag")
    modified = entry.get("lastModified")
    if not (isinstance(etag, str) and etag.strip()) and not (isinstance(modified, str) and modified.strip()):
        # Tracked, but the server never gave us anything to send back. Return
        # before the fingerprint check so a legitimately changed body does not
        # produce a drift warning about validators that do not exist.
        return {}
    held = _body_fingerprint(destination)
    if held is None:
        return {}
    if (entry.get("bodySha256"), entry.get("bodyBytes")) != (held["bodySha256"], held["bodyBytes"]):
        log(
            f"{dataset}: cached body no longer matches its recorded validators; "
            "asking unconditionally rather than risking a 304 for data we do not hold"
        )
        return {}
    headers: dict[str, str] = {}
    # Sent verbatim.  RFC 9110 makes these opaque strings; reformatting a date or
    # stripping a weak-ETag prefix is how a conditional request silently stops
    # matching and starts costing a full download again.
    if isinstance(etag, str) and etag.strip():
        headers["If-None-Match"] = etag.strip()
    if isinstance(modified, str) and modified.strip():
        headers["If-Modified-Since"] = modified.strip()
    return headers


def note_unchanged_download(dataset: str, previous: dict[str, Any] | None, body: bytes) -> bool:
    """Did we just re-download bytes we already had?

    This is the ONLY mechanism that detects a wasted request against an endpoint
    that offers no validator, and it is not hypothetical: the 2026-08-26 incident
    was diagnosed exactly this way, from a log showing the same set arriving at
    6,902,667 bytes three times running before CelesTrak refused the fourth ask.
    The program should be able to see that about itself rather than needing a
    human to read a day of logs.
    """
    if not previous:
        return False
    same = (
        previous.get("bodySha256") == hashlib.sha256(body).hexdigest()
        and previous.get("bodyBytes") == len(body)
    )
    if same:
        log(
            f"{dataset}: WASTED REQUEST -- {len(body):,} bytes byte-identical to the copy "
            "we already held. The data had not changed and we asked anyway; this is the "
            "shape CelesTrak answered with HTTP 403 on 2026-08-26."
        )
    return same


def record_validators(dataset: str, url: str, headers: Any, destination: Path, body: bytes = b"") -> None:
    """Remember what the server said, bound to the body it said it about.

    The entry is kept even when CelesTrak offers no validator at all -- which,
    measured against the live endpoints on 2026-08-27, is the case for every one
    of them.  The etag/lastModified fields are then null and no conditional
    request is possible, but the body fingerprint and the change ledger below
    still record whether our weekly interval is asking for data that moves.
    """
    etag = _header(headers, "ETag")
    modified = _header(headers, "Last-Modified")
    entries = _read_validators()
    previous = entries.get(dataset) if isinstance(entries.get(dataset), dict) else None
    held = _body_fingerprint(destination)
    if held is None:
        entries.pop(dataset, None)
        _write_validators(entries)
        return
    unchanged = note_unchanged_download(dataset, previous, body) if body else False
    entry: dict[str, Any] = {
        "url": url,
        "etag": etag,
        "lastModified": modified,
        "conditionalPossible": bool(etag or modified),
        "recordedAt": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "unchangedRepeats": (previous or {}).get("unchangedRepeats", 0) + 1 if unchanged else 0,
        "lastChangedAt": (
            (previous or {}).get("lastChangedAt")
            if unchanged
            else dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        ),
        **held,
    }
    entries[dataset] = entry
    _write_validators(entries)
    if etag or modified:
        offered = ", ".join(
            part for part in (
                f"ETag: {etag}" if etag else "",
                f"Last-Modified: {modified}" if modified else "",
            ) if part
        )
        log(f"{dataset}: recorded validators for the next request ({offered})")
    elif not previous or previous.get("conditionalPossible") is not False:
        # Said once per dataset, not once per run.  This is a standing property
        # of CelesTrak's PHP endpoints, not an incident.
        log(
            f"{dataset}: upstream offered no ETag or Last-Modified, so the next request "
            "for it cannot be conditional; freshness falls back to the interval and the "
            "byte-identical check"
        )


def _refresh_validators_after_304(dataset: str, headers: Any, destination: Path) -> None:
    """A 304 may carry a new ETag; keep the old one when it carries nothing."""
    entries = _read_validators()
    entry = entries.get(dataset)
    if not isinstance(entry, dict):
        return
    etag = _header(headers, "ETag")
    modified = _header(headers, "Last-Modified")
    if etag:
        entry["etag"] = etag
    if modified:
        entry["lastModified"] = modified
    entry["lastNotModifiedAt"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    held = _body_fingerprint(destination)
    if held:
        entry.update(held)
    entries[dataset] = entry
    _write_validators(entries)


def _honor_not_modified(
    *,
    dataset: str,
    url: str,
    destination: Path,
    headers: Any,
    group: str | None,
) -> FetchResult:
    """Accept HTTP 304 as success, or halt if we cannot honestly accept it.

    Renewing the cache file's mtime is the whole point: freshness in this program
    is keyed to that mtime, so a 304 has to re-arm the interval.  Otherwise every
    run would re-ask a question the server has already answered -- which is the
    behaviour that produced the 403.
    """
    body = destination.read_bytes() if destination.exists() else b""
    if not body.strip():
        halt("HTTP 304 but no cached body to honor it with", url)
        raise Halted(f"{dataset}: 304 without a cached body")
    try:
        _validate_dataset(body, url=url, dataset=dataset, group=group)
    except (InvalidCelestrakGroup, ValueError, TypeError) as error:
        halt(f"HTTP 304 but the cached body is invalid: {error}", url)
        raise Halted(f"{dataset}: 304 over an invalid cache") from error
    os.utime(destination, None)
    _refresh_validators_after_304(dataset, headers, destination)
    log(
        f"{dataset}: HTTP 304 Not Modified -- upstream data unchanged, "
        f"nothing downloaded, {len(body):,} cached bytes kept and re-dated"
    )
    return FetchResult(304, body, True)


# The cache files this program owns, and the dataset name each belongs to.  The
# mapping is written out rather than derived so that a file nothing requests any
# more -- gp-active.json, the 6.9 MB leftover of the forbidden download -- cannot
# be seeded into the ledger and quietly look like a live dataset again.
def _dataset_for_cache_file(path: Path) -> str | None:
    if path.name == "satcat-dir.json":
        return "satcat-directory"
    if path.name == "satcat-active.json":
        return "satcat-active"
    if path.name.startswith("group-") and path.suffix == ".json":
        return path.stem
    return None


def _seed_change_ledger_from_existing_cache() -> None:
    """One-time local migration; it never contacts CelesTrak.

    Without a baseline the first download of every dataset after this ships would
    look like a change, and the byte-identical check -- the only wasted-request
    evidence available while CelesTrak offers no validators -- would not start
    working until the second one.  ``lastChangedAt`` is deliberately left null:
    we know what these bytes ARE, not when they last changed.
    """
    entries = _read_validators()
    seeded = 0
    for path in sorted(CACHE.glob("*.json")):
        dataset = _dataset_for_cache_file(path)
        if dataset is None or dataset in entries:
            continue
        held = _body_fingerprint(path)
        if held is None:
            continue
        entries[dataset] = {
            "url": None,
            "etag": None,
            "lastModified": None,
            "conditionalPossible": False,
            "recordedAt": None,
            "seededFromCacheAt": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "unchangedRepeats": 0,
            "lastChangedAt": None,
            **held,
        }
        seeded += 1
    if seeded:
        _write_validators(entries)
        log(f"seeded the change ledger from {seeded} cached file(s); no request made")


def _validate_url(url: str) -> None:
    parsed = urllib.parse.urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname != "celestrak.org"
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port not in (None, 443)
    ):
        raise ValueError(f"offline URL guard refused non-canonical CelesTrak URL: {url}")
    # The backstop. Whatever built this string -- gp_url(), a future refactor, a
    # hand-written f-string in a hurry -- a forbidden GP group does not get a
    # socket. This runs before RequestBudget.claim(), so a refused URL does not
    # even spend a request slot.
    if parsed.path == GP_PATH:
        group = group_from_url(url)
        reason = forbidden_gp_reason(group)
        if reason:
            raise ForbiddenCelestrakGroup(str(group), "_validate_url before the socket", reason)


def _read_response(response) -> bytes:  # noqa: ANN001
    body = response.read(MAX_RESPONSE_BYTES + 1)
    if len(body) > MAX_RESPONSE_BYTES:
        raise RuntimeError(f"response exceeds {MAX_RESPONSE_BYTES:,} byte safety ceiling")
    return body


def satcat_signature(body: bytes) -> dict[str, Any]:
    try:
        rows = json.loads(body)
    except json.JSONDecodeError as error:
        raise ValueError(f"SATCAT directory is not JSON: {error}") from error
    if not isinstance(rows, list):
        raise ValueError("SATCAT directory is not a JSON array")
    matches = [row for row in rows if isinstance(row, dict) and row.get("FILE_NAME") == "satcat.csv"]
    if len(matches) != 1:
        raise ValueError(f"SATCAT directory names satcat.csv {len(matches)} times, expected once")
    row = matches[0]
    try:
        size = int(row["FILE_SIZE"])
        modified = str(row["FILE_MTIME"]).strip()
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("SATCAT directory lacks a valid FILE_SIZE/FILE_MTIME") from error
    if size < 1_000_000 or not modified:
        raise ValueError(f"implausible SATCAT directory signature: size={size}, mtime={modified!r}")
    return {"file": "satcat.csv", "size": size, "mtime": modified}


def _validate_dataset(body: bytes, *, url: str, dataset: str, group: str | None) -> None:
    if dataset == "satcat-directory":
        satcat_signature(body)
        return
    records = validate_group_body(body, url=url, group=group)
    if not isinstance(records, list):
        raise ValueError(f"{dataset} response is not a JSON array")


def fetch(
    url: str,
    destination: Path,
    *,
    budget: RequestBudget,
    dataset: str,
    group: str | None = None,
    revalidate: bool = True,
) -> FetchResult:
    """Make exactly one direct request.  Every surprise becomes a permanent halt.

    Two answers are successes.  200 means new data, which is written to the
    cache.  304 means the data has not changed since the validator we were given,
    which costs no body at all and is precisely what CelesTrak's one-download-per
    -update rule asks us to do instead of downloading the same bytes again.
    Everything else -- 301, 403, 404, 5xx, a redirect, a transport failure, an
    empty or malformed body, or an HTTP-200 "Invalid query" -- still halts.
    """
    _validate_url(url)
    conditional = conditional_headers(dataset, destination) if revalidate else {}
    budget.claim(dataset, url)
    if conditional:
        log(
            f"{dataset}: conditional request -- "
            + "; ".join(f"{name}: {value}" for name, value in sorted(conditional.items()))
        )
    request = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json", **conditional},
        method="GET",
    )
    body = b""
    response_headers: Any = {}
    try:
        with DIRECT_OPENER.open(request, timeout=60) as response:
            # Defensive: an opener whose error processor is bypassed can hand a
            # 304 back here rather than raising it.  Both doors lead to the same
            # room.
            if response.status == 304 and conditional:
                return _honor_not_modified(
                    dataset=dataset, url=url, destination=destination,
                    headers=response.headers, group=group,
                )
            if response.status != 200:
                body = _read_response(response)
                halt(response.status, url, response_body=body)
                raise Halted(f"{dataset}: HTTP {response.status}")
            response_headers = getattr(response, "headers", None) or {}
            body = _read_response(response)
    except urllib.error.HTTPError as error:
        # urllib routes 304 here, because its error processor treats every
        # non-2xx as an error.  A 304 we ASKED for is not one.
        if error.code == 304 and conditional:
            return _honor_not_modified(
                dataset=dataset, url=url, destination=destination,
                headers=getattr(error, "headers", None) or {}, group=group,
            )
        with contextlib.suppress(Exception):
            body = _read_response(error)
        halt(error.code, url, response_body=body)
        raise Halted(f"{dataset}: HTTP {error.code}") from error
    except (urllib.error.URLError, TimeoutError, OSError, RuntimeError) as error:
        halt(f"transport: {error}", url)
        raise Halted(f"{dataset}: transport failure") from error

    if not body.strip():
        halt("HTTP 200 empty body", url)
        raise Halted(f"{dataset}: empty body")

    try:
        _validate_dataset(body, url=url, dataset=dataset, group=group)
    except InvalidCelestrakGroup as error:
        if group is not None:
            record_invalid_group(STATE, error, seen_by="ingest/celestrak_mirror.py")
        halt(f"HTTP 200 invalid response: {error.detail}", url, response_body=body)
        raise Halted(f"{dataset}: invalid CelesTrak response") from error
    except (ValueError, TypeError) as error:
        halt(f"HTTP 200 invalid response: {error}", url, response_body=body)
        raise Halted(f"{dataset}: invalid response") from error

    _atomic_write(destination, body, mode=0o644)
    log(f"fetched {len(body):,} bytes -> {destination.name}")
    # Recorded only after the body is safely on disk, so a validator can never
    # outlive the bytes it describes.  The body is passed in as well so the
    # change ledger can compare it against what we held a moment ago.
    record_validators(dataset, url, response_headers, destination, body)
    return FetchResult(200, body, False)


def age_seconds(path: Path) -> float:
    return float("inf") if not path.exists() else time.time() - path.stat().st_mtime


def _read_applied_signature() -> dict[str, Any] | None:
    try:
        payload = json.loads(SATCAT_APPLIED.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    signature = payload.get("signature") if isinstance(payload, dict) else None
    return signature if isinstance(signature, dict) else None


def _mark_satcat_applied(signature: dict[str, Any], *, reason: str) -> None:
    payload = {
        "appliedAt": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "signature": signature,
        "reason": reason,
    }
    _atomic_write(SATCAT_APPLIED, (json.dumps(payload, indent=2) + "\n").encode(), mode=0o600)


def _seed_applied_signature_from_existing_cache() -> None:
    """One-time local migration; it never contacts CelesTrak."""
    directory = CACHE / "satcat-dir.json"
    catalog = CACHE / "satcat-active.json"
    if SATCAT_APPLIED.exists() or not directory.exists() or not catalog.exists():
        return
    if catalog.stat().st_mtime < directory.stat().st_mtime:
        return
    try:
        signature = satcat_signature(directory.read_bytes())
    except (OSError, ValueError):
        return
    _mark_satcat_applied(signature, reason="seeded from validated pre-v2 cache; no request made")
    log("seeded SATCAT applied signature from existing validated cache; no request made")


def run() -> int:
    marker = halted_reason()
    if marker:
        log(f"still halted since {marker.get('at')} ({marker.get('status')}); not querying")
        return 0
    if GROUP_LIST_PROBLEMS:
        for name, reason in GROUP_LIST_PROBLEMS:
            log(f"CONFIGURATION ERROR: group {name!r} {reason}")
        log("refusing to query CelesTrak until GROUPS is fixed")
        return 4

    CACHE.mkdir(parents=True, exist_ok=True)
    STATE.mkdir(parents=True, exist_ok=True)
    _seed_applied_signature_from_existing_cache()
    _seed_change_ledger_from_existing_cache()
    if age_seconds(LAST_ATTEMPT) < OUTBOUND_INTERVAL:
        log("outbound cadence not due; no request made")
        log("run complete; 0 request(s) made")
        return 0
    budget = RequestBudget()

    try:
        directory = CACHE / "satcat-dir.json"
        if age_seconds(directory) >= DIR_INTERVAL:
            # On a 304 this returns the body we already held, so the signature
            # gate below reads the same either way.  Recomputing it even on a 304
            # is deliberate: it also catches the case where the directory never
            # changed but a previous full-SATCAT fetch failed to be applied.
            result = fetch(
                SATCAT_DIR,
                directory,
                budget=budget,
                dataset="satcat-directory",
            )
            signature = satcat_signature(result.body)
            if signature != _read_applied_signature():
                time.sleep(POLITE_GAP)
                fetch(
                    SATCAT_ACTIVE,
                    CACHE / "satcat-active.json",
                    budget=budget,
                    dataset="satcat-active",
                    group="active",
                )
                _mark_satcat_applied(signature, reason="full SATCAT fetched for this directory signature")
            else:
                log("SATCAT directory signature unchanged; full catalogue not requested")

        quarantined = quarantined_groups(STATE)
        # This list answers "may we ASK yet", never "must we DOWNLOAD".  The
        # answer to the second question belongs to CelesTrak, and it gives it as
        # 200 or 304 to the conditional request fetch() builds from the validators
        # recorded last time.
        due = [
            group for group in GROUPS
            if group not in quarantined
            and age_seconds(CACHE / f"group-{group}.json") >= GROUP_INTERVAL
        ]
        if due and budget.remaining:
            if budget.used:
                time.sleep(POLITE_GAP)
            group = due[0]
            fetch(
                gp_url(group, base=BASE, where="ingest/celestrak_mirror.py GROUPS"),
                CACHE / f"group-{group}.json",
                budget=budget,
                dataset=f"group-{group}",
                group=group,
            )
            # No branch on the result on purpose.  A 304 has already re-dated the
            # cache file inside fetch(), which is the only thing "due" reads, so
            # an unchanged group falls out of the due list exactly like a
            # downloaded one -- without a second copy of the same bytes.
            if len(due) > 1:
                log(f"{len(due) - 1} more group(s) due; deferred to later runs on purpose")
    except Halted as error:
        log(f"run stopped: {error}")
        return 2

    log(f"run complete; {budget.used} request(s) made")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--status", action="store_true", help="report cache and halt state; no network")
    parser.add_argument("--clear-halt", action="store_true", help="clear only after investigation")
    parser.add_argument("--reason", help="required audit reason when --clear-halt is used")
    parser.add_argument(
        "--clear-invalid-groups",
        action="store_true",
        help="forget quarantined names only after removing them from GROUPS",
    )
    args = parser.parse_args()
    enforce_entity_boundary()

    if args.clear_halt:
        reason = (args.reason or "").strip()
        if len(reason) < 12:
            print("refusing to clear: --reason must record the investigation", file=sys.stderr)
            return 2
        if HALT_MARKER.exists():
            previous = halted_reason()
            # The marker is ARCHIVED, never deleted.  The incident history is the
            # only durable record of what this lane was refused and why, and a
            # cleared halt with no trace is how the same 403 gets re-diagnosed
            # from scratch six months from now.
            stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            archive = STATE / "halts" / f"HALTED-{stamp}.json"
            record = {
                "marker": previous,
                "clearedAt": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                "clearedBy": os.environ.get("SUDO_USER") or os.environ.get("USER") or "root",
                "reason": reason,
            }
            _atomic_write(archive, (json.dumps(record, indent=2) + "\n").encode(), mode=0o600)
            log(
                "halt cleared by operator after recorded investigation: "
                f"reason={reason!r}; previous_status={(previous or {}).get('status')!r}; "
                f"archived={archive}"
            )
            HALT_MARKER.unlink()
            print(f"halt cleared; incident archived to {archive}")
        else:
            print("no halt in place")
        return 0

    if args.clear_invalid_groups:
        cleared = celestrak_groups.clear_ledger(STATE)
        still_listed = sorted(set(cleared) & set(GROUPS))
        print(f"cleared: {', '.join(cleared) if cleared else 'nothing was quarantined'}")
        if still_listed:
            print("refusing: remove still-configured names before clearing their ledger", file=sys.stderr)
            return 1
        return 0

    if args.status:
        marker = halted_reason()
        print(f"halted: {bool(marker)}" + (f" -> {marker}" if marker else ""))
        print(ledger_sentence(read_ledger(STATE)))
        print(f"request ceiling per run: {MAX_REQUESTS_PER_RUN}; no retries; redirects disabled")
        stored = _read_validators()
        conditional = [
            name for name, entry in stored.items()
            if isinstance(entry, dict) and entry.get("conditionalPossible")
        ]
        print(
            f"datasets tracked: {len(stored)}; "
            f"conditional requests possible for {len(conditional)} of them"
        )
        if stored and not conditional:
            print(
                "  CelesTrak's PHP endpoints send neither ETag nor Last-Modified "
                "(measured 2026-08-27), so no 304 is obtainable; the machinery is in "
                "place and inert until they do."
            )
        for name in sorted(stored):
            entry = stored[name] if isinstance(stored[name], dict) else {}
            print(
                f"  {name:22s} ETag={entry.get('etag') or '-'} "
                f"Last-Modified={entry.get('lastModified') or '-'} "
                f"unchangedRepeats={entry.get('unchangedRepeats', 0)} "
                f"lastChanged={entry.get('lastChangedAt') or '-'}"
            )
        print(
            f"gp.php groups refused by contract: {len(FORBIDDEN_GP_GROUPS)} "
            f"(including 'active', the 2026-08-26 HTTP 403); "
            "satcat/records.php?GROUP=active is a different endpoint and is allowed"
        )
        for name, reason in GROUP_LIST_PROBLEMS:
            print(f"CONFIGURATION ERROR: group {name!r} {reason}")
        for path in sorted(CACHE.glob("*.json")):
            print(
                f"  {path.name:34s} {age_seconds(path)/3600:6.1f} h old  "
                f"{path.stat().st_size:>9,} bytes"
            )
        return 0

    return run()


if __name__ == "__main__":
    sys.exit(main())
