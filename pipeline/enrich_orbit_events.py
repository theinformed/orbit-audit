#!/usr/bin/env python3
"""Ask the local model to phrase orbit events that code has already decided.

The model's job here is narrow on purpose. Every number, every classification,
every candidate cause and every honesty statement has been computed by
`pipeline/orbit_events.py` before this script runs. What it adds is a readable
paragraph choosing among computed possibilities — and `pipeline/orbit_narrative.py`
rejects anything that steps outside them.

**Nothing here can break the site.** `describe()` has already produced a
complete, publishable card for every event. If this script is never run, if the
endpoint is down, or if every candidate is rejected, the browser is unchanged
except for a label saying the wording is deterministic. That is what "the model
decorates, never gates" has to mean operationally, and it is the reason this is
a separate script on a separate schedule rather than a step inside
`build_release`.

Endpoint behaviour follows `enrich_qwen.py` exactly, including the
unreachable-endpoint backoff. Retrying a dead endpoint on a five-minute timer is
the anti-pattern that got this project firewalled by CelesTrak once, and it does
not happen here either.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import json
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

from pipeline import gpu_usage_ledger
from typing import Any

from pipeline.orbit_events import load_catalog, NON_PROPULSIVE_SIGNATURES
from pipeline.orbit_release import read_fragment
from pipeline.orbit_narrative import (
    SYSTEM_PROMPT,
    evidence_sheet,
    event_key,
    validate_candidate,
)

ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = ROOT / "public" / "data"
CACHE = ROOT / "pipeline" / ".cache"
NARRATIVE_CACHE = CACHE / "qwen-orbit-narratives.json"

# Shared with enrich_qwen.py deliberately: both lanes talk to the same server,
# so one lane discovering it is down should stop the other knocking too.
UNREACHABLE_MARKER = CACHE / "qwen-endpoint-unreachable"
UNREACHABLE_BACKOFF_SECONDS = 30 * 60

# Writing one narrative costs tens of seconds of local GPU on the same server
# Bob answers from. A cap keeps a catalogue-wide run from occupying it for an
# hour, and the events are processed largest-Delta-v first so the cap always
# spends the budget on the events a visitor is most likely to open.
DEFAULT_MAX_EVENTS = 12


def endpoint_recently_unreachable() -> bool:
    if not UNREACHABLE_MARKER.exists():
        return False
    return (time.time() - UNREACHABLE_MARKER.stat().st_mtime) < UNREACHABLE_BACKOFF_SECONDS


def call_model(endpoint: str, model: str, messages: list[dict[str, str]], max_tokens: int) -> tuple[str, str]:
    """One narrative. Measured, even though this lane is hand-run.

    Its registry row says it writes no log and no artifact, so a manual run left
    only anonymous busy time on the GPU — which is precisely the case the
    unmeasured-GPU-use rule is about. Being dormant is not a reason to be
    invisible on the runs that do happen.
    """
    started = dt.datetime.now(dt.timezone.utc)
    clock = time.monotonic()
    try:
        content, reasoning, usage = _call_model_inner(endpoint, model, messages, max_tokens)
    except Exception as error:  # noqa: BLE001 - recorded, then re-raised unchanged
        gpu_usage_ledger.record(
            "space-orbit-narrative-enrich",
            started=started,
            duration_seconds=time.monotonic() - clock,
            model=model,
            outcome=f"failed: {type(error).__name__}",
            ok=False,
            invocation="manual",
        )
        raise
    # A hand-run lane is the easiest one to leave sizeless: it showed as held GPU time
    # with no token count, because the server's `usage` block was parsed and dropped.
    # A failed call still writes no counts — there is no body to read them from.
    gpu_usage_ledger.record(
        "space-orbit-narrative-enrich",
        started=started,
        duration_seconds=time.monotonic() - clock,
        model=model,
        outcome="wrote-narrative",
        invocation="manual",
        **gpu_usage_ledger.usage_fields(usage),
    )
    return content, reasoning


def _call_model_inner(
    endpoint: str, model: str, messages: list[dict[str, str]], max_tokens: int
) -> tuple[str, str, object]:
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"},
        "chat_template_kwargs": {"enable_thinking": True},
    }
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            result = json.load(response)
    except urllib.error.URLError as error:
        CACHE.mkdir(parents=True, exist_ok=True)
        UNREACHABLE_MARKER.touch()
        raise RuntimeError(
            f"local model endpoint {endpoint} is unreachable ({error.reason});"
            f" backing off for {UNREACHABLE_BACKOFF_SECONDS // 60} minutes"
        ) from error
    with contextlib.suppress(FileNotFoundError):
        UNREACHABLE_MARKER.unlink()
    choice = result["choices"][0]
    message = choice["message"]
    content = str(message.get("content") or "")
    reasoning = str(message.get("reasoning_content") or "")
    # This model thinks first and answers second. A token ceiling hit mid-thought
    # returns a full reasoning trace and an EMPTY answer, which otherwise
    # surfaces as an unhelpful JSON parse error several frames later.
    if not content.strip():
        raise RuntimeError(
            "the model returned no answer"
            f" (finish_reason={choice.get('finish_reason')}, reasoning_chars={len(reasoning)});"
            " raise --max-tokens if the reasoning trace is long"
        )
    # Third element is the server's own usage block (None when it sent none) — the
    # caller ledgers it. Kept out of the return shape the pipeline consumes.
    return content, reasoning, result.get("usage")


def parse_reply(content: str) -> dict[str, str]:
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip(), flags=re.IGNORECASE)
    value = json.loads(cleaned)
    text, caveat = value.get("text"), value.get("caveat")
    if not isinstance(text, str) or not isinstance(caveat, str):
        raise RuntimeError("model response must contain string text and caveat fields")
    if not (40 <= len(text) <= 700) or not (20 <= len(caveat) <= 200):
        raise RuntimeError(
            f"model response length is outside the contract: text={len(text)}, caveat={len(caveat)}"
        )
    if re.search(r"\d", text + caveat):
        raise RuntimeError("model narrative introduced a number; every value is rendered by code")
    return {"text": text.strip(), "caveat": caveat.strip()}


def call_and_parse(
    endpoint: str, model: str, messages: list[dict[str, str]], max_tokens: int, attempts: int = 2
) -> dict[str, str]:
    """One bounded retry that tells the model exactly what was wrong.

    A reply that misses the contract by a few characters used to throw away the
    whole generation. One correction recovers the common case without letting a
    confused model loop.
    """
    feedback: str | None = None
    for attempt in range(attempts):
        turn = messages if feedback is None else [*messages, {"role": "user", "content": feedback}]
        content, reasoning = call_model(endpoint, model, turn, max_tokens)
        if not reasoning.strip():
            raise RuntimeError(
                "the endpoint returned no reasoning_content; use a dedicated reasoning-enabled"
                " profile rather than Bob's shared production lane"
            )
        try:
            return parse_reply(content)
        except (RuntimeError, json.JSONDecodeError) as error:
            if attempt == attempts - 1:
                raise
            feedback = (
                f"Your previous reply was rejected: {error}."
                " Return corrected JSON with exactly the same two fields, obeying every length"
                " limit precisely. Do not add commentary."
            )
    raise RuntimeError("unreachable")


def build_event_records() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """The published events, read back rather than recomputed.

    **This used to open the archive and run the whole detector again.** That was
    cheap when the archive was hours old and it is the same 9.3 GB, five-minute
    scan that took the live site down when the 2004-2025 back-fill landed — see
    `docs/orbit-browser-wiring.md` §0. Running it a second time on a second timer
    would have reproduced the outage on the nightly narrative lane instead of the
    publish lane.

    It is also wrong on its own terms. A narrative has to describe **the event a
    visitor is looking at**, and a visitor is looking at what was published. A
    second independent detection run can differ from the published one — a
    cohort gains a member, a baseline shifts by one interval — and a narrative
    written against a slightly different event is a narrative attached to
    numbers the reader cannot see.

    So this reads the artifact `pipeline/orbit_release.py` wrote, through the
    manifest fragment that names it, and adds only the catalogue facts the
    evidence sheet wants and the bundle does not carry.
    """
    fragment = read_fragment(DATA_ROOT)
    record_ref = fragment.get("orbitEvents") if fragment else None
    if not record_ref:
        raise RuntimeError(
            "no published orbit events to write narratives for; "
            "run `python3 -m pipeline.orbit_release --build-cache` first"
        )
    bundle = json.loads((DATA_ROOT / record_ref["path"]).read_text())
    controls = bundle.get("controls") or {}
    catalog = load_catalog(DATA_ROOT)
    records = [
        {**record, "catalog": catalog.get(record["norad"], {})}
        for record in bundle.get("events", [])
        if record.get("signature") not in NON_PROPULSIVE_SIGNATURES
    ]
    records.sort(key=lambda r: -(r["deltaV"]["totalMetresPerSecond"] or 0.0))
    return records, controls


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", default="http://127.0.0.1:8080/v1/chat/completions")
    parser.add_argument("--model", default="bigmem-chat")
    parser.add_argument("--max-tokens", type=int, default=8192)
    parser.add_argument("--max-events", type=int, default=DEFAULT_MAX_EVENTS)
    parser.add_argument(
        "--force",
        action="store_true",
        help="rewrite narratives that are already cached and still valid",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print the evidence sheet and prompt for the top event without calling anything",
    )
    args = parser.parse_args()

    records, controls = build_event_records()
    if not records:
        print("no propulsive events in the archive; nothing to narrate")
        return 0

    if args.dry_run:
        sheet = evidence_sheet(records[0], controls)
        print(json.dumps({"system": SYSTEM_PROMPT, "evidenceSheet": sheet}, indent=2))
        return 0

    if endpoint_recently_unreachable():
        print("local model endpoint was unreachable recently; not knocking again yet")
        return 0

    try:
        cached = json.loads(NARRATIVE_CACHE.read_text())
        cached = cached if isinstance(cached, dict) else {}
    except (OSError, json.JSONDecodeError):
        cached = {}

    written = 0
    kept = 0
    rejected = 0
    for record in records:
        if written >= args.max_events:
            break
        key = event_key(record)
        if not args.force and validate_candidate(cached.get(key), record) is not None:
            kept += 1
            continue
        sheet = json.dumps(evidence_sheet(record, controls), indent=2, sort_keys=True)
        try:
            reply = call_and_parse(
                args.endpoint,
                args.model,
                [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"Evidence sheet:\n{sheet}"},
                ],
                args.max_tokens,
            )
        except RuntimeError as error:
            print(f"stopping: {error}")
            break
        candidate = {
            "schema": 1,
            "model": args.model,
            "eventKey": key,
            "generatedAt": dt.datetime.now(dt.timezone.utc)
            .isoformat(timespec="seconds")
            .replace("+00:00", "Z"),
            **reply,
        }
        # Validated here as well as at publish time. Caching a candidate the
        # gate will reject wastes the GPU that produced it on every subsequent
        # run, because nothing else would ever mark it as tried.
        if validate_candidate(candidate, record) is None:
            rejected += 1
            print(f"rejected narrative for {record['norad']} {record['name']}: failed the gate")
            continue
        cached[key] = candidate
        written += 1
        print(f"wrote narrative for {record['norad']} {record['name']} ({record['signature']})")

    CACHE.mkdir(parents=True, exist_ok=True)
    temporary = NARRATIVE_CACHE.with_suffix(".next")
    temporary.write_text(json.dumps(cached, indent=2, sort_keys=True) + "\n")
    temporary.chmod(0o600)
    temporary.replace(NARRATIVE_CACHE)
    print(f"{written} written, {kept} still valid, {rejected} rejected -> {NARRATIVE_CACHE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
