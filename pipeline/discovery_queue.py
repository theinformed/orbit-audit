#!/usr/bin/env python3
"""The review queue: append-only, hash-chained, and with no way to publish.

Stage three of the discovery feature. ``pipeline/discovery.py`` finds a
departure and measures it; ``pipeline/discovery_literature.py`` goes and asks
whether anybody has already written it up; and everything either of them
produces lands here, where it waits for a person.

The ledger design is lifted deliberately from
``docs/mission-speculation-design.md`` Section 5, because the discipline there
was worked out for exactly this problem and re-inventing it would only lose the
parts that were paid for.

Three streams, joined by ``candidateId``
----------------------------------------
``data/discovery-queue.jsonl``
    One line per candidate, as detected. Never rewritten.
``data/discovery-literature.jsonl``
    One line per literature check. A separate stream because the check happens
    minutes to days after detection, and rewriting the candidate line to attach
    a result would destroy the append-only property.
``data/discovery-reviews.jsonl``
    One line per human decision. Also separate, and for the same reason: a
    verdict arrives long after the finding, and often more than once.

Why append-only with a hash chain
---------------------------------
The queue is the record of what this site thought was interesting and what it
decided to do about it. If a finding can be quietly edited or removed after the
fact, the queue is not evidence of anything. ``prevHash`` is the SHA-256 of the
previous line, so reordering, editing, or deleting a line anywhere in the file
breaks every hash after it and ``verify_chain()`` names the first line that
broke. That turns "trust us, this is append-only" into something a reader can
check with a hashing tool and twenty lines of script.

Rules that keep it honest
-------------------------
1. **Decisions are human-entered only.** ``recordedBy`` must begin with
   ``human:``. A model may not approve, reject, or withdraw anything, and there
   is no argument that would make it acceptable: a system that grades its own
   homework produces a meaningless scoreboard. This is the same rule as "the
   model decorates, never gates", applied to the accountability record itself.
2. **The eligibility gate runs before the write, not before the render.** The
   queue is permanent. Nothing about an object denied by
   ``pipeline.discovery.eligible()`` may ever enter it, not even in a field
   nobody displays. ``append_candidates()`` re-checks rather than trusting the
   detector.
3. **Deduplication by tolerance-quantised fingerprint.** The publish timer runs
   every five minutes over thousands of objects; an exact hash over drifting
   values re-fires forever. The fingerprint is computed over a quantised
   snapshot, so ordinary element churn does not manufacture a new finding.
4. **A growth cap per run**, so a bug in the fingerprint cannot silently
   produce a hundred-megabyte file. When the cap binds it is logged, not
   swallowed.
5. **Schema closure.** A record carrying a field outside the schema is
   rejected, and so is any field that would relate two spacecraft —
   ``relatedObjects``, ``planeMates``, ``associatedWith``, ``pairing``,
   ``coOrbital``. ``docs/mission-speculation-design.md`` Section 1.6 is a
   decision by the site owner, who is a serving US information warfare officer,
   and the ledger is the only artifact here that is permanent, so a relational
   field that merely went unrendered would still be a published correlation.
6. **There is no publish function.** Not a disabled one, not one behind a flag,
   not one behind an environment variable — there is no code path in this
   module or in ``pipeline/discovery.py`` that writes into
   ``public/data/artifacts/`` or into ``manifest.json``.
   ``tests/test_discovery_queue.py`` asserts the absence by parsing the source,
   because a flag can be flipped by anyone in a hurry and a missing function
   cannot. Approving a finding changes what an operator-only page says about it
   and nothing else; putting it on the public site is a separate, deliberate,
   human act with its own review.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

from pipeline.discovery import CANDIDATE_CLASSES, Candidate, eligible

ROOT = Path(__file__).resolve().parents[1]
QUEUE_PATH = ROOT / "data" / "discovery-queue.jsonl"
LITERATURE_PATH = ROOT / "data" / "discovery-literature.jsonl"
REVIEWS_PATH = ROOT / "data" / "discovery-reviews.jsonl"

SCHEMA_VERSION = 1

# Rule 4. Chosen so that a full first run of every detector fits comfortably
# and a runaway does not. When it binds, the run says so.
MAX_APPENDS_PER_RUN = 200

# Rule 1.
HUMAN_PREFIX = "human:"

DECISIONS = frozenset(
    {
        # A reviewer has read the evidence and the literature searches and is
        # content for this to be written up. It still publishes nothing.
        "approved",
        # Not interesting, or not sound. Says why.
        "rejected",
        # Interesting, but the evidence or the literature search is not good
        # enough yet. Says what is missing.
        "needs-more-evidence",
        # Approved earlier, and now retracted. The original line stays exactly
        # as written; this is a new line.
        "withdrawn",
    }
)

# Rule 5. Any of these appearing anywhere in a record, at any depth, is a hard
# rejection rather than a stripped field, because a silently stripped field
# looks like it worked.
FORBIDDEN_FIELDS = frozenset(
    {
        "relatedObjects",
        "planeMates",
        "associatedWith",
        "pairing",
        "coOrbital",
        "coplanarWith",
        "neighbours",
        "neighbors",
        "cohortMembers",
        "members",
    }
)

_CANDIDATE_FIELDS = frozenset(
    {
        "schema",
        "candidateId",
        "prevHash",
        "recordedAt",
        "detectorVersion",
        "class",
        "subject",
        "subjectKey",
        "headline",
        "measured",
        "expected",
        "margin",
        "observedWindow",
        "reproduce",
        "alternativeExplanations",
        "fingerprint",
        "status",
        "honesty",
    }
)

_LITERATURE_FIELDS = frozenset(
    {
        "schema",
        "candidateId",
        "prevHash",
        "recordedAt",
        "recordedBy",
        "searches",
        "foundPriorWork",
        "results",
        "absenceMeaning",
        "toolVersion",
    }
)

_REVIEW_FIELDS = frozenset(
    {
        "schema",
        "candidateId",
        "prevHash",
        "recordedAt",
        "recordedBy",
        "decision",
        "reason",
        "supersedes",
    }
)

# Code owns this sentence and a model may never phrase it. It is the entire
# honesty property of the feature, and a caveat a model can phrase is a caveat
# a model can weaken.
HONESTY_LABEL = (
    "This is something the site noticed, not something the site discovered. The "
    "numbers and the threshold are shown so you can disagree with both. If no "
    "prior publication turned up, that may mean the finding is uninteresting, or "
    "that it is already known under a name we did not search for, or simply that "
    "we searched badly — an absence of results is not a claim of novelty."
)

ABSENCE_MEANING = (
    "No prior publication was found by the searches listed above. That is not "
    "evidence of novelty. It may mean the finding is uninteresting, that it is "
    "published under terminology these queries did not cover, that it sits in a "
    "conference proceeding or an operator's own bulletin that these indexes do "
    "not carry, or that the searches were simply bad. Every query that was run "
    "is recorded so someone can improve on them."
)


class QueueError(RuntimeError):
    """A write that would have damaged the record. Never swallowed."""


# ---------------------------------------------------------------------------
# The chain
# ---------------------------------------------------------------------------
def _canonical(record: dict[str, Any]) -> bytes:
    return json.dumps(record, sort_keys=True, separators=(",", ":")).encode()


def _line_hash(line: str) -> str:
    return hashlib.sha256(line.rstrip("\n").encode()).hexdigest()


def read_lines(path: Path) -> list[dict[str, Any]]:
    """Every record in a stream, in order. A missing stream is empty, not an error."""
    if not path.is_file():
        return []
    out: list[dict[str, Any]] = []
    for number, raw in enumerate(path.read_text().splitlines(), start=1):
        if not raw.strip():
            continue
        try:
            out.append(json.loads(raw))
        except json.JSONDecodeError as error:
            raise QueueError(f"{path}: line {number} is not JSON: {error}") from error
    return out


def chain_head(path: Path) -> str | None:
    """SHA-256 of the last line, which is what the next line must reference."""
    if not path.is_file():
        return None
    lines = [line for line in path.read_text().splitlines() if line.strip()]
    return _line_hash(lines[-1]) if lines else None


def verify_chain(path: Path) -> dict[str, Any]:
    """Walk the chain and name the first line that broke it.

    Returns rather than raises, because the caller is usually a report that
    wants to *display* the damage. A tampered ledger is a finding in its own
    right and hiding it behind an exception helps nobody.
    """
    if not path.is_file():
        return {"path": str(path), "lines": 0, "intact": True, "head": None}
    previous: str | None = None
    lines = [line for line in path.read_text().splitlines() if line.strip()]
    for number, raw in enumerate(lines, start=1):
        try:
            record = json.loads(raw)
        except json.JSONDecodeError:
            return {"path": str(path), "lines": number, "intact": False,
                    "brokeAt": number, "reason": "not JSON", "head": None}
        if record.get("prevHash") != previous:
            return {
                "path": str(path),
                "lines": len(lines),
                "intact": False,
                "brokeAt": number,
                "reason": (
                    f"prevHash is {record.get('prevHash')!r}, but the previous line hashes "
                    f"to {previous!r}"
                ),
                "head": None,
            }
        previous = _line_hash(raw)
    return {"path": str(path), "lines": len(lines), "intact": True, "head": previous}


def _reject_forbidden(record: Any, trail: str = "") -> None:
    """Rule 5, applied at every depth rather than only at the top level."""
    if isinstance(record, dict):
        for key, value in record.items():
            if key in FORBIDDEN_FIELDS:
                raise QueueError(
                    f"refusing to write a relational field {trail}{key!r}: "
                    "docs/mission-speculation-design.md Section 1.6 excludes object-to-object "
                    "association structurally, and this ledger is permanent"
                )
            _reject_forbidden(value, f"{trail}{key}.")
    elif isinstance(record, list):
        for item in record:
            _reject_forbidden(item, trail)


def _check_fields(record: dict[str, Any], allowed: frozenset[str], kind: str) -> None:
    unknown = set(record) - allowed
    if unknown:
        raise QueueError(f"unknown field(s) on a {kind} record: {sorted(unknown)}")


def _append(path: Path, record: dict[str, Any]) -> str:
    """Append one line, chained to whatever is already there.

    Opened in append mode and written as a single line, so an interrupted run
    cannot leave a half-record: either the line is there or it is not.
    """
    _reject_forbidden(record)
    record = {**record, "prevHash": chain_head(path)}
    line = _canonical(record).decode()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")
    return _line_hash(line)


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def candidate_id(candidate: Candidate) -> str:
    """Stable identity: the same finding gets the same id across runs.

    Derived from the deduplication key rather than from a random value, so a
    literature check recorded against a candidate still joins after a re-run
    that produced the identical finding.
    """
    key = f"{candidate.candidate_class}|{candidate.subject.key}|{candidate.detector_version}|{candidate.fingerprint}"
    return "disc-" + hashlib.sha256(key.encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Writing
# ---------------------------------------------------------------------------
def existing_keys(path: Path = QUEUE_PATH) -> set[tuple[str, str, str, str]]:
    return {
        (
            str(record.get("class")),
            str(record.get("subjectKey")),
            str(record.get("detectorVersion")),
            str(record.get("fingerprint")),
        )
        for record in read_lines(path)
    }


def append_candidates(
    candidates: Sequence[Candidate],
    *,
    path: Path = QUEUE_PATH,
    catalog: dict[int, dict[str, Any]] | None = None,
    cap: int = MAX_APPENDS_PER_RUN,
    now: str | None = None,
) -> dict[str, Any]:
    """Queue every genuinely new candidate. Returns what happened, including refusals."""
    catalog = catalog or {}
    seen = existing_keys(path)
    appended: list[str] = []
    duplicates = 0
    denied = 0
    capped = False

    for candidate in candidates:
        if candidate.candidate_class not in CANDIDATE_CLASSES:
            raise QueueError(f"unknown candidate class: {candidate.candidate_class!r}")
        # Rule 2: re-check the gate at the write, never trust the caller.
        if candidate.subject.kind == "object":
            record = catalog.get(candidate.subject.norad or -1, {})
            if not eligible(record, candidate.subject.name):
                denied += 1
                continue
        key = (
            candidate.candidate_class,
            candidate.subject.key,
            candidate.detector_version,
            candidate.fingerprint,
        )
        if key in seen:
            duplicates += 1
            continue
        if len(appended) >= cap:
            capped = True
            break
        payload = {
            "schema": SCHEMA_VERSION,
            "candidateId": candidate_id(candidate),
            "recordedAt": now or _now(),
            "status": "open",
            "honesty": HONESTY_LABEL,
            **candidate.as_dict(),
        }
        _check_fields(payload, _CANDIDATE_FIELDS, "candidate")
        _append(path, payload)
        seen.add(key)
        appended.append(payload["candidateId"])

    return {
        "appended": appended,
        "appendedCount": len(appended),
        "duplicates": duplicates,
        "deniedByEligibilityGate": denied,
        "capBound": capped,
        "cap": cap,
        "head": chain_head(path),
    }


def append_literature(
    candidate_key: str,
    *,
    searches: Sequence[dict[str, Any]],
    results: Sequence[dict[str, Any]],
    recorded_by: str,
    found_prior_work: bool | None = None,
    path: Path = LITERATURE_PATH,
    tool_version: str | None = None,
    now: str | None = None,
) -> str:
    """Record one literature check, whatever it found.

    A hit and a miss are both recorded, and the record always carries the
    queries that were run. A search whose queries are not written down is not
    evidence of anything, in either direction.
    """
    if not searches:
        raise QueueError("a literature record with no searches is not a literature check")
    payload = {
        "schema": SCHEMA_VERSION,
        "candidateId": candidate_key,
        "recordedAt": now or _now(),
        "recordedBy": recorded_by,
        "searches": list(searches),
        "results": list(results),
        # Whether prior work was found is decided by the caller's relevance
        # rule, not by "did any query return anything". Every index returns
        # something for almost any query; treating a non-empty response as a
        # hit would mark every candidate as already known and quietly disable
        # the whole check.
        "foundPriorWork": bool(results) if found_prior_work is None else bool(found_prior_work),
        "absenceMeaning": ABSENCE_MEANING,
        "toolVersion": tool_version,
    }
    _check_fields(payload, _LITERATURE_FIELDS, "literature")
    _append(path, payload)
    return payload["candidateId"]


def append_review(
    candidate_key: str,
    *,
    decision: str,
    reason: str,
    recorded_by: str,
    supersedes: str | None = None,
    path: Path = REVIEWS_PATH,
    now: str | None = None,
) -> str:
    """Record one human decision. Rule 1 is enforced here and nowhere else is enough."""
    if decision not in DECISIONS:
        raise QueueError(f"unknown decision: {decision!r}; expected one of {sorted(DECISIONS)}")
    if not recorded_by.startswith(HUMAN_PREFIX):
        raise QueueError(
            f"recordedBy must name a person and begin with {HUMAN_PREFIX!r}; got "
            f"{recorded_by!r}. No model, scraper, or heuristic may enter a decision: a system "
            "that grades its own homework produces a meaningless scoreboard."
        )
    if not reason.strip():
        raise QueueError("a decision with no stated reason is not reviewable")
    payload = {
        "schema": SCHEMA_VERSION,
        "candidateId": candidate_key,
        "recordedAt": now or _now(),
        "recordedBy": recorded_by,
        "decision": decision,
        "reason": reason.strip(),
        "supersedes": supersedes,
    }
    _check_fields(payload, _REVIEW_FIELDS, "review")
    _append(path, payload)
    return payload["candidateId"]


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------
@dataclass
class QueueEntry:
    candidate: dict[str, Any]
    literature: list[dict[str, Any]]
    reviews: list[dict[str, Any]]

    @property
    def state(self) -> str:
        """The current state, derived from the streams rather than stored.

        Nothing is ever rewritten, so state is always the newest decision. An
        entry with no decision is ``awaiting-review``; one whose literature
        check found prior work is ``prior-work-found`` until somebody looks,
        because that is a genuinely different thing to hand a reviewer.
        """
        if self.reviews:
            return self.reviews[-1]["decision"]
        if any(record.get("foundPriorWork") for record in self.literature):
            return "prior-work-found"
        if self.literature:
            return "searched-nothing-found"
        return "awaiting-review"

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidate": self.candidate,
            "literature": self.literature,
            "reviews": self.reviews,
            "state": self.state,
        }


def load_queue(
    *,
    queue_path: Path = QUEUE_PATH,
    literature_path: Path = LITERATURE_PATH,
    reviews_path: Path = REVIEWS_PATH,
) -> list[QueueEntry]:
    """The three streams joined by candidate id, newest candidate first."""
    literature: dict[str, list[dict[str, Any]]] = {}
    for record in read_lines(literature_path):
        literature.setdefault(str(record.get("candidateId")), []).append(record)
    reviews: dict[str, list[dict[str, Any]]] = {}
    for record in read_lines(reviews_path):
        reviews.setdefault(str(record.get("candidateId")), []).append(record)

    entries = [
        QueueEntry(
            candidate=record,
            literature=literature.get(str(record.get("candidateId")), []),
            reviews=reviews.get(str(record.get("candidateId")), []),
        )
        for record in read_lines(queue_path)
    ]
    entries.sort(key=lambda entry: str(entry.candidate.get("recordedAt")), reverse=True)
    return entries


def scoreboard(entries: Iterable[QueueEntry]) -> dict[str, int]:
    """Counts by state. The site's own record, kept where a visitor could check it."""
    counts: dict[str, int] = {}
    for entry in entries:
        counts[entry.state] = counts.get(entry.state, 0) + 1
    return counts


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Append-only discovery review queue.")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("verify", help="check the hash chain of every stream")
    sub.add_parser("list", help="print the joined queue")

    ingest = sub.add_parser(
        "ingest", help="queue the candidates from a sweep artifact"
    )
    ingest.add_argument("sweep_json", type=Path)
    ingest.add_argument("--data-root", type=Path, default=ROOT / "public" / "data")
    ingest.add_argument(
        "--only",
        default=None,
        help="queue a single candidate class from the sweep",
    )
    ingest.add_argument("--cap", type=int, default=MAX_APPENDS_PER_RUN)

    review = sub.add_parser("review", help="record a human decision")
    review.add_argument("candidate_id")
    review.add_argument("--decision", required=True, choices=sorted(DECISIONS))
    review.add_argument("--reason", required=True)
    review.add_argument(
        "--by",
        required=True,
        help="who decided, as human:<name>. A model may not enter a decision.",
    )
    review.add_argument("--supersedes", default=None)

    args = parser.parse_args(argv)

    if args.command == "verify":
        report = {
            "queue": verify_chain(QUEUE_PATH),
            "literature": verify_chain(LITERATURE_PATH),
            "reviews": verify_chain(REVIEWS_PATH),
        }
        print(json.dumps(report, indent=2))
        return 0 if all(stream["intact"] for stream in report.values()) else 1

    if args.command == "ingest":
        from pipeline.orbit_events import load_catalog

        sweep = json.loads(args.sweep_json.read_text())
        records = [
            record
            for record in sweep.get("candidates", [])
            if not args.only or record.get("class") == args.only
        ]
        result = append_candidates(
            [Candidate.from_dict(record) for record in records],
            catalog=load_catalog(args.data_root),
            cap=args.cap,
        )
        print(json.dumps(result, indent=2))
        return 0

    if args.command == "list":
        entries = load_queue()
        print(
            json.dumps(
                {
                    "scoreboard": scoreboard(entries),
                    "entries": [entry.as_dict() for entry in entries],
                },
                indent=2,
            )
        )
        return 0

    append_review(
        args.candidate_id,
        decision=args.decision,
        reason=args.reason,
        recorded_by=args.by,
        supersedes=args.supersedes,
    )
    print(f"recorded {args.decision} for {args.candidate_id}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
