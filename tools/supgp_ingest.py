"""T16a -- operator-derived element sets and operator ephemerides, beside the GP archive.

Registered in ``docs/t16a-ingest-registration-20260922.md``.  Read that first:
every constant below is a number the registration committed to before any byte
was fetched, and changing one here without changing it there is how a budget
stops being a budget.

Three things live in this module and they are deliberately separable:

1.  **Policy.**  Host gates, the verified set allowlist, the per-set interval,
    the per-process ceiling, the halt contract.  All of it is reachable
    offline, and every test exercises it without a socket.
2.  **Transport.**  One function, injectable, so that the policy tests cannot
    pass by never reaching the code they claim to guard.
3.  **Offline work.**  Parsing, archiving, and the comparison.  None of it
    touches the network, and none of it writes to the GP archive.

The route rule is not advice.  Supplemental element sets are requested from the
VPS and from nowhere else -- not from this workstation, not from a home
connection, not through a proxy, and not as a reachability check.  The operator
ephemerides are large and are fetched on the workstation, where they stay.
Both gates are checked before a socket can be created, and a refusal costs no
request.
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import gzip
import hashlib
import json
import math
import os
import socket
import sqlite3
import ssl
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable, Iterable, Sequence

try:  # as a package member, which is how the tests import it
    from tools import starlink_ephemeris
except ImportError:  # run directly from the tools directory
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import starlink_ephemeris  # noqa: E402

# ---------------------------------------------------------------------------
# Policy -- every value here is registered
# ---------------------------------------------------------------------------

# Each lane is pinned to one host, because a provider counts requests per
# address and two machines asking on the same account is how a research
# archive gets itself blocked. The hostname is an installation fact, so it is
# read from the environment with a placeholder that matches no real machine:
# an unconfigured checkout refuses to open a socket rather than fetching from
# wherever it happens to be run.
SUPGP_HOST = os.environ.get("SUPGP_FETCH_HOST", "supgp-lane.example.invalid")
STARLINK_HOST = os.environ.get("EPHEMERIS_FETCH_HOST",
                               "ephemeris-lane.example.invalid")

SUPGP_BASE = "https://celestrak.org/NORAD/elements/supplemental/sup-gp.php"
STARLINK_BASE = "https://api.starlink.com/public-files/ephemerides/"
STARLINK_MANIFEST = STARLINK_BASE + "MANIFEST.txt"

# Only set names verified from a source outside the provider may be requested.
# A guessed name costs a 404, and a 404 is one of the three statuses the
# provider counts toward its firewall threshold.  Adding a name is an amendment
# to the registration, and needs a verified spelling rather than a likely one.
VERIFIED_SUPGP_SETS: dict[str, str] = {
    "starlink": "LEO",
    "orbcomm": "LEO",
    "glonass": "MEO",
    "gps": "MEO",
    "intelsat": "GEO",
}

SUPGP_INTERVAL_SECONDS = 24 * 60 * 60
SUPGP_REQUESTS_PER_PROCESS = 4
SUPGP_GAP_SECONDS = 10.0

STARLINK_MANIFEST_INTERVAL_SECONDS = 8 * 60 * 60
STARLINK_FILES_PER_RUN = 250
STARLINK_GAP_SECONDS = 0.5

BODY_CEILING_BYTES = 32 * 1024 * 1024
TIMEOUT_SECONDS = 60.0

USER_AGENT = "theinformed.org-space-research/1.0 (non-commercial research archive)"

# Where the fetched products are kept. Installation-specific, so named by an
# environment variable with a placeholder that cannot resolve; the element
# mirror and the element archive are required arguments of the one subcommand
# that reads them.
DEFAULT_ROOT = Path(os.environ.get("SUPPLEMENTAL_ARCHIVE_ROOT",
                                   "supplemental-archive.not-configured"))

# The archive stores published elements as exact integers at these scales.
SCALE_MEAN_MOTION = 10**8
SCALE_ECCENTRICITY = 10**8
SCALE_ANGLE = 10**4
SCALE_BSTAR = 10**12

# The registered dedupe key.  The GP archive's key is the naive one and is kept
# here only so that a test can show what it costs: the provider states that one
# object can carry several supplemental element sets at one time, so the naive
# key silently drops data rather than refusing it.
REGISTERED_KEY = ("norad", "epoch_ms", "element_set_no", "set_name")
NAIVE_GP_KEY = ("norad", "epoch_ms")

COMPARISON_LEAD_HOURS = (0, 1, 3, 6, 12, 24, 48, 72)
EPOCH_GAP_CEILING_SECONDS = 24 * 60 * 60
MINIMUM_OBJECTS_FOR_QUANTILES = 30
QUANTILES = (0.05, 0.25, 0.50, 0.75, 0.95)
EPOCH_GAP_BINS_HOURS = ((0.0, 2.0), (2.0, 6.0), (6.0, 12.0), (12.0, 24.0))


class Refused(RuntimeError):
    """A request was refused before a socket could be created."""


class Halted(RuntimeError):
    """A permanent halt marker is in place, or was just written."""


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def stamp(moment: dt.datetime) -> str:
    return moment.strftime("%Y%m%dT%H%M%SZ")


def _read_json(path: Path, fallback):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return fallback


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".next")
    temporary.write_text(json.dumps(payload, indent=1, sort_keys=True), encoding="utf-8")
    temporary.replace(path)


def _append_jsonl(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def quantiles(values: Sequence[float], probabilities: Sequence[float] = QUANTILES) -> dict:
    """Linear-interpolated quantiles, defined here so the definition is fixed."""
    ordered = sorted(values)
    if not ordered:
        return {}
    out = {}
    for probability in probabilities:
        position = probability * (len(ordered) - 1)
        low = math.floor(position)
        high = math.ceil(position)
        if low == high:
            out[f"p{int(round(probability * 100)):02d}"] = ordered[low]
        else:
            weight = position - low
            out[f"p{int(round(probability * 100)):02d}"] = (
                ordered[low] * (1.0 - weight) + ordered[high] * weight
            )
    return out


# ---------------------------------------------------------------------------
# Archive roots and state
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class Roots:
    root: Path

    @property
    def supgp_raw(self) -> Path:
        return self.root / "supgp" / "raw"

    @property
    def supgp_db(self) -> Path:
        return self.root / "supgp" / "supgp.sqlite3"

    @property
    def starlink_raw(self) -> Path:
        return self.root / "starlink" / "raw"

    @property
    def starlink_db(self) -> Path:
        return self.root / "starlink" / "starlink.sqlite3"

    @property
    def requests_ledger(self) -> Path:
        return self.root / "ledger" / "requests.jsonl"

    @property
    def captures_ledger(self) -> Path:
        return self.root / "ledger" / "captures.jsonl"

    @property
    def state(self) -> Path:
        return self.root / "state"

    @property
    def halt_marker(self) -> Path:
        return self.root / "HALTED.json"


def halted(roots: Roots) -> dict | None:
    if not roots.halt_marker.exists():
        return None
    return _read_json(roots.halt_marker, {"status": "unreadable marker"})


def write_halt(roots: Roots, reason: str, detail: dict | None = None) -> None:
    payload = {
        "haltedAt": utc_now().isoformat(),
        "reason": reason,
        "detail": detail or {},
        "clearedBy": None,
    }
    roots.halt_marker.parent.mkdir(parents=True, exist_ok=True)
    roots.halt_marker.write_text(json.dumps(payload, indent=1, sort_keys=True), encoding="utf-8")
    try:
        os.chmod(roots.halt_marker, 0o600)
    except OSError:
        pass


def clear_halt(roots: Roots, reason: str) -> Path:
    marker = halted(roots)
    if marker is None:
        raise Refused("no halt marker is in place")
    archive = roots.root / "state" / "halts"
    archive.mkdir(parents=True, exist_ok=True)
    marker["clearedBy"] = reason
    marker["clearedAt"] = utc_now().isoformat()
    destination = archive / f"HALTED-{stamp(utc_now())}.json"
    destination.write_text(json.dumps(marker, indent=1, sort_keys=True), encoding="utf-8")
    roots.halt_marker.unlink()
    return destination


# ---------------------------------------------------------------------------
# The request gate
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class RequestGate:
    """Everything that must be true before a socket may be created.

    Each guard can be switched off individually.  That is not a convenience:
    it is what lets a test run the same scenario twice -- once with the guard
    and once without -- and assert that the unguarded run reproduces the bad
    behaviour.  A guard test whose code path is never reached passes for the
    wrong reason.
    """

    roots: Roots
    lane: str
    expected_host: str
    interval_seconds: float
    requests_per_process: int
    gap_seconds: float
    enforce_host: bool = True
    enforce_halt: bool = True
    enforce_interval: bool = True
    enforce_ceiling: bool = True
    record_attempt_before_socket: bool = True
    hostname: str | None = None
    spent: int = 0
    last_started: float | None = None

    def host(self) -> str:
        return self.hostname if self.hostname is not None else socket.gethostname()

    def _attempts_path(self) -> Path:
        return self.roots.state / f"last-request-at-{self.lane}.json"

    def attempts(self) -> dict:
        return _read_json(self._attempts_path(), {})

    def record_attempt(self, key: str, when: dt.datetime) -> None:
        book = self.attempts()
        book[key] = when.isoformat()
        _write_json(self._attempts_path(), book)

    def seconds_since(self, key: str, now: dt.datetime) -> float | None:
        book = self.attempts()
        text = book.get(key)
        if not text:
            return None
        try:
            previous = dt.datetime.fromisoformat(text)
        except ValueError:
            return None
        return (now - previous).total_seconds()

    def check(self, key: str, now: dt.datetime | None = None) -> None:
        now = now or utc_now()
        if self.enforce_host and self.host() != self.expected_host:
            raise Refused(
                f"{self.lane} may be requested only from {self.expected_host}; "
                f"this host is {self.host()}"
            )
        if self.enforce_halt:
            marker = halted(self.roots)
            if marker is not None:
                raise Halted(
                    f"a halt marker is in place since {marker.get('haltedAt')}: "
                    f"{marker.get('reason')}; not querying"
                )
        if self.enforce_ceiling and self.spent >= self.requests_per_process:
            raise Refused(
                f"{self.lane} ceiling of {self.requests_per_process} request(s) "
                f"per process is spent"
            )
        if self.enforce_interval:
            elapsed = self.seconds_since(key, now)
            if elapsed is not None and elapsed < self.interval_seconds:
                raise Refused(
                    f"{self.lane}/{key} was requested {elapsed:.0f} s ago; the "
                    f"interval is {self.interval_seconds:.0f} s. An interval is a "
                    f"floor on how often we may ask, never permission to ask."
                )

    def spend(self, key: str, now: dt.datetime | None = None) -> None:
        now = now or utc_now()
        if self.record_attempt_before_socket:
            self.record_attempt(key, now)
        self.spent += 1

    def wait_for_gap(self, sleeper: Callable[[float], None] = time.sleep) -> None:
        if self.last_started is None or self.gap_seconds <= 0:
            return
        remaining = self.gap_seconds - (time.monotonic() - self.last_started)
        if remaining > 0:
            sleeper(remaining)


# ---------------------------------------------------------------------------
# Transport
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class Response:
    status: int
    body: bytes
    headers: dict


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D102
        raise urllib.error.HTTPError(
            req.full_url, code, f"redirect to {newurl} refused", headers, fp
        )


def http_get(url: str, validators: dict | None = None) -> Response:
    """The only outbound call in this module.

    No proxy handler is installed, so ``HTTP_PROXY``/``HTTPS_PROXY`` cannot
    quietly move the route.  Redirects raise rather than being followed.  There
    is no retry loop anywhere in this file.
    """
    request = urllib.request.Request(url, method="GET")
    request.add_header("User-Agent", USER_AGENT)
    request.add_header("Accept-Encoding", "identity")
    for header, value in (validators or {}).items():
        request.add_header(header, value)
    opener = urllib.request.build_opener(
        _NoRedirect(),
        urllib.request.HTTPSHandler(context=ssl.create_default_context()),
    )
    with opener.open(request, timeout=TIMEOUT_SECONDS) as answer:
        body = answer.read(BODY_CEILING_BYTES + 1)
        return Response(
            status=answer.status,
            body=body,
            headers={key.lower(): value for key, value in answer.headers.items()},
        )


Transport = Callable[[str, dict], Response]


# ---------------------------------------------------------------------------
# Fetching
# ---------------------------------------------------------------------------


def supgp_url(set_name: str) -> str:
    """The only builder for a supplemental URL, and it refuses offline.

    An unverified set name never reaches a socket, so it never costs a 404.
    """
    if set_name not in VERIFIED_SUPGP_SETS:
        raise Refused(
            f"set {set_name!r} is not in the verified allowlist "
            f"{sorted(VERIFIED_SUPGP_SETS)}; a guessed set name costs a 404, and a "
            f"404 counts toward the provider's firewall threshold"
        )
    return f"{SUPGP_BASE}?FILE={set_name}&FORMAT=json"


def _validators_for(roots: Roots, lane: str, key: str, body_sha: str | None) -> dict:
    """Send a cache validator only when it is bound to the body we still hold."""
    book = _read_json(roots.state / f"validators-{lane}.json", {})
    entry = book.get(key)
    if not entry or not body_sha or entry.get("bodySha256") != body_sha:
        return {}
    out = {}
    if entry.get("etag"):
        out["If-None-Match"] = entry["etag"]
    if entry.get("lastModified"):
        out["If-Modified-Since"] = entry["lastModified"]
    return out


def _remember_validators(roots: Roots, lane: str, key: str, response: Response, body_sha: str) -> None:
    path = roots.state / f"validators-{lane}.json"
    book = _read_json(path, {})
    book[key] = {
        "etag": response.headers.get("etag"),
        "lastModified": response.headers.get("last-modified"),
        "bodySha256": body_sha,
        "seenAt": utc_now().isoformat(),
    }
    _write_json(path, book)


def _remember_body(roots: Roots, lane: str, key: str, body_sha: str, size: int) -> bool:
    """Record the body hash. Returns True when it is byte-identical to the last."""
    path = roots.state / f"bodies-{lane}.json"
    book = _read_json(path, {})
    previous = book.get(key, {})
    repeated = previous.get("sha256") == body_sha
    book[key] = {
        "sha256": body_sha,
        "bytes": size,
        "seenAt": utc_now().isoformat(),
        "unchangedRepeats": previous.get("unchangedRepeats", 0) + (1 if repeated else 0),
    }
    _write_json(path, book)
    return repeated


def perform(
    roots: Roots,
    gate: RequestGate,
    key: str,
    url: str,
    *,
    transport: Transport = None,
    sleeper: Callable[[float], None] = time.sleep,
) -> Response:
    """Gate, log, request, validate, and halt on anything unexpected."""
    transport = transport or (lambda address, headers: http_get(address, headers))
    now = utc_now()
    try:
        gate.check(key, now)
    except (Refused, Halted) as refusal:
        # A refusal is evidence too: the ledger has to show the requests that
        # were not made, or "we respected the budget" is a claim with no file
        # behind it.
        _append_jsonl(
            roots.requests_ledger,
            {
                "lane": gate.lane,
                "key": key,
                "url": url,
                "host": gate.host(),
                "startedAt": now.isoformat(),
                "status": None,
                "bytes": None,
                "outcome": "refused",
                "note": str(refusal),
            },
        )
        raise

    previous_body = _read_json(roots.state / f"bodies-{gate.lane}.json", {}).get(key, {})
    validators = _validators_for(roots, gate.lane, key, previous_body.get("sha256"))

    gate.wait_for_gap(sleeper)
    gate.spend(key, now)
    started = time.monotonic()
    gate.last_started = started

    line = {
        "lane": gate.lane,
        "key": key,
        "url": url,
        "host": gate.host(),
        "startedAt": now.isoformat(),
        "validatorsSent": validators,
        "status": None,
        "bytes": None,
        "sha256": None,
        "elapsedMs": None,
        "validatorsSeen": None,
        "outcome": "started",
        "note": None,
    }
    _append_jsonl(roots.requests_ledger, dict(line))

    def close(outcome: str, note: str | None = None, **extra) -> None:
        line.update(extra)
        line["outcome"] = outcome
        line["note"] = note
        line["elapsedMs"] = int(round((time.monotonic() - started) * 1000))
        _append_jsonl(roots.requests_ledger, dict(line))

    try:
        response = transport(url, validators)
    except urllib.error.HTTPError as error:
        close("halt", f"HTTP {error.code}", status=error.code)
        write_halt(roots, f"HTTP {error.code} on {gate.lane}/{key}", {"url": url})
        raise Halted(f"HTTP {error.code} on {gate.lane}/{key}; halted") from error
    except Exception as error:  # transport failure of any kind
        close("halt", f"transport failure: {type(error).__name__}")
        write_halt(roots, f"transport failure on {gate.lane}/{key}", {"error": repr(error)})
        raise Halted(f"transport failure on {gate.lane}/{key}; halted") from error

    if response.status == 304:
        if not validators:
            close("halt", "unsolicited 304", status=304)
            write_halt(roots, f"unsolicited 304 on {gate.lane}/{key}", {"url": url})
            raise Halted(f"unsolicited 304 on {gate.lane}/{key}; halted")
        close("not-modified", None, status=304, bytes=0,
              validatorsSeen={k: v for k, v in response.headers.items()
                              if k in ("etag", "last-modified")})
        return response
    if response.status != 200:
        close("halt", f"status {response.status}", status=response.status)
        write_halt(roots, f"status {response.status} on {gate.lane}/{key}", {"url": url})
        raise Halted(f"status {response.status} on {gate.lane}/{key}; halted")
    if not response.body:
        close("halt", "empty body", status=200, bytes=0)
        write_halt(roots, f"empty body on {gate.lane}/{key}", {"url": url})
        raise Halted(f"empty body on {gate.lane}/{key}; halted")
    if len(response.body) > BODY_CEILING_BYTES:
        close("halt", "body over ceiling", status=200, bytes=len(response.body))
        write_halt(roots, f"body over ceiling on {gate.lane}/{key}", {"url": url})
        raise Halted(f"body over the {BODY_CEILING_BYTES} byte ceiling; halted")

    body_sha = hashlib.sha256(response.body).hexdigest()
    repeated = _remember_body(roots, gate.lane, key, body_sha, len(response.body))
    _remember_validators(roots, gate.lane, key, response, body_sha)
    close(
        "ok",
        "WASTED REQUEST: body is byte-identical to the one already held" if repeated else None,
        status=200,
        bytes=len(response.body),
        sha256=body_sha,
        validatorsSeen={k: v for k, v in response.headers.items()
                        if k in ("etag", "last-modified")},
    )
    return response


def fetch_supgp(
    roots: Roots,
    set_names: Sequence[str],
    *,
    transport: Transport = None,
    hostname: str | None = None,
    sleeper: Callable[[float], None] = time.sleep,
    **gate_overrides,
) -> list[Path]:
    """One request per named set, under the registered ceiling."""
    gate = RequestGate(
        roots=roots,
        lane="supgp",
        expected_host=SUPGP_HOST,
        interval_seconds=SUPGP_INTERVAL_SECONDS,
        requests_per_process=SUPGP_REQUESTS_PER_PROCESS,
        gap_seconds=SUPGP_GAP_SECONDS,
        hostname=hostname,
        **gate_overrides,
    )
    written: list[Path] = []
    for set_name in set_names:
        url = supgp_url(set_name)
        response = perform(roots, gate, set_name, url, transport=transport, sleeper=sleeper)
        if response.status == 304:
            continue
        payload = json.loads(response.body.decode("utf-8"))
        if not isinstance(payload, list) or not payload:
            write_halt(roots, f"supplemental set {set_name} is not a non-empty array", {})
            raise Halted(f"supplemental set {set_name} is not a non-empty JSON array; halted")
        now = utc_now()
        destination = (
            roots.supgp_raw
            / f"{now:%Y}"
            / f"{now:%m}"
            / f"sup-gp-{set_name}-{stamp(now)}.json.gz"
        )
        destination.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(destination, "wb") as handle:
            handle.write(response.body)
        written.append(destination)
    return written


def fetch_starlink(
    roots: Roots,
    *,
    limit: int = STARLINK_FILES_PER_RUN,
    transport: Transport = None,
    hostname: str | None = None,
    sleeper: Callable[[float], None] = time.sleep,
    **gate_overrides,
) -> tuple[Path, list[Path]]:
    """The manifest, then a deterministic sample of the files it names."""
    if limit > STARLINK_FILES_PER_RUN:
        raise Refused(
            f"{limit} files exceeds the registered ceiling of {STARLINK_FILES_PER_RUN} per run"
        )
    gate = RequestGate(
        roots=roots,
        lane="starlink",
        expected_host=STARLINK_HOST,
        interval_seconds=STARLINK_MANIFEST_INTERVAL_SECONDS,
        requests_per_process=limit + 1,
        gap_seconds=STARLINK_GAP_SECONDS,
        hostname=hostname,
        **gate_overrides,
    )
    now = utc_now()
    response = perform(
        roots, gate, "MANIFEST", STARLINK_MANIFEST, transport=transport, sleeper=sleeper
    )
    day = roots.starlink_raw / f"{now:%Y}" / f"{now:%m}" / f"{now:%d}"
    day.mkdir(parents=True, exist_ok=True)
    manifest_path = day / f"MANIFEST-{stamp(now)}.txt.gz"
    with gzip.open(manifest_path, "wb") as handle:
        handle.write(response.body)

    names = [line.strip() for line in response.body.decode("ascii").splitlines() if line.strip()]
    chosen = sample_manifest(names, limit)
    written: list[Path] = []
    for name in chosen:
        file_response = perform(
            roots, gate, name, STARLINK_BASE + name, transport=transport, sleeper=sleeper
        )
        if file_response.status == 304:
            continue
        destination = day / (name + ".gz")
        with gzip.open(destination, "wb") as handle:
            handle.write(file_response.body)
        written.append(destination)
    return manifest_path, written


def sample_manifest(names: Sequence[str], limit: int) -> list[str]:
    """A deterministic, recorded sampling rule: every k-th name, k from the size.

    Deterministic so that the sample can be reproduced from the manifest alone,
    and spread across the whole file rather than taking a prefix, because the
    manifest is ordered and a prefix is a block of the constellation, not a
    sample of it.
    """
    if limit <= 0 or not names:
        return []
    if len(names) <= limit:
        return list(names)
    step = len(names) / float(limit)
    return [names[int(index * step)] for index in range(limit)]


# ---------------------------------------------------------------------------
# Supplemental element sets -- offline archiving
# ---------------------------------------------------------------------------

SUPGP_SCHEMA = """
CREATE TABLE IF NOT EXISTS element_set_sup (
  norad            INTEGER NOT NULL,
  epoch_ms         INTEGER NOT NULL,
  element_set_no   INTEGER NOT NULL,
  set_name         TEXT    NOT NULL,
  object_name      TEXT,
  object_id        TEXT,
  mean_motion      REAL, eccentricity REAL, inclination REAL,
  raan             REAL, arg_perigee  REAL, mean_anomaly REAL,
  bstar            REAL, ndot REAL, nddot REAL, rev_at_epoch INTEGER,
  source           TEXT NOT NULL,
  fetched_at_ms    INTEGER NOT NULL,
  body_sha256      TEXT NOT NULL,
  classification   TEXT,
  operator_derived INTEGER NOT NULL,
  prediction       INTEGER NOT NULL,
  covariance       INTEGER NOT NULL,
  originator       TEXT,
  data_source      TEXT,                 -- the provider names the input product
  fit_rms_km       REAL,                 -- the provider publishes its own fit residual
  ingest_host      TEXT NOT NULL,
  PRIMARY KEY (norad, epoch_ms, element_set_no, set_name)
) WITHOUT ROWID;
"""

NAIVE_SCHEMA = SUPGP_SCHEMA.replace(
    "PRIMARY KEY (norad, epoch_ms, element_set_no, set_name)",
    "PRIMARY KEY (norad, epoch_ms)",
)

_COLUMNS = (
    "norad", "epoch_ms", "element_set_no", "set_name", "object_name", "object_id",
    "mean_motion", "eccentricity", "inclination", "raan", "arg_perigee", "mean_anomaly",
    "bstar", "ndot", "nddot", "rev_at_epoch", "source", "fetched_at_ms", "body_sha256",
    "classification", "operator_derived", "prediction", "covariance", "originator",
    "data_source", "fit_rms_km", "ingest_host",
)


def parse_epoch_ms(text: str) -> int:
    moment = dt.datetime.fromisoformat(text)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=dt.timezone.utc)
    return int(round(moment.timestamp() * 1000))


def rows_from_supgp(
    payload: Iterable[dict],
    set_name: str,
    *,
    fetched_at_ms: int,
    body_sha256: str,
    host: str,
) -> tuple[list[tuple], dict]:
    rows: list[tuple] = []
    notes = {"read": 0, "rejected": 0, "classificationNotC": 0, "byReason": {}}

    def reject(reason: str) -> None:
        notes["rejected"] += 1
        notes["byReason"][reason] = notes["byReason"].get(reason, 0) + 1

    for record in payload:
        notes["read"] += 1
        try:
            norad = int(record["NORAD_CAT_ID"])
            epoch_ms = parse_epoch_ms(str(record["EPOCH"]))
            mean_motion = float(record["MEAN_MOTION"])
            eccentricity = float(record["ECCENTRICITY"])
            inclination = float(record["INCLINATION"])
            raan = float(record["RA_OF_ASC_NODE"])
            arg_perigee = float(record["ARG_OF_PERICENTER"])
            mean_anomaly = float(record["MEAN_ANOMALY"])
        except (KeyError, TypeError, ValueError):
            reject("unreadable-required-field")
            continue
        if not 0.0 <= eccentricity < 1.0:
            reject("eccentricity-out-of-range")
            continue
        if mean_motion <= 0.0:
            reject("mean-motion-not-positive")
            continue
        classification = record.get("CLASSIFICATION_TYPE")
        # The provider marks its own supplemental sets with 'C'.  A record that
        # does not carry it is archived with operator_derived = 0 and counted:
        # the flag is read off the record, never inferred from the set name.
        operator_derived = 1 if classification == "C" else 0
        if not operator_derived:
            notes["classificationNotC"] += 1
        rows.append(
            (
                norad,
                epoch_ms,
                int(record.get("ELEMENT_SET_NO") or 0),
                set_name,
                record.get("OBJECT_NAME"),
                record.get("OBJECT_ID"),
                mean_motion,
                eccentricity,
                inclination,
                raan,
                arg_perigee,
                mean_anomaly,
                _optional_float(record.get("BSTAR")),
                _optional_float(record.get("MEAN_MOTION_DOT")),
                _optional_float(record.get("MEAN_MOTION_DDOT")),
                _optional_int(record.get("REV_AT_EPOCH")),
                "celestrak-supgp",
                fetched_at_ms,
                body_sha256,
                classification,
                operator_derived,
                1,  # prediction: fitted forward from epoch, per the provider
                0,  # covariance: a supplemental element set carries none
                record.get("ORIGINATOR"),
                record.get("DATA_SOURCE"),
                _optional_float(record.get("RMS")),
                host,
            )
        )
    return rows, notes


def _optional_float(value) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_int(value) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def ingest_supgp_rows(
    database: Path, rows: Sequence[tuple], *, key: Sequence[str] = REGISTERED_KEY
) -> dict:
    """Append every element set not already archived. Idempotent.

    ``key`` exists so a test can run this twice -- once with the registered key
    and once with the GP archive's naive key -- and show that the naive key
    loses data the provider says can exist.
    """
    database.parent.mkdir(parents=True, exist_ok=True)
    schema = SUPGP_SCHEMA if tuple(key) == REGISTERED_KEY else NAIVE_SCHEMA
    connection = sqlite3.connect(database)
    try:
        connection.executescript(schema)
        before = connection.execute("SELECT COUNT(*) FROM element_set_sup").fetchone()[0]
        placeholders = ",".join("?" for _ in _COLUMNS)
        connection.executemany(
            f"INSERT OR IGNORE INTO element_set_sup VALUES ({placeholders})", rows
        )
        connection.commit()
        after = connection.execute("SELECT COUNT(*) FROM element_set_sup").fetchone()[0]
    finally:
        connection.close()
    inserted = after - before
    return {
        "recordsRead": len(rows),
        "elementsNew": inserted,
        "duplicates": len(rows) - inserted,
        "rowsAfter": after,
    }


def ingest_supgp_file(roots: Roots, path: Path, *, host: str | None = None) -> dict:
    """Parse one raw body from disk and archive it. Opens no socket."""
    raw = gzip.open(path, "rb").read() if path.suffix == ".gz" else path.read_bytes()
    body_sha = hashlib.sha256(raw).hexdigest()
    payload = json.loads(raw.decode("utf-8"))
    set_name = path.name.split("sup-gp-", 1)[-1].rsplit("-", 1)[0]
    fetched_at_ms = int(path.stat().st_mtime * 1000)
    rows, notes = rows_from_supgp(
        payload,
        set_name,
        fetched_at_ms=fetched_at_ms,
        body_sha256=body_sha,
        host=host or socket.gethostname(),
    )
    summary = ingest_supgp_rows(roots.supgp_db, rows)
    summary.update(
        {
            "capturedAt": utc_now().isoformat(),
            "lane": "supgp",
            "set": set_name,
            "file": str(path),
            "bodySha256": body_sha,
            "parse": notes,
        }
    )
    _append_jsonl(roots.captures_ledger, summary)
    return summary


# ---------------------------------------------------------------------------
# Operator ephemerides -- offline archiving
# ---------------------------------------------------------------------------

STARLINK_SCHEMA = """
CREATE TABLE IF NOT EXISTS ephemeris_file (
  body_sha256      TEXT PRIMARY KEY,
  filename         TEXT NOT NULL,
  spacecraft       TEXT,
  norad            INTEGER,
  created_ms       INTEGER NOT NULL,
  start_ms         INTEGER NOT NULL,
  stop_ms          INTEGER NOT NULL,
  step_seconds     INTEGER NOT NULL,
  ephemeris_source TEXT,
  covariance_frame TEXT,
  records          INTEGER NOT NULL,
  source           TEXT NOT NULL,
  fetched_at_ms    INTEGER NOT NULL,
  operator_derived INTEGER NOT NULL,
  prediction       INTEGER NOT NULL,
  covariance       INTEGER NOT NULL,
  ingest_host      TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ephemeris_sigma (
  body_sha256  TEXT NOT NULL,
  lead_hours   REAL NOT NULL,
  epoch_ms     INTEGER NOT NULL,
  sigma_axis1_m REAL, sigma_axis2_m REAL, sigma_axis3_m REAL,
  var_axis4 REAL, var_axis5 REAL, var_axis6 REAL,
  PRIMARY KEY (body_sha256, lead_hours)
) WITHOUT ROWID;
"""


def summarise_ephemeris(path: Path, leads_hours: Sequence[float] = COMPARISON_LEAD_HOURS) -> dict:
    """Header provenance plus the covariance diagonal at the registered leads.

    The full sixty-second tabulation is not expanded into the database; it
    stays in the file.  Axis names are the file's own -- index one is not
    called radial here, because this module has not verified that it is.
    """
    ephemeris = starlink_ephemeris.read(path)
    header = ephemeris.header
    wanted = [header.start + dt.timedelta(hours=lead) for lead in leads_hours]
    picked: dict[float, starlink_ephemeris.EphemerisRecord] = {}
    for lead, target in zip(leads_hours, wanted):
        best = None
        best_gap = None
        for record in ephemeris.records:
            gap = abs((record.epoch - target).total_seconds())
            if best_gap is None or gap < best_gap:
                best, best_gap = record, gap
        if best is not None and best_gap is not None and best_gap <= header.step_seconds:
            picked[lead] = best
    sigmas = []
    for lead, record in picked.items():
        sigma = record.position_sigma_km
        sigmas.append(
            {
                "leadHours": lead,
                "epochMs": int(record.epoch.timestamp() * 1000),
                "sigmaAxis1M": None if sigma is None else sigma[0] * 1000.0,
                "sigmaAxis2M": None if sigma is None else sigma[1] * 1000.0,
                "sigmaAxis3M": None if sigma is None else sigma[2] * 1000.0,
                "varAxis4": record.covariance[9] if record.covariance else None,
                "varAxis5": record.covariance[14] if record.covariance else None,
                "varAxis6": record.covariance[20] if record.covariance else None,
            }
        )
    return {
        "filename": path.name.removesuffix(".gz"),
        "spacecraft": starlink_ephemeris.spacecraft_name(path.name),
        "created": header.created.isoformat(),
        "start": header.start.isoformat(),
        "stop": header.stop.isoformat(),
        "stepSeconds": header.step_seconds,
        "ephemerisSource": header.source,
        "covarianceFrame": header.covariance_frame,
        "records": len(ephemeris.records),
        "sigmas": sigmas,
    }


def ingest_starlink_file(roots: Roots, path: Path, *, names: dict | None = None,
                         host: str | None = None) -> dict:
    raw = gzip.open(path, "rb").read() if path.suffix == ".gz" else path.read_bytes()
    body_sha = hashlib.sha256(raw).hexdigest()
    summary = summarise_ephemeris(path)
    spacecraft = summary["spacecraft"]
    norad = (names or {}).get(spacecraft)
    roots.starlink_db.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(roots.starlink_db)
    try:
        connection.executescript(STARLINK_SCHEMA)
        connection.execute(
            "INSERT OR IGNORE INTO ephemeris_file VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                body_sha,
                summary["filename"],
                spacecraft,
                norad,
                int(dt.datetime.fromisoformat(summary["created"]).timestamp() * 1000),
                int(dt.datetime.fromisoformat(summary["start"]).timestamp() * 1000),
                int(dt.datetime.fromisoformat(summary["stop"]).timestamp() * 1000),
                summary["stepSeconds"],
                summary["ephemerisSource"],
                summary["covarianceFrame"],
                summary["records"],
                "spacex-starlink-ephemeris",
                int(path.stat().st_mtime * 1000),
                1,  # operator_derived
                1,  # prediction: a seventy-two hour forward tabulation
                1,  # covariance: present in the bytes
                host or socket.gethostname(),
            ),
        )
        connection.executemany(
            "INSERT OR IGNORE INTO ephemeris_sigma VALUES (?,?,?,?,?,?,?,?,?)",
            [
                (
                    body_sha,
                    row["leadHours"],
                    row["epochMs"],
                    row["sigmaAxis1M"],
                    row["sigmaAxis2M"],
                    row["sigmaAxis3M"],
                    row["varAxis4"],
                    row["varAxis5"],
                    row["varAxis6"],
                )
                for row in summary["sigmas"]
            ],
        )
        connection.commit()
    finally:
        connection.close()
    summary["bodySha256"] = body_sha
    summary["norad"] = norad
    return summary


# ---------------------------------------------------------------------------
# The comparison
# ---------------------------------------------------------------------------

MINUTES_PER_DAY = 1440.0
JULIAN_1949_12_31 = 2433281.5


def _julian_day(moment: dt.datetime) -> float:
    moment = moment.astimezone(dt.timezone.utc)
    year, month = moment.year, moment.month
    day = (
        moment.day
        + (moment.hour + (moment.minute + (moment.second + moment.microsecond / 1e6) / 60.0) / 60.0)
        / 24.0
    )
    if month <= 2:
        year -= 1
        month += 12
    a = year // 100
    b = 2 - a + a // 4
    return (
        math.floor(365.25 * (year + 4716))
        + math.floor(30.6001 * (month + 1))
        + day
        + b
        - 1524.5
    )


@dataclasses.dataclass(frozen=True)
class MeanElements:
    norad: int
    epoch: dt.datetime
    mean_motion: float      # rev/day
    eccentricity: float
    inclination: float      # degrees
    raan: float             # degrees
    arg_perigee: float      # degrees
    mean_anomaly: float     # degrees
    bstar: float


def build_propagator(element: MeanElements):
    """Both sides of the comparison are initialised the same way.

    Published element values are used on both sides rather than the two-line
    text on one side and values on the other, because the two-line form is
    rounded and a rounding applied to only one side is a systematic difference
    that would be read as a disagreement.
    """
    from sgp4.api import Satrec, WGS72

    satellite = Satrec()
    satellite.sgp4init(
        WGS72,
        "i",
        element.norad,
        _julian_day(element.epoch) - JULIAN_1949_12_31,
        element.bstar,
        0.0,  # unused by the propagation model
        0.0,  # unused by the propagation model
        element.eccentricity,
        math.radians(element.arg_perigee),
        math.radians(element.inclination),
        math.radians(element.mean_anomaly),
        element.mean_motion * 2.0 * math.pi / MINUTES_PER_DAY,
        math.radians(element.raan),
    )
    return satellite


def propagate(element: MeanElements, when: dt.datetime):
    from sgp4.api import jday

    satellite = build_propagator(element)
    whole, fraction = jday(
        when.year, when.month, when.day, when.hour, when.minute,
        when.second + when.microsecond / 1e6,
    )
    code, position, velocity = satellite.sgp4(whole, fraction)
    return code, position, velocity


def rtn_difference(reference_r, reference_v, other_r) -> tuple[float, float, float]:
    """Project a position difference onto the reference state's own frame.

    Radial is along the reference position, normal is along its angular
    momentum, and along-track completes the triad.  Returned in metres.
    """
    rx, ry, rz = reference_r
    vx, vy, vz = reference_v
    r_norm = math.sqrt(rx * rx + ry * ry + rz * rz)
    radial = (rx / r_norm, ry / r_norm, rz / r_norm)
    hx = ry * vz - rz * vy
    hy = rz * vx - rx * vz
    hz = rx * vy - ry * vx
    h_norm = math.sqrt(hx * hx + hy * hy + hz * hz)
    normal = (hx / h_norm, hy / h_norm, hz / h_norm)
    along = (
        normal[1] * radial[2] - normal[2] * radial[1],
        normal[2] * radial[0] - normal[0] * radial[2],
        normal[0] * radial[1] - normal[1] * radial[0],
    )
    delta = (other_r[0] - rx, other_r[1] - ry, other_r[2] - rz)

    def project(axis) -> float:
        return (delta[0] * axis[0] + delta[1] * axis[1] + delta[2] * axis[2]) * 1000.0

    return project(radial), project(along), project(normal)


def gp_elements_from_mirror(path: Path) -> dict[int, MeanElements]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    out: dict[int, MeanElements] = {}
    for record in payload:
        if record.get("DECAY_DATE"):
            continue
        try:
            norad = int(record["NORAD_CAT_ID"])
            element = MeanElements(
                norad=norad,
                epoch=dt.datetime.fromisoformat(str(record["EPOCH"])).replace(
                    tzinfo=dt.timezone.utc
                ),
                mean_motion=float(record["MEAN_MOTION"]),
                eccentricity=float(record["ECCENTRICITY"]),
                inclination=float(record["INCLINATION"]),
                raan=float(record["RA_OF_ASC_NODE"]),
                arg_perigee=float(record["ARG_OF_PERICENTER"]),
                mean_anomaly=float(record["MEAN_ANOMALY"]),
                bstar=float(record.get("BSTAR") or 0.0),
            )
        except (KeyError, TypeError, ValueError):
            continue
        keep = out.get(norad)
        if keep is None or element.epoch > keep.epoch:
            out[norad] = element
    return out


def archive_pairs(archive: Path, norads: Sequence[int], before_ms: dict[int, int]) -> dict:
    """The two most recent archived GP element sets before each object's own time.

    Read-only, and read-only in the way the archive's own readers require: a
    stray write cursor on a thirteen-gigabyte database is a problem for every
    other reader, not just for this one.
    """
    connection = sqlite3.connect(f"file:{archive}?mode=ro", uri=True, timeout=900.0)
    try:
        connection.execute("PRAGMA query_only=1")
        out: dict[int, list[MeanElements]] = {}
        query = (
            "SELECT epoch_ms, mean_motion_q, eccentricity_q, inclination_q, raan_q, "
            "arg_perigee_q, mean_anomaly_q, bstar_q FROM element_set "
            "WHERE norad = ? AND epoch_ms <= ? ORDER BY epoch_ms DESC LIMIT 2"
        )
        for norad in norads:
            limit = before_ms.get(norad)
            if limit is None:
                continue
            rows = connection.execute(query, (norad, limit)).fetchall()
            elements = []
            for row in rows:
                if row[7] is None:
                    bstar = 0.0
                else:
                    bstar = row[7] / SCALE_BSTAR
                elements.append(
                    MeanElements(
                        norad=norad,
                        epoch=dt.datetime.fromtimestamp(row[0] / 1000.0, dt.timezone.utc),
                        mean_motion=row[1] / SCALE_MEAN_MOTION,
                        eccentricity=row[2] / SCALE_ECCENTRICITY,
                        inclination=row[3] / SCALE_ANGLE,
                        raan=row[4] / SCALE_ANGLE,
                        arg_perigee=row[5] / SCALE_ANGLE,
                        mean_anomaly=row[6] / SCALE_ANGLE,
                        bstar=bstar,
                    )
                )
            if len(elements) == 2:
                out[norad] = elements
        return out
    finally:
        connection.close()


def compare_set(
    supgp_rows: Sequence[MeanElements],
    gp: dict[int, MeanElements],
    *,
    gap_ceiling_seconds: float = EPOCH_GAP_CEILING_SECONDS,
) -> dict:
    """The registered statistic, for one supplemental set."""
    paired: list[dict] = []
    excluded = {"noGpRecord": 0, "epochGapOverCeiling": 0, "propagationError": {}}
    for element in supgp_rows:
        counterpart = gp.get(element.norad)
        if counterpart is None:
            excluded["noGpRecord"] += 1
            continue
        gap = (element.epoch - counterpart.epoch).total_seconds()
        if abs(gap) > gap_ceiling_seconds:
            excluded["epochGapOverCeiling"] += 1
            continue
        code_a, r_a, v_a = propagate(element, element.epoch)
        code_b, r_b, v_b = propagate(counterpart, element.epoch)
        if code_a or code_b:
            key = f"{code_a}/{code_b}"
            excluded["propagationError"][key] = excluded["propagationError"].get(key, 0) + 1
            continue
        d_radial, d_along, d_normal = rtn_difference(r_b, v_b, r_a)
        paired.append(
            {
                "norad": element.norad,
                "gapSeconds": gap,
                "radialM": d_radial,
                "alongTrackM": d_along,
                "crossTrackM": d_normal,
            }
        )
    return {"paired": paired, "excluded": excluded}


def summarise_pairs(paired: Sequence[dict], label: str) -> dict:
    n = len(paired)
    out = {"label": label, "n": n}
    if n < MINIMUM_OBJECTS_FOR_QUANTILES:
        out["quantiles"] = None
        out["note"] = (
            f"n = {n} is below the registered floor of {MINIMUM_OBJECTS_FOR_QUANTILES}; "
            f"counts only, no quantiles"
        )
        return out
    out["quantiles"] = {
        "absRadialM": quantiles([abs(row["radialM"]) for row in paired]),
        "absAlongTrackM": quantiles([abs(row["alongTrackM"]) for row in paired]),
        "absCrossTrackM": quantiles([abs(row["crossTrackM"]) for row in paired]),
        "absGapHours": quantiles([abs(row["gapSeconds"]) / 3600.0 for row in paired]),
    }
    out["binnedByGap"] = {}
    for low, high in EPOCH_GAP_BINS_HOURS:
        inside = [
            row for row in paired if low <= abs(row["gapSeconds"]) / 3600.0 < high
        ]
        entry = {"n": len(inside)}
        if len(inside) >= MINIMUM_OBJECTS_FOR_QUANTILES:
            entry["absRadialM"] = quantiles([abs(row["radialM"]) for row in inside])
            entry["absAlongTrackM"] = quantiles([abs(row["alongTrackM"]) for row in inside])
        out["binnedByGap"][f"{low:g}-{high:g}h"] = entry
    return out


def mean_elements_from_supgp(record: dict) -> MeanElements | None:
    try:
        return MeanElements(
            norad=int(record["NORAD_CAT_ID"]),
            epoch=dt.datetime.fromisoformat(str(record["EPOCH"])).replace(
                tzinfo=dt.timezone.utc
            ),
            mean_motion=float(record["MEAN_MOTION"]),
            eccentricity=float(record["ECCENTRICITY"]),
            inclination=float(record["INCLINATION"]),
            raan=float(record["RA_OF_ASC_NODE"]),
            arg_perigee=float(record["ARG_OF_PERICENTER"]),
            mean_anomaly=float(record["MEAN_ANOMALY"]),
            bstar=float(record.get("BSTAR") or 0.0),
        )
    except (KeyError, TypeError, ValueError):
        return None


def latest_per_object(records: Sequence[dict]) -> tuple[list[MeanElements], int]:
    """One element set per object -- the latest epoch -- and how often we chose.

    The provider ships several element sets for some objects. Picking one is a
    choice, so the number of objects it was made for is counted and printed
    rather than left to the reader to wonder about.
    """
    best: dict[int, tuple[MeanElements, dict]] = {}
    multiple = 0
    for record in records:
        element = mean_elements_from_supgp(record)
        if element is None:
            continue
        held = best.get(element.norad)
        if held is None:
            best[element.norad] = (element, record)
        else:
            multiple += 1
            if element.epoch > held[0].epoch:
                best[element.norad] = (element, record)
    return [pair[0] for pair in best.values()], multiple


def gp_self_floor(
    archive: Path, paired: Sequence[dict], at_ms: dict[int, int]
) -> dict:
    """The archive's own set-to-set disagreement, on the same objects.

    Two consecutive archived element sets for one object, both carried forward
    to the same instant and differenced by the identical procedure. This is the
    number the comparison is read against; zero is not.
    """
    norads = [row["norad"] for row in paired]
    pairs = archive_pairs(archive, norads, at_ms)
    rows: list[dict] = []
    failures = {"onlyOneSetInArchive": len(norads) - len(pairs), "propagationError": 0}
    for norad, (newer, older) in pairs.items():
        when = dt.datetime.fromtimestamp(at_ms[norad] / 1000.0, dt.timezone.utc)
        code_a, r_a, v_a = propagate(newer, when)
        code_b, r_b, _ = propagate(older, when)
        if code_a or code_b:
            failures["propagationError"] += 1
            continue
        d_radial, d_along, d_normal = rtn_difference(r_a, v_a, r_b)
        rows.append(
            {
                "norad": norad,
                "gapSeconds": (newer.epoch - older.epoch).total_seconds(),
                "radialM": d_radial,
                "alongTrackM": d_along,
                "crossTrackM": d_normal,
            }
        )
    summary = summarise_pairs(rows, "gp-vs-gp floor")
    summary["failures"] = failures
    return summary


def run_comparison(
    raw_files: Sequence[Path], gp_mirror: Path, archive: Path | None
) -> dict:
    gp = gp_elements_from_mirror(gp_mirror)
    result = {
        "gpMirror": {
            "path": str(gp_mirror),
            "bytes": gp_mirror.stat().st_size,
            "mtime": dt.datetime.fromtimestamp(
                gp_mirror.stat().st_mtime, dt.timezone.utc
            ).isoformat(),
            "objects": len(gp),
        },
        "sets": {},
    }
    for path in raw_files:
        raw = gzip.open(path, "rb").read() if path.suffix == ".gz" else path.read_bytes()
        payload = json.loads(raw.decode("utf-8"))
        set_name = path.name.split("sup-gp-", 1)[-1].rsplit("-", 1)[0]
        elements, multiple = latest_per_object(payload)
        comparison = compare_set(elements, gp)
        summary = summarise_pairs(comparison["paired"], set_name)
        summary["recordsInFile"] = len(payload)
        summary["objectsInFile"] = len(elements)
        summary["objectsWithSeveralElementSets"] = multiple
        summary["excluded"] = comparison["excluded"]
        summary["bodySha256"] = hashlib.sha256(raw).hexdigest()
        summary["sourceFile"] = str(path)
        summary["fitRmsKm"] = quantiles(
            [float(r["RMS"]) for r in payload if r.get("RMS") not in (None, "")]
        )
        summary["dataSources"] = sorted(
            {str(r.get("DATA_SOURCE")) for r in payload if r.get("DATA_SOURCE")}
        )
        if archive is not None and comparison["paired"]:
            epoch_by_norad = {
                element.norad: int(element.epoch.timestamp() * 1000)
                for element in elements
            }
            at_ms = {row["norad"]: epoch_by_norad[row["norad"]] for row in comparison["paired"]}
            summary["floor"] = gp_self_floor(archive, comparison["paired"], at_ms)
        result["sets"][set_name] = summary
    return result


def starlink_covariance_quantiles(paths: Sequence[Path]) -> dict:
    """Quantiles of the published one-sigma position terms, by column index."""
    by_lead: dict[float, dict[str, list[float]]] = {}
    frames: set[str] = set()
    sources: set[str] = set()
    files = 0
    terminal_values: dict[str, set[float]] = {"axis1": set(), "axis2": set(), "axis3": set()}
    for path in paths:
        try:
            summary = summarise_ephemeris(path)
        except starlink_ephemeris.EphemerisFormatError:
            continue
        files += 1
        frames.add(summary["covarianceFrame"])
        sources.add(summary["ephemerisSource"])
        for row in summary["sigmas"]:
            bucket = by_lead.setdefault(
                row["leadHours"], {"axis1": [], "axis2": [], "axis3": []}
            )
            for index in (1, 2, 3):
                value = row[f"sigmaAxis{index}M"]
                if value is not None:
                    bucket[f"axis{index}"].append(value)
            if row["leadHours"] == max(COMPARISON_LEAD_HOURS):
                for index in (1, 2, 3):
                    value = row[f"sigmaAxis{index}M"]
                    if value is not None:
                        terminal_values[f"axis{index}"].add(round(value, 6))
    out = {
        "files": files,
        "covarianceFrames": sorted(frames),
        "ephemerisSources": sorted(sources),
        "byLeadHours": {},
        "terminalLeadDistinctValues": {
            axis: len(values) for axis, values in terminal_values.items()
        },
    }
    for lead in sorted(by_lead):
        entry = {"n": len(by_lead[lead]["axis1"])}
        for index in (1, 2, 3):
            values = by_lead[lead][f"axis{index}"]
            entry[f"sigmaAxis{index}M"] = (
                quantiles(values) if len(values) >= MINIMUM_OBJECTS_FOR_QUANTILES else None
            )
        out["byLeadHours"][str(lead)] = entry
    return out


# ---------------------------------------------------------------------------
# Command line
# ---------------------------------------------------------------------------


def _roots(args) -> Roots:
    return Roots(Path(args.root))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", default=str(DEFAULT_ROOT))
    sub = parser.add_subparsers(dest="command", required=True)

    fetch = sub.add_parser("fetch-supgp", help="request supplemental sets (VPS only)")
    fetch.add_argument("sets", nargs="+")
    fetch.add_argument(
        "--other-lane-attempts-24h",
        type=int,
        required=True,
        help="attempts the site mirror has already spent in the last 24 hours; "
             "the two lanes share one address, so the combined figure is stated "
             "deliberately rather than discovered afterwards",
    )
    fetch.add_argument("--combined-ceiling", type=int, default=7)

    star = sub.add_parser("fetch-starlink", help="request the manifest and a sample")
    star.add_argument("--limit", type=int, default=STARLINK_FILES_PER_RUN)

    ingest = sub.add_parser("ingest-supgp")
    ingest.add_argument("files", nargs="+")

    ingest_star = sub.add_parser("ingest-starlink")
    ingest_star.add_argument("files", nargs="+")
    ingest_star.add_argument("--names", default=None)

    compare = sub.add_parser("compare", help="the registered statistic; opens no socket")
    compare.add_argument("files", nargs="+")
    compare.add_argument("--gp-mirror", required=True,
                         help="the general-perturbations mirror to compare against")
    compare.add_argument("--archive", required=True,
                         help="the element-set archive database")
    compare.add_argument("--no-floor", action="store_true")
    compare.add_argument("--out", required=True)

    cov = sub.add_parser("covariance", help="quantiles of the published covariance")
    cov.add_argument("files", nargs="+")
    cov.add_argument("--out", required=True)

    sub.add_parser("status")

    clear = sub.add_parser("clear-halt")
    clear.add_argument("--reason", required=True)

    args = parser.parse_args(argv)
    roots = _roots(args)

    if args.command == "status":
        marker = halted(roots)
        print(f"root: {roots.root}")
        print(f"halted: {marker is not None}")
        if marker:
            print(f"  since {marker.get('haltedAt')}: {marker.get('reason')}")
        for lane in ("supgp", "starlink"):
            book = _read_json(roots.state / f"last-request-at-{lane}.json", {})
            print(f"{lane}: {len(book)} key(s) with a recorded attempt")
        print(f"verified sets: {sorted(VERIFIED_SUPGP_SETS)}")
        return 0

    if args.command == "clear-halt":
        destination = clear_halt(roots, args.reason)
        print(f"halt cleared and archived to {destination}")
        return 0

    if args.command == "fetch-supgp":
        combined = args.other_lane_attempts_24h + len(args.sets)
        if combined > args.combined_ceiling:
            print(
                f"refused: {args.other_lane_attempts_24h} attempt(s) already spent on this "
                f"address in 24 h plus {len(args.sets)} here is {combined}, over the "
                f"combined ceiling of {args.combined_ceiling}",
                file=sys.stderr,
            )
            return 2
        written = fetch_supgp(roots, args.sets)
        for path in written:
            print(f"stored {path} ({path.stat().st_size} bytes)")
        return 0

    if args.command == "fetch-starlink":
        manifest, written = fetch_starlink(roots, limit=args.limit)
        print(f"manifest {manifest} ({manifest.stat().st_size} bytes)")
        print(f"files {len(written)}")
        return 0

    if args.command == "compare":
        result = run_comparison(
            [Path(name) for name in args.files],
            Path(args.gp_mirror),
            None if args.no_floor else Path(args.archive),
        )
        _write_json(Path(args.out), result)
        print(f"wrote {args.out}")
        return 0

    if args.command == "covariance":
        result = starlink_covariance_quantiles([Path(name) for name in args.files])
        _write_json(Path(args.out), result)
        print(f"wrote {args.out}")
        return 0

    if args.command == "ingest-supgp":
        for name in args.files:
            summary = ingest_supgp_file(roots, Path(name))
            print(json.dumps(summary, sort_keys=True))
        return 0

    if args.command == "ingest-starlink":
        names = _read_json(Path(args.names), {}) if args.names else {}
        for name in args.files:
            summary = ingest_starlink_file(roots, Path(name), names=names)
            print(json.dumps({k: summary[k] for k in ("filename", "spacecraft", "norad",
                                                      "records", "covarianceFrame")},
                             sort_keys=True))
        return 0

    return 1


def cli(argv: Sequence[str] | None = None) -> int:
    """A refusal must leave a non-zero status.

    A wrapper that reads a traceback on standard error and a zero exit code
    concludes the fetch succeeded, which is the opposite of what happened.
    """
    try:
        return main(argv)
    except Refused as refusal:
        print(f"refused: {refusal}", file=sys.stderr)
        return 2
    except Halted as halt:
        print(f"halted: {halt}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(cli())
