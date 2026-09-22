#!/usr/bin/env python3
"""Render the review queue as a page — into the one tree that cannot be published.

Where this lives, and why that is the gate
------------------------------------------
This feature exists but stays off the published site, in a hidden area. The
project already has a convention for that, in two halves, and both are used
here rather than a new one being invented.

**Half one — the publish allowlist.** ``deploy/publish_data.py`` stages "only
the artifacts referenced by the current atomic manifest": it walks
``manifest.json``, verifies each SHA-256, and copies those files and nothing
else. ``pipeline/publish_vps.sh`` then rsyncs *the staged tree*, not
``public/data``. So a file under ``public/data`` that no manifest entry points
at is structurally unable to reach the VPS. This is not a theory — it is how
``public/data/manifests/`` and ``public/data/releases/`` already behave, and
they have hundreds of files on this machine and none on the server.

**Half two — put it outside ``artifacts/``.** ``deploy/prune_data.py`` deletes
unreferenced ``*.json`` files inside ``artifacts/``, so an intentionally
unpublished artifact left *there* would be garbage-collected. The existing
local-only trees sit beside it instead, and so does this one:

    public/data/review/discovery-queue.html

Nothing writes a manifest entry for it. Nothing in ``index.html`` or
``src/main.ts`` refers to it — and the frontend could not pick it up by
accident even if it appeared in the manifest, because every layer in that
application is hand-wired to a named key rather than rendered from whatever the
manifest happens to contain. There is no nav item, no route (the site is a
single-page application with one HTML file and no router), no sitemap and no
robots.txt to leak it — the repository has neither.

So this page is not merely unlinked. It is **unpublishable by construction**,
and making it public would take a deliberate manifest change that a reviewer
would see. A ``noindex`` meta tag is included as well, but it is the least of
the four controls and it is the only one that would matter if the other three
were removed.

What the copy is allowed to say
-------------------------------
The site is not claiming discoveries. It is showing its working. Every string
on this page is written to sit on that side of the line: *here is something
curious, here is what we checked, here is what we do not know*. There is no
"we discovered", no "first detection", no "unreported". The honesty label is
code-owned (``pipeline/discovery_queue.HONESTY_LABEL``) and no model may
rephrase it, because a caveat a model can phrase is a caveat a model can
weaken.
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
from pathlib import Path
from typing import Any, Sequence

from pipeline.discovery_queue import (
    ABSENCE_MEANING,
    HONESTY_LABEL,
    LITERATURE_PATH,
    QUEUE_PATH,
    REVIEWS_PATH,
    QueueEntry,
    load_queue,
    scoreboard,
    verify_chain,
)

ROOT = Path(__file__).resolve().parents[1]

# The local-only tree. Deliberately NOT `artifacts/`: see the module docstring.
DEFAULT_OUTPUT = ROOT / "public" / "data" / "review" / "discovery-queue.html"

BANNER = (
    "OPERATOR ONLY · NOT PUBLISHED · This page is written into a directory the "
    "publish step cannot stage. Nothing here has been approved for the site."
)

LEDE = (
    "This is the site's working, not the site's conclusions. Code measured "
    "something that departs from a stated expectation, wrote down the numbers "
    "and the command that reproduces them, then went and asked whether anyone "
    "has already published it. Finding that somebody has is the good outcome: "
    "it means the method rediscovered a known result from raw orbital elements, "
    "and it costs nothing to be second. Nothing on this page reaches the public "
    "site until a person approves it."
)

STATE_LABELS = {
    "awaiting-review": "Awaiting review",
    "searched-nothing-found": "Searched, nothing found",
    "prior-work-found": "Prior work found",
    "approved": "Approved for write-up",
    "rejected": "Rejected",
    "needs-more-evidence": "Needs more evidence",
    "withdrawn": "Withdrawn",
}

_STYLE = """
:root { color-scheme: light dark;
  --ink:#12161c; --dim:#5a6673; --line:#d8dee6; --bg:#fbfcfd; --card:#ffffff;
  --warn:#8a4b00; --warnbg:#fff4e2; --ok:#0d5c3c; --okbg:#e6f5ee; --code:#f2f4f7; }
@media (prefers-color-scheme: dark) { :root {
  --ink:#e6ebf2; --dim:#9aa7b6; --line:#2b3440; --bg:#0d1117; --card:#151b23;
  --warn:#ffcc8a; --warnbg:#3a2607; --ok:#8ee0b8; --okbg:#0f2c20; --code:#1c232c; } }
* { box-sizing:border-box; }
body { margin:0; padding:0 1rem 4rem; background:var(--bg); color:var(--ink);
  font:16px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif; }
main { max-width:64rem; margin:0 auto; }
.banner { background:var(--warnbg); color:var(--warn); border:1px solid currentColor;
  border-radius:.4rem; padding:.7rem 1rem; margin:1.2rem 0; font-weight:600; }
h1 { font-size:1.6rem; margin:1.4rem 0 .3rem; }
h2 { font-size:1.15rem; margin:2.2rem 0 .6rem; border-bottom:1px solid var(--line);
  padding-bottom:.3rem; }
h3 { font-size:1.02rem; margin:1.4rem 0 .4rem; }
p.lede { color:var(--dim); max-width:52rem; }
.card { background:var(--card); border:1px solid var(--line); border-radius:.5rem;
  padding:1rem 1.15rem; margin:1rem 0; }
.state { display:inline-block; font-size:.72rem; letter-spacing:.06em;
  text-transform:uppercase; border:1px solid var(--line); border-radius:.25rem;
  padding:.12rem .45rem; color:var(--dim); }
.state.prior { background:var(--okbg); color:var(--ok); border-color:currentColor; }
table { border-collapse:collapse; width:100%; font-size:.9rem; margin:.5rem 0; }
th,td { text-align:left; padding:.3rem .6rem .3rem 0; vertical-align:top;
  border-bottom:1px solid var(--line); }
th { color:var(--dim); font-weight:600; white-space:nowrap; }
td.num { font-variant-numeric:tabular-nums; }
code,pre { background:var(--code); border-radius:.25rem; font-size:.85rem; }
code { padding:.08rem .3rem; }
pre { padding:.6rem .8rem; overflow-x:auto; }
ul { margin:.35rem 0 .35rem 1.1rem; padding:0; }
li { margin:.2rem 0; }
.dim { color:var(--dim); }
.honesty { border-left:3px solid var(--line); padding-left:.8rem; color:var(--dim);
  font-size:.9rem; margin:.8rem 0; }
.scoreboard { display:flex; flex-wrap:wrap; gap:.6rem; margin:.6rem 0; }
.scoreboard div { border:1px solid var(--line); border-radius:.4rem; padding:.4rem .7rem;
  background:var(--card); font-size:.9rem; }
.scoreboard b { font-size:1.25rem; display:block; font-variant-numeric:tabular-nums; }
a { color:inherit; }
"""


def _e(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def _table(rows: Sequence[tuple[str, Any]]) -> str:
    body = "".join(
        f"<tr><th>{_e(label)}</th><td class='num'>{_e(value)}</td></tr>"
        for label, value in rows
        if value is not None
    )
    return f"<table>{body}</table>" if body else ""


def _measured_table(measured: dict[str, Any]) -> str:
    return _table([(_humanise(key), value) for key, value in sorted(measured.items())])


def _humanise(key: str) -> str:
    out = ""
    for character in key:
        if character.isupper() and out:
            out += " "
        out += character
    return out[0].upper() + out[1:] if out else key


def _literature_block(records: Sequence[dict[str, Any]]) -> str:
    if not records:
        return (
            "<p class='dim'>No literature check has been run for this candidate yet. "
            "Until one has, nothing can be said about whether it is already known.</p>"
        )
    parts: list[str] = []
    for record in records:
        searched = "".join(
            "<tr>"
            f"<td>{_e(search.get('source'))}</td>"
            f"<td>{_e(search.get('status'))}</td>"
            f"<td class='num'>{_e(search.get('hits'))}</td>"
            f"<td><a href='{_e(search.get('url'))}'>{_e(search.get('query'))}</a></td>"
            "</tr>"
            for search in record.get("searches", [])
        )
        results = record.get("results", [])
        relevant = [hit for hit in results if hit.get("relevant")]
        programme = [hit for hit in results if hit.get("matchLevel") == "programme"]
        other = [
            hit
            for hit in results
            if not hit.get("relevant") and hit.get("matchLevel") != "programme"
        ]

        def _list(items: Sequence[dict[str, Any]]) -> str:
            return "".join(
                "<li>"
                f"<a href='{_e(hit.get('url'))}'>{_e(hit.get('title'))}</a> "
                f"<span class='dim'>({_e(hit.get('source'))}"
                + (f", {_e(hit.get('year'))}" if hit.get("year") else "")
                + (f", {_e(hit.get('venue'))}" if hit.get("venue") else "")
                + ")</span></li>"
                for hit in items[:12]
            )

        hits = _list(relevant)
        programme_block = (
            "<h4>About the programme, but not about this spacecraft</h4>"
            "<p class='dim'>These name the programme and not this flight. For a member of a "
            "large constellation that is the only kind of match there will ever be, so they "
            "are shown — but they are not counted as prior work about this object, because "
            "they are not.</p>"
            f"<ul>{_list(programme)}</ul>"
            if programme
            else ""
        )
        parts.append(
            f"<p class='dim'>Searched {_e(record.get('recordedAt'))} by "
            f"{_e(record.get('recordedBy'))} using tool {_e(record.get('toolVersion'))}.</p>"
            "<table><tr><th>Index</th><th>Status</th><th>Hits</th><th>Query</th></tr>"
            f"{searched}</table>"
            + (
                f"<h4>Prior work that appears to concern this object</h4><ul>{hits}</ul>"
                if relevant
                else "<p><b>No prior work matched.</b></p>"
                f"<p class='honesty'>{_e(ABSENCE_MEANING)}</p>"
            )
            + programme_block
            + (
                f"<p class='dim'>{len(other)} further result(s) were returned and recorded "
                "but did not match this object by name.</p>"
                if other
                else ""
            )
        )
    return "".join(parts)


def _entry_block(entry: QueueEntry) -> str:
    candidate = entry.candidate
    state = entry.state
    state_class = "state prior" if state == "prior-work-found" else "state"
    subject = candidate.get("subject") or {}
    identity = (
        f"NORAD {subject.get('noradId')}"
        if subject.get("kind") == "object"
        else f"perigee {subject.get('perigeeAltitudeKm')} km"
    )
    expected = candidate.get("expected") or {}
    reproduce = candidate.get("reproduce") or {}
    alternatives = "".join(
        f"<li>{_e(item)}</li>" for item in candidate.get("alternativeExplanations", [])
    )
    reviews = "".join(
        f"<li><b>{_e(review.get('decision'))}</b> — {_e(review.get('reason'))} "
        f"<span class='dim'>({_e(review.get('recordedBy'))}, "
        f"{_e(review.get('recordedAt'))})</span></li>"
        for review in entry.reviews
    )
    return f"""
<article class="card" id="{_e(candidate.get('candidateId'))}">
  <p><span class="{state_class}">{_e(STATE_LABELS.get(state, state))}</span>
     <span class="dim"> · {_e(candidate.get('class'))} · {_e(identity)} ·
     <code>{_e(candidate.get('candidateId'))}</code></span></p>
  <h3>{_e(candidate.get('headline'))}</h3>

  <h4>What was measured</h4>
  {_measured_table(candidate.get('measured') or {})}

  <h4>What it was measured against</h4>
  {_table([
      ('Source of the expectation', expected.get('source')),
      ('Class', expected.get('class')),
      ('Verdict', expected.get('verdict')),
      ('Threshold', expected.get('threshold')),
      ('Reason', expected.get('reason')),
      ('Physics', expected.get('physics')),
      ('Catalog mission', expected.get('catalogMission')),
      ('Catalog orbit', expected.get('catalogOrbit')),
      ('Classification basis', expected.get('classificationBasis')),
      ('Classification confidence', expected.get('classificationConfidence')),
      ('Budget figure', expected.get('figure')),
      ('Derivation', expected.get('derivation')),
  ])}
  <p><b>Margin.</b> {_e(candidate.get('margin'))}</p>
  <p class="dim">Observed {_e((candidate.get('observedWindow') or {}).get('from'))}
     to {_e((candidate.get('observedWindow') or {}).get('to'))} ·
     detector {_e(candidate.get('detectorVersion'))} ·
     fingerprint <code>{_e(str(candidate.get('fingerprint'))[:16])}</code></p>

  <h4>Reproduce it</h4>
  <pre>{_e(reproduce.get('command'))}</pre>
  <pre>{_e(json.dumps(reproduce.get('inputs') or {}, indent=2))}</pre>

  <h4>What else could produce this</h4>
  <ul>{alternatives}</ul>

  <h4>Has anybody already published this?</h4>
  {_literature_block(entry.literature)}

  <p class="honesty">{_e(HONESTY_LABEL)}</p>

  {"<h4>Review history</h4><ul>" + reviews + "</ul>" if reviews else ""}
  <h4>Record a decision</h4>
  <pre>python3 -m pipeline.discovery_queue review {_e(candidate.get('candidateId'))} \\
    --decision approved --by human:sean --reason "..."</pre>
  <p class="dim">Approval records that Sean is content for this to be written up.
     It does not publish anything, and there is no code path that could: the
     detector and the queue contain no function that writes a manifest entry or
     an artifact. Putting an approved finding on the site is a separate,
     deliberate act.</p>
</article>
"""


def _deferral_block(deferrals: Sequence[dict[str, Any]]) -> str:
    if not deferrals:
        return ""
    cards = "".join(
        f"""<article class="card">
      <p><span class="state">Not yet computable</span>
         <span class="dim"> · {_e(item.get('class'))}</span></p>
      <p><b>Needs:</b> {_e(item.get('needs'))}</p>
      <p>{_e(item.get('why'))}</p>
      {_table([(_humanise(key), value) for key, value in sorted((item.get('have') or {}).items())])}
    </article>"""
        for item in deferrals
    )
    return (
        "<h2>Detectors that cannot run yet</h2>"
        "<p class='lede'>These are not empty results. They are detectors whose inputs "
        "do not exist on this disk yet, listed so that a silent absence never gets "
        "mistaken for a clean sweep. The orbital archive began capturing on "
        "2026-08-07 and cannot be back-filled at this installation's published "
        "query rate, so several of these resolve with nothing but elapsed time.</p>"
        + cards
    )


def _false_alarm_block(false_alarms: dict[str, Any]) -> str:
    events = false_alarms.get("events") or []
    if not events:
        return ""
    rows = "".join(
        "<tr>"
        f"<td>{_e(event.get('name'))}</td>"
        f"<td>{_e(event.get('objectType'))}</td>"
        f"<td>{_e(event.get('signature'))}</td>"
        f"<td class='num'>{_e(event.get('deltaVMetresPerSecond'))}</td>"
        f"<td>{_e(event.get('startAt'))}</td>"
        "</tr>"
        for event in events
    )
    return (
        "<h2>Known false alarms from the same sweep</h2>"
        "<p class='lede'>Debris fragments and spent rocket stages have no propulsion, "
        "so a propulsive signature reported on one of them is wrong — on the "
        "strength of the catalogue entry that says what it is. A fragment cannot "
        "burn, but an entry can be wrong or out of date, and that is the one way a "
        "line below could be something else. "
        "They are the free negative control, and they are shown here rather than "
        "filtered out because they are the honest measure of how much to believe "
        "everything above. They are never queued as findings.</p>"
        "<table><tr><th>Object</th><th>Type</th><th>Signature</th>"
        "<th>&Delta;v m/s</th><th>From</th></tr>"
        f"{rows}</table>"
    )


def render(
    entries: Sequence[QueueEntry],
    *,
    sweep: dict[str, Any] | None = None,
    generated_at: str | None = None,
) -> str:
    counts = scoreboard(entries)
    tiles = "".join(
        f"<div><b>{count}</b>{_e(STATE_LABELS.get(state, state))}</div>"
        for state, count in sorted(counts.items())
    )
    chains = {
        "candidates": verify_chain(QUEUE_PATH),
        "literature": verify_chain(LITERATURE_PATH),
        "reviews": verify_chain(REVIEWS_PATH),
    }
    chain_rows = "".join(
        "<tr>"
        f"<td>{_e(name)}</td>"
        f"<td class='num'>{_e(report.get('lines'))}</td>"
        f"<td>{'intact' if report.get('intact') else 'BROKEN at line ' + str(report.get('brokeAt'))}</td>"
        f"<td><code>{_e(str(report.get('head') or '')[:16])}</code></td>"
        "</tr>"
        for name, report in chains.items()
    )
    sweep = sweep or {}
    stamp = generated_at or dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")

    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex, nofollow, noarchive">
<title>Discovery review queue — operator only</title>
<style>{_STYLE}</style>
</head><body><main>
<div class="banner">{_e(BANNER)}</div>
<h1>Discovery review queue</h1>
<p class="lede">{_e(LEDE)}</p>

<h2>Where this stands</h2>
<div class="scoreboard">{tiles or "<div><b>0</b>nothing queued</div>"}</div>
{_table([
    ('Generated', stamp),
    ('Detector version', sweep.get('detectorVersion')),
    ('Element-set intervals examined', (sweep.get('inputs') or {}).get('intervals')),
    ('Catalog objects examined', (sweep.get('inputs') or {}).get('catalogObjects')),
    ('Archive window from', (sweep.get('inputs') or {}).get('windowFrom')),
    ('Archive window to', (sweep.get('inputs') or {}).get('windowTo')),
    ('Highest Kp over the window', (sweep.get('inputs') or {}).get('kpMaxOverWindow')),
])}

<h2>Ledger integrity</h2>
<p class="lede">Each stream is append-only and hash-chained: every line records the
SHA-256 of the line before it, so editing, deleting or reordering anything breaks
every hash after it. Verify independently with
<code>python3 -m pipeline.discovery_queue verify</code>.</p>
<table><tr><th>Stream</th><th>Lines</th><th>Chain</th><th>Head</th></tr>{chain_rows}</table>

<h2>Candidates</h2>
{"".join(_entry_block(entry) for entry in entries) or
 "<p class='dim'>Nothing is queued. That is a real result, not an error state — "
 "check the deferrals below before reading it as a clean sweep.</p>"}

{_deferral_block(sweep.get('deferrals') or [])}
{_false_alarm_block(sweep.get('falseAlarms') or {})}

<h2>What is deliberately not here</h2>
<ul>
<li><b>Nothing about an object the eligibility gate denies.</b> The gate in
<code>docs/mission-speculation-design.md</code> §1.3–1.5 applies to this feature
unchanged, and it makes no reference to nationality: an opaque US object is denied
on exactly the same terms as an opaque Russian or Chinese one. Denied objects
produce no record at all, and their absence carries no marker — a visible
redaction badge is an assessment by implication.</li>
<li><b>Nothing relating one spacecraft to another.</b> §1.6 is a decision by the
site owner and it is enforced structurally: a candidate's subject can hold one
object or one anonymous altitude band, and the queue writer rejects any record
carrying a relational field at any depth.</li>
<li><b>No automatic publication.</b> Not disabled, not flagged off — absent.</li>
<li><b>No model anywhere on this path.</b> Detection, thresholds, ranking and
approval are all code or people. A model never decides that something is
interesting. Every sentence on this page was either written by code or quoted
from a search result &mdash; no language model wrote any of it, and the honesty
label above each candidate is a fixed string in the source rather than
generated prose, because a caveat that can be rephrased is a caveat that can be
weakened.</li>
</ul>
</main></body></html>
"""


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--sweep-json",
        type=Path,
        default=None,
        help="a sweep written by `python3 -m pipeline.discovery --sweep`, for the "
        "deferrals and the false-alarm control",
    )
    args = parser.parse_args(argv)

    if args.output.resolve().parent.name == "artifacts":
        raise SystemExit(
            "refusing to write into artifacts/: that directory is the publish "
            "allowlist's source and is garbage-collected by deploy/prune_data.py. "
            "The review page belongs in a sibling directory the publish step "
            "cannot stage."
        )

    sweep: dict[str, Any] = {}
    if args.sweep_json and args.sweep_json.is_file():
        # A sweep takes minutes and the file is written in place, so a render
        # started while one is running finds a truncated or empty file. The
        # queue is the point of this page and it is read from elsewhere, so a
        # bad sweep costs the deferrals and the false-alarm control, not the
        # page. Say so out loud rather than failing or, worse, silently
        # rendering as though there were no deferrals at all.
        try:
            sweep = json.loads(args.sweep_json.read_text())
        except (OSError, json.JSONDecodeError) as error:
            print(
                f"WARNING: {args.sweep_json} is unreadable ({error}); rendering the queue "
                "without the deferrals or the false-alarm control. Re-run the sweep."
            )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render(load_queue(), sweep=sweep), encoding="utf-8")
    print(f"wrote {args.output} ({args.output.stat().st_size} bytes, not published)")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
