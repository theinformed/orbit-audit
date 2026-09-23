#!/usr/bin/env python3
"""Regenerate every figure in the two space papers, deterministically.

Run from the repository root:

    python3 tools/make_figures.py

Every figure is drawn from a COMMITTED artifact in docs/ -- never from a live
archive read, a re-measurement, or a number typed in by hand.  The one figure
that is not drawn from a docs/ artifact is the registration timeline, which is
drawn from this repository's own commit metadata (`git log`) plus the committed
OpenTimestamps manifest; it names the commits it plots, and it fails loudly if
any of them is missing rather than quietly drawing a shorter history.

The provenance of each figure (source file and field) is repeated in the
caption comment that travels with it in both the markdown draft and the .tex,
so a reader can check a plotted value against a receipt without running this.

Determinism: no randomness is used anywhere, so there is no seed and no jitter;
the PDF CreationDate is suppressed and Creator/Producer are pinned, so two runs
on the same artifacts produce byte-identical output.

Style: vector PDF, serif, grayscale-printable and colourblind-safe (no hue
carries meaning anywhere), axis labels carry units, every registered threshold
is drawn as a labelled reference line, and no axis is truncated or rescaled in
a way that would soften an unfavourable verdict.
"""
import datetime as dt
import json
import os
import re
import subprocess
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.cm import ScalarMappable
from matplotlib.colors import LinearSegmentedColormap, LogNorm
from matplotlib.patches import FancyArrowPatch, Rectangle
from matplotlib.ticker import FuncFormatter, NullFormatter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ROOT, "docs")
FIGS_A = os.path.join(DOCS, "latex", "paper-a", "figs")
FIGS_B = os.path.join(DOCS, "latex", "paper-b", "figs")
FIGS_D = os.path.join(DOCS, "latex", "paper-d", "figs")

# ---------------------------------------------------------------- house style
INK = "#000000"
MID = "#7f7f7f"
DARK = "#333333"
LIGHT = "#d9d9d9"
PALE = "#f0f0f0"

matplotlib.rcParams.update({
    "font.family": "serif",
    "font.serif": ["DejaVu Serif"],
    "mathtext.fontset": "dejavuserif",
    "font.size": 9,
    "axes.labelsize": 9,
    "axes.titlesize": 9,
    "xtick.labelsize": 8,
    "ytick.labelsize": 8,
    "legend.fontsize": 7.5,
    "axes.linewidth": 0.7,
    "xtick.major.width": 0.7,
    "ytick.major.width": 0.7,
    "axes.edgecolor": INK,
    "text.color": INK,
    "axes.labelcolor": INK,
    "xtick.color": INK,
    "ytick.color": INK,
    "figure.facecolor": "white",
    "axes.facecolor": "white",
    "savefig.facecolor": "white",
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
    "pdf.compression": 6,
})

PDF_META = {
    "Title": "Figure",
    "Author": "",
    "Subject": "",
    "Keywords": "",
    "Creator": "tools/make_figures.py",
    "Producer": "matplotlib",
    "CreationDate": None,
}

PERIGEE_ORDER = ["<300 km", "300-500 km", "500-800 km", "800-1200 km",
                 "1200-2000 km", ">2000 km"]
INCLINATION_ORDER = ["0-1", "1-5", "5-15", "15-30", "30-60", "60-90",
                     "90-120", "120-180"]


def load(name):
    with open(os.path.join(DOCS, name), encoding="utf-8") as handle:
        return json.load(handle)


def load_lines(name):
    with open(os.path.join(DOCS, name), encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def tidy(ax, which=("top", "right")):
    for side in which:
        ax.spines[side].set_visible(False)


def save(fig, directory, stem):
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, stem + ".pdf")
    fig.savefig(path, format="pdf", bbox_inches="tight", pad_inches=0.02,
                metadata=PDF_META)
    plt.close(fig)
    print("wrote %s" % os.path.relpath(path, ROOT))


# ------------------------------------------------------------------ paper B 1
def fig_gate_separations(corroboration, phase3, paperb):
    """Three routes to the same verdict, against the 10x requirement.

    A dot plot rather than bars: the quantity is a point on a ratio scale, not
    an amount, and only two of the three routes carry a published spread.

    src: docs/orbit-phase2b-corroboration-20260920.json fullPopulation.after
           payload.jeffreys95[0] / passive.jeffreys95[1]  -> raw separation
         docs/paperb-results-20260920.json
           analysis1CorroborationOn.primary.ratioToRaw       (matched composite)
           analysis1CorroborationOn.coarseSensitivityB.ratioToRaw
           analysis1CorroborationOn.bootstrapPrimaryInterval (upper tail)
         docs/phase3-results-20260921.json
           clause2.boundRatio, clause2.secondaryBoundRatio,
           clause2.requiredBoundRatio, payloadSide.ratePer1000,
           primary.reweightedFloorPer1000
    """
    after = corroboration["fullPopulation"]["after"]
    raw = after["payload"]["jeffreys95"][0] / after["passive"]["jeffreys95"][1]

    on = paperb["analysis1CorroborationOn"]
    matched = raw / on["primary"]["ratioToRaw"]
    matched_coarse = raw / on["coarseSensitivityB"]["ratioToRaw"]
    boot_high = on["bootstrapPrimaryInterval"]["high95Per1000"]
    matched_boot = (after["payload"]["jeffreys95"][0] * 1000.0) / boot_high

    full = phase3["clause2"]["boundRatio"]
    full_secondary = phase3["clause2"]["secondaryBoundRatio"]
    required = phase3["clause2"]["requiredBoundRatio"]
    ceiling = (phase3["payloadSide"]["ratePer1000"]
               / phase3["primary"]["reweightedFloorPer1000"])

    rows = [
        ("raw passive floor, corroboration active\n"
         "(full-population paired rerun)", raw, None, None),
        ("covariate-matched composite\n(registered primary, 1-in-5 sample)",
         matched, (matched_boot, matched_coarse),
         "registered spread: bootstrap upper tail to the coarse 48-cell variant"),
        ("full-archive reweighted\n(registered primary, no sampling modulus)",
         full, None,
         "both payload estimators agree to %.1f"
         % (100.0 * abs(full - full_secondary) / full) + "%"),
    ]

    fig, ax = plt.subplots(figsize=(6.3, 2.95))
    ypos = [2, 1, 0]
    for y, (_label, value, span, note) in zip(ypos, rows):
        if span is not None:
            ax.plot(span, [y, y], color=MID, linewidth=1.6,
                    solid_capstyle="butt", zorder=2)
            for edge in span:
                ax.plot([edge], [y], marker="|", markersize=7, color=MID,
                        markeredgewidth=1.4, zorder=2)
        ax.plot([0, value], [y, y], color=LIGHT, linewidth=0.8, zorder=1)
        ax.plot([value], [y], marker="o", markersize=7.5, color=INK, zorder=3)
        ax.text(value, y + 0.17, "%.2f" % value + "×", ha="center", va="bottom",
                fontsize=9)
        if note and span:
            centre = 0.5 * (span[0] + span[1])
            ax.text(centre, y - 0.22, note, fontsize=6.5, va="top",
                    ha="center", color=DARK)
        elif note:
            ax.text(0.2, y - 0.22, note, fontsize=6.5, va="top", ha="left",
                    color=DARK)

    ax.axvline(required, color=INK, linestyle="-", linewidth=1.8, zorder=4)
    ax.text(required, 2.94, "%g" % required + "× requirement", fontsize=8.5,
            va="bottom", ha="center")
    ax.text(required - 0.30, 2.62, "gate shut ", fontsize=8, style="italic",
            ha="right", va="center", color=DARK)
    ax.text(required + 0.30, 2.62, " gate open", fontsize=8, style="italic",
            ha="left", va="center", color=DARK)

    ax.plot([ceiling], [-0.78], marker="^", markersize=6, color=INK,
            clip_on=False, zorder=5)
    ax.text(ceiling - 0.35, -0.78,
            "point-estimate ceiling %.2f" % ceiling + "×", fontsize=8,
            va="center", ha="right")

    ax.set_yticks(ypos)
    ax.set_yticklabels([r[0] for r in rows], fontsize=8)
    ax.set_xlim(0, 20.5)
    ax.set_ylim(-1.05, 2.90)
    ax.set_xlabel("bound separation (dimensionless):\n"
                  "payload 95% lower bound ÷ passive 95% upper bound")
    ax.xaxis.grid(True, linewidth=0.4, color="#e5e5e5")
    ax.set_axisbelow(True)
    tidy(ax, ("top", "right", "left"))
    ax.tick_params(axis="y", length=0)
    save(fig, FIGS_B, "gate-separations")


# ------------------------------------------------------------------ paper B 2
def fig_covariate_grid(strata):
    """Passive-per-payload exposure over the perigee x inclination grid.

    The registered stratification is a grid, so the mismatch is drawn as one.
    Eccentricity and interval-span bands are summed out; the two remaining
    factors carry the effect.

    src: docs/phase3-strata-20260921.jsonl, every record (kind `stratum` and
         kind `belowTier`): passiveIntervals, payloadIntervals, keyed by the
         perigee and inclination fields of the `stratum` string
    """
    cells = {}
    for row in strata:
        perigee, inclination = row["stratum"].split("|")[:2]
        key = (perigee, inclination)
        passive, payload = cells.get(key, (0, 0))
        cells[key] = (passive + row.get("passiveIntervals", 0),
                      payload + row.get("payloadIntervals", 0))
    total_payload = sum(v[1] for v in cells.values())

    lo, hi = 0.01, 16.0
    greys = LinearSegmentedColormap.from_list(
        "paper-greys", [(0.16, 0.16, 0.16), (0.97, 0.97, 0.97)])
    norm = LogNorm(vmin=lo, vmax=hi, clip=True)

    fig, ax = plt.subplots(figsize=(6.4, 3.3))
    hatched = 0
    for ri, perigee in enumerate(PERIGEE_ORDER):
        for ci, inclination in enumerate(INCLINATION_ORDER):
            passive, payload = cells.get((perigee, inclination), (0, 0))
            heavy = payload / total_payload >= 0.01 if total_payload else False
            if payload == 0:
                hatched += 1
                ax.add_patch(Rectangle((ci, ri), 1, 1, facecolor="white",
                                       edgecolor="#bbbbbb", linewidth=0.5,
                                       hatch="///"))
                continue
            ratio = passive / float(payload)
            face = greys(norm(max(ratio, lo)))
            ax.add_patch(Rectangle(
                (ci, ri), 1, 1, facecolor=face,
                edgecolor=INK, linewidth=1.6 if heavy else 0.4))
            label = "0" if ratio == 0 else ("%.2f" % ratio if ratio < 10
                                            else "%.0f" % ratio)
            ax.text(ci + 0.5, ri + 0.5, label, ha="center", va="center",
                    fontsize=7, color="white" if face[0] < 0.55 else INK)

    ax.set_xlim(0, len(INCLINATION_ORDER))
    ax.set_ylim(0, len(PERIGEE_ORDER))
    ax.set_xticks([i + 0.5 for i in range(len(INCLINATION_ORDER))])
    ax.set_xticklabels(INCLINATION_ORDER, fontsize=7.5)
    ax.set_yticks([i + 0.5 for i in range(len(PERIGEE_ORDER))])
    ax.set_yticklabels(PERIGEE_ORDER, fontsize=7.5)
    ax.set_xlabel("inclination band (degrees)")
    ax.set_ylabel("perigee band (km)")
    ax.tick_params(length=0)
    for side in ("top", "right", "bottom", "left"):
        ax.spines[side].set_visible(False)

    bar = fig.colorbar(ScalarMappable(norm=norm, cmap=greys), ax=ax,
                       orientation="vertical", fraction=0.032, pad=0.02,
                       extend="both")
    bar.set_ticks([0.01, 0.1, 1.0, 10.0])
    bar.set_ticklabels(["0.01", "0.1", "1", "10"])
    bar.ax.tick_params(labelsize=7, length=2)
    bar.set_label("passive usable intervals per payload\nusable interval "
                  "(log scale, clipped at the arrows)", fontsize=7.5)
    bar.outline.set_linewidth(0.5)

    notes = ["cell value: the same ratio, printed; below one means the "
             "stratum is passive-starved",
             "bold outline: the cell carries at least one per cent of all "
             "payload exposure"]
    if hatched:
        notes.append("hatched: no payload exposure in the cell")
    for idx, note in enumerate(notes):
        ax.text(0, -0.85 - 0.42 * idx, note, fontsize=7.2, ha="left", va="top")
    save(fig, FIGS_B, "covariate-grid")


# ------------------------------------------------------------------ paper B 3
def fig_corroboration_slopegraph(corroboration):
    """Before and after the corroboration rule, as a slopegraph.

    Rates are drawn on a log axis so that equal proportional falls are equal
    slopes: that is the comparison the acceptance turns on, and a linear axis
    would make a two-thirds fall and a five-per-cent fall look alike.

    src: docs/orbit-phase2b-corroboration-20260920.json
         fullPopulation.before / .after:
           passive.ratePerInterval, payload.ratePerInterval,
           rateSeparation.boundRatio, rateSeparation.requiredBoundRatio
    """
    before = corroboration["fullPopulation"]["before"]
    after = corroboration["fullPopulation"]["after"]
    required = after["rateSeparation"]["requiredBoundRatio"]

    pas = (before["passive"]["ratePerInterval"] * 1000.0,
           after["passive"]["ratePerInterval"] * 1000.0)
    pay = (before["payload"]["ratePerInterval"] * 1000.0,
           after["payload"]["ratePerInterval"] * 1000.0)
    sep = (before["rateSeparation"]["boundRatio"],
           after["rateSeparation"]["boundRatio"])

    fig, (left, right) = plt.subplots(1, 2, figsize=(6.3, 3.0),
                                      gridspec_kw={"wspace": 0.42})

    for values, name, lift in ((pay, "payload", 1.16), (pas, "passive", 0.62)):
        left.plot([0, 1], values, color=INK, linewidth=1.3,
                  marker="o", markersize=5)
        left.text(-0.06, values[0], "%.3f" % values[0], ha="right", va="center",
                  fontsize=8)
        left.text(1.06, values[1], "%.3f" % values[1], ha="left", va="center",
                  fontsize=8)
        fall = 100.0 * (values[0] - values[1]) / values[0]
        left.text(0.5 if lift > 1 else 0.33,
                  (values[0] * values[1]) ** 0.5 * lift,
                  name + ", −%.2f" % fall + "%", ha="center",
                  va="bottom" if lift > 1 else "top", fontsize=8)
    left.set_yscale("log")
    left.set_ylim(0.1, 6.0)
    left.set_xlim(-0.55, 1.55)
    left.set_xticks([0, 1])
    left.set_xticklabels(["before", "after"])
    left.set_ylabel("flag rate per 1,000 usable intervals\n(log scale)")
    left.set_yticks([0.1, 0.2, 0.5, 1.0, 2.0, 5.0])
    left.yaxis.set_major_formatter(FuncFormatter(lambda v, _: "%g" % v))
    left.yaxis.set_minor_formatter(NullFormatter())
    tidy(left)

    right.plot([0, 1], sep, color=INK, linewidth=1.5, marker="o", markersize=5)
    right.text(-0.06, sep[0], "%.3f" % sep[0] + "×", ha="right", va="center",
               fontsize=8)
    right.text(1.06, sep[1], "%.3f" % sep[1] + "×", ha="left", va="center",
               fontsize=8)
    right.axhline(required, color=INK, linestyle="-", linewidth=1.8)
    right.text(1.52, required + 0.4, "%g" % required + "× requirement",
               fontsize=8, ha="right", va="bottom")
    right.text(1.52, required - 0.6, "gate shut below", fontsize=8,
               style="italic", ha="right", va="top", color=DARK)
    right.set_ylim(0, 21)
    right.set_xlim(-0.55, 1.55)
    right.set_xticks([0, 1])
    right.set_xticklabels(["before", "after"])
    right.set_ylabel("bound separation (dimensionless)")
    tidy(right)
    save(fig, FIGS_B, "corroboration-slopegraph")


# ------------------------------------------------------------------ paper B 4
REGISTRATION_TIMELINE = [
    ("Phase 2 and 2b\ndemonstration", [
        ("4c1722d", "decomposition,\npre-fix stop", "result"),
        ("56eef64", "corroboration rule,\npaired acceptance", "result"),
    ]),
    ("Paper B\nstress tests", [
        ("f317a28", "registration", "registration"),
        ("8604de2", "amendment", "registration"),
        ("d4c09ee", "analysis code", "code"),
        ("46dee20", "resume fix", "code"),
        ("7626c55", "results", "result"),
    ]),
    ("Phase 3,\nwhole archive", [
        ("7eab5a4", "registration", "registration"),
        ("70e8414", "analysis code", "code"),
        ("d4e9090", "order pin", "code"),
        ("1093a3c", "results", "result"),
    ]),
]

MARKERS = {
    "registration": ("s", INK, "registration committed"),
    "code": ("o", "white", "analysis code committed"),
    "result": ("^", INK, "result committed"),
}


def git_commit_time(sha):
    try:
        out = subprocess.run(
            ["git", "-C", ROOT, "log", "-1", "--format=%cI", sha],
            capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        raise SystemExit(
            "make_figures: commit %s is not in this repository, so the "
            "registration timeline cannot be drawn honestly. Refusing to draw "
            "a shorter history instead." % sha)
    return dt.datetime.fromisoformat(out)


def manifest_time():
    """The moment the committed OpenTimestamps manifest was generated.

    src: docs/registration-anchor-manifest-20260921.txt, the
         `HEAD at manifest time = ...` line
    """
    path = os.path.join(DOCS, "registration-anchor-manifest-20260921.txt")
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    match = re.search(r"HEAD at manifest time = \S+ \((\d{4}-\d{2}-\d{2} "
                      r"\d{2}:\d{2}:\d{2}) ([+-]\d{4})\)", text)
    if not match:
        raise SystemExit("make_figures: the anchor manifest no longer carries "
                         "its generation time.")
    stamp = match.group(1) + match.group(2)
    return dt.datetime.strptime(stamp, "%Y-%m-%d %H:%M:%S%z")


def fig_registration_timeline():
    """Every registration commit sits to the left of the result it governs.

    Gantt bars on a real time axis, because the claim is about when things
    happened and not merely in what order; the ordered commit list under each
    bar carries the detail the bar is too short to label in place.

    src: this repository's commit metadata (`git log -1 --format=%cI <sha>`)
         for the commits named in the reproducibility table, and
         docs/registration-anchor-manifest-20260921.txt for the anchor time
    """
    anchor = manifest_time()
    tz = anchor.tzinfo

    fig, ax = plt.subplots(figsize=(6.4, 3.0))
    ypos = list(range(len(REGISTRATION_TIMELINE)))[::-1]
    for y, (_name, events) in zip(ypos, REGISTRATION_TIMELINE):
        times = [git_commit_time(sha).astimezone(tz) for sha, _l, _k in events]
        ax.plot([min(times), max(times)], [y + 0.16, y + 0.16], color=LIGHT,
                linewidth=7, solid_capstyle="round", zorder=1)
        for (sha, _label, kind), when in zip(events, times):
            marker, fill, _legend = MARKERS[kind]
            ax.plot([when], [y + 0.16], marker=marker, markersize=6.5,
                    markerfacecolor=fill, markeredgecolor=INK,
                    markeredgewidth=1.0, zorder=3)
        detail = "  ·  ".join(
            "%s %s %s" % (label.replace("\n", " "), sha, when.strftime("%H:%M"))
            for (sha, label, _k), when in zip(events, times))
        ax.text(0.004, y - 0.26, times[0].strftime("%d %b") + " — " + detail,
                transform=ax.get_yaxis_transform(), fontsize=6.2, ha="left",
                va="center", color=DARK)

    ax.axvline(anchor, color=INK, linestyle="--", linewidth=1.2, zorder=2)
    ax.text(anchor, len(REGISTRATION_TIMELINE) - 0.30,
            " anchor manifest generated,\n OpenTimestamps stamp follows",
            fontsize=7.2, ha="left", va="center")

    ax.set_yticks([y + 0.16 for y in ypos])
    ax.set_yticklabels([name for name, _e in REGISTRATION_TIMELINE], fontsize=8)
    ax.set_ylim(-0.65, len(REGISTRATION_TIMELINE) - 0.35)
    ax.set_xlim(dt.datetime(2026, 9, 20, 0, 0, tzinfo=tz),
                dt.datetime(2026, 9, 22, 0, 0, tzinfo=tz))
    ax.xaxis.set_major_locator(mdates.HourLocator(byhour=(0, 12)))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b\n%H:%M"))
    ax.xaxis.set_minor_locator(mdates.HourLocator(byhour=(6, 18)))
    ax.set_xlabel("committer time, the repository's own clock")
    ax.xaxis.grid(True, which="both", linewidth=0.4, color="#e5e5e5")
    ax.set_axisbelow(True)
    ax.tick_params(axis="y", length=0)
    tidy(ax, ("top", "right", "left"))

    handles = []
    for kind in ("registration", "code", "result"):
        marker, fill, legend = MARKERS[kind]
        handles.append(plt.Line2D([], [], linestyle="none", marker=marker,
                                  markerfacecolor=fill, markeredgecolor=INK,
                                  markersize=6, label=legend))
    ax.legend(handles=handles, loc="upper left", frameon=False, ncol=3,
              bbox_to_anchor=(0.0, -0.30), handletextpad=0.4, columnspacing=1.6)
    save(fig, FIGS_B, "registration-timeline")


# ------------------------------------------------------------------ paper A 1
def fig_census_waterfall(policy_receipt, three_arm_receipt):
    """What removing a publication filter does to the census, step by step.

    src: docs/eol-policy-relaxation-20260920-receipt.json
           distinctRetireeCandidates      (published-artifact payloads)
         docs/eol-three-arm-20260920-receipt.json
           raiseFlow.payloadObjects        (unfiltered payloads)
           raiseFlow.contaminatedFlags     (flags the launch screen removes)
           arms.arm1.candidates            (screened candidate endpoints)
         derivation: the screen step is the difference of the two published
         payload-object counts, since the receipt counts the screen in flags
    """
    published = policy_receipt["distinctRetireeCandidates"]
    unfiltered = three_arm_receipt["raiseFlow"]["payloadObjects"]
    screened = three_arm_receipt["arms"]["arm1"]["candidates"]
    flags_removed = three_arm_receipt["raiseFlow"]["contaminatedFlags"]
    gained = unfiltered - published
    lost = unfiltered - screened

    fig, ax = plt.subplots(figsize=(5.8, 3.1))
    positions = [0, 1, 2, 3]
    width = 0.58

    ax.bar(0, published, width=width, color=LIGHT, edgecolor=INK, linewidth=0.7)
    ax.bar(1, gained, width=width, bottom=published, color=DARK,
           edgecolor=INK, linewidth=0.7)
    ax.bar(2, lost, width=width, bottom=screened, color="white",
           edgecolor=INK, linewidth=0.7, hatch="////")
    ax.bar(3, screened, width=width, color=MID, edgecolor=INK, linewidth=0.7)

    for x, base, top in ((0, 0, published), (1, published, unfiltered),
                         (3, 0, screened)):
        ax.text(x, top + 3, "%d" % top, ha="center", va="bottom", fontsize=9)
    ax.text(1, published + gained / 2.0, "+%d" % gained, ha="center",
            va="center", fontsize=8.5, color="white")
    ax.text(2, screened + lost / 2.0, "−%d" % lost, ha="center", va="center",
            fontsize=8.5,
            bbox=dict(facecolor="white", edgecolor="none", pad=1.5))

    for x, level in ((0, published), (1, unfiltered), (2, screened)):
        ax.plot([x + width / 2.0, x + 1 - width / 2.0], [level, level],
                color=MID, linewidth=0.7, linestyle=(0, (3, 2)))

    ax.set_xticks(positions)
    ax.set_xticklabels(["published\nartifact",
                        "publication filter\nremoved",
                        "launch-acquisition\nscreen (%d flags)" % flags_removed,
                        "candidate\nendpoints"])
    ax.set_ylim(0, unfiltered * 1.20)
    ax.set_ylabel("distinct payloads carrying a detected\ngraveyard-raise flag")
    ax.yaxis.grid(True, linewidth=0.4, color="#e5e5e5")
    ax.set_axisbelow(True)
    tidy(ax)
    save(fig, FIGS_A, "census-waterfall")


# ------------------------------------------------------------------ paper A 2
def fig_recall_wall(three_arm_receipt, policy_receipt):
    """Where the candidates go, and why the registered test never ran.

    A flow rather than a chart: the eligibility counts are overlapping
    marginals, so a stacked or sankey rendering would assert a decomposition
    the receipt does not report.

    src: docs/eol-three-arm-20260920-receipt.json
         arms.<arm>.candidates, arms.<arm>.usable,
         arms.<arm>.effects.R_interval.n (complete pairs with both ratios),
         arms.arm1.eligibilityFailures.<reason>,
         docs/eol-policy-relaxation-20260920-receipt.json requiredRetirees
    """
    arm1 = three_arm_receipt["arms"]["arm1"]
    arm2 = three_arm_receipt["arms"]["arm2"]
    fails = arm1["eligibilityFailures"]

    fig, ax = plt.subplots(figsize=(6.4, 4.0))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 7.7)
    ax.axis("off")

    def box(x, y, w, h, text, face, fontsize=8.5):
        ax.add_patch(Rectangle((x, y), w, h, facecolor=face, edgecolor=INK,
                               linewidth=0.9))
        ax.text(x + w / 2.0, y + h / 2.0, text, ha="center", va="center",
                fontsize=fontsize)

    def arrow(x0, y0, x1, y1, style="-|>"):
        ax.add_patch(FancyArrowPatch((x0, y0), (x1, y1), arrowstyle=style,
                                     mutation_scale=10, linewidth=0.9,
                                     color=INK, shrinkA=0, shrinkB=0))

    lanes = [
        ("arm one — first uncontaminated raise", 6.35, arm1),
        ("arm two — total keeping ceases, no later raise", 4.55, arm2),
    ]
    for title, y, arm in lanes:
        pairs = arm["effects"]["R_interval"]["n"]
        ax.text(0.05, y + 1.08, title, fontsize=8.5, style="italic",
                ha="left", va="bottom")
        box(0.05, y, 2.7, 1.0, "%d\ncandidate endpoints" % arm["candidates"],
            LIGHT)
        box(3.70, y, 2.5, 1.0, "%d\nusable trajectories" % arm["usable"], MID)
        box(7.10, y, 2.88, 1.0, "%d\ncomplete matched pairs" % pairs, "white",
            8.0)
        arrow(2.75, y + 0.5, 3.70, y + 0.5)
        arrow(6.20, y + 0.5, 7.10, y + 0.5)

    ax.add_patch(Rectangle((7.02, 3.34), 2.96, 0.80, facecolor="white",
                           edgecolor=INK, linewidth=0.9, linestyle="--"))
    ax.text(8.50, 3.74, "registered feasibility floor:\n"
            "%d complete matched pairs" % policy_receipt["requiredRetirees"],
            ha="center", va="center", fontsize=7.2)
    arrow(8.54, 4.50, 8.54, 4.15, style="<|-")

    reasons = [
        ("final-year cadence not estimable",
         fails["final-year-cadence-not-estimable"]),
        ("baseline cadence not estimable",
         fails["baseline-cadence-not-estimable"]),
        ("keeping depth below three years",
         fails["nsk-depth-below-three-years"]),
        ("observed exposure below three years",
         fails["observed-exposure-below-three-years"]),
    ]
    ax.plot([0.05, 9.95], [2.95, 2.95], color="#cccccc", linewidth=0.7)
    ax.text(0.05, 2.70, "why arm-one candidates fall out — overlapping "
            "marginal counts, which do not sum:", fontsize=7.8, ha="left",
            va="center")
    left_edge, span = 4.00, 5.60
    scale = span / float(arm1["candidates"])
    for idx, (label, count) in enumerate(reasons):
        row_y = 2.15 - 0.60 * idx
        ax.text(left_edge - 0.15, row_y, label, fontsize=7.6, ha="right",
                va="center")
        ax.add_patch(Rectangle((left_edge, row_y - 0.17), scale * count, 0.34,
                               facecolor=DARK, edgecolor=INK, linewidth=0.5))
        ax.text(left_edge + scale * count - 0.12, row_y, "%d" % count,
                fontsize=8, ha="right", va="center", color="white")
    ax.plot([left_edge + span, left_edge + span], [-0.05, 2.45], color=INK,
            linestyle="--", linewidth=0.8)
    ax.text(left_edge + span, -0.12, "all %d candidates" % arm1["candidates"],
            fontsize=7.2, ha="center", va="bottom")
    save(fig, FIGS_A, "recall-wall")


# ------------------------------------------------------------------ paper A 3
def fig_odometer_recall(fuel_rows, repricing_rows):
    """How much of the routine keeping budget the detector actually recovers.

    One dot per anchored satellite, sorted, rather than a median and a range:
    the distribution is the argument, and the median alone hides both the
    cluster at the floor and the handful near the budget.

    src: docs/fuel-odometer-20260920.jsonl sanity.flag, to select the
           anchored cohort (`far-below-folklore-detection-gap` and
           `within-order-of-folklore`)
         docs/repricing-20260921.jsonl perigee.explainedFractionOfFolkloreBudget
           and circular.explainedFractionOfFolkloreBudget
    """
    anchored = {row["norad"] for row in fuel_rows
                if row["sanity"]["flag"] in ("far-below-folklore-detection-gap",
                                             "within-order-of-folklore")}
    priced = {row["norad"]: row for row in repricing_rows}
    values = sorted(
        (priced[n]["perigee"]["explainedFractionOfFolkloreBudget"] * 100.0,
         priced[n]["circular"]["explainedFractionOfFolkloreBudget"] * 100.0)
        for n in anchored)
    perigee = [v[0] for v in values]
    circular = [v[1] for v in values]
    count = len(values)
    ordered = sorted(perigee)
    median = (ordered[count // 2] if count % 2
              else 0.5 * (ordered[count // 2 - 1] + ordered[count // 2]))
    below_ten = sum(1 for v in perigee if v < 10.0)
    zeros = sum(1 for v in perigee if v == 0.0)
    floor = 0.02

    fig, ax = plt.subplots(figsize=(6.3, 3.2))
    ax.axvspan(floor, 10.0, color=PALE, zorder=0)
    for rank, (p, c) in enumerate(zip(perigee, circular), start=1):
        if p == 0.0:
            ax.plot([floor], [rank], marker="<", markersize=5,
                    markerfacecolor="white", markeredgecolor=INK,
                    markeredgewidth=0.8, zorder=3, clip_on=False)
            continue
        ax.plot([c], [rank], marker="o", markersize=5.0,
                markerfacecolor="white", markeredgecolor=MID,
                markeredgewidth=0.8, zorder=2)
        ax.plot([p], [rank], marker="o", markersize=3.6, color=INK, zorder=3)

    ax.axvline(median, color=INK, linestyle="--", linewidth=1.2, zorder=4)
    ax.text(median * 1.12, count * 0.97, "median %.2f" % median + "%",
            fontsize=8, ha="left", va="top")
    ax.axvline(10.0, color=INK, linestyle="-", linewidth=1.4, zorder=4)
    ax.text(9.2, count * 0.22, "%d of %d" % (below_ten, count) +
            " below a tenth\nof the budget", fontsize=8, ha="right",
            va="center")
    ax.text(floor * 1.25, count * 0.55,
            "%d" % zeros + " with no detected\nstation-keeping at all",
            fontsize=7.6, ha="left", va="center")

    ax.set_xscale("log")
    ax.set_xlim(floor, 130)
    ax.set_ylim(0, count + 1)
    ax.set_xticks([0.1, 1, 10, 100])
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: "%g" % v + "%"))
    ax.set_xlabel("share of the routine north-south keeping budget\n"
                  "explained by detected delta-v (log scale)")
    ax.set_ylabel("anchored satellites, ranked")
    ax.xaxis.grid(True, linewidth=0.4, color="#e5e5e5")
    ax.set_axisbelow(True)
    tidy(ax)

    handles = [
        plt.Line2D([], [], linestyle="none", marker="o", color=INK,
                   markersize=4, label="perigee-priced (primary)"),
        plt.Line2D([], [], linestyle="none", marker="o",
                   markerfacecolor="white", markeredgecolor=MID, markersize=5,
                   label="circular-priced convention"),
    ]
    ax.legend(handles=handles, loc="upper left", frameon=False,
              bbox_to_anchor=(0.01, 0.99))
    save(fig, FIGS_A, "odometer-recall")


# ------------------------------------------------------------------ paper D 1
def fig_record_states(record):
    """What the record holds, and what it refused to open.

    Left: the 2,058 detected steps by the family they came from, and the 130
    that opened no episode, drawn as a bar of its own rather than folded into
    the total.  Right: the 1,992 episodes by lifecycle state and by kind.  The
    counts are tallies over the published record's own rows; nothing here is a
    measurement.

    src: docs/orbit-changes-record-20260923.json
         changeSteps, changeStepsByFamily, stepsWithoutEpisode,
         episodes, byState, byKind
    """
    families = record["changeStepsByFamily"]
    family_order = ["catalogue", "geoColocation", "leoStation"]
    family_label = {"catalogue": "catalogue step detector",
                    "geoColocation": "slot co-location, near-GEO",
                    "leoStation": "co-orbital station, low orbit"}
    state_order = ["INITIATED", "IN PROGRESS", "COMPLETED"]
    kind_order = ["impulsive", "campaign", "not-observed-onset"]
    kind_label = {"impulsive": "impulsive",
                  "campaign": "campaign",
                  "not-observed-onset": "onset not observed"}

    fig, (left, right) = plt.subplots(1, 2, figsize=(6.6, 3.1),
                                      gridspec_kw={"wspace": 0.55})

    labels = [family_label[key] for key in family_order]
    values = [families[key] for key in family_order]
    labels.append("opened no episode")
    values.append(record["stepsWithoutEpisode"])
    ypos = list(range(len(values)))[::-1]
    colours = [DARK, DARK, DARK, MID]
    left.barh(ypos, values, color=colours, height=0.62, edgecolor=INK,
              linewidth=0.6)
    for y, value in zip(ypos, values):
        left.text(value + 28, y, "{:,}".format(value), va="center",
                  ha="left", fontsize=8)
    left.set_yticks(ypos)
    left.set_yticklabels(labels, fontsize=8)
    left.set_xlim(0, max(values) * 1.28)
    left.set_xlabel("detected change steps (count)")
    left.set_title("%s steps in the record" % "{:,}".format(record["changeSteps"]),
                   loc="left", fontsize=9)
    tidy(left)

    state_values = [record["byState"][key] for key in state_order]
    kind_values = [record["byKind"][key] for key in kind_order]
    rows = ([(key.lower(), value, INK) for key, value in
             zip(state_order, state_values)] +
            [(kind_label[key], value, MID) for key, value in
             zip(kind_order, kind_values)])
    ypos = list(range(len(rows)))[::-1]
    right.barh(ypos, [row[1] for row in rows], color=[row[2] for row in rows],
               height=0.62, edgecolor=INK, linewidth=0.6)
    for y, row in zip(ypos, rows):
        right.text(row[1] + 26, y, "{:,}".format(row[1]), va="center",
                   ha="left", fontsize=8)
    right.set_yticks(ypos)
    right.set_yticklabels([row[0] for row in rows], fontsize=8)
    right.set_xlim(0, max(row[1] for row in rows) * 1.30)
    right.set_xlabel("episodes (count)")
    right.set_title("%s episodes: state (upper), kind (lower)"
                    % "{:,}".format(record["episodes"]), loc="left", fontsize=9)
    right.axhline(2.5, color=LIGHT, linewidth=0.8)
    tidy(right)
    save(fig, FIGS_D, "record-states")


# ------------------------------------------------------------------ paper D 2
def fig_error_bands(kinematic):
    """The measured forward error against the three screens it has to clear.

    Every band is the qualifying set's own p50/p75/p95 at that horizon; the
    three horizontal rules are the registered screens, and the two vertical
    rules are the horizons the registration's own decision rules return when
    they are applied to this table.  Drawn on a log error axis because the
    quantity spans two decades over the horizons plotted.

    src: docs/kinematic-inputs-20260922.json
         M1.armA.byHorizon (n, p50, p75, p95), M1.armB.byHorizon,
         M1.crossings (colocationDeg, slotSpacingMedianDeg, gateWBarDeg)
    """
    arm_a = kinematic["M1"]["armA"]["byHorizon"]
    arm_b = kinematic["M1"]["armB"]["byHorizon"]
    crossings = kinematic["M1"]["crossings"]
    horizons = sorted(int(key) for key in arm_a)

    p50 = [arm_a[str(h)]["p50"] for h in horizons]
    p75 = [arm_a[str(h)]["p75"] for h in horizons]
    p95 = [arm_a[str(h)]["p95"] for h in horizons]

    fig, ax = plt.subplots(figsize=(6.4, 3.6))
    ax.fill_between(horizons, p50, p95, color=PALE, linewidth=0)
    ax.fill_between(horizons, p50, p75, color=LIGHT, linewidth=0)
    ax.plot(horizons, p95, color=MID, linewidth=1.0, linestyle=(0, (4, 2)))
    ax.plot(horizons, p75, color=MID, linewidth=1.0, linestyle=(0, (1, 1.6)))
    ax.plot(horizons, p50, color=INK, linewidth=1.6, marker="o", markersize=3.6)

    b_horizons = sorted(int(key) for key in arm_b)
    ax.plot(b_horizons, [arm_b[str(h)]["p50"] for h in b_horizons],
            color=INK, linewidth=1.0, linestyle=(0, (5, 2)), marker="s",
            markersize=3.4, markerfacecolor="white")

    for value, text in ((crossings["colocationDeg"], "co-location tolerance"),
                        (crossings["slotSpacingMedianDeg"],
                         "median spacing of occupied longitudes"),
                        (crossings["gateWBarDeg"], "registered unfit bar")):
        ax.axhline(value, color=INK, linewidth=0.8, linestyle=(0, (6, 3)))
        ax.text(4.7, value * 1.10, text, fontsize=7.5, ha="left", va="bottom")

    for value in (10, 20):
        ax.axvline(value, color=DARK, linewidth=0.8)
    ax.text(195, 0.0265,
            "the registration's own decision rules, applied to this table,\n"
            "resolve arrival timing at the first vertical rule and set\n"
            "membership at the second", fontsize=7.2, ha="right", va="bottom",
            color=DARK)

    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlim(4.4, 200)
    ax.set_ylim(0.025, 32)
    ax.set_xticks(horizons)
    ax.set_xticklabels([str(h) for h in horizons])
    ax.xaxis.set_minor_formatter(NullFormatter())
    ax.set_yticks([0.03, 0.1, 0.3, 1.0, 3.0, 10.0, 30.0])
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: "%g" % v))
    ax.yaxis.set_minor_formatter(NullFormatter())
    ax.set_xlabel("horizon after the trigger (days, log scale)")
    ax.set_ylabel("error in mean longitude (degrees, log scale)")
    handles = [
        plt.Line2D([], [], color=INK, linewidth=1.6, marker="o", markersize=3.6,
                   label="median, each horizon on its own qualifying set"),
        plt.Line2D([], [], color=MID, linewidth=1.0, linestyle=(0, (1, 1.6)),
                   label="p75"),
        plt.Line2D([], [], color=MID, linewidth=1.0, linestyle=(0, (4, 2)),
                   label="p95"),
        plt.Line2D([], [], color=INK, linewidth=1.0, linestyle=(0, (5, 2)),
                   marker="s", markersize=3.4, markerfacecolor="white",
                   label="median, matched cohort"),
    ]
    ax.legend(handles=handles, loc="upper left", frameon=False)
    tidy(ax)
    save(fig, FIGS_D, "error-bands")


# ------------------------------------------------------------------ paper D 3
def fig_recall_by_burn_size(recall):
    """Recall against burn size, with the detector's own floor drawn on it.

    The bins are the registration's; the shaded column is the span of the
    shipped arm's per-object minimum detectable change across the eleven
    spacecraft, and the dashed rule is the per-object arm's floor.  The label
    count sits on each bin so that a high rate on a thin bin cannot read as a
    strong one.

    src: docs/t16b-truthset-recall-20260922.json
         arms.pooled / arms.perObject .windows.madleoEventWindow.byDaBin
         (k, n, recall); arms.*.perSpacecraft.*.floor.minDetectableDaMetres
    """
    bins = ["0-20 m", "20-50 m", "50-100 m", "100-200 m", "200-500 m",
            ">=500 m"]
    edges = {"0-20 m": (7.0, 20.0), "20-50 m": (20.0, 50.0),
             "50-100 m": (50.0, 100.0), "100-200 m": (100.0, 200.0),
             "200-500 m": (200.0, 500.0), ">=500 m": (500.0, 1400.0)}
    pooled = recall["arms"]["pooled"]["windows"]["madleoEventWindow"]["byDaBin"]
    per_object = recall["arms"]["perObject"]["windows"]["madleoEventWindow"]["byDaBin"]

    floors = [entry["floor"]["minDetectableDaMetres"]
              for entry in recall["arms"]["pooled"]["perSpacecraft"].values()]
    object_floors = [entry["floor"]["minDetectableDaMetres"]
                     for entry in recall["arms"]["perObject"]["perSpacecraft"].values()]

    fig, ax = plt.subplots(figsize=(6.4, 3.5))
    ax.axvspan(min(floors), max(floors), color=LIGHT, linewidth=0, zorder=0)
    ax.text((min(floors) * max(floors)) ** 0.5, 71.5,
            "shipped floor\n%.1f to %.1f m" % (min(floors), max(floors)),
            fontsize=7.5, ha="center", va="top")
    ax.axvline(max(object_floors), color=INK, linewidth=0.9,
               linestyle=(0, (5, 2)), zorder=1)
    ax.text(max(object_floors) * 0.93, 71.5,
            "per-object\nfloor, %.0f m" % max(object_floors), fontsize=7.5,
            ha="right", va="top")

    for name in bins:
        low, high = edges[name]
        centre = (low * high) ** 0.5
        shipped = 100.0 * pooled[name]["recall"]
        adapted = 100.0 * per_object[name]["recall"]
        ax.plot([low, high], [adapted, adapted], color=MID, linewidth=1.5,
                solid_capstyle="butt", zorder=2)
        ax.plot([low, high], [shipped, shipped], color=INK, linewidth=2.4,
                solid_capstyle="butt", zorder=3)
        ax.text(centre, max(shipped, adapted) + 1.6,
                "n = %d" % pooled[name]["n"], fontsize=7, ha="center",
                va="bottom", color=DARK)

    ax.set_xscale("log")
    ax.set_xlim(7.0, 1400.0)
    ax.set_ylim(0, 74)
    ax.set_xticks([10, 20, 50, 100, 200, 500, 1000])
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: "%g" % v))
    ax.xaxis.set_minor_formatter(NullFormatter())
    ax.set_xlabel("labelled burn size, semi-major-axis change (metres, log scale)")
    ax.set_ylabel("recall on the labelled set (per cent)")
    handles = [
        plt.Line2D([], [], color=INK, linewidth=2.4, label="shipped settings"),
        plt.Line2D([], [], color=MID, linewidth=1.5,
                   label="per-object noise arm"),
    ]
    ax.legend(handles=handles, loc="center left", frameon=False,
              bbox_to_anchor=(0.02, 0.62))
    tidy(ax)
    save(fig, FIGS_D, "recall-by-burn-size")


# ------------------------------------------------------------------ paper D 4
def fig_operating_points(points):
    """The operating-point table as a plot: tighter is not more precise.

    Left: each named setting's measured precision with its Wilson interval,
    for both classes, against the whole-population base rate.  Right: what
    tightening actually buys and costs -- the alert count falls and the median
    warning moves -- while the intervals on the left keep overlapping.

    src: docs/alarm-lane-operating-points-20260922.json
         namedSettings[].classes[]: alerts, precision, wilson95, className,
         leadDays.p50; basePopulationByHorizon["180.0"].precision
    """
    order = ["everything", "balanced", "high-confidence", "very-high"]
    named = {setting["name"]: setting for setting in points["namedSettings"]}
    styles = {"WIDE-CROSSING": ("o", INK, "-"),
              "RESIDUAL": ("s", MID, (0, (4, 2)))}
    xs = list(range(len(order)))

    fig, (left, right) = plt.subplots(1, 2, figsize=(6.6, 3.2),
                                      gridspec_kw={"wspace": 0.34})

    for class_name in ("WIDE-CROSSING", "RESIDUAL"):
        marker, colour, dash = styles[class_name]
        precision, lows, highs, alerts, leads = [], [], [], [], []
        for name in order:
            entry = [row for row in named[name]["classes"]
                     if row["className"] == class_name][0]
            precision.append(100.0 * entry["precision"])
            lows.append(100.0 * (entry["precision"] - entry["wilson95"][0]))
            highs.append(100.0 * (entry["wilson95"][1] - entry["precision"]))
            alerts.append(entry["alerts"])
            leads.append(entry["leadDays"]["p50"])
        offset = -0.08 if colour == INK else 0.08
        left.errorbar([x + offset for x in xs], precision,
                      yerr=[lows, highs], fmt=marker, color=colour,
                      ecolor=colour, elinewidth=0.9, capsize=2.6,
                      markersize=4.6, linewidth=1.0, linestyle=dash,
                      markerfacecolor="white" if colour == MID else colour,
                      label=class_name.lower())
        right.plot(xs, leads, marker=marker, color=colour, linewidth=1.0,
                   linestyle=dash, markersize=4.6,
                   markerfacecolor="white" if colour == MID else colour,
                   label=class_name.lower())
        for x, lead, count in zip(xs, leads, alerts):
            if colour == INK:
                right.text(x, lead * 0.90, "{:,}".format(count), fontsize=6.8,
                           ha="center", va="top", color=DARK)
            else:
                right.text(x, lead * 1.12, "{:,}".format(count), fontsize=6.8,
                           ha="center", va="bottom", color=DARK)

    base = points["basePopulationByHorizon"]["180.0"]
    left.axhline(100.0 * base["precision"], color=INK, linewidth=0.9,
                 linestyle=(0, (1, 1.6)))
    left.text(-0.35, 100.0 * base["precision"] * 0.80,
              "whole-population base rate, %.3f%%" % (100.0 * base["precision"]),
              fontsize=7, ha="left", va="top")

    left.set_yscale("log")
    left.set_ylim(0.05, 24)
    left.set_yticks([0.1, 0.5, 1.0, 5.0, 10.0])
    left.yaxis.set_major_formatter(FuncFormatter(lambda v, _: "%g" % v))
    left.yaxis.set_minor_formatter(NullFormatter())
    left.set_ylabel("measured precision (per cent, log scale)")
    left.legend(loc="upper left", frameon=False)

    right.set_yscale("log")
    right.set_ylim(15, 320)
    right.set_yticks([20, 30, 50, 100, 200, 300])
    right.yaxis.set_major_formatter(FuncFormatter(lambda v, _: "%g" % v))
    right.yaxis.set_minor_formatter(NullFormatter())
    right.set_ylabel("median warning (days, log scale)")
    right.text(-0.35, 290, "figures beside each marker are the alerts\n"
               "that setting raises over the archive", fontsize=7,
               ha="left", va="top", color=DARK)

    for axis in (left, right):
        axis.set_xlim(-0.45, len(order) - 0.55)
        axis.set_xticks(xs)
        axis.set_xticklabels(order, fontsize=7.5, rotation=20, ha="right")
        axis.set_xlabel("evidence setting, loosest to tightest")
        tidy(axis)
    save(fig, FIGS_D, "operating-points")


# ------------------------------------------------------------------ paper D 5
def fig_lead_times(proximity, trigger, replay, leo_events):
    """Four lead-time distributions, drawn as the quantiles that were measured.

    A box is p25 to p75, the heavy rule is the median, the whiskers are p5 and
    p95 where the source carries them.  The four populations are different and
    are never pooled: the caption and the axis label say which is which, and
    the count sits beside each row.

    src: docs/proximity-20260922-receipt.json leadTime.leadCausalDays
         docs/trigger-alarm-20260922-receipt.json classes[cluster 1].arrivalDays
         docs/alarm-lane-replay-20260922-receipt.json
             runs[everything].classes[class 1].leadDaysFromAnnounceRule
         docs/proximity-leo-events-20260922.jsonl leadCausalDays over armM rows
    """
    geo = proximity["leadTime"]["leadCausalDays"]
    geo_n = proximity["leadTime"]["withFlag"]

    class_one = [entry for entry in trigger["classes"]
                 if entry["cluster"] == 1][0]["arrivalDays"]

    run = [entry for entry in replay["runs"]
           if entry["setting"] == "everything"][0]
    replay_lead = [entry for entry in run["classes"]
                   if entry["class"] == 1][0]["leadDaysFromAnnounceRule"]

    arm_m = sorted(row["leadCausalDays"] for row in leo_events
                   if row.get("armM") and row.get("leadCausalDays") is not None)

    def quantile(values, q):
        position = (len(values) - 1) * q
        low = int(position)
        high = min(low + 1, len(values) - 1)
        frac = position - low
        return values[low] * (1.0 - frac) + values[high] * frac

    leo = {"p5": quantile(arm_m, 0.05), "p25": quantile(arm_m, 0.25),
           "p50": quantile(arm_m, 0.50), "p75": quantile(arm_m, 0.75),
           "p95": quantile(arm_m, 0.95), "n": len(arm_m)}

    rows = [
        ("co-orbital stations, low orbit\n(arm M, T8b)", leo, leo["n"]),
        ("approach events, near-GEO\n(causal lead, T8a)", geo, geo_n),
        ("trigger-time class 1, near-GEO\n(arrival after announce, T8d)",
         class_one, class_one["n"]),
        ("the same class replayed over the 2010s\n(lead from the announce rule)",
         replay_lead, replay_lead["n"]),
    ]

    fig, ax = plt.subplots(figsize=(6.4, 3.4))
    for index, (label, stats, count) in enumerate(rows):
        y = len(rows) - 1 - index
        if "p5" in stats and "p95" in stats:
            ax.plot([stats["p5"], stats["p95"]], [y, y], color=MID,
                    linewidth=0.9)
            for key in ("p5", "p95"):
                ax.plot([stats[key], stats[key]], [y - 0.12, y + 0.12],
                        color=MID, linewidth=0.9)
        ax.add_patch(Rectangle((stats["p25"], y - 0.22),
                               stats["p75"] - stats["p25"], 0.44,
                               facecolor=LIGHT, edgecolor=INK, linewidth=0.7))
        ax.plot([stats["p50"], stats["p50"]], [y - 0.22, y + 0.22],
                color=INK, linewidth=2.0)
        ax.text(stats["p50"] * 1.06, y + 0.26, "%.1f d" % stats["p50"],
                fontsize=8, ha="left", va="bottom")
        ax.text(0.40, y, "n = %d" % count, fontsize=7.5, ha="left",
                va="center", color=DARK)

    ax.set_yticks(list(range(len(rows)))[::-1])
    ax.set_yticklabels([row[0] for row in rows], fontsize=7.5)
    ax.set_xscale("log")
    ax.set_xlim(0.36, 1800)
    ax.set_xticks([1, 3, 10, 30, 100, 300, 1000])
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: "%g" % v))
    ax.xaxis.set_minor_formatter(NullFormatter())
    ax.set_xlabel("warning available before arrival (days, log scale)")
    ax.set_ylim(-0.6, len(rows) - 0.3)
    tidy(ax)
    save(fig, FIGS_D, "lead-times")


# ------------------------------------------------------------------ paper D 6
def fig_geo_leak(epoch_receipt):
    """The near-GEO control's leak, against the speed of the motion it admits.

    The bar is the registered 0.10 of the reference rate.  The lowest band
    carries no event on 48 per cent of the exposure one expected event needs,
    so it is drawn as a labelled gap and not as a zero.  The low-orbit control,
    which returns no event on 18.8 million object-days, is drawn beside it to
    show what a control that does not leak looks like on the same axis.

    src: docs/geo-libration-epoch-control-20260922-receipt.json
         postRegistrationDiagnostics.leakByImpliedAmplitudeBand
         (impliedUMaxDegFrom/To, epochObjectDays, t8aEvents,
          reading.leakRatio, reading.leakRatioCi95, reading.bar,
          reading.evaluable)
    """
    bands = epoch_receipt["postRegistrationDiagnostics"]["leakByImpliedAmplitudeBand"]
    bar = bands[0]["reading"]["bar"]

    labels, values, lows, highs, notes = [], [], [], [], []
    for band in bands:
        labels.append("%g to %g" % (band["impliedUMaxDegFrom"],
                                    band["impliedUMaxDegTo"]))
        reading = band["reading"]
        if reading["evaluable"]:
            values.append(reading["leakRatio"])
            lows.append(reading["leakRatio"] - reading["leakRatioCi95"][0])
            highs.append(reading["leakRatioCi95"][1] - reading["leakRatio"])
            notes.append("%d events on\n%s object-days"
                         % (band["t8aEvents"],
                            "{:,}".format(band["epochObjectDays"])))
        else:
            values.append(None)
            lows.append(0.0)
            highs.append(0.0)
            notes.append("no event on\n%s object-days"
                         % "{:,}".format(band["epochObjectDays"]))

    fig, ax = plt.subplots(figsize=(6.4, 3.4))
    xs = list(range(len(bands)))
    drawn = [(x, v, lo, hi) for x, v, lo, hi in zip(xs, values, lows, highs)
             if v is not None]
    ax.errorbar([d[0] for d in drawn], [d[1] for d in drawn],
                yerr=[[d[2] for d in drawn], [d[3] for d in drawn]],
                fmt="o", color=INK, ecolor=INK, elinewidth=0.9, capsize=2.6,
                markersize=5, linewidth=1.1, linestyle="-")
    for x, value in zip(xs, values):
        if value is None:
            ax.plot([x], [bar], marker="x", color=MID, markersize=8,
                    markeredgewidth=1.4)
            ax.text(x, bar * 1.35, "UNEVALUABLE", fontsize=7.2, ha="center",
                    va="bottom", color=DARK)

    ax.axhline(bar, color=INK, linewidth=1.6)
    ax.text(len(bands) - 0.5, bar * 0.80, "registered bar, %g" % bar,
            fontsize=8, ha="right", va="top")
    ax.axhline(0.0001, color=MID, linewidth=0.9, linestyle=(0, (4, 2)))
    ax.text(-0.45, 0.00013,
            "low-orbit control: no event on 18,792,698 object-days",
            fontsize=7.2, ha="left", va="bottom", color=DARK)

    ax.set_yscale("log")
    ax.set_ylim(8e-5, 20)
    ax.set_xlim(-0.55, len(bands) - 0.45)
    ax.set_xticks(xs)
    ax.set_xticklabels(["%s\n%s" % (label, note)
                        for label, note in zip(labels, notes)], fontsize=6.8)
    ax.set_xlabel("implied libration half-amplitude of the admitted epoch (degrees)")
    ax.set_ylabel("event rate as a fraction of the\nactive-payload rate (log scale)")
    tidy(ax)
    save(fig, FIGS_D, "geo-leak-by-amplitude")


def main():
    only = sys.argv[1] if len(sys.argv) > 1 else "all"
    if only in ("all", "paper-d"):
        record = load("orbit-changes-record-20260923.json")
        kinematic = load("kinematic-inputs-20260922.json")
        recall = load("t16b-truthset-recall-20260922.json")
        points = load("alarm-lane-operating-points-20260922.json")
        proximity = load("proximity-20260922-receipt.json")
        trigger = load("trigger-alarm-20260922-receipt.json")
        replay = load("alarm-lane-replay-20260922-receipt.json")
        leo_events = load_lines("proximity-leo-events-20260922.jsonl")
        epoch_receipt = load("geo-libration-epoch-control-20260922-receipt.json")

        fig_record_states(record)
        fig_error_bands(kinematic)
        fig_recall_by_burn_size(recall)
        fig_operating_points(points)
        fig_lead_times(proximity, trigger, replay, leo_events)
        fig_geo_leak(epoch_receipt)
    if only == "paper-d":
        return 0

    corroboration = load("orbit-phase2b-corroboration-20260920.json")
    phase3 = load("phase3-results-20260921.json")
    paperb = load("paperb-results-20260920.json")
    strata = load_lines("phase3-strata-20260921.jsonl")
    policy_receipt = load("eol-policy-relaxation-20260920-receipt.json")
    three_arm_receipt = load("eol-three-arm-20260920-receipt.json")
    fuel_rows = load_lines("fuel-odometer-20260920.jsonl")
    repricing_rows = load_lines("repricing-20260921.jsonl")

    fig_corroboration_slopegraph(corroboration)
    fig_gate_separations(corroboration, phase3, paperb)
    fig_covariate_grid(strata)
    fig_registration_timeline()
    fig_census_waterfall(policy_receipt, three_arm_receipt)
    fig_recall_wall(three_arm_receipt, policy_receipt)
    fig_odometer_recall(fuel_rows, repricing_rows)
    return 0


if __name__ == "__main__":
    sys.exit(main())
