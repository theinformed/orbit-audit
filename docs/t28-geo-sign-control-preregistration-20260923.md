# Pre-registration: T28 — a GEO control built from the ramp-sign-versus-slot-side test

**Registered 2026-09-23, committed ALONE before any instrument for this track
exists and before any number below the derivations has been computed.**

This document fixes, in advance: the classifier's three clauses and every
threshold they use (each derived from a committed constant, none fitted); the
positive controls and their bars; the estimands, one per consumer, with the
exposure a meaningful zero requires printed beside each; the operating-point
curve and the rule that picks the operating point *before* any leak is read;
the gates; the decision rule; and the exact sentences that will be written for
each outcome.

---

## 0. Vocabulary, carried forward unchanged

| word | meaning here |
|---|---|
| **chain** | T8d's flag chain: consecutive v1 drift-change flags merged at 5.0 d. `(t_first, t_trig, stages, drift_change, drift_base)`. Imported from `tools/trigger_alarm.py`, never rebuilt |
| **epoch** | T8e's admitted free-libration interval: `tools/geo_epoch_control.find_epochs`. The substrate of this track, carried unchanged |
| **class** | the set of *asserted intervals* this track's classifier admits — the candidate GEO control |
| **leak** | a consumer's event rate inside the class, divided by the same consumer's rate on the matched active reference |
| **meaningful zero** | the exposure at which the reference rate would produce one expected event. Below it, a zero is a labelled gap, never a number |

No word in this document, in the instrument, or in any output of this track
names an intent, a motive, an operator or a mission. The subject is angles and
times.

---

## 1. Committed inputs, pinned before anything reads them

| input | pin |
|---|---|
| near-GEO extract | `runtime/proximity-geo/near-geo.npz`, T8a's cached pass: 217,007,154 rows scanned, 11,626,494 kept, 1,768 objects. GATE F aborts on any other |
| measured noise floor | `sigma_n = 6.038533519066339e-4` deg/day, T8a's calibration, read from the world build, never retyped as a literal in a decision |
| triaxial acceleration | `A = 1.7006955627927864e-3` deg/day², `pg.LAMBDA_DDOT_MAX` |
| stable longitudes | `(75.1, -104.7)` deg, `pg.STABLE_LONGITUDES_DEG` |
| T8a event catalogue | `docs/proximity-events-20260922.jsonl`, 493 rows, SHA-256 pinned at run time and printed |
| T11 episode catalogue | `docs/persistent-pairs-20260922.jsonl`, SHA-256 pinned against `geo_passive_control.CATALOGUE_SHA256`; a mismatch aborts (GATE G-S7) |
| alarm-lane replay ledger | `docs/trigger-alarm-triggers-20260922.jsonl`, the committed 2010s replay, for E5 |
| the sign test | T22 `docs/t22-scheduled-null-results-20260923.md` §7.3: carriers 0.8294 [0.8251, 0.8336] of 29,836 chains, passives 0.1515 [0.1434, 0.1600] of 7,160 |
| the amplitude evidence | T8e `docs/geo-libration-epoch-control-results-20260922.md` §6: leak by implied `u_max` — [1,5) 7.349, [5,20) 3.356, [20,90) 0.604 |
| the epoch substrate | T8e's `find_epochs`, imported. The test suite reads this track's source and fails if `find_epochs`, `v2_flags`, `flag_baselines`, `chain_flags`, `free_acceleration`, `nearest_stable` or `A` is redefined here |

**Every number in §1 was read before this registration was written. This is not
a blind analysis; only the combination, the thresholds' derivations and the
decision rule are fixed in advance.**

---

## 2. Why this track exists, in the committed numbers

T22 measured that **the sign of a flagged drift change relative to the local
triaxial acceleration separates a controlled object from a free one** —
0.8294 against 0.1515, two Wilson intervals 67 points apart — and registered
no operating point, no threshold and no detector. T22 §9.4 says so in those
words.

T8e measured that **every whole-object or epoch-based GEO control leaks**: the
best of nine pre-specified readings is 0.256 against a bar of 0.10, and the
leak falls monotonically with libration amplitude, by a factor of twelve from
[1°,5°) to [20°,90°). T8e §10 owes four items, of which this track discharges
two: **a registered amplitude clause**, and **the completed blind-band
derivation with the unstable longitudes included**.

The hypothesis under test is that those two measurements compose. Written so
it can fail:

> **H28.** A per-chain classifier that (a) requires each flagged drift change
> to run WITH the local triaxial acceleration — the free-motion sign, the
> complement of T22's keeper rule — (b) requires the motion's implied
> libration half-amplitude to exceed the value at which the consumer's own
> dwell criterion becomes kinematically unreachable, and (c) requires (a) to
> hold on `k` consecutive chains, admits a class of asserted intervals whose
> leak against the T8a event detector, the T11 episode detector and the
> trigger-time flag is below 0.10, with exposure above each consumer's
> meaningful zero.

---

## 3. The physics, and every threshold derived before measurement

### 3.1 Carried forward unchanged

```
lambda''            = acc(lambda) = -A sin 2u,     u = lambda - lambda_stable
2A_r                = 5.9365474e-5 rad/day^2
T_0 = 2 pi/sqrt(2A_r) = 815.4792 d
|lambda'|_max(u_max) = sqrt(2A) sin u_max,  sqrt(2A) = 0.4414582154284887 deg/day
s = sin^2 u + v^2/(2A_r)     (T8e §3.2, the local first integral)
u_max = arcsin sqrt(s)
```

`s` is conserved along the pendulum to one part in 10⁶ on an integrated
trajectory and is computable from **one** element set. The amplitude clause
below is a statement about `s`, therefore evaluable sample by sample.

### 3.2 Clause (a) — the sign test, written as a local causal rule

T22's rule (14): a burn that holds a slot pushes the drift rate **against**
the acceleration. Its complement is the rule this track admits on:

> **Free-motion sign.** For a chain at `t_trig` with drift change `Δd`, let
> `λ_b` be the **median longitude of the ten-sample baseline window that T8a's
> own flag rule used for that flag** — a quantity read entirely from element
> sets strictly before `t_trig`. The chain carries the **free sign** when
>
> ```
> sign(Δd) == sign(acc(λ_b)),    acc(λ) = -A sin 2(λ - λ_s)
> ```
>
> and the **keeper sign** when `sign(Δd) == -sign(acc(λ_b))`.

The baseline-window median is chosen over T22's ±45-day slot median because it
is causal by construction and because a control must not assume the object has
a slot. **T22's ±45 d slot-window centre is registered here as sensitivity arm
S1**, reported beside the primary in every table.

### 3.3 Clause (a)'s evaluability band — the completed derivation (T8e owed item 4)

`acc` vanishes at `u = 0` **and at `u = ±90°`**. T8e §3.3 solved for `u` near
zero only and its own results document records that as defect 2. Completed
here, before measurement:

> A keeping burn at the measured 14.00-day cycle is under the measured noise
> floor when `A |sin 2u| T/2 < 5 sigma_n`, i.e. `|sin 2u| < r` with
>
> ```
> r      = 5 sigma_n / (A T / 2) = 0.25361612755792523
> u*     = (1/2) arcsin r        = 7.345800 deg
> ```
>
> and because `|sin 2u|` is symmetric about 45°, the blind band is
>
> ```
> |u| < u*    OR    |u| > 90 - u*  = 82.654200 deg
> ```
>
> — **16.32% of longitude, not 8.16%.**

**Registered rule.** A chain whose `λ_b` lies in the completed blind band has
an **UNEVALUABLE sign**. An unevaluable chain **breaks the persistence run of
clause (c)** and is counted in a named column. It is never scored as a free
sign and never silently skipped. This is the conservative direction: a keeper
hiding in the blind band cannot accumulate `k` certified-free chains.

### 3.4 Clause (b) — the amplitude clause, derived from each consumer's own criterion

**T8a.** An event requires the approacher to remain within `X = 0.1°` of the
target for `D = 30` days. For a target held at a fixed longitude the approacher
must therefore stay inside a 0.1° window for 30 days. A free librator is
slowest at its turning point, where `λ'' = -A sin 2u_max` and, to second order,
`Δλ = ½ A |sin 2u_max| t²` about that point. Requiring `Δλ ≤ X` at `t = D/2`:

```
|sin 2u_max| <= 2 X / (A (D/2)^2) = 0.1 / (0.5 * A * 225) = 0.5226619674536022
u_dwell      = (1/2) arcsin(0.5226619674536022) = 15.755490 deg
```

> **A free librator of half-amplitude greater than `u_dwell = 15.755490°`
> cannot satisfy T8a's dwell criterion against a fixed longitude anywhere on
> its trajectory, including its turning point.**

**T11.** An episode requires two objects inside `X_pair = 2 A T²/16 =
0.041667041288423266°` for `D_pair = 56` days. The same second-order argument
against a fixed longitude gives

```
|sin 2u_max| <= 2 X_pair / (A (D_pair/2)^2) = 0.0625
u_T11        = (1/2) arcsin(0.0625) = 1.791661 deg
```

and T8e §6 reports that **all six** leaking T11 episodes carry implied
half-amplitudes between 0.87° and 1.25° — inside a bound derived here without
reference to them. That agreement is recorded as a check, not as a result.

**The binding threshold is the larger.** Clause (b) is registered as

```
CLAUSE (b):   implied u_max over the evidence window  >  u_dwell = 15.755490 deg
```

and it clears `u_T11` by a factor of 8.8.

**Declared now, not later: this derivation bounds dwell against a FIXED
longitude.** Two librators with matched amplitude and phase co-move, and their
separation obeys `Δ'' ≈ -2A cos(2u) Δ`, a harmonic equation of period `T_0`,
so a pair can remain boxed for 56 days at any amplitude. **Clause (b) is
therefore derived for T8a's fixed-slot targets and is NOT expected to protect
T11.** §7.2 registers the measurement that tests this: for every leaking T8a
event, whether the target is itself in the class or a fixed-slot object.

### 3.5 Clause (c) — persistence, and the factor it buys

T22 measures the per-chain keeper false rate as `p = 1 - 0.8294 = 0.1706`,
95% `[0.1664, 0.1749]` — a station-keeping object's flagged drift change
carries the free sign about one time in six, because the sign of a small drift
change is not always readable against the archive's scatter (T22 §3: one arc
in twenty measures the acceleration with the wrong sign).

> **The computable factor.** If consecutive chains on one object were
> independent, the probability that a keeper presents `k` consecutive
> free-sign chains is `p^k`:
>
> | k | 1 | 2 | 3 | 4 | 5 | 6 |
> |---|---:|---:|---:|---:|---:|---:|
> | `p^k` | 0.17060 | 0.029104 | 0.0049652 | 0.00084706 | 0.00014451 | 0.000024653 |

**Independence is not assumed; it is MEASURED before it is used.** The
instrument computes, over the 207 east-west carriers' 29,836 chains:

1. `P(chain i+1 free-sign | chain i free-sign)` against the marginal `p`;
2. the empirical distribution of run lengths of consecutive free-sign chains,
   against the geometric distribution `p^k(1-p)` the independence model
   predicts;
3. **the empirical per-carrier `k`-consecutive rate `q_k`** — the fraction of
   length-`k` consecutive chain windows on carriers in which every chain
   carries the free sign — for `k = 1…6`.

`q_k`, not `p^k`, is what the classifier is entitled to. `p^k` is printed
beside it so the reader sees the cost of dependence.

> **REGISTERED CHOICE RULE for `k`, fixed before any leak is read.** `k` is the
> **smallest** integer in `1…6` for which the MEASURED `q_k ≤ 0.01` — one
> station-keeping object in a hundred wrongly certified free over a `k`-chain
> window. If no `k ≤ 6` reaches 0.01, `k = 6` is used and the achieved `q_6` is
> printed in the verdict paragraph. The rule reads only `q_k`, which is a
> property of the carrier population and is **not** any consumer's leak.

---

## 4. The classifier, registered exactly

### 4.0 Clause (0) — the substrate, carried unchanged from T8e

An asserted interval must lie inside a T8e **admitted free-libration epoch**:
no v2 flag, the local free-libration bounds satisfied at every sample, no
energy step beyond free motion, no 14.00-day line in any block, no catalogue
gap beyond 5.0 d, ≥12 element sets, ≥56.00 days, family-wise cadence level
0.10. `find_epochs` is imported; the suite fails if it is reimplemented.
Carrying it unchanged is what makes this track's exposure table directly
comparable with T8e's.

### 4.1 The evidence window and the asserted interval — causal by construction

On one object, inside one epoch:

1. **Evidence window.** A run of `k` consecutive chains `c_1…c_k` whose
   `t_trig` all fall inside the epoch, **all** carrying the free sign of §3.2,
   with **no** intervening chain of keeper or unevaluable sign.
2. **Clause (b)** is evaluated over the evidence window only: the implied
   `u_max` from the maximum `s` over element sets in `[t_trig(c_1), t_trig(c_k)]`
   must exceed `u_dwell`.
3. **The asserted interval** runs from `t_trig(c_k)` — **exclusive** — to the
   end of the containing epoch.
4. A later chain inside the asserted interval that carries the **keeper sign**
   **terminates** the asserted interval at its own `t_first`. The class does
   not assert past evidence against it.

> **No consumer event is counted before `t_trig(c_k)`.** The class is declared
> from history and measured forward. This is registered because it is the only
> way the trigger-chain consumer can be read at all: a class whose admission
> rule reads the same chains the consumer counts would return a construction,
> not a measurement. A proof asserts the exclusion.

### 4.2 UNCLASSIFIABLE — registered so that an absence is never an admission

An epoch that yields **no** evidence window — because it contains fewer than
`k` chains, because a chain carries the keeper sign, because a sign is
unevaluable, or because clause (b) fails — is **UNCLASSIFIABLE** and is **NOT
admitted**. Its days enter no exposure. The count of unclassifiable epochs and
their days are printed, broken down by the clause that refused them.

**This is a deliberate departure from T8e**, where an epoch with no flags at
all was admitted. Here the class requires **positive evidence of free motion**.
The cost — the exposure T8e had and this track gives up — is reported as the
first row of the exposure table.

### 4.3 The three registered arms

| arm | clauses | status |
|---|---|---|
| **A — NOAMP** | (0), (a), (c) | secondary |
| **B — AMP** | (0), (a), (b), (c) | **PRIMARY** |
| **C — AMP+CADENCE** | (0), (a), (b), (c) + §4.4 | secondary |

### 4.4 Arm C's cadence clause, derived

v1's flag rule (the trigger consumer's own detector) compares a drift against
the **median of the previous ten drifts** and does **not** predict and subtract
free triaxial motion — that subtraction is exactly what distinguishes v2 from
v1. Free libration therefore trips v1 whenever

```
|A sin 2u| * dt  >  max(5 sigma_n, 0.010) = 0.010 deg/day
```

where `dt = t_i - median(t_{i-10..i-1})`. At the archive's median spacing of
0.865 d, `dt ≈ 5.5 × 0.865 = 4.757 d` and the requirement is
`|sin 2u| > 1.236` — **impossible**. At the maximum `dt` a 5.0-day-gap run
permits, `dt ≈ 5.5 × 5.0 = 27.5 d`, it is `|sin 2u| > 0.2137`, i.e.
`u > 6.17°` — **easy**. Arm C requires, at every sample of the asserted
interval,

```
dt_i  <  0.010 / (A * max|sin 2u| over the evidence window)
```

so that free motion at this object's own amplitude provably cannot trip v1.
The threshold is a ratio of two committed constants and a measured amplitude;
nothing is chosen.

> **REGISTERED PREDICTION T-PRED.** The trigger-chain leak will **rise** from
> T8e's 0.288 in arms A and B, because the class is selected for containing
> chains, and the chains it contains are the ones free motion produced. It will
> fall in arm C if and only if the leak is a **cadence artefact** — free motion
> flagged because the baseline reached back too far. The instrument measures
> `dt` at every leaking chain and prints its distribution against the derived
> 4.757 d and 27.5 d. If the median `dt` at leaking chains is near the archive
> median, T-PRED's mechanism is refuted and the trigger leak is not a cadence
> artefact.

---

## 5. Exposure and the matched reference

**Identical to T8e §5, so the two tables may be read side by side.** The
reference is the payload class minus T8a's v1 `never_manoeuvred` set, on
watched days — days inside a run of element sets with no gap beyond 5.0 d —
and the reference rates are recomputed in this run rather than copied.

| consumer | unit | meaningful zero = 1/rate |
|---|---|---|
| T8a events | object-days | recomputed; T8e measured 16,747 |
| T11 episodes | pair-days | recomputed; T8e measured 2,523,960 |
| trigger chains | object-days | recomputed; T8e measured 39.1 |

Exposure is reported as **objects, asserted-interval days, object-days and
pair-days**, and the ratio `exposure ÷ meaningful zero` is printed beside every
reading, as T8e's table format requires.

**Registered sensitivity arm S2 — a purely causal horizon.** The asserted
interval's END is the epoch's end, which is known only from the whole history.
Arm S2 replaces it with `t_trig(c_k) + 180.0` days — `pg.T_LOOK_DAYS`, T8a's
own look horizon — truncated by a catalogue gap of 5.0 d or by a keeper-sign
chain, whichever comes first. Arm S2 is fully causal at both ends and is
reported for all three consumers.

---

## 6. Validation BEFORE use

Bars are stated **with the level of the test that enforces them**, which is
T8e defect 1 applied to this registration.

### V1 — synthetic free librators must be ADMITTED
200 objects, `u_max` uniform in [1°, 60°], 20-year histories at the archive's
median spacing, perturbed by the measured `sigma_n`. Generator imported
unchanged from `geo_passive_control.synthetic_librators`, seed 20260922.

| reading | bar |
|---|---|
| **hard bar** — eligible librators (`u_max > u_dwell`) rejected by **clause (a)**, the sign clause | **0**. The sign clause must never call free motion controlled |
| eligible librators admitted | **≥ 0.80**, stated with the substrate's family-wise cadence level 0.10 and the chain-availability requirement beside it |
| every non-admission | **attributed to a named clause**; an unattributed rejection fails V1 outright |

### V2 — synthetic station-keepers must be EXCLUDED
200 self-consistent sawtooth keepers at the measured 14.00-day cycle (the ramp
is the triaxial acceleration at the object's own slot), seed 20260923,
`geo_passive_control.synthetic_keepers(self_consistent=True)`.

| reading | bar |
|---|---|
| keepers **outside the completed blind band** of §3.3 yielding zero asserted intervals | **200/200 of those outside**, i.e. fraction 1.000 |
| keepers inside the completed blind band | reported, **not barred** — §3.3 derives in advance that they are invisible |
| labelled arm: maximum-ramp keepers (`self_consistent=False`) | reported |

### V3 — the T8e leak case, with a SPLIT bar registered in advance
A synthetic free librator at `u_max` in [2°, 5°] — the amplitude band that
carried T8e's worst leak (7.349) and every leaking T11 episode.

| reading | bar |
|---|---|
| classified as **free** by clauses (a) and (c) | **must pass.** The T8e leak case must never be called controlled |
| clause (b) | it is **EXCLUDED-BY-AMPLITUDE**, and the instrument must emit that label, never `CONTROLLED` and never a silent drop |
| arm A (NOAMP) | **must admit it.** Arm A is where the slow librator is in the class, and arm A's readings are what the amplitude clause costs |

**This is the honest resolution of a real conflict** between the track brief's
positive control (the T8e leak case must be admitted) and the derived amplitude
clause (which excludes it). A control may refuse motion it cannot certify as
non-leaking; it may not misclassify it. Both statements are enforced.

### V4 — the sparse librator: classifiable or UNCLASSIFIABLE, never silently admitted
A free librator at `u_max = 30°` sampled every 10.0 days — beyond the 5.0-day
catalogue gap — must return `UNCLASSIFIABLE` with the reason `catalogue-gap`,
must not appear in any admitted set, and its days must not appear in any
exposure. A second fixture at 4.0-day spacing must be classifiable.

### V5 — the parity split
Even-NORAD and odd-NORAD halves, all three consumers. A reading whose two
halves differ by more than a factor of 3 is printed **UNSTABLE**, in that word.

### V6 — the two bugs the suite asserts (registered as tests)
1. **A keeper whose ramp opposes its slot side must be EXCLUDED.** A planted
   sawtooth at a slot outside the blind band, whose every drift change carries
   the keeper sign, yields zero asserted intervals — asserted directly, not via
   a summary statistic.
2. **A librator sampled sparsely must still be classifiable or marked
   unclassifiable — never silently admitted** (V4, asserted as a test).
3. Causality: no consumer event at or before `t_trig(c_k)` is counted.
4. The blind band is two-sided: a chain at `|u| = 85°` is UNEVALUABLE.
5. `u_dwell`'s closed form, and that a librator at exactly `u_dwell` traverses
   exactly 0.1° in exactly 15.0 days from its turning point in the second-order
   model.
6. `s` conservation, imported from T8e's suite and re-asserted here.

---

## 7. The estimands, one per consumer

Bar **0.10** in every row, as in T8e. Each reading prints: events, exposure,
`exposure ÷ meaningful zero`, leak ratio, its exact conditional 95% interval,
and the verdict `LEAKS` / `LEAK-FREE` / `UNEVALUABLE`.

### 7.1 E1 — T8a events
Counted by arrival epoch inside an asserted interval, `count_t8a` imported.
Secondary anchors: transfer start; whole transfer-to-departure span contained.

### 7.2 E2 — T11 episodes
Counted when both members are inside asserted intervals for the whole episode
(containment), `count_t11` imported. Secondary: overlap.

**Registered measurement for §3.4's declared blind spot.** For every leaking
T8a event and every leaking T11 episode, the instrument prints whether the
**target/partner** object is itself in the class on that day. A leak whose
partner is in the class is a co-moving-librator leak, which §3.4 predicts and
clause (b) cannot reach. A leak whose partner is a fixed-slot object refutes
the derivation of §3.4 and must be reported in those words.

### 7.3 E3 — trigger-time flags
Every v1 chain whose `t_trig` falls inside an asserted interval, `count_triggers`
imported, built **without** the active-class restriction — which is how a
control is proved.

### 7.4 E4 — the operating-point curve, registered as an estimand
For `k = 1…6` × arms {A, B}, the instrument prints a curve of

* the **measured carrier false rate** `q_k` (x-axis, the cost of admission),
* against the **admitted exposure** in object-days and pair-days (y-axis),
* with each consumer's leak ratio annotated at every point.

The curve is printed **whole**, and the point the §3.5 rule selects is marked
on it. A reader must be able to see what every other choice would have given.

### 7.5 E5 — the alarm lane's GEO arm, registered here so it is NOT post-registration
On the committed 2010s replay ledger, the class-1 precision **before** and
**after** removing from the denominator every spoken class-1 alert whose
`(norad, t_trig)` chain falls inside an admitted asserted interval — those
chains are certified free motion, hence certified false alarms. Reported with
Wilson intervals, the number of alerts removed, the number of hits removed, and
the join chain printed count by count rather than asserted. **Registering E5
here is what allows the alarm-lane implication to be reported as a re-freeze
candidate rather than as a post-registration reading.**

---

## 8. Gates

| gate | fires when |
|---|---|
| **G-S1** | the classifier admits nothing in the primary arm |
| **G-S2** | no reading in any arm has exposure above its meaningful zero |
| **G-S3** | every evaluable reading leaks |
| **G-S4** | V1's hard bar is missed — the sign clause rejects free motion |
| **G-S5** | V2's bar is missed outside the completed blind band |
| **G-S6** | V3's split bar is missed — the slow librator is called CONTROLLED, or excluded without the `EXCLUDED-BY-AMPLITUDE` label |
| **G-S7** | either catalogue pin fails |
| **G-S8** | the chosen `k` is 6 and `q_6 > 0.01` — persistence did not buy what §3.5 derived |

**Contingency, registered.** If G-S4, G-S5 or G-S6 fires, the class is **NOT
USED** and the readings it would have supplied are printed anyway, labelled
`WOULD HAVE READ`, as T8e did. If G-S8 fires the verdict paragraph must carry
the achieved `q_6` in its first sentence.

---

## 9. The decision rule, and what falsifies the claim

**The verdict sentence is one of exactly two:**

> **a leak-free GEO control EXISTS**
>
> **a leak-free GEO control DOES NOT EXIST**

**EXISTS** is awarded only if, in **one named arm**, **all three** consumers
read `LEAK-FREE` — leak ratio ≤ 0.10 — **with exposure at or above that
consumer's meaningful zero**. The arm must be named in the verdict sentence.

**Multiplicity, declared and penalised.** Three arms × two horizon variants =
six chances at a positive claim. Because the claim is positive, the verdict
paragraph must also print the **STRICT criterion**: the 95% interval's **upper**
end below 0.10 in the arm that carries the verdict. The headline verdict uses
the primary criterion, for comparability with T8e; the strict criterion's
outcome is printed beside it in the same paragraph, whichever way it goes.

**DOES NOT EXIST — and the registration fixes which reason is written:**

* **by LEAK** — at least one reading in every arm is evaluable, and no arm has
  all three consumers leak-free. Sentence: *"all three consumers ≥ 0.10 with
  exposure above the meaningful zero"*, naming the consumers that leak.
* **by EXPOSURE** — the deciding readings have exposure **below** the
  meaningful zero. Sentence: *"exposure below the meaningful zero"*, naming the
  consumers and printing the shortfall as a ratio. A zero is then a **labelled
  gap, not a number**, and this document forbids reading it as anything.
* **by BOTH** — both sentences are written, per consumer.

**Registered in advance:** §3.4 derives that clause (b) is not expected to
protect T11, and §5 notes that a class demanding positive evidence of free
motion must lose most of T8e's 23,960,622 pair-days. **The most likely single
outcome is therefore `DOES NOT EXIST — by EXPOSURE for T11 and by LEAK for the
trigger consumer`.** Registering the expected outcome is not a prediction of
failure; it is what stops an expected failure being reported as a discovery.

**What would make H28 true and is therefore what this track is looking for:**
arm B or arm C admitting ≥ 16,747 object-days with zero or few T8a events,
because clause (b) makes the dwell kinematically unreachable and clause (a)+(c)
removes the controlled motion T8e admitted. That is a real possibility and
nothing above is written to make it unreachable.

---

## 10. Declared blind spots

1. **`A` is an upper bound**, so every test admits too much, never too little.
   Carried from T8a unchanged.
2. **Clause (b)'s derivation bounds dwell against a FIXED longitude.**
   Co-moving librators evade it (§3.4). §7.2 measures how much of the leak is
   of that kind; it does not remove it.
3. **The completed blind band is 16.32% of longitude.** A keeper inside it
   cannot be excluded by clause (a) at all; §3.3's rule makes it
   unclassifiable rather than admitted, which costs exposure and buys safety.
4. **Recall is unmeasured**, inherited from T11 §9.2 and T22 §9.4. Every count
   is a lower bound.
5. **An asserted interval is not a statement about an object** outside it.
6. **The second-order dwell model** neglects `O(t⁴)`. Over 30 days against a
   libration period of 815 days the neglected term is below 0.1% of `Δλ`; the
   suite asserts this against an integrated trajectory.
7. **The sign test's own ceiling.** Carriers obey the keeper rule only 0.8294
   of the time; T22 §3 attributes the gap to measurement scatter, not physics.
   Clause (a) inherits that ceiling and cannot beat it.
8. **This is not a blind analysis** (§1).

---

## 11. Compute, provenance, determinism

CPU on `pc`, one core, no GPU — therefore **no `gpu-consumers.json` row is
owed**, and the receipt states so. Seeds 20260922 (librators) and 20260923
(keepers), fixed. Nothing is written to `src/`, `data/`, `public/` or any site
surface; nothing is scheduled, no timer, no cron entry, no state file, no
alert. Disk free is reported before and after. The receipt carries the archive
provenance, both catalogue SHA-256 pins, every derived threshold with its
closed form, both validations with their bars, every reading with its exposure
and meaningful zero, the operating-point curve whole, the parity split, and the
instrument's own SHA-256.

**Determinism is measured, not assumed:** the instrument is run twice end to
end and every statistical block of the two receipts must be identical.

---

## 12. What is committed with this document

**This file and nothing else.** `tools/geo_sign_control.py`,
`tests/test_geo_sign_control.py`, the results document, the receipt, the
runbook row and the notebook entry are all written afterwards and committed
afterwards, so that `git log` shows the registration preceding the first
number.
