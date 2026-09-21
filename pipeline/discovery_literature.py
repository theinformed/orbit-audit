#!/usr/bin/env python3
"""Stage two: go and find out whether somebody has already published this.

    "see if a publication already knows about it, and if not, throw it in a
    page that brings up how curious it is"

**A hit is a success, not a failure.** This is the part of the feature most
likely to be built backwards, so it is worth being blunt about it: the best
possible outcome of a literature check is *"this is already known, and here is
the paper"*. That result demonstrates that the detector rediscovered a
published finding from raw elements, which is the strongest evidence available
that the method works at all — and it costs nothing, risks nothing, and can be
checked by anyone with the DOI. A finding with **no** prior work is the weaker,
more dangerous outcome, because the honest reading of it is "either nobody
cared, or we searched badly", and there is no way from here to tell which.

So this module records the searches either way, and the queue renders the
absence with that sentence attached, in code-owned copy that no model may
rephrase.

What it searches, and what it cannot
------------------------------------
* **arXiv** — full-text preprint index, an Atom API, no key required. Best
  coverage of the space-physics and astrodynamics preprint literature.
* **Crossref** — the DOI registry, a REST API, no key required. Covers the
  published journal literature broadly, including AGU, AIAA and Elsevier
  titles, but matches on metadata only.
* **NASA ADS** — by far the best index for this subject, and it requires an API
  token this installation does not hold. Rather than pretend, the plan emits a
  ready-made ADS query **URL** for a human to open, and the queue records that
  the ADS arm was not run. An unrun search recorded as unrun is honest; an
  unrun search silently omitted is not.

None of these is space-track or CelesTrak. The orbital-data boundary in
``docs/OPEN-WORK.md`` Section 0 is untouched: this module never fetches
elements, only bibliography.

Where the network is, and is not
--------------------------------
Every HTTP call goes through an injectable ``transport`` callable. The default
uses ``urllib``; the tests pass a fake and therefore run with **no network**,
which is a hard requirement on this project.

Nothing here runs on the five-minute publish timer. Literature indexes are
somebody else's donated infrastructure — this project has already been banned
from one such server for retrying failed requests on a five-minute loop — so
this is an operator-invoked tool with an explicit ``--run`` flag, a request
delay, and a hard stop on any non-200. Halt and tell a human; never retry.
"""

from __future__ import annotations

import argparse
import json
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Sequence

from pipeline.discovery_queue import (
    LITERATURE_PATH,
    QueueEntry,
    append_literature,
    load_queue,
)

TOOL_VERSION = "2026-08-07.1"

ARXIV_ENDPOINT = "https://export.arxiv.org/api/query"
CROSSREF_ENDPOINT = "https://api.crossref.org/works"
ADS_UI = "https://ui.adsabs.harvard.edu/search/q="
# A general web arm, for a person. Never queried automatically -- see search_plan().
WEB_SEARCH_UI = "https://lite.duckduckgo.com/lite/?q="

# One request at a time, with a pause. These indexes are free and shared.
REQUEST_DELAY_SECONDS = 3.0
REQUEST_TIMEOUT_SECONDS = 30.0
MAX_RESULTS = 8

USER_AGENT = (
    "space-environment-explorer/1.0 (teaching site; literature check for a "
    "human review queue; mailto:sean@theinformed.org)"
)

# Terms that describe each candidate class in the language the literature
# actually uses. Hand-written, because a query built by a model is a query
# nobody can audit, and the whole point of recording the searches is that
# somebody can improve on them.
CLASS_TERMS: dict[str, list[str]] = {
    "manoeuvre-out-of-family": [
        "satellite maneuver detection two-line elements",
        "TLE-based maneuver detection anomalous",
        "unusual station-keeping pattern detection catalog",
    ],
    "correlated-shell-decay": [
        "geomagnetic storm thermospheric density enhancement orbital decay",
        "satellite drag storm-time density low Earth orbit",
        "orbital decay rate space weather debris population",
    ],
    "orbit-contradicts-catalog": [
        "geostationary optical remote sensing satellite high resolution imaging",
        "satellite mission orbit regime mismatch catalog attribution",
    ],
    "delta-v-out-of-budget": [
        "station-keeping delta-v budget geostationary measured from elements",
        "large orbital maneuver detection delta-v estimation TLE",
    ],
    "decay-rate-out-of-family": [
        "ballistic coefficient estimation TLE B-star anomalous drag",
        "anomalous orbital decay single object thermosphere",
        # Added after reading a real result. The two candidates this detector
        # produced were objects whose semi-major axis ROSE while their shell
        # fell, and the leading explanation for that is solar radiation
        # pressure on a high area-to-mass fragment -- a well-studied effect
        # that none of the terms above would have found. The queries have to
        # describe the phenomenon the finding is about, not only the
        # measurement technique that surfaced it.
        "high area-to-mass ratio debris solar radiation pressure orbit evolution",
        "semi-major axis increase debris non-gravitational perturbation",
    ],
}


class LiteratureError(RuntimeError):
    """A non-200, a malformed response, or a refusal to guess. Never swallowed."""


# ---------------------------------------------------------------------------
# Transport
# ---------------------------------------------------------------------------
Transport = Callable[[str], bytes]


def urllib_transport(url: str) -> bytes:
    """The default. Halts on any non-200 rather than retrying.

    ``docs/OPEN-WORK.md`` Section 0 records why: this project was banned from
    CelesTrak for retrying queries that had never succeeded, on every
    five-minute cycle, forever. The rule that keeps you out of a firewall is
    stop on error and tell a human, and it applies to every upstream, not only
    the one that did the banning.
    """
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
        if response.status != 200:
            raise LiteratureError(f"{url} returned HTTP {response.status}; stopping")
        return response.read()


def offline_transport(url: str) -> bytes:
    """The default when ``--run`` was not passed. Refuses, loudly."""
    raise LiteratureError(
        f"refusing to fetch {url}: this tool does not touch the network unless "
        "--run is passed explicitly"
    )


# ---------------------------------------------------------------------------
# Query construction — deterministic, and readable by the person auditing it
# ---------------------------------------------------------------------------
_STOP = frozenset({"the", "and", "for", "its", "own", "a", "an", "of", "is", "in", "to"})


def subject_terms(candidate: dict[str, Any]) -> list[str]:
    """Search terms drawn from the candidate itself.

    For an object: its name, with any trailing flight number stripped so that
    ``GAOFEN 13 02`` also searches for the ``GAOFEN`` programme, since a paper
    about the programme is prior work about this object.

    For a shell: the altitude band, because a shell has no name and searching
    for one would be inventing an identity the record deliberately does not
    carry.
    """
    subject = candidate.get("subject") or {}
    if subject.get("kind") == "shell":
        band = subject.get("perigeeAltitudeKm") or []
        if len(band) == 2:
            return [f"{int(band[0])} km altitude thermosphere density", "orbital decay shell"]
        return ["orbital decay altitude shell"]
    name = str(subject.get("name") or "").strip()
    if not name:
        return []
    terms = [name]
    # "GAOFEN 13 02" -> "GAOFEN 13" -> "GAOFEN"
    parts = name.split()
    while len(parts) > 1:
        parts = parts[:-1]
        trimmed = " ".join(parts)
        if trimmed.lower() not in _STOP and not re.fullmatch(r"[\d\W]+", trimmed):
            terms.append(trimmed)
    return terms


# Catalogue labels that mean "an anonymous piece of something", not a
# programme anybody has published about. Anchored on word boundaries so
# "DEBUT-1" is not caught by "DEB".
_FRAGMENT_MARKERS = (
    r"\bDEB\b", r"\bDEBRIS\b", r"\bR/B\b", r"\bAKM\b", r"\bPKM\b",
    r"\bCOOLANT\b", r"\bSHROUD\b", r"\bTANK\b", r"\bPLATFORM\b",
    r"\bOBJECT\b", r"\bFRAGMENT\b", r"\bAUX MOTOR\b",
)


def subject_name(candidate: dict[str, Any]) -> str:
    return str((candidate.get("subject") or {}).get("name") or "")


def _is_anonymous_fragment(name: str, candidate: dict[str, Any]) -> bool:
    """True when the object's catalogue label is not a searchable identity.

    Two independent signals, either of which is enough: the catalogue object
    type says DEBRIS or ROCKET BODY, or the name carries one of the standard
    fragment markers. Both are checked because the subject record does not
    always carry an object type -- a candidate rebuilt from a sweep artifact
    written by an older detector version may not have one, and falling back to
    "this is a programme name" would reintroduce the poisoned query.
    """
    object_type = str((candidate.get("subject") or {}).get("objectType") or "").upper()
    if object_type in ("DEBRIS", "ROCKET BODY", "UNKNOWN"):
        return True
    return any(re.search(marker, name.upper()) for marker in _FRAGMENT_MARKERS)


def search_plan(candidate: dict[str, Any]) -> list[dict[str, Any]]:
    """Every query this candidate should be checked against, before any of them runs.

    Emitted as data so it can be read, argued with, and improved without
    running anything. The plan is what gets recorded alongside the results, so
    a reader can see what was asked as well as what came back.
    """
    subject = subject_terms(candidate)
    klass = str(candidate.get("class"))
    class_terms = CLASS_TERMS.get(klass, [])
    plan: list[dict[str, Any]] = []

    primary = subject[0] if subject else ""
    programme = subject[-1] if len(subject) > 1 else primary

    # Whether the object's name is a searchable identity at all.
    #
    # "GAOFEN 4" is a programme name and narrowing a class term with it is
    # exactly right. "DELTA 1 DEB" is a catalogue label for an anonymous
    # fragment: nobody has ever written a paper about it, and prefixing a class
    # term with it actively poisons the query. Observed live -- searching
    # "DELTA high area-to-mass ratio debris solar radiation pressure" returned
    # condensed-matter papers on the anomalous Hall effect, because Crossref
    # matched on the wrong words entirely.
    #
    # For those objects the finding is about a PHENOMENON, not a spacecraft, so
    # the class terms are searched unqualified. This is the same reasoning that
    # makes a shell subject search by altitude rather than by a name it does
    # not have.
    anonymous = _is_anonymous_fragment(subject_name(candidate), candidate)
    for term in class_terms:
        query = f"{programme} {term}".strip() if programme and not anonymous else term
        plan.append(
            {
                "source": "arxiv",
                "query": query,
                "url": _arxiv_url(query),
                "why": f"class term for {klass}, narrowed by the subject",
            }
        )
        plan.append(
            {
                "source": "crossref",
                "query": query,
                "url": _crossref_url(query),
                "why": f"class term for {klass}, narrowed by the subject",
            }
        )
    if primary and anonymous:
        # Searching a catalogue label for an anonymous fragment is two wasted
        # requests on somebody else's donated server and a guaranteed miss:
        # no paper has ever named this object, and none ever will. Recorded as
        # deliberately not attempted rather than quietly dropped, so the record
        # still shows every arm that was considered.
        plan.append(
            {
                "source": "object-name",
                "query": primary,
                "url": ADS_UI + urllib.parse.quote(f'abs:"{primary}"'),
                "why": (
                    "This object's catalogue label identifies an anonymous fragment, not a "
                    "programme. The finding is about a phenomenon, so the class terms above "
                    "were searched unqualified instead."
                ),
                "reason": "a catalogue label for a fragment is not a searchable identity",
                "run": False,
            }
        )
    elif primary:
        plan.append(
            {
                "source": "arxiv",
                "query": primary,
                "url": _arxiv_url(primary),
                "why": "the object by name, unqualified",
            }
        )
        plan.append(
            {
                "source": "crossref",
                "query": primary,
                "url": _crossref_url(primary),
                "why": "the object by name, unqualified",
            }
        )
        plan.append(
            {
                "source": "ads-manual",
                "query": primary,
                "url": ADS_UI + urllib.parse.quote(f'abs:"{primary}"'),
                "why": (
                    "NASA ADS is the best index for this subject and needs an API token "
                    "this installation does not hold. This URL is for a person to open. "
                    "The queue records this arm as NOT RUN rather than omitting it."
                ),
                "reason": "no API token for this index on this installation",
                "run": False,
            }
        )
        plan.append(
            {
                "source": "web-manual",
                "query": primary,
                "url": WEB_SEARCH_UI + urllib.parse.quote(f"{primary} orbit satellite"),
                "why": (
                    "arXiv and Crossref between them miss three things that matter here: "
                    "Chinese-language literature, conference proceedings that never got a "
                    "DOI, and operators' own mission pages. Those are exactly where the "
                    "answer lives for several of these candidates, so a general web arm is "
                    "listed for a person to run. It is deliberately NOT automated: a blog "
                    "post is not a publication, and a machine that cannot tell the "
                    "difference would quietly close findings with one."
                ),
                "reason": "deliberately not automated; a person runs this arm",
                "run": False,
            }
        )
    return plan


def _arxiv_url(query: str) -> str:
    return (
        f"{ARXIV_ENDPOINT}?"
        + urllib.parse.urlencode(
            {
                "search_query": f"all:{query}",
                "start": 0,
                "max_results": MAX_RESULTS,
                "sortBy": "relevance",
            }
        )
    )


def _crossref_url(query: str) -> str:
    return (
        f"{CROSSREF_ENDPOINT}?"
        + urllib.parse.urlencode(
            {"query.bibliographic": query, "rows": MAX_RESULTS, "select": "DOI,title,issued,container-title,author"}
        )
    )


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------
_ATOM = "{http://www.w3.org/2005/Atom}"


def parse_arxiv(payload: bytes) -> list[dict[str, Any]]:
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as error:
        raise LiteratureError(f"arXiv returned unparseable XML: {error}") from error
    out: list[dict[str, Any]] = []
    for entry in root.findall(f"{_ATOM}entry"):
        title = (entry.findtext(f"{_ATOM}title") or "").strip()
        link = (entry.findtext(f"{_ATOM}id") or "").strip()
        published = (entry.findtext(f"{_ATOM}published") or "").strip()
        summary = " ".join((entry.findtext(f"{_ATOM}summary") or "").split())
        if not title:
            continue
        out.append(
            {
                "source": "arxiv",
                "title": " ".join(title.split()),
                "url": link,
                "year": published[:4] or None,
                "abstract": summary[:400],
            }
        )
    return out


def parse_crossref(payload: bytes) -> list[dict[str, Any]]:
    try:
        body = json.loads(payload)
    except json.JSONDecodeError as error:
        raise LiteratureError(f"Crossref returned unparseable JSON: {error}") from error
    items = ((body.get("message") or {}).get("items")) or []
    out: list[dict[str, Any]] = []
    for item in items:
        titles = item.get("title") or []
        if not titles:
            continue
        issued = ((item.get("issued") or {}).get("date-parts") or [[None]])[0]
        container = item.get("container-title") or []
        doi = item.get("DOI")
        out.append(
            {
                "source": "crossref",
                "title": " ".join(str(titles[0]).split()),
                "url": f"https://doi.org/{doi}" if doi else None,
                "doi": doi,
                "year": str(issued[0]) if issued and issued[0] else None,
                "venue": container[0] if container else None,
            }
        )
    return out


# ---------------------------------------------------------------------------
# Relevance — deterministic, and deliberately dumb
# ---------------------------------------------------------------------------
def _tokens(text: str) -> set[str]:
    return {token for token in re.split(r"[^a-z0-9]+", text.lower()) if token}


def relevant(result: dict[str, Any], candidate: dict[str, Any]) -> bool:
    """Does this hit plausibly concern *this* object, rather than its programme?

    A token test, not a model. It is crude, and being crude is the point: this
    decides only what a *person* is shown first, never what is true, and a
    deterministic rule a reviewer can predict beats a clever one they cannot.
    Everything a query returns is recorded regardless; this only orders the
    page.

    Two conditions, and the second one exists because of a real miss. The first
    version required only that some word of the name appeared, so every paper
    about *GaoFen-4* was marked relevant to *GAOFEN 13* — the programme token
    matched and the flight number was thrown away for being two characters
    long. The flight number is exactly the part that distinguishes one
    spacecraft from another, so:

    1. every alphabetic token of the name must appear as a whole token in the
       title, abstract or venue; **and**
    2. every numeric token of the name must appear too — all of them, not one
       of them, so ``GAOFEN 13 02`` does not match a paper about ``GaoFen-5 (02)``.

    Both sides are tokenised, so ``GaoFen-4`` splits to ``{gaofen, 4}`` and
    matches ``GAOFEN 4`` while failing ``GAOFEN 13``.

    This is strict, and it will mark a genuinely relevant paper irrelevant when
    the paper spells the designator differently. That is the safer direction:
    an over-strict matcher under-claims prior work, and under-claiming prior
    work sends the finding to a human rather than quietly declaring it novel.
    """
    return match_level(result, candidate) == "object"


def match_level(result: dict[str, Any], candidate: dict[str, Any]) -> str | None:
    """``"object"``, ``"programme"``, or ``None``.

    The distinction exists because of a real gap the strict rule opened. For
    ``GAOFEN 13`` the flight number is the whole point — a paper about
    *GaoFen-4* is not about this spacecraft, and treating it as such was the
    original bug. But for ``KUIPER-00118`` the serial number will **never**
    appear in a paper, because nobody writes up an individual member of a
    mega-constellation. Under the strict rule alone, every constellation member
    is guaranteed a "nothing found" result forever, which is not a measurement,
    it is a rule producing a constant.

    So both are computed and both are recorded, and they are not merged:

    ``object``
        every token of the name, numbers included, appears in the hit.
    ``programme``
        the alphabetic tokens appear but a flight number does not. A paper
        about Project Kuiper's orbit raising is genuinely prior work about a
        Kuiper satellite raising its orbit; it is not evidence about *that*
        spacecraft.

    ``found_prior_work`` counts only ``object`` matches — the conservative
    choice, because it is the one that sends a finding to a human rather than
    closing it. Programme-level hits are shown to the reviewer under their own
    heading, which is what makes them useful without letting them over-claim.
    """
    subject = candidate.get("subject") or {}
    if subject.get("kind") != "object":
        return "object"
    name_tokens = _tokens(str(subject.get("name") or ""))
    words = {token for token in name_tokens if not token.isdigit()}
    numbers = {token for token in name_tokens if token.isdigit()}
    if not words:
        return "object"
    haystack = _tokens(
        " ".join(str(result.get(field) or "") for field in ("title", "abstract", "venue"))
    )
    if not words <= haystack:
        return None
    return "object" if numbers <= haystack else "programme"


# ---------------------------------------------------------------------------
# Running
# ---------------------------------------------------------------------------
@dataclass
class LiteratureCheck:
    candidate_id: str
    searches: list[dict[str, Any]]
    results: list[dict[str, Any]]
    found_prior_work: bool


def run_searches(
    candidate: dict[str, Any],
    *,
    transport: Transport = offline_transport,
    delay_seconds: float = REQUEST_DELAY_SECONDS,
    sleep: Callable[[float], None] = time.sleep,
) -> LiteratureCheck:
    """Run the plan and record what happened to every arm of it.

    A query that errored is recorded as errored, with the message. A query that
    returned nothing is recorded as having returned nothing. Neither is dropped:
    a literature check whose failures are invisible is a check that will read as
    "we looked and found nothing" when it never looked at all.
    """
    plan = search_plan(candidate)
    searches: list[dict[str, Any]] = []
    results: list[dict[str, Any]] = []

    for index, step in enumerate(plan):
        record = {
            "source": step["source"],
            "query": step["query"],
            "url": step["url"],
            "why": step["why"],
        }
        if step.get("run") is False:
            record.update(
                {
                    "status": "not-run",
                    # The reason travels from the plan: "no API token" is true
                    # of the ADS arm and false of the web arm, and a wrong
                    # reason on an unrun search is worse than no reason.
                    "reason": step.get("reason") or step["why"],
                    "hits": None,
                }
            )
            searches.append(record)
            continue
        if index and delay_seconds:
            sleep(delay_seconds)
        try:
            payload = transport(step["url"])
            parsed = parse_arxiv(payload) if step["source"] == "arxiv" else parse_crossref(payload)
        except Exception as error:  # noqa: BLE001 - recorded, not swallowed
            record.update({"status": "error", "reason": f"{type(error).__name__}: {error}", "hits": None})
            searches.append(record)
            continue
        marked = [
            {
                **hit,
                "query": step["query"],
                "matchLevel": match_level(hit, candidate),
                "relevant": match_level(hit, candidate) == "object",
            }
            for hit in parsed
        ]
        record.update({"status": "ok", "hits": len(marked)})
        searches.append(record)
        results.extend(marked)

    # Deduplicate on URL, keeping the first sighting and its query.
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for hit in results:
        key = str(hit.get("url") or hit.get("title"))
        if key in seen:
            continue
        seen.add(key)
        unique.append(hit)
    _ORDER = {"object": 0, "programme": 1, None: 2}
    unique.sort(key=lambda hit: (_ORDER[hit.get("matchLevel")], str(hit.get("year") or "")))

    return LiteratureCheck(
        candidate_id=str(candidate.get("candidateId")),
        searches=searches,
        results=unique,
        # Only object-level matches count as prior work. A programme-level hit
        # is shown to the reviewer but never closes a finding on its own.
        found_prior_work=any(hit["relevant"] for hit in unique),
    )


def check_entry(
    entry: QueueEntry,
    *,
    transport: Transport,
    recorded_by: str,
    literature_path: Path = LITERATURE_PATH,
    sleep: Callable[[float], None] = time.sleep,
) -> LiteratureCheck:
    check = run_searches(entry.candidate, transport=transport, sleep=sleep)
    append_literature(
        check.candidate_id,
        searches=check.searches,
        results=check.results,
        recorded_by=recorded_by,
        found_prior_work=check.found_prior_work,
        path=literature_path,
        tool_version=TOOL_VERSION,
    )
    return check


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", action="store_true", help="print the queries, run nothing")
    parser.add_argument(
        "--run",
        action="store_true",
        help="actually query arXiv and Crossref. Off by default, on purpose.",
    )
    parser.add_argument("--candidate", default=None, help="one candidate id; default is every unsearched one")
    parser.add_argument(
        "--by",
        default=None,
        help="who ran it, as human:<name>. Required with --run: a search nobody owns is not evidence.",
    )
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args(argv)

    entries = load_queue()
    if args.candidate:
        entries = [entry for entry in entries if entry.candidate.get("candidateId") == args.candidate]
    else:
        entries = [entry for entry in entries if not entry.literature]
    entries = entries[: args.limit]

    if args.plan or not args.run:
        print(
            json.dumps(
                [
                    {
                        "candidateId": entry.candidate.get("candidateId"),
                        "headline": entry.candidate.get("headline"),
                        "plan": search_plan(entry.candidate),
                    }
                    for entry in entries
                ],
                indent=2,
            )
        )
        return 0

    if not args.by or not args.by.startswith("human:"):
        raise SystemExit("--by human:<name> is required with --run")

    for entry in entries:
        check = check_entry(entry, transport=urllib_transport, recorded_by=args.by)
        print(
            json.dumps(
                {
                    "candidateId": check.candidate_id,
                    "searches": len(check.searches),
                    "results": len(check.results),
                    "foundPriorWork": check.found_prior_work,
                },
                indent=2,
            )
        )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
