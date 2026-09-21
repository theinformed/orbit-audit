"""
MECHANISM 03 - HF skip, the MUF, and the blackout.

The most operationally loaded piece on the list. Layer heights are drawn to
scale against each other (D 80 km, E 110 km, F2 300 km on one vertical scale);
the ray paths are schematic. The 1/f^2 frequency dependence of D-region
absorption is real and is the reason the bottom of the band dies first.
"""

import numpy as np
from manim import *
from theme import *
from parts import *

GY = -2.02          # ground line, low in the frame
# RE is the curvature radius, and it is a CUE rather than a measurement (this
# piece is stamped VERTICAL SCALE EXAGGERATED). At 34 the ground sagged 0.71
# units from centre to edge and its ends finished at y=-2.81 -- below the
# bottom rule, inside the reserved caption band, on 90 of the clip's 137 body
# frames. That was this library's one real caption/diagram collision. At 62 the
# sag is 0.39, the ends finish at -2.41, and the ground still reads as the
# curve of a planet rather than a flat floor.
RE = 62.0           # a gentle curvature so the ground reads as a planet
KM = 0.01250        # screen units per km of altitude
TX, RXX = -5.15, 4.35

D_KM, E_KM, F2_KM = 80.0, 110.0, 300.0


def ground_y(x):
    return GY + (np.sqrt(RE ** 2 - x ** 2) - RE)


def arc(alt_km, color, width=2.4, opacity=0.9, x0=-6.75, x1=6.75, n=70):
    pts = [[x, ground_y(x) + alt_km * KM] for x in np.linspace(x0, x1, n)]
    v = VMobject(stroke_color=color, stroke_width=width, stroke_opacity=opacity)
    v.set_points_smoothly([np.array([p[0], p[1], 0.0]) for p in pts])
    return v


def hop(x0, x1, apex_km, n=48):
    """One ray: up from x0, turned over at apex_km, back down at x1."""
    pts = []
    for i in range(n + 1):
        u = i / n
        x = x0 + u * (x1 - x0)
        h = apex_km * np.sin(np.pi * u) ** 0.72
        pts.append([x, ground_y(x) + h * KM])
    return pts


def escape(x0, apex_km, n=40):
    """A ray that is not turned back: it bends, then leaves."""
    pts = []
    for i in range(n + 1):
        u = i / n
        x = x0 + u * 11.9
        h = apex_km * (u ** 0.62) * (1.0 + 0.36 * u ** 3)
        pts.append([x, ground_y(x) + h * KM])
    return pts


class HF(MechanismScene):
    TITLE = "The skip, the MUF, and the blackout"
    KICKER = "Mechanism 03 · HF propagation"
    SUB = "Why the far station is loud, the near one is silent, and a flare kills the low end first."
    TAKEAWAY = "A radio blackout is not the band going quiet. It is the usable window closing from the bottom."
    MARK = "SCHEMATIC · VERTICAL SCALE EXAGGERATED"

    def stage(self):
        gnd = VMobject(stroke_color=LINE_STRONG, stroke_width=3.2)
        gnd.set_points_smoothly([np.array([x, ground_y(x), 0.0]) for x in np.linspace(-6.9, 6.9, 60)])
        d = arc(D_KM, VIOLET, 2.4, 0.55)
        e = arc(E_KM, MINT, 2.2, 0.45)
        f2 = arc(F2_KM, CYAN, 2.8, 0.85)
        lbls = VGroup(
            Text("F2", font=MONO_SB, font_size=30, color=CYAN)
            .move_to([-6.25, ground_y(-6.25) + F2_KM * KM + 0.26, 0]),
            Text("E", font=MONO_SB, font_size=26, color=MINT)
            .move_to([-6.25, ground_y(-6.25) + E_KM * KM + 0.22, 0]),
            Text("D", font=MONO_SB, font_size=26, color=VIOLET)
            .move_to([-6.25, ground_y(-6.25) + D_KM * KM - 0.24, 0]),
        )
        tx = VGroup(Line([TX, ground_y(TX), 0], [TX, ground_y(TX) + 0.34, 0],
                         stroke_color=AMBER, stroke_width=4),
                    Text("TX", font=MONO_SB, font_size=26, color=AMBER)
                    .move_to([TX - 0.45, ground_y(TX) + 0.20, 0]))
        rx = VGroup(Line([RXX, ground_y(RXX), 0], [RXX, ground_y(RXX) + 0.34, 0],
                         stroke_color=AMBER, stroke_width=4),
                    Text("RX", font=MONO_SB, font_size=26, color=AMBER)
                    .move_to([RXX + 0.45, ground_y(RXX) + 0.20, 0]))
        return gnd, VGroup(d, e, f2), lbls, tx, rx, d, f2

    def body(self):
        chrome = self.frame_chrome()
        gnd, layers, lbls, tx, rx, dlayer, f2layer = self.stage()
        self.play(Create(gnd), run_time=0.7)
        self.play(LaggedStart(*[Create(m) for m in layers], lag_ratio=0.15),
                  FadeIn(lbls), run_time=1.4)
        self.play(FadeIn(tx), FadeIn(rx), run_time=0.5)
        self.say("Three ionised layers over one transmitter. The heights are to scale with each other.", hold=1.9)

        # ---- ground wave
        gw = flow([[TX, ground_y(TX) + 0.05], [TX + 0.9, ground_y(TX + 0.9) + 0.10],
                   [TX + 1.7, ground_y(TX + 1.7) + 0.06]], AMBER, 3.0, arrows=(0.7,), size=0.10)
        gw.set_stroke(opacity=0.8)
        self.play(Create(gw), run_time=0.8)
        self.say("A little power crawls along the ground and is gone within a couple of hundred miles.", hold=1.8)

        # ---- one hop off F2
        r7 = flow(hop(TX, RXX, F2_KM * 0.92), MINT, 4.0, arrows=(0.28, 0.74), size=0.125)
        f7 = Text("7 MHz", font=MONO_SB, font_size=30, color=MINT)
        f7.move_to([-0.4, ground_y(0) + F2_KM * KM + 0.40, 0])
        self.play(Create(r7), FadeIn(f7), run_time=1.6)
        self.say("The rest goes up, is bent back by the F2 layer, and lands a long way off. One hop.", hold=2.0)

        # ---- the skip zone
        zone = VGroup()
        for x in np.linspace(TX + 1.75, RXX - 0.15, 16):
            zone.add(Line([x, ground_y(x) - 0.02, 0], [x, ground_y(x) - 0.24, 0],
                          stroke_color=CORAL, stroke_width=2.4).set_opacity(0.55))
        zlbl = Text("SKIP ZONE — NOTHING HEARD", font=MONO_SB, font_size=27, color=CORAL)
        zlbl.move_to([-0.35, ground_y(0) + 0.34, 0])
        self.play(LaggedStart(*[Create(m) for m in zone], lag_ratio=0.04), FadeIn(zlbl), run_time=1.2)
        self.say("Between the two there is nothing at all.", hold=1.4)
        self.say("The station five hundred miles away can be unreachable; the one two thousand miles away is loud.",
                 hold=2.3)   # NOT "a hundred": the ground wave two captions back reaches further than that
        self.play(FadeOut(VGroup(zone, zlbl, gw)), run_time=0.5)

        # ---- raise the frequency until it punches through
        r14 = flow(hop(TX, RXX + 1.7, F2_KM * 0.99), MINT, 4.0, arrows=(0.28, 0.74), size=0.125)
        f14 = Text("14 MHz", font=MONO_SB, font_size=30, color=MINT)
        f14.move_to([0.1, ground_y(0) + F2_KM * KM + 0.40, 0])
        self.play(ReplacementTransform(r7, r14), ReplacementTransform(f7, f14), run_time=1.3)
        self.say("Raise the frequency and the ray goes deeper before it turns, and lands further away.", hold=2.0)

        resc = flow(escape(TX, F2_KM * 1.02), CORAL, 4.0, arrows=(0.55, 0.9), size=0.125)

        # The MUF callout is BUILT HERE, a beat before it is played, because
        # "28 MHz" has to be told what it must not touch. Parked at a fixed x
        # near the apex it printed straight through the word MUF -- the frame
        # read "MU28 MHz" for three and a half seconds. Construction is free;
        # only self.play costs time, so nothing about the timing moves.
        muf = Text("MUF", font=MONO_SB, font_size=34, color=AMBER)
        mufs = Text("the highest frequency that still comes back on this path",
                    font=SANS, font_size=30, color=MUTED)
        mg = VGroup(muf, mufs).arrange(DOWN, buff=0.12)
        mg.move_to([0.0, ground_y(0) + F2_KM * KM + 0.95, 0])

        fesc = Text("28 MHz", font=MONO_SB, font_size=30, color=CORAL)
        # The label belongs to the ray, so it rides the ray out of the frame
        # rather than sitting where the callout is about to land.
        fesc.move_to(resc.get_top() + np.array([-0.55, 0.34, 0]))
        clear_of(fesc, mg, direction=UR, gap=0.26)
        self.play(ReplacementTransform(r14, resc), ReplacementTransform(f14, fesc), run_time=1.3)
        self.say("Push it too far and the layer cannot turn it back at all. The signal leaves.", hold=1.9)

        self.play(FadeIn(mg), run_time=0.7)
        self.wait(1.9)
        self.play(FadeOut(VGroup(mg, resc, fesc)), run_time=0.6)

        # ---- the flare
        xray = VGroup(*[
            flow([[-6.6 + 1.05 * i, 3.20], [-6.6 + 1.05 * i, ground_y(-6.6 + 1.05 * i) + D_KM * KM + 0.10]],
                 AMBER, 2.4, arrows=(0.85,), smooth=False, size=0.11, opacity=0.75)
            for i in range(12)])
        self.say("Now a flare goes off on the Sun.", hold=0.9)
        self.play(LaggedStart(*[Create(m) for m in xray], lag_ratio=0.04), run_time=1.2)
        self.say("Its X-rays cross in eight minutes and stop in the D region — the lowest layer.", hold=2.0)
        thick = arc(D_KM, VIOLET, 12.0, 0.42)
        self.play(FadeIn(thick), dlayer.animate.set_stroke(width=4.5, opacity=1.0), run_time=0.9)
        self.play(FadeOut(xray), run_time=0.4)
        self.say("D stops being a mirror and starts being a sponge.", hold=3.46)  # widened for narration

        # ---- 1/f^2 : the bottom of the band dies first
        rays = []
        for fq, frac, col, alive in ((4, 0.80, CORAL, False), (7, 0.92, AMBER, False), (14, 0.99, MINT, True)):
            rays.append((fq, flow(hop(TX, RXX + (frac - 0.92) * 18, F2_KM * frac), col, 3.6,
                                  arrows=(0.30, 0.74), size=0.115), col, alive))
        legend = VGroup()
        for i, (fq, r, col, alive) in enumerate(rays):
            legend.add(Text(f"{fq} MHz", font=MONO_SB, font_size=28, color=col))
        legend.arrange(DOWN, buff=0.18).move_to([5.95, 2.45, 0])
        self.play(*[Create(r) for _, r, _, _ in rays], FadeIn(legend), run_time=1.3)

        # The stub has to reach the D layer. At 0.85 of D's height it stopped
        # SHORT of the purple arc, so the frame showed 4 MHz never getting INTO
        # the D region under a caption that says it never gets OUT of it.
        stub4 = flow([[TX, ground_y(TX)], [TX + 0.85, ground_y(TX + 0.85) + D_KM * KM]],
                     CORAL, 3.6, arrows=(), smooth=False)
        stub7 = flow(hop(TX, RXX, F2_KM * 0.92), AMBER, 3.6, arrows=(0.30, 0.74), size=0.115)
        stub7.set_stroke(opacity=0.32)
        self.play(ReplacementTransform(rays[0][1], stub4),
                  ReplacementTransform(rays[1][1], stub7), run_time=1.2)
        self.say("Absorption goes as one over frequency squared. Four megahertz never gets out of the D region.", hold=2.3)
        self.say("Seven is badly weakened. Fourteen is still working.", hold=1.7)

        self.play(FadeOut(VGroup(gnd, layers, lbls, tx, rx, thick, stub4, stub7,
                                 rays[2][1], legend, chrome)), run_time=0.7)
        self.clear_caption()
        self.window()

    # ------------------------------------------------------------------
    def window(self):
        """The operational picture: a band with a ceiling and a rising floor."""
        chrome = self.frame_chrome()
        x0, x1 = -4.6, 4.6
        base = -1.55
        top = 2.55
        axis = Line([x0, base, 0], [x1, base, 0], stroke_color=LINE_STRONG, stroke_width=2.4)
        vax = Line([x0, base, 0], [x0, top + 0.25, 0], stroke_color=LINE_STRONG, stroke_width=2.4)
        ylab = Text("FREQUENCY", font=MONO_SB, font_size=24, color=MUTED)
        ylab.rotate(PI / 2).move_to([x0 - 0.62, (base + top) / 2, 0])
        xlab = Text("TIME THROUGH THE FLARE", font=MONO_SB, font_size=24, color=MUTED)
        xlab.move_to([0, base - 0.42, 0])
        self.play(Create(axis), Create(vax), FadeIn(ylab), FadeIn(xlab), run_time=0.8)

        muf_y = 1.95
        mufline = Line([x0, muf_y, 0], [x1, muf_y, 0], stroke_color=AMBER, stroke_width=4)
        muflbl = Text("MUF — ceiling", font=MONO_SB, font_size=28, color=AMBER)
        muflbl.move_to([x1 - 1.30, muf_y + 0.32, 0])
        luf0 = -0.55
        lufline = Line([x0, luf0, 0], [x1, luf0, 0], stroke_color=CORAL, stroke_width=4)
        luflbl = Text("LUF — floor", font=MONO_SB, font_size=28, color=CORAL)
        luflbl.move_to([x0 + 1.24, luf0 - 0.34, 0])
        band = Rectangle(width=x1 - x0, height=muf_y - luf0, fill_color=MINT,
                         fill_opacity=0.16, stroke_width=0)
        band.move_to([(x0 + x1) / 2, (muf_y + luf0) / 2, 0])
        bandlbl = Text("USABLE", font=MONO_SB, font_size=30, color=MINT)
        bandlbl.move_to([-2.6, (muf_y + luf0) / 2, 0])
        self.play(Create(mufline), FadeIn(muflbl), run_time=0.7)
        self.play(Create(lufline), FadeIn(luflbl), run_time=0.7)
        self.play(FadeIn(band), FadeIn(bandlbl), run_time=0.6)
        self.say("Every HF path has a ceiling and a floor. You work between them.", hold=1.8)

        lt = ValueTracker(luf0)
        dyn_luf = always_redraw(lambda: Line([x0, lt.get_value(), 0], [x1, lt.get_value(), 0],
                                             stroke_color=CORAL, stroke_width=4))
        dyn_band = always_redraw(lambda: Rectangle(
            width=x1 - x0, height=max(0.001, muf_y - lt.get_value()),
            fill_color=(MINT if lt.get_value() < muf_y - 0.4 else CORAL),
            fill_opacity=0.16, stroke_width=0
        ).move_to([(x0 + x1) / 2, (muf_y + lt.get_value()) / 2, 0]))
        self.remove(lufline, band, bandlbl)
        self.add(dyn_band, dyn_luf)
        
        self.say("The flare barely moves the ceiling. It lifts the floor.", hold=3.21)  # widened for narration
        self.play(lt.animate.set_value(1.05), luflbl.animate.move_to([x0 + 1.24, 0.70, 0]),
                  run_time=2.2)
        self.say("The low end goes first, then the middle.", hold=1.5)
        self.play(lt.animate.set_value(muf_y), luflbl.animate.move_to([x0 + 1.24, muf_y - 0.38, 0]),
                  run_time=2.0)
        black = Text("BLACKOUT", font=MONO_SB, font_size=44, color=CORAL)
        black.move_to([0, 0.55, 0])
        self.play(FadeIn(black), run_time=0.6)
        self.say("When the floor reaches the ceiling there is no usable frequency left.", hold=2.2)

        # Wrapped to the PLOT's width, not the frame's. At one line it was
        # 10.0 units wide inside a 9.2-unit plot, so it hung over the left axis
        # and printed through the rotated FREQUENCY label for the last eight
        # seconds of the piece. A footnote about a chart belongs inside the
        # chart; making it fit the chart is the fix, and at two lines it keeps
        # its full size.
        note = self._wrap("The explorer draws this live: D-region HF absorption, NOAA D-RAP.",
                          30, SANS, MUTED, (x1 - x0) - 0.8, buff=0.16)
        note.move_to([0, -0.62, 0])
        clear_of(note, vax, ylab, direction=RIGHT)
        self.play(FadeIn(note), run_time=0.6)
        self.wait(2.0)
        self.play(FadeOut(VGroup(axis, vax, ylab, xlab, mufline, muflbl, luflbl,
                                 dyn_band, dyn_luf, black, note, chrome)), run_time=0.7)
        self.clear_caption()
