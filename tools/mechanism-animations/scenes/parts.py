"""Drawing parts shared by the mechanism animations."""

import numpy as np
from manim import *
from theme import *


def head(pos, tangent, color, size=0.115):
    """A filled arrowhead sitting at `pos`, pointing along `tangent`."""
    t = np.array(tangent, dtype=float)
    n = np.linalg.norm(t)
    if n < 1e-9:
        t = np.array([1.0, 0.0, 0.0])
        n = 1.0
    t = t / n
    tri = Triangle(fill_color=color, fill_opacity=1.0, stroke_width=0).scale(size)
    tri.rotate(angle_of_vector(t) - PI / 2)
    tri.move_to(np.array([pos[0], pos[1], 0.0]))
    return tri


def flow(pts, color, width=3.0, arrows=(0.5,), smooth=True, opacity=1.0, size=0.115):
    """A field or flow line: one smooth stroke plus arrowheads along it."""
    pts = [np.array([p[0], p[1], 0.0], dtype=float) for p in pts]
    v = VMobject(stroke_color=color, stroke_width=width, stroke_opacity=opacity)
    if smooth:
        v.set_points_smoothly(pts)
    else:
        v.set_points_as_corners(pts)
    g = VGroup(v)
    for a in arrows:
        p = v.point_from_proportion(a)
        eps = 0.008
        q = v.point_from_proportion(min(1.0, a + eps))
        r = v.point_from_proportion(max(0.0, a - eps))
        g.add(head(p, q - r, color, size).set_opacity(opacity))
    return g


def earth_disc(center, r, label_it=False, lit_from=LEFT):
    """A small Earth: dark disc, bright limb, and a day/night terminator."""
    cx, cy = center[0], center[1]
    body = Circle(radius=r, stroke_color=CYAN, stroke_width=2.2,
                  fill_color="#08202c", fill_opacity=1.0).move_to([cx, cy, 0])
    d = np.array([lit_from[0], lit_from[1], 0.0], dtype=float)
    d = d / np.linalg.norm(d)
    lit = AnnularSector(inner_radius=0.0, outer_radius=r, angle=PI,
                        start_angle=angle_of_vector(d) - PI / 2,
                        fill_color=CYAN, fill_opacity=0.16, stroke_width=0)
    lit.move_to([cx + d[0] * r * 0.424, cy + d[1] * r * 0.424, 0])
    g = VGroup(body, lit)
    if label_it:
        t = Text("EARTH", font=MONO_SB, font_size=26, color=MUTED).next_to(body, DOWN, buff=0.16)
        g.add(t)
    return g


def dashed_v(x, y0, y1, color=VIOLET, width=2.2, dash=0.13):
    return DashedLine([x, y0, 0], [x, y1, 0], stroke_color=color,
                      stroke_width=width, dash_length=dash, dashed_ratio=0.55)


def tag(text, at, color, size=FS_SMALL, mono=True, anchor=ORIGIN, buff=0.0):
    t = Text(text, font=(MONO_SB if mono else SANS_SB), font_size=size, color=color)
    t.move_to([at[0], at[1], 0])
    if not np.allclose(anchor, ORIGIN):
        t.shift(np.array([anchor[0], anchor[1], 0.0]) * buff)
    return t


def shue(theta, r0=10.0, alpha=0.58):
    return r0 * (2.0 / (1.0 + np.cos(theta))) ** alpha


def magnetopause(ex, ey, s, r0=10.0, alpha=0.58, tmax=2.30, n=140):
    """Screen points of a Shue-shaped magnetopause. Sunward is screen-left."""
    out = []
    for th in np.linspace(-tmax, tmax, n):
        r = shue(abs(th), r0, alpha)
        out.append([ex - s * r * np.cos(th), ey + s * r * np.sin(th)])
    return out


def dipole_arc(L, ex, ey, s, sunward=True, lat_max=None, n=90):
    """One closed dipole shell in the meridian plane, screen coordinates."""
    lm = np.arccos(np.sqrt(1.0 / L)) if lat_max is None else lat_max
    out = []
    for lat in np.linspace(-lm, lm, n):
        r = L * np.cos(lat) ** 2
        x = r * np.cos(lat)
        z = r * np.sin(lat)
        out.append([ex - s * x * (1 if sunward else -1), ey + s * z])
    return out
