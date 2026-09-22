#!/usr/bin/env python3
"""Create a fact-bounded teaching brief with a dedicated reasoning-enabled Qwen lane.

THIS PROGRAM IS A GUEST ON SOMEBODY ELSE'S GPU
----------------------------------------------
The model server on 127.0.0.1:8080 is not ours. It is one ``llama-server``
process with exactly two slots, and its other users are:

  * An assistant's night batch — seven jobs between 22:50 and 05:30 ET,
    serialised behind one global lock with a 600-second wait. When they are
    slowed they hit LOCK TIMEOUT and the night's work is lost, which has
    happened.
  * That assistant's live traffic, where a human is waiting for the answer.
  * A second teaching site that narrates at 02:30, 03:30, 08:30, 14:30, 15:30,
    20:30 and 21:30 ET.

Measured over the 24 hours to 2026-08-08, this program fired 245 times, called
the model 110 times, and held it for 8,590 seconds — a 9.7% duty cycle on a
server that had produced 11,212 seconds of generation in total since boot. The
teaching site was the largest single consumer of this machine's GPUs and nothing
on the operations page showed it.

Four things keep it a guest, and they are independent on purpose:

  1. **It writes far less often.** pipeline/teaching_brief.py now invalidates the
     cached brief only when a value leaves the band that would change a word in
     it. See that module for the derivation.
  2. **It is silent all night.** ``--quiet-window`` covers the whole night
     batch with margin. Its edges are wall-clock Eastern, so daylight saving
     moves them with the jobs they are protecting.
  3. **It yields to anyone actually working.** ``--yield-to-busy`` asks the
     server whether a slot is busy and skips the tick if one is. A skip costs
     nothing; the timer fires again in five minutes. A probe that fails is
     treated as "do not call", never as "call anyway", because a closed port
     under WSL2 hangs rather than refusing and a hang here is indistinguishable
     from a busy server.
  4. **It has a spending budget.** ``--min-write-interval-minutes`` puts a floor
     on the gap between two model calls. The fact gate decides whether a rewrite
     would be CORRECT; this decides how often we are willing to PAY for one.
     Suppressing a rewrite never publishes a stale interpretation: the gate in
     pipeline/teaching_brief.py is evaluated again at publish time, and
     build_release falls back to the deterministic sentence, which is honest,
     just less interesting.

Nothing here changes the server. ``--reasoning off`` is a global flag on the
shared local inference server that other scheduled work depends on; this
program opts into thinking per request, which is the only correct place to
do it.
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
import zoneinfo
from pathlib import Path

from pipeline import gpu_usage_ledger
from typing import Any

from pipeline.build_release import CACHE, brief_fact_packet, canonical_json, sha256
from pipeline.teaching_brief import (
    MAX_BRIEF_AGE_MINUTES,
    brief_fingerprint,
    facts_snapshot,
    latest_observed_at,
    load_candidate,
    validate_candidate,
)


ROOT = Path(__file__).resolve().parents[1]


# Retrying a dead endpoint on a timer is the same anti-pattern that got this
# project firewalled by CelesTrak, so it does not happen here either. When the
# local model server is unreachable, back off instead of knocking every five
# minutes. The site is unaffected: build_release simply publishes the
# deterministic sentence, which is honest, just less interesting.
UNREACHABLE_MARKER = CACHE / "qwen-endpoint-unreachable"
UNREACHABLE_BACKOFF_SECONDS = 30 * 60


def endpoint_recently_unreachable() -> bool:
    if not UNREACHABLE_MARKER.exists():
        return False
    return (time.time() - UNREACHABLE_MARKER.stat().st_mtime) < UNREACHABLE_BACKOFF_SECONDS


# ---------------------------------------------------------------------------
# The nightly quiet window
# ---------------------------------------------------------------------------

#: The night batch runs on local wall clock, so this window does too. A window
#: expressed in UTC would silently slide by an hour twice a year and stop
#: covering the jobs it exists to protect — in November it would open at 23:45
#: local and the 22:50 job would be back in contention.
QUIET_ZONE = "America/New_York"

#: 22:45 is five minutes ahead of the first night job (22:50); 05:45 is fifteen
#: minutes past the last (05:30). The
#: window also covers both of the Skew-T site's night narrations, at 02:30 and
#: 03:30. The first tick after it closes repopulates the brief before morning.
QUIET_START = dt.time(22, 45)
QUIET_END = dt.time(5, 45)

#: The spending budget: the shortest gap allowed between two model calls. A
#: module constant rather than only an argparse default because ops/watchdog.py
#: imports it to work out how many writes a day the configuration permits, and a
#: watchdog with its own private copy of a threshold is a watchdog that will one
#: day report green against a rule nobody is applying any more.
DEFAULT_MIN_WRITE_INTERVAL_MINUTES = 120.0

#: Measured on 2026-08-08 over three real fact packets: one call, an 8,192-token
#: ceiling, mean 37.7 s and 6,392 completion tokens. Exported for the same
#: reason as the interval above — the operations page turns it into "seconds of
#: somebody else's GPU per day" and must not guess at it.
MEASURED_SECONDS_PER_WRITE = 37.7


def zone(name: str = QUIET_ZONE) -> dt.tzinfo:
    """The named zone, or UTC with a warning rather than a silent wrong answer.

    A missing tzdata would otherwise turn the quiet window into a seven-hour
    band in the wrong place, which is the failure that only shows up months
    later. UTC is wrong too, but it is wrong loudly and in the log.
    """
    try:
        return zoneinfo.ZoneInfo(name)
    except zoneinfo.ZoneInfoNotFoundError:
        print(f"WARNING: no tz database entry for {name}; the quiet window will be "
              "applied in UTC, which is not what it was designed for", flush=True)
        return dt.timezone.utc


def in_quiet_window(moment: dt.datetime, start: dt.time = QUIET_START,
                    end: dt.time = QUIET_END, tz: dt.tzinfo | None = None) -> bool:
    """True when local wall-clock time is inside the window, which wraps midnight.

    Wall clock, deliberately: the comparison is made after converting to the
    zone, so the window follows daylight saving instead of drifting against it.
    """
    local = moment.astimezone(tz or zone()).time()
    if start <= end:
        return start <= local < end
    return local >= start or local < end


# ---------------------------------------------------------------------------
# Yielding to whoever is actually working
# ---------------------------------------------------------------------------

#: Short on purpose. Under WSL2 a closed port HANGS rather than refusing, so a
#: probe without a tight deadline can sit here for the whole systemd timeout
#: while holding nothing and learning nothing. Both endpoints are tried, so the
#: worst case is twice this; measured against a closed port it returned "busy"
#: after 6.0 s rather than hanging.
PROBE_TIMEOUT_SECONDS = 3.0

_METRIC_PROCESSING = re.compile(r"^llamacpp:requests_processing\s+([0-9.eE+-]+)\s*$", re.MULTILINE)

#: vLLM (the Spark pair) names its equivalent gauge vllm:num_requests_running and labels it.
#: Continuous batching means one extra request does not block anyone the way a llama.cpp slot
#: does, so "busy" for a Spark endpoint is a queue depth, not any activity at all: the
#: neighbouring workload bursts 8 chains, and one 2-hourly brief riding alongside
#: fewer than 4 of them is noise.
_METRIC_VLLM_RUNNING = re.compile(
    r"^vllm:num_requests_running\{[^}]*\}\s+([0-9.eE+-]+)\s*$", re.MULTILINE)
VLLM_BUSY_THRESHOLD = 4.0



def _get(url: str, timeout: float) -> str:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return response.read().decode("utf-8", "replace")


def server_is_busy(base: str, timeout: float = PROBE_TIMEOUT_SECONDS) -> tuple[bool, str]:
    """(busy, why). Anything that is not a clear "idle" answer counts as busy.

    Both endpoints are free and local. /slots is asked first because it names
    which slot is occupied; /metrics is the fallback for a server started with
    --no-slots, which answers 501 there.

    The default is deliberately busy-on-doubt. This program is the lowest
    priority consumer on the machine and a skipped tick costs nothing, so the
    cheap mistake is skipping when the server was free, and the expensive one is
    calling while a human waits on the same GPU.
    """
    try:
        slots = json.loads(_get(f"{base}/slots", timeout))
        if isinstance(slots, list):
            busy = [slot for slot in slots
                    if isinstance(slot, dict) and slot.get("is_processing")]
            return bool(busy), (
                f"{len(busy)} of {len(slots)} slots processing" if busy
                else f"all {len(slots)} slots idle")
    except (urllib.error.URLError, OSError, ValueError, TimeoutError) as error:
        slots_error = str(error)[:120]
    else:
        slots_error = "/slots did not answer with a list of slots"

    try:
        body = _get(f"{base}/metrics", timeout)
    except (urllib.error.URLError, OSError, ValueError, TimeoutError) as error:
        return True, f"neither endpoint answered ({slots_error}; {str(error)[:120]})"
    found = _METRIC_PROCESSING.search(body)
    if not found:
        vllm = _METRIC_VLLM_RUNNING.search(body)
        if vllm:
            running = float(vllm.group(1))
            return running >= VLLM_BUSY_THRESHOLD, f"vllm num_requests_running={running:g}"
        return True, f"/metrics has no requests_processing gauge ({slots_error})"
    processing = float(found.group(1))
    return processing > 0, f"requests_processing={processing:g}"


def last_write_age_minutes(path: Path, now: dt.datetime) -> float | None:
    """How long since a brief was last written, from the brief's own stamp.

    Falls back to the file's mtime, and returns None only when there is no file
    at all — which is the one case that should never be rate-limited, because
    the site has no brief to fall back on but the deterministic sentence.
    """
    candidate = load_candidate(path)
    if isinstance(candidate, dict):
        stamp = candidate.get("generatedAt")
        if isinstance(stamp, str) and stamp:
            try:
                written = dt.datetime.fromisoformat(stamp.replace("Z", "+00:00"))
            except ValueError:
                written = None
            if written is not None:
                if written.tzinfo is None:
                    written = written.replace(tzinfo=dt.timezone.utc)
                return (now - written).total_seconds() / 60.0
    try:
        return (now.timestamp() - path.stat().st_mtime) / 60.0
    except OSError:
        return None


# How many tokens one brief is allowed to think for.
#
# 8,192, and it is a measurement rather than a preference. Every number below
# was taken on 2026-08-08 against real published fact packets on this server.
#
# The intuition — cap it near the size of the answer, which is 850 + 240
# characters, about 300 tokens — does not survive contact with this model. Its
# reasoning trace for this task runs about 22,000 characters, roughly 6,000
# tokens, and it does not adapt to the room it is given. Measured, three packets
# at each ceiling:
#
#     ceiling   result
#     2,048     0 of 3 answered. finish_reason=length every time.
#     3,072     0 of 3 answered. finish_reason=length every time.
#     4,096     0 of 3 answered. finish_reason=length every time.
#     6,144     2 of 3 answered; the third truncated mid-JSON.
#     8,192     3 of 3 answered, finish_reason=stop, mean 6,392 completion
#               tokens and 37.7 s.
#
# Adding "think briefly, keep your reasoning under a hundred words" to the
# system prompt was tried and changed nothing: at a 2,048 ceiling the trace was
# ~7,200 characters and overran, at 4,096 it was ~14,800 and overran. The thought
# grows to whatever it is given and then runs past it, so a low ceiling does not
# buy a cheap brief, it buys no brief and a failed unit.
#
# So the saving comes from making ONE call instead of two — 11,148 completion
# tokens and 72.0 s per brief before, 6,392 and 37.7 s after — and this ceiling
# is set where it stops a runaway thought without truncating an ordinary one.
#
# Truncation stays loud rather than silent: call_model raises when the answer
# comes back empty, naming the finish reason and the size of the trace. A brief
# assembled out of a truncated thought would be worse than no brief.
DEFAULT_MAX_TOKENS = 8192


def call_model(endpoint: str, model: str, messages: list[dict[str, str]], max_tokens: int) -> tuple[str, str]:
    """One brief. Measured, because unmeasured GPU use is a defect.

    The measurement wraps THIS function rather than the process: the timer wakes
    every five minutes and usually decides not to call the model at all, and
    recording those would inflate the picture with work that never happened.
    A failed call is recorded too — a 300 s timeout against a wedged endpoint
    occupies the same slot a successful brief would have.
    """
    started = dt.datetime.now(dt.timezone.utc)
    clock = time.monotonic()
    try:
        content, reasoning, usage = _call_model_inner(endpoint, model, messages, max_tokens)
    except Exception as error:  # noqa: BLE001 - recorded, then re-raised unchanged
        gpu_usage_ledger.record(
            "space-explorer-brief",
            started=started,
            duration_seconds=time.monotonic() - clock,
            model=model,
            outcome=f"failed: {type(error).__name__}",
            ok=False,
        )
        raise
    # The receipt used to say only how LONG the GPU was held. llama-server had been
    # returning its own `usage` block on every one of these calls and the parse threw
    # it away, so /system/models drew this lane as unmeasured while the numbers sat in
    # the response body. A failed call still writes no counts, because there is no
    # body to read them from — an honest gap, never an estimate.
    gpu_usage_ledger.record(
        "space-explorer-brief",
        started=started,
        duration_seconds=time.monotonic() - clock,
        model=model,
        outcome="wrote-brief",
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
        # Opting in per request. The server's own --reasoning off stays where it
        # is: it is global and the neighbouring night batch depends on it.
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
    # This model thinks first and answers second. If the token ceiling is hit
    # mid-thought the reply is a full reasoning trace and an EMPTY answer, which
    # otherwise surfaces as an unhelpful JSON parse error several frames later.
    if not content.strip():
        raise RuntimeError(
            "the model returned no answer"
            f" (finish_reason={choice.get('finish_reason')},"
            f" reasoning_chars={len(reasoning)});"
            " raise --max-tokens if the reasoning trace is long"
        )
    # Third element is the server's own usage block (None when it sent none) — the
    # caller ledgers it. Kept out of the return shape the pipeline consumes.
    return content, reasoning, result.get("usage")


def parse_brief(content: str) -> dict[str, str]:
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip(), flags=re.IGNORECASE)
    value = json.loads(cleaned)
    text = value.get("text")
    caveat = value.get("caveat")
    if not isinstance(text, str) or not isinstance(caveat, str):
        raise RuntimeError("model response must contain string text and caveat fields")
    if not (40 <= len(text) <= 850) or not (20 <= len(caveat) <= 240):
        raise RuntimeError(
            f"model response length is outside the brief contract: text={len(text)}, caveat={len(caveat)}"
        )
    hit = re.search(r"\S*\d\S*", text + caveat)
    if hit:
        # Naming the offending token matters: the bounded retry feeds this message back to the
        # model, and "introduced a number" alone does not teach it that F2/F10.7 nomenclature
        # counts as a digit.
        raise RuntimeError(
            f"model brief introduced a number ({hit.group(0)!r}); exact values belong in fact"
            " cards, and jargon containing digits (F2, F10.7, S4) must be reworded"
        )
    return {"text": text.strip(), "caveat": caveat.strip()}


def call_and_parse(
    endpoint: str,
    model: str,
    messages: list[dict[str, str]],
    max_tokens: int,
    attempts: int = 2,
    require_reasoning: bool = True,
) -> tuple[dict[str, str], str]:
    """Call the model and parse, giving it one chance to correct itself.

    A reply that misses the length contract by a few characters used to raise
    and throw away the roughly seventy seconds of local GPU that produced it.
    One bounded retry that tells the model exactly what was wrong recovers the
    common case without letting a confused model loop.
    """
    feedback: str | None = None
    for attempt in range(attempts):
        turn = messages if feedback is None else [*messages, {"role": "user", "content": feedback}]
        content, reasoning = call_model(endpoint, model, turn, max_tokens)
        if require_reasoning and not reasoning.strip():
            # A routing tripwire, not a quality gate: it catches the misconfiguration where
            # this unit silently lands on the shared non-thinking production profile. The Spark
            # endpoint serves an Instruct model that never emits reasoning_content, so the
            # unit opts out explicitly with --allow-no-reasoning; every hard constraint on
            # the brief itself is enforced deterministically in pipeline/teaching_brief.py.
            raise RuntimeError(
                "the endpoint returned no reasoning_content; use a dedicated reasoning-enabled"
                " profile rather than Bob's shared production lane"
            )
        try:
            return parse_brief(content), reasoning
        except (RuntimeError, json.JSONDecodeError) as error:
            if attempt == attempts - 1:
                raise
            feedback = (
                f"Your previous reply was rejected: {error}."
                " Return corrected JSON with exactly the same two fields, obeying every"
                " length limit precisely. Do not add commentary."
            )
    raise RuntimeError("unreachable")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", default="http://127.0.0.1:8080/v1/chat/completions")
    parser.add_argument("--model", default="bigmem-chat")
    parser.add_argument("--max-tokens", type=int, default=DEFAULT_MAX_TOKENS)
    parser.add_argument(
        "--allow-no-reasoning", action="store_true",
        help="accept a reply without reasoning_content (required for non-thinking Instruct"
             " endpoints such as the Spark pair; the deterministic brief gates still apply)")
    parser.add_argument(
        "--skip-if-valid",
        action="store_true",
        help=(
            "exit without calling the model when the cached brief still describes the current"
            " conditions and has life left. Writing a brief costs about thirty-eight seconds of"
            " local GPU on the same server Bob answers from, so on a quiet day this does nothing."
        ),
    )
    parser.add_argument(
        "--refresh-before-minutes",
        type=int,
        default=45,
        help="with --skip-if-valid, rewrite once the cached brief is within this many minutes of expiring",
    )
    parser.add_argument(
        "--quiet-window", default=f"{QUIET_START:%H:%M}-{QUIET_END:%H:%M}",
        help=("local Eastern wall-clock window during which this never calls the model, so"
              " Bob's night lane and the Skew-T site have both slots. Set to an empty string"
              " to disable."),
    )
    parser.add_argument(
        "--min-write-interval-minutes", type=float,
        default=DEFAULT_MIN_WRITE_INTERVAL_MINUTES,
        help=("floor on the gap between two model calls. The fact gate decides whether a"
              " rewrite would be correct; this decides how often it is worth paying for one."
              " Suppressing a rewrite never shows a stale brief — the same gate runs again at"
              " publish time and the site falls back to its deterministic sentence."),
    )
    parser.add_argument(
        "--no-yield-to-busy", dest="yield_to_busy", action="store_false",
        help="call even when another request is already occupying a slot (not the default)",
    )
    args = parser.parse_args()

    now = dt.datetime.now(dt.timezone.utc)
    destination = CACHE / "qwen-teaching-brief.json"

    # The quiet window is checked FIRST and unconditionally, before any file is
    # read and before any socket is opened, because at 03:00 the correct amount
    # of work for this program to do is none.
    if args.quiet_window.strip():
        try:
            start_text, _, end_text = args.quiet_window.partition("-")
            start = dt.time.fromisoformat(start_text.strip())
            end = dt.time.fromisoformat(end_text.strip())
        except ValueError:
            print(f"--quiet-window {args.quiet_window!r} is not HH:MM-HH:MM", flush=True)
            return 2
        if in_quiet_window(now, start, end):
            local = now.astimezone(zone())
            print(f"inside the {start:%H:%M}-{end:%H:%M} quiet window "
                  f"(local time {local:%H:%M %Z}); leaving both slots to Bob's night lane")
            return 0

    manifest = json.loads((ROOT / "public" / "data" / "manifest.json").read_text())
    weather = json.loads((ROOT / "public" / "data" / manifest["spaceWeather"]["path"]).read_text())
    facts = brief_fact_packet(weather)

    if args.skip_if_valid and endpoint_recently_unreachable():
        print("local model endpoint was unreachable recently; not knocking again yet")
        return 0

    if args.skip_if_valid:
        cached = load_candidate(destination)
        horizon = now + dt.timedelta(minutes=args.refresh_before_minutes)
        if validate_candidate(cached, facts, sha256, canonical_json, now=horizon) is not None:
            print("cached brief still describes current conditions; not calling the model")
            return 0

        # Past the gate: conditions have moved enough that the brief is wrong.
        # That says a rewrite would be correct, not that it is affordable.
        age_minutes = last_write_age_minutes(destination, now)
        if age_minutes is not None and age_minutes < args.min_write_interval_minutes:
            print(f"conditions have moved, but the last brief is only {age_minutes:.0f} min old "
                  f"and the budget is one write per {args.min_write_interval_minutes:.0f} min; "
                  "the site publishes its deterministic sentence until then")
            return 0

        if args.yield_to_busy:
            base = args.endpoint.split("/v1/")[0]
            busy, why = server_is_busy(base)
            if busy:
                print(f"model server is busy ({why}); yielding this tick, the timer fires again "
                      "in five minutes")
                return 0
            print(f"model server is free ({why})")

    facts_json = json.dumps(facts, indent=2, sort_keys=True)
    system = (
        "You write concise space-weather teaching interpretations for U.S. Navy students. "
        "Use only the supplied facts. Separate observations from possible physical meaning. "
        "Do not forecast, claim local spacecraft effects, or invent values. "
        "State NO quantities at all: no digits, and do not spell numbers out as words either "
        "(no 'three hundred kilometers', no 'twelve Earth radii'). Describe magnitudes only in "
        "qualitative terms such as low, moderate, elevated, quiet, or disturbed. "
        "Jargon containing digits counts as a number too: never write F2-layer, F10.7, S4, or "
        "any flare class with a digit - say 'the ionospheric F-region peak', 'solar radio flux', "
        "'scintillation index', 'a minor B-class flare' instead. "
        "The text must be between seventy and one hundred ten words. "
        "The caveat must be one sentence under thirty words describing the limits of YOUR OWN interpretation "
        "- that it is a snapshot of current observations, not a forecast and not a claim about any particular "
        "spacecraft or location. Never copy or paraphrase a caveat field from the fact packet: those describe "
        "individual source models, not this brief. "
        "Return JSON with exactly two strings: text and caveat."
    )
    # ONE call, not two.
    #
    # There used to be a second, "strict factual reviewer" pass over the draft.
    # It was measured rather than assumed, on three real fact packets drawn from
    # different parts of a live 26-hour history: the draft alone was accepted by
    # validate_candidate() 3 times out of 3, and the reviewer rewrote wording in
    # 2 of those 3 without changing whether the brief was publishable. It was
    # paying about half of a 72-second run for prose churn.
    #
    # It could be dropped because it was never what made the brief safe. Every
    # hard constraint — no digits, no spelled-out quantities, the length
    # contract, no echoed source caveat, still describes the conditions, not
    # stale — is enforced deterministically in pipeline/teaching_brief.py, on
    # the way out, by code that consults no model. A model reviewing a model was
    # decoration over a gate that was already closed.
    written, _ = call_and_parse(
        args.endpoint,
        args.model,
        [{"role": "system", "content": system},
         {"role": "user", "content": f"Write the brief from this fact packet:\n{facts_json}"}],
        args.max_tokens,
        require_reasoning=not args.allow_no_reasoning,
    )
    candidate = {
        "schema": 1,
        "kind": "model-assisted",
        "model": args.model,
        "reasoningUsed": not args.allow_no_reasoning,
        "factsSha256": sha256(canonical_json(facts)),
        "factsFingerprint": brief_fingerprint(facts, sha256, canonical_json),
        "factsSnapshot": facts_snapshot(facts),
        "observationsAt": latest_observed_at(facts),
        "generatedAt": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        **written,
    }
    CACHE.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".next")
    temporary.write_text(json.dumps(candidate, indent=2) + "\n")
    temporary.chmod(0o600)
    temporary.replace(destination)
    print(destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
