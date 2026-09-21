"""
MECHANISM 06 - Drag lowers the orbit and RAISES the speed.

The counter-intuitive one. Every number quoted is circular-orbit arithmetic on
mu = 398 600 km^3/s^2 and a 6 378 km equatorial radius, computed rather than
recalled: 400 km -> 7 669 m/s and 92.6 min; 300 km -> 7 726 m/s and 90.5 min.
The energy accounting is the exact circular-orbit result: for a fall of one
unit of total energy, potential energy falls by two and kinetic energy rises
by one.

WHY THE TIMINGS IN HERE LOOK HAND-PICKED
----------------------------------------
They are, and they are picked from a measurement rather than from taste. Sean,
2026-08-27: "the timing needs to be checked on the videos ... my voice matches
what is being drawn on the screen based on timing." This scene is the pilot for
docs/PLAN-video-expansion.md, so every hold below is cut to a WORD TIME in the
delivered narration - the transcriber returns a start and end for every word,
and the holds are set so that the -1 bar is on the frame at "one unit out", the
-2 bar at "worth two", the +1 bar at "into speed", the equation card at "the
equation closes the case", the REENTRY label at "all the way to reentry" and so
on. Change a line's text and its recording changes length, so the holds have to
be re-derived against the new audio; they are not free parameters.

TWO THINGS ON THIS FRAME USED TO BE DRAWN WITH NO CAPTION OF THEIR OWN: the
along-track ops block and the geomagnetic-storm note. A visual with no caption
has no `anchor` a narration line can name, which is why neither of them was ever
spoken. Both now have a `say()` - and the headline each block used to carry is
the caption, so no words were added to the frame and none were duplicated on it.

A HOLD ON THIS SCENE IS USUALLY A LAP, NOT A FREEZE. The satellite is an
`always_redraw` on a ValueTracker, so `self.wait()` leaves it hanging still in
space. Where the orbit is what the viewer is looking at, time is bought by
letting it keep going round at the pace it was already going - `spin()` below -
rather than by freezing it for ten seconds.
"""

import numpy as np
from manim import *
from theme import *
from parts import *

EC = np.array([-3.75, 0.55, 0.0])
RE_D = 1.05
ORB0, ORB1 = 2.32, 1.86
CX = 3.15

# One lap at each altitude, in seconds of screen time. RATE_LO is faster because
# the lower orbit is faster, which is the whole point of the piece; 3.0 s is the
# pace the shrink animation has always used, so nothing on screen changes speed
# at a moment the narration is not talking about speed.
LAP_HI, LAP_LO = 3.4, 3.0
RATE_HI, RATE_LO = 2 * PI / LAP_HI, 2 * PI / LAP_LO


class Drag(MechanismScene):
    TITLE = "Drag makes it go faster"
    KICKER = "Mechanism 06 · Orbit decay"
    SUB = "A force that opposes the motion, and the spacecraft speeds up."
    TAKEAWAY = "Drag does not slow a satellite down. It lowers it — and a lower orbit is a faster one."
    MARK = "SCHEMATIC · CIRCULAR-ORBIT ARITHMETIC"

    def readout(self, alt, v, per, color=CYAN_BRIGHT):
        g = VGroup(
            Text(f"{alt}", font=MONO_SB, font_size=40, color=color),
            Text(f"{v}", font=MONO_SB, font_size=40, color=color),
            Text(f"{per}", font=MONO_SB, font_size=40, color=color),
        ).arrange(DOWN, buff=0.16, aligned_edge=RIGHT)
        keys = VGroup(
            Text("ALTITUDE", font=MONO, font_size=26, color=MUTED),
            Text("SPEED", font=MONO, font_size=26, color=MUTED),
            Text("PERIOD", font=MONO, font_size=26, color=MUTED),
        ).arrange(DOWN, buff=0.32, aligned_edge=LEFT)
        row = VGroup(keys, g).arrange(RIGHT, buff=0.55)
        return row

    def spin(self, ang, seconds, rate):
        """Hold the frame for `seconds` by flying the orbit, not by freezing it."""
        self.play(ang.animate.set_value(ang.get_value() + rate * seconds),
                  run_time=seconds, rate_func=linear)

    def body(self):
        chrome = self.frame_chrome()
        earth = earth_disc([EC[0], EC[1]], RE_D)
        earth[1].set_opacity(0.0)   # no Sun in this view, so no terminator
        orbit = Circle(radius=ORB0, stroke_color=CYAN, stroke_width=2.6).move_to(EC)
        orbit.set_stroke(opacity=0.7)
        self.play(FadeIn(earth), Create(orbit), run_time=1.0)

        ang = ValueTracker(0.4)
        rad = ValueTracker(ORB0)

        def pos():
            return EC + rad.get_value() * np.array([np.cos(ang.get_value()),
                                                    np.sin(ang.get_value()), 0.0])

        sat = always_redraw(lambda: Dot(pos(), radius=0.115, color=TEXT))
        vel = always_redraw(lambda: Arrow(
            pos(), pos() + 0.95 * np.array([-np.sin(ang.get_value()), np.cos(ang.get_value()), 0.0]),
            color=MINT, buff=0, stroke_width=5, max_tip_length_to_length_ratio=0.32))
        self.add(sat, vel)
        r1 = self.readout("400 km", "7 669 m/s", "92.6 min")
        r1.move_to([CX, 1.75, 0])
        self.play(FadeIn(r1), run_time=0.6)
        # The opening laps run under the title line. The readout has to be up
        # before "Four hundred kilometres up" is spoken, which is 8.9 s in.
        self.spin(ang, 7.5, RATE_HI)
        self.say("One altitude, one speed, one period. A circular orbit has no choice about it.")
        self.spin(ang, 11.4, RATE_HI)

        # ---- drag
        drg = always_redraw(lambda: Arrow(
            pos(), pos() - 0.78 * np.array([-np.sin(ang.get_value()), np.cos(ang.get_value()), 0.0]),
            color=CORAL, buff=0, stroke_width=6, max_tip_length_to_length_ratio=0.34))
        dlbl = Text("DRAG", font=MONO_SB, font_size=28, color=CORAL)
        dlbl.move_to([CX - 1.45, -0.55, 0])
        self.add(drg)
        self.play(FadeIn(dlbl), run_time=0.5)
        self.say("Thin air. The drag force points backwards along the track.")
        self.spin(ang, 8.9, RATE_HI)
        self.say("Backwards. So obviously it slows down.")
        # 7.1 s of ordinary orbit, and then the shrink starts as the voice says
        # "Watch the readout while the orbit shrinks" - word 21 of that line.
        self.spin(ang, 7.1, RATE_HI)

        # ---- and yet
        r2 = self.readout("300 km", "7 726 m/s", "90.5 min", AMBER)
        r2.move_to([CX, 1.75, 0])
        self.play(rad.animate.set_value(ORB1),
                  orbit.animate.scale(ORB1 / ORB0),
                  ang.animate.set_value(ang.get_value() + 2 * PI),
                  run_time=3.0, rate_func=linear)
        self.play(FadeOut(r1), FadeIn(r2), run_time=0.6)
        self.say("It does not. It ends up a hundred kilometres lower — and 57 metres a second faster.")
        self.spin(ang, 9.8, RATE_LO)
        self.play(FadeOut(VGroup(drg, dlbl)), run_time=0.4)
        self.remove(vel)

        # ---- the bookkeeping
        BASE = 0.34
        UNIT = 0.70
        bx = [1.30, 3.55, 5.80]
        zero = Line([0.30, BASE, 0], [6.85, BASE, 0], stroke_color=LINE_STRONG, stroke_width=2.2)
        self.play(FadeOut(r2), Create(zero), run_time=0.7)
        self.say("The accounting is exact, and it is the reason.")
        self.spin(ang, 6.7, RATE_LO)

        def bar(x, units, color, num, l1, l2):
            h = units * UNIT
            rect = Rectangle(width=1.28, height=abs(h), fill_color=color, fill_opacity=0.26,
                             stroke_color=color, stroke_width=3.2)
            rect.move_to([x, BASE + h / 2, 0])
            n = Text(num, font=MONO_SB, font_size=42, color=color)
            n.move_to([x, BASE + h / 2, 0])
            cap = VGroup(Text(l1, font=SANS, font_size=27, color=MUTED),
                         Text(l2, font=SANS, font_size=27, color=MUTED)
                         ).arrange(DOWN, buff=0.08)
            if cap.width > 2.10:
                cap.scale(2.10 / cap.width)
            cap.move_to([x, -1.90, 0])
            return VGroup(rect, n, cap)

        b1 = bar(bx[0], -1, CORAL, "−1", "energy drag", "took out")
        b2 = bar(bx[1], -2, VIOLET, "−2", "height", "given up")
        b3 = bar(bx[2], +1, MINT, "+1", "speed", "gained")
        # One line of narration runs across these three beats and the equation
        # card. The three holds are cut to its clause boundaries: -2 lands at
        # "the height it gave up was worth two", +1 at "one unit paid the drag",
        # and the equation at "the equation closes the case".
        self.play(FadeIn(b1), run_time=0.8)
        self.say("Drag takes energy out of the orbit. Call it one unit.")
        self.spin(ang, 1.7, RATE_LO)
        self.play(FadeIn(b2), run_time=0.8)
        self.say("The orbit drops, and the height it gives up is worth two units.")
        self.spin(ang, 1.2, RATE_LO)
        self.play(FadeIn(b3), run_time=0.8)
        self.say("One went to drag. The other had nowhere to go but into speed.")
        self.spin(ang, 2.6, RATE_LO)

        eq = Text("v = √( μ / r )", font=MONO_SB, font_size=36, color=CYAN_BRIGHT)
        eqs = Text("smaller r, larger v — always", font=SANS, font_size=30, color=MUTED)
        eg = VGroup(eq, eqs).arrange(DOWN, buff=0.13).move_to([3.55, 2.45, 0])
        self.play(FadeIn(eg), run_time=0.7)
        self.spin(ang, 7.4, RATE_LO)
        self.play(FadeOut(VGroup(b1, b2, b3, zero, eg)), run_time=0.6)

        # ---- runaway, and what an operator sees
        self.say("And it does not settle there.")
        self.spin(ang, 1.75, RATE_LO)
        # This caption used to land AFTER the spiral had finished drawing. It now
        # lands 0.1 s before the voice says "because lower means denser air", and
        # the spiral is drawn under that clause rather than after it.
        self.say("Lower means denser air, which means more drag, which means lower still.")
        spiral = VMobject(stroke_color=CORAL, stroke_width=3)
        pts = []
        for i in range(420):
            u = i / 419
            a = 0.4 + u * 7.4 * PI
            r = ORB1 * (1 - 0.395 * u ** 2.4)
            pts.append(EC + r * np.array([np.cos(a), np.sin(a), 0.0]))
        spiral.set_points_smoothly(pts)
        self.remove(sat)
        self.play(FadeOut(orbit), Create(spiral), run_time=6.5, rate_func=linear)
        self.wait(2.2)
        rein = Text("REENTRY", font=MONO_SB, font_size=28, color=CORAL)
        rein.move_to([EC[0] + 0.10, EC[1] - RE_D - 1.02, 0])
        self.play(FadeIn(rein), run_time=0.4)
        self.wait(1.7)

        # The ops block loses its own headline, because the headline is now the
        # caption for this beat. Nothing was added to the frame and nothing is
        # said twice on it; what changed is that the beat exists at all, so a
        # narration line can anchor to the moment this block appears instead of
        # arriving while the frame had already moved on to the storm note.
        ops = VGroup(
            Text("Each orbit is two minutes", font=SANS_SB, font_size=33, color=AMBER),
            Text("shorter, so it arrives early.", font=SANS_SB, font_size=33, color=AMBER),
            Text("Along-track error, growing", font=SANS, font_size=31, color=MUTED),
            Text("every revolution.", font=SANS, font_size=31, color=MUTED),
        ).arrange(DOWN, buff=0.15)
        ops.submobjects[2].shift(DOWN * 0.30)
        ops.submobjects[3].shift(DOWN * 0.30)
        if ops.width > 5.60:
            ops.scale(5.60 / ops.width)
        ops.move_to([CX + 0.30, 0.60, 0])
        clear_of(ops, rein, direction=UP)
        self.play(FadeIn(ops), run_time=0.9)
        self.say("What you notice first is not the altitude.")
        self.wait(11.2)

        # This note REPLACES the ops block, so it belongs in the ops block's
        # column, not across the full width. Full width it ran straight through
        # the REENTRY label on the spiral -- the frame read "RY storm heats the
        # thermosphere" for four seconds -- and there is no gap beside REENTRY
        # wide enough for a full-width line, so moving it was never going to
        # work. It goes where the text it replaces already lived.
        #
        # Its first sentence is the caption for this beat, for the same reason
        # the ops block gave its headline up: the note was drawn with no caption,
        # so nothing could anchor to it and the frame's last statement was never
        # spoken aloud in a clip that talks the whole way through.
        wrapped = self._wrap("The density at 400 km rises, and drag jumps for "
                             "everything in low orbit at once.",
                             31, SANS, MUTED, 5.30, buff=0.14)
        wrapped.move_to([CX + 0.30, 0.60, 0])
        clear_of(wrapped, rein, direction=UP)
        self.play(FadeOut(ops), FadeIn(wrapped), run_time=0.9)
        self.say("A geomagnetic storm heats the thermosphere.")
        self.wait(14.2)
        self.play(FadeOut(VGroup(earth, spiral, rein, wrapped, chrome)), run_time=0.7)
        self.clear_caption()
