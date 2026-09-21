# Phase 2: inclination conditioning pre-fix decomposition

Measured 2026-09-20 on bigmem; detector source unchanged throughout measurement.

**Decision: stop at the pre-registered diagnostic gate. No detector fix was
attempted.** The measured concentration is predominantly high-inclination,
well-covered histories, not low inclination or sparse baselines. No operating
point was selected and the 10× target was not used to fit a threshold.

In the fixed archive sample, **1,050/1,127 (93.17%)** passive inclination flags
lie between 60° and 120°; only **2/1,127 (0.18%)** are below 1°.
**953/1,127 (84.56%)** have all 12 neighboring baseline blocks. Sparse baselines
with 3–5 blocks account for only ten flags. The highest scatter band contains
one passive flag, and longer intervals do not have an elevated passive flag
rate. This does not prove every fit is well conditioned, but it rejects the
proposed location of the dominant false-alarm floor in this diagnostic sample.

The GEO constraint points the opposite way: **221/226** sampled payload
north–south catches and **2,734/2,845** published catalogue north–south catches
are below 1°. A blanket one-degree inclination gate would discard those
inclination catches while addressing only two sampled passive inclination flags.
Those are channel-catch counts, not a simulated after-gating event classification.
The underlying events remain candidates, not independently confirmed burns.

The published north–south catches are also not universally far above the threshold:
**2,345/2,845 (82.43%)** have 32 ≤ |z| < 64. Sample median |z| is **40.18 passive
versus 42.20 payload**; the z distributions substantially overlap. A general
threshold increase is not justified by these results.

## Pre-registration and decision rule

The supplied hypothesis was that passive inclination flags concentrate at low
inclination, sparse/irregular baseline coverage, or high fit scatter, while payload
inclination catches, especially GEO north–south keeping, survive above their own
conditioning floor. The supplied stop rule was to stop if the decomposition did
not support that concentration. No parameter, optional detector flag, or threshold
was changed for this investigation. Production kappa remains 32.

Before reading the archive results, the diagnostic population was fixed to all
classified passive/payload objects with `NORAD % 25 == 0`, across their entire
retained histories. Inclination bins were 0/1/5/15/30/60/90/120/180 degrees;
perigee bins use the existing Phase-0 function; baseline block counts were retained
individually; |z| bins were 32/64/128/256. Additional scatter and interval-duration
bins test the other two parts of the hypothesis. This is a diagnostic sample,
not a full-population remeasurement or a selected operating point.

## Live evidence and populations

The live manifest was fetched directly from
`https://sean.theinformed.org/space/data/manifest.json`. Its orbit event and history
records matched the local published copies. The event artifact and all 256
history shards were SHA-256 checked against that manifest. Artifact:
`orbit-events-d7919fbbd28d8c62.json`, generated `2026-09-19T12:48:51Z`.
This is newer than the brief's 6.84× reading: the current artifact reports 6.86×.

| Full-population published measure | Before | After |
|---|---:|---|
| Passive flags / intervals | 39,953 / 89,368,801 | Not run: pre-fix stop |
| Passive point rate, per 1,000 | 0.447058 | Not run |
| Passive Jeffreys 95% upper bound | 0.0004514564572 (0.451456 per 1,000) | Not run |
| Payload flags / intervals | 195,818 / 62,952,784 | Not run |
| Payload point rate | 0.003110553459 (3.110553 per 1,000) | Not run |
| Payload Jeffreys 95% lower bound | 0.003096820584 | Not run |
| Bound separation | 6.86×; requirement 10× | Not run |
| Passive inclination-channel flags | 29,625 | No detector change |
| Payload inclination-channel catches | 21,053 | No detector change |
| Payload GEO north–south-keeping catches | 4,660 | No detector change |
| Catalogue GEO north–south-keeping catches | 2,845 | No detector change |

“Channel” means the inclination test remained tripped after persistence and
physical-cost checks. It is not the signature count: 29,597 passive events have
`inclination-change` signatures; another 28 have `geo-north-south-keeping`.
The 74.08% figure is the former divided by all passive flags, not the channel's
share of all tripped elements.

The published detail shards contain **6,641 payload inclination catches**, including
all **2,845 catalogue north–south catches**, but **no passive self-history event
records**. The full control counts passive events before catalogue retention;
the retained detail records cannot reconstruct the complete passive control.
The headline list of 1,500 is ranked and was not used as a sample. The archive
sample below supplies the missing passive diagnostic evidence. Published and
archive columns overlap and must never be added together.

## Archive sample and join coverage

The unmodified CPU detector completed all **1,281 selected objects**: 528 passive
and 753 payload, **6,632,347 element rows**. Three passive objects and one payload
object had fewer than nine usable intervals and were excluded by the existing
production admission rule; they are counted here, not silently dropped. No
selected object was absent from the archive. Admitted interval totals were
**3,769,544 passive** and **2,242,250 payload**. There were **1,597 passive flags**,
**7,405 payload flags**, **1,127 passive inclination flags**, **809 payload
inclination catches**, and **226 payload GEO north–south catches**.

As a sampling check only, the pooled sample passive rate is 0.423659 per 1,000,
with Jeffreys upper bound 0.444818 per 1,000; the payload rate is 3.302486 per
1,000, with lower bound 3.228031 per 1,000, giving **7.257×** bound separation.
These sample numbers do not replace the published full-population control.
The systematic 1-in-25 sample is not a random confidence sample over objects;
these interval-level Jeffreys bounds do not quantify sampling/cluster uncertainty.

All **6,641** published inclination events matched an archive interval by NORAD
and the published start/end seconds: **zero missing joins**. Current baseline
sample counts equal the published `cohortCount` for **6,596**. For **45** events,
including **15** north–south catches, that count differs. Labelled gap:
`published-baseline-reconstructed-after-archive-growth (45 events)`.
Their current reconstructed block/scatter values remain in the table and are
not represented as exact historical published baselines. Matching a sample
count alone does not prove an unchanged historical baseline either.

## Inclination-channel decomposition

All cells count events whose inclination channel tripped. GEO NS is a subset of
payload, not another population. Bins are lower-inclusive/upper-exclusive; the
existing `>2000 km` label includes 2,000 km. z uses exact archive arithmetic or
the published z rounded to two decimals. Block counts/scatter for published
catches are reconstructed from the current archive.

| Dimension / band | Sample passive | Sample payload | Sample GEO NS | Published payload | Published GEO NS |
|---|---:|---:|---:|---:|---:|
| inclination / 0-1 | 2 | 223 | 221 | 2,809 | 2,734 |
| inclination / 1-5 | 3 | 14 | 4 | 255 | 84 |
| inclination / 5-15 | 5 | 12 | 1 | 211 | 20 |
| inclination / 15-30 | 13 | 2 | 0 | 139 | 6 |
| inclination / 30-60 | 54 | 73 | 0 | 338 | 1 |
| inclination / 60-90 | 681 | 400 | 0 | 1,307 | 0 |
| inclination / 90-120 | 369 | 85 | 0 | 1,582 | 0 |
| inclination / 120-180 | 0 | 0 | 0 | 0 | 0 |
| perigee / <300 km | 14 | 15 | 0 | 145 | 0 |
| perigee / 300-500 km | 35 | 61 | 0 | 598 | 0 |
| perigee / 500-800 km | 201 | 154 | 0 | 1,879 | 0 |
| perigee / 800-1200 km | 498 | 107 | 0 | 660 | 0 |
| perigee / 1200-2000 km | 374 | 232 | 0 | 104 | 0 |
| perigee / >2000 km | 5 | 240 | 226 | 3,255 | 2,845 |
| blockCount / 3 | 1 | 1 | 0 | 4 | 1 |
| blockCount / 4 | 3 | 2 | 1 | 28 | 1 |
| blockCount / 5 | 6 | 6 | 0 | 76 | 0 |
| blockCount / 6 | 3 | 29 | 1 | 519 | 14 |
| blockCount / 7 | 17 | 16 | 2 | 310 | 41 |
| blockCount / 8 | 16 | 12 | 5 | 163 | 42 |
| blockCount / 9 | 24 | 26 | 6 | 110 | 26 |
| blockCount / 10 | 33 | 33 | 9 | 181 | 29 |
| blockCount / 11 | 71 | 53 | 12 | 249 | 56 |
| blockCount / 12 | 953 | 631 | 190 | 5,001 | 2,635 |
| absZ / 32-64 | 995 | 650 | 178 | 4,273 | 2,345 |
| absZ / 64-128 | 117 | 101 | 40 | 1,142 | 404 |
| absZ / 128-256 | 10 | 32 | 5 | 519 | 65 |
| absZ / >=256 | 5 | 26 | 3 | 707 | 31 |
| scatterDegPerDay / <0.0001 | 79 | 78 | 0 | 578 | 7 |
| scatterDegPerDay / 0.0001-0.001 | 935 | 608 | 139 | 4,497 | 1,789 |
| scatterDegPerDay / 0.001-0.01 | 112 | 112 | 86 | 1,511 | 1,044 |
| scatterDegPerDay / >=0.01 | 1 | 11 | 1 | 55 | 5 |
| spanDays / 0.1-0.25 | 58 | 159 | 99 | — | — |
| spanDays / 0.25-1 | 836 | 529 | 121 | — | — |
| spanDays / 1-2 | 203 | 110 | 3 | — | — |
| spanDays / >=2 | 30 | 11 | 3 | — | — |

## Exposure-normalized diagnostic rates

These are **inclination-channel** flags per 1,000 usable archive intervals, not
the pooled all-channel false-alarm rate. The denominator follows production:
objects with fewer than nine intervals are excluded; retained intervals may
still have an unusable baseline. Zero flags in a bin is not a zero upper bound.

| Dimension / band | Passive intervals | Passive flags / 1,000 | Payload intervals | Payload flags / 1,000 |
|---|---:|---:|---:|---:|
| inclination / 0-1 | 18,874 | 0.1060 | 141,380 | 1.5773 |
| inclination / 1-5 | 52,754 | 0.0569 | 54,948 | 0.2548 |
| inclination / 5-15 | 155,180 | 0.0322 | 155,115 | 0.0774 |
| inclination / 15-30 | 142,220 | 0.0914 | 12,460 | 0.1605 |
| inclination / 30-60 | 177,975 | 0.3034 | 601,717 | 0.1213 |
| inclination / 60-90 | 1,720,126 | 0.3959 | 894,493 | 0.4472 |
| inclination / 90-120 | 1,501,148 | 0.2458 | 382,136 | 0.2224 |
| inclination / 120-180 | 1,267 | 0.0000 | 1 | 0.0000 |
| blockCount / 0 | 1,324 | 0.0000 | 439 | 0.0000 |
| blockCount / 1 | 2,363 | 0.0000 | 852 | 0.0000 |
| blockCount / 2 | 3,760 | 0.0000 | 1,696 | 0.0000 |
| blockCount / 3 | 5,791 | 0.1727 | 1,992 | 0.5020 |
| blockCount / 4 | 8,845 | 0.3392 | 2,929 | 0.6828 |
| blockCount / 5 | 11,638 | 0.5156 | 3,612 | 1.6611 |
| blockCount / 6 | 23,394 | 0.1282 | 19,250 | 1.5065 |
| blockCount / 7 | 33,648 | 0.5052 | 31,254 | 0.5119 |
| blockCount / 8 | 47,077 | 0.3399 | 39,022 | 0.3075 |
| blockCount / 9 | 68,588 | 0.3499 | 48,944 | 0.5312 |
| blockCount / 10 | 94,389 | 0.3496 | 38,700 | 0.8527 |
| blockCount / 11 | 197,801 | 0.3589 | 65,932 | 0.8039 |
| blockCount / 12 | 3,270,926 | 0.2914 | 1,987,628 | 0.3175 |
| scatterDegPerDay / <0.0001 | 1,085,694 | 0.0728 | 509,886 | 0.1530 |
| scatterDegPerDay / 0.0001-0.001 | 2,366,068 | 0.3952 | 1,300,912 | 0.4674 |
| scatterDegPerDay / 0.001-0.01 | 311,874 | 0.3591 | 425,827 | 0.2630 |
| scatterDegPerDay / >=0.01 | 5,908 | 0.1693 | 5,625 | 1.9556 |
| spanDays / 0.1-0.25 | 197,483 | 0.2937 | 263,323 | 0.6038 |
| spanDays / 0.25-1 | 2,424,419 | 0.3448 | 1,606,903 | 0.3292 |
| spanDays / 1-2 | 948,321 | 0.2141 | 319,394 | 0.3444 |
| spanDays / >=2 | 199,321 | 0.1505 | 52,630 | 0.2090 |

## Interpretation, arithmetic paths, and limits

The passive concentration is **872/1,127 (77.37%) at 800–2,000 km**, mostly with
ordinary baseline scatter: **935/1,127 (82.96%)** in 0.0001–0.001 deg/day. Sparse
coverage, large scatter, and long spans show no monotone control curve that
selects a conditioning gate. The scatter is `Baseline.scale`, the larger of
within-block and between-block robust rate scatter; it is **not** per-fit orbital
covariance. A robust scale can miss a fitter's tail. The earlier quantisation/tail
hypothesis remains a separate hypothesis, not a cause proven by this report;
`INCLINATION_FLOOR_TAIL_AWARE` remains false.

The existing geometry comment in [orbit_events.py](../pipeline/orbit_events.py)
states `di = eps` and `dRAAN sin(i) = eps`. Its `sigma/sin(i)` amplification applies
to the node coordinate. The node's one-degree abstention precedent therefore
cannot simply be transferred to the inclination channel. The measured passive
population reinforces that distinction.

Both arithmetic implementations are **unchanged**: `orbit_campaigns.py`,
`orbit_events.py`, and `orbit_sweep_gpu.py` retain their pre-measurement SHA-256
hashes, recorded in the [measurement receipt](orbit-phase2-inclination-decomposition-20260920.json).
No checkpoint fields, detector defaults, gap semantics, release code, drift code,
columnar code, UI, deployment, or timer were changed. No new data were dropped or
abstained by a proposed fix, because there is no proposed fix.

**No new parity proof is claimed.** The CPU/GPU parity suite and real-population
`--sweep-gpu-verify` were not run: the explicit stop rule terminated this phase
before any arithmetic change. The existing verification receipts remain historical
evidence only. Fixed-code full-population before/after acceptance, payload-loss
acceptance, and achievement of 10× remain **unmeasured/unproven**, not passes.
The live published bound remains 0.0004514564572 and separation 6.86×.

The archive diagnostic and published-baseline join used
`open_archive_for_reading`, SSD WAL, `query_only=1`, indexed selected-object reads,
nice **19**, and idle I/O. Archive measurement completed in **881.81 s wall /
850.72 s CPU** under a 1,500 s cooperative / 1,530 s hard bound; the published join
completed in **692.04 s** under a 900 s cooperative / 930 s hard bound. The two
small CPU readers overlapped; no GPU was used. The live publisher was left alone.
No deployment was performed; this report is committed repository evidence.

Other limits: the archive is mutable, not a preserved snapshot of the published
sweep; the diagnosis is a 1-in-25 sample, not a full-population inclination
breakdown; covariance and independent truth of payload manoeuvres are unavailable.
Published z values are rounded to two decimals (one is exactly 128.00), so a
published bin at that boundary is not an exact-arithmetic classification.

The receipt contains the selection SQL, code/data hashes, complete histogram
counts and denominators, measured timings, source function recipe, and gap counts.
The measurement programs are retained verbatim in that receipt as experiment
provenance; they are not installed into the production pipeline. All three
optional detector switches remained false, kappa was 32, and the CPU detector
was invoked without a GPU executor or verifier. The learn chapter and control
notes need no change because neither published numbers nor their meaning changed.
