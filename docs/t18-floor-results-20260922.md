# T18 floor results — the sampling schedule alone recovers two thirds of the shipped detector's recall

**Registration:** `docs/t18-preregistration-20260922.md`, committed **alone** at `2618343` before any
T18 code existed; amended alone at `3979f4e` (E2 only, before any E2 number exists and untouched by
anything here). **Instruments:** `tools/t18_data.py`, `tools/t18_model.py`, `tools/t18_floor.py`,
committed at `9e043a1` and after; **50 tests** in `tests/test_t18.py`. **Artefacts:**
`docs/t18-floor-20260922.json`, `docs/t18-floor-model-20260922.json`,
`docs/t18-split-20260922.json` (assignment SHA-256
`3097df9e29a085d8c8d5f88bc7aad457ceb031ea80aba65052be15c8b5eedb8a`).
**Model version:** `t18-learned-model/20260922/cadence`, checkpoint SHA-256
`27d23e7f6c2a2d132932922eb848bdad24318499f042db1349bc7f865ef52e97`.
**Wired into:** nothing. No timer, no cron, no site surface. The learned model decorates; it never gates.

**This is build step B4, and it is deliberately ahead of every headline number.** No full model has been
trained. Nothing here says what a model that reads the residual channels can do.

---

## 0. The number this document exists to fix

**A model that is shown the archive's SAMPLING SCHEDULE and nothing else — no element value, no regime,
no catalogue number, no name — flags 58 of 1,134 mission-reported manoeuvres, a recall of 5.115%
[3.977, 6.555], at the shipped detector's own false-flag rate of 0.012642669 flags per labelled-quiet
window-day.**

The shipped detector's recall on the identical 1,134 labels at the identical operating point is
**7.937% [6.502, 9.656]** (`docs/t16b-truthset-recall-20260922.json`). So **64.4% of the shipped
detector's recall (58 of its 90 hits) is reachable from timing and residual magnitude alone, with no
learned representation of behaviour anywhere in the model.**

**That 5.115% is the artefact floor. It is the bar. Every T18 number that follows is reported as an
increment above it, with it printed alongside — not as an increment above 7.937%.**

Both numbers are benchmarks on **eleven geodetic and altimetry spacecraft**, and §7 says what they may
not be used for.

---

## 1. What was run, and what it cost

| | |
|---|---|
| Corpus, direct scan 2026-09-22 | **68,749 objects, 217,046,214 element sets**; 33,105 admissible under the registered rule |
| Split | seeded hash on the registered unit; assignment SHA-256 **identical across two independent constructions**, files byte-identical |
| Training partition | **1,998 objects, 5,172,912 valid residual steps**, every epoch below `T_cut` = 2024-01-01Z |
| Validation | 500 objects, 1,448,072 steps |
| Evaluation | 11 truth spacecraft (113,158 steps, whole histories); 1,000 passive test objects (3,371,256); 41 routine keepers (162,413); 500 general test objects (1,526,411) |
| Propagation failures | **21 of 5,172,933 training steps** (0.0004%); 0 of 113,158 on the truth arm |
| Model | cadence-only variant, **696,475 parameters**, 6 dilated causal layers, `d_model` 128, Student-t heads |
| Training | **20,000 steps in 745.2 s = 0.2070 GPU-hours**, 26.84 steps/s |
| Card | one RTX 4080, `GPU-e7724e1e-bdd0-0671-dd83-00b1177c7c0e`, granted by `gpu-run`, class `standard` |
| **Peak measured** | **798.0 MiB** against a **2,048 MiB claim** and a registered ceiling of 4,096 MiB |
| **What else was resident** | a super-resolution training run holding ~11,264 MiB on each card throughout; an extraction job of this same track occupied host CPU for the first ~3 minutes. **The run was CO-TENANTED and the step rate is reported as a lower bound, not a clean rate.** |

**Registry and ledger shipped in the same change as the run**, as the registration requires:
`space-t18-learned-model` in the estate's `workspace/infrastructure/gpu-consumers.json` (`b56bdee`),
`resource: ["gpu-direct", "gpu-broker"]` so it renders on `/brain/gpu`, with a `jsonl` usage ledger at
`state/space-t18-learned-model-usage.jsonl` carrying this run's start, duration, steps, peak, claim,
card UUID and co-tenancy. The ledger is written on bigmem and carried to the VPS by the estate's own
every-ten-minute puller, which gained this lane in the same change and was **run by hand immediately**
rather than left to its timer: it drew the row, and the page's own reader turns that row into a real
745-second span. The `/brain/gpu` schedule timeline was checked for conflicts **before** the run.

### 1.1 The re-price, and the stop rule

At **26.84 steps/s**, a 20,000-step run costs **0.207 GPU-h**. The registered campaign is 8–12 runs plus
about 2 GPU-h of inference: **a re-priced total of roughly 4.5 GPU-hours against a budget of ≤ 120, or
3.7% of it.** The 2× stop rule (240 GPU-h) is nowhere near firing.

**Deviation, recorded rather than smoothed over:** the registered re-price is taken at a **30-minute**
mark. This run finished in **12.4 minutes**, so that mark never fired and is `null` in the receipt. The
re-price above is computed from the run's own whole-run measured rate, which covers a longer span than
the 30-minute mark would have. **The 30-minute mark itself is UNPROVEN** (§8).

---

## 2. E1 — the floor, at a matched operating point

**The match is exact, not approximate.** Swept as registered — the smallest threshold whose false-flag
rate on MAD-LEO's own 1,139 labelled-quiet windows does not exceed the baseline's — the chosen threshold
`τ = 4.0217` produces **18 flags over 1,423.75 quiet window-days = 0.012642669007901668 per window-day**,
which is the shipped detector's figure to every digit, because it is the same 18 flags in the same
windows. The confirmation rule is the shipped detector's own: two consecutive element sets over the bar
and agreeing in the sign of `δa`, flag epoch on the second set.

### 2.1 Arm A1 — unseen object, any era (the floor's headline arm)

| | cadence-only floor | shipped detector | source |
|---|---|---|---|
| Recall | **58/1,134 = 5.115%** [3.977, 6.555] | 90/1,134 = 7.937% [6.502, 9.656] | T16b recall JSON |
| Labels not evaluable | **0** | 0 | |
| Flags raised, whole span | 429 | 460 | |
| Flags in labelled-quiet windows | 18 / 1,423.75 window-days | 18 / 1,423.75 | matched by construction |
| **Placebo control** (post-registration) | 52/5,610 = **0.927%**, lift **5.52×** | 17/5,610 = 0.303%, lift **26.2×** | |
| Campaign-level | 11/1,134 = 0.97% | 15/1,134 = 1.32% | ceiling 2.9% on this population |

**Registered screen E1: does the floor's recall lower bound (3.977%) exceed the shipped detector's upper
bound (9.656%)? NO.** The floor does not beat the rules, which is the outcome the registration expected
and wrote down in advance (§3.2): the registered clause that would have made a floor *above* the
baseline a finding about the shipped detector's population threshold did not need to be used.

**The placebo column is the most informative cell in the table.** The floor's flags are only **5.5×**
more likely inside a labelled manoeuvre window than beside one; the shipped detector's are **26×**. The
floor finds real manoeuvres, but far less specifically — which is what an artefact floor should look
like.

### 2.2 Split at the shipped detector's own floor

| | cadence-only floor | shipped detector |
|---|---|---|
| Above the 102–126 m threshold | **50/157 = 31.85%** | 81/157 = 51.59% |
| Below it | **8/977 = 0.82%** | 9/977 = 0.92% |

Below the threshold the two are **indistinguishable** — both about 1%. The whole of the floor's deficit
is on the burns the shipped detector can actually see.

### 2.3 Per burn-size bin — and a sign reversal that will bind on the full model

| `\|Δa\|` bin | labels | floor | shipped |
|---|---:|---:|---:|
| < 20 m | 576 | 0.17% | 1.04% |
| 20–50 m | 342 | 0.58% | 0.58% |
| **50–100 m** | 53 | **7.55%** | **1.89%** |
| 100–200 m | 27 | 22.22% | 37.04% |
| 200–500 m | 36 | 44.44% | 58.33% |
| ≥ 500 m | 100 | 29.00% | 50.00% |

**The 50–100 m bin REVERSES SIGN**: the cadence-only floor catches four of 53 there against the shipped
detector's one. That bin is exactly where T16(b) found the shipped detector's population-set threshold
biting (1.9% at the pooled floor, 39.6% once the floor drops to 50 m). A statistic whose scale is
conditioned on the object's own sampling cadence is not held up by a pooled `σ_n` that is 130–470×
larger than these objects' own noise. **The reversal is reported as the result for that bin, and the
registered reversal clause is now live for the full model.**

### 2.4 Per spacecraft — where the floor beats the rules, and where it collapses

| spacecraft | floor | shipped |
|---|---:|---:|
| SWOT | **20.9%** (18/86) | 12.8% (11/86) |
| Sentinel-6A | 12.5% | 12.5% |
| SARAL | 11.9% | 11.9% |
| Jason-3 | 7.1% | 20.0% |
| Jason-2 | 4.5% | 14.4% |
| **HY-2A** | **3.4%** (2/58) | **0.0%** (0/58) |
| Sentinel-3B | 3.4% | 5.5% |
| CryoSat-2 | 3.3% | 5.4% |
| Jason-1 | 1.7% | 5.9% |
| Sentinel-3A | **0.0%** | 1.4% |
| TOPEX/Poseidon | **0.0%** | 9.3% |

HY-2A is the sharpest case: T16(b) measured that **not one** of its 58 labelled manoeuvres moves the
semi-major axis as far as the shipped threshold requires, and the shipped detector therefore caught
none. The cadence-conditioned statistic caught two. Two of 58 is 3.4% with a wide interval and is
**UNDERPOWERED by gate G7's own bar of 20 supporting events**; it is reported because the registration
required the split, and it is not interpreted further.

### 2.5 Arm A2 — unseen object, unseen era — and why its rate is not verified

| | |
|---|---|
| Labels at or after `T_cut` | **257** |
| Recall | **3/257 = 1.167%** [0.40, 3.38] |
| Flags in post-`T_cut` labelled-quiet windows | **0** over 265 windows / 331.25 window-days |

**The A2 false-flag rate is UNMEASURED AT THIS EXPOSURE, and is never reported as zero.** A2's recall is
therefore **not at a verified matched operating point** — the threshold was matched on the whole quiet
population, and whether it also matches on the post-`T_cut` slice cannot be told from 331 window-days
that contain no flags at all. A2 is reported as a diagnostic and no comparison against the baseline is
drawn from it.

---

## 3. E3 — the floor's anomaly behaviour, and a screen that fires

The threshold is fixed on the passive null at the registered **1% of scored steps**: `τ = 8.2619`.

| population | objects | confirmed flags | window-days | flags per window-day |
|---|---:|---:|---:|---:|
| Passive null (`DEBRIS` / `ROCKET BODY`, test partition) | 1,000 | 4,392 | 7,885,080 | **0.000557** |
| Routine operations (north-south keepers, T10b, test partition) | 41 | 1,365 | 260,280 | **0.005244** |

**Ratio 9.415, against the registered screen of 3.0. THE SCREEN FIRES.**

For the cadence-only floor this is not a verdict on the anomaly claim — there is no anomaly claim here —
it is **the floor of the E3 ratio**: a statistic with no behaviour representation already puts objects
that are manoeuvring constantly and correctly 9.4× above the passive null. A full model whose ratio is
not *better* than 9.4 has added nothing on this axis, and by the registration a full model above 3.0
withdraws the anomaly claim outright.

**The comparison is NOT regime-matched, and that is a real limitation of it, not a footnote.** The
routine population is **41 of 41 GEO**; the passive null is **842 of 1,000 LEO**. Regime and routine
operation are confounded in this ratio, and nothing here separates them. A regime-matched control is
**owed** before the ratio is used against the full model.

### 3.1 The dispersion screen — the floor is twice as geometry-driven as the rules

Per-class flag rate across the committed sampling-geometry classes carrying at least the registered 200
windows of exposure (**8 classes of 55 present** reach it; the rest are counted and attributed, never
folded into a rate):

| | p10 | p90 | **p90/p10** |
|---|---:|---:|---:|
| Cadence-only floor | 0.000422 | 0.002912 | **6.900** |
| **Shipped detector, identical population** | 0.000885 | 0.003037 | **3.433** |

**The floor's flag rate varies 6.9× across sampling-geometry classes; the shipped detector's varies
3.4×.** The floor is **2.01× more geometry-dispersed than the deterministic rules** on exactly the same
objects and windows — the positive control succeeding. **6.900 is the bar**: the full model's dispersion
must come in below it with a bootstrap lower bound on the difference above zero.

The routine-keeper dispersion is **UNMEASURED**: none of its classes reaches 200 windows across 41
objects. Not zero — unmeasured.

---

## 4. Gate G — the geometry probe, and what it caught

Linear probes on the frozen, L2-normalised, mean-pooled embedding; fitted on **8,055 training windows**,
evaluated on **2,380 test windows** from object- and constellation-group-disjoint partitions; each
normalised against its own majority-class rate, object-clustered bootstrap, 2,000 resamples, seed
20260922.

| probe | classes | accuracy | majority rate | **normalised** | clustered 95% |
|---|---:|---:|---:|---:|---|
| **Sampling class** (committed Rung-2) | 55 | 0.5509 | 0.3007 | **0.3578** | [0.3004, 0.4159] |
| **Behaviour class** (registered fallback) | 25 | 0.4029 | 0.2274 | **0.2272** | [0.1751, 0.2768] |

**Verdict: FAIL, margin −0.1305.** On the cadence-only model **this FAIL is the positive control
discharging**, exactly as registration §3.2(a) set out in advance: an embedding built from timing alone
*must* carry sampling class more strongly than behaviour, and if it had not, the probe machinery would
have been the thing that was broken. The probe machinery's own positive controls — a synthetic embedding
carrying only sampling class, and its mirror image carrying only behaviour class — pass offline in both
directions.

### 4.1 The clause that did NOT hold, and it is a finding about the target

Registration §3.2(a) also says the cadence-only embedding **must not recover the behaviour class above
chance, since it never saw behaviour.** It does: normalised 0.2272, clustered lower bound **0.1751,
above zero.**

The registered behaviour target is the **T14 class baseline** — `regime × era × bus family` — because the
T13 v1 library is not committed and §3.6's fallback applies. **That target is itself substantially
predictable from cadence.** LEO objects are sampled far more often than GEO ones, and §5's measurement
below shows the fit-latency channel is very nearly a clock. So the fallback target mixes behaviour with
sampling geometry, and **a gate discharged against it is weaker than a gate discharged against T13
episode types.**

This is reported as a defect in the *target*, not in the model and not in the gate. **Gate G is owed a
re-run on T13 types when they land**, and until then the full model's G verdict inherits this weakness.

### 4.2 G5 — the leakage audit, published rather than asserted

Cosine similarity of a frozen window embedding to its nearest neighbour in the training partition:

| quantile | test → train | train → train (self excluded) |
|---|---:|---:|
| p5 | **0.7135** | 0.9860 |
| p25 | 0.9481 | 0.9936 |
| p50 | 0.9901 | 0.9963 |
| p95 | 0.9984 | 0.9994 |

Test windows sit measurably further from the training set than training windows sit from each other, and
the test distribution carries a long low tail the training one does not. **That is the distribution, and
it is published; it is not asserted to show the split worked.** A median of 0.99 is high in absolute
terms — these are 128-dimensional embeddings of cadence, and most objects in this archive are sampled on
similar schedules — so this audit bounds *representational* overlap and does not certify the split on its
own. The split's own disjointness is what the tests assert, and they assert it on cases built to contain
the leak.

---

## 5. Two measurements that change how later numbers must be read

### 5.1 The fit-latency channel is very nearly a clock

The archive was back-filled, so `ingest_hour` on a historical row records **when the back-fill ran**, not
when the element set arrived. Measured over 200 training objects: the Pearson correlation between the
`log1pLatencyHours` channel and the element-set epoch is **−0.9577**.

`ingest_hour` is a registered input (§2.1 group B and C) and it stays. But it means **a cadence-only
model can read absolute era off one of its five channels**, and every era-shaped result in this track —
including §4.1's behaviour probe, whose target contains an era term — must be read with that number
beside it. **It is not a defect that was hidden; it is a property of the archive, measured and written
down before anything depends on it.**

### 5.2 The Student-t head sits on its own floor

Learned degrees of freedom, per target channel, at the frozen checkpoint:

| channel | df | | channel | df |
|---|---:|---|---|---:|
| `dRAAN_deg` | 2.004 | | `dM_deg` | 2.053 |
| `dRadial_km` | 2.004 | | `dAlongTrack_km` | 2.187 |
| `dARGP_deg` | 2.006 | | `dCrossTrack_km` | 2.448 |
| `dI_deg` | 2.007 | | `dE` | 2.649 |
| `dA_km` | 2.007 | | | |

The head is parameterised as `df = 2 + exp(·)` so the variance exists, and **every channel has pushed
`df` onto that lower bound.** The registration anticipated the opposite — *"a df drifting toward Gaussian
is itself a finding about the channel"* — and what happened instead is a finding of the same kind read
the other way: **the residual distributions are heavier-tailed than any finite-variance Student-t this
head can express.** That is consistent with the archive's measured element scatter (`p99/σ` of 116 at GEO
and 3,558 below 500 km) and it means the surprisal statistic is **conservative**: the likelihood
under-weights the tail it is asked to score, so a real excursion is scored as less surprising than it is.

---

## 6. Gates

| Gate | Verdict |
|---|---|
| **E1 screen** | Did not clear — 3.977% lower bound against a 9.656% upper bound. Reported as the FLOOR, which is what it is |
| **E1c** | Floor established at **5.115%** [3.977, 6.555]; the full model's increment is measured above it, not above 7.937% |
| **E3 ratio** | **FIRED** — 9.415 against a registered 3.0, on a population that is not regime-matched |
| **E3 dispersion** | Measured: floor 6.900 against the shipped detector's 3.433 on the identical population; 8 of 55 classes reach the registered exposure |
| **G geometry probe** | **FAIL** (margin −0.1305) — on a cadence-only embedding this is the positive control discharging; the behaviour clause did not hold and §4.1 says why |
| **G5 leakage** | Discharged — distribution published, not asserted |
| **G7 underpowered** | Applied — HY-2A's 2/58 and every stratum below 20 supporting events lends its name to nothing |
| **G8 detector untouched** | Discharged — `proximity_plane.detect_manoeuvres` imported and called; the baseline is quoted from T16(b)'s committed JSON |
| E2, E1c increment, G2, G3, G4, G6 | **NOT EVALUATED** — they need the full model, which does not exist |

**Reproducibility, measured not claimed:** the whole measurement was run twice from the frozen
checkpoint. **E1, E3 and the geometry probe reproduced byte-for-byte identically.** The split artefact
likewise reproduced byte-identically from two independent constructions.

---

## 7. What these numbers may not be used for

- **The labels are ELEVEN GEODETIC AND ALTIMETRY SPACECRAFT, not constellations** — CryoSat-2,
  Sentinel-3A, Sentinel-3B, Jason-1, Jason-2, Jason-3, SWOT, SARAL, HY-2A, TOPEX/Poseidon, Sentinel-6A.
- **No figure here is "the model's recall"** without the qualifier *on this labelled set, these eleven
  geodetic and altimetry spacecraft, these burn sizes*.
- **Nothing here says anything about Starlink, about any constellation, or about any operator whose
  manoeuvre log is not public.** MAD-LEO's Starlink subset carries no manoeuvre labels at all — its
  authors state it is operator *prediction*, "never maneuver ground truth". **A constellation-class
  labelled baseline remains UNMEASURED.**
- **Eleven cooperative, exceptionally well-tracked spacecraft are not a census.** What makes them
  measurable — large, tracked by GNSS/DORIS/SLR, small frequent planned burns — makes them
  unrepresentative.
- **Recall and precision measured on different populations do not compose.**
- **Every threshold here is a chosen screen, not a physical law** — the 1% E3 false-alarm fraction, the
  ratio of 3.0, the 200-window exposure bar, the 20-event underpowered bar and the matched operating
  point itself.
- The E3 ratio confounds regime with routine operation (§3).

---

## 8. Deviations, and unproven items in those words

**Deviations from the registration**

1. **The broker claim was 2,048 MiB, not the registered ceiling of 4,096.** The ceiling is a maximum and
   2,048 is inside it, but the reason is worth recording: the broker's admissible headroom on the only
   card with room was 3,517 MiB and falling beside a resident super-resolution training claim, and a
   4,096 request queued rather than measuring anything. The measured peak was **798 MiB**, and the
   process binds its own allocator to its claim so an overrun fails this process and never the card.
2. **The registered 30-minute step-rate mark did not fire** — the run finished in 12.4 minutes. The
   re-price uses the whole-run measured rate instead (§1.1).
3. **The behaviour probe target is the registered fallback** (T14 class baseline), because the T13 v1
   library is not committed. §3.6 provides for this; the gate is owed a re-run on T13 types.
4. **A placebo control was added to E1**, labelled post-registration here exactly as T16(b) labelled its
   own. Without it a single-digit recall cannot be told from the background density of flags.
5. **The E3 routine population is not regime-matched** to the passive null (§3). A regime-matched control
   is owed and is post-registration work.
6. **A third instrument, `tools/t18_floor.py`,** carries the measurement; the registration named only the
   data and model tools.
7. **A defect in this session's own leakage audit was found and fixed before publication:** the first
   run's within-training reference distribution did not exclude each window's similarity to itself and
   came back as all ones. It was corrected and the whole measurement re-run; E1, E3 and the probe
   reproduced byte-for-byte, which is why that re-run is also the reproducibility check.
8. The two departures already registered in advance — per burn-size **bin** rather than decile (§1 of the
   registration) and the split artefact committed with the instrument rather than with the registration
   (§2.3) — were applied as written.

**Unproven items, in those words**

- **The 30-minute step-rate re-price mark is UNPROVEN.** It never fired, because the run was shorter than
  the mark. The whole-run rate stands in its place and the mark itself has not been exercised.
- **The 2× stop rule is UNPROVEN.** The re-priced campaign is about 3.7% of its budget, so the rule has
  never been tested against a real overrun.
- **The A2 arm's matched false-flag rate is UNMEASURED at this exposure** — zero flags over 331.25
  post-`T_cut` quiet window-days — so the A2 recall is not at a verified matched operating point.
- **Gate G against T13 episode types is UNPROVEN.** It was discharged against the registered fallback
  target only, and §4.1 shows that target is contaminated by cadence.
- **The full model is UNMEASURED.** Nothing here says what a model that reads the residual and fit
  channels can do, and no increment above this floor exists yet.
- **E2 is UNMEASURED**, and its bar was raised by T20 in amendment 1 before any E2 number existed.
- **The routine-keeper dispersion is UNMEASURED** at this exposure, not zero.
- **A regime-matched E3 control is UNPROVEN.**


---

## 8.1 CORRECTION, 2026-09-22 — the Wilson upper bound

**This document printed the floor's Wilson upper bound as 6.564 in three places. It is 6.555.**
58/1,134 at z = 1.959964 gives [3.9772, 6.5551], and this track's own committed artefact
`docs/t18-floor-20260922.json` carries the correct `[0.039772, 0.065551]` — the wrong value was in the
prose and in no artefact. It is corrected in place above.

**Nothing else moves.** The floor is 5.115%, its lower bound is 3.977%, the E1 screen was read against
the shipped detector's bounds rather than the floor's, and no comparison drawn from this document
depended on the ninth thousandth of a point. The correction was found by the registered adversarial
pass over the full-model fail-record (`docs/t18-capitulation-ledger-20260922.jsonl`, pass 1) and is made
in the same change as that document, because a published number that is wrong is corrected where it was
published and not only where it was noticed.

---

## 9. What this changes for the track

1. **The full model's bar is 5.115%, not 7.937%.** Gate G2 now has a number: the increment above this
   floor must carry an object-clustered bootstrap lower bound above zero, and the floor is printed beside
   every headline.
2. **The E3 dispersion bar is 6.900** and the shipped detector's own 3.433 sits below it, so the full
   model has to beat a pure-geometry statistic *and* stay in sight of the rules.
3. **The 50–100 m bin already reverses sign.** The registered reversal clause is live, and a full model
   that wins pooled while losing that bin publishes the reversal, not the pooled claim.
4. **The behaviour probe target needs T13.** Gate G's strength is capped until the T13 v1 library is
   committed, and this document says so rather than treating the fallback verdict as final.
5. **The fit-latency channel is a clock**, and every era-shaped reading in this track carries −0.9577
   beside it.
6. **The campaign is cheap.** 0.207 GPU-hours bought the floor; the whole registered campaign re-prices
   to roughly 4.5 GPU-hours against a budget of 120. Compute is not this track's constraint — the
   1,134 labels are.
