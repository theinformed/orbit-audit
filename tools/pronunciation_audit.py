#!/usr/bin/env python3
"""
Pronunciation audit — prove how the clone says the hard words BEFORE paying to render
fifteen clips that contain them.

    python3 tools/pronunciation_audit.py --render      # one short clip per term (paid, tiny)
    python3 tools/pronunciation_audit.py --assemble    # one audit mp3 + a written index
    python3 tools/pronunciation_audit.py --sweep dst "D S T" "Dee Ess Tee"   # try respellings

WHY THIS EXISTS
---------------
The synthesiser mispronounces some words -- proper names, and science terms in
particular -- and it does so inconsistently between renders of the same text.

That is measurable: rendering `Egan.` through this voice on
eleven_multilingual_v2 comes back as EGG-an. Finding that out AFTER a bulk render means
paying for the bulk render twice.

WHAT IT PRODUCES, AND WHY THAT SHAPE
------------------------------------
One mp3 per term and one concatenated audit file with a written index. That lets a
reviewer approve sixty terms in about two minutes instead of listening to twenty minutes
of narration hunting for the one word that is wrong. Terms, not sentences, because the audit is billed
by the character like everything else.

**A term spoken alone is not identical to the same term inside a sentence.** Rhythm and
neighbouring vowels move a synthesiser's stress. This audit catches the word-level failure
- the wrong vowel, the wrong stress, the acronym read as a word - which is every failure
observed on this site so far. It does not prove the term is right in every sentence.

THE SEPARATION THAT MATTERS
---------------------------
`display` is what a reader sees. `spoken` is what the synthesiser is sent. They are
different fields on purpose and the respelling must never reach a transcript: see
`tools/narrate.py` and `tests/narration-spoken-text.test.ts`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from narrate import (  # noqa: E402  - same directory, same lane, same voice settings
    VOICE_SETTINGS,
    _ffmpeg,
    api_key,
    duration_seconds,
    synthesize,
)

LEXICON = ROOT / "narration" / "pronunciation-lexicon.json"
OUTDIR = ROOT / "media" / "pronunciation-audit"

# Silence between terms in the assembled audit file. Long enough to hear the boundary,
# short enough that sixty terms stay inside two minutes.
GAP_SECONDS = 0.75


# A one-word clip is too short to level the way the narration lane levels a sentence.
# `loudnorm` measures INTEGRATED loudness, which is defined over gated 3-second blocks; ask
# it about 0.8 seconds of the word "apogee" and it answers, but the answer is not a
# measurement. Levelling 59 terms that way left them spread over 10 dB - the very
# volume-jumping this house rule exists to stop, reintroduced by using the right tool on the
# wrong length of audio.
#
# So the audit clips are levelled on RMS instead, which is exact at any length: measure the
# mean level, apply one gain, limit the peak. Full narration lines keep the two-pass
# `loudnorm` in tools/narrate.py, where the audio is long enough for it to mean something.
TARGET_RMS_DBFS = -21.0   # speech at this RMS sits near the house -16 LUFS target
TARGET_LUFS = -16.0


def measure_rms(path: Path) -> float | None:
    r = _ffmpeg(["-i", str(path), "-af", "volumedetect", "-f", "null", "-"])
    for line in r.stderr.splitlines():
        if "mean_volume:" in line:
            return float(line.split("mean_volume:")[1].strip().split()[0])
    return None


def measure_lufs(path: Path) -> float | None:
    """Only meaningful on audio longer than about three seconds. Used for the assembled file."""
    r = _ffmpeg(["-i", str(path), "-af", "loudnorm=print_format=json", "-f", "null", "-"])
    try:
        blob = r.stderr[r.stderr.rindex("{"):]
        return float(json.loads(blob[:blob.rindex("}") + 1])["input_i"])
    except Exception:
        return None


def level(path: Path) -> dict | None:
    before = measure_rms(path)
    if before is None:
        return None
    gain = TARGET_RMS_DBFS - before
    tmp = path.with_suffix(".lvl.mp3")
    r = _ffmpeg(["-i", str(path), "-af", f"volume={gain:.2f}dB,alimiter=limit=0.891",
                 "-ar", "44100", "-ac", "1", "-c:a", "libmp3lame", "-b:a", "128k", str(tmp)])
    if r.returncode != 0 or not tmp.is_file():
        tmp.unlink(missing_ok=True)
        return None
    tmp.replace(path)
    return {"targetRmsDbfs": TARGET_RMS_DBFS, "measuredRmsBefore": round(before, 2),
            "gainDb": round(gain, 2), "measuredRmsAfter": measure_rms(path)}


def slug(s: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in s.lower()).strip("-")


def spoken_form(term: dict) -> str:
    """What the synthesiser is sent. Terminal punctuation, because TTS needs prosody."""
    text = term.get("spoken") or term["display"]
    return text if text.strip()[-1] in ".!?" else text + "."


def audit_set(lex: dict) -> list[dict]:
    """The two kinds of thing worth speaking, and nothing else.

    A FIX is a word that was heard wrong and is now respelled; it is spoken as it will be
    sent, so the fix itself can be checked. A SPOT CHECK is a word that appears in the
    scripts more than once and is spoken exactly as written, so a person can hear whether it
    is fine. Nothing else belongs here. The audit used to speak fifty-nine terms chosen for
    looking risky, which is how a listening aid turns into a ritual rather than a check.
    """
    rows = []
    for t in lex["terms"]:
        # A fix is spoken inside a real sentence, because that is the only place it was ever
        # heard failing. `Eegan.` on its own comes back "E gun"; the same respelling inside
        # the carrier sentence is right. Checking a respelling as a bare word is the mistake that
        # filled this file with 57 speculative entries.
        carrier = t.get("carrier")
        display = carrier or t["display"]
        spoken = None
        if t.get("spoken"):
            spoken = (carrier.replace(t["display"], t["spoken"]) if carrier else t["spoken"])
        rows.append({"id": t["id"], "display": display, "spoken": spoken,
                     "kind": "fix", "expectedIpa": t.get("expectedIpa", ""),
                     "word": t["display"], "respelling": t.get("spoken"),
                     "note": t.get("target", ""), "seed": t.get("seed")})
    for w in lex.get("spotCheck", {}).get("words", []):
        rows.append({"id": slug(w), "display": w, "spoken": None, "kind": "spot-check",
                     "expectedIpa": "", "note": "spoken exactly as written", "seed": None})
    return rows


def term_hash(text: str, voice: str, model: str) -> str:
    h = hashlib.sha256()
    for part in (text, voice, model, json.dumps(VOICE_SETTINGS, sort_keys=True)):
        h.update(part.encode())
    return h.hexdigest()[:16]


def render(only: set[str] | None, force: bool) -> int:
    lex = json.loads(LEXICON.read_text())
    voice = lex["voiceProvenOn"]["voice_id"]
    model = lex["voiceProvenOn"]["model_id"]
    terms = [t for t in audit_set(lex) if not only or t["id"] in only]

    termdir = OUTDIR / "terms"
    termdir.mkdir(parents=True, exist_ok=True)
    manifest_path = OUTDIR / "manifest.json"
    previous = {}
    if manifest_path.is_file():
        try:
            previous = {e["id"]: e for e in json.loads(manifest_path.read_text())["terms"]}
        except Exception:
            previous = {}

    chars = sum(len(spoken_form(t)) for t in terms)
    print(f"{len(terms)} terms, {chars} characters if every one is re-rendered.")

    key = api_key()
    entries, spent = [], 0
    for t in terms:
        text = spoken_form(t)
        h = term_hash(text + f"|seed={t.get('seed')}", voice, model)
        dest = termdir / f"{t['id']}.mp3"
        prior = previous.get(t["id"])
        if not force and prior and prior.get("hash") == h and dest.is_file():
            print(f"  skip   {t['id']}")
            entries.append(prior)
            continue
        dest.write_bytes(synthesize(text, voice, model, key, t.get("seed")))
        spent += len(text)
        loud = level(dest)
        entries.append({
            "id": t["id"], "display": t["display"], "spoken": t.get("spoken"),
            "sent": text, "hash": h, "file": dest.name,
            "bytes": dest.stat().st_size, "seconds": duration_seconds(dest),
            "expectedIpa": t.get("expectedIpa", ""), "kind": t["kind"],
            "word": t.get("word"), "respelling": t.get("respelling"),
            "note": t.get("note", ""), "seed": t.get("seed"),
            "loudness": loud, "voice_id": voice, "model_id": model,
        })
        print(f"  render {t['id']:16s} sent={text!r} {dest.stat().st_size}B "
              f"{entries[-1]['seconds']}s")

    # Anything not rendered this run keeps its previous entry, so --only never truncates
    # the manifest the audit file is assembled from.
    # A term that has left the lexicon leaves the audit with it. Carrying an old clip because
    # its file still exists is how the checklist grew in the first place.
    order = [t["id"] for t in audit_set(lex)]
    kept = [e for e in previous.values()
            if e["id"] in order and e["id"] not in {x["id"] for x in entries}]
    allterms = sorted(entries + kept, key=lambda e: order.index(e["id"]))
    for stale in termdir.glob("*.mp3"):
        if stale.stem not in order:
            stale.unlink()
            print(f"  drop   {stale.stem} (no longer in the lexicon)")
    manifest_path.write_text(json.dumps({
        "generator": "tools/pronunciation_audit.py",
        "voice_id": voice, "model_id": model, "terms": allterms}, indent=1) + "\n")
    print(f"\nCharacters billed this run: {spent}\nManifest: {manifest_path}")
    return 0


def assemble() -> int:
    """One file, in lexicon order, with the gaps measured back out of the delivered mp3."""
    manifest = json.loads((OUTDIR / "manifest.json").read_text())
    terms = manifest["terms"]
    if not terms:
        sys.exit("Nothing rendered yet. Run --render first.")

    silence = OUTDIR / ".gap.mp3"
    subprocess.run(["ffmpeg", "-hide_banner", "-nostdin", "-y", "-f", "lavfi",
                    "-i", f"anullsrc=r=44100:cl=mono", "-t", str(GAP_SECONDS),
                    "-c:a", "libmp3lame", "-b:a", "128k", str(silence)],
                   capture_output=True, check=True)

    listing = OUTDIR / ".concat.txt"
    files, head = [], []
    for t in terms:
        files.append(OUTDIR / "terms" / t["file"])
        files.append(silence)
    listing.write_text("".join(f"file '{f}'\n" for f in files))

    out = OUTDIR / "audit.mp3"
    subprocess.run(["ffmpeg", "-hide_banner", "-nostdin", "-y", "-f", "concat",
                    "-safe", "0", "-i", str(listing), "-c", "copy", str(out)],
                   capture_output=True, check=True)

    # Loudness on the assembled file, and the trap that cost three attempts.
    #
    # This file is a third silence by construction - ten words with gaps between them - and
    # integrated loudness is a GATED measurement: it discards the quiet parts. Measure a
    # gappy file, apply the gain that measurement implies, and re-measure, and the second
    # answer disagrees with the first, because the gating threshold moved with the gain. A
    # correction loop built on that chases its own tail: it went -17.6, then -15.3 with true
    # peak at -0.2 dBTP, then -14.1 with true peak ABOVE zero - each step further from the
    # house ceiling it was trying to respect.
    #
    # So: one two-pass loudnorm at the house target, and then leave it alone. What a listener
    # actually notices here is whether one word is louder than the next, and that is fixed in
    # the term clips themselves, which sit within 1.1 dB of each other. The integrated figure
    # for the whole file reads a little under target because of the silence, and that is a
    # property of the measurement rather than a defect in the audio.
    m = measure_lufs(out)
    if m is not None:
        tmp = out.with_suffix(".norm.mp3")
        r = _ffmpeg(["-i", str(out), "-af",
                     f"loudnorm=I={TARGET_LUFS}:TP=-1.5:LRA=9:measured_I={m}:linear=false",
                     "-ar", "44100", "-ac", "1", "-c:a", "libmp3lame", "-b:a", "128k", str(tmp)])
        if r.returncode == 0 and tmp.is_file():
            tmp.replace(out)
        else:
            tmp.unlink(missing_ok=True)
    measured = measure_lufs(out)

    # Timecodes are ARITHMETIC on the durations measured out of each delivered file, not on
    # the durations we asked for: a clip a tenth of a second longer than requested would put
    # every entry after it in the wrong place.
    index, at = [], 0.0
    for t in terms:
        secs = duration_seconds(OUTDIR / "terms" / t["file"]) or t["seconds"]
        index.append({
            "at": round(at, 2), "id": t["id"], "display": t["display"],
            "sent": t["sent"], "respelled": bool(t.get("spoken")),
            "kind": t.get("kind", ""), "note": t.get("note", ""),
            "word": t.get("word"), "respelling": t.get("respelling"),
            "seconds": secs, "file": f"terms/{t['file']}",
        })
        at += secs + GAP_SECONDS

    (OUTDIR / "index.json").write_text(json.dumps({
        "audio": "audit.mp3",
        "totalSeconds": round(at, 2),
        "measuredLufs": measured,
        "gapSeconds": GAP_SECONDS,
        "voice_id": manifest["voice_id"], "model_id": manifest["model_id"],
        "howToUse": "Play audit.mp3 and follow the index. Every entry gives the second it "
                    "is spoken at, the word as it is written on the site, and how it "
                    "should sound. Flag any that are wrong by id.",
        "terms": index}, indent=1) + "\n")

    listing.unlink(missing_ok=True)
    silence.unlink(missing_ok=True)
    print(f"{out}  {round(at,1)}s  {out.stat().st_size} bytes")
    print(f"{OUTDIR / 'index.json'}  {len(index)} entries")
    return 0


# Seeds to try, in order. Fixed rather than random so that a rerun of the search reproduces
# the same answer, and small because the first or second usually lands.
SEED_CANDIDATES = [101, 7, 42, 13, 23, 77]


# The model A/B that used to live here is gone: it was settled by blind listening, and
# eleven_multilingual_v2 won. The renders are kept at
# media/pronunciation-audit/name-candidates/ with the measurement beside them.


def find_seeds(only: set[str] | None) -> int:
    """Pin each term's pronunciation to a seed that was MEASURED to be right.

    Measured 2026-08-21: the same text sent twice with no seed comes back pronounced two
    different ways - `Eagen.` was "Egan" on one call and "again" on the next. That makes an
    approved audit clip worthless on its own, because the next render is a fresh roll. With
    a seed the pronunciation repeats.

    So for every term this searches seeds until the free local readback agrees the audio
    says the right thing, and writes the winning seed into the lexicon. What a reviewer
    approves in the audit clip is then what the pipeline reproduces.

    Run under the ASR virtualenv:
        /home/sdegan/.venv-asr/bin/python tools/pronunciation_audit.py --find-seeds
    """
    sys.path.insert(0, str(ROOT / "tools"))
    from pronunciation_readback import distance, phone_classes, phonemes, words

    lex = json.loads(LEXICON.read_text())
    voice = lex["voiceProvenOn"]["voice_id"]
    model = lex["voiceProvenOn"]["model_id"]
    key = api_key()
    termdir = OUTDIR / "terms"
    termdir.mkdir(parents=True, exist_ok=True)
    spent = 0

    for t in audit_set(lex):
        if only and t["id"] not in only:
            continue
        if not t.get("expectedIpa") or t.get("kind") == "fix":
            print(f"  skip   {t['id']}: "
                  + ("spot check, no target to search against" if t.get("kind") != "fix"
                     else "spoken in a carrier sentence; a person judges it, not a word matcher"))
            continue
        text = spoken_form(t)
        want = phone_classes(t["expectedIpa"])
        dest = termdir / f"{t['id']}.mp3"
        best = None
        for seed in SEED_CANDIDATES:
            dest.write_bytes(synthesize(text, voice, model, key, seed))
            spent += len(text)
            level(dest)
            sim = distance(want, phone_classes(phonemes(dest)))
            heard = words(dest)
            if best is None or sim > best[1]:
                best = (seed, sim, heard, dest.read_bytes())
            if sim >= 0.75:
                break
        seed, sim, heard, blob = best
        dest.write_bytes(blob)
        entry = next(e for e in lex["terms"] if e["id"] == t["id"])
        entry["seed"] = seed
        entry["seedEvidence"] = {"similarity": round(sim, 3), "whisper": heard,
                                 "tried": SEED_CANDIDATES[:SEED_CANDIDATES.index(seed) + 1]}
        flag = "ok " if sim >= 0.75 else "WEAK"
        print(f"  {flag} {t['id']:14s} seed={seed:<5} sim={sim:.2f} whisper={heard!r}")

    LEXICON.write_text(json.dumps(lex, indent=1, ensure_ascii=False) + "\n")
    print(f"\nCharacters billed this search: {spent}")
    return 0


def sweep(term_id: str, candidates: list[str]) -> int:
    """Render candidate respellings of one term into /tmp so a choice can be measured.

    Sweeps are scratch, not product: only the form that wins reaches the lexicon.
    """
    lex = json.loads(LEXICON.read_text())
    term = next((t for t in audit_set(lex) if t["id"] == term_id), None)
    if term is None:
        sys.exit(f"no such term: {term_id}")
    out = Path(f"/tmp/pron-sweep/{term_id}")
    out.mkdir(parents=True, exist_ok=True)
    key = api_key()
    for c in candidates:
        text = c if c.strip()[-1] in ".!?" else c + "."
        dest = out / f"{slug(c)}.mp3"
        dest.write_bytes(synthesize(text, lex["voiceProvenOn"]["voice_id"],
                                    lex["voiceProvenOn"]["model_id"], key))
        print(f"  {dest}  sent={text!r}")
    print(f"\nTarget: {term.get('note','')}  ({term.get('expectedIpa','')})")
    print(f"Read them back with tools/pronunciation_readback.py {out}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--render", action="store_true")
    ap.add_argument("--assemble", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--only", action="append", default=None)
    ap.add_argument("--sweep", nargs="+", default=None,
                    metavar=("TERM_ID", "CANDIDATE"))
    ap.add_argument("--find-seeds", action="store_true",
                    help="search seeds until the local readback agrees (needs the ASR venv)")
    args = ap.parse_args()
    if args.sweep:
        return sweep(args.sweep[0], args.sweep[1:])
    rc = 0
    if args.find_seeds:
        rc |= find_seeds(set(args.only) if args.only else None)
    if args.render:
        rc |= render(set(args.only) if args.only else None, args.force)
    if args.assemble:
        rc |= assemble()
    if not (args.render or args.assemble or args.find_seeds):
        ap.print_help()
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
