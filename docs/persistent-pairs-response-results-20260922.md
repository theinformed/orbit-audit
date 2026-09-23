# T11b part 1 results: the segment-level response estimator — **E3 IS NOT READ**, failing check **R1**

**Registration:** `docs/persistent-pairs-response-preregistration-20260922.md`,
committed alone at `0aa028a` before either instrument existed.
**Verdict: E3 IS NOT READ. The failing check is R1.** Per registration §6, no
hazard ratio is printed here for any arm, and none is left in the receipt
either — the receipt carries the counts and the string
`NOT READ (prereg 6: a failing check prints no hazard ratio)` in place of every
ratio, because a number left in a machine artifact is a number a reader can
read.

**What is nonetheless established, and is the point of this document:** the
registered estimator is *not* the estimator T11 used, it is *not* length-biased,
and it *can* see an effect. Three of the four checks passed, including the two
that are hard to pass — a synthetic whose truth is 1.0 and a synthetic whose
truth is 2.0 — and on the population that carries the archive's own measured
length bias the new estimator returns 1.00 where T11's returns 0.78.

---

## 0. The four registered checks, printed above any ratio

| Check | Registered bar | Measured | Verdict |
|---|---|---|---|
| **R1** — permutation null on the real data | null median `HR` in **[0.95, 1.05]** and its 95% interval containing 1.0 | **median 0.9485**, 95% [0.2520, 2.3972], 998 of 1,000 permutations | **FAILED** |
| **R2** — matched controls' sham window | 95% interval containing 1.0 and the point in [0.80, 1.25] | **1.2036**, 95% [0.9756, 1.4689] | **PASSED** |
| **R3** — flat-hazard synthetic, truth 1.0 | `HR` in [0.90, 1.10] for M1 and M2, interval containing 1.0 | **M1 0.9178** [0.7690, 1.0870], **M2 0.9376** [0.7977, 1.0932] | **PASSED** |
| **R4** — recovery synthetic, truth 2.0 | interval containing 2.0 and excluding 1.0, M1 and M2 | **M1 2.1166** [1.8394, 2.4263], **M2 2.1397** [1.8932, 2.4077] | **PASSED** |

R1 fails, so by the registered decision rule of §7 the ratio is not read and
this document names the failing check. It does not say that a response effect
exists, and it does not say that one does not.

### 0.1 Gates

| Gate | Meaning | Measured | Fired |
|---|---|---|---|
| G1 | the response estimator is biased | R1 failed | **yes** |
| G2 | the controls are selected on the outcome | R2 passed | no |
| G3 | underpowered | 26 informative events at the primary arm, bar 10 | no |
| G7 | provenance | catalogue SHA-256 matches the T11 pin | no |

---

## 1. What ran

| | |
|---|---|
| Host | `pc`, CPU only |
| Input | `docs/persistent-pairs-20260922.jsonl`, SHA-256 verified against the registered pin `5df7753…9d0167bb` |
| Archive | the same 13.89 GB orbit history, gate-F extract pin verified (217,007,154 rows scanned, 11,626,494 kept, 1,768 objects) |
| Wall | 45 s world build, 5 s matched controls, 29 s checks, 1 s models |
| Determinism | seed 20260922 for the match draw and the 1,000 permutations; no other randomness |

**The arrivals, and a defect in T11 that the registered deduplication found.**

| | count |
|---|---:|
| Catalogue rows with a resolved arrival order | 1,209 |
| **Distinct physical arrivals** `(incumbent, later arrival, arrival day)` | **524** |
| **Duplicate arrivals removed** | **685** |
| Arrivals falling on a day the incumbent was not stationed | 0 |
| Distinct incumbents | 164 |

T11's per-day estimator iterated over **episodes**, and 685 of its 1,209
"arrivals" were the same physical arrival counted again because the pair's
co-location was cut into several episodes at station-segment boundaries. The
registration required the deduplication in advance (§3) and it removed **57%**
of the units. This is reported as a defect in T11's implementation of its own
registered unit of analysis — T11 §6.1 says "one later arrival", not "one
episode" — and it is reported rather than edited away.

---

## 2. R1 — what failed, by how much, and against what precision

| | |
|---|---:|
| Permutation null median `HR` (model M1) | **0.948461** |
| Registered band | [0.950, 1.050] |
| **Distance below the band** | **0.001539** |
| Bootstrap standard error of that median (2,000 resamples of the 998 draws) | **0.021230** |
| **The miss, in units of its own precision** | **0.072 standard errors** |
| Distance of the median from 1.0 | 2.43 standard errors |
| Null 95% interval | [0.2520, 2.3972] — **contains 1.0** |
| Permutations returning a finite positive ratio | 998 of 1,000 |
| Fraction of null draws below 1.0 | 0.5351 |
| Null mean / geometric mean | 1.0652 / 0.9227 |

**The check failed on a distinction 14 times smaller than its own measurement
error.** The registration fixed the band [0.95, 1.05] and fixed 1,000
permutations, and it did **not** state the precision at which the median would
be measured. At the achieved precision the bar cannot be applied the way it is
written: the null median's standard error is 0.021, so the band's edge and the
measured value are the same number to within a fifteenth of a standard error.

**That is a defect in this registration, reported and not edited out of it.**
It is the same class of defect as T11's φ_lock degree gloss and T8a §7.2's
unvalidated bound: a quantity written down without the uncertainty it would be
compared against. The remedy — a bar stated as *"the null median's 95%
confidence interval must contain 1.0"*, or a bar on the log scale with a
stated Monte Carlo precision — belongs in a new registration, not in this one.

**No re-roll was performed.** The seed was fixed in advance and the number
above is the first and only value the registered procedure produced. Drawing
again until the median cleared 0.95 would be the exact failure this programme
registers against.

### 2.1 Is the residual a real bias, or the shape of a ratio's null?

Measured, post-registration, labelled as such, changing no registered verdict.

1. **The machinery is unbiased when it has precision.** On a synthetic
   population whose segment lengths carry a length-bias factor of **5.77**
   — close to the archive's measured 6.50 — the identical permutation null of
   the identical estimator returns a median of **0.9978**, 95% [0.8557,
   1.1606].
2. **The real arm has one ninth of that precision.** Its null 95% interval
   spans [0.252, 2.397] against the synthetic's [0.856, 1.161]. A ratio's null
   distribution is right-skewed, so its median sits below its mean: here the
   mean is 1.065 and the median 0.948, and 53.5% of draws lie below 1.0.
3. **The primary arm carries 26 informative events.** A band of ±5% on the
   median of a null built from 26 informative events is a tighter bar than 26
   events can support.

The honest reading is that **R1 has not shown the estimator to be biased**, and
that the registration's bar was mis-specified for the precision the data
affords. The registered verdict stands regardless: **E3 IS NOT READ.**

---

## 3. R3, R3b, R3c — the new estimator against the one it replaces

All three populations have a true hazard ratio of exactly 1.0 by construction.
Both estimators were run on each. R3 is registered; R3b and R3c are
**post-registration additions, labelled**, and neither is a gate.

| Population | length-bias factor | segments | **segment-level M1** | **T11's per-day ratio** |
|---|---:|---:|---|---:|
| **R3** (registered) — exponential durations, mean 300 d | 2.00 | 10,207 | **0.9178** [0.7690, 1.0870] | 0.9407 |
| **R3b** — lognormal matched to the archive's measured bias factor | **5.77** | 59,897 | **0.9952** [0.8436, 1.1647] | **0.7752** |
| **R3c** — T11 §6.2's own fixture: one move every 300 days, fixed | 1.02 | 10,000 | 1.0000 [0.8687, 1.1445] | **1.3615** |

**R3 passed, and R3 could not have shown what it was registered to show.** The
registered R3 population draws durations from an exponential, which is
memoryless — and on a memoryless population the per-day rate ratio is
**unbiased**. T11's per-day estimator returns 0.9407 there, inside the band it
was supposed to miss. The registration asserted, in §6 R3, that "the two
numbers must differ and only one of them may be 1.0". **That assertion is
wrong, and it is wrong for a reason the registration should have derived: the
waiting-time paradox has no bite on an exponential.** Reported, not edited out.

**R3b is the fixture that does show it.** Give the segments a length
distribution matched to the archive's own measured length-bias factor and
T11's estimator returns **0.7752**, outside the band, while the registered
segment-level estimator returns **0.9952** with an interval containing 1.0.
That is the defect and the repair, measured side by side on one population.

**R3c reproduces T11's own committed number with an independent
implementation.** T11 §6.2 committed **1.298** for its estimator on 400
objects moving once every 300 days with `W` = 162.7 d; this implementation
returns **1.3615** on that construction — the same bias, in the same
direction, at the same size. That is the second bias T11 measured: exposure
inside the window is truncated at the segment end while the event at that end
is still counted.

**One thing R3c is not.** The segment-level estimator returns exactly 1.0000
there, and that is arithmetically forced rather than evidence: when every
segment has the same length there is one failure time, every segment is at
risk at it, and every segment fails, so the exposed fraction among failures
equals the exposed fraction at risk by construction. R3c tests the old
estimator; it does not test the new one.

---

## 4. R4 — the estimator can still see an effect

Registered because R1, R2 and R3 would all be passed by an estimator that
returns 1.0 whatever it is given.

| | M1 | M2 | T11's per-day ratio |
|---|---|---|---:|
| Injected hazard ratio | 2.0 exactly | 2.0 exactly | 2.0 exactly |
| Recovered | **2.1166** [1.8394, 2.4263] | **2.1397** [1.8932, 2.4077] | 2.1559 |
| Contains 2.0 | yes | yes | — |
| Excludes 1.0 | yes | yes | — |

The residual durations were generated by inverse transform on the
piecewise-constant cumulative hazard, so the injected ratio is exact and not
approximate. Both models recover it about 6% high, consistent with the
truncation bias R3c isolates, and both exclude 1.0 decisively.

---

## 5. R2 — the matched controls

| | |
|---|---:|
| Distinct control objects | 656 |
| Sham windows placed | 2,475 |
| Arrivals with no match (excluded, counted) | 7 |
| Arrivals with fewer than five matches | 48 |
| Events in the control segments | 1,546 |
| Sham `HR` | **1.2036**, 95% [0.9756, 1.4689] |

The interval contains 1.0 and the point estimate is inside the registered
[0.80, 1.25], so R2 passed — but it passed with the point estimate **0.046
from the bar's edge**, and the interval's lower end is 0.9756. This is
reported rather than rounded: the matching rule is closer to selecting on the
outcome than a reader should be comfortable with, and a future registration
should tighten it or match on more than crowding, tenure and calendar year.

---

## 6. Power and the risk sets, reported whatever the verdict

Informative events — an event whose risk set holds at least one exposed and
one unexposed row — at every arm, model M1 (stratified by incumbent):

| Outcome | `W` = 36.1 d | 96 d | **162.7 d** | 365 d | to segment end |
|---|---:|---:|---:|---:|---:|
| relocation (primary) | 10 | 18 | **26** | 35 | 41 |
| station departure | 599 | 1,028 | **1,149** | 1,265 | 1,293 |

At the primary arm: **3,097 incumbent station segments**, 170 relocation
events, 26 of them informative; M2 (pooled baseline) has 168 informative of
170; M3 adds **13,632 control segments** from 656 control objects and has
1,712 informative of 1,716. The registered power gate (bar 10) did not fire.

**The primary outcome is thin and always was.** 170 relocation events over
3,097 segments is one segment in 18, and the exposure windows touch 26 of
them. The registration's §5 bar of 10 was set low enough that this counts as
powered; a reader should treat that as the weakest registered decision in this
document.

---

## 7. What is not claimed

No response effect is claimed and none is refuted. The registered FALSIFIED
verdict was not reached, because reaching it requires R1 to have passed, and
the registration's §7 null wording is therefore **not** used. No sentence here
attributes a relocation to a later arrival.

The estimator's proportional-hazards assumption is **not tested** — the
registration declared that blind spot in §8.1 and nothing here discharges it.

---

## 8. Defects in this registration, reported rather than edited out

1. **R3 could not do its job** (§3). An exponential population is memoryless,
   so the per-day rate ratio is unbiased on it. The registration claimed the
   two estimators must differ there. They do not.
2. **R1's band was stated without a precision** (§2). The measured miss is
   0.072 of the bar's own standard error.
3. **R2's band is loose enough to pass a control that is drifting toward the
   outcome** (§5).
4. **The §14-style positive check on the estimator's own assumption is
   missing**: nothing in the registration tests proportional hazards.

Each needs a new registration; none may be repaired inside this one.

---

## 9. Owed

1. **A bar on R1 that is stated with its precision** — the null median's
   interval containing 1.0, or a log-scale bar with a Monte Carlo tolerance —
   and then E3 re-read under it.
2. **A test of proportional hazards**, with the `W=segment` arm as the natural
   probe.
3. **A tighter matched-control rule**, given §5.
4. Everything T11 §10 still owes that this document did not touch: the cadence
   clause off the 14.00-day line, and a composite rank whose components are
   not near-constant.

---

## 10. Reproduction

```
git show 0aa028a --stat     # the registration, committed alone
git show HEAD~1 --stat      # the instruments and their 54 offline proofs

python3 -m unittest tests.test_persistent_pairs_response      # 27 tests
python3 -m unittest tests.test_geo_passive_control            # 27 tests
python3 tools/persistent_pairs_response.py                    # 45 s + 33 s, CPU
```

Receipt: `docs/persistent-pairs-response-20260922-receipt.json` — the archive
provenance, the input pins, every check with its measured value, the 998 null
draws themselves, the informative-event counts, and the source SHA-256 of the
instrument. Nothing from T11b was written to `src/`, `data/`, `public/` or any
site surface.
