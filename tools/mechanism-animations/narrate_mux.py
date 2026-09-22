#!/usr/bin/env python3
"""
Lay the rendered narration onto the six mechanism animations.

WHY THIS EXISTS RATHER THAN A SECOND SET OF FILES
-------------------------------------------------
The narration is muxed INTO each mp4 rather than served as a parallel mp3 the
page has to keep in sync with the video element. One file means the browser's
own transport bar scrubs picture and voice together, a download carries the
voice with it, and there is no second network request to fail.

WHERE THE ALIGNMENT COMES FROM
------------------------------
Every scene writes `scripts/<Scene>.json` at render time: each caption and the
second at which it becomes legible. A narration line names the caption it is
anchored to, so the voice starts at the instant that caption lands. Nothing here
is hand-timed and nothing is guessed -- change a `hold=` in a scene, re-render,
and the audio follows without being touched.

A line may instead name an explicit `at` second. That is for the opening line of
each clip, which is spoken over the title card and so has no caption to anchor
to. It is the only placement in this file a scene edit does not move, and it is
deliberately at the top of the clip where nothing else is happening.

A line is allowed to still be speaking when a caption changes. It is not allowed
to still be speaking when the NEXT LINE starts, and that is what is enforced.

The audio bed is built the same way the Quebec 1989 GIC schematic in
tools/manim/ builds its own -- loudnorm, adelay, amix, normalize=0 -- so the two
Manim lanes on this site sound like one site.

    python3 narrate_mux.py --scripts scripts --audio media/mechanisms/narration \
                           --script narration/mechanisms.json --video out
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    import numpy as np
except ImportError:                       # the head repair below degrades, it does not fail
    np = None

# Scene class name -> the file stem it is published under.
STEMS = {
    "Reconnection": "dayside-reconnection",
    "Chapman": "chapman-layer",
    "HF": "hf-skip-blackout",
    "Trapped": "trapped-motion",
    "SAA": "eccentric-dipole-saa",
    "Drag": "drag-orbit-decay",
}

# ---------------------------------------------------------------------------
# WHERE LOUDNESS IS SET, AND WHY IT MOVED.
# ---------------------------------------------------------------------------
#
# This file used to run `loudnorm` on EVERY LINE on the way into the mix - a second
# per-line R128 pass on top of the per-line R128 pass tools/narrate.py was already
# doing. EBU R128 integrated loudness is GATED, and a narration line is 3 to 13
# seconds long; on the short ones the gate throws away much of the content, so
# loudnorm measures the wrong input level and applies the wrong gain. Two wrong
# gains in series is not more accurate than one.
#
# The lane now levels each line on RMS at generation (constant gain, no gate) and
# R128 runs ONCE, HERE, on the assembled audio - where it is long enough for R128 to
# be the right tool. Target -18 LUFS / -2 dBTP, matched to tools/manim/mux.py so the
# mechanism clips and the Quebec GIC chain land at the same loudness; Quebec, the
# reference clip, measures -18.5 LUFS.
#
# BACKWARD COMPATIBILITY IS DELIBERATE, NOT DECORATION. A clip whose mp3s predate
# the RMS change is still in the old world: those files were normalised per line to
# -16 LUFS, or (three of them) never normalised at all and sitting 26 dB down.
# Dropping the per-line pass for THOSE would ship a clip with an audible hole in it.
# So the per-line filter is chosen from what the manifest says was actually done to
# each file. When every scene has been re-rendered, the else-branch can go.
LOUDNORM = "loudnorm=I=-18:TP=-2:LRA=9"          # legacy per-line, pre-RMS manifests
FINAL_I, FINAL_TP, FINAL_LRA = -18.0, -2.0, 9.0  # the one R128 pass, on the mix
LEAD_IN_MS = 0     # the caption time already carries the 0.30 s legibility lead


# ---------------------------------------------------------------------------
# THE LEADING EDGE OF A LINE, AND WHY IT HAS TO BE REPAIRED HERE.
# ---------------------------------------------------------------------------
#
# On the rebuilt Drag clip, the voice broke on many transitions: "It does not slow
# down" arrived clipped, and the word "Backwards" was cut off at its head.
#
# Both examples are the FIRST WORDS of their lines, which is why it reads as a
# transition problem. It is not one. Measured, sample by sample, on the shipped clip:
#
#   * the mp3 and the muxed mp4 agree on every line's onset to 0.0 ms, and their
#     first 400 ms correlate at 0.98-0.999, so nothing here moves or truncates a line;
#   * the assembled mix's gain is flat to within 1.5 dB across the whole clip;
#   * the levelling chain in narrate.py (volume + alimiter + a 128k mp3 re-encode) was
#     run against a control file with a clean head and left it untouched.
#
# What is actually wrong is in the file ElevenLabs delivered. A STITCHED generation --
# one carrying previous_text / previous_request_ids, which is what makes a line
# continue the one before it rather than restart -- opens BELOW its own speaking level
# and climbs to it. On mech-06-brake the first 200 ms sit 33.6 dB down, so the /b/ and
# the vowel of "Backwards" are inaudible and the ear is handed "...wards". Across the
# 40-line library, all 6 lines with a soft head are stitched and none of the 7
# unstitched ones are.
#
# THE ROUND-TRIP VERIFIER CANNOT SEE THIS. mech-06-brake transcribes back at
# similarity 1.0 with the syllable inaudible, because speech-to-text reconstructs a
# swallowed onset from context. A verifier that says "the words are all there" is
# answering a different question from "can a listener hear them".
#
# So the repair is here, in the assembly, and it is GAIN ONLY:
#
#   reference    the line's own speaking level over its opening 2.5 s -- the words
#                immediately after the first one, not the whole-line average, which a
#                long quiet clause drags down
#   window       from the onset to the moment the voice first reaches that level, and
#                never longer than 0.50 s. Past the recovery the line is healthy, and a
#                window that ran on would lift a word that never needed it
#   curve        the measured deficit, made non-increasing and smoothed over 40 ms, so
#                it is the inverse of a fade-in rather than a compressor
#   ceiling      26 dB. A hole deeper than that is not a soft attack, it is a take with
#                the word missing, and the honest answer to that is a re-render
#
# It changes no timing, so the alignment above and the phrase-to-visual sync table are
# untouched by construction, and it costs nothing: not one character is re-rendered.
# A line that does not need it is passed through as its own mp3, byte for byte.
LEAD_REF_S = 2.5           # the opening clause whose level the first word must match
LEAD_WINDOW_S = 0.50       # the longest head this will touch
LEAD_MAX_LIFT_DB = 26.0    # past this it is a missing word, not a soft one
LEAD_FLOOR_DB = 6.0        # restore to (speaking level - 6 dB); never above it
LEAD_ENV_W = 12            # 60 ms peak envelope: a stop closure is not a deficit
LEAD_SMOOTH = 8            # 40 ms smoothing on the corrective curve
LEAD_MIN_LIFT_DB = 1.0     # below this, leave the file alone
_FR = 220                  # 5 ms analysis frame at 44100


def _frames_db(x):
    n = len(x) // _FR * _FR
    if n == 0:
        return np.zeros(0)
    return 20 * np.log10(np.sqrt((x[:n].reshape(-1, _FR) ** 2).mean(axis=1)) + 1e-12)


def head_gain(x) -> dict | None:
    """The corrective gain curve for one line's leading edge, or None if it is healthy."""
    db = _frames_db(x)
    if len(db) < 40:
        return None
    speaking = float(np.median(db[db > db.max() - 25]))
    on = int(np.argmax(db > speaking - 30))
    seg = db[on:min(len(db), on + int(round(LEAD_REF_S / 0.005)))]
    opening = float(np.median(seg[seg > seg.max() - 25])) if len(seg) else speaking
    target = opening - LEAD_FLOOR_DB
    env = np.array([db[max(0, i - LEAD_ENV_W // 2):i + LEAD_ENV_W // 2 + 1].max()
                    for i in range(len(db))])
    lim = min(len(db), on + int(round(LEAD_WINDOW_S / 0.005)))
    recovered = np.nonzero(env[on:lim] >= target)[0]
    rec = on + int(recovered[0]) if len(recovered) else lim
    raw = np.clip(target - env[on:rec], 0.0, None)
    deficit = np.clip(raw, 0.0, LEAD_MAX_LIFT_DB)
    if deficit.size == 0 or float(deficit.max()) < LEAD_MIN_LIFT_DB:
        return None
    hull = np.maximum.accumulate(np.append(deficit, 0.0)[::-1])[::-1][:-1]
    k = np.ones(LEAD_SMOOTH) / LEAD_SMOOTH
    padded = np.concatenate([[hull[0]] * LEAD_SMOOTH, hull, [0.0] * LEAD_SMOOTH])
    curve = np.minimum.accumulate(
        np.convolve(padded, k, mode="same")[LEAD_SMOOTH:LEAD_SMOOTH + len(hull)])
    live = np.nonzero(curve > 0.5)[0]
    if not len(live):
        return None
    return {"onFrame": on, "curve": curve,
            "liftDb": round(float(curve[0]), 2),
            "headMs": round(float((live[-1] + 1) * 5.0), 1),
            "speakingDb": round(speaking, 2), "openingDb": round(opening, 2),
            "clampedAtCeiling": bool(float(raw.max()) > LEAD_MAX_LIFT_DB + 1e-9)}


def apply_head_gain(x, c: dict):
    """Apply the curve, with a 20 ms raised-cosine lead-in so the gain never steps."""
    g = np.zeros(len(x))
    on = c["onFrame"] * _FR
    seg = np.repeat(c["curve"], _FR)[:max(0, len(x) - on)]
    g[on:on + len(seg)] = seg
    start = max(0, on - int(0.020 * 44100))
    if on > start:
        g[start:on] = c["liftDb"] * 0.5 * (1 - np.cos(np.linspace(0, np.pi, on - start)))
    return x * 10 ** (g / 20.0)


def decode_pcm(path: Path):
    out = subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(path),
         "-map", "0:a:0", "-ac", "1", "-ar", "44100", "-f", "f32le", "-"],
        capture_output=True, check=True).stdout
    return np.frombuffer(out, dtype="<f4").astype(np.float64)


def stage_line(mp3: Path, dest: Path) -> tuple[Path, dict]:
    """What to feed the mix for this line, and what was done to its leading edge.

    A healthy line is handed back as its own mp3 and is never decoded twice or
    re-encoded. Only a line that measured a soft head is corrected and staged as raw
    f32, which the mix reads losslessly.
    """
    if np is None:
        return mp3, {"applied": False, "reason": "numpy unavailable; head left as delivered"}
    x = decode_pcm(mp3)
    c = head_gain(x)
    if c is None:
        return mp3, {"applied": False, "liftDb": 0.0, "headMs": 0.0}
    y = apply_head_gain(x, c)
    dest.write_bytes(y.astype("<f4").tobytes())
    return dest, {"applied": True, "liftDb": c["liftDb"], "headMs": c["headMs"],
                  "speakingDb": c["speakingDb"], "openingDb": c["openingDb"],
                  "clampedAtCeiling": c["clampedAtCeiling"],
                  "peakAfter": round(float(np.abs(y).max()), 4)}


def line_filter(entry: dict) -> str:
    """The per-line audio filter for one narration clip.

    RMS-levelled clips are passed through untouched: they already sit at a common
    RMS and the final pass sets the absolute level. Anything else is a pre-RMS file
    and keeps the old per-line loudnorm, which is wrong but is less wrong than
    leaving a 26 dB hole in a published clip.
    """
    loud = entry.get("loudness") or {}
    if loud.get("method") == "rms":
        return "aresample=44100"
    return f"{LOUDNORM},aresample=44100"


def probe(path: Path, entries: str) -> str:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", entries, "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True, check=True)
    return out.stdout.strip()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scripts", type=Path, required=True, help="dir of <Scene>.json caption maps")
    ap.add_argument("--audio", type=Path, required=True, help="dir of narration mp3s + manifest.json")
    ap.add_argument("--script", type=Path, required=True, help="narration script (anchors live here)")
    ap.add_argument("--video", type=Path, required=True, help="dir of <stem>.silent.mp4")
    ap.add_argument("--out", type=Path, default=None, help="default: same as --video")
    ap.add_argument("--report", type=Path, default=None,
                    help="where to write narration-alignment.json (default: next to this script)")
    ap.add_argument("--scene", action="append", default=None,
                    help="re-mux only these scenes (e.g. --scene HF). Sean's rule is that "
                         "one clip gets judged before six get paid for, so muxing one clip "
                         "has to be a first-class operation rather than a whole-library run "
                         "with five failures in it. The alignment report is MERGED, not "
                         "replaced, so a single-scene run cannot silently delete the other "
                         "five scenes' rows.")
    args = ap.parse_args()
    outdir = args.out or args.video
    report_path = args.report or (Path(__file__).resolve().parent / "narration-alignment.json")

    spec = json.loads(args.script.read_text())
    manifest = {e["id"]: e for e in json.loads((args.audio / "manifest.json").read_text())["lines"]}

    # Corrected leading edges are staged here as raw f32 and are gone when this
    # function returns. Nothing durable is written outside `outdir` and the report.
    staging_dir = tempfile.TemporaryDirectory(prefix="narrate-mux-")
    staging = Path(staging_dir.name)
    if np is None:
        print("WARNING: numpy is not importable, so no leading edge can be repaired; "
              "lines will be mixed exactly as delivered", file=sys.stderr)

    by_scene: dict[str, list[dict]] = {}
    for line in spec["lines"]:
        by_scene.setdefault(line["scene"], []).append(line)

    report, failures = [], 0
    wanted = set(args.scene) if args.scene else None
    if wanted:
        unknown = wanted - set(STEMS)
        if unknown:
            sys.exit(f"--scene names scenes that are not in this library: {sorted(unknown)}")
    for scene, stem in STEMS.items():
        if wanted and scene not in wanted:
            continue
        silent = args.video / f"{stem}.silent.mp4"
        final = outdir / f"{stem}.mp4"
        if not silent.is_file():
            print(f"MISSING {silent}", file=sys.stderr)
            failures += 1
            continue

        captions = json.loads((args.scripts / f"{scene}.json").read_text())
        marks = captions["lines"]
        vdur = float(probe(silent, "format=duration"))
        lines = by_scene.get(scene, [])

        # A silent bed for the whole clip, as input 1.
        #
        # This is not belt-and-braces. `adelay` shifts the stream's TIMESTAMPS
        # rather than writing leading silence, so a mix of nothing but delayed
        # lines produces an mp4 whose audio stream starts at the first word --
        # 35.36 s into a 60 s clip, in the case that caught this. Players that
        # honour the edit list get it right and players that do not start the
        # voice at frame one, which is a silent, plausible, completely wrong
        # result. An anullsrc input pinned at PTS 0 forces real samples from the
        # start, and the check at the end of this function refuses the file if
        # the audio stream still does not begin at zero.
        inputs = ["-f", "lavfi", "-t", f"{vdur:.3f}", "-i", "anullsrc=r=44100:cl=mono"]
        filters, mixes = [], ["[1:a]"]
        placed = []

        # WHERE A LINE STARTS: a caption index, or an explicit second.
        #
        # `anchor` names a caption and the voice starts when that caption lands,
        # which is still how most lines are placed. `at` names a second directly,
        # and exists because the most important line in each clip has no caption
        # to hang on: the opening one, spoken over the title card before the
        # first caption appears. Without it the earliest a voice could start was
        # the first caption, which on these six clips is 6.1 to 10.3 s in.
        def start_of(line):
            return float(line["at"]) if "at" in line else marks[line["anchor"]]["t"]

        lines = sorted(lines, key=start_of)

        for i, line in enumerate(lines, start=2):
            entry = manifest[line["id"]]
            if not entry.get("verified"):
                print(f"REFUSING {line['id']}: not round-trip verified", file=sys.stderr)
                return 2
            mp3 = args.audio / entry["file"]
            start = start_of(line)
            adur = float(entry["seconds"])

            # THE THING A LINE MUST NOT RUN INTO IS THE NEXT LINE, NOT THE NEXT
            # CAPTION.
            #
            # This check used to measure slack to the next caption, which made a
            # line's maximum length the length of one caption's window -- two to
            # three seconds on these clips. That is a sentence fragment, so the
            # lane wrote very few lines and left the rest of each clip silent.
            # The consequence was three delivered clips whose voice did not
            # arrive until past the halfway mark.
            #
            # Captions change while a person is still talking; that is normal,
            # and it is what Quebec -- the reference clip, the one that works --
            # does on every one of its seven lines. Two voices at once
            # is the real defect, so that is what is refused here.
            nxt = start_of(lines[i - 1]) if i - 1 < len(lines) else vdur
            slack = round(nxt - start - adur, 3)
            anchored = marks[line["anchor"]]["text"] if "anchor" in line else "(explicit time)"
            placed.append({
                "id": line["id"],
                "anchor": line.get("anchor"), "at": line.get("at"),
                "caption": anchored,
                "startSeconds": round(start, 3), "audioSeconds": round(adur, 3),
                "nextLineSeconds": round(nxt, 3), "slackSeconds": slack,
                "fits": slack >= 0,
            })
            if slack < 0:
                failures += 1
                print(f"OVERRUN {line['id']}: audio runs {-slack:.2f}s past the next line",
                      file=sys.stderr)
            delay = int(round(start * 1000)) + LEAD_IN_MS
            src, lead = stage_line(mp3, staging / f"{line['id']}.f32")
            placed[-1]["leadingEdge"] = lead
            if src.suffix == ".f32":
                inputs += ["-f", "f32le", "-ar", "44100", "-ac", "1", "-i", str(src)]
            else:
                inputs += ["-i", str(src)]
            filters.append(f"[{i}:a]{line_filter(entry)},adelay={delay}|{delay}[a{i}]")
            mixes.append(f"[a{i}]")

        mix = (";".join(filters) + ";" + "".join(mixes)
               + f"amix=inputs={len(lines) + 1}:normalize=0,atrim=0:{vdur:.3f}")
        base = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(silent)] + inputs

        # ONE R128 PASS, ON THE ASSEMBLED MIX, IN TWO MEASURED HALVES.
        #
        # Single-pass loudnorm is a dynamic filter: it does not know the file's real
        # loudness until it has heard it, so it guesses at the start and converges,
        # which puts the opening seconds at the wrong level. The measure pass costs a
        # few seconds of CPU and renders no audio, so the AAC encode still happens
        # exactly once - the alternative, encoding and then re-encoding to level, adds
        # a second lossy generation to every clip.
        # `-loglevel error` on `base` would SWALLOW the measurement: loudnorm prints
        # its JSON summary at INFO. That is a silent failure - ffmpeg exits 0, the
        # JSON is simply absent, and the clip ships unlevelled with a warning nobody
        # reads. Measured once, on this clip, before it was caught.
        measure_base = ["ffmpeg", "-hide_banner", "-loglevel", "info"] + base[4:]
        measure = subprocess.run(
            measure_base + ["-filter_complex",
                    f"{mix},loudnorm=I={FINAL_I}:TP={FINAL_TP}:LRA={FINAL_LRA}"
                    ":print_format=json[a]",
                    "-map", "[a]", "-f", "null", "-"],
            capture_output=True, text=True)
        try:
            blob = measure.stderr[measure.stderr.rindex("{"):]
            st = json.loads(blob[:blob.rindex("}") + 1])
            final_af = (f",loudnorm=I={FINAL_I}:TP={FINAL_TP}:LRA={FINAL_LRA}"
                        f":measured_I={st['input_i']}:measured_TP={st['input_tp']}"
                        f":measured_LRA={st['input_lra']}:measured_thresh={st['input_thresh']}"
                        f":offset={st['target_offset']}:linear=true,aresample=44100")
            measured_before = float(st["input_i"])
        except Exception:
            # A clip that could not be measured is still a usable clip. Say so rather
            # than shipping an unlevelled one silently.
            print(f"  WARNING {stem}: could not measure assembled loudness; "
                  f"shipping the mix unlevelled", file=sys.stderr)
            final_af, measured_before = "", None

        subprocess.run(
            base + ["-filter_complex", mix + final_af + "[a]",
                    "-map", "0:v", "-map", "[a]",
                    # Mono. The clone renders a mono voice, so a stereo track would
                    # carry the same signal twice; 96k mono is transparent on speech.
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "96k", "-ac", "1",
                    "-movflags", "+faststart", str(final)], check=True)

        # The audio must begin at the start of the file, not at the first word.
        start = float(probe(final, "stream=start_time").splitlines()[-1])
        if abs(start) > 0.05:
            print(f"REFUSING {stem}: audio stream starts at {start:.3f}s, not 0", file=sys.stderr)
            return 3

        report.append({
            "stem": stem, "scene": scene,
            "videoSeconds": round(vdur, 3),
            "bytes": final.stat().st_size,
            "loudness": {"targetI": FINAL_I, "targetTP": FINAL_TP, "targetLRA": FINAL_LRA,
                         "measuredIBefore": measured_before,
                         "perLine": sorted({line_filter(manifest[l["id"]]).split(",")[0]
                                            for l in lines})},
            "lines": placed,
        })
        talk = sum(p["audioSeconds"] for p in placed)
        lifted = [p for p in placed if (p.get("leadingEdge") or {}).get("applied")]
        print(f"{stem:24s} {vdur:6.2f}s video  {len(placed)} lines  {talk:5.1f}s voice "
              f"({talk / vdur * 100:4.1f}%)  {final.stat().st_size // 1024:5d} KB")
        if lifted:
            worst = max(lifted, key=lambda p: p["leadingEdge"]["liftDb"])
            print(f"{'':24s} leading edge restored on {len(lifted)} line(s), "
                  f"worst {worst['id']} +{worst['leadingEdge']['liftDb']:.1f} dB over "
                  f"{worst['leadingEdge']['headMs']:.0f} ms"
                  + (" (AT THE CEILING - consider a re-render)"
                     if any(p["leadingEdge"]["clampedAtCeiling"] for p in lifted) else ""))

    # MERGE, never replace: a run that produced rows for SOME scenes must not
    # delete the rows of the scenes it did not produce.
    #
    # This merge used to be gated on `if wanted` -- i.e. it only protected the
    # --scene path. That gate did not cover the way the file was actually lost
    # on 2026-09-03: the run passed no --scene at all, just
    #     --video <dir holding one clip>
    # so `wanted` was None, the other five scenes fell out of the loop above as
    # MISSING, and the report was REPLACED with a single row. Five scenes'
    # alignment went with it. tests/mechanism-narration-coverage.test.ts is what
    # noticed; nothing in this file did.
    #
    # A subset can arrive by --scene, by a --video directory holding fewer
    # clips, or by any scene failing mid-run. The write must be safe under all
    # three, so the merge is now unconditional: whatever this run produced
    # updates its own rows and nothing else. A full six-scene run still
    # overwrites all six, because all six are fresh.
    preserved = []
    if report_path.is_file():
        try:
            existing = json.loads(report_path.read_text())
        except Exception:
            existing = []
        produced = {r["scene"] for r in report}
        fresh = {r["scene"]: r for r in report}
        merged = [fresh.pop(r["scene"], r) for r in existing]
        merged.extend(fresh[s] for s in list(fresh))
        preserved = [r["scene"] for r in existing if r["scene"] not in produced]
        report = merged

    report_path.write_text(json.dumps(report, indent=1) + "\n")
    if preserved:
        # Say so out loud. A merge that happens silently is indistinguishable
        # from a replace that happened to be harmless.
        print("  kept existing alignment rows this run did not regenerate: "
              + ", ".join(preserved))
    print(f"\nAlignment written to {report_path}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
