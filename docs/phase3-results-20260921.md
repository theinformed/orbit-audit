# Phase 3 results: the covariate-aware gate, measured on the whole archive

Measured 2026-09-21 on `bigmem` (pc), against the pre-registration committed at
`7eab5a4` — **ahead of every number below**, in its own commit, which is what
makes it a registration rather than a description. Read
`docs/phase3-preregistration-20260921.md` first; this document only reports what
its rules produced.

**Registered verdict: FAIL. The covariate-aware gate does not ship.**

It fails for a reason worth stating precisely, because it is not the reason the
registration expected. The exposure experiment the registration named
*worked* — the clause Paper B failed now passes, decisively. The gate is shut by
the **other** clause, and that clause is not short of data. It is short of
separation, on the point estimates themselves.

## The headline

| Quantity (per 1,000 usable intervals) | Paper B, 1-in-5 sample | Phase 3, full archive |
|---|---:|---:|
| Raw passive floor | 0.162716 | **0.158910** |
| Reweighted to the payload covariate mix, `S_1000` | 0.223524 | **0.275578** |
| Reweighted / raw | 1.3737x | **1.7342x** |
| Primary clustered-bootstrap 95% | [0.153825, **1.845847**] | [0.207891, **0.502491**] |
| Payload exposure in labelled gaps | 13.358% | **3.621%** |
| Supported strata at `S_1000` | — | **389** (162 gap strata) |

| Registered clause | Requirement | Measured | |
|---|---|---:|---|
| 1. `R_rw` bootstrap 95% upper below the published target | < 1.0 | **0.502491** | **PASS** |
| 2. Reweighted separation, payload lower bound over passive upper bound | >= 10.0x | **5.3560x** | **FAIL** |

Both clauses are required. One passing does not make a partial win, and the
registration says so in advance (§5): a result that clears one clause and not
the other is reported as *"the covariate-aware gate does not yet ship"*, not as
a half-victory quoted without its failing half.

## What the experiment bought, and it is not nothing

The registration's §3 experiment was to widen the `norad % 5 == 0` systematic
sample inside the thin, payload-heavy strata. This pass widened it to the
limit: **modulus 1, every in-scope object in the archive** — 31,499 objects,
89,402,955 passive and 63,018,120 payload usable intervals, against Paper B's
17,877,732 and 12,746,434. That is a strict superset of the targeted
oversample, and it is the only version of the experiment with no sampling
headroom left behind it.

It did what the results report predicted it would do:

- The primary bootstrap upper bound fell from **1.846 to 0.502**, a factor of
  3.7. Clause 1, which Paper B failed by nearly 2x, now **passes by a factor of
  2**.
- Labelled gaps fell from **13.358% to 3.621%** of payload exposure.
- The support tier stopped mattering. In Paper B the choice between `S>=1` and
  `S_1000` moved the upper bound from 26.19 to 1.85; on the full archive the
  `S>=1` tier gives `R_rw` 0.277853 against `S_1000`'s 0.275578, a difference of
  0.8%, with gaps of 0.175%. The estimator is no longer an artefact of where the
  support line is drawn — which was the single strongest objection to Paper B's
  Analysis 1.

So the diagnosis in `docs/paperb-results-20260920.md` §5.2 was correct, and the
remedy it named was the right remedy. It simply was not sufficient.

## Stop rule: which condition ended collection

The registration's §5 primary stop rule offers two conditions: (a) all ten named
strata reach `S_1000`, or (b) the resource budget is exhausted first. **Neither
is what happened, and the honest answer is a third thing the registration did
not anticipate: the archive itself was exhausted.**

**8 of the 10 named strata reached `S_1000`.** The other two cannot, by any
sampling effort, because modulus 1 *is* the entire retained archive. There is no
denser pass available.

| Stratum | Sampled | Full archive | Growth | Flags | Payload weight | `S_1000` |
|---|---:|---:|---:|---:|---:|:--|
| `300-500 km \| 30-60 \| <0.001 \| 0.25-1 d` | 512 | **5,429** | 10.60x | 3 | 5.083% | YES |
| `>2000 km \| 0-1 \| <0.001 \| 0.25-1 d` | 1,773 | **12,296** | 6.94x | 18 | 3.564% | YES |
| `500-800 km \| 30-60 \| <0.001 \| <0.25 d` | 1,206 | **9,801** | 8.13x | 1 | 1.891% | YES |
| `300-500 km \| 90-120 \| <0.001 \| 0.25-1 d` | 582 | **5,563** | 9.56x | 0 | 1.003% | YES |
| `>2000 km \| 0-1 \| <0.001 \| 1-2 d` | 565 | **3,270** | 5.79x | 6 | 0.890% | YES |
| `300-500 km \| 30-60 \| <0.001 \| <0.25 d` | 133 | **998** | 7.50x | 0 | 0.781% | **no** |
| `>2000 km \| 0-1 \| <0.001 \| <0.25 d` | 366 | **3,293** | 9.00x | 7 | 0.821% | YES |
| `500-800 km \| 30-60 \| <0.001 \| 1-2 d` | 1,747 | **20,145** | 11.53x | 0 | 0.680% | YES |
| `300-500 km \| 30-60 \| <0.001 \| 1-2 d` | 38 | **473** | 12.45x | 0 | 0.389% | **no** |
| `300-500 km \| 90-120 \| <0.001 \| <0.25 d` | 162 | **1,223** | 7.55x | 0 | 0.260% | YES |

Growth factors exceed the naive 5x because the 1-in-5 modulus sample was itself
unlucky in these small cells, and because the archive gained a day of
observations between the two passes. The two strata that did not clear are both
at 300-500 km perigee, and one of them — 998 intervals — missed the line by two.
That is reported as it fell; the tier is not moved to collect it.

## Why the gate is shut, and why more data will not open it

Clause 2 fails at **5.3560x** against a required 10x. The tempting reading is
that this is another power problem: widen the interval's waist and the ratio
climbs. **It is not, and this is the most important number in this document.**

The separation is the payload rate's lower bound over the passive floor's upper
bound. Drive the passive interval's width to zero — infinite passive exposure,
a bootstrap upper bound collapsed onto the point estimate — and the ratio
becomes 2.691352 / 0.275578 = **9.7662x**. Still short.

Read *both* sides at their point estimates, with no uncertainty anywhere at all:

> payload 2.704389 / passive 0.275578 = **9.8135x**, against a 10x requirement.

**The covariate-matched separation is below the bar on the point estimates
themselves.** No quantity of additional passive exposure can move it, because
exposure only narrows intervals and the intervals are no longer what is
binding. The reweighted payload rate is 9.81 times the reweighted passive floor,
and the detector requires 10. That is a statement about the detector and the
populations, not about the sample size.

Both estimators of the payload side agree: the shipped Jeffreys estimator that
`_control_rates` actually uses gives 5.3560x, and the secondary clustered
payload-object bootstrap gives 5.3133x. There is no version of the payload
bound under which clause 2 passes.

This also means the verdict is **FAIL** and specifically **not**
"still-underpowered". Underpowering is real but confined: it affects 3.62% of
payload exposure sitting in labelled gaps, and it cannot rescue clause 2 even if
every gap were filled at the most favourable rate.

### The registered response

§5 of the registration anticipated exactly this and fixed the response in
advance:

> If the exposure experiment in §3 fails to clear the acceptance rule even after
> (a), the correct registered response is to report that the low-perigee,
> near-circular, 30-120-degree belt's passive floor still does not bound the
> payload population at 1-in-1,000 — **not to fall back on moving the
> corroboration boundary as an alternate route to a shippable number.**

So: the pooled-floor gate keeps governing `sufficientToLabel` exactly as it does
today. Nothing in the shipped detector changes on the strength of this
measurement. `INCLINATION_CORROBORATION_MIN_DEG` is not touched, and the
54-degree matched region measured in Paper B's Analysis 2b remains an open
question requiring its own registration (§4).

Per the operator's standing ruling, **the site keeps its wording either way**.
Phase 3 gates the papers, not the site.

## M7 — which gaps are physically unfillable, quantified

Reviewer finding M7 says the remedy Paper B named may be physically
unobtainable in the lowest perigee bands, because debris lifetimes at 300-500 km
are months and strongly solar-cycle dependent: the atmosphere removes the
exposure faster than any campaign can observe it.

That is a physical claim, and this pass tests it without an atmosphere model. If
it is true, the ratio of passive to payload exposure must **collapse** as perigee
falls — fragments are removed while the payloads sharing the shell are
drag-compensated and stay. It does:

| Perigee band | Passive intervals | Payload intervals | passive/payload | Strata < `S_1000` | Gap payload weight |
|---|---:|---:|---:|---:|---:|
| `<300 km` | 1,730,899 | 198,879 | 8.703 | 58 | 0.083% |
| **`300-500 km`** | 3,523,547 | 6,377,514 | **0.552** | 43 | **1.595%** |
| `500-800 km` | 31,119,569 | 22,490,091 | 1.384 | 20 | 0.042% |
| `800-1200 km` | 36,409,230 | 10,316,389 | **3.529** | 12 | 0.260% |
| `1200-2000 km` | 12,274,669 | 11,967,634 | 1.026 | 8 | 1.345% |
| `>2000 km` | 4,345,041 | 11,667,613 | 0.372 | 21 | 0.297% |

At 800-1200 km there are 3.5 passive intervals for every payload interval. At
300-500 km there are 0.55 — a factor of 6.4 collapse into the shell where
payload exposure is *largest*. The `<300 km` ratio of 8.7 is not a
counter-example: that band holds almost no payload exposure (198,879 intervals,
0.3% of the payload population), so it is debris-rich and payload-poor rather
than well-matched.

**Atmosphere-limited totals.** Of the 162 strata below `S_1000` carrying payload
exposure, **101 lie at or below 500 km perigee**. They carry **1.678% of total
payload exposure**, which is **46.33% of the entire 3.621% labelled gap**. These
are reported as labelled gaps permanently: they are not targets, and no future
pass should be planned against them.

The remaining 53.67% of the gap is **not** atmosphere-limited and should not be
described as such. Its single heaviest member makes the point:

| Stratum | Passive | Payload | Payload weight | Atmosphere-limited? |
|---|---:|---:|---:|:--|
| `1200-2000 km \| 30-60 \| <0.001 \| 0.25-1 d` | **4** | 591,826 | 0.939% | no |
| `300-500 km \| 30-60 \| <0.001 \| <0.25 d` | 998 | 492,168 | 0.781% | **yes** |
| `300-500 km \| 30-60 \| <0.001 \| 1-2 d` | 473 | 245,213 | 0.389% | **yes** |
| `300-500 km \| 60-90 \| <0.001 \| 0.25-1 d` | 952 | 171,989 | 0.273% | **yes** |
| `1200-2000 km \| 30-60 \| <0.001 \| 1-2 d` | 7 | 163,677 | 0.260% | no |
| `>2000 km \| 0-1 \| <0.001 \| >=2 d` | 585 | 155,764 | 0.247% | no |
| `1200-2000 km \| 30-60 \| <0.001 \| <0.25 d` | **0** | 87,598 | 0.139% | no |

The heaviest labelled gap in the whole estimate is a **1200-2000 km**,
near-circular, 30-60 degree cell holding 0.939% of payload exposure on **four**
passive intervals, and one closely related cell holds 87,598 payload intervals
on **zero**. Debris does not decay out of 1200-2000 km on any human timescale,
so this is not an atmospheric limit — it is a genuine sparseness of passive
objects in near-circular mid-altitude orbits at those inclinations. Calling the
whole residual gap "atmosphere-limited" would be wrong by more than half, and
that distinction is exactly what a referee would check.

## M14 — the Kozai perigee offset, measured rather than asserted

Reviewer finding M14 observes that the archive's semi-major axis is derived
Keplerian from the catalogue's Brouwer-Kozai mean motion with no Kozai
transform, so the derived **perigee altitude** inherits an inclination-dependent
offset: about **+3.35 km at i = 0** and **-1.68 km at i = 90** at 500 km
altitude, a spread of roughly 5 km. Perigee is one of this analysis's four
stratification factors, and the band edges sit at 300, 500, 800, 1200 and
2000 km — so the offset can move exposure across a stratum boundary.

Two measurements bound the effect.

**How much exposure is even at risk.** Tallying every interval whose derived
perigee lies within one full Kozai spread (5.03 km) of a band edge: **2.997% of
passive exposure and 2.415% of payload exposure**. Roughly 97% of the
stratification cannot be affected by the offset at all, because it is nowhere
near an edge.

**What happens if the whole population is shifted.** Re-binning every interval
at perigee + 3.35 km and again at perigee - 1.68 km — a deliberately worst-case
uniform shift, since it moves every near-edge interval the same way at once:

| Perigee assignment | `R_rw` per 1,000 | Ratio to raw | `S_1000` strata | Gap share |
|---|---:|---:|---:|---:|
| **Nominal (registered)** | **0.275578** | 1.7342x | 389 | 3.621% |
| +3.35 km (i = 0 extreme) | 0.276447 | 1.7396x | 390 | 3.662% |
| -1.68 km (i = 90 extreme) | 0.273085 | 1.7185x | 391 | 2.833% |

The estimand moves by at most **+0.32% / -0.90%**. Clause 1 passes under all
three assignments; clause 2 fails under all three by a wide margin. **The Kozai
offset cannot change either registered decision.** The effect on stratum
boundaries is real, bounded, and immaterial at this scale — which is what the
methods sentence M14 asks for should say, with these numbers attached.

This is a **post-hoc, not pre-registered** diagnostic and carries no decision
weight. The registered estimand is the nominal assignment alone.

## M8 — the pre-registration timestamp is still not external

Reviewer finding M8 is not addressed by this work and is restated here so it is
not lost: commit dates are set by the committing process and are trivially
forgeable, so a private local git history is **not** a third-party
pre-registration timestamp, however truthful its ordering happens to be. That
applies to `docs/phase3-preregistration-20260921.md` exactly as it applies to
Paper B's.

**TODO, owned outside this measurement and required before submission:** anchor
the registration commits externally — a public mirror, OpenTimestamps stamps on
the registration blobs, or an OSF deposit with a DOI — and then replace
"verifiable from the repository history" with the name of the external anchor.
Until that is done, every registration-ordering claim in both papers should be
read as asserted rather than verified.

## What was measured, and how

- Read-only throughout, via `orbit_campaigns.open_archive_for_reading()`:
  `mode=ro` URI, `PRAGMA query_only=1`, WAL, `nice 19`, idle I/O, a cooperative
  wall-clock budget per reader with resumable NORAD cursors under
  `/tmp/phase3-20260921`, and a hard deadline enforced inside SQLite's progress
  handler. No write path was opened. The `orbit_release` timer kept running on
  its two-hourly schedule throughout and was never touched; a read-only
  connection never contends for the sweep's lock.
- Sample: **every** archive object with `object_type` in `DEBRIS`,
  `ROCKET BODY`, `PAYLOAD`, across whole retained histories. 31,499 objects
  selected (12,635 passive, 18,864 payload); 119 excluded by the production
  nine-interval admission rule and counted, not dropped.
- Detector: current HEAD, `kappa = 32`, all three optional switches `False`,
  **no source file outside `tools/phase3_*` changed by this task**. Corroboration
  **active** — the detector that ships, which is what the registered estimand is
  defined on. The pre-corroboration state Paper B also tallied is out of Phase 3
  scope and was not run, which is what made a 5x larger sample affordable.
- A "flag" is an event whose signature is not in `NON_PROPULSIVE_SIGNATURES`;
  exposure is usable intervals from admitted objects. Both unchanged from the
  published control and from Paper B.
- Estimators **imported** from `tools/paperb_strata.py`, not reimplemented:
  `reweight`, `bootstrap_reweighted`, `jeffreys`. `MIN_SEPARATION_BOUND_RATIO`
  and the 0.001 target imported from `pipeline/orbit_events.py`. Phase 3 applies
  the existing standard to a new quantity; it does not restate the standard.
- Bootstrap: 2,000 resamples, **seed 20260921**, 12,547 passive objects
  resampled with replacement, payload weights held at observed values. Run once.

### Validation, before the numbers

`tools/phase3_measure.py` was checked against Paper B rather than trusted. Re-run
over the 115 objects of the modulus-5 sample below NORAD 3000 and compared
record by record against `/tmp/paperb-20260920/part0.objects.jsonl`: **every flag
count identical per object and per stratum cell**, no object lost exposure, no
new stratum key. The only difference was +0 to +2 intervals per object — one day
of archive growth — in the expected direction and magnitude.

`tools/phase3_selftest.py` holds 50 offline assertions that never open the
archive, including an end-to-end synthetic case that returns **PASS**, so the
harness was shown capable of producing the favourable answer before it was
pointed at real data.

### One defect found and fixed before any result existed

The registered primary interval is an object-level clustered bootstrap, and
`bootstrap_reweighted` resamples objects **by index**. The order of the object
list was therefore part of the estimator's input — and that order was whatever
order records happened to be read, which depends on how many shards the
extraction was split into and in what order their files were passed. When the
extraction was widened from 2 shards to 9, that would have silently moved the
number the acceptance rule is applied to, and the move would have looked like a
measurement rather than an artefact of process scheduling. Fixed at `d4e9090` by
sorting per-object records by NORAD before the bootstrap sees them; verified on
frozen snapshots that either shard order now reproduces the floor and both
bounds to the last digit. No estimand, seed, margin, tier or rule changed.

### Deviation from the registered resource bound

Registration §6 sets "at most two concurrent readers". The extraction ran with
**two readers for the first 45 minutes, then seven, peaking briefly at eight**, on the
operator's explicit instruction to use the host's available headroom (the host
was measured at 43% idle at the time). This is recorded as a deviation rather
than quietly absorbed. It changes wall-clock only: the work is partitioned by
NORAD range, every object is processed independently and identically, the
partition was verified to sum to exactly 31,499 objects with no overlap, the
analyser refuses duplicate NORADs outright, and the ordering fix above makes the
result provably invariant to how the work was divided. No estimand, seed or
result depends on it.

### Cost

| | |
|---|---:|
| Extraction wall clock, first reader start to last reader exit | **2h 00m** |
| Reader CPU, final resume cycle across 9 shards | 5,076 s |
| Analysis (aggregate + 2,000-draw bootstrap + sensitivities) | 86 s wall |
| **GPU** | **none** |

The detector's GPU execution path was probed through
`/home/sdegan/gpu-broker/gpu-run --estimate-mib 320 --class standard` on 14 real
archive objects, because the operator asked whether the card would finish this
faster. It would not. The GPU path is **bit-for-bit equivalent** — 14/14 objects
identical in flags, event signatures and per-stratum cells — but **0.49x the
speed** of the CPU path (1.8 s CPU against 3.6 s GPU for the same 32,530
intervals), because the per-object arrays are far too small to amortise kernel
launch and host/device transfer. The measurement is therefore pure CPU. The
probe wrote a usage record to its ledger; it is a one-off, not a scheduled
consumer.

## What a reviewer still attacks

Honestly, and in the order a referee would reach for them.

1. **The near-miss at 998.** One of the two unfilled strata is two intervals
   short of the `S_1000` line. A reader is entitled to ask what the result looks
   like at 995, and the answer is that we will not tell them, because choosing
   the tier after seeing which strata fall near it is the exact move the
   registration exists to prevent. The tier was fixed at 1,000 in `7eab5a4`. It
   stays there, and the near-miss is reported as a near-miss.
2. **Clause 2 was never going to pass, and we should have known.** The
   registration wrote down that Phase 3 "is not expected to pass on today's
   exposure" — but it justified that expectation entirely from clause 1's upper
   bound, which is precisely the clause that ended up passing. Nobody computed
   the point-estimate separation in advance. Had they, they would have seen that
   clause 2 was the binding one and that exposure was the wrong lever. The
   experiment was well-run against a partly misdiagnosed target.
3. **9.81x against a 10x bar is uncomfortably close.** A referee will observe
   that a 2% change in either rate flips the verdict, and that 10.0 is a round
   number chosen by this project. Both are true. The defence is only that the
   constant is load-bearing elsewhere, predates this measurement, and was not
   touched — not that 10.0 is principled to two significant figures.
4. **`w_s` is a plug-in estimate treated as fixed.** Payload weights are held at
   observed values, as registered, so the intervals carry passive sampling
   uncertainty only. With 63M payload intervals the weights are precise, but
   "precise" is not "known", and the reported interval is therefore slightly
   narrower than a fully propagated one.
5. **The passive population is not exchangeable with the payload population,
   and covariate matching does not make it so.** Four factors — perigee,
   inclination, eccentricity, cadence — do not capture area-to-mass ratio,
   attitude control, tracking priority, or sensor tasking. A drag-compensated
   constellation payload and a decaying fragment at the same perigee, the same
   inclination and the same cadence are still different objects fitted
   differently. This bounds what any reweighting of this kind can claim.
6. **Solar-cycle confounding is unaddressed.** Passive exposure at low perigee
   varies by an order of magnitude across a cycle, and "whole retained
   histories" pools across cycle phase. The atmosphere-limited gaps are
   therefore not a fixed property of the catalogue; they would look different
   measured at a different epoch, and nothing here conditions on that.
7. **One flag, one stratum, one object.** `300-500 km|30-60|<0.001|0.25-1 d`
   carries 5.27% of payload weight on 5,429 passive intervals holding **3**
   flags, at a rate of 0.5526 per 1,000 — more than three times the pooled floor
   and one of the largest single contributors to `R_rw`. It clears `S_1000`
   honestly, but the reweighted floor still leans hard on a handful of events.
8. **The 1200-2000 km hole is not explained.** The heaviest labelled gap in the
   estimate sits on four passive intervals at an altitude where nothing decays.
   This document establishes that it is not atmospheric; it does not establish
   what it *is*. That cell deserves its own look before anyone builds a gate that
   propagates it as a labelled gap into shipped wording.
9. **M8 stands unaddressed.** The registration ordering is real but externally
   unverifiable. See above.

## Commit references

- `7eab5a4` — the Phase 3 pre-registration, committed alone, ahead of every
  artefact in this document.
- `f317a28`, `8604de2` — Paper B's pre-registration and amendment 1.
- `7626c55` — Paper B results, the measurement this experiment was designed
  against.
- `70e8414` — the three Phase 3 tools and the per-perigee-band M7 measurement.
- `d4e9090` — the object-ordering fix described above.
- `1093a3c` — this document, the receipt and the stratum JSONL.

Ordering in the current history, which is the claim: `7eab5a4` (09:09:25) →
`70e8414` (10:01:43) → `d4e9090` (10:38:36) → `1093a3c` (12:01:38), all
ancestors of HEAD, with real gaps. Every rule this document is judged by was
committed before the tools existed, and every tool before any number did.

### A live demonstration of M8, in this repository, today

The tools were first committed at `8327aa2`, swept into a concurrent session's
commit by a staging collision. That commit **no longer exists in this
repository's history**: another session rewrote the branch later the same day,
and `8327aa2` is now unreachable. Nothing was lost — the tool content is
byte-identical and re-enters at `70e8414` — but a commit hash cited in an
earlier draft of this very document became a dangling reference within hours.

This is exactly M8's point, and it is no longer hypothetical here. The
ordering above is true, and a reader with this repository can verify it; a
referee without it cannot, because the history that proves it is
rewritable and was in fact rewritten. **That is an argument for the external
anchor, not against the ordering.**

## Artefacts

- `docs/phase3-results-20260921.json` — machine receipt: selection, per-shard
  summaries and digests, source SHA-256s, detector flags, counts, timings,
  seed, both clauses, and the M7/M14 blocks.
- `docs/phase3-strata-20260921.jsonl` — 551 rows: every `S_1000` stratum with
  counts, rates and Jeffreys bounds, and every sub-tier stratum with its payload
  weight and atmosphere-limited flag.
