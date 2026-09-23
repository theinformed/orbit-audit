# T11b part 2 results: a GEO passive control, built by construction — **the GEO catalogues remain uncontrolled**

**Registration:** `docs/persistent-pairs-response-preregistration-20260922.md`,
committed alone at `0aa028a` before the instrument existed.

**Verdict, in the registered words:** the registered primary control, class
**I**, contains **zero objects and zero pair-exposure-days** and is therefore
**UNEVALUABLE**, exactly as T11's inherited control was. The best candidate
that has exposure produces **three T8a events over 2,635 stationed
object-days** against an expectation of 0.346 — an event leak ratio of
**8.67**, 95% [1.78, 25.50], against a registered bar of 0.10. Therefore:

> **the GEO catalogues remain uncontrolled**

**What is nonetheless established, and is the point of this document:** the
mechanism is now measured rather than supposed, the v2 rule works and is
validated against synthetic free motion and synthetic station-keeping before
being used, and T11's 1,317 episodes can be re-expressed with **positive**
evidence rather than with an absent control — **1,237 of them (93.9%) carry a
confirmed drift change on *both* members *inside the episode itself*.**

---

## 1. What ran

| | |
|---|---|
| Host | `pc`, CPU only, 105 s plus a 45 s world build |
| Inputs | `docs/persistent-pairs-20260922.jsonl` (SHA-256 verified against the registered pin) and `docs/proximity-events-20260922.jsonl`, 493 T8a events |
| Population | the same 1,652 near-GEO objects, the same station segments, the same measured σ_n |
| Determinism | seed 20260922 for every synthetic |

## 2. The physics, recomputed and reported

Every constant is T8a's committed J₂₂ derivation or T8a's measured noise
floor. Nothing is fitted.

| Quantity | Derivation | Value |
|---|---|---:|
| `A`, maximum longitude acceleration | T8a prereg §2.6, unchanged | **1.7006955627927864e-3 deg/day²** |
| Stable longitudes | T8a prereg §2.6, unchanged | **75.1° E, 104.7° W** |
| `ω₀ = sqrt(2A)` | the pendulum's small-amplitude rate | 7.704899e-3 rad/day |
| **`T₀ = 2π/ω₀`** | small-amplitude libration period | **815.4792 d = 2.2327 yr** |
| **Amplitude–rate coefficient** | `|λ'|_max = sqrt(2A)·sin u_max` | **0.4414582 deg/day** |
| σ_n | T8a's measured drift noise, unchanged | 6.038534e-4 deg/day |
| 5σ_n | T8a's noise term, unchanged | 3.019267e-3 deg/day |
| Free-motion drift change over one element set (0.865 d) | `A·Δt` | 1.4711e-3 deg/day |
| **Free-motion drift change over the flag's 10-sample baseline (8.65 d)** | `A·Δt` | **1.4711e-2 deg/day** |
| **T8a's constant flag floor** | T8a prereg §5.5 | **1.0e-2 deg/day** |
| East–west keeping burn at the measured 14.00 d cycle | `A·T/2` | 1.1905e-2 deg/day |

**The derivation the registration made before measuring**: free motion alone
moves the drift rate by up to 1.4711e-2 deg/day across the flag's own baseline
window, which is **1.47× above** T8a's constant floor. A free object observed
across an ordinary catalogue gap therefore crosses that floor without having
manoeuvred.

**Measured, and it is the number that derivation predicted**: **51 of the
1,652 near-GEO objects lose every one of their T8a v1 flags** once free motion
is predicted from the object's own longitude and subtracted. Those objects
were flagged by the archive's sampling and by triaxiality, not by anything
they did.

A one-sided caution, carried from T8a §7.2 and applied here throughout: `A` is
an **upper bound** on the restoring acceleration, because a real object's
equilibrium is displaced by solar radiation pressure and modulated by
luni-solar terms. Every libration test below is therefore written one-sided —
free motion cannot be *faster* than the bound, and cannot turn around
*sooner*. T8a's falsified dwell bound assumed the opposite and this
registration does not repeat it.

## 3. The T8a v2 rule

```
base_i   = median( d_{i-10 .. i-1} )                  # T8a's baseline, unchanged
t_c,i    = median( t_{i-10 .. i-1} )
acc(λ)   = − A · sin( 2 ( λ − λ_s(λ) ) )
pred_i   = 0.5 · ( acc(λ_c,i) + acc(λ_i) ) · ( t_i − t_c,i )
dev_i    = | d_i − base_i − pred_i |
thresh_i = max( 5 σ_n , | acc(λ_i) | · ( t_i − t_c,i ) )
flag     = dev_i > thresh_i at two consecutive element sets
```

In words: *a drift change is evidence of a manoeuvre only when it exceeds the
measured noise floor and is more than twice what free triaxial motion at this
longitude could have produced over the same interval.* No constant floor.

**Evaluability bites hard, and is reported rather than hidden.** A sample
whose baseline span exceeds 14.00 d is not evaluable, because past that the
free-motion allowance exceeds `A·14 = 2.381e-2 deg/day` and the rule stops
discriminating. **775 of 1,652 objects (46.9%)** exceed the registered 5%
non-evaluable ceiling and are refused admission to any class. That is not a
failure of the rule; it is the archive's sampling, stated as a number.

## 4. Validation BEFORE use — the T8a §7.2 lesson applied to a control

### V1 — synthetic free librators must be admitted

200 objects, `u_max` uniform in [1°, 60°], integrated from `u'' = −A sin 2u`
by RK4, 20 years at the archive's median 0.865-day spacing, drift perturbed by
the **measured** σ_n.

| | measured | bar | |
|---|---:|---:|---|
| Zero v2 flags | **200/200 = 1.000** | ≥ 0.95 | **pass** |
| Pass the five libration bounds F2 | **200/200 = 1.000** | ≥ 0.95 | **pass** |
| Admitted by the **registered** F1 rule | **2/200 = 0.010** | — | see §5 |
| Admitted by the family-wise F1 rule | 193/200 = 0.965 | — | see §5 |

The integrated pendulum's own half-period agrees with the closed-form
`(1/π)·T₀·K(sin u_max)` to better than 1% at every amplitude tested, and for
one 59.5° librator the observed half-period was **556.42 d** against a
predicted **556.42 d**. The period–amplitude law describes the equation it
came from.

### V2 — synthetic station-keepers must be excluded

200 sawtooth keepers at the measured 14.00-day cycle, same sampling, same
measured noise.

| | registered construction | self-consistent variant (labelled addition) | bar |
|---|---:|---:|---:|
| Carry ≥ 1 v2 flag | **200/200 = 1.000** | 182/200 = 0.910 | ≥ 0.95 |
| Fail libration criterion 2 or 5 | **200/200 = 1.000** | 200/200 = 1.000 | ≥ 0.95 |
| Excluded by the registered F1 | 200/200 | 200/200 | — |
| **V2 verdict** | **pass** | — | |

The self-consistent variant — a post-registration addition in which the ramp
rate is the triaxial acceleration at the object's *own* slot rather than the
registered maximum — flags 91% rather than 100%, below the bar. It is not the
registered gate and does not change V2's verdict, but it is the more faithful
synthetic and it says the v2 rule misses about one keeper in eleven when the
slot sits close to a stable longitude and the burns are correspondingly small.

### V3 — the detection floor, measured and not assumed

The burn was scaled from 0.1× to 2.0× of `A·T/2`. **At the smallest scale
tested — 1.1905e-3 deg/day, a tenth of a routine east–west keeping burn — the
rule already flags 86% of synthetic keepers.** The detection floor is
therefore **at or below 1.19e-3 deg/day** and was not resolved downward by
this ladder. The registration's contingency — *"if that floor exceeds
`A·T/2` = 1.1905e-2 deg/day, say that a routine keeping burn is below the v2
detection floor"* — **does not apply**: a routine keeping burn is ten times
above the floor.

### V4 — the parity split

Not evaluable: the primary class is empty, so both halves are empty.

**G6 did not fire.** V1 and V2 both cleared their registered bars.

## 5. A defect in this registration, measured by its own validation

The registered F1 rule excludes an object if **any** of its 56-day blocks
returns a cadence false-alarm probability ≤ 0.10. A 20-year object has about
**131 blocks**, so under the null the minimum of 131 p-values is below 0.10
with probability `1 − 0.9¹³¹ ≈ 1.000`. **The registered F1 rule throws out
99% of synthetic free librators** (V1: 2 admitted of 200) and would empty the
class it was written to build.

This is reported, not edited out of the registration. Alongside the registered
rule, every class is also computed with the **family-wise threshold at the
same registered 0.10 level** — the Šidák per-block value
`1 − 0.9^(1/N)`, which introduces no new constant and no tuned parameter.
Both variants are carried through the leak proof below and **both are reported
whatever they show**, because the leak measurement is the gate and a class
that leaks fails however it was built.

## 6. The classes

| | count of 1,652 |
|---|---:|
| Payload class | 1,308 |
| Catalogue-passive class | 307 |
| **T8a v1 `never_manoeuvred`** (T11's control) | **9** |
| Zero **v2** flags | 110 |
| … and admissible (≥ 200 element sets, ≥ 365 d) | 44 |
| **v1-flagged but v2-clean** — free motion converted into flags | **51** |
| Non-evaluable under the 14-day baseline rule | 775 |
| Passing **F1** as registered (no 14.00-day line in any block) | 21 |
| Passing F1 at the family-wise threshold | 112 |
| Passing **F2** (all five libration bounds) | 28 |
| … failing only the period bound | 4 |
| **Class D** (payload, admissible, evaluable, zero v2 flags) | **3** |
| **Class F** (F1 registered ∧ F2) | **0** |
| **Class I = D ∩ F — the registered primary control** | **0** |
| Class F, family-wise variant | 5 |
| Class I, family-wise variant | **0** |

**Class D's three members are all station-keepers, by positive evidence.**

| NORAD | name | type | v1 flags | v2 flags | blocks | minimum block FAP |
|---:|---|---|---:|---:|---:|---:|
| 8482 | OPS 3165 | PAYLOAD | 50 | 0 | 46 | 3.09e-4 |
| 23132 | UFO 3 (USA 104) | PAYLOAD | 93 | 0 | 70 | 3.92e-6 |
| 59479 | DUMMY SAT 3/ORION | PAYLOAD | 1 | 0 | 14 | **2.92e-14** |

All three carry the measured 14.00-day east–west line at family-wise
significance — 59479 at a false-alarm probability of 3e-14. **A class built on
the absence of drift-change flags alone contains objects that are visibly
holding a station.** That is class D failing on its own, and it is why the
registration made the primary control the *conjunction*.

**Class F's five family-wise members are all catalogue-passive.**

| NORAD | name | type | v1 flags | v2 flags | `u_max` | turnarounds | minimum block FAP |
|---:|---|---|---:|---:|---:|---:|---:|
| 17874 | SL-12 R/B(2) | ROCKET BODY | 2,035 | 12 | 24.85° | 39 | 9.04e-4 |
| 22839 | SL-12 R/B(2) | ROCKET BODY | 1,654 | 6 | 75.63° | 15 | 7.87e-4 |
| 26939 | SL-12 R/B(2) | ROCKET BODY | 1,151 | 4 | 29.06° | 22 | 5.72e-3 |
| 40924 | COSMOS 1700 DEB | DEBRIS | 366 | 3 | 27.14° | 10 | 3.86e-2 |
| 43645 | FENGYUN 2H DEB | DEBRIS | 78 | 195 | 22.88° | 7 | 3.76e-3 |

Every one of them carries v2 flags, so none is in class D, so the intersection
is empty in the family-wise variant too. Their v1 flag counts — up to 2,035 —
against their v2 counts of 3 to 12 are the §2 measurement again: **the
constant floor reads free libration as hundreds of manoeuvres.**

## 7. The leak proof, with the exposure printed beside every zero

Rates, never counts. The reference is the payload class outside
`never_manoeuvred`: **1,306 objects, 712,483,466 pair-exposure-days, 1,317
episodes (1.8485e-6 per pair-day); 3,717,395 stationed object-days, 488 T8a
events (1.3127e-4 per object-day).**

| Class | objects | pair-exposure-days | episodes | T8a events | stationed object-days | event rate | **event leak ratio** | verdict |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| **I — registered primary** | **0** | **0** | 0 | 0 | 0 | — | — | **UNEVALUABLE** |
| I, family-wise | 0 | 0 | 0 | 0 | 0 | — | — | **UNEVALUABLE** |
| D | 3 | **0** | 0 | 0 | 578 | 0.000 | 0.000 | **UNEVALUABLE** (and §6) |
| F, registered | 0 | 0 | 0 | 0 | 0 | — | — | **UNEVALUABLE** |
| **F, family-wise** | **5** | **232** | **0** | **3** | **2,635** | 1.1385e-3 | **8.67** [1.78, 25.50] | **LEAKS** |
| T8a v1 `never_manoeuvred` | 9 | **0** | 0 | 0 | 3,029 | 0.000 | 0.000 | **UNEVALUABLE** (T11 §2.3, reproduced) |

**Gate G4 fired: the registered primary control does not exist.** Zero
objects, zero pair-exposure-days. Gate G5 did not fire only because a class
with no exposure cannot be shown to leak.

**The bound on what a zero can mean, computed and applied.** A zero is
evidence only against the exposure that produced it:

| | |
|---|---:|
| Episodes expected in class F's 232 pair-days at the payload rate | **0.00043** |
| **Pair-exposure-days needed for one expected episode** | **540,990** |
| T8a events expected in class F's 2,635 object-days at the payload rate | **0.346** |
| T8a events expected in class D's 578 object-days | 0.076 |
| T8a events expected in the v1 class's 3,029 object-days | 0.398 |

**Class F's zero episodes over 232 pair-days is not evidence of anything** —
it is 1/2,330th of the exposure a single expected episode would need. Neither
is class D's zero events over 578 object-days, nor the v1 class's zero over
3,029. The only measurement in the table with the exposure to speak is class
F's **three T8a events against 0.346 expected**, and it says the class leaks
by a factor of 8.67, with the interval's lower end still 18 times the bar.

### 7.1 The leak has names, and T8a already knew them

| approacher | arrival | object approached | loiter | longitude | transfer drift |
|---|---|---|---:|---:|---:|
| 43645 FENGYUN 2H DEB | 2020-09-11 | 32478 EXPRESS AM-33 | 30.9 d | 96.54° | 0.0367 °/d |
| 22839 SL-12 R/B(2) | 2021-03-19 | 37816 EUTE 7 WEST A (AB 7) | 67.3 d | −7.29° | 0.0049 °/d |
| 43645 FENGYUN 2H DEB | 2022-10-27 | 42695 GSAT 9 | 30.0 d | 97.36° | 0.0345 °/d |

**These are three of the five events T8a §7.1 listed as its passive-class
leak.** The class built here to be leak-free by construction turns out to be
made of precisely the objects that generated T8a's leak — which is the
deepest result in this document and is a fact about GEO rather than about any
rule: *free libration through a turnaround is itself a slow approach and a
sustained co-location.* An object with no fuel, held by triaxiality alone,
reverses its longitude near its swing's end and sits there for tens of days.
T8a's detector is built to find exactly that shape, so a control of free
librators cannot be empty of T8a events. None of the three is inside T8a's
±3.75° libration flag, which T8a §7.2 had already falsified.

## 8. The E1 re-expression — proven station-keeping against geometry

T11's 1,317 episodes, split by the registered rule of §14. The categories are
disjoint and sum to 1,317.

| Category | Definition | count | of 1,317 |
|---|---|---:|---:|
| **Proven station-keeping** | **both** members carry a **v2** flag with its epoch **inside the episode window** | **1,237** | **93.9%** |
| **Geometry only** | a member is in the primary control class, or fails the evaluability rule | **58** | 4.4% |
| **Unproven** | neither | **22** | 1.7% |

Because the primary control class is empty, all 58 "geometry only" episodes
are there for the evaluability reason — one member's sampling is too sparse
for the v2 rule to discriminate — and none because a member was proved
passive.

Two further counts, reported as labelled additions:

| | count |
|---|---:|
| Episodes where both members carry **any** T8a v1 flag over their whole history | **1,317 (all)** |
| Episodes that are **cadence-testable** in T11's own sense (both members' 14.00-day line at FAP ≤ 0.01 *during the episode*) | **449** |

The v1 figure is uninformative — §2 shows why a v1 flag is not proof of a
manoeuvre. The cadence figure is a second, independent line of positive
evidence and it agrees in direction while being far more conservative,
because it demands the line be detectable inside the episode's own window
against the fit noise of a tight box.

**The answer to the question T11 §2.3 posed.** T11 said every E1 count is a
count of geometry that could not be proven to be station-keeping. With the v2
rule, **1,237 of the 1,317 can be proven to be station-keeping by positive
evidence — a confirmed drift change on both members while they were beside
each other — and 22 remain unproven.** The proof runs the other way from the
one the registration expected: not by excluding a passive class, which does
not exist at GEO, but by demanding evidence of control from each member.

## 9. Gates

| Gate | Meaning | Measured | Fired |
|---|---|---|---|
| **G4** | the passive class does not exist | class I: 0 objects, 0 pair-exposure-days | **yes** |
| G5 | the passive class leaks | not evaluable for class I; **8.67 for the family-wise class F** | no (for want of exposure) |
| G6 | the class rules do not do what they were derived to do | V1 and V2 both cleared | no |
| G7 | provenance | both catalogue pins verified | no |

## 10. Defects and blind spots

1. **The registered F1 threshold is a per-block test applied N times** (§5).
   Measured: it admits 1% of synthetic free librators.
2. **The registered V2 synthetic is not self-consistent** (§4): its ramp rate
   is the maximum triaxial acceleration rather than the acceleration at the
   object's own slot. The faithful variant flags 91%, below the bar.
3. **Evaluability removes 47% of the population** (§3), and no registered rule
   recovers them. A control cannot be built from objects the archive samples
   too sparsely to judge.
4. **`A` is an upper bound, not a measurement of any object's own restoring
   acceleration.** Every test here is one-sided for that reason, which makes
   them conservative in the direction of admitting too much.
5. **Recall is unmeasured**, inherited unchanged from T11 §9.2.
6. **The class sizes are tiny and the exposure is tinier.** Nothing in §7
   except the three events has the exposure to support a conclusion.

## 11. Owed

1. **A GEO control that has exposure at all.** Class I has none, and the
   reason is now measured rather than assumed: at GEO a stationed passive
   object is a librator at its turnaround, and a librator at its turnaround
   produces exactly the events the detectors look for. A control may have to
   be built on something other than station segments — for instance on
   *epochs* of free motion inside an object's history rather than on objects.
2. **A registered F1 with its multiplicity** (§5), and the classes recomputed
   under it as a registered rather than a labelled quantity.
3. **A self-consistent keeper synthetic** as the registered V2 (§10.2).
4. **The evaluability gap** (§10.3): a v2 variant for sparsely sampled
   objects, or an honest statement that 47% of near-GEO objects cannot be
   classified from this archive.

## 12. Reproduction

```
git show 0aa028a --stat     # the registration, committed alone
python3 -m unittest tests.test_geo_passive_control     # 27 tests
python3 tools/geo_passive_control.py                   # 45 s + 105 s, CPU
```

Receipt: `docs/geo-passive-control-20260922-receipt.json` — the derivations,
every validation with its bar, every class with its exposure and its leak, the
parity split, the E1 re-expression, and the per-object rows for every class
member. Nothing from T11b was written to `src/`, `data/`, `public/` or any
site surface.
