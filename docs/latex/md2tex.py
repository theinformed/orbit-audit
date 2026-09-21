#!/usr/bin/env python3
"""Faithful markdown -> LaTeX converter used once to typeset the two space papers.

The committed .tex files are the source of record from here on: do NOT regenerate
over hand edits.  This script is kept so the conversion is reproducible and so the
number-fidelity test in check-numbers.py has a documented counterpart.

Design rules:
  * every sentence, table, list, footnote and HTML comment transfers
  * HTML comments become % comments at the same position (verbatim content)
  * no numeric token is added, dropped or altered in the document body
"""
import re, sys, html

# ---------------------------------------------------------------- placeholders
def ph(kind, i):
    return "ZZ%sZZ%dZZ" % (kind, i)

PH_RE = re.compile(r"ZZ(CMT|CODE|URL|MATH|AST)ZZ(\d+)ZZ")

# ------------------------------------------------------------- curated math
# Exact source substrings that must become real math.  Digit sequences are
# preserved character for character.
MATH_MAP = [
    ("(1 + \u221a2)\u00b7*v*",
     r"$(1 + \sqrt{2})\cdot v$"),
    ("2*V*\u00b7sin(\u03b8/2)",
     r"$2V\cdot\sin(\theta/2)$"),
    ("*v*_c\u00b7\u0394*e*/(2\u221a(1\u2212*e*\u00b2))",
     r"$v_c\cdot\Delta e/(2\sqrt{1-e^2})$"),
    ("*v*_c\u00b7\u0394*e*/2",
     r"$v_c\cdot\Delta e/2$"),
    ("*v*\u00b2 = \u03bc(2/*r* \u2212 1/*a*)",
     r"$v^2 = \mu(2/r - 1/a)$"),
    ("\u0394*v* = \u03bc\u00b7\u0394*a*/(2*a*\u00b2*v*)",
     r"$\Delta v = \mu\cdot\Delta a/(2a^2v)$"),
    ("d*a*/d*t* = (2*a*\u00b2*v*/\u03bc)\u00b7*f*_t",
     r"$da/dt = (2a^2v/\mu)\cdot f_t$"),
    ("\u0394*v* = *n*\u00b7\u0394*a*/2",
     r"$\Delta v = n\cdot\Delta a/2$"),
    ("*v*_p = *v*_c\u221a((1+*e*)/(1\u2212*e*))",
     r"$v_p = v_c\sqrt{(1+e)/(1-e)}$"),
    ("\u221a((1\u2212*e*)/(1+*e*))",
     r"$\sqrt{(1-e)/(1+e)}$"),
    ("\u221a((1+*e*)/(1\u2212*e*))",
     r"$\sqrt{(1+e)/(1-e)}$"),
    ("*a* = (\u03bc/*n*\u00b2)^(1/3)",
     r"$a = (\mu/n^2)^{1/3}$"),
    ("1/*n*\u2081 + 1/*n*\u2082 = 2.706 \u00d7 10\u207b\u2078",
     r"$1/n_1 + 1/n_2 = 2.706 \times 10^{-8}$"),
    ("(*r* \u2212 1)\u00b7\u221a(*p* / 2.706 \u00d7 10\u207b\u2078)",
     r"$(r - 1)\cdot\sqrt{p / 2.706 \times 10^{-8}}$"),
    ("\u03c3_e/*e*",
     r"$\sigma_e/e$"),
    ("*v*(*r*) + *v*_esc(*r*) = (1 + \u221a2)\u00b7*v*(*r*) \u2248 2.414\u00b7*v*(*r*)",
     r"$v(r) + v_{\mathrm{esc}}(r) = (1 + \sqrt{2})\cdot v(r) \approx 2.414\cdot v(r)$"),
    ("*v*(*r*)", r"$v(r)$"),
]

# ------------------------------------------------------------- unicode map
UNI = {
    "\u2014": "---",
    "\u2013": "--",
    "\u2212": "$-$",
    "\u00a7": r"\S{}",
    "\u00d7": r"$\times$",
    "\u00f7": r"$\div$",
    "\u00b7": r"$\cdot$",
    "\u00b0": r"\textdegree{}",
    "\u2248": r"$\approx$",
    "\u2265": r"$\ge$",
    "\u2264": r"$\le$",
    "\u2261": r"$\equiv$",
    "\u00b1": r"$\pm$",
    "\u2192": r"$\rightarrow$",
    "\u2020": r"\dag{}",
    "\u2026": r"\ldots{}",
    "\u00be": r"$\tfrac{3}{4}$",
    "\u0394": r"$\Delta$",
    "\u03b4": r"$\delta$",
    "\u03bc": r"$\mu$",
    "\u03ba": r"$\kappa$",
    "\u03b8": r"$\theta$",
    "\u03c3": r"$\sigma$",
    "\u221a": r"$\surd$",
    "\u00fc": r'\"u',
    "\u00e1": r"\'a",
}
SUP = {"\u2070": "0", "\u00b9": "1", "\u00b2": "2", "\u00b3": "3", "\u2074": "4",
       "\u2075": "5", "\u2076": "6", "\u2077": "7", "\u2078": "8", "\u2079": "9",
       "\u207b": "-"}
SUB = {"\u2080": "0", "\u2081": "1", "\u2082": "2", "\u2083": "3", "\u2084": "4",
       "\u2085": "5", "\u2086": "6", "\u2087": "7", "\u2088": "8", "\u2089": "9"}
SUP_RE = re.compile("[" + "".join(SUP) + "]+")
SUB_RE = re.compile("[" + "".join(SUB) + "]+")

ESCAPES = {"\\": r"\textbackslash{}", "{": r"\{", "}": r"\}", "$": r"\$",
           "&": r"\&", "#": r"\#", "_": r"\_", "%": r"\%",
           "~": r"$\sim$", "^": r"\textasciicircum{}"}


class Conv:
    def __init__(self):
        self.store = {"CMT": [], "CODE": [], "URL": [], "MATH": [], "AST": []}

    def keep(self, kind, text):
        self.store[kind].append(text)
        return ph(kind, len(self.store[kind]) - 1)

    # ---------------------------------------------------------- inline text
    def inline(self, s):
        # markdown-escaped asterisk
        s = s.replace("\\*", self.keep("AST", "*"))
        # curated math
        for src, dst in MATH_MAP:
            if src in s:
                s = s.replace(src, self.keep("MATH", dst))
        # inline code spans (before URLs: some code spans hold URLs)
        s = re.sub(r"`([^`]+)`", lambda m: self.keep("CODE", m.group(1)), s)
        # bare URLs
        s = re.sub(r"https?://[^\s)\]}<>,]+",
                   lambda m: self.keep("URL", m.group(0)), s)
        # escape LaTeX specials
        s = "".join(ESCAPES.get(c, c) for c in s)
        # emphasis
        if s.count("*") % 2:
            raise SystemExit("unbalanced '*' in: " + s[:200])
        s = re.sub(r"\*\*(.+?)\*\*", r"\\textbf{\1}", s, flags=re.S)
        s = re.sub(r"\*([^*]+?)\*", r"\\emph{\1}", s, flags=re.S)
        if "*" in s:
            raise SystemExit("leftover '*' in: " + s[:200])
        # straight double quotes -> TeX quotes
        out, open_q = [], True
        for i, c in enumerate(s):
            if c == '"':
                prev = s[i - 1] if i else " "
                out.append("``" if (prev.isspace() or prev in "([-\u2014") else "''")
            else:
                out.append(c)
        s = "".join(out)
        # unicode super/subscripts
        s = SUP_RE.sub(lambda m: r"\ensuremath{^{%s}}" % "".join(SUP[c] for c in m.group(0)), s)
        s = SUB_RE.sub(lambda m: r"\ensuremath{_{%s}}" % "".join(SUB[c] for c in m.group(0)), s)
        # remaining unicode
        s = "".join(UNI.get(c, c) for c in s)
        bad = sorted({c for c in s if ord(c) > 126})
        if bad:
            raise SystemExit("unmapped unicode %r in: %s" % (bad, s[:200]))
        return s

    def restore(self, s):
        def rep(m):
            kind, i = m.group(1), int(m.group(2))
            raw = self.store[kind][i]
            if kind == "CODE":
                return self.code(raw)
            if kind == "URL":
                return r"\url{%s}" % raw
            return raw
        prev = None
        while prev != s:
            prev, s = s, PH_RE.sub(rep, s)
        return s

    def code(self, raw):
        if all(ord(c) < 127 for c in raw) and "{" not in raw and "}" not in raw:
            return r"\path{%s}" % raw
        # non-ASCII code span: typeset by hand
        body = "".join(ESCAPES.get(c, c) for c in raw)
        body = body.replace("|", r"\textbar{}")
        body = body.replace("<", r"\textless{}").replace(">", r"\textgreater{}")
        body = SUP_RE.sub(lambda m: "".join(SUP[c] for c in m.group(0)), body)
        body = "".join(UNI.get(c, c) for c in body)
        return r"\texttt{%s}" % body

    # ---------------------------------------------------------- paragraphs
    def para(self, raw):
        """Convert a paragraph that may contain inline comment placeholders."""
        pieces = re.split(r"(ZZCMTZZ\d+ZZ)", raw)
        out = []
        for piece in pieces:
            m = re.fullmatch(r"ZZCMTZZ(\d+)ZZ", piece)
            if not m:
                out.append(("text", piece))
            else:
                out.append(("cmt", self.store["CMT"][int(m.group(1))]))
        lines = []
        buf = ""
        for idx, (kind, val) in enumerate(out):
            if kind == "text":
                buf += val
                continue
            nxt = out[idx + 1][1] if idx + 1 < len(out) and out[idx + 1][0] == "text" else ""
            glue_tight = bool(nxt) and not nxt[:1].isspace()
            body = buf.rstrip()
            if body:
                lines.append(self.inline(body) + ("%" if glue_tight else ""))
            buf = ""
            lines.extend(comment_lines(val))
            if not glue_tight and nxt:
                out[idx + 1] = ("text", nxt.lstrip())
        if buf.strip():
            lines.append(self.inline(buf.strip()))
        return "\n".join(lines)


def comment_lines(text):
    return ["%" + ln for ln in text.split("\n")]


# ------------------------------------------------------------------ tables
def colspec(cell):
    cell = cell.strip()
    if cell.startswith(":") and cell.endswith(":"):
        return "c"
    if cell.endswith(":"):
        return "r"
    return "l"


def split_row(line):
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    return [c.strip() for c in line.split("|")]


def table(conv, lines):
    header = split_row(lines[0])
    spec = [colspec(c) for c in split_row(lines[1])]
    rows = [split_row(l) for l in lines[2:]]
    n = len(header)
    for r in [header] + rows:
        if len(r) != n:
            raise SystemExit("ragged table row: %r" % r)
    def row(cells):
        return " & ".join(conv.restore(conv.inline(c)) for c in cells) + r" \\"
    out = [r"\begin{center}", r"\small", r"\fitwidth{%",
           r"\begin{tabular}{" + "".join(spec) + "}", r"\toprule", row(header),
           r"\midrule"]
    out += [row(r) for r in rows]
    out += [r"\bottomrule", r"\end{tabular}}", r"\end{center}"]
    return "\n".join(out)


# ------------------------------------------------------------------ driver
def convert(md_path, tex_path, title_override=None):
    conv = Conv()
    text = open(md_path, encoding="utf-8").read()
    # pull every HTML comment out first, verbatim
    text = re.sub(r"<!--(.*?)-->", lambda m: conv.keep("CMT", m.group(1).strip("\n")),
                  text, flags=re.S)

    blocks = re.split(r"\n\s*\n", text)
    body, front = [], {}
    in_abstract = False
    in_biblio = False
    bibn = 0
    seen_title = False

    def close_abstract():
        nonlocal in_abstract
        if in_abstract:
            body.append(r"\end{abstract}")
            in_abstract = False

    for bi, blk in enumerate(blocks):
        blk = blk.strip("\n")
        if not blk.strip():
            continue
        lines = [l for l in blk.split("\n")]

        # front matter -------------------------------------------------
        if not seen_title and lines[0].startswith("# "):
            front["title"] = conv.restore(conv.inline(lines[0][2:].strip()))
            seen_title = True
            continue
        if seen_title and "authors" not in front and lines[0].startswith("**"):
            front["authors"] = lines[0]
            front["note"] = lines[1] if len(lines) > 1 else ""
            continue
        if seen_title and "date" not in front and lines[0].startswith("Draft,"):
            front["date"] = conv.restore(conv.inline(blk))
            continue

        # horizontal rule ----------------------------------------------
        if blk.strip() == "---":
            close_abstract()
            continue

        # standalone comment block --------------------------------------
        if re.fullmatch(r"ZZCMTZZ\d+ZZ", blk.strip()):
            idx = int(re.fullmatch(r"ZZCMTZZ(\d+)ZZ", blk.strip()).group(1))
            body.append("\n".join(comment_lines(conv.store["CMT"][idx])))
            continue

        # headings -------------------------------------------------------
        if lines[0].startswith("#"):
            level = len(lines[0]) - len(lines[0].lstrip("#"))
            htext = lines[0].lstrip("#").strip()
            rest = lines[1:]
            if htext.lower() == "abstract":
                close_abstract()
                body.append(r"\begin{abstract}")
                in_abstract = True
            else:
                close_abstract()
                if in_biblio:
                    body.append(r"\end{thebibliography}")
                    in_biblio = False
                cmd = r"\section*" if level <= 2 else (
                    r"\subsection*" if level == 3 else r"\subsubsection*")
                t = conv.restore(conv.inline(htext))
                body.append("%s{%s}" % (cmd, t))
                if htext.lower() == "references":
                    body.append(r"\begin{thebibliography}{XX}")
                    in_biblio = True
            if rest and any(l.strip() for l in rest):
                blk = "\n".join(rest).strip("\n")
                lines = rest
            else:
                continue

        # table ----------------------------------------------------------
        if all(l.lstrip().startswith("|") for l in lines if l.strip()):
            body.append(table(conv, [l for l in lines if l.strip()]))
            continue

        # blockquote ------------------------------------------------------
        if all(l.lstrip().startswith(">") for l in lines if l.strip()):
            inner = " ".join(l.lstrip()[1:].strip() for l in lines if l.strip())
            body.append("\n".join([r"\begin{quote}",
                                    conv.restore(conv.para(inner)),
                                    r"\end{quote}"]))
            continue

        # ordered list -----------------------------------------------------
        if all(re.match(r"\d+\.\s", l) for l in lines if l.strip()):
            items = [r"\begin{enumerate}"]
            for l in lines:
                if not l.strip():
                    continue
                m = re.match(r"(\d+)\.\s+(.*)", l, flags=re.S)
                items.append(r"\item[%s.] %s" % (m.group(1),
                                                 conv.restore(conv.para(m.group(2)))))
            items.append(r"\end{enumerate}")
            body.append("\n".join(items))
            continue

        if re.match(r"\s*[-*+]\s", lines[0]):
            raise SystemExit("unhandled bullet list: " + blk[:120])

        # bibliography entry ------------------------------------------------
        if in_biblio:
            bibn += 1
            key = re.sub(r"[^a-z]", "", blk.split(",")[0].lower())[:14] or "ref"
            key = key + "abcdefghijklmnop"[bibn % 16]
            body.append(r"\bibitem{%s} " % key + conv.restore(conv.para(blk)))
            continue

        # ordinary paragraph --------------------------------------------------
        body.append(conv.restore(conv.para(blk)))

    close_abstract()
    if in_biblio:
        body.append(r"\end{thebibliography}")

    title = title_override or front["title"]
    note_raw = front.get("note", "")
    note_cmt = comment_lines(
        "FRONT MATTER. The draft's author-block parenthetical is retained here "
        "verbatim as a source comment; the affiliation and corresponding-author "
        "line above records the decision that settled it.\n" + note_raw)

    preamble = r"""\documentclass[11pt]{article}
%% Standard article class, arXiv-compatible: no exotic packages.
\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage{lmodern}
\usepackage{textcomp}
\usepackage{amsmath}
\usepackage{amssymb}
\usepackage{booktabs}
\usepackage{graphicx}
\usepackage[margin=1in]{geometry}
\usepackage[hidelinks]{hyperref}
%% Let long paths, hashes and URLs break anywhere rather than run into the margin.
\makeatletter
\g@addto@macro\UrlBreaks{%
  \do\a\do\b\do\c\do\d\do\e\do\f\do\g\do\h\do\i\do\j\do\k\do\l\do\m%
  \do\n\do\o\do\p\do\q\do\r\do\s\do\t\do\u\do\v\do\w\do\x\do\y\do\z%
  \do\A\do\B\do\C\do\D\do\E\do\F\do\G\do\H\do\I\do\J\do\K\do\L\do\M%
  \do\N\do\O\do\P\do\Q\do\R\do\S\do\T\do\U\do\V\do\W\do\X\do\Y\do\Z%
  \do\0\do\1\do\2\do\3\do\4\do\5\do\6\do\7\do\8\do\9\do\:\do\=\do\?}
\makeatother
\Urlmuskip=0mu plus 1mu\relax
%% Shrink a table only when it is wider than the text block.
\newcommand{\fitwidth}[1]{%
  \resizebox{\ifdim\width>\linewidth\linewidth\else\width\fi}{!}{#1}}
\setlength{\parskip}{0.4\baselineskip}
\setlength{\parindent}{0pt}
\emergencystretch=3em
\sloppy
"""
    out = [preamble, r"\begin{document}", "",
           r"\title{%s}" % title,
           r"\author{Sean D. Egan\thanks{The Informed, theinformed.org."
           r" Corresponding author: sean@theinformed.org}"
           "\n" r"  \and Derek Conklin\thanks{The Informed, theinformed.org}}",
           r"\date{%s}" % front.get("date", ""),
           r"\maketitle", ""]
    out += note_cmt
    out.append("")
    out.append("\n\n".join(body))
    out.append("")
    out.append(r"\end{document}")
    open(tex_path, "w", encoding="utf-8").write("\n".join(out) + "\n")
    print("wrote", tex_path)


if __name__ == "__main__":
    convert(sys.argv[1], sys.argv[2])
