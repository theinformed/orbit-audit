# T18 FAIL-RECORD — the learned model measures the sampling schedule; the representation is the exception

**VERDICT. Against the cadence-only artefact floor and on the registered screens: E1 NO (increment
+0.529 points, paired clustered 95% [−1.205, +2.366], straddles zero — NOT DEMONSTRATED); E2 NO and
worse than the floor (−23.4 km at +30 d against the floor's −9.4, an increment of −14.0 km); E3 NO and
worse than the floor (routine-keeper ratio 10.67 against the floor's 9.415 and a screen of 3.0;
between-class dispersion 28.19 against the floor's 6.900); GATE G PASS — and it is the one evaluation
that passes. The frozen embedding carries behaviour more strongly than sampling class (margin +0.07612 on
T13 v2 episode types, +0.10975 on the registered fallback) where the cadence-only embedding FAILED that
same gate. The representation learned something. The detection statistic, the anomaly score and the
forecast read off it did not.**

**Registration:** `docs/t18-preregistration-20260922.md`, committed **alone** at `2618343` before any
T18 code existed, and amended **alone** four times, each before the numbers it governs existed:
`3979f4e` (the E2 bars T20 raised, before any E2 number), `91ceede` (four ambiguities, before any
full-model number), `ffb97d6` (five constructions, while the full variant was training and before any
of its numbers were read) and `8db0a36` (a second device and its cross-check tolerance, before either
side of that cross-check existed). **Instruments:** `tools/t18_data.py`, `tools/t18_model.py`,
`tools/t18_floor.py`, `tools/t18_full.py`, `tools/t18_forecast.py`, `tools/t18_device_check.py`,
`tools/t18_geo_passive.py`, with `tools/t18_campaign.sh` as the invocation record; **75 offline
proofs** in `tests/test_t18.py`, up from 50. **Artefacts:** `docs/t18-full-20260922.json`,
`docs/t18-forecast-20260922.json`, `docs/t18-forecast-floor-20260922.json`,
`docs/t18-floor-addenda-20260922.json`, `docs/t18-ablation-seed2-20260922.json`,
`docs/t18-ablation-nobstar-20260922.json`, `docs/t18-device-check-20260922.json`, alongside the
floor's `docs/t18-floor-20260922.json`. **Adversarial pass 1** is recorded in
`docs/t18-capitulation-ledger-20260922.jsonl`, verdict `revised`; what it changed is in section 10.
**Model version:** `t18-learned-model/20260922/full`, checkpoint SHA-256
`8e7573d9fc7d525e2741514b61f851897efb02b4be89dd05fdf6e3533889de5e`.
**Split:** unchanged, assignment SHA-256 `3097df9e29a085d8c8d5f88bc7aad457ceb031ea80aba65052be15c8b5eedb8a`.
**Wired into:** nothing. No timer, no cron, no site surface. The learned model decorates; it never gates.

---

## 0. Read the floor first

Every number below is an increment above **5.115% [3.977, 6.555]** — the recall a model shown the
archive's **sampling schedule and nothing else** achieves on the same 1,134 mission-reported manoeuvres
at the shipped detector's own false-flag rate. **It is not an increment above the shipped detector's
7.937%.** The other three floors this document is read against, all from `c62b298`:

| floor | value |
|---|---|
| E1 recall, cadence-only | **5.115%** [3.977, **6.555**] at 0.012642669 flags/quiet-window-day |
| E3 routine-keeper ratio, cadence-only | **9.415** (registered screen: 3.0) |
| E3 between-class dispersion p90/p10, cadence-only | **6.900** (shipped detector, same population: 3.433) |
| Gate G, cadence-only | **FAIL** on both targets — margin **−0.1373** on T13 v2 episode types, **−0.1289** on the registered fallback (the committed floor document printed **−0.1305** for the fallback, before amendment 2 made the v2 re-run the gate of record). The positive control discharging |

**A correction to the committed floor document, carried here because it is a published number.** The
floor's Wilson upper bound is **6.555**, not 6.564. 58/1,134 at z = 1.959964 gives [3.9772, 6.5551], and
`docs/t18-floor-20260922.json` carries the correct `[0.039772, 0.065551]`; the value 6.564 appears three
times in the floor's results prose and nowhere in its own artefact. The floor's verdict, its screens and
every comparison drawn from it are unaffected — an upper bound nine thousandths of a point wide of the
truth changes no clause — and the prose is corrected in the same change as this document.

**The labels are eleven geodetic and altimetry spacecraft, not constellations.** §9 says what these
numbers may not be used for, and it binds every sentence above it.

---

## 1. What was run, and what it cost

| | |
|---|---|
| Headline model | `full`, seed `20260922`, **698,011 parameters** — the floor's 696,475 plus one wider input projection, and nothing else |
| Training | **20,000 steps in 1,819.0 s = 0.5053 GPU-hours**, 10.995 steps/s |
| Card | one RTX 4080, `GPU-e7724e1e-bdd0-0671-dd83-00b1177c7c0e`, granted by `gpu-run --estimate-mib 2048 --class standard`, by **UUID**, never parsed as an index |
| **Peak measured** | **796.0 MiB** against a **2,048 MiB** claim and a registered ceiling of **4,096 MiB** |
| **Co-tenancy** | **CO-TENANTED throughout.** A super-resolution training run was resident on both cards for the whole campaign; a T18 CPU measurement and a T18 extraction shared the host. Host load average during the measurement phase was **22.75 on 12 cores**. Every rate here is a **lower bound, not a clean rate.** |
| Best validation NLL | **0.80861**, against the cadence-only floor's **1.67747** on the identical validation objects |
| Ablation arms | `full` seed `20260923`; `full-nobstar` seed `20260922` — identical in depth, width, heads, loss, optimiser, split and step budget |

### 1.1 The 30-minute re-price mark FIRED, on the registered clock, with no injection

The floor run finished in 12.4 minutes and the mark never fired; the floor results named it **UNPROVEN**
in those words. It has now fired, on the real headline run:

```
re-price mark FIRED: {"atSeconds": 1800.0570197105408, "steps": 19790,
  "stepsPerSecond": 10.994096177676829, "markSeconds": 1800.0,
  "registeredMarkSeconds": 1800.0, "injectedClock": false,
  "reprice": {"hoursPerRun": 0.5053217168352537, "runs": 12,
    "inferenceHours": 2.0, "repricedCampaignGpuHours": 8.063860602023045,
    "budgetGpuHours": 120.0, "fractionOfBudget": 0.06719883835019204,
    "stopThresholdGpuHours": 240.0, "stop": false,
    "verdict": "CONTINUE: the re-priced campaign is inside the registered budget"}}
```

**The re-price moved upward by 79% the moment it was taken on the model that matters** — 8.064 GPU-hours
against the floor run's 4.5, because the full model's data assembly is three times the work and runs at
10.99 steps/s instead of 26.84. That is the entire reason registration §5 puts the mark on a real
training run rather than on a design estimate. 8.064 GPU-hours is **6.7% of the 120-hour budget**.

**It fired a second time, on the second-seed run, and the two firings disagree in exactly the way they
should.** That run was co-tenanted with a T18 CPU measurement as well as the resident super-resolution
training, and its mark reads **7.411 steps/s at step 13,340**, re-pricing the campaign to **10.996
GPU-hours** — 9.2% of the budget, still CONTINUE. A step rate read on a busier host is a slower rate
and a dearer campaign, and the mark records that rather than averaging it away. **Every rate in this
document is a lower bound, not a clean rate**, and the two marks are the measurement of that.

**The 2× stop rule was exercised, on a fixture rather than on an overrun.** `reprice()` fed a synthetic
rate of 0.05 steps/s re-prices the campaign to **1,335.3 GPU-hours** against the 240-hour threshold and
returns `stop: true` with the verdict *"STOP: the campaign is re-priced above 2x the registered budget
and the registration is amended before any further run"*; the boundary is asserted on both sides, at
exactly 2× (continue) and a hair below the rate that produces it (stop). **In the live run the rule was
evaluated and did not fire**, because 8.064 is not above 240 — which is a rule discharged, not a rule
untested.

### 1.2 Two devices, and the cross-check that licenses putting their numbers side by side

An operator ruling of 2026-09-22 opened the desktop node's Apple-silicon GPU as a sanctioned compute
lane, so that the resident super-resolution training keeps the video memory on the two 4080s. It arrived
mid-campaign, and its own words are that a run in flight is not moved. **So the floor, the headline
`full` run and the second-seed `full` run trained on the NVIDIA lane, and the no-`B*` ablation — the run
that follows — trained on the Apple lane.** Amendment 4 (`8db0a36`) was committed **alone, before either
side of the cross-check existed**, and it registered what that costs.

| | NVIDIA lane | Apple lane |
|---|---|---|
| Admission | `gpu-run --estimate-mib 2048 --class standard`, card by UUID | the lane's own single-job lock; **no broker** |
| Allocator bound to the claim? | **yes** — an overrun fails this process and never the card | **no** — the claim is asserted against the measured peak every step, so an overrun aborts the run **after** the allocation rather than instead of it |
| Resident list | read per process | **UNMEASURED** — the lane exposes no per-process GPU accounting; exclusivity comes from the lock |
| Usage row | this track's ledger | this track's ledger **and** the lane's own |

**The cross-check, run on both devices with the registered protocol** — same variant, same seed, same
initialisation, same batches in the same order, same optimiser state, fp32, 200 steps, loss recorded at
every step:

| | value |
|---|---:|
| **Maximum absolute difference of the two loss curves** | **7.90 × 10⁻⁵** |
| Registered tolerance (amendment 4 A4.2, fixed before either curve existed) | **1 × 10⁻³** |
| **Verdict** | **AGREES** |
| First step's absolute difference — the one that isolates association order | **4.77 × 10⁻⁷** |
| Median absolute difference | 3.03 × 10⁻⁵ |
| Maximum relative difference | 5.19 × 10⁻⁵ |
| Final loss after 200 steps | 1.823854 (NVIDIA) against 1.823915 (Apple) |
| Throughput | **15.475 steps/s** (NVIDIA, uncontended) against **11.031 steps/s** (Apple) |
| Peak | 796.0 MiB against 1,104.2 MiB |

**No operation fell back off the Apple GPU and none errored**, so amendment 4's clause returning the run
to the NVIDIA lane did not fire. The first step's difference of 4.8 × 10⁻⁷ is the pure floating-point
association-order term, before any optimiser step has compounded it; the maximum of 7.9 × 10⁻⁵ at step
149 is that term after 149 compounding steps. **Both are two orders of magnitude below the ~0.003
run-to-run drift this document publishes for its own probe fit on a single device**, which is the
context that makes "agrees" mean something.

**The no-`B*` run itself, on the Apple lane:** 20,000 steps in **1,444 s = 0.4011 GPU-hours** at
**13.85 steps/s**, peak **1,104.2 MiB** against the same 2,048 MiB claim and the registered 4,096
ceiling, `coTenanted: false` — the lane's lock made it exclusive, which no bigmem run in this campaign
was. It is **faster than either bigmem run of the same length** (13.85 against 10.99 and 8.2 steps/s),
and that is a statement about co-tenancy rather than about the two accelerators: the uncontended
cross-check on the NVIDIA card ran at 15.48 steps/s.

**Which run ran where is named in every table**, as amendment 4 A4.3 requires, and the ablation's verdict
is read from a frozen checkpoint by the **same instrument on the same CPU** as every other arm — so only
the training crossed devices, never the evaluation.

**Both lanes wrote their usage rows.** This track's own ledger carries one row per run with its device —
four rows now, `t18_train_cadence`, `t18_train_full`, `t18_train_full` at the second seed and
`t18_train_full-nobstar` with `deviceKind: mps` — and the Apple lane's own wrapper wrote its two rows
(`space-t18-device-check`, 22 s; `space-t18-nobstar`, 1,445 s) to the lane's ledger under its own
registry row. Neither substitutes for the other and both are named here.

---

## 2. E1 — detection, at the shipped detector's own false-flag rate

**The match is conservative, and by the registered tie-break.** Swept as registered — *the smallest
threshold whose false-flag rate on MAD-LEO's 1,139 labelled-quiet windows does not exceed the
baseline's* — the chosen threshold `τ = 4.6021` produces **17** flags over 1,423.75 quiet window-days =
**0.011940 per window-day**, against the baseline's 0.012643. The full model is therefore read at an
operating point **5.6% stricter than the baseline's**, not at a matched-or-looser one. The floor's own
sweep lands on 18 flags and the figure to every digit; the two models are each swept independently, as
§3.1 requires and amendment 3 A3.5 restates.

### 2.1 Arm A1 — unseen object, any era

| | full model | cadence-only floor | shipped detector |
|---|---|---|---|
| Recall | **64/1,134 = 5.644%** [4.444, 7.143] | 58/1,134 = 5.115% [3.977, 6.555] | 90/1,134 = 7.937% [6.502, 9.656] |
| Labels not evaluable | 0 | 0 | 0 |
| Flags in labelled-quiet windows | 17 / 1,423.75 window-days | 18 / 1,423.75 | 18 / 1,423.75 |
| Flags raised, whole span | 1,095 | 429 | 460 |
| **Placebo control** (post-registration) | 56/5,610 = **0.998%**, lift **5.66×** | 52/5,610 = 0.927%, lift 5.52× | 17/5,610 = 0.303%, lift 26.2× |
| Campaign-level | 13/1,134 = 1.15% | 11/1,134 = 0.97% | 15/1,134 = 1.32% |
| Above the 102–126 m detector floor | 46/157 = 29.30% | 50/157 = 31.85% | 81/157 = 51.59% |
| Below it | 18/977 = 1.84% | 8/977 = 0.82% | 9/977 = 0.92% |

**Registered screen E1: does the learned model's recall lower bound (4.444%) exceed the shipped
detector's upper bound (9.656%)? NO. The screen does not clear.** The falsifier's first clause is
satisfied: at matched false-flag rate the learned model does not beat the rules.

**The placebo column is again the most informative cell.** The full model's flags are **5.66×** more
likely inside a labelled manoeuvre window than beside one; the floor's are 5.52×; the shipped detector's
are **26.2×**. Reading the residual and fit channels moved that specificity by **0.14 of a multiple**.
The learned statistic raises 1,095 flags to the rules' 460 and converts the extra 635 into six more
hits. That is what a 5.6× lift looks like next to a 26× one.

### 2.2 E1c — the increment above the floor, paired and clustered

| | |
|---|---|
| Full model recall | 5.644% |
| Cadence-only floor, same labels | 5.115% |
| **Increment** | **+0.529 percentage points** |
| Paired object-clustered 95% (11 clusters, 2,000 resamples, seed 20260922) | **[−1.205, +2.366] points** |
| Lower bound above zero? | **NO** |

**The increment inherits the stricter operating point, and that makes it a slight UNDER-estimate.** The
full model is read at 17 quiet flags and the floor at 18; §2's paragraph on that difference is written
against the shipped detector, but the pairing carries it too. One flag cannot move an interval ±1.79
points wide, and the direction is stated so the reader does not have to derive it: **+0.529 is the
conservative side of the increment, not the flattering one.**

**Registered screen E1c: the increment above the floor must have an object-clustered bootstrap lower
bound above zero. It does not. The screen FAILS.** Registration §3.2 says in advance what failing means:
**the model measures the sampling schedule.**

The interval is wide because there are eleven clusters, which amendment 2 A2.4 wrote down in advance
rather than discovering here: *"eleven clusters is a small number of clusters… an increment whose
interval straddles zero is reported as not demonstrated, not as a trend."* That is the reading. Six
labels of 1,134 is not a demonstrated advantage over a model that was shown no element value at all.

**Three things are true at once here and all three belong in the record.** (1) The interval's half-width
is about **1.79 points**, so the smallest increment this design could have demonstrated *in either
direction* is roughly **+1.8 to +2.0 points — about 20 labels.** An increment of +0.529 points could not
have been demonstrated by this design whatever its sign. (2) **The design is not therefore powerless for
what it was built to test:** the registered E1 target is a recall lower bound above 9.656%, which needs
roughly +6.3 points over the floor, comfortably outside that minimum — any model that cleared E1 would
have cleared E1c with room. (3) **The width is earned, not an artefact of the estimator.** The
per-spacecraft deltas genuinely cancel: Jason-1 +6, Jason-2 +5, Jason-3 +2, Sentinel-6A +2,
Sentinel-3A +1, SWOT / Sentinel-3B / TOPEX 0, HY-2A −2, CryoSat-2 −3, SARAL −5. A cluster bootstrap over
eleven spacecraft that disagree in sign *should* produce an interval through zero, and it does.

### 2.2.1 Where the increment lives — and it is not where a detector would want it

The shipped detector's own 102–126 m floor splits the labels into the burns it can see and the burns it
cannot, and the increment is entirely on one side of that line:

| stratum | full model | cadence-only floor | increment | paired clustered 95% |
|---|---:|---:|---:|---|
| **Above** the 102–126 m floor | 46/157 = **29.30%** | 50/157 = **31.85%** | **−2.548 pts** (−4 hits) | [−10.400, +4.730] |
| **Below** it | 18/977 = **1.84%** [1.169, 2.893] | 8/977 = **0.82%** | **+1.024 pts** (+10 hits) | [−0.119, +2.315] |
| net | 64/1,134 | 58/1,134 | **+0.529 pts** (+6) | [−1.205, +2.366] |

**Neither stratum's increment has a lower bound above zero either**, so the split is a statement about
where the hits moved, not a demonstration that they were gained.

**The full model is four hits WORSE than the cadence-only floor on the burns a detector is actually
asked to catch**, and buys ten on the burns below the instrument limit. In that lower stratum its hit
rate is **1.84%** against its own placebo density of **0.998%** [0.770, 1.294] — a lift of **1.85×**,
with a Wilson lower bound of 1.169 that only just clears the placebo's upper bound of 1.294. Above the
floor the same model's flags carry a lift of about 29×.

**So the entire increment lives in the stratum where the model's hits are barely separable from its own
background**, and the stratum where separation is unambiguous is where it loses. That is a stronger
statement than "not demonstrated", it is made of cells this document already prints, and it is the
reading E1c's interval was always going to deliver.

### 2.3 Per burn-size bin, and the reversal clause

| `\|Δa\|` bin | labels | **full** | floor | shipped | reverses vs shipped | vs floor |
|---|---:|---:|---:|---:|:--:|:--:|
| 0–20 m | 576 | **1.389%** | 0.174% | 1.042% | no | no |
| 20–50 m | 342 | **0.877%** | 0.585% | 0.585% | no | no |
| 50–100 m | 53 | **9.434%** | 7.547% | 1.887% | no | no |
| 100–200 m | 27 | **25.926%** | 22.222% | 37.037% | **YES** | no |
| 200–500 m | 36 | **22.222%** | 44.444% | 58.333% | **YES** | **YES** |
| ≥ 500 m | 100 | **33.000%** | 29.000% | 50.000% | **YES** | no |

**THREE BINS REVERSE AGAINST THE SHIPPED DETECTOR, SO THE POOLED CLAIM IS WITHHELD AND THE REVERSAL IS
THE RESULT.** That is registration §3.1's clause, applied; the floor already made it live and the full
model does not retire it.

The shape is legible and it is not flattering. **The learned statistic gains on small burns and loses on
large ones.** Below 100 m it beats both the floor and the rules, and the 50–100 m reversal the floor
opened against the shipped detector widens from 7.55% to 9.434% against 1.887% — the bin where T16(b)
found the pooled population threshold biting, exactly where a statistic scaled by the object's own
cadence should help. Above 100 m it loses to the rules in every bin, and in the 200–500 m bin it loses
to **the cadence-only floor as well**, halving 44.4% to 22.2%. A detector that finds more of the burns
nobody can see and fewer of the burns everybody can see has not become a better detector; it has moved
its flags.

### 2.4 Per spacecraft

| spacecraft | full | floor | shipped |
|---|---:|---:|---:|
| SWOT | 20.93% (18/86) | 20.93% | 12.8% |
| Sentinel-6A | 18.75% (6/32) | 12.50% | 12.5% |
| Jason-3 | 9.41% (8/85) | 7.06% | 20.0% |
| Jason-2 | 9.01% (10/111) | 4.50% | 14.4% |
| Jason-1 | 6.72% (8/119) | 1.68% | 5.9% |
| SARAL | 4.48% (3/67) | **11.94%** | 11.9% |
| Sentinel-3B | 3.45% (5/145) | 3.45% | 5.5% |
| CryoSat-2 | 2.07% (5/241) | **3.32%** | 5.4% |
| Sentinel-3A | 0.68% (1/147) | 0.00% | 1.4% |
| **HY-2A** | **0.00%** (0/58) | **3.45%** (2/58) | 0.0% |
| TOPEX/Poseidon | 0.00% (0/43) | 0.00% | 9.3% |

**HY-2A is the case worth naming.** T16(b) measured that not one of its 58 labelled manoeuvres moves the
semi-major axis as far as the shipped threshold requires, and the shipped detector caught none. The
cadence-only floor caught two. **The full model catches none.** Two of 58 is UNDERPOWERED by gate G7's
own bar of 20 supporting events and lends its name to nothing — but the direction is the direction, and
the full model gave back the one place where the floor beat the rules outright.

### 2.5 Arm A2 — unseen object, unseen era

| | |
|---|---|
| Labels at or after `T_cut` | 257 |
| Recall | **7/257 = 2.724%** [1.326, 5.514] (floor: 3/257 = 1.167%) |
| Flags in post-`T_cut` labelled-quiet windows | **2** over 265 windows / 331.25 window-days = 0.006038 per window-day |

The floor's A2 arm had **zero** flags in that exposure and its rate was reported as UNMEASURED. This arm
has two, so a rate exists — 0.006038 against the pooled 0.011940 — but **331 window-days carrying two
flags does not verify an operating point**, and A2 remains a diagnostic. No comparison against the
baseline is drawn from it. **Note the era hazard beside it, always:** the fit-latency channel is very
nearly a clock (Pearson −0.9577 against epoch), so any era-restricted reading in this track carries that
number.

### 2.6 Gate G4 — the label-shuffled arm

With the inter-label gaps permuted within each spacecraft under seed `20260922` (amendment 3 A3.1), the
same model at the same threshold recovers **10/1,134 = 0.882%** [0.480, 1.616] against its real-label
5.644% — **15.6% of its skill survives the permutation**, and what survives is the background density of
1,095 flags, which is what the placebo control measures independently at 0.998%. **G4 discharges:** the
arm loses essentially all skill, and the residue it keeps is accounted for by a control that was
measured separately.

Paired against the cadence-only floor **on the same shuffled labels** — which is the only pairing that
is defined once the event times have moved (amendment 3 A3.1, and §10's second defect) — the increment
is **−0.088 percentage points [−0.591, +0.263]**: 0.882% against the floor's 0.970%. **On permuted
labels the full model has no advantage over the floor either, and the interval contains zero from both
sides.** That is what a control with nothing left to find looks like.

---

---

## 3. The ablation and seed arms — E1 is stable, E3 is not

The registered set, dispositioned in advance by amendment 2 A2.5 and run here. **Every arm is read by
the same instrument, on the same CPU, from a frozen checkpoint**, so only the training of the no-`B*`
checkpoint crossed devices and never its evaluation.

| arm | device | steps | best val NLL | matched `τ` | matched rate | **E1 recall (A1)** | **increment above the floor** |
|---|---|---:|---:|---:|---:|---|---|
| **`full`, seed 20260922 — the headline** | NVIDIA | 20,000 | 0.80861 | 4.6021 | 0.011940 | **64/1,134 = 5.644%** [4.444, 7.143] | **+0.529 pts** [−1.205, +2.366] |
| `full`, seed 20260923 | NVIDIA | 18,000 (early stop, patience 3) | 0.90543 | 4.1277 | 0.011238 | **64/1,134 = 5.644%** [4.444, 7.143] | **+0.529 pts** [−0.901, +2.190] |
| `full-nobstar`, seed 20260922 | Apple | 20,000 | 0.80797 | 4.0663 | 0.011940 | **65/1,134 = 5.732%** [4.522, 7.240] | **+0.617 pts** [−0.567, +1.992] |
| cadence-only floor (`c62b298`) | NVIDIA | 20,000 | 1.67747 | 4.0217 | 0.012643 | 58/1,134 = 5.115% [3.977, 6.555] | — |

### 3.1 E1 is seed-stable to the label

**The second seed lands on the identical pooled recall — 64 of 1,134 — from a different threshold
(4.1277 against 4.6021), a different operating point (0.011238 against 0.011940) and a validation NLL
0.097 worse.** That is a stronger stability statement than the two runs agreeing to within an interval:
they agree to the label. It also means the +0.529-point increment and its failure to clear zero are not
an accident of one seed.

### 3.2 E3 is NOT seed-stable, and the screen's verdict flips

| arm | E3 threshold | passive null rate | routine rate | **registered ratio** | regime-matched | screen |
|---|---:|---:|---:|---:|---:|---|
| `full`, seed 20260922 | 9.0396 | 0.0000429 | 0.0004572 | **10.666** | 3.310 | **FIRES** |
| `full`, seed 20260923 | 8.1168 | 0.0010233 | 0.0022591 | **2.208** | 1.485 | does **not** fire |
| `full-nobstar`, seed 20260922 | 7.8128 | — | — | **2.713** | 1.684 | does **not** fire |
| cadence-only floor | 8.2619 | 0.000557 | 0.005244 | **9.415** | 2.592 | **FIRES** |

**One seed puts routine keepers 10.7× above the passive null and the other puts them 2.2× above it, on
the same objects, the same windows and the same registered 1%-of-scored-steps threshold rule.** The
screen's verdict flips between them. The two models confirm wildly different numbers of flags at their
own 1% points — 8,069 against 338 on the passive null — so what moves is not the ordering of the score
but how many of its exceedances survive the two-consecutive-same-sign confirmation rule, and that is
evidently a fragile property of a trained surprisal statistic.

**This is reported as an instability of the E3 ratio, not as a rescue of the anomaly claim.** The
headline model is fixed by amendment 3 A3.5 as `full` seed `20260922` and its ratio is 10.666, which
fires; and the registration's reading of a fired screen — *the anomaly claim is withdrawn, not
rescaled* — is not weakened by a second seed disagreeing. If anything a quantity whose verdict depends
on the seed is a quantity that should not carry an anomaly claim in either direction, and **the honest
statement is that the E3 ratio is UNSTABLE ACROSS SEEDS at this sample size and neither value should be
treated as the method's.**

**The second seed's dispersion is UNMEASURABLE**, not favourable: at its own threshold one of the eight
gated sampling-geometry classes carries **no flags at all**, so p10 is zero and p90/p10 is undefined.
A class with zero flags is the extreme of class dependence, not the absence of it, and it is reported
as undefined rather than as a pass.

**The dispersion's DIRECTION, unlike the ratio's, survives every arm.** 28.195 on the headline, 67.144
on the no-`B*` arm, undefined on the second seed because a gated class went silent — against the
cadence-only floor's 6.900 and the shipped rules' 3.433. The magnitude is as unstable as the ratio; the
finding that **every full-variant arm is far more geometry-dispersed than the model that was shown only
geometry** is not. That is the axis the falsifier's third clause reads, and it reads the same on all
three arms.

### 3.3 Gate G survives every arm

| arm | sampling probe | behaviour (T13 v2) | margin | verdict |
|---|---:|---:|---:|---|
| `full`, seed 20260922 | 0.28262 | 0.35874 | **+0.07612** | **PASS** |
| `full`, seed 20260923 | 0.27480 | 0.35602 | **+0.08121** | **PASS** |
| `full-nobstar`, seed 20260922 | 0.29465 | 0.37343 | **+0.07879** | **PASS** |
| cadence-only floor | 0.35779 | 0.22047 | **−0.13732** | **FAIL** |

**The one evaluation that passes passes on all three arms**, with margins within 0.006 of each other — which
is the opposite of E3's behaviour and is worth saying beside it. Whatever the residual channels put into
the representation is stable; what the detection and anomaly read-outs make of it is not.

### 3.4 The `no-B*` ablation

**Removing `B*` changes nothing that matters, which is itself the answer to why it was a named
ablation.** The registration made `B*` both a channel and an ablation because it is a drag and attitude
channel *and* a known carrier of fit artefacts, so the question was whether the full model's behaviour
rests on it. It does not:

- **E1 recall 65/1,134 = 5.732%** [4.522, 7.240] against the full model's 64/1,134 = 5.644% — **one
  label**, at the same matched operating point of 0.011940 flags per quiet window-day.
- **The increment above the floor is +0.617 points [−0.567, +1.992]** — larger than the full model's
  +0.529 and with an interval that still straddles zero. Dropping a channel did not make the model
  worse and did not make the increment demonstrable.
- **Best validation NLL 0.80797** against the full model's 0.80861 — the narrower model fits the
  validation set marginally *better*.
- **Gate G still passes**, margin +0.07879 on T13 v2 types against the full model's +0.07612.
- **The dispersion is worse, not better: 67.144** against the full model's 28.195 and the floor's 6.900,
  with 937 of 2,000 draws usable.

So `B*` is not where the (absent) advantage lived, and it is not where the geometry dependence lived
either. **A channel whose removal costs one label out of 1,134 was not carrying the result.**

### 3.5 The two arms that were NOT run, named again

- **`no-adversary` is out of registered scope.** §4 fixes an architecture with no adversary at all, so
  every model here already *is* that arm. An adversarial arm is **UNPROVEN**.
- **The weak-label pre-training arm is NOT RUN.** No weak-label auxiliary target entered any training
  run, so §2.5(ii)'s "both with and without" never triggers. It is **UNPROVEN**.

Both were fixed in amendment 2 A2.5 **before any full-model number existed**, precisely so that neither
could later look like a choice made after seeing a result.

---

## 4. E2 — the forecast, and the clearest failure in the track

**The learned forecast is WORSE than plain SGP4 at every horizon at or beyond +7 d, on every arm, on
both held-out spacecraft and on Sentinel-1A. The registered screen fails on both of its clauses at
once — there is no reduction at +30 d, and there is an increase at every horizon. And so does every arm
of this construction, including the one with no model in it:** the registered intercept-only arm, which
learns nothing and applies the object's own observed median rate, loses **4.241 km at +30 d** and
**17.016** at +60 and **42.640** at +90. Roughly **18% of the full model's −23.417 km and 45% of the
floor's −9.380 km at +30 d is the construction itself**, not anything either model learned. That is
said here rather than left for a reader to derive, because "the learned forecast is worse" would
otherwise read as a verdict on learning when a good part of it is a verdict on the carry.

**Note also what is NOT true of both models.** The cadence-only floor *gains* at +1 d (+0.011 km) and at
**+7 d (+0.398 km)**; only from +14 d does it lose. The sentence above is true of the full model at every
horizon from +7 d and of the floor from +14 d, and the table below is the place to read which.

Headline arm, Sentinel-3A and Sentinel-3B, registered origin window (2023-01-01 to 2023-10-03),
median along-track error in km, n = 528 comparisons:

| horizon | plain SGP4 | learned | gain | clustered 95% lower | floor (cadence-only) gain |
|---|---:|---:|---:|---:|---:|
| **+0 d** | 0.502 | 0.502 | 0.000 | 0.000 | 0.000 |
| +1 d | 0.324 | 0.322 | +0.002 | −0.006 | +0.011 |
| +7 d | 2.287 | 3.232 | **−0.944** | −1.248 | +0.398 |
| +14 d | 19.519 | 24.248 | **−4.729** | −5.222 | −1.643 |
| **+30 d** | 94.523 | 117.940 | **−23.417** | −25.731 | −9.380 |
| +60 d | 391.706 | 444.160 | **−52.453** | −69.950 | −40.889 |
| +90 d | 871.212 | 970.712 | **−99.501** | −142.920 | −75.071 |

The +0 d row is the floor and is printed first: 0.502 km pooled, against T16(b)'s committed
0.577 / 0.330 km per object. The correction is identically zero there by construction (h² = 0), which
is the zero-head identity showing up in the measurement rather than only in a test. **No gain is
quoted at +1 d**, which is floor-limited.

**The increment above the floor is NEGATIVE at every horizon.** At +30 d the cadence-only model loses
9.380 km and the full model loses 23.417 km, so reading the residual and fit channels makes the
forecast **14.04 km worse** than reading the sampling schedule alone. E1c's question — does the full
model add information above the floor — is answered **no** on this evaluation, in the strongest
direction available.

### Against the bars amendment 1 raised

On T20's own embargoed test origins (2023-07-01 to 2023-12-02), n = 293:

| | +14 d | +30 d |
|---|---:|---:|
| T18 learned gain, 3A + 3B | **−5.909** [−6.227, …] | **−23.219** [−24.662, …] |
| T20 classical, Sentinel-3A (per object) | +2.24 | +56.50 |
| T20 classical, Sentinel-3B (per object) | +4.50 | +60.14 |
| T20 classical, published 3-object pooled | +14.28 | +80.40 |
| T20 intercept-only, published 3-object pooled | +5.13 | +51.82 |

**The published T20 bar is almost entirely Sentinel-1A**, which amendment 2 A2.3 excluded from the
T18 headline *before any T18 E2 number existed* — at +14 d the classical gain is +25.31 km on
Sentinel-1A against +2.24 and +4.50 on the two spacecraft that are held out by construction. That is
why the amendment ordered the bar recomputed per object; the recomputation makes the bar **lower**,
and T18 still does not come near it, because T18's number is on the wrong side of zero.

### The two hard gates of amendment 1

- **G-E2-placebo.** The 180-day-shifted-covariate arm **does not gain** (−2.251 km at +14 d, −7.536 at
  +30 d on the registered window). The gate does not fire. It does not rescue anything: the real arm
  does not gain either.
- **G-E2-manoeuvre-free.** The gain does not hold manoeuvre-free, because there is no gain to hold:
  −0.260 km at +7 d and −2.386 km at +14 d. **This control is UNMEASURABLE at +30 d and beyond** —
  T16(b) measured n = 0 manoeuvre-free intervals there on Sentinel-3A/3B and Sentinel-1A has no
  fetchable manoeuvre notice at all — so **the manoeuvre-free control is unmeasured at the horizon the
  headline screen reads.** That is a weakness of the truth set, not of the model, and it is not
  resolved by deciding it does not matter.

### The intercept-only arm is model-independent, and it is the only arm that ever gains

Amendment 2 A2.3 defines the intercept-only arm from the object's **own observed** residual rate, with
no learned covariate, so it is identical for the cadence-only floor and the full model — and it is,
to every digit (+0.158 km at +7 d, −0.393 at +14 d, −4.241 at +30 d). That identity is an internal
check that the arm is what it claims to be. It gains only at +7 d and on the manoeuvre-free subset
(+0.139 km), and amendment 1 A1.2 is explicit that **a gain at or below the intercept-only line is a
per-object bias, not a model.** Here the learned arm is below zero, which is below the bias line.

### Why it fails, measured rather than assumed (POST-REGISTRATION DIAGNOSTIC)

A correction that loses could be a sign error in the instrument. It is not.

On Sentinel-3A, 14,761 steps: the **observed** `dA_km` rate has median −6.80×10⁻⁵ km/day and a
5–95 range of ±1.6×10⁻³ km/day; the model's **predicted** rate has median −1.68×10⁻⁴ km/day and a
5–95 range of −6.4×10⁻³ to +1.0×10⁻³. **The correlation between predicted and observed rate is
+0.2777.** A sign error would show as a negative correlation. The sign is right, the scale is right —
the predicted correction at +30 d has a median magnitude of 20.8 km against a plain error of 94.5 km —
and **a correction of the same order as the error that is only 28% correlated with it adds more
variance than it removes bias.** Multiplying by h² makes that worse quadratically.

The same diagnostic explains why the floor is *less* bad: the cadence-only model's predicted rate has a
5–95 range roughly an order of magnitude narrower (p95 8.5×10⁻⁵ against 1.05×10⁻³ km/day), so its
corrections are smaller and do less damage. **A model that knows less about the residual damages the
forecast less.**

**What that correlation test can and cannot catch, stated so it is not over-read.** A correlation can
only detect an *inversion*; it cannot detect *miscalibration*, and the predictor is badly miscalibrated:
its median is about **2.5× larger** than the quantity it estimates and its lower tail about **3.8×
wider**. The amplification at +30 d is roughly **6.1 × 10⁴ km per km/day**, which is why a rate that is
wrong by a factor of a few becomes a correction of the same order as the error itself. The shrinkage
that would have fixed it — scaling the predicted rate by about `ρ · σ_obs/σ_pred ≈ 0.09` — **appears
nowhere in the registration**: §2.1's honesty clause names the noise but amendment 2 A2.3 registers the
raw rate with no calibration step. Proposing it now would be hindsight, so **the construction is not
revised and the E2 numbers stand.** It is written down here as the thing a later track would register
first.

The registration's own honesty clause said this in advance and is worth repeating as the reading:
*the SGP4 residual is not a physical acceleration; it is the difference between two fits over different
observation spans, so it carries fit noise and the sampling geometry along with whatever the object
did.* A one-step conditional mean of that quantity is not an estimate of a secular decay rate, and
E2 asked it to be one.

**The construction was registered before any E2 number existed (amendment 2 A2.3, `91ceede`) and is
not revised now. The named linear secondary is published beside it and loses too** (−1.280 km at
+14 d, −1.710 at +30 d), **and it was never permitted to become the headline.**

---

## 5. E3 — the anomaly score, and the control the floor left owed

The threshold is fixed on the registered all-regime passive null at **1% of scored steps**:
`τ = 9.0396` for the full model (the floor's is 8.2619, fixed the same way on the same population).

| population | objects | confirmed flags | window-days | flags per window-day |
|---|---:|---:|---:|---:|
| Passive null (`DEBRIS` / `ROCKET BODY`, test partition) | 1,000 | 338 | 7,885,080 | **0.0000429** |
| Routine operations (north-south keepers, T10b, test partition) | 41 | 119 | 260,280 | **0.0004572** |
| **Regime-matched null** (the same passive class, restricted to GEO) | **75** | 71 | 514,080 | **0.0001381** |

| ratio | full model | cadence-only floor | against |
|---|---:|---:|---|
| **Registered ratio** (routine ÷ all-regime passive) | **10.666** | 9.415 | the registered screen of **3.0** — **THE SCREEN FIRES for both**, and the full model is **worse than the floor** |
| **Regime-matched ratio** (routine ÷ GEO passive) | **3.310** | **2.592** | **the floor CLEARS 3.0 once regime is matched. The full model does not.** |

**That second row is the sharpest thing the owed control bought.** Matched for regime, a model shown
nothing but the sampling schedule puts routine keepers **2.592×** above a passive null of the same
regime — inside the registered screen of 3.0. The full model, shown the residual and fit channels as
well, puts them **3.310×** above it — outside. **Adding the physics moved the anomaly score from
passing this screen to failing it.**

**The regime-matched control was owed by the floor results and it changes the reading, without rescuing
it.** Amendment 2 A2.1 registered it before any full-model number existed: same passive class, same
partition, same admissibility rule, same seeded-hash order, same cap, **restricted to GEO**, with the
threshold left where §3.4 fixed it. The matched null flags at **3.2× the rate of the all-regime null**,
because GEO objects are sampled on schedules that make the surprisal statistic fire more often — and
**two thirds of the apparent "routine keepers look anomalous" signal was regime, not operation.** What
survives the matching is 3.310, which is still above the registered 3.0. **Registration §3.4 says what
that means, and it is not rescaled: if routine keepers score anomalous, the score is detecting
station-keeping — ordinary operations — and the anomaly claim is withdrawn.**

Selection honesty, per amendment 3 A3.2: the matched pool is **75 of the 2,330 admissible passive
test-partition objects**, chosen by `regime_of` on each object's first element set. The extractor's own
median-based regime disagrees on **4 of the 75** (71 GEO, 3 LEO, 1 HEO) — **5.3%**, published rather
than filtered away after the fact. 75 objects clears gate G7's bar of 20 and is small, and both are
printed.

### 5.1 The dispersion screen — the full model is four times more geometry-driven than the floor

Per-class flag rate across the committed sampling-geometry classes carrying at least the registered 200
windows of exposure (**8 of 55 classes** reach it; the rest are counted, attributed and never folded
into a rate):

| | p90/p10 |
|---|---:|
| **Full model** | **28.195** |
| Cadence-only floor, identical population | **6.900** |
| Shipped detector, identical population | 3.433 |
| Difference (floor − full), paired object-clustered 95% | **−21.295 [−115.00, −2.858]** |

**Registered screen: the screen FIRES unless the full model's dispersion is below the floor's with a
bootstrap lower bound on the difference above zero. It is four times ABOVE it. THE SCREEN FIRES.**
Registration §3.4 states the reading in advance: **a score whose rate is predicted by sampling class is
measuring sampling class.**

This is the sharpest single result in the track. The cadence-only model, which was shown nothing but
timing, produces a flag rate that varies 6.9× across sampling-geometry classes. The full model, which
was additionally shown nine residual channels and three fit covariates, produces one that varies
**28.2×**. Adding the physics made the statistic **more** geometry-driven, not less.

The new instrument reproduces the floor's published dispersion of **6.900** as **6.8997** on the same
population — an independent re-implementation landing on the committed number, which is the check that
the comparison is a comparison.

Three honesty notes on this cell, and the first of them cuts against the document rather than for it.

**1,064 of 2,000 bootstrap draws were usable**, and the 936 that were dropped are dropped for a reason
with a direction. A draw is discarded when either model's p10 over the eight fixed classes is zero —
when a resample leaves a gated class with no flag at all. The floor's own self-comparison used **2,000
of 2,000**, so **every one of the 936 drops is the full model alone** having both of its two
lowest-rate gated classes go silent in a resample. Those are exactly the draws in which the full
model's ratio diverges upward, so **the truncation biases the published interval TOWARD the screen
clearing.** It fires anyway, at [−115.00, −2.858], entirely below zero. And the fact that 47% of
resamples find the full model with two dead classes is itself a measurement of how concentrated its
flags are across sampling geometry.

**The class set is fixed by the exposure gate on the real data and is not re-gated inside a draw**
(amendment 3 A3.3) — re-gating per draw would let the resample choose which classes are compared, which
is a different estimator on every draw.

**A p90/p10 over eight points is close to a range ratio**, interpolating between the first and second
and the seventh and eighth order statistics. It is a weak summary of a distribution — and it is
nonetheless a valid *paired comparison* here, because the class set is fixed and both models are read
on the same resampled objects in every draw. It is reported as the comparison it is, not as a
distributional statistic it is not.

**The routine-keeper dispersion is UNMEASURED**, as it was for the floor: no class reaches 200 windows
across 41 objects. Not zero — unmeasured.

### 5.2 Two comparators §3.4 requires, and neither can be run

Both were checked against the committed record in amendment 3 A3.4, **before any number**:

- **The T3 14.00 d inclination-line carriers are UNMEASURED.** §3.4 admits them only *where their NORADs
  are recoverable from a committed artifact*. The committed line artefact carries **8** named top
  carriers for that line, not the 56 named comsats the runbook describes, and 8 is below gate G7's bar
  of 20. The population lends its name to nothing.
- **The T14 comparator is UNMEASURED.** §3.4 requires T14's own tail-rank score on the identical
  populations and threshold. T14 is `DESIGN LANDED … registration not yet written`: there is no
  registration, no instrument and no committed score to run. **§3.4's "if T14 wins, the learned score is
  withdrawn" CANNOT BE DISCHARGED, and the learned score is not credited with beating it.**

---

## 6. Gate G — the one evaluation that passes

Linear probes on the frozen, L2-normalised, mean-pooled embedding; fitted on **8,055 training windows**,
evaluated on **2,380 test windows** from object- and constellation-group-disjoint partitions; each
normalised against its own majority-class rate; object-clustered bootstrap, 2,000 resamples, seed
`20260922`. No gradient reaches the model from any probe.

| probe | classes | **normalised** | clustered 95% |
|---|---:|---:|---|
| **Sampling class** (committed Rung-2) | 55 | **0.28262** | [0.21965, 0.34638] |
| **Behaviour, T13 v2 episode types** (amendment 2 A2.2) | 29 | **0.35874** | [0.30154, 0.41400] |
| **Behaviour, registered T14 fallback** | 25 | **0.39237** | [0.33124, 0.45228] |

| | verdict | margin |
|---|---|---:|
| **Full model, T13 v2 episode types** | **PASS** | **+0.07612** |
| **Full model, registered fallback** | **PASS** | **+0.10975** |
| **Cadence-only floor, T13 v2 episode types — the re-run §3.6 OWED** | **FAIL** | **−0.1373** |
| Cadence-only floor, registered fallback (re-measured here) | FAIL | −0.1289 |
| Cadence-only floor, registered fallback (published, `c62b298`) | FAIL | −0.1305 |

**The re-run §3.6 owed is discharged, and it does not change the floor's verdict.** Registration §3.6
required the gate to be re-run on T13 types when they landed, and §4.1 of the floor results warned that
the fallback target is itself predictable from cadence, so the floor's FAIL might have been an artefact
of a weak target. It was not: on the stronger target the cadence-only embedding fails **harder**
(−0.1373 against −0.1289), because its behaviour probe falls from 0.2289 to 0.2205 while its sampling
probe is unmoved at 0.3578. **The cadence-only embedding carries sampling class and not behaviour, on
both targets, exactly as its positive control required.**

**Reproduction note, published rather than smoothed.** Re-measuring the floor's registered-fallback
behaviour probe with this session's instrument gives **0.2289 [0.1762, 0.2782]** against the committed
**0.2272 [0.1751, 0.2768]** — 0.0017 apart, far inside both intervals, and attributable to the linear
solver's tolerance under a different BLAS thread count. Every other floor quantity re-measured here
reproduced to the published digits: the passive null's 0.000557, the routine keepers' 0.005244, the
ratio 9.415, the dispersion 6.900 and the sampling probe's 0.3578.

**The gate reverses, and it reverses on both targets.** On the cadence-only embedding the sampling probe
scores **0.3578** and the fallback behaviour probe **0.2289**; on the full model's embedding the
sampling probe falls to **0.28262** and the same fallback behaviour probe rises to **0.39237**. Every
figure in this section is from the artefact this document publishes, `docs/t18-full-20260922.json`, and
§8 publishes the ~0.003 run-to-run drift the probe fit carries — twenty times smaller than the margin,
and published rather than hidden behind a rounding. The
registration made this a **hard fail** — an embedding whose sampling probe beats its behaviour probe is
not published — and it is the one place in this track where the full model clears a registered bar.
**It is not in the falsifier, and it does not rescue the track.**

### 6.1 Is the behaviour probe reading ERA rather than behaviour?

It is the obvious objection and it deserves a number rather than a reassurance. The behaviour target is
`regime × era × bus family`, it contains an era term, and the floor results measured that the
fit-latency channel is very nearly a clock — **Pearson −0.9577 against epoch**. An embedding that can
read the calendar can read part of that target without knowing anything about behaviour.

**The control is already in the table, and it bounds the objection without answering it.** The
cadence-only model reads the *same* fit-latency channel, so era is exactly as **legible** to it; its
behaviour probe scores **0.2289** against the full model's **0.3924**. So the 0.1635 the full model adds
**is not explained by unequal access to the clock channel.** That is weaker than "cannot be era": being
shown a channel is not the same as encoding it, and a training objective that rewards predicting the
residual may well encode the clock more strongly than one that does not.

**The decisive control was not run, and it is named here rather than left implicit.** The fallback target
is `regime × era × bus family`; the number that would settle this is the probe's accuracy on the **era
marginal alone** against the **regime marginal alone**, on both embeddings. It is not measured, so the
honest statement is the bounded one: **unequal access to the clock does not explain the gap, and how
much of the gap is era remains UNMEASURED.**

### 6.2 The T13 re-run is owed a stronger version, and this says so

§3.6 required the gate to be re-run on T13 episode types when they landed. They have, as v2 (`c2e0b9d`),
and the re-run is above. **It is only nominally a re-run.** Of 2,380 test windows, **76 (3.19%)** carry a
real T13 v2 episode type; of 8,055 training windows, **83 (1.03%)** do. **The T13 target is therefore
96.8% the T14 fallback target**, and the two verdicts differ mostly because the T13 arm has four more
classes and a different majority rate. Both clear gate G7's bar of 20 supporting windows, and both are
published, and **neither is a gate against a complete typing.**

The reason is registered in amendment 2 A2.2 and is a property of the committed artefact, not a
discovery: the v2 ledger is a **subset** — every burn that matched another instrument's label plus a
seeded uniform sample of the rest, **10,326 rows of a full table of 3,914,621** — so which windows carry
a type is biased toward windows another instrument also flagged. **Gate G against a complete T13 typing
remains UNPROVEN.**

### 6.3 G5 — the leakage audit, published rather than asserted

Cosine similarity of a frozen test-window embedding to its nearest training-partition neighbour:

| quantile | full model, test → train | cadence floor, test → train |
|---|---:|---:|
| p5 | **0.9241** | 0.7135 |
| p25 | 0.9788 | 0.9481 |
| p50 | 0.9906 | 0.9901 |
| p95 | 0.9991 | 0.9984 |

The full model's test windows sit **closer** to the training set than the floor's did, and the long low
tail the floor's distribution carried is largely gone. **That is the distribution, and it is published;
it is not asserted to show the split worked.** These are 128-dimensional embeddings of objects most of
which are sampled on similar schedules, so the audit bounds *representational* overlap and does not
certify the split on its own. The split's disjointness is what the tests assert, on cases built to
contain the leak.

---

## 7. The falsifier fired, on all three clauses

Registration §0, verbatim:

> **"The learned model adds information" is FALSE if, at matched false-flag rate, its recall lower bound
> does not exceed the shipped detector's upper bound; AND the forecast non-inferiority clause fires; AND
> the anomaly score's flag rate is not separable from Rung-2 sampling class. If all three hold, T18 is a
> fail-record, the numbers are published, and the track closes.**

| clause | measured | holds? |
|---|---|:--:|
| recall lower bound does not exceed the shipped detector's upper bound | **4.444%** against **9.656%** | **YES** |
| the forecast non-inferiority clause fires | the error **increases at every one of the five registered horizons** (+0.94, +4.73, +23.42, +52.45, +99.50 km) | **YES** |
| the anomaly flag rate is not separable from Rung-2 sampling class | p90/p10 = **28.195** across sampling classes | **YES** |

**ALL THREE HOLD. T18 IS A FAIL-RECORD. The numbers are published here, no clause of the registration
has been rewritten to rescue the track, and the track closes.** The `gpu-consumers.json` row
`space-t18-learned-model` is retired in the same change, as §5 requires.

**Gate G passing does not change this.** The falsifier names three clauses and the geometry gate is not
one of them; a gate that says *the embedding is publishable* is not a claim that the model adds
information, and this document does not convert it into one.

---

## 8. Gates

| Gate | Verdict |
|---|---|
| **E1 screen** | **DOES NOT CLEAR** — 4.444% lower bound against the shipped detector's 9.656% upper bound at a matched (in fact stricter) false-flag rate |
| **E1c** | **FAILS** — increment above the floor +0.529 points, paired clustered 95% [−1.205, +2.366], lower bound **not** above zero. Registration §3.2: failing means the model measures the sampling schedule |
| **E1 reversal clause** | **FIRED** — three bins reverse against the shipped detector (100–200 m, 200–500 m, ≥500 m), so **the pooled claim is WITHHELD and the reversal is the result**. The 200–500 m bin reverses against the cadence-only floor as well |
| **E2 screen** | **FAILS on both clauses** — no reduction at +30 d (the error rises 23.417 km) and an increase at every one of the five registered horizons |
| **G-E2-placebo** (amendment 1) | Does **not** fire — the 180-day-shifted arm does not gain. It rescues nothing: the real arm does not gain either |
| **G-E2-manoeuvre-free** (amendment 1) | No gain to hold at +7 d or +14 d, and **UNMEASURABLE at +30 d and beyond** — the control is unmeasured at the horizon the headline screen reads |
| **E3 ratio** | **FIRES** — 10.666 against a registered 3.0, and **above the floor's 9.415**. Regime-matched: 3.310, still above 3.0 |
| **E3 dispersion** | **FIRES** — 28.195 against the floor's 6.900 (difference −21.295 [−115.00, −2.858]) and the shipped detector's 3.433 |
| **G1 geometry probe** | **PASS**, margins +0.0761 (T13 v2 types) and +0.1097 (registered fallback). The floor FAILED it, which was its positive control discharging. Not in the falsifier |
| **G2 cadence floor** | Applied — every number is printed as an increment above 5.115% with the floor beside it |
| **G3 negative control** | **NOT DISCHARGED.** No interval rate is published here that carries `sufficientToLabel`'s four conditions — a passive control of ≥ 200 intervals, a passive Jeffreys upper bound below 0.001, a payload excess at p < 0.01 and 10× bound separation. Nothing here is published as an interval rate, and nothing reaches a page |
| **G4 label shuffle** | **DISCHARGED** — the gap-permuted arm falls from 5.644% to 0.882%, and what survives is accounted for by the independently measured placebo density of 0.998% |
| **G5 leakage** | **DISCHARGED** — the nearest-neighbour distribution is published, not asserted |
| **G6 routine operations** | **FAILS** — routine keeping scores anomalous at 10.666× unmatched and 3.310× regime-matched, both above 3.0. §3.4: the anomaly claim is **withdrawn, not rescaled** |
| **G7 underpowered** | Applied — HY-2A's 0/58 and 2/58, the 8 recoverable T3 carriers, the routine-keeper dispersion and every stratum below 20 supporting events lend their names to nothing |
| **G8 detector untouched** | **DISCHARGED** — `proximity_plane.detect_manoeuvres` is imported and called at shipped settings, never edited, and the baseline is quoted from T16(b)'s committed JSON |
| **§6 capitulation ledger** | One row per adversarial pass in `docs/t18-capitulation-ledger-20260922.jsonl`; no pass may run without it, and the prompt must carry the registered sentence verbatim |
| **§8.3 publication fence** | **NOT DISCHARGED, and nothing is wired.** No output has a replay-measured precision, so nothing reaches any page and the clause is WITHHELD in the page's own words |

**Reproducibility, measured not claimed — and one part of it does NOT reproduce.**

The E1/E3/G measurement was run three times: once, then again after two instrument defects were fixed,
then a third time after four artefact defects were fixed (§10). **The matched threshold, the pooled
recalls, every burn-size bin, the E3 rates and both ratios, the dispersion and both gate-G verdicts
reproduced exactly across all three.** The two E1 cells the first fix touched changed, as they were
meant to.

**The probe fit does not.** The linear probes moved between runs without any change to their inputs:
the sampling probe by **+0.0006** and the T13 behaviour probe by **−0.0033** in normalised units,
eight minutes apart on the same host, from the same frozen embedding and the same seed. The earlier
suggestion that the floor's 0.0017 drift was a BLAS thread-count effect does not survive that — the
honest statement is that **the probe's linear solver is not bit-reproducible under a fixed seed at this
tolerance, and the observed run-to-run drift is about 0.003 in normalised units.** Gate G's margin is
**+0.0722**, roughly twenty times that drift, so the verdict is not at risk; the drift is published
because a number that moves is a number a reader must be told moves.

The new instrument reproduces the committed floor's **published** numbers on the identical population —
0.000557, 0.005244, 9.415, 6.900 and a sampling probe of 0.3578 — which is what makes the comparison a
comparison rather than two numbers from two programs.

---

## 9. What these numbers may not be used for

- **The labels are ELEVEN GEODETIC AND ALTIMETRY SPACECRAFT, not constellations** — CryoSat-2,
  Sentinel-3A, Sentinel-3B, Jason-1, Jason-2, Jason-3, SWOT, SARAL, HY-2A, TOPEX/Poseidon,
  Sentinel-6A.
- **No figure here is "the model's recall"** without the qualifier *on this labelled set, these eleven
  geodetic and altimetry spacecraft, these burn sizes*.
- **Nothing here says anything about Starlink, about any constellation, or about any operator whose
  manoeuvre log is not public.** MAD-LEO's Starlink subset carries no manoeuvre labels at all — its
  authors state it is operator *prediction*, "never maneuver ground truth". **A constellation-class
  labelled baseline remains UNMEASURED.**
- **Eleven cooperative, exceptionally well-tracked spacecraft are not a census.** Precisely what makes
  them measurable — large, tracked by GNSS/DORIS/SLR, small frequent planned burns — makes them
  unrepresentative.
- **Recall and precision measured on different populations do not compose.**
- **E2 is measured on two or three spacecraft.** An object-clustered interval over two clusters is
  nearly uninformative; it is published as measured and never narrowed by pooling origins as if they
  were independent. Sentinel-1A's interval is degenerate by construction — one cluster — and every
  Sentinel-1A cell says so.
- **Every threshold here is a chosen screen, not a physical law**: the 1% E3 false-alarm fraction, the
  ratio of 3.0, the 200-window exposure bar, the 20-event underpowered bar, and the matched operating
  point itself.
- **The E2 correction rests on one derived relation**, `δn = −(3/2)(n/a) δa` and its integral, which is
  two-body and is derived in the registration rather than cited. It is a derivation, not a law of this
  archive, and the failure of the correction is a failure of the *predicted rate*, not of that algebra.

---

## 10. Deviations, and unproven items in those words

### Deviations from the registration

1. **Two amendments were committed ALONE before any full-model number existed** — `91ceede` (the
   regime-matched control, the T13 v2 behaviour target, the E2 construction, the bootstrap cluster and
   the ablation-set dispositions) and `ffb97d6` (the label-shuffle construction, the GEO-pool
   operationalisation, the fixed dispersion class set, the two unrunnable comparators and the headline
   checkpoint). The commit history carries the ordering; neither lowers a bar.
2. **The broker claim was 2,048 MiB, not the registered ceiling of 4,096**, as in the floor run. The
   ceiling is a maximum, 2,048 is inside it, the measured peak was 796 MiB, and the process binds its
   own allocator to its claim so an overrun fails this process and never the card.
3. **Two defects in this session's own instrument were found and fixed BEFORE publication**, and the
   whole measurement was re-run:
   - the smallest burn-size bin was quoted under a key `truthset_recall.bin_of` does not produce, so
     the reversal clause compared that bin **against nothing** and read as silence rather than as a
     comparison;
   - the label-shuffled arm's paired increment was computed against the **real-label** floor, which
     matched 22 of 1,134 keys because shuffling moves the event times; it is now paired against the
     floor on the same shuffled labels.
   The re-run is also the reproducibility check: the matched threshold, the recalls and the gate
   verdicts reproduced.
4. **The `no-adversary` ablation is OUT OF REGISTERED SCOPE** and the weak-label pre-training arm is
   **NOT RUN**, both fixed in amendment 2 A2.5 before any number. §4 of the registration specifies an
   architecture with no adversary at all, so every T18 model already *is* the no-adversary arm; and no
   weak-label auxiliary target entered any training run, so §2.5(ii)'s "both with and without" never
   triggers.
5. **The T3 routine population and the T14 comparator are UNMEASURED** for the reasons §5.2 gives, both
   checked against the committed record in amendment 3 A3.4 before any number.
6. **The regime-matched pool is selected on each object's first element set**, with the extractor's own
   median-based regime published as a disagreement count (4 of 75). Amendment 3 A3.2.
7. **A post-registration diagnostic was added to E2** to explain why the correction loses — the
   correlation between the predicted and observed `dA_km` rate — and is labelled post-registration
   wherever it appears. It changes no registered construction and no number.
8. **Sentinel-1A is published as a separate labelled arm** and never enters an E2 headline, because its
   split partition is `train`. It was not among the 1,998 objects the training extraction drew, so no
   element set of it entered any batch — **unseen in fact, not held out by construction.**
9. **Four artefact defects were found by the registered adversarial pass and fixed before publication**,
   and the measurement was run a third time: the E1 sweep was decimated and **did not contain its own
   chosen operating point**, so a reader checking the registered tie-break against it landed on the
   wrong threshold; the dispersion cell reported its *usable* draw count under the field name the
   registered resample count uses; the checkpoint hash was `null` in every artefact, because the
   trainer fills that field only after `torch.save` has already written the bytes; and the artefact's
   `amendments` block listed two of the four amendments it implements.
10. **The Gate G probe was fitted more than once on this split.** §3.6 says the gate is evaluated once
    and a second probe fit after seeing the first is forbidden. What happened here is a **defect re-run,
    not a retry**: the instrument was re-run whole after defects elsewhere in it, the probe was not
    altered between runs, no threshold or target was changed after seeing a verdict, and the verdict
    was PASS on every run. It is recorded as a deviation rather than argued away, and §8 publishes the
    drift the re-runs exposed.
11. **The registration's own §2.1 describes the residual sign backwards.** Its words —
    "propagate to `epoch_{i+1}`, and difference against set `i+1`" — read as *predicted − observed*,
    while the instrument computes *observed − predicted*, which is what every downstream clause needs.
    Amendment 2 A2.3, committed before any E2 number existed, states the convention correctly: *the
    residual is signed (new fit) − (propagation of the previous fit)*. So the ambiguity was registered
    away in advance and no number moves; it is recorded here so the E2 sign question is closed on the
    record rather than on a reader's re-derivation.
12. The departures already registered in advance — burn-size **bins** rather than deciles, and the split
    artefact committed with the instrument — were applied as written.

### Unproven items, in those words

- **The 2× stop rule is UNPROVEN against a real overrun.** It was exercised on a fixture — a synthetic
  0.05 steps/s re-pricing the campaign to 1,335.3 GPU-hours and returning `stop: true` — and in the
  live run it was evaluated and did not fire, because 8.064 GPU-hours is not above 240.
- **Gate G against a COMPLETE T13 typing is UNPROVEN.** 76 of 2,380 test windows and 83 of 8,055
  training windows carry a real T13 v2 episode type, so the T13 target is 96.8% the registered
  fallback, and the committed ledger is a seeded subset biased toward burns another instrument also
  flagged.
- **The A2 arm's matched operating point is UNVERIFIED at this exposure** — two flags over 331.25
  post-`T_cut` quiet window-days.
- **The T14 comparator is UNMEASURED**, and §3.4's "if T14 wins, the learned score is withdrawn"
  **cannot be discharged**.
- **The T3 14.00 d carrier population is UNMEASURED**, not zero.
- **The routine-keeper dispersion is UNMEASURED** at this exposure, not zero.
- **The weak-label pre-training arm is NOT RUN** and is UNPROVEN; **an adversarial arm is NOT RUN** and
  is out of registered scope.
- **The manoeuvre-free E2 control is UNMEASURABLE at +30 d and beyond** — T16(b) measured n = 0 there
  and Sentinel-1A has no fetchable manoeuvre notice — so **the manoeuvre-free control is unmeasured at
  the horizon the headline screen reads.**
- **A constellation-class labelled baseline remains UNMEASURED.**
- **No replay-measured precision exists for anything here**, so §8.3's publication fence is not
  discharged and nothing reaches any page. Nothing is wired to anything.
- **Every step rate in this document is a lower bound, not a clean rate**, because the card and the host
  were co-tenanted throughout.
- **How much of the Gate G behaviour probe's advantage is ERA rather than behaviour is UNMEASURED.**
  The control that exists bounds the objection — unequal access to the clock channel does not explain
  the gap — but the decisive comparison, the probe's accuracy on the era marginal against the regime
  marginal, was not run.
- **The probe's linear solver is not bit-reproducible under a fixed seed at this tolerance.** The
  measured run-to-run drift is about 0.003 in normalised units against a Gate G margin of +0.0722.
- **The E2 construction was never calibrated**, and a shrinkage step is the thing a later track would
  register first. That it would have helped is UNPROVEN: it was not run, because proposing it after
  seeing the numbers is hindsight.

---

## 11. What this closes, and the one thing worth carrying forward

1. **The track closes on its own falsifier.** Three clauses, all measured, all holding. The detection
   claim, the forecast claim and the anomaly claim are all withdrawn, and the registry row is retired in
   this change.
2. **The artefact floor did its job.** Without it, 5.644% recall against a rules baseline of 7.937%
   would have read as "close, and improving with scale". Against the floor it reads as **+0.529 points,
   interval straddling zero, not demonstrated** — six labels of 1,134 over a model that was shown no
   element value at all. **A floor measured before the headline is the difference between a null result
   and a promising one.**
3. **Adding the physics made the statistic more geometry-driven, not less.** 28.2× dispersion against
   the floor's 6.9× and the rules' 3.4×. That is the single most transferable finding here, and it is
   the opposite of what the design expected.
4. **Two thirds of the "routine keepers look anomalous" signal was regime.** 10.67 unmatched, 3.31
   matched. The owed control was worth running and it still does not clear the screen.
5. **The embedding is the exception, and it is worth carrying forward.** Gate G reverses — sampling
   0.3578 → 0.2826 and behaviour 0.2272 → 0.3924 — so a representation trained on the residual channels
   really does carry more about what an object is than about how often it was sampled. Nothing read off
   it beat anything; that is a statement about the read-outs, not about the representation. **Any future
   track that wants to use it owes a stronger Gate G than this one: a complete T13 typing, not a 3%
   sample.**
6. **The 30-minute mark earned its place.** It re-priced the campaign upward by 79% the moment it was
   taken on the model that mattered rather than on the cheap positive control.
