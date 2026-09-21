"""
MECHANISM 02 - Chapman layer formation.

Why the ionosphere has a peak at all. The production curve is the Chapman
production function (Chapman 1931),

    q(z) / q_max = exp( 1 - Z - sec(chi) * exp(-Z) ),   Z = (z - z_m) / H

evaluated live rather than traced by hand. The scale height and reference
altitude are illustrative round numbers and the frame says so; the SHAPE, and
the way the peak climbs and weakens as the Sun goes down, are the real
behaviour of that function - which is the whole point of the piece.

Note on axes: altitude is the VERTICAL axis and the plotted quantity is
horizontal, so every curve is built by mapping (amount, altitude) through
Axes.c2p by hand. Axes.plot() would draw y = f(x), which is the other way up.
"""

import numpy as np
from manim import *
from theme import *
from parts import *

H_KM = 28.0
ZM_KM = 105.0
Z0, Z1 = 60.0, 360.0
ZS = list(np.linspace(Z0, Z1, 90))


def zz(z):
    return (z - ZM_KM) / H_KM


def flux(z, chi_deg=0.0):
    return float(np.exp(-(1.0 / np.cos(np.deg2rad(chi_deg))) * np.exp(-zz(z))))


def density(z):
    return float(min(1.06, np.exp(-zz(z))))


def production(z, chi_deg=0.0):
    return float(np.exp(1.0 - zz(z) - (1.0 / np.cos(np.deg2rad(chi_deg))) * np.exp(-zz(z))))


def vcurve(ax, f, color, width=4.6, zs=ZS, opacity=1.0):
    """A curve of amount-versus-altitude: altitude runs up the y axis."""
    v = VMobject(stroke_color=color, stroke_width=width, stroke_opacity=opacity)
    v.set_points_smoothly([ax.c2p(f(z), z) for z in zs])
    return v


class Chapman(MechanismScene):
    TITLE = "Why the ionosphere has a peak"
    KICKER = "Mechanism 02 · Chapman layer"
    SUB = "One balance explains D, E and F1 — and the whole day/night behaviour."
    TAKEAWAY = "Light without air makes nothing. Air without light makes nothing. The layer is where both are enough."
    MARK = "SCHEMATIC · CHAPMAN 1931"

    def make_axes(self, cx, xmax=1.10):
        return Axes(x_range=[0, xmax, 0.5], y_range=[Z0, Z1, 100],
                    x_length=4.3, y_length=4.35,
                    axis_config={"stroke_color": LINE_STRONG, "stroke_width": 2},
                    tips=False).move_to([cx, 0.60, 0])

    def alt_ticks(self, ax, top=Z1):
        g = VGroup()
        for km in (100, 200, 300):
            p = ax.c2p(0, km)
            g.add(Text(f"{km}", font=MONO, font_size=23, color=MUTED)
                  .move_to([p[0] - 0.44, p[1], 0]),
                  Line([p[0] - 0.08, p[1], 0], [p[0] + 0.08, p[1], 0],
                       stroke_color=LINE_STRONG, stroke_width=2))
        g.add(Text("km", font=MONO, font_size=21, color=MUTED)
              .move_to([ax.c2p(0, top)[0] - 0.44, ax.c2p(0, top)[1] + 0.22, 0]))
        return g

    def body(self):
        chrome = self.frame_chrome()
        left = self.make_axes(-3.75)
        right = self.make_axes(3.05)
        lt = self.alt_ticks(left)
        lhead = Text("ALTITUDE", font=MONO_SB, font_size=23, color=MUTED)
        lhead.rotate(PI / 2).move_to([left.c2p(0, Z0)[0] - 1.02, 0.60, 0])
        self.play(Create(left), FadeIn(lt), FadeIn(lhead), run_time=0.8)
        self.say("One column of upper atmosphere. Ground below, space above.", hold=1.3)

        rays = VGroup(*[
            flow([[-5.55 + 0.60 * i, 3.16], [-5.55 + 0.60 * i, 2.62]], AMBER, 2.4,
                 arrows=(0.82,), smooth=False, size=0.10, opacity=0.5)
            for i in range(7)])
        self.play(LaggedStart(*[FadeIn(m) for m in rays], lag_ratio=0.06), run_time=0.5)

        def legend_row(color, text, y):
            sw = Line([-0.26, 0, 0], [0.26, 0, 0], stroke_color=color, stroke_width=5)
            tx = Text(text, font=SANS_SB, font_size=32, color=color)
            g = VGroup(sw, tx).arrange(RIGHT, buff=0.24)
            g.move_to([-3.75, y, 0])
            return g

        fcurve = vcurve(left, flux, AMBER)
        flbl = legend_row(AMBER, "ionising light", -1.82)
        self.play(Create(fcurve), FadeIn(flbl), run_time=1.3)
        self.say("Light is strongest at the top, and is used up on the way down.", hold=1.6)

        dcurve = vcurve(left, density, VIOLET)
        dlbl = legend_row(VIOLET, "air density", -2.19)
        self.play(Create(dcurve), FadeIn(dlbl), run_time=1.3)
        self.say("Air does the opposite. It thickens downward, nearly tripling every scale height.",
                 hold=1.8)   # e, not 2: the curve drawn beside this is exp(-(z-z_m)/H)

        rt = self.alt_ticks(right)
        self.play(Create(right), FadeIn(rt), run_time=0.7)
        rhead = Text("IONS MADE PER SECOND", font=MONO_SB, font_size=23, color=MINT)
        rhead.move_to([3.05, 3.08, 0])
        self.play(FadeIn(rhead), run_time=0.4)
        self.say("Multiply the two, one altitude at a time.", hold=1.1)

        scan = ValueTracker(Z1)
        parts = VGroup(
            always_redraw(lambda: Line(left.c2p(0, scan.get_value()), left.c2p(1.10, scan.get_value()),
                                       stroke_color=CYAN_BRIGHT, stroke_width=1.6).set_opacity(0.5)),
            always_redraw(lambda: Line(right.c2p(0, scan.get_value()), right.c2p(1.10, scan.get_value()),
                                       stroke_color=CYAN_BRIGHT, stroke_width=1.6).set_opacity(0.5)),
            always_redraw(lambda: Dot(left.c2p(flux(scan.get_value()), scan.get_value()),
                                      radius=0.075, color=AMBER)),
            always_redraw(lambda: Dot(left.c2p(density(scan.get_value()), scan.get_value()),
                                      radius=0.075, color=VIOLET)),
            always_redraw(lambda: Dot(right.c2p(production(scan.get_value()), scan.get_value()),
                                      radius=0.085, color=MINT)),
        )
        pcurve = vcurve(right, production, MINT, 5.2)
        self.add(parts)
        self.play(scan.animate.set_value(Z0), Create(pcurve), run_time=4.2, rate_func=linear)
        self.remove(parts)
        self.say("At the top: light, but no air. At the bottom: air, but no light.", hold=1.9)

        pk = right.c2p(1.0, ZM_KM)
        peak = Dot(pk, radius=0.095, color=CYAN_BRIGHT)
        plbl = Text("THE PEAK", font=MONO_SB, font_size=26, color=CYAN_BRIGHT)
        plbl.move_to([pk[0] - 1.80, pk[1], 0])
        plead = Line([pk[0] - 1.16, pk[1], 0], [pk[0] - 0.16, pk[1], 0],
                     stroke_color=CYAN_BRIGHT, stroke_width=1.6).set_opacity(0.7)
        self.play(FadeIn(peak), FadeIn(plbl), FadeIn(plead), run_time=0.6)
        self.say("The peak is the compromise. That is a Chapman layer.", hold=7.88)  # widened for narration
        self.play(FadeOut(VGroup(peak, plbl, plead, rays)), run_time=0.5)

        # ---- the Sun goes down
        chi = ValueTracker(0.0)
        fdyn = always_redraw(lambda: vcurve(left, lambda z: flux(z, chi.get_value()), AMBER))
        pdyn = always_redraw(lambda: vcurve(right, lambda z: production(z, chi.get_value()), MINT, 5.2))
        readout = always_redraw(lambda: Text(
            f"SUN {chi.get_value():.0f}° FROM OVERHEAD", font=MONO_SB, font_size=25, color=AMBER)
            .move_to([-3.75, 3.08, 0]))

        def peak_km():
            return ZM_KM + H_KM * np.log(1.0 / np.cos(np.deg2rad(chi.get_value())))

        peakmark = VGroup(
            always_redraw(lambda: Dot(right.c2p(production(peak_km(), chi.get_value()), peak_km()),
                                      radius=0.085, color=CYAN_BRIGHT)),
            always_redraw(lambda: DashedLine(
                right.c2p(0, peak_km()),
                right.c2p(production(peak_km(), chi.get_value()), peak_km()),
                stroke_color=CYAN_BRIGHT, stroke_width=1.8, dash_length=0.1).set_opacity(0.55)),
            always_redraw(lambda: Text(f"PEAK {peak_km():.0f} km", font=MONO_SB, font_size=25,
                                       color=CYAN_BRIGHT)
                          .move_to([right.c2p(0, peak_km())[0] - 1.02,
                                    right.c2p(0, peak_km())[1] + 0.30, 0])),
        )
        self.remove(fcurve, pcurve)
        self.add(fdyn, pdyn, readout, peakmark)
        self.say("Now let the Sun go down.", hold=0.9)
        self.play(chi.animate.set_value(80.0), run_time=4.4, rate_func=smooth)
        self.say("The peak climbs and it weakens. A low Sun gives a higher, thinner layer.", hold=2.1)
        self.play(chi.animate.set_value(0.0), run_time=1.5)

        self.play(FadeOut(VGroup(left, right, lt, rt, lhead, rhead, fdyn, pdyn, readout,
                                 peakmark, dcurve, flbl, dlbl, chrome)), run_time=0.7)
        self.clear_caption()
        self.layers()

    # ------------------------------------------------------------------
    def layers(self):
        """The payoff: the same balance four times over, and the one exception."""
        chrome = self.frame_chrome()
        ax = Axes(x_range=[0, 1.18, 0.5], y_range=[60, 420, 100],
                  x_length=5.5, y_length=4.5,
                  axis_config={"stroke_color": LINE_STRONG, "stroke_width": 2},
                  tips=False).move_to([2.30, 0.52, 0])
        ylab = Text("ALTITUDE", font=MONO_SB, font_size=23, color=MUTED)
        ylab.rotate(PI / 2).move_to([ax.c2p(0, 60)[0] - 1.10, 0.52, 0])
        xlab = Text("ELECTRON DENSITY", font=MONO_SB, font_size=23, color=MUTED)
        xlab.move_to([2.30, ax.c2p(0, 60)[1] - 0.42, 0])
        ticks = VGroup()
        for km in (100, 200, 300, 400):
            p = ax.c2p(0, km)
            ticks.add(Text(f"{km}", font=MONO, font_size=22, color=MUTED)
                      .move_to([p[0] - 0.46, p[1], 0]))
        ticks.add(Text("km", font=MONO, font_size=20, color=MUTED)
                  .move_to([ax.c2p(0, 420)[0] - 0.46, ax.c2p(0, 420)[1] + 0.22, 0]))
        self.play(Create(ax), FadeIn(ylab), FadeIn(xlab), FadeIn(ticks), run_time=0.9)

        zs = list(np.linspace(60, 420, 130))

        def bump(z, zc, w, a):
            return a * np.exp(-((z - zc) / w) ** 2)

        def day(z):
            return (bump(z, 78, 13, 0.10) + bump(z, 108, 15, 0.32)
                    + bump(z, 182, 28, 0.45) + bump(z, 300, 80, 1.0))

        def night(z):
            return bump(z, 110, 13, 0.05) + bump(z, 312, 90, 0.42)

        dcur = vcurve(ax, day, CYAN_BRIGHT, 5.0, zs)
        self.play(Create(dcur), run_time=1.6)
        self.say("This is the shape a real daytime profile carries.", hold=1.3)

        marks = VGroup()
        for nm, z, col in (("D", 78, VIOLET), ("E", 108, MINT), ("F1", 182, AMBER), ("F2", 300, CORAL)):
            p = ax.c2p(day(z), z)
            marks.add(VGroup(Dot([p[0], p[1], 0], radius=0.07, color=col),
                             Text(nm, font=MONO_SB, font_size=34, color=col)
                             .move_to([p[0] + 0.50, p[1], 0])))
        self.play(LaggedStart(*[FadeIn(m) for m in marks], lag_ratio=0.2), run_time=1.3)
        self.say("D, E and F1 are the same balance — different wavelengths, different gases.", hold=2.2)

        # Night is dashed so the two profiles never have to be told apart by a
        # label sitting on top of a curve.
        ncur = DashedVMobject(vcurve(ax, night, CYAN_BRIGHT, 4.2, zs), num_dashes=64,
                              dashed_ratio=0.55).set_stroke(opacity=0.75)
        dlbl2 = VGroup(Line([-0.28, 0, 0], [0.28, 0, 0], stroke_color=CYAN_BRIGHT, stroke_width=5),
                       Text("DAY", font=MONO_SB, font_size=26, color=CYAN_BRIGHT)
                       ).arrange(RIGHT, buff=0.18)
        nlbl = VGroup(DashedLine([-0.28, 0, 0], [0.28, 0, 0], stroke_color=CYAN_BRIGHT,
                                 stroke_width=5, dash_length=0.09).set_opacity(0.75),
                      Text("NIGHT", font=MONO_SB, font_size=26, color=MUTED)
                      ).arrange(RIGHT, buff=0.18)
        leg = VGroup(dlbl2, nlbl).arrange(RIGHT, buff=0.70).move_to([3.15, 3.05, 0])
        self.play(FadeIn(dlbl2), run_time=0.4)
        self.play(Create(ncur), FadeIn(nlbl), run_time=1.6)
        self.say("At sunset production stops. D and E collapse in minutes: dense air, fast recombination.", hold=2.3)
        self.say("That is why the shortwave bands go long after dark.", hold=1.9)

        cav = VGroup(
            Text("F2 is the exception", font=SANS_SB, font_size=FS_LABEL, color=CORAL),
            Text("It sits above the peak of", font=SANS, font_size=30, color=MUTED),
            Text("production. Transport and", font=SANS, font_size=30, color=MUTED),
            Text("slow loss shape it, not", font=SANS, font_size=30, color=MUTED),
            Text("Chapman's balance.", font=SANS, font_size=30, color=MUTED),
        ).arrange(DOWN, buff=0.10, aligned_edge=LEFT)
        if cav.width > 4.55:
            cav.scale(4.55 / cav.width)
        cav.move_to([-6.85 + cav.width / 2, 1.05, 0])
        self.play(FadeIn(cav), Indicate(marks[3], color=CORAL, scale_factor=1.2), run_time=1.1)
        self.wait(2.6)
        self.play(FadeOut(VGroup(ax, ylab, xlab, ticks, dcur, ncur, marks, nlbl, dlbl2, cav, chrome)),
                  run_time=0.7)
        self.clear_caption()
