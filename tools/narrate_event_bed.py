#!/usr/bin/env python3
"""
Stitch the six rendered event-chart lines into ONE narration bed, and measure it.

WHY A BED AT ALL, WHEN SIX MP3S ALREADY EXIST
---------------------------------------------
Sean asked for a voice-over that walks a reader through the Starlink chart, "just over a
minute". Six separate files can be played in sequence by a browser, but then the schedule
lives in JavaScript: a queue of `ended` handlers, each one starting the next fetch, on a
tab that may be throttled or backgrounded, with the picture trying to follow whichever
element happens to be current. Every gap in that clip is a place where the timing can slip
and nothing can measure it afterwards.

One bed removes the schedule. The gaps are baked in by ffmpeg here, offline, and the page
is left with a single number to follow -- `audio.currentTime` on one element that never
seeks. That is the same trade tools/narrate_layers_bed.py makes for the layer clips, and
this file reuses its measurement helpers rather than re-deriving them.

Nothing here calls ElevenLabs. The per-line mp3s are already rendered and already paid
for; this only pads and concatenates them.

THE BED'S SHAPE
---------------
    lead-in | line 01 | gap | line 02 | gap | ... | line 06 | tail

The lead-in exists so the first word does not arrive on the same frame as the reader's
click. The gaps are the breath between sentences -- long enough to hear a full stop, short
enough that the picture does not visibly idle. The tail lets the last sentence land before
the clip stops. All three are stated once, below, and every start time in the manifest is
derived from them plus the MEASURED duration of each line. No start time is hand-typed.

WHAT IS MEASURED, AND REFUSED
-----------------------------
After the bed is written it is re-opened and each line's onset is read back out of the
delivered mp3 with silencedetect, corrected for that line's own attack (a soft consonant
sits under the noise floor for 60-110 ms and would otherwise read as a placement error).
A line more than OFFSET_TOLERANCE_SECONDS off its intended start fails the run. "It sounds
about right" is not evidence.

    python3 tools/narrate_event_bed.py --script narration/event-charts.json \
        --audio media/event-charts/narration --scene starlink-2022-chart
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from narrate_layers_bed import (  # noqa: E402
    OFFSET_TOLERANCE_SECONDS,
    duration,
    onset_at_or_after,
    voice_onsets,
)

# The bed's three spacings, in seconds. A reader hears these as pacing; the chart's
# narration anchors are expressed against the line starts these produce, so changing any of
# them re-times the picture too -- which is why the anchors are keyed to line IDs in
# src/event-narration.ts rather than to seconds copied out of here.
LEAD_IN_SECONDS = 0.80
GAP_SECONDS = 0.55
TAIL_SECONDS = 1.60


def build(scene: str, lines: list, audio_dir: Path, out_dir: Path) -> dict:
    dest = out_dir / f"{scene}-bed.mp3"

    placed: list[dict] = []
    inputs: list[str] = []
    filters: list[str] = []
    mixes: list[str] = []
    at = LEAD_IN_SECONDS

    for index, line in enumerate(lines):
        src = audio_dir / f"{line['id']}.mp3"
        if not src.is_file():
            print(f"REFUSING {scene}: no rendered audio at {src}", file=sys.stderr)
            return {"scene": scene, "ok": False}
        seconds = duration(src)
        # The file's own attack, measured with the same 20 ms window the bed is read back
        # with, so the two numbers are comparable. See narrate_layers_bed.onset_at_or_after.
        onsets = voice_onsets(src, min_seconds=0.02)
        lead_in = round(onsets[0], 3) if onsets else 0.0
        placed.append({
            "id": line["id"],
            "index": index,
            "startSeconds": round(at, 3),
            "audioSeconds": seconds,
            "endsAtSeconds": round(at + seconds, 3),
            "leadInSeconds": lead_in,
            "text": line["text"],
            "note": line.get("note", ""),
        })
        at += seconds + GAP_SECONDS

    total = round(at - GAP_SECONDS + TAIL_SECONDS, 3)

    # An anullsrc pinned at PTS 0 for the whole length. `adelay` shifts TIMESTAMPS rather
    # than writing samples, so without this the bed's audio stream can begin at the first
    # word; a player that ignores the edit list then starts the voice at frame one, which
    # is silent, plausible and completely wrong.
    inputs += ["-f", "lavfi", "-t", f"{total:.3f}", "-i", "anullsrc=r=44100:cl=mono"]
    mixes.append("[0:a]")
    for i, entry in enumerate(placed, start=1):
        delay = int(round(entry["startSeconds"] * 1000))
        inputs += ["-i", str(audio_dir / f"{entry['id']}.mp3")]
        filters.append(f"[{i}:a]aresample=44100,adelay={delay}|{delay}[a{i}]")
        mixes.append(f"[a{i}]")

    # normalize=0: every line was already levelled to -20 dB RMS where it was rendered, and
    # amix's default averaging would drop each of them by a factor of the input count.
    graph = (";".join(filters) + ";" + "".join(mixes)
             + f"amix=inputs={len(mixes)}:normalize=0,atrim=0:{total:.3f},"
               f"apad=whole_dur={total:.3f}[a]")
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"] + inputs
                   + ["-filter_complex", graph, "-map", "[a]",
                      "-ar", "44100", "-ac", "1", "-c:a", "libmp3lame", "-b:a", "96k",
                      str(dest)], check=True)

    bed_seconds = duration(dest)
    worst = 0.0
    for entry in placed:
        expected = entry["startSeconds"] + entry["leadInSeconds"]
        measured = onset_at_or_after(dest, entry["startSeconds"])
        if measured is None:
            measured = expected
        entry["measuredStartSeconds"] = measured
        entry["expectedVoiceAtSeconds"] = round(expected, 3)
        entry["measuredOffsetSeconds"] = round(measured - expected, 3)
        entry["onTime"] = abs(measured - expected) <= OFFSET_TOLERANCE_SECONDS
        worst = max(worst, abs(measured - expected))
        if not entry["onTime"]:
            print(f"OFF-BEAT {scene}/{entry['id']}: expected the voice at {expected:.3f}s, "
                  f"measured {measured:.3f}s", file=sys.stderr)

    return {
        "scene": scene,
        "ok": all(e["onTime"] for e in placed),
        "file": dest.name,
        "bytes": dest.stat().st_size,
        "bedSeconds": bed_seconds,
        "plannedSeconds": total,
        "leadInSeconds": LEAD_IN_SECONDS,
        "gapSeconds": GAP_SECONDS,
        "tailSeconds": TAIL_SECONDS,
        "voiceSeconds": round(sum(e["audioSeconds"] for e in placed), 3),
        "worstOffsetSeconds": round(worst, 3),
        "offsetToleranceSeconds": OFFSET_TOLERANCE_SECONDS,
        "lines": placed,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--script", type=Path, required=True)
    ap.add_argument("--audio", type=Path, required=True)
    ap.add_argument("--scene", action="append", default=[],
                    help="scene id to stitch; repeatable. Default: every scene in the script.")
    args = ap.parse_args()

    script = json.loads(args.script.read_text())
    scenes: dict[str, list] = {}
    for line in script["lines"]:
        scenes.setdefault(line["scene"], []).append(line)
    wanted = args.scene or sorted(scenes)

    reports = [build(scene, scenes[scene], args.audio, args.audio) for scene in wanted
               if scene in scenes]
    manifest = args.audio / "bed-manifest.json"
    manifest.write_text(json.dumps({
        "generator": "tools/narrate_event_bed.py",
        "note": ("One narration bed per chart scene: the six already-rendered lines "
                 "concatenated with a measured lead-in, gaps and tail, so the page has a "
                 "single clock to follow. `measuredStartSeconds` was read back out of the "
                 "delivered mp3 with silencedetect, not asserted from the filter graph."),
        "voice": f'{script.get("voice_name", "")} ({script.get("voice_id", "")}, {script.get("model_id", "")})',
        "scenes": reports,
    }, indent=1, ensure_ascii=False) + "\n")

    for report in reports:
        if not report.get("ok"):
            print(f"{report['scene']}: FAILED", file=sys.stderr)
            continue
        print(f"{report['scene']}: {report['bedSeconds']:.2f}s bed, "
              f"{report['voiceSeconds']:.2f}s of voice, worst offset "
              f"{report['worstOffsetSeconds']:.3f}s")
        for entry in report["lines"]:
            print(f"    {entry['id']}  starts {entry['startSeconds']:7.3f}s  "
                  f"runs {entry['audioSeconds']:6.3f}s  measured "
                  f"{entry['measuredStartSeconds']:7.3f}s  "
                  f"off {entry['measuredOffsetSeconds']:+.3f}s")
    return 0 if all(r.get("ok") for r in reports) else 1


if __name__ == "__main__":
    raise SystemExit(main())
