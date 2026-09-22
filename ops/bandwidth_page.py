#!/usr/bin/env python3
"""The bandwidth and cadence sections of the operations page.

WHAT THIS SECTION IS FOR, AND WHAT IT IS DELIBERATELY NOT FOR
-------------------------------------------------------------
It is for making the *breakdown* visible. On 2026-08-08 this site was moving
83 GB/day of raw artifacts from bigmem to the VPS and 71% of it was one layer —
the 256 orbit-history shards, rebuilt hourly, every shard content-addressed and
therefore shipped in full every time. That was invisible until somebody
measured it, and it was findable the moment the bytes could be attributed to a
layer. Attribution is the deliverable.

It is **not** an alarm. The server allowance is 3 TB of egress and a cold visit
costs about 1.7 MB, so that side supports something like 1.75 million visits and
is nowhere near binding; the home connection is moving to unlimited. A page that
warns about bandwidth nobody is short of is a page that gets ignored on the day
it has something real to say. So this section states the numbers, states the
trend, and says plainly when a side is not a constraint.

THE THREE RULES THE DRAWING CODE MUST NOT BREAK
-----------------------------------------------
1. **An unmeasured cell never renders as a number.** ``LegTotal.bytes is None``
   means no instrument reported, which is not zero, and the cell says so in
   words. This is the same rule the watchdog grid uses for an unmeasurable
   hour, for the same reason.
2. **A projection always says it is a projection**, and says what window it was
   extrapolated from. ``Projection.sentence()`` carries both, and there is no
   code path here that prints the number without it.
3. **Wire bytes and raw bytes are never in the same column.** Every table here
   states its basis in the header. Adding a raw figure to a wire total would
   repeat the mistake that once reported one cold visit as 13.97 MB when it was
   really 1.71 MB.

WHY THE CADENCE OPTIONS CARRY A COST AND A WARNING
---------------------------------------------------
Choosing a rebuild frequency is a bandwidth decision, so each option shows what
it costs per month in measured bytes. It is also a contention decision: a
rebuild takes 32-45 minutes and the element ingest occupies :17-:23 every hour,
so hourly cannot clear it. That is displayed, not enforced — the home connection
is moving to unlimited and hourly may well be wanted back, and the page's job is
to let an operator choose knowing both things.
"""

from __future__ import annotations

import datetime as dt
import html
from typing import Sequence

from ops import bandwidth as bw
from ops import cadence as cad

DAY = 86400.0


def esc(value) -> str:
    return html.escape(str(value), quote=True)


def utc(stamp: float | None, fmt: str = "%Y-%m-%d %H:%M UTC") -> str:
    if stamp is None:
        return "never"
    return dt.datetime.fromtimestamp(stamp, dt.timezone.utc).strftime(fmt)


def human_bytes(count: float | None) -> str:
    """Bytes in words, or an explicit refusal. Never a zero standing in for None."""
    if count is None:
        return "not measured"
    for unit, size in (("TB", 1e12), ("GB", 1e9), ("MB", 1e6), ("kB", 1e3)):
        if abs(count) >= size:
            return f"{count / size:.2f} {unit}"
    return f"{int(count)} B"


def per_day(count: float | None) -> str:
    return "not measured" if count is None else f"{human_bytes(count)}/day"


#: The one cell style that must exist: something the page could not measure.
#: Grey and worded, never green and never a figure.
UNMEASURED = '<span class="dim">not measured</span>'


def measured_cell(total: bw.LegTotal, why_absent: str) -> str:
    """A leg's figure, or the reason there is not one.

    ``why_absent`` is shown instead of a number. It has to be specific: "not
    measured" alone teaches an operator that the page is broken, where "the
    Caddy access log is not enabled" teaches them what to do about it.
    """
    if total.bytes is None:
        return f'<span class="dim">not measured — {esc(why_absent)}</span>'
    return (f"<b>{esc(human_bytes(total.bytes))}</b><br>"
            f'<span class="sub">{total.records:,} measurement(s), '
            f'{esc(total.basis)} bytes</span>')


def projection_cell(projection: bw.Projection | None) -> str:
    """A month-end figure, or the reason there is not one yet.

    Below a day of records there is no number in this cell at all — only the
    measured rate and the reason. A month-end figure extrapolated from twelve
    minutes reads exactly like one extrapolated from twelve days, and the first
    one put this leg at 92% of the home allowance on a window that could not
    have contained the daily rebuild.
    """
    if projection is None:
        return UNMEASURED
    if not projection.reliable:
        return (f'<span class="dim">not yet projectable</span><br>'
                f'<span class="sub">{esc(projection.sentence())}</span>')
    return (f"{esc(human_bytes(projection.period_total))}<br>"
            f'<span class="sub">{esc(projection.sentence())}</span>')


def share_cell(byte_count: int | float | None, window: bw.AllowanceWindow | None,
               counts_this_leg: bool, absent: str = "not measured") -> str:
    """Percentage of an allowance, or the reason there is not one.

    Four distinct "no percentage" cases, kept distinct because they mean
    completely different things to whoever is reading: an allowance with no
    ceiling, an allowance this leg does not bill against, an allowance nobody
    has recorded, and a figure not yet solid enough to take a percentage of.
    Collapsing them into one grey cell would make an unlimited plan look like a
    broken instrument.
    """
    if not counts_this_leg:
        return '<span class="dim">does not count against this allowance</span>'
    if window is None:
        return '<span class="dim">no allowance recorded</span>'
    if window.unlimited:
        return '<span class="ok">no ceiling on this plan</span>'
    if byte_count is None or not window.bytes:
        return f'<span class="dim">{esc(absent)}</span>'
    fraction = byte_count / window.bytes
    return f"{fraction * 100:.1f}% of {esc(human_bytes(window.bytes))}"


def allowance_panel(key: str, allowance: bw.Allowance | None, now: float) -> str:
    if allowance is None:
        return ('<div class="card"><b>' + esc(key) + '</b><br>'
                '<span class="dim">No allowance is recorded for this connection. '
                'ops/allowances.json has no entry, and this page will not invent one.'
                '</span></div>')
    window = allowance.at(now)
    if window is None:
        current = '<span class="dim">nothing in force</span>'
    elif window.unlimited:
        current = '<span class="ok"><b>unlimited</b></span>'
    else:
        current = f"<b>{esc(human_bytes(window.bytes))} per month</b>"
    confirmed = (
        f'<span class="ok">confirmed</span>' if window and window.confirmed
        else '<span class="warn">NOT CONFIRMED — treat as a placeholder</span>'
    )
    announced = "".join(
        f'<div class="sub" style="margin-top:6px">Announced, <b>not in force</b>: '
        f'{esc("unlimited" if w.unlimited else human_bytes(w.bytes))} — {esc(w.note)}</div>'
        for w in allowance.announced
    )
    billing = ("the calendar month (UTC)" if allowance.billing_start_day == 1
               else f"from day {allowance.billing_start_day} of each month (UTC)")
    billing_note = ("" if allowance.billing_day_confirmed else
                    " — <b>assumed</b>; the real reset day has not been confirmed")
    return (
        f'<div class="card"><b>{esc(allowance.label)}</b><br>'
        f'{current} &middot; {confirmed}<br>'
        f'<span class="sub">Counts: <b>{esc(allowance.counts)}</b>. '
        f'Period: {esc(billing)}{billing_note}.</span><br>'
        f'<span class="sub">{esc(allowance.source_note)}</span>'
        f'{announced}</div>'
    )


def family_table(rows: Sequence[tuple[str, int, int]], *, basis: str,
                 empty: str) -> str:
    if not rows:
        return f'<p class="sub">{esc(empty)}</p>'
    total = sum(count for _, count, _ in rows)
    body = "".join(
        f"<tr><td><b>{esc(name)}</b></td>"
        f"<td>{esc(human_bytes(count))}</td>"
        f"<td>{(count / total * 100) if total else 0:.1f}%</td>"
        f"<td>{hits:,}</td></tr>"
        for name, count, hits in rows
    )
    return (
        '<div class="scroll"><table><thead><tr><th>Layer</th>'
        f'<th>Bytes ({esc(basis)})</th><th>Share</th><th>Measurements</th></tr></thead>'
        f"<tbody>{body}"
        f'<tr><td><b>Total</b></td><td><b>{esc(human_bytes(total))}</b></td>'
        f"<td>100.0%</td><td></td></tr></tbody></table></div>"
    )


def cadence_table(cadence_state: dict, rebuild: dict) -> str:
    """One row per allowed option, with what it costs and whether it collides."""
    cost = rebuild["bytes"]
    rows = []
    live_key = cadence_state.get("liveKey")
    requested = cadence_state.get("requested")
    for option in cadence_state["options"]:
        monthly = cost * option.runs_per_month
        marks = []
        if option.key == live_key:
            marks.append('<span class="ok">running now</span>')
        if option.key == requested:
            marks.append('<span class="st">requested</span>')
        if option.key == cadence_state.get("repoDefault"):
            marks.append('<span class="sub">repository default</span>')
        collision = ('<span class="ok">clears the element ingest</span>'
                     if option.clears_ingest else
                     '<span class="warn">overlaps the element ingest</span>')
        rows.append(
            f"<tr><td><b>{esc(option.label)}</b><br>"
            f'<code>{esc(option.key)}</code> &middot; '
            f'<code>OnCalendar={esc(option.on_calendar)}</code></td>'
            # Below one a day the per-day figure is a fraction nobody reads
            # ("0.142857/day"), so the sentence flips to the interval instead.
            f"<td>{esc(f'{option.runs_per_day:.0f} a day' if option.runs_per_day >= 1 else f'1 every {1 / option.runs_per_day:.0f} days')}<br>"
            f'<span class="sub">{option.runs_per_month:.0f} a month</span></td>'
            f"<td>{esc(human_bytes(monthly))}<br>"
            f'<span class="sub">{esc(human_bytes(cost))} a rebuild</span></td>'
            f"<td>{collision}<br><span class='sub'>{esc(option.note)}</span></td>"
            f"<td>{' '.join(marks) or '&mdash;'}</td></tr>"
        )
    return (
        '<div class="scroll"><table><thead><tr><th>Cadence</th><th>Rebuilds</th>'
        '<th>Cost per month (wire bytes)</th><th>Element-ingest collision</th>'
        '<th></th></tr></thead>'
        f"<tbody>{''.join(rows)}</tbody></table></div>"
        f'<p class="sub">Cost per rebuild: {esc(rebuild["note"])}. Monthly figures are that '
        'number multiplied by the number of runs in a 30-day month — arithmetic over a '
        'measurement, not a forecast of anything else changing.</p>'
    )


def cadence_state_lines(cadence_state: dict) -> str:
    live = cadence_state.get("live") or []
    if not cadence_state.get("measurable"):
        state = ('<span class="dim">systemd did not answer, so what is actually running '
                 'could not be read. Nothing below should be taken as the live state.</span>')
    else:
        state = (f'Running: <code>{esc(", ".join(live))}</code>'
                 + (f' ({esc(cadence_state["liveKey"])})' if cadence_state.get("liveKey")
                    else ' <span class="warn">— which is not one of the options below; '
                         'the timer has been edited by hand</span>'))
    default = cadence_state.get("repoDefault")
    default_line = (f'Repository default: <code>{esc(default)}</code>' if default else
                    '<span class="warn">The repository timer file does not match any option '
                    'on this page.</span>')
    requested = cadence_state.get("requested")
    request_line = (
        f'Requested from this page: <code>{esc(requested)}</code>, '
        f'{esc(utc(cadence_state.get("requestedAt")))}'
        if requested else
        '<span class="sub">Nothing requested — the repository default is the authority.</span>'
    )
    diverged = (
        '<div class="banner bad">The live timer is not what the repository file says and no '
        'request explains the difference. Someone has edited the unit by hand, or a drop-in '
        'was left behind. <code>systemctl cat orbit-release.timer</code></div>'
        if cadence_state.get("diverged") else ""
    )
    ambiguous = cadence_state.get("ambiguous") or []
    ambiguous_line = (
        '<div class="banner warn">Two requests carry the same timestamp '
        f'(<code>{esc(", ".join(ambiguous))}</code>) and cannot be put in order, so '
        'nothing was changed and the current cadence stands. Click one option again to '
        'settle it.</div>' if ambiguous else ""
    )
    rejected = cadence_state.get("rejected") or []
    rejected_line = (
        f'<div class="sub">Ignored, not in the allow-list: '
        f'<code>{esc(", ".join(rejected))}</code>. A request naming a cadence this page does '
        'not define is skipped and counted, never acted on.</div>' if rejected else ""
    )
    applied = cadence_state.get("applied") or []
    history = "".join(
        f'<li>{esc(utc(entry.get("at")))} — <b>{esc(entry.get("action"))}</b> '
        f'<code>{esc(entry.get("cadence"))}</code> '
        f'({esc(entry.get("onCalendar", "?"))})</li>'
        for entry in reversed(applied[-8:])
    )
    return (
        f"{diverged}{ambiguous_line}"
        f"<div>{state}</div><div>{default_line}</div><div>{request_line}</div>"
        f"{rejected_line}"
        + (f'<h4>What the reconciler has changed</h4><ul class="sub">{history}</ul>'
           if history else
           '<p class="sub">The reconciler has not changed anything yet.</p>')
    )


def buttons(cadence_state: dict) -> str:
    """The control itself. One button per allow-list entry, and nothing else.

    Each button issues a ``PUT`` to a URL that is a literal in this file. There
    is no input box, no template, and nothing an operator types anywhere in
    this page reaches the request. The endpoint is behind the same
    ``forward_auth`` as the rest of ``/space/ops``.
    """
    items = "".join(
        f'<button class="cad" data-cadence="{esc(option.key)}">{esc(option.label)}</button>'
        for option in cadence_state["options"]
    )
    return (
        f'<div class="cadbtns">{items}</div>'
        '<p class="sub" id="cadmsg">A click writes a one-word request file on the VPS. '
        'bigmem pulls it on its next publish cycle, checks the word against its own '
        'allow-list a second time, and edits its own systemd timer. Nothing on the VPS ever '
        'runs anything on bigmem. Expect the change to take effect within about ten '
        'minutes.</p>'
    )


CSS = """
.bwgrid{display:grid;gap:12px;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));
  margin:12px 0}
.cadbtns{display:flex;flex-wrap:wrap;gap:8px;margin:10px 0}
.cadbtns button{font:inherit;padding:7px 12px;border-radius:999px;cursor:pointer;
  border:1px solid var(--line);background:var(--panel);color:var(--ink)}
.cadbtns button[disabled]{opacity:.5;cursor:default}
"""

SCRIPT = """
document.querySelectorAll('.cadbtns button.cad').forEach(function (button) {
  button.addEventListener('click', function () {
    var key = button.dataset.cadence;
    var note = document.getElementById('cadmsg');
    document.querySelectorAll('.cadbtns button.cad').forEach(function (b) {
      b.disabled = true;
    });
    note.textContent = 'Requesting ' + key + '\\u2026';
    // The URL is built from the button's own data attribute, which came from
    // the allow-list rendered by ops/cadence.py. There is no free-text input
    // anywhere on this page, and the endpoint rejects any path outside the
    // same fixed set regardless of what is sent here.
    fetch('cadence/' + encodeURIComponent(key), { method: 'PUT', body: '' })
      .then(function (response) {
        note.textContent = response.ok
          ? 'Requested ' + key + '. bigmem applies it on its next publish cycle '
            + '(about ten minutes); refresh this page after that to see it confirmed.'
          : 'The endpoint refused that request (HTTP ' + response.status
            + '). Nothing changed.';
      })
      .catch(function () {
        note.textContent = 'Could not reach the endpoint. Nothing changed.';
      })
      .finally(function () {
        document.querySelectorAll('.cadbtns button.cad').forEach(function (b) {
          b.disabled = false;
        });
      });
  });
});
"""


def render(state: dict, cadence_state: dict, now: float) -> str:
    """The whole section, as markup for ops/watchdog_page.render to embed."""
    coverage: bw.Coverage = state["coverage"]
    legs = state["legs"]
    home = state["allowances"].get("home")
    vps = state["allowances"].get("vps")
    home_window = state.get("homeWindow")
    vps_window = state.get("vpsWindow")
    visit = state.get("visit")

    egress = legs[f"{bw.BIGMEM_EGRESS}/{bw.WIRE}"]
    ingress = legs[f"{bw.BIGMEM_INGRESS}/{bw.RAW}"]
    ingress_wire = legs[f"{bw.BIGMEM_INGRESS}/{bw.WIRE}"]
    vps_in = legs[f"{bw.VPS_INGRESS}/{bw.WIRE}"]
    vps_out = legs[f"{bw.VPS_EGRESS}/{bw.RAW}"]

    projections = state["projections"]

    coverage_line = (
        "This period is fully covered by measurements."
        if coverage.complete else
        f"<b>Partial period.</b> The ledger starts "
        f"{esc(utc(coverage.first_record_at))}, so these figures cover "
        f"{coverage.measured_seconds / DAY:.2f} of the "
        f"{coverage.elapsed_seconds / DAY:.2f} days elapsed in this period"
        + (f" ({coverage.fraction * 100:.1f}%)" if coverage.fraction is not None else "")
        + ". The month-to-date column is therefore a measurement of part of the month, "
          "not of all of it, and the projection is computed from the measured window "
          "rather than from the whole month so that installing the tracker mid-month "
          "does not read as a quiet one."
    )

    leg_rows = [
        ("bigmem → VPS (the publish)", egress,
         projections[f"{bw.BIGMEM_EGRESS}/{bw.WIRE}"],
         home_window, True,
         "the publish has not run since the tracker was installed"),
        ("bigmem ← upstream (NOAA, space-track)", ingress,
         projections[f"{bw.BIGMEM_INGRESS}/{bw.RAW}"],
         home_window, True,
         "no fetch has been recorded yet"),
        ("bigmem ← VPS (the CelesTrak mirror pull)", ingress_wire,
         projections[f"{bw.BIGMEM_INGRESS}/{bw.WIRE}"],
         home_window, True,
         "no mirror pull has been recorded yet"),
        ("VPS ← bigmem (same traffic, counted at the far end)", vps_in,
         projections[f"{bw.VPS_INGRESS}/{bw.WIRE}"],
         vps_window, False,
         "the WireGuard counter has not been sampled twice yet"),
        ("VPS → the public internet (visitors)", vps_out,
         projections[f"{bw.VPS_EGRESS}/{bw.RAW}"],
         vps_window, True,
         "the origin log has not been sampled twice yet"),
    ]

    def leg_row(label, total, projection, window, counts, why) -> str:
        # The share is of the PROJECTED month-end, so it inherits the
        # projection's reliability: no month-end figure means no percentage,
        # rather than a percentage of a number the page has just refused to
        # print.
        reliable = bool(projection and projection.reliable)
        against = projection.period_total if reliable else None
        absent = ("waiting on a full day of records" if projection else
                  "nothing measured on this leg yet")
        instruments = ", ".join(total.sources) or "no instrument reported"
        return (f"<tr><td><b>{esc(label)}</b><br>"
                f'<span class="sub">{esc(instruments)}</span></td>'
                f"<td>{measured_cell(total, why)}</td>"
                f"<td>{projection_cell(projection)}</td>"
                f"<td>{share_cell(against, window, counts, absent)}</td></tr>")

    rows = "".join(leg_row(*row) for row in leg_rows)

    cross = state["crossCheck"]
    cross_class = "ok" if cross.agrees else ("bad" if cross.agrees is False else "dim")
    cross_block = (
        f'<div class="banner {"" if cross_class == "dim" else cross_class}">'
        f"<b>Cross-check of the publish leg:</b> {esc(cross.sentence())}"
        "<br><span class='sub'>Two independent instruments on the same transfer. rsync counts "
        "what it put on the socket; WireGuard counts every packet through the tunnel, so it "
        "includes SSH and TCP framing rsync never sees and is expected to read a little "
        "high. They are shown side by side and never reconciled: a large gap means something "
        "is using this link that nobody wrote down, and averaging that away would hide the "
        "only interesting thing here.</span></div>"
    )

    visits = bw.visits_supported(vps_window, visit)
    if visit is None:
        visit_block = (
            '<p class="sub">No per-visit measurement has been taken. Run '
            "<code>node tools/measure-visit-payload.mjs</code> to take one.</p>"
        )
    else:
        visit_block = (
            f'<div class="banner ok"><b>One cold first visit costs '
            f'{esc(human_bytes(visit["wireBytes"]))} on the wire</b>'
            + (f" ({esc(human_bytes(visit.get('decodedBytes')))} decoded, which is what the "
               "browser sees after decompression and is NOT what is billed)"
               if visit.get("decodedBytes") else "")
            + (f", so the allowance covers roughly {visits:,.0f} such visits."
               if visits else ".")
            + f'<br><span class="sub">Measured {esc(utc(visit.get("at")))} by driving a real '
              f'browser at {esc(visit.get("url", "the live site"))} with a cold cache.'
            # Not an opinion: a stated threshold and an arithmetic comparison,
            # the same shape as every colour on this page. The threshold is
            # 100,000 visits a month because the intended audience is US Navy
            # Space Cadre and METOC officers, and a jump from tens to thousands
            # is realistic while a jump to six figures is not.
            + (" At more than 100,000 visits a month of headroom, this side is not "
               "a constraint at any visitor count this site is likely to see, and "
               "nothing here needs watching."
               if visits and visits > 100_000 else
               " Headroom is under 100,000 visits a month, which is inside the range "
               "this site could plausibly reach — worth watching.")
            + "</span></div>"
        )

    family_wire = state["families"][f"{bw.BIGMEM_EGRESS}/{bw.WIRE}"]
    family_raw = state["families"][f"{bw.BIGMEM_EGRESS}/{bw.RAW}"]
    upstream = state["families"][f"{bw.BIGMEM_INGRESS}/{bw.RAW}"]

    origin = state.get("originEgressNow") or {}
    origin_line = (
        f'<p class="sub">The public-egress row above is an <b>upper bound</b>. It comes from '
        f'the origin nginx log, which records {esc(human_bytes(origin.get("bytes")))} across '
        f'{origin.get("requests", 0):,} requests since that container started — but nginx '
        "hands its bytes to Caddy uncompressed and Caddy compresses them before they leave "
        "the machine, so the real figure is several times smaller. An exact number needs "
        "Caddy's own access log, which is not enabled; see RUNBOOK.md. An upper bound can "
        "only make an allowance look tighter than it is, which is the safe direction to be "
        "wrong in.</p>"
        if origin else
        '<p class="sub">The VPS did not report an origin byte total, so public egress is '
        "not measured at all this cycle.</p>"
    )

    return f"""
<h2>What this site moves, and what it costs</h2>
<p class="sub">Every figure here is measured at the transfer itself — <code>rsync --stats</code>
inside the publish script, the fetchers at the point their socket read returns, the WireGuard
peer counter on the VPS, and the origin access log. None of it comes from
<code>/proc/net/dev</code> or <code>vnstat</code>: bigmem also runs ComfyUI, local language
models and other agents, and the VPS runs the whole OpenClaw stack, so an interface total on
either machine is mostly not this site.
Period: {esc(utc(state['periodStart'], '%d %b'))} to {esc(utc(state['periodEnd'], '%d %b'))},
{coverage.remaining_days:.1f} days remaining. {coverage_line}</p>

<div class="bwgrid">
{allowance_panel('home', home, now)}
{allowance_panel('vps', vps, now)}
</div>

<div class="scroll"><table>
<thead><tr><th>Leg / instrument</th><th>This period, measured</th>
<th>Projected month-end</th><th>Against the allowance</th></tr></thead>
<tbody>{rows}</tbody></table></div>

{cross_block}

<p class="sub"><b>Which allowance the publish traffic actually touches.</b> It runs
bigmem&nbsp;→&nbsp;VPS, which is <em>ingress</em> at the VPS, and the VPS allowance bills
egress only — so the publish costs nothing against the 3&nbsp;TB. It crosses Sean's home
connection in the outbound direction, so it is the home allowance it consumes. Sean confirmed
both of these on 2026-08-08.</p>

{visit_block}
{origin_line}

<h3>Where the publish bytes go, by layer</h3>
<p class="sub">This is the table the whole page exists for. On 2026-08-08 one layer was 71% of
everything crossing this link and nobody knew, because nothing attributed bytes to a layer.
Figures are what rsync actually put on the socket, after compression.</p>
{family_table(family_wire, basis="wire, after rsync -z",
              empty="No publish has been measured yet in this period.")}

<h4>The same layers before compression</h4>
<p class="sub">Kept separate and never added to the column above. The gap between the two is
what <code>rsync -z</code> is worth; on 2026-08-08 it was about fourfold.</p>
{family_table(family_raw, basis="raw, on disk",
              empty="No publish has been measured yet in this period.")}

<h3>What bigmem downloads, by upstream</h3>
<p class="sub">Recorded where each fetcher's socket read returns, so a cache hit — which costs
nothing — is not counted as traffic. These are decoded lengths: the fetchers see the response
after urllib has decompressed it, so the real bytes on the wire are smaller. Labelled raw for
exactly that reason.</p>
{family_table(upstream, basis="raw, decoded",
              empty="No upstream fetch has been recorded yet in this period.")}

<h2>How often the orbit archive is rebuilt</h2>
<p class="sub">The 256 orbit-history shards are content-addressed, so every rebuild gives every
shard a new filename and ships all of them in full. That makes cadence a bandwidth decision
rather than a freshness one — the shards are a months-long element archive, not live data.
Choose an option and bigmem applies it; the buttons write a request, and
<code>ops/cadence.py</code> on bigmem validates it again before touching anything.</p>
{cadence_state_lines(cadence_state)}
{cadence_table(cadence_state, state['rebuildCost'])}
{buttons(cadence_state)}
"""
