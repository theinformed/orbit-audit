"""
MECHANISM 04 - Gyration, bounce, drift, and why the ring current is a current.

The three motions and their three timescales, then the part that actually
matters operationally: ions and electrons drift in OPPOSITE directions, which
is exactly why they do not cancel. Both contribute to the same westward ring
current, and that current is what a magnetometer at the equator sees as Dst.

Honesty note built into the piece: the drift paths are drawn as circles. Real
drift shells are distorted by convection and their shape depends on energy;
the explorer's inner-magnetosphere layer is where those are drawn. This scene
deliberately does not assert a local-time asymmetry it is not computing.

The Dst trace at the end is the exception to everything above: it is the only
MEASURED object in the mechanism library, badged as such on the frame, and it
is plotted point-for-point from the site's own published Halloween-2003 lane.
See the note on _DST below for why it is no longer a drawn shape.
"""

import json
import os

import numpy as np
from manim import *
from theme import *
from parts import *

# The one measured thing in this piece.
#
# The first version of this scene ended on a curve that LOOKED like a storm and
# was derived from nothing: a closed-form exponential, hand-tuned until the
# shape read right. Every other number in the mechanism library is either
# computed from a named formula or absent, and a drawn curve that implies a
# measurement it is not is the exact failure this site exists to avoid. So the
# trace is now the real series.
#
# 120 hourly points of final Dst from the World Data Centre for Geomagnetism,
# Kyoto, covering the Halloween storm of 2003. They are read out of this
# repository's OWN published artifact - the `dst` lane of the halloween-2003
# replay, one of the three traces the historical-events page already draws -
# rather than fetched again, so the animation and the page cannot drift apart
# and the render needs no network.
_DST = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   "dst_halloween_2003.json")))
DST_HOURS = [p[0] / 60.0 for p in _DST["points_minutes_nT"]]
DST_NT = [float(p[1]) for p in _DST["points_minutes_nT"]]
DST_MIN = min(DST_NT)
DST_MIN_HOUR = DST_HOURS[DST_NT.index(DST_MIN)]

EC = np.array([-5.05, 0.52, 0.0])   # Earth, side view
SS = 1.42                            # screen units per Earth radius, side view
ER = SS                              # Earth at true scale against the field line
L = 4.0


def fieldline(L, n=220):
    lm = np.arccos(np.sqrt(1.0 / L))
    out = []
    for lat in np.linspace(-lm, lm, n):
        r = L * np.cos(lat) ** 2
        out.append(np.array([EC[0] + SS * r * np.cos(lat), EC[1] + SS * r * np.sin(lat), 0.0]))
    return out


def helix(L, turns=34, amp=0.34, n=760):
    """The field line with a gyration wound around it, drawn in the plane."""
    lm = np.arccos(np.sqrt(1.0 / L))
    out = []
    for i in range(n):
        u = i / (n - 1)
        lat = -lm + 2 * lm * u
        r = L * np.cos(lat) ** 2
        p = np.array([EC[0] + SS * r * np.cos(lat), EC[1] + SS * r * np.sin(lat), 0.0])
        nxt_lat = lat + 1e-3
        nr = L * np.cos(nxt_lat) ** 2
        q = np.array([EC[0] + SS * nr * np.cos(nxt_lat), EC[1] + SS * nr * np.sin(nxt_lat), 0.0])
        t = q - p
        t = t / max(1e-9, np.linalg.norm(t))
        nvec = np.array([-t[1], t[0], 0.0])
        # gyroradius shrinks where the field is strong, i.e. near the feet
        b = (1.0 + 3.0 * np.sin(lat) ** 2) ** 0.5 / np.cos(lat) ** 6
        a = amp / (b ** 0.34)
        out.append(p + nvec * a * np.sin(2 * np.pi * turns * u))
    return out


class Trapped(MechanismScene):
    TITLE = "Three motions, and one current"
    KICKER = "Mechanism 04 · Trapped particles"
    SUB = "Gyration, bounce, drift — and why the ring current is a current at all."
    TAKEAWAY = "Opposite charges drifting opposite ways do not cancel. They add to the same westward current."
    MARK = "SCHEMATIC · DRIFT PATHS DRAWN AS CIRCLES"

    def body(self):
        chrome = self.frame_chrome()
        self.motions()
        self.play(FadeOut(chrome), run_time=0.5)
        self.clear_caption()
        self.current()

    # ------------------------------------------------------------------
    def motions(self):
        earth = earth_disc([EC[0], EC[1]], ER)
        fl = VMobject(stroke_color=CYAN, stroke_width=2.8, stroke_opacity=0.55)
        fl.set_points_smoothly(fieldline(L))
        self.play(FadeIn(earth), Create(fl), run_time=1.1)
        self.say("One field line, anchored in the northern and southern hemispheres.", hold=1.5)

        hx = VMobject(stroke_color=MINT, stroke_width=2.4)
        hx.set_points_smoothly(helix(L))
        self.play(Create(hx), run_time=2.6)
        n1 = VGroup(Text("1 · GYRATION", font=MONO_SB, font_size=32, color=MINT),
                    Text("it circles the line", font=SANS, font_size=32, color=MUTED),
                    Text("milliseconds", font=MONO_SB, font_size=30, color=CYAN_BRIGHT)
                    ).arrange(DOWN, buff=0.13)
        if n1.width > 4.60:
            n1.scale(4.60 / n1.width)
        n1.move_to([4.50, 2.08, 0])
        self.play(FadeIn(n1), run_time=0.6)
        self.say("A charged particle circles its field line. Circling alone never carries it to another.", hold=4.92)  # widened for narration

        dot = Dot(hx.point_from_proportion(0.5), radius=0.11, color=CORAL)
        self.add(dot)
        fpts = fieldline(L)
        mp_n, mp_s = Dot(fpts[-20], radius=0.10, color=AMBER), Dot(fpts[19], radius=0.10, color=AMBER)
        mlbl = Text("MIRROR POINTS", font=MONO_SB, font_size=26, color=AMBER)
        mlbl.move_to([-4.45, 3.02, 0])
        mlead = Line([mlbl.get_right()[0] + 0.14, mlbl.get_center()[1] - 0.06, 0],
                     [fpts[-20][0] - 0.06, fpts[-20][1] + 0.16, 0],
                     stroke_color=AMBER, stroke_width=1.6).set_opacity(0.6)
        self.play(MoveAlongPath(dot, hx), run_time=2.4, rate_func=linear)
        self.play(FadeIn(mp_n), FadeIn(mp_s), FadeIn(mlbl), FadeIn(mlead), run_time=0.6)
        n2 = VGroup(Text("2 · BOUNCE", font=MONO_SB, font_size=32, color=AMBER),
                    Text("the field crowds toward", font=SANS, font_size=29, color=MUTED),
                    Text("the poles and turns it back", font=SANS, font_size=29, color=MUTED),
                    Text("seconds", font=MONO_SB, font_size=30, color=CYAN_BRIGHT)
                    ).arrange(DOWN, buff=0.12)
        if n2.width > 4.60:
            n2.scale(4.60 / n2.width)
        n2.move_to([4.50, -0.62, 0])
        self.play(FadeIn(n2), run_time=0.6)
        self.say("Toward the feet the field crowds together, and the particle is turned around.", hold=1.9)
        self.play(MoveAlongPath(dot, hx), run_time=1.9, rate_func=lambda t: 1 - t)
        self.say("It bounces, for as long as nothing scatters it.", hold=5.28)  # widened for narration

        self.play(FadeOut(VGroup(earth, fl, hx, dot, mp_n, mp_s, mlbl, mlead, n1, n2)), run_time=0.7)

    # ------------------------------------------------------------------
    def current(self):
        chrome = self.frame_chrome()
        C = np.array([-3.62, 0.72, 0.0])
        R, DR = 0.50, 1.92
        CX = 3.05                       # the text column, clear of the ring
        earth = earth_disc([C[0], C[1]], R)
        ring = DashedVMobject(Circle(radius=DR, stroke_color=LINE_STRONG, stroke_width=2.2)
                              .move_to(C), num_dashes=44).set_stroke(opacity=0.6)
        sun = VGroup(Text("NOON", font=MONO_SB, font_size=25, color=AMBER)
                     .move_to([C[0] - DR - 0.62, C[1], 0]),
                     Text("MIDNIGHT", font=MONO_SB, font_size=25, color=MUTED)
                     .move_to([C[0] + DR + 1.08, C[1], 0]),
                     Text("DAWN", font=MONO_SB, font_size=25, color=MUTED)
                     .move_to([C[0], C[1] + DR + 0.32, 0]),
                     Text("DUSK", font=MONO_SB, font_size=25, color=MUTED)
                     .move_to([C[0], C[1] - DR - 0.32, 0]))
        view = Text("LOOKING DOWN ON THE NORTH POLE", font=MONO, font_size=22, color=MUTED)
        view.set_opacity(0.62).move_to([CX, 2.86, 0])
        self.play(FadeIn(earth), Create(ring), FadeIn(sun), FadeIn(view), run_time=1.1)
        self.say("Same particles, seen from above the north pole.", hold=1.4)

        ang = ValueTracker(0.0)
        ion = always_redraw(lambda: Dot(
            C + DR * np.array([np.cos(-ang.get_value()), np.sin(-ang.get_value()), 0.0]),
            radius=0.115, color=CORAL))
        ele = always_redraw(lambda: Dot(
            C + DR * np.array([np.cos(PI + ang.get_value()), np.sin(PI + ang.get_value()), 0.0]),
            radius=0.10, color=CYAN_BRIGHT))
        keys = VGroup(Text("ION  +", font=MONO_SB, font_size=30, color=CORAL),
                      Text("ELECTRON  −", font=MONO_SB, font_size=30, color=CYAN_BRIGHT)
                      ).arrange(DOWN, buff=0.14).move_to([CX, 2.06, 0])
        n3 = VGroup(Text("3 · DRIFT", font=MONO_SB, font_size=32, color=VIOLET),
                    Text("the field weakens outward,", font=SANS, font_size=29, color=MUTED),
                    Text("and that walks it round the Earth", font=SANS, font_size=29, color=MUTED),
                    Text("hours", font=MONO_SB, font_size=30, color=CYAN_BRIGHT)
                    ).arrange(DOWN, buff=0.12)
        if n3.width > 5.10:
            n3.scale(5.10 / n3.width)
        n3.move_to([CX + 0.30, 0.55, 0])
        self.add(ion, ele)
        self.play(FadeIn(keys), FadeIn(n3), run_time=0.7)
        self.play(ang.animate.set_value(2 * PI), run_time=4.6, rate_func=linear)
        self.say("They drift right round the planet — and they go opposite ways.", hold=1.9)

        iarr = CurvedArrow(C + (DR + 0.34) * np.array([0.34, 0.94, 0]),
                           C + (DR + 0.34) * np.array([0.94, 0.34, 0]),
                           angle=-0.62, color=CORAL, stroke_width=5, tip_length=0.22)
        earr = CurvedArrow(C + (DR + 0.34) * np.array([-0.94, -0.34, 0]),
                           C + (DR + 0.34) * np.array([-0.34, -0.94, 0]),
                           angle=-0.62, color=CYAN_BRIGHT, stroke_width=5, tip_length=0.22)
        self.play(GrowFromCenter(iarr), GrowFromCenter(earr), run_time=0.8)
        self.say("Ions drift west. Electrons drift east.", hold=1.7)

        big = VGroup(
            Text("A positive charge west", font=SANS_SB, font_size=34, color=CORAL),
            Text("and a negative charge east", font=SANS_SB, font_size=34, color=CYAN_BRIGHT),
            Text("are the same current.", font=SANS_SB, font_size=36, color=TEXT),
        ).arrange(DOWN, buff=0.16)
        if big.width > 5.30:
            big.scale(5.30 / big.width)
        big.move_to([CX + 0.35, 0.62, 0])
        self.play(FadeOut(n3), run_time=0.35)
        self.play(FadeIn(big), run_time=0.8)
        self.say("They do not cancel. They add.", hold=2.0)

        cur = Circle(radius=DR, stroke_color=CORAL, stroke_width=8).move_to(C).set_stroke(opacity=0.35)
        clbl = Text("RING CURRENT · WESTWARD", font=MONO_SB, font_size=26, color=CORAL)
        clbl.move_to([C[0], C[1] - DR - 0.78, 0])
        self.play(FadeOut(big), FadeOut(sun[3]), FadeIn(cur), FadeIn(clbl), run_time=0.9)
        self.remove(ion, ele)
        self.play(FadeOut(VGroup(iarr, earr)), run_time=0.3)
        self.say("One westward current, tens of thousands of kilometres across.", hold=1.8)

        dg = VGroup(Text("Its field inside the ring", font=SANS, font_size=32, color=MUTED),
                    Text("points SOUTH — against", font=SANS, font_size=32, color=MUTED),
                    Text("Earth's own.", font=SANS, font_size=32, color=MUTED)
                    ).arrange(DOWN, buff=0.11)
        if dg.width > 5.10:
            dg.scale(5.10 / dg.width)
        dg.move_to([CX + 0.30, 0.72, 0])
        arrow = Arrow(C + UP * 0.34, C + DOWN * 0.34, color=CORAL, buff=0,
                      stroke_width=6, max_tip_length_to_length_ratio=0.35)
        self.play(FadeIn(dg), GrowArrow(arrow), run_time=0.9)
        self.say("So the field measured at the ground goes down.", hold=1.7)

        ax = Axes(x_range=[0, 120, 24], y_range=[-400, 60, 100], x_length=4.9, y_length=1.62,
                  axis_config={"stroke_color": LINE_STRONG, "stroke_width": 2}, tips=False)
        ax.move_to([CX + 0.30, -1.30, 0])
        # Every vertex below is one measured hourly value. Nothing is smoothed
        # between samples and nothing is interpolated: set_points_as_corners,
        # not set_points_smoothly, because a spline through measurements draws
        # excursions that were never recorded.
        trace = VMobject(stroke_color=CORAL, stroke_width=3.4)
        trace.set_points_as_corners([ax.c2p(h, v) for h, v in zip(DST_HOURS, DST_NT)])
        low = Dot(ax.c2p(DST_MIN_HOUR, DST_MIN), radius=0.055, color=CORAL)

        chip_t = Text("MEASUREMENT", font=MONO_SB, font_size=21, color=VOID)
        chip = VGroup(RoundedRectangle(corner_radius=0.05, width=chip_t.width + 0.30,
                                       height=chip_t.height + 0.20, fill_color=MINT,
                                       fill_opacity=1.0, stroke_width=0), chip_t)
        chip_t.move_to(chip[0].get_center())
        head = VGroup(chip, Text("Dst  ·  Kyoto WDC, final, hourly", font=MONO,
                                 font_size=24, color=TEXT)).arrange(RIGHT, buff=0.26)
        if head.width > 5.30:
            head.scale(5.30 / head.width)
        head.move_to([CX + 0.30, -0.32, 0])

        y0 = Text("0", font=MONO, font_size=20, color=MUTED).set_opacity(0.7)
        y0.next_to(ax.c2p(0, 0), LEFT, buff=0.10)
        y1 = Text("-400 nT", font=MONO, font_size=20, color=MUTED).set_opacity(0.7)
        y1.next_to(ax.c2p(0, -400), LEFT, buff=0.10)

        prov = VGroup(
            Text("KYOTO WDC FINAL HOURLY  ·  28 OCT - 2 NOV 2003  ·  120 HOURS",
                 font=MONO, font_size=20, color=MUTED),
            Text("MINIMUM -383 nT AT 30 OCT 22 UT  ·  EVERY VERTEX IS ONE MEASUREMENT",
                 font=MONO, font_size=20, color=MUTED),
        ).arrange(DOWN, buff=0.10).set_opacity(0.62)
        if prov.width > 5.60:
            prov.scale(5.60 / prov.width)
        # Clear of the bottom rule. At -2.40 this two-line provenance note sat
        # ON the rule with the caption immediately under it -- three rows of
        # type inside ninety pixels, which reads as one smear at the size these
        # play at. It is a citation, and a citation that cannot be read is not
        # a citation.
        prov.move_to([CX + 0.30, BOTTOM_RULE_Y + 0.36, 0])

        self.play(FadeOut(dg), Create(ax), FadeIn(head), FadeIn(y0), FadeIn(y1), run_time=0.7)
        self.play(Create(trace), run_time=2.0)
        self.play(FadeIn(low), FadeIn(prov), run_time=0.5)
        self.say("That dip is Dst. It is how the size of a magnetic storm is stated.", hold=2.3)

        cav = VGroup(
            Text("Drawn as circles.", font=SANS_SB, font_size=32, color=AMBER),
            Text("Real drift shells are pulled out of", font=SANS, font_size=28, color=MUTED),
            Text("round by convection, and their shape", font=SANS, font_size=28, color=MUTED),
            Text("depends on the particle's energy.", font=SANS, font_size=28, color=MUTED),
        ).arrange(DOWN, buff=0.11)
        if cav.width > 5.40:
            cav.scale(5.40 / cav.width)
        cav.move_to([CX + 0.30, -1.16, 0])
        self.play(FadeOut(VGroup(ax, trace, low, head, y0, y1, prov)), run_time=0.5)
        self.play(FadeIn(cav), run_time=0.7)
        self.wait(2.6)
        # `keys` was missing from this list, so the ION + / ELECTRON - legend
        # outlived the diagram it belonged to and sat on the end card for the
        # last five seconds, labelling nothing.
        self.play(FadeOut(VGroup(earth, ring, sun[0], sun[1], sun[2], view, cur, clbl,
                                 arrow, cav, keys, chrome)), run_time=0.7)
        self.clear_caption()
