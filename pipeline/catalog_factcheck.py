"""Check what a satellite card claims against the open web, and fill gaps with citations.

WHY THIS EXISTS. The site's owner searched for DSCS -- the Defense Satellite
Communications System, a real and well-known US military SATCOM programme -- and
found nothing on the site. He was right to worry. The objects ARE in the catalog:
space-track files US military spacecraft under **USA designations**, so DSCS III
B-6 is catalogued as ``USA 170``, and a classifier whose only DSCS rule is the
string ``"DSCS"`` matches a name that never appears. Nineteen ``USA nnn`` objects
sat with mission ``other``, sector ``unknown``, basis ``unclassified``.

`satnogs_verify` cannot reach them and never will. SatNOGS is a database of
spacecraft radio amateurs receive from: 930 of this catalog's 8,000 objects
appear in it, and no US military spacecraft ever will. Closing this class of gap
needs the open web, which is what this module adds.

WHAT DECIDES A FACT HERE, AND WHAT DOES NOT
-------------------------------------------

The local model NEVER decides anything. The chain is:

  1. **the deterministic key** -- the NORAD catalog number, second the COSPAR id.
     A retrieved page that does not contain the object's own key as a standalone
     token is discarded before the model is ever called. This is the join, and it
     is the reason a page about a *different* DSCS flight cannot leak in.
  2. **retrieval** -- Exa, one query per object, built from the object's own keys,
     cached permanently (a 2003 launch does not change).
  3. **extraction** -- the local model is asked ONE closed question per page and
     must copy a span out of the text. It proposes; it never concludes.
  4. **validation** -- the quote must be a literal substring of the retrieved
     text, the designation must appear inside the quote, and the quote must
     contain the object's key. Any failure drops the page.
  5. **corroboration** -- a designation is written only when TWO INDEPENDENT
     registrable domains produce the same normalised designation, and only when
     the programme it names is in `PROGRAMME_FACTS`, a hand-written, per-entry
     cited table. Anything else is written as **unknown** and listed in the report
     for a person.

That last rule is the whole design. The owner is about to put this in front of
test users, and a confidently wrong card is the exact failure he is angry about.
A gap this lane declines to fill costs a reader nothing; a wrong fill costs the
site its credibility.

THE FLIGHT-NUMBER TRAP. Several DSCS III spacecraft exist and their flight
designations (B-6, A-3, ...) are the part a reader would most notice being wrong
and the part most likely to be mismatched. Two guards: every accepted quote must
contain the object's OWN catalog number, and `unique_designations` refuses to
write ANY object in a batch when two objects resolve to the same designation.

THE LOCAL MODEL, MEASURED RATHER THAN ASSUMED
---------------------------------------------

Probed on the live endpoint 2026-08-19. The server is llama.cpp holding
``Qwen3.6-35B-A3B-UD-IQ4_XS`` (35.5B params, 4.25 bpw, 131k context), ChatML.

* Reasoning is emitted as ``<think> ... </think>``. The server parses a CLOSED
  block out into ``message.reasoning_content`` and leaves ``message.content``
  clean -- which is why a naive caller sees no tags and wrongly concludes there
  are none.
* Thinking is OFF in this server's current default (58 completion tokens for the
  probe question). With ``chat_template_kwargs={"enable_thinking": true}`` the
  same question spent **1,295** tokens. A default is not a guarantee, so this
  module SENDS ``enable_thinking: false`` explicitly AND strips the tags anyway.
* **The failure that reads like an answer**: thinking on and the budget short
  gives ``finish_reason: "length"``, ``reasoning_content`` full of scratch work
  and ``content`` EXACTLY ``""``. An empty answer is indistinguishable from "the
  model declined" unless you look at the finish reason. So `ask_model` treats any
  non-``stop`` finish as a hard failure and never as a verdict.
* Asked the OPEN question "explain what USA 170 is", the model answered:
  *"There is no officially designated USA-170 satellite ... you are likely
  referring to USA-193"*. Confidently, fluently wrong about the exact object this
  lane exists to fix. Asked the CLOSED question against retrieved text it was
  right, and correctly answered "no" when the text did not support the claim.
  That contrast is the argument for this module's shape, and it is measured.

WHAT THIS MODULE WRITES. ``data/catalog_factcheck.json`` -- a table keyed on
catalog number, applied by `build_release` ONLY where the card currently says
nothing at all, and overridden by the curated table like every other automated
source. Plus ``state/factcheck-report.md``, which is written for a person.
"""

from __future__ import annotations

import argparse
import collections
import datetime as dt
import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Iterable

from pipeline import gpu_usage_ledger

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "pipeline" / ".cache" / "factcheck"
STATE = ROOT / "state"
FINDINGS = ROOT / "data" / "catalog_factcheck.json"

EXA_ENDPOINT = "https://api.exa.ai/search"

#: Named so a webmaster reading their logs can tell who this is and complain to a
#: person rather than to a firewall. This project was banned by CelesTrak once.
USER_AGENT = (
    "SpaceEnvironmentExplorer/0.1 (educational catalog fact-check; "
    "contact=sean.theinformed.org)"
)

#: Exa publishes a rate limit far above anything here; the budget is this
#: project's own courtesy floor, and it is the same one the SatNOGS lane uses.
MIN_REQUEST_INTERVAL_S = 1.2

#: A search result about a 2003 launch does not go stale. Re-running the lane
#: must cost nothing, or it will not be re-run.
_LAST_REQUEST_AT = 0.0


class FactcheckUnavailable(RuntimeError):
    """The web side could not run. Never a silent partial answer.

    Raised for a missing key, a non-200, or a malformed body. The lane stops and
    says so rather than reporting a smaller, quieter set of findings that reads
    like "there was less to find".
    """


# ---------------------------------------------------------------------------
# The key, read at runtime and never kept
# ---------------------------------------------------------------------------

DEFAULT_KEY_FILE = Path.home() / ".config" / "space-teaching-aid" / "exa.env"


def exa_key() -> str | None:
    """The Exa API key: environment first, then the untracked env file.

    Same shape as `satnogs_verify.api_token`, deliberately. Read at CALL TIME and
    never cached in a module global, because the owner intends to rotate it: a
    process that read it once at import would keep using a revoked key until
    something restarted it.

    It is never logged, never written to a report, and never embedded as a
    fallback. `EXA_KEY_FILE` moves the file for a test.
    """
    from_env = os.environ.get("EXA_API_KEY")
    if from_env and from_env.strip():
        return from_env.strip()
    path = Path(os.environ.get("EXA_KEY_FILE") or DEFAULT_KEY_FILE)
    if not path.is_file():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name, _, value = line.partition("=")
        if name.strip() == "EXA_API_KEY":
            return value.strip().strip("'\"") or None
    return None


MISSING_KEY_MESSAGE = (
    "No Exa API key. Put EXA_API_KEY in the environment, or one line "
    "'EXA_API_KEY=...' in ~/.config/space-teaching-aid/exa.env (mode 600, outside "
    "every git repository), or point EXA_KEY_FILE at another file. This lane will "
    "not run without one and has no fallback by design."
)


def require_key() -> str:
    key = exa_key()
    if not key:
        raise FactcheckUnavailable(MISSING_KEY_MESSAGE)
    return key


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------


def _throttle() -> None:
    global _LAST_REQUEST_AT
    wait = MIN_REQUEST_INTERVAL_S - (time.monotonic() - _LAST_REQUEST_AT)
    if wait > 0:
        time.sleep(wait)
    _LAST_REQUEST_AT = time.monotonic()


def _cache_path(query: str, directory: Path | None = None) -> Path:
    digest = hashlib.sha256(query.encode("utf-8")).hexdigest()[:20]
    return Path(directory or CACHE) / f"search-{digest}.json"


def search(
    query: str,
    *,
    key: str,
    num_results: int = 6,
    max_characters: int = 1200,
    include_domains: Iterable[str] | None = None,
    directory: Path | None = None,
    refresh: bool = False,
    timeout: int = 60,
) -> dict[str, Any]:
    """One Exa search, cached on disk forever.

    Stops on any non-200 rather than retrying. A search API that starts refusing
    is telling you something, and the honest response is to stop and report --
    the same rule the SatNOGS lane follows and for the same reason.
    """
    domains = tuple(include_domains or ())
    # The cache key covers the domain restriction and the text budget, so the
    # two passes over one object cannot collide on disk and a widened window
    # cannot be served a narrower cached answer.
    cache_key = f"{query}|{num_results}|{max_characters}|{','.join(domains)}"
    path = _cache_path(cache_key, directory)
    if path.is_file() and not refresh:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
    payload = {
        "query": query,
        "numResults": num_results,
        "contents": {"text": {"maxCharacters": max_characters}},
    }
    if domains:
        payload["includeDomains"] = list(domains)
    request = urllib.request.Request(
        EXA_ENDPOINT,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "x-api-key": key,
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
        },
        method="POST",
    )
    _throttle()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
    except urllib.error.HTTPError as error:
        # The body may carry a useful message; the key is never in it, and the
        # request headers (which do carry it) are deliberately not reported.
        detail = ""
        try:
            detail = error.read().decode("utf-8", "replace")[:300]
        except Exception:  # pragma: no cover - best effort only
            pass
        raise FactcheckUnavailable(f"Exa returned HTTP {error.code}. {detail}") from error
    except Exception as error:
        raise FactcheckUnavailable(f"Exa request failed: {type(error).__name__}") from error
    try:
        body = json.loads(raw.decode("utf-8", "replace"))
    except json.JSONDecodeError as error:
        raise FactcheckUnavailable("Exa returned a body that is not JSON") from error
    if not isinstance(body, dict) or "results" not in body:
        raise FactcheckUnavailable("Exa returned a body with no 'results'")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(body, indent=1, sort_keys=True), encoding="utf-8")
    return body


def reference_query_for(satellite: dict[str, Any]) -> str:
    """The second query: the same keys, aimed at the reference works.

    Deliberately a SEPARATE request rather than a bigger first one. A general
    search ranks trackers first because trackers are what a catalogue-number
    query looks like; restricting the domains is the only way to make the pages
    that index by programme name compete at all.
    """
    parts = [str(satellite.get("name") or "").strip()]
    cospar = str(satellite.get("cosparId") or "").strip()
    if cospar:
        parts.append(cospar)
    parts.append(f"NORAD {satellite['id']}")
    parts.append("spacecraft programme")
    return " ".join(part for part in parts if part)


def query_for(satellite: dict[str, Any]) -> str:
    """The search string, built ONLY from keys the catalog is certain about.

    Name, catalog number and COSPAR id -- no guess about what the object might
    be. Putting a hypothesis in the query is how a search engine is talked into
    confirming it.
    """
    parts = [str(satellite.get("name") or "").strip(), f"NORAD {satellite['id']}"]
    cospar = str(satellite.get("cosparId") or "").strip()
    if cospar:
        parts.append(f"COSPAR {cospar}")
    parts.append("satellite programme designation")
    return " ".join(part for part in parts if part)


# ---------------------------------------------------------------------------
# The deterministic key: does this page even mention our object?
# ---------------------------------------------------------------------------


def _collapse(text: str) -> str:
    return " ".join((text or "").split())


def mentions_key(text: str, catalog_id: int, cospar_id: str | None) -> list[str]:
    """Which of the object's keys the retrieved text actually contains.

    The catalog number is matched on a DIGIT boundary, not a word boundary:
    ``\\b27875\\b`` happily matches inside ``127875``, and a catalog of 8,000
    five-digit numbers gives that plenty of chances. COSPAR ids are matched
    case-insensitively and tolerate the hyphen being absent.
    """
    body = _collapse(text)
    found: list[str] = []
    if re.search(rf"(?<!\d){catalog_id}(?!\d)", body):
        found.append(f"NORAD {catalog_id}")
    cospar = (cospar_id or "").strip().upper()
    if cospar:
        loose = re.escape(cospar).replace(r"\-", r"[-\s]?")
        if re.search(loose, body.upper()):
            found.append(f"COSPAR {cospar}")
    return found


KEY_WINDOW_CHARS = 1400


def key_window(text: str, catalog_id: int, cospar_id: str | None) -> str:
    """The part of a retrieved page that is actually about this object.

    A reference page can be nine thousand characters of launch tables, and the
    one line naming this spacecraft can be anywhere in it. Truncating from the
    front throws that line away as often as not -- which is how the DSCS case
    failed on the first run.

    Windowing on the KEY rather than truncating does two jobs at once: it keeps
    the evidence, and it hands a modest model a short passage with one relevant
    line in it instead of a wall of unrelated launches to be confused by.
    """
    body = _collapse(text)
    positions: list[int] = []
    match = re.search(rf"(?<!\d){catalog_id}(?!\d)", body)
    if match:
        positions.append(match.start())
    cospar = (cospar_id or "").strip().upper()
    if cospar:
        loose = re.escape(cospar).replace(r"\-", r"[-\s]?")
        found = re.search(loose, body.upper())
        if found:
            positions.append(found.start())
    if not positions:
        return body[:KEY_WINDOW_CHARS]
    start = max(0, min(positions) - KEY_WINDOW_CHARS // 2)
    end = max(positions) + KEY_WINDOW_CHARS
    return body[start:end]


def registrable_domain(url: str) -> str:
    """Enough of the host to tell two sources apart.

    Deliberately crude -- the last two labels, with a short public-suffix list
    for the two-part TLDs that actually appear in this project's sources. It only
    ever has to answer "are these the same site?", and being crude in the
    direction of MERGING two hosts is the safe error: it makes corroboration
    harder to satisfy, never easier.
    """
    host = (urllib.parse.urlparse(url).hostname or "").lower().strip(".")
    if not host:
        return ""
    labels = host.split(".")
    two_part = {"co.uk", "org.uk", "ac.uk", "com.au", "co.jp", "gov.uk", "com.br"}
    if len(labels) >= 3 and ".".join(labels[-2:]) in two_part:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:]) if len(labels) >= 2 else host


#: How much weight a reader should give a citation. Recorded on every finding so
#: a person can weigh it, and used by `corroborate` to refuse a claim resting on
#: nothing but automated republishers of the very catalog we are checking.
#:
#: `tracker` is the important tier. keeptrack.space, n2yo, satellitemap and
#: friends REPUBLISH space-track data; two of them agreeing is one source
#: agreeing with itself, which is why the corroboration rule below requires more
#: than trackers alone for a claim to ship.
SOURCE_TIERS: dict[str, str] = {
    # Trackers. They republish space-track/CelesTrak -- the very catalogue this
    # lane is checking -- so two of them agreeing is one source agreeing with
    # itself. Every one below was seen in a real result during the USA-family run.
    "keeptrack.space": "tracker",
    "n2yo.com": "tracker",
    "satellitemap.space": "tracker",
    "orbitalradar.com": "tracker",
    "in-the-sky.org": "tracker",
    "heavens-above.com": "tracker",
    "satflare.com": "tracker",
    "satcat.com": "tracker",
    "isstracker.pl": "tracker",
    "celestrak.org": "tracker",
    "space-track.org": "tracker",
    # References. Compiled and edited by a named person or institution, indexing
    # spacecraft by PROGRAMME rather than by catalogue number, which is exactly
    # the direction of lookup a tracker cannot do.
    "wikipedia.org": "reference",
    "skyrocket.de": "reference",        # Gunter's Space Page
    "astronautix.com": "reference",     # Encyclopedia Astronautica
    "planet4589.org": "reference",      # Jonathan McDowell's space report
    "tbs-satellite.com": "reference",   # TSE / Encyclopedia of spacecraft
    "designation-systems.info": "reference",  # Andreas Parsch, US military designations
    "designation-systems.net": "reference",
    "cas.cz": "reference",              # Czech Academy of Sciences "Space 40" catalogue
    # Enthusiast compilations and independent OBSERVERS. Weaker than a reference
    # work, stronger than a republisher: satobs.org identifies classified objects
    # from optical observation, which owes nothing to the catalogue.
    "weebau.com": "enthusiast",
    "satobs.org": "enthusiast",
    "satbeams.com": "enthusiast",
}

#: Where to look when the general search returns nothing but trackers. Restricting
#: a second query to these is the "prefer an authoritative page where one exists"
#: rule, made mechanical. It matters more than it sounds: reference works index by
#: programme name, so the pages that can actually SETTLE a USA designation are the
#: ones a name-shaped query is least likely to surface on its own.
REFERENCE_DOMAINS: tuple[str, ...] = (
    "space.skyrocket.de",
    "en.wikipedia.org",
    "planet4589.org",
    "astronautix.com",
    "www.astronautix.com",
    "tbs-satellite.com",
    "www.tbs-satellite.com",
    "designation-systems.info",
    "www.designation-systems.info",
    "www.lib.cas.cz",
    "weebau.com",
)

#: Anything under these suffixes is a primary source: the operator, the agency or
#: the government that flies the spacecraft, publishing about its own programme.
PRIMARY_SUFFIXES = (".mil", ".gov", "esa.int", "eumetsat.int", "jaxa.jp", "spaceforce.mil")


def source_tier(url: str) -> str:
    host = (urllib.parse.urlparse(url).hostname or "").lower()
    if any(host.endswith(suffix) for suffix in PRIMARY_SUFFIXES):
        return "primary"
    return SOURCE_TIERS.get(registrable_domain(url), "unrated")


# ---------------------------------------------------------------------------
# The local model: it copies spans, it does not conclude
# ---------------------------------------------------------------------------

MODEL_URL = os.environ.get("SPACE_MODEL_URL", "http://model-host.example.invalid:18080/v1/chat/completions")
MODEL_NAME = os.environ.get("SPACE_MODEL_NAME", "bigmem-chat")
MODEL_LANE = "space-catalog-factcheck"

#: Measured, not guessed, and RAISED after a real run. The first budget was 400,
#: on the strength of a 58-token probe answer -- and the very first keeptrack page
#: for USA 170 blew through it, because the model copies the whole span it was
#: asked for and a tracker page's identity line is long. That failure arrived as
#: `finish_reason: length`, which `ask_model` correctly refuses to treat as a
#: verdict, so the page was dropped rather than mis-read; but it dropped the best
#: evidence on the object this lane was built for. 900 is comfortably above every
#: answer observed since, and still an order of magnitude below the 8,192 a
#: thinking call would need. Thinking is explicitly OFF, which is what makes a
#: budget this small safe at all.
MODEL_MAX_TOKENS = 900
MODEL_TIMEOUT_S = 120

#: Qwen3.6 emits `<think>...</think>`. The server hoists a CLOSED block into
#: `reasoning_content` and hands back clean `content`; an UNCLOSED one (budget
#: exhausted mid-thought) can arrive inline. Both are stripped here rather than
#: trusted to a server setting that some other lane may change.
THINK_BLOCK = re.compile(r"<think>.*?</think>", re.S | re.I)
OPEN_THINK = re.compile(r"<think>.*", re.S | re.I)
CODE_FENCE = re.compile(r"```[a-zA-Z0-9_-]*\n?|```", re.S)


def strip_reasoning(raw: str) -> str:
    """Remove the reasoning block and any code fence from a model answer.

    An unterminated ``<think>`` drops everything after it, which is correct:
    there is no answer behind it, only scratch work that was cut off.
    """
    body = THINK_BLOCK.sub(" ", raw or "")
    body = OPEN_THINK.sub(" ", body)
    return CODE_FENCE.sub(" ", body).strip()


def first_json_object(text: str) -> dict[str, Any] | None:
    """The first balanced ``{...}``, honouring strings and escapes.

    Brace-counting rather than a greedy span, because a quote copied out of a
    page can contain a brace and a greedy first-to-last span then swallows the
    rest of the answer.
    """
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                try:
                    parsed = json.loads(text[start : index + 1])
                except json.JSONDecodeError:
                    return None
                return parsed if isinstance(parsed, dict) else None
    return None


def ask_model(
    system: str,
    user: str,
    *,
    url: str | None = None,
    model: str | None = None,
    max_tokens: int = MODEL_MAX_TOKENS,
    timeout: float = MODEL_TIMEOUT_S,
) -> tuple[dict[str, Any] | None, str, object]:
    """One closed question. → (parsed answer, error, usage block or None).

    The third element is the server's OWN token counts, straight off the response
    body. It used to be parsed and dropped, so this lane's receipts said how long
    the GPU was held and never how much was asked of it — /system/models drew it as
    unmeasured. A fault with no body (network, HTTP error) yields None and the
    caller writes no token fields at all: never a zero, never an estimate.

    THREE THINGS THIS DOES THAT A NAIVE CALLER DOES NOT, each of them measured on
    the live endpoint rather than assumed:

    * sends ``chat_template_kwargs={"enable_thinking": false}`` EXPLICITLY. The
      server's current default is already off, but a default is not a contract
      and another lane could change it. With thinking on, this call's 400-token
      budget would be exhausted mid-thought every time.
    * treats ``finish_reason != "stop"`` as a hard failure. A truncated thinking
      call returns ``content == ""`` with the scratch work in
      ``reasoning_content``: an EMPTY STRING that parses as "no answer" and reads
      exactly like a model that declined to answer. It is a budget bug and must
      never be recorded as a verdict.
    * strips ``<think>`` blocks from ``content`` anyway.

    Never raises for a network fault. A dead GPU is a normal outcome for a lane
    that runs unattended, and the caller records it and moves on.
    """
    payload = {
        "model": model or MODEL_NAME,
        "temperature": 0,
        "max_tokens": max_tokens,
        "chat_template_kwargs": {"enable_thinking": False},
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    request = urllib.request.Request(
        url or MODEL_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as error:
        return None, f"http_{error.code}", None
    except Exception as error:
        return None, type(error).__name__, None
    choice = (body.get("choices") or [{}])[0]
    usage = body.get("usage")
    finish = choice.get("finish_reason")
    # A truncated or unparseable answer still SPENT the tokens it spent. Those
    # receipts carry the counts too, or the page would under-report the lane by
    # exactly the calls that went wrong.
    if finish != "stop":
        return None, f"finish_{finish}", usage
    content = (choice.get("message") or {}).get("content") or ""
    parsed = first_json_object(strip_reasoning(content))
    if parsed is None:
        return None, "unparseable", usage
    return parsed, "", usage


EXTRACT_SYSTEM = (
    "You copy text. You never add facts and you never use knowledge of your own. "
    "You answer with one JSON object and nothing else."
)

#: Small, closed, and answerable. It names the object by its catalog NUMBER --
#: the thing both sides can be checked against -- and asks for a span, not a
#: judgement. "What is USA 167?" is the question that produced a fluent
#: paragraph about a different spacecraft; this is the question that did not.
EXTRACT_PROMPT = """Below is text copied from one web page.

--- PAGE TEXT ---
{text}
--- END PAGE TEXT ---

The satellite catalogue number {catalog_id} identifies one spacecraft. This site
records that spacecraft under the name "{name}".

QUESTION: does this page text give another name for catalogue number {catalog_id} --
a programme or mission name, such as a series name with a flight number?

Answer with this JSON object and nothing else:

{{"designation": "<the other name, copied exactly from the page text; empty string if the page does not give one>",
  "quote": "<one span copied EXACTLY and WORD FOR WORD from the page text above, containing both the number {catalog_id} and that other name; empty string if there is none>"}}

Rules you must follow:
- Copy. Do not correct spelling, do not expand abbreviations, do not reformat.
- If the page text does not contain the number {catalog_id}, both fields are empty.
- If the page is about a different spacecraft, both fields are empty.
- An empty answer is a correct and useful answer. Do not guess."""


#: How close the designation and the object's catalogue key must be, in
#: characters of collapsed page text.
#:
#: THIS REPLACED "the quote must contain the catalogue number", which was too
#: strict in a way that cost real evidence: a reference page states the identity
#: in prose ("Orig PL Name: DSCS III B-6") and the catalogue number in a table
#: cell eighty characters away, so weebau's entirely correct answer about USA 170
#: was thrown out. Proximity does the same job better, because it is measured
#: DETERMINISTICALLY over the page rather than depending on how wide a span the
#: model chose to copy.
#:
#: It is still a real guard, and the case that proves it is
#: `astronautix.com/d/delta4m.html`: one page listing dozens of Delta IV launches,
#: each with its own designation beside its own catalogue number. 300 characters
#: keeps "USA 167 ... DSCS III A-3 ... USAF Sat Cat: 27691" together and keeps
#: every other launch on that page out.
KEY_PROXIMITY_CHARS = 300


def key_proximity(
    text: str, designation: str, catalog_id: int, cospar_id: str | None
) -> int | None:
    """Smallest gap between this designation and one of the object's keys. None if too far."""
    body = _collapse(text)
    key_spans: list[tuple[int, int]] = []
    for match in re.finditer(rf"(?<!\d){catalog_id}(?!\d)", body):
        key_spans.append(match.span())
    cospar = (cospar_id or "").strip().upper()
    if cospar:
        loose = re.escape(cospar).replace(r"\-", r"[-\s]?")
        for match in re.finditer(loose, body, re.I):
            key_spans.append(match.span())
    if not key_spans:
        return None
    best: int | None = None
    for match in re.finditer(re.escape(designation), body):
        start, end = match.span()
        for key_start, key_end in key_spans:
            gap = key_start - end if key_start >= end else start - key_end
            gap = max(0, gap)
            if best is None or gap < best:
                best = gap
    if best is None or best > KEY_PROXIMITY_CHARS:
        return None
    return best


#: A designation must look like a programme name: at least one capitalised or
#: numeric token, no sentence punctuation, and short. This is what stops the
#: model handing back a clause ("the satellite formerly known as") and it being
#: written to a card as if it were a name.
DESIGNATION_SHAPE = re.compile(r"^[A-Z0-9][A-Za-z0-9 ()/.‐-―-]{1,44}$")

#: A page often glosses the name -- "DSCS III B-6 (Defense Satellite Communications
#: System)". The gloss is not part of the name, and leaving it on would make the
#: same claim fail to corroborate the same claim written without it. Trimmed
#: deterministically here rather than asked of the model, because a rule that runs
#: every time beats an instruction a small model follows most of the time.
TRAILING_GLOSS = re.compile(r"\s*\([^)]*\)\s*$")

#: Things a page says that are not another name for the spacecraft. Checked
#: against the NORMALISED designation.
DESIGNATION_STOPWORDS = frozenset({
    "PAYLOAD", "SATELLITE", "SPACECRAFT", "OPERATIONAL", "ACTIVE", "UNKNOWN",
    "GEO", "LEO", "MEO", "HEO", "IGSO", "GEOSYNCHRONOUS", "GEOSTATIONARY",
    "COSPAR", "NORAD", "TLE", "ROCKET BODY", "DEBRIS", "N/A", "NONE",
})


def normalized_designation(value: str) -> str:
    """A designation reduced to what two sources have to agree on.

    Case, punctuation and internal spacing are noise -- "DSCS III B-6",
    "DSCS-3 B-6" and "DSCS III B6" are one claim written three ways. Roman
    numerals are folded to digits so a tracker's "DSCS 3" and a reference work's
    "DSCS III" corroborate each other instead of silently failing to.
    """
    text = _collapse(value).upper()
    text = re.sub(r"[‐-―]", "-", text)
    for numeral, digit in (("VIII", "8"), ("VII", "7"), ("VI", "6"), ("IV", "4"),
                           ("III", "3"), ("II", "2"), ("IX", "9"), ("X", "10"),
                           ("V", "5"), ("I", "1")):
        text = re.sub(rf"(?<![A-Z0-9]){numeral}(?![A-Z0-9])", digit, text)
    text = re.sub(r"[^A-Z0-9]+", " ", text)
    # Split letter-digit runs, so a flight designation written "A-3" and one
    # written "A3" are one claim. Found by a live run: USA 167 came back as
    # "DSCS III A-3" from two sources and "DSCS-3 A3" from two others, and this
    # function called them different designations -- so four agreeing sources
    # were reported as an even split and NOTHING was written. A normaliser that
    # under-merges does not fail loudly; it fails as a shortage of evidence,
    # which is the hardest kind of bug to see in a report.
    text = re.sub(r"(?<=[A-Z])(?=[0-9])", " ", text)
    text = re.sub(r"(?<=[0-9])(?=[A-Z])", " ", text)
    return " ".join(text.split())


def plausible_designation(value: str, satellite_name: str) -> bool:
    """Is this string shaped like another name for a spacecraft?

    Rejects the object's OWN name, which pages repeat constantly and a model will
    dutifully hand back as "the other name" -- an answer that is true, useless,
    and would corroborate itself across every source.
    """
    text = _collapse(value)
    if not text or not DESIGNATION_SHAPE.match(text):
        return False
    normalised = normalized_designation(text)
    if not normalised or normalised in DESIGNATION_STOPWORDS:
        return False
    if normalised == normalized_designation(satellite_name):
        return False
    # A designation with no letters at all is a number the page happened to
    # print, not a programme name.
    return bool(re.search(r"[A-Z]", normalised))


def validated_extraction(
    answer: dict[str, Any],
    *,
    text: str,
    satellite: dict[str, Any],
) -> tuple[dict[str, str] | None, str]:
    """→ (accepted extraction, reason it was rejected).

    Every one of these checks exists because the alternative is trusting a 35B
    model's assertion about a military spacecraft, which the probe showed is
    worth nothing. The quote must be REAL (a literal substring of what was
    retrieved), it must be ABOUT THIS OBJECT (it contains the catalog number),
    and the designation must be IN it.
    """
    designation = TRAILING_GLOSS.sub("", _collapse(str(answer.get("designation") or "")))
    quote = _collapse(str(answer.get("quote") or ""))
    if not designation or not quote:
        return None, "empty"
    haystack = _collapse(text)
    if quote not in haystack:
        return None, "quote-not-in-source"
    if designation not in quote:
        return None, "designation-not-in-quote"
    distance = key_proximity(haystack, designation, satellite["id"], satellite.get("cosparId"))
    if distance is None:
        return None, "designation-far-from-catalog-number"
    if not plausible_designation(designation, str(satellite.get("name") or "")):
        return None, "designation-implausible"
    return {"designation": designation, "quote": quote, "keyDistance": distance}, ""


# ---------------------------------------------------------------------------
# What a programme name is allowed to mean
# ---------------------------------------------------------------------------

#: Programme -> what the site may say about it, and where a reader can check it.
#:
#: HAND-WRITTEN AND CITED, exactly like `OPERATOR_SECTORS`. This is the one place
#: in this module that ADDS a claim rather than corroborating an identity, so it
#: is the one place a person had to read a source. The lane's automated half
#: decides only WHICH programme an object belongs to; what that programme IS
#: comes from here, and an object whose designation is not in this table is
#: reported as unknown rather than described from the model's own knowledge.
#:
#: EVERY URL HERE WAS FETCHED AND READ, not recalled. The first draft of this
#: table was written from memory and three of its five links were wrong --
#: AEHF and WGS were given the SAME spaceforce.mil article id, and the DSCS
#: fact sheet it cited does not exist. `sourceTier` records whether a reader
#: is getting the operator or a reference work.
#:
#: Keys are `normalized_designation` PREFIXES: "DSCS 3 B 6" matches "DSCS 3",
#: which matches "DSCS". Longest prefix wins, so a series-specific entry can be
#: added later without disturbing the family entry.
PROGRAMME_FACTS: dict[str, dict[str, str]] = {
    "DSCS": {
        "programme": "Defense Satellite Communications System",
        "mission": "communications",
        "sector": "military",
        "organization": "U.S. Space Force (formerly U.S. Air Force)",
        "purpose": (
            "A Defense Satellite Communications System spacecraft: a geostationary "
            "super-high-frequency relay carrying long-haul communications for United "
            "States forces and allied government users. The public catalogue lists it "
            "only by its USA designation, which is how US military spacecraft are "
            "registered; the programme name comes from the sources cited beside this "
            "card."
        ),
        # DSCS is retired and has no live fact sheet on spaceforce.mil -- the
        # obvious URL for one does not exist, and an invented one would be the
        # exact failure this module was built to prevent. This is Air & Space
        # Forces Magazine's weapons reference, which is edited and attributable
        # but is NOT the operator speaking, and `sourceTier` says so.
        "source": "https://www.airandspaceforces.com/weapons/dscs/",
        "sourceTier": "reference",
    },
    "MILSTAR": {
        "programme": "Milstar",
        "mission": "communications",
        "sector": "military",
        "organization": "U.S. Space Force (formerly U.S. Air Force)",
        "purpose": (
            "A Milstar spacecraft: a hardened, jam-resistant military communications "
            "satellite carrying extremely-high-frequency and ultra-high-frequency links "
            "for United States strategic and tactical forces."
        ),
        "source": "https://www.spaceforce.mil/About-Us/Fact-Sheets/Fact-Sheet-Display/Article/2197755/milstar-satellite-communications-system/",
        "sourceTier": "primary",
    },
    "WGS": {
        "programme": "Wideband Global SATCOM",
        "mission": "communications",
        "sector": "military",
        "organization": "U.S. Space Force",
        "purpose": (
            "A Wideband Global SATCOM spacecraft: the high-capacity X- and Ka-band "
            "backbone of United States military satellite communications, and the "
            "system that replaced DSCS."
        ),
        "source": "https://www.spaceforce.mil/About-Us/Fact-Sheets/Fact-Sheet-Display/Article/2197740/wideband-global-satcom-satellite/",
        "sourceTier": "primary",
    },
    "AEHF": {
        "programme": "Advanced Extremely High Frequency",
        "mission": "communications",
        "sector": "military",
        "organization": "U.S. Space Force",
        "purpose": (
            "An Advanced Extremely High Frequency spacecraft: protected, survivable "
            "communications for United States and allied strategic and tactical forces, "
            "and the successor to Milstar."
        ),
        "source": "https://www.spaceforce.mil/About-Us/Fact-Sheets/Fact-Sheet-Display/Article/2197713/advanced-extremely-high-frequency-system/",
        "sourceTier": "primary",
    },
    # The retrieval
    # half of this lane had already corroborated `DSP 22`, `GSSAP 3`, `GSSAP 4`
    # and `CBAS 2` across independent domains and then refused to write them,
    # for the one reason the design intends: what a programme IS comes from a
    # person reading a source, and these three programmes were not yet in this
    # table. They are now, each with a live citation, and the objects resolve on
    # the lane's own evidence rather than on an assertion.
    "DSP": {
        "programme": "Defense Support Program",
        "mission": "missile-warning",
        "sector": "military",
        "organization": "U.S. Space Force (formerly U.S. Air Force)",
        "purpose": (
            "A Defense Support Program spacecraft: the geostationary infrared early-warning "
            "constellation that has watched for ballistic-missile launches since 1970, and "
            "which also carries the optical, X-ray and radiation sensors of the US Nuclear "
            "Detonation Detection System. SBIRS augments and is replacing it. The public "
            "catalogue lists this object only by its USA designation, which is how US "
            "military spacecraft are registered."
        ),
        # No live spaceforce.mil fact sheet for a programme this old; the base
        # override table's DSP link points at the GPS article's ID and serves the
        # GPS fact sheet instead. Air & Space Forces Magazine's weapons reference
        # is edited and attributable but is NOT the operator speaking, and
        # `sourceTier` says so.
        "source": "https://www.airandspaceforces.com/weapons/defense-support-program/",
        "sourceTier": "reference",
    },
    "GSSAP": {
        "programme": "Geosynchronous Space Situational Awareness Program",
        "mission": "other",
        "sector": "military",
        "organization": "U.S. Space Force",
        "purpose": (
            "A Geosynchronous Space Situational Awareness Program spacecraft: a manoeuvrable "
            "US Space Force inspector carrying electro-optical sensors, flown in a near-"
            "geosynchronous drift orbit so that it can close on and characterise other objects "
            "in the belt from short range. It is one of the few US space-surveillance systems "
            "the Space Force discusses openly, and the catalogue still lists it only by its "
            "USA designation."
        ),
        "source": "https://www.airandspaceforces.com/weapons/gssap/",
        "sourceTier": "reference",
    },
    "CBAS": {
        "programme": "Continuous Broadcast Augmenting SATCOM",
        "mission": "communications",
        "sector": "military",
        "organization": "U.S. Space Force",
        "purpose": (
            "A Continuous Broadcast Augmenting SATCOM spacecraft: a geostationary relay that "
            "adds broadcast capacity for senior leaders and combatant commanders on top of the "
            "existing military SATCOM constellations rather than replacing any of them. The "
            "public catalogue lists it only by its USA designation."
        ),
        "source": "https://www.airandspaceforces.com/weapons/continuous-broadcast-augmenting-satcom/",
        "sourceTier": "reference",
    },
    "SDS": {
        "programme": "Satellite Data System",
        "mission": "communications",
        "sector": "military",
        "organization": "U.S. National Reconnaissance Office",
        "purpose": (
            "A Satellite Data System spacecraft: a United States military relay used to "
            "carry data from other spacecraft and from polar regions that a "
            "geostationary satellite cannot see."
        ),
        # No operator page exists for a programme the NRO barely acknowledges.
        # Andreas Parsch's designation reference is the citable one.
        "source": "https://www.designation-systems.net/dusrm/app3/sds.html",
        "sourceTier": "reference",
    },
}


def programme_for(designation: str) -> tuple[str, dict[str, str]] | None:
    """The longest `PROGRAMME_FACTS` prefix this designation starts with."""
    normalised = normalized_designation(designation)
    best: tuple[str, dict[str, str]] | None = None
    for key, facts in PROGRAMME_FACTS.items():
        normalised_key = normalized_designation(key)
        if normalised == normalised_key or normalised.startswith(normalised_key + " "):
            if best is None or len(normalised_key) > len(normalized_designation(best[0])):
                best = (key, facts)
    return best


# ---------------------------------------------------------------------------
# Corroboration: two independent sites, or nothing
# ---------------------------------------------------------------------------

#: How many DIFFERENT registrable domains must give the same designation.
MIN_INDEPENDENT_DOMAINS = 2

#: Tiers that can carry a claim. At least one supporting source must be one of
#: these or nothing is written.
#:
#: `tracker` is excluded because trackers republish the very catalogue this lane
#: is checking: three of them agreeing is one source agreeing with itself.
#: `unrated` is excluded for a different and equally firm reason -- nobody has
#: assessed the site, so counting it as corroboration would mean the bar quietly
#: drops every time the search surfaces a domain the tier table has not seen.
#: Both still count towards DOMAIN INDEPENDENCE; they just cannot be the whole
#: case. Rating a new domain is a deliberate edit to `SOURCE_TIERS`, by a person.
WEIGHT_BEARING_TIERS = frozenset({"primary", "reference", "enthusiast"})


def corroborate(evidence: list[dict[str, Any]]) -> tuple[str | None, str, list[dict[str, Any]]]:
    """→ (designation, why, the citations supporting it).

    Groups extractions by normalised designation and takes the one with the most
    INDEPENDENT DOMAINS behind it -- not the most rows, because one site can put
    the same string on five pages.
    """
    by_designation: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for item in evidence:
        by_designation[normalized_designation(item["designation"])].append(item)
    if not by_designation:
        return None, "no page gave another name for this object", []

    def domains(rows: list[dict[str, Any]]) -> set[str]:
        return {row["domain"] for row in rows if row["domain"]}

    ranked = sorted(by_designation.items(), key=lambda kv: (-len(domains(kv[1])), kv[0]))
    normalised, rows = ranked[0]
    unique = domains(rows)
    if len(unique) < MIN_INDEPENDENT_DOMAINS:
        return None, (
            f"only {len(unique)} independent source gave '{rows[0]['designation']}'; "
            f"{MIN_INDEPENDENT_DOMAINS} are required"
        ), rows
    if not any(row["tier"] in WEIGHT_BEARING_TIERS for row in rows):
        tiers = ", ".join(sorted({row["tier"] for row in rows}))
        return None, (
            f"'{rows[0]['designation']}' rests only on {tiers} sources; a primary, "
            "reference or observer source is required, because trackers republish the "
            "same catalogue this lane is checking and an unrated site has not been "
            "assessed at all"
        ), rows
    if len(ranked) > 1 and len(domains(ranked[1][1])) == len(unique):
        return None, (
            f"sources are split between '{rows[0]['designation']}' and "
            f"'{ranked[1][1][0]['designation']}' with equal support"
        ), rows
    # Which SPELLING to show. The normalised form is for comparing; a card should
    # show what a source actually wrote. Preference order is deliberate and
    # total, so the same evidence always produces the same string: a
    # weight-bearing source's spelling first (a reference work writes a
    # designation the way the programme writes it, a tracker writes it the way
    # its database happens to store it), then the most common, then alphabetical
    # to break a remaining tie rather than leaving it to dictionary order.
    counts = collections.Counter(row["designation"] for row in rows)
    weighted = {row["designation"] for row in rows if row["tier"] in WEIGHT_BEARING_TIERS}
    best_spelling = min(
        counts,
        key=lambda spelling: (spelling not in weighted, -counts[spelling], spelling),
    )
    return best_spelling, f"{len(unique)} independent sources agree", rows


def unique_designations(findings: dict[int, dict[str, Any]]) -> dict[int, dict[str, Any]]:
    """Refuse any designation claimed by more than one catalogue number.

    THE FLIGHT-NUMBER GUARD. Several DSCS III spacecraft exist, and the flight
    designation is both the part most likely to be mismatched and the part a
    reader would notice. If two objects both come out as "DSCS III B-6", at least
    one is wrong and there is no way here to say which -- so BOTH are withdrawn
    and both go to a person. Silently keeping one would be the confident wrong
    answer this whole lane exists to prevent.
    """
    counts = collections.Counter(
        normalized_designation(entry["designation"]) for entry in findings.values()
    )
    kept: dict[int, dict[str, Any]] = {}
    for catalog_id, entry in findings.items():
        if counts[normalized_designation(entry["designation"])] > 1:
            entry["withheld"] = (
                f"the designation '{entry['designation']}' was resolved for more than one "
                "catalogue number, so at least one of them is wrong"
            )
            continue
        kept[catalog_id] = entry
    return kept


# ---------------------------------------------------------------------------
# The gap census: how big is this really?
# ---------------------------------------------------------------------------

#: An object whose card says nothing at all. Same bar the SatNOGS licence lane
#: uses, so the two lanes compete for nothing.
def is_unresolved(satellite: dict[str, Any]) -> bool:
    """Is this a card the site has nothing to say about -- or one THIS lane filled?

    The second half is not a convenience. It is the trap `satnogs_verify` hit and
    wrote up, and this lane walked straight into it on its first re-run. This
    module reads the PUBLISHED catalogue. The moment a finding ships, the object
    stops being `unclassified` and becomes `web-corroborated`; a bar that asked
    only for `unclassified` then found 15 objects where there had been 19,
    re-resolved one of them, and wrote a findings file that silently DROPPED the
    other three -- including both DSCS spacecraft this lane was built for. It
    happened here, on a real run, and the report looked entirely healthy.

    Re-deriving from scratch every run rather than remembering is the point. A
    source can be corrected and a page can come down, and when that happens the
    claim must come off the card.
    """
    return (
        satellite.get("mission") == "other"
        and satellite.get("classificationBasis") == "unclassified"
    ) or satellite.get("classificationBasis") == "web-corroborated"


_FAMILY_TRIM = re.compile(r"[-_ ]*\(?[0-9].*$")


def designation_family(name: str) -> str:
    """The part of a spacecraft name shared by its whole series.

    ``USA 167`` and ``USA 170`` are one family; ``GEESAT-1 A03`` and
    ``GEESAT-1 A04`` are one family. Crude on purpose: this only ranks work, it
    never attaches a claim.
    """
    upper = _collapse(name).upper()
    stem = _FAMILY_TRIM.sub("", upper).strip(" -_/()")
    return stem or upper


def gap_census(satellites: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Every family of objects the classifier cannot resolve, biggest first."""
    families: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for satellite in satellites:
        if is_unresolved(satellite):
            families[designation_family(str(satellite.get("name") or ""))].append(satellite)
    rows = [
        {
            "family": family,
            "objects": len(members),
            "owners": dict(collections.Counter(m.get("ownerCode") for m in members).most_common(3)),
            "orbits": dict(collections.Counter(m.get("orbit") for m in members).most_common(3)),
            "ids": sorted(m["id"] for m in members),
        }
        for family, members in families.items()
    ]
    rows.sort(key=lambda row: (-row["objects"], row["family"]))
    return rows


# ---------------------------------------------------------------------------
# The lane
# ---------------------------------------------------------------------------


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def check_object(
    satellite: dict[str, Any],
    *,
    key: str,
    cache_dir: Path | None = None,
    refresh: bool = False,
    model_url: str | None = None,
) -> dict[str, Any]:
    """One object, end to end. Never writes anything; returns what it found."""
    catalog_id = satellite["id"]
    query = query_for(satellite)
    reference_query = reference_query_for(satellite)

    # TWO PASSES, and the second one is not a nicety. The general pass returns
    # trackers, because a catalogue-number query looks like a tracker query; the
    # restricted pass is the only way the reference works that index by PROGRAMME
    # NAME get a hearing. Measured on USA 170: pass one returned six trackers and
    # the claim was refused; pass two returned Gunter's Space Page, Encyclopedia
    # Astronautica and weebau, and settled it.
    #
    # The reference pass reads a far bigger text window because a reference page
    # is a launch table and the one line naming this spacecraft sits anywhere in
    # it. `key_window` then cuts it back down before the model sees it.
    results: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    for pass_query, domains, chars in (
        (query, None, 1200),
        (reference_query, REFERENCE_DOMAINS, 9000),
    ):
        body = search(
            pass_query, key=key, include_domains=domains, max_characters=chars,
            directory=cache_dir, refresh=refresh,
        )
        for result in body.get("results") or []:
            url = str(result.get("url") or "")
            if url in seen_urls:
                continue
            seen_urls.add(url)
            results.append(result)

    evidence: list[dict[str, Any]] = []
    considered: list[dict[str, Any]] = []
    for result in results:
        url = str(result.get("url") or "")
        text = str(result.get("text") or "")
        title = str(result.get("title") or "")
        haystack = f"{title} {text}"
        keys = mentions_key(haystack, catalog_id, satellite.get("cosparId"))
        row = {
            "url": url,
            "domain": registrable_domain(url),
            "tier": source_tier(url),
            "keys": keys,
        }
        if not keys:
            # Never shown to the model. A page that does not contain the object's
            # own catalogue number cannot say anything about it that this lane is
            # allowed to believe.
            row["outcome"] = "no-key-match"
            considered.append(row)
            continue
        started = dt.datetime.now(dt.timezone.utc)
        began = time.monotonic()
        answer, error, usage = ask_model(
            EXTRACT_SYSTEM,
            EXTRACT_PROMPT.format(
                text=key_window(haystack, catalog_id, satellite.get("cosparId")),
                catalog_id=catalog_id,
                name=satellite.get("name"),
            ),
            url=model_url,
        )
        gpu_usage_ledger.record(
            MODEL_LANE,
            started=started,
            duration_seconds=time.monotonic() - began,
            model=MODEL_NAME,
            outcome="extract" if not error else f"error:{error}",
            ok=not error,
            resource="model",
            catalogId=catalog_id,
            # Real counts when the endpoint answered at all; nothing when it did not.
            **gpu_usage_ledger.usage_fields(usage),
        )
        if error:
            row["outcome"] = f"model-{error}"
            considered.append(row)
            continue
        accepted, why = validated_extraction(answer, text=haystack, satellite=satellite)
        if accepted is None:
            row["outcome"] = f"rejected-{why}"
            considered.append(row)
            continue
        row["outcome"] = "extracted"
        row.update(accepted)
        considered.append(row)
        evidence.append(row)

    designation, why, supporting = corroborate(evidence)
    finding: dict[str, Any] = {
        "id": catalog_id,
        "name": satellite.get("name"),
        "cosparId": satellite.get("cosparId"),
        "query": query,
        "resultsSeen": len(results),
        "considered": considered,
        "verdict": why,
        "checkedAt": utc_now(),
    }
    if designation is None:
        finding["designation"] = None
        return finding
    matched = programme_for(designation)
    if matched is None:
        finding["designation"] = designation
        finding["verdict"] = (
            f"{why}, but '{designation}' is not in the cited programme table, so this "
            "lane has nothing it is allowed to say about it"
        )
        finding["citations"] = [
            {"url": row["url"], "tier": row["tier"], "quote": row["quote"]} for row in supporting
        ]
        return finding
    _, facts = matched
    finding.update({
        "designation": designation,
        "programme": facts["programme"],
        "mission": facts["mission"],
        "sector": facts["sector"],
        "organization": facts["organization"],
        "purpose": facts["purpose"],
        "programmeSource": facts["source"],
        "programmeSourceTier": facts["sourceTier"],
        "citations": [
            {"url": row["url"], "tier": row["tier"], "quote": row["quote"]} for row in supporting
        ],
    })
    return finding


def resolved(findings: Iterable[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    """The findings complete enough to reach a card, after the uniqueness guard."""
    candidates = {
        finding["id"]: finding
        for finding in findings
        if finding.get("designation") and finding.get("programme")
    }
    return unique_designations(candidates)


def write_findings(entries: dict[int, dict[str, Any]], path: Path | None = None) -> Path:
    """The table `build_release` reads. Only what a card needs, plus its evidence."""
    target = path or FINDINGS
    payload = {
        "generatedAt": utc_now(),
        "note": (
            "Written by pipeline/catalog_factcheck.py. Every entry rests on a catalogue-number "
            "match in at least two independent sources, quoted below. Gap-filling only: "
            "build_release applies these where a card says nothing at all, and the curated "
            "override table outranks them."
        ),
        "objects": {
            str(catalog_id): {
                "name": entry["name"],
                "designation": entry["designation"],
                "programme": entry["programme"],
                "mission": entry["mission"],
                "sector": entry["sector"],
                "organization": entry["organization"],
                "purpose": entry["purpose"],
                "programmeSource": entry["programmeSource"],
                "programmeSourceTier": entry["programmeSourceTier"],
                "citations": entry["citations"],
                "checkedAt": entry["checkedAt"],
            }
            for catalog_id, entry in sorted(entries.items())
        },
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return target


def load_findings(path: Path | None = None) -> dict[int, dict[str, Any]]:
    """The web-corroborated table, keyed on catalogue number.

    Keyed on the NUMBER and never on the name -- the same rule the withdrawal and
    participation tables follow, because a lane that exists to fix name-based
    misattribution must not itself attach by name.
    """
    target = path or FINDINGS
    if not target.is_file():
        return {}
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    out: dict[int, dict[str, Any]] = {}
    for key, entry in (raw.get("objects") or {}).items():
        try:
            catalog_id = int(key)
        except (TypeError, ValueError):
            continue
        if not isinstance(entry, dict):
            continue
        # A finding with no citation is not a finding. Refusing it here means a
        # hand-edited or truncated file degrades to "no claim" rather than to an
        # uncited claim on a card.
        if not entry.get("citations") or not entry.get("mission"):
            continue
        out[catalog_id] = entry
    return out


# ---------------------------------------------------------------------------
# The report a person reads
# ---------------------------------------------------------------------------


def render_report(
    *,
    census: list[dict[str, Any]],
    total_objects: int,
    findings: list[dict[str, Any]],
    written: dict[int, dict[str, Any]],
    worked_family: str,
) -> str:
    unresolved_total = sum(row["objects"] for row in census)
    lines: list[str] = []
    add = lines.append
    add("# What the catalogue cannot name, and what the web could settle")
    add("")
    add(f"Generated {utc_now()} by `pipeline/catalog_factcheck.py`.")
    add("")
    add("## The scale of the gap")
    add("")
    add("| | objects |")
    add("|---|---:|")
    add(f"| Objects in the published catalogue | {total_objects} |")
    add(f"| Carrying a designation the classifier cannot resolve | {unresolved_total} |")
    add(f"| Distinct name families among them | {len(census)} |")
    add("")
    add(
        "An unresolved object is one whose card says `mission: other`, `sector: unknown`, "
        "`classificationBasis: unclassified` -- the site has looked at the name and "
        "recognised nothing. That is not the same as a wrong card, and it is worse in one "
        "way and better in another: better because it claims nothing false, worse because "
        f"it is {unresolved_total} cards that teach a visitor nothing."
    )
    add("")
    add("### The biggest families, by object count")
    add("")
    add("| family | objects | owners | orbits |")
    add("|---|---:|---|---|")
    for row in census[:30]:
        owners = ", ".join(f"{k}:{v}" for k, v in row["owners"].items())
        orbits = ", ".join(f"{k}:{v}" for k, v in row["orbits"].items())
        add(f"| `{row['family']}` | {row['objects']} | {owners} | {orbits} |")
    add("")
    add(f"## Worked this run: `{worked_family}`")
    add("")
    add(
        "This is the family the site's owner found missing. US military spacecraft are "
        "registered under **USA designations**, not programme names, which is why a "
        "classifier rule matching the string `DSCS` matched nothing: that string does not "
        "appear anywhere in the catalogue."
    )
    add("")
    add("### Resolved, with citations")
    add("")
    if not written:
        add("Nothing in this family met the corroboration bar this run.")
    else:
        add("| NORAD | catalogue name | resolved as | programme | sources |")
        add("|---:|---|---|---|---|")
        for catalog_id, entry in sorted(written.items()):
            cites = " ".join(
                f"[{cite['tier']}]({cite['url']})" for cite in entry["citations"]
            )
            add(
                f"| {catalog_id} | {entry['name']} | **{entry['designation']}** | "
                f"{entry['programme']} | {cites} |"
            )
        add("")
        add("The quoted spans each check held, verbatim from the retrieved page:")
        add("")
        for catalog_id, entry in sorted(written.items()):
            add(f"- **{catalog_id} {entry['name']} -> {entry['designation']}**")
            for cite in entry["citations"]:
                add(f"  - `{cite['quote'][:220]}` -- <{cite['url']}> ({cite['tier']})")
    add("")
    add("### Left for a person")
    add("")
    add(
        "Every object below stays `unknown` on the site. That is the deliberate outcome: "
        "where the evidence does not settle it, this lane writes nothing."
    )
    add("")
    add("| NORAD | name | pages that mentioned it | why nothing was written |")
    add("|---:|---|---:|---|")
    for finding in sorted(findings, key=lambda f: f["id"]):
        if finding["id"] in written:
            continue
        matched = sum(1 for row in finding["considered"] if row["keys"])
        add(f"| {finding['id']} | {finding['name']} | {matched}/{finding['resultsSeen']} | {finding['verdict']} |")
    add("")
    add("## How a claim gets onto a card")
    add("")
    add(
        "1. The **catalogue number** is the key. A retrieved page that does not contain it "
        "as a standalone token is discarded before the language model sees it.\n"
        "2. The model is asked one closed question and must **copy a span** out of the page. "
        "It is never asked what a spacecraft is; asked that open question about USA 170 it "
        "replied that no such satellite exists and offered a different one.\n"
        "3. The quote must be a **literal substring** of what was retrieved, must contain the "
        "object's own catalogue number, and must contain the designation.\n"
        "4. **Two independent registrable domains** must produce the same designation, and "
        "trackers alone are not enough -- they republish the catalogue being checked.\n"
        "5. The designation must name a programme in the module's **hand-written cited "
        "table**. What a programme IS comes from a person reading a source; the automated "
        "half only decides which programme an object belongs to.\n"
        "6. If two objects resolve to the **same** designation, both are withdrawn: at least "
        "one is wrong and nothing here can say which."
    )
    add("")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    from pipeline import satnogs_verify

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data-root", default=str(ROOT / "public" / "data"))
    parser.add_argument("--report", default=str(STATE / "factcheck-report.md"))
    parser.add_argument("--family", default="USA",
                        help="which unresolved name family to work this run")
    parser.add_argument("--limit", type=int, default=25,
                        help="most objects to check in one run")
    parser.add_argument("--census-only", action="store_true",
                        help="measure the gap and write no findings; needs no key")
    parser.add_argument("--refresh", action="store_true", help="re-fetch even if cached")
    parser.add_argument("--dry-run", action="store_true",
                        help="write the report, write no findings file")
    args = parser.parse_args(argv)

    catalog = satnogs_verify.published_catalog(Path(args.data_root))
    satellites = catalog["satellites"]
    census = gap_census(satellites)

    if args.census_only:
        report = render_report(
            census=census, total_objects=len(satellites), findings=[], written={},
            worked_family=args.family,
        )
        Path(args.report).write_text(report, encoding="utf-8")
        print(f"census only: {sum(r['objects'] for r in census)} unresolved objects "
              f"in {len(census)} families -> {args.report}")
        return 0

    key = require_key()
    work = [
        satellite for satellite in satellites
        if is_unresolved(satellite)
        and designation_family(str(satellite.get("name") or "")) == args.family.upper()
    ][: args.limit]
    if not work:
        print(f"no unresolved objects in family {args.family!r}")
        return 0

    findings = [check_object(satellite, key=key, refresh=args.refresh) for satellite in work]
    written = resolved(findings)
    if not args.dry_run:
        write_findings(written)
    report = render_report(
        census=census, total_objects=len(satellites), findings=findings,
        written=written, worked_family=args.family,
    )
    Path(args.report).write_text(report, encoding="utf-8")
    print(
        f"{len(work)} checked, {len(written)} resolved with citations, "
        f"{len(work) - len(written)} left for a person -> {args.report}"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
