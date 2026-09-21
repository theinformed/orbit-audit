"""The March 1989 geomagnetically-induced-current chain, drawn.

This is a MECHANISM animation and nothing else. Every measured thing about this
storm is on the page beside it as a chart of real data; what a chart cannot show
is the causal chain, because the chain is an argument rather than an event with a
location. Nobody instrumented a transformer neutral in Quebec that night, there
is no footage of the collapse, and a generated photoreal video of a 1989 control
room would read as archive film and would be a lie. A labelled vector diagram
that moves is the correct evidence class for a causal chain, and nobody has ever
mistaken one for a photograph.

Render (Manim Community v0.20.1, inside the gateway container):

    manim -qm --fps 30 gic_chain.py GicChain
"""

import json
from pathlib import Path

from manim import *

BG = "#02070c"
CYAN = "#29d4e3"
CYAN_HI = "#5ce8f1"
AMBER = "#f5c96a"
CORAL = "#ff7b78"
VIOLET = "#a98cff"
TEXT = "#edf8fb"
MUTED = "#8da8b3"
LINE = "#264a58"

MONO = "IBM Plex Mono"

config.background_color = BG


def label(text, size=22, colour=TEXT, weight=NORMAL):
    return Text(text, font=MONO, font_size=size, color=colour, weight=weight)


# The bottom of the frame belongs to the caption and to the video player's own
# control bar, which the browser draws over the lowest tenth of the picture
# whenever the video is paused or hovered. Nothing else goes below this line.
CAPTION_FLOOR = -2.55


def caption(text, size=25):
    """The line of prose at the bottom of the frame, always in the same place."""
    node = Text(text, font=MONO, font_size=size, color=TEXT, weight=MEDIUM)
    node.to_edge(DOWN, buff=1.05)
    if node.width > config.frame_width - 1.2:
        node.scale((config.frame_width - 1.2) / node.width)
        node.to_edge(DOWN, buff=1.05)
    return node


def step_badge(number, title):
    """The persistent step counter in the top-left, so the chain stays countable."""
    index = Text(f"{number}", font=MONO, font_size=44, color=VIOLET, weight=BOLD)
    name = Text(title.upper(), font=MONO, font_size=17, color=MUTED, weight=MEDIUM)
    name.next_to(index, RIGHT, buff=0.22, aligned_edge=DOWN)
    group = VGroup(index, name)
    group.to_corner(UL, buff=0.45)
    return group


# How long each narrated line runs, measured from the rendered audio rather than
# guessed. The scene pads each section to its line plus a beat, so the narration
# never runs over the picture it describes. Written by tools/narrate.py.
NARRATION_PATH = Path(__file__).with_name("narration-durations.json")
NARRATION = json.loads(NARRATION_PATH.read_text()) if NARRATION_PATH.is_file() else {}
TAIL_BEAT = 1.1


class GicChain(Scene):
    def construct(self):
        self.marks = []
        for line_id, section in (
            ("gic-01-field", self.sky),
            ("gic-02-faraday", self.faraday),
            ("gic-03-line", self.the_line),
            ("gic-04-saturation", self.saturation),
            ("gic-05-harmonics", self.harmonics),
            ("gic-06-relays", self.relays),
            ("gic-07-collapse", self.collapse),
        ):
            start = self.renderer.time
            need = NARRATION.get(line_id, 0.0) + TAIL_BEAT

            def hold(_start=start, _need=need):
                """Wait, if needed, so the section outlives its narration line."""
                short = _need - (self.renderer.time - _start)
                if short > 0.05:
                    self.wait(short)

            section(hold)
            self.marks.append({
                "id": line_id,
                "start": round(start, 3),
                "end": round(self.renderer.time, 3),
            })
        Path("/tmp/gic_marks.json").write_text(json.dumps(self.marks, indent=1))

    # -- 1 ----------------------------------------------------------------
    def sky(self, hold):
        badge = step_badge(1, "the field moves")
        ground = Line(LEFT * 6.6, RIGHT * 6.6, color=LINE, stroke_width=3).shift(DOWN * 1.55)
        soil = Rectangle(width=13.2, height=1.0, stroke_width=0,
                         fill_color="#0a1620", fill_opacity=1).next_to(ground, DOWN, buff=0)
        ground_label = label("GROUND · 45° N", 16, MUTED).next_to(ground, DOWN, buff=0.16).align_to(ground, LEFT)

        jet = Rectangle(width=11.0, height=0.42, stroke_width=0,
                        fill_color=CYAN, fill_opacity=0.30).shift(UP * 2.0)
        jet_edge = Rectangle(width=11.0, height=0.42, stroke_color=CYAN,
                             stroke_width=2, fill_opacity=0).shift(UP * 2.0)
        jet_label = label("AURORAL ELECTROJET · ~100 km up", 17, CYAN_HI).next_to(jet, UP, buff=0.18)
        arrows = VGroup(*[
            Arrow(RIGHT * (x + 0.9), RIGHT * (x - 0.9), buff=0, color=CYAN_HI,
                  stroke_width=3, max_tip_length_to_length_ratio=0.35).shift(UP * 2.0)
            for x in (-3.4, 0.0, 3.4)
        ])

        field = VGroup(*[
            Arrow(UP * 1.75 + RIGHT * x, DOWN * 1.45 + RIGHT * x, buff=0,
                  color=VIOLET, stroke_width=2.5, max_tip_length_to_length_ratio=0.08)
            for x in (-4.4, -2.2, 0.0, 2.2, 4.4)
        ])
        field_label = label("B at the ground", 17, VIOLET).move_to(RIGHT * 5.5 + DOWN * 0.35)

        readout_value = DecimalNumber(1, num_decimal_places=0, font_size=52,
                                      color=TEXT).set_color(TEXT)
        readout_unit = label("nT / min", 18, MUTED)
        readout_unit.next_to(readout_value, DOWN, buff=0.14)
        readout = VGroup(readout_value, readout_unit).to_corner(UR, buff=0.5)

        self.add(badge)
        self.play(FadeIn(soil, shift=UP * 0.2), Create(ground), FadeIn(ground_label), run_time=0.8)
        self.play(FadeIn(jet), Create(jet_edge), FadeIn(jet_label), *[GrowArrow(a) for a in arrows], run_time=1.1)
        self.play(*[GrowArrow(a) for a in field], FadeIn(field_label), run_time=1.0)
        self.play(FadeIn(readout), run_time=0.4)

        cap = caption("A current sheet a continent wide, a hundred kilometres up.")
        self.play(FadeIn(cap), run_time=0.5)
        self.wait(1.2)

        # The jet strengthens and shifts equatorward; the ground field follows it.
        tracker = ValueTracker(1.0)
        readout_value.add_updater(lambda m: m.set_value(tracker.get_value()))
        readout_value.add_updater(
            lambda m: m.set_color(CORAL if tracker.get_value() > 100 else TEXT))
        self.play(
            jet.animate.set_fill(opacity=0.75).shift(DOWN * 0.45),
            jet_edge.animate.shift(DOWN * 0.45),
            jet_label.animate.shift(DOWN * 0.45),
            arrows.animate.shift(DOWN * 0.45).set_stroke(width=6),
            field.animate.set_stroke(width=6, color=CORAL),
            tracker.animate.set_value(435),
            run_time=2.4,
        )
        readout_value.clear_updaters()
        cap2 = caption("At Ottawa the field moved four hundred and thirty-five nanotesla in one minute.")
        self.play(FadeOut(cap), FadeIn(cap2), run_time=0.5)
        self.wait(1.6)
        hold()
        self.play(*[FadeOut(m) for m in (jet, jet_edge, jet_label, arrows, field, field_label,
                                         readout, cap2, badge)], run_time=0.6)
        self.ground = ground
        self.soil = soil
        self.ground_label = ground_label

    # -- 2 ----------------------------------------------------------------
    def faraday(self, hold):
        badge = step_badge(2, "the rock answers")
        law = MathTex(r"\nabla \times \mathbf{E} \;=\; -\,\frac{\partial \mathbf{B}}{\partial t}",
                      color=TEXT, font_size=54).shift(UP * 1.55)
        law_note = label("a field that CHANGES makes an electric field. one that merely exists does not.",
                         17, MUTED).next_to(law, DOWN, buff=0.35)

        efield = VGroup(*[
            Arrow(RIGHT * (x - 0.85) + DOWN * 2.28, RIGHT * (x + 0.85) + DOWN * 2.28, buff=0,
                  color=AMBER, stroke_width=4, max_tip_length_to_length_ratio=0.32)
            for x in (-4.6, -2.3, 0.0, 2.3, 4.6)
        ])
        efield_label = label("E in the ground  ·  a few volts per kilometre", 18, AMBER)
        efield_label.next_to(efield, UP, buff=0.14)

        self.add(badge)
        self.play(Write(law), run_time=1.3)
        self.play(FadeIn(law_note), run_time=0.5)
        cap = caption("A magnetic field that changes drives an electric field in the rock beneath it.")
        self.play(FadeIn(cap), run_time=0.5)
        self.play(LaggedStart(*[GrowArrow(a) for a in efield], lag_ratio=0.14), run_time=1.4)
        self.play(FadeIn(efield_label), run_time=0.5)
        self.wait(1.4)

        cap2 = caption("A few volts per kilometre is nothing. Now find something a thousand kilometres long.")
        self.play(FadeOut(cap), FadeIn(cap2), run_time=0.5)
        self.wait(1.8)
        hold()
        self.play(*[FadeOut(m) for m in (law, law_note, efield, efield_label, cap2, badge,
                                         self.ground, self.soil, self.ground_label)], run_time=0.6)

    # -- 3 ----------------------------------------------------------------
    def the_line(self, hold):
        badge = step_badge(3, "the line is an antenna")
        ground = Line(LEFT * 6.8, RIGHT * 6.8, color=LINE, stroke_width=3).shift(DOWN * 1.55)
        soil = Rectangle(width=13.6, height=1.0, stroke_width=0,
                         fill_color="#0a1620", fill_opacity=1).next_to(ground, DOWN, buff=0)

        def station(x, name):
            body = Rectangle(width=1.15, height=1.15, stroke_color=CYAN, stroke_width=2.5,
                             fill_color="#06131b", fill_opacity=1)
            body.move_to(RIGHT * x + UP * 0.35)
            coil = VGroup(*[Arc(radius=0.13, angle=PI, start_angle=0, color=CYAN_HI, stroke_width=3)
                            .move_to(body.get_center() + LEFT * 0.3 + UP * (0.26 - 0.26 * k))
                            for k in range(3)])
            neutral = Line(body.get_bottom(), RIGHT * x + DOWN * 1.55, color=CYAN, stroke_width=3)
            earth = VGroup(*[Line(RIGHT * (x - 0.26 + 0.09 * k) + DOWN * (1.55 + 0.13 * k),
                                  RIGHT * (x + 0.26 - 0.09 * k) + DOWN * (1.55 + 0.13 * k),
                                  color=CYAN, stroke_width=3) for k in range(3)])
            tag = label(name, 16, MUTED).next_to(body, UP, buff=0.18)
            return VGroup(body, coil, neutral, earth, tag)

        west = station(-4.7, "SUBSTATION")
        east = station(4.7, "SUBSTATION")
        line = Line(RIGHT * -4.7 + UP * 0.93, RIGHT * 4.7 + UP * 0.93, color=CYAN, stroke_width=3)
        towers = VGroup(*[
            VGroup(Line(RIGHT * x + UP * 0.93, RIGHT * x + DOWN * 0.6, color=LINE, stroke_width=2),
                   Line(RIGHT * (x - 0.28) + UP * 0.75, RIGHT * (x + 0.28) + UP * 0.75,
                        color=LINE, stroke_width=2))
            for x in (-2.4, 0.0, 2.4)])
        span = DoubleArrow(RIGHT * -4.7 + UP * 1.6, RIGHT * 4.7 + UP * 1.6, buff=0,
                           color=MUTED, stroke_width=2, tip_length=0.18)
        span_label = label("hundreds of kilometres", 17, MUTED).next_to(span, UP, buff=0.12)

        efield = VGroup(*[
            Arrow(RIGHT * (x - 0.7) + DOWN * 2.3, RIGHT * (x + 0.7) + DOWN * 2.3, buff=0,
                  color=AMBER, stroke_width=3.5, max_tip_length_to_length_ratio=0.3)
            for x in (-4.0, -2.0, 0.0, 2.0, 4.0)
        ])
        potential = label("E × length  =  a real voltage between the two earths", 18, AMBER)
        potential.move_to(DOWN * 1.0)

        self.add(badge)
        self.play(FadeIn(soil), Create(ground), run_time=0.5)
        self.play(FadeIn(west), FadeIn(east), Create(line), FadeIn(towers), run_time=1.2)
        self.play(GrowFromCenter(span), FadeIn(span_label), run_time=0.6)
        cap = caption("Both ends of that line are bolted to the ground through a transformer neutral.")
        self.play(FadeIn(cap), run_time=0.5)
        self.wait(1.3)
        self.play(LaggedStart(*[GrowArrow(a) for a in efield], lag_ratio=0.1), FadeIn(potential), run_time=1.2)
        self.wait(0.9)

        # The current, traced along the loop it actually takes.
        path = VMobject(color=CORAL, stroke_width=6)
        path.set_points_as_corners([
            RIGHT * -4.7 + DOWN * 1.55, RIGHT * -4.7 + UP * 0.93,
            RIGHT * 4.7 + UP * 0.93, RIGHT * 4.7 + DOWN * 1.55,
        ])
        cap2 = caption("So a current flows: up one neutral, along the line, down the other.")
        self.play(FadeOut(cap), FadeIn(cap2), run_time=0.5)
        self.play(Create(path), run_time=1.8)
        gic = label("GEOMAGNETICALLY INDUCED CURRENT", 20, CORAL, BOLD).move_to(UP * 2.6)
        gic_note = label("quasi-direct  ·  tens to hundreds of amperes", 18, MUTED).next_to(gic, DOWN, buff=0.16)
        self.play(FadeIn(gic), FadeIn(gic_note), run_time=0.6)
        self.wait(1.6)
        hold()
        self.play(*[FadeOut(m) for m in (soil, ground, west, east, line, towers, span, span_label,
                                         efield, potential, path, gic, gic_note, cap2, badge)],
                  run_time=0.6)

    # -- 4 ----------------------------------------------------------------
    def saturation(self, hold):
        """Half-cycle saturation, shown as the B-H curve and the current it makes.

        This is the link in the chain that people skip, and it is the one that
        does the damage. A transformer core is a magnetic amplifier with a knee
        in it. Sixty-hertz excitation lives below the knee, where a large change
        in flux costs a small magnetising current. Add a steady offset and one
        half of every cycle is pushed over the knee, where the same change in
        flux costs an enormous one.
        """
        badge = step_badge(4, "the core saturates")

        axes = Axes(x_range=[-3.2, 3.2, 1], y_range=[-1.5, 1.5, 0.5],
                    x_length=5.2, y_length=3.4,
                    axis_config={"color": LINE, "stroke_width": 2,
                                 "include_ticks": False, "include_tip": False})
        axes.shift(LEFT * 3.5 + UP * 0.35)
        bh = axes.plot(lambda h: 1.18 * np.tanh(1.55 * h), color=CYAN, stroke_width=4)
        knee = DashedLine(axes.c2p(-3.2, 1.06), axes.c2p(3.2, 1.06), color=MUTED, stroke_width=1.5)
        knee_label = label("the knee", 15, MUTED).next_to(knee, UP, buff=0.14).shift(LEFT * 1.6)
        h_label = label("H  ·  magnetising current", 16, MUTED).next_to(axes, DOWN, buff=0.2)
        b_label = label("B", 16, MUTED).next_to(axes, LEFT, buff=0.15)

        wave = Axes(x_range=[0, 4 * PI, PI], y_range=[-1.8, 3.2, 1],
                    x_length=5.6, y_length=3.4,
                    axis_config={"color": LINE, "stroke_width": 2,
                                 "include_ticks": False, "include_tip": False})
        wave.shift(RIGHT * 3.4 + UP * 0.35)
        flux = wave.plot(lambda t: 1.0 * np.sin(t), color=CYAN, stroke_width=3.5)
        current = wave.plot(lambda t: 0.40 * np.tanh(2.2 * np.sin(t)), color=AMBER, stroke_width=3.5)
        wave_flux = label("flux", 16, CYAN).next_to(wave, UP, buff=0.14).shift(LEFT * 1.1)
        wave_current = label("magnetising current", 16, AMBER).next_to(wave, UP, buff=0.14).shift(RIGHT * 1.3)

        self.add(badge)
        self.play(Create(axes), Create(wave), run_time=0.7)
        self.play(Create(bh), FadeIn(h_label), FadeIn(b_label), run_time=0.9)
        self.play(Create(knee), FadeIn(knee_label), run_time=0.5)
        self.play(Create(flux), Create(current), FadeIn(wave_flux), FadeIn(wave_current), run_time=1.1)
        cap = caption("At sixty hertz the core stays under the knee. The current is small and symmetric.")
        self.play(FadeIn(cap), run_time=0.5)
        self.wait(1.5)

        offset = ValueTracker(0.0)
        bias = always_redraw(lambda: DashedLine(
            axes.c2p(-3.2, offset.get_value() * 1.0), axes.c2p(3.2, offset.get_value() * 1.0),
            color=CORAL, stroke_width=2))
        shifted_flux = always_redraw(lambda: wave.plot(
            lambda t: 1.0 * np.sin(t) + offset.get_value(), color=CYAN, stroke_width=3.5))
        shifted_current = always_redraw(lambda: wave.plot(
            lambda t: 0.40 * np.tanh(2.2 * (np.sin(t) + offset.get_value()))
            + 5.0 * np.maximum(0.0, np.sin(t) + offset.get_value() - 0.92) ** 2.0,
            color=AMBER, stroke_width=3.5))

        self.remove(flux, current)
        self.add(bias, shifted_flux, shifted_current)
        cap2 = caption("The induced current adds a steady offset. Half of every cycle now goes over the knee.")
        self.play(FadeOut(cap), FadeIn(cap2), run_time=0.5)
        self.play(offset.animate.set_value(0.62), run_time=2.6)
        self.wait(0.6)

        spike = label("HALF-CYCLE SATURATION", 21, CORAL, BOLD).move_to(DOWN * 2.0)
        self.play(FadeIn(spike), run_time=0.5)
        cap3 = caption("The magnetising current stops being a sine wave and becomes a spike.")
        self.play(FadeOut(cap2), FadeIn(cap3), run_time=0.5)
        self.wait(1.7)
        hold()
        # always_redraw rebuilds these every frame, so an animation that
        # interpolates them against themselves fails. Freeze them first.
        for live in (bias, shifted_flux, shifted_current):
            live.clear_updaters()
        self.play(*[FadeOut(m) for m in (axes, bh, knee, knee_label, h_label, b_label, wave,
                                         bias, shifted_flux, shifted_current, wave_flux,
                                         wave_current, spike, cap3, badge)], run_time=0.6)

    # -- 5 ----------------------------------------------------------------
    def harmonics(self, hold):
        badge = step_badge(5, "harmonics, and heat")
        chart = Axes(x_range=[0, 8, 1], y_range=[0, 1.15, 0.5], x_length=6.4, y_length=3.0,
                     axis_config={"color": LINE, "stroke_width": 2, "include_tip": False})
        chart.shift(LEFT * 2.6 + UP * 0.5)
        heights = {1: 1.0, 2: 0.62, 3: 0.44, 4: 0.30, 5: 0.21, 6: 0.14, 7: 0.09}
        bars = VGroup()
        for order, height in heights.items():
            bar = Rectangle(width=0.34, height=chart.y_axis.unit_size * height,
                            stroke_width=0, fill_opacity=1,
                            fill_color=CYAN if order == 1 else AMBER)
            bar.move_to(chart.c2p(order, height / 2))
            bars.add(bar)
        ticks = VGroup(*[label(str(o), 15, MUTED).next_to(chart.c2p(o, 0), DOWN, buff=0.14)
                         for o in heights])
        chart_label = label("harmonic order", 16, MUTED).next_to(chart, DOWN, buff=0.5)
        fundamental = label("60 Hz", 15, CYAN).next_to(bars[0], UP, buff=0.1)

        tank = Rectangle(width=2.1, height=2.4, stroke_color=CYAN, stroke_width=2.5,
                         fill_color="#06131b", fill_opacity=1).shift(RIGHT * 4.3 + UP * 0.5)
        glow = Rectangle(width=2.1, height=2.4, stroke_width=0,
                         fill_color=CORAL, fill_opacity=0.0).move_to(tank)
        tank_label = label("TRANSFORMER", 15, MUTED).next_to(tank, UP, buff=0.16)
        stray = VGroup(*[Arrow(tank.get_center() + LEFT * 0.55 + UP * (0.7 - 0.55 * k),
                               tank.get_center() + RIGHT * 0.8 + UP * (0.55 - 0.55 * k),
                               buff=0, color=CORAL, stroke_width=2.5,
                               max_tip_length_to_length_ratio=0.25) for k in range(3)])
        stray_label = label("stray flux into the tank", 15, CORAL).next_to(tank, DOWN, buff=0.2)

        self.add(badge)
        self.play(Create(chart), FadeIn(ticks), FadeIn(chart_label), run_time=0.7)
        self.play(LaggedStart(*[GrowFromEdge(b, DOWN) for b in bars], lag_ratio=0.12), run_time=1.4)
        self.play(FadeIn(fundamental), run_time=0.4)
        cap = caption("A spike is a stack of harmonics. The network was tuned for exactly one frequency.")
        self.play(FadeIn(cap), run_time=0.5)
        self.wait(1.5)
        self.play(Create(tank), FadeIn(tank_label), run_time=0.6)
        self.play(glow.animate.set_fill(opacity=0.28),
                  LaggedStart(*[GrowArrow(a) for a in stray], lag_ratio=0.15),
                  FadeIn(stray_label), run_time=1.3)
        cap2 = caption("The flux that no longer fits in the core goes into the steel around it, as heat.")
        self.play(FadeOut(cap), FadeIn(cap2), run_time=0.5)
        self.wait(1.6)
        hold()
        self.play(*[FadeOut(m) for m in (chart, bars, ticks, chart_label, fundamental, tank,
                                         glow, tank_label, stray, stray_label, cap2, badge)],
                  run_time=0.6)

    # -- 6 ----------------------------------------------------------------
    def relays(self, hold):
        badge = step_badge(6, "the protection acts")
        title = label("LA GRANDE NETWORK  ·  735 kV", 19, MUTED).move_to(UP * 2.75)

        blocks = VGroup()
        labels = VGroup()
        for k in range(7):
            x = -4.5 + k * 1.5
            body = RoundedRectangle(width=1.15, height=1.45, corner_radius=0.08,
                                    stroke_color=CYAN, stroke_width=2.5,
                                    fill_color="#07161f", fill_opacity=1).move_to(RIGHT * x + UP * 0.9)
            blocks.add(body)
            labels.add(label(f"SVC {k + 1}", 14, MUTED).next_to(body, DOWN, buff=0.14))
        note = label("static compensators — the machines holding the voltage up", 17, MUTED)
        note.move_to(DOWN * 0.55)

        meter = Axes(x_range=[0, 10, 1], y_range=[0, 1.1, 1], x_length=7.6, y_length=1.5,
                     axis_config={"color": LINE, "stroke_width": 2, "include_ticks": False,
                                  "include_tip": False}).move_to(DOWN * 1.7 + RIGHT * 1.5)
        threshold = DashedLine(meter.c2p(0, 0.72), meter.c2p(10, 0.72), color=CORAL, stroke_width=2)
        threshold_label = label("relay setting", 14, CORAL).next_to(threshold, RIGHT, buff=0.12)
        meter_label = label("harmonic distortion", 15, MUTED).next_to(meter, LEFT, buff=0.15)
        level = ValueTracker(0.18)
        bar = always_redraw(lambda: Rectangle(
            width=max(0.02, meter.x_axis.unit_size * 9.6 * level.get_value()),
            height=0.55, stroke_width=0, fill_opacity=1,
            fill_color=CORAL if level.get_value() > 0.72 else AMBER,
        ).align_to(meter.c2p(0, 0), LEFT).move_to(meter.c2p(0, 0.3), aligned_edge=LEFT))

        self.add(badge)
        self.play(FadeIn(title), LaggedStart(*[FadeIn(b) for b in blocks], lag_ratio=0.07),
                  FadeIn(labels), FadeIn(note), run_time=1.2)
        self.play(Create(meter), FadeIn(meter_label), Create(threshold),
                  FadeIn(threshold_label), run_time=0.7)
        self.add(bar)
        cap = caption("Their protection watches for distortion. Distortion is exactly what arrived.")
        self.play(FadeIn(cap), run_time=0.5)
        self.play(level.animate.set_value(0.93), run_time=1.8)
        self.wait(0.5)

        counter = label("7", 40, CYAN_HI, BOLD).move_to(RIGHT * 5.35 + UP * 2.75)
        counter_note = label("still in service", 15, MUTED)
        counter_note.next_to(counter, DOWN, buff=0.12).align_to(RIGHT * 6.5, RIGHT)
        self.play(FadeIn(counter), FadeIn(counter_note), run_time=0.4)
        cap2 = caption("Seven compensators tripped one after another, inside a minute.")
        self.play(FadeOut(cap), FadeIn(cap2), run_time=0.5)

        for k in range(7):
            remaining = label(str(6 - k), 40, CORAL if k > 3 else CYAN_HI, BOLD).move_to(counter)
            self.play(
                blocks[k].animate.set_stroke(color=CORAL, width=2).set_fill("#1a0a0c", opacity=1),
                labels[k].animate.set_color(CORAL),
                Transform(counter, remaining),
                run_time=0.28,
            )
        self.wait(0.8)
        hold()
        level.clear_updaters()
        bar.clear_updaters()
        self.play(*[FadeOut(m) for m in (title, blocks, labels, note, meter, meter_label,
                                         threshold, threshold_label, bar, counter, counter_note,
                                         cap2, badge)], run_time=0.6)

    # -- 7 ----------------------------------------------------------------
    def collapse(self, hold):
        badge = step_badge(7, "ninety-two seconds")
        volts = Axes(x_range=[0, 92, 10], y_range=[0, 1.15, 0.5], x_length=9.4, y_length=3.0,
                     axis_config={"color": LINE, "stroke_width": 2, "include_tip": False})
        volts.shift(UP * 0.35)
        axis_note = label("seconds after 02:44:17 EST", 16, MUTED).next_to(volts, DOWN, buff=0.35)
        v_note = label("system voltage, La Grande corridor", 16, MUTED).next_to(volts, UP, buff=0.2)

        def profile(t):
            if t < 8:
                return 1.0 - 0.02 * t
            if t < 60:
                return 0.84 - 0.006 * (t - 8)
            return max(0.0, 0.53 - 0.017 * (t - 60) ** 1.35)

        curve = volts.plot(profile, x_range=[0, 92], color=CORAL, stroke_width=4)
        marks = VGroup(*[
            VGroup(DashedLine(volts.c2p(0, frac), volts.c2p(92, frac), color=LINE, stroke_width=1),
                   label(text, 15, MUTED).next_to(volts.c2p(0, frac), LEFT, buff=0.16))
            for frac, text in ((1.0, "normal"), (0.5, "half"), (0.0, "nothing"))
        ])
        clock = DecimalNumber(0, num_decimal_places=0, font_size=64, color=TEXT).to_corner(UR, buff=0.5)
        clock_unit = label("seconds", 16, MUTED).next_to(clock, DOWN, buff=0.12)
        seconds = ValueTracker(0)
        clock.add_updater(lambda m: m.set_value(seconds.get_value()))

        self.add(badge)
        self.play(Create(volts), FadeIn(marks), FadeIn(axis_note), FadeIn(v_note),
                  FadeIn(clock), FadeIn(clock_unit), run_time=0.8)
        cap = caption("Five lines opened, and nine thousand four hundred megawatts went with them.")
        self.play(FadeIn(cap), run_time=0.5)
        self.play(Create(curve), seconds.animate.set_value(92), run_time=3.4, rate_func=linear)
        clock.clear_updaters()
        self.wait(0.5)

        cap2 = caption("Ninety-two seconds after the first trip, the province was dark.")
        self.play(FadeOut(cap), FadeIn(cap2), run_time=0.5)
        self.wait(1.4)
        hold()

        self.play(*[FadeOut(m) for m in (volts, curve, marks, axis_note, v_note, clock, clock_unit,
                                         cap2, badge)], run_time=0.6)

        headline = label("13 March 1989  ·  02:44:17 EST", 40, TEXT, BOLD).move_to(UP * 1.15)
        facts = VGroup(
            label("21,500 MW of load lost", 26, CORAL),
            label("six million people", 26, CORAL),
            label("nine hours", 26, CORAL),
        ).arrange(DOWN, buff=0.34).move_to(DOWN * 0.35)
        rule = Line(LEFT * 3.4, RIGHT * 3.4, color=LINE, stroke_width=2).move_to(DOWN * 1.85)
        disclaimer = label(
            "Schematic. Drawn from the published post-mortems. No part of this is footage.",
            18, MUTED).move_to(DOWN * 2.35)
        self.play(FadeIn(headline, shift=UP * 0.2), run_time=0.7)
        self.play(LaggedStart(*[FadeIn(f, shift=UP * 0.15) for f in facts], lag_ratio=0.25), run_time=1.2)
        self.play(Create(rule), FadeIn(disclaimer), run_time=0.6)
        self.wait(2.4)
        self.play(FadeOut(headline), FadeOut(facts), FadeOut(rule), FadeOut(disclaimer), run_time=0.8)
