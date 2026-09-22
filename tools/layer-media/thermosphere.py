"""Deterministic scientific figure; regenerate both delivered assets with build.py.

Dots are the three published model values; dashed segments declare interpolation.
The animation highlights the dots in reading order, never invents a data epoch.
"""
import json
import math
from pathlib import Path

from manim import Scene, Text, Line, DashedLine, Dot, Circle, FadeIn, FadeOut

DATA = json.loads(Path(__file__).with_suffix('.json').read_text())
BG, INK, MUTED, CYAN, GOLD = '#030b10', '#e0eef4', '#b4cbd4', '#40d7df', '#ffce75'


class Thermosphere(Scene):
    def construct(self):
        self.camera.background_color = BG

        def label(text, x, y, size=22, color=INK):
            obj = Text(text, font='DejaVu Sans', font_size=size, color=color)
            obj.move_to([x + obj.width / 2, y, 0])
            self.add(obj)
            return obj

        label('THERMOSPHERE · 120–1,000 km', -6.6, 3.55, 22, CYAN)
        label(DATA['headline'], -6.6, 2.93, 34)
        label('SCHEMATIC · model reference points, no time axis', -6.6, -3.15, 23, GOLD)
        label(DATA['caveat'], -6.6, -3.65, 21, MUTED)

        x0, x1, y0, y1 = -5.8, 0.0, -2.2, 2.0
        def xy(alt, density):
            return [x0 + (math.log10(density) + 15.5) / 8 * (x1-x0),
                    y0 + (alt-100) / 950 * (y1-y0), 0]
        self.add(Line([x0,y1,0], [x0,y0,0], color=MUTED),
                 Line([x0,y0,0], [x1,y0,0], color=MUTED))
        label('Altitude (km)', x0, 2.37, 21, MUTED)
        for alt in [120,420,700,1000]:
            y = xy(alt, 1e-15)[1]
            label(str(alt), x0-.85, y, 19, MUTED)
            self.add(Line([x0-.08,y,0], [x0,y,0], color=MUTED))
        for exponent in [-15,-13,-11,-9,-8]:
            x = xy(100, 10**exponent)[0]
            label(str(exponent), x-.19, y0-.25, 19, MUTED)
        label('log₁₀ density (kg m⁻³)', -4.95, -2.8, 21, MUTED)
        points = [xy(p['altitudeKm'], p['densityKgM3']) for p in DATA['points']]
        for start, end in zip(points, points[1:]):
            self.add(DashedLine(start, end, dash_length=.09, stroke_width=2, color=CYAN))
        for p, position in zip(DATA['points'], points):
            self.add(Dot(position, radius=.065, color=GOLD))
            label_x = position[0]-1.9 if p['altitudeKm'] == 120 else position[0]+.24
            label(p['label'], label_x, position[1]+.15, 20, GOLD)

        decades = math.log10(DATA['points'][0]['densityKgM3'] / DATA['points'][-1]['densityKgM3'])
        label(f'{decades:.2f} decades', 1.25, 1.65, 32, GOLD)
        ratio_millions = DATA['points'][0]['densityKgM3'] / DATA['points'][-1]['densityKgM3'] / 1e6
        label(f'Density ratio ≈ {ratio_millions:.2f} million', 1.25, 1.0, 23)
        label('Three dots: WAM model values', 1.25, .25, 22)
        label('Dashed line:', 1.25, -.4, 22, CYAN)
        label('log-linear interpolation', 1.25, -.8, 22, CYAN)
        label('Highlight order is a teaching aid;', 1.25, -1.6, 20, MUTED)
        label('it does not represent changing air.', 1.25, -1.95, 20, MUTED)
        label('Source: NOAA Whole Atmosphere Model', 1.25, -2.55, 18, MUTED)
        self.wait(1.1)
        for position in points:
            ring = Circle(radius=.16, color=GOLD, stroke_width=2).move_to(position)
            self.play(FadeIn(ring), run_time=.4)
            self.wait(5.8)
            self.play(FadeOut(ring), run_time=.4)
