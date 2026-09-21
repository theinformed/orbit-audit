# Paper B results: covariate-matched transfer, and the inclination finding done properly

Measured 2026-09-20 on `bigmem` (pc), against the pre-registration committed at
`f317a28` and amended at `8604de2` — **both ahead of every number below**, in
their own commits, which is what makes them a registration rather than a
description. Read `docs/paperb-preregistration-20260920.md` first; this document
only reports what those rules produced.

Two reviewer objections are answered here, and both were given a real chance to
win:

1. *"The debris false-alarm rate does not transfer to payloads."* Answered by
   estimating the passive floor **inside** covariate strata and carrying it onto
   the payload population's own covariate distribution.
2. *"Identical rates at 60-120 degrees is null-acceptance from p>0.05, and the
   band looks fitted."* Answered by replacing the non-significant difference
   with an exact **equivalence** test at a margin registered in advance, and by
   letting a boundary **fall out** of a fine-binned curve instead of being read
   off a coarse table.

## What was measured, and how

- Read-only archive access through `orbit_campaigns.open_archive_for_reading()`;
  `PRAGMA query_only=1`, WAL, `nice 19`, idle I/O, two concurrent readers, a
  cooperative wall-clock budget with resumable object cursors, and a hard
  deadline enforced inside SQLite's progress handler so a page read that goes
  slow behind a writer cannot run unbounded. No write path was opened, no
  production timer was touched, and the `orbit_release` sweep that was running
  throughout (PIDs 2596909/2596914, started 13:59) was left alone.
- Sample: every archive object with `norad % 5 == 0` and `object_type` in
  `DEBRIS`, `ROCKET BODY`, `PAYLOAD`, across whole retained histories. Uniform
  1-in-5 inclusion probability in both populations, so no design weights are
  needed and the reweighting below is purely a covariate reweighting. Roughly
  four times the Phase-2/2b diagnostic sample.
- Detector: current HEAD, `kappa = 32`, all three optional switches `False`,
  **no source file changed by this task**. Each object's intervals were run
  through `detect_object_events` **twice** — once with the shipped
  high-inclination energy corroboration active, once through the existing
  `_inclination_corroboration=False` keyword — over the same in-memory rows.
- A "flag" is an event whose signature is not in `NON_PROPULSIVE_SIGNATURES`,
  the numerator of the published control. Exposure is usable intervals from
  admitted objects, the published denominator, under the production
  nine-interval admission rule.

### Why Analysis 2 is measured with corroboration off

The shipped corroboration rule suppresses an inclination trip at or above
30 degrees unless an energy channel also survives persistence in the same
interval. An "inclination-only" catch above 30 degrees therefore **cannot
exist** under the shipped detector. The measurement confirms this directly and
the confirmation is left in the tables: inclination-only catches with
corroboration ACTIVE are, in the high-inclination region, structurally zero on
both sides.

Analysis 2 is consequently measured on the pre-corroboration detector — the
state the finding under review was actually made in, and the state whose rate
table the 30-degree boundary was justified from. This was registered as
amendment 1 **before any rate, ratio, test or boundary had been computed**; the
trigger was a structural zero visible in a progress log, not an analysis
outcome. Analysis 1 stays on the shipping detector, because the paper's floor is
a claim about the detector that ships.

## Headline: both analyses came out against the paper's current claims

Neither result is the one that would have been convenient. Both are reported at
the prominence the registration demands.

### Analysis 1 — the floor does NOT transfer, on the registered test

| | Per 1,000 usable intervals |
|---|---:|
| Raw passive floor (sample) | **0.162716** |
| Reweighted to the payload covariate mix | **0.335055** |
| Primary 95%, clustered object bootstrap | **[0.179740, 26.190132]** |
| Reweighted / raw | **2.0591x** |
| Registered target | 1.000 |

**Registered verdict: DOES NOT TRANSFER.** Both clauses of the registered rule
fail, and they fail for different reasons:

- Clause (i) required the reweighted floor *and its primary bootstrap upper
  bound* below the 0.001-per-interval target. The point estimate clears it by a
  factor of three. The **upper bound does not**: it is 26.19 per 1,000, twenty-six
  times the target.
- Clause (ii) required the reweighted floor within 2x the raw floor. It is
  **2.0591x** — a failure by three percent, which is a failure.

The third registered clause **passes**: unsupported payload exposure is
**2.114%**, far inside the 20% ceiling, so the estimate is not disqualified for
coverage. The gaps are small and named.

What actually broke it is visible in the tables and is not a subtlety: **150
supported strata hold fewer than 2,000 passive intervals each, yet carry 18.21%
of the payload weight between them.** The single heaviest is `300-500
km|30-60|<0.001|0.25-1 d` — 5.13% of the payload population resting on **512**
passive intervals carrying one flag. Under a clustered bootstrap, a stratum like
that swings between zero and the rate of whichever single object happens to be
drawn, and a few percent of weight on such a stratum is enough to throw the
composite's upper tail to 26 per 1,000. The registered secondary support tier
makes the same point from the other side: restricted to strata with at least
1,000 passive intervals, the reweighted floor is **0.223524** (1.3737x raw) and
the bootstrap interval tightens to **[0.153825, 1.845847]** — still above the
target at the top, and now 13.358% of payload exposure is in labelled gaps.

So the honest statement the paper can make is **narrower than the one it
currently makes**:

- The raw passive floor is **not** demonstrated to be a payload-applicable
  bound. The claim as written does not survive.
- The *point* estimate of the covariate-matched floor stays three times below
  target, and the coarse 48-cell stratification gives 0.214884 (1.3206x raw),
  so nothing here suggests the floor is secretly enormous.
- What is missing is **passive exposure in the strata where payloads actually
  live** — low-perigee moderate-inclination near-circular orbits above all. The
  remedy is more measurement in those cells, not a different estimator. A denser
  or covariate-targeted passive sample is the experiment this result asks for.

The same calculation on the pre-corroboration detector is reported alongside as
context: raw 0.451623, reweighted 0.551587, **1.2213x** raw. That ratio is
comfortably inside 2x, which says something worth noticing — **the corroboration
rule made the floor more covariate-sensitive, not less.** It suppressed
false alarms hardest in the strata that are best measured, leaving the thin
strata to dominate the reweighted estimate.

### Analysis 2b — equivalence FAILS at the shipped boundary, and the direction is the surprise

| Region (inclination-only rates) | Ratio payload/passive | Exact 90% interval | Equivalent at 1.5? |
|---|---:|---|---|
| **>=30 deg (registered primary)** | **0.6585** | **[0.6316, 0.6865]** | **NO** |
| 30-60 deg | 0.2444 | [0.2089, 0.2860] | NO |
| 60-90 deg excluding SSO | 0.8903 | [0.8465, 0.9363] | **YES** |
| SSO 96-100 deg | 0.5934 | [0.5204, 0.6753] | NO |
| 90-120 deg excluding SSO | 0.7892 | [0.6814, 0.9108] | **YES** |
| >=30 deg excluding SSO | 0.6184 | [0.5916, 0.6463] | NO |
| <30 deg | 7.8690 | [6.5292, 9.5466] | NO (strongly discriminating) |

The registered primary test **fails**. And it fails in a way that is worse for
the shipped rule than a simple "inconclusive" would have been: the superiority
p-value is **6.03e-65**. The two rates at and above 30 degrees are not
indistinguishable at all — the payload inclination-only rate is about
**two-thirds** of the passive rate, and this sample is large enough to say so
decisively.

This is precisely what the reviewer's objection predicted. Phase 2b read
"identical rates" off a coarse table and a non-significant difference. With four
times the exposure, 2-degree bins and an exact test, the rates are **not**
identical; they differ, reliably, and the difference was hidden by binning.

The 30-60 degree band is the sharpest case: the payload rate there is **0.24x**
the passive rate. The shipped abstention message says the channel is suppressed
"where the control measures no discriminating power". In 30-60 degrees that
sentence is **wrong as stated** — there is discriminating power, it simply runs
the *other way*: the channel fires four times more readily on debris than on
payloads. Abstaining there may still be the right operational call, because a
band where most catches are false alarms is a band worth declining. But the
published justification is not what the data say, and the paper must reword it.

### Analysis 2c — the SSO composition objection is ANSWERED, and answered against the artefact hypothesis

Sun-synchronous orbits are **30.50%** of passive exposure at and above 30
degrees but only **21.08%** of payload exposure there, so the composition
objection was well posed: the populations genuinely are mixed differently.

It is not, however, the explanation. Equivalence holds in **60-90 excluding
SSO** and in **90-120 excluding SSO**, and **fails inside the SSO band itself**
(0.5934, payload significantly lower). Removing SSO does not destroy the
equivalence in those bands — if anything it is cleaner without it. The
registered summary verdict reads *"inconclusive: neither split establishes
equivalence"*, and that is reported as the verdict, but it is an artefact of the
registered pooling: `>=30 excluding SSO` lumps the strongly adverse 30-60 band
in with the matched 60-120 bands, and the 30-60 band drags the pooled test
under. The finer splits, all of them registered in section 9, tell the clearer
story and are reported above.

### Analysis 2a — no data-driven boundary exists at the registered margin, and 30 degrees is not one

**Data-driven boundary: none.** The registered rule requires the smallest grid
candidate that passes *and* whose every larger candidate also passes. Equivalence
holds for the pooled regions `[54,180)` through `[74,180)` continuously, then
**fails** at 76, 78, 80, 82, passes again at 84 and 86, and fails at 88 and 90.
Monotone stability is therefore never satisfied and the registered answer is the
one the registration named in advance: no boundary at margin 1.5, rather than a
relaxed margin.

**The shipped 30-degree boundary fails its own candidate test** (interval
[0.6316, 0.6865]). So does every candidate from 2 through 48. The region where
the two populations genuinely match begins somewhere near **54 degrees**, not
30 — and even there it is not stable all the way to the pole.

The registered scan's known dilution property did **not** bite here: the
candidate at 0 degrees passes ([0.7942, 0.8561]) purely because the enormous
matched high-inclination exposure swamps the strongly discriminating 0-2 degree
bin, and the monotone-stability clause correctly refuses it because the
candidate at 2 fails. The property is visible in the scan table, exactly where
the amendment said to look for it.

### The curve, and the shape of it

Passive inclination-only false alarms per 1,000 usable intervals:

- **Below 30 degrees:** low and ragged, 0.00-0.14, on modest exposure.
- **36-42 degrees:** essentially nothing. The 38-40 bin has 27,268 intervals and
  **zero** flags, Jeffreys 95% upper bound **0.092**.
- **42-76 degrees:** a broad plateau between roughly **0.26 and 0.72**, with
  local maxima at 46-48 (0.658), 56-58 (0.643) and 72-74 (0.723).
- **78-96 degrees:** a trough, down to **0.195** at 82-84.
- **96-100 degrees (SSO):** 0.124 and 0.158 on very large exposure.
- **100-116 degrees:** rises again, 0.45 to 0.98.

The payload curve is different in shape as well as level: it is dominated by the
**0-2 degree** bin (1.069 per 1,000, ratio **25.7x** passive), which is
geostationary north-south keeping — the one place the inclination channel is
doing exactly the job it was built for.

### Against Flohrer et al.: the false-alarm peak is not where the out-of-plane error peak is

Flohrer, Krag and Klinkrad report that TLE **out-of-plane** uncertainty has "the
largest uncertainties ... at medium inclinations, centered on ~40 deg". Our
inclination-only false-alarm rate does **not** peak there. At 38-40 degrees its
95% upper bound is **0.092 per 1,000**, which lies below the 95% *lower* bound
of every 2-degree bin from 44 through 76 degrees (44-46: [0.267, 0.711];
56-58: [0.500, 0.816]; 72-74: [0.647, 0.804]). Those intervals do not overlap,
so this is an exclusion rather than an impression.

That is a real disagreement in shape, and it is **not** a refutation of Flohrer
et al., because the two papers measure different things. They measure orbit
uncertainty against an independent orbit determination; we measure how often a
self-history detector at kappa 32 declares a step **relative to that object's own
fitted baseline scatter**. A regime can carry large but well-characterised
out-of-plane error and stay quiet for us, because the baseline absorbs it. The
defensible conclusion is narrow and worth stating exactly: **the inclination
false-alarm floor of this detector does not inherit the ~40-degree structure of
TLE out-of-plane error**, so whatever drives our 42-76 degree plateau is not
simply the error magnitude Flohrer et al. mapped.

One point of agreement is worth more than the disagreement, though: their
conclusion proposes classifying TLE covariance in the
**eccentricity-inclination-perigee-height** domain. That is three of the four
factors Analysis 1 registered, chosen independently fifteen years earlier for
the same reason. The covariate stratification in this paper is not an invention
of convenience; it is the structure ESA's own collision-avoidance tooling uses.

## The tables

Generated by `tools/paperb_analyze.py` and reproduced byte-for-byte in
`docs/paperb-tables-20260920.md`. All rates are per 1,000 usable intervals; the
published target is 1.000 per 1,000. Ratio intervals are exact conditional
(Clopper-Pearson on the conditional binomial), never normal-approximate.
### Sample and exposure

| Measure | Passive | Payload |
|---|---:|---:|
| Objects with tallies | 2,510 | 3,787 |
| Element rows read | 19,582,922 | 14,176,221 |
| Usable intervals (exposure) | 17,877,732 | 12,746,434 |
| Admission exclusions (<9 intervals) | 11 | 5 |
| Propulsive flags, corroboration ON | 2,909 | 36,472 |
| Propulsive flags, corroboration OFF | 8,074 | 38,757 |
| Inclination-channel catches, ON | 735 | 1,889 |
| Inclination-channel catches, OFF | 5,900 | 4,174 |
| Inclination-ONLY catches, ON | 89 | 804 |
| Inclination-ONLY catches, OFF | 5,254 | 3,089 |

### Analysis 1: reweighted passive floor, corroboration ACTIVE (shipping detector)

| Quantity | Per 1,000 usable intervals |
|---|---:|
| Raw passive floor | 0.162716 |
| Raw Jeffreys 95% | [0.156884, 0.168710] |
| **Reweighted to the payload covariate mix** | **0.335055** |
| Primary 95% (clustered object bootstrap) | [0.179740, 26.190132] |
| Secondary 95% (Jeffreys posteriors, conservative) | [0.571995, 1.510412] |
| Reweighted / raw | 2.0591x |
| Target | 1.000 |
| Sensitivity A, gaps filled at the pooled upper bound | 0.331538 (2.0375x raw) |
| Sensitivity B, perigee x inclination only (48 cells) | 0.214884 (1.3206x raw) |

Registered secondary support tier (>=1,000 passive intervals per stratum), reported alongside and with no bearing on the verdict above:

| Quantity | Per 1,000 usable intervals |
|---|---:|
| Reweighted floor, >=1,000-interval strata only | 0.223524 (1.3737x raw) |
| Primary 95% (clustered object bootstrap) | [0.153825, 1.845847] |
| Secondary 95% (Jeffreys posteriors, conservative) | [0.203932, 0.370809] |

Thin support: **150** supported strata hold fewer than 2,000 passive intervals each yet carry **18.21%** of the payload weight between them. Heaviest:

| Stratum | Payload weight | Passive intervals | Passive flags | Passive rate /1,000 |
|---|---:|---:|---:|---:|
| `300-500 km|30-60|<0.001|0.25-1 d` | 5.134% | 512 | 1 | 1.953125 |
| `>2000 km|0-1|<0.001|0.25-1 d` | 3.242% | 1,773 | 3 | 1.692047 |
| `500-800 km|30-60|<0.001|<0.25 d` | 1.952% | 1,206 | 0 | 0.000000 |
| `300-500 km|90-120|<0.001|0.25-1 d` | 1.122% | 582 | 0 | 0.000000 |
| `>2000 km|0-1|<0.001|1-2 d` | 0.818% | 565 | 1 | 1.769912 |
| `300-500 km|30-60|<0.001|<0.25 d` | 0.771% | 133 | 0 | 0.000000 |
| `>2000 km|0-1|<0.001|<0.25 d` | 0.736% | 366 | 1 | 2.732240 |
| `500-800 km|30-60|<0.001|1-2 d` | 0.681% | 1,747 | 0 | 0.000000 |
| `300-500 km|30-60|<0.001|1-2 d` | 0.390% | 38 | 0 | 0.000000 |
| `300-500 km|90-120|<0.001|<0.25 d` | 0.310% | 162 | 0 | 0.000000 |
| `>2000 km|1-5|<0.001|1-2 d` | 0.304% | 617 | 0 | 0.000000 |
| `1200-2000 km|90-120|<0.001|0.25-1 d` | 0.244% | 1,481 | 0 | 0.000000 |

| Support | Strata | Payload exposure in labelled gaps |
|---|---:|---:|
| Supported (>=1 passive interval) | 369 | 2.114% in 82 gap strata |
| Supported (>=1,000 passive intervals) | 256 | 13.358% in 195 gap strata |

**Registered verdict: DOES NOT TRANSFER: the reweighted floor or its upper bound reaches the target**

Largest labelled gaps (payload exposure with no passive support):

| Stratum | Payload intervals | Share of payload exposure |
|---|---:|---:|
| `1200-2000 km|30-60|<0.001|0.25-1 d` | 93,327 | 0.7322% |
| `800-1200 km|30-60|<0.001|0.25-1 d` | 25,588 | 0.2007% |
| `1200-2000 km|30-60|<0.001|1-2 d` | 25,413 | 0.1994% |
| `500-800 km|15-30|0.001-0.01|0.25-1 d` | 19,881 | 0.1560% |
| `500-800 km|15-30|<0.001|0.25-1 d` | 17,588 | 0.1380% |
| `1200-2000 km|30-60|<0.001|<0.25 d` | 14,584 | 0.1144% |
| `800-1200 km|30-60|<0.001|<0.25 d` | 8,968 | 0.0704% |
| `800-1200 km|30-60|0.001-0.01|0.25-1 d` | 7,402 | 0.0581% |
| `300-500 km|15-30|<0.001|0.25-1 d` | 6,225 | 0.0488% |
| `500-800 km|15-30|0.001-0.01|1-2 d` | 5,959 | 0.0468% |
| `500-800 km|5-15|<0.001|0.25-1 d` | 5,477 | 0.0430% |
| `500-800 km|15-30|<0.001|1-2 d` | 4,023 | 0.0316% |

### Analysis 1: reweighted passive floor, corroboration OFF (context only)

| Quantity | Per 1,000 usable intervals |
|---|---:|
| Raw passive floor | 0.451623 |
| Raw Jeffreys 95% | [0.441855, 0.461553] |
| **Reweighted to the payload covariate mix** | **0.551587** |
| Primary 95% (clustered object bootstrap) | [0.388573, 26.376536] |
| Secondary 95% (Jeffreys posteriors, conservative) | [0.786792, 1.720323] |
| Reweighted / raw | 1.2213x |
| Target | 1.000 |
| Sensitivity A, gaps filled at the pooled upper bound | 0.549684 (1.2171x raw) |
| Sensitivity B, perigee x inclination only (48 cells) | 0.488234 (1.0811x raw) |

Registered secondary support tier (>=1,000 passive intervals per stratum), reported alongside and with no bearing on the verdict above:

| Quantity | Per 1,000 usable intervals |
|---|---:|
| Reweighted floor, >=1,000-interval strata only | 0.468137 (1.0366x raw) |
| Primary 95% (clustered object bootstrap) | [0.387130, 2.062374] |
| Secondary 95% (Jeffreys posteriors, conservative) | [0.445541, 0.615423] |

Thin support: **150** supported strata hold fewer than 2,000 passive intervals each yet carry **18.21%** of the payload weight between them. Heaviest:

| Stratum | Payload weight | Passive intervals | Passive flags | Passive rate /1,000 |
|---|---:|---:|---:|---:|
| `300-500 km|30-60|<0.001|0.25-1 d` | 5.134% | 512 | 1 | 1.953125 |
| `>2000 km|0-1|<0.001|0.25-1 d` | 3.242% | 1,773 | 3 | 1.692047 |
| `500-800 km|30-60|<0.001|<0.25 d` | 1.952% | 1,206 | 0 | 0.000000 |
| `300-500 km|90-120|<0.001|0.25-1 d` | 1.122% | 582 | 0 | 0.000000 |
| `>2000 km|0-1|<0.001|1-2 d` | 0.818% | 565 | 1 | 1.769912 |
| `300-500 km|30-60|<0.001|<0.25 d` | 0.771% | 133 | 0 | 0.000000 |
| `>2000 km|0-1|<0.001|<0.25 d` | 0.736% | 366 | 1 | 2.732240 |
| `500-800 km|30-60|<0.001|1-2 d` | 0.681% | 1,747 | 0 | 0.000000 |
| `300-500 km|30-60|<0.001|1-2 d` | 0.390% | 38 | 0 | 0.000000 |
| `300-500 km|90-120|<0.001|<0.25 d` | 0.310% | 162 | 0 | 0.000000 |
| `>2000 km|1-5|<0.001|1-2 d` | 0.304% | 617 | 0 | 0.000000 |
| `1200-2000 km|90-120|<0.001|0.25-1 d` | 0.244% | 1,481 | 0 | 0.000000 |

| Support | Strata | Payload exposure in labelled gaps |
|---|---:|---:|
| Supported (>=1 passive interval) | 369 | 2.114% in 82 gap strata |
| Supported (>=1,000 passive intervals) | 256 | 13.358% in 195 gap strata |

**Registered verdict: DOES NOT TRANSFER: the reweighted floor or its upper bound reaches the target**

Largest labelled gaps (payload exposure with no passive support):

| Stratum | Payload intervals | Share of payload exposure |
|---|---:|---:|
| `1200-2000 km|30-60|<0.001|0.25-1 d` | 93,327 | 0.7322% |
| `800-1200 km|30-60|<0.001|0.25-1 d` | 25,588 | 0.2007% |
| `1200-2000 km|30-60|<0.001|1-2 d` | 25,413 | 0.1994% |
| `500-800 km|15-30|0.001-0.01|0.25-1 d` | 19,881 | 0.1560% |
| `500-800 km|15-30|<0.001|0.25-1 d` | 17,588 | 0.1380% |
| `1200-2000 km|30-60|<0.001|<0.25 d` | 14,584 | 0.1144% |
| `800-1200 km|30-60|<0.001|<0.25 d` | 8,968 | 0.0704% |
| `800-1200 km|30-60|0.001-0.01|0.25-1 d` | 7,402 | 0.0581% |
| `300-500 km|15-30|<0.001|0.25-1 d` | 6,225 | 0.0488% |
| `500-800 km|15-30|0.001-0.01|1-2 d` | 5,959 | 0.0468% |
| `500-800 km|5-15|<0.001|0.25-1 d` | 5,477 | 0.0430% |
| `500-800 km|15-30|<0.001|1-2 d` | 4,023 | 0.0316% |

### Analysis 1: the twenty heaviest payload strata

| Stratum | Payload weight | Passive intervals | Passive flags | Passive rate /1,000 | Passive Jeffreys 95% | Payload rate /1,000 |
|---|---:|---:|---:|---:|---|---:|
| `500-800 km|30-60|<0.001|0.25-1 d` | 10.787% | 10,295 | 0 | 0.000000 | [0.000000, 0.243961] | 2.339046 |
| `1200-2000 km|60-90|0.001-0.01|0.25-1 d` | 7.577% | 285,750 | 47 | 0.164479 | [0.122356, 0.216718] | 0.112130 |
| `800-1200 km|60-90|0.001-0.01|0.25-1 d` | 5.914% | 1,552,103 | 248 | 0.159783 | [0.140817, 0.180613] | 0.697941 |
| `500-800 km|90-120|0.001-0.01|0.25-1 d` | 5.769% | 854,430 | 64 | 0.074904 | [0.058199, 0.094993] | 1.272599 |
| `300-500 km|30-60|<0.001|0.25-1 d` | 5.134% | 512 | 1 | 1.953125 | [0.210818, 9.092179] | 15.268999 |
| `500-800 km|90-120|<0.001|0.25-1 d` | 4.135% | 86,825 | 7 | 0.080622 | [0.036063, 0.158291] | 3.438904 |
| `1200-2000 km|60-90|<0.001|0.25-1 d` | 3.735% | 27,550 | 1 | 0.036298 | [0.003916, 0.169650] | 1.534117 |
| `>2000 km|0-1|<0.001|0.25-1 d` | 3.242% | 1,773 | 3 | 1.692047 | [0.476779, 4.508719] | 3.693723 |
| `500-800 km|60-90|0.001-0.01|0.25-1 d` | 2.889% | 1,059,267 | 74 | 0.069860 | [0.055274, 0.087176] | 1.187579 |
| `500-800 km|60-90|<0.001|0.25-1 d` | 2.354% | 124,921 | 10 | 0.080051 | [0.041158, 0.142001] | 4.498384 |
| `1200-2000 km|60-90|0.001-0.01|1-2 d` | 2.342% | 107,575 | 10 | 0.092958 | [0.047795, 0.164897] | 0.061589 |
| `500-800 km|30-60|<0.001|<0.25 d` | 1.952% | 1,206 | 0 | 0.000000 | [0.000000, 2.080273] | 0.989705 |
| `>2000 km|5-15|<0.001|0.25-1 d` | 1.911% | 24,913 | 1 | 0.040140 | [0.004331, 0.187605] | 0.809272 |
| `800-1200 km|60-90|0.001-0.01|1-2 d` | 1.823% | 618,311 | 76 | 0.122915 | [0.097562, 0.152945] | 0.325306 |
| `800-1200 km|90-120|0.001-0.01|0.25-1 d` | 1.530% | 1,311,451 | 275 | 0.209691 | [0.185999, 0.235590] | 0.476772 |
| `800-1200 km|60-90|<0.001|0.25-1 d` | 1.442% | 127,580 | 20 | 0.156764 | [0.098821, 0.237333] | 7.265713 |
| `500-800 km|90-120|0.001-0.01|<0.25 d` | 1.342% | 79,748 | 25 | 0.313487 | [0.207926, 0.455250] | 1.277688 |
| `300-500 km|90-120|<0.001|0.25-1 d` | 1.122% | 582 | 0 | 0.000000 | [0.000000, 4.304906] | 9.586604 |
| `800-1200 km|90-120|<0.001|0.25-1 d` | 1.112% | 122,271 | 18 | 0.147214 | [0.090398, 0.227632] | 1.606686 |
| `500-800 km|90-120|<0.001|<0.25 d` | 1.085% | 9,803 | 4 | 0.408038 | [0.137748, 0.969955] | 3.551677 |

### Analysis 2a: rate against inclination, 2-degree bins, pre-corroboration detector

Inclination-ONLY catches per 1,000 usable intervals, both populations, with Jeffreys 95% bounds and the exact conditional payload/passive ratio. Bins with no exposure are omitted; bins with no flags anywhere carry no ratio.

| Inclination | Passive intervals | Passive i-only | Rate /1,000 | Jeffreys 95% | Payload intervals | Payload i-only | Rate /1,000 | Jeffreys 95% | Ratio (exact 95%) |
|---|---:|---:|---:|---|---:|---:|---:|---|---|
| 0-2 | 96,093 | 4 | 0.041626 | [0.014051, 0.098978] | 714,382 | 764 | 1.069456 | [0.995668, 1.147287] | 25.692 [9.993, 94.535] |
| 2-4 | 91,836 | 5 | 0.054445 | [0.020775, 0.119339] | 139,754 | 11 | 0.078710 | [0.041819, 0.136220] | 1.446 [0.463, 5.308] |
| 4-6 | 132,966 | 1 | 0.007521 | [0.000811, 0.035153] | 116,118 | 5 | 0.043060 | [0.016431, 0.094384] | 5.725 [0.641, 270.801] |
| 6-8 | 208,435 | 14 | 0.067167 | [0.038495, 0.109677] | 125,778 | 6 | 0.047703 | [0.019911, 0.098328] | 0.710 [0.224, 1.967] |
| 8-10 | 60,789 | 0 | 0.000000 | [0.000000, 0.041321] | 112,286 | 0 | 0.000000 | [0.000000, 0.022371] | not a ratio (no flags in either population) |
| 10-12 | 75,129 | 0 | 0.000000 | [0.000000, 0.033434] | 131,193 | 2 | 0.015245 | [0.003168, 0.048906] | one-sided [0.108, inf] |
| 12-14 | 113,765 | 3 | 0.026370 | [0.007427, 0.070375] | 146,432 | 2 | 0.013658 | [0.002838, 0.043817] | 0.518 [0.043, 4.521] |
| 14-16 | 94,796 | 0 | 0.000000 | [0.000000, 0.026498] | 181,677 | 1 | 0.005504 | [0.000594, 0.025728] | one-sided [0.013, inf] |
| 16-18 | 66,735 | 6 | 0.089908 | [0.037528, 0.185318] | 10,672 | 0 | 0.000000 | [0.000000, 0.235344] | 0.000 [0.000, 5.311] |
| 18-20 | 86,976 | 2 | 0.022995 | [0.004778, 0.073768] | 11,887 | 1 | 0.084126 | [0.009077, 0.393151] | 3.658 [0.062, 70.275] |
| 20-22 | 75,417 | 0 | 0.000000 | [0.000000, 0.033307] | 10,414 | 0 | 0.000000 | [0.000000, 0.241173] | not a ratio (no flags in either population) |
| 22-24 | 68,767 | 6 | 0.087251 | [0.036419, 0.179842] | 4,171 | 0 | 0.000000 | [0.000000, 0.602023] | 0.000 [0.000, 14.003] |
| 24-26 | 52,371 | 4 | 0.076378 | [0.025782, 0.181605] | 19,107 | 0 | 0.000000 | [0.000000, 0.131457] | 0.000 [0.000, 4.152] |
| 26-28 | 155,060 | 20 | 0.128982 | [0.081307, 0.195274] | 1,226 | 1 | 0.815661 | [0.088022, 3.806079] | 6.324 [0.153, 39.538] |
| 28-30 | 166,131 | 24 | 0.144464 | [0.094972, 0.211339] | 48,888 | 11 | 0.225004 | [0.119550, 0.389383] | 1.558 [0.689, 3.303] |
| 30-32 | 66,690 | 7 | 0.104963 | [0.046951, 0.206080] | 24,847 | 19 | 0.764680 | [0.476064, 1.169310] | 7.285 [2.933, 20.508] |
| 32-34 | 62,033 | 6 | 0.096723 | [0.040373, 0.199364] | 61,259 | 23 | 0.375455 | [0.244519, 0.553505] | 3.882 [1.536, 11.655] |
| 34-36 | 38,742 | 2 | 0.051624 | [0.010728, 0.165604] | 105,914 | 12 | 0.113299 | [0.061937, 0.191876] | 2.195 [0.489, 20.190] |
| 36-38 | 3,791 | 0 | 0.000000 | [0.000000, 0.662344] | 20,233 | 8 | 0.395394 | [0.186944, 0.745943] | one-sided [0.320, inf] |
| 38-40 | 27,268 | 0 | 0.000000 | [0.000000, 0.092115] | 20,556 | 2 | 0.097295 | [0.020219, 0.312098] | one-sided [0.249, inf] |
| 40-42 | 1,311 | 0 | 0.000000 | [0.000000, 1.913852] | 4,398 | 0 | 0.000000 | [0.000000, 0.570960] | not a ratio (no flags in either population) |
| 42-44 | 18,463 | 8 | 0.433299 | [0.204868, 0.817440] | 716,847 | 7 | 0.009765 | [0.004368, 0.019173] | 0.023 [0.007, 0.071] |
| 44-46 | 35,678 | 16 | 0.448456 | [0.266947, 0.710775] | 139,453 | 36 | 0.258151 | [0.183813, 0.353206] | 0.576 [0.311, 1.111] |
| 46-48 | 41,058 | 27 | 0.657606 | [0.443297, 0.942191] | 21,923 | 0 | 0.000000 | [0.000000, 0.114572] | 0.000 [0.000, 0.274] |
| 48-50 | 125,929 | 33 | 0.262052 | [0.183686, 0.363358] | 49,081 | 1 | 0.020374 | [0.002198, 0.095230] | 0.078 [0.002, 0.464] |
| 50-52 | 101,934 | 34 | 0.333549 | [0.235085, 0.460348] | 163,924 | 53 | 0.323321 | [0.244839, 0.419432] | 0.969 [0.619, 1.538] |
| 52-54 | 26,474 | 12 | 0.453275 | [0.247808, 0.767540] | 1,614,027 | 62 | 0.038413 | [0.029723, 0.048896] | 0.085 [0.045, 0.173] |
| 54-56 | 37,165 | 13 | 0.349791 | [0.196077, 0.581047] | 134,064 | 1 | 0.007459 | [0.000805, 0.034865] | 0.021 [0.001, 0.142] |
| 56-58 | 99,501 | 64 | 0.643210 | [0.499794, 0.815654] | 67,871 | 16 | 0.235741 | [0.140321, 0.373660] | 0.367 [0.198, 0.641] |
| 58-60 | 32,783 | 2 | 0.061007 | [0.012678, 0.195704] | 6,883 | 0 | 0.000000 | [0.000000, 0.364869] | 0.000 [0.000, 25.360] |
| 60-62 | 22,958 | 5 | 0.217789 | [0.083107, 0.477327] | 11,794 | 0 | 0.000000 | [0.000000, 0.212958] | 0.000 [0.000, 2.124] |
| 62-64 | 379,847 | 115 | 0.302753 | [0.251156, 0.361962] | 256,429 | 22 | 0.085794 | [0.055311, 0.127538] | 0.283 [0.171, 0.450] |
| 64-66 | 1,237,983 | 755 | 0.609863 | [0.567533, 0.654528] | 419,143 | 103 | 0.245740 | [0.201663, 0.296715] | 0.403 [0.325, 0.496] |
| 66-68 | 775,094 | 338 | 0.436076 | [0.391440, 0.484443] | 166,750 | 25 | 0.149925 | [0.099438, 0.217731] | 0.344 [0.219, 0.516] |
| 68-70 | 189,805 | 106 | 0.558468 | [0.459634, 0.672527] | 184,937 | 31 | 0.167625 | [0.116124, 0.234746] | 0.300 [0.194, 0.452] |
| 70-72 | 882,213 | 401 | 0.454539 | [0.411681, 0.500674] | 162,118 | 34 | 0.209724 | [0.147811, 0.289458] | 0.461 [0.315, 0.656] |
| 72-74 | 451,133 | 326 | 0.722625 | [0.647375, 0.804281] | 251,048 | 179 | 0.713011 | [0.614257, 0.823275] | 0.987 [0.818, 1.188] |
| 74-76 | 1,231,381 | 421 | 0.341893 | [0.310401, 0.375732] | 1,330,746 | 852 | 0.640242 | [0.598344, 0.684313] | 1.873 [1.664, 2.110] |
| 76-78 | 0 | 0 | 0.000000 | [0.000000, 1000.000000] | 132 | 0 | 0.000000 | [0.000000, 18.814562] | not a ratio (no exposure) |
| 78-80 | 18,641 | 5 | 0.268226 | [0.102355, 0.587851] | 18,613 | 3 | 0.161178 | [0.045397, 0.430086] | 0.601 [0.093, 3.089] |
| 80-82 | 408,166 | 93 | 0.227848 | [0.185008, 0.277774] | 155,914 | 28 | 0.179586 | [0.121951, 0.255747] | 0.788 [0.497, 1.214] |
| 82-84 | 1,984,230 | 386 | 0.194534 | [0.175850, 0.214676] | 1,368,641 | 123 | 0.089870 | [0.075024, 0.106829] | 0.462 [0.374, 0.567] |
| 84-86 | 23,308 | 2 | 0.085807 | [0.017831, 0.275252] | 10,583 | 3 | 0.283473 | [0.079845, 0.756336] | 3.304 [0.378, 39.553] |
| 86-88 | 248,551 | 35 | 0.140816 | [0.099764, 0.193494] | 580,567 | 193 | 0.332434 | [0.287992, 0.381856] | 2.361 [1.640, 3.488] |
| 88-90 | 389,461 | 66 | 0.169465 | [0.132196, 0.214158] | 169,373 | 82 | 0.484139 | [0.387701, 0.597638] | 2.857 [2.041, 4.012] |
| 90-92 | 379,802 | 118 | 0.310688 | [0.258369, 0.370620] | 138,585 | 44 | 0.317495 | [0.233777, 0.422061] | 1.022 [0.706, 1.456] |
| 92-94 | 9,220 | 0 | 0.000000 | [0.000000, 0.272401] | 19,800 | 5 | 0.252525 | [0.096364, 0.553446] | one-sided [0.427, inf] |
| 94-96 | 14,995 | 4 | 0.266756 | [0.090049, 0.634177] | 67 | 0 | 0.000000 | [0.000000, 36.662656] | 0.000 [0.000, 339.036] |
| 96-98 | 378,798 | 47 | 0.124077 | [0.092300, 0.163485] | 1,140,016 | 60 | 0.052631 | [0.040546, 0.067252] | 0.424 [0.285, 0.635] |
| 98-100 | 4,602,411 | 726 | 0.157743 | [0.146582, 0.169534] | 1,172,883 | 153 | 0.130448 | [0.110990, 0.152371] | 0.827 [0.690, 0.986] |
| 100-102 | 1,110,959 | 504 | 0.453662 | [0.415353, 0.494574] | 159,472 | 48 | 0.300993 | [0.224629, 0.395478] | 0.663 [0.483, 0.893] |
| 102-104 | 785,700 | 422 | 0.537101 | [0.487690, 0.590191] | 37,536 | 25 | 0.666027 | [0.441780, 0.967132] | 1.240 [0.793, 1.856] |
| 104-106 | 858 | 0 | 0.000000 | [0.000000, 2.922541] | 25,951 | 13 | 0.500944 | [0.280815, 0.832086] | one-sided [0.101, inf] |
| 106-108 | 25,567 | 24 | 0.938710 | [0.617196, 1.372990] | 15 | 0 | 0.000000 | [0.000000, 151.816662] | 0.000 [0.000, 283.188] |
| 108-110 | 5,113 | 5 | 0.977899 | [0.373236, 2.142207] | 34,645 | 19 | 0.548420 | [0.341414, 0.838667] | 0.561 [0.203, 1.922] |
| 110-112 | 0 | 0 | 0.000000 | [0.000000, 1000.000000] | 24 | 0 | 0.000000 | [0.000000, 98.387604] | not a ratio (no exposure) |
| 112-114 | 0 | 0 | 0.000000 | [0.000000, 1000.000000] | 19 | 0 | 0.000000 | [0.000000, 122.309404] | not a ratio (no exposure) |
| 114-116 | 37,276 | 34 | 0.912115 | [0.642911, 1.258713] | 22 | 0 | 0.000000 | [0.000000, 106.739718] | 0.000 [0.000, 194.176] |
| 116-118 | 0 | 0 | 0.000000 | [0.000000, 1000.000000] | 23 | 0 | 0.000000 | [0.000000, 102.393828] | not a ratio (no exposure) |
| 118-120 | 0 | 0 | 0.000000 | [0.000000, 1000.000000] | 19 | 0 | 0.000000 | [0.000000, 122.309404] | not a ratio (no exposure) |
| 120-122 | 20,092 | 3 | 0.149313 | [0.042055, 0.398431] | 21 | 0 | 0.000000 | [0.000000, 111.470316] | 0.000 [0.000, 2315.318] |
| 122-124 | 0 | 0 | 0.000000 | [0.000000, 1000.000000] | 20 | 0 | 0.000000 | [0.000000, 116.638983] | not a ratio (no exposure) |
| 124-126 | 0 | 0 | 0.000000 | [0.000000, 1000.000000] | 22 | 0 | 0.000000 | [0.000000, 106.739718] | not a ratio (no exposure) |
| 126-128 | 0 | 0 | 0.000000 | [0.000000, 1000.000000] | 22 | 0 | 0.000000 | [0.000000, 106.739718] | not a ratio (no exposure) |
| 128-130 | 0 | 0 | 0.000000 | [0.000000, 1000.000000] | 22 | 0 | 0.000000 | [0.000000, 106.739718] | not a ratio (no exposure) |
| 130-132 | 0 | 0 | 0.000000 | [0.000000, 1000.000000] | 714 | 0 | 0.000000 | [0.000000, 3.510719] | not a ratio (no exposure) |
| 132-134 | 0 | 0 | 0.000000 | [0.000000, 1000.000000] | 449 | 0 | 0.000000 | [0.000000, 5.575810] | not a ratio (no exposure) |
| 134-136 | 0 | 0 | 0.000000 | [0.000000, 1000.000000] | 286 | 0 | 0.000000 | [0.000000, 8.736947] | not a ratio (no exposure) |
| 136-138 | 0 | 0 | 0.000000 | [0.000000, 1000.000000] | 213 | 0 | 0.000000 | [0.000000, 11.710208] | not a ratio (no exposure) |
| 138-140 | 0 | 0 | 0.000000 | [0.000000, 1000.000000] | 3,240 | 0 | 0.000000 | [0.000000, 0.774931] | not a ratio (no exposure) |
| 140-142 | 77 | 0 | 0.000000 | [0.000000, 31.993626] | 177 | 0 | 0.000000 | [0.000000, 14.071769] | not a ratio (no flags in either population) |
| 142-144 | 7 | 0 | 0.000000 | [0.000000, 292.436174] | 34 | 0 | 0.000000 | [0.000000, 70.711631] | not a ratio (no flags in either population) |
| 144-146 | 0 | 0 | 0.000000 | [0.000000, 1000.000000] | 49 | 0 | 0.000000 | [0.000000, 49.723385] | not a ratio (no exposure) |
| 146-148 | 0 | 0 | 0.000000 | [0.000000, 1000.000000] | 30 | 0 | 0.000000 | [0.000000, 79.678174] | not a ratio (no exposure) |
| 148-150 | 0 | 0 | 0.000000 | [0.000000, 1000.000000] | 4 | 0 | 0.000000 | [0.000000, 444.762618] | not a ratio (no exposure) |
| 178-180 | 0 | 0 | 0.000000 | [0.000000, 1000.000000] | 1 | 0 | 0.000000 | [0.000000, 853.253684] | not a ratio (no exposure) |

### Analysis 2a zoom: 0.2-degree bins below 2 degrees (the GEO population)

| Inclination | Passive intervals | Passive i-only /1,000 | Payload intervals | Payload i-only /1,000 | Ratio (exact 95%) |
|---|---:|---:|---:|---:|---|
| 0.0-0.2 | 18,258 | 0.164312 | 572,560 | 1.257510 | 7.653 [2.608, 37.198] |
| 0.2-0.4 | 13,557 | 0.000000 | 19,203 | 0.416602 | one-sided [1.205, inf] |
| 0.4-0.6 | 17,163 | 0.058265 | 14,922 | 0.335076 | 5.751 [0.644, 272.004] |
| 0.6-0.8 | 10,231 | 0.000000 | 15,102 | 0.198649 | one-sided [0.280, inf] |
| 0.8-1.0 | 8,379 | 0.000000 | 17,876 | 0.167823 | one-sided [0.194, inf] |
| 1.0-1.2 | 6,860 | 0.000000 | 15,476 | 0.775394 | one-sided [1.232, inf] |
| 1.2-1.4 | 9,792 | 0.000000 | 15,373 | 0.260196 | one-sided [0.420, inf] |
| 1.4-1.6 | 5,142 | 0.000000 | 14,764 | 0.135465 | one-sided [0.065, inf] |
| 1.6-1.8 | 3,517 | 0.000000 | 13,637 | 0.293320 | one-sided [0.170, inf] |
| 1.8-2.0 | 3,194 | 0.000000 | 15,469 | 0.193936 | one-sided [0.085, inf] |

### Analysis 2b and 2c: exact conditional TOST by region

Registered margin: rate ratio inside [1/1.5, 1.5], alpha 0.05, two one-sided exact tests.

| Region | Passive i-only / exposure | Payload i-only / exposure | Ratio | Exact 90% ratio interval | TOST p | Superiority p (no decision weight) | Equivalent? |
|---|---:|---:|---:|---|---:|---:|---|
| >=30 deg (registered primary) | 5,165 / 16,332,466 | 2,285 / 10,972,449 | 0.6585 | [0.6316, 0.6865] | 0.692 | 6.03e-65 | NO |
| 30-60 deg | 224 / 718,820 | 240 / 3,151,280 | 0.2444 | [0.2089, 0.2860] | 1 | 2.32e-47 | NO |
| 60-90 deg excluding SSO | 3,054 / 8,242,771 | 1,678 / 5,086,788 | 0.8903 | [0.8465, 0.9363] | 3.94e-21 | 0.00013 | YES |
| SSO 96-100 deg | 773 / 4,981,209 | 213 / 2,312,899 | 0.5934 | [0.5204, 0.6753] | 0.94 | 2.21e-12 | NO |
| 90-120 deg excluding SSO | 1,111 / 2,369,490 | 154 / 416,178 | 0.7892 | [0.6814, 0.9108] | 0.0295 | 0.00535 | YES |
| 120-180 deg | 3 / 20,176 | 0 / 5,304 | 0.0000 | [0.0000, 6.5215] | 1 | 0.993 | NO |
| >=30 deg excluding SSO | 4,392 / 11,351,257 | 2,072 / 8,659,550 | 0.6184 | [0.5916, 0.6463] | 0.998 | 3.65e-76 | NO |
| <30 deg (below the shipped boundary) | 89 / 1,545,266 | 804 / 1,773,985 | 7.8690 | [6.5292, 9.5466] | 1 | 0 | NO |

**SSO composition verdict: inconclusive: neither split establishes equivalence at the registered margin**

SSO (96-100 deg) is 30.50% of passive exposure at >=30 deg and 21.08% of payload exposure there.

### Analysis 2a: the registered boundary scan

Rule: smallest grid boundary whose pooled region passes exact TOST at the registered margin, and every larger grid boundary also passes. **Data-driven boundary: none.** Shipped boundary: 30 deg.

| Candidate | Passive i-only / exposure | Payload i-only / exposure | Exact 90% ratio interval | Equivalent? |
|---|---:|---:|---|---|
| 0 | 5,254 / 17,877,732 | 3,089 / 12,746,434 | [0.7942, 0.8561] | YES |
| 2 | 5,250 / 17,781,639 | 2,325 / 12,032,052 | [0.6280, 0.6820] | NO |
| 4 | 5,245 / 17,689,803 | 2,314 / 11,892,298 | [0.6296, 0.6839] | NO |
| 6 | 5,244 / 17,556,837 | 2,309 / 11,776,180 | [0.6298, 0.6841] | NO |
| 8 | 5,230 / 17,348,402 | 2,303 / 11,650,402 | [0.6290, 0.6834] | NO |
| 10 | 5,230 / 17,287,613 | 2,303 / 11,538,116 | [0.6329, 0.6876] | NO |
| 12 | 5,230 / 17,212,484 | 2,301 / 11,406,923 | [0.6369, 0.6919] | NO |
| 14 | 5,227 / 17,098,719 | 2,299 / 11,260,491 | [0.6407, 0.6961] | NO |
| 16 | 5,227 / 17,003,923 | 2,298 / 11,078,814 | [0.6473, 0.7033] | NO |
| 18 | 5,221 / 16,937,188 | 2,298 / 11,068,142 | [0.6461, 0.7020] | NO |
| 20 | 5,219 / 16,850,212 | 2,297 / 11,056,255 | [0.6435, 0.6991] | NO |
| 22 | 5,219 / 16,774,795 | 2,297 / 11,045,841 | [0.6412, 0.6967] | NO |
| 24 | 5,213 / 16,706,028 | 2,297 / 11,041,670 | [0.6395, 0.6949] | NO |
| 26 | 5,209 / 16,653,657 | 2,297 / 11,022,563 | [0.6391, 0.6944] | NO |
| 28 | 5,189 / 16,498,597 | 2,296 / 11,021,337 | [0.6354, 0.6904] | NO |
| 30 | 5,165 / 16,332,466 | 2,285 / 10,972,449 | [0.6316, 0.6865] | NO |
| 32 | 5,158 / 16,265,776 | 2,266 / 10,947,602 | [0.6260, 0.6805] | NO |
| 34 | 5,152 / 16,203,743 | 2,243 / 10,886,343 | [0.6214, 0.6757] | NO |
| 36 | 5,150 / 16,165,001 | 2,231 / 10,780,429 | [0.6228, 0.6774] | NO |
| 38 | 5,150 / 16,161,210 | 2,223 / 10,760,196 | [0.6216, 0.6761] | NO |
| 40 | 5,150 / 16,133,942 | 2,221 / 10,739,640 | [0.6211, 0.6757] | NO |
| 42 | 5,150 / 16,132,631 | 2,221 / 10,735,242 | [0.6213, 0.6759] | NO |
| 44 | 5,142 / 16,114,168 | 2,214 / 10,018,395 | [0.6639, 0.7223] | NO |
| 46 | 5,126 / 16,078,490 | 2,178 / 9,878,942 | [0.6628, 0.7214] | NO |
| 48 | 5,099 / 16,037,432 | 2,178 / 9,857,019 | [0.6660, 0.7250] | NO |
| 50 | 5,066 / 15,911,503 | 2,177 / 9,807,938 | [0.6681, 0.7273] | YES |
| 52 | 5,032 / 15,809,569 | 2,124 / 9,644,014 | [0.6628, 0.7222] | NO |
| 54 | 5,020 / 15,783,095 | 2,062 / 8,029,987 | [0.7730, 0.8431] | YES |
| 56 | 5,007 / 15,745,930 | 2,061 / 7,895,923 | [0.7859, 0.8572] | YES |
| 58 | 4,943 / 15,646,429 | 2,045 / 7,828,052 | [0.7916, 0.8637] | YES |
| 60 | 4,941 / 15,613,646 | 2,045 / 7,821,169 | [0.7909, 0.8630] | YES |
| 62 | 4,936 / 15,590,688 | 2,045 / 7,809,375 | [0.7918, 0.8639] | YES |
| 64 | 4,821 / 15,210,841 | 2,023 / 7,552,946 | [0.8087, 0.8829] | YES |
| 66 | 4,066 / 13,972,858 | 1,920 / 7,133,803 | [0.8833, 0.9683] | YES |
| 68 | 3,728 / 13,197,764 | 1,895 / 6,967,053 | [0.9188, 1.0090] | YES |
| 70 | 3,622 / 13,007,959 | 1,864 / 6,782,116 | [0.9414, 1.0348] | YES |
| 72 | 3,221 / 12,125,746 | 1,830 / 6,619,998 | [0.9913, 1.0924] | YES |
| 74 | 2,895 / 11,674,613 | 1,651 / 6,368,950 | [0.9931, 1.1002] | YES |
| 76 | 2,474 / 10,443,232 | 799 / 5,038,204 | [0.6254, 0.7162] | NO |
| 78 | 2,474 / 10,443,232 | 799 / 5,038,072 | [0.6254, 0.7162] | NO |
| 80 | 2,469 / 10,424,591 | 796 / 5,019,459 | [0.6255, 0.7164] | NO |
| 82 | 2,376 / 10,016,425 | 768 / 4,863,545 | [0.6211, 0.7132] | NO |
| 84 | 1,990 / 8,032,195 | 645 / 3,494,904 | [0.6905, 0.8031] | YES |
| 86 | 1,988 / 8,008,887 | 642 / 3,484,321 | [0.6880, 0.8004] | YES |
| 88 | 1,953 / 7,760,336 | 449 / 2,903,754 | [0.5627, 0.6702] | NO |
| 90 | 1,887 / 7,370,875 | 367 / 2,734,381 | [0.4762, 0.5764] | NO |

### Post-hoc, NOT pre-registered: bin-wise equivalence

No decision weight. Present only so a diluted pooled boundary can be recognised as dilution rather than read as a physical edge.

| Inclination | Passive i-only | Payload i-only | Equivalent at the registered margin? |
|---|---:|---:|---|
| 0-2 | 4 | 764 | inconclusive |
| 2-4 | 5 | 11 | inconclusive |
| 4-6 | 1 | 5 | inconclusive |
| 6-8 | 14 | 6 | inconclusive |
| 8-10 | 0 | 0 | no flags |
| 10-12 | 0 | 2 | inconclusive |
| 12-14 | 3 | 2 | inconclusive |
| 14-16 | 0 | 1 | inconclusive |
| 16-18 | 6 | 0 | inconclusive |
| 18-20 | 2 | 1 | inconclusive |
| 20-22 | 0 | 0 | no flags |
| 22-24 | 6 | 0 | inconclusive |
| 24-26 | 4 | 0 | inconclusive |
| 26-28 | 20 | 1 | inconclusive |
| 28-30 | 24 | 11 | inconclusive |
| 30-32 | 7 | 19 | inconclusive |
| 32-34 | 6 | 23 | inconclusive |
| 34-36 | 2 | 12 | inconclusive |
| 36-38 | 0 | 8 | inconclusive |
| 38-40 | 0 | 2 | inconclusive |
| 40-42 | 0 | 0 | no flags |
| 42-44 | 8 | 7 | inconclusive |
| 44-46 | 16 | 36 | inconclusive |
| 46-48 | 27 | 0 | inconclusive |
| 48-50 | 33 | 1 | inconclusive |
| 50-52 | 34 | 53 | inconclusive |
| 52-54 | 12 | 62 | inconclusive |
| 54-56 | 13 | 1 | inconclusive |
| 56-58 | 64 | 16 | inconclusive |
| 58-60 | 2 | 0 | inconclusive |
| 60-62 | 5 | 0 | inconclusive |
| 62-64 | 115 | 22 | inconclusive |
| 64-66 | 755 | 103 | inconclusive |
| 66-68 | 338 | 25 | inconclusive |
| 68-70 | 106 | 31 | inconclusive |
| 70-72 | 401 | 34 | inconclusive |
| 72-74 | 326 | 179 | YES |
| 74-76 | 421 | 852 | inconclusive |
| 76-78 | 0 | 0 | no flags |
| 78-80 | 5 | 3 | inconclusive |
| 80-82 | 93 | 28 | inconclusive |
| 82-84 | 386 | 123 | inconclusive |
| 84-86 | 2 | 3 | inconclusive |
| 86-88 | 35 | 193 | inconclusive |
| 88-90 | 66 | 82 | inconclusive |
| 90-92 | 118 | 44 | YES |
| 92-94 | 0 | 5 | inconclusive |
| 94-96 | 4 | 0 | inconclusive |
| 96-98 | 47 | 60 | inconclusive |
| 98-100 | 726 | 153 | YES |
| 100-102 | 504 | 48 | inconclusive |
| 102-104 | 422 | 25 | inconclusive |
| 104-106 | 0 | 13 | inconclusive |
| 106-108 | 24 | 0 | inconclusive |
| 108-110 | 5 | 19 | inconclusive |
| 110-112 | 0 | 0 | no flags |
| 112-114 | 0 | 0 | no flags |
| 114-116 | 34 | 0 | inconclusive |
| 116-118 | 0 | 0 | no flags |
| 118-120 | 0 | 0 | no flags |
| 120-122 | 3 | 0 | inconclusive |
| 122-124 | 0 | 0 | no flags |
| 124-126 | 0 | 0 | no flags |
| 126-128 | 0 | 0 | no flags |
| 128-130 | 0 | 0 | no flags |
| 130-132 | 0 | 0 | no flags |
| 132-134 | 0 | 0 | no flags |
| 134-136 | 0 | 0 | no flags |
| 136-138 | 0 | 0 | no flags |
| 138-140 | 0 | 0 | no flags |
| 140-142 | 0 | 0 | no flags |
| 142-144 | 0 | 0 | no flags |
| 144-146 | 0 | 0 | no flags |
| 146-148 | 0 | 0 | no flags |
| 148-150 | 0 | 0 | no flags |
| 178-180 | 0 | 0 | no flags |
## Discussion: Flohrer, Krag and Klinkrad (AMOS 2008), and what our curve can say about it

The reference is *Assessment and Categorization of TLE Orbit Errors for the US
SSN Catalogue*, Tim Flohrer, Holger Krag and Heiner Klinkrad, ESA/ESOC Space
Debris Office, AMOS 2008. The copy read for this section was fetched directly
and its text extracted; the passages quoted below are verbatim from it, not from
memory or from a secondary summary.

Three things in that paper bear on this analysis, and one of them is a warning.

**First, it independently justifies the stratification.** ESA's collision-risk
tool CRASS carries TLE covariance in look-up tables "sorted by eccentricity,
perigee height and inclination", and the paper's conclusion proposes "to keep
this classification in the domain eccentricity-inclination-perigee height". That
is three of the four factors registered for Analysis 1, chosen independently, a
decade and a half earlier, for the same underlying reason: TLE error structure
is not homogeneous across the catalogue. Our fourth factor, TLE update cadence,
is the one they gesture at rather than tabulate — their suggested follow-up to
the pattern they could not explain was "the bridging of gaps in the
observations, or the performance of the used sensors".

**Second, the ~40-degree out-of-plane peak is real and is stated plainly:**

> "Leaving the circular orbits out, objects in low-inclined orbits show higher
> uncertainties in radial and along-track direction compared to objects orbiting
> in higher inclinations. This is slightly different in the out-of-plane
> component, where the largest uncertainties are found at medium inclinations,
> centered on ~40 deg. It is difficult to give the reason for the observed
> pattern, as the applied process for the TLE generation is unknown."

Out-of-plane is the component our inclination channel is sensitive to, so this
is the single most relevant prediction in the literature for where a
TLE-driven inclination false-alarm floor ought to peak. They also record that in
eccentric orbits, objects "orbiting in the inclination band between 60 and 65
deg are of significantly lower uncertainty" — so their picture is a mid-latitude
out-of-plane bulge with a high-inclination trough, not a monotone rise.

**Third, the warning.** Flohrer et al. measure *orbit uncertainty* — the spread
between a TLE state and an orbit determination from TLE-derived
pseudo-observations. We measure *false-alarm rate* — how often a self-history
detector at kappa 32 declares a step. Those are different quantities, and the
map between them is not a proportionality. A detector's flag rate depends on the
uncertainty **relative to its own fitted baseline scatter**, so a regime with
large but well-characterised out-of-plane error can be quieter than a regime with
smaller but less stable error. Any claim that our curve "confirms" or "refutes"
their peak has to survive that gap, and the honest statement is that our curve
constrains the false-alarm consequence of their error structure, not the error
structure itself.

What our curve can legitimately say is whether the **inclination dependence of
the false-alarm rate** has its maximum near 40 degrees, as an out-of-plane-error
mechanism would predict, or somewhere else, which would point at a different
mechanism. That comparison is made below against the measured bins and their
bounds, and "consistent with" is used only where the measured Jeffreys intervals
actually exclude the alternative.
## Limitations, stated before a reviewer has to find them

### The sample is systematic, not random

A `norad % 5` sample is a uniform-probability sample over objects, but it is not
a random confidence sample, and NORAD number correlates with launch epoch,
operator and constellation membership. Interval-level Jeffreys bounds quantify
binomial uncertainty inside the sample and nothing else. The **clustered
object-level bootstrap** is the interval quoted for the headline reweighted
floor precisely because intervals inside one object share a baseline, a fit
history and a cadence, and treating millions of them as independent trials would
produce an interval far too narrow to believe. Even the bootstrap assumes the
sampled objects are exchangeable with the unsampled ones at fixed covariates;
that assumption is not testable from inside this sample.

### The archive is mutable

It is a live ingest, not a preserved snapshot. Both detector policies see
exactly the same in-memory rows for each object, so the "on" and "off" tallies
cannot drift apart, but a whole pass is still a mosaic of read times rather than
one global database snapshot. The published full-population control is a
separate, earlier population, and the two must not be added together or compared
row for row.

### Detection recall is very low, and that constrains what the floor means

The fuel-odometer work committed the same day (`2575e4f`,
`docs/fuel-odometer-20260920.md`) measured that for the 54 chemically
station-kept GEO satellites where the comparison is meaningful, the **detected**
station-keeping delta-v accounts for a median of **1.81%** of the ~50 m/s/yr
north-south-keeping rule of thumb, with 46 of 54 below 10%. Electric
station-keeping is worse than low-recall: a continuous low-thrust burn produces
no step at all for a step detector, so 84 further satellites are structurally
blind. That result has to be reckoned with here, and it cuts three ways.

**It does not invalidate the reweighting.** The estimand of Analysis 1 is the
passive **false-alarm** rate carried onto the payload covariate distribution.
Its numerator counts flags raised on objects believed not to manoeuvre and its
denominator counts their exposure; neither changes when the detector misses
small true burns on payloads. The covariate reweighting assumptions — that
within a stratum the passive noise process is exchangeable with the payload
noise process, and that the strata capture the covariates that drive that noise
— are untouched by recall. The reweighted floor below is therefore unaffected by
the 1.81% figure.

**It does change what the separation between the two rates means.** The payload
rate is not a manoeuvre rate; it is the rate of manoeuvres **large enough for
this detector to see**, and the odometer measures that this is a small and
non-random subset of the truth. Any bound separation, this task's or the
published 18.191x, is a statement about large-excursion detection only. The
paper must not let that ratio be read as "payloads manoeuvre 18 times more often
than debris false-alarms".

**It correlates with a stratum, which is the part that genuinely bites.** The
blind population — electric station-keeping GEO satellites — sits almost
entirely in one corner of the covariate space: perigee `>2000 km`, inclination
`0-1`, eccentricity `<0.001`. That is exactly a stratum where payload exposure
is heavy. The passive floor in that stratum is still measurable and still
transfers, because passive objects there are judged by the same detector. But
the **payload** rate in that stratum understates truth by an unmeasured and
probably large factor, so any per-stratum comparison of passive to payload rates
in the GEO corner is a comparison against a known-depressed payload number. The
tables report both rates; the interpretation must not treat the GEO payload rate
as a true-positive rate.

### A floor is not a bound on any individual event

The control measures a rate over a population. It says nothing about whether a
particular catch is real, and no catch in this catalogue is promoted past
"candidate" by anything in this document.

### Unsupported strata are gaps, not zeros

Where payload exposure sits in a stratum with no passive support, the stratum is
listed, its share of payload exposure is quantified, and the reweighted estimate
is explicitly renormalised over the supported strata only. The worst-case fill
(Sensitivity A) shows what happens if every such stratum were as bad as the
pooled Jeffreys upper bound allows. Neither number is a measurement of those
strata, and neither is presented as one.

### The equivalence margin is a choice, defended but still a choice

1.5 was reused from the Phase-2b gate rather than invented here, and it was
registered before the test was run. A reviewer who thinks the right margin is
1.2 will get a different verdict, and is entitled to; the exact conditional
ratio intervals are reported in full so that verdict can be read off directly
without re-running anything.

### The target distribution is itself estimated

The payload covariate weights are measured from the same 1-in-5 sample as the
passive rates, not from the full payload population. The weights are therefore
estimates with their own sampling error, which the clustered bootstrap does
**not** propagate — it resamples passive objects only, holding the payload
weights fixed, exactly as registered. Payload exposure is large enough that the
weights are well determined in the heavy strata; in the thin tail of the
distribution they are not, and a reviewer may reasonably ask for a double
bootstrap that resamples both populations. That was not registered and is not
reported here.

### The corroboration rule made the floor more covariate-sensitive

Measured, not argued: the reweighted-to-raw ratio is **1.2213x** on the
pre-corroboration detector and **2.0591x** on the shipping one. The rule
suppresses false alarms most effectively in the strata that carry the most
passive exposure — high-inclination LEO — which leaves the thinly-measured
strata contributing a larger share of what remains. A change that improves a
pooled control can therefore make its covariate-matched version *harder* to
establish, and nothing in the pooled 18.191x separation would have revealed
that. This is an argument for reporting both numbers, not for reverting
anything.
## What a reviewer still attacks

These are the objections this document does **not** close. They are listed
because a methods paper that lists them is harder to reject than one that waits
to be told.

1. **"Your passive population is not passive."** Object type comes from the
   catalogue. A `ROCKET BODY` with an unrecorded disposal burn, or a `DEBRIS`
   fragment that is really a misclassified payload, contributes a real
   manoeuvre to the false-alarm numerator. This inflates the floor, so it is
   conservative for a bound — but it is unmeasured, and a reviewer is entitled
   to ask how much of the floor is it. Nothing here answers that.
2. **"Exchangeability inside a stratum is the whole argument, and it is
   assumed."** Reweighting only transfers the floor if, at fixed perigee,
   inclination, eccentricity and cadence, a passive object's noise process is
   the same as a payload object's. Payloads are tracked differently, are often
   larger and brighter, and may be prioritised by the sensor tasking that
   generates the TLEs. The four registered factors are the observable proxies
   for that; sensor tasking itself is not in the archive and cannot be
   stratified on.
3. **"The strata are yours."** Four factors and 768 cells is a choice. The
   coarse 48-cell sensitivity shows the answer is not an artefact of
   fragmentation, and the eccentricity banding was registered as untuned decade
   boundaries, but no reviewer has to accept that a fifth factor — solar
   activity epoch, RCS size, operator, sensor coverage — would leave the number
   where it is.
4. **"Equivalence at 1.5 is a weak claim."** It is. TOST at 1.5 says the two
   rates are within a factor of 1.5 of each other; it does not say they are
   equal, and it would pass for a genuine 1.4x difference. The exact ratio
   intervals are published so a stricter reader can apply their own margin.
5. **"A boundary that falls out of a pooled scan is still a boundary you
   defined."** The grid, the pooling, the margin and the monotone-stability
   clause are all registered choices, and the registered rule has a dilution
   property, documented in advance and pinned by an offline test. A different
   defensible rule could land elsewhere.
6. **"Recall is 1.8%, so what is the payload rate even measuring?"** Answered
   above at length, and the answer is uncomfortable: the payload rate is a
   large-excursion detection rate, not a manoeuvre rate. The transfer analysis
   survives this because it is about the false-alarm side, but the separation
   statistic does not survive being read as a physical manoeuvre ratio.
7. **"The archive moved under you."** It did; it is a live ingest. The two
   detector policies are paired per object, which removes the worst version of
   this, but nothing here is a frozen snapshot that a third party could re-run
   bit for bit.
8. **"One-in-five is not the catalogue."** The full-population control exists
   for the pooled rates; the stratified control does not, and building it would
   be a multi-hour full-archive pass. Every stratified number here carries
   sample uncertainty that the pooled published numbers do not.
9. **"You never showed a false alarm."** Correct. No visual or independent
   confirmation of any individual passive flag is presented, and no external
   truth source for payload manoeuvres was available. The control is a rate
   argument end to end.
10. **"Your Analysis-1 failure is an estimator artefact, not a finding."** A
    reviewer can fairly say that a bootstrap upper bound of 26 per 1,000, driven
    by strata holding a few hundred passive intervals, tells you about the
    estimator rather than about the sky, and that the `>=1,000`-interval tier
    (0.223524, 1.3737x raw) is the honest number. That may well be right. It
    does not change the verdict, because the rule was registered on the `>=1`
    tier before the data existed, and rewriting it now is the one move this
    whole apparatus exists to prevent. The correct response is more passive
    exposure in the thin strata, and that experiment is named rather than run.
11. **"2.0591x versus a 2x threshold is a coin toss."** It is. A three percent
    margin is not a physical statement, and had the registration said 2.5x the
    clause would have passed. The threshold was fixed in advance precisely so
    that it could not be adjusted to taste afterwards; the raw ratio is reported
    so any reader can apply their own.
12. **"You refuted your own shipped rule and shipped nothing."** Correct, and
    deliberate. This task changed no detector, no threshold, no boundary and no
    deployment. The 30-degree rule remains live while the evidence against its
    stated justification sits in the repository. That is a decision for the
    owner, not for the session that found it.
13. **"Equivalence at 60-90 and 90-120 is still an acceptance of a null you
    chose."** TOST at 1.5 answers the original null-acceptance objection, but it
    substitutes a different judgement call — the margin. At a margin of 1.2,
    60-90 excluding SSO ([0.8465, 0.9363]) would fail. The intervals are
    published so that verdict needs no re-run.
## Reproduction and provenance

Every number in this document comes from three programs in this repository and
nothing else. They are committed, not pasted into a receipt.

```bash
# offline arithmetic tests - no archive, no network, no GPU
.venv-gpu/bin/python tools/paperb_selftest.py

# the bounded, resumable, read-only archive pass (two disjoint NORAD ranges)
nice -n 19 ionice -c3 .venv-gpu/bin/python tools/paperb_measure.py \
    --modulus 5 --min-norad 0 --max-norad 21405 \
    --out /tmp/paperb-20260920/part0 --budget-seconds 3600 --hard-seconds 3660
nice -n 19 ionice -c3 .venv-gpu/bin/python tools/paperb_measure.py \
    --modulus 5 --min-norad 21405 --max-norad 2147483647 \
    --out /tmp/paperb-20260920/part1 --budget-seconds 3600 --hard-seconds 3660

# the registered tables, verdicts and receipts
.venv-gpu/bin/python tools/paperb_analyze.py \
    --inputs '/tmp/paperb-20260920/part*.objects.jsonl' \
    --summaries '/tmp/paperb-20260920/part*.summary.json'
```

Artefacts:

- `docs/paperb-preregistration-20260920.md` — the contract, committed at
  `f317a28`, amended at `8604de2`, both before any result.
- `docs/paperb-strata-20260920.jsonl` — one line per stratum-level measurement,
  both populations, both detector policies, plus the curve bins, the zoom bins,
  the region tests and every boundary candidate.
- `docs/paperb-results-20260920.json` — the machine receipt: selection, counts,
  timings, seeds, source SHA-256 hashes, every verdict, and the
  shipping-detector structural check that makes amendment 1 verifiable.
- `docs/paperb-tables-20260920.md` — the generated tables, byte-identical to
  the tables section below.

No GPU was used: the pass is a CPU reader, and the GPU broker was never
invoked. No release, deployment, checkpoint, timer, frontend or public artifact
was produced or modified. The detector source is untouched — the two policies
are reached through a keyword argument that already existed on the production
function.

### What the run actually cost, and what else was on the machine

Two readers, disjoint NORAD ranges split at 21405 by a rollup row estimate used
only to partition and never as a denominator. Each hit its registered 3,600 s
cooperative budget once, stopped cleanly, wrote its object cursor and resumed
from it: part 0 finished its tail in a further 574 s, part 1 in a further 773 s.
Both reported `COMPLETE`, and between them they hold every one of the 6,313
selected objects — 6,297 with tallies plus 16 excluded by the production
nine-interval admission rule (11 passive, 5 payload), counted rather than
dropped.

The resume path was verified before it was relied on, not after: a run was
stopped at its budget, a stray record appended past its cursor to simulate a
reader killed between writing an object and updating the cursor, and the resume
then truncated the stray, processed no object twice, and produced totals
**bit-identical** to the same range measured in one uninterrupted pass. That
check found a real defect — the original resume would have double-counted any
object written after the last cursor write — which is fixed in `46dee20`.

The host was under heavy unrelated load throughout: a 12-core machine at load
average 26-28, running an `orbit_release` sweep, two METOC training jobs and a
publisher. Both readers ran at `nice 19` with idle I/O and 86-87% of a core
each, and nothing else was slowed enough to notice. No GPU was used.

`tools/paperb_selftest.py`: **40 tests, OK**. The repository's orbital suite,
`python -m unittest discover -s tests -p 'test_orbit*.py'`, was run three times:
**626 tests, OK (5 opt-in skips)** on the second and third runs. The first run,
which was executed concurrently with both archive readers, reported one failure
— and only the tail of its output was retained, so **the failing test was not
captured and cannot be named here.** That is a gap, not a pass: the honest
statement is that two clean runs of the identical command followed, that this
task modified no file under `pipeline/`, and that the failure is therefore
unlikely to be attributable to it — but "unlikely" is not "shown".
