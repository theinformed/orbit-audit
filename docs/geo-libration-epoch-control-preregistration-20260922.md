# Pre-registration: a GEO control built on epochs of free libration inside a history

**Registered 2026-09-22, committed alone, before `tools/geo_epoch_control.py`
exists and before any epoch, exposure day, leak count or verdict exists.**

T11b part 2 discharged with a measured negative result and named the reason in
its own §11.1: *"A control may have to be built on something other than
station segments — for instance on epochs of free motion inside an object's
history rather than on objects."* This document registers that instrument,
alone and in advance.

**Nothing in this document is a result.** Every number below is either a
constant committed by an earlier registration, a quantity derived here from
those constants with no fit, or a bar. No epoch has been found, no exposure
counted, no leak measured.

---

## 0. Vocabulary, carried forward unchanged

T11 §0's vocabulary ban is inherited without modification and applies to this
document, to `tools/geo_epoch_control.py`, to its tests, to its receipt, to
its epoch catalogue and to its results document. Facts only. No motive is
attributed to any object for any manoeuvre, relocation, arrival or departure.
Catalogue registry codes, names, object identifiers and launch dates are
**metadata**: they may be printed beside a row and they may enter **no**
detector branch, no class definition, no admission rule, no ranking, no
stratification and no sentence that draws a conclusion. Nothing from this
track reaches any site surface.

---

## 1. The committed inputs, pinned before anything reads them

| Input | Pin | What it supplies |
|---|---|---|
| `docs/persistent-pairs-response-preregistration-20260922.md` | commit `0aa028a`, committed alone | the v2 rule, the five free-libration bounds, `A`, `λ_s`, the leak bar |
| `docs/persistent-pairs-20260922.jsonl` | SHA-256 `5df77537334ac5792b708c4c93f84c14b28d07df7803b5a7ccd459a29d0167bb` | the 1,317 committed T11 episodes |
| `docs/proximity-events-20260922.jsonl` | T8a's committed GEO event catalogue, 493 rows | the T8a leak numerator |
| `runtime/proximity-geo/` extract | T11 gate F: 217,007,154 rows scanned, 11,626,494 kept, 1,768 objects | the element-set series, unchanged |
| `tools/proximity_geo.py`, `tools/persistent_pairs.py`, `tools/geo_passive_control.py`, `tools/trigger_alarm.py` | read and reused, not modified | the station segments, the daily grid, σ_n, the fixed-period cadence phasor, the v1 and v2 flag rules, the trigger chain arithmetic, the synthetic generators |

**This registration measures nothing new from the archive's raw rows.** It
re-reads the same pinned extract through the same `build_world`, re-derives
the same σ_n by the same function, and re-expresses three committed catalogues
over a new kind of exposure. If the extract or a catalogue pin does not match,
the run aborts and reports nothing (gate G-E7).

**A pin is not a proof of correctness.** It proves only that this study reads
the objects T8a, T8d and T11 committed.

---

## 2. Why the object-level control failed, in the committed numbers

Restated from `docs/geo-passive-control-results-20260922.md` so that what
follows is traceable, and not re-derived here:

1. **Class I — no 14.00-day line, a free-libration signature, and zero v2
   flags — contains 0 objects and 0 pair-exposure-days.** UNEVALUABLE.
2. **Class D (zero v2 flags alone) contains 3 payloads and all three carry the
   measured 14.00-day line**, one at a false-alarm probability of 3e-14.
3. **The only class with exposure leaks by 8.67** [1.78, 25.50] against a bar
   of 0.10 — 3 T8a events over 2,635 stationed object-days against 0.346
   expected — and its three events are three of the five T8a §7.1 had already
   named as its own passive-class leak.
4. **The mechanism is physics, not bookkeeping**: a stationed passive GEO
   object is a free librator, and a free librator *at its turnaround* dwells
   near whatever shares its longitude. T8a's event definition is built to find
   a slow approach that dwells. A control made of whole librating objects
   therefore cannot be empty of T8a events.
5. **232 pair-days against the 540,990 one expected episode requires.** Every
   zero in that document was printed with the exposure it rests on, and none
   of them had the exposure to mean anything.

**The move this registration makes.** (4) is a statement about *when* in an
object's history the signal appears, not about *which objects* have it. A
librator is near its turnaround for a small part of each swing and away from
it for the rest. The unit of a control can therefore be an **interval of one
object's history** rather than the object. That is the only structural change;
every rule below is built from constants already committed.

---

## 3. The physics, carried forward and extended, with no fitted parameter

### 3.1 Carried forward unchanged from T11b §10

| Quantity | Source | Value |
|---|---|---:|
| `A`, maximum longitude acceleration | T8a prereg §2.6, `proximity_geo.LAMBDA_DDOT_MAX` | **1.7006955627927864e-3 deg/day²** |
| `A_r` | `A · π/180` | 2.9682737e-5 rad/day² |
| stable longitudes `λ_s` | T8a prereg §2.6 | **75.1° E**, **104.7° W** |
| `ω₀ = sqrt(2 A_r)` | the pendulum | 7.704899e-3 rad/day |
| `T₀ = 2π/ω₀` | small-amplitude libration period | **815.4792 d** |
| amplitude–rate coefficient `sqrt(2A_r)` in degrees | `\|λ'\|_max = 0.4414582 · sin u_max` deg/day | **0.4414582 deg/day** |
| `T(u_max) = (2/π) T₀ K(sin u_max)` | the exact nonlinear period, `K` by the arithmetic–geometric mean | 815.48 d at `u_max → 0`; 1,119.6 d at 60° |
| σ_n | T8a's measured drift noise | **6.038534e-4 deg/day** |
| `5 σ_n` | T8a's noise term, `BURN_SIGMA_K` unchanged | 3.019267e-3 deg/day |
| `T_ew` | T3's measured east–west cycle | **14.00 d** |
| east–west keeping burn at the maximum acceleration, `A·T_ew/2` | T11b §10.3 | 1.1904869e-2 deg/day |
| catalogue gap that breaks an interval, `MAX_GAP_DAYS` | T8a prereg §4.1, unchanged | **5.0 d** |

**The one-sided posture, carried forward verbatim in force.** `A` is an
**upper bound** on the restoring acceleration, because a real object's
instantaneous equilibrium is displaced by solar radiation pressure and
modulated by luni-solar terms (T8a §7.2, T11b §10.1). Every test below is
written one-sided in the direction where that error cannot make the motion
look *slower* than it is. The cost of that posture is stated in §11.4: it
admits too much, never too little, and this registration does not pretend
otherwise.

### 3.2 The first integral, written as a local quantity

Writing `u = λ − λ_s` in radians and `v = λ'` in rad/day, the pendulum
`u'' = −A_r sin 2u` has the first integral

```
s  ≡  sin²u  +  v² / (2 A_r)                                        (3.2.1)
```

with `ds/dt = v sin 2u + (v/A_r)(−A_r sin 2u) = 0` for free motion, and
`s = sin² u_max`. **`s` is computable from a single element set** — one
longitude and one drift rate — which is what makes it the local form of the
bounds T11b could only test over a whole swing.

**Under the one-sided bound.** If the true restoring acceleration is `κ A_r`
with `0 < κ ≤ 1`, the conserved quantity is `s_κ = sin²u + v²/(2κA_r)` and the
quantity (3.2.1) evolves as

```
ds/dt = v sin 2u + (v/A_r)(−κ A_r sin 2u) = (1 − κ) · v · sin 2u       (3.2.2)
```

so that, **with no knowledge of κ**,

```
|ds/dt|  ≤  |v · sin 2u|                                             (3.2.3)
```

(3.2.3) is the κ-free, one-sided bound this registration uses. It is a
derivation from the committed constants, not a fit, and §7 registers the
validation that must pass before it is used for anything.

### 3.3 What (3.2.3) can and cannot see — derived here, before measurement

**It cannot see a symmetric velocity reversal.** A station-keeper holding a
box about a slot at displacement `u` experiences the same triaxial
acceleration as a free object at that longitude; between burns its motion *is*
free motion. Its burn reverses the drift sawtooth from `−aT_ew/4` to
`+aT_ew/4` with `a = A|sin 2u|`, so `v²` is unchanged and, by (3.2.1),
**Δs = 0**. The energy test of §4 is therefore **blind to a routine east–west
keeping burn by construction**, and this registration states that here rather
than discovering it afterwards. The keeper is excluded by criteria (a) and
(c), never by the energy test. The energy test is registered because it sees
what (a) and (c) cannot: an *asymmetric* change of libration energy inside an
otherwise quiet interval.

**The derived blind spot of criterion (a), with its size.** The v2 rule flags
a drift change that exceeds `max(5σ_n, |acc|·Δt_base)`. At the archive's
median element-set spacing the baseline span `Δt_base` is about 5.5 spacings
= 4.76 d, which is below `T_ew/2 = 7 d`, so the binding branch is `5σ_n` and
a keeper at slot displacement `u` is flagged when

```
A · |sin 2u| · T_ew/2  >  5 σ_n
|sin 2u|  >  3.0192668e-3 / 1.1904869e-2  =  0.253617
```

```
u*  =  7.3468°                                                       (3.3.1)
```

**A station-keeper whose slot lies within 7.3468° of a stable longitude has a
triaxial acceleration too small for the v2 rule to separate its burns from
noise.** For slots drawn uniformly in longitude that is `4 u*/360 = 8.16%` of
them. This is derived here, before any synthetic is run, and §7's V-E2 bar is
written around it rather than around a hope. Such a keeper must then be
excluded by criterion (c) alone, whose power inside a single epoch is
**measured by V-E2 and not derived**, because the phasor's power against a
sawtooth of amplitude `A|sin 2u| T_ew/4` depends on the sample count in the
block and has no closed form this registration is willing to assert.

---

## 4. The epoch-segment definition, registered exactly

### 4.1 The unit

A **free-libration epoch** of object `i` is a maximal run of consecutive
element sets of `i`, `[t_a, t_b]`, every one of which is **admissible**, with
no internal catalogue gap exceeding `MAX_GAP_DAYS = 5.0 d` and no internal
violation of the energy test, and which then passes the **run-level** tests of
§4.4.

The epoch is an interval of **one object's history**. It is not an object, not
a station segment, and it carries no requirement that the object be stationed.

### 4.2 Sample-level admissibility — the local tests

A sample `j` of object `i` is **admissible** when all of the following hold.
Each is stated with the minimum run length that makes it testable.

| Tag | Test | Minimum to be testable |
|---|---|---|
| **A1 — evaluability** | the v2 baseline at `j` is finite (the sample has 10 prior element sets) **and** its baseline span `t_j − t_c,j ≤ 14.00 d` | the sample itself, given 10 prior element sets |
| **A2 — criterion (a), no v2 residual** | `j` is not a v2 flag epoch. The v2 flag array is computed once over the object's whole series by `geo_passive_control.v2_flags`, **unchanged**, and the epoch is an interval containing none of its epochs | 1 element set |
| **A3 — bound 1, one cell** | the nearest stable longitude is the same for every sample of the run, and `\|u_j\| < 90°` | 1 element set |
| **A4 — bound 4 made local, below the separatrix** | `s_j = sin²u_j + v_j²/(2A_r) ≤ 1` | 1 element set |

**A4 is T11b's rate bound with the amplitude supplied by the first integral
instead of by an observed swing.** T11b bound `max|λ'| ≤ 1.25 · 0.4414582 ·
sin u_max` with `u_max` read off a whole history. Locally, (3.2.1) *defines*
the implied half-amplitude `û_max = arcsin sqrt(s)`, and the rate bound is then
the statement `s ≤ 1` — the object is on a bounded trajectory inside one cell
rather than circulating. The registered factor 1.25 of T11b is not carried
over because with `û_max` derived from `v` itself the bound is no longer a
comparison of two measured quantities; the slack it bought is replaced by the
one-sidedness of `A` itself (§3.1).

**Circulating free motion is excluded on purpose.** An object above the
separatrix is uncontrolled but sweeps the whole longitude ring, so it meets
every other object's slot in turn and would carry approach events into the
control by geometry alone. Excluding it is conservative toward a smaller,
cleaner class, and the exposure that choice costs is reported (§8).

### 4.3 The pair-level test — criterion (b)'s energy form

**A5 — no energy step.** For every consecutive admissible pair `(j−1, j)`
inside a run, with `Δt = t_j − t_{j−1}`:

```
|s_j − s_{j-1}|  ≤  Δt · max( |v_{j-1} sin 2u_{j-1}| , |v_j sin 2u_j| )
                    +  5 · sqrt( σ_s,j² + σ_s,j-1² )
                    +  σ_r² / (2 A_r)
σ_s,j  =  |v_j| · σ_r / A_r ,        σ_r = σ_n in rad/day = 1.0540e-5
```

The first term is the κ-free free-motion bound (3.2.3) integrated over the
interval, taken at the larger endpoint so that it is one-sided. The second is
the propagation of the **measured** σ_n into `s` at 5σ, `BURN_SIGMA_K`
unchanged from T8a. The third is the second-order noise term, which does not
cancel in a difference. Every constant is committed or derived; none is
chosen here.

A violation **breaks the run**: the epoch ends at `j−1` and a new candidate
begins at `j`. It does not condemn the object.

**Minimum to be testable: 2 element sets.**

### 4.4 Run-level tests

| Tag | Test | Minimum length that makes it testable |
|---|---|---|
| **A6 — length** | `t_b − t_a ≥ 56.00 d` (`D_pair`, four measured east–west cycles, T11's constant unchanged) **and** ≥ 12 element sets (10 baseline + the 2 the v2 confirmation needs) | — |
| **A7 — criterion (c), no 14.00-day line** | the run is cut into consecutive non-overlapping **56.00-day** blocks from `t_a`; every block with ≥ 8 element sets is fitted by `persistent_pairs.cadence_phasor` at the **fixed 14.00-day** period; the run is **rejected** if any block returns a false-alarm probability `≤ α_N` | one 56.00-day block with ≥ 8 element sets |

**The registered α_N is the family-wise Šidák value at the 0.10 level**,
`α_N = 1 − (1 − 0.10)^(1/N)` over the `N` blocks tested **inside the run**.

This is registered as the primary rather than T11b's per-block 0.10 because
`docs/geo-passive-control-results-20260922.md` §5 **measured** that the
per-block form admits 2 of 200 synthetic free librators: the minimum of `N`
p-values is not a level-0.10 test of anything. That is a committed prior
measurement of the *instrument*, cited here, not a number produced by this
study. The per-block 0.10 form is carried through the whole analysis as a
**registered sensitivity arm** and both are reported whatever they show.

**A7 rejects the whole run rather than splitting it.** A 14.00-day line
anywhere inside a run is evidence of longitude control over the run's span,
and this registration holds no rule for locating that control in time. Whole
rejection is the conservative reading.

**A6's 56.00 d is not a comfort margin.** It is the smallest length at which
A7 is testable at all, and it contains four measured east–west cycles, so a
keeper's burn train cannot fall between two epochs by phase.

### 4.5 Which of T11b's five bounds are local, which need a whole swing

Registered in the form the reviewer's thread asks for, with the minimum epoch
length each would require.

| T11b bound | Local? | Registered disposition here | Minimum epoch length to be testable |
|---|---|---|---:|
| **1 — bound motion in one cell**, `\|u\| < 90°`, one stable longitude | **LOCAL** | **A3**, a gate | 1 element set |
| **2 — a turnaround exists**, a `λ'` sign change with ≥ 30 d of each sign | **NOT LOCAL** | **NOT a gate.** Computed per epoch and used as a registered **stratification** (§6) | ≥ 60 d, and only near a turnaround: a free librator passes through 2 turnarounds per full period `T(u_max) ≥ 815.48 d`, so an epoch drawn at random contains one with probability ≈ `2 × 60 / T(u_max) ≤ 0.147` |
| **3 — the swing is centred**, `\|u_mid\| ≤ max(5°, 0.25 u_max)` | **NOT LOCAL** — needs both extremes of the swing | reported for epochs long enough, never a gate | ≥ one half-period, `P½ = 407.74 d` at small amplitude, 559.8 d at 60° |
| **4 — rate bound**, `max\|λ'\| ≤ 1.25 · 0.4414582 sin u_max` | **LOCAL once `u_max` comes from the first integral** | **A4**, a gate, in the form `s ≤ 1` | 1 element set |
| **5 — period bound**, median turnaround interval `≥ 0.80 P½(u_max)` | **NOT LOCAL** — needs two turnarounds | reported for epochs long enough, never a gate | ≥ one full period, `T(u_max) ≥ 815.48 d` |

**Bound 2 is the registration's central decision and it is made here, in
advance, for a stated physical reason.** Requiring a turnaround inside every
epoch would do two things: it would cut the admitted exposure by at least
6.8× (the probability above), and — decisively — **it would select exactly
the turnaround dwell that T11b §7.1 measured as the leak**. A control whose
admission rule selects the failure mode is not a control. Bound 2 is therefore
demoted from a gate to a **pre-specified stratification**, so that the leak can
be read separately on epochs that contain a turnaround and on epochs that do
not. That stratification is registered in §6 and is the mechanism claim's own
falsification test.

---

## 5. Exposure

Computed on T11's daily grid, with the same global origin, and reported
whether or not anything is zero.

| Quantity | Definition |
|---|---|
| **epochs** | admitted runs |
| **epoch-days** | `Σ (t_b − t_a)` over admitted epochs, in days |
| **objects** | distinct objects carrying ≥ 1 admitted epoch |
| **epoch object-days** | days `d` with `⌈t_a⌉ ≤ d ≤ ⌊t_b⌋` for some admitted epoch, summed over objects |
| **pair-epoch-days** | `Σ_d C(k_d, 2)` where `k_d` is the number of objects inside an admitted epoch on day `d` |

### 5.1 The matched reference, registered so the units cannot drift

Every leak ratio compares a class rate to a reference rate **computed by the
same function over the same kind of day**. The reference population is the
**payload (active) class minus T8a's v1 `never_manoeuvred` set**, as T11b used.

A **watched day** of object `i` is a day lying inside a run of `i`'s element
sets with no internal gap exceeding `MAX_GAP_DAYS = 5.0 d` — a day on which
the detector could have seen the object. Reference exposure is watched
object-days and watched pair-days of the reference population; class exposure
is epoch object-days and pair-epoch-days. Both are days of continuous
coverage, and the same code computes both.

T11b's stationed-day reference is **also** computed and printed beside each
number, so that a disagreement between the two readings is visible rather than
hidden.

---

## 6. The registered stratification

Every exposure count, every leak count and every ratio is reported three ways:

| Stratum | Definition |
|---|---|
| **ALL** | every admitted epoch. The registered **primary**. |
| **TURN** | admitted epochs containing a `λ'` sign change with ≥ 30 consecutive days of each sign (T11b bound 2, `_sign_runs` unchanged) |
| **QUIET** | admitted epochs containing no such sign change |

The strata are disjoint and sum to ALL. They are defined **entirely from the
object's own motion inside the epoch**, read no consumer's output, and are
fixed here before any epoch exists.

---

## 7. Validation BEFORE use — the T8a §7.2 lesson, applied again

Nothing in §4 is validated by being derived. The following runs **before** any
epoch of the real archive is used for any leak count, and its bars are fixed
here.

### V-E1 — synthetic free librators must be ADMITTED

`geo_passive_control.synthetic_librators`, **unchanged**: 200 objects, seed
20260922, `u_max` uniform in [1°, 60°], phase uniform, integrated from
`u'' = −A sin 2u` by fourth-order Runge–Kutta at a 0.01-day step, 20-year
history sampled at the archive's measured median spacing of 0.865 d, drift
perturbed by the **measured** σ_n.

> **Bar: 200 of 200 carry at least one admitted epoch.**

Also reported, and **not** a bar: the admitted fraction of their sampled days,
the epoch count and length distribution, and the TURN/QUIET split. The
admitted day fraction is an exposure-efficiency measurement; the exposure gate
is §9's meaningful-zero requirement, and a second bar on the same thing would
be a bar with no derivation behind it.

### V-E2 — synthetic station-keepers must be EXCLUDED

`geo_passive_control.synthetic_keepers`, **unchanged code**, run in its
`self_consistent=True` form as the **registered primary**: the drift ramp is
the triaxial acceleration at the object's **own** slot rather than the
registered maximum. T11b §10.2 named its own non-self-consistent keeper as a
defect of that registration; this registration fixes it rather than repeating
it. 200 objects, seed 20260923, same sampling, same measured noise.

> **Bar, registered primary: of the keepers whose slot displacement satisfies
> `|u_slot| ≥ u* = 7.3468°` (3.3.1), 100% yield ZERO admitted epochs.**

> **Bar, registered overall: 200 of 200 yield ZERO admitted epochs.**

The two bars differ because §3.3 **derived in advance** that a keeper inside
`u*` of a stable longitude has burns the v2 rule cannot separate from noise,
and that at uniform slots 8.16% of 200 — an expected 16 objects — fall there.
If the overall bar is missed:

- the results document reports the miss, names the surviving keepers by their
  `|u_slot|` against `u*`, and states whether every one of them lies inside
  `u*` (the derived exception) or whether any lies outside it (a defect of the
  rule, not of the derivation);
- **registered contingency**: if any keeper outside `u*` is admitted, the
  epoch class is **NOT USED** and the results document says which control it
  does not have. If every admitted keeper lies inside `u*`, the class **may**
  be used, and then every leak number in the document must be printed beside
  the measured fraction of admitted epoch-days whose median `|u|` lies inside
  `u*` — the size of the derived blind spot in the real class.

The maximum-ramp variant (T11b's registered V2 construction) is run and
reported as a labelled arm.

### V-E3 — the two bugs the test suite must catch, registered as tests

Asserted in `tests/test_geo_epoch_control.py` before any archive run:

1. **A keeper interval sandwiched between two free intervals must be split
   out, not averaged in.** A synthetic history of free libration, then a run
   of east–west keeping at the measured cycle, then free libration again, must
   yield **two** admitted epochs whose union excludes the keeping interval —
   never one epoch spanning it.
2. **A free librator sampled at 2-day spacing must be admitted.** At 2-day
   spacing the v2 baseline span is ≈ 11 d, inside the 14.00-day evaluability
   ceiling, and free motion over that baseline is `A × 11 d = 1.87e-2 deg/day`
   — 6.2× the `5σ_n` term. An implementation that thresholds on a constant, or
   that fails to subtract the predicted free motion, flags the librator and
   admits nothing. The test asserts admission.

### V-E4 — the parity split

Every class count and every leak ratio is recomputed on the even-NORAD and
odd-NORAD halves separately and reported side by side. A leak rate differing
by more than a factor of 3 between the halves is reported as **unstable** and
the pooled number is qualified by that word. This is a stability check, not a
fit: no rule in §4 has a free parameter.

**If V-E1 or V-E2's primary bar is missed, the class that failed is NOT USED**,
the failure is reported with its measured rate, and the results document says
which control it does not have (gate G-E6).

---

## 8. The leak proof — what must be zero, against what exposure, per consumer

The **unchanged** detectors are re-expressed over the admitted epochs. Rates,
never counts. The registered bar in every case is T8b's gate-B bar as T11b
carried it: **a ratio of class rate to reference rate above 0.10 means the
control leaks.**

### 8.1 Consumer 1 — T8a events

- **Numerator**: rows of `docs/proximity-events-20260922.jsonl` at T8a's
  primary arm whose **approacher** is a class member and whose **`arrivalMs`**
  lies inside one of that member's admitted epochs. The arrival is registered
  as the anchor because the loiter that defines a T8a event is anchored to it
  and because T11b §7.1 reported its leak as arrivals.
- **Registered secondary readings, both reported**: (i) events whose
  `transferStartMs` lies inside an admitted epoch; (ii) events whose whole
  `[transferStartMs, departureMs]` span lies inside one admitted epoch.
- **Denominator**: epoch object-days.
- **Reference**: the same numerator rule over reference-population objects on
  watched days, divided by reference watched object-days.

### 8.2 Consumer 2 — T11 episodes

- **Numerator**: rows of `docs/persistent-pairs-20260922.jsonl` whose **both**
  members have an admitted epoch **containing the whole episode window**
  `[startMs, endMs]`.
- **Registered secondary reading**: both members have an admitted epoch
  **overlapping** the episode window at all.
- **Denominator**: pair-epoch-days.
- **Reference**: episodes with both members in the reference population, over
  reference watched pair-days.

### 8.3 Consumer 3 — trigger-time flags

The alarm lane's GEO trigger is T8d's: a chain of T8a **v1** drift-change
flags, merged at `MAX_GAP_DAYS = 5.0 d`, the trigger epoch being the last flag
of the chain. It is evaluated by `trigger_alarm.flag_baselines` and
`trigger_alarm.chain_flags`, **unchanged and unmodified**, run over class
members **regardless of catalogue class** — which is exactly how T8b proved
its LEO control.

- **Numerator**: trigger chains whose `t_trig` lies inside an admitted epoch.
- **Denominator**: epoch object-days.
- **Reference**: the same arithmetic over reference-population objects on
  watched days, over reference watched object-days.

**Registered in advance, because it is a prediction and not a hope.** T11b §2
measured that **51 of 1,652 objects lose every one of their v1 flags** when
free motion is predicted and subtracted, and that the v1 constant floor reads
free libration as up to 2,035 manoeuvres on a single rocket body. The v1
trigger is therefore **expected** to fire inside free-libration epochs, and
this consumer is expected to leak. It is registered and reported anyway,
because a control that is honest about which consumer it cannot serve is worth
more than one that quietly reports two of three. The **v2** rule is run over
the same epochs as a **labelled addendum** so the size of the v1-versus-v2
difference is visible; it is not a consumer, because no shipped lane uses it.

### 8.4 The meaningful zero, registered per consumer

For each consumer `c` with reference rate `R_c`, the exposure at which a
single event is expected is

```
N*_c  =  1 / R_c
```

Every zero in the results document is printed with **both** the exposure that
produced it and `N*_c`. A class whose admitted exposure is below `N*_c` has
**not** passed that consumer: it is **UNEVALUABLE** for it, in that word, and
the word *leak-free* may not be used.

Intervals on every ratio by `persistent_pairs.rate_ratio_ci` (exact Poisson),
unchanged.

---

## 9. The decision rule, and what falsifies the claim

For each of the three strata of §6 and each of the three consumers of §8 —
nine pre-specified readings, all nine reported:

| Reading | Condition |
|---|---|
| **UNEVALUABLE** | admitted exposure `< N*_c` |
| **LEAK-FREE** | admitted exposure `≥ N*_c` **and** leak ratio `≤ 0.10` |
| **LEAKS** | admitted exposure `≥ N*_c` **and** leak ratio `> 0.10` |

**The verdict sentence, and the only two forms it may take.**

> **a GEO epoch control EXISTS** — permitted if and only if at least one
> (stratum, consumer) reading is **LEAK-FREE**. The sentence must name the
> stratum and the consumer, print that reading's exposure against its `N*_c`,
> and state which of the other eight readings are UNEVALUABLE and which LEAK.

> **a GEO epoch control DOES NOT EXIST** — written in those words if no
> reading is LEAK-FREE.

**The registered falsifier, stated as the reviewer's thread asks.** If the
admitted exposure is below `N*_c` for **every** consumer in **every** stratum,
the answer is **a GEO epoch control DOES NOT EXIST**, and the reason printed
is *insufficient admitted exposure*, not *a leak*. A zero on too little
exposure is not evidence, and this registration will not let one be read as
though it were.

**Multiplicity is acknowledged here rather than argued away later.** Nine
readings are registered, all nine are printed, the verdict names the one it
rests on, and the results document states plainly that the verdict is the
*best* of nine pre-specified readings and must be read as such.

Sensitivity arms — the per-block 0.10 cadence form, the secondary numerator
readings of §8.1 and §8.2, the maximum-ramp keeper, the stationed-day
reference, the parity split — are reported in full and **cannot change the
primary verdict**.

---

## 10. Gates

| Gate | Registered meaning | Condition |
|---|---|---|
| **G-E1** | the epoch rule admits nothing | zero admitted epochs → the verdict is DOES NOT EXIST, reason *no admitted exposure* |
| **G-E2** | the exposure cannot support a zero | admitted exposure `< N*_c` for every consumer in every stratum → DOES NOT EXIST, reason *insufficient admitted exposure* |
| **G-E3** | the control leaks | every evaluable reading has ratio `> 0.10` → DOES NOT EXIST, reason *leak*, with T11b §13.1's sentence **the GEO catalogues remain uncontrolled** repeated verbatim |
| **G-E4** | the stratification is degenerate | either TURN or QUIET holds zero admitted epochs → that stratum is UNEVALUABLE and the word is used |
| **G-E5** | the rules do not do what they were derived to do | V-E1 or V-E2's primary bar missed → the class is NOT USED |
| **G-E6** | the derived blind spot is material | any keeper **outside** `u*` admitted → the class is NOT USED (§7 contingency) |
| **G-E7** | provenance | any pin in §1 fails to verify → the run aborts and reports nothing |

Every gate is reported with its measured value whether it fires or not.

---

## 11. Declared blind spots

1. **`A` is an upper bound, not any object's own restoring acceleration.**
   Every test in §4 is one-sided for that reason, which makes them
   conservative in the direction of **admitting too much**. A control that
   admits too much leaks; this registration cannot remove that and does not
   claim to.
2. **The energy test is blind to a symmetric velocity reversal** (§3.3),
   derived here and not discovered later.
3. **A keeper within `u* = 7.3468°` of a stable longitude is separable only by
   the 14.00-day line**, whose power inside a single 56-day epoch is measured
   by V-E2 and not derived.
4. **Evaluability is inherited from T11b and removes 47% of the objects there.**
   Applied per sample here it will remove intervals rather than objects, but
   the same sparsely sampled history is still unjudgeable and its cost is
   reported as lost exposure, never as a clean class.
5. **Recall is unmeasured**, inherited unchanged from T11 §9.2. Every count is
   a lower bound.
6. **An epoch is not a proof of an object's state.** It is a statement about an
   interval of an object's history, and nothing here licenses a sentence about
   the object outside that interval.
7. **The catalogues are the ones T8a and T11 committed.** A detector defect in
   either travels into every leak count here unchanged.
8. **The verdict is the best of nine pre-specified readings** (§9).

---

## 12. Compute, provenance, determinism

CPU only, on `pc`; nothing on the VPS and no GPU. Seed **20260922** for the
librator synthetic and **20260923** for the keeper synthetic; no other
randomness. `scipy` is not installed on the host, so every special function
(the arithmetic–geometric-mean elliptic integral, the incomplete beta, the
exact Poisson interval) is the one already implemented and tested in
`persistent_pairs` and `geo_passive_control`, reused rather than rewritten.

Outputs:

- `docs/geo-libration-epoch-control-results-20260922.md`
- `docs/geo-libration-epoch-control-20260922-receipt.json` — the archive
  provenance, the §1 pins, the derivations, every validation with its bar,
  every stratum × consumer reading with its exposure and its `N*`, the parity
  split, and the source SHA-256 of the instrument
- `docs/geo-libration-epochs-20260922.jsonl` — one row per admitted epoch:
  object, start, end, element sets, `û_max`, stratum, and nothing that names a
  motive

---

## 13. What is committed with this document

This file, **alone**, before:

- `tools/geo_epoch_control.py`;
- `tests/test_geo_epoch_control.py`, whose first assertions are the two bugs
  of §7 V-E3;
- the results document, the receipt and the epoch catalogue;
- the runbook rows for T8 and T11.

If any measurement in this document turns out to have been mis-specified, the
defect is **reported in the results document and not edited out of this one**,
as T11 reported the φ_lock degree gloss, as T11b reported R1's missing
precision and F1's multiplicity, and as T8a reported its falsified dwell
bound.
