# T11 results: persistent pairs, arrival order and response hazard

Measured 2026-09-22. Registration:
`docs/persistent-pairs-preregistration-20260922.md`, committed **alone** at
`ca7f5f4` before any measurement code existed; the instrument and its offline
proofs followed at `649bac4`; a defect found by reading the first case list
was fixed at `089da4b` and **every number below was re-measured after it**.
The ordering in `git log` is the evidence. Every threshold below was fixed in
that registration and none was changed after a number existed.

Framing, restated because it constrains this document: the instrument is
**ownership-agnostic mathematics**. Catalogue registry codes are metadata
columns on the episode rows, enter no detector decision, and are used here for
exactly one descriptive count. This document contains no per-registry
breakdown and no sentence that attributes a purpose to any measured motion.
The registration's §0 fixes the vocabulary and a test enforces it against this
file, the instrument, the catalogue and the case list. Nothing from T11 was
written to `src/`, `data/`, `public/` or any site surface; publication and
framing for this track is reserved to the operator.

**Read §1.1 before any number in this document.** The estimand is *mean
longitude*, a slot coordinate. **No figure here is a miss distance.**

---

## 0. The registered gates, discharged

| Gate | Registered meaning | Verdict |
|---|---|---|
| **A** | the cadence clause is unmeasurable | Does not fire — **but at 0.3301 rad against a 0.3882 rad bar it is an 85%-of-the-bar pass**, the weakest shape this programme has a name for. §4.1 |
| **B** | the pair detector leaks | **CANNOT BE EVALUATED. The control has ZERO exposure: only 9 near-GEO objects have never tripped the drift-change flag, and no two of them are ever stationed within the screen on the same day. The registered ratio is 0/0.** §2.3 |
| **C** | the null explains the cadence | **FIRES on its second clause** — the control's own phase differences are not uniform (R̄ = 0.0279 against a 0.0110 bar at n = 24,669). **It does NOT fire on its first clause**: the observed R̄ = 0.4324 is 4.0× the control bootstrap's upper bound. §4.2 |
| **D** | underpowered | Does not fire: 1,317 episodes against a bar of 20, and **12 exposed relocation events against a bar of 10 — one event above it**. §6 |
| **E** | arrival order unresolvable | Does not fire: 8.2% censored or tied against a 50% bar. §5 |
| **F** | the input is not T8a's | Does not fire: the extract matches T8a's three published counts exactly. §1 |

**The one-sentence verdict.** Persistent pairs are real and numerous — 1,317
episodes over 239 distinct pairs — their east–west station-keeping cycles
agree far more often than in matched non-co-located pairs (44.1% against
27.7%), and arrival order is resolvable for 91.8% of them with a median gap of
**579 days**; but **the falsifiable claim of the track, E3, is NOT READ**,
because the registered leak check L1 caught the hazard estimator being biased
by a factor of about three *before* any ratio was interpreted, and §6.2
measures the mechanism that does it.

---

## 1. What ran, where, and for how long

| | |
|---|---|
| Host | `pc` (`bigmem-PC`), CPU only, `nice -n 15` |
| GPU | none. The registration declared no GPU stage and none was needed. |
| Input | T8a's committed near-GEO extract, **hash-pinned by its three published counts**: 217,007,154 element sets scanned, 11,626,494 kept, 1,768 objects. Gate F checks all three and stops the run on a mismatch. |
| Archive | `/home/sdegan/space-orbit-history/orbit-history.sqlite3`, read-only with `PRAGMA query_only=1` |
| World build | **50 s** (λ, station segments, σ_n, drift-change flags, relocations) |
| Screen | **3.2 s** — 3,733,646 stationed object-days, 3,574 pairs with any proximity, **2,015 candidate pairs** |
| Detect | **30 s**, seven registered arms from one packed pass per candidate pair |
| Cadence + arrival | **46 s** — 449 cadence-testable episodes, 24,669 control pairs |
| Hazard | **164 s** — 2 outcomes × 4 windows × 1,000 permutations |
| **Total analysis** | **243.5 s, single core** |

**A cross-check of the pinned input, reported because it is the cheapest
possible evidence that T11 is measuring what T8a measured.** σ_n re-measured
by T8a's registered procedure over the identical **3,740,056** consecutive
pairs comes back at **0.0006038533519066339 deg/day** — bit-identical to T8a's
published value.

`build_series` drops objects with fewer than two element sets, so the analysis
runs on **1,652** of the extract's 1,768 objects.

### 1.1 What the estimand is, and is not

λ = RAAN + argument of perigee + mean anomaly − GMST (T8a prereg §2.2): the
classical geostationary **mean longitude**, a slot coordinate carrying no
eccentricity or inclination content by construction.

It is **not** a position and **not** a miss distance. A T11 separation of
0.010° means the two objects' *slots* coincided to 7 km of along-arc
longitude; their physical separation is set by their eccentricity and
inclination vectors, which T11 never reads.

---

## 2. Thresholds, population and the control

### 2.1 The derived thresholds, recomputed and reported

| Quantity | Derivation | Value |
|---|---|---:|
| Longitude acceleration amplitude | T3's committed J22 derivation | 1.7006e-3 deg/day² |
| Deadband half-width at the measured 14.00 d cycle | `Δλ = A T²/16` | **0.0208324°** |
| **`X_pair`, primary** | `2 Δλ` | **0.0416647° = 30.661 km** |
| `X_pair`, tight arm | the same at half the maximum acceleration | 0.0208324° = 15.331 km |
| `X_pair`, loose arm | the same at T3's measured 21.00 d line | 0.0937456° = 69.00 km |
| `X_pair`, T8a arm | T8a's registered primary X | 0.1000000° = 73.59 km |
| **`D_pair`, primary** | T3's `MIN_CYCLES_IN_WINDOW` (4.0) × 14.00 d | **56.00 d** |
| **`φ_lock`** | `2π × 0.865 d / 14.00 d` | **0.3882111 rad** |
| **`W`, primary** | T8a's measured p95 `lead_causal` | **162.7 d** |

**A defect in the registration, reported rather than edited away.** The
registration writes `φ_lock = 2π · 0.865 / 14.00 = 0.388214 rad = 22.244°`.
The radian value is right; the **degree gloss is wrong by 0.0011°** — the
correct conversion is 22.2429°. The implementation encodes the formula, as
T8a's gate-A implementation encoded its formula, and the slip reaches no
decision: 0.0011° of phase is 4e-5 of a cycle. It is recorded because a
registration whose arithmetic is not checked is a registration whose numbers
cannot be trusted, and this programme has paid for that once already
(T8a §2.3, where the formula and the number written beside it disagreed by
10×).

### 2.2 Population

| | count |
|---|---:|
| Objects with ≥ 2 near-GEO element sets | **1,652** |
| Payload class | 1,308 |
| Catalogue-passive class (DEBRIS, ROCKET BODY) | 307 |
| `object_type` null or unknown, excluded and counted | 37 |
| Station segments (T8a §5.3, borrowed unchanged) | **24,698** |
| Stationed object-days | **3,733,646** |
| **`never_manoeuvred`** (zero confirmed drift-change flags over the whole near-GEO history, ≥ 200 element sets, ≥ 365 d span) | **9** |
| … of which payload class | 2 |
| Catalogue-passive objects **not** in `never_manoeuvred` | **300** |

### 2.3 The control this programme learned to build DOES NOT TRANSFER TO GEO, and that is the most consequential number in this document

T8a's §10.3 said, in those words, that the right control "is objects with no
observed manoeuvre of any kind over the relevant span — which includes a large
population of dead payloads. That control must be constructed, not inherited
from `object_type`." T8b constructed it in LEO and it worked perfectly:
**855** payload-class LEO objects had never manoeuvred, and the class returned
**exactly zero** events across 18,792,698 object-days — a gate-B ratio of
0.000 against a bar of 0.10, where T8a's `object_type` control had leaked at
parity (0.9995).

Transposed to GEO with T8a's own registered drift-change flag, that class
contains **9 objects out of 1,652**, and **300 of the 307 catalogue-passive
objects fall outside it**. Pair-exposure-days for the never-manoeuvred class:
**zero** — no two of those nine are ever stationed within the screen on the
same day. The registered ratio is **0/0** and **gate B cannot be evaluated at
all.**

The mechanism is measured, not supposed. T8a's flag threshold is
`max(5σ_n, 0.010 deg/day)`, and with σ_n = 0.0006039 the **derived physical
floor of 0.010 deg/day dominates**. T8d measured what that floor sees at GEO:
a confirmed drift change there is not a rare event but **routine east–west
station-keeping — about six a year per active near-GEO object, 226,422 flag
chains across the archive**. Free libration about a triaxial equilibrium
crosses the same floor given a long enough history, and the near-GEO archive
is long. A class defined as "zero flags over the entire history, with ≥ 200
element sets and ≥ 365 days of span" is therefore, at GEO, close to empty by
construction.

**Stated plainly: the manoeuvre-history control is a LEO instrument. At GEO
the same definition has no exposure, so T11 has no leak-free control for its
pair detector, and every E1 count in this document is a count of GEOMETRY that
T11 cannot independently prove is STATION-KEEPING.** The `x-tight` and
`d-very-long` arms (§3.2) and the cadence clause (§4) are the only evidence
here that bears on that question, and neither is a control.

What is needed is registered as owed work in §10, not attempted in-track: a
GEO never-manoeuvred class defined against a threshold *below* the 0.010
deg/day physical floor, validated before it is used — the T8a §7.2 lesson (a
derivation is not a validation) applied to a control rather than to a bound.

---

## 3. E1 — persistent pairs

### 3.1 Primary arm: `X_pair` = 0.0416647°, `D_pair` = 56.00 d

| | count |
|---|---:|
| **Persistent-pair episodes** | **1,317** |
| **Distinct unordered pairs** | **239** |
| Episodes per pair | 5.51 |
| Episodes with both members payload-class and neither never-manoeuvred | **1,317 (all of them)** |
| Episodes inside T8a's ±3.75° libration flag (recorded, **not** a screen) | **376 (28.6%)** |

**Why 1,317 episodes over 239 pairs.** The registered criterion 1 requires
*one* station segment of *each* member to cover the episode in full. A pair
that holds a slot for a decade is therefore reported as a sequence of
episodes, cut wherever either member's station segment ends — which is
frequently, because a station segment ends at every excursion beyond ±0.3° of
its own median. The pair count is the one to quote for "how many pairs";
the episode count is the one every distribution below is over.

| Quantity | p5 | p25 | **median** | p75 | p95 | max |
|---|---:|---:|---:|---:|---:|---:|
| Dwell (d) | 58.8 | 68.9 | **90.3** | 138.2 | 304.0 | 1,809.8 |
| Median separation during the episode (°) | 0.0055 | 0.0086 | **0.0113** | 0.0148 | 0.0206 | 0.0302 |
| Median separation during the episode (km) | 4.03 | 6.35 | **8.35** | 10.86 | 15.17 | 22.26 |
| Distance of the station from the nearer stable longitude (°) | 1.08 | 2.61 | **19.90** | 55.90 | 80.89 | 89.69 |

The median episode holds the pair within **0.0113° = 8.35 km of mean
longitude for 90 days** — inside one shared station-keeping box, which is what
the derived threshold was built to find. Note the station-longitude
distribution: **a quarter of episodes sit within 2.61° of a stable
longitude**, and 28.6% inside T8a's ±3.75° flag. That flag was falsified by
T8a §7.2 and T11 screens on nothing, but the concentration is reported because
a reader weighing §2.3's missing control should see it.

### 3.2 Registered sensitivity arms

| Arm | `X_pair` | `D_pair` | Episodes | Distinct pairs | median dwell (d) | in ±3.75° |
|---|---:|---:|---:|---:|---:|---:|
| **primary** | 0.0416647° | 56.00 d | **1,317** | **239** | 90.3 | 376 |
| x-tight | 0.0208324° | 56.00 d | 289 | 73 | 74.8 | 88 |
| x-loose | 0.0937456° | 56.00 d | 2,006 | 496 | 104.9 | 575 |
| x-t8a | 0.1000000° | 56.00 d | 2,103 | 535 | 104.7 | 618 |
| d-short | 0.0416647° | 42.00 d | 1,940 | 302 | 70.0 | 546 |
| d-long | 0.0416647° | 112.00 d | 461 | 121 | 166.7 | 136 |
| d-very-long | 0.0416647° | 168.00 d | 223 | 83 | 236.9 | 63 |

Halving the threshold from the derived box to the half-acceleration box costs
**4.6× the episodes**; doubling it from the derived box to T8a's 0.1° buys only
**1.6×**. The catalogue is concentrated *inside* the derived box rather than
smeared across it, which is the shape a shared-station population should have
and a drift-through population should not — but §2.3 is why that is an
observation and not a control.

33,228 candidate runs were rejected at the primary arm for being shorter than
the registered dwell and 2 for failing the occupancy requirement; rejections
are counted at every arm rather than dropped in silence.

### 3.3 The descriptive family split

Registered in §3.4 as **one descriptive count**, from the catalogue name stem,
used to group nothing:

| | episodes | of 1,317 |
|---|---:|---:|
| Same catalogue family (equal name stems ≥ 3 characters) | **776** | 58.9% |
| Different catalogue family | **541** | 41.1% |
| Catalogue registry codes agree | 1,206 | 91.6% |

**The stem is a screen, not a fact about ownership.** It merges distinct
operators flying similarly named buses and splits one operator's differently
named fleets — case 5 and case 8 of §7 are exactly that failure
(`28945 SPAINSAT` with `43228 HISPASAT 30W-6`, and `28946 EUTELSAT HOTBIRD
13E` with `29270 EUTE HOT BIRD 13B (HB 8)`, both called "different families"
by the stem). The registry-agreement count is reported once, here, and is used
in no ranking, ordering, stratification or narrative anywhere in T11.

Read with §5: the median arrival gap is **579 days**, so these are
overwhelmingly not pairs launched together into one slot. They are one object
already stationed and another reaching it much later, and the same-family
majority says that most of the time the later arrival carries the same
catalogue name stem as the object already there.

---

## 4. E1's second clause — matched station-keeping cadence

### 4.1 Whether the members carry the 14.00-day cycle at all

**449 of 1,317 episodes (34.1%) are cadence-testable** — both members'
least-squares amplitude at the fixed 14.00-day frequency has a
single-frequency false-alarm probability ≤ 0.01 against a constant-plus-slope
null model. They cover **114 of the 239 distinct pairs**.

Gate A: the median per-member phase uncertainty is `σ_φ = 0.3300610 rad`
against a bar of `φ_lock` = 0.3882111 rad. **The gate does not fire, at 85.0%
of its bar.** Stated as plainly as that deserves: the instrument resolves a
phase lock, and it resolves it by 15%. Any future arm that widens the
population, shortens the dwell or admits noisier members will cross this bar,
and the clause will stop being measurable before it stops being interesting.

### 4.2 The phase difference, against the non-co-located control

24,669 control pairs were drawn (seed 20260922): both members stationed over
the **identical** window inside one station segment each, separated by more
than `X_pair` at **every** retained epoch of that window, with retained sample
counts within a factor of two of the real pair's.

| | observed (co-located) | control (not co-located) | ratio |
|---|---:|---:|---:|
| Cadence-testable pairs | **449** | **24,669** | |
| Rayleigh mean resultant `R̄` | **0.4324** | **0.0279** | 15.5× |
| Rayleigh p | ≈ 0 | 4.66e-9 | |
| Phase-locked (\|Δφ\| ≤ φ_lock) | 164 = **36.5%** [32.2, 41.1] | 3,554 = 14.4% [14.0, 14.9] | **2.54×** |
| Anti-phase-locked | 34 = **7.6%** [5.5, 10.4] | 3,275 = 13.3% [12.9, 13.7] | **0.57×** |
| **Matched cadence** (either) | **198 = 44.1%** [39.6, 48.7] | **6,829 = 27.7%** [27.1, 28.2] | **1.59×** |
| Near-locked (at 2 φ_lock) | 128 = 28.5% | 6,332 = 25.7% | 1.11× |
| Unlocked | 123 = 27.4% | 11,508 = 46.6% | 0.59× |

**Gate C fires on its second clause and not on its first, and the two mean
different things.**

- **First clause — does the null explain the catalogue?** No. The control's
  bootstrapped `R̄` at the observed sample size of 449 has a 95% interval of
  **[0.0080, 0.1069]**; the observed `R̄` = 0.4324 sits **4.0× above its upper
  bound**. The matched-cadence fraction is **1.59×** the control's and the two
  Wilson intervals are nowhere near overlapping.
- **Second clause — is the control itself uniform?** No, and the registration
  named that as a firing condition. The control's `R̄` = 0.0279 exceeds the
  Rayleigh 5% bar of 0.0110 **at n = 24,669**. The bar scales as `1/√n`, so a
  control twenty times the size of the observation makes a concentration of
  0.028 "significant" while leaving it **15.5× smaller than the observation**.
  The honest reading, and the one this document takes: the estimator carries a
  small amount of manufactured phase agreement, visible only because the
  control is large, and far too small to account for the observation.

The decomposition says where the excess sits: **the locked fraction is 2.54×
the control's while the anti-locked fraction is 0.57× — below it.** The excess
is in-phase agreement, not anti-phase agreement. T11 says nothing about why
either would be flown.

**What a locked category does and does not mean.** Per registration §5.4 a
single episode yields one Δφ, and no individual pair "is" phase-locked. The
per-pair flag in the catalogue is a **descriptive category**. The population
statement — 44.1% against 27.7% — is what the measurement earns. Across
distinct pairs, **67 of the 114 cadence-testable pairs** show matched cadence
in at least one episode.

### 4.3 The registered free-period variant

Refitting each member's own period over T3's measured core half-width
(14.00 ± 0.109 d) and requiring both to land inside the band:

| | fixed frequency (primary) | free period |
|---|---:|---:|
| Cadence-testable episodes | 449 | **487** |
| Rayleigh `R̄` | 0.4324 | **0.2033** |
| Matched cadence | 44.1% | **31.8%** |

**The free-period variant is weaker, and is reported as computed.** Letting
each member find its own best period inside the line's measured width admits
38 more episodes but decorrelates the phases of the ones already there: a
period difference of 0.109 d accumulates a full 2π of relative phase in about
1,798 days, and these episodes are long. The fixed-frequency arm is the
registered primary; no post-hoc preference is being exercised and both numbers
stand.

### 4.4 The per-pair test that does exist

461 episodes are long enough to carry two or more consecutive four-cycle
blocks. Their across-block circular standard deviation of Δφ:

| p5 | p25 | median | p75 | p95 |
|---:|---:|---:|---:|---:|
| 0.048 | 0.341 | **0.805** | 1.310 | 1.839 |

A quarter of the tested episodes hold their relative phase to better than
0.341 rad across blocks — tighter than `φ_lock` itself — and a quarter scatter
by more than 1.31 rad, which is most of a cycle. This is the only per-pair
cadence statement T11 makes, and it has the identical blocking available on
the control pairs.

---

## 5. E2 — arrival order

| | count | of 1,317 |
|---|---:|---:|
| **Order resolved** | **1,209** | **91.8%** |
| Tied inside the resolution limit (`order: unresolved`) | 81 | 6.2% |
| Left-censored (a member's station segment begins at the edge of its element coverage) | 27 | 2.1% |

Gate E does not fire: 8.2% against a 50% bar.

**The resolution limit, registered before the measurement: 1.73 d** —
`max(1.0 d, 2 × 0.865 d)`, from the daily grid's ±0.5 d quantisation and T8a's
measured median near-GEO epoch spacing of 0.865 d. A gap at or below 1.73 d is
recorded as unresolved and excluded from the distribution, never rounded into
an order.

| Arrival gap (d), n = 1,209 | p5 | p25 | **median** | p75 | p95 | min | max |
|---|---:|---:|---:|---:|---:|---:|---:|
| | 22 | 152 | **579** | 1,561 | 3,244 | 2 | 4,468 |

**The median persistent pair is formed 579 days apart, and the upper quartile
more than four years apart.** The 27 left-censored episodes are the size of
the blind spot the registration declared in advance: an object whose station
segment begins at its first near-GEO element set may have been there before
the archive saw it.

The registered secondary arrival epoch — entry to the pair band rather than to
the ±0.3° slot envelope — differs from the primary by a median of **959 days**
for the first-named member (p95 3,445 d). That is not an error: an object
typically reaches its slot long before it comes within half of `X_pair` of the
other object's longitude, and the registration carries both epochs precisely
so that a reader asking *when did it reach the slot* and a reader asking *when
did it come alongside* are not handed the same number.

---

## 6. E3 — the response hazard: **NOT READ**

### 6.1 The leak checks, printed above the ratio as the registration requires

| Check | Registered bar | Measured (primary arm) | Verdict |
|---|---|---|---|
| **L1** — machinery bias | permutation-null median `HR_self` inside [0.95, 1.05] and its 95% interval containing 1.0 | **null median 0.3575, 95% [0.1930, 0.5634]** | **FAILED** |
| **L2** — control selection | the matched controls' counterfactual rate against their own all-archive rate, 95% interval containing 1.0 | **ratio 0.4863, 95% [0.4220, 0.5582]** | **FAILED** |
| **L3** — detector leak (gate B) | never-manoeuvred pair yield ≤ 0.10 × payload-pair yield, per pair-exposure-day | **0 never-manoeuvred pair-days exist; the ratio is 0/0** | **CANNOT BE EVALUATED** (§2.3) |

Per the registered decision rule of §6.5, **E3 is NOT READ.** The ratios below
are printed because the registration requires every arm to be reported in
full. **They are not to be interpreted as a response effect in either
direction.**

| Outcome | W (d) | exposed ev / days | self-baseline ev / days | `HR_self` [95%] | `HR_ctrl` [95%] | null median |
|---|---:|---|---|---|---|---:|
| relocation | 36.1 | 0 / 43,524 | 170 / 760,383 | 0.000 [0.000, 0.383] | 0.000 [0.000, 0.187] | 0.436 |
| relocation | 96.0 | 3 / 115,373 | 167 / 731,807 | 0.114 [0.023, 0.339] | 0.089 [0.018, 0.266] | 0.421 |
| **relocation** | **162.7** | **12 / 191,547** | **159 / 703,903** | **0.277 [0.140, 0.498]** | **0.224 [0.114, 0.400]** | **0.357** |
| relocation | 365.0 | 23 / 404,565 | 151 / 636,974 | 0.240 [0.148, 0.373] | 0.274 [0.171, 0.417] | 0.289 |
| departure | 36.1 | 0 / 43,524 | 3,097 / 760,383 | 0.000 [0.000, 0.021] | 0.000 [0.000, 0.034] | 0.801 |
| departure | 96.0 | 36 / 115,373 | 3,061 / 731,807 | 0.075 [0.052, 0.104] | 0.174 [0.121, 0.243] | 0.619 |
| departure | 162.7 | 100 / 191,547 | 2,991 / 703,903 | 0.123 [0.100, 0.150] | 0.345 [0.279, 0.423] | 0.496 |
| departure | 365.0 | 221 / 404,565 | 2,835 / 636,974 | 0.123 [0.107, 0.141] | 0.457 [0.396, 0.526] | 0.343 |

1,209 resolved arrivals over **164 distinct incumbents**. The matched control
found five matches for 1,125 arrivals, fewer than five for 73, and none for 11
(excluded from `HR_ctrl`, kept in `HR_self`, as registered), drawing on 719
distinct control objects at the primary arm. Intervals are exact conditional
Poisson rate-ratio intervals, inverted from a Clopper–Pearson interval and
computed from a continued-fraction incomplete beta because scipy is not
installed on the host.

L1 fails in the **same direction and by a similar factor at every window and
for both outcomes**, and `HR_self` tracks the null median rather than 1.0.
That is the signature of a structural bias in the estimator, not of an effect.

### 6.2 Why L1 failed — measured, not supposed

Post-registration diagnostic, labelled as such, changing no registered
verdict. Both registered outcomes — a relocation and a station departure — are
defined at a **station segment's end**, so each can happen **at most once per
segment**. A window that starts on a uniformly drawn stationed day is
therefore subject to **length-biased sampling**: it lands inside a long
segment in proportion to that segment's length, and then sits far from its
end. Measured over the 164 incumbents' 3,097 station segments:

| Quantity | Measured |
|---|---:|
| Mean station-segment length | 251.3 d |
| **Median** station-segment length | **71.0 d** |
| Mean segment length **at a uniformly drawn stationed day** | **1,634.8 d** |
| **Length-bias factor** | **6.50×** |
| Mean residual to the segment end from a drawn day | **816.9 d** |
| Mean segment length / 2 (an unbiased draw) | 125.7 d |
| Pooled stationed days per departure | 251.3 d |
| Mean length of the segment **carrying an episode** | **2,388.1 d** (median 2,271) |

The pooled per-day rate implies an outcome every **251 d**; the expected wait
from a randomly drawn stationed day is **817 d**. The ratio, **0.308**, sits
squarely inside the range of permutation-null medians actually observed
(0.289–0.436 for relocation, 0.343–0.801 for departure). **The bias is length-biased sampling -- the waiting-time paradox --
and its size is accounted for.**

A second, smaller bias runs the other way and is also measured: on a synthetic
flat-hazard population where the truth is exactly 1.0 by construction — 400
objects, one move every 300 days, W = 162.7 d — the registered estimator
returns **1.298**, because exposure inside the window is truncated at the
segment end while the event at that end is still counted. The two biases have
opposite signs and in the real population the length bias dominates by a wide
margin.

**The lesson, for the programme rather than for this track: a per-day rate
ratio is the wrong estimator for an outcome that can occur only once per
station segment.** The right one treats the segment as the risk set — a
time-to-event comparison of residual durations, or a comparison stratified on
segment length. The registration fixed L1 as a floor *specifically* so that a
ratio produced by a biased estimator could not be read as a finding, and that
is exactly what happened. This is the T8a gate-B lesson working in advance
rather than in retrospect, and it is the first time in this programme that a
registered leak check has caught an estimator before the number was quoted.

Note also that the registered window `W` = 162.7 d is **short relative to the
incumbents' segments** (mean 2,388 d for the segment carrying an episode).
Whatever E3 becomes, its risk set has to be matched to that scale.

### 6.3 What is *not* claimed

No response effect is claimed, and none is refuted. **E3 is NOT READ**; the
registered FALSIFIED verdict was not reached, because reaching it requires L1
and L2 to have passed. The registration's §6.6 wording for a null result is
therefore **not** used here — it would be a stronger statement than the
measurement supports.

One descriptive fact, carried without a ratio attached: of the 1,209 resolved
arrivals, the first-arrived object had a ≥ 2° relocation inside the registered
162.7-day window **12 times**, and none of the ten highest-ranked cases in §7
is one of them.

---

## 7. E4 — the case list

`docs/persistent-pairs-cases-20260922.md` carries the top 10 by the composite
evidence rank registered in §7 before any number existed — the unweighted mean
of the within-catalogue percentile ranks of dwell, cadence phase agreement,
arrival gap and post-arrival relocation latency — plus every episode above the
99th percentile of that composite (13 of 1,209), with every underlying
measurement beside each row and no interpretation sentences.

| # | a | name a | b | name b | episode | dwell d | median sep ° | Δφ ° | lock | gap d | first arrived | relocation latency |
|---:|---:|---|---:|---|---|---:|---:|---:|---|---:|---:|---|
| 1 | 33436 | ASTRA 1M | 37775 | ASTRA 1N | 2023-04-28 → 2023-12-05 | 220.6 | 0.00964 | −3.4 | locked | 2,594 | 33436 | none in W |
| 2 | 41028 | GSAT 15 | 42815 | GSAT 17 | 2023-05-28 → 2024-01-09 | 226.1 | 0.01146 | −175.5 | anti-locked | 1,780 | 42815 | none in W |
| 3 | 27460 | EUTE 5 WEST A (STELLAT5) | 44624 | EUTE 5W B | 2022-04-21 → 2023-01-04 | 258.7 | 0.01330 | +17.3 | locked | 2,086 | 27460 | none in W |
| 4 | 35362 | MEASAT 3A | 40147 | MEASAT 3B | 2019-07-22 → 2020-04-23 | 275.7 | 0.01032 | −6.7 | locked | 1,542 | 35362 | none in W |
| 5 | 28945 | SPAINSAT | 43228 | HISPASAT 30W-6 | 2021-04-25 → 2021-11-10 | 199.1 | 0.01634 | −164.2 | anti-locked | 1,823 | 28945 | none in W |
| 6 | 35362 | MEASAT 3A | 40147 | MEASAT 3B | 2018-10-28 → 2019-07-20 | 264.4 | 0.01007 | −11.5 | locked | 1,542 | 35362 | none in W |
| 7 | 42747 | GSAT 19 | 44035 | GSAT 31 | 2023-12-20 → 2024-06-11 | 174.0 | 0.01103 | +5.6 | locked | 1,735 | 42747 | none in W |
| 8 | 28946 | EUTELSAT HOTBIRD 13E | 29270 | EUTE HOT BIRD 13B (HB 8) | 2022-07-30 → 2023-09-12 | 409.2 | 0.00997 | −5.5 | locked | 1,095 | 29270 | none in W |
| 9 | 33436 | ASTRA 1M | 37775 | ASTRA 1N | 2023-12-08 → 2024-05-06 | 150.0 | 0.00609 | +18.9 | locked | 2,594 | 33436 | none in W |
| 10 | 37264 | HISPASAT 30W-5 | 43228 | HISPASAT 30W-6 | 2019-05-16 → 2019-11-04 | 171.8 | 0.01207 | −179.9 | anti-locked | 1,501 | 37264 | none in W |

Composite ranks 0.8174 down to 0.7657; the 99th-percentile cut is 0.7504. The
case list file carries, for each of these, both members' own longitude spread
over the episode, the difference of their episode-median longitudes, the
false-alarm probability of each member's cadence fit, the phase-stability
circular s.d. across four-cycle blocks, and the catalogue metadata.

**Three properties of the ranking, measured and reported rather than fixed
after the fact:**

1. **All ten are cadence-testable and all ten are matched** — seven locked,
   three anti-locked. That is the state *after* the §7 defect fix; before it,
   none of the top ten was cadence-testable at all.
2. **804 of the 1,209 ranked episodes score exactly 0 on the cadence
   component**, so that component separates only the top third of the list.
3. **Only 12 of the 1,209 have a relocation inside `W`**, so the fourth
   component is 0 for 99.0% of the list and contributes nothing to the top ten.
   An evidence rank with one near-constant component is, over most of its
   range, a three-component rank, and this document says so rather than
   presenting four independent lines of evidence.

**The defect, found by reading the first case list and fixed TO the
registration at `089da4b`.** The first implementation computed the
"within-catalogue percentile rank" by a double argsort, which orders equal
values by their position in the array — and with 804 episodes tied at exactly
0 on the cadence component, those were being ordered by nothing at all. Ties
now take the mid-rank. The fix **changed the whole top ten**: the pre-fix list
was led by long-dwell, long-gap pairs none of which carried a measurable
cadence, and the post-fix list is led by pairs that carry one. Every number in
this document is from the post-fix run.

---

## 8. The low-Earth arm: a re-expression, not a measurement

Registration §9 declared **in advance** that T11 runs no LEO arm, for two
reasons that are facts about committed results: T3's registered per-object
cadence test returned **0 of 2,809 Starlink and 0 of 618 OneWeb**, and there
is no common LEO station-keeping period to phase-lock against, because drag
make-up cadence is set by each object's own ballistic coefficient and by the
solar cycle — a LEO phase-lock statistic would measure the thermosphere; and
T8b has already committed the LEO co-orbital station catalogue, in which the
later-arriving object is the approaching one by construction, so re-deriving
arrival order from it would restate T8b's attribution rule rather than measure
anything.

What is reported is a **descriptive re-expression of T8b's committed file**,
hash-pinned and verified:

| | |
|---|---|
| Source | `docs/proximity-leo-events-20260922.jsonl` |
| SHA-256 | `39321a4bda7edaa9939a1784a3e9fae10360815dde41aae44b474ec4add4611b` |
| Pin | **matches T8b's committed receipt entry for `LEO-primary-events.jsonl` exactly** |
| Arm-M rows | 71 |
| Distinct pairs | 63 |
| Dwell (d) | p5 31.0, p25 41.3, **median 55.3**, p75 76.7, p95 240.2, max 383.7 |
| Cadence clause | **NOT MEASURABLE** |
| Hazard | **NOT MEASURED** |

**No LEO number in T11 is a T11 measurement.** The LEO median co-orbital dwell
of 55.3 d sits within a day of T11's derived GEO dwell threshold of 56.00 d;
two unrelated derivations landing in the same place is a coincidence and is
noted as one.

---

## 9. Registered blind spots, as they actually bit

Each was declared in registration §8 before measurement.

1. **Mean longitude is not miss distance.** Unchanged and unquantifiable
   within T11.
2. **RECALL IS UNMEASURED.** There is no ground truth for how many co-stationed
   pairs exist. **1,317 episodes and 239 pairs are a lower bound, never a
   census**, and absence of a pair is not evidence of absence of co-location.
3. **The burn train is a subsample.** T8d measured about six confirmed drift
   changes per year per active near-GEO object against a 14.00-day cycle
   implying about twenty-six. The cadence estimator reads the drift *series*
   rather than the flag train, which is why it works at all — but **65.9% of
   episodes are not cadence-testable**, for the reason the registration named
   in advance: a member whose box is tight enough that its sawtooth falls under
   the fit noise fails the screen.
4. **One cycle, one belt.** The estimator tests the 14.00-day line. §4.3's
   free-period variant is the only probe of the line's measured width, and
   T3's 21.00-day Inmarsat-shaped carriers are invisible to the clause.
5. **Co-location by design is not separated from co-location by arrival**
   except through E2, which is censored for 27 episodes.
6. **Adjacent touching boxes are admitted** by the separation screen. Every row
   carries each member's own longitude spread and the difference of their
   episode-median longitudes so a reader can see which case it is; §7's ten
   cases show spreads of 0.06–0.13° against median-longitude differences of
   0.0004–0.011° — boxes an order of magnitude wider than their offset, which
   is one shared station and not two adjacent ones.
7. **The libration zone.** 376 of 1,317 episodes (28.6%) sit inside T8a's
   falsified ±3.75° flag. Nothing was excluded by it.
8. **Catalogue completeness.** Untested and untestable from inside.
9. **Regime.** Near-GEO only, 1,652 of the archive's 68,089 objects.

**One blind spot was NOT declared and should have been**, and it is the one
that cost E3: the registration did not notice that both of its outcomes can
occur only once per station segment, and therefore did not notice that a
per-day rate ratio over a window drawn from stationed days is length-biased.
L1 caught it; the registration did not foresee it.

---

## 10. Owed follow-up registrations, not fixed in-track by choice

1. **A GEO never-manoeuvred control that has exposure** (§2.3). Needs a flag
   threshold below the 0.010 deg/day physical floor, validated against
   held-out objects before it is used — the T8a §7.2 lesson applied to a
   control rather than to a bound. Without it, no GEO pair or event catalogue
   in this programme has a leak-free control.
2. **A risk-set estimator for E3** (§6.2): segment-conditional time-to-event
   rather than a per-day rate ratio, with the window matched to the measured
   segment scale (mean 2,388 d for the segments that carry episodes).
3. **A cadence clause for carriers off the 14.00-day line** (§9.4), and a
   principled treatment of the free-period variant's phase decorrelation.
4. **A composite rank whose components are not near-constant** (§7), or an
   explicit statement that the case list is a dwell-cadence-gap ordering.

---

## 11. Reproduction

```
git show ca7f5f4 --stat      # the registration, committed alone
git show 649bac4 --stat      # the instrument and its tests
git show 089da4b --stat      # the mid-rank defect fix

python3 -m unittest tests.test_persistent_pairs      # 54 tests
python3 tools/persistent_pairs.py                    # 50 s + 243.5 s, CPU
```

Determinism: seed 20260922 for the §5.3 control draw, the §6.2 match draw and
the §6.2 permutation null. No other randomness. Source hashes of
`tools/persistent_pairs.py` and `tools/proximity_geo.py`, the archive
provenance, and the SHA-256 of the catalogue and the case list are in
`docs/persistent-pairs-20260922-receipt.json`.

Nothing from T11 was written to `src/`, `data/`, `public/` or any site
surface. Publication and framing for this track is reserved to the operator.
