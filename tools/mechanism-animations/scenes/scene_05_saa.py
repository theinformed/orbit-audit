"""
MECHANISM 05 - The South Atlantic Anomaly is geometry, not mystery.

Every number on screen comes from the site's own arithmetic in
src/eccentric-dipole.ts: IGRF-13 degree-1 and degree-2 Gauss coefficients put
through Fraser-Smith (1987). Evaluated for 2026.6 that gives an offset of
610 km toward 22.7 N 134.7 E, and a dipole tilt of 9.1 degrees. The antipode of
that offset direction - 22.7 S, 45.3 W - is in the South Atlantic off Brazil,
which is the entire point of the piece.

An eccentric dipole is still a dipole. It reproduces where the anomaly is, not
its exact shape, and the frame says so.
"""

import numpy as np
from manim import *
from theme import *
from parts import *

EC = np.array([-1.90, 0.45, 0.0])
R = 1.72                       # 6371 km
KMU = R / 6371.0               # screen units per km
OFF = 610.0 * KMU              # the offset, drawn to the same scale
RB = 1.966                     # one chosen surface of equal field strength:
                               # 300 km up on the far side, 1520 km on the near one
ORB = R * (6371.0 + 500.0) / 6371.0


class SAA(MechanismScene):
    TITLE = "The South Atlantic Anomaly is geometry"
    KICKER = "Mechanism 05 · Eccentric dipole"
    SUB = "The dipole is not at the centre of the Earth, and Brazil is on the far side of the offset."
    TAKEAWAY = "Nothing is missing over Brazil. The dipole is 610 km off centre, and Brazil is on the other side of it."
    MARK = "SCHEMATIC · ECCENTRIC DIPOLE, IGRF-13"

    def body(self):
        chrome = self.frame_chrome()
        earth = earth_disc([EC[0], EC[1]], R)
        earth[1].set_opacity(0.0)   # no Sun in this view, so no terminator
        centre = VGroup(Line(EC + LEFT * 0.16, EC + RIGHT * 0.16, stroke_color=TEXT, stroke_width=2.4),
                        Line(EC + UP * 0.16, EC + DOWN * 0.16, stroke_color=TEXT, stroke_width=2.4))
        clbl = Text("EARTH'S CENTRE", font=MONO, font_size=22, color=MUTED).set_opacity(0.75)
        clbl.move_to([EC[0], EC[1] - 0.42, 0])
        self.play(FadeIn(earth), run_time=0.7)
        self.play(FadeIn(centre), FadeIn(clbl), run_time=0.5)
        self.say("Earth's field is very close to a bar magnet. Two things about it are not obvious.", hold=1.9)

        tilt = VGroup(
            Text("1 · It is tilted 9.1° from the spin axis.", font=SANS, font_size=34, color=MUTED),
            Text("2 · It is not at the centre.", font=SANS_SB, font_size=36, color=AMBER),
        ).arrange(DOWN, buff=0.18, aligned_edge=LEFT)
        if tilt.width > 5.6:
            tilt.scale(5.6 / tilt.width)
        tilt.move_to([3.85, 2.20, 0])
        self.play(FadeIn(tilt[0]), run_time=0.7)
        self.wait(1.0)
        self.play(FadeIn(tilt[1]), run_time=0.7)
        self.say("The second one is the whole story here.", hold=1.4)

        # ---- move the dipole off centre
        DC = EC + LEFT * OFF
        dip = VGroup(Line(DC + LEFT * 0.16, DC + RIGHT * 0.16, stroke_color=AMBER, stroke_width=3.0),
                     Line(DC + UP * 0.16, DC + DOWN * 0.16, stroke_color=AMBER, stroke_width=3.0))
        offarrow = Arrow(EC, DC, color=AMBER, buff=0, stroke_width=5,
                         max_tip_length_to_length_ratio=0.6)
        dim = VGroup(
            Line([EC[0], EC[1] + 0.30, 0], [EC[0], EC[1] + R + 0.55, 0],
                 stroke_color=AMBER, stroke_width=1.4).set_opacity(0.6),
            Line([DC[0], DC[1] + 0.30, 0], [DC[0], DC[1] + R + 0.55, 0],
                 stroke_color=AMBER, stroke_width=1.4).set_opacity(0.6),
            Line([DC[0], EC[1] + R + 0.42, 0], [EC[0], EC[1] + R + 0.42, 0],
                 stroke_color=AMBER, stroke_width=3.0),
        )
        dimlbl = VGroup(Text("610 km", font=MONO_SB, font_size=30, color=AMBER),
                        Text("toward 22.7°N 134.7°E", font=MONO, font_size=23, color=MUTED)
                        ).arrange(DOWN, buff=0.09)
        dimlbl.move_to([EC[0] - 2.30, EC[1] + R + 0.70, 0])
        dimlead = Line([dimlbl.get_right()[0] + 0.16, dimlbl.get_center()[1], 0],
                       [(EC[0] + DC[0]) / 2, EC[1] + R + 0.48, 0],
                       stroke_color=AMBER, stroke_width=1.4).set_opacity(0.55)
        dimlbl.add(dimlead)
        offlbl = dimlbl
        self.play(GrowArrow(offarrow), FadeIn(dip), Create(dim), FadeIn(dimlbl), run_time=1.2)
        self.say("The best-fit dipole sits 610 kilometres from Earth's centre.", hold=1.8)
        self.say("A tenth of an Earth radius. Small enough that you can barely see it here.", hold=2.0)

        # ---- one surface of equal field strength
        surf = Circle(radius=RB, stroke_color=CORAL, stroke_width=3.4).move_to(DC)
        slbl = Text("ONE SURFACE OF EQUAL FIELD STRENGTH", font=MONO_SB, font_size=24, color=CORAL)
        # HOME is centred over the surface it names. But the 610 km dimension
        # callout is still on screen on the same row for the next seven
        # seconds, and centred here the two ran into each other: the frame read
        # "610 kmONE SURFACE OF EQUAL FIELD STRENGTH". So the label starts
        # clear of the callout and walks home the moment the callout leaves --
        # inside a fade that was already being played, so it costs nothing.
        SLBL_HOME = np.array([-0.10, EC[1] + RB + 0.50, 0.0])
        slbl.move_to(SLBL_HOME)
        clear_of(slbl, dimlbl, direction=RIGHT, gap=0.30)
        self.play(Create(surf), FadeIn(slbl), run_time=1.4)
        self.say("Field strength falls off with distance from the dipole — not from the Earth.", hold=2.1)
        self.say("So a surface of equal field strength rides off centre with the dipole.", hold=2.1)
        # NOT "is a sphere around the dipole": a dipole's field at a fixed distance is
        # twice as strong over the poles as over the equator, so its true equal-field
        # surfaces are not spheres. The circle here is the schematic; the OFFSET is the
        # claim, and it is the offset that puts the anomaly over Brazil.

        # ---- the two altitudes, measured on the drawing
        def gap(x_surf, x_limb, color, text, side):
            bar = Line([x_surf, EC[1], 0], [x_limb, EC[1], 0], stroke_color=color, stroke_width=4)
            t1 = Line([x_surf, EC[1] - 0.13, 0], [x_surf, EC[1] + 0.13, 0],
                      stroke_color=color, stroke_width=3)
            t2 = Line([x_limb, EC[1] - 0.13, 0], [x_limb, EC[1] + 0.13, 0],
                      stroke_color=color, stroke_width=3)
            lab = Text(text, font=MONO_SB, font_size=30, color=color)
            lab.move_to([x_surf + side * 0.92, EC[1] + 0.42, 0])
            lead = Line([lab.get_center()[0], lab.get_center()[1] - 0.22, 0],
                        [(x_surf + x_limb) / 2, EC[1] + 0.16, 0],
                        stroke_color=color, stroke_width=1.6).set_opacity(0.6)
            return VGroup(bar, t1, t2, lab, lead)

        hi = gap(DC[0] - RB, EC[0] - R, CYAN_BRIGHT, "1 520 km", -1)
        lo = gap(DC[0] + RB, EC[0] + R, MINT, "300 km", +1)
        self.play(FadeOut(VGroup(offlbl, offarrow, tilt, dimlbl, dim)),
                  slbl.animate.move_to(SLBL_HOME), run_time=0.5)
        self.play(FadeIn(hi), run_time=0.9)
        self.play(FadeIn(lo), run_time=0.9)
        self.say("On one side that surface is fifteen hundred kilometres up. On the other, three hundred.", hold=2.3)

        diff = VGroup(
            Text("1 220 km apart", font=SANS_SB, font_size=38, color=AMBER),
            Text("exactly twice the offset", font=SANS, font_size=32, color=MUTED),
        ).arrange(DOWN, buff=0.12)
        diff.move_to([4.35, -1.70, 0])
        self.play(FadeIn(diff), run_time=0.7)
        self.say("The gap between them is twice the offset. That is the whole anomaly.", hold=2.2)

        # ---- what a satellite actually meets
        th = np.arccos((RB ** 2 - ORB ** 2 - OFF ** 2) / (2 * ORB * OFF))
        def orb_pt(a):
            return EC + ORB * np.array([np.cos(a), np.sin(a), 0.0])
        safe = DashedVMobject(
            VMobject(stroke_color=VIOLET, stroke_width=2.8).set_points_smoothly(
                [orb_pt(a) for a in np.linspace(th, 2 * PI - th, 90)]),
            num_dashes=52).set_stroke(opacity=0.7)
        hot = VMobject(stroke_color=AMBER, stroke_width=7)
        hot.set_points_smoothly([orb_pt(a) for a in np.linspace(-th, th, 50)])
        olbl = Text("SATELLITE AT 500 km", font=MONO_SB, font_size=24, color=VIOLET)
        olbl.move_to([EC[0], EC[1] - ORB - 0.40, 0])
        self.play(FadeOut(diff), Create(safe), FadeIn(olbl), run_time=1.3)
        self.say("Now fly something at five hundred kilometres.", hold=1.3)

        ang = ValueTracker(PI)
        sat = always_redraw(lambda: Dot(orb_pt(ang.get_value()), radius=0.105, color=TEXT))
        self.add(sat)
        self.play(ang.animate.set_value(PI - 1.6), run_time=1.9, rate_func=linear)
        self.play(ang.animate.set_value(th), run_time=2.2, rate_func=linear)
        self.play(Create(hot), ang.animate.set_value(-th), run_time=2.4, rate_func=linear)
        hotlbl = Text("INSIDE THE BELT", font=MONO_SB, font_size=30, color=AMBER)
        hotlbl.move_to([4.35, -1.70, 0])
        self.play(FadeIn(hotlbl), run_time=0.5)
        self.play(ang.animate.set_value(-PI), run_time=2.0, rate_func=linear)
        self.remove(sat)
        self.say("For most of the orbit it flies under that surface. Over one region it is above it.",
                 hold=2.3)   # ABOVE, not "inside": below and inside are the same thing here,
                             # and the amber arc drawn at this beat is OUTSIDE the coral circle

        # ---- name the place
        mark = Dot(EC + (R + 0.05) * RIGHT, radius=0.10, color=CORAL)
        mlbl = VGroup(
            Text("22.7°S  45.3°W", font=MONO_SB, font_size=30, color=CORAL),
            Text("South Atlantic, off Brazil", font=SANS, font_size=32, color=TEXT),
            Text("the antipode of the offset", font=SANS, font_size=28, color=MUTED),
        ).arrange(DOWN, buff=0.11)
        if mlbl.width > 5.30:
            mlbl.scale(5.30 / mlbl.width)
        mlbl.move_to([4.30, 1.05, 0])
        self.play(FadeOut(hotlbl), FadeIn(mark), FadeIn(mlbl), run_time=0.9)
        self.say("That region is the antipode of the offset — and it is over Brazil.", hold=2.3)

        src = Text("IGRF-13 through Fraser-Smith (1987), evaluated for 2026.6 — the site's own arithmetic.",
                   font=SANS, font_size=27, color=MUTED)
        if src.width > 12.6:
            src.scale(12.6 / src.width)
        src.move_to([0, -2.26, 0])
        self.play(FadeIn(src), run_time=0.8)
        self.wait(2.4)
        self.play(FadeOut(VGroup(earth, centre, clbl, dip, surf, slbl, safe, hot, olbl,
                                 lo, hi, mark, mlbl, src, chrome)), run_time=0.7)
        self.clear_caption()
