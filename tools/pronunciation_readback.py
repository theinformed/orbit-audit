#!/usr/bin/env python3
"""
Read the rendered audio back, locally and for free, and say which terms look wrong.

    /home/sdegan/.venv-asr/bin/python tools/pronunciation_readback.py            # the audit set
    /home/sdegan/.venv-asr/bin/python tools/pronunciation_readback.py /tmp/pron-sweep/dst

WHAT THIS IS, AND WHAT IT IS NOT
--------------------------------
It is a FILTER, not a proof. Two models are run over every clip and they fail in opposite
directions, which is the only reason running both is worth it:

  * **Whisper** (`faster-whisper small.en`) returns WORDS. It is a language model as much
    as an acoustic one, so it will happily return the word it expected to hear: ask it to
    transcribe a badly-pronounced "magnetopause" and it may still write "magnetopause".
    **When Whisper returns something else entirely - "EGGON" for Egan, "That's" for Dst -
    that is a loud, reliable signal that the audio is wrong.** Silence from Whisper is not
    a signal that the audio is right.

  * **wav2vec2-lv-60-espeak-cv-ft** returns PHONEMES. It has no lexicon and no language
    model, so it cannot auto-correct toward the expected word - it reports the vowels and
    consonants that were actually there. It is noisier: it confuses schwa with wedge,
    flaps t and d, and is unreliable about vowel length. So a small distance means little
    and a large distance means a lot.

Neither model can tell you that a correct-sounding word carries the wrong STRESS, and
neither is a human ear. The audit clip exists because a listener is the actual acceptance
test; this script exists so that the obvious failures are found and fixed before that
listening time is spent.

Runs on CPU inside an ASR virtualenv. It is free and it uses no GPU: sixty one-second
clips take about a minute, and the GPU is usually busy with other work.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
AUDIT = ROOT / "media" / "pronunciation-audit"

# Coarse phone classes. The phoneme model is noisy in ways that are NOT pronunciation
# errors - schwa vs wedge vs turned-a, flapped t, vowel length - so those are folded
# together before anything is compared. What is deliberately NOT folded is every
# distinction this site has actually been bitten by: EE vs EH (Egan), OW vs AW (-pause),
# and any consonant.
CLASSES = {
    "i": "i", "iː": "i", "ɪ": "i", "y": "i",
    "ɛ": "E", "e": "E", "æ": "E", "ɜ": "ə", "ɐ": "ə", "ə": "ə", "ʌ": "ə", "ɚ": "ə", "ɵ": "ə",
    "ɑ": "A", "ɑː": "A", "ɒ": "A", "ɔ": "A", "ɔː": "A", "a": "A", "ɶ": "A",
    "u": "u", "uː": "u", "ʊ": "u", "o": "u", "oː": "u", "ɤ": "u",
    "eɪ": "eI", "aɪ": "aI", "aʊ": "aU", "ɔɪ": "OI", "oʊ": "oU", "əʊ": "oU",
    "ɹ": "r", "r": "r", "ɻ": "r", "ɾ": "t", "t": "t", "d": "t", "ð": "T", "θ": "T",
    "tʃ": "C", "dʒ": "J", "ʃ": "S", "ʒ": "S", "ɡ": "g", "g": "g",
}


def phone_classes(ipa: str) -> str:
    """Fold an IPA string to one character per phone class.

    Greedy longest-match, because the two sides arrive in different shapes: the lexicon
    writes `oʊveɪʃən` as one string and the phoneme model returns `oʊ v eɪ ʃ ə n` with
    spaces. Splitting the first per character would break every diphthong in it and report
    a mismatch on a term that was pronounced perfectly - which is exactly what the first
    run of this script did to OVATION, LASCO and AIA.
    """
    s = "".join(c for c in ipa if c not in "ˈˌ' \u0361" and not c.isdigit())
    out, i = [], 0
    while i < len(s):
        for length in (2, 1):
            tok = s[i:i + length]
            if tok in CLASSES:
                out.append(CLASSES[tok])
                i += length
                break
        else:
            out.append(s[i])
            i += 1
    return "".join(out)


def distance(a: str, b: str) -> float:
    """Levenshtein similarity on folded phone classes, 1.0 identical."""
    if not a and not b:
        return 1.0
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return 1 - prev[-1] / max(len(a), len(b), 1)


_ph: dict = {}
_wh: dict = {}


def wav16(p: Path) -> np.ndarray:
    out = subprocess.run(["ffmpeg", "-v", "error", "-i", str(p), "-ac", "1",
                          "-ar", "16000", "-f", "f32le", "-"], capture_output=True)
    return np.frombuffer(out.stdout, dtype=np.float32)


def phonemes(p: Path) -> str:
    if not _ph:
        import torch
        from transformers import AutoModelForCTC, AutoProcessor
        _ph["proc"] = AutoProcessor.from_pretrained("facebook/wav2vec2-lv-60-espeak-cv-ft")
        _ph["model"] = AutoModelForCTC.from_pretrained("facebook/wav2vec2-lv-60-espeak-cv-ft")
        _ph["torch"] = torch
    torch = _ph["torch"]
    iv = _ph["proc"](wav16(p), sampling_rate=16000, return_tensors="pt").input_values
    with torch.no_grad():
        logits = _ph["model"](iv).logits
    return _ph["proc"].batch_decode(torch.argmax(logits, dim=-1))[0]


def words(p: Path) -> str:
    if not _wh:
        from faster_whisper import WhisperModel
        _wh["m"] = WhisperModel("small.en", device="cpu", compute_type="int8")
    segs, _ = _wh["m"].transcribe(str(p), language="en", beam_size=5)
    return " ".join(s.text.strip() for s in segs).strip()


# A term whose folded phone sequence matches this closely is not worth a listener's
# attention first; below the lower bound it almost certainly is. Both numbers are calibrated on the
# controls in the lexicon, not chosen for looking tidy.
MATCH = 0.75
SUSPECT = 0.55


def verdict(sim: float, heard_words: str, display: str) -> str:
    letters = "".join(c for c in display.lower() if c.isalnum())
    heard = "".join(c for c in heard_words.lower() if c.isalnum())
    word_disagrees = letters not in heard and heard not in letters
    if sim >= MATCH:
        return "suspect (words disagree)" if word_disagrees and sim < 0.9 else "match"
    if sim >= SUSPECT:
        return "suspect"
    return "MISMATCH"


def main() -> int:
    if len(sys.argv) > 1:
        d = Path(sys.argv[1])
        for f in sorted(d.glob("*.mp3")):
            print(f"{f.stem:24s} whisper={words(f)!r:28s} ipa={phonemes(f)!r}")
        return 0

    manifest = json.loads((AUDIT / "manifest.json").read_text())
    rows = []
    for t in manifest["terms"]:
        f = AUDIT / "terms" / t["file"]
        heard_ipa = phonemes(f)
        heard_words = words(f)
        sim = round(distance(phone_classes(t["expectedIpa"]), phone_classes(heard_ipa)), 3)
        v = verdict(sim, heard_words, t["display"])
        rows.append({"id": t["id"], "display": t["display"], "sent": t["sent"],
                     "expectedIpa": t["expectedIpa"], "heardIpa": heard_ipa,
                     "heardWords": heard_words, "similarity": sim, "verdict": v,
                     "priority": t["priority"]})
        print(f"{v:24s} {t['id']:16s} sim={sim:<6} want={t['expectedIpa']:<22} "
              f"got={heard_ipa:<28} whisper={heard_words!r}")

    (AUDIT / "readback.json").write_text(json.dumps({
        "tool": "tools/pronunciation_readback.py",
        "asr": ["faster-whisper small.en (words)",
                "facebook/wav2vec2-lv-60-espeak-cv-ft (phonemes)"],
        "limitation": "A filter, not a proof. Whisper auto-corrects toward the expected "
                      "word, so silence from it means nothing; the phoneme model is noisy "
                      "about vowel quality and length, so a small distance means little. "
                      "Stress is not measured by either. Sean's ear is the acceptance test.",
        "thresholds": {"match": MATCH, "suspect": SUSPECT},
        "terms": rows}, indent=1) + "\n")
    bad = [r for r in rows if r["verdict"] != "match"]
    print(f"\n{len(rows)} terms, {len(bad)} not clean: "
          f"{', '.join(r['id'] for r in bad) or 'none'}")
    print(f"Written: {AUDIT / 'readback.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
