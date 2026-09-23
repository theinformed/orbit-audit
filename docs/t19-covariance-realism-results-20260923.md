# T19 results — covariance realism of a megaconstellation's public ephemerides

**Registration:** `docs/t19-covariance-realism-preregistration-20260922.md`, committed **alone**
as `d246fb4` before any code in this track existed.
**Collected:** 2026-09-22 19:44 to 2026-09-23 00:36 UTC. **Host:** `pc`.
**Archive:** `/home/sdegan/space-supplemental-history/starlink/` — outside the repository; raw
files never leave that host and nothing raw is republished.

**The word throughout is SELF-CONSISTENCY, never accuracy.** A later issue is a later
prediction, not a measurement. Every residual here is a disagreement between two predictions
and attributes to neither.

---

## 1. Headline

Two publication cycles of one megaconstellation's public ephemerides — **15,137 files,
11,137 spacecraft, 3,999 overlapping pairs** — measured against the operator's own published
covariance.

1. **The file advertises 72 hours of prediction and contains 48.** Beyond a lead of
   **exactly 48.000 h measured from its own start**, a newer issue republishes the previous
   issue's states **verbatim** — identical in all ten printed digits, which at a print
   precision of 1e-10 km is identity and not coincidence. Measured on 200 pairs scanned at
   one-hour resolution: 194 have such a tail, its onset has minimum, median and maximum all
   **48.000 h**, and **not one** of the 200 has an identical region that is not a single
   contiguous tail. At 72 h the republished covariance is identical too, to a relative
   difference of **exactly zero**.

2. **At long lead the published covariance is not a propagated uncertainty.** Across the
   11,137 files of one issue, the number of distinct published one-sigma values collapses from
   **11,137 of 11,137** at 0–12 h lead to **12 / 13 / 13** (radial / in-track / cross-track)
   across 10,959 files from 58 h out to 72 h — 0.11%. Replicated in the second issue at
   **7 / 8 / 8** of 3,945. The registration's licence condition for the word *placeholder* —
   under 1% of the file count in **every** issue measured — is met at 72 h on all three columns.
   The values are round: 300 m (71.8%), 3,800 m (64.9%), 500 m (64.9%).

3. **The in-track sigma falls with lead, which no propagated uncertainty can do.** Between
   24 h and 36 h the in-track value decreases in **7,388 of 11,137 files (66.3%)**, replicated
   at **64.6%** in the second issue; the median goes 3,300.1 m at 24 h to 2,500.0 m at 36 h and
   is still 2,514.8 m at 48 h. §6.3 derives why a forward prediction from one epoch cannot
   produce that.

4. **Containment holds to 36 h and then collapses.** Against the earlier issue's own published
   covariance, the fraction of pairs inside the 95% chi-square contour is **97.7% [96.6, 98.5]
   at 8 h**, rising to **99.0% [98.6, 99.2] at 36 h** — the covariance is *conservative* there,
   too large by a factor of 1/k = 1.7 to 7.4 — and then falls to **16.1% [15.0, 17.4] at 48 h**,
   where the covariance is **4.47× too small** and the cross-track column is **8.9× too small**
   with only **18.4% [17.1, 19.7]** contained. The collapse sits exactly where the earlier
   issue's own 48-hour splice begins: at that lead it is republishing its predecessor's states
   while the later issue is still fresh, and the published covariance does not account for
   states that are eight hours staler than the header implies.

5. **The consequence.** At 48 h lead, a two-dimensional collision probability computed from the
   published covariance is **20.0× too high** at zero miss and **2×10⁸ times too low** at a
   1 km miss along the projected radial axis. At 24 h lead, where the covariance is too large,
   the signs reverse: **27× too low** at zero miss and **57× too high** at a 100 m radial miss.
   The direction of the error is a property of the encounter geometry, so a single ratio without
   its miss distance would be a misrepresentation and none is quoted.

**This is a first public statement, not a discovery** (§2), and it does not say anyone's data is
wrong. It says what the published files contain, measured from the published files.

---

## 2. What is new, what is not, and the deduction against interest

The overlap self-consistency residual is **occupied**: arXiv:2510.11242 compares each
three-day ephemeris against overlapping segments from newer issues over about 1,500 spacecraft
and two months (~300 m position RMSE for stable spacecraft, ~600 m for deorbiting ones);
arXiv:2605.19850 runs the sibling experiment with the next element set as the reference over
24,641 pairs; and the open archive project `Kira-Ryan/ephemera` has been collecting these files
daily since August 2026 and names its metric "self-consistency, contaminated by re-plans" in
those words. None of that is claimed here.

The containment method is **occupied** and is used here unchanged: Park, E. S. et al.,
*Statistical Covariance Realism [for] a Commercial Space Situational Awareness Radar Network*,
AMOS 2019 (LeoLabs) — Mahalanobis distance of overlap residuals against a chi-square
expectation, reporting 95.2% of distances at or below 4.0 with realism holding through seven
days. Related: Poore et al., *Covariance and Uncertainty Realism in Space Surveillance and
Tracking* (2016).

**What is unoccupied is the pairing.** Nobody located has taken the public files' own overlap
residual and tested it against the operator's own published covariance at the same lead. That
pairing, and the distinct-value census of §6, is the whole of the contribution.

**Deduction against interest, kept.** The conjunction-assessment literature describes screening
organisations as routinely checking owner/operator ephemeris covariances for realism. This may
therefore be well known inside that practice and simply unpublished. The framing is **first
public statement**, not discovery. Nothing here says anyone's data is wrong.

---

---

## 3. What was collected, and the etiquette evidence

Two passes of `tools/starlink_collect.py`, both from `pc`, both against the registered
etiquette: 0.5 s between file requests, no retries, no redirects, no proxy, a 32 MiB body
ceiling, the attempt timestamp written before the socket opens, and one ledger line per attempt
including the attempts that were refused.

| | pass A | pass B |
|---|---|---|
| clock (injected) | 2026-09-22T19:52Z | 2026-09-22T23:10Z |
| manifest | **304, unchanged** — the held body reused | 200, a new issue cycle |
| names in manifest | 11,137 | 11,136 |
| requested | 10,887 | 4,000 (registered deterministic spread) |
| written | 10,887 | 4,000 |
| already held, not requested | 250 (T16a's) | 0 |
| failures | **0** | **0** |
| provider refusals | **0** | **0** |

**15,137 ephemeris files held**, 22.1 GB of response bodies, **12 GB on disk gzipped**. Disk on
`pc`: **135 GiB free (86%) before, 125 GiB free (87%) after**; the archive's own growth is
11.8 GB and the rest of the movement is other work on a shared filesystem. No halt marker stands.

The two cycles are cleanly separated by their own creation stamps: cycle 1 created
09:00:14–12:29:35 UTC (11,137 files), cycle 2 created 17:00:11–20:33:10 UTC (4,000 files).
Every file declares `ephemeris_source: blend` and frame `UVW`.

### 3.1 A live 304, and the defect it exposed

The first T19 manifest request returned **HTTP 304**, answering an `If-None-Match` bound to the
body T16a already held, with `Last-Modified: Tue, 22 Sep 2026 12:29:52 GMT` — the end of cycle
1's creation window. **This provider sends cache validators and honours conditional requests**,
where T16a measured the supplemental element-set endpoint as sending neither and recorded a live
304 there as unproven. The two statements are about different providers and neither transfers.

The inherited etiquette engine raises on any status outside 2xx and reads the raised error as a
transport failure, so it wrote a permanent halt marker for the politest outcome the protocol
has. The marker was cleared with a recorded reason and archived
(`state/halts/HALTED-20260922T194347Z.json`); **no provider refusal occurred**. The collector now
installs a transport that returns an answered 304 and falls back to the manifest already on
disk — which is exactly what a 304 asserts that manifest to be. `tools/supgp_ingest.py` was not
modified; it belongs to T16a.

### 3.2 The collector, exercised at two injected clocks

Registered as a **daily collector with no timer and no cron entry**, taking a clock so its
cadence can be driven rather than waited for. Driven against the real state file and the real
archive, socket-free:

| injected clock | verdict | reason |
|---|---|---|
| 2026-09-22T19:45Z | **due** | no rule refuses this pass |
| 2026-09-22T20:30Z | **refused** | "the manifest was fetched 2280 s ago and the interval is 7200 s. An interval is a floor on how often we may ask, never permission to ask." |
| 2026-09-22T22:45Z | **due** | last pass 10380 s ago, 1 in the last 24 h |
| 2026-09-22T23:10Z | **due** | last pass 11880 s ago, 1 in the last 24 h — and this one ran, fetching cycle 2 |

Nothing here waits for tomorrow. The four-passes-per-day ceiling is exercised in the offline
tests, both with the guard and with the guard disabled.

---

## 4. The pairs, and what the publication cadence makes unreachable

**3,999 pairs accepted**, one per spacecraft holding two issues; 1 rejected for an overlap under
12 h; 7,137 spacecraft hold a single issue and contribute to the census only. **0 pairs failed to
measure.**

Publication cadence, measured rather than assumed: **median 8.067 h**, p05–p95 7.90–8.22 h,
minimum 4.15 h, maximum 11.30 h.

**Leads 1, 3 and 6 h are UNREACHABLE, exactly as the registration predicted in advance.** The
shortest reachable lead is the cadence, because the later issue's span begins there. They are
reported as `n = 0` and are not filled by pairing non-adjacent issues, which would silently
change what the cadence means. The registered native grid — 8, 12, 16, 24, 36, 48, 60, 72 h —
carries the measurement.

Exclusions, all counted:

| class | n | rule |
|---|---:|---|
| calibration hold-out | 397 | catalogue field ending in `0`; buys the re-plan threshold and nothing else |
| off-cadence re-issue | 2 | \|cadence − median\| > 2 h |
| re-plan | 20 (0.56%) | semi-major-axis step > 278.4 m |
| **reported** | **3,580** | |

The re-plan threshold is 3 × the 99th percentile of the semi-major-axis step on the hold-out
(hold-out p99 = 92.8 m, hold-out median 1.14 m, reported median 1.20 m). **Excluding re-plans
moves containment by at most 0.36 points at every lead out to 48 h** (table in §5), so the rule
is not doing the covariance's work. At 60 and 72 h it moves the number by ~10 points, but those
leads rest on 74 pairs and are qualified in §5.2.

### 4.1 The interpolation floor, measured not assumed

The two issues' 60 s grids proved to be **aligned** — every comparison instant matched an exact
record, so **no interpolation entered any reported residual**. The registered leave-one-out
self-test was run anyway on 40 real files, 320 samples: **median 4.2 mm, p95 16.0 mm, max
89 mm**, against a registered limit of 1 m. Four orders of magnitude below the smallest residual
reported here. Interpolation is not a floor on anything in this document.

---

## 5. Containment against the published covariance

One residual per pair per lead — the unit of replication is the **(pair, lead)**, never the
instant, because instants inside one pair are a smooth function of time along one orbit and
pooling them would manufacture an interval a hundred times too narrow. Every interval is a
Wilson score interval at 95% on the number of pairs.

`k` is the factor by which the published covariance would have to be multiplied to be
calibrated: **`k` below 1 means the published covariance is too large, above 1 too small.**
`k lower bound` is `k/√2`, the bound that applies if the later issue's own state error at the
instant were as large as the earlier issue's; it is smaller, so the true scale lies between them.

| lead (h) | pairs offered | identical-state | informative n | contained (m² ≤ 7.8147) | Wilson 95% | m ≤ 4.0 | median m² | k robust | k lower bound | k₉₅ | median \|d\| (m) | p95 \|d\| (m) |
|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 0 | 0 | UNREACHABLE at this lead: no pair overlaps it | | | | | | | | |
| 3 | 0 | 0 | 0 | UNREACHABLE at this lead: no pair overlaps it | | | | | | | | |
| 6 | 0 | 0 | 0 | UNREACHABLE at this lead: no pair overlaps it | | | | | | | | |
| 8 | 998 | 0 | 998 | **97.7%** | [96.6, 98.5] | 98.8% | 0.786 | 0.577 | 0.408 | 0.764 | 35.8 | 181.5 |
| 12 | 3,580 | 0 | 3,580 | **97.7%** | [97.1, 98.1] | 98.6% | 0.463 | 0.442 | 0.313 | 0.663 | 68.6 | 333.2 |
| 16 | 3,580 | 0 | 3,580 | **98.1%** | [97.6, 98.5] | 98.8% | 0.237 | 0.317 | 0.224 | 0.556 | 107.5 | 558.7 |
| 24 | 3,580 | 0 | 3,580 | **98.5%** | [98.1, 98.9] | 99.0% | 0.086 | 0.190 | 0.135 | 0.358 | 174.8 | 889.3 |
| 36 | 3,580 | 0 | 3,580 | **99.0%** | [98.6, 99.2] | 99.4% | 0.044 | 0.136 | 0.096 | 0.255 | 169.4 | 1,149.2 |
| 48 | 3,533 | 0 | 3,533 | **16.1%** | [15.0, 17.4] | 26.5% | 47.363 | 4.474 | 3.164 | 7.552 | 1,117.9 | 4,007.3 |
| 60 | 3,533 | 3,459 | 74 | **74.3%** | [63.3, 82.9] | 83.8% | 2.032 | 0.927 | 0.655 | 3.307 | 2,620.8 | 18,411.8 |
| 72 | 3,533 | 3,459 | 74 | **63.5%** | [52.1, 73.6] | 70.3% | 3.633 | 1.239 | 0.876 | 5.055 | 3,535.4 | 28,204.9 |

**Read the `identical-state` column first.** At 60 and 72 h, 3,459 of 3,533 pairs — **97.9%** —
publish the *same state* in both issues, so there is no residual to test and those pairs are
excluded from the containment. Where the states are identical at 72 h the published covariance
is identical too, to a relative difference of **exactly zero**. §5.1 is about what happens if
they are counted instead.

### 5.1 What happens if a republished state is counted as containment

| lead (h) | pairs offered | identical-state | informative n | contained (m² ≤ 7.8147) | Wilson 95% | m ≤ 4.0 | median m² | k robust | k lower bound | k₉₅ | median \|d\| (m) | p95 \|d\| (m) |
|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 0 | 0 | UNREACHABLE at this lead: no pair overlaps it | | | | | | | | |
| 3 | 0 | 0 | 0 | UNREACHABLE at this lead: no pair overlaps it | | | | | | | | |
| 6 | 0 | 0 | 0 | UNREACHABLE at this lead: no pair overlaps it | | | | | | | | |
| 8 | 998 | 0 | 998 | **97.7%** | [96.6, 98.5] | 98.8% | 0.786 | 0.577 | 0.408 | 0.764 | 35.8 | 181.5 |
| 12 | 3,580 | 0 | 3,580 | **97.7%** | [97.1, 98.1] | 98.6% | 0.463 | 0.442 | 0.313 | 0.663 | 68.6 | 333.2 |
| 16 | 3,580 | 0 | 3,580 | **98.1%** | [97.6, 98.5] | 98.8% | 0.237 | 0.317 | 0.224 | 0.556 | 107.5 | 558.7 |
| 24 | 3,580 | 0 | 3,580 | **98.5%** | [98.1, 98.9] | 99.0% | 0.086 | 0.190 | 0.135 | 0.358 | 174.8 | 889.3 |
| 36 | 3,580 | 0 | 3,580 | **99.0%** | [98.6, 99.2] | 99.4% | 0.044 | 0.136 | 0.096 | 0.255 | 169.4 | 1,149.2 |
| 48 | 3,533 | 0 | 3,533 | **16.1%** | [15.0, 17.4] | 26.5% | 47.363 | 4.474 | 3.164 | 7.552 | 1,117.9 | 4,007.3 |
| 60 | 3,533 | 3,459 | 3,533 | **99.5%** | [99.2, 99.7] | 99.7% | 0.000 | 0.000 | 0.000 | 0.000 | 0.0 | 0.0 |
| 72 | 3,533 | 3,459 | 3,533 | **99.2%** | [98.9, 99.5] | 99.4% | 0.000 | 0.000 | 0.000 | 0.000 | 0.0 | 0.0 |

Counted in, 60 and 72 h score **99.5% and 99.2%** on 3,533 pairs — near-perfect realism, bought
entirely by differencing a number against itself. This table exists because the
registration did not anticipate the republished tail and a reader is entitled to see exactly what
it does. **The headline table is the informative one.**

### 5.2 The 60 and 72 h rows rest on a selected subpopulation

The 74 informative pairs at 60 and 72 h are, by construction, the ~2% of spacecraft whose newer
issue regenerated its whole span instead of inheriting a tail. That is not a random 2%: it is
plausibly the spacecraft whose plans changed. Their containment (74.3% and 63.5%) and their
scale factors (0.93 and 1.24) are **reported as a property of that subpopulation and of nothing
else**, and no statement about the constellation is made from them.

### 5.3 Per axis

| lead (h) | column | axis (from label) | contained \|z\| ≤ 1.96 | Wilson 95% | k robust | k₉₅ | median \|z\| |
|---:|---:|---|---:|---|---:|---:|---:|
| 8 | 1 | radial | 99.5% | [98.8, 99.8] | 0.270 | 0.317 | 0.182 |
| 8 | 2 | in-track | 99.4% | [98.7, 99.7] | 0.178 | 0.248 | 0.120 |
| 8 | 3 | cross-track | 97.1% | [95.9, 98.0] | 0.800 | 0.867 | 0.540 |
| 12 | 1 | radial | 98.9% | [98.5, 99.2] | 0.156 | 0.185 | 0.105 |
| 12 | 2 | in-track | 99.1% | [98.7, 99.3] | 0.127 | 0.188 | 0.085 |
| 12 | 3 | cross-track | 98.1% | [97.6, 98.5] | 0.683 | 0.749 | 0.461 |
| 16 | 1 | radial | 99.2% | [98.9, 99.5] | 0.111 | 0.148 | 0.075 |
| 16 | 2 | in-track | 98.8% | [98.4, 99.1] | 0.097 | 0.157 | 0.065 |
| 16 | 3 | cross-track | 99.1% | [98.7, 99.3] | 0.527 | 0.632 | 0.355 |
| 24 | 1 | radial | 99.5% | [99.2, 99.7] | 0.076 | 0.124 | 0.051 |
| 24 | 2 | in-track | 98.8% | [98.4, 99.1] | 0.079 | 0.127 | 0.053 |
| 24 | 3 | cross-track | 99.7% | [99.5, 99.9] | 0.305 | 0.398 | 0.206 |
| 36 | 1 | radial | 99.7% | [99.5, 99.9] | 0.080 | 0.163 | 0.054 |
| 36 | 2 | in-track | 99.1% | [98.7, 99.3] | 0.079 | 0.187 | 0.054 |
| 36 | 3 | cross-track | 100.0% | [99.9, 100.0] | 0.194 | 0.223 | 0.131 |
| 48 | 1 | radial | 67.4% | [65.9, 69.0] | 1.993 | 3.308 | 1.344 |
| 48 | 2 | in-track | 92.2% | [91.3, 93.1] | 0.649 | 2.216 | 0.438 |
| 48 | 3 | cross-track | 18.4% | [17.1, 19.7] | 8.875 | 9.068 | 5.986 |
| 60 | 1 | radial | 100.0% | [95.1, 100.0] | 0.606 | 0.638 | 0.409 |
| 60 | 2 | in-track | 66.2% | [54.9, 76.0] | 1.825 | 4.697 | 1.230 |
| 60 | 3 | cross-track | 100.0% | [95.1, 100.0] | 0.109 | 0.115 | 0.073 |
| 72 | 1 | radial | 98.6% | [92.7, 99.8] | 0.419 | 0.503 | 0.283 |
| 72 | 2 | in-track | 54.1% | [42.8, 64.9] | 2.452 | 7.195 | 1.653 |
| 72 | 3 | cross-track | 100.0% | [95.1, 100.0] | 0.077 | 0.103 | 0.052 |

Out to 36 h the covariance is conservative on every column, most strongly in-track
(`k` = 0.18 at 8 h falling to 0.08 at 24–36 h — 12× too large). At 48 h the picture inverts and
**the cross-track column fails hardest: 18.4% contained, `k` = 8.9**, against an in-track column
that is still 1.5× too large (`k` = 0.65). A single overall scale factor would hide that, which
is why the registration required the per-axis table.

Every row carries the **column index** beside the axis name. T16a discharged the identification
of columns 1/2/3 with radial/in-track/cross-track as *consistent* — the column whose published
sigma grows fastest with lead is the second, which is what a near-circular orbit's along-track
growth predicts — but not as an independent determination, and nothing here upgrades it.

### 5.4 The re-plan exclusion did not do the covariance's work

| lead (h) | n with re-plans | contained | n without | contained | change |
|---:|---:|---:|---:|---:|---:|
| 8 | 1,001 | 97.5% | 998 | 97.7% | -0.19 pts |
| 12 | 3,600 | 97.5% | 3,580 | 97.7% | -0.18 pts |
| 16 | 3,600 | 98.0% | 3,580 | 98.1% | -0.10 pts |
| 24 | 3,600 | 98.4% | 3,580 | 98.5% | -0.10 pts |
| 36 | 3,600 | 98.6% | 3,580 | 99.0% | -0.36 pts |
| 48 | 3,550 | 16.1% | 3,533 | 16.1% | -0.05 pts |
| 60 | 88 | 63.6% | 74 | 74.3% | -10.69 pts |
| 72 | 88 | 53.4% | 74 | 63.5% | -10.10 pts |

The registration required this comparison and set a 5-point alarm: if excluding re-plans moved
the headline by more than 5 points at any lead, the rule would be doing more work than the
covariance. **Out to 48 h the largest move is 0.36 points.** At 60 and 72 h it is ~10 points,
which is the §5.2 subpopulation and not the rule.

### 5.5 Why the collapse is at 48 hours

The 48 h collapse is not a property of the covariance alone; it is where the **earlier** issue's
own splice begins. Each issue is freshly generated for 48 h of its own lead and then republishes
its predecessor. At an earlier-issue lead of 48 h, the earlier issue has therefore already
handed over to the issue before it, while the later issue at that same instant is only ~40 h
into its own fresh span. The residual there is a fresh prediction differenced against one whose
information is **an extra publication cycle old** — and the published covariance, which at 48 h
has just stepped up to 104 / 2,515 / 58 m, does not carry that. Median residual at that lead:
**1,118 m**, p95 **4,007 m**.

This is an inference about mechanism, drawn from the splice measurement in §1 item 1 and the census in
§6. The measured facts are the containment fraction, the splice location and the distinct-value
counts; the explanation joining them is offered as an explanation.

---

## 6. The distinct-value census

Computed over **every file of every issue held** — no sample. An issue is a publication cycle,
assigned per file from its own `created` stamp. Distinctness is of the published decimal's float
value: no rounding, no tolerance.

### 6.1 Cycle 1 — all 11,137 files

| lead (h) | files | distinct col 1 | col 2 | col 3 | median col 1 (m) | col 2 (m) | col 3 (m) |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 11,137 | 11,137 | 11,137 | 11,137 | 0.68 | 0.9 | 1.10 |
| 1 | 11,137 | 11,137 | 11,137 | 11,137 | 1.72 | 6.8 | 2.27 |
| 3 | 11,137 | 11,137 | 11,137 | 11,137 | 4.27 | 27.3 | 1.72 |
| 6 | 11,136 | 11,136 | 11,136 | 11,136 | 10.29 | 143.3 | 2.61 |
| 12 | 11,136 | 11,136 | 11,136 | 11,136 | 28.29 | 811.2 | 3.66 |
| 24 | 11,135 | 8,718 | 8,878 | 8,698 | 93.32 | 3,300.1 | 6.57 |
| 36 | 11,135 | 3,897 | 4,250 | 3,791 | 100.00 | 2,500.0 | 15.00 |
| 40 | 11,135 | 2,383 | 2,875 | 2,268 | 100.00 | 2,500.0 | 15.00 |
| 44 | 11,135 | 4,569 | 3,504 | 11,028 | 100.00 | 2,500.0 | 15.00 |
| 46 | 11,135 | 11,112 | 11,083 | 11,135 | 100.00 | 2,500.0 | 15.06 |
| 47 | 11,135 | 11,135 | 11,135 | 11,135 | 100.12 | 2,500.5 | 17.25 |
| 48 | 10,959 | 10,959 | 10,959 | 10,959 | 103.58 | 2,514.8 | 57.72 |
| 49 | 10,959 | 10,959 | 10,959 | 10,959 | 175.95 | 2,904.3 | 284.30 |
| 50 | 10,959 | 10,959 | 10,959 | 10,959 | 290.14 | 3,713.5 | 488.99 |
| 52 | 10,959 | 10,953 | 10,910 | 10,942 | 299.99 | 3,799.9 | 499.99 |
| 54 | 10,959 | 6,216 | 3,574 | 3,974 | 300.00 | 3,800.0 | 500.00 |
| 56 | 10,959 | 484 | 322 | 370 | 300.00 | 3,800.0 | 500.00 |
| 58 | 10,959 | 15 | 14 | 15 | 300.00 | 3,800.0 | 500.00 |
| 60 | 10,959 | 12 | 13 | 13 | 300.00 | 3,800.0 | 500.00 |
| 64 | 10,959 | 12 | 13 | 13 | 300.00 | 3,800.0 | 500.00 |
| 68 | 10,959 | 12 | 13 | 13 | 300.00 | 3,800.0 | 500.00 |
| 72 | 10,959 | 12 | 13 | 13 | 300.00 | 3,800.0 | 500.00 |
Three regimes, and the transition between them is sharp:

- **0–12 h — a real propagated covariance.** Every one of 11,137 files carries a distinct value
  on every column, and the values grow: in-track 0.9 m at epoch to 811 m at 12 h.
- **24–44 h — a first plateau.** Distinct values fall to 8,718 at 24 h and to 2,268–2,875 at
  40 h, with the medians pinned at exactly **100.00 / 2,500.0 / 15.00 m**. Then 44–52 h returns
  to near-full cardinality: a transition band, not a plateau.
- **52–72 h — a second plateau, and the one that matters.** By 58 h the count is 15 / 14 / 15,
  and from 60 h to 72 h it is **12 / 13 / 13 distinct values across 10,959 files** — 0.11% —
  with the medians pinned at exactly **300.00 / 3,800.0 / 500.00 m**.

Most frequent published values at 72 h, cycle 1:

- column 1 (radial): 300.0 m (71.8%), 250.0 m (21.8%), 260.0 m (3.2%), 350.0 m (3.0%)
- column 2 (in-track): 3,800.0 m (64.9%), 3,000.0 m (20.1%), 2,000.0 m (5.9%), 3,400.0 m (5.8%)
- column 3 (cross-track): 500.0 m (64.9%), 550.0 m (29.0%), 350.0 m (3.2%), 600.0 m (1.7%)

### 6.2 Cycle 2 — the replication, on 4,000 files

| lead (h) | files | distinct col 1 | col 2 | col 3 |
|---:|---:|---:|---:|---:|
| 0 | 4,000 | 4,000 | 4,000 | 4,000 |
| 1 | 4,000 | 4,000 | 4,000 | 4,000 |
| 3 | 4,000 | 4,000 | 4,000 | 4,000 |
| 6 | 3,999 | 3,999 | 3,999 | 3,999 |
| 12 | 3,999 | 3,999 | 3,998 | 3,999 |
| 24 | 3,999 | 3,004 | 3,090 | 3,000 |
| 36 | 3,999 | 1,275 | 1,387 | 1,251 |
| 40 | 3,999 | 792 | 947 | 736 |
| 44 | 3,999 | 2,207 | 1,976 | 3,983 |
| 46 | 3,999 | 3,996 | 3,989 | 3,999 |
| 47 | 3,999 | 3,999 | 3,998 | 3,999 |
| 48 | 3,945 | 3,945 | 3,945 | 3,945 |
| 49 | 3,945 | 3,945 | 3,945 | 3,945 |
| 50 | 3,945 | 3,945 | 3,945 | 3,945 |
| 52 | 3,945 | 3,944 | 3,938 | 3,942 |
| 54 | 3,945 | 3,132 | 1,821 | 2,394 |
| 56 | 3,945 | 268 | 176 | 219 |
| 58 | 3,945 | 10 | 10 | 9 |
| 60 | 3,945 | 7 | 8 | 8 |
| 64 | 3,945 | 7 | 8 | 8 |
| 68 | 3,945 | 7 | 8 | 8 |
| 72 | 3,945 | 7 | 8 | 8 |
The same three regimes at the same leads, with **7 / 8 / 8 distinct values across 3,945 files**
from 60 h out. The shares at 72 h agree to within a point: 300.0 m (72.0%), 3,800.0 m (65.1%),
500.0 m (65.1%).

**The registration's licence condition is met.** The rule fixed before the data was that the
word *placeholder* may be used only where a lead's distinct-value count is below 1% of the file
count in **every** issue measured. At 72 h the counts are 0.11-0.12% of cycle 1's 10,959 files and 0.18-0.20% of cycle 2's 3,945,
on all three columns.
The rule returns column 1, 2 and 3 at 72 h and nothing else — and that is the only place the
word is used.

**What this is not.** It is not a statement about the operator's intent, and no public
documentation of how this covariance is generated, of any default, or of any cap has been
located (T16a). The absence of documentation is reported as an absence and is not evidence of a
default.

### 6.3 The in-track sigma falls with lead, and propagation cannot do that

The census reports every **adjacent** pair of leads on its grid. Between 24 h and 36 h the
published in-track one-sigma **decreases** in **7,388 of 11,137 files (66.3%)** in cycle 1 and
**2,583 of 4,000 (64.6%)** in cycle 2. That is where the fall happens: the median goes 3,300.1 m
at 24 h to 2,500.0 m at 36 h, and is still 2,514.8 m at 48 h — **785 m below its own 24 h
value**. (T16a saw this as a 48 h value below the 24 h one on a coarse grid; the fine grid
locates it at the 24 h → 36 h step.) The fall continues, weaker, at 36 h → 40 h in 31.0% and
29.1% of files.

The derivation, with its assumptions stated. For a near-circular orbit, an error `δa` in
semi-major axis produces an along-track displacement that grows secularly,
`δs ≈ (3/2) n δa · t`, from the mean-motion dependence `n = √(μ/a³)`. At the measured median
radius of 6,847.6 km, `n = 1.114×10⁻³ rad/s`, so **an error of one metre in semi-major axis
alone moves the along-track position by about 144 m over 24 hours and 289 m over 48 hours.** A
covariance propagated forward from a single epoch, receiving no new information, therefore has a
monotonically non-decreasing in-track term at these leads: the secular contribution dominates the
periodic ones for any error budget consistent with the published short-lead values. A published
in-track sigma that is 800 m smaller at 36 h than at 24 h, and still 785 m smaller at 48 h, is
not producible by propagation.

The same argument does **not** apply to the cross-track column, and the document does not make
it. A cross-track error oscillates at the orbital period with bounded amplitude, so a cross-track
sigma that falls between two leads is expected physics, not an anomaly. That is why the
**1 h → 3 h cross-track decrease in 98.8% of files is reported here and claimed as nothing**: at
a 94-minute period, 1 h and 3 h sit at different phases of the same oscillation.

---

## 7. The consequence: what this does to a collision probability

### 7.1 Method, and why the relative speed cancels

**Alfano/Foster two-dimensional Pc** (Foster & Estes, NASA JSC-25898, 1992; Alfano, 2005).
For a short-duration encounter the relative motion is rectilinear over the interval in which
probability accumulates, so the three-dimensional integral collapses onto the **encounter
plane** — the plane through the primary perpendicular to the relative velocity. Project the
combined position covariance and the miss vector onto that plane and integrate the resulting
bivariate Gaussian over the disk of the combined hard-body radius `R`:

```
Pc = ∬_{|x − x₀| ≤ R}  (2π σ_x σ_z)⁻¹ · exp( −½ ( x²/σ_x² + z²/σ_z² ) ) dx dz
```

in the principal axes of the projected covariance, integrated numerically in polar coordinates
about the hard-body disk so that the domain is exact and only the integrand is discretised.

The relative speed sets the orientation of the encounter plane and the validity of the
short-encounter assumption. **It does not appear in the integrand.** The ratio reported below
is therefore independent of the crossing speed — which is not asserted but shown, by computing
the ratio across a family of crossing angles whose relative speeds differ by a factor of three
and finding the same number.

### 7.2 The geometry, stated rather than assumed

- **Intra-constellation.** Both objects are spacecraft of the same constellation, each carrying
  the operator's published covariance at the same lead. This is the case that requires no
  assumption about a third party's covariance, and it is the case the operator screens most
  often.
- At the conjunction point the two objects share the radial direction, and their in-track axes
  differ by the crossing angle about that direction. The secondary's covariance is therefore the
  primary's rotated about the radial axis, and the combined covariance is the sum.
  **Summing assumes the two solutions are independent.** Two solutions produced by one
  operator's one process are plausibly correlated; a positive correlation would make the
  combined covariance smaller and every Pc below larger. Stated, not hidden.
- Combined hard-body radius `R = 10 m`: **a chosen conservative screen, not a measured
  dimension.**
- The orbital radius is the median `|r|` measured over the collected issue set, and the circular
  speed `v = √(μ/r)` and relative speed `v_rel = 2 v sin(θ/2)` are printed with it so a reader
  can check the short-encounter assumption.

### 7.3 The two regimes, derived before the numbers

Write `Pc(k)` for the probability computed with the covariance scaled by `k`. In the limit
`R ≪ σ` the integrand is nearly constant across the disk, so

```
Pc(k) ≈ ( R² / (2 k² σ_x σ_z) ) · exp( −d²/(2k²) ),     d² = x₀²/σ_x² + z₀²/σ_z²
Pc(1) / Pc(k) = k² · exp( −(d²/2)(1 − 1/k²) )
```

- **Near field (`d → 0`):** the ratio tends to `k²`. A covariance that is too **large**
  (`k < 1`) **understates** the collision probability.
- **Far field (`d ≫ 1`):** the exponential dominates and the sign reverses — a too-large
  covariance **overstates** Pc at large miss.

Which regime a given miss distance is in is a property of the **axis it lies along**, not of the
miss distance alone: at these covariances a 3 km miss is seven sigma along the projected radial
axis and well inside one sigma along the projected in-track axis. The registration therefore
forbids quoting a ratio without its miss geometry, and this document does not.

### 7.4 The numbers

**At 24 h lead** — the covariance is too large.

published one-sigma (93.3, 3,300.1, 6.6) m · k = 0.190 · k lower bound = 0.135
geometry: r = 6,847.6 km, v = 7.630 km/s, crossing 90°, v_rel = 10.790 km/s, hard-body radius 10 m (a chosen conservative screen, not a measured dimension)

| miss (m) | along | Pc published | Pc self-consistent | ratio published / self-consistent |
|---:|---|---:|---:|---:|
| 0 | radial | 1.147e-04 | 3.104e-03 | 0.04 |
| 0 | in-plane | 1.147e-04 | 3.104e-03 | 0.04 |
| 100 | radial | 8.613e-05 | 1.520e-06 | 56.67 |
| 100 | in-plane | 1.147e-04 | 3.065e-03 | 0.04 |
| 300 | radial | 8.695e-06 | 2.857e-33 | 3.04e+27 |
| 300 | in-plane | 1.142e-04 | 2.770e-03 | 0.04 |
| 1000 | radial | 4.084e-17 | 0.000e+00 | inf |
| 1000 | in-plane | 1.096e-04 | 8.753e-04 | 0.13 |

crossing-angle family at zero miss — the relative speed changes by 3.7× and the ratio does not:

| crossing angle | v_rel (km/s) | ratio |
|---:|---:|---:|
| 30° | 3.949 | 0.03696 |
| 60° | 7.630 | 0.03696 |
| 90° | 10.790 | 0.03696 |
| 120° | 13.215 | 0.03696 |
| 150° | 14.739 | 0.03697 |

**At 48 h lead** — the covariance is too small, and this is the operative row.

published one-sigma (103.6, 2,514.8, 57.7) m · k = 4.474 · k lower bound = 3.164
geometry: r = 6,847.6 km, v = 7.630 km/s, crossing 90°, v_rel = 10.790 km/s, hard-body radius 10 m (a chosen conservative screen, not a measured dimension)

| miss (m) | along | Pc published | Pc self-consistent | ratio published / self-consistent |
|---:|---|---:|---:|---:|
| 0 | radial | 1.356e-04 | 6.779e-06 | 20.01 |
| 0 | in-plane | 1.356e-04 | 6.779e-06 | 20.01 |
| 100 | radial | 1.075e-04 | 6.700e-06 | 16.04 |
| 100 | in-plane | 1.355e-04 | 6.778e-06 | 19.99 |
| 300 | radial | 1.669e-05 | 6.104e-06 | 2.73 |
| 300 | in-plane | 1.347e-04 | 6.776e-06 | 19.87 |
| 1000 | radial | 1.056e-14 | 2.116e-06 | 4.99e-09 |
| 1000 | in-plane | 1.253e-04 | 6.752e-06 | 18.56 |

crossing-angle family at zero miss — the relative speed changes by 3.7× and the ratio does not:

| crossing angle | v_rel (km/s) | ratio |
|---:|---:|---:|
| 30° | 3.949 | 20.01 |
| 60° | 7.630 | 20.01 |
| 90° | 10.790 | 20.01 |
| 120° | 13.215 | 20.01 |
| 150° | 14.739 | 20.01 |

**At 72 h lead** — from the selected subpopulation of §5.2, and carrying its caveat.

published one-sigma (300.0, 3,800.0, 500.0) m · k = 1.239 · k lower bound = 0.876
geometry: r = 6,847.6 km, v = 7.630 km/s, crossing 90°, v_rel = 10.790 km/s, hard-body radius 10 m (a chosen conservative screen, not a measured dimension)

| miss (m) | along | Pc published | Pc self-consistent | ratio published / self-consistent |
|---:|---|---:|---:|---:|
| 0 | radial | 3.075e-05 | 2.002e-05 | 1.54 |
| 0 | in-plane | 3.075e-05 | 2.002e-05 | 1.54 |
| 100 | radial | 2.990e-05 | 1.966e-05 | 1.52 |
| 100 | in-plane | 3.074e-05 | 2.002e-05 | 1.54 |
| 300 | radial | 2.395e-05 | 1.701e-05 | 1.41 |
| 300 | in-plane | 3.065e-05 | 1.998e-05 | 1.53 |
| 1000 | radial | 1.912e-06 | 3.281e-06 | 0.58 |
| 1000 | in-plane | 2.972e-05 | 1.958e-05 | 1.52 |

crossing-angle family at zero miss — the relative speed changes by 3.7× and the ratio does not:

| crossing angle | v_rel (km/s) | ratio |
|---:|---:|---:|
| 30° | 3.949 | 1.536 |
| 60° | 7.630 | 1.536 |
| 90° | 10.790 | 1.536 |
| 120° | 13.215 | 1.536 |
| 150° | 14.739 | 1.536 |

**The sentence, with its geometry attached.** At a 48-hour lead, a two-dimensional collision
probability computed from the published covariance is **20.0× too high** for a conjunction whose
predicted miss is small compared with the uncertainty, and **2×10⁸ times too low** for a
predicted miss of 1 km along the projected radial axis. At 24 h the covariance is too large and
the signs reverse: **27× too low** at zero miss, **57× too high** at a 100 m radial miss, and
**3×10²⁷ times too high** at 300 m. Which regime a screening sits in is set by the miss geometry,
not by the lead, so no single ratio is quoted here without it.

**This is what operators, space-traffic-management regulators and — weakly, as a governance fact
rather than a rating fact — insurers would care about.** It is a first public statement, not a
discovery, and it does not say anyone's data is wrong.

---

## 8. Deviations from the registration

1. **A live 304 was received, and the inherited engine treated it as a halt.** The registration
   inherited T16a's etiquette engine wholesale. That engine raises on any status outside 2xx,
   including a 304 that answers a validator it sent itself, and writes a permanent halt marker.
   The first T19 manifest request received exactly that: `HTTP 304`, answering an
   `If-None-Match` bound to the body T16a already held. A halt marker was written at
   19:41:40 UTC and **cleared with a recorded reason** (archived to
   `state/halts/HALTED-20260922T194347Z.json`). **No provider refusal occurred**; the 304 is the
   politest outcome the protocol has. `tools/starlink_collect.py` now installs a transport that
   returns an answered 304 instead of raising it, and falls back to the manifest already on
   disk — which is exactly what the 304 asserts that manifest to be. `tools/supgp_ingest.py`
   was **not modified**: it belongs to T16a and the fix lives in the new module.

2. **The provider sends cache validators; T16a's supplemental endpoint does not.** T16a measured
   the supplemental element-set endpoint as sending neither `ETag` nor `Last-Modified` and
   recorded a live 304 as unproven there. The ephemeris endpoint sends both, and the 304 above
   is the proof for this endpoint family. The two statements are about different providers and
   neither transfers to the other.

3. **Leads 1, 3 and 6 h are unreachable, as the registration predicted in advance.** They are
   reported as `n = 0` with the word UNREACHABLE and are not filled by pairing non-adjacent
   issues.

4. **The republished tail was not anticipated, and the instrument had to change.** The
   registration assumed two overlapping issues are two predictions. Beyond 48 h of its own lead
   a newer issue republishes the previous issue's states verbatim, so at those leads they are
   the same numbers twice. Instants where the two issues publish the same state are now
   detected, counted and excluded from the headline containment, and the containment that counts
   them is reported beside it (§5.1). The threshold is the file's own print precision, so
   "identical" is a property of the published bytes and not a chosen tolerance. This change was
   made before any number was produced, and is committed as `e380975` with three tests that
   assert the bug first.

5. **The census grid was extended from 8 leads to 22.** The registered grid
   (0, 1, 3, 6, 12, 24, 48, 72 h) cannot locate where a column stops being a propagated
   uncertainty, and the containment collapse and the splice both live between 40 and 72 h. The
   registered leads are all still reported; the extra ones are additional resolution on the same
   quantity, not a different one.

6. **The second cycle is 4,000 files, not the whole manifest.** The registration permits the
   whole manifest once per cycle; 4,000 is below that ceiling, drawn by the registered
   deterministic spread rather than as a prefix. The cycle-1 census is the full 11,137.

7. **No interpolation entered any reported residual.** The registration provided for 8th-order
   Lagrange interpolation because the two issues' 60 s grids need not align. They did align, at
   every comparison instant. The self-test was run anyway (§4.1).

## 9. Unproven items, in those words

- **A live non-200 refusal from this provider is UNPROVEN, deliberately.** Every ephemeris and
  manifest request in this track returned 200 or an answered 304. The halt path was driven by a
  hand-written marker and by the 304 that the inherited engine mis-read; it has never been
  driven by a provider refusal, and it will not be provoked.
- **Which issue is closer to truth is UNMEASURED.** Nothing here ranks the two issues. The
  residual is a disagreement and attributes to neither. The word "accuracy" appears in this
  document only to say that it is not what is being measured.
- **The published covariance is UNVALIDATED against any independent measurement.** It is the
  operator's formal covariance of a blended solution: a statement about a filter. A containment
  figure here is a statement about the pair (residual, published covariance), not about the
  operator's true uncertainty.
- **The axis-order label is discharged only as CONSISTENT, not independently determined**
  (T16a §6.1). Every table carries the column index beside the axis name for that reason.
- **The re-plan classification is an INFERENCE, not an operator declaration.** The files carry
  no manoeuvre flag. The rule is the registered semi-major-axis step with a threshold set on a
  pre-registered hold-out, and the hold-out is itself drawn from the same population, so any
  manoeuvre inside the hold-out raises the threshold and makes the rule under-exclude. The
  sensitivity of the reported numbers to that threshold is printed; the threshold is not
  re-chosen.
- **The operator's covariance generation method is UNDOCUMENTED publicly.** T16a located no
  public statement of how it is produced, of any default, or of any cap. The absence of
  documentation is reported as an absence and is not evidence of a default.
- **Correlation between the two conjunction partners' covariances in §7 is UNMEASURED.** The
  combined covariance is a sum, which assumes independence; two solutions from one operator's
  one process are plausibly correlated, which would make every Pc here larger.
- **Nothing here is a claim of discovery.** Screening organisations may already run this check
  internally and unpublished; the framing is first public statement.
- **The mechanism joining the 48 h collapse to the splice is an EXPLANATION, not a measurement**
  (§5.5). The containment fraction, the splice location and the distinct-value counts are
  measured; the account that ties them together is offered as an account.
- **The 60 and 72 h containment figures describe a SELECTED SUBPOPULATION** (§5.2) and are not
  statements about the constellation.
- **Whether the republished tail affects previously published overlap statistics is UNMEASURED.**
  Any overlap comparison on these files that does not check for identical segments will average
  real residuals together with exact zeros. This document makes no claim about what any
  particular prior study did; it records that the check is necessary and that this document
  performs it.

## 10. What is owed before any of this is published

1. **More than one day.** This is two publication cycles of one constellation on one date. The
   registration's binding condition for the word "placeholder" is that the low cardinality hold
   in *every* issue measured; two issues clear that bar mechanically but are not a multi-month
   census, and the reviewer's condition was months. The collector exists, has no timer, and is
   the operator's to schedule.
2. **A manoeuvre truth set.** The re-plan rule is an inference from an energy argument. A
   labelled set — even a small one — would turn the excluded fraction from a rule's output into
   a measured false-exclusion rate.
3. **A second constellation.** Every number here is one operator's. Nothing says whether this is
   a property of megaconstellation ephemerides or of this megaconstellation's ephemerides.
4. **The operator's own documentation.** No public statement of how the covariance is generated,
   of any default, or of any cap has been located. A reader inside the operator could close this
   in one sentence, and the note should be written so that sentence would improve it rather than
   refute it.
5. **A registration naming a consumer.** Nothing in the programme reads these numbers yet, and
   nothing may until a registration says how.
