# Mechanism animations

Six short Manim pieces for the Learn side of the space explorer: the steps the
site had been asserting in words because no camera has filmed them.

    01  dayside-reconnection   How the wind gets in
    02  chapman-layer          Why the ionosphere has a peak
    03  hf-skip-blackout       The skip, the MUF, and the blackout
    04  trapped-motion         Three motions, and one current
    05  eccentric-dipole-saa   The South Atlantic Anomaly is geometry
    06  drag-orbit-decay       Drag makes it go faster

The manifest that puts them on the page is `src/mechanism-animations.ts`. The
rendered assets are `media/mechanisms/<stem>.mp4` and `<stem>.jpg`.

## Where Manim lives

**These render on bigmem-PC.** Manim renders are CPU-heavy and that is the
machine with the cores; the VPS should not be doing this work.

    /home/sdegan/manimenv/bin/manim -r 1920,1080 --fps 30 --disable_caching \
      --media_dir ~/space-manim-render/iso-Reconnection \
      scene_01_reconnection.py Reconnection

Manim Community v0.20.1 in `/home/sdegan/manimenv`, with ffmpeg present. None of
these six scenes uses LaTeX, so no TeX install is needed. The OpenClaw gateway
container on the VPS still has Manim and remains a fallback; it is no longer the
only place, and `package.sh`'s defaults now point at bigmem.

### Give every concurrent render its OWN `--media_dir`

Rendering all six at once into one `--media_dir` **fails**, and it fails in a way
that looks like a Manim bug rather than a mistake:

    FileNotFoundError: .../texts/ea34bc374716e4ad_.svg

`--media_dir` contains a shared `texts/` directory where Manim writes one SVG per
distinct string. Two scenes rendering the same string at the same time write the
same filename, and whichever finishes first unlinks it out from under the other.
Two of six died this way. `--disable_caching` does not help: the collision is in
the intermediate SVG, not in the partial-movie cache. One media dir per scene.

## The two typefaces

The frames are set in the site's own Inter and IBM Plex Mono — literally the
woff2 files from `src/fonts/`, converted to TTF so Pango can see them, because
fontconfig cannot load woff2. `make_fonts.py` does the conversion; it needs
`fontTools` and `brotli`, which are installed to a temp prefix rather than into
the container's system Python:

    /home/sdegan/manimenv/bin/pip install brotli fonttools
    /home/sdegan/manimenv/bin/python make_fonts.py     # writes ttf/
    cp ttf/*.ttf ~/.local/share/fonts && fc-cache -f ~/.local/share/fonts

`make_fonts.py` reads `src/fonts/` and writes `scenes/ttf/` by default, both
resolved from its own location, with `FONT_SRC` / `FONT_OUT` overrides. It used
to be hardcoded to `/home/node/...` inside the gateway container, which is why
it ran in exactly one place. `fc-list | grep -iE "inter|plex"` must show the
four families `theme.py` names -- `Inter`, `Inter SemiBold`, `IBM Plex Mono`,
`IBM Plex Mono SemiBold` -- or Pango silently substitutes and every measurement
in the layout is wrong.

## House style

`theme.py` holds the palette (copied from the tokens in `src/styles.css`), the
type scale, and `MechanismScene` — the shell that draws the title card, the
caption band, the corner evidence stamp and the end card. `parts.py` holds the
drawing primitives: field lines with arrowheads, Earth, Shue magnetopause,
dipole arcs.

**A caption is wrapped, never shrunk, and captions never cross-dissolve.**
`say()` used to scale a long line down to fit the band -- the longest lines
landed at about 73%, caption size visibly changed from beat to beat, and at that
size they fell under the floor this section sets. It now takes a second line at
full size. It also used to play `FadeOut(old)` and `FadeIn(new)` together, which
put two different sentences in the same place at half opacity for a quarter of a
second, on every one of the 85 caption changes in the library. The swap is
sequential now. Both changes keep the total at 0.45 s and the legibility instant
at 0.30 s, so no caption timestamp moved and the narration alignment did not
have to be touched.

**`clear_of()` is in `theme.py` for the collisions the source cannot show you.**
Two labels laid out independently and landing in the same place is the commonest
way a frame here ends up messy, and each `move_to` reads perfectly well on its
own -- the collision exists only in the composition. Position a label where it
belongs, then tell it what it must not touch.

**The type is large on purpose.** These play in a content column about 350 CSS
px wide on a phone, so a 16:9 frame lands near 197 CSS px tall; a label at
font_size N in a 1080-line frame is about N × 197/1080 CSS px there. CAPTION is
44 (≈8 px on a phone) and LABEL is 40 (≈7.3 px). That is the floor. Anything
smaller is decoration and is treated as decoration.

## Honesty

Every frame carries `SCHEMATIC` in the bottom-left corner as well as in the
figcaption, so the evidence class survives being screenshotted. Where a piece
carries a real number it names the source on the frame and in the manifest:

* **Chapman** evaluates Chapman's 1931 production function live rather than
  tracing a curve. The scale height and reference altitude are illustrative.
* **Eccentric dipole** uses this repository's own arithmetic — IGRF-13
  degree-1 and degree-2 coefficients through Fraser-Smith (1987), the same
  method as `src/eccentric-dipole.ts`. For 2026.6 that is an offset of 610 km
  toward 22.7°N 134.7°E, whose antipode is 22.7°S 45.3°W.
* **Drag** quotes circular-orbit arithmetic on μ = 398 600 km³/s².

`trapped-motion` deliberately draws the drift paths as circles and says so on
the frame. It asserts no local-time asymmetry, because the real Alfvén-layer
shape is energy-dependent and the explorer's inner-magnetosphere layer is where
that is computed.

## Encoding

    ffmpeg -i master.mp4 -c:v libx264 -crf 29 -preset slower -tune animation \
           -profile:v high -pix_fmt yuv420p -movflags +faststart -an out.mp4

`-tune animation` for flat colour and thin bright strokes on black; checked at
1:1 on a text-heavy frame for mosquito noise. About a third the size of Manim's
own output. `package.sh` does this and cuts each poster.

## Timing marks

`media/mechanisms/<stem>.marks.json`, one section per visual beat, in the same
shape as `media/quebec-1989-gic-chain.marks.json`. Written by `emit_marks.py`
from `scripts/<Scene>.json` -- the render's own clock -- and by `package.sh` in
the same run that produces the clips, so a clip and its marks cannot be
published out of step. `emit_marks.py --check` re-derives and fails if any file
on disk is stale. The title and end cards are parsed out of the scene source
rather than copied into a table, because a copied title is how a marks file ends
up describing a card the clip no longer shows.

## Narration

Sean's own voice, muxed into each mp4. `tools/narrate.py` renders it, this
directory aligns it, and `narrate_mux.py` lays it on.

```bash
python3 tools/narrate.py narration/mechanisms.json \
        --outdir media/mechanisms/narration --dry-run   # lint only, spends nothing
python3 tools/narrate.py narration/mechanisms.json --outdir media/mechanisms/narration
SRC=… OUT=… SCRIPTS=… AUDIO=media/mechanisms/narration \
SCRIPT_JSON=narration/mechanisms.json bash package.sh
```

### The rule the writing follows

> Say the point the caption is making, then extend it with what the caption had
> no room for.
>
> **And carry the last line's idea into this one, by name.**

The second half was added 2026-08-27, after Sean rejected all six clips on the
WRITING rather than the audio: *"the content is just weird. it is cringy. There
isn't any flow in the things that I'm saying. Nothing has a good transition. I'm
not talking like a person that is speaking to an audience about what is happening
before their eyes. It is like I'm basically reading bullet points."*

The lane had one line per caption beat — 44 lines, median 152 characters, each
pinned to its own beat. Read in order, a scene came out as labels with verbs:
"The nose is where the two fields are pressed hardest together." / "This is the
quiet case." / "This is the only door." Nothing could carry, because each line
was written to sit under one beat and stop.

Québec — same voice, same model, same renderer, and the clip Sean calls amazing —
is 7 lines, median 205 characters, and every line picks up the last one by name:
"...a few volts per kilometre." → "Multiply a few volts per kilometre by a few
hundred kilometres..." → "That current is nearly direct...". One person telling
one story.

So: **fewer lines, each longer, each anchored to the caption where its THOUGHT
starts** rather than to every caption it plays over. A line is allowed to run
across three captions; the muxer only refuses a line still talking when the next
LINE starts. All six scenes are written this way now — `hf-skip-blackout` first,
on 2026-08-27, and the other five the same night:

| Scene | Lines | Median chars | Chars per second of clip |
|---|---|---|---|
| Reconnection | 7 | 183 | 14.8 |
| Chapman | 6 | 187 | 15.1 |
| HF | 6 | 197 | 14.4 |
| Trapped | 6 | 170 | 15.1 |
| SAA | 5 | 168 | 14.9 |
| Drag | 10 | 203 | 15.1 |

`drag-orbit-decay` is the pilot for `docs/PLAN-video-expansion.md` and is the
only one rewritten so far — see **The expansion pass** below. The other five are
as they were.

Québec is 14.2 and the rejected lane was 4.6. The five run a shade denser than
Québec on purpose: these clips carry long stretches with no caption on them at
all, and `drag-orbit-decay` had 8.8 seconds of unbroken silence in the middle of
it. The script is also **grouped by scene and stored in spoken order**, because
`narrate.py` starts a new stitching chain wherever `scene` changes from one line
to the next; interleaved scenes gave one clip several short chains.

**The two halves of the library are deliberately rendered at different voice
settings.** HF is 0.45/0.80 with the rewritten script; the other five are
0.62/0.75, the settings Sean chose in a blind pairwise tournament. That is the
A/B: HF isolates the WRITING change and the other five add the delivery change
on top of it. Re-rendering HF for consistency destroys the comparison and
re-bills 1 136 characters, so it is not done without being asked.

That is Québec's pattern, and Québec is the clip that works. The voice and the
caption agree; the voice never contradicts one and never reads one back flat.
Where the caption states the physics, the extension is the operational
consequence, the timescale, the uncertainty, or the limit of the drawing.

**The opposite rule used to be written here, and it is retired.** It read: *the
captions are burned into the frame and they are good, so the voice never reads
them; the rest is silence on purpose.* It was followed exactly, and it produced
fifteen lines for seventy-nine caption beats. Measured on the delivered files,
speech covered 18 to 37 percent of each clip and the voice first arrived 40.8 s
into a 79.1 s clip, 36.6 s into 66.0 s, and 35.4 s into 60.5 s. Sean watched one
and reported his voice missing from the videos. Nothing was broken; the design
was wrong. Québec runs 14.2 characters of narration per second of clip against
this lane's old 4.6.

Do not reinstate it. If a beat has nothing worth saying, the answer is a shorter
clip, not a silent one. Measure any change here with
`python3 tools/narration-coverage.py --table media/mechanisms/*.mp4` and compare
against Québec: 0.00 s onset, 76.9 percent speech.

**Captions stay.** Sean asked whether they were still needed. They are the
accessibility floor for a deaf reader, they are what makes a clip work with the
sound off, and they survive a screenshot because they are burned in.

`tools/narrate.py` will still refuse a line that opens with throat-clearing,
hedges, or runs past sixty words before it spends a character.

### The delivery used to change from line to line, and why

Sean, 2026-08-27, on all six clips: *"why does the volume and the style of my
speech change as the video progresses?... I hear myself speed up. or my pitch
will change."* And: *"I sometimes end sentences that are declarative as if they
are interrogative."*

`tools/narrate.py` issued **one independent API request per line**. No
`previous_text`, no `previous_request_ids`. The model re-picked speaking rate,
pitch contour and terminal intonation from scratch on every line, because
nothing told it there was a line before this one. That is the whole defect.

It now **stitches**: every request carries the previous few lines as
`previous_text` and the `request-id` of the previous few generations as
`previous_request_ids`, which is a handle on the actual audio and is the stronger
of the two. One chain per SCENE; the chain resets at a scene boundary, because
handing one clip's run-up to another clip's opening line is contamination, not
continuity. `next_text` is deliberately not sent — it needs the scene's script
declared up front in spoken order, and guessing at that would be worse.

Measured on this repo's own HF scene, the level ElevenLabs delivered before any
processing:

| | raw level as delivered | spread |
|---|---|---|
| 9 lines, independent requests (2026-08-26) | −29.1 to −43.8 LUFS | **14.7 dB** |
| 6 lines, stitched (2026-08-27) | −41.6 to −43.5 dB RMS | **1.9 dB** |

The two clusters in the first row are this account's known bimodal emission,
about 14 dB apart, which an unstitched chain flips between at random. The
stitched chain locked onto one mode and stayed there for all six lines. (The two
rows are different meters — integrated LUFS against mean RMS — because the older
files were levelled in place and their raw RMS is gone. The SPREADS are
comparable; the absolute numbers are not.)

**Honest limit, from the lane that measured it first (`/root/voice-notes.md`):
stitching greatly reduces this, it does not abolish it. One chain in three still
drifted mid-chain there.** The RMS levelling below is the belt to its braces, and
only Sean's ear can say whether the delivery itself now holds.

### Loudness: RMS at generation, R128 once on the mix

The lane used to run two-pass `loudnorm` **per line** in `narrate.py` and then a
second per-line `loudnorm` in `narrate_mux.py` on the way into the mix. EBU R128
integrated loudness is **gated**, and a narration line is 3 to 13 seconds long;
on the short ones the gate throws away much of the content, so loudnorm measures
the wrong input level and applies the wrong gain. Two wrong gains in series are
not more accurate than one.

Now: one **constant gain** per line to a fixed RMS target at generation (RMS has
no gate, and a constant gain moves the whole sentence rather than squashing its
dynamics), then **one** R128 pass on the assembled clip, where the audio is long
enough for R128 to be the right tool. Target −18 LUFS / −2 dBTP, matched to
`tools/manim/mux.py`, so these clips and the Québec GIC chain land together.

Measured per line INSIDE the assembled clip — which is what "my voice changes
level from sentence to sentence" actually means, and is not confounded by how
much silence falls in a fixed window:

    old  spread 2.6 dB  (−18.3 to −20.9), peaks −1.8 to −3.8
    new  spread 0.5 dB  (−17.9 to −18.4), peaks −1.9 to −2.1

`speechnorm` was tried on the sibling lane and made it worse. Do not add it.

There is also a **relative bad-take guard**: the API occasionally returns a
near-silent generation, and one shipped in this repo — the old
`mech-03-timescales.mp3` sat at −26.6 dB peak against neighbours at −1.9 dB. The
guard compares each clip's raw peak against the rolling median of the clips
already accepted and re-requests only true outliers, **reusing the same stitching
arguments** so the retry cannot silently un-stitch the line. An absolute floor is
the wrong shape and was tried: these settings legitimately peak low, so any floor
high enough to catch a dead take rejects healthy ones too.

### The first word of a line, and the repair that is NOT a re-render

Sean, 2026-08-27, on the rebuilt Drag clip: *"there is a small break in my voice
on many of the transitions. Like 'It does not slow down', or the word 'Backwards'
gets cut off. So we are sounding better but the transitions are cutting things
off."*

Both examples are the **first words of their lines**, which is why it reads as a
transition problem. It is not one. Measured on the shipped file, sample by
sample:

* every line's onset in the muxed mp4 matches its mp3 to **0.0 ms**, and a
  cross-correlation over a 3 s slice of each of the 40 lines puts the lag at
  **exactly 0 samples**;
* the assembled mix's gain is flat to within 1.5 dB end to end;
* `narrate.py`'s levelling chain (`volume` + `alimiter=limit=0.89` + a 128k mp3
  re-encode) was run against a control file with a clean head and left it alone.

The assembly was innocent. What is wrong is in the file ElevenLabs delivered: a
**stitched** generation — one carrying `previous_text` / `previous_request_ids`,
which is what makes a line continue the one before it rather than restart —
opens below its own speaking level and climbs to it. On `mech-06-brake` the
first 200 ms sat **33.6 dB down**, so the /b/ and the vowel of "Backwards" were
inaudible and the ear was handed "…wards". Across the 40-line library, **all six
lines with a soft head are stitched and none of the seven unstitched ones are**.
Stitching is still the right call — it is what fixed the drifting delivery — but
it has this cost, and it is paid at the leading edge.

**The round-trip verifier cannot see this.** `mech-06-brake` transcribes back at
similarity 1.0 with the syllable inaudible, and so does a 1.4 s window cut around
just that word: speech-to-text reconstructs a swallowed onset from context. A
verifier that says "the words are all there" is answering a different question
from "can Sean hear them". The detector that works is the level measurement in
`narrate_mux.py`, and `check_alignment.py` already agreed from the other side —
its late-onset check was failing on `mech-04-flat-frame`, `mech-04-drift` and
`mech-04-why-they-add`, three of the six soft heads, before anyone knew why.

So the repair is in the assembly and it is **gain only**:

| | |
|---|---|
| reference | the line's own speaking level over its opening 2.5 s — the words immediately after the first one, not the whole-line average, which a long quiet clause drags down |
| window | from the onset to the moment the voice first reaches that level, never longer than 0.50 s. Past the recovery the line is healthy, and a window that ran on would lift a word that never needed it |
| curve | the measured deficit, made non-increasing and smoothed over 40 ms, so it is the inverse of a fade-in rather than a compressor |
| ceiling | 26 dB. A hole deeper than that is not a soft attack, it is a take with the word missing, and the honest answer to that is a re-render |

A line that measures healthy is passed to the mix as **its own mp3, byte for
byte** — it is never decoded, corrected or re-encoded. Only a line with a
measured deficit is staged as raw f32 in a temp directory that is gone when the
run ends. Because it is gain only, **no sample moves**: the alignment report and
the phrase-to-visual sync table are untouched by construction, and not one
character is re-rendered. `narration-alignment.json` records what was done to
each line under `leadingEdge`, and the run prints the worst lift per clip.

Measured across the library, 27 of 40 lines needed something. The worst before →
after, as the mean level of the first 200 ms against the line's own speaking
level:

| line | before | after | lift |
|---|---|---|---|
| `mech-04-why-they-add` | −32.2 dB | −15.8 dB | +26.0 dB, **at the ceiling** |
| `mech-06-brake` | −27.5 dB | −6.9 dB | +25.0 dB |
| `mech-02-optical-depth` | −26.8 dB | −26.0 dB | +18.5 dB |
| `mech-06-one-speed` | −26.3 dB | −16.1 dB | +26.0 dB, **at the ceiling** |
| `mech-04-drift` | −19.6 dB | −9.5 dB | +15.8 dB |
| `mech-04-flat-frame` | −14.4 dB | −5.5 dB | +22.2 dB |

`check_alignment.py` went from 4 failures to 1 on the same six clips. A line that
comes back **at the ceiling** is the lane telling you gain has run out: it is the
one case where re-rendering that single line is the right answer, and the mux
prints it by name rather than leaving it to a reader of the JSON.

### Muxing one clip

`narrate_mux.py --scene HF` re-muxes a single clip. Sean's rule is that one clip
gets judged before six get paid for, so this has to be a first-class operation
rather than a whole-library run with five failures in it. The alignment report is
MERGED, not replaced.

The per-line filter is chosen from what the manifest says was actually done to
each mp3: RMS-levelled files pass straight through, and anything older keeps the
old per-line `loudnorm`. **As of 2026-08-27 all 36 lines in the manifest are on
the RMS path and nothing takes the else-branch** — the twelve files that carried
no levelling record at all, one of them 26 dB down, were retired with the lines
they belonged to. The branch is kept as the safe default for any file that
arrives without a levelling record; it is no longer load-bearing, and
`narration-alignment.json` records `perLine: ["aresample=44100"]` for every clip,
which is how you check that from outside.

### How the alignment works, and why nothing here is hand-timed

Each scene writes `scripts/<Scene>.json` at render time: every caption with the
second it becomes legible. Each narration line in `narration/mechanisms.json`
carries an `anchor` — the index of the caption it belongs to — and nothing else
about timing. `narrate_mux.py` reads the two together and delays each mp3 to its
caption's own timestamp.

A line may instead carry an explicit `at` second. That is for the opening line
of each clip, which is spoken over the title card and has no caption to anchor
to; the first caption on these six lands 6.1 to 10.3 s in, which used to be the
floor on how early any voice could start.

What the muxer refuses is a line still talking when the NEXT LINE starts, not
when the next caption lands. A caption window here is two to three seconds, and
enforcing that as a maximum line length is what kept this lane writing fragments
and leaving the rest of the clip silent. Captions changing mid-sentence is
normal and is what Québec does on every one of its seven lines.

That means the picture stays the authority. Change a `hold=` in a scene,
re-render, and the audio follows without being touched.

Eight `hold=` values were widened to make room, which is the only change the
voice forced on the pictures:

| Scene | Was | Now | Runtime |
|---|---|---|---|
| Reconnection | 1:18 | 1:27 | +11.3 % |
| Chapman | 1:03 | 1:09 | +9.4 % |
| HF | 1:15 | 1:19 | +4.5 % |
| Trapped | 1:03 | 1:11 | +11.4 % |
| SAA | 1:00 | 1:00 | unchanged |
| Drag | 1:03 | 1:06 | +4.9 % |

`SAA` needed none: both of its lines already fitted the gaps that were there.
`Drag` was then rebuilt again on 2026-08-27 and now runs **2:10** — see below.

### The expansion pass, and how a hold gets its number

Sean, 2026-08-27, on the delivered six: *"The timing needs to be checked on the
videos. For example, the X rays going down to the D layer happen long before my
voice talks about it."* And, on scope: the clips must *"cover the entire concept
... so that the video sort of stands alone"*, in the shape *"introduction of the
topic, then explanation, then some sort of wrap up"*.

`docs/PLAN-video-expansion.md` is the approved plan for all six.
**`drag-orbit-decay` is the pilot and the only one done.** It went from 6 lines
and 1:06 to 10 lines and 2:10, and the numbers in `scene_06_drag.py` are not
taste:

1. **Render the narration first, then cut the picture to it.** Line lengths are
   whatever ElevenLabs delivers, so a hold guessed before the audio exists is a
   guess. The order is narrate → measure → set holds → render once.
2. **Measure WORD times, not characters per second.** The speech-to-text pass
   `narrate.py` already makes for verification returns a start and an end for
   every word. Ask for `timestamps_granularity=word` and the beat spacing can be
   cut to a clause: the −1 bar lands at *"one unit out"*, the −2 at *"worth
   two"*, the +1 at *"into speed"*, the equation card at *"the equation closes
   the case"*, the REENTRY label at *"all the way to reentry"*.
3. **The scene clock is predictable to the frame, so this can be solved on
   paper before anything renders.** A `play` consumes `ceil(run_time × fps)`
   frames and a static `wait` consumes `floor(duration × fps)` — the two differ,
   and `hold=5.31` is exactly where they differ. A simulator built on that rule
   reproduced this scene's twelve caption times and its 130.267 s duration with
   zero disagreement, which is what let the whole timing be designed offline and
   rendered once instead of iterated.
4. **A hold on an orbit is a lap, not a freeze.** The satellite is an
   `always_redraw` on a ValueTracker, so `wait()` hangs it motionless in space.
   Where the orbit is the subject, `Drag.spin()` buys the time by letting it keep
   going round at the pace it was already going.

**A drawn visual with no caption cannot be narrated.** A narration line names a
caption `anchor`, so anything the scene draws without a `say()` has nothing for a
line to hang on — and in this scene there were two: the along-track ops block and
the geomagnetic-storm note, both of which the voice had therefore never mentioned
in a clip that talks the whole way through. The plan caught the storm note; the
ops block turned up during implementation. Both are fixed the same way, and the
way matters: **the headline each block already carried became the caption**, so
the beat exists without a word being added to the frame or said twice on it.
Adding captions at the END of a scene shifts no earlier anchor; adding one in the
middle shifts every index after it, so re-check the anchors after any insertion.

### Muxed, not served alongside

The audio goes into the mp4. One file means the transport bar scrubs picture and
voice together, a download carries the voice with it, and there is no second
request to fail. The video stream is encoded once, silent, and
`narrate_mux.py` copies it through with `-c:v copy` — so re-timing the narration
never re-encodes a frame and never costs picture quality.

The mp3s under `media/mechanisms/narration/` are **build inputs**. Nothing
imports them, so Vite never emits them and the page never fetches them; they are
in the repository so that a re-mux costs nothing, since narration bills per
character.

The clips are no longer `muted` and no longer `loop`. A muted narration is not a
narration, and a voice track that restarts forever is an irritation.

### What a reader who cannot hear loses

Nothing that was there before — the captions are still burned into every frame.
But everything the voice adds is by construction *not* on the frame, so the
spoken lines are also carried in `src/mechanism-animations.ts` as `narration`
and printed under each figure inside a disclosure that lands closed.

## The Dst trace in `trapped-motion`

The first version of that scene ended on a curve that **looked** like a storm and
was derived from nothing: a closed-form exponential, hand-tuned until the shape
read right. Every other number in this library is either computed from a named
formula or absent. A drawn curve that implies a measurement it is not is the one
thing this site may never do, so it was replaced rather than defended.

It is now 120 hourly points of **final Dst from the World Data Centre for
Geomagnetism, Kyoto**, covering the Halloween storm of 2003 — 28 October to
2 November, minimum −383 nT at 30 October 22 UT. The double minimum on the frame
is the real one; the invented curve had a single smooth dip and could not have
shown it.

The points are read from `dst_halloween_2003.json`, which is extracted from this
site's **own published artifact** — the `dst` lane of the `halloween-2003`
replay, one of the three traces the historical-events page already draws. Not a
fresh fetch: the animation and the page cannot drift apart, and the render needs
no network.

Two rules govern how it is drawn:

* **`set_points_as_corners`, never `set_points_smoothly`.** A spline through
  hourly samples draws excursions that were never recorded.
* **It is badged `MEASUREMENT` on the frame,** in the site's own evidence
  vocabulary, because everything else in the animation is drawn and the reader
  has to be able to tell which is which without reading the caption.

## Two Manim lanes, and why they were left as two

There are two Manim lanes in this repository:

| | `tools/manim/` | `tools/mechanism-animations/` |
|---|---|---|
| Piece | Québec 1989 GIC chain | the six mechanisms |
| Frame | 1280×720 | 1920×1080 |
| Type | IBM Plex Mono only | Inter for prose, Plex Mono for chrome |
| Caption floor | `-2.55`, reserved above the player's control bar | `-3.10` |
| Background | `config.background_color` at module import | per scene, in `setup()` |
| Narration | audio-first: the picture is padded to the measured line | picture-first: the line is fitted to the caption |
| Evidence badge | once, on the end card | burned into every frame |

Merging them was scoped and **deliberately not done**. The reasons, in order of
weight:

1. **The narration contracts are inverted.** `gic_chain.py` reads measured audio
   durations at render time and pads each section to its line. `MechanismScene`
   dumps caption times at render time and the voice is fitted afterwards. These
   are not two implementations of one idea; merging the shells means choosing
   one and re-rendering the loser.
2. **`parts.py` is not the shared module it looks like.** It holds
   magnetospheric geometry — Shue magnetopause, dipole shells, field lines with
   arrowheads, an Earth disc. `gic_chain.py` draws a power grid, a transformer
   core, a harmonic spectrum and a voltage collapse. There is no primitive in
   `parts.py` it can use.
3. **The two type scales are tuned to different frame heights,** and the whole
   legibility argument in this README is arithmetic on 1080 lines. Re-hosting a
   720-line scene under it changes every size on the frame.
4. **The two disagree about where the bottom of the frame is,** and
   `gic_chain.py`'s answer — leave room for the browser's own control bar — is
   the better-reasoned one. That is worth adopting on its merits, not smuggling
   in as part of a move.

What genuinely duplicates is the palette: both files carry the same six hex
values, typed twice. That is the merge worth doing, and it is one small module —
but it should be done when nothing is mid-flight, because at the time this was
written a `manim … gic_chain.py GicChain` process was live in the container and
that lane was still being iterated.
