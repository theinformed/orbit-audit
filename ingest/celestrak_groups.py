#!/usr/bin/env python3
"""The one guard every caller that writes ``GROUP=`` into a CelesTrak URL uses.

WHY THIS FILE EXISTS
--------------------
CelesTrak answers a request for a group it does not publish with **HTTP 200**
and a plain-text body::

    Invalid query: "GROUP=swarm&FORMAT=json" (GROUP=swarm not found)

It does that even when ``FORMAT=json`` was asked for. So a status-code check
sees success, JSON parsing blows up or does not depending on the caller, and
nothing anywhere reports a failure.

This project shipped five names that do not exist -- ``noaa``, ``swarm``,
``molniya``, ``raduga`` and ``gorizont`` -- and asked CelesTrak for them on a
weekly timer for an unknown length of time before anyone noticed. They were
removed from the consumer table in 9be75d0 and from the mirror on 2026-08-18.

That fix was to the DATA. The knowledge lived only in two code comments, which
is not a guard: the next person to add a plausible-sounding group name gets the
identical silent failure. This file is the MECHANISM, so the mistake reports
itself on the first request instead of never.

WHAT IT GUARANTEES
------------------
1. A body carrying the ``Invalid query`` marker is a hard failure, whatever the
   status code said.
2. A body that is not JSON is a hard failure, whatever the status code said.
3. The offending group name is written to a ledger on disk, so the failure
   outlives the log line that reported it and an operator can see it on the
   watchdog page and in the daily politeness check.
4. A group in that ledger is never asked for again until a human clears it.
   That is the politeness half: the original incident was not one bad request,
   it was one bad request repeated forever.
5. The mirror treats one bad group as a permanent global halt. Once the
   upstream has rejected any query, no other query is attempted until a human
   fixes the configured list and records why resuming is safe.

WHAT IT DELIBERATELY DOES NOT DO
--------------------------------
It never makes a network request, and nothing here validates the configured
group list against the live service. Checking 19 names against celestrak.org on
a schedule would trade one politeness problem for another. The offline checks
below are shape checks and a list of names measured to be absent; the live
answer is learned once, from the one request the group was going to make
anyway, and then remembered.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import tempfile
import urllib.parse
from pathlib import Path
from typing import Any, Iterable, Sequence

#: The literal CelesTrak puts at the front of the body when the query is bad.
#: Matched against the head of the response only, so a satellite that somehow
#: had this phrase in its name could not trip it.
INVALID_QUERY_MARKER = "invalid query"

#: How much of the body is examined for the marker. CelesTrak puts it first;
#: a real GP payload starts ``[{"OBJECT_NAME":`` within the first few bytes.
MARKER_WINDOW = 400

#: Names this project actually shipped and that CelesTrak does not publish,
#: each measured from the VPS -- the only host permitted to reach
#: celestrak.org. Configuring any of them again is a hard error at import time,
#: with no request made to find out.
KNOWN_ABSENT_GROUPS = frozenset({"noaa", "swarm", "molniya", "raduga", "gorizont"})

#: Group names that must NEVER appear in a ``gp.php`` URL, and the plain reason
#: for each. This is the compliance contract expressed as a mechanism instead of
#: a docstring: on 2026-08-26 the mirror's own header said the Active GP file was
#: "never requested" while the code below it requested it every two hours, and
#: CelesTrak answered the fifth identical download of the day with HTTP 403.
#:
#: These are NOT "names CelesTrak does not publish" -- CelesTrak publishes every
#: one of them. They are names this project is not allowed to ask for. Keep the
#: two ideas apart: KNOWN_ABSENT_GROUPS is about what exists, this is about what
#: we are entitled to take.
#:
#: Keys are lower-case; lookup lower-cases the caller's name, so ``iridium-NEXT``
#: and ``Active`` are caught as well.
#:
#: Adding a name here is cheap. Removing one requires changing
#: ``docs/CELESTRAK-COMPLIANCE.md`` first, because that document is what the
#: removal would be contradicting.
_DUPLICATE_BULK = (
    "Space-Track already supplies every orbital element this site draws, so "
    "asking CelesTrak for the same objects is duplicate bulk data. CelesTrak "
    "answered exactly this request with HTTP 403 one-download-per-update "
    "enforcement on 2026-08-26 after five identical downloads in one day"
)
_OVERLAPPING_SUBSET = (
    "a large constellation subset of the Active catalogue. CelesTrak's usage "
    "policy names Active-plus-a-large-subset as the overlap it enforces "
    "against, and every object in it is already identified by OBJECT_NAME in "
    "data the site already holds"
)
_NOT_A_MISSION = (
    "an orbit-regime, brightness or time-window alias, not a mission category. "
    "It carries no evidence about what the spacecraft is for, which is the only "
    "reason this project is allowed to fetch a group at all"
)

FORBIDDEN_GP_GROUPS: dict[str, str] = {
    "active": _DUPLICATE_BULK,
    "analyst": _DUPLICATE_BULK,
    "starlink": _OVERLAPPING_SUBSET,
    "oneweb": _OVERLAPPING_SUBSET,
    "kuiper": _OVERLAPPING_SUBSET,
    "qianfan": _OVERLAPPING_SUBSET,
    "hulianwang": _OVERLAPPING_SUBSET,
    "globalstar": _OVERLAPPING_SUBSET,
    "iridium": _OVERLAPPING_SUBSET,
    "iridium-next": _OVERLAPPING_SUBSET,
    "orbcomm": _OVERLAPPING_SUBSET,
    "planet": _OVERLAPPING_SUBSET,
    "spire": _OVERLAPPING_SUBSET,
    "ses": _OVERLAPPING_SUBSET,
    "intelsat": _OVERLAPPING_SUBSET,
    "eutelsat": _OVERLAPPING_SUBSET,
    "telesat": _OVERLAPPING_SUBSET,
    "geo": _NOT_A_MISSION,
    "gpz": _NOT_A_MISSION,
    "gpz-plus": _NOT_A_MISSION,
    "visual": _NOT_A_MISSION,
    "last-30-days": _NOT_A_MISSION,
    "tle-new": _NOT_A_MISSION,
    "cosmos-1408-debris": _NOT_A_MISSION,
    "cosmos-2251-debris": _NOT_A_MISSION,
    "fengyun-1c-debris": _NOT_A_MISSION,
    "iridium-33-debris": _NOT_A_MISSION,
}

#: The one documented GP path. Written once, here, so that a grep for
#: ``gp.php`` in any other module is itself the bug report.
GP_PATH = "/NORAD/elements/gp.php"

#: The SATCAT record path. ``GROUP=active`` on THIS path is the small
#: operational-status directory the site legitimately uses, and it is a
#: different endpoint from the GP bulk file above. Conflating the two is how
#: the 2026-08-26 incident was nearly mis-diagnosed.
SATCAT_PATH = "/satcat/records.php"


class ForbiddenCelestrakGroup(RuntimeError):
    """A ``gp.php`` request was built for a group the contract excludes.

    Deliberately not an ``InvalidCelestrakGroup``: that one means CelesTrak said
    no. This one means WE said no, before a socket existed, and no amount of
    upstream good behaviour makes it acceptable. It must never be caught by a
    handler that treats upstream trouble as retryable.
    """

    def __init__(self, group: str, where: str, reason: str) -> None:
        self.group = group
        self.where = where
        self.reason = reason
        super().__init__(
            f"REFUSING to build a CelesTrak gp.php request for GROUP={group!r} "
            f"({where}): {reason}. See docs/CELESTRAK-COMPLIANCE.md."
        )


def forbidden_gp_reason(group: str | None) -> str | None:
    """Why this group may not be requested from gp.php, or None if it may."""
    if not isinstance(group, str):
        return None
    return FORBIDDEN_GP_GROUPS.get(group.strip().lower())


def forbidden_gp_groups(groups: Iterable[str]) -> list[tuple[str, str]]:
    """(name, reason) for every configured name that gp.php must never see.

    Shaped like ``malformed_group_names`` so a caller can concatenate the two
    into one "this list cannot be used" report. Kept SEPARATE from that function
    on purpose: the publisher legitimately holds names such as ``starlink`` as
    mirror FILE names to read from disk, and only the act of putting one into an
    outbound gp.php URL is forbidden.
    """
    problems: list[tuple[str, str]] = []
    for name in groups:
        reason = forbidden_gp_reason(name)
        if reason:
            problems.append((name, f"must never be requested from gp.php: {reason}"))
    return problems


def assert_gp_group_allowed(group: str, *, where: str) -> None:
    """Raise ForbiddenCelestrakGroup unless gp.php may be asked for this group."""
    reason = forbidden_gp_reason(group)
    if reason:
        raise ForbiddenCelestrakGroup(group, where, reason)


def gp_url(group: str, *, base: str = "https://celestrak.org", where: str, fmt: str = "json") -> str:
    """The ONLY supported way to build a CelesTrak GP URL.

    Every gp.php URL in this project comes from here, so the contract is checked
    on the single path that can produce one rather than restated in a comment
    beside each construction site.
    """
    if not isinstance(group, str) or not group.strip():
        raise ValueError(f"gp_url() needs a group name ({where})")
    group = group.strip()
    assert_gp_group_allowed(group, where=where)
    problems = malformed_group_names([group])
    if problems:
        raise ValueError(
            f"gp_url() refused {group!r} ({where}): "
            + "; ".join(reason for _name, reason in problems)
        )
    return f"{base}{GP_PATH}?GROUP={group}&FORMAT={fmt}"


#: Shape of a CelesTrak group name. Case is allowed because ``iridium-NEXT``
#: is a real group name; whitespace, slashes and query punctuation are not,
#: because a name carrying them is a construction bug, not a wrong guess.
WELL_FORMED_GROUP = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")

#: File name of the quarantine ledger inside whichever state directory the
#: caller owns. The mirror keeps its state in ingest/state on the VPS; the
#: publisher keeps its in pipeline/.cache on bigmem.
LEDGER_NAME = "invalid-groups.json"

LEDGER_SCHEMA = 1


class InvalidCelestrakGroup(RuntimeError):
    """CelesTrak said the group does not exist, in a 200.

    Deliberately NOT a subclass of anything the existing call sites already
    catch as "upstream is having a bad day". A transient outage should be
    retried later; a group name that does not exist never will be, and the two
    must not share a code path or the bad name goes back to being invisible.
    """

    def __init__(self, group: str | None, url: str, detail: str, excerpt: str = "") -> None:
        self.group = group
        self.url = url
        self.detail = detail
        self.excerpt = excerpt
        super().__init__(
            f"CelesTrak group {group!r} is not a group CelesTrak publishes: {detail}"
            if group else f"invalid CelesTrak response from {url}: {detail}"
        )


def group_from_url(url: str) -> str | None:
    """The GROUP= value in a CelesTrak URL, or None if there is not one."""
    try:
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
    except ValueError:
        return None
    for key in ("GROUP", "group"):
        values = query.get(key)
        if values:
            return values[0]
    return None


def looks_like_invalid_query(body: bytes | str) -> bool:
    """True when the body is CelesTrak telling us the query was bad."""
    if isinstance(body, bytes):
        head = body[:MARKER_WINDOW].decode("utf-8", errors="replace")
    else:
        head = body[:MARKER_WINDOW]
    return INVALID_QUERY_MARKER in head.lower()


def validate_group_body(body: bytes | str, *, url: str = "", group: str | None = None) -> Any:
    """Parse a CelesTrak group response, or raise InvalidCelestrakGroup.

    Returns the decoded records. Raising is the whole point: every caller
    passes this as a validator so that a 200 carrying ``Invalid query`` can
    never be mistaken for data.
    """
    if group is None and url:
        group = group_from_url(url)
    raw = body.encode("utf-8") if isinstance(body, str) else body
    excerpt = raw[:MARKER_WINDOW].decode("utf-8", errors="replace").strip()

    if not raw.strip():
        raise InvalidCelestrakGroup(group, url, "the response body was empty", excerpt)
    if looks_like_invalid_query(raw):
        raise InvalidCelestrakGroup(
            group, url,
            "CelesTrak answered HTTP 200 with its plain-text \"Invalid query\" "
            "refusal, which means it does not publish a group by this name",
            excerpt,
        )
    try:
        records = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise InvalidCelestrakGroup(
            group, url,
            f"the response is not JSON even though FORMAT=JSON was requested ({error})",
            excerpt,
        ) from error
    if not isinstance(records, (list, dict)):
        raise InvalidCelestrakGroup(
            group, url,
            f"the response parsed as {type(records).__name__}, not the array of "
            "records a GROUP query returns",
            excerpt,
        )
    return records


def group_validator(url: str):
    """A ``validator=`` callable for pipeline fetchers, bound to one URL."""
    group = group_from_url(url)

    def validate(body: bytes) -> Any:
        return validate_group_body(body, url=url, group=group)

    return validate


# ---------------------------------------------------------------------------
# The ledger. A log line scrolls away; this does not.
# ---------------------------------------------------------------------------

def ledger_path(directory: str | os.PathLike[str]) -> Path:
    return Path(directory) / LEDGER_NAME


def read_ledger(directory: str | os.PathLike[str]) -> dict[str, dict]:
    """Group name -> record. Unreadable ledger reads as empty, never as fatal."""
    try:
        path = ledger_path(directory)
        payload = json.loads(path.read_text())
    except (OSError, ValueError):
        # ValueError covers both a malformed ledger and an unusable path (an
        # embedded null byte raises ValueError, not OSError). Neither is worth
        # taking a run down for: an unreadable ledger reads as empty.
        return {}
    if not isinstance(payload, dict):
        return {}
    groups = payload.get("groups")
    if isinstance(groups, dict):
        return groups
    if "schema" in payload:
        return {}
    # Ledgers written before the {"schema", "groups"} wrapper existed are a flat
    # name -> record map. Reading one as empty silently un-quarantines names
    # CelesTrak has already rejected, which is the exact repetition that got
    # this installation firewalled in the first place, so the old shape is read
    # rather than discarded.
    if payload and all(isinstance(row, dict) for row in payload.values()):
        return payload
    return {}


def quarantined_groups(directory: str | os.PathLike[str]) -> set[str]:
    """Names that must not be requested again until a human clears them."""
    return set(read_ledger(directory))


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(descriptor, "w") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o644)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def record_invalid_group(
    directory: str | os.PathLike[str],
    error: InvalidCelestrakGroup,
    *,
    seen_by: str = "",
) -> dict:
    """Write the failure down. Returns the ledger row.

    Recording must never itself break a run, so an unwritable state directory
    degrades to "we could not remember this" rather than to an exception --
    but the caller has already logged the failure loudly by then, and the run
    exit status will still be non-zero.
    """
    group = error.group or "(no GROUP= in the URL)"
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    ledger = read_ledger(directory)
    row = ledger.get(group) or {"group": group, "firstSeen": now, "count": 0}
    row.update({
        "group": group,
        "url": error.url,
        "detail": error.detail,
        "excerpt": error.excerpt[:200],
        "lastSeen": now,
        "count": int(row.get("count", 0)) + 1,
        "seenBy": seen_by or row.get("seenBy", ""),
        "note": (
            "This group is QUARANTINED: nothing will request it again until a "
            "human removes it from the configured list and clears this row. "
            "Clearing it without removing the name just restarts the pointless "
            "weekly request."
        ),
    })
    ledger[group] = row
    try:
        _atomic_write(
            ledger_path(directory),
            json.dumps({"schema": LEDGER_SCHEMA, "groups": ledger}, indent=2, sort_keys=True) + "\n",
        )
    except (OSError, ValueError):
        pass
    return row


def clear_ledger(directory: str | os.PathLike[str], group: str | None = None) -> list[str]:
    """Forget one quarantined group, or all of them. Returns what was cleared."""
    ledger = read_ledger(directory)
    if group is None:
        cleared = sorted(ledger)
        ledger = {}
    elif group in ledger:
        cleared = [group]
        ledger.pop(group)
    else:
        return []
    path = ledger_path(directory)
    if ledger:
        _atomic_write(path, json.dumps({"schema": LEDGER_SCHEMA, "groups": ledger}, indent=2, sort_keys=True) + "\n")
    else:
        try:
            path.unlink(missing_ok=True)
        except (OSError, ValueError):
            pass
    return cleared


# ---------------------------------------------------------------------------
# Offline checks on the configured list. No network, ever.
# ---------------------------------------------------------------------------

def malformed_group_names(groups: Iterable[str]) -> list[tuple[str, str]]:
    """(name, reason) for every configured name that cannot be right.

    Shape only, plus the five names measured absent. This cannot tell you a
    plausible new name exists -- only the first request can, and the guard
    above makes that request report itself.
    """
    problems: list[tuple[str, str]] = []
    seen: set[str] = set()
    for name in groups:
        if not isinstance(name, str) or not name.strip():
            problems.append((repr(name), "is empty or not a string"))
            continue
        if name != name.strip():
            problems.append((name, "has leading or trailing whitespace"))
        if not WELL_FORMED_GROUP.match(name.strip()):
            problems.append((name, "is not a well-formed CelesTrak group name"))
        if name.strip().lower() in KNOWN_ABSENT_GROUPS:
            problems.append((
                name,
                "was measured from the VPS and CelesTrak does not publish it; "
                "asking for it returns HTTP 200 with a plain-text \"Invalid query\"",
            ))
        if name in seen:
            problems.append((name, "is listed twice, so it would be fetched twice"))
        seen.add(name)
    return problems


def assert_group_list_is_sane(groups: Sequence[str], *, where: str) -> None:
    """Refuse to start with a group list that cannot work. Offline."""
    problems = malformed_group_names(groups)
    if not problems:
        return
    lines = "\n".join(f"  - {name}: {reason}" for name, reason in problems)
    raise ValueError(
        f"{where} configures CelesTrak group name(s) that cannot work:\n{lines}\n"
        "Fix the list. Do not verify names by querying celestrak.org from anywhere "
        "except the VPS, and never on a schedule."
    )


def ledger_sentence(ledger: dict[str, dict]) -> str:
    """One plain sentence about the ledger, for an operator-facing surface."""
    if not ledger:
        return "No CelesTrak group has been rejected as non-existent."
    names = ", ".join(sorted(ledger))
    return (
        f"CelesTrak REJECTED {len(ledger)} configured group name(s) as non-existent: "
        f"{names}. It answered HTTP 200 with a plain-text \"Invalid query\", so nothing "
        "would have noticed. Each is quarantined and will not be requested again. "
        "Remove the name from the configured list, then clear the ledger."
    )
