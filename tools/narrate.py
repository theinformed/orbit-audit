#!/usr/bin/env python3
"""
Space Environment Explorer — narration lane.

Turns a JSON script into narrated MP3s in Sean's own cloned voice, verifies every
file by transcribing it back, and writes a manifest the site can read.

    python3 tools/narrate.py narration/script.json
    python3 tools/narrate.py narration/script.json --dry-run    # lint only, no spend
    python3 tools/narrate.py narration/script.json --force      # re-render unchanged lines

WHY IT WORKS THIS WAY
---------------------
1. It is IDEMPOTENT. Each line's text + voice + model is hashed. A line whose hash
   already appears in the manifest is skipped, so re-running costs nothing. Narration
   is billed per character; a pipeline that silently re-renders everything on every
   run is a pipeline that quietly spends money.

2. It VERIFIES. Every rendered file is transcribed back through speech-to-text and
   compared, word by word, against the script. Text-to-speech fails in ways that are
   invisible to a byte count: a truncated line still produces a valid MP3. If the
   round-trip does not match, the line is marked `verified: false` in the manifest
   and the exit code is non-zero. Nothing here reports success it did not observe.

3. It LINTS THE WRITING BEFORE IT SPENDS. See HOUSE_STYLE below. Sean's standing
   instruction is "stop adding filler/fluff text to my site". Filler is cheap to
   write and expensive to notice, so the rule is enforced mechanically rather than
   left to the good intentions of whichever agent is writing this week.

CREDENTIALS
-----------
Read from the environment first, then from a local secret file. The key is never
logged, never written to the manifest, and never committed.

    export ELEVENLABS_API_KEY=...

Voice `9M1l09pkVunOZDmYq0Ms` ("Myself") is a professional clone of Sean's own voice.
Use `eleven_multilingual_v2`: it is the model the clone is fully fine-tuned on.

SETTLED 2026-08-21, by Sean listening. He compared this model against eleven_v3 on the same
sentence at the same loudness: "A is way better. C is much worse." A was multilingual v2.
v3 also wandered 18% in duration across three renders of one line, against v2's 6.7%, which
would read as tone and pace changing between clips in a fifteen-clip set and cannot be
normalised away afterwards. v3's inline IPA made pronunciation WORSE rather than better - it
read the IPA for magnetopause as "man-knee-two-pause". So: no IPA, respelling only, on
multilingual v2, and the estate's other lanes are back on it too.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

API = "https://api.elevenlabs.io/v1"
DEFAULT_VOICE = "9M1l09pkVunOZDmYq0Ms"   # "Myself" — Sean's professional clone
DEFAULT_MODEL = "eleven_multilingual_v2"  # the clone is fine_tuned on this one, and Sean picked it
# Checked in order. The user-local copy comes first: the root-owned path is
# unreadable by the account that actually runs this tool on bigmem, and a
# PermissionError there is indistinguishable to a reader from "no credential".
SECRET_FALLBACKS = (
    str(Path.home() / ".secrets" / "elevenlabs.json"),
    "/root/.openclaw/workspace/.secrets/elevenlabs.json",
)
# Kept for anything that imported the old name.
SECRET_FALLBACK = SECRET_FALLBACKS[-1]

# ---------------------------------------------------------------------------
# VOICE SETTINGS. CHOSEN BY EAR, BLIND, NOT BY ARGUMENT.
# ---------------------------------------------------------------------------
#
# These used to be 0.45 / 0.80, tuned by reasoning about what narration "should"
# want. They are now 0.62 / 0.75, which Sean picked in a blind pairwise
# tournament run on the sibling lane (/root/voice-notes.md): 18 clips of one
# sentence differing only in model and settings, levelled to within 0.3 dB of
# each other so loudness could not bias the choice, presented as ~20 comparisons
# with the settings hidden until the end. He chose the same clip SIX separate
# times without knowing what it was, and it beat the config behind the video he
# already liked, head to head. It also lands on the intersection of two configs
# he had approved independently before: 0.62 is the stability behind the
# published books and 0.75 the similarity behind the Part 1 video.
#
# `style` stays at 0.0 because this is explanation and not performance, and
# `use_speaker_boost` stays on.
#
# THIS IS PART OF THE CACHE KEY (see `line_hash`), and that is deliberate: audio
# rendered at other settings is not the same audio, so a manifest entry from the
# old dials must not silently satisfy a request under the new ones. The cost of
# that is real - changing this line makes every previously rendered line a cache
# MISS - so a change here is made with `--only` naming the scenes being
# re-rendered, never as a whole-script run that quietly re-bills approved audio.
#
# WHAT IS RENDERED AT WHICH SETTINGS, AND WHY IT IS NOT UNIFORM. As of
# 2026-08-27 the HF scene (hf-skip-blackout) is the only clip rendered at
# 0.45/0.80 with the rewritten script; the other five carry the rewrite AND
# these dials. Sean asked to hear the difference, and one clip holding the old
# dials is what makes the comparison mean anything: HF isolates the writing
# change, the other five add the delivery change on top of it. Re-rendering HF
# to make the library "consistent" destroys that comparison and re-bills 1 136
# characters. Do not do it without being asked.
VOICE_SETTINGS = {
    "stability": 0.62,
    "similarity_boost": 0.75,
    "style": 0.0,
    "use_speaker_boost": True,
}

# ---------------------------------------------------------------------------
# Loudness, applied AT GENERATION TIME - CONSTANT-GAIN RMS, not R128.
# ---------------------------------------------------------------------------
#
# ElevenLabs returns each line as its own file, and each file comes back at its own
# level. Measured 2026-08-27 on THIS repo's own manifest, the raw integrated loudness
# the API delivered for the six freshly-rendered HF lines was:
#
#     -29.09  -29.38  -30.33   |   -39.20  -41.06  -43.75
#
# Two clusters roughly 14 dB apart, with the account flipping between them line by
# line. That is the same bimodal emission the explainer narration lane measured
# independently, and it is why levelling belongs HERE, on the way out.
#
# THE TOOL USED TO BE WRONG. This lane ran two-pass `loudnorm` PER LINE. EBU R128
# integrated loudness is GATED: on a short clip the gate discards much of the
# content, so loudnorm measures the wrong input level and applies the wrong gain.
# Measured on the explainer narration lane over 27 clips: clips >= 2.5 s landed at
# -18.1 LUFS, clips < 2.5 s at -20.5 LUFS - an 8.7 LU spread, plainly audible from
# one sentence to the next. RMS has no gate and reads a two-second clip as reliably
# as a ten-second one; the same 27 clips levelled on RMS spread 2.8 LU.
#
# So: ONE CONSTANT GAIN per line to a fixed RMS target. It moves the whole sentence
# and leaves the delivery inside it alone - which is the point, because Sean's
# complaint was that the delivery changes, and a compressor riding gain inside a
# line is one of the things that makes it change. `alimiter` only catches the rare
# peak the gain would have pushed into clipping.
#
# The ABSOLUTE target is then set once, on the ASSEMBLED clip, by
# tools/mechanism-animations/narrate_mux.py - where the audio is long enough for
# R128 to be the right tool.
#
# `speechnorm` was tried on the explainer narration lane and made it WORSE (4.1 -> 5.5 LU).
# Do not add it. The old acompressor is gone for the same reason.
TARGET_RMS_DB = -20.0
LEVEL_METHOD = "rms"      # written into the manifest; narrate_mux reads it


def _ffmpeg(args: list) -> subprocess.CompletedProcess:
    return subprocess.run(["ffmpeg", "-hide_banner", "-nostdin", "-y"] + args,
                          capture_output=True, text=True)


def measure_levels(path: Path) -> tuple[float | None, float | None]:
    """(mean RMS dB, peak dB) for one clip, or (None, None) if unmeasurable."""
    out = _ffmpeg(["-i", str(path), "-af", "volumedetect", "-f", "null", "-"]).stderr
    mean = re.search(r"mean_volume:\s*(-?\d+(?:\.\d+)?) dB", out)
    peak = re.search(r"max_volume:\s*(-?\d+(?:\.\d+)?) dB", out)
    return (float(mean.group(1)) if mean else None,
            float(peak.group(1)) if peak else None)


def level_rms(path: Path, target_db: float = TARGET_RMS_DB) -> dict | None:
    """Move one clip to `target_db` RMS with a single constant gain, in place.

    Returns what it measured and what it applied, or None if it could not measure -
    a line that could not be levelled is still a usable line, and refusing to write
    it would trade a small defect for a total one.
    """
    mean, peak = measure_levels(path)
    if mean is None:
        return None
    gain = target_db - mean
    tmp = path.with_suffix(".lvl.mp3")
    r = _ffmpeg(["-i", str(path), "-af", f"volume={gain:.2f}dB,alimiter=limit=0.89",
                 "-ar", "44100", "-ac", "1", "-c:a", "libmp3lame", "-b:a", "128k",
                 str(tmp)])
    if r.returncode != 0 or not tmp.is_file():
        tmp.unlink(missing_ok=True)
        return None
    tmp.replace(path)
    return {"method": LEVEL_METHOD, "targetRmsDb": target_db,
            "measuredMeanBefore": mean, "measuredPeakBefore": peak,
            "gainDb": round(gain, 2)}


# ---------------------------------------------------------------------------
# RELATIVE bad-take guard.
# ---------------------------------------------------------------------------
#
# The API occasionally returns a near-silent generation. One is sitting in this
# repo right now: media/mechanisms/narration/mech-03-timescales.mp3 measures -42.6 dB
# mean and -26.6 dB peak, against neighbours peaking at -1.9 dB. It shipped, and it
# played under a visual beat as near-silence.
#
# AN ABSOLUTE FLOOR IS THE WRONG SHAPE AND WAS TRIED ON THE OTHER LANE. These voice
# settings legitimately peak low on quiet lines, so any fixed floor high enough to
# catch a dead take rejects healthy takes too. What makes a dead take obviously dead
# is not its absolute level but that it sits far below ITS NEIGHBOURS.
#
# So: compare each clip's PEAK against the rolling median peak of the clips already
# accepted in this run. Measured on the RAW file, BEFORE levelling - levelling
# normalises RMS and would erase exactly the difference being looked for.
#
# THE MARGIN IS 20 dB AND NOT 12 because this account's natural spread is already
# 15-19 dB (the bimodal emission above). A 12 dB margin would fire on healthy audio
# several times per clip and pay for retries that fix nothing. The real defect sat
# ~25 dB down. 20 dB clears the lottery with room and still catches it with room.
#
# THE RETRY REUSES THE SAME STITCHING ARGUMENTS. A retry that dropped them would
# silently un-stitch precisely the line that needed the most help - the fix undoing
# itself. The arguments are captured in one dict and passed to both calls.
_BADTAKE_MARGIN_DB = 20.0
_BADTAKE_MIN_SAMPLES = 4
_BADTAKE_WINDOW = 12


def _median(values: list[float]) -> float | None:
    v = sorted(values)
    n = len(v)
    if not n:
        return None
    return v[n // 2] if n % 2 else 0.5 * (v[n // 2 - 1] + v[n // 2])


def is_bad_take(peak: float | None, recent: list[float]) -> bool:
    if peak is None or len(recent) < _BADTAKE_MIN_SAMPLES:
        return False
    med = _median(recent[-_BADTAKE_WINDOW:])
    return med is not None and peak < med - _BADTAKE_MARGIN_DB


# ---------------------------------------------------------------------------
# WHAT IS SPOKEN IS NOT WHAT IS SHOWN.
# ---------------------------------------------------------------------------
#
# Sean: "Sometimes ElevenLabs will pronounce things weird, like my last name. E says its
# name in Egan, but sometimes ElevenLabs will pronounce it like Egg-an."
#
# Measured on this voice and this model: it does. `Egan.` comes back EGG-an. `GOES.` comes
# back as the English verb. `Dst.` comes back as "died". The fix is to send the synthesiser
# a DIFFERENT STRING from the one the reader sees - `Eagen`, `Go-ess`, `D S T` - and the
# one rule that matters is that the respelling must never reach the page. So:
#
#     text        what the reader sees. Transcripts, captions and manifests carry this.
#     spokenText  what the synthesiser is sent. Derived, never displayed.
#
# The derivation is automatic and central: every respelling lives in
# narration/pronunciation-lexicon.json, with the failure that justifies it. A script writer
# writes `Egan` and gets the right sound without knowing any of this. A line may still carry
# an explicit `spokenText` to override, and a term the lexicon marks `unresolved` - one where
# no respelling was ever made to work - REFUSES to render, because a term that cannot be said
# correctly should not be said at all.
#
# THE FILE IS MEANT TO BE ALMOST EMPTY. A respelling is a liability, not an improvement: it
# is a permanent silent override on every future render, so respelling a word the model
# already says correctly manufactures a defect rather than preventing one. Entries are added
# only after a word is HEARD wrong in real narration. Render, listen, then fix what failed.
#
# tests/narration-spoken-text.test.ts fails if a respelled form ever appears in anything a
# reader can see.

LEXICON_PATH = Path(__file__).resolve().parent.parent / "narration" / "pronunciation-lexicon.json"


def load_lexicon() -> list[dict]:
    if not LEXICON_PATH.is_file():
        return []
    return json.loads(LEXICON_PATH.read_text())["terms"]


def _term_pattern(display: str) -> re.Pattern:
    """Match the term as a whole word.

    Case matters, and only in one direction. `GOES` is a satellite and `goes` is a verb, so
    a term written with a capital in it is matched case-sensitively; a term written all in
    lower case is matched either way, because a sentence may start with it.
    """
    flags = 0 if any(c.isupper() for c in display) else re.IGNORECASE
    return re.compile(rf"(?<![A-Za-z0-9]){re.escape(display)}(?![A-Za-z0-9])", flags)


def apply_lexicon(text: str, terms: list[dict] | None = None) -> tuple[str, list[str]]:
    """Return (what to send to the synthesiser, which respellings were applied)."""
    terms = load_lexicon() if terms is None else terms
    spoken, applied = text, []
    # Longest display form first, so `L-shell` is not eaten by a rule for `L`.
    for t in sorted(terms, key=lambda t: -len(t["display"])):
        if not t.get("spoken"):
            continue
        pat = _term_pattern(t["display"])
        if pat.search(spoken):
            spoken = pat.sub(t["spoken"], spoken)
            applied.append(f"{t['display']} -> {t['spoken']}")
    return spoken, applied


def lexicon_refusals(text: str, terms: list[dict] | None = None) -> list[str]:
    """Terms in this line that no respelling was ever made to work for."""
    terms = load_lexicon() if terms is None else terms
    out = []
    for t in terms:
        if t.get("status") == "unresolved" and _term_pattern(t["display"]).search(text):
            out.append(f"{t['display']!r} has no working spoken form: {t['spokenWhy']}")
    return out


# ---------------------------------------------------------------------------
# House style, enforced.
# ---------------------------------------------------------------------------

# Throat-clearing and narration-about-narration. These are the phrases that make
# a teaching site sound like a corporate explainer.
BANNED_PHRASES = [
    "in this video", "in this clip", "in this animation", "in this section",
    "we will explore", "we'll explore", "let's explore", "let us explore",
    "let's take a look", "lets take a look", "take a look at",
    "as you can see", "as we can see", "you can see that", "here we see",
    "what you're looking at", "what you are looking at",
    "welcome to", "today we", "first, let's", "now let's", "now we will",
    "it is important to note", "it's important to note", "importantly",
    "in conclusion", "to summarise", "to summarize", "in summary",
    "dive into", "deep dive", "unpack", "journey through",
    "stay tuned", "don't forget", "remember that",
    "simply put", "basically", "essentially", "obviously", "of course",
]

# Words that describe the picture instead of adding to it. The rule for this site
# is: say the thing that is NOT obvious from the picture.
HEDGES = ["very", "really", "quite", "rather", "somewhat", "fairly", "actually", "just"]

MAX_WORDS = 60          # a narration line longer than this belongs on the page as text
MAX_SENTENCES = 4


def lint(line_id: str, text: str) -> list[str]:
    """Return a list of style problems. Empty list means the line passes."""
    problems: list[str] = []
    low = text.lower()

    for phrase in BANNED_PHRASES:
        if phrase in low:
            problems.append(f"filler phrase {phrase!r} — say the thing itself")

    words = re.findall(r"[a-zA-Z']+", text)
    if len(words) > MAX_WORDS:
        problems.append(f"{len(words)} words (max {MAX_WORDS}) — cut it or split it")

    sentences = [s for s in re.split(r"[.!?]+", text) if s.strip()]
    if len(sentences) > MAX_SENTENCES:
        problems.append(f"{len(sentences)} sentences (max {MAX_SENTENCES})")

    for h in HEDGES:
        if re.search(rf"\b{h}\b", low):
            problems.append(f"hedge/filler word {h!r}")

    if not text.strip():
        problems.append("empty text")
    if text.strip() and text.strip()[-1] not in ".!?":
        problems.append("no terminal punctuation — TTS needs it for prosody")

    problems.extend(lexicon_refusals(text))

    return problems


# ---------------------------------------------------------------------------
# Credentials
# ---------------------------------------------------------------------------

def api_key() -> str:
    key = os.environ.get("ELEVENLABS_API_KEY") or os.environ.get("XI_API_KEY")
    if key:
        return key.strip()
    unreadable: list[str] = []
    for candidate in SECRET_FALLBACKS:
        p = Path(candidate)
        try:
            if not p.is_file():
                continue
            return json.loads(p.read_text())["api_key"].strip()
        except PermissionError:
            # Say WHICH path could not be read. The previous message sent a
            # reader off to set an environment variable when the real problem
            # was a file mode, which cost a session's worth of confusion.
            unreadable.append(candidate)
        except Exception:
            unreadable.append(f"{candidate} (present but unreadable as JSON)")
    if unreadable:
        sys.exit(
            "No usable ElevenLabs credential. These exist but could not be read: "
            + ", ".join(unreadable)
            + ". Fix the file mode, or set ELEVENLABS_API_KEY."
        )
    sys.exit("No ElevenLabs credential. Set ELEVENLABS_API_KEY.")


def _request(url: str, *, key: str, data=None, headers=None, timeout=180,
             want_request_id: bool = False):
    """POST/GET one call. With want_request_id, returns (body, request-id header).

    The `request-id` response header is the whole of `previous_request_ids`: it is
    the handle on the GENERATION, and passing it to the next call is what makes the
    next line continue this one's delivery rather than restart it. Never logs the key.
    """
    h = {"xi-api-key": key}
    h.update(headers or {})
    req = urllib.request.Request(url, data=data, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read()
            return (body, r.headers.get("request-id")) if want_request_id else body
    except urllib.error.HTTPError as e:
        # Surface the API's own message - that is how an expired request id or a bad
        # voice id gets diagnosed - but never the key.
        detail = e.read()[:500].decode("utf-8", "replace")
        raise RuntimeError(f"ElevenLabs HTTP {e.code}: {detail}") from None


# ---------------------------------------------------------------------------
# Render + verify
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# REQUEST STITCHING.
# ---------------------------------------------------------------------------
#
# Sean, 2026-08-27, on the six mechanism clips: "why does the volume and the style of
# my speech change as the video progresses? ... I hear myself speed up. or my pitch
# will change."
#
# That is literally what this lane did. Every line was ONE INDEPENDENT REQUEST, so
# the model re-picked speaking rate, pitch contour and terminal intonation from
# scratch on every line - which is also why a declarative sentence sometimes landed
# as a question. Nothing joined one line to the next.
#
# ElevenLabs' own mechanism for that is stitching:
#
#     previous_text          what was said immediately before, as prosodic run-up
#     previous_request_ids   up to 3 ids of the preceding GENERATIONS, read from the
#                            `request-id` RESPONSE HEADER. Stronger than
#                            previous_text: it points at the actual audio.
#
# Measured on the explainer narration lane, same seven-sentence passage, pre-levelling RMS
# spread: 18.8 dB independent, 3.0 dB stitched.
#
# HONEST LIMIT, from that lane and not re-derived here: stitching greatly reduces
# the defect, it does not abolish it. One chain in three still drifted mid-chain.
# The RMS levelling above is the belt to this lane's braces.
#
# `next_text` is NOT sent. It needs the whole scene's script declared up front in
# spoken order; this script file is not stored in spoken order, and guessing at it
# would be worse than not sending it.
#
# WHY STITCHING IS NOT IN THE CACHE KEY. `line_hash` covers text + voice + model +
# settings + seed and deliberately not the stitching context. Adding it would change
# every hash in the file at once and re-bill 38 lines Sean has not asked to have
# re-rendered, to fix a lane he has only asked to see one clip of. The cost of
# leaving it out is that re-rendering ONE line in the middle of an approved scene
# gives it a different run-up than it had; the answer to that is to re-render the
# scene, which is what --only <whole scene> does.
_STITCH_LOOKBACK = 3      # the API accepts at most 3 previous_request_ids


def synthesize(text: str, voice: str, model: str, key: str,
               seed: int | None = None, previous_text: str | None = None,
               previous_request_ids: list[str] | None = None) -> tuple[bytes, str | None]:
    """Render one line.

    `seed` is the difference between a pronunciation you measured and a pronunciation you
    hoped for. Measured 2026-08-21: sending the SAME text twice with no seed returns two
    different performances, and they can differ in how a word is PRONOUNCED, not merely in
    delivery - `Eagen.` came back as "Egan" on one call and "again" on the next. With a
    seed, repeated calls say it the same way every time (the mp3 bytes still differ; the
    pronunciation does not). So any line containing a term from
    narration/pronunciation-lexicon.json carries the seed that was proven for it.
    """
    body = {
        "text": text,
        "model_id": model,
        "voice_settings": VOICE_SETTINGS,
    }
    if seed is not None:
        body["seed"] = int(seed)
    if previous_text:
        body["previous_text"] = previous_text
    if previous_request_ids:
        body["previous_request_ids"] = list(previous_request_ids)[-_STITCH_LOOKBACK:]
    payload = json.dumps(body).encode()
    url = f"{API}/text-to-speech/{voice}?output_format=mp3_44100_128"
    return _request(url, key=key, data=payload, want_request_id=True,
                    headers={"Content-Type": "application/json"})


def transcribe(path: Path, key: str) -> str:
    """Round-trip the rendered audio back to text so we can prove what was said."""
    boundary = "----narrate" + hashlib.md5(path.name.encode()).hexdigest()
    parts = [
        f'--{boundary}\r\nContent-Disposition: form-data; name="model_id"\r\n\r\nscribe_v2\r\n'.encode(),
        f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{path.name}"\r\n'
        f'Content-Type: audio/mpeg\r\n\r\n'.encode(),
        path.read_bytes(),
        f'\r\n--{boundary}--\r\n'.encode(),
    ]
    body = b"".join(parts)
    raw = _request(f"{API}/speech-to-text", key=key, data=body,
                   headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    return json.loads(raw).get("text", "")


# The transcriber normalises spelling and numerals: it returns "disk" for "disc",
# "center" for "centre", "kilometers" for "kilometres", "15" for "fifteen" and
# "1989" for "nineteen eighty nine". None of those are synthesis errors — the audio
# says what the script says. Comparing them raw produced three false failures on the
# first real run, which is the fastest way to teach an operator to ignore a verifier.
# So: fold the known variants, then compare on a similarity ratio rather than exact
# equality. Truncation — the failure this check actually exists to catch — moves the
# ratio and the word count a long way, so it is still caught.
SPELLING_VARIANTS = {
    "disc": "disk", "centre": "center", "metre": "meter", "metres": "meters",
    "kilometre": "kilometer", "kilometres": "kilometers",
    "colour": "color", "behaviour": "behavior", "grey": "gray",
    "analyse": "analyze", "recognise": "recognize", "summarise": "summarize",
    "modelling": "modeling", "travelling": "traveling", "defence": "defense",
    "ionise": "ionize", "ionised": "ionized", "ionisation": "ionization",
}

# The transcriber CONTRACTS where the script does not: `Here is the column`
# came back `Here's the column`, which is one token against two and dropped an
# otherwise perfect line to 0.906. Expanding is the safe direction - it can only
# make two sequences agree that already say the same words - and it keeps the
# contraction out of the token count, which is what the length tolerance reads.
CONTRACTIONS = {
    "here's": ["here", "is"], "there's": ["there", "is"], "it's": ["it", "is"],
    "that's": ["that", "is"], "what's": ["what", "is"], "who's": ["who", "is"],
    "he's": ["he", "is"], "she's": ["she", "is"], "let's": ["let", "us"],
    "don't": ["do", "not"], "doesn't": ["does", "not"], "didn't": ["did", "not"],
    "isn't": ["is", "not"], "aren't": ["are", "not"], "wasn't": ["was", "not"],
    "weren't": ["were", "not"], "won't": ["will", "not"], "can't": ["cannot"],
}

_UNITS = {"zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
          "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
          "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16,
          "seventeen": 17, "eighteen": 18, "nineteen": 19}
_TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
         "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90}


def _fold_thousands(words: list[str]) -> list[str]:
    """`two thousand three` -> 2003. Narration spells years out; transcribers write digits."""
    out, i = [], 0
    while i < len(words):
        if (words[i] in _UNITS and i + 1 < len(words) and words[i + 1] == "thousand"):
            total = _UNITS[words[i]] * 1000
            j = i + 2
            # "two thousand AND three". The transcriber writes the British form
            # and this walked past it, leaving 2000 + 3 as two tokens - so the
            # concatenated digit string read 20003 and a correct line failed on
            # the one comparison that is deliberately exact.
            if j < len(words) and words[j] == "and":
                j += 1
            if j < len(words) and words[j] in _TENS:
                total += _TENS[words[j]]
                j += 1
                if j < len(words) and words[j] in _UNITS and _UNITS[words[j]] < 10:
                    total += _UNITS[words[j]]
                    j += 1
            elif j < len(words) and words[j] in _UNITS:
                total += _UNITS[words[j]]
                j += 1
            out.append(str(total))
            i = j
            continue
        out.append(words[i])
        i += 1
    return out


def _fold_numbers(words: list[str]) -> list[str]:
    """Collapse simple spelled-out numbers to digits so 'fifteen' == '15'.

    Deliberately small. It handles the cases narration actually uses — bare units,
    tens, tens+unit, and four-digit years read as two pairs — and leaves anything
    more elaborate as words, where the similarity ratio absorbs it.
    """
    out: list[str] = []
    i = 0
    while i < len(words):
        w = words[i]
        nxt = words[i + 1] if i + 1 < len(words) else ""
        # year read as two pairs: "nineteen eighty nine" -> 1989
        if w in _UNITS and 10 <= _UNITS[w] <= 19 and nxt in _TENS:
            tail = _TENS[nxt]
            j = i + 2
            if j < len(words) and words[j] in _UNITS and _UNITS[words[j]] < 10:
                tail += _UNITS[words[j]]
                j += 1
            out.append(str(_UNITS[w] * 100 + tail))
            i = j
            continue
        if w in _TENS:
            if nxt in _UNITS and _UNITS[nxt] < 10:
                out.append(str(_TENS[w] + _UNITS[nxt]))
                i += 2
                continue
            out.append(str(_TENS[w]))
            i += 1
            continue
        if w in _UNITS:
            out.append(str(_UNITS[w]))
            i += 1
            continue
        out.append(w)
        i += 1
    return out


def _fold_hundreds(words: list[str]) -> list[str]:
    """`a hundred` -> 100, `four hundred and thirty five` -> 435.

    Added 2026-08-27 after a CORRECT line failed verification. The script said
    "It ends up a hundred kilometres lower and fifty-seven metres a second
    faster"; the transcriber heard it perfectly and wrote "100 kilometers ...
    57 meters". `_fold_numbers` turns "fifty seven" into 57 on both sides but
    had no rule for hundreds, so the exact-digit comparison read 57 against
    10057 and reported a good take as a bad one - the fastest way to teach an
    operator to ignore a verifier.

    (The evidence was mixed before this run and is worth recording: the same
    transcriber wrote "A hundred kilometers up" in words at the START of a
    sentence, and "100 kilometers" mid-sentence. Either form now folds.)

    DELIBERATELY SMALL, like the two folders above. It fires only when the
    token before `hundred` is `a` or a digit 1-19 - the forms narration
    actually says - so a token some earlier folder already built (`21 thousand
    five hundred` arrives here as `20 1005 hundred`) is left exactly as it was
    and keeps comparing the way it did before.
    """
    out: list[str] = []
    i = 0
    while i < len(words):
        w = words[i]
        if w == "hundred" and out:
            prev = out[-1]
            base = None
            if prev == "a":
                base = 1
            elif prev.isdigit() and 1 <= int(prev) <= 19:
                base = int(prev)
            if base is not None:
                out.pop()
                total = base * 100
                j = i + 1
                if j < len(words) and words[j] == "and":
                    j += 1
                if j < len(words) and words[j].isdigit() and int(words[j]) < 100:
                    total += int(words[j])
                    j += 1
                out.append(str(total))
                i = j
                continue
        out.append(w)
        i += 1
    return out


def normalise_words(s: str) -> list[str]:
    """Compare on words only. Punctuation and case are the transcriber's business."""
    s = s.replace("’", "'").replace("‘", "'")
    s = s.replace("“", '"').replace("”", '"').replace("—", " ")
    words = re.findall(r"[a-z0-9']+", s.lower())
    expanded: list[str] = []
    for w in words:
        expanded.extend(CONTRACTIONS.get(w, [w]))
    words = [SPELLING_VARIANTS.get(w, w) for w in expanded]
    return _fold_hundreds(_fold_numbers(_fold_thousands(words)))


# A rendered line must match the script this closely to count as verified.
SIMILARITY_FLOOR = 0.93
LENGTH_TOLERANCE = 0.15


def compare(script_text: str, heard_text: str) -> tuple[bool, float]:
    """Did the synthesiser say what the script said?

    Numbers and words are compared SEPARATELY, and the reason is a real failure this check
    produced on 2026-08-21. The script says "ten twenty four" and the transcriber writes
    "10:24"; the script says "two thousand three" and it writes "2003". Folded into one
    word sequence those disagree on how many tokens a number is, and a correct rendering
    was reported as a failed one - which is the fastest way to teach an operator to ignore
    a verifier.

    So: the DIGITS, in order, concatenated, must match exactly - which still catches a
    misread number, the thing that matters most on a teaching site - and the words around
    them are compared on a similarity ratio. Truncation, the failure this check exists for,
    moves both.
    """
    import difflib
    a, b = normalise_words(script_text), normalise_words(heard_text)
    if not a:
        return False, 0.0
    digits_a = "".join(t for t in a if t.isdigit())
    digits_b = "".join(t for t in b if t.isdigit())
    words_a = [t for t in a if not t.isdigit()]
    words_b = [t for t in b if not t.isdigit()]
    ratio = difflib.SequenceMatcher(None, words_a, words_b).ratio()
    length_ok = abs(len(words_b) - len(words_a)) <= max(1, LENGTH_TOLERANCE * len(words_a))
    return (digits_a == digits_b and ratio >= SIMILARITY_FLOOR and length_ok), round(ratio, 4)


def duration_seconds(path: Path) -> float | None:
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nw=1:nk=1", str(path)],
            capture_output=True, text=True, timeout=60)
        return round(float(out.stdout.strip()), 3)
    except Exception:
        return None


def line_hash(text: str, voice: str, model: str, seed: int | None = None) -> str:
    h = hashlib.sha256()
    h.update(text.encode()); h.update(voice.encode()); h.update(model.encode())
    h.update(json.dumps(VOICE_SETTINGS, sort_keys=True).encode())
    h.update(str(seed).encode())
    return h.hexdigest()[:16]


def main() -> int:
    ap = argparse.ArgumentParser(description="Render narration in Sean's cloned voice.")
    ap.add_argument("script", type=Path)
    ap.add_argument("--outdir", type=Path, default=None,
                    help="default: <script dir>/../media/narration")
    ap.add_argument("--dry-run", action="store_true", help="lint only, spend nothing")
    ap.add_argument("--force", action="store_true", help="re-render even if unchanged")
    ap.add_argument("--reverify", action="store_true",
                    help="re-run the comparison against the transcripts already in the "
                         "manifest. Free: it calls nothing and renders nothing. For when the "
                         "COMPARATOR was wrong rather than the audio.")
    ap.add_argument("--only", action="append", default=None,
                    help="render just these line ids. Sean's rule is that ElevenLabs is the "
                         "FINAL render after he approves the words, so a whole script is "
                         "almost never what you want to spend on first: one representative "
                         "line proves the pipeline for a few cents.")
    args = ap.parse_args()

    spec = json.loads(args.script.read_text())
    voice = spec.get("voice_id", DEFAULT_VOICE)
    model = spec.get("model_id", DEFAULT_MODEL)
    lines = spec["lines"]
    if args.only:
        wanted = set(args.only)
        missing = wanted - {l["id"] for l in lines}
        if missing:
            sys.exit(f"--only names lines that are not in this script: {sorted(missing)}")
        lines = [l for l in lines if l["id"] in wanted]

    outdir = args.outdir or (args.script.parent.parent / "media" / "narration")
    if args.reverify:
        mp = outdir / "manifest.json"
        man = json.loads(mp.read_text())
        changed = 0
        for e in man["lines"]:
            if not e.get("transcript"):
                continue
            ok, ratio = compare(e.get("spokenText") or e["text"], e["transcript"])
            if (ok, ratio) != (e.get("verified"), e.get("similarity")):
                changed += 1
                print(f"  {e['id']}: verified {e.get('verified')} -> {ok} "
                      f"(similarity {e.get('similarity')} -> {ratio})")
            e["verified"], e["similarity"] = ok, ratio
        mp.write_text(json.dumps(man, indent=1) + "\n")
        bad = [e["id"] for e in man["lines"] if not e.get("verified")]
        print(f"{len(man['lines'])} lines re-checked, {changed} changed, "
              f"still failing: {bad or 'none'}")
        return 1 if bad else 0
    outdir.mkdir(parents=True, exist_ok=True)
    manifest_path = outdir / "manifest.json"
    previous = {}
    if manifest_path.is_file():
        try:
            previous = {e["id"]: e for e in json.loads(manifest_path.read_text())["lines"]}
        except Exception:
            previous = {}

    # ---- lint everything before spending a single character -----------------
    failed = False
    for ln in lines:
        problems = lint(ln["id"], ln["text"])
        if problems:
            failed = True
            print(f"STYLE FAIL {ln['id']}", file=sys.stderr)
            for p in problems:
                print(f"    - {p}", file=sys.stderr)
    if failed:
        print("\nNothing was rendered and nothing was spent.", file=sys.stderr)
        return 2

    # What each line will actually be SENT, worked out once so the character count that is
    # printed before anything is billed is the count that is billed.
    terms = load_lexicon()
    for ln in lines:
        derived, applied = apply_lexicon(ln["text"], terms)
        ln["_spoken"] = ln.get("spokenText") or derived
        ln["_applied"] = [] if ln.get("spokenText") else applied

    total_chars = sum(len(l["_spoken"]) for l in lines)
    print(f"{len(lines)} lines, {total_chars} characters, style clean.")

    # ---- what this run will COST, worked out before it spends anything -------
    #
    # Narration bills per character, and the expensive mistake on this lane is
    # not a slow run - it is a run that quietly re-renders lines somebody already
    # approved. The worst version of it is invisible: change VOICE_SETTINGS and
    # every hash in the manifest goes stale at once, so a line whose text nobody
    # touched becomes a cache miss and is billed again. That is called out by
    # name here, because "the text is identical" is exactly what makes a person
    # not look.
    will_bill, hits = 0, 0
    resettles = []
    for ln in lines:
        h = line_hash(ln["_spoken"], voice, model, ln.get("seed"))
        prior = previous.get(ln["id"])
        if not args.force and prior and prior.get("hash") == h and (outdir / f"{ln['id']}.mp3").is_file():
            hits += 1
            continue
        will_bill += len(ln["_spoken"])
        if prior and (prior.get("spokenText") or prior.get("text")) == ln["_spoken"]:
            resettles.append(ln["id"])
    print(f"  cache: {hits} hit, {len(lines) - hits} to render, {will_bill} characters to bill"
          + (" (--force)" if args.force else ""))
    if resettles:
        print(f"  RE-BILL WARNING: {len(resettles)} line(s) are a miss with UNCHANGED TEXT - "
              f"the voice settings or seed moved, not the words: {', '.join(resettles)}",
              file=sys.stderr)
    if args.dry_run:
        print("Dry run: no audio rendered.")
        return 0

    key = api_key()
    entries, spent, verified_all = [], 0, True

    # ---- stitching state ---------------------------------------------------
    # One chain per SCENE. A chain across two unrelated clips would hand the run-up
    # of one piece to the opening line of another, which is not continuity, it is
    # contamination. `scene` is absent on scripts that have no scenes, and then the
    # whole file is one chain, which is right for a single-clip script.
    chain_scene = object()      # sentinel: never equal to a real scene name
    history: list[str] = []     # spoken lines already requested, in order
    request_ids: list[str] = [] # request-ids of ACCEPTED generations
    recent_peaks: list[float] = []
    retries = 0

    for ln in lines:
        lid, text = ln["id"], ln["text"]
        spoken = ln["_spoken"]
        seed = ln.get("seed")
        h = line_hash(spoken, voice, model, seed)
        dest = outdir / f"{lid}.mp3"
        prior = previous.get(lid)

        if ln.get("scene") != chain_scene:
            chain_scene = ln.get("scene")
            history, request_ids, recent_peaks = [], [], []

        # Resolve the run-up BEFORE the cache check, and advance `history` for every
        # line the scene speaks, cached or not. A cache hit that did not advance it
        # would desynchronise the context of every line after it. A cached line makes
        # no call, so it contributes no request id - graceful degradation, and the
        # reason a whole-scene re-render is the most consistent result.
        prev_text = " ".join(history[-_STITCH_LOOKBACK:]) or None
        history.append(spoken)

        if not args.force and prior and prior.get("hash") == h and dest.is_file():
            print(f"  skip   {lid} (unchanged)")
            entries.append(prior)
            continue

        if ln["_applied"]:
            print(f"  spoken {lid}: {'; '.join(ln['_applied'])}")

        # Captured once so the retry cannot diverge from the first attempt.
        call = {"previous_text": prev_text,
                "previous_request_ids": request_ids[-_STITCH_LOOKBACK:] or None}
        audio, req_id = synthesize(spoken, voice, model, key, seed, **call)
        dest.write_bytes(audio)
        spent += len(spoken)

        # The guard reads the RAW file, before levelling erases the difference.
        _, peak = measure_levels(dest)
        retried = False
        if is_bad_take(peak, recent_peaks):
            med = _median(recent_peaks[-_BADTAKE_WINDOW:])
            print(f"  BADTAKE {lid}: peak {peak:.1f} dB against a median of {med:.1f} dB "
                  f"- re-requesting once, stitched the same way", file=sys.stderr)
            audio2, req_id2 = synthesize(spoken, voice, model, key, seed, **call)
            spent += len(spoken)
            retries += 1
            retried = True
            alt = dest.with_suffix(".retry.mp3")
            alt.write_bytes(audio2)
            _, peak2 = measure_levels(alt)
            if peak2 is not None and (peak is None or peak2 > peak):
                alt.replace(dest)
                peak, req_id = peak2, req_id2
            else:
                alt.unlink(missing_ok=True)
        if peak is not None:
            recent_peaks.append(peak)
        if req_id:
            request_ids.append(req_id)

        # Before anything measures or transcribes it. `seconds` in the manifest must be the
        # duration of the file that actually ships, and the verifier must hear the file that
        # actually ships.
        loudness = level_rms(dest)
        if loudness is None:
            print(f"  WARNING {lid}: could not level loudness; file kept as delivered",
                  file=sys.stderr)
        else:
            loudness["stitched"] = bool(call["previous_text"] or call["previous_request_ids"])
            loudness["retried"] = retried

        heard = transcribe(dest, key)
        ok, ratio = compare(spoken, heard)
        if not ok:
            verified_all = False
            print(f"  RENDER {lid} — VERIFY FAILED (similarity {ratio})", file=sys.stderr)
            print(f"    wrote: {text}", file=sys.stderr)
            print(f"    heard: {heard}", file=sys.stderr)
        else:
            print(f"  render {lid} ok ({len(spoken)} chars, {dest.stat().st_size} bytes, similarity {ratio})")

        entries.append({
            "id": lid,
            # `text` is what a reader sees. `spokenText` is what the synthesiser was sent,
            # and is present only when the two differ. Anything rendering a transcript
            # reads `text` and must never read `spokenText`.
            "text": text,
            "spokenText": spoken if spoken != text else None,
            "respellings": ln["_applied"],
            "seed": seed,
            "hash": h,
            "file": dest.name,
            "bytes": dest.stat().st_size,
            "seconds": duration_seconds(dest),
            "verified": ok,
            "similarity": ratio,
            "transcript": heard,
            "voice_id": voice,
            "voice_name": spec.get("voice_name", "Myself (Sean, professional clone)"),
            "model_id": model,
            # What produced this file. The library is deliberately not uniform:
            # see the VOICE_SETTINGS comment at the top of this file.
            "voiceSettings": dict(VOICE_SETTINGS),
            "loudness": loudness,
            "note": ln.get("note", ""),
        })

    # --only RENDERS A SUBSET, IT DOES NOT DEFINE THE MANIFEST.
    #
    # This used to write `entries` straight out, which meant that running
    # `--only one-line` replaced a 44-line manifest with a 1-line one. The mp3s
    # survived on disk, so nothing looked broken until narrate_mux.py went
    # looking for a duration and found no entry at all. The docstring at the top
    # of this file recommends --only as the careful way to spend money, so the
    # careful path was the one that destroyed the manifest.
    #
    # Merge on id, keep the order the manifest already had, and append anything
    # new at the end.
    if args.only and previous:
        merged, rendered = [], {e["id"]: e for e in entries}
        for e in previous.values():
            merged.append(rendered.pop(e["id"], e))
        merged.extend(rendered[i] for i in list(rendered))
        entries = merged

    manifest_path.write_text(json.dumps({
        "generator": "tools/narrate.py",
        "voice_id": voice,
        "model_id": model,
        "lines": entries,
    }, indent=1) + "\n")

    print(f"\nCharacters billed this run: {spent}"
          + (f" (includes {retries} bad-take retry/retries)" if retries else ""))
    print(f"Manifest: {manifest_path}")
    if not verified_all:
        print("At least one line failed round-trip verification.", file=sys.stderr)
        return 1
    print("All lines verified by transcribing the rendered audio back.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
