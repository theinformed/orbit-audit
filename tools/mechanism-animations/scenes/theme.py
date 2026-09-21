"""
House style for the Space Environment Explorer mechanism animations.

Every colour and both typefaces here are the site's own: the palette tokens are
copied from src/styles.css (--void, --cyan, --amber, --coral, --violet, --mint)
and the fonts are the exact woff2 files the site ships in src/fonts/, converted
to TTF so Pango can see them. Nothing here is Manim's default blue-on-black.

Legibility rule, and both halves of it are measured rather than derived.

WHERE THESE PLAY. Driven in the built page: the six clips render 1060 x 596 CSS
px at a 1440 px desktop viewport and 358 x 201 on a 390 px phone. The 720 px cap
in layer-pages.css is written `.layer-page .layer-video`, and the mechanism
library is not a `.layer-page`, so it kept the full 1060 - worth knowing before
quoting a caption size in CSS pixels, because the desktop figure is 47% larger
than the layer pages would suggest.

WHAT A font_size IS WORTH. Not pixels: measured through Pango, a capital at
font_size N stands about N * 1.36 px tall in the 1080-line master. FS_CAPTION
(34) is therefore a 46 px cap in the master, 25.6 CSS px at 1060 and 8.6 CSS px
at 358. The PHONE is the binding case and 8-9 px of cap height is the floor;
the desktop end has room to spare at any size the phone can take. Anything
below the floor is decoration, and is treated as decoration - never as
something the reader is required to read. The old note here did the arithmetic
as if font_size were pixels, and so understated every size in this file by
about a third.
"""

import numpy as np
from manim import *

# ----------------------------------------------------------------- palette
VOID        = "#02070c"
SURFACE     = "#020a10"
SURFACE_2   = "#05131d"
SURFACE_3   = "#09202b"
TEXT        = "#edf8fb"
MUTED       = "#8da8b3"
LINE        = "#2b4a57"   # opaque stand-in for rgba(132,194,214,.18) on --void
LINE_STRONG = "#3f6b7a"
CYAN        = "#29d4e3"
CYAN_BRIGHT = "#5ce8f1"
AMBER       = "#f5c96a"
CORAL       = "#ff7b78"
VIOLET      = "#a98cff"
MINT        = "#76e6a5"

# ----------------------------------------------------------------- type
SANS = "Inter"
SANS_SB = "Inter SemiBold"
MONO = "IBM Plex Mono"
MONO_SB = "IBM Plex Mono SemiBold"

FS_TITLE   = 62
FS_SUB     = 40
FS_CAPTION = 34   # ONE size, every caption, every clip. Never scaled.
FS_LABEL   = 40
FS_SMALL   = 32
FS_KICKER  = 26
FS_MARK    = 21

# ----------------------------------------------------------------- geometry
TOP_RULE_Y    = 3.30
KICKER_Y      = 3.56
BOTTOM_RULE_Y = -2.46
MARK_Y        = -3.84
HALF_W        = 7.111

# THE CAPTION BAND: ONE SIZE, AND SPACE RESERVED FOR IT.
#
# Every caption in every clip is set at FS_CAPTION and nothing scales it. A
# sentence too wide for one line takes a SECOND LINE at the same size; it never
# takes a smaller type size.
#
# What this replaced picked between three sizes depending on how long the
# sentence was - 44 pt if it fitted, 36 pt if shrinking it by 18% made it fit,
# 32 pt on two lines otherwise - so 62 of the 79 captions in scripts/ came out
# at something other than the nominal size, and the type visibly changed size
# from beat to beat. That variance is what read as untidy, and it is the thing
# being removed here.
#
# READ THE HISTORY BEFORE MAKING THIS SMALLER. The pass before the three-size
# rule shrank captions without any limit, and the longest line in the library
# came out at about 17 pt - 3 CSS px on a phone, which is not type. 34 is above
# the 32 pt that rule settled on for its wrapped lines and below the 44 pt it
# used for short ones, so nothing in the library is now set smaller than
# something already was, and the largest have come down by 23%.
#
# The band is now RESERVED rather than negotiated. At one constant size the
# vertical room a caption can ever want is a known number: measured over all 79
# captions in scripts/, none needs three lines, so the worst case is two lines
# plus one CAPTION_LINE_BUFF. Measured, not idealised - the figures below are
# the real longest caption, not a full-ascender-and-descender stand-in.
#
#   line box at 34 pt   0.456 u   (61.6 px of a 1080-line frame)
#   worst real block    1.022 u   (138.0 px)   two lines, HF t=47.13
#   band                1.130 u   (152.5 px)   7.3 px clear at each end
#
# The band is cut to that, the bottom rule sits above it, and the diagrams are
# drawn to stay above the rule. Keeping the caption and the picture apart is a
# layout property, not something checked frame by frame. Opening the band cost
# the picture area 22 px at the bottom, which is why scene_01's nose inset,
# scene_02's legend and scene_03's ground curve moved up with the rule: they
# were the only three things in the library reaching that far down.
CAPTION_MAX_W     = 12.9
CAPTION_LINE_BUFF = 0.10
CAPTION_BREAK_AT_PUNCT = 0.55   # units of imbalance forgiven to break at a stop
CAPTION_BAND_TOP  = BOTTOM_RULE_Y - 0.05
CAPTION_BAND_BOT  = MARK_Y + 0.20     # 0.06 u of air above the evidence stamps
CAPTION_BAND_H    = CAPTION_BAND_TOP - CAPTION_BAND_BOT
CAPTION_BAND_MID  = (CAPTION_BAND_TOP + CAPTION_BAND_BOT) / 2


def kicker(s, color=CYAN):
    """The site's section kicker: mono, uppercase, widely tracked."""
    return Text(s.upper(), font=MONO_SB, font_size=FS_KICKER, color=color).set_opacity(0.92)


def label(s, color=TEXT, size=FS_LABEL, mono=False, weight_semi=True):
    f = (MONO_SB if weight_semi else MONO) if mono else (SANS_SB if weight_semi else SANS)
    return Text(s, font=f, font_size=size, color=color)


def clear_of(mob, *others, direction=RIGHT, gap=0.24, limit=7.0, step=0.05):
    """Slide `mob` along `direction` until its box clears every one of `others`.

    Two labels laid out independently and landing in the same place is the
    commonest way a frame in this library ends up messy, and it is INVISIBLE in
    the source: each `move_to` reads perfectly well on its own, and the
    collision only exists in the composition. Three of the four text-on-text
    collisions this library shipped with were exactly that shape.

    So a label gets positioned where it belongs and is then told what it must
    not touch, rather than being nudged by hand to a number that stops being
    right the next time the sentence changes length.

    Returns `mob` so it can be used inline. If nothing within `limit` clears,
    the label is left where it was and a warning is printed -- a silently
    relocated label off the edge of the frame would be worse than the overlap.
    """
    others = [o for o in others if o is not None]
    if not others:
        return mob

    def hits(m):
        ml, mr = m.get_left()[0] - gap, m.get_right()[0] + gap
        mb, mt = m.get_bottom()[1] - gap, m.get_top()[1] + gap
        for o in others:
            if (ml < o.get_right()[0] and mr > o.get_left()[0]
                    and mb < o.get_top()[1] and mt > o.get_bottom()[1]):
                return True
        return False

    if not hits(mob):
        return mob
    unit = np.array(direction, dtype=float)
    n = np.linalg.norm(unit)
    if n == 0:
        return mob
    unit = unit / n
    moved = 0.0
    while moved < limit:
        mob.shift(unit * step)
        moved += step
        if not hits(mob):
            return mob
    mob.shift(-unit * moved)
    print(f"clear_of: could not clear within {limit} units; left in place")
    return mob


def hairline(y, width=13.6, color=LINE):
    return Line([-width / 2, y, 0], [width / 2, y, 0], stroke_width=1.4, color=color)


def corner_mark(text="SCHEMATIC · ILLUSTRATION OF MECHANISM"):
    """Bottom-left evidence stamp. Clamped so it can never run into the URL
    on the other side - that collision is invisible in source and obvious on
    screen, so it is prevented here rather than checked per scene."""
    t = Text(text, font=MONO, font_size=FS_MARK, color=MUTED).set_opacity(0.62)
    limit = 2 * HALF_W - 0.84 - 5.10
    if t.width > limit:
        t.scale(limit / t.width)
    t.move_to([-HALF_W + 0.42 + t.width / 2, MARK_Y, 0])
    return t


def site_mark():
    t = Text("sean.theinformed.org/space", font=MONO, font_size=FS_MARK, color=MUTED).set_opacity(0.45)
    t.move_to([HALF_W - 0.42 - t.width / 2, MARK_Y, 0])
    return t


class MechanismScene(Scene):
    """
    Common shell: dark ground, a title card, a captioned body, an end card.

    Subclasses set TITLE / KICKER / SUB / TAKEAWAY and implement body().
    The caption band is the only text the reader is required to follow, so it
    holds one short line at a time and never competes with the diagram.
    """

    TITLE = ""
    KICKER = ""
    SUB = ""
    TAKEAWAY = ""
    MARK = "SCHEMATIC · ILLUSTRATION OF MECHANISM"

    def setup(self):
        self.camera.background_color = VOID
        self._caption = None
        self._script = []          # (seconds, caption) - the narration timing map

    def _log(self, text):
        """Record when a caption becomes readable, for narration alignment.

        The swap animation runs 0.45 s, so the new line is legible at about
        0.30 s in; that is the instant a voice should start saying it.
        """
        self._script.append({"t": round(float(self.time) + 0.30, 3), "text": text})

    # -------------------------------------------------- caption band
    _WIDTH_CACHE = {}

    @classmethod
    def _text_w(cls, s):
        """Width of `s` at the caption size. Cached: balancing a line asks for
        every possible split, and a Text object is a Pango render each time."""
        if s not in cls._WIDTH_CACHE:
            cls._WIDTH_CACHE[s] = Text(s, font=SANS, font_size=FS_CAPTION).width
        return cls._WIDTH_CACHE[s]

    @classmethod
    def _caption_lines(cls, s):
        """Break one caption into lines, BALANCED rather than greedy.

        Greedy wrapping fills line one to the limit and drops what is left onto
        line two, so a sentence 3% too wide for one line has exactly one word
        to give and strands it. That happened to 20 of the 49 captions in this
        library that need two lines: measured, greedy left the two lines up to
        11.6 units apart in width, and balancing leaves at most 1.9. Same text,
        same size, same number of lines - it stops looking like an accident.

        The break is chosen to make the wider line as narrow as possible, with
        CAPTION_BREAK_AT_PUNCT units of that forgiven for a break that lands on
        a full stop, comma or dash. 13 of the 49 come out cut where the sentence
        is already punctuated; pure width-balance finds 10 of those on its own
        and the forgiveness earns the other three, of which the clearest is
        "At the top: light, but no air. At | the bottom: air, but no light."
        becoming "At the top: light, but no air. | At the bottom: air, but no
        light." Three captions is a small return for six lines of code, and it
        is kept because those three are the ones a reader would notice.

        Falls back to greedy for anything two lines cannot hold. Nothing in the
        library reaches that, and if a future caption does, say() will print a
        band overflow rather than silently resize it.
        """
        if cls._text_w(s) <= CAPTION_MAX_W:
            return [s]
        words = s.split()
        best = None
        for i in range(1, len(words)):
            a, b = " ".join(words[:i]), " ".join(words[i:])
            wa, wb = cls._text_w(a), cls._text_w(b)
            if wa > CAPTION_MAX_W or wb > CAPTION_MAX_W:
                continue
            score = max(wa, wb)
            if a.endswith((".", ",", ";", ":", "!", "?", "\u2014", "\u2013")):
                score -= CAPTION_BREAK_AT_PUNCT
            if best is None or score < best[0]:
                best = (score, [a, b])
        if best is not None:
            return best[1]
        lines, cur = [], ""
        for x in words:
            trial = (cur + " " + x).strip()
            if cls._text_w(trial) > CAPTION_MAX_W and cur:
                lines.append(cur)
                cur = x
            else:
                cur = trial
        if cur:
            lines.append(cur)
        return lines

    def say(self, s, hold=0.0, color=TEXT):
        """Replace the caption line. `hold` waits after the swap.

        ONE SIZE, ALWAYS. Every caption is FS_CAPTION. A sentence too wide for
        CAPTION_MAX_W takes a second line at the same size, broken where the
        two lines come out closest in width (see _caption_lines); nothing here
        picks a smaller size to make a long sentence fit. The rule this replaced had
        three sizes and chose between them per caption, so the type changed
        size from beat to beat -- a reader watching the six clips saw 62 of the
        79 captions set at something other than the nominal size. The caption
        is the one thing the reader is required to read, so it looks the same
        every time and sits in the same place every time.

        THE BAND IS RESERVED, NOT NEGOTIATED. CAPTION_BAND_* is cut to hold the
        tallest block this library can produce, and the six diagrams are laid
        out to stay above the bottom rule, so the caption and the picture
        cannot meet. The clamp below is a backstop for a caption longer than
        anything now in scripts/, and it SAYS SO rather than quietly shrinking
        the type back to the variance this change removed. It does not fire on
        any of the 79 captions in the library.

        THE SWAP IS SEQUENTIAL, NOT A CROSS-DISSOLVE. FadeOut(old) and
        FadeIn(new) played together put two different sentences in the same
        place at half opacity each, and for about a quarter of a second the
        caption band was an unreadable smear. It happened on EVERY caption
        change in all six pieces -- 85 times -- and it is what "the text is
        overlapping so it looks messy" was mostly describing. The old line
        leaves first and the new one arrives after it has gone. The total is
        still 0.45 s and the new line is still legible 0.30 s in, so every
        caption timestamp in scripts/<Scene>.json is unchanged and the
        narration alignment does not move.
        """
        lines = self._caption_lines(s)
        new = Text(lines[0], font=SANS, font_size=FS_CAPTION, color=color)
        if len(lines) > 1:
            new = VGroup(*[Text(l, font=SANS, font_size=FS_CAPTION, color=color)
                           for l in lines]).arrange(DOWN, buff=CAPTION_LINE_BUFF)
        if new.width > CAPTION_MAX_W + 0.01 or new.height > CAPTION_BAND_H:
            print("say: CAPTION OVERFLOWS THE RESERVED BAND -- clamped, which "
                  "means this one caption is a different size from every other "
                  "one. Shorten it, or open the band. "
                  f"w={new.width:.2f}/{CAPTION_MAX_W} "
                  f"h={new.height:.2f}/{CAPTION_BAND_H:.2f}: {s!r}")
            if new.width > CAPTION_MAX_W:
                new.scale(CAPTION_MAX_W / new.width)
            if new.height > CAPTION_BAND_H:
                new.scale(CAPTION_BAND_H / new.height)
        new.move_to([0, CAPTION_BAND_MID, 0])
        self._log(s)
        if self._caption is None:
            self._caption = new
            self.play(FadeIn(new, shift=UP * 0.12), run_time=0.45)
        else:
            old = self._caption
            self._caption = new
            self.play(FadeOut(old, shift=UP * 0.12), run_time=0.15)
            self.play(FadeIn(new, shift=UP * 0.12), run_time=0.30)
        if hold:
            self.wait(hold)

    def clear_caption(self):
        if self._caption is not None:
            self.play(FadeOut(self._caption), run_time=0.3)
            self._caption = None

    # -------------------------------------------------- cards
    def title_card(self, hold=1.9):
        k = kicker(self.KICKER)
        t = Text(self.TITLE, font=SANS_SB, font_size=FS_TITLE, color=TEXT)
        if t.width > 12.4:
            t.scale(12.4 / t.width)
        s = Text(self.SUB, font=SANS, font_size=FS_SUB, color=MUTED)
        if s.width > 12.0:
            s.scale(12.0 / s.width)
        badge = self._badge()
        g = VGroup(k, t, s).arrange(DOWN, buff=0.42).move_to([0, 0.55, 0])
        rule = hairline(g.get_bottom()[1] - 0.55, width=5.0, color=CYAN).set_opacity(0.5)
        badge.next_to(rule, DOWN, buff=0.55)
        self.play(FadeIn(k, shift=UP * 0.2), run_time=0.5)
        self.play(FadeIn(t, shift=UP * 0.2), run_time=0.6)
        self.play(FadeIn(s), Create(rule), run_time=0.5)
        self.play(FadeIn(badge), run_time=0.45)
        self.wait(hold)
        self.play(FadeOut(VGroup(k, t, s, rule, badge)), run_time=0.55)

    def _badge(self):
        chip = Text("SCHEMATIC", font=MONO_SB, font_size=28, color=VOID)
        box = RoundedRectangle(
            corner_radius=0.07, width=chip.width + 0.5, height=chip.height + 0.34,
            fill_color=AMBER, fill_opacity=1.0, stroke_width=0,
        )
        chip.move_to(box.get_center())
        # Two lines, and the second one is borrowed deliberately. The Quebec
        # 1989 GIC schematic in tools/manim/ badges itself "no part of this is
        # footage"; a reader who meets both pieces on this site should meet one
        # vocabulary, not two. The corner stamp stays short because it has to
        # share the bottom rule with the site URL; this is where there is room
        # to say it at full size.
        meaning = VGroup(
            Text("Drawn to explain a shape, not to report a value.",
                 font=SANS, font_size=30, color=MUTED),
            Text("No part of this is footage.", font=SANS, font_size=30, color=MUTED),
        ).arrange(DOWN, buff=0.10, aligned_edge=LEFT)
        g = VGroup(VGroup(box, chip), meaning).arrange(RIGHT, buff=0.38)
        if g.width > 12.0:
            g.scale(12.0 / g.width)
        return g

    def frame_chrome(self):
        """The persistent furniture during the body of the piece."""
        k = kicker(self.KICKER)
        k.move_to([-HALF_W + 0.42 + k.width / 2, KICKER_Y, 0])
        chrome = VGroup(
            k, hairline(TOP_RULE_Y), hairline(BOTTOM_RULE_Y),
            corner_mark(self.MARK), site_mark(),
        )
        self.play(FadeIn(chrome), run_time=0.5)
        return chrome

    def end_card(self, hold=2.4):
        t = Text(self.TAKEAWAY, font=SANS_SB, font_size=48, color=TEXT)
        if t.width > 12.0:
            t = self._wrap(self.TAKEAWAY, 48, SANS_SB, TEXT, 11.6)
        t.move_to([0, 0.35, 0])
        rule = hairline(t.get_bottom()[1] - 0.6, width=3.4, color=CYAN).set_opacity(0.55)
        mark = Text(self.MARK, font=MONO, font_size=26, color=MUTED).set_opacity(0.6)
        mark.next_to(rule, DOWN, buff=0.5)
        self.play(FadeIn(t, shift=UP * 0.15), run_time=0.6)
        self.play(Create(rule), FadeIn(mark), run_time=0.45)
        self.wait(hold)
        self.play(FadeOut(VGroup(t, rule, mark)), run_time=0.6)

    @staticmethod
    def _wrap(s, size, font, color, max_w, buff=0.28):
        words, lines, cur = s.split(), [], ""
        for w in words:
            trial = (cur + " " + w).strip()
            if Text(trial, font=font, font_size=size).width > max_w and cur:
                lines.append(cur)
                cur = w
            else:
                cur = trial
        if cur:
            lines.append(cur)
        return VGroup(*[Text(l, font=font, font_size=size, color=color) for l in lines]).arrange(DOWN, buff=buff)

    # -------------------------------------------------- entry point
    def construct(self):
        self.title_card()
        self.body()
        self.end_card()
        self._dump_script()

    def _dump_script(self):
        import json, os
        out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scripts")
        os.makedirs(out, exist_ok=True)
        path = os.path.join(out, f"{type(self).__name__}.json")
        with open(path, "w") as fh:
            json.dump({"scene": type(self).__name__,
                       "duration": round(float(self.time), 3),
                       "lines": self._script}, fh, indent=1)

    def body(self):
        raise NotImplementedError
