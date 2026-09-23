# Results: a GEO control built on epochs of free libration — **a GEO epoch control DOES NOT EXIST**

**Registration:** `docs/geo-libration-epoch-control-preregistration-20260922.md`,
committed alone at `86e80c3` before the instrument existed.

**Verdict, in the registered words:**

> **a GEO epoch control DOES NOT EXIST**

**and the registered reason is a LEAK, not an absence of exposure.** Eight of
the nine pre-specified readings are **evaluable** — the registered falsifier,
*admitted exposure below the meaningful zero for every consumer*, did **not**
fire — and **none** of the nine is leak-free.

**What the epoch unit nonetheless achieved, and it is the point of this
document.** T11b's object-level control had **232 pair-exposure-days against
the 540,990 a single expected episode needs** — 1/2,330th — so its zeros meant
nothing. Epochs give **23,960,622 pair-epoch-days against the 2,523,960 one
expected episode needs**, and **517,391 object-days against 16,747**. The
exposure problem is solved. What replaces it is a measured leak with an
interval, on a class that has the exposure to carry one.

**And the mechanism is now measured and is broader than the one T11b named.**
T11b said the leak is the *turnaround*. The leak falls monotonically with
libration amplitude — that is, with **speed** — and the epochs that contain
**no** turnaround leak on their own at 1.63× the active-payload rate. It is
slowness, and the turnaround is only its extreme case.

---

## 0. The gates, printed above everything

| Gate | Registered meaning | Measured | Fired |
|---|---|---|---|
| **G-E1** | the epoch rule admits nothing | 2,605 admitted epochs | no |
| **G-E2** | the exposure cannot support a zero | 8 of 9 readings evaluable | no |
| **G-E3** | the control leaks | 0 of 9 readings leak-free | **yes** |
| **G-E4** | the stratification is degenerate | TURN 163, QUIET 2,442 | no |
| **G-E5** | the rules do not do what they were derived to do | V-E1 191/200 against 200/200; V-E2 primary 183/184 against 100% | **yes** |
| **G-E6** | the derived blind spot is material | 1 keeper admitted outside `u*` | **yes** |
| **G-E7** | provenance | both catalogue pins verified | no |

**G-E5 and G-E6 fired, so by the registered contingency of §7 the epoch class
is NOT USED.** The verdict does not depend on that: every reading the class
would have supplied **leaks**, so the answer is the same whether the class is
used or withheld. Both statements are printed because the registration
requires the contingency to be honoured and because a reader is entitled to
the numbers that would have been read.

---

## 1. What ran

| | |
|---|---|
| Host | `pc`, CPU only. 60 s world build, 30 s epoch pass, 108 s total analysis |
| Inputs | `docs/persistent-pairs-20260922.jsonl` (SHA-256 verified against the registered pin), `docs/proximity-events-20260922.jsonl` (493 rows), the T11 gate-F extract (217,007,154 rows scanned, 11,626,494 kept, 1,768 objects) |
| Population | the same 1,652 near-GEO objects, the same measured σ_n = **6.038534e-4 deg/day** |
| Determinism | seed 20260922 for the librator synthetic, 20260923 for the keeper synthetic; no other randomness |
| Site surfaces | nothing written to `src/`, `data/`, `public/` or any page |

---

## 2. The physics, recomputed

Every constant is carried from T8a's committed J₂₂ derivation or T8a's
measured noise floor. Nothing is fitted.

| Quantity | Value |
|---|---:|
| `A` | 1.7006955627927864e-3 deg/day² |
| `2A_r` | 5.9365474e-5 rad/day² |
| `T₀ = 2π/sqrt(2A_r)` | 815.4792 d |
| σ_n / 5σ_n | 6.038534e-4 / 3.019267e-3 deg/day |
| east–west keeping burn at the maximum acceleration `A·T/2` | 1.1904869e-2 deg/day |
| **`u*` — the derived keeper blind spot** | **7.345800°** |
| catalogue gap that breaks a run | 5.0 d |
| minimum epoch length / element sets | 56.00 d / 12 |

### 2.1 The local first integral did what it was derived to do

`s = sin²u + v²/(2A_r)` is conserved along the pendulum to 1 part in 10⁶ on an
integrated trajectory, equals `sin² u_max` at both the turning point and the
stable longitude to 10–12 decimal places, and equals exactly 1 on the
separatrix. Those four checks are in the test suite. The local rate bound
`s ≤ 1` is therefore T11b's whole-swing rate bound with the amplitude supplied
by the motion itself, and it is testable on **one element set** where T11b's
needed a whole history.

The κ-free one-sided energy bound `|ds/dt| ≤ |v sin 2u|` also did what §3.3
derived: it catches a one-sided drift change and is **exactly blind to a
symmetric velocity reversal**, which the suite asserts to 15 decimal places so
that the blindness is a stated property rather than a later discovery.

---

## 3. Validation BEFORE use — both registered bars were MISSED

### V-E1 — synthetic free librators must be ADMITTED

200 objects, `u_max` uniform in [1°, 60°], 20-year histories at the archive's
median spacing, perturbed by the **measured** σ_n. Generator unchanged from
T11b.

| | measured | bar | |
|---|---:|---:|---|
| Objects carrying ≥ 1 admitted epoch | **191 / 200 = 0.955** | **1.000** | **MISSED** |
| Admitted fraction of their sampled days | 0.9539 | reported, not a bar | — |
| Admitted epochs | 203 | — | — |

**All nine failures have the same shape, and it was checkable in advance.**
Each of the nine had **exactly one** candidate run — the whole 20-year history
— and each was rejected by criterion (c), the cadence test. None was rejected
for length, for sample count or for want of a block.

**That is a defect in this registration, reported and not edited out of it.**
Rule A7 rejects the **whole run** rather than splitting it, and A7's
registered threshold is the **family-wise 0.10 over the blocks inside the
run**. A level-0.10 family-wise test excludes 10% of true nulls by
construction, so the probability that all 200 synthetic librators survive is
`0.9²⁰⁰ ≈ 7e-10`. **A bar of 200/200 asked a level-0.10 test to have level
zero.** The measured 4.5% loss is *better* than the 10% ceiling, because some
librators carry more than one run. The remedy — a bar stated as a fraction
with the test's own level beside it, or a rule that splits a lined run instead
of condemning it — belongs in a new registration, not in this one. It is the
same class of defect as T11b's R1 band stated without its precision.

**A second, separate blind spot in V-E1, declared here.** All 203 admitted
librator epochs are **TURN** epochs and **none** is QUIET, because a 20-year
free history is one epoch containing roughly seventeen turnarounds. The
registered positive control therefore **does not exercise the QUIET
stratum**, which carries 94% of the real admitted epochs and 84% of the real
exposure. Nothing in this registration discharges that.

### V-E2 — synthetic station-keepers must be EXCLUDED

200 sawtooth keepers at the measured 14.00-day cycle, **self-consistent** (the
ramp is the triaxial acceleration at the object's own slot) as the registered
primary — which discharges T11b §10.2's owed item.

| | measured | bar | |
|---|---:|---:|---|
| Keepers yielding zero admitted epochs | **199 / 200** | 200/200 | **MISSED** |
| Keepers **outside `u*`** yielding zero admitted epochs | **183 / 184 = 0.9946** | 1.000 | **MISSED** |
| Labelled arm — the maximum-ramp keeper (T11b's registered construction) | **200 / 200 excluded**, 0 outside `u*` | — | — |

**The one admitted keeper, and the derivation defect it exposes.** Its slot is
−14.659°, which is **89.759°** from the nearer stable longitude — **0.241°
from an *unstable* longitude.**

The registration's §3.3 solved `A|sin 2u| · T/2 > 5σ_n` **for `u` near zero
only**. The triaxial acceleration `−A sin 2u` vanishes at `u = 0` **and at
`u = ±90°`**. The blind band is therefore

```
|u| < u*   OR   |u| > 90° − u*            u* = 7.345800°
```

— **16.32%** of longitude, not the 8.16% the registration stated. The single
escapee lies inside the band the completed derivation predicts, 0.241° from
its centre, and 33 of the 200 keepers fall in that completed band while only
one survived: the 14.00-day line caught the other 32. **The derivation was
incomplete, the validation found it, and it is reported here rather than
edited out of the registration.**

**A third defect, arithmetic.** §3.3 printed `u* = 7.3468°` beside a formula
whose exact evaluation is **7.345800°** — a transcription error of 0.0010° at
the fourth significant figure. The instrument computes `u*` from the formula
and from the **measured** σ_n, never from the printed number; the test suite
asserts the formula and records the discrepancy.

### V-E4 — the parity split

| half | epochs | epoch object-days | T8a ratio | T11 ratio | trigger ratio |
|---|---:|---:|---:|---:|---:|
| even NORAD | 1,202 | 236,585 | 2.053 | **0.000** | 0.3055 |
| odd NORAD | 1,403 | 280,806 | 1.670 | **2.199** | 0.2735 |

The T8a and trigger readings differ between the halves by 1.23× and 1.12×,
inside the registered factor of 3 and therefore **stable**. The T11 reading
differs by an unbounded factor — all six episodes have both members on the
odd side — so **the pooled T11 number is reported as UNSTABLE**, in that word,
as the registration requires.

---

## 4. The admitted exposure

| | ALL (primary) | TURN | QUIET |
|---|---:|---:|---:|
| epochs | **2,605** | 163 | 2,442 |
| objects | **297** | 100 | 293 |
| epoch-days | 517,398 | 84,846 | 432,551 |
| **epoch object-days** | **517,391** | 84,852 | 432,539 |
| **pair-epoch-days** | **23,960,622** | 1,221,962 | 15,517,273 |
| median epoch length (d) | 111.8 | 499.9 | 107.9 |
| epochs whose median \|u\| lies inside `u*` | 758 | 42 | 716 |

TURN and QUIET object-days sum exactly to ALL. Their **pair**-days do not,
because a pair-day formed by one TURN epoch and one QUIET epoch belongs to
neither stratum and to ALL.

**Catalogue class of the 297 objects carrying an admitted epoch** (metadata,
entering no decision): **266 active**, 30 passive, 1 unknown. The epoch unit's
whole gain comes from there: it admits **payloads during the intervals when
they were not holding a station**, which is why the exposure rose by four
orders of magnitude over a class of whole objects.

**What was refused.** 813,376 candidate runs were built; 718,377 were rejected
for fewer than 12 element sets, 90,972 for less than 56.00 days, 1,422 by the
cadence test, none for want of a testable block. 1,276 of 1,652 objects had at
least one candidate run and 297 carry an admitted epoch. **Zero v2 flag epochs
fall inside any admitted epoch**, printed because it is true by construction
and a construction should be visible rather than assumed.

---

## 5. The leak, per consumer, with the meaningful zero beside every number

**The matched reference**, computed by the same function over the same kind of
day: the payload class minus T8a's v1 `never_manoeuvred` set — **1,306
objects, 8,172,393 watched object-days, 3,324,051,937 watched pair-days** —
carrying **488** T8a events, **1,317** T11 episodes and **208,962** trigger
chains.

| consumer | reference rate | **exposure one expected event needs** |
|---|---:|---:|
| T8a events | 5.9713e-5 per object-day | **16,747 object-days** |
| T11 episodes | 3.9620e-7 per pair-day | **2,523,960 pair-days** |
| trigger chains | 2.5569e-2 per object-day | **39.1 object-days** |

T11b's stationed-day denominator for the same population is 3,717,395
object-days, printed for continuity.

### The nine registered readings

| stratum | consumer | events | exposure | exposure ÷ meaningful zero | leak ratio | 95% | verdict |
|---|---|---:|---:|---:|---:|---|---|
| **ALL** | T8a events | 57 | 517,391 | **30.9×** | **1.845** | [1.377, 2.431] | **LEAKS** |
| **ALL** | T11 episodes | 6 | 23,960,622 | **9.5×** | **0.632** | [0.232, 1.379] | **LEAKS** (unstable, §3) |
| **ALL** | trigger chains | 3,812 | 517,391 | **13,229×** | **0.288** | [0.279, 0.298] | **LEAKS** |
| TURN | T8a events | 15 | 84,852 | 5.1× | 2.960 | [1.644, 4.932] | LEAKS |
| TURN | T11 episodes | 0 | 1,221,962 | **0.48×** | 0 | [0, 7.63] | **UNEVALUABLE** |
| TURN | trigger chains | 555 | 84,852 | 2,170× | 0.256 | [0.235, 0.278] | LEAKS |
| QUIET | T8a events | 42 | 432,539 | 25.8× | 1.626 | [1.157, 2.231] | LEAKS |
| QUIET | T11 episodes | 6 | 15,517,273 | 6.1× | 0.976 | [0.357, 2.130] | LEAKS |
| QUIET | trigger chains | 3,257 | 432,539 | 11,059× | 0.295 | [0.284, 0.305] | LEAKS |

**The bar is 0.10 in every row.** The best ratio in the table is 0.256 — 2.6×
the bar — and its interval's lower end, 0.235, is still 2.35× the bar. The one
UNEVALUABLE row is a zero on 48% of the exposure a single expected episode
requires, and this document does not read it as anything.

### 5.1 The words the registration fixed for this outcome

> **the GEO catalogues remain uncontrolled**

Repeated verbatim from T11b §13.1, now with the exposure to mean it: 517,391
object-days and 23,960,622 pair-days, against a whole-object class that had
2,635 and 232.

### 5.2 Registered sensitivity arms — none changes the verdict

| arm | T8a | T11 | trigger |
|---|---:|---:|---:|
| **primary** (family-wise cadence, arrival anchor, containment) | 57 / ratio 1.845 | 6 / ratio 0.632 | 3,812 / ratio 0.288 |
| cadence threshold applied per block at 0.10 (2,118 epochs, 286 objects, 378,569 object-days) | 26 / ratio 1.150 | 2 / ratio 0.415 | 3,018 / ratio 0.312 |
| T8a anchored on the transfer start instead of the arrival | 54 | — | — |
| T8a requiring the whole transfer-to-departure span inside one epoch | 7 | — | — |
| T11 requiring only an overlap instead of containment | — | 26 | — |

Every arm leaks. The stricter T8a whole-span reading still returns 7 events on
517,391 object-days — 0.226 of the reference rate, 2.3× the bar.

---

## 6. The mechanism, measured — it is slowness, not only the turnaround

**Post-registration, labelled. It enters no gate, no bar and not the verdict.**

The registration stratified on the turnaround because T11b named the
turnaround as the leak. The stratification is directional but does not
separate: TURN leaks at 2.960 [1.644, 4.932] and QUIET at 1.626 [1.157,
2.231], and **the intervals overlap**. QUIET — epochs with no `λ'` sign change
at all — leaks by itself at 16× the bar.

Binned instead on the epoch's own implied half-amplitude, which is the
quantity that sets the speed:

| implied `u_max` | epochs | objects | object-days | T8a events | leak ratio | peak rate (°/day) | days to cross 0.1° at that rate |
|---|---:|---:|---:|---:|---:|---:|---:|
| [0°, 1°) | 48 | 10 | 8,120 | **0** | — (UNEVALUABLE, 0.48×) | 0.0077 | **12.98** |
| [1°, 5°) | 336 | 59 | 59,250 | 26 | **7.349** | 0.0385 | 2.60 |
| [5°, 20°) | 462 | 60 | 89,820 | 18 | 3.356 | 0.1510 | 0.66 |
| [20°, 90°) | 1,759 | 198 | 360,201 | 13 | **0.604** | 0.4415 | 0.23 |

**The leak falls monotonically as the libration gets faster, by a factor of 12
from the slow band to the fast one.** T8a's event definition requires a
**30-day** dwell inside 0.1° of longitude. A librator of half-amplitude 5°
crosses 0.1° in 2.6 days *at its fastest* and far more slowly everywhere else
in its swing; one of half-amplitude 1° takes 13 days at its fastest. Such an
object satisfies the dwell criterion over most of its trajectory, not only at
its turnaround — which is why the QUIET stratum leaks. A librator of
half-amplitude 20–60° crosses 0.1° in a quarter of a day at its fastest and
meets the criterion **only** near its extremes, which is why its ratio, 0.604,
is the lowest in the table and still 6× the bar.

**This is T11b §7.1's sentence, corrected and widened**: it is not that a
librator dwells *at its turnaround*; it is that a **slow** librator dwells
**everywhere**, and the turnaround is where every librator is slow.

**The 57 events come from 30 distinct approachers**, 55 of them
catalogue-class active. Metadata, printed beside the rows and entering no
decision:

| approacher | object approached | loiter (d) | implied `u_max` | stratum |
|---|---|---:|---:|---|
| 4250 SKYNET 1 | ANIK G1 | 110.1 | 2.98° | QUIET |
| 4250 SKYNET 1 | ANIK F1 | 104.3 | 2.98° | QUIET |
| 4250 SKYNET 1 | ANIK F1-R | 97.5 | 2.98° | QUIET |
| 4353 NATO 2A | ECHOSTAR 10 | 64.3 | 5.66° | QUIET |
| 22911 SOLIDARIDAD 1 | TELSTAR 12 (ORION 2) | 64.1 | 4.63° | QUIET |
| 35491 EWS-G3 | GSTAR 3 | 60.3 | 1.20° | QUIET |
| 22927 TELSTAR 401 | GALAXY 25 (TELSTAR 5) | 55.0 | 7.66° | QUIET |
| 20643 INSAT 1D | CHINASAT 1C | 44.0 | 7.61° | TURN |

**All six T11 episodes that fall inside admitted epochs on both members
involve one object.** GSTAR 3 (19483) appears in every one — five times with
GSTAR 1 (15677) and once with ATS 3 (3029) — and every implied half-amplitude
is between **0.87° and 1.25°**, every stratum QUIET, dwells 59.9 to 183.6 days.
Two slow, small-amplitude librators beside one another for months. That is the
episode detector finding exactly what the amplitude table predicts it must.

---

## 7. What this changes for the three consumers

**T8a.** The approach detector now has a GEO exposure class with 30.9× the
object-days a meaningful zero requires, and the class produces events at
**1.845×** the active-payload rate rather than below it. The detector cannot
be validated against free libration at GEO, and the number that says so has an
interval.

**T11.** The episode detector has 9.5× the pair-days a meaningful zero
requires — against T11b's 1/2,330th — and returns **6 episodes at 0.632 of the
active rate**, a reading flagged UNSTABLE by its own parity split. T11's §2.3
sentence still stands: its E1 counts remain geometry plus positive evidence,
and the positive-evidence route (T11b §8: 1,237 of 1,317 with a v2 flag on
both members inside the episode) remains the only one that works at GEO.

**The alarm lane.** For the first time the GEO arm has the number T8b's LEO
arm supplies: **zero-events-per-exposure-day with the exposure printed**. It is
not zero. The lane's own trigger — a chain of v1 drift-change flags — fires
**3,812 times inside 517,391 days of provably uncontrolled motion, 0.288 of
the rate it fires on objects that can manoeuvre**, against a bar of 0.10 and
against the LEO control's 0 over 18,792,698 object-days. The registration
predicted this in advance from T11b's measurement that 51 objects lose every
v1 flag to free motion, registered it anyway, and reports it. **The GEO arm
still has no passive control, and the size of what it does not have is now
0.288 [0.279, 0.298].**

---

## 8. Defects in this registration, reported rather than edited out

1. **V-E1's bar of 200/200 is unattainable against the registration's own
   family-wise level of 0.10 per run** (§3). Measured 191/200.
2. **§3.3's derivation of `u*` covered only the stable side.** The triaxial
   acceleration vanishes at the unstable longitudes too, so the blind band is
   16.32% of longitude rather than 8.16%, and the one keeper that survived
   V-E2 sits 0.241° from an unstable longitude (§3).
3. **§3.3 printed `u* = 7.3468°` where its own formula gives 7.345800°** (§3).
4. **The registered positive control never exercises the QUIET stratum** (§3),
   which carries 94% of the admitted epochs and 84% of the exposure.
5. **The registration stratified on the turnaround and the turnaround is not
   the discriminating variable** (§6). Amplitude is, and no bound on amplitude
   was registered.

Each needs a new registration; none may be repaired inside this one.

## 9. Blind spots, carried and new

1. **`A` is an upper bound**, so every test admits too much, never too little.
   Declared in the registration and unchanged by anything here.
2. **The energy test is blind to a symmetric velocity reversal**, derived in
   advance and asserted in the suite.
3. **Evaluability**: 718,377 candidate runs were refused for fewer than 12
   element sets. Sparsely sampled history remains unjudgeable.
4. **Recall is unmeasured**, inherited from T11 §9.2; every count is a lower
   bound.
5. **An epoch is not a statement about an object** outside that interval.
6. **The verdict is the best of nine pre-specified readings**, and it is a
   negative verdict, so the multiplicity runs against the claim rather than
   for it.

## 10. Owed

1. **A registered amplitude clause.** §6 measures the discriminating variable
   and no bar was registered against it. The [20°, 90°) band's 0.604 is the
   lowest leak in this study; a registration that admits only fast librators
   would trade almost all the exposure for a factor of three, and whether that
   trade can reach 0.10 is an open, answerable question.
2. **A cadence rule that splits a lined run instead of condemning it**, and a
   V-E1 bar stated with the test's own level beside it.
3. **A positive control that exercises the QUIET stratum** — short synthetic
   epochs away from a turnaround, not whole histories.
4. **The completed blind-band derivation** registered, with the unstable
   longitudes included.
5. T11b's still-open items that this study did not touch: the evaluability
   gap, and an R1 bar stated with its precision.

## 11. Reproduction

```
git show 86e80c3 --stat     # the registration, committed alone, one file
python3 -m unittest tests.test_geo_epoch_control     # 38 tests
python3 tools/geo_epoch_control.py                   # 60 s + 108 s, CPU
```

Receipt: `docs/geo-libration-epoch-control-20260922-receipt.json` — the
archive provenance, the input pins, the derivations, both validations with
their bars, all nine readings with their exposure and their meaningful zero,
the sensitivity arms, the parity split, the labelled diagnostics and the
source SHA-256 of the instrument. Epoch catalogue:
`docs/geo-libration-epochs-20260922.jsonl`, one row per admitted epoch.
Nothing from this study was written to `src/`, `data/`, `public/` or any site
surface.
