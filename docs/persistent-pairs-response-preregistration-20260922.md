# T11b pre-registration: a segment-level response estimator, and a GEO passive control built by construction

**Registered 2026-09-22, committed alone, before any T11b estimate, class
membership, exposure count, leak count or hazard ratio exists.**

T11 discharged with two named failures, both of them caught by its own
registered machinery rather than by a later reading:

1. **E3 was NOT READ** because leak check L1 failed. T11's response estimator
   was a per-day rate ratio over windows drawn from stationed days, and both
   of its outcomes can occur **at most once per station segment**. The
   permutation null returned a median `HR_self` of **0.3575** where the
   registration required 1.00 ± 0.05, and it failed in the same direction at
   every window and for both outcomes. T11 §6.2 measured the cause: mean
   station-segment length **251.3 d** overall against **1,634.8 d at a
   uniformly drawn stationed day** — a length-bias factor of **6.50×** — and
   measured a second, smaller bias running the other way, a flat-hazard
   synthetic returning **1.298** because exposure inside the window is
   truncated at the segment end while the event at that end is still counted.
2. **Gate B could not be evaluated at all**, because the manoeuvre-history
   `never_manoeuvred` class that worked perfectly in LEO — 855 dead payloads,
   exactly zero events across 18,792,698 object-days — contains **9 of 1,652**
   near-GEO objects and **zero pair-exposure-days**. T11 §2.3 states the
   consequence in its own words: every T11 E1 count is a count of **geometry**
   that T11 cannot independently prove is **station-keeping**.

This document registers the two replacements, in advance and together,
because they share an input catalogue and a provenance pin. It registers
**what must be true before any number may be read**, and the words that get
used if those conditions are not met.

**Nothing in this document is a result.** No estimator has been run, no class
has been enumerated, no episode has been counted. The instrument that will
answer it does not exist at the moment this file is committed.

---

## 0. Vocabulary, carried forward unchanged

T11 §0's vocabulary ban is inherited without modification and applies to this
document, to `tools/persistent_pairs_response.py`, to
`tools/geo_passive_control.py`, to their tests, to every receipt and to every
results document produced under this registration. Facts only. No motive is
attributed to any object for any manoeuvre, relocation, arrival or departure.
Catalogue registry codes, names, object identifiers and launch dates are
**metadata**: they may be printed beside a row and they may enter **no**
detector branch, no class definition, no ranking, no stratification and no
sentence that draws a conclusion. Nothing from this track reaches any site
surface.

The permitted form for a response sentence remains exactly T11 §6.6's:
*"relocated N days after the later arrival"*, never a sentence that says why.

---

## 1. The committed inputs, pinned before anything reads them

Every input to T11b is already committed. This registration pins each one by
hash or by commit, and the instruments **must verify the pin and refuse to run
if it does not match**.

| Input | Pin | What it supplies |
|---|---|---|
| `docs/persistent-pairs-preregistration-20260922.md` | commit `ca7f5f4`, committed alone, one file, 824 lines | the estimand, the thresholds, the arrival-order rule |
| `docs/persistent-pairs-20260922.jsonl` | SHA-256 `5df77537334ac5792b708c4c93f84c14b28d07df7803b5a7ccd459a29d0167bb` | **the 1,317 committed episodes**, 239 pairs, of which 1,209 carry a resolved arrival order |
| `docs/persistent-pairs-20260922-receipt.json` | the T11 receipt, read for the pin and for the derived constants | `X_pair`, `D_pair`, `W`, σ_n, the archive provenance |
| `docs/proximity-events-20260922.jsonl` | T8a's committed GEO event catalogue, 493 events | the T8a leak denominator and numerator |
| `runtime/proximity-geo/` extract | T11 gate F: 217,007,154 rows scanned, 11,626,494 kept, 1,768 objects | the element-set series, unchanged |
| `tools/proximity_geo.py`, `tools/persistent_pairs.py` | SHA-256 recorded in the T11 receipt | station segments, drift flags, the cadence phasor, the interval machinery |

**T11b measures nothing new from the archive's raw rows.** It re-reads the
same pinned extract, re-derives the same station segments by the same
function, and re-expresses two committed catalogues. If the extract does not
match T11's gate-F pin the run aborts, as T11's did.

**A pin is not a proof of correctness.** It proves only that T11b is reading
the object T11 and T8a committed, so that a disagreement between the two
documents is a disagreement about method and never about data.

---

# PART 1 — THE RESPONSE ESTIMATOR

## 2. Why the registered T11 estimator was the wrong shape

Stated as measurement, not as opinion, and sourced to the committed T11
results document:

- Both registered outcomes — a relocation of ≥ 2.0°, and a station departure —
  are defined at **a station segment's end**. Each can therefore occur **at
  most once per segment**.
- A window opened on a uniformly drawn stationed day lands inside a segment
  **in proportion to that segment's length**. T11 measured the size of this:
  1,634.8 d against 251.3 d, a factor of 6.50.
- The expected wait to the segment end from such a draw is **816.9 d**, while
  the pooled per-day rate implies an outcome every **251.3 d**. Their ratio,
  **0.308**, sits inside the range of permutation-null medians T11 actually
  observed (0.289–0.436 for relocation, 0.343–0.801 for departure).

This is the waiting-time paradox, and a per-day rate ratio cannot be repaired
by choosing a different window. The estimand has to be re-posed on the object
that carries the outcome. That object is the **station segment**.

## 3. The re-posed estimand

**Risk set.** One **station segment** of one incumbent, borrowed unchanged
from T8a `station_segments()` as T11 borrowed it: a maximal run of days over
which the object's mean longitude stays within ±0.3° of that run's own median,
of length ≥ 30 d. A segment enters the risk set at **age 0** and leaves it at
its end.

**Clock.** **Segment age** in days — time since the segment began — not
calendar time and not time since the arrival. Registered because the quantity
being compared is the chance that a station ends, and a station's own history
begins when it begins.

**Exposure.** A binary, **time-varying** covariate `x(t)`. For a segment of
incumbent `i`, `x(t) = 1` on the age interval
`(a_arr, min(a_arr + W, L)]` where `a_arr` is the age of the segment at the
later arrival's epoch and `L` is the segment's length; `x(t) = 0` elsewhere,
**including after the window closes**. Several arrivals inside one segment
contribute the **union** of their windows.

**Outcomes**, both borrowed from T11 §6.1 unchanged and both reported:

- **Primary — relocation.** The segment ends and the object's next station
  segment has a median longitude ≥ 2.0° away (T8a `relocations()`). A segment
  that ends any other way is **censored at its end**, never scored zero.
- **Secondary — station departure.** Every segment end is an event. Its two
  registered limitations are restated beside its number: it fires on an object
  that merely stops being catalogued near GEO, and the final segment of an
  object is censored by the archive's end. A registered sensitivity arm
  censors any segment whose end lies within 30 d of the object's last element
  set.

**Arrivals.** From the pinned T11 catalogue, the rows with
`order == "resolved"` (1,209 of 1,317). Arrivals are **deduplicated on
`(incumbent, laterArrival, laterArrivalDay)`** before any window is formed,
because one physical arrival appears once per episode of the same pair and
T11's per-day estimator summed exposure per **episode**. The number of
duplicate arrivals removed is reported. An arrival whose epoch falls on a day
when the incumbent is not stationed is excluded and counted.

### 3.1 What this estimand is, and is not

It is the ratio of the instantaneous rate at which an incumbent's station
segment ends, while a window opened by a later arrival is open, to the rate at
which it ends otherwise, at the same segment age. It is **not** a probability
that a relocation follows an arrival, **not** a statement about any individual
pair, and **not** a statement about why anything moved.

## 4. The estimator, stated exactly

**Cox proportional-hazards regression with a time-dependent covariate, in the
counting-process (start, stop, event) form, maximising the Breslow partial
likelihood.**

- Cox, D. R. (1972). "Regression Models and Life-Tables." *Journal of the
  Royal Statistical Society B* **34**(2), 187–220 — the partial likelihood.
- Andersen, P. K. & Gill, R. D. (1982). "Cox's Regression Model for Counting
  Processes: A Large Sample Study." *Annals of Statistics* **10**(4),
  1100–1120 — the counting-process formulation that makes `(start, stop]`
  rows and a time-varying covariate legitimate.
- Kalbfleisch, J. D. & Prentice, R. L. (2002). *The Statistical Analysis of
  Failure Time Data*, 2nd ed., Wiley — §6.3 on time-dependent covariates, and
  the Breslow (1974) handling of tied failure times.

For a single scalar covariate the Breslow partial log-likelihood over strata
`s` and failure times `t` is

```
l(b) = SUM_s SUM_{t in D_s} [ b * S1_{s,t}  -  d_{s,t} * log( SUM_{j in R_s(t)} exp(b * x_j(t)) ) ]
```

where `R_s(t) = { j in stratum s : start_j < t <= stop_j }`, `d_{s,t}` is the
number of failures at `t`, and `S1_{s,t}` is the sum of `x_j(t)` over those
failures. With `x` binary this reduces at each failure time to a count of the
exposed and unexposed rows at risk, and the score and information are exact,
closed-form, and need no numerical differentiation:

```
U(b)  = SUM [ S1 - d * n1*e^b / (n0 + n1*e^b) ]
I(b)  = SUM [ d * n0*n1*e^b / (n0 + n1*e^b)^2 ]
```

`n1`, `n0` = exposed and unexposed rows in the risk set. `b` is found by
Newton–Raphson from `b = 0`, step-halved on any non-increase, to
`|U| < 1e-10` or 200 iterations. **`HR = exp(b)`.**

**Intervals: profile likelihood, not Wald.** The 95% interval is the set
`{ b : 2[l(b_hat) - l(b)] <= 3.841459 }`, found by bisection outward from
`b_hat` on `[-20, +20]`. Registered in preference to a Wald interval because
the primary arm may carry of order ten events, where the Wald interval is
known to be poor and can cover 1.0 by symmetry alone. The Wald interval and
the score test are **also** computed and printed, so that a disagreement
between them is visible rather than hidden. If `b_hat` diverges — zero exposed
events, or zero unexposed events — the point estimate is reported as
`0` or `infinity` with the finite side of the profile interval, and the arm is
flagged `degenerate`.

**Why this removes the length bias.** The partial likelihood conditions on the
risk set at each observed failure time. A long segment contributes to many
risk sets, but every comparison it enters is against other segments **at the
same age**. Nothing is ever drawn from a pool of stationed days, so no
quantity in the estimator is proportional to a segment's length. This
statement is a derivation, not a result; §6 registers the three measurements
that must confirm it before any ratio is read, and the one that must confirm
the estimator can still see an effect when one is present.

### 4.1 The three registered models

| | Risk set | Baseline |
|---|---|---|
| **M1 — primary** | every station segment of every incumbent | **stratified by incumbent object**: one baseline hazard per object |
| M2 | the same segments | pooled: one baseline hazard |
| M3 | incumbent segments **plus** matched-control objects' segments | pooled |

M1 is the segment-level analogue of T11's `HR_self` — the comparison is inside
one object's own history. M3 is the analogue of `HR_ctrl`. The matched
controls are T11 §6.2's rule, borrowed unchanged: for each arrival, up to 5
payload-class objects, neither member of the pair, stationed at the arrival
epoch, with **no** second object arriving within `X_pair` of their own station
during `(t − W, t + W]`, matched on the crowding decile (objects within ±5.0°),
the tenure quartile, and calendar year ± 2, seed 20260922. Control segments
carry `x = 0` throughout.

### 4.2 The windows

Registered arms, all run and all reported, **the primary fixed here**:

| Arm | `W` | Source |
|---|---:|---|
| `W=36.1d` | 36.1 d | T8a's measured median `lead_causal` |
| `W=96d` | 96.0 d | T8a's measured p75 |
| **`W=162.7d` — PRIMARY** | **162.7 d** | T8a's measured p95, T11's registered primary |
| `W=365d` | 365.0 d | one year |
| `W=segment` | to the segment end | the risk-set-native arm: once opened, the window stays open |

The `W=segment` arm is registered because T11 §6.2 observed that 162.7 d is
short against the measured segment scale (mean 2,388 d for segments carrying
an episode). It is a **sensitivity arm** and by T11 §6.5's rule cannot change
the primary verdict.

## 5. Power, registered before the count exists

If model M1 at the primary arm and primary outcome has **fewer than 10
informative events** — an event in a stratum whose risk set at that failure
time contains at least one exposed and one unexposed row — the result is
reported **UNDERPOWERED**, intervals printed, no claim in either direction,
and the word UNDERPOWERED used in the results document's first screen. The
informative-event count is reported for every arm and model whatever the
verdict.

## 6. The checks that must pass BEFORE any ratio is read

T11 registered three leak checks above its ratio and one of them stopped the
number. T11b registers four, with their tolerances fixed here, and the results
document **may not print a hazard ratio until all four are printed**.

### R1 — permutation null on the real data

Identical in construction to T11's L1, so that the two estimators are tested
by the same instrument: each deduplicated arrival epoch is reassigned to an
epoch drawn uniformly from the **same incumbent's own stationed days** — that
is, the very length-biased draw that broke the T11 estimator — preserving the
incumbent, its segments and its outcome history. `HR` is recomputed for model
M1 by the identical code path. **1,000 permutations, seed 20260922.**

> **Bar: the null's median `HR` lies in [0.95, 1.05] AND the null's 95%
> interval contains 1.0.**

Failure means the estimator is biased by construction. Then **the ratio is not
read**, the results document says so in those words, and T11b reports the bias
instead of a hazard — exactly as T11 did.

### R2 — matched-control self-consistency

The matched controls of §4.1 are given a **sham exposure window** of the same
length `W`, opened at the epoch for which they were matched, and model M2 is
fitted **on the control segments alone**. A control object had, by
construction, no arrival; the sham window marks nothing. Its estimated `HR`
must therefore be 1.0.

> **Bar: the 95% profile interval of the sham `HR` contains 1.0, and the point
> estimate lies in [0.80, 1.25].**

Failure means the matching selected on the outcome — a control chosen at an
epoch where the outcome was already more or less likely than usual — and then
**M3 is not read**, while M1 may still be read if R1, R3 and R4 pass. The
asymmetry is registered by design: R2 is a statement about the controls,
not about the machinery.

### R3 — flat-hazard synthetic, truth exactly 1.0 by construction

Registered in full so that it cannot be tuned afterwards:

- **400 synthetic objects**, horizon 7,300 d each, seed 20260922.
- Segment durations drawn `Exponential(mean = 300 d)`, laid end to end with no
  gap. The hazard is constant by construction; every segment end is an event;
  the last segment of each object is censored at the horizon.
- **One arrival per object**, placed uniformly at random over that object's
  **total stationed time** — the length-biased draw, on purpose.
- The arrival is independent of every duration. **True `HR` = 1.0 exactly.**
- The registered estimator, M1 and M2, at `W = 162.7 d`.

> **Bar: `HR` in [0.90, 1.10] for both M1 and M2, and the 95% interval
> contains 1.0.**

The same synthetic is also passed through **T11's per-day rate-ratio
estimator**, and the value it returns is reported beside T11b's. T11 §6.2
measured 1.298 for a construction of this shape. If T11b's estimator is doing
what §4 derives, the two numbers must differ and only one of them may be 1.0.

### R4 — recovery synthetic, truth exactly 2.0 by construction

Registered because R1–R3 are all tests that the estimator can return 1.0, and
an estimator that returns 1.0 **always** would pass every one of them. This is
the check that it can still see an effect.

- The R3 population, same seed, with one change: inside a segment that
  contains an arrival, the hazard is multiplied by **2.0** on the age interval
  `(a_arr, a_arr + W]` and is unchanged elsewhere. Residual durations are
  generated by inverse transform on the piecewise-constant cumulative hazard,
  so the injected ratio is exact and not approximate.

> **Bar: the 95% interval of `HR` contains 2.0 AND excludes 1.0, for both M1
> and M2.**

Failure means the estimator has no power to detect a doubling at this sample
size, and **the ratio is not read**: a null that cannot distinguish itself
from an effect twice its size is not a null.

### The order of printing

R1, R2, R3, R4, each with its measured value and its bar, then the
informative-event counts, then — **only if R1, R3 and R4 all pass** — the
hazard ratios. If any of R1, R3, R4 fails, the results document prints
**"E3 IS NOT READ"** and names the failing check, and prints no hazard ratio
for any arm.

## 7. The decision rule

At the primary arm (`W = 162.7 d`, primary outcome, models M1 and M3), with
R1, R2, R3 and R4 all passed and the §5 power gate clear:

| Verdict | Condition |
|---|---|
| **SUPPORTED** | the 95% intervals of **both** M1 and M3 exclude 1.0 **on the same side**, and the R1 null's 95% interval excludes the observed M1 `HR` |
| **FALSIFIED** | the 95% intervals of **both** M1 and M3 contain 1.0 |
| **INCONCLUSIVE** | anything else, including the two models disagreeing in direction |
| **UNDERPOWERED** | §5 |
| **NOT READ** | any of R1, R3, R4 fails; or R2 fails and M3 alone would have decided it |

If the verdict is FALSIFIED the results document writes T11 §6.6's sentence,
unchanged and in those words: *"No response effect is detected. The
incumbent's relocation hazard after a later arrival is consistent with its own
baseline and with matched stationed objects that had no later arrival."*

Sensitivity arms are reported in full and cannot change the primary verdict.

## 8. Declared blind spots of Part 1

1. **Proportional hazards is an assumption, not a fact.** It is not tested
   here for lack of a registered test, and the results document must say so.
   The `W=segment` arm is the closest available probe: if the effect is
   confined to the first weeks, the long-window arms will dilute it and the
   two will disagree.
2. **The segment definition is T8a's**, and a relocation smaller than 0.3°
   does not end a segment while a station-keeping excursion of 0.31° does.
   Every count inherits that boundary.
3. **Arrival epochs carry T11's 1.73-day resolution limit** and 27 episodes
   were censored there. Nothing here improves that.
4. **Recall is unmeasured**, inherited from T11 §9.2. Every count is a lower
   bound on the co-stationed population.
5. **An incumbent is an object that had an arrival.** M1 removes between-object
   differences by stratification; M3 does not, and its controls are matched on
   three registered quantities only.
6. **The departure outcome fires on a catalogue gap**, not only on a station
   ending. Its sensitivity arm bounds that, it does not remove it.

---

# PART 2 — A GEO PASSIVE CONTROL, BUILT BY CONSTRUCTION

## 9. What a control has to do, and what the GEO one has to survive

T8b proved its LEO control the only way a control can be proved: it ran the
**unchanged detector** on a class of objects that could not produce the thing
being detected, and got **zero**, per unit exposure, with the exposure
reported. 855 dead payloads, 18,792,698 object-days, 0 events, leak ratio
0.000 against a bar of 0.10.

Transposed to GEO with T8a's own drift-change flag, that class is 9 objects
with **zero pair-exposure-days** and the gate is 0/0. A control with no
exposure proves nothing; T11 §2.3 says so and T11b does not dispute it.

**A control that cannot be shown to be empty of the signal is not a control.**
T11b therefore registers classes that are passive **by construction from the
physics**, and registers the proof each must pass before it is used for
anything.

## 10. The physics, derived here with no fitted parameter

### 10.1 The pendulum

Earth's triaxiality (the J₂₂ sectorial term) gives a near-geostationary
object's mean longitude the equation of motion of a pendulum about the nearer
of two stable longitudes. Writing `u = λ − λ_s` for the displacement from that
stable longitude,

```
u'' = − A · sin(2u)
```

with `A` the maximum longitude acceleration. `A` is **not refitted here**: it
is T8a prereg §2.6's committed J₂₂ derivation, recomputed by
`proximity_geo.LAMBDA_DDOT_MAX`:

| Quantity | Value |
|---|---|
| `A` | **1.7006955627927864e-3 deg/day²** = 2.9682737e-5 rad/day² |
| stable longitudes `λ_s` | **75.1° E** and **104.7° W** (T8a prereg §2.6, `STABLE_LONGITUDES_DEG`) |
| unstable longitudes | 90° from each stable longitude |

**The one place T8a's falsified derivation must not be repeated.** T8a §7.2
falsified the *dwell bound* built from `A`, and identified the error exactly:
it assumed the restoring acceleration at a real object equals the full
triaxial value at its distance from the *nominal* stable longitude, when a
real object's instantaneous equilibrium is displaced by solar radiation
pressure and modulated by luni-solar terms, so the true restoring acceleration
is **smaller**. Every use of `A` in this registration is therefore an
**upper bound on |λ̈|**, in the direction where that error cannot bite: the
true motion is slower than the bound, never faster. Each of the tests below is
written one-sided for exactly that reason. **A derivation is not a validation**
— §12 registers the validation.

### 10.2 The first integral, the amplitude–rate relation, and the period

Multiplying by `u'` and integrating, with `u_max` the libration half-amplitude
(`u' = 0` there):

```
u'^2 = 2 A_r ( sin^2 u_max − sin^2 u )            A_r = A in rad/day^2
```

At the stable longitude (`u = 0`) this gives the **amplitude–rate relation,
with no free parameter**:

```
|λ'|_max = sqrt(2 A_r) · sin(u_max)   rad/day
         = 0.4414582 · sin(u_max)     deg/day
```

Small-amplitude period, and the exact nonlinear period from the pendulum's
complete elliptic integral of the first kind `K`:

```
T_0     = 2π / sqrt(2 A_r) = 815.4792 d = 2.2327 yr
T(u_max) = (2/π) · T_0 · K( sin u_max )      half-period P½ = T/2
```

`K` is evaluated by the arithmetic–geometric mean, to machine precision, and
is checked in the test suite against independently computed values.

Numerically, for the upper-bound `A`:

| `u_max` | `|λ'|_max` (deg/day) | half-period P½ (d) |
|---:|---:|---:|
| 0.3° | 0.00231 | 407.7 |
| 1° | 0.00771 | 407.8 |
| 5° | 0.03848 | 408.5 |
| 20° | 0.15099 | 420.5 |
| 60° | 0.38231 | 559.8 |

Because `A` is an upper bound on the restoring acceleration, a genuinely free
object is **slower** than the first column and **slower** — longer-period —
than the second.

### 10.3 Why T8a's flag floor empties the GEO control — derived, then measured

T8a's drift-change flag is a departure of the drift rate from the trailing
median of the previous 10 element sets, exceeding `max(5σ_n, 0.010 deg/day)`
at two consecutive element sets. With the measured σ_n = 6.0385335e-4 deg/day,
`5σ_n = 3.0193e-3 deg/day`, so **the 0.010 deg/day floor dominates by 3.3×**.

Free motion alone changes the drift rate. Over an interval `Δt` it changes by
at most `A · Δt`:

| Interval | Free-motion drift change (upper bound) | Against T8a's floor |
|---|---:|---|
| one element set at the archive's median spacing, 0.865 d | 1.471e-3 deg/day | 6.8× **below** the floor |
| the 10-sample baseline span, ≈ 8.65 d | **1.4711e-2 deg/day** | **1.47× above the floor** |
| a 30-day catalogue gap | 5.10e-2 deg/day | 5.1× above the floor |

**Derived, before measurement: a free object whose element sets are 8.65 days
apart across the flag's baseline window can cross T8a's floor on free motion
alone, and one observed across a catalogue gap crosses it comfortably.** That
is a candidate mechanism for a GEO class of 9. It is a prediction of this
registration and §14 registers its measurement: how many of the 1,652 objects
lose their zero-flag status to a drift change no larger than free motion could
have produced.

For contrast, and from the same constant: an east–west station-keeping burn at
T3's measured 14.00-day cycle reverses a drift sawtooth of half-amplitude
`A·T/4`, a single-step change of

```
A · T / 2 = 1.1905e-2 deg/day
```

which is **8.1× the free-motion change over one element-set interval** and
**3.9× the measured 5σ_n**. A rule that predicts and subtracts free motion,
and then thresholds on the measured noise, separates the two by construction.
A rule with a constant floor at 0.010 deg/day does not.

## 11. The registered classes

### 11.1 Class D — the T8a v2 dead-payload rule

T8a §10.3 and T11 §10.1 both owe this rule; it is registered here for the
first time. It replaces T8a's constant floor with the **derived free-motion
bound at the object's own longitude and its own sampling**:

```
base_i   = median( d_{i−10 .. i−1} )                       # T8a, unchanged
t_c,i    = median( t_{i−10 .. i−1} )
acc(λ)   = − A · sin( 2 ( λ − λ_s(λ) ) )                   # A = 1.7006956e-3
pred_i   = 0.5 · ( acc(λ_{c,i}) + acc(λ_i) ) · ( t_i − t_c,i )
dev_i    = | d_i − base_i − pred_i |
thresh_i = max( 5 σ_n , | acc(λ_i) | · ( t_i − t_c,i ) )
flag     = dev_i > thresh_i at two consecutive element sets
```

The flag epoch is the second of the two, as T8a registered. There is **no
0.010 deg/day floor**. Reading the rule in words: *a drift change is evidence
of a manoeuvre only when it exceeds the measured noise floor and is more than
twice what free triaxial motion at this longitude could have produced over the
same interval.* Every constant is measured (σ_n) or derived (`A`, `λ_s`).
Nothing is fitted, and nothing may be adjusted after a number is seen.

**Class D** = catalogue class `PAYLOAD`, with

- **zero** v2 flags over the whole near-GEO history;
- ≥ 200 element sets and ≥ 365 d of span (T8a's admission rule, unchanged);
- **evaluability**: a sample whose baseline span `t_i − t_c,i` exceeds 14.00 d
  — one measured east–west cycle, beyond which the free-motion allowance
  exceeds `A · 14 = 2.381e-2 deg/day` and the rule stops discriminating — is
  **not evaluable**. An object with more than **5%** non-evaluable samples is
  **not admitted**. Unproven means excluded, never included.

Also enumerated and reported, for comparison only and entering no class:
class `PAYLOAD` with zero **T8a v1** flags (the 2 objects T11 counted), and the
full v1 `never_manoeuvred` class (9).

### 11.2 Class F — the free-libration class

Two criteria, both required.

**F1 — no east–west line.** The object's drift series is cut into consecutive
non-overlapping **56.00-day** blocks (T11's `D_pair`, four measured cycles)
from its first element set. Every block with ≥ 8 element sets is fitted by
T11's `cadence_phasor` at the **fixed 14.00-day** period. The object is
**excluded** if **any** block returns a false-alarm probability
**≤ 0.10**. The threshold is by design **ten times more permissive than
T11's detection threshold of 0.01**, because here a detection is a reason to
throw the object out: over-detection makes the control cleaner, and
under-detection makes it leak. The number of blocks tested per object is
reported.

**F2 — a free-libration signature, as a set of one-sided bounds.** All five
are required:

1. **Bound motion in one cell.** Over the whole near-GEO history the
   displacement `u = λ − λ_s` from a *single* stable longitude satisfies
   `|u| < 90°` throughout — the object never crosses an unstable longitude and
   never changes cell.
2. **A turnaround exists.** The daily longitude series contains a sign change
   of `λ'` with **at least 30 consecutive days of each sign** on either side of
   it. A station-keeper inside a ±0.3° box reverses every ~7 days at the
   measured 14.00-day cycle and cannot satisfy this.
3. **The swing is centred on the stable longitude.** With
   `u_max = (max u − min u)/2` and `u_mid = (max u + min u)/2`,
   `|u_mid| <= max(5°, 0.25 · u_max)`. A pendulum's swing is symmetric about
   its equilibrium.
4. **Rate bound.** `max |λ'| <= 1.25 × 0.4414582 · sin(u_max)` deg/day. An
   object moving faster than the fastest free libration of its own amplitude
   has been pushed. One-sided, because `A` is an upper bound (§10.1).
5. **Period bound.** The median observed interval between consecutive
   turnarounds is `>= 0.80 × P½(u_max)` from §10.2. Free motion cannot turn
   around faster than the maximum restoring acceleration allows. One-sided,
   for the same reason.

An object whose archive span contains **no** turnaround fails criterion 2 and
is **not admitted**. Unproven means excluded.

### 11.3 Class I — the intersection, and the registered primary control

**Class I = D ∩ F.** It is the registered **primary** GEO passive control,
because D and F fail in opposite directions and their conjunction is bounded
by both:

- Class D's blind spot is a station-keeper whose burns are small enough to sit
  under `max(5σ_n, free-motion allowance)`. Such an object is nonetheless
  holding a box on a 14.00-day cycle and is therefore **caught by F1**.
- Class F's blind spot is an object whose longitude history happens to look
  like a swing — a slow relocation that reverses, say. Such an object changes
  its drift rate impulsively and is therefore **caught by D**.

All three classes — D, F and I — are enumerated, given exposure, and
leak-tested. **The primary is I**; D and F are reported in full so that the
cost of the conjunction is visible.

## 12. Validation BEFORE use — the T8a §7.2 lesson, applied to a control

T8a registered a derived bound and used it without validating it, and §7.2
records what that cost. Every rule in §11 is derived; none of them is
validated by being derived. The following runs **before** any class is used
for any leak count, and its bars are fixed here.

**V1 — synthetic free librators must be ADMITTED.** 200 synthetic objects,
seed 20260922, each integrated from `u'' = −A sin 2u` by fourth-order
Runge–Kutta with a 0.01-day step, `u_max` drawn uniformly in [1°, 60°], phase
uniform, 20-year history sampled at the archive's measured median spacing of
0.865 d, drift rates perturbed by Gaussian noise of the **measured**
σ_n = 6.0385335e-4 deg/day.

> **Bar: ≥ 95% carry ZERO v2 flags, and ≥ 95% pass F2.**

**V2 — synthetic station-keepers must be EXCLUDED.** 200 synthetic objects,
same sampling and the same measured noise: a longitude sawtooth about a slot
drawn uniformly in longitude, at T3's measured 14.00-day cycle, drift
half-amplitude `A·T/4 = 5.9524e-3 deg/day`, with the burn applied as a single
step of `A·T/2 = 1.1905e-2 deg/day`.

> **Bar: ≥ 95% carry ≥ 1 v2 flag, AND ≥ 95% fail F2 criterion 2 or 5.**

**V3 — the detection floor, measured and reported, not assumed.** V2 is
repeated with the burn size scaled from 0.1× to 2.0× in 20 steps; the
**smallest single-step drift change the v2 rule flags in ≥ 50% of synthetic
keepers** is reported as the rule's detection floor, in deg/day and as a
multiple of `A·T/2`. If that floor exceeds `A·T/2 = 1.1905e-2 deg/day`, the
results document must state that **a routine east–west keeping burn at the
measured cycle is below the v2 detection floor**, and class D is reported as
leaky by construction with that number attached.

**V4 — a parity split, reported as a stability check and not as a fit.** No
rule in §11 has a free parameter, so there is nothing to hold out in the
fitting sense. The classes and their leak rates are nonetheless recomputed on
the even-NORAD and odd-NORAD halves separately and reported side by side. A
leak rate that differs by more than a factor of 3 between the halves is
reported as **unstable** and the pooled number is qualified by that word.

**If V1 or V2 misses its bar, the class that failed is NOT USED**, the failure
is reported with its measured rate, and the results document says which
control it does not have.

## 13. The leak proof — what must be ZERO, and against what exposure

Proved the way T8b proved it: the **unchanged** detectors are re-expressed
over the classes, and rates — never counts — are compared.

**Leak 1 — the T11 pair detector.** T11's committed catalogue is complete over
the near-GEO population at the primary arm and its screen reads no class, so
any episode of a class member is already in the file. For each class `C`:

- **numerator**: episodes in `docs/persistent-pairs-20260922.jsonl` with
  **both** members in `C`;
- **denominator**: `C`'s **pair-exposure-days** — days on which two members of
  `C` are simultaneously stationed — computed by T11's `leak_check` pair-day
  function, unchanged;
- compared against the payload-pair rate from the same function.

**Leak 2 — the T8a event detector.** For each class `C`:

- **numerator**: events in `docs/proximity-events-20260922.jsonl` whose
  **approacher** is in `C`, at T8a's primary arm (X = 0.1°, D = 30 d);
- **denominator**: `C`'s stationed object-days, and separately its station
  segments, so the rate can be read in both of T8a's and T8b's units.

> **The registered bar, borrowed from T8b's gate B: leak-free means ZERO
> episodes and ZERO events, with the exposure reported beside the zero. A
> ratio of class rate to payload rate above 0.10 in either detector means the
> control leaks.**

**Exposure is reported whether or not it is zero.** A class with zero
pair-exposure-days has **not** passed: it has failed to be evaluable, exactly
as T11's did, and the results document must use the word **UNEVALUABLE** for
it and not the word leak-free.

### 13.1 The words if it leaks

If the best of the three classes still produces episodes or events per unit
exposure above the bar, the results document reports the measured leak rate,
its interval, and writes, in exactly these words:

> **the GEO catalogues remain uncontrolled**

No softer phrasing is permitted, and no class may be redefined after its leak
is measured. A rule changed after seeing its leak is a fitted rule, and this
registration forbids it.

## 14. The E1 re-expression

With the primary control in hand, T11's 1,317 episodes are re-expressed into
three **disjoint** categories, registered here before the split is computed:

| Category | Definition |
|---|---|
| **Proven station-keeping** | **both** members carry ≥ 1 **v2** flag with its epoch **inside the episode window** — positive evidence of longitude control while co-located |
| **Geometry only** | at least one member is in the primary control class `I`, or at least one member fails the evaluability rule of §11.1 |
| **Unproven** | everything else: no positive evidence inside the episode, and no member in the control class |

The three counts sum to 1,317 and are reported as such. **"Unproven" is not a
synonym for either of the others** and is reported under that word. Registered
in advance: it is entirely possible that the largest category is Unproven, in
which case T11's §2.3 sentence stands with a number attached rather than being
replaced.

Also reported, and registered here: how many of the 1,652 near-GEO objects
lose their v1 zero-flag status to a drift change **no larger than free motion
could have produced** — the measurement of §10.3's prediction — and the size
of the v1 `never_manoeuvred` class against v2's.

## 15. Gates — what makes a T11b estimand uninformative

| Gate | Registered meaning | Condition |
|---|---|---|
| **G1** | the response estimator is biased | any of R1, R3, R4 fails → **E3 NOT READ**, failing check named |
| **G2** | the controls are selected on the outcome | R2 fails → **M3 not read** |
| **G3** | underpowered | § 5 |
| **G4** | the passive class does not exist | class `I` has **zero** pair-exposure-days → **UNEVALUABLE**, the word used |
| **G5** | the passive class leaks | leak ratio > 0.10 in either detector → §13.1's sentence, verbatim |
| **G6** | the class rules do not do what they were derived to do | V1 or V2 below bar → that class is not used |
| **G7** | provenance | any pin in §1 fails to verify → the run aborts and reports nothing |

Every gate is reported with its measured value whether it fires or not.

## 16. Compute, provenance, determinism

CPU only, on `pc`; nothing on the VPS and no GPU. Seed **20260922**
everywhere: the R1 permutation, the R3/R4 synthetics, the V1/V2/V3 synthetics
and the §4.1 match draw. No other randomness. `scipy` is not installed on the
host, so the elliptic integral (AGM), the Newton–Raphson, the profile
likelihood and the exact intervals are implemented from first principles and
checked in the test suite against independently computed values.

Receipts: `docs/persistent-pairs-response-20260922-receipt.json` and
`docs/geo-passive-control-20260922-receipt.json`, each carrying the archive
provenance, the input pins of §1, the source SHA-256 of both new tools, every
gate with its measured value, and the wall seconds of each stage.

## 17. What is committed with this document

This file, alone, before:

- `tools/persistent_pairs_response.py` — the segment-level estimator;
- `tools/geo_passive_control.py` — the classes, their validation and their
  leak proof;
- `tests/test_persistent_pairs_response.py` and
  `tests/test_geo_passive_control.py`, which must include, as their first
  assertions, **the bug**: a seeded length-biased draw on a flat-hazard
  synthetic must make T11's per-day rate-ratio estimator fail R1's band, and
  the same draw must leave the registered segment-level estimator inside it;
- `docs/persistent-pairs-response-results-20260922.md` and
  `docs/geo-passive-control-results-20260922.md`;
- the two receipts;
- the runbook rows for T11 and T8.

If any measurement in this document turns out to have been mis-specified, the
defect is **reported in the results document and not edited out of this one**,
as T11 reported the φ_lock degree gloss and the mid-rank defect.
