"""One line per real GPU call, in the shape /brain/gpu can actually read.

Why this exists. The page draws usage bars from a jsonl ledger under the VPS
workspace, and every consumer that draws bars is `machine: "vps"` — a
bigmem-resident lane cannot write to a VPS path, so bigmem's GPU work rendered
only as "recorded elsewhere" or as anonymous busy time in the telemetry ring.
The standing rule is that unmeasured GPU use is a defect, and a whole machine
unable to report is the largest instance of it.

FIELD NAMES ARE A CONTRACT, not a preference. `bigmem-gpu-consumers.md` ->
"The /brain/gpu rendering contract" says the gateway needs a time field named
`ts`/`timestamp`/`at`/`t`, and takes a span from `durationMs` (or
`duration_s`/`durationSec`/`tookMs`). A first version of this file used
`startedAt` and `durationSeconds`, which are in neither list: the lines would
have been written, pulled, and drawn as nothing, while every check said done.

ONE FILE PER LANE, matching every other consumer (`ai-web-naming-usage.jsonl`,
`quote-verify-usage.jsonl`). A shared file would leave the gateway to guess
which row owns which line.

What is recorded is the MODEL CALL, not the process. These lanes wake every few
minutes and usually decide not to call the model at all; a quiet-window skip
costs no GPU, and counting it would inflate the picture with work that never
happened.
"""

from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path

STATE_DIR = Path(
    os.environ.get(
        "SPACE_GPU_USAGE_DIR",
        str(Path(__file__).resolve().parents[1] / "state"),
    )
)


def ledger_path(lane: str, directory: Path | None = None) -> Path:
    """Where one lane's receipts live. Named after the lane, so the VPS puller
    and the registry row can both point at it without a lookup table."""
    return Path(directory or STATE_DIR) / f"{lane}-usage.jsonl"


def usage_fields(usage: object, source: str = "llama-server") -> dict:
    """Token counts off a provider's own response body, in the field names the
    VPS usage collector reads — or {} when the response carried none.

    WHY IT RETURNS {} AND NEVER A NUMBER OF ITS OWN. Token counts are never
    estimated: where a call path cannot report usage, the row has to say so.
    /system/models distinguishes a MEASURED row from an absent
    one, and it can only do that if an unmeasurable call writes no token fields
    at all. A chars/4 estimate, or a 0 standing in for "unknown", would draw a
    confident bar over a number nobody counted — worse than the gap it filled.

    Passed through ``record(**usage_fields(...))``, so absent counts add nothing
    to the line: the keys are optional by construction.
    """
    if not isinstance(usage, dict):
        return {}

    def pick(*keys: str) -> int | None:
        for key in keys:
            value = usage.get(key)
            if isinstance(value, bool):
                continue
            if isinstance(value, (int, float)):
                return int(value)
        return None

    prompt = pick("prompt_tokens", "promptTokens", "input_tokens", "inputTokens")
    completion = pick("completion_tokens", "completionTokens", "output_tokens", "outputTokens")
    if prompt is None and completion is None:
        return {}
    out: dict = {"tokenSource": source}
    if prompt is not None:
        out["promptTokens"] = prompt
    if completion is not None:
        out["completionTokens"] = completion
    return out


def record(
    lane: str,
    *,
    started: dt.datetime,
    duration_seconds: float,
    model: str,
    outcome: str,
    ok: bool = True,
    resource: str = "model",
    directory: Path | None = None,
    **extra: object,
) -> None:
    """Append one receipt. Never raises: measurement must not break the lane.

    `extra` is where a lane's real token counts ride — `**usage_fields(usage)`,
    which contributes NOTHING when the transport reported no usage block. Until
    2026-09-21 every lane here threw the response's `usage` away, so /system/models
    could only show these lanes as unmeasured GPU time with no size to it.
    """
    line = {
        # Contract field names. See the module docstring before renaming these.
        "ts": started.astimezone(dt.timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z"),
        "durationMs": int(round(float(duration_seconds) * 1000)),
        "ok": bool(ok),
        "outcome": outcome,
        "lane": lane,
        "resource": resource,
        "model": model,
        "host": os.uname().nodename,
    }
    line.update(extra)
    target = ledger_path(lane, directory)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(line, sort_keys=True) + "\n")
    except OSError as error:  # noqa: BLE001 - never break the lane over a ledger
        print(f"WARNING: could not record GPU usage for {lane}: {error}")


def read(lane: str, directory: Path | None = None) -> list[dict]:
    """Every receipt for one lane, oldest first. Malformed lines are skipped."""
    target = ledger_path(lane, directory)
    if not target.is_file():
        return []
    out: list[dict] = []
    for raw in target.read_text(encoding="utf-8", errors="replace").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            out.append(json.loads(raw))
        except json.JSONDecodeError:
            continue
    return out
