# T28 results: **a leak-free GEO control DOES NOT EXIST** — and the reason is that the errors are not independent

**Registration:** `docs/t28-geo-sign-control-preregistration-20260923.md`,
committed **ALONE** at `b56c8b6`, 580 lines, one file, before the instrument
existed and before any number below.
**Instrument:** `tools/geo_sign_control.py` with `tests/test_geo_sign_control.py`,
**29 offline proofs**, no archive and no network, committed at `e2ed923` — also
before any number reached the repository.
**Artefacts:** `docs/t28-geo-sign-control-20260923-receipt.json`,
`docs/t28-geo-sign-control-20260923.jsonl`.
**Compute:** CPU on `pc`, one core, **202 s wall**. No GPU was taken, so **no
`gpu-consumers.json` row is owed**. Nothing is scheduled, nothing is deployed,
nothing reaches `src/`, `data/`, `public/` or any site surface.

---

## 0. The verdict, stated first

> **REGISTERED VERDICT: `a leak-free GEO control DOES NOT EXIST`.**
>
> **By LEAK for the trigger consumer, and by EXPOSURE for T11 — the two
> sentences the registration fixed in advance, per consumer:**
>
> * **T8a events — LEAK-FREE.** 0 events on **25,714 object-days**, which is
>   **1.535×** the exposure one expected event needs. Leak ratio **0.0000**,
>   exact 95% **[0.0000, 2.4116]**. This is the first leak-free T8a reading in
>   the programme, and its interval says plainly that one event would have
>   ended it.
> * **T11 episodes — `exposure below the meaningful zero`.** 153,061 pair-days
>   against the 2,523,957 one expected episode needs: **0.061×**. The zero is a
>   **labelled gap, not a number**, and this document reads it as nothing.
> * **Trigger-time flags — `all arms ≥ 0.10 with exposure above the meaningful
>   zero`.** **318 chains on 25,714 object-days, leak 0.4837 [0.4319,
>   0.5399]**, against a bar of 0.10 and against T8e's 0.288. The class is
>   **worse** than the one it was built to improve, and **the registration
>   predicted that in advance** (T-PRED, §4.4).
>
> **No arm of the four has all three consumers leak-free**, so no arm carries a
> positive claim and the strict criterion is not reached for.

**And the mechanism is measured, not supposed.**

> **Persistence does not buy what independence would buy.** The registration
> derived that `k` consecutive free-sign chains on a station-keeping object
> should occur at `p^k`, from `p = 0.1706`. Measured on the same 207 east-west
> carriers T22 used: **`q_1 = 0.2660` and `q_6 = 0.0999`.** Six chains of
> agreement buy a factor of **2.66**, where independence promised **6,900**.
> The conditional probability is the reason: **`P(free | previous free) =
> 0.5994` against a marginal of `0.2660`** — and a carrier's run of free-sign
> chains reaches **400 chains long**. A sign that is misread is misread again,
> because the misreading is a property of where the object sits and how it is
> sampled, not a coin.

**One derived prediction held exactly, and it is the usable result of this
track.**

> **The amplitude clause was derived, before measurement, from T8a's own dwell
> criterion: a free librator of half-amplitude above `u_dwell = 15.755490°`
> cannot stay inside 0.1° of a fixed longitude for 30 days. The class contains
> zero T8a events on 25,714 object-days.** Against T8e's 57 events on 517,391
> days of the same substrate, at the same bar, with the same reference.

**And one registered prediction held in the direction that kills the track.**

> **T-PRED.** §4.4 predicted the trigger-chain leak would RISE, because a class
> that demands positive evidence of free motion is selected for containing
> exactly the chains the consumer counts. It rose from **0.288 to 0.4837**, and
> it is **flat in `k`** — 0.4837 to 0.5426 across every point of the
> operating-point curve. **Persistence does not touch it at all.**

---

## 1. What ran

| | |
|---|---|
| host | `pc`, CPU, one core |
| wall | **201.6 s** (chain signs 37.8 s, epochs 9.1 s) |
| archive | `/home/sdegan/space-orbit-history/orbit-history.sqlite3`, 13.9 GB, rollup 1959-01 to 2026-09 |
| extract | `runtime/proximity-geo/near-geo.npz`, T8a's cached pass: 217,007,154 rows scanned, 11,626,494 kept, 1,768 objects, GATE F asserted at load |
| population | the same 1,652 near-GEO objects, the same measured `sigma_n = 6.038534e-4` deg/day |
| catalogue pins | T11 `5df77537…` (asserted against the committed pin, GATE G-S7 clean), T8a `b2e6b364…` |
| substrate | **2,605 admitted free-libration epochs — T8e's number, reproduced exactly** by the imported `find_epochs` |
| seeds | 20260922 librators, 20260923 keepers |
| disk | **123 GB free before, 123 GB free after** (88% both times). Nothing large was written: the receipt is 29 KB, the interval ledger 48 KB, and both run directories are outside the repository |

**Determinism, measured rather than assumed.** The instrument was run **twice
end to end** and the two receipts were compared by a recursive field-for-field
walk that excludes only the timestamp and the three wall clocks. **It reports
0 differences** — the persistence profile, all four arms, every reading, the
operating-point curve, all four validations, E5, the gates and the verdict are
identical.

---

## 2. The derivations, each a closed form, each fixed before measurement

| quantity | closed form | value |
|---|---|---:|
| blind-band ratio | `5 sigma_n / (A T/2)` | 0.25361613 |
| **`u*`, the completed two-sided blind band** | `(1/2) arcsin r`, blind for `\|u\| < u*` **and** `\|u\| > 90 − u*` | **7.345800°** |
| fraction of longitude blind | `8 u* / 360` | **16.324%** |
| **`u_dwell`** | `(1/2) arcsin[2 X /(A (D/2)²)]`, `X = 0.1°`, `D = 30 d` | **15.755490°** |
| `u_T11` | same form, `X = 0.0416647°`, `D = 56 d` | **1.791661°** |
| arm C cadence limit at `u_dwell` | `0.010 / (A \|sin 2u\|)` | 11.25 d |
| substrate cadence ceiling | `14.00 / 5.5` | 2.545 d |

**T8e owed item 4 is discharged.** T8e §3.3 solved the blind-band inequality
for `u` near zero only and its own results document records that as defect 2.
The acceleration vanishes at the unstable longitudes too; the completed band is
**16.32% of longitude, not 8.16%**, and it is registered, implemented and
asserted by a proof that a chain at `|u| = 85°` is UNEVALUABLE rather than
free.

**T8e owed item 1 is discharged.** A registered amplitude clause now exists,
derived rather than binned, and §0 reports what it bought.

**A provenance discrepancy, found by a proof and reported rather than edited
out.** T11's pair box was built from `A = 1.7006e-3`; T8a's acceleration is
`A = 1.7006955627927864e-3`. They differ in the fifth significant figure. The
`u_T11` bound is derived with the constant that built the box, giving
**1.791661°**; with T8a's constant it is **1.791560°**. The difference is
0.0001° and `u_T11` enters no decision, but the two committed values of the
same physical constant are not the same number and a proof now asserts it.
Same class as T8e's defect 3.

**And the T11 bound brackets the measurement it was derived without.** T8e §6
reports that all six leaking T11 episodes carry implied half-amplitudes between
**0.87° and 1.25°**. The bound derived here from the box and the period alone
is **1.791661°**. A proof asserts `1.25 < u_T11`.

---

## 3. The sign test, made causal — and what causality costs

The registration replaced T22's ±45-day slot-window centre with the **median
longitude of the ten-sample baseline window T8a's own flag rule already used**,
because a control must be causal and must not assume the object has a slot.
Measured over all 1,652 objects, 275,490 chains:

| | free sign | keeper sign | unevaluable |
|---|---:|---:|---:|
| all near-GEO chains | 178,784 | 78,401 | 18,305 |

| population | chains | free-sign fraction |
|---|---:|---:|
| **207 east-west carriers** (T22's roster) | 40,578 | **0.2660** |
| **239 same-shell passives** (T22's roster) | 47,571 | **0.9096** |

**The separation survives: 64 percentage points, against T22's 67.** But the
carrier false rate is **0.2660, not the 0.1706 the registration derived from
T22's 0.8294**, and the difference is the price of causality: a ten-sample
window spanning about nine days reads the sign of a small drift change less
reliably than a forty-five-day slot median does. **The registration's `p` was
therefore optimistic by 56%, and the instrument used the MEASURED `q_k`, never
`p^k`, exactly as §3.5 required.**

---

## 4. Persistence, measured before it was used — the finding that decides the track

| `k` | measured `q_k` on carriers | windows | independence model `p^k` | ratio, model to measurement |
|---:|---:|---:|---:|---:|
| 1 | **0.26603** | 40,578 | 0.17060 | 0.64 |
| 2 | 0.15915 | 40,371 | 0.029104 | 5.5 |
| 3 | 0.12778 | 40,164 | 0.0049652 | 26 |
| 4 | 0.11382 | 39,957 | 0.00084706 | 134 |
| 5 | 0.10558 | 39,750 | 0.00014451 | 731 |
| **6** | **0.09987** | 39,543 | 0.000024653 | **4,051** |

> **The registered choice rule asked for the smallest `k ≤ 6` with `q_k ≤
> 0.01`. No `k` reaches it. `k = 6` was used and `q_6 = 0.0999` is printed in
> this document's first sentences, as the registration required. GATE G-S8
> FIRED.**

**Why, measured.** `P(free | previous free) = 0.5994` on carriers against a
marginal of `0.2660`: a carrier chain that reads free is **2.25× more likely**
to be followed by another that reads free. The run-length histogram is the same
statement in another form — carriers carry free-sign runs of **288 and 400
consecutive chains**. The passive arm behaves the same way in the other
direction: marginal 0.9096, conditional 0.9332.

**This is the general lesson of the track and it is not about GEO.** A
persistence requirement is a bet that the classifier's errors are independent.
Here they are not, because a misread sign is a property of where the object
sits relative to the equilibria and how densely it is sampled — both of which
persist for months. **Six agreeing observations bought a factor of 2.66 where
the arithmetic promised 6,900.**

---

## 5. Validation BEFORE use

| | measured | bar | |
|---|---|---|---|
| **V1 hard bar** — eligible synthetic librators rejected by the SIGN clause | **0** | 0 | **PASSED** |
| V1 — pooled free-sign fraction on synthetic librators | **1.000** | reported | — |
| V1 admission — eligible librators admitted | **0 / 155 = 0.000** | ≥ 0.80 | **MISSED** |
| **V2** — keepers outside the blind band excluded | **164 / 164 = 1.000** | 1.000 | **PASSED** |
| V2 signed-ramp addendum | 0 admitted | — | PASSED |
| V2 maximum-ramp arm | 0 admitted | — | PASSED |
| **V3** — the T8e leak case | **not called controlled, but not admitted either** | split bar | **MISSED** |
| **V4** — sparse librator | UNCLASSIFIABLE, reason `catalogue-gap`, 0 exposure | — | **PASSED** |

**The sign clause does exactly what it was derived to do.** Every evaluable
chain on every one of the 200 synthetic free librators reads FREE — the pooled
fraction is **1.000** — and not one eligible librator was refused by clause
(a). That is the hard bar, and it passed.

**And V1's admission bar failed for a reason the registration derived before
the run.** All 155 eligible librators were refused, **148 for `too-few-chains`
and 7 for `no-epoch`; zero unattributed.** §4.4 derived why: v1's flag rule
compares a drift against the median of the previous ten, and at the archive's
median spacing that baseline reaches back `5.5 × 0.865 = 4.757` days, so free
motion trips it only if `|sin 2u| > 1.236` — **which is impossible**. **A clean
free librator, sampled the way this archive samples, produces no flag chains at
all**, and a classifier that demands `k` of them has nothing to work with.

**V3 is the same sentence about the object T8e's leak was made of.** The
synthetic slow librator at `u_max = 3.5°` produced **zero chains**. It was not
called CONTROLLED — the registration's first clause held — but arm A did not
admit it, so the registered split bar is MISSED and **GATE G-S6 FIRED**.

> **Registered contingency, honoured.** G-S6 and G-S8 fired, so by §8 the class
> is **NOT USED**, and the readings it would have supplied are printed below
> labelled **WOULD HAVE READ**. The verdict does not depend on that: the
> trigger consumer leaks at every point of the operating-point curve and T11 is
> unevaluable everywhere, so the answer is the same whether the class is used
> or withheld. Both statements are printed because the registration requires
> the contingency to be honoured and because a reader is entitled to the
> numbers.

---

## 6. The admitted class and its readings — WOULD HAVE READ

**The matched reference, recomputed in this run and identical to T8e's:** the
payload class minus T8a's v1 `never_manoeuvred` set — **1,306 objects,
8,172,393 watched object-days, 3,324,051,937 watched pair-days** — carrying
**488** T8a events, **1,317** T11 episodes and **208,962** trigger chains.

| consumer | reference rate | **exposure one expected event needs** |
|---|---:|---:|
| T8a events | 5.9713e-5 per object-day | **16,746.7 object-days** |
| T11 episodes | 3.9620e-7 per pair-day | **2,523,957 pair-days** |
| trigger chains | 2.5569e-2 per object-day | **39.1 object-days** |

### 6.1 Exposure

| | A — NOAMP | **B — AMP (primary)** | C — AMP+CADENCE | S2 — causal horizon |
|---|---:|---:|---:|---:|
| asserted intervals | 127 | **127** | 142 | 136 |
| objects | 71 | **71** | 71 | 71 |
| asserted days | 25,712 | **25,712** | 12,319 | 14,389 |
| **object-days** | 25,714 | **25,714** | 12,317 | 14,387 |
| **pair-days** | 153,061 | **153,061** | 34,960 | 39,869 |
| median interval (d) | 108.2 | **108.2** | 21.6 | 115.4 |

**Arm B equals arm A exactly.** The amplitude clause removed **nothing**: every
evidence window that survived the sign and persistence clauses already implied
`u_max > 15.755490°`. That is not a null result — it is §4.4's derivation
arriving from the other side. The only free motion that trips v1 at this
archive's cadence is **fast** free motion, so the class the sign clause can
build is already above the amplitude threshold before the threshold is applied.

**What was refused**, counted rather than dropped, over 2,605 substrate epochs
on 1,652 objects: **2,466 epochs carried fewer than `k = 6` chains**, 1,335
objects produced no epoch at all, 20 were refused for a catalogue gap, and the
remaining **139 epochs yielded 127 admitted evidence windows**.

> **And here is the limitation that qualifies everything above.** Of the chains
> inside those 139 epochs, **not one carried the keeper sign and not one was
> unevaluable** — the clause (a) and clause (b) refusal counters are both
> **zero**. **On the real archive, neither the sign clause nor the amplitude
> clause removed anything.** All of the classifier's work was done by the
> persistence requirement, and it was done in one blunt form: 2,466 of 2,605
> epochs refused for carrying fewer than six chains.
>
> The reason is T8e's substrate. An epoch is admitted only where the v2 rule —
> which predicts and subtracts free triaxial motion — raises no flag, where the
> local free-libration bounds hold at every sample, where no energy step exceeds
> free motion and where no 14.00-day line appears in any block. **That rule has
> already excluded keeper-like motion before the sign clause is asked**, so the
> sign clause has nothing left to exclude.
>
> **The sign test is therefore validated on synthetics here and UNEXERCISED on
> the archive.** Its 0.2660-against-0.9096 separation is real and is measured on
> 88,149 carrier and passive chains in §3; what this track did not get is a
> single case in which it changed a class decision on a real object. A successor
> that wants to price the sign test must run it on a substrate that does not
> already do its job — which is a different registration.

**Catalogue class of the 71 objects carrying an asserted interval** (metadata,
entering no decision): **58 active, 13 passive, 0 unknown** — the same shape
T8e found, payloads during intervals when they were not holding a station.

### 6.2 The readings, with the meaningful zero beside every number

| arm | consumer | events | exposure | exposure ÷ meaningful zero | leak ratio | 95% | verdict |
|---|---|---:|---:|---:|---:|---|---|
| **B — AMP** | **T8a events** | **0** | **25,714** | **1.535×** | **0.0000** | [0.0000, 2.4116] | **LEAK-FREE** |
| **B — AMP** | **T11 episodes** | 0 | 153,061 | **0.061×** | — | — | **UNEVALUABLE** |
| **B — AMP** | **trigger chains** | **318** | **25,714** | **657×** | **0.4837** | [0.4319, 0.5399] | **LEAKS** |
| A — NOAMP | T8a events | 0 | 25,714 | 1.535× | 0.0000 | [0.0000, 2.4116] | LEAK-FREE |
| A — NOAMP | T11 episodes | 0 | 153,061 | 0.061× | — | — | UNEVALUABLE |
| A — NOAMP | trigger chains | 318 | 25,714 | 657× | 0.4837 | [0.4319, 0.5399] | LEAKS |
| C — AMP+CADENCE | T8a events | 0 | 12,317 | 0.735× | — | — | UNEVALUABLE |
| C — AMP+CADENCE | T11 episodes | 0 | 34,960 | 0.014× | — | — | UNEVALUABLE |
| C — AMP+CADENCE | trigger chains | 117 | 12,317 | 315× | **0.3715** | [0.3072, 0.4453] | LEAKS |
| S2 — causal horizon | T8a events | 0 | 14,387 | 0.859× | — | — | UNEVALUABLE |
| S2 — causal horizon | T11 episodes | 0 | 39,869 | 0.016× | — | — | UNEVALUABLE |
| S2 — causal horizon | trigger chains | 209 | 14,387 | 368× | 0.5681 | [0.4937, 0.6507] | LEAKS |

Secondary anchors, every arm: T8a on the transfer start **0**, T8a on the whole
transfer-to-departure span **0**, T11 on overlap instead of containment **0**.

**Read the T8a row honestly.** A zero on 1.535× the exposure one expected event
needs is evaluable by the registered rule and by T8e's, and it is the first
such zero the GEO arm has produced. It is also thin: the exact conditional
interval runs to **2.4116**, one event would have put the ratio at 0.65, and
the same zero in arm C and arm S2 is UNEVALUABLE because those arms have less
exposure. **The claim this reading supports is "no T8a event was found in
25,714 days of certified fast free libration", not "the T8a detector is
controlled at GEO".**

### 6.3 The two registered measurements that had nothing to measure

§7.2 registered that every leaking T8a event and every leaking T11 episode
would be reported with whether its partner was itself in the class, to separate
a co-moving-librator leak from a refutation of §3.4's fixed-longitude
derivation. **There are no leaking T8a events and no leaking T11 episodes, so
the measurement is a labelled gap.** The blind spot §3.4 declared — that two
librators with matched amplitude and phase co-move, and their separation obeys
a harmonic equation of period 815 days, so a pair can stay boxed at any
amplitude — **is therefore untested by this run and remains open.**

---

## 7. The operating-point curve — the choice made visible rather than tuned

Every point, printed whole. `q_k` is the measured carrier false rate; `p^k` is
the independence model, printed only so the gap is visible.

| `k` | arm | `q_k` | `p^k` | objects | object-days | pair-days | T8a leak | T11 leak | trigger leak |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | A-NOAMP | 0.26603 | 1.71e-01 | 168 | 203,376 | **4,103,796** | 0.6587 | 0.0000 | 0.4906 |
| 1 | B-AMP | 0.26603 | 1.71e-01 | 163 | 201,852 | **4,040,817** | 0.5808 | 0.0000 | 0.4927 |
| 2 | A-NOAMP | 0.15915 | 2.91e-02 | 151 | 120,469 | 1,623,608 | 0.4170 | 0.0000 | 0.5376 |
| 2 | B-AMP | 0.15915 | 2.91e-02 | 149 | 119,954 | 1,609,896 | 0.4188 | 0.0000 | 0.5389 |
| 3 | A-NOAMP | 0.12778 | 4.97e-03 | 131 | 75,407 | 730,216 | 0.2221 | 0.0000 | 0.5425 |
| 3 | B-AMP | 0.12778 | 4.97e-03 | 131 | 75,401 | 730,210 | 0.2221 | 0.0000 | 0.5420 |
| 4 | A-NOAMP | 0.11382 | 8.47e-04 | 110 | 50,169 | 378,719 | 0.3338 | 0.0000 | 0.5301 |
| 4 | B-AMP | 0.11382 | 8.47e-04 | 110 | 50,169 | 378,719 | 0.3338 | 0.0000 | 0.5301 |
| 5 | A-NOAMP | 0.10558 | 1.45e-04 | 87 | 35,102 | 239,919 | **0.0000** | 0.0000 | 0.5092 |
| 5 | B-AMP | 0.10558 | 1.45e-04 | 87 | 35,102 | 239,919 | **0.0000** | 0.0000 | 0.5092 |
| **6** | A-NOAMP | 0.09987 | 2.47e-05 | 71 | 25,714 | 153,061 | **0.0000** | 0.0000 | 0.4837 |
| **6** | **B-AMP** | **0.09987** | 2.47e-05 | **71** | **25,714** | **153,061** | **0.0000** | 0.0000 | **0.4837** | **← CHOSEN** |

**The chosen point was chosen by the rule, not by the outcome.** §3.5 fixed the
rule before any leak was read: the smallest `k` with `q_k ≤ 0.01`. None
qualified, so `k = 6` by the registered fallback. **The rule reads `q_k`, which
is a property of the carrier population and not any consumer's leak**, and the
table above lets a reader price every other choice.

**Three things the curve says that no single point could.**

1. **T8a's leak falls with `k` and reaches zero at `k = 5`**, where the
   exposure is 35,102 object-days — **2.10× the meaningful zero, better than
   the chosen point's 1.535×.** The registered rule did not pick it, and this
   document does not retrofit the choice; it prints it.
2. **T11 reads 0.0000 at every point, and is evaluable only at `k = 1`**, where
   4,103,796 pair-days is **1.63×** the meaningful zero — but `k = 1` is the
   point at which T8a leaks at 0.66 and the carrier false rate is 0.266. **No
   `k` makes T8a and T11 evaluable and leak-free together**: the exposure the
   pair-day consumer needs and the purity the event consumer needs pull in
   opposite directions along the same axis.
3. **The trigger leak does not move.** 0.4837 to 0.5426 across a twelve-fold
   change in exposure and a 2.7-fold change in the carrier false rate.
   Persistence is simply not a lever on it.

---

## 8. Where the trigger leak comes from — T-PRED, evaluated

**T-PRED, registered in §4.4:** the trigger-chain leak would rise in arms A and
B because the class is selected for containing chains, and it would fall in arm
C **if and only if** the leak is a cadence artefact — free motion flagged
because v1's baseline reached back too far.

| | measured |
|---|---:|
| leak, arm B | **0.4837** [0.4319, 0.5399] |
| leak, arm C (cadence clause) | **0.3715** [0.3072, 0.4453] |
| chains removed by the cadence clause | **318 → 117**, 63% |
| exposure removed by the cadence clause | **25,714 → 12,317**, 52% |
| baseline reach `dt` at the 318 leaking chains, median | **6.43 d** (p25 5.77, p75 7.01, p95 8.64) |
| the archive's own median baseline reach | **4.76 d** |
| the maximum a 5.0-day-gap run permits | **27.5 d** |

**T-PRED's direction held and its mechanism is only partly supported.** The
leak rose, as registered. It falls under the cadence clause, as registered —
but by a factor of 1.30, not to the bar, and it costs more than half the
exposure, which drops T8a below its own meaningful zero. The leaking chains sit
at a baseline reach **35% longer than the archive's median but nowhere near the
27.5-day maximum**, so this is not a population of badly sampled objects; it is
a population of **fast** librators whose own motion is enough. At `dt = 6.43 d`
the requirement is `|sin 2u| > 0.9145`, i.e. `u_max > 33.1°` — and the class is
made of exactly that, because the sign clause can only see motion that trips
v1 in the first place.

> **The trigger leak is the DETECTOR's, not the class's.** These 318 chains are
> not contamination by controlled motion; they are free libration, correctly
> flagged as a drift change by a rule that does not subtract free triaxial
> motion. **A control cannot remove them, because they are real.**

---

## 9. E5 — the alarm lane's GEO arm, registered in advance

Registered as estimand E5 in §7.5, so this is not a post-registration reading.
Committed 2010s replay ledger, SHA-256 `c78462e9…`.

| | hits | alerts | precision | Wilson 95% |
|---|---:|---:|---:|---|
| **before** | 14 | 272 | **5.147%** | [3.090%, 8.453%] |
| **after**, certified-free chains removed from the denominator | 14 | 272 | **5.147%** | [3.090%, 8.453%] |
| removed | — | **0** | — | — |

The class certified **318** trigger chains as free motion and **none of them is
a spoken class-1 alert**. The re-scoring removes nothing, for the same reason
T22's did: the alarm's class-1 triggers are wide-crossing events on objects
that have left their slots, and this class is built from objects that have not.

**What the lane's GEO arm actually gains from this track is a number, not a
precision change:** its own trigger fires **318 times in 25,714 days of motion
this instrument certifies as free libration, 0.4837 [0.4319, 0.5399] of the
rate it fires on objects that can manoeuvre**, against a bar of 0.10 and
against the LEO control's 0 over 18,792,698 object-days. **The GEO arm still
has no passive control, and the size of what it does not have is now 0.4837 —
larger than T8e's 0.288, because this class is purer and therefore more
concentrated in the motion the trigger reacts to.**

**The re-freeze candidate this track can name, and the sentence that limits
it.** Every one of the 318 chains is a **v1** flag chain; **zero v2 flags fall
inside any admitted interval**, because the substrate's own admission rule
forbids them. So swapping the lane's GEO trigger from v1 to v2 — the rule that
predicts and subtracts free triaxial motion before testing a drift change —
would remove all 318. **That is a construction and not a measurement**, it is
printed here for the same reason T8e printed its own, and it licenses exactly
one owed item: **measure v2's RECALL against the labelled manoeuvre set before
proposing it as the lane's GEO trigger.** Nothing here measures recall, at GEO
or anywhere.

---

## 10. Gates

| Gate | Registered meaning | Measured | Fired |
|---|---|---|---|
| **G-S1** | the classifier admits nothing | 127 intervals | no |
| **G-S2** | no reading has exposure above its meaningful zero | T8a at 1.535×, trigger at 657× | no |
| **G-S3** | the control leaks | trigger 0.4837 in every arm | **yes** |
| **G-S4** | the sign clause rejects free motion | 0 of 155 | no |
| **G-S5** | a keeper outside the blind band is admitted | 0 of 164 | no |
| **G-S6** | the slow librator is mislabelled | V3 split bar missed | **yes** |
| **G-S7** | provenance | both pins verified | no |
| **G-S8** | persistence did not buy what §3.5 derived | `k = 6`, `q_6 = 0.0999` | **yes** |

**V5, the parity split.** Even NORAD: 59 intervals, 11,545 object-days, trigger
leak **0.4472**. Odd: 68 intervals, 14,169 object-days, trigger leak
**0.5134**. The halves differ by **1.15×**, inside the registered factor of 3,
so the trigger reading is **stable**. T8a and T11 are UNEVALUABLE in both
halves, which is what splitting a thin exposure does and is printed rather than
read.

---

## 11. Defects in this registration, reported rather than edited out

1. **§3.5's `p = 0.1706` is not this track's false rate.** It was carried from
   T22, whose sign test uses a ±45-day slot median. The causal
   baseline-window sign the registration itself specified in §3.2 measures
   **0.2660** on the same carriers. The registration derived a factor from a
   number its own instrument would not produce; it also required the factor to
   be measured before use, which is what saved the track from using it.
2. **V1's admission bar of 0.80 was unattainable against this registration's
   own §4.4 derivation.** §4.4 proves that free motion at the archive's median
   cadence cannot trip v1, and V1's librators are generated at exactly that
   cadence. A bar of 0.80 asked a positive-evidence classifier to admit objects
   that produce no evidence. The remedy — a positive control generated at the
   cadence the archive actually carries on the objects the class is built from
   — belongs in a new registration.
3. **V3's split bar inherits the same fault** and fired G-S6 for it. The slow
   librator was not misclassified; it was unjudgeable, which is a different
   thing and is what the instrument reported.
4. **The registration did not derive that arm B would equal arm A.** It is
   derivable from §4.4 and was not derived, so the amplitude clause's zero cost
   arrives here as a measurement where it could have arrived as a prediction.
5. **Two committed values of the same acceleration differ in the fifth
   significant figure** (§2).

Each needs a new registration; none may be repaired inside this one.

---

## 11b. Deviations, each declared

| # | what | why, and what it cost |
|---|---|---|
| **D1** | **The first launch aborted inside E5** on a three-versus-two tuple unpack of an imported Wilson helper. | No estimand had been written to any file; the fix touched that call site and nothing else, and **both completed runs postdate it**. The aborted launch's console output is not used anywhere in this document |
| **D2** | The `q_k` measurement reads **T22's committed carrier and passive rosters** from `docs/matched-filter-devset-20260922.json` rather than re-deriving them from the 369 MB arm-G burn-type ledger. | The same roster file T22 read, the same 207 carriers and 239 passives, and **no burn type enters this track at all**. It also means no large artefact was regenerated and disk was untouched |
| **D3** | V3's slow librator and V4's two fixtures are built by a **thin wrapper over T11b's own integrator** rather than by a named generator in `geo_passive_control`, which has no single-object entry point. | The integrator, the acceleration, the stable longitude and the sample spacing are all imported; only the initial condition and the resampling step are set here |
| **D4** | V4's "dense" control was generated at **2.0-day spacing rather than 4.0**. | A proof written before any archive number showed the substrate's evaluability needs `5.5 h ≤ 14.00 d`, so a 4.0-day series cannot produce an epoch at all. The ceiling is now asserted as its own proof and reported as blind spot 6 |

---

## 12. Declared blind spots, carried and new

1. **`A` is an upper bound**, so every test admits too much, never too little.
2. **Clause (b)'s derivation bounds dwell against a FIXED longitude.** The
   co-moving-librator evasion is untested because the class produced no leaking
   event to test it on (§6.3).
3. **The completed blind band is 16.32% of longitude.** A keeper inside it is
   unclassifiable rather than admitted — safe, and it costs exposure.
4. **Recall is unmeasured**, inherited from T11 §9.2 and T22 §9.4. Every count
   is a lower bound, including the 318.
5. **An asserted interval is not a statement about an object** outside it.
6. **The substrate cannot judge a coarse cadence.** v2's evaluability needs
   `5.5 h ≤ 14.00 d`, so nothing sampled more sparsely than **2.545 days** can
   enter the class at all. A proof asserts it. This is T8e blind spot 3,
   quantified.
7. **The T8a zero rests on 1.535× the meaningful zero** and its interval runs
   to 2.41.
8. **On the archive, the sign clause and the amplitude clause refused nothing**
   (§6.1). The substrate had already done their work, so the composition this
   track set out to test was never put under load on a real object. Everything
   the sign clause is credited with here is synthetic.
9. **This is not a blind analysis.** Every constant was read before the
   registration was written; only the combination, the derivations and the
   decision rule were fixed in advance.

---

## 13. What is owed

1. **A positive control at the archive's real cadence.** Every synthetic
   librator here is sampled at 0.865 d, where §4.4 proves no v1 chain can
   arise. The class is built from objects the archive samples more coarsely,
   and no synthetic exercises that regime. **Until one does, the V1 and V3
   readings say nothing about the objects the class actually contains.**
2. **v2's recall at GEO**, before the re-freeze candidate of §9 may be proposed
   as anything.
3. **A classifier that does not require positive evidence.** The whole exposure
   loss here comes from demanding `k` chains. T8e's class, which admitted
   quiet epochs, had 517,391 object-days and leaked; this one has 25,714 and
   is pure on T8a. **Nothing in the programme has measured the class in
   between**, and the operating-point curve's `k = 1` row — 203,376 object-days
   at a T8a leak of 0.659 — is the only point on that line.
4. **The co-moving-librator blind spot**, still untested (§6.3).
5. **T11's exposure problem is now worse, not better.** T8e solved it with
   23,960,622 pair-days; this track has 153,061. Any successor must say in
   advance how it intends to reach 2,523,957 pair-days without readmitting the
   slow librators that carry the T8a leak.
6. **A substrate that does not already do the sign clause's job**, so the sign
   test can be priced on real objects rather than on synthetics (§6.1). This is
   the single largest gap in the track and it is a registration, not a patch.
7. **Nothing in this track has been exercised as a scheduled lane, because
   nothing here is a lane.** No timer, no cron entry, no state file, no alert,
   no surface. The instrument is a one-shot measurement and it was run twice
   end to end.

---

## 14. Reproduction

```
git show b56c8b6 --stat     # the registration, committed alone, one file
git show e2ed923 --stat     # the instrument and its proofs, before any number
python3 -m unittest tests.test_geo_sign_control      # 29 proofs, no archive
python3 tools/geo_sign_control.py --out docs         # 202 s, CPU, one core
```

Receipt: `docs/t28-geo-sign-control-20260923-receipt.json` — the archive
provenance, both catalogue pins, every derived threshold with its closed form,
the persistence profile with `q_k` and `p^k` side by side, all four validations
with their bars, every reading with its exposure and its meaningful zero, the
operating-point curve whole, the parity split, E5 with its ledger hash, the
labelled diagnostics and the instrument's own SHA-256
`60f8575a16872f42dfbdb7af956edb054752c24f4fed7b5a8745114cdfb8fe89`. Interval
ledger: `docs/t28-geo-sign-control-20260923.jsonl`, one row per asserted
interval with the evidence that admitted it. Nothing from this study was
written to `src/`, `data/`, `public/` or any site surface.
