# Does station-keeping relax before retirement? Feasibility probe

Measured 2026-09-20 UTC. **Verdict: underpowered in the published event population;
stop rule triggered. This is not a null test of policy relaxation.**

The complete published detail census has **28 self-history graveyard-raise flags
on 22 payloads**. Only **two** have any pre-raise NSK detection reaching three
calendar years back; **zero** have estimable baseline and final-year cadence.
The required feasibility floor is 15 distinct usable retirees. Accordingly no
matched controls, outcome ratios, hypothesis test, effect size or confidence
interval were calculated. Missing values below mean **not estimated**, not zero.

The full archive's retained aggregate counters are larger: **152 payload raise
flags plus four passive-object false alarms**, in both the older published
release and an existing current-code sweep. The full archive's number of distinct
usable retirees remains **unknown**: aggregate flags do not retain identities or
per-object NSK histories. The underpowered conclusion applies to the published
detail population, not a proof that the archive could never supply 15 retirees.

## Registration and measurement definition

The [registration](eol-policy-relaxation-preregistration-20260920.md) was written
before inspecting per-object retirement histories. It transcribes the user's
hypothesis and freezes these outcomes:

| Outcome | Numerator | Denominator |
|---|---|---|
| R_interval, primary | Median spacing between NSK corrections in final 12 calendar months | Same object's median spacing in all earlier available history |
| R_dv, secondary | Median lower-bound total Delta-v per NSK correction in final 12 months | Same object's median lower-bound total Delta-v in earlier history |
| Control outcomes | The same quantities in exactly the retiree's calendar windows | Matched GEO objects with no detected raise in those windows |

T is the first published self-history raise's start time; repeats never create
additional independent retirees. Final year is [T−1 calendar year,T); baseline
ends at T−1 year. Events must lie wholly in their window. Only self-history
`geo-north-south-keeping` events qualify; cohort events are excluded. Leap-day
anniversaries clamp to February 28. A cadence needs at least three events and two
within-segment spacings, following the repository's existing rule. The initial
three-year test deliberately uses a generous upper bound—any NSK detection at
least three years before T. Even this upper bound is only two.

Had that gate passed, the primary planned test was a one-sided permutation of
retiree/control labels within matched pairs, alpha **0.05**, on mean paired log
R_interval differences. The planned effect was the exponentiated mean difference,
with a **95% paired bootstrap CI**, 10,000 resamples, seed 20260920. Matching would
use baseline-only characteristics and be frozen before final-year outcomes.
Delta-v is secondary and cannot rescue a failed primary test. None of these
inferential calculations ran. Fifteen is a feasibility floor supplied by the
user, not a formal power calculation for a specified effect size.

## Census and provenance

| Population / source | Raise flags | Distinct payload candidates | ≥3-year NSK depth | Fully usable retirees |
|---|---:|---:|---:|---:|
| Published self-history detail records, all 256 shards | 28 payload; 0 passive | 22 | 2 | 0 |
| Published full-sweep classified-population counters | 152 payload; 4 passive | Not retained | Not retained | Unknown |
| Existing current-code full-sweep receipt, separate reference | 152 payload; 4 passive | Not retained | Not retained | Unknown |

There are **124 payload raise flags absent from published detail histories**,
81.6% of the 152 aggregate flags. No inference about their distinct-object count
is possible from those counters. They may include repeated raises. The totals
above are for classified payload/passive populations; they do not establish a
count for unclassified objects.

The source for **every per-object record** is the published artifact
`orbit-events-d7919fbbd28d8c62.json`, generated **2026-09-19T12:48:51Z**, and its
256 manifest-linked detail shards. The analysis verified all artifact SHA-256s,
**11,335 distinct detail objects**, **105,523 total detail events**, and **91,197
self-history events**, including **2,845 NSK events**. It did not use only the
1,500-event headline list. The selected manifest SHA-256 is
`006732fdc3cda78fa7eaea37960387d3d7ca83b3ba10b45e58f8cf45affba26c`.
These are local copies of published artifacts; the previous Phase-2b report
independently verified this same event artifact and these shard hashes against
the public manifest. This probe made no provider or public-site requests.

The separate [Phase-2b report](orbit-phase2b-corroboration-20260920.md) and
[receipt](orbit-phase2b-corroboration-20260920.json) document a completed sweep of
**216,937,493 rows / 68,711 objects**, with 61,377 admitted objects, completed
2026-09-20T15:04:46Z. Its accepted detector source hashes match the current
`56eef643f600af5635fbdf493eb3361bb1a4896c` code. Its four passive and 152 payload
raise counts are unchanged by that policy change. It supplies aggregate context
only; no newer detections or calibration were spliced into the older per-object
measurements. The reference receipt SHA-256 is
`a28ca4e25694fbc58b97af0e81f582a0c49dfd5bf40b9c4a1cb16a346d65b232`.

Publication selection matters here: `orbit_campaigns._sweep_archive_serial`
accumulates full-population control counters before its `keep_summaries_for`
filter; `orbit_release` supplies the teaching catalogue to that filter. Thus
all detail shards can be complete for publication and still omit most archive
raise events. Selecting a current catalogue is particularly problematic for a
retirement study; those 22 candidates are not a representative retired cohort.

### False-alarm context

All **28** individual published raise records have
`manoeuvreLabelPermitted=false`. The published overall self-history passive rate
is **0.4471 per 1,000 usable intervals**, Jeffreys 95% interval
**[0.4427,0.4515]**, and its bound separation is **6.86×**, below the site's 10×
label gate. These population bounds are not probabilities that an individual
raise is false.

| Published GEO+ era | Passive flags / intervals | Passive rate per 1,000, 95% interval | Bound separation | Stratum gate |
|---|---:|---|---:|---|
| pre-2013 | 81 / 410,932 | 0.1971 [0.1576,0.2436] | 8.871× | Fails |
| 2013–2020 | 69 / 577,148 | 0.1196 [0.0938,0.1503] | 18.968× | Passes |
| 2021+ | 22 / 749,470 | 0.0294 [0.0189,0.0436] | 58.829× | Passes |

These stratum diagnostics do not override the false label permission actually
carried by each event. Five published raise flags are pre-2013, 12 are in
2013–2020, and 11 are in 2021+. The later current-code full sweep has an overall
passive rate of 0.1589 per 1,000, 95% interval [0.1563,0.1615], and bound separation
18.191×. That newer calibration is **not** assigned to this study's old records.
Neither calibration measures the positive predictive value of the retirement
interpretation specifically.

### Per-object retirement census

“NSK depth” is elapsed time from the earliest detected pre-raise NSK to T,
reported in 365.25-day years; eligibility itself uses calendar anniversaries.
“Observed” sums usable orbital-element interval durations before T, including
periods with no NSK detection. It is not three years of verified station-keeping.

| NORAD | Published name | First raise UTC | Raise flags | Pre-raise NSK events | NSK depth, years | Observed pre-raise years |
|---|---|---|---:|---:|---:|---:|
| 23613 | TDRS 7 | 2009-06-09 | 1 | 0 | — | 8.25 |
| 24307 | INMARSAT 3-F2 | 1996-09-25 | 1 | 0 | — | 0.04 |
| 27632 | NIMIQ 2 | 2019-04-26 | 2 | 1 | 16.17 | 10.27 |
| 28158 | USA 176 | 2026-09-14 | 1 | 0 | — | 7.90 |
| 28659 | DIRECTV 8 | 2005-09-07 | 1 | 0 | — | 0.20 |
| 33278 | INMARSAT 4-F3 | 2008-09-16 | 1 | 0 | — | 0.06 |
| 36108 | WGS F3 (USA 211) | 2021-04-29 | 2 | 0 | — | 5.43 |
| 36131 | DIRECTV 12 | 2010-05-04 | 1 | 0 | — | 0.33 |
| 36828 | BEIDOU 5 | 2021-08-03 | 1 | 0 | — | 10.69 |
| 37207 | BSAT-3B | 2013-01-23 | 1 | 1 | 0.76 | 1.58 |
| 41586 | BD-2-G7 | 2018-09-17 | 1 | 0 | — | 2.25 |
| 41838 | SJ-17 | 2018-02-10 | 2 | 9 | 1.27 | 1.26 |
| 42907 | COSMOS 2520 | 2021-01-25 | 1 | 2 | 3.39 | 3.20 |
| 42965 | QZS-4 | 2017-10-14 | 1 | 1 | 0.00 | 0.01 |
| 44071 | WGS 10 (USA 291) | 2019-09-23 | 2 | 0 | — | 0.46 |
| 44625 | MEV-1 | 2020-02-01 | 2 | 1 | 0.03 | 0.19 |
| 44903 | ELEKTRO-L 3 | 2020-05-31 | 1 | 0 | — | 0.42 |
| 53355 | SBIRS GEO 6 (USA 336) | 2023-10-11 | 1 | 0 | — | 1.06 |
| 53765 | EUTE KONNECT VHTS | 2023-01-29 | 1 | 0 | — | 0.20 |
| 54219 | LDPE-2 | 2025-05-21 | 1 | 3 | 1.30 | 2.06 |
| 55131 | SJ-23 | 2023-01-22 | 2 | 0 | — | 0.01 |
| 55841 | LUCH (OLYMP) 2 | 2023-05-05 | 1 | 0 | — | 0.13 |

Only NIMIQ 2 and COSMOS 2520 reach the three-year NSK-depth upper bound. NIMIQ 2
has one baseline NSK detection and no final-year detections; COSMOS 2520 has two
baseline detections and none in its final year. Their raw orbital coverage is
10.27 and 3.20 observed years respectively, but that does not make either NSK
cadence estimable.

## Baseline versus final-year outcomes

Each B/F cell is baseline / final year. Outcome medians and both ratios are
unestimated under the stop rule. Even without the stop, no candidate has enough
retained spacings in **both** windows to estimate R_interval. Coverage and counts
are census diagnostics, not substitute outcomes.

| NORAD | NSK events B/F | Retained spacings B/F | Observed days B/F | R_interval | R_dv |
|---|---:|---:|---:|---|---|
| 23613 | 0 / 0 | 0 / 0 | 2747.8 / 265.8 | — | — |
| 24307 | 0 / 0 | 0 / 0 | 0.0 / 13.6 | — | — |
| 27632 | 1 / 0 | 0 / 0 | 3395.6 / 356.2 | — | — |
| 28158 | 0 / 0 | 0 / 0 | 2749.3 / 136.9 | — | — |
| 28659 | 0 / 0 | 0 / 0 | 0.0 / 73.2 | — | — |
| 33278 | 0 / 0 | 0 / 0 | 0.0 / 22.7 | — | — |
| 36108 | 0 / 0 | 0 / 0 | 1626.5 / 356.7 | — | — |
| 36131 | 0 / 0 | 0 / 0 | 0.0 / 120.7 | — | — |
| 36828 | 0 / 0 | 0 / 0 | 3548.6 / 354.3 | — | — |
| 37207 | 0 / 1 | 0 / 0 | 260.3 / 317.9 | — | — |
| 41586 | 0 / 0 | 0 / 0 | 456.5 / 364.3 | — | — |
| 41838 | 2 / 7 | 1 / 6 | 99.1 / 362.7 | — | — |
| 42907 | 2 / 0 | 0 / 0 | 811.0 / 356.8 | — | — |
| 42965 | 0 / 1 | 0 / 0 | 0.0 / 4.8 | — | — |
| 44071 | 0 / 0 | 0 / 0 | 0.0 / 167.2 | — | — |
| 44625 | 0 / 1 | 0 / 0 | 0.0 / 70.4 | — | — |
| 44903 | 0 / 0 | 0 / 0 | 0.0 / 153.8 | — | — |
| 53355 | 0 / 0 | 0 / 0 | 58.5 / 327.6 | — | — |
| 53765 | 0 / 0 | 0 / 0 | 0.0 / 73.1 | — | — |
| 54219 | 1 / 2 | 0 / 0 | 401.8 / 351.0 | — | — |
| 55131 | 0 / 0 | 0 / 0 | 0.0 / 4.1 | — | — |
| 55841 | 0 / 0 | 0 / 0 | 0.0 / 48.7 | — | — |

| Requested comparison | Retiree observations | Control observations | Effect size | 95% CI | p-value | Result |
|---|---:|---:|---|---|---|---|
| R_interval distribution, primary | 0 usable | Not selected | Not estimated | Not estimated | Not tested | Underpowered; stopped |
| R_dv distribution, secondary | Not measured | Not selected | Not estimated | Not estimated | Not tested | Stopped |

No zero-effect estimate, p=1, or artificial confidence interval is substituted
for a test that was not run. Zero detected corrections also does not establish
zero true corrections or an infinitely long cadence.

## Coverage holes that mattered

The analysis used the existing SSD archive at
`/home/sdegan/space-orbit-history/orbit-history.sqlite3`, checked that it existed,
and opened it only through `open_archive_for_reading`; `query_only=1`, WAL.
It reused `intervals_from_rows`, `MAXIMUM_JOINABLE_GAP_DAYS=3.0`, and `_segments`.
A spacing longer than three days is allowed when observations remain continuous;
a spacing crossing a broken observation segment is excluded. No interpolation,
network fallback, database mutation or cold-shard extraction was performed.

There are **750 internal observation gaps** across these candidates' pre-raise
baseline/final windows. These are per-object segment gaps, not 750 distinct
archive-wide outages. Missing window edges also reduce exposure and are not
counted in that internal-gap total. The rollup contains at least some rows in
every month of 2004–2025; month presence emphatically does not imply complete
coverage of an object.

Two possible NSK spacings were excluded: COSMOS 2520's baseline pair (2017-09-04
to 2019-10-15) crosses several holes, and LDPE-2's final-year pair crosses a hole.
Consequently their retained pair counts are zero. USA 176's final year has only
**136.9 observed days**, including a **218.33-day internal hole** from
2025-12-31T12:47:45Z to 2026-08-06T20:37:46Z. NIMIQ 2 has a **40.05-day baseline
hole** spanning 2009-12-03 to 2010-01-12, among many others. Exact per-object
segments and exclusions are retained in the JSONL.

The coverage reader used the live archive after the published release. Its
per-object pre-raise row hashes are recorded, but paged reads are not one global
immutable database snapshot. No new event detections were introduced. A future
outcome study should freeze detection and exposure on the same archive snapshot.

## Retirement labels and scientific limits

The detector's raise signature is a geometric threshold crossing: the
semi-major axis passes from below to at least **235 km above GEO**, in its GEO
or near-GEO branch, without an inclination trip taking classification priority.
It does not independently establish end of service. **11 of the 22 first flags
occur within 365 days of the archive-listed launch date**, including QZS-4 at
five days, SJ-23 at 14 days, and INMARSAT 3-F2 at 19 days. Those timings expose a
serious problem with treating every raise as retirement ground truth; they do
not by themselves identify the actual manoeuvre purpose.

BSAT-3B's 2013-01-23 raise is followed by 29 published NSK detections, extending
to 2026. Repeated threshold crossings and continuing detected corrections require
an independent retirement-label audit. We did not hand-relabel objects or move
T to whichever raise gives a desired result.

Delta-v here is the detector's **lower bound** on the cheapest impulse consistent
with fitted element changes, not thruster telemetry, propellant mass or remaining
fuel. Changes in burn direction, orbital geometry, fit noise, propulsion mode and
detection threshold can alter the measured lower bound and event completeness.
The self-history detector's rolling baseline can absorb gradual changes. Weak or
continuous corrections may not appear as step events. A future positive result
would support an association in detected behaviour, not uniquely identify fuel
state. Calendar-matched controls address common seasonal changes only under
adequate coverage, comparable detection sensitivity and defensible matching.

## What full-history re-detection would add

1. Retain per-object current-code raise and NSK records for **all historical
   payloads**, including objects outside the current teaching catalogue. Recover
   the identities behind the 124 omitted raise flags before estimating the number
   of additional independent retirees. Do not extrapolate 124 flags to 124 cases.
2. Audit retirement labels against independent evidence and post-raise evolution,
   with decisions blinded to the final-year ratio. Freeze a revised registration
   if the operational retirement definition changes.
3. Freeze event and coverage provenance on one archive snapshot; census usable
   exposure, repeat raises, launch/transfer contamination and NSK sample counts.
   Stop again if fewer than 15 usable retirees remain.
4. Only if that gate passes, freeze baseline-only matching, form identical calendar
   windows, and execute the registered test and paired confidence interval.

The existing current-code full sweep demonstrates that archive re-detection is
already feasible on the present host: its accepted slices cost **20,825 worker
wall-seconds / 10,604 CPU-seconds**, with a parallel phase of **11,246 seconds**
and at most two readers. These are recorded costs of that paired detector
experiment, not a runtime prediction for this probe or for a future study.
Larger compute allocations would support repeated snapshot-controlled sweeps,
validation and uncertainty studies across the historical population. They cannot
repair missing orbital fits, prove retirement, or turn lower-bound Delta-v into
a propellant gauge. The defensible compute pitch is broader retained histories
and reproducible validation, not a demonstrated fuel-state estimator.

## Deliverables and verification

- [Per-object JSONL](eol-policy-relaxation-20260920.jsonl): 22 candidate records,
  event provenance, window counts, gap exclusions, exposure, eligibility and
  explicit null outcomes. These records are **not publishable EOL watch scores**.
- [Machine-readable receipt](eol-policy-relaxation-20260920-receipt.json): frozen
  manifest, source hashes, false-alarm context, archive rollup and stop decision.
- [Analysis module](../tools/eol_policy_probe.py): offline published-artifact
  census plus reusable gap-aware window and ratio helpers. Its CLI stops after
  this feasibility gate; it does not pretend to implement the future control study.

Canonical run: `nice -n 19 ionice -c 3 timeout 930s python3 tools/eol_policy_probe.py
--output-prefix docs/eol-policy-relaxation-20260920`. Output creation is exclusive;
reproduction needs a fresh output prefix. The canonical run took
**153.27 s wall / 130.26 s CPU**, read **137,788**
selected-object archive rows and verified all 256 shards. An initial independent
published-artifact census agreed on all 28 flags and 22 objects. Both used low
CPU/I/O priority; no GPU or production detector run was launched.

Offline synthetic checks passed for long spacings with continuous observations,
archive-hole rejection through the actual interval builder, exposure versus
calendar span, insufficient pairs, window boundaries, leap anniversaries,
missing/zero-denominator ratios and stop-rule nulls. No production, source UI,
existing tests, site, timer or deployment files were changed.
