"""
MECHANISM 01 - Magnetic reconnection at the dayside magnetopause.

The site asserts this in words in content.ts (dungeyCycleSection): "two magnetic
fields pointing in opposite directions are pressed together until the field
breaks and rejoins across the join". This draws it.

Structure: establishing shot of the whole magnetosphere, a zoom to the nose
where the reconnection itself is shown at a scale you can actually read, then
back out for transport down the tail, tail reconnection, injection, and the
sunward return - the Dungey cycle closed.
"""

import numpy as np
from manim import *
from theme import *
from parts import *

EX, EY, S = -4.25, 0.45, 0.115
RDRAW = 0.20
RIGHT_EDGE = 6.70


def clip_body(pts, ymin=-1.95, ymax=3.05, xmin=-7.05, xmax=6.95):
    return [p for p in pts if ymin <= p[1] <= ymax and xmin <= p[0] <= xmax]


def _mp_branches():
    """Upper half of the boundary as (x, halfwidth) samples, nose to tail."""
    pts = magnetopause(EX, EY, S, tmax=2.24)
    up = [(x, y - EY) for x, y in pts if y >= EY - 1e-9]
    up.sort(key=lambda t: t[0])
    x_end, h_end = up[-1]
    for f in (0.3, 0.62, 1.0):
        up.append((x_end + f * (RIGHT_EDGE - x_end), h_end * (1.0 - 0.06 * f)))
    return up


_MPU = _mp_branches()
_MPX = np.array([t[0] for t in _MPU])
_MPH = np.array([t[1] for t in _MPU])
NOSE_X = float(_MPX[0])


def mp_half(x):
    """Half-width of the magnetopause at screen x. Zero at the nose."""
    return float(np.interp(x, _MPX, _MPH))


def mp_full():
    up = [[x, EY + h] for x, h in _MPU]
    lo = [[x, EY - h] for x, h in reversed(_MPU)]
    return lo + up[1:]


def _xs(x0, n=9):
    return list(np.linspace(x0, RIGHT_EDGE, n))


def lobe(sign, frac, foot_deg, taper=1.0):
    """An open lobe line: foot on the polar cap, then a constant fraction of
    the way from the tail axis to the boundary, so it can never cross it."""
    fx = EX + RDRAW * np.cos(np.deg2rad(foot_deg))
    fy = EY + sign * RDRAW * np.sin(np.deg2rad(foot_deg))
    pts = [[fx, fy], [EX - 0.10, EY + sign * 0.55 * frac * mp_half(EX)]]
    for i, x in enumerate(_xs(EX + 0.45, 8)):
        f = frac * (1.0 - (1.0 - taper) * i / 7.0)
        pts.append([x, EY + sign * f * mp_half(x)])
    return pts


def lobe_flow(sign, frac, foot_deg, color, width, taper=1.0, arrows=(0.55, 0.87), **kw):
    """One lobe line drawn with its arrowheads pointing the way the FIELD does.

    THE ARROWHEADS ARE FIELD DIRECTION, NOT DRAWING ORDER, AND THEY USED TO BE
    BOTH. Earth's field enters the northern polar cap and leaves the southern
    one, so along a NORTHERN lobe line the field runs from far down the tail
    back toward Earth, and along a southern one it runs from Earth out down the
    tail. `lobe()` builds every line foot-first, so both lobes came out with
    tailward heads -- drawn PARALLEL, on the very frame whose caption says "Far
    down the tail, the two stacked lobes are antiparallel too". The picture
    disproved the caption, and the tail X-line that the next four beats depend
    on has no reason to exist unless the two lobes oppose each other.

    Reversing the northern point list turns the heads round; the arrow
    proportions are mirrored with it so each head still sits where it did.
    """
    pts = lobe(sign, frac, foot_deg, taper)
    if sign > 0:
        pts = pts[::-1]
        arrows = tuple(1.0 - a for a in arrows)
    return flow(pts, color, width, arrows=arrows, **kw)


def stretched_closed(frac, tip_x, foot_deg=52):
    """A closed night-side line, stretched down-tail and rounded off at tip_x."""
    n = 18
    north = [[EX + RDRAW * np.cos(np.deg2rad(foot_deg)),
              EY + RDRAW * np.sin(np.deg2rad(foot_deg))]]
    for i in range(1, n + 1):
        u = i / n
        x = EX + 0.12 + u * (tip_x - EX - 0.12)
        h = frac * mp_half(x) * (1.0 - u ** 6) ** 0.5 * min(1.0, 0.18 + u * 5.0)
        north.append([x, EY + h])
    south = [[x, 2 * EY - y] for x, y in reversed(north)]
    # SOUTH FOOT OUT, NORTH FOOT IN. Field lines leave the southern hemisphere
    # and enter the northern one, which is what makes Earth's field point NORTH
    # at the subsolar point -- the fact the zoomed inset in this same clip is
    # built on. Built north-first these lines carried the opposite polarity to
    # the dayside dipole arcs drawn beside them on the same frame.
    return (north + south)[::-1]


class Reconnection(MechanismScene):
    TITLE = "How the wind gets in"
    KICKER = "Mechanism 01 · Dayside magnetopause"
    SUB = "Magnetic reconnection, and why Bz is the number everyone watches."
    TAKEAWAY = "Southward Bz does not make the wind stronger. It decides whether the wind's field can join Earth's."
    MARK = "SCHEMATIC · NOT TO SCALE"

    # ------------------------------------------------------------------ parts
    def magnetosphere(self):
        mp = VMobject(stroke_color=VIOLET, stroke_width=2.6, stroke_opacity=0.85)
        mp.set_points_smoothly([np.array([p[0], p[1], 0.0]) for p in mp_full()])

        bs_pts = clip_body(magnetopause(EX, EY, S, r0=13.6, alpha=0.76, tmax=2.0),
                           ymin=EY - 2.35, ymax=EY + 2.55)
        bs = VMobject(stroke_color=CORAL, stroke_width=2.0, stroke_opacity=0.42)
        bs.set_points_smoothly([np.array([p[0], p[1], 0.0]) for p in bs_pts])
        bs_lbl = Text("BOW SHOCK", font=MONO, font_size=21, color=CORAL).set_opacity(0.6)
        bs_lbl.move_to([-5.62, EY + 2.20, 0])
        mp_lbl = Text("MAGNETOPAUSE", font=MONO, font_size=21, color=VIOLET).set_opacity(0.75)
        mp_lbl.move_to([-2.45, EY + 2.62, 0])

        closed = VGroup()
        for L in (6.5, 10.4):
            closed.add(flow(dipole_arc(L, EX, EY, S, sunward=True), CYAN, 2.4,
                            arrows=(0.5,), size=0.10))
        for frac, tip_x in ((0.24, EX + 2.9), (0.42, EX + 5.6)):
            closed.add(flow(stretched_closed(frac, tip_x), CYAN, 2.4,
                            arrows=(0.22, 0.78), size=0.10))

        lobes = VGroup()
        for sign in (+1, -1):
            lobes.add(lobe_flow(sign, 0.88, 118, taper=0.92, color=CYAN, width=2.2,
                                size=0.10, opacity=0.80))
            lobes.add(lobe_flow(sign, 0.62, 96, taper=0.88, color=CYAN, width=2.2,
                                size=0.10, opacity=0.80))

        e = earth_disc([EX, EY], RDRAW)
        return VGroup(bs, bs_lbl, mp, mp_lbl, closed, lobes, e), mp, closed, lobes, e

    def wind(self, southward=False):
        # THE WIND STOPS AT THE SHOCK. These four are the arriving field carried
        # in the wind, and they used to start at x=-6.62 and slide 1.9 units
        # right -- which finished them at x=-4.72, INSIDE the bow shock (nose
        # -5.81), inside the magnetopause (nose -5.40), and with one of them
        # drawn straight through the Earth. They sat there for eight seconds
        # under the caption that had just said the field is "a bubble the solar
        # wind flows around", and under the clip's whole thesis that the only
        # way in is the door the next beat opens. They now begin further left
        # and drift 0.70, which reads the same and ends short of the shock.
        g = VGroup()
        for i, y in enumerate((EY + 2.05, EY + 0.80, EY - 0.45, EY - 1.70)):
            x = -7.05 + 0.28 * (i % 2)
            d = -1 if southward else +1
            g.add(flow([[x, y - d * 0.58], [x, y + d * 0.58]], AMBER, 2.6,
                       arrows=(0.74,), size=0.115, smooth=False))
        return g

    # ------------------------------------------------------------------ body
    def body(self):
        chrome = self.frame_chrome()
        mag, mp, closed, lobes, earth = self.magnetosphere()

        # ---- beat 1: the picture everyone has seen
        self.play(Create(mp), run_time=0.9)
        self.play(FadeIn(earth), LaggedStart(*[Create(m) for m in closed], lag_ratio=0.12), run_time=1.3)
        self.play(FadeIn(mag[0]), LaggedStart(*[Create(m) for m in lobes], lag_ratio=0.10),
                  FadeIn(mag[-1]), run_time=1.2)
        self.say("Earth's field is a bubble the solar wind flows around.", hold=1.5)

        imf = self.wind()
        self.play(LaggedStart(*[FadeIn(m) for m in imf], lag_ratio=0.08), run_time=0.6)
        self.play(imf.animate.shift(RIGHT * 0.70), run_time=1.6, rate_func=linear)
        self.say("The wind carries the Sun's own field with it. Everything depends on which way that field points.", hold=6.15)  # widened for narration

        # ---- beat 2: zoom to the nose
        nose = Circle(radius=0.52, stroke_color=CYAN_BRIGHT, stroke_width=2.6).move_to([NOSE_X + 0.14, EY, 0])
        self.play(Create(nose), run_time=0.6)
        self.play(nose.animate.set_stroke(width=5.0), rate_func=there_and_back, run_time=0.7)
        self.say("Look at the nose.", hold=1.0)
        self.play(FadeOut(VGroup(mag, imf)), nose.animate.scale(6.5).set_stroke(opacity=0.0), run_time=0.9)
        self.remove(nose)

        self.nose_scene()

        # ---- back out for transport
        self.transport(mag, mp, closed, lobes, earth)
        self.play(FadeOut(VGroup(mag, chrome)), run_time=0.6)
        self.clear_caption()

    # ------------------------------------------------------------------ zoomed nose
    def nose_scene(self):
        BY = 0.55            # vertical centre of the zoomed diagram
        # BOTY is 1.93 rather than 2.10 below BY because the two-line field
        # labels hang 0.52 under it: at 2.10 their descenders reached y=-2.57,
        # which is inside the reserved caption band. The inset cannot move down
        # instead -- MAGNETOPAUSE already sits 0.15 under the top rule -- so the
        # field lines are drawn a little shorter at the bottom and the labels
        # ride up with them. Nothing here is to scale; the length of the drawn
        # segment carries no meaning, and the label clearance does.
        TOPY, BOTY = BY + 2.30, BY - 1.93
        sheet = dashed_v(0, BOTY, TOPY, VIOLET, 2.4)
        sheet_lbl = Text("MAGNETOPAUSE", font=MONO_SB, font_size=24, color=VIOLET)
        sheet_lbl.move_to([0, TOPY + 0.30, 0]).set_opacity(0.9)

        sunward = VGroup(
            Text("SUNWARD", font=MONO_SB, font_size=24, color=AMBER).move_to([-4.9, TOPY + 0.30, 0]),
        )
        earthward = VGroup(
            Text("EARTHWARD", font=MONO_SB, font_size=24, color=CYAN).move_to([4.7, TOPY + 0.30, 0]),
        )

        self.play(Create(sheet), FadeIn(sheet_lbl), FadeIn(sunward), FadeIn(earthward), run_time=0.7)

        def vline(x, up, color, op=1.0, w=3.2):
            a, b = (BOTY, TOPY) if up else (TOPY, BOTY)
            return flow([[x, a], [x, b]], color, w, arrows=(0.30, 0.72), smooth=False, opacity=op)

        # Earth's field: northward on the earthward side.
        exs = [0.95, 1.95, 2.95, 3.95]
        efield = VGroup(*[vline(x, True, CYAN) for x in exs])
        elbl = VGroup(
            Text("Earth's field", font=SANS, font_size=34, color=MUTED),
            Text("NORTH", font=MONO_SB, font_size=FS_LABEL, color=CYAN_BRIGHT),
        ).arrange(DOWN, buff=0.14)
        elbl.move_to([3.45, BOTY - 0.52, 0])
        self.play(LaggedStart(*[Create(m) for m in efield], lag_ratio=0.1), FadeIn(elbl), run_time=0.9)
        self.say("On the earthward side, Earth's field points north.", hold=1.1)

        # Northward IMF first: the case where nothing happens.
        ixs = [-0.95, -1.95, -2.95, -3.95]
        imf_n = VGroup(*[vline(x, True, AMBER) for x in ixs])
        ilbl = VGroup(
            Text("Arriving field", font=SANS, font_size=34, color=MUTED),
            Text("NORTH", font=MONO_SB, font_size=FS_LABEL, color=AMBER),
        ).arrange(DOWN, buff=0.14)
        ilbl.move_to([-3.45, BOTY - 0.52, 0])
        self.play(LaggedStart(*[Create(m) for m in imf_n], lag_ratio=0.1), FadeIn(ilbl), run_time=0.9)
        self.say("Northward Bz: the two fields are parallel.", hold=1.2)
        self.play(imf_n.animate.shift(UP * 0.55), efield.animate.shift(UP * 0.30), run_time=1.1)
        self.play(imf_n.animate.shift(DOWN * 0.55), efield.animate.shift(DOWN * 0.30), run_time=1.1)
        self.say("Parallel fields slide past each other. Nothing opens at the nose.", hold=1.5)

        # Flip to southward.
        imf_s = VGroup(*[vline(x, False, AMBER) for x in ixs])
        ilbl2 = VGroup(
            Text("Arriving field", font=SANS, font_size=34, color=MUTED),
            Text("SOUTH", font=MONO_SB, font_size=FS_LABEL, color=CORAL),
        ).arrange(DOWN, buff=0.14)
        ilbl2.move_to([-3.45, BOTY - 0.52, 0])
        self.say("Now turn it over.", hold=0.5)
        self.play(ReplacementTransform(imf_n, imf_s), ReplacementTransform(ilbl, ilbl2), run_time=1.1)
        self.say("Southward Bz: at the nose the two fields are exactly antiparallel.", hold=1.6)

        # The reconnection itself.
        inner_i, inner_e = imf_s[0], efield[0]
        self.play(inner_i.animate.shift(RIGHT * 0.52), inner_e.animate.shift(LEFT * 0.52), run_time=1.2)
        self.say("Pressed together, the field cannot stay in two pieces.", hold=1.0)

        xp = np.array([0.0, BY, 0.0])
        burst = Dot(xp, radius=0.10, color=CYAN_BRIGHT)
        glow = Circle(radius=0.10, stroke_color=CYAN_BRIGHT, stroke_width=4)
        glow.move_to(xp)
        self.play(FadeIn(burst), run_time=0.2)
        self.play(glow.animate.scale(7.0).set_stroke(opacity=0.0), run_time=0.7)
        self.remove(glow)

        # Two new lines: a V above the X-point and an inverted V below.
        #
        # They are built SHORT, by exactly the distance the slingshot below
        # then flings them, so the outflow ends level with the diagram's own
        # top and bottom instead of past them. Built full length they were
        # shifted 0.85 up into the "MAGNETOPAUSE" panel label AND through the
        # top rule into the kicker -- for six seconds, and invisibly in source,
        # because neither the label nor the rule appears anywhere in this
        # method. Physically the freshly reconnected lines have just detached,
        # so starting shorter than their neighbours and reaching full extent as
        # they straighten is the truer picture as well as the safe one.
        VTOP, VBOT = TOPY - 0.85, BOTY + 0.80
        vtop = flow([[-0.43, VTOP], [-0.30, BY + 0.55], [0.0, BY], [0.30, BY + 0.55], [0.43, VTOP]],
                    MINT, 3.4, arrows=(0.22, 0.80), smooth=False)
        vbot = flow([[0.43, VBOT], [0.30, BY - 0.52], [0.0, BY], [-0.30, BY - 0.52], [-0.43, VBOT]],
                    MINT, 3.4, arrows=(0.22, 0.80), smooth=False)
        self.play(ReplacementTransform(VGroup(inner_i, inner_e), VGroup(vtop, vbot)),
                  FadeOut(burst), run_time=1.1)
        self.say("It breaks, and rejoins across the join. Two lines went in; two different lines came out.", hold=1.9)

        xlbl = Text("X-POINT", font=MONO_SB, font_size=24, color=CYAN_BRIGHT)
        xlbl.move_to([1.05, BY - 0.05, 0])
        self.play(FadeIn(xlbl), run_time=0.4)

        # Slingshot: the kinked lines straighten and fly apart. That is the outflow.
        jet_up = flow([[-0.30, BY + 1.3], [0.30, BY + 1.3]], MINT, 0, arrows=())
        up_arrow = Arrow([0, BY + 1.05, 0], [0, BY + 2.15, 0], color=MINT, buff=0,
                         stroke_width=6, max_tip_length_to_length_ratio=0.28)
        dn_arrow = Arrow([0, BY - 0.95, 0], [0, BY - 2.0, 0], color=MINT, buff=0,
                         stroke_width=6, max_tip_length_to_length_ratio=0.28)
        self.play(vtop.animate.shift(UP * 0.85).set_stroke(opacity=0.45),
                  vbot.animate.shift(DOWN * 0.80).set_stroke(opacity=0.45),
                  GrowArrow(up_arrow), GrowArrow(dn_arrow), run_time=1.2)
        self.say("The bent field straightens and flings the plasma away. That is the energy release.", hold=1.7)

        self.say("Each new line now has one foot on Earth and one end loose in the wind. It is open.", hold=1.9)

        self.play(FadeOut(VGroup(sheet, sheet_lbl, sunward, earthward, efield, imf_s,
                                 elbl, ilbl2, vtop, vbot, xlbl, up_arrow, dn_arrow, jet_up)),
                  run_time=0.7)

    # ------------------------------------------------------------------ transport
    def transport(self, mag, mp, closed, lobes, earth):
        self.play(FadeIn(mag), run_time=0.8)
        self.say("Zoom back out, and follow the open lines.", hold=1.0)

        # open flux swept over the poles
        sweep = VGroup()
        for sign in (+1, -1):
            sweep.add(lobe_flow(sign, 0.88, 118, taper=0.92, arrows=(0.50, 0.86),
                                color=MINT, width=3.4, size=0.115))
        self.play(LaggedStart(*[Create(m) for m in sweep], lag_ratio=0.15), run_time=1.4)
        self.say("The wind drags the open ends back over the poles and stacks them in the tail.", hold=1.8)

        lobe_lbl = Text("TAIL LOBES · FLUX LOADING", font=MONO_SB, font_size=24, color=MINT)
        lobe_lbl.move_to([2.95, EY + 2.62, 0]).set_opacity(0.92)
        self.play(FadeIn(lobe_lbl), run_time=0.7)
        self.say("The tail loads. This is the storing half of the cycle.", hold=5.69)  # widened for narration

        # tail X-line
        xl = np.array([2.55, EY, 0.0])
        sheet = DashedLine([0.35, EY, 0], [RIGHT_EDGE, EY, 0], stroke_color=VIOLET,
                           stroke_width=2.2, dash_length=0.12)
        xdot = Dot(xl, radius=0.11, color=CYAN_BRIGHT)
        glow = Circle(radius=0.11, stroke_color=CYAN_BRIGHT, stroke_width=4).move_to(xl)
        self.play(Create(sheet), run_time=0.6)
        self.say("Far down the tail, the two stacked lobes are antiparallel too.", hold=1.5)
        self.play(FadeIn(xdot), run_time=0.25)
        self.play(glow.animate.scale(8.0).set_stroke(opacity=0.0), run_time=0.7)
        self.remove(glow)

        plasmoid = Ellipse(width=0.95, height=0.62, stroke_color=CORAL, stroke_width=3,
                           fill_color=CORAL, fill_opacity=0.16).move_to([3.6, EY, 0])
        jet = Arrow([2.05, EY, 0], [0.35, EY, 0], color=CORAL, buff=0, stroke_width=6,
                    max_tip_length_to_length_ratio=0.22)
        self.play(FadeIn(plasmoid), GrowArrow(jet), FadeOut(xdot), run_time=0.9)
        self.play(plasmoid.animate.shift(RIGHT * 2.6).set_opacity(0.0), run_time=1.4)
        self.say("It reconnects. One piece leaves down-tail; the rest is fired straight back at Earth.", hold=1.9)

        # injection -> ring current + aurora
        ring = Ellipse(width=1.30, height=0.44, stroke_color=CORAL, stroke_width=3.6).move_to([EX, EY, 0])
        rl = Text("RING CURRENT", font=MONO_SB, font_size=24, color=CORAL)
        rl.move_to([EX - 0.15, EY - 1.62, 0])
        rlead = Line([EX - 0.15, EY - 1.40, 0], [EX - 0.10, EY - 0.30, 0],
                     stroke_color=CORAL, stroke_width=1.6).set_opacity(0.65)

        self.play(FadeOut(jet), FadeIn(ring), FadeIn(rl), FadeIn(rlead), run_time=1.0)
        self.say("That injection lights the aurora and feeds the ring current.", hold=1.8)

        # sunward return
        rf = 0.70
        ret = flow([[1.9, EY + rf * mp_half(1.9)], [-0.4, EY + rf * mp_half(-0.4)],
                    [-2.6, EY + rf * mp_half(-2.6)], [-4.0, EY + rf * mp_half(-4.0)],
                    [NOSE_X + 0.55, EY + 0.72], [NOSE_X + 0.30, EY + 0.18]],
                   CYAN_BRIGHT, 3.6, arrows=(0.30, 0.72), size=0.13)
        self.play(sweep.animate.set_stroke(opacity=0.28), run_time=0.5)
        self.play(Create(ret), run_time=1.2)
        self.say("The closed line drifts back to the dayside, and the loop starts again.", hold=1.7)

        cyc = Text("THE DUNGEY CYCLE · 1961", font=MONO_SB, font_size=27, color=CYAN_BRIGHT)
        cyc.move_to([2.55, EY + 2.62, 0])
        self.play(FadeOut(lobe_lbl), run_time=0.35)
        self.play(FadeIn(cyc), run_time=0.5)
        self.wait(1.3)
        self.play(FadeOut(VGroup(sweep, sheet, plasmoid, ring, rl, rlead, ret, cyc)), run_time=0.7)


class Est(Reconnection):
    """Geometry-tuning scene: the establishing shot only."""
    def construct(self):
        self.camera.background_color = VOID
        self._caption = None
        self.frame_chrome()
        mag, mp, closed, lobes, earth = self.magnetosphere()
        self.add(mag, self.wind(southward=True))
        self.say("Earth's field is a bubble the solar wind flows around.")
        self.wait(0.2)
