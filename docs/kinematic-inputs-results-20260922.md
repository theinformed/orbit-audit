# M0, M1, M2 results — the kinematic inputs of the reach layer

Measured 2026-09-22 on `pc`, CPU only, `nice`-d. Registration:
`docs/kinematic-inputs-preregistration-20260922.md`, committed **alone** at
`3f8bcab` before any measurement code existed; the instrument and its 42 tests
followed at `e4873ce`. The ordering in `git log` is the evidence. Every
threshold below was fixed in that registration and none was changed after a
number existed.

Artifacts: `docs/kinematic-inputs-20260922.json` (every number with its n),
`docs/kinematic-inputs-m2-phase-20260922.jsonl` (1,295 per-object rows),
`docs/kinematic-inputs-20260922-receipt.json` (provenance, input sha256s,
wall and CPU seconds per stage). Wall clock actually observed: M0 4.1 s,
M1 271.0 s, M2 78.6 s.

**Framing, restated because it constrains this document.** No propellant, mass
or consumables figure is read, computed or published for any object; the
delta-v figures below are the exact-minimum impulses the committed ledgers
already carry, or element-unit quantities converted by a two-body relation
labelled *derived* at every appearance. No registry or country code enters any
row. No figure here is a miss distance, and nothing here states an intent.

---

## 0. The three answers, in one line each

| | Answer | What it changes |
|---|---|---|
| **M0** | six classes tabulated, five powered and one **blinded**; the next-burn size spans 0.016 °/day (routine GEO drift change, median) to 371 m/s (transfer leg, median) | `withinClassRange` is computable for C1–C5; the LEO plane class supplies no B and must print a labelled gap |
| **M1** | the forward error grows **0.408° → 1.076° → 1.520° → 2.651°** (median) at +30/60/90/180 d; it passes the co-location threshold at **+15 d**, the measured slot spacing at **+30 d**, and **Gate W's own 2.0° bar at +180 d** | the design's horizon is cut: membership is resolvable to **+20 d**, arrival timing to co-location precision to **+10 d**, and the +180 d arm is **unfit by T8d's registered bar** |
| **M2** | at +90 d, **58.2%** of LEO objects with a usable window keep the along-track phase inside Γ = 5° (610 of 1,048; 47.1% of the 1,295 sampled, 247 having no usable window at all) | the LEO phase horizon stays **per object**, as the design said, and the fraction is now a number rather than an expectation |

---

## 1. M0 — class-conditional next-burn size

### 1.1 What the estimand is, and the three truncations it inherits

The estimand is **the size of one burn of a class**, from the committed
ledgers; it is deliberately **not** remaining propellant. Three truncations
were registered before the numbers existed and they govern every reading
below:

1. **Every distribution is conditional on detection.** A class p5 is as much a
   statement about its detector's floor as about its objects. The floor is
   printed in the table beside each class.
2. **The east-west ledger is recall-limited at a measured 1.81%** — its
   detected distribution is over the largest burns only.
3. **Recall of the initiating flag is UNMEASURED, in those words**, for the
   GEO drift-change class: 33% of T8a's events had no visible initiating flag,
   and nothing here estimates the burns the detector did not see.

### 1.2 The table

Quantiles are the registered "smallest value whose cumulative weight reaches
q·ΣW" rule, applied identically to every class. (That is the lower empirical
quantile, not an interpolating one; against T8a's interpolating publication of
the same C1 column the two agree to better than 1% at every quantile.)

| Class | n | p5 | p25 | **p50** | p75 | p95 | unit | floor |
|---|---:|---:|---:|---:|---:|---:|---|---:|
| **C1** relocation stop, GEO | 487 | 0.0131 | 0.0225 | **0.0668** | 0.462 | 1.339 | °/day of drift the stop nulls | 0.010 °/day |
| …derived | | 0.037 | 0.064 | **0.190** | 1.31 | 3.80 | m/s (*derived*) | |
| **C2** any confirmed drift change, GEO | 5,904 rows → **226,422** weighted | 0.0105 | 0.0127 | **0.0156** | 0.0240 | 0.0621 | °/day | 0.010 °/day |
| …derived | | 0.030 | 0.036 | **0.044** | 0.068 | 0.176 | m/s (*derived*) | |
| **C2a** …cluster 1 | 84 rows → 701.5 weighted | 0.0147 | 0.0262 | **0.989** | 2.699 | 7.160 | °/day | |
| **C2b** …cluster 0 | 2,796 rows → 100,309 weighted | 0.0102 | 0.0117 | **0.0140** | 0.0186 | 0.0388 | °/day | |
| **C3** north-south keeping, GEO | 738 on 66 objects | 1.261 | 1.787 | **2.147** | 2.543 | 3.334 | m/s, exact minimum | 5σ_i at the 1e-4° quantum |
| **C4** east-west keeping, detected | 212 | 0.049 | 0.072 | **0.306** | 1.218 | 3.300 | m/s per detected burn | recall 1.81% |
| **C4** …derived per cycle | 834 | 0.029 | 0.056 | **0.084** | 0.110 | 0.159 | m/s per cycle (*derived*) | |
| **C5** transfer legs, informative phases | 217 | 1.72 | 112.8 | **371.1** | 508.9 | 941.9 | m/s per leg, exact minimum | |
| **C5** …all phases | 267 | 1.73 | 102.6 | **335.7** | 503.1 | 1034 | m/s per leg | |
| **C6** LEO phasing campaign, \|δa\| implied by the campaign's peak phase rate | 71 | 1.15 | 5.93 | **26.55** | 44.05 | 132.5 | km | 0.050 km |
| **C6** …derived | | 0.61 | 2.90 | **12.88** | 21.12 | 75.19 | m/s (*derived*, da = 2 dv/n) | |
| **C6** …median \|δa\| during the dwell | 71 | 0.0 | 0.0028 | **0.0065** | 0.0143 | 0.184 | km | |
| **C6i** LEO plane change in a campaign | 71 events, **0** plane manoeuvres | — | — | **BLINDED CHANNEL** | — | — | — | 3.5° threshold |

**Per bus family (C3a), with the power rule applied row by row:**

| Bus family | n | p5 | p50 | p95 | verdict |
|---|---:|---:|---:|---:|---|
| EUROSTAR-3000 | 335 | 1.288 | **2.153** | 3.200 | powered |
| SPACEBUS-4000 | 145 | 1.305 | **2.097** | 3.180 | powered |
| A2100 | 105 | 1.190 | **2.041** | 2.970 | powered |
| SSL-1300 | 84 | 1.521 | **2.242** | 4.085 | powered |
| HS-601 | 27 | 0.893 | **1.652** | 2.711 | powered |
| BSS-702 | 19 | 0.940 | 2.437 | 2.839 | **UNDERPOWERED** |
| LM 2100 | 11 | 1.381 | 2.214 | 2.448 | **UNDERPOWERED** |
| EUROSTAR-2000, GE ASTRO 5000, HS-376, HS-389, LOCKHEED MARTIN 7000, SPACEBUS-3000 | 3, 3, 2, 1, 1, 2 | | | | **UNDERPOWERED** |

Seven of thirteen bus families are underpowered and supply no B. A bus with
fewer than 20 events borrows nothing from another bus and nothing from the
pooled C3 figure; `withinClassRange` for such an object falls back to the
pooled class or prints "class range not measured", never to a neighbour's p95.

### 1.3 The weighting worked, and the cross-check says so

The committed trigger subset is enriched — every positive plus a uniform
sample of the rest — so unweighted quantiles over it would describe the sample.
Weighted per the registration (1.0 for a positive, 45.1036 for a sampled
other), and cross-checked against the full 226,422-row table **after asserting
its committed sha256 `f4c3ca9b…`**:

| | p5 | p25 | p50 | p75 | p95 |
|---|---:|---:|---:|---:|---:|
| weighted committed subset (governing) | 0.01054 | 0.01268 | **0.01560** | 0.02398 | 0.06213 |
| full table, 226,422 rows (cross-check) | 0.01055 | 0.01265 | **0.01580** | 0.02422 | 0.06604 |

Agreement is 0.1% at the median and 5.9% at p95, which is the sampling error of
5,000 draws in the tail and not a defect. The weighted total recovers 226,422
exactly. **Where the weighting is visibly strained is C2a:** 84 cluster-1 rows
weight to 701.5 against the full table's 822, a 15% shortfall — the tail of a
small enriched stratum. C2a's quantiles are reported and its weighted count is
printed beside them so the strain is visible rather than hidden.

### 1.4 What M0 says about the design's budget prior B

- **B is not one number.** The class-conditional p95 spans three orders of
  magnitude: 0.176 m/s for a routine GEO drift change, 3.33 m/s for a
  north-south burn, 3.80 m/s for a relocation stop, 75 m/s for a LEO phasing
  campaign, 942 m/s for a transfer leg. Reading a candidate against the wrong
  class's p95 would change its `withinClassRange` verdict by a factor of
  5,000. **The class assignment is therefore load-bearing and it is T13's job**,
  which is not registered yet: until it is, the design's §2.6 field must name
  which class it priced against, on the row.
- **C2's p95 is 0.0621 °/day — 0.176 m/s.** That is the budget prior for "a
  confirmed drift change of no further known type", and it is *tiny*: at GEO it
  reaches 0.176 × 0.3522 = 0.062 °/day of drift, which over a 20-day resolvable
  horizon (§2) sweeps 1.2° of the belt. Against a measured median slot spacing
  of 0.394° that is about three occupied longitudes — a reachable set of a few,
  not of hundreds, **if** the class is the routine one.
- **C2a is the class that reaches.** Its median is 0.989 °/day, seventy
  times C2b's, and its p95 is 7.16 °/day. That is the class-1/class-0 split
  T8d found, priced.
- **C6i supplies nothing and must not be read as zero.** No arm-M campaign
  carries a single detected plane manoeuvre, because T8b's plane threshold is
  3.5° — a consequence of the registered σ_θ coming back 145× too large, not of
  the objects. The design's LEO cross-plane arm stays blocked on M6 exactly as
  §2.3 said.
- **C6's two δa columns are four thousand times apart and both are right.**
  The campaign's peak implies a median 26.55 km of semi-major-axis offset; the
  median offset *during the dwell* is 6.5 m. A phasing campaign is a large
  offset flown for weeks and then removed — the burn size and the residue are
  different quantities and the layer needs the first.

---

## 2. M1 — the forward error beyond +30 d

### 2.1 Gate K1: the instrument reproduced its published figure

Re-measuring at `check_days = 30` returned **n = 49,318** and a median of
**0.40836°** — the published 49,318 and 0.408°. Gate K1 passes, so the
longer-horizon figures may stand beside it.

### 2.2 Arm A — each horizon on its own qualifying set

This is the governing arm: a live alert is exactly a trigger with no further
flag yet.

| horizon | n | p50 | p75 | p95 |
|---:|---:|---:|---:|---:|
| +5 d | 158,758 | 0.0365 | 0.0897 | 0.551 |
| +10 d | 131,987 | 0.0817 | 0.203 | 0.865 |
| +15 d | 96,631 | 0.1406 | 0.356 | 1.183 |
| +20 d | 73,970 | 0.2027 | 0.485 | 1.441 |
| **+30 d** | **49,318** | **0.4084** | **0.8982** | **2.080** |
| +45 d | 33,720 | 0.8154 | 1.592 | 2.653 |
| **+60 d** | **24,373** | **1.0762** | **2.074** | **3.720** |
| **+90 d** | **15,664** | **1.5197** | **3.862** | **7.345** |
| +120 d | 11,501 | 1.9244 | 6.306 | 12.34 |
| **+180 d** | **6,882** | **2.6514** | **12.06** | **25.77** |

The qualifying set shrinks by 23× from +5 d to +180 d, which is the whole
reason the registration demanded a second arm.

### 2.3 Arm B — the matched cohort, n = 6,193 at every horizon

The 6,193 triggers that qualify at *all four* primary horizons, re-measured on
that one fixed set. The run asserted that `validate_propagator` accepted every
cohort member at every horizon (`selectorAgreesWithInstrument: true`), so the
cohort selector cannot have disagreed with the instrument it selects for.

| horizon | p50 | p75 | p95 |
|---:|---:|---:|---:|
| +30 d | 0.4811 | 1.039 | 2.597 |
| +60 d | 0.9532 | 1.879 | 3.423 |
| +90 d | 1.4305 | 3.161 | 6.803 |
| +180 d | 2.5216 | 10.91 | 25.15 |

**The two arms agree to within 18% at every horizon, and the cohort is
slightly *worse* at +30 d than the full set (0.481 vs 0.408).** The growth is
therefore a property of the propagation and not of which objects stayed quiet
— the confound the second arm was registered to catch did not materialise, and
that is itself the finding. Growth from +30 d to +180 d is 5.2× on Arm B and
6.5× on Arm A, against the √-of-nothing and the H² a constant acceleration
would give; the error is not noise growing, it is behaviour accumulating.

### 2.4 The slot spacing, measured — and the crossings

At the archive's final element epoch, **538 objects** were stationed by the
lane's own eligibility proxy (current set inside the merge window, ≥ 30 d of
history, |ḋ| ≤ 0.020 °/day). The gaps between adjacent occupied longitudes on
the wrapped belt:

| p5 | p25 | **p50** | p75 | p95 | max |
|---:|---:|---:|---:|---:|---:|
| 0.0099° | 0.155° | **0.394°** | 0.905° | 2.005° | 11.0° |

**This is a description of today's belt, not a regulatory slot plan and not a
physical constant.** It moves as the belt fills.

| Screen | Value | First horizon whose Arm A **median** exceeds it |
|---|---:|---:|
| co-location tolerance (T8a X_primary) | 0.100° | **+15 d** |
| measured median slot spacing | 0.394° | **+30 d** |
| Gate W's registered bar | 2.000° | **+180 d** |

**Every bar here is a screen, not a law.** None of them says the propagation
becomes wrong at a horizon; they say its error stops being small compared with
the quantity the layer wants to resolve.

### 2.5 What this changes in the design, applied and not merely computed

Applying the registration's own rules to these numbers:

- **The reachability horizon H is +20 days**, not the 90 d (class 1) or 158 d
  (all triggers) class-p95 arrival the design drew the set to. Beyond +20 d the
  median forward error exceeds the median gap between occupied longitudes, so
  the propagated path cannot distinguish one candidate longitude from the next:
  the *membership* of the reachable set, not merely its timing, is unresolved.
- **Arrival windows may be stated to co-location precision only to +10 days.**
  At +15 d the median error is already 1.4× the 0.1° tolerance the estimand is
  defined at.
- **The +180 d arm is unfit by T8d's own registered bar.** The Arm A median of
  2.651° exceeds Gate W's 2.0°. The design's §2.7 discussion of the operating
  table at horizon 180 d, and the runbook's 180 d rows, are computed on a
  geometry whose own gate fires there. That does not invalidate the committed
  T8d table, whose Gate W was registered and discharged **at +30 d**; it means
  the *reach layer* may not use the +180 d horizon, and the alarm lane's 180 d
  operating points should print the forward error at their own horizon beside
  the alert count.
- **The site ribbon reconciles, and extends — with a caveat the design did not
  have.** `docs/orbits-section-design-20260922.md` §2.2 draws the GEO ribbon at
  the measured p50/p75/p95 to +30 d and hatches everything beyond as "error not
  measured beyond 30 days". That hatching may now be replaced by measured
  bands at +45/60/90/120/180 d from the Arm A table. **But the path itself
  should still stop at +20 d**, because beyond that the ribbon is wider than
  the belt's own slot spacing, and a ribbon that covers several occupied
  longitudes invites a reader to conclude a reach the geometry cannot support.
  Drawn honestly the ribbon *grows past the objects it is drawn among*, and
  that is the picture the section should show.
- **The 0.408° at +30 d is still 22× the element-noise floor** (σ_ḋ · 30 d =
  0.018°), and the ratio worsens with horizon: at +180 d the noise floor is
  0.11° against a measured 2.65°, a factor of 24. The error is what the object
  does next, and no arithmetic removes it — only T6's special-perturbations
  ephemerides would change the sharpness, as the design already says.

---

## 3. M2 — LEO along-track phase-error growth

### 3.1 DECLARED DEVIATION from the registration §4.1, and why

The registration defined the measurand as the error of
u = ω + M propagated at 360·n₀. **That form is dominated by secular terms the
propagation omits** — the J₂ apsidal precession is of order 3 °/day at a 53°
inclination, so it alone contributes hundreds of degrees over 90 days,
regardless of what the object does. Measuring it would have measured the
model, not the object.

The measurement therefore reports **two arms**, and the governing one is the
second:

- **Arm U**, the registration as written. Pooled median error: **79.3°** at
  +30 d, **219.8°** at +90 d, **412.7°** at +180 d. That is the size of the
  omitted secular terms, shown rather than asserted.
- **Arm P**, the governing arm: **360 · ∫₀^H (n(t) − n₀) dt**, by trapezoid
  over the object's own observed mean motion. It is the along-track angle the
  object accumulates *because its mean motion is not what it was*, which is what
  an unmodelled semi-major-axis change or drag produces, and what T8b's own
  model (γ̇ = k(a)·δa) says relative phase responds to. It carries no secular
  term, so nothing common-mode to both objects of a pair enters it, and it
  cannot alias — there is no wrap in an integral.

The deviation is declared here because a registration is a promise about what
will be measured, and changing the measurand after seeing why the registered
one could not work is exactly the move that has to be visible.

### 3.2 Population, and what was rejected

1,295 objects sampled with the registered seed 20260922 from T8b's own detect
stage, all four strata, none failing to return an element series:

| Stratum | eligible | sampled |
|---|---:|---:|
| S-arm-M (every eligible arm-M approacher and target) | 95 | **95 (all)** |
| S-payload (payload, at least one detected manoeuvre) | 11,533 | 400 |
| S-never (T8b's never-manoeuvred control) | 2,161 | 400 |
| S-passive (catalogue-passive, not never-manoeuvred) | 8,143 | 400 |

Windows rejected, counted rather than dropped in silence: **98,116** for an
internal gap over 5 days, **51,618** for no element set within 5 days of the
far end, **25,148** for a detected manoeuvre inside the window, **193** as
`unwrapSuspect` (Arm U only). The dominant rejection is archive sampling, not
behaviour.

### 3.3 Arm P — the measured phase error, by stratum

Per-object median over that object's usable windows; quantiles then taken
across objects.

| horizon | stratum | n | p5 | p25 | **p50** | p75 | p95 |
|---:|---|---:|---:|---:|---:|---:|---:|
| +30 d | S-arm-M | 94 | 0.101 | 0.153 | **0.194** | 0.365 | 58.9 |
| | S-payload | 342 | 0.121 | 0.287 | **0.507** | 0.937 | 29.7 |
| | S-never | 397 | 0.020 | 0.031 | **0.114** | 0.319 | 7.79 |
| | S-passive | 399 | 0.252 | 0.852 | **2.08** | 3.60 | 23.3 |
| | **POOLED** | 1,232 | 0.023 | 0.160 | **0.492** | 2.02 | 24.7 |
| +60 d | **POOLED** | 1,140 | 0.084 | 0.385 | **1.419** | 8.04 | 97.7 |
| +90 d | S-arm-M | 85 | 0.173 | 0.402 | **0.533** | 1.21 | 833 |
| | S-payload | 205 | 0.261 | 0.705 | **1.834** | 8.90 | 309 |
| | S-never | 377 | 0.160 | 0.264 | **0.928** | 2.68 | 64.8 |
| | S-passive | 381 | 2.11 | 7.32 | **17.55** | 31.5 | 182 |
| | **POOLED** | 1,048 | 0.173 | 0.707 | **3.021** | 18.1 | 244 |
| +180 d | **POOLED** | 899 | 0.612 | 1.73 | **11.92** | 70.8 | 1,063 |

**The design's arithmetic survives at the median and fails in the tail.**
Design §2.5 computed 2.0° at 90 d from σ_n alone; the measured pooled median is
**3.02°** — within 1.5× of a noise-only calculation that has no drag in it. But
the same design sentence said the p95 object "loses phase in days", and the
measured p95 at 90 d is **244°** — and already **24.7° at the shortest horizon
measured, +30 d**, five times the Γ = 5° box. So the p95 object does lose its
phase inside the first month; **whether it loses it "in days" is UNRESOLVED**,
because this measurement's shortest horizon is 30 days and cannot see inside
it. The passive stratum carries that tail: median 17.6° at 90 d, outside the
box at the median. Both halves of the design's sentence needed measuring; the
median half now has a number and the p95 half has a bound.

### 3.4 The meaningful-horizon fraction — the headline

A horizon is **meaningful for an object** if that object's median Arm P error
at that horizon is ≤ Γ = 5°, the registered T8b phase half-box. **Γ = 5° is a
registered tolerance, not a physical limit:** an object outside it has not
lost its orbit, it has lost the ability of this propagation to say where along
the orbit it is to the precision a co-orbital station is defined at.

| horizon | objects with a usable window | inside Γ = 5° | **fraction** | of all 1,295 sampled |
|---:|---:|---:|---:|---:|
| +30 d | 1,232 | 1,083 | **87.9%** | 83.6% |
| +60 d | 1,140 | 790 | **69.3%** | 61.0% |
| **+90 d** | **1,048** | **610** | **58.2%** | **47.1%** |
| +180 d | 899 | 335 | **37.3%** | 25.9% |

Objects with no usable window are reported separately and are never counted as
passes: 63 / 155 / **247** / 396 at the four horizons.

**By stratum at +90 d, and this is where the number stops being one number:**

| stratum | usable | fraction inside Γ = 5° | inside Γ/2 = 2.5° | inside Γ = 0.2085° (the tightest registered arm) |
|---|---:|---:|---:|---:|
| S-arm-M | 85 | **85.9%** | 83.5% | 7.1% |
| S-never | 377 | **87.3%** | 72.1% | 21.8% |
| S-payload | 205 | **69.3%** | 58.0% | 3.9% |
| S-passive | 381 | **17.3%** | 6.6% | **0.0%** |

**A 90-day horizon is meaningful for the objects the reach layer would name
and meaningless for most of the catalogue.** The arm-M population — the
objects T8b's own catalogue is made of — keeps 85.9%; catalogue-passive objects
keep 17.3%. A regime-wide LEO horizon would have been wrong in both directions
at once. The design's per-object phase horizon is the right construction and
now has the measurement behind it.

**The stratum comparison is confounded, and the confound is the finding.** The
strata differ in drag as much as in class: median B* is 3.39e-4 for S-passive
against 6.93e-5 for S-payload and 4.12e-5 for S-arm-M, and median |`ndot`| is
1.72e-5 rev/day² for S-passive against 1.16e-6 for S-payload — a factor of 15.
They differ in altitude too, and in the opposite direction (median altitude
854 km for S-passive, 540 km for S-payload, 1,289 km for S-never), so altitude
alone does not explain the ordering and area-to-mass does. **Read the strata as
drag populations, not as behaviour classes:** nothing here says a
catalogue-passive object is intrinsically less predictable than a payload, only
that the objects in that stratum carry five times the drag term. The
per-object gate the design calls for is a gate on the object's own measured
drag, and `ndot` is the covariate that carries it (§3.5).

At the tightest registered arm (Γ = 0.2085°, the 25 km along-track box), the
fraction collapses to 9.2% pooled and **zero** for the passive stratum. That
arm was already labelled below the noise in T8b §2.4; this is the same verdict
from the other side.

### 3.5 The covariates — association, and nothing more

Spearman rank correlation of the per-object +90 d Arm P error against each
covariate, n = 1,048. **No functional form is fitted and no drag model is
built. LEO drag remains unmodelled, and this measurement does not discharge
that.**

| covariate | ρ | what it is |
|---|---:|---|
| `ndot` (Theil–Sen secular dn/dt, T8b's own fit) | **+0.878** | the archive's measurement of the object's drag |
| `bstar` (catalogue B*, median over the window) | **+0.661** | what the element set asserts about drag |
| σ_n (per object, T8b's registered MAD statistic) | **+0.603** | fit-to-fit scatter |

**Drag dominates, and the measured drag beats the asserted drag.** The decile
table makes it plain: median +90 d error rises from 0.73° in the lowest `ndot`
decile to **212.8°** in the highest, monotonically across eight of ten deciles.
The same sweep on σ_n rises from 0.18° to 107° but **breaks monotonicity at
deciles 7 and 10** (0.78° and 2.06°) — σ_n is a noise statistic and at its
extreme it is measuring bad element fits on objects whose orbits are in fact
stable. **σ_n is therefore not a substitute for a drag term**, which matters
because the design's §2.5 LEO sentence is built on σ_n alone.

**One data artifact, named rather than smoothed:** 234 of the 1,048 objects
share a B* of almost exactly 1.0e-4 — a value that piles up in the catalogue,
and piles up hardest in the never-manoeuvred stratum, whose own median B* is
exactly that number — so the B* decile table has one bin of 234 and an empty
bin beside it. The B*
correlation is reported with that artifact visible; `ndot`, which is fitted
from the archive rather than read from the element set, has no such pile-up
and is the stronger covariate.

---

## 4. Gates, discharged

| Gate | Registered meaning | Verdict |
|---|---|---|
| **K1** | M1's +30 d re-measurement must reproduce n = 49,318 and median 0.408° | **passed** (49,318 / 0.40836) |
| **K2** | M0's C2 published only with the full-table cross-check or an explicit statement that it was not performed | **passed** — sha256 asserted, cross-check performed, both columns printed |
| **K3** | n < 20 is UNDERPOWERED in those words and supplies no design input | **applied** — 7 of 13 bus families; no stratum or horizon cell fell below 20 |
| **K4** | a blind channel is a labelled gap, never a zero | **applied** — C6i is a BLINDED CHANNEL and carries no quantiles |
| **K5** | no propellant, mass or consumables figure, registry code, miss distance or never-say word on any output | **passed** — asserted by `tests/test_kinematic_inputs.py` over the emitted rows and over the module's own field accesses |

**42 tests, offline, no archive and no network** (`python3 -m unittest
tests.test_kinematic_inputs`), all OK.

---

## 5. What remains UNMEASURED, in those words

- **Recall of the GEO initiating flag is UNMEASURED.** 33% of T8a's events had
  no visible initiating flag; M0's C1 and C2 describe the burns the detector
  saw.
- **The east-west per-burn distribution is recall-limited at 1.81%** and
  describes the largest burns only; the design's derived 0.0675 m/s per cycle
  remains the class's B, with the measured per-cycle median of 0.084 m/s beside
  it.
- **The LEO plane-change size distribution does not exist**, because the
  channel is blind. M6 (the plane-noise floor re-derivation) is still the hard
  dependency the design named.
- **The reachable set's own recall is UNMEASURED** — whether the eventual
  partner is inside R₁ is estimand E4 of the §4 replay, which is M3 and has not
  run.
- **LEO drag is unmodelled.** M2 measures its consequence and correlates two
  proxies with it; it fits nothing and predicts nothing.
- **Nothing here is scheduled.** All three measurements were run to completion
  in the session that registered them, and the wall clocks above are the ones
  actually observed.

---

## 6. Sources

```
docs/kinematic-inputs-preregistration-20260922.md   the registration, 3f8bcab
docs/kinematic-reach-design-20260922.md             sections 2.2-2.6, 8, 9
docs/orbits-section-design-20260922.md              section 2.2, the ribbon
docs/trigger-alarm-results-20260922.md              section 4, Gate W at +30 d
docs/proximity-results-20260922.md                  T8a primary arm, 0.1 deg
docs/proximity-leo-results-20260922.md              sections 2.2-2.5, 3.1-3.3
docs/stationkeeping-efficiency-results-20260922.md  738 on 66; the 1.81% recall
docs/transfer-loss-results-20260922.md              the exact-minimum form
tools/trigger_alarm.py  proximity_geo.py  proximity_plane.py  kinematic_inputs.py
```

Derived here and labelled as such at every appearance: the 45.1036 subset
weight; the slot-spacing definition and its measurement; the matched cohort;
the drift-to-impulse and δa-to-impulse conversions; the horizon H = 20 d and
the arrival-precision horizon of 10 d, which are the registration's decision
rules applied to Arm A's table.
