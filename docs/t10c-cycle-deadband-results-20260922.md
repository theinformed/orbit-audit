# The cycle-resolved east-west deadband — measured

**Registration:** `docs/t10c-cycle-deadband-preregistration-20260922.md`,
committed alone at `0a49ba5` before any number below existed.
**Parent:** `docs/stationkeeping-efficiency-preregistration-20260922.md`
(`f0f2b41`) §4, results `docs/stationkeeping-efficiency-results-20260922.md`.
**Instrument:** `tools/t10_followup_deadband_cycles.py` (`9189e92`, corrected
floor `a67804e`), 22 offline proofs in
`tests/test_orbit_t10c_cycle_deadband.py`.
**Artifacts:** `docs/t10c-cycle-deadband-20260922.jsonl`,
`docs/t10c-cycle-deadband-20260922-receipt.json`.
**Compute:** CPU only, 389 s wall, 1.17 GB peak RSS on `pc`. No GPU arm, so no
`gpu-consumers.json` row is owed.

---

## The verdict, stated first — and it has two halves that must not be mixed

**The REGISTERED verdict is "MEASURED, AND THE 14.00-DAY LINE DOES NOT PREDICT
IT", at a per-object median box of 0.118 deg [0.116, 0.125] over 68 carriers.**
That is what the registered screens produce and it is reported as the registered
outcome.

**It is also wrong, and the reason is in the registration, not in the data.**
The registered floor screen G6 rests on a surrogate (F1) that is not a noise
floor. It permutes the longitude residuals *about the segment centre*, and those
residuals **contain the sawtooth itself**, so the surrogate keeps the signal's
amplitude and only destroys its order. F1 therefore measures the segment
envelope — the very quantity T10c already measured and this track exists to get
underneath — and comes out at **0.0333 deg**, which is **1.6 times larger than
the ±0.0208 deg box the 14.00-day line implies.** Screening at `3 × F1 = 0.0998
deg` then discards **183,360 of 184,591 cycles** and keeps only the tail whose
boxes are five times the target. **The registered screen makes the registered
question unanswerable by construction.**

The derived element-noise floor, which does not have that problem, is
**0.01083 deg** — measured `sigma_lambda = 0.00665 deg` on this population,
times the expected range of 12 standard normals (3.256), halved. **T3's
±0.0208 deg sits above that floor**, so the box *is* measurable.

**And measured, it agrees.** On the 80,677 cycles that pass the registered
sample, duration and ramp screens G3–G5 but not the mis-specified G6, over
**207 of the 208 GEO line carriers**:

> **measured deadband half-width 0.0203 deg, bootstrap 95% interval
> [0.0188, 0.0212] deg, against the 0.0208 deg T3 inferred independently from a
> 14.00-day periodogram line. The interval contains T3's figure.**
> **191 of 207 carriers** are within a factor of two of it.

**That number is UNREGISTERED and is NOT claimed.** It comes from dropping a
registered screen after seeing what the screen did, which is exactly what
registration exists to prevent — even though the defect was diagnosed from F1's
construction and not from its answer. A follow-up registration owes the
corrected surrogate and the corrected floor multiple, and only then may the
agreement be claimed. It is reported here because refusing to report a measured
agreement would be its own dishonesty.

**One registered check passes, and it is the one T10c most needed.** The
free-drift control — measured longitude acceleration against the derived
triaxial acceleration — has a Theil–Sen slope of **0.922, interval
[0.320, 1.094], which contains 1**. T10c's registered version of this control
returned **INPUT NOT VERIFIED** at segment scale, recovering about 1% of the
derived acceleration, and its diagnosis was that the window was longer than the
cycle. **At cycle scale the control passes, and the parent's diagnosis is
confirmed by a registered estimator rather than by the unregistered adjacent-pair
patch that was added in-track.**

---

## 1. Census and the registered path

| | Value |
| --- | ---: |
| T3 line carriers reproduced from the committed artifact | **214** (208 GEO, 6 LEO) — asserted, S2 |
| GEO carriers with archived history | 208 |
| Cycles found | 184,591 |
| ... flagged `G3-too-few-samples` | 95,110 |
| ... flagged `G4-too-short` | 78,210 |
| ... flagged `G6-at-floor` | **183,360** |
| Cycles **resolved** (all screens) | **732**, on 136 objects |
| Carriers with ≥ 3 resolved cycles | 68 |
| Registered per-object median box | 0.1180 deg [0.1163, 0.1254] |
| Carriers within a factor of two of ±0.0208 deg | **0 of 68** |
| Registered acceptance | D1 pass, D2 pass, D3 pass, **D4 fail** |
| Registered verdict | MEASURED, AND THE 14.00-DAY LINE DOES NOT PREDICT IT |

**`sigma_rate` came out 6.8 times the propagated value.** The registration asked
for two figures and required the larger: propagated from the band floor through
`dn/da = -(3/2) n/a` gives `1.598e-4 deg/day`; measured on this population by
the second-difference MAD over 1,858 segments gives **`1.091e-3 deg/day`**. The
band floor is a quiet-object measurement and the real drift-rate scatter on a
station-kept GEO satellite is seven times it. The larger was used, as registered.

---

## 2. Two defects in the registration, and what they cost

### 2.1 F1 is an envelope floor, not a noise floor

Registration §3.2 builds F1 by permuting each segment's residuals about the
segment centre, on the stated reasoning that this "destroys the sawtooth while
preserving the marginal scatter". It does destroy the sawtooth. But the marginal
scatter it preserves **includes the sawtooth's own amplitude**, because the
residuals being permuted are residuals about the segment centre, not about a
local cycle model. A time-scrambled series whose variance is dominated by the
signal returns a peak-to-trough close to the whole envelope, whatever the noise
is.

This is a property of the construction and is diagnosable without any number.
It is reported under the registration's §6.3 D1 rule: the defect is named with
its size, both floors are published, and the registration is not edited.

**Its size:** F1 = **0.0333 deg** against a derived element-noise floor of
**0.0108 deg**, a factor of 3.1, and against the target box of 0.0208 deg a
factor of 1.6 **the wrong way**.

### 2.2 D2 as registered is vacuous

D2 asks whether the median resolved box exceeds 3× the floor. Screen G6 already
requires exactly that of every cycle it admits, so the median of the survivors
cannot fail D2. **The check cannot fire.** It is reported as a registration
defect rather than as a passed criterion, and the substantive question it was
meant to ask — does the *target* box lie above the floor — is answered by the
derived-floor block instead.

### 2.3 A third problem, which is the multiple and not the floor

Even with the corrected floor, the registered `3 ×` multiple would fail: the
measured box, 0.0203 deg, is **1.87 times** the derived floor of 0.0108 deg, so
a screen demanding 3× would still discard it. **A genuine signal at twice its
noise floor cannot pass a 3σ-style screen**, and choosing 3× without first
knowing the signal-to-floor ratio was the error. The corrected registration owes
a multiple derived from the expected ratio, not chosen for comfort.

---

## 3. The measurement the corrected floor licenses — reported, not claimed

Over the 80,677 cycles passing G3–G5 on 207 of 208 GEO carriers:

| | Value |
| --- | ---: |
| Per-cycle median box | 0.01827 deg (p25 0.01143, p75 0.02718) |
| **Per-object median box** | **0.02030 deg, 95% [0.01875, 0.02119]** |
| T3's inferred box from the 14.00-day line | **0.0208 deg** |
| Carriers within a factor of two of it | **191 of 207** |
| Per-object median cycle | 9.94 d (p25 6.73, p75 11.69) |
| Carriers with median cycle in [7, 28] d | 145 of 207 |

**Two instruments with nothing in common agree on the box and disagree on the
period.** T3 measured a 14.00-day line in a Lomb–Scargle periodogram of mean
motion over 208 payloads and inverted `T = 4 sqrt(R/A)` to get ±0.0208 deg.
This reads the box directly off mean longitude, cycle by cycle, on the same 208
objects, with no periodogram anywhere, and gets 0.0203 [0.0188, 0.0212].

But the cycle it reads is **9.94 days, not 14.00**, and the two readings are not
internally consistent: the measured box is a median **2.66 times** what its own
measured cycle predicts through `R = A T^2 / 16`.

**The registration named this trap in advance** and its sentence applies with
the halves swapped:

> a 14.00-day line in a periodogram is a statement about **periodicity**, not
> about box width ... if the measured cycles come out at 14 days but the
> measured box does not, the line is still real and the inference
> `R = A T^2 / 16` is what has failed.

Here the **box** matches and the **period** does not. The registration's named
candidate — east-west keeping flown as a **pair** of burns half a cycle apart —
would halve the apparent cycle **and quarter the apparent box**. The observed
cycle is 0.71× of 14 days and the observed box is 0.98× of 0.0208 deg, so a
clean pair does not fit either. **Neither the one-burn relation nor a clean pair
explains both readings. The discrepancy is reported and it is not explained.**

A second candidate, named because the instrument makes it plausible and not
because it is established: the swing filter's prominence threshold is
`5 sigma_rate = 5.45e-3 deg/day` against a full cycle ramp of roughly
`1.7e-2 deg/day` at a typical slot, i.e. **a third of the ramp**. A noise
reversal of a third of the ramp mid-cycle splits one cycle into two, which
shortens the apparent period. Whether that accounts for 14 → 9.94 is not
measured here and is not asserted.

---

## 4. The registered control that passes — and why it matters most

| Control | Slope | 95% interval | Registered prediction | Outcome |
| --- | ---: | --- | ---: | --- |
| Measured `A_cycle` on derived `A(lambda)` | **0.922** | **[0.320, 1.094]** | 1 | **PASSES** |
| `R_rate` on `R_pos` (D4) | 0.380 | [0.169, 0.660] | 1 | **FAILS** |

T10c's registered free-drift control asked exactly the first question — is the
triaxial acceleration this theory rests on actually there in the archive — and
returned **INPUT NOT VERIFIED**, recovering about 1% of the derived value,
because it fitted one line across arcs containing several undetected cycles. An
unregistered adjacent-pair estimator added in-track afterwards recovered 0.844
[0.804, 0.885] and was labelled unregistered and allowed to change no verdict.

**At cycle scale the registered control passes**, with an interval containing 1
over 136 objects. The parent's diagnosis — "a timescale, not a physics failure"
— is now confirmed by an estimator registered before the number existed. That is
the single most durable result in this document, because it is the input every
other T10c statement depends on.

**D4 fails**, and it is a real finding rather than a technicality. The
positional read (`R_pos`, from mean longitude) and the rate read (`R_rate`, from
mean motion through eq. (21)) are the same quantity through different elements,
and they disagree by a factor of about 2.6 — `R_rate/R_pos` has a median of
**0.681** per cycle. The registration's consequence applies: the positional
estimator is reported alone and the disagreement is stated in the same sentence.
The direction is consistent with §3's period problem, since (21) carries the
ramp amplitude and the fitted acceleration, both of which a split cycle
corrupts.

---

## 5. The never-manoeuvred arm (F2) — control tightens the box

| | Line carriers (registered screens) | Never-manoeuvred GEO passives |
| --- | ---: | ---: |
| Cycles | 732 | 461 |
| Objects | 136 | 29 |
| Per-object median box | **0.1180 [0.1163, 0.1254]** | **0.1790 [0.1750, 0.1841]** |

The 331 GEO objects of class `passive` carry **zero** detected events (S3
passed with no contamination), and 29 of them hold a slot tightly enough to form
station segments — a passive object near a stable longitude librates under the
same triaxial torque with no control loop at all.

**Their excursions are 1.5 times larger than the line carriers', and the two
bootstrap intervals are disjoint**, so D3 passes: the carriers are
distinguishable from an uncontrolled object sitting in a slot, and the direction
is the physical one — control produces a tighter box than natural libration.

Both arms pass through the **same** G6 screen at the same floor, so the
comparison is like-for-like even though both are floor-selected. The comparison
on the unscreened population is not computed here and is owed with the corrected
registration.

---

## 6. Sensitivities, and the carriers that are not east-west keepers

Registered sensitivities, on the registered (G6-screened) population:

| Variant | Cycles | Median box | Median cycle |
| --- | ---: | ---: | ---: |
| Primary, prominence 5 `sigma` | 732 | 0.1329 deg (per cycle) | 18.84 d |
| Prominence 3 `sigma` | 648 | 0.1325 deg | 17.62 d |
| Prominence 8 `sigma` | 797 | 0.1301 deg | 19.93 d |
| With the parent's `i < 25 deg` screen | 730 | 0.1327 deg | — |

The prominence threshold moves the answer by under 2% across a factor of 2.7 in
`k`, and the parent's inclination clause removes two cycles. **The inclination
screen was dropped for a derived reason** — longitude keeping is
inclination-independent, since `lambda = RAAN + argp + M - theta_GMST` is
defined at any inclination and the triaxial torque on it carries no `i` to first
order — and the sensitivity confirms the choice was immaterial.

**The carriers that are not routine east-west keepers**, required to be reported
separately by registration §7: **17 of the 208** sit at 5 degrees of inclination
or more, including T3's top three named carriers — OPS 9437 (DSCS 2-7) at 15.88
deg, Gorizont 13 at 13.94, GSAT 1 at 9.09. Their median box is **0.1306 deg**
against the population's 0.1180 on the same screened population — indistinguishable
from the rest. **Whatever carries their 14-day line, this instrument cannot tell
it apart from a deadband**, and that is stated rather than resolved.

---

## 7. Delta-v, for the commercial-civil catalogue only

The line-carrier roster is **not** the commercial-civil catalogue; it is T3's
line sweep over the whole public catalogue. Every carrier in this document
carries **angles and times only**, which are geometric properties of a public
orbit that T3 has already published.

**Eight** carriers are also in `data/propulsion-catalog-v1.json`, and for those
eight — and only those — the receipt carries `DV_cycle` and the annual budget.
A test asserts that no field of a cycle record can name a delta-v, a propellant
mass, an Isp or a fuel quantity, and the catalogue's `commercial-civil-only`
policy is a stop rule that the run enforces.

Those eight show the same internal inconsistency §3 reports: their measured
cycles (14.0 to 24.2 days) are about half the period their own measured boxes
predict (32.9 to 51.4 days), which is the `R/R_pred` ratio seen per object
rather than pooled.

---

## 8. What is owed

1. **The corrected surrogate, registered.** F1 must permute residuals about a
   **local cycle model**, not about the segment centre, so that it measures the
   noise rather than the envelope. Until that is registered and run, the
   0.0203 deg agreement with T3 is reported and not claimed.
2. **A floor multiple derived rather than chosen.** 3× cannot admit a signal
   sitting at 1.87× its floor. The replacement must be derived from the expected
   signal-to-floor ratio.
3. **The period discrepancy.** The box matches T3 and the period does not, and
   neither the one-burn relation nor a burn pair explains both. Candidates named
   and untested: cycle splitting by the prominence threshold, and burn patterns
   other than one-per-cycle or a clean half-cycle pair.
4. **D4's disagreement between elements**, which at cycle scale is a real
   finding and not a technicality.
5. **The F2 comparison on the unscreened population**, which this run computes
   only for the carriers.

---

## 9. Blind spots, from the registration and measured where possible

* **One burn per cycle** is assumed by (15), (16) and (21). §3 and §4 are where
  that assumption is failing, and it is named rather than patched.
* **The estimator measures flown excursion, not licensed box.** An operator
  holding a ±0.05 deg licence inside ±0.01 deg of actual excursion is measured
  at 0.01. Every number here is a flown excursion.
* **Longitude retargets inside 0.3 deg** appear as one very large cycle; G4 and
  the period distribution expose them and nothing is removed by hand.
* **The draconitic-year longitude oscillation is not subtracted**; it is slow
  against a 10-day cycle and enters as a baseline, but it is part of `R_pos`.
* **The line carriers are not a random sample of GEO.** They are the objects
  whose mean-motion periodogram carries a 14.00-day peak, which selects for
  regular, detectable manoeuvring, so the measured box is a regular east-west
  keeper's box and the bias runs toward tighter, more disciplined boxes.
* **The published JSONL is thinned**: every resolved cycle plus every fourth of
  the rest, 47,183 rows. Every cycle is in the statistics; only the file is
  thinned, and the receipt says so.
