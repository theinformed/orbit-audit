# Phase 2b: pre-registered high-inclination corroboration

Measured 2026-09-20 on bigmem, following `4c1722d`. The Phase-2
sin(i)-conditioning hypothesis remains rejected. This is a separate,
pre-registered corroboration test; no z threshold or 10× requirement was tuned.

**Accepted, then stopped:** the completed full-population bound separation rises
from **6.901× to 18.191×**, crossing the unchanged 10× requirement. The passive
rate falls 64.45% and the payload rate falls 5.66%; this is not the registered
symmetric trap. No further detector change or threshold tuning was attempted.
CPU and GPU implementations are committed together.

## Pre-registration and decision

**The diagnostic gate passed before either detector implementation was edited.**
At inclination ≥30°, **1,009/1,104 passive inclination flags (91.39%)** are
inclination-only, above the registered 60% requirement. Payload inclination-only
rate is **0.215083 per 1,000 usable intervals**, versus **0.296720 passive**:
**0.724868×**, below the registered approximately 1.5× ceiling.

| Pre-registered high-inclination measure | Passive sample | Payload sample | Published payload details |
|---|---:|---:|---:|
| Usable intervals at ≥30° | 3,400,516 | 1,878,347 | Not a control denominator |
| Inclination catches at ≥30° | 1,104 | 558 | 3,227 |
| Inclination-only catches | 1,009 | 404 | 1,413 |
| Inclination-only fraction | 91.39% | 72.40% | 43.79% |
| Inclination-only catches / 1,000 intervals | 0.296720 | 0.215083 | Not estimated |

All **1,413** published high-inclination-only catches carry the
`inclination-change` signature. The other **1,814** published high-inclination
catches co-trip semi-major axis or eccentricity. The different 72.40% sample
and 43.79% published fractions describe different populations: the published
catalogue is retained selectively and its events are not a representative
control sample. Neither fraction alone supplies a false-alarm rate.

Selection and thresholds were supplied in the user pre-registration, before
measurement: all classified passive/payload objects with `NORAD % 25 == 0`,
whole retained histories, the prior inclination bins, the production admission
rule of at least nine usable intervals, and kappa 32. “Inclination-only” uses
exactly the sorted persistence-surviving tripped-channel set carried by each
propulsive self-history event, after the physical-cost check. Sample and
published counts overlap and must not be added.

## Inputs and reproducibility

The public manifest was fetched directly from
`https://sean.theinformed.org/space/data/manifest.json`. Its event record remains
`orbit-events-d7919fbbd28d8c62.json`, generated `2026-09-19T12:48:51Z`.
The event artifact and all **256** local detail shards passed SHA-256 checks
against that live manifest. All self-history detail records were scanned,
not just the ranked headline list of 1,500. They contain **91,197 payload
self-history events**, including **6,641 inclination catches**, and no passive
self-history detail records. Thus the passive gate requires the archive sample.

The sample completed all **1,281 objects**: 528 passive and 753 payload,
**6,632,347 element rows**. Three passive objects and one payload object had
fewer than nine usable intervals; they remain counted as admission exclusions.
Admitted exposure is **3,769,544 passive / 2,242,250 payload intervals**.
The sample's exact input SHA-256, counts, and source hashes match Phase 2.
It again produced 1,597 passive flags, 7,405 payload flags, 1,127 passive
inclination flags, 809 payload inclination catches, and 226 payload GEO
north–south catches. The new measurement adds the channel-combination cross-tab.

The sample used the original retained measurement program with that extra
field, an SSD/WAL `query_only` reader, indexed selected-object reads, nice 19,
and idle I/O. It took **977.17 s wall / 930.01 s CPU**, within the registered
1,500 s cooperative / 1,530 s hard measurement bound. The published scan took
105.83 s. No provider ingestion or orbital-elements fetch was involved.
The [JSON receipt](orbit-phase2b-corroboration-20260920.json) retains the
measurement programs, counts, data/source hashes, resource receipts, and
verification evidence. Its registration timestamp is the durable transcription
time; the user supplied the rules before measurement began.

## Channel combination × inclination

`i` = inclination; `a` = semiMajorAxis; `e` = eccentricity. Each row counts
inclination catches only, so the four combinations are mutually exclusive
and sum to the row total. Bins are lower-inclusive, upper-exclusive, with
180° included in the last band. Blank fractions have zero observed catches,
not a zero statistical upper bound.
### Sample passive

| Inclination | i only | i+a | i+e | i+a+e | Total i | i-only fraction |
|---|---:|---:|---:|---:|---:|---:|
| 0-1 | 1 | 0 | 1 | 0 | 2 | 50.00% |
| 1-5 | 1 | 0 | 1 | 1 | 3 | 33.33% |
| 5-15 | 4 | 0 | 0 | 1 | 5 | 80.00% |
| 15-30 | 9 | 0 | 4 | 0 | 13 | 69.23% |
| 30-60 | 51 | 0 | 3 | 0 | 54 | 94.44% |
| 60-90 | 622 | 8 | 43 | 8 | 681 | 91.34% |
| 90-120 | 336 | 8 | 21 | 4 | 369 | 91.06% |
| 120-180 | 0 | 0 | 0 | 0 | 0 | — |

### Sample payload

| Inclination | i only | i+a | i+e | i+a+e | Total i | i-only fraction |
|---|---:|---:|---:|---:|---:|---:|
| 0-1 | 191 | 14 | 6 | 12 | 223 | 85.65% |
| 1-5 | 4 | 2 | 0 | 8 | 14 | 28.57% |
| 5-15 | 7 | 0 | 4 | 1 | 12 | 58.33% |
| 15-30 | 0 | 0 | 0 | 2 | 2 | 0.00% |
| 30-60 | 48 | 4 | 10 | 11 | 73 | 65.75% |
| 60-90 | 307 | 63 | 17 | 13 | 400 | 76.75% |
| 90-120 | 49 | 26 | 4 | 6 | 85 | 57.65% |
| 120-180 | 0 | 0 | 0 | 0 | 0 | — |

### Published payload

| Inclination | i only | i+a | i+e | i+a+e | Total i | i-only fraction |
|---|---:|---:|---:|---:|---:|---:|
| 0-1 | 2,533 | 103 | 64 | 109 | 2,809 | 90.17% |
| 1-5 | 62 | 9 | 16 | 168 | 255 | 24.31% |
| 5-15 | 17 | 6 | 12 | 176 | 211 | 8.06% |
| 15-30 | 23 | 8 | 3 | 105 | 139 | 16.55% |
| 30-60 | 134 | 59 | 23 | 122 | 338 | 39.64% |
| 60-90 | 595 | 596 | 42 | 74 | 1,307 | 45.52% |
| 90-120 | 684 | 614 | 46 | 238 | 1,582 | 43.24% |
| 120-180 | 0 | 0 | 0 | 0 | 0 | — |

### Sample exposure-normalized inclination-only rates

| Inclination | Passive intervals | Passive i-only / 1,000 | Payload intervals | Payload i-only / 1,000 | Payload/passive |
|---|---:|---:|---:|---:|---:|
| 0-1 | 18,874 | 0.052983 | 141,380 | 1.350969 | 25.4982× |
| 1-5 | 52,754 | 0.018956 | 54,948 | 0.072796 | 3.8403× |
| 5-15 | 155,180 | 0.025777 | 155,115 | 0.045128 | 1.7507× |
| 15-30 | 142,220 | 0.063282 | 12,460 | 0.000000 | 0.0000× |
| 30-60 | 177,975 | 0.286557 | 601,717 | 0.079772 | 0.2784× |
| 60-90 | 1,720,126 | 0.361601 | 894,493 | 0.343211 | 0.9491× |
| 90-120 | 1,501,148 | 0.223829 | 382,136 | 0.128227 | 0.5729× |
| 120-180 | 1,267 | 0.000000 | 1 | 0.000000 | — |

## Why 30°, and what the test does not establish

The boundary was fixed from the **prior all-inclination-channel rate table**:

| Prior band | Passive i / 1,000 | Payload i / 1,000 | Payload/passive |
|---|---:|---:|---:|
| 0–1° | 0.1060 | 1.5773 | 14.88× |
| 15–30° | 0.0914 | 0.1605 | 1.76× |
| 30–60° | 0.3034 | 0.1213 | 0.40× |
| 60–90° | 0.3959 | 0.4472 | 1.13× |
| 90–120° | 0.2458 | 0.2224 | 0.90× |

That collapse selects the already declared 30° boundary; it was not scanned
against the eventual separation. The 15–30° evidence is sparse—13 passive and
only two payload inclination catches—so it does **not** establish a precise
physical discontinuity at 30°. The new inclination-only table actually has
zero payload inclination-only catches in that lower band; the boundary was
not selected from this new table. No alternative cutoff was tried.

These rates support a dominant, poorly discriminating component. They do not
prove that every removed payload catch is noise, that energy corroboration
confirms a burn, or that every physical plane change must trip an energy
channel. The operational action is an explicitly labelled abstention under a
measured control limitation, not a declaration of the cause of each anomaly.

## Implementation and checkpoint continuity

For fresh self-history sweeps, an inclination trip with starting inclination
≥30° abstains unless `semiMajorAxis` or `eccentricity` **also survives persistence
in that same interval**. A raw energy spike that fails persistence cannot
corroborate it. A node trip cannot corroborate it. Below 30° the channel set and
returned events are unchanged by construction. Other enabled channels may still
produce an event after an inclination abstention.

The CPU tests the surviving set at the existing call site. The GPU independently
computes a corroboration mask from its threshold and persistence arrays and the
same starting inclination. Raw threshold and persistence decisions remain
available for exact comparison; verification additionally compares every
visited corroboration decision exactly. GPU execution consumes the device
mask without running the CPU corroboration predicate.

Every abstention increments detector diagnostics, the whole-pass count, and
its passive/payload Phase-0 `abstention.inclinationUncorroborated` bucket where
applicable. The published control output exposes the count, boundary, and reason:

> inclination change unconfirmed by any energy channel at high inclination,
> where the control measures no discriminating power

Counts are at the post-persistence decision, before later tracking-gap and
physical-cost checks. Therefore an abstention need not equal an event removed
from the old final catalogue: the old detector might already have rejected that
interval later. Such differences are not silently represented as saved false alarms.

`ArchivePass.__setstate__` backfills the new counter and policy provenance.
**A checkpoint predating corroboration finishes its entire sweep under the old
policy**, including serial, process-pool, columnar, and GPU execution. Its control
output explicitly says corroboration is disabled for that legacy checkpoint
and its abstention count is unmeasured, not zero. Fresh sweeps enable the rule.
Merging incompatible nonempty sweep policies raises. This preserves in-flight
work without pooling two detectors into one reported rate. Neither release
checkpoint identity nor its version was changed.

All **2,845** GEO north–south catches in the verified public artifact would retain their
inclination channel under the rule. There are 2,844 below 30°; the remaining
catch, NORAD 42965 on 2017-10-13 at 40.2242°, co-trips semi-major axis. That is a
published-record cross-check, separate from the actual full-sweep acceptance
counts below.


## Full-population paired acceptance

The full read completed **68,711 objects / 216,937,493 element rows**,
with **61,377 objects** admitted to both detectors.
The remaining objects had fewer than nine usable intervals. Both detectors
received identical rows and GPU arithmetic for each admitted object; both
control denominators agree exactly. The earlier live artifact is shown separately.

| Measure | Live artifact before this task | Paired original | Paired corroboration |
|---|---:|---:|---:|
| Passive usable intervals | 89,368,801 | 89,384,239 | 89,384,239 |
| Passive flags | 39,953 | 39,954 | 14,204 |
| Passive flags / 1,000 | 0.447058 | 0.446992 | 0.158909 |
| Passive 95% upper bound / 1,000 | 0.451456 | 0.451390 | 0.161539 |
| Payload usable intervals | 62,952,784 | 62,984,047 | 62,984,047 |
| Payload flags | 195,818 | 197,075 | 185,926 |
| Payload flags / 1,000 | 3.110553 | 3.128967 | 2.951954 |
| Payload 95% lower bound / 1,000 | 3.096821 | 3.115197 | 2.938579 |
| Bound separation (10× required) | 6.860× | 6.901× | 18.191× |
| Passive inclination catches | 29,625 | 29,626 | 3,876 |
| Payload inclination catches | 21,053 | 21,055 | 9,906 |
| Payload GEO north–south catches | 4,660 | 4,662 | 4,662 |
| Teaching-catalogue GEO north–south catches | 2,845 | 2,847 | 2,847 |
| Passive inclination abstentions | Not measured | Not measured | 25,752 |
| Payload inclination abstentions | Not measured | Not measured | 11,174 |
| All-object inclination abstentions | Not measured | Not measured | 40,300 |

The passive point rate falls **64.45%**, while the payload rate falls
**5.66%**, retaining 94.34% of payload flags. This is not proportional loss
and does not trigger the registered symmetric trap. Bound separation reaches
**18.191×**, so the registered scientific stop rule is satisfied: stop here.
No threshold, 30° boundary, or 10× requirement was changed after this result.
The exact control bounds are retained in the JSON receipt.

Every one of **38,693 returned events
below 30°** was compared for exact equality and remained unchanged. Across all
object types, 40,160 old events were removed and
0 events appeared. All 40,160 removals carry `inclination-change`; other
signatures, including all 4,662 payload GEO north–south catches, are preserved.
The all-object abstention count includes 3,374 outside passive/payload classes.
There are 140 more abstentions than final event removals; these counters
measure different stages of the detector.
This is an actual detector rerun, rather than subtraction of the pre-registration
table. Abstentions precede later event rejection, so their count is not the
number of removed final events.

The bounded full measurement used three disjoint consecutive NORAD ranges,
(0, 22966], (22966, 57648], and (57648, 2147483647], merged in archive order.
It began with two ranges; when the first completed, the unscanned tail of the
second was split so the freed reader could help. At most two readers ran
concurrently. All three ranges completed;
no partial range was accepted. Both initial 7,200-second slices stopped cleanly
and resumed from their saved object cursors under the same bounds. The initial
183,281,909-row planning rollup underestimated the rows actually read; it was
used only to choose the partition, never as a denominator or completion test.
The difference is not attributed to a particular cause here. All admitted
objects used the GPU, with zero
fallbacks, failures, or telemetry gaps. This is an execution receipt, separate
from the CPU/GPU oracle proof below. Peak accounted VRAM across the recorded
workers was 285,703,168 bytes per process,
within each broker's 320 MiB allowance. Each worker ran at nice 19 and idle I/O,
with a 7,200 s cooperative / 7,260 s hard bound and resumable diagnostic
checkpoints written only under `/tmp/orbit-phase2b`.

Accepted worker slices total **20825.23 worker-seconds
wall / 10603.88 CPU-seconds**; the parallel phase elapsed
11245.50 s. These are **not total task costs**. An
initial non-resumable exploratory prefix was discarded when its throughput
showed it would exceed the bound. A subsequent selected-object reader was
replaced after its SQLite query plan exposed repeated epoch-prefix filtering;
saved complete batches were retained. The consecutive reader was then split
into two ranges, retaining its 512-object / 3,403,114-row prefix. The later
tail split retained every saved object and is recorded in the partition receipt.
Unsaved work at these restarts was discarded and is absent from accepted-worker
timings. No discarded counts enter the result. The receipt records the input
hash chains, partition, final programs, and timing limitation.

## Arithmetic verification

The actual sweep verification path used by `--sweep-gpu-verify` was exercised
through `tools/measure_orbit_sweep_modes.py --mode verify`, which forwards to
`sweep_archive(gpu_verify_devices=(0,))`. The CLI forwarding regression also
passes. This avoids invoking the release builder, checkpoint writer, or tail.

The deterministic real-population verification selected **1,000 objects**,
**1,230,008 element rows / 1,086,894 usable intervals**, in the fixed
2024-01-01 ≤ epoch < 2026-09-01 window, seed 20260912, at production kappa 32.
It completed **3,260,682 channel comparisons**, **4,632 raw threshold flags**,
**2,681 persistent channel flags**, and **4,118 corroboration decisions**,
including **21 inclination abstentions**. There were **zero disagreements,
zero fallbacks, and zero telemetry gaps**. Largest absolute z difference was
1.8189894035458565e-12; flag comparisons have no numerical tolerance.

This run took **321.53 s wall / 3.15968 CPU core-minutes** under shared load.
The private pool peaked at **1,294,848 bytes**; with the existing 256 MiB context
reserve, accounted VRAM peaked at **269,730,304 bytes**, below the 320 MiB
ceiling. This is accounted memory, not an exact physical per-process VRAM
measurement under WSL. The broker assigned physical card 1, exposed as logical
CUDA device 0. The command was admitted through:

```
/home/sdegan/gpu-broker/gpu-run --estimate-mib 320 --class standard
```

All optional detector switches remained false. CPU/GPU tests include deliberate
threshold, persistence, and corroboration flips, which raise instead of falling
back; execution tests forbid the CPU corroboration predicate while GPU results
are consumed. Real CUDA fixtures cover the 30° boundary, each energy channel,
energy spikes failing persistence, and GEO north–south preservation. All
**35 CUDA-enabled focused tests passed**, with no skips. Two further offline
regressions verify legacy policy preservation through columnar dispatch and
GPU execution. No model placement, workload, timer, release, or deployment
was changed by the measurements.

The final suite ran from the actual repository after the measured files were
installed: **624 tests in 125.138 s, OK (5 opt-in skips)**. The four CUDA cases
were also covered by the separate 35-test CUDA-enabled run above. An earlier
broad run under the temporary candidate directory encountered only fixture-path
errors; those paths were checked, and this final repository run is the clean
acceptance result. `git diff --check` also passes.

```
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 nice -n 19 timeout 360 \
  .venv-gpu/bin/python -m unittest discover -s tests -p 'test_orbit*.py'
```

## Unproven items and scope

- A systematic 1-in-25 object sample is not a random confidence sample; pooled
  interval Jeffreys bounds do not quantify clustering or object-selection
  uncertainty. The diagnostic and full-population archive overlap, so the
  full control is not independent physical ground truth.
- The GPU oracle proof is the measured 1,000-object population and fixtures,
  not a full-archive CPU/GPU comparison. Full-population before/after acceptance
  uses the same GPU arithmetic for the original and candidate event passes;
  it does not establish zero CPU/GPU flag disagreements on unverified intervals.
- Independent truth for removed payload manoeuvres, per-fit orbital covariance,
  the physical cause of high-inclination tails, and a physical discontinuity
  exactly at 30° remain unproven. Catch retention is not measured true-positive
  recall. A co-tripped energy channel does not independently confirm a burn.
- The archive is mutable. Both detectors see exactly the same in-memory rows
  for each object, but a whole sweep is a mosaic of read times, not a preserved
  global database snapshot. The live artifact is a separate earlier population.
- This is source and repository evidence. No release tail, public after-change
  artifact, frontend, deployment, or timer operation was exercised. Legacy
  checkpoints intentionally finish their old policy; only fresh sweeps use
  corroboration. The public artifact measured at the start reported 6.86×; the 18.191× result
  is a repository measurement, not a claim that a new artifact was published.
