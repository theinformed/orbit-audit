#!/usr/bin/env python3
"""Number-fidelity acceptance test for the LaTeX typesetting of the papers.

Extracts every numeric token from a markdown draft and from the .tex produced
from it, and diffs the two ordered sequences.  A single lost, added or altered
digit fails the test.

Normalisation applied to BOTH sides so that the comparison is about numbers and
not about notation:

  * unicode super/subscript digits are folded to ASCII digits
    (10 U+207B U+2078  ->  10-8 ;  \\ensuremath{^{-8}}  ->  ^-8)
  * unicode dashes and the minus sign U+2212 fold to ASCII '-'
  * unicode operators (x, /, +-, >=, <=, ~=, ., degree) and their LaTeX
    spellings (\\times \\div \\pm \\ge \\le \\approx \\cdot \\textdegree ...)
    both fold to a single space, so they separate tokens identically
  * on the LaTeX side every control sequence becomes a space and braces/$
    are dropped, so \\path{docs/x-20260920.md} and docs/x-20260920.md agree
  * a comma counts as part of a number only as a thousands separator
    (\"216,937,797\" is one token; the comma in \"a/2, the\" is punctuation)
  * HTML comments in the markdown and % comments in the .tex are BOTH kept:
    the provenance comments carry numbers and must transfer too
  * the .tex preamble (everything before \\begin{document}) is ignored: it is
    LaTeX machinery with no counterpart in the draft

Usage:  check-numbers.py <draft.md> <paper.tex>
"""
import re
import sys
import difflib
import unicodedata

SUP = {"\u2070": "0", "\u00b9": "1", "\u00b2": "2", "\u00b3": "3", "\u2074": "4",
       "\u2075": "5", "\u2076": "6", "\u2077": "7", "\u2078": "8", "\u2079": "9",
       "\u207b": "-"}
SUB = {"\u2080": "0", "\u2081": "1", "\u2082": "2", "\u2083": "3", "\u2084": "4",
       "\u2085": "5", "\u2086": "6", "\u2087": "7", "\u2088": "8", "\u2089": "9"}

TOKEN = re.compile(r"\d(?:,\d{3}|\d)*(?:\.\d+)?")


def normalise(text, is_tex):
    if is_tex:
        head, sep, tail = text.partition(r"\begin{document}")
        if sep:
            text = tail
        # control sequences -> space (keeps neighbouring tokens apart)
        text = re.sub(r"\\[A-Za-z@]+\s*", " ", text)
        text = re.sub(r"\\.", " ", text, flags=re.S)
        text = re.sub(r"[{}$]", " ", text)
    text = "".join(SUP.get(c, SUB.get(c, c)) for c in text)
    text = (text.replace("\u2014", "-").replace("\u2013", "-")
                .replace("\u2212", "-").replace("\u2010", "-"))
    # any remaining non-ASCII becomes a separator
    text = "".join(c if ord(c) < 128 else " " for c in text)
    return text


def tokens(path, is_tex):
    raw = open(path, encoding="utf-8").read()
    return TOKEN.findall(normalise(raw, is_tex))


def main():
    md, tex = sys.argv[1], sys.argv[2]
    a, b = tokens(md, False), tokens(tex, True)
    print("%-28s %6d numeric tokens" % (md.split("/")[-1], len(a)))
    print("%-28s %6d numeric tokens" % (tex.split("/")[-1], len(b)))
    diffs = [d for d in difflib.unified_diff(a, b, "markdown", "latex", n=2, lineterm="")
             if d.startswith(("+", "-")) and not d.startswith(("+++", "---"))]
    if not diffs:
        print("RESULT: PASS - sequences identical, 0 discrepancies")
        return 0
    print("RESULT: FAIL - %d differing tokens" % len(diffs))
    for d in difflib.unified_diff(a, b, "markdown", "latex", n=3, lineterm=""):
        print(d)
    return 1


if __name__ == "__main__":
    sys.exit(main())
