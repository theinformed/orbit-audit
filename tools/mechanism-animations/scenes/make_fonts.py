"""
Convert the site's own woff2 faces to TTF so Pango can see them.

fontconfig cannot load woff2, and these frames are set in the site's real
Inter and IBM Plex Mono rather than a lookalike, so the conversion is a step in
the render recipe. Inter ships as a 400-700 variable font and is instantiated
at two static weights; Plex Mono ships as separate static faces and only needs
the wrapper stripped.

Paths are repo-relative with env overrides, because this used to be hardcoded
to /home/node inside the OpenClaw gateway container and therefore ran in
exactly one place. Manim is also installed on bigmem now, which is where
Manim renders belong -- they are CPU-heavy and that machine has the cores.

    python3 make_fonts.py
    cp ttf/*.ttf ~/.local/share/fonts && fc-cache -f ~/.local/share/fonts
"""

import os
import sys

sys.path.insert(0, os.environ.get("PYLIBS", "/tmp/pylibs"))
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
SRC = os.environ.get("FONT_SRC", os.path.join(REPO, "src", "fonts"))
OUT = os.environ.get("FONT_OUT", os.path.join(HERE, "ttf"))
os.makedirs(OUT, exist_ok=True)

f = TTFont(os.path.join(SRC, "inter-400-700.woff2"))
axes = [a.axisTag for a in f["fvar"].axes] if "fvar" in f else []
print("Inter axes:", axes)
for wght, name in ((400, "Regular"), (600, "SemiBold")):
    g = TTFont(os.path.join(SRC, "inter-400-700.woff2"))
    inst = instancer.instantiateVariableFont(g, {"wght": wght}, inplace=True, updateFontNames=True)
    inst.flavor = None
    p = os.path.join(OUT, f"Inter-{name}.ttf")
    inst.save(p)
    print("wrote", p, os.path.getsize(p))

for w, name in ((400, "Regular"), (500, "Medium"), (600, "SemiBold"), (700, "Bold")):
    src = os.path.join(SRC, f"plex-mono-{w}.woff2")
    t = TTFont(src)
    t.flavor = None
    p = os.path.join(OUT, f"IBMPlexMono-{name}.ttf")
    t.save(p)
    print("wrote", p, os.path.getsize(p))
