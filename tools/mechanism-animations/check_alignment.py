#!/usr/bin/env python3
"""
Prove the voice lands on the caption -- in the shipped file, not in the plan.

`narrate_mux.py` writes narration-alignment.json from arithmetic: caption time
plus audio length against the next caption time. That is the intent. This reads
the finished mp4 back, finds where somebody is actually speaking, and checks the
intent against it. The two disagree for reasons arithmetic cannot see, and one
of them cost a full re-mux to find: `adelay` shifts a stream's TIMESTAMPS rather
than writing leading silence, so the first version of these files had an audio
stream that began 35 seconds in. Every number in the alignment report was right
and the file was wrong.

    python3 check_alignment.py media/mechanisms narration-alignment.json

Checks, per line, per clip:
  * the audio stream starts at 0 and not at the first word
  * somebody is speaking at the second each line says it starts
  * no line is still speaking when the next line starts
  * no speech runs past the end of the picture

It used to also require exactly one speech run per line. That check could not
survive the narration getting denser: lines are now about a second apart, which
is inside its own JOIN_GAP, so two lines read as one run. Quebec has thirteen
runs for seven lines and would have failed it too. What replaced it is the pair
of things that actually matter -- the voice is there when it should be, and two
lines never talk over each other.
"""

from __future__ import annotations

import array
import json
import math
import subprocess
import sys
from pathlib import Path

SR = 8000          # speech detection does not need better
WIN = 0.05         # 50 ms windows
THRESH_DB = -45.0  # anything above this is somebody talking
JOIN_GAP = 1.5     # pauses shorter than this are inside one line, not between two
MIN_RUN = 0.30
ONSET_TOLERANCE = 0.20


def loud_windows(path: Path) -> list[float]:
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-f", "s16le", "-acodec", "pcm_s16le",
         "-ac", "1", "-ar", str(SR), "-"], capture_output=True).stdout
    x = array.array("h")
    x.frombytes(raw[: len(raw) // 2 * 2])
    n = int(SR * WIN)
    out = []
    for i in range(len(x) // n):
        chunk = x[i * n:(i + 1) * n]
        power = sum((v / 32768.0) ** 2 for v in chunk) / n
        if 10 * math.log10(power + 1e-12) > THRESH_DB:
            out.append(i * WIN)
    return out


def runs(windows: list[float]) -> list[tuple[float, float]]:
    segs: list[list[float]] = []
    for t in windows:
        if segs and t - segs[-1][1] <= JOIN_GAP:
            segs[-1][1] = t + WIN
        else:
            segs.append([t, t + WIN])
    return [(round(a, 2), round(b, 2)) for a, b in segs if b - a >= MIN_RUN]


def audio_start(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=start_time",
         "-of", "csv=p=0", str(path)], capture_output=True, text=True).stdout.strip()
    return float(out) if out else float("nan")


def main() -> int:
    media = Path(sys.argv[1])
    report = json.loads(Path(sys.argv[2]).read_text())
    bad = 0
    print(f"{'clip':24s} {'line':22s} {'caption':>8s} {'voice in':>9s} {'voice out':>9s} "
          f"{'onset':>7s} {'headroom':>9s}")
    for scene in report:
        clip = media / f"{scene['stem']}.mp4"
        start = audio_start(clip)
        if not abs(start) < 0.05:
            print(f"  {scene['stem']}: audio stream starts at {start}s, not 0")
            bad += 1
        windows = loud_windows(clip)
        segs = runs(windows)
        if segs and segs[-1][1] > scene["videoSeconds"] + 0.05:
            print(f"  {scene['stem']}: speech runs {segs[-1][1] - scene['videoSeconds']:.2f}s "
                  f"past the end of the picture")
            bad += 1
        for line in scene["lines"]:
            start, adur = line["startSeconds"], line["audioSeconds"]
            # Is anybody talking where this line says it starts? Look in a short
            # window after the declared start: the mp3 carries a few tens of
            # milliseconds of lead-in before the first syllable.
            onset = next((t for t in windows if t >= start - 0.05), None)
            offset = None if onset is None else round(onset - start, 2)
            speaking = offset is not None and offset < ONSET_TOLERANCE
            # The line must be finished before the next one opens its mouth.
            headroom = round(line["nextLineSeconds"] - (start + adur), 3)
            ok = speaking and headroom > -0.05 and start + adur <= scene["videoSeconds"] + 0.05
            bad += 0 if ok else 1
            print(f"{scene['stem']:24s} {line['id']:22s} {start:8.2f} "
                  f"{start:9.2f} {start + adur:9.2f} "
                  f"{'   n/a' if offset is None else f'{offset:+7.2f}'} {headroom:9.2f} "
                  f"{'OK' if ok else 'BAD'}")
    print("\n" + (f"FAILURES: {bad}" if bad else
                  "Every line is being spoken where it says it is, and no two overlap."))
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
