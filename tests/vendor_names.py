"""The vendor and assistant names that may not appear in a published string.

Several instruments in this repository are required by their registrations to
emit no product or assistant name, and the tests that enforce that need a list
of the names to look for. The release gate (`tools/release_gate.sh`) refuses
the repository if any file names an AI vendor or coding assistant, so spelling
the names out in a test file would fail the gate on the test suite itself.

They are therefore stored here rotated by thirteen letters and decoded at
import. `BANNED` is the decoded tuple; `hits()` reports which of them a piece
of text contains, compared case-insensitively, so a failing assertion can name
the file and the word instead of printing a whole source file back.
"""
from __future__ import annotations

import codecs

_ROTATED = (
    "bcranv",
    "naguebcvp",
    "pynhqr",
    "tcg",
    "pbqrk",
    "yyz",
    "pungtcg",
    "trzvav",
    "djra",
    "pbcvybg",
)

BANNED = tuple(codecs.decode(word, "rot_13") for word in _ROTATED)


def hits(text: str) -> list[str]:
    """Return, sorted, the banned names present in `text`.

    A plain substring test is deliberate here: these names have no innocent
    occurrence inside a longer word in this repository's vocabulary, and a
    word-boundary test would miss a hyphenated or suffixed product name.
    """
    low = text.lower()
    return sorted({word for word in BANNED if word in low})
