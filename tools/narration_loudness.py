#!/usr/bin/env python3
"""
Measure — and, on request, fix — the loudness of every narration file this site plays.

WHY THIS EXISTS
---------------
Sean's complaint about the chemistry videos was not that any one line sounded wrong. It was
that the level JUMPED between them, because manim-voiceover asked ElevenLabs for each line
separately and shipped whatever level came back. The same thing had quietly happened here:
measured on 2026-08-21, the six narration mp3s the event pages play directly ran from -26.8
to -42.0 LUFS, a fifteen-decibel spread, and every one of them was far below the level of
anything else on the site. A reader turns the volume up for one clip and is startled by the
next.

The lanes that MUX their voice into an mp4 were already fine, because both muxers apply
loudnorm as they mix. The lanes that ship a bare mp3 to an <audio> element had nothing
applying it, and nothing measuring it either — which is the real defect. A level you never
measure is a level you find out about from the person listening.

So: the generators now normalise at the moment they write a file (tools/narrate.py and
tools/narrate_free.py both do), and this exists to catch anything that predates them or
arrives from somewhere else. Run it with no flags and it reports; run it with --fix and it
brings the outliers to the house target without re-rendering anything, which costs nothing
because the audio is already recorded.

THE TARGET, AND WHY THESE NUMBERS
---------------------------------
I = -16 LUFS, TP = -1.5 dBTP, LRA 7. -16 is the streaming-speech convention and leaves
headroom a phone speaker can actually use; -1.5 dBTP keeps the mp3 encoder from clipping on
reconstruction; LRA 7 is tighter than the music default of 9 because narration is one voice
in a quiet room and a wide range here just means one emphatic sentence sitting well above
its neighbours — the exact complaint this file is about.

    python3 tools/narration_loudness.py                    # report
    python3 tools/narration_loudness.py --fix              # report, then correct outliers
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

TARGET_I = -16.0
TARGET_TP = -1.5
TARGET_LRA = 7.0
# How far from target a file may sit and still be left alone. Half a decibel is inaudible;
# two is not, and two is roughly where a listener starts reaching for the volume.
TOLERANCE_DB = 2.0

# Only the files a browser plays DIRECTLY belong here.
#
# media/narration-mechanism/ and media/mechanisms/narration/ are deliberately NOT in this
# list. Nothing serves them: they are the per-line inputs their muxers mix into the mp4s,
# and those muxers apply their own loudnorm as they mix. Normalising them here would put a
# second gain stage in front of the first and make the finished video quieter, not more
# consistent. Their output is what matters and it already measures -18.5 and -18.7 LUFS.
SERVED = [
    ("media/narration", "played by src/observed-imagery.ts on the historical event pages"),
    ("media/narration-layers", "the layer-page beds, played by src/layer-narration.ts"),
]


def measure(path: Path) -> float | None:
    """Integrated loudness of a file, in LUFS."""
    out = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostdin", "-i", str(path),
         "-af", "ebur128=framelog=quiet", "-f", "null", "-"],
        capture_output=True, text=True)
    found = re.findall(r"I:\s*(-?[\d.]+)\s*LUFS", out.stderr)
    return float(found[-1]) if found else None


def normalise(path: Path) -> bool:
    """Two-pass loudnorm, in place. Returns whether the file was rewritten.

    Two passes rather than one because single-pass loudnorm does not know the file's real
    loudness until it has heard it: it guesses at the start and converges, which leaves the
    first second of a ten-second line at the wrong level. The measured pass costs a second
    of CPU.
    """
    probe = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostdin", "-i", str(path), "-af",
         f"loudnorm=I={TARGET_I}:TP={TARGET_TP}:LRA={TARGET_LRA}:print_format=json",
         "-f", "null", "-"], capture_output=True, text=True)
    try:
        blob = probe.stderr[probe.stderr.rindex("{"):]
        stats = json.loads(blob[:blob.rindex("}") + 1])
    except Exception:
        return False

    tmp = path.with_suffix(".norm.mp3")
    run = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostdin", "-y", "-i", str(path), "-af",
         f"loudnorm=I={TARGET_I}:TP={TARGET_TP}:LRA={TARGET_LRA}"
         f":measured_I={stats['input_i']}:measured_TP={stats['input_tp']}"
         f":measured_LRA={stats['input_lra']}:measured_thresh={stats['input_thresh']}"
         f":offset={stats['target_offset']}:linear=true",
         "-ar", "44100", "-ac", "1", "-c:a", "libmp3lame", "-b:a", "128k", str(tmp)],
        capture_output=True, text=True)
    if run.returncode != 0 or not tmp.is_file():
        tmp.unlink(missing_ok=True)
        return False
    tmp.replace(path)
    return True


def refresh_manifest(directory: Path, changed: dict) -> None:
    """Keep a manifest's byte counts honest after the files under it were rewritten.

    A manifest that still claims the old size is a manifest nobody can use to check
    anything, and these ones are read by the verifier as well as by a human.
    """
    manifest = directory / "manifest.json"
    if not manifest.is_file() or not changed:
        return
    try:
        spec = json.loads(manifest.read_text())
    except Exception:
        return
    for entry in spec.get("lines", []):
        name = entry.get("file")
        if name in changed:
            path = directory / name
            entry["bytes"] = path.stat().st_size
            entry["loudnessLUFS"] = changed[name]
            entry["loudnessTarget"] = {"I": TARGET_I, "TP": TARGET_TP, "LRA": TARGET_LRA}
    manifest.write_text(json.dumps(spec, indent=1, ensure_ascii=False) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fix", action="store_true",
                    help="bring anything outside the tolerance to the house target, in place")
    args = ap.parse_args()

    outliers = 0
    for rel, why in SERVED:
        directory = ROOT / rel
        if not directory.is_dir():
            continue
        files = sorted(directory.glob("*.mp3"))
        if not files:
            continue
        print(f"\n{rel} — {why}")
        changed = {}
        for path in files:
            before = measure(path)
            if before is None:
                print(f"  {path.name:38s} UNMEASURABLE")
                outliers += 1
                continue
            off = abs(before - TARGET_I) > TOLERANCE_DB
            if off and args.fix and normalise(path):
                after = measure(path)
                print(f"  {path.name:38s} {before:7.1f} -> {after:7.1f} LUFS  corrected")
                if after is not None:
                    changed[path.name] = round(after, 1)
            else:
                flag = "  OUTSIDE TOLERANCE" if off else ""
                print(f"  {path.name:38s} {before:7.1f} LUFS{flag}")
                if off:
                    outliers += 1
        refresh_manifest(directory, changed)

    print(f"\nTarget I={TARGET_I} LUFS, TP={TARGET_TP} dBTP, LRA={TARGET_LRA}, "
          f"tolerance {TOLERANCE_DB} dB.")
    print(f"{outliers} file(s) still outside it.")
    return 1 if outliers else 0


if __name__ == "__main__":
    raise SystemExit(main())
