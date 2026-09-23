"""Daily collector for the public operator ephemeris archive. No timer.

T19, registration `docs/t19-covariance-realism-preregistration-20260922.md` §9.

This module ships **no cron entry and no systemd unit**. It takes a clock, so
that every cadence decision it makes can be driven on demand rather than waited
for; a lane that can only be observed tomorrow has not been observed. Who runs
it, and when, is the operator's decision.

Etiquette is inherited wholesale from the T16a ingest registration §4.3 and is
not re-implemented here: the host gate, the 0.5 s gap, no retries, no redirects,
no proxy, the body ceiling, the attempt timestamp written before the socket, the
halt marker, and one ledger line per attempt including the attempts that were
refused.  Two rules are added by the T19 registration §9.1:

    manifest   at most one fetch per 2 h
    passes     at most four per day

and one ceiling is amended: a pass may fetch the **whole manifest** rather than
T16a's 250-file sample, because the distinct-value census of T19 §7 is a
statement about all files of an issue and a distinct-value count is a function
of n.  Fetching every named file once per publication cycle is the same
principle T16a already applies elsewhere -- download once per actual update, and
not again.

A file whose exact name is already on disk is **not requested**.  The published
filename changes when the issue changes, so "already held" and "unchanged" are
the same fact here, and the cheapest possible conditional request is the one
that never opens a socket.

**One transport detail, measured rather than assumed.**  This provider *does*
send ``ETag`` and ``Last-Modified`` (unlike the supplemental element-set
endpoint, which T16a measured as sending neither), so a conditional request can
and does return 304.  The standard library raises ``HTTPError`` for any status
outside 2xx, including a 304 that answers a validator we sent ourselves, and the
inherited engine reads that raised error as a transport-level halt.  A 304 we
asked for is the politest outcome available and must not halt anything, so this
module installs a transport that turns it back into a response.  When the
manifest answers 304 the most recent manifest already on disk is used, which is
exactly what the 304 asserts it is: byte-identical.
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import gzip
import json
import sys
import time
import urllib.error
from pathlib import Path
from typing import Callable, Iterable, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent))

import supgp_ingest as ingest  # noqa: E402  the etiquette engine, reused not forked

MANIFEST_INTERVAL_SECONDS = 2 * 60 * 60
PASSES_PER_DAY = 4
STATE_NAME = "collect-state.json"


class NotDue(RuntimeError):
    """The clock says this pass may not run yet. A refusal, not a failure."""


def transport_honouring_304(url: str, validators: dict) -> ingest.Response:
    """The inherited transport, with an answered 304 returned instead of raised.

    Nothing else is changed: no retry, no redirect, no proxy, the same timeout
    and the same body ceiling.  Every status other than 304 is left to raise
    exactly as before, so a real refusal still halts.
    """
    try:
        return ingest.http_get(url, validators)
    except urllib.error.HTTPError as error:
        if error.code != 304:
            raise
        return ingest.Response(
            status=304,
            body=b"",
            headers={key.lower(): value for key, value in error.headers.items()},
        )


def latest_manifest(roots: ingest.Roots) -> Path | None:
    """The most recently written manifest already on disk."""
    held = sorted(roots.starlink_raw.rglob("MANIFEST-*.txt.gz"))
    return held[-1] if held else None


def _state_path(roots: ingest.Roots) -> Path:
    return roots.state / STATE_NAME


def read_state(roots: ingest.Roots) -> dict:
    return ingest._read_json(_state_path(roots), {"passes": []})


def write_state(roots: ingest.Roots, state: dict) -> None:
    ingest._write_json(_state_path(roots), state)


@dataclasses.dataclass(frozen=True)
class Verdict:
    due: bool
    reason: str
    sinceLastManifestSeconds: float | None
    passesInWindow: int


def due(roots: ingest.Roots, now: dt.datetime) -> Verdict:
    """Whether a pass may start at ``now``.

    The clock is an argument.  Nothing in this function reads the system time,
    so the cadence rules can be exercised at an injected clock against the real
    state file and the real archive.
    """
    state = read_state(roots)
    stamps = []
    for entry in state.get("passes", []):
        try:
            stamps.append(dt.datetime.fromisoformat(entry["startedAt"]))
        except (KeyError, ValueError):
            continue
    last = max(stamps) if stamps else None
    since = (now - last).total_seconds() if last is not None else None
    window = [moment for moment in stamps if (now - moment).total_seconds() < 24 * 3600]

    if len(window) >= PASSES_PER_DAY:
        return Verdict(
            False,
            f"{len(window)} passes already started in the last 24 h; the ceiling is "
            f"{PASSES_PER_DAY}. The operator publishes about three issues a day; a "
            f"fourth pass is slack, not appetite.",
            since,
            len(window),
        )
    if since is not None and since < MANIFEST_INTERVAL_SECONDS:
        return Verdict(
            False,
            f"the manifest was fetched {since:.0f} s ago and the interval is "
            f"{MANIFEST_INTERVAL_SECONDS} s. An interval is a floor on how often we "
            f"may ask, never permission to ask.",
            since,
            len(window),
        )
    return Verdict(
        True,
        "no rule refuses this pass"
        if since is None
        else f"last pass {since:.0f} s ago, {len(window)} in the last 24 h",
        since,
        len(window),
    )


def held_names(roots: ingest.Roots) -> set[str]:
    """Every ephemeris filename already on disk, in any day directory."""
    out: set[str] = set()
    for path in roots.starlink_raw.rglob("MEME_*.txt.gz"):
        out.add(path.name[: -len(".gz")])
    return out


def catalogue_number(name: str) -> str | None:
    """The catalogue field of a published filename: the second field.

    Measured against an independent name join in T16a (249 of 249 agreements,
    zero disagreements), which is why it is used as the join and the name is
    kept only as a cross-check.
    """
    parts = name.split("_")
    if len(parts) < 2 or not parts[1].isdigit():
        return None
    return parts[1]


def run_pass(
    roots: ingest.Roots,
    *,
    now: dt.datetime,
    transport: ingest.Transport = None,
    hostname: str | None = None,
    sleeper: Callable[[float], None] = time.sleep,
    only_missing: bool = True,
    only_catalogues: Iterable[str] | None = None,
    limit: int | None = None,
    sample: int | None = None,
    enforce_due: bool = True,
    progress: Callable[[str], None] | None = None,
    **gate_overrides,
) -> dict:
    """One collection pass: the manifest, then the files it names that we lack.

    ``enforce_due`` can be switched off so that a test can run the same scenario
    twice -- once with the cadence rule and once without -- and assert that the
    unguarded run reproduces the behaviour the rule exists to prevent.
    """
    verdict = due(roots, now)
    if enforce_due and not verdict.due:
        raise NotDue(verdict.reason)

    wanted = set(only_catalogues) if only_catalogues is not None else None
    gate = ingest.RequestGate(
        roots=roots,
        lane="starlink",
        expected_host=ingest.STARLINK_HOST,
        interval_seconds=0.0,  # per-file: a filename is requested at most once, ever
        requests_per_process=10**9,
        gap_seconds=ingest.STARLINK_GAP_SECONDS,
        hostname=hostname,
        **gate_overrides,
    )
    response = ingest.perform(
        roots,
        gate,
        "MANIFEST",
        ingest.STARLINK_MANIFEST,
        transport=transport or transport_honouring_304,
        sleeper=sleeper,
    )
    day = roots.starlink_raw / f"{now:%Y}" / f"{now:%m}" / f"{now:%d}"
    day.mkdir(parents=True, exist_ok=True)
    if response.status == 304:
        manifest_path = latest_manifest(roots)
        if manifest_path is None:
            raise ingest.Refused(
                "the provider answered 304 but no manifest is held on disk; the "
                "validator and the body have come apart and nothing may be inferred"
            )
        manifest_unchanged = True
        with gzip.open(manifest_path, "rb") as handle:
            body = handle.read()
    else:
        manifest_unchanged = False
        manifest_path = day / f"MANIFEST-{ingest.stamp(now)}.txt.gz"
        body = response.body
        with gzip.open(manifest_path, "wb") as handle:
            handle.write(body)

    names = [line.strip() for line in body.decode("ascii").splitlines() if line.strip()]
    already = held_names(roots) if only_missing else set()

    chosen: list[str] = []
    skipped_held = 0
    skipped_catalogue = 0
    for name in names:
        if name in already:
            skipped_held += 1
            continue
        if wanted is not None and catalogue_number(name) not in wanted:
            skipped_catalogue += 1
            continue
        chosen.append(name)
    if sample is not None and sample < len(chosen):
        # The registered deterministic rule: every k-th name, k from the size.
        # A prefix would be a block of the constellation, not a sample of it.
        chosen = ingest.sample_manifest(chosen, sample)
    if limit is not None:
        chosen = chosen[:limit]

    state = read_state(roots)
    state.setdefault("passes", []).append(
        {
            "startedAt": now.isoformat(),
            "manifestNames": len(names),
            "requested": len(chosen),
            "skippedAlreadyHeld": skipped_held,
            "skippedNotRequested": skipped_catalogue,
        }
    )
    write_state(roots, state)

    written: list[str] = []
    failed = 0
    for index, name in enumerate(chosen):
        try:
            file_response = ingest.perform(
                roots,
                gate,
                name,
                ingest.STARLINK_BASE + name,
                transport=transport or transport_honouring_304,
                sleeper=sleeper,
            )
        except ingest.Halted:
            failed += 1
            raise
        if file_response.status == 304:
            continue
        destination = day / (name + ".gz")
        with gzip.open(destination, "wb") as handle:
            handle.write(file_response.body)
        written.append(name)
        if progress is not None and index % 250 == 0:
            progress(f"{index + 1}/{len(chosen)} {name}")

    summary = {
        "startedAt": now.isoformat(),
        "manifest": str(manifest_path),
        "manifestUnchanged": manifest_unchanged,
        "manifestNames": len(names),
        "requested": len(chosen),
        "written": len(written),
        "skippedAlreadyHeld": skipped_held,
        "skippedNotRequested": skipped_catalogue,
        "failed": failed,
        "verdict": dataclasses.asdict(verdict),
    }
    ingest._append_jsonl(roots.captures_ledger, {"lane": "t19-collect", **summary})
    return summary


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=ingest.DEFAULT_ROOT)
    parser.add_argument(
        "--now",
        default=None,
        help="inject the clock (ISO 8601 UTC). Every cadence decision is taken "
        "against this value, so the lane can be exercised rather than waited for.",
    )
    parser.add_argument("--check-only", action="store_true", help="print the verdict, open no socket")
    parser.add_argument("--all", action="store_true", help="request named files even when already held")
    parser.add_argument("--catalogues", type=Path, default=None, help="file of catalogue numbers, one per line")
    parser.add_argument("--limit", type=int, default=None, help="a prefix; prefer --sample")
    parser.add_argument(
        "--sample",
        type=int,
        default=None,
        help="request this many names, spread across the manifest by the "
        "registered deterministic rule rather than taken as a prefix",
    )
    parser.add_argument("--ignore-cadence", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(list(argv) if argv is not None else None)

    roots = ingest.Roots(root=args.root)
    for directory in (roots.starlink_raw, roots.state, roots.requests_ledger.parent):
        directory.mkdir(parents=True, exist_ok=True)
    now = dt.datetime.fromisoformat(args.now) if args.now else ingest.utc_now()
    if now.tzinfo is None:
        now = now.replace(tzinfo=dt.timezone.utc)

    verdict = due(roots, now)
    if args.check_only:
        print(json.dumps({"now": now.isoformat(), **dataclasses.asdict(verdict)}, indent=1))
        return 0 if verdict.due else 3

    catalogues = None
    if args.catalogues is not None:
        catalogues = [line.strip() for line in args.catalogues.read_text().splitlines() if line.strip()]

    try:
        summary = run_pass(
            roots,
            now=now,
            only_missing=not args.all,
            only_catalogues=catalogues,
            limit=args.limit,
            sample=args.sample,
            enforce_due=not args.ignore_cadence,
            progress=lambda text: print(text, flush=True),
        )
    except NotDue as refusal:
        print(json.dumps({"now": now.isoformat(), "due": False, "reason": str(refusal)}, indent=1))
        return 3
    except (ingest.Refused, ingest.Halted) as refusal:
        print(json.dumps({"now": now.isoformat(), "outcome": "refused", "reason": str(refusal)}, indent=1))
        return 4
    print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
