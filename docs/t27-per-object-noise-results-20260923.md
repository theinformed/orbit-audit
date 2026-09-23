# T27 results — the per-object-noise arm: NOT SHIPPED, on the passive control

**VERDICT. The change is NOT SHIPPED, and the failing clauses are E3a and E3c —
the passive control. It buys the recall both by-products said it would, and it
buys it by lowering the bar hardest on the one class of object that cannot
manoeuvre at all.** On the eleven-spacecraft label set recall rises from
**90/1,134 = 7.937%** [6.502, 9.656] to **128/1,134 = 11.287%** [9.572, 13.257]
— an increment of **+3.351 points**, object-cluster 95% **[1.120, 5.537]**
against a minimum detectable effect of 2.208 points, 90-day block 95% [2.024,
4.909] — with the labelled-quiet false-flag count **unchanged at 18**, so **E1
passes on the arm of record**. But run over the archive's own low-orbit
population, the flag rate on the physically passive class — 9,915 objects of
`DEBRIS` and `ROCKET BODY` over 86,859,654 object-days — rises from
**0.0017565** to **0.0044933 flags per object-day**, and the registered
bound-versus-bound test is not close: the per-object arm's Jeffreys 95% lower
bound of **0.0044792** stands above the shipped arm's Jeffreys 95% upper bound
of **0.0017653**, a point ratio of **2.558×**. **E3a FAILS.** The campaign-level
passive-to-payload alert ratio rises from **0.5378 to 0.7396**, so **E3c FAILS**
too. E4 passes comfortably (1.065× the flags, 1.187× the campaign starts,
against a registered 2.0× bar) and E5's reversal clause does not fire.

**And the reason is measured, not guessed.** On the control's own admitted
population the median per-object scale of the passive class is **0.062 × the
pooled value** — sixteen times smaller — against **0.948 ×** for payloads.
Debris and spent stages are ballistic: nothing perturbs them but drag, so their
fit-to-fit scatter is tiny and a per-object bar collapses on them. Payloads
carry the very manoeuvres the detector is looking for, and the estimator's
second-difference median absolute deviation absorbs them, so their own bar
barely moves. **The estimator is contaminated by the signal it is meant to
help detect.** The measured consequence is exactly that asymmetry: passive
in-track flags rise **151,543 → 379,720** (2.506×) while payload in-track flags
**fall** 1,573,393 → 1,527,134 (0.971×).

**Both placebos reproduce the per-object arm to the flag.** Giving every
spacecraft *another* spacecraft's scale (P1, a seeded derangement) returns
**128/1,134**, 18 quiet flags and 520 unmatched — identical in every cell.
So does a scale computed from a window displaced two years (P2). The
registration wrote the consequence down before any number existed
(§1.5, §5.1): **the gain is the registered 50 m floor term becoming binding,
not the detector adapting to the object, and the word describing adaptation is
withheld from this document.** On all eleven spacecraft the threshold moves
from `5σ_n` to the 50 m floor and the detectable step moves from 102.2–126.0 m
to exactly 50.0 m.

**Registration:** `docs/t27-per-object-noise-preregistration-20260923.md`,
committed **alone** at `b85df25` before the instrument existed and before any
T27 number. **Instrument:** `tools/per_object_noise.py` with 25 offline proofs
at `23abc1c`, still before any number. **Artefact:**
`docs/t27-per-object-noise-20260923.json`. **Host:** `pc`, CPU only, `nice -n
15`; no GPU stage declared and none used.

---

## 0. Read the floors and the gates first

| | |
|---|---|
| Shipped detector floor, eleven spacecraft | **102.2 – 126.0 m** of semi-major axis, set by `5σ_n` on all eleven |
| Per-object arm floor, same eleven | **50.0 m**, set by the `DA_FLOOR_KM` term on all eleven |
| Cadence-only schedule floor, same labels, same operating point (T18 §0) | **5.115%** [3.977, 6.555] |
| **G1 — the production detector untouched** | **discharged.** `git diff` over `proximity_plane.py`, `trigger_alarm.py`, `alarm_lane_leo.py` and `pipeline/orbit_events.py` empty; blob hashes in the artefact |
| **G2 — reproduction before novelty** | **discharged, exactly.** Shipped 90/1,134 with 18 quiet flags and 321 unmatched; per-object 128/1,134 with 18 and 520. Every one of the eight published cells reproduced to the unit before any T27 number was read |
| **G3 — no cross-population increment** | held. No eleven-spacecraft number is differenced against a catalogue number anywhere below |
| **G4 — the minimum detectable effect beside every increment** | held; §1.3 |
| **G5 — the `\|Δa\|` proxy is a stratifier** | held. It is read from the same element sets the detector reads and carries no claim |
| **G7 — exposure floor for E3a** | did not fire: 9,915 passive objects against a bar of 200 |

---

## 1. E1 — recall, at the shipped false-flag operating point

### 1.1 The primary cell

Association on MAD-LEO's own event window (event −6 h / +24 h), 1,134 labels,
**0 not evaluable**. Both arms sit at the **same** labelled-quiet false-flag
count, 18, so the comparison is a comparison.

| arm | hits | recall | Wilson 95% | quiet flags | unmatched | placebo | lift |
|---|---:|---:|---|---:|---:|---:|---:|
| **shipped (pooled σ)** | 90/1,134 | **7.937%** | [6.502, 9.656] | **18** | 321 | 17/5,610 = 0.303% | **26.2×** |
| **per-object σ** | 128/1,134 | **11.287%** | [9.572, 13.257] | **18** | 520 | 27/5,610 = 0.481% | 23.5× |
| P1 — donor-permuted σ | 128/1,134 | 11.287% | [9.572, 13.257] | 18 | 520 | 27/5,610 | 23.5× |
| P2 — σ from a window displaced two years | 128/1,134 | 11.287% | [9.572, 13.257] | 18 | 520 | 27/5,610 | 23.5× |

The **placebo** column is the registered association control: the identical rule
applied to the same windows displaced by ±30, ±60 and ±90 days, discarding
placebo windows landing within two days of another label. Both arms beat their
own background by more than twenty-fold, so neither recall is background flag
density.

**The plane channel recalled zero of 1,134 manoeuvres under every arm**, as
T16b measured and as T8b's 3.5° plane threshold implies. Nothing is concluded
from it here.

**Campaign level — what an alarm lane would actually say:** 15/1,134 = 1.32%
[0.80, 2.17] shipped against 23/1,134 = 2.03% [1.36, 3.03] per-object. Neither
number may be printed without the other.

### 1.2 Per spacecraft, and the floor that moved

| spacecraft | shipped | per-object | own σ_n (rev/day) | ratio to pooled | floor (m) |
|---|---:|---:|---:|---:|---|
| cryosat-2 | 13/241 | **32**/241 | 4.963e-07 | 1/126 | 102.2 → 50.0 |
| hy-2a | 0/58 | 0/58 | 4.479e-07 | 1/140 | 111.4 → 50.0 |
| jason-1 | 7/119 | 10/119 | 2.118e-07 | 1/296 | 125.5 → 50.0 |
| jason-2 | 16/111 | 17/111 | 1.997e-07 | 1/314 | 124.9 → 50.0 |
| jason-3 | 17/85 | 17/85 | 1.755e-07 | 1/358 | 126.0 → 50.0 |
| saral | 8/67 | 15/67 | 3.450e-07 | 1/182 | 104.6 → 50.0 |
| sentinel-3a | 2/147 | 6/147 | 2.179e-07 | 1/288 | 105.3 → 50.0 |
| sentinel-3b | 8/145 | 9/145 | 4.237e-07 | 1/148 | 105.3 → 50.0 |
| sentinel-6a | 4/32 | 4/32 | 1.332e-07 | 1/471 | 126.0 → 50.0 |
| swot | 11/86 | 12/86 | 4.600e-07 | 1/136 | 108.6 → 50.0 |
| topex-poseidon | 4/43 | 6/43 | 1.755e-07 | 1/358 | 126.0 → 50.0 |

On **all eleven** the binding term changes from `5σ_n` to the 50 m floor. That
is the registration's §1.5 prediction, measured, and it is why both placebos
reproduce the arm exactly: on this population the per-object scale never enters
the threshold at all.

### 1.3 The increment, two bootstraps, and the minimum detectable effect

| interval | increment | 95% | minimum detectable | lower bound above zero? |
|---|---:|---|---:|---|
| **object cluster (11 spacecraft, arm of record)** | **+3.351 pts** | **[1.120, 5.537]** | 2.208 pts | **YES** |
| 90-day time block (118 blocks) | +3.351 pts | [2.024, 4.909] | 1.443 pts | YES |

Both are paired, 2,000 resamples, seed 20260923. The arm of record is the more
conservative lower bound, named in the registration before either was computed.
The increment exceeds its own half-width on both, so it is **demonstrable by
this design** rather than merely positive. **E1 passes.**

Against the cadence-only schedule floor measured on these same labels at this
same operating point (T18: 5.115%), the shipped arm stands **+2.822 points**
and the per-object arm **+6.172 points**.

### 1.4 Where the increment lives — and this is not T18's stratum

The shipped arm's own 102–126 m floor splits the labels into what it can see and
what it cannot. Thirty-five of the thirty-eight extra hits — **92.1%** — land
below that line:

| stratum | shipped | per-object | extra |
|---|---:|---:|---:|
| **above** the shipped 102–126 m floor | 81/157 = 51.59% [43.83, 59.28] | 84/157 = 53.50% [45.71, 61.13] | +3 |
| **below** it | 9/977 = 0.92% [0.49, 1.74] | 44/977 = **4.50%** [3.37, 5.99] | **+35** |

T18's learned model failed for a reading that looks like this one, so the
distinction has to be made explicitly. **It is not the same stratum
behaviour.** T18's below-floor hits ran at 1.84% [1.169, 2.893] against its own
placebo density of 0.998% [0.770, 1.294] — a lift of 1.85×, with a Wilson lower
bound that only just cleared the placebo's upper bound. Here the below-floor
hits run at **4.50%** [3.37, 5.99] against this arm's own placebo density of
**0.481%** [0.33, 0.70] — a lift of **9.36×**, and the two intervals are nowhere
near each other. The hits are separable from the background that produced them.

Split at the **per-object arm's own** floor instead, the picture is what a moved
floor should look like: 108/216 = 50.0% above it, 20/918 = 2.18% below it. The
shipped arm's own split is 81/157 = 51.6% and 9/977 = 0.92%. **Both arms catch
about half of what they can see.** What changed is how much they can see.

---

## 2. E2 — the two false-flag counts, as counts

| | shipped | per-object |
|---|---:|---:|
| labelled-quiet windows | 1,139 (1,423.75 window-days) | same |
| **flags inside them** | **18** | **18** |
| …in windows the dataset itself marks as suspected unreported manoeuvres | 9 | 9 |
| windows carrying at least one flag | 10 of 1,139 | 10 of 1,139 |
| flags per stable-window-day | 0.012643 | 0.012643 |
| flags inside the labelled span | 460 | 715 |
| **unmatched flags** | **321** | **520** |

The 18 is an **upper bound** on false flags: MAD-LEO's stable windows are mined
from an element-set archive rather than declared quiet by an operator, and the
dataset flags half of these very windows as suspected unreported manoeuvres. The
321 and 520 are **counts**, never a false-alarm rate, because the completeness of
the published manoeuvre histories is not verified here.

**The cell that matters for the verdict is the last row, not the bold one.** The
unchanged 18 is what both by-products reported as the change's headline
attraction; the same change raises unmatched flags on the same eleven
spacecraft by **62%**. Neither number is a false-alarm rate, which is why the
decision rests on E3 and not on either of them.

---

## 3. E3 — the passive control, and the clause that stops the change

### 3.1 E3a — the physically defined passive class. **FAILS.**

`DEBRIS` and `ROCKET BODY` in low orbit, admitted at the control's own bar of
200 element sets and 365 days. The admission is frozen at the shipped arm's, so
both arms are scored on one population. This is an **upper bound** on the
false-alarm rate, because some spent stages do perform disposal burns.

| | shipped | per-object |
|---|---:|---:|
| objects | 9,915 | 9,915 |
| exposure | 86,859,654 object-days | same |
| **flags** | **152,567** (151,543 in-track / 1,024 plane) | **390,284** (379,720 / 10,564) |
| **flags per object-day** | **0.0017565** | **0.0044933** |
| **Jeffreys 95%** | **[0.0017477, 0.0017653]** | **[0.0044792, 0.0045074]** |
| flags per object-year | 0.6416 [0.6383, 0.6448] | 1.6412 [1.6360, 1.6463] |
| objects carrying any flag | 8,665 = 87.39% | 9,365 = **94.45%** |
| campaign-initiating in-track alerts per object-year | 0.13897 | 0.21421 |

**The registered test, and it is not close.** The change fails E3a if the
per-object arm's Jeffreys 95% lower bound exceeds the shipped arm's Jeffreys 95%
upper bound. It does, by a factor of **2.54** on the bounds themselves
(0.0044792 against 0.0017653) and **2.558×** on the point estimates. The
exposure floor G7 did not fire. **E3a FAILS.**

### 3.2 Why it fails — the estimator is contaminated by the signal

The registration predicted (§1.5) that a per-object scale would *raise* the bar
on badly-tracked objects and so *remove* their flags, and named the passive
class as where that would be measured. **The prediction is wrong, and the
measurement says why.**

Post-registration diagnostic, labelled as such, on the control's own admitted
population:

| class | objects | median own σ_n | as a multiple of pooled | quartiles | below pooled |
|---|---:|---:|---:|---|---:|
| **catalogue-passive** | 9,915 | **3.874e-06** | **0.062 ×** | [1.374e-06, 9.634e-06] | **97.8%** |
| payload | 12,520 | 5.950e-05 | 0.948 × | [5.429e-06, 9.451e-05] | 55.2% |

Debris and spent stages are **ballistic**: nothing acts on them but drag and the
fit, so their fit-to-fit scatter is sixteen times smaller than the population
median the shipped detector uses. Payloads carry the manoeuvres the detector is
hunting, and the estimator — a median absolute deviation of second differences
over the object's whole retained history — absorbs those steps into its own
scale. So the change lowers the bar **hardest on the class that cannot
manoeuvre** and **barely at all on the class that can**.

The flag counts are that sentence, measured:

| channel and class | shipped | per-object | ratio |
|---|---:|---:|---:|
| **passive, in-track** | 151,543 | **379,720** | **2.506×** |
| **payload, in-track** | 1,573,393 | **1,527,134** | **0.971×** |
| passive, plane | 1,024 | 10,564 | 10.32× |
| payload, plane | 9,278 | 80,799 | 8.71× |

**The payload in-track count falls.** A manoeuvre detector whose passive flags
multiply by two and a half while its payload flags decline is moving in the one
direction a detector may not move, and no recall number on eleven cooperative
spacecraft rescues that.

This is a property of *this estimator with this window*, not a law about
per-object noise. A scale estimated inside declared quiet stretches — which the
estimator's own docstring describes and its code does not do (registration
§1.3) — is a different change, and this track does not measure it.

### 3.3 E3b — the frozen never-manoeuvred class. Reported, not gating.

**This class is defined by the shipped detector raising no flag on it**, so the
shipped arm's rate is zero by construction and any per-object flag makes the
change look worse for a reason that is not about the change. The production file
says exactly this at `detector_false_alarm_rate`. Reported with the circularity
named, as registered, and gating nothing.

| | shipped | per-object |
|---|---:|---:|
| objects (low orbit) | 2,259 | same |
| exposure | 26,054,565 object-days | same |
| flags | **0** *(by construction)* | **14,508** (12,831 in-track / 1,677 plane) |
| per object-day | 0.0, Jeffreys 95% [0.0, **9.641e-08**] | 5.568e-04 [5.478e-04, 5.659e-04] |
| objects now carrying a flag | 0 | **993 of 2,259 = 44.0%** |
| **payload subset** | 765 objects, 11,761,949 object-days | same |
| payload subset flags | 0, Jeffreys 95% [0.0, 2.136e-07] | 2,713 (1,649 / 1,064), 2.307e-04 [2.221e-04, 2.395e-04] |
| payload objects now carrying a flag | 0 | **205 of 765 = 26.80%** |

**The registered secondary screen is a named concern.** It asked whether more
than 10% of the frozen never-manoeuvred payload objects acquire a flag. 26.80%
do — 2.68 times the bar. It blocks nothing by itself, and it points the same way
as E3a.

The zero rows carry non-zero Jeffreys upper bounds because a zero point estimate
is never reported as a zero bound (Paper B §2.4).

**Two scope statements, both registered in advance rather than discovered.**
(1) T8b's published **zero events over 18,792,698 object-days** is an
*approach-event* rate produced by that track's whole analyze stage — pair
screening, geometry arms, nulls — and not a flag rate. **It is carried as
context here and is NOT re-scored.** Re-deriving it under a changed detector
needs that stage re-run, which is outside this track's compute, and it is named
in the report as unproven. (2) This track's frozen class holds 2,259 low-orbit
objects (765 payload) against T8b's cross-tabulated 3,011 (855 payload), because
T8b's count spans every regime and this one is restricted to low orbit.

### 3.4 E3c — the alarm lane's own passive ratio. **FAILS.**

The live low-orbit alarm arm publishes no clause about what its flags mean,
because its own passive control fires at **0.797** of the rate it fires on
objects that can manoeuvre. A detector change may not make that worse.

| | shipped | per-object |
|---|---:|---:|
| passive campaign alerts per object-year | 0.13897 | 0.21421 |
| payload campaign alerts per object-year | 0.25841 | 0.28963 |
| **ratio** | **0.5378** | **0.7396** |

The ratio rises by a factor of **1.375**. **E3c FAILS.**

**These are not the alarm lane's published 0.797** and must never be printed as
if they were: that figure comes from the lane's own replay over 2020-01-01 →
2023-06-01 in its own band, and this one is measured over the whole retained
low-orbit archive. The registered clause is on *this* measurement, with both
arms computed by one instrument on one population, and it is like-for-like
internally. The published figure is the reason the clause exists and not its
baseline.

---

## 4. E4 — the catalogue-wide price. **Passes, and the clause was declared weak.**

61,861 low-orbit objects, 172,386,301 object-days = 471,968 object-years, from
the existing element-set column cache.

| | shipped | per-object | ratio |
|---|---:|---:|---:|
| flags | 2,765,282 | 2,944,697 | 1.065× |
| …in-track | 2,753,349 | 2,845,593 | 1.034× |
| …plane | **11,933** | **99,104** | **8.31×** |
| flags per object-year | 5.859 | 6.239 | **1.065×** |
| campaign starts (in-track) | 129,508 | 153,725 | **1.187×** |
| objects carrying any flag | 49,137 | 49,294 | 1.003× |

Both registered quantities sit well inside the 2.0× bar. **E4 passes** — and the
registration declared this clause weak in the same breath that set it, because
the eleven-spacecraft ratio the bar sits above was already published. It is a
guard against a blow-up, not a discriminating test, and it discriminated
nothing.

**The price, in the units the alarm lane inherits.** Across the whole retained
archive the change adds **179,415 flags** and **24,217 campaign starts**. At the
catalogue's present object count that is **+0.380 flags per object-year ×
61,861 objects = about 23,500 extra flags a year**, and **about 3,170 extra
campaign alerts a year**. The lane's own replay raised roughly 1,558 alerts a
year, so the addition is of the order of twice its present intake — affordable
by the registered bar and not obviously affordable by the lane.

**The plane channel is the finding inside E4.** It carries **87,171 of the
179,415 extra flags — 48.6% of the entire growth** — and it is the channel T8b
**blinded by its own registration**: its registered plane-noise calibration came back 145
times too large, which set the plane threshold to 3.5° and switched the channel
off, and the alarm lane ships with that channel unbuilt and its vocabulary
banned from its strings. The change reopens it silently, and not through the
0.01° resolution floor: only **87** of 61,861 objects have their plane bar
pinned there. It reopens because the median per-object plane scale is 0.70476°,
so five of it is **3.52°** at the median and far less below it, against the
pooled arm's fixed 3.497°. **A change advertised as touching the in-track floor
turns a blinded channel back on for half its cost.** Nothing in either
by-product measurement could have seen this, because the plane channel recalls
zero on the label set under both arms.

**The scale distribution, for the record.** Of 56,890 low-orbit objects with a
finite own scale, 30,665 (53.9%) sit **above** the pooled value and 26,225
(46.1%) below; the median is 7.073e-05 (1.127 × pooled) and the p95 is
5.804e-03 (92.5 × pooled). The plane scale's median is 0.70476° (1.008 ×
pooled), p95 2.8914°. **4,971 objects fell back to the pooled value in both
channels** under the registered ladder; **no object returned a zero scale**, so
rung 3 was never exercised.

Read against §3.2, the distribution is the trap: a *median* near the pooled
value conceals two populations pulling in opposite directions, and the one
pulling the bar down is the one that cannot manoeuvre.

---

## 5. E5 — burn size, and the reversal clause

| `\|Δa\|` bin | labels | shipped | per-object |
|---|---:|---:|---:|
| < 20 m | 576 | 6 = 1.0% | 8 = 1.4% |
| 20–50 m | 342 | 2 = 0.6% | 12 = 3.5% |
| **50–100 m** | **53** | **1 = 1.9%** | **21 = 39.6%** |
| 100–200 m | 27 | 10 = 37.0% | 14 = 51.9% |
| 200–500 m | 36 | 21 = 58.3% | 22 = 61.1% |
| ≥ 500 m | 100 | 50 = 50.0% | 51 = 51.0% |

**The 50–100 m bin is the floor moving and almost nothing else**: twenty of the
thirty-eight extra hits are in a bin holding 4.7% of the labels. It is the bin
that straddles the two arms' floors — above the per-object arm's 50 m and below
the shipped arm's 102–126 m — and it behaves exactly as a moved floor must.

**The registered reversal clause does not fire.** No bin has the per-object arm
worse than the shipped arm, so no interval was computed and the pooled claim is
not withheld. `|Δa|` is a stratifier read from the same element sets the
detector reads, and carries no claim (gate G5).

---

## 6. The decision

**NOT SHIPPED.** The registered rule requires all five clauses; two fail.

| clause | verdict |
|---|---|
| **E1** — increment lower bound above zero, outside the minimum detectable effect | **PASSES** (+3.351 pts, [1.120, 5.537], MDE 2.208) |
| **E2** — both counts reported as counts | reported: 18 / 18 and 321 / 520 |
| **E3a** — passive rate not demonstrably worse | **FAILS** (Jeffreys lower 0.0044792 above Jeffreys upper 0.0017653; 2.558×) |
| **E3b** — frozen never-manoeuvred class | reported, not gating; the 10% secondary screen is a **named concern** at 26.80% |
| **E3c** — alarm lane passive/payload ratio not larger | **FAILS** (0.5378 → 0.7396) |
| **E4** — growth within 2.0× | **PASSES** (1.065×, 1.187×) — clause declared weak in advance |
| **E5** — no bin reverses | **PASSES** |

**What the programme keeps from this.** The recall gain is real, measured twice
over and demonstrable by its own design — and it is not what it was called. It
is the 50 m floor term becoming binding on well-tracked objects, which two
placebos establish and which the eleven per-spacecraft rows show directly. **The
cheap change that the two by-products identified is therefore a smaller and more
precise change than they described, and it can be registered on its own terms:
lower the in-track floor on objects whose fit supports it, by a rule that does
not read a scale the manoeuvres themselves contaminate.** This document does not
propose that change; it records that the change actually measured here is not
it, and names why.

---

## 7. Deviations

1. **The registration commit's message was truncated by a shell fault** while
   the file itself was committed whole and alone. The registration file at
   `b85df25` is complete and was never edited afterwards; amending is barred by
   the repository's own rules, so the full text is attached to that commit as a
   note. The registration-alone property is intact and verifiable from the
   commit's file list.
2. **Two post-registration diagnostics were added and are labelled as such in
   the artefact and above**: the per-channel split of every control cell (§3.1,
   §3.3, §4), added after the pooled cells were read because the passive control
   cannot be explained without knowing which channel produced it; and the
   per-object scale by class (§3.2), added because E3a's direction is the
   opposite of the registration's §1.5 prediction and the reason had to be
   measured rather than asserted. **Neither touches a screen, a threshold, a
   bar or a decision rule**, and the verdict is identical with or without them.
3. **E3b's frozen class is restricted to low orbit** (2,259 objects, 765
   payload) where T8b's published cross-tabulation spans every regime (3,011,
   855). The restriction follows from this track's registered population **C**
   and is noted where the counts appear.

## 8. What is unmeasured, in those words

- **T8b's approach-event control is not re-scored.** The published *zero events
  over 18,792,698 object-days* is an approach-event rate from that track's whole
  analyze stage, not a flag rate, and re-deriving it under a changed detector is
  **unproven** here. §3.3 measures the flag-level analogue instead and says so.
- **The alarm lane's published 0.797 is not recomputed.** The lane's replay was
  not re-run under the change; §3.4's ratios are this instrument's own, on a
  different window and population, and the two are never equated.
- **No estimator other than the one in the production file was tested.** A scale
  estimated inside declared quiet stretches, or shrunk toward the pooled value,
  or clipped, is a different change and is **unmeasured**.
- **Nothing here is a census.** Eleven cooperative, well-tracked spacecraft with
  published manoeuvre logs. No recall number above is about any constellation or
  any operator whose manoeuvre log is not public.
- **Every threshold named above is a screen, not a law** — the five-sigma
  multiplier, the 50 m and 0.01° floors, the burn-size bins, the 2.0× growth
  bar, the 10% secondary screen. Two of them are this track's own and were
  chosen, not derived.

## 9. Reproduction

```
python3 tools/per_object_noise.py --stage labels    --out <work>/labels.json
python3 tools/per_object_noise.py --stage catalogue --out <work>/catalogue.json
python3 tools/per_object_noise.py --stage sigma     --out <work>/sigma.json
python3 -m unittest tests.test_per_object_noise          # 25 proofs, all pass
```

Inputs, all read-only: the programme archive, the MAD-LEO tables under
`/home/sdegan/t16b-truth`, and the existing element-set column cache under
`/home/sdegan/t13-work` (68,749 objects, 217,046,214 rows). Seed 20260923
everywhere. Nothing large was written: the three stage files and the merged
artefact total under 200 kB.
