#!/usr/bin/env python3
"""
Space Environment Explorer — FREE draft narration.

Renders every line of a narration script with offline espeak-ng, at the same loudness
target the paid lane uses, so a whole script can be heard, timed and thrown away without
spending anything.

WHY THIS EXISTS. ElevenLabs is billed per character and Sean's standing rule (2026-07-07)
is that drafting uses a free voice and his clone is the FINAL render only, after he has
approved the words. Sixteen draft renders of an unapproved script is money spent on text
that is about to change. This makes the draft set instead.

IT IS ALSO THE FIT TEST. espeak-ng's default 175 words per minute is within 1% of the
measured rate of the eleven lines already rendered in Sean's clone (2.92 words per second),
so the draft's DURATION is a usable prediction of the paid one's. Every line is measured
against the clip it is spoken over and the overrun is printed, because a line that runs
past its animation is the one defect that cannot be fixed after the audio exists.

LOUDNESS IS APPLIED AT GENERATION TIME, NOT AS A RETROFIT. Each segment is normalised to
I=-16 LUFS, TP=-1.5 dBTP, LRA 7 as it is written. Generating each line as a separate clip
with no normalisation is exactly what produced the dramatic volume jumps between sentences
in Sean's chemistry videos; the fix belongs here, where the file is made.

    python3 tools/narrate_free.py narration/layer-pages.json --outdir <dir>
    python3 tools/narrate_free.py narration/mechanisms.json --outdir <dir>
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

# Matched to the paid lane and to tools/manim/mux.py so a draft and a final sit at the same
# level. LRA 7 rather than 9: a narration line is one voice in a quiet room, and a tighter
# range is what stops one emphatic sentence sitting 6 dB above its neighbours.
LOUDNORM = "loudnorm=I=-16:TP=-1.5:LRA=7"

VOICE = "en-gb"          # the clone is a British-English speaker
WORDS_PER_MINUTE = 175   # espeak-ng's default, and the clone's measured rate


def words(text: str) -> int:
    return len(re.findall(r"[A-Za-z0-9'’.-]+", text))


def duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True, check=True)
    return round(float(out.stdout.strip()), 3)


def render(text: str, dest: Path) -> None:
    """espeak-ng to a wav, then one normalising pass into the mp3 that is kept."""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        wav = Path(tmp.name)
    try:
        subprocess.run(["espeak-ng", "-v", VOICE, "-s", str(WORDS_PER_MINUTE),
                        "-w", str(wav), text], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav),
                        "-af", LOUDNORM, "-ar", "44100", "-ac", "1",
                        "-c:a", "libmp3lame", "-b:a", "96k", str(dest)], check=True)
    finally:
        wav.unlink(missing_ok=True)


def main() -> int:
    ap = argparse.ArgumentParser(description="Draft narration in a free offline voice.")
    ap.add_argument("script", type=Path)
    ap.add_argument("--outdir", type=Path, required=True)
    args = ap.parse_args()

    spec = json.loads(args.script.read_text())
    args.outdir.mkdir(parents=True, exist_ok=True)

    entries, overruns = [], 0
    for line in spec["lines"]:
        lid = line["id"]
        dest = args.outdir / f"{lid}.mp3"
        render(line["text"], dest)
        secs = duration(dest)
        clip_secs = line.get("clipSeconds")
        fits = None if clip_secs is None else secs <= clip_secs
        if fits is False:
            overruns += 1
        entries.append({
            "id": lid,
            "clip": line.get("clip"),
            "file": dest.name,
            "bytes": dest.stat().st_size,
            "seconds": secs,
            "words": words(line["text"]),
            "clipSeconds": clip_secs,
            "slackSeconds": None if clip_secs is None else round(clip_secs - secs, 3),
            "fits": fits,
            "source": line.get("source"),
            "text": line["text"],
        })
        slack = "" if clip_secs is None else f"  clip {clip_secs:5.2f}s  slack {clip_secs - secs:+5.2f}s"
        flag = "" if fits is not False else "   *** OVERRUNS THE CLIP ***"
        print(f"{lid:32s} {words(line['text']):3d} w  {secs:6.2f}s{slack}{flag}")

    manifest = args.outdir / "manifest.json"
    manifest.write_text(json.dumps({
        "generator": "tools/narrate_free.py",
        "engine": f"espeak-ng {VOICE} at {WORDS_PER_MINUTE} wpm",
        "loudness": LOUDNORM,
        "isDraft": True,
        "note": "FREE DRAFT VOICE. Not Sean's clone, and not for publication - this exists so a "
                "script can be heard and timed before anything is billed. The DURATIONS are "
                "meaningful: espeak-ng's rate is within 1% of the clone's measured rate.",
        "script": str(args.script),
        "lines": entries,
    }, indent=1, ensure_ascii=False) + "\n")

    print(f"\n{len(entries)} draft lines in {args.outdir}")
    print(f"{overruns} overrun their clip.")
    return 1 if overruns else 0


if __name__ == "__main__":
    raise SystemExit(main())
