"""Mux the seven rendered GIC-chain narration lines onto the silent animation.

Each line is delayed to its own mark, levelled to -18 LUFS, and mixed into one
track trimmed to the last mark's end.

    python3 tools/manim/mux.py
"""
import json, subprocess
marks = {m["id"]: m for m in json.load(open("marks.json"))}
order = ["gic-01-field","gic-02-faraday","gic-03-line","gic-04-saturation",
         "gic-05-harmonics","gic-06-relays","gic-07-collapse"]
end = max(m["end"] for m in marks.values())
inputs, filters, mixes = [], [], []
for i, key in enumerate(order, start=1):
    inputs += ["-i", f"out/{key}.mp3"]
    delay = int(round(marks[key]["start"] * 1000)) + 250
    filters.append(f"[{i}:a]loudnorm=I=-18:TP=-2:LRA=9,adelay={delay}|{delay},apad[a{i}]")
    mixes.append(f"[a{i}]")
graph = ";".join(filters) + ";" + "".join(mixes) + f"amix=inputs={len(order)}:normalize=0,atrim=0:{end:.2f}[a]"
subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-i","silent.mp4"] + inputs + [
    "-filter_complex", graph, "-map","0:v","-map","[a]",
    "-c:v","libx264","-profile:v","high","-crf","24","-preset","slow","-pix_fmt","yuv420p",
    "-movflags","+faststart","-c:a","aac","-b:a","112k","-ac","2",
    "quebec-1989-gic-chain.mp4","-y"], check=True)
json.dump({"stem":"quebec-1989-gic-chain","durationSeconds":round(end,2),
           "width":1280,"height":720,
           "sections":[{"id":m["id"],"start":m["start"],"end":m["end"]} for m in json.load(open("marks.json"))]},
          open("quebec-1989-gic-chain.marks.json","w"), indent=1)
print("muxed", round(end,2))
