#!/usr/bin/env python3
"""Prove the marks -> per-beat placement path against a REAL marks file.

tools/mechanism-animations/emit_marks.py writes one marks file per MECHANISM clip. The ten
layer clips still have none, so the layer beds remain one beat each — but the FORMAT is the
one this lane consumes, and a real file with real beat boundaries is much better evidence
than the synthetic fixture.

The mechanism script anchors each line to a CAPTION INDEX rather than to a beat id, so the
two have to be reconciled. Section 01 of every marks file is the title card, which carries
no caption; caption i is therefore section i + 2, one-based. That mapping is not assumed —
it is CHECKED against tools/mechanism-animations/narration-alignment.json, which recorded
each line's start straight from the caption map when the mp4s were muxed. If the two
disagree the mapping is wrong and this refuses to go on.

Writes into this lane's own scratch. It does not touch the rendered marks files.

ONE CAVEAT. This feeds MECHANISM lines through the LAYER bed
builder as a format test, and that builder refuses a line which overruns the
beat it is anchored to. Mechanism lines are no longer bound by that: since the
silence rule was retired they routinely span several caption beats, exactly as
Quebec's do, and the authority for whether a mechanism line fits is
narrate_mux.py -- which checks it against the next LINE, not the next beat. So
`SHORTEN THE LINE` in the output below is the layer lane's constraint talking
about the wrong lane's lines. Do not shorten a mechanism line on its say-so;
check tools/mechanism-animations/check_alignment.py instead. The mapping check
this file exists for is the part that still means something.
"""
import json
import pathlib
import subprocess
import sys

REPO = pathlib.Path("/home/sdegan/space-teaching-aid")
STEM = "dayside-reconnection"
SCENE = "Reconnection"
OUT = REPO / ".agent-scratch-narration/realmarks"   # scratch: nothing here ships

marks = json.loads((REPO / f"media/mechanisms/{STEM}.marks.json").read_text())
sections = marks["sections"]
script = json.loads((REPO / "narration/mechanisms.json").read_text())
alignment = json.loads((REPO / "tools/mechanism-animations/narration-alignment.json").read_text())

recorded = {}
for clip in alignment:
    if clip.get("stem") == STEM:
        for placed in clip["lines"]:
            recorded[placed["id"]] = placed["startSeconds"]

lines, bad = [], 0
for line in script["lines"]:
    if line.get("scene") != SCENE:
        continue
    # A line placed by an explicit `at` second -- the opening line of each clip,
    # spoken over the title card -- has no caption and so no section to map to.
    # It is not a mapping failure; there is nothing to map.
    if "anchor" not in line:
        continue
    idx = line["anchor"] + 1          # zero-based caption -> one-based section, +1 title card
    if idx >= len(sections):
        sys.exit(f"{line['id']}: caption {line['anchor']} has no section")
    section = sections[idx]
    want = recorded.get(line["id"])
    if want is None or abs(section["start"] - want) > 0.05:
        print(f"MAPPING WRONG for {line['id']}: marks section {section['id']} starts at "
              f"{section['start']}, the muxer recorded {want}", file=sys.stderr)
        bad += 1
    lines.append({"id": line["id"], "clip": STEM, "beat": section["id"],
                  "source": "already rendered", "text": line["text"]})

if bad:
    sys.exit(f"{bad} line(s) do not line up; the caption->section mapping is not what was assumed")

print(f"caption->section mapping agrees with the muxer's own record for all "
      f"{len(lines)} lines on {STEM}")

OUT.mkdir(parents=True, exist_ok=True)
(OUT / "script.json").write_text(json.dumps({
    "name": f"REAL-MARKS PROOF: {STEM}",
    "note": "The mechanism clip's own already-rendered lines, re-placed from the video "
            "agent's real marks file by tools/narrate_layers_bed.py, purely to prove the "
            "marks path on real data. Nothing here ships.",
    "voice_id": "9M1l09pkVunOZDmYq0Ms",
    "model_id": "eleven_multilingual_v2",
    "lines": lines,
}, indent=1, ensure_ascii=False) + "\n")

# The bed builder wants the clip beside it; the mechanism mp4 already carries its own voice,
# so a copy under a plain video dir is used only for its DURATION.
(OUT / "video").mkdir(exist_ok=True)
link = OUT / "video" / f"{STEM}.mp4"
if not link.exists():
    link.symlink_to(REPO / f"media/mechanisms/{STEM}.mp4")

marksdir = OUT / "marks"
marksdir.mkdir(exist_ok=True)
(marksdir / f"{STEM}.marks.json").write_text(json.dumps(marks))

run = subprocess.run([
    "python3", str(REPO / "tools/narrate_layers_bed.py"),
    "--script", str(OUT / "script.json"),
    "--audio", str(REPO / "media/mechanisms/narration"),
    "--video", str(OUT / "video"),
    "--marks", str(marksdir),
    "--out", str(OUT / "bed"),
    "--voice", "elevenlabs-sean-clone (already rendered)",
], capture_output=True, text=True)
print(run.stdout or "", run.stderr or "", sep="")

manifest = OUT / "bed" / "manifest.json"
if manifest.is_file():
    for clip in json.loads(manifest.read_text())["clips"]:
        print(f"\n{clip['clip']}  clip {clip['videoSeconds']}s  bed {clip['bedSeconds']}s  "
              f"worst offset {clip['worstOffsetSeconds']:+.3f}s  allOnTime={clip['allOnTime']}")
        for placed in clip["lines"]:
            print("  %-22s beat %-28s mark %7.3f  measured %7.3f  offset %+0.3f  "
                  "line %5.2fs  spare %+5.2fs"
                  % (placed["id"], placed["beat"], placed["beatStartSeconds"],
                     placed["measuredStartSeconds"], placed["measuredOffsetSeconds"],
                     placed["audioSeconds"], -placed["overrunSeconds"]))
raise SystemExit(run.returncode)
