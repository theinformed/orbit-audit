# T20 results — the corrections are not periodic, and the gain that looks like structure is a bias and a schedule

**Registration**: `docs/t20-residual-forecast-preregistration-20260922.md`,
committed alone before any number was computed (`f54b32c`).
**Artefacts**: `docs/t20-residual-forecast-spectra-20260922.json` (written
before the fit existed), `docs/t20-residual-forecast-results-20260922.json`.
**Instruments**: `tools/residual_forecast.py`, `tools/residual_covariates.py`,
reusing T16b's `tools/truthset_truth.py` and `tools/truthset_sgp4.mjs`
unchanged; 28 tests in `tests/test_residual_forecast.py`.
**Wired into**: nothing. No timer, no site surface, no GPU.

---

## 0. The answer to the operator's question

He asked: *"what if the corrections — not burns but the corrections themselves —
have periodic or repeating structure? Couldn't you model them and give
predicted orbits that drift much less?"*

**On these three spacecraft, over calendar 2023, the answer is no, and the
measurement says so twice over.**

1. **There is no periodic structure to find.** Across **fifteen residual
   series** — three spacecraft × five series each — the Lomb–Scargle
   periodogram produced **zero lines above the surrogate floor**, anywhere in
   the 2-to-200-day band. The largest named-band peak in the whole study sits
   at **1.00×** the floor (Sentinel-3B, solar-rotation band, 26.79 d) — exactly
   at it, not above. The 27-day solar rotation, the semi-annual term and the
   ground-track repeat all come back empty, at the derived period **and** at
   the published one.

2. **A model fitted on the first half of 2023 does reduce the error on the
   second half — and the registered controls say the reduction is not
   structure.** Pooled, the median along-track error falls from **28.9 to
   14.6 km at +14 d** and from **119.3 to 38.9 km at +30 d**. But the
   registered placebo, with every covariate shifted 180 days into the past,
   **also gains** (6.96 km at +14 d, lower bound 5.49 > 0), which fires gate
   **G5**; and on intervals containing **no operator manoeuvre** the same
   correction is **worse than plain SGP4** at +14 d (−1.44 km, upper bound
   −1.08), which fires gate **G6**.

**Registered verdict: the two pass-screen clauses are satisfied and the
structure claim FAILS anyway**, because the registration says in §5.4 that a
placebo which gains fails the claim *regardless of the real arm's number*. The
screen and the control disagree, the control was written down first, and it
wins.

**What is actually there, and it is worth having:** a per-object, per-horizon
**bias**. A post-registration control that may learn nothing but the training
median offset — no covariate at all — recovers **5.1 km of the 14.3 km gain at
+14 d and 51.8 km of the 80.4 km at +30 d**. SGP4 run from this archive is
systematically late, per object, by an amount the past predicts. That is a
correction, and it is not a rhythm.

---

## 1. The spectral test, reported before the fit — as registered

`tools/residual_forecast.py spectra` was run and its JSON written **before
`fit` had ever been executed**, so that the periodicity claim stands on its own.

### 1.1 Nothing cleared the floor

| | series tested | points | lines above the global floor |
|---|---|---:|---:|
| Sentinel-1A | +7 d, +14 d, +30 d, linear coefficient, quadratic coefficient | 332 | **0** |
| Sentinel-3A | same five | 332 | **0** |
| Sentinel-3B | same five | 315 | **0** |

The floor is the 95th percentile of the **maximum** power over the scanned band
across **200 phase-scrambled surrogates** (seed 20260922). Phase scrambling
keeps each series' own amplitude spectrum and therefore its autocorrelation, so
this is a floor against **red** noise. `tests/test_residual_forecast.py` drives
the failure it exists to prevent: on a pure AR(1) series with no periodicity in
it, the registered floor calls nothing, while a white-noise floor built on the
same series **does** call a line.

### 1.2 The named bands, with the numbers rather than a verdict

Power at the band peak, as a multiple of that series' global floor. Above 1.00
would be a line; nothing is.

| Series | solar rotation 27.28 d | semi-annual 182.6 d | derived ground-track repeat | 14 d orbit-control |
|---|---:|---:|---:|---:|
| 1A +7 d | 0.62 | 0.06 | 0.62 (27 d) | 0.18 |
| 1A +14 d | 0.80 | 0.16 | 0.80 (27 d) | 0.04 |
| 1A +30 d | 0.67 | 0.20 | 0.67 (27 d) | 0.05 |
| 1A quadratic | 0.66 | 0.23 | 0.66 (27 d) | 0.08 |
| 3A +30 d | 0.27 | 0.30 | 0.10 (15 d) | 0.06 |
| 3A quadratic | 0.52 | **0.64** | 0.24 (15 d) | 0.04 |
| 3B +14 d | **0.78** | 0.20 | 0.11 (15 d) | 0.15 |
| 3B +30 d | 0.58 | **0.78** | 0.11 (15 d) | 0.20 |
| 3B quadratic | 0.43 | **0.76** | 0.02 (15 d) | 0.05 |
| 3B linear | **1.00** | 0.02 | 0.17 (15 d) | 0.28 |

The single largest value in the study is Sentinel-3B's linear coefficient at the
solar-rotation band: power 29.86 against a floor of 29.91. **Level with the
floor, and the floor is the threshold.** No line is declared, and none is
implied.

### 1.3 The derived repeat period disagreed with the published one — reported as a disagreement

Registration §2.8 required the repeat period to be **derived** from the
archive's own measured mean motion rather than quoted, and required a
disagreement with the published mission cycle to be reported as one. It
disagreed on all three:

| | median mean motion, 2023 | derived repeat | published cycle |
|---|---:|---|---|
| Sentinel-1A | 14.59199 rev/day | **27 d / 394 rev** (residual 0.016 rev) | 12 d / 175 rev (n = 14.58333) |
| Sentinel-3A | 14.26737 rev/day | **15 d / 214 rev** (residual 0.011 rev) | 27 d / 385 rev (n = 14.25926) |
| Sentinel-3B | 14.26737 rev/day | **15 d / 214 rev** (residual 0.010 rev) | 27 d / 385 rev |

**The reason, derived rather than guessed:** the element set's `MEAN_MOTION` is
a Brouwer–Kozai *mean* element, while a ground-track repeat cycle is defined on
the **nodal (draconic) rate relative to the rotating Earth**. The two differ by
the secular J2 rates of the argument of perigee and the mean anomaly, which at
these altitudes is of order 10⁻² rev/day — and the gap here is 0.0087 rev/day
for Sentinel-1A and 0.0081 for Sentinel-3. That is enough to push the
0.02-revolution tolerance onto a different integer. **The registered derivation
is therefore measuring the wrong flavour of mean motion for this purpose.** It
is reported, not repaired: the registration was committed first and the tool is
not edited after a number exists.

**What that did to the disentangling plan, and why it did not matter.**
Registration §2.8 warned that Sentinel-3's published 27-day repeat is
inseparable from the 27.27-day solar rotation at this frequency resolution, and
named Sentinel-1A — published repeat 12 days — as the object that could
separate them. The derived periods invert that: Sentinel-1A's derived repeat is
**27 days**, so Sentinel-1A is now the confounded one, and Sentinel-3's derived
15 days is clear of the Sun. The confound did not have to be resolved, because
**no line was found at any of these periods on any object.**

### 1.4 A post-registration diagnostic: the published periods are empty too

Labelled post-registration, because the registration tested the derived period.
Re-reading each periodogram at the **published** repeat cycle:

| | published period | peak found | power | floor | above? |
|---|---:|---:|---:|---:|---|
| 1A +7 / +14 / +30 d | 12 d | 11.90 / 11.82 / 11.82 d | 2.35 / 3.01 / 2.79 | 12.10 / 13.60 / 15.60 | no |
| 3A +7 / +14 / +30 d | 27 d | 26.78 d | 4.41 / 9.80 / 10.72 | 34.60 / 52.60 / 39.29 | no |
| 3B +7 / +14 / +30 d | 27 d | 27.22 / 26.79 / 26.79 d | 16.10 / 28.26 / 14.36 | 24.17 / 36.18 / 24.86 | no |

Strictly this adds nothing — no frequency anywhere in the 2–200 d band cleared
the floor, and 12 d and 27 d are inside that band — but the numbers are printed
so that nobody has to take the coverage argument on trust.

### 1.5 What §1 means for "the corrections are structured"

**The periodic half of the hypothesis is falsified on these three objects.**
Not "not found": tested, with a floor that survives red noise, on five
different expressions of the residual including the quadratic coefficient that
§2.1 of the registration derives to *be* the drag-rate error, and nothing
cleared the floor. Two hypotheses were ruled untestable in advance and remain
so (the annual term, unidentifiable in one year; the diurnal term, aliased by
daily sampling and frozen by sun-synchronous design), and the rest were tested
and came back empty.

This does not say the physics is absent from the world. It says that at the
amplitude these three well-tracked spacecraft carry, against the noise their own
element sets carry, a one-year daily series does not show it.

---

## 2. The forecast

### 2.1 Arm A — all intervals, the pass-screen arm

Three objects, 445 test rows per horizon (152 + 152 + 141), origins in
2023-07-01 … 2023-12-01, model fitted on 2023-01-01 … 2023-06-01 with a 30-day
embargo between them. Medians in kilometres; intervals are the moving-block
bootstrap over origins (block 30 d, 2,000 resamples) with the registered
object-clustered bootstrap beside it.

| Horizon | plain SGP4 | corrected | gain | gain % | block 95% | object-clustered 95% |
|---|---:|---:|---:|---:|---|---|
| +1 d | 3.574 | 1.955 | 1.619 | 45.3% | [1.315, 1.981] | [1.436, 2.209] |
| +2 d | 3.924 | 2.283 | 1.641 | 41.8% | [1.207, 2.337] | [1.238, 2.138] |
| +3 d | 4.296 | 2.676 | 1.620 | 37.7% | [1.097, 2.223] | [1.274, 2.369] |
| +5 d | 5.955 | 4.086 | 1.870 | 31.4% | [1.277, 2.624] | [−0.059, 4.477] |
| **+7 d** | **7.573** | **6.161** | **1.413** | **18.7%** | **[0.644, 2.976]** | [−2.761, 9.407] |
| +10 d | 14.765 | 11.213 | 3.551 | 24.1% | [1.477, 6.986] | [−3.975, 10.816] |
| **+14 d** | **28.875** | **14.591** | **14.284** | **49.5%** | **[11.653, 19.256]** | [2.243, 25.312] |
| +21 d | 61.514 | 23.000 | 38.514 | 62.6% | [33.293, 49.220] | [20.112, 60.754] |
| **+30 d** | **119.323** | **38.923** | **80.399** | **67.4%** | **[68.972, 99.640]** | [56.497, 113.484] |

**The object-clustered interval rests on three clusters and is not a 95%
interval in any meaningful sense** — three objects admit ten distinct resample
multisets — exactly as the registration recorded in advance. It is printed
because the registration required it, and it is not the basis of any statement.

**The pooled median hides a reversal, and the reversal matters more than the
pooled number.** Per object:

| | +7 d plain → corrected | +14 d | +30 d |
|---|---|---|---|
| Sentinel-1A | 13.311 → 3.904 (**+9.407**) | 36.501 → 11.190 (**+25.312**) | 148.604 → 35.120 (**+113.484**) |
| Sentinel-3A | 4.686 → 6.720 (**−2.034**) | 18.518 → 16.275 (+2.243) | 98.472 → 41.975 (+56.497) |
| Sentinel-3B | 5.042 → 7.803 (**−2.761**) | 21.947 → 17.445 (+4.502) | 101.696 → 41.558 (+60.138) |

**At +7 d two of the three spacecraft are made worse by the correction**, by
43% and 55% of their own plain error, and the pooled gain of +1.41 km is
Sentinel-1A carrying the other two. The registered non-inferiority clause is
pooled and it passes; per object it would fail at +7 d on two of three. Both
facts are printed and the registered one is not quietly replaced.

### 2.2 The intercept-only control — post-registration, and it is the one that explains the result

A model allowed to learn **the training median offset at that horizon and
nothing else**: no covariate, no Fourier term, no index. Same split, same
embargo, same bootstrap.

| Horizon | full model gain | intercept-only gain | attributable to covariates |
|---|---:|---:|---:|
| +7 d | 1.413 | **−0.107** [−0.852, 1.121] | 1.520 |
| +14 d | 14.284 | **5.134** [3.456, 10.999] | 9.150 |
| +30 d | 80.399 | **51.817** [37.198, 71.748] | 28.582 |

Per object at +30 d the split is starker: Sentinel-3A gains 56.497 km with the
full model and **55.683 km with no covariates at all**; Sentinel-3B, 60.138
against **56.255**. **On the two Sentinel-3 spacecraft, essentially the whole
+30 d gain is the removal of a bias.** Only Sentinel-1A shows a large covariate
increment (113.484 against 28.929), and Sentinel-1A is the object with no
manoeuvre notices and therefore no way to test whether that increment is the
atmosphere or its operator's schedule.

This control is **not registered**, was added after the placebo fired, and is
labelled as post-registration everywhere it appears. Without it the placebo
result (§2.4) is unreadable, because every arm — real, placebo and ablation —
carries an intercept, and the intercept alone gains.

### 2.3 Arm B — manoeuvre-free intervals, and gate G6

Intervals containing no IDS-reported manoeuvre, Sentinel-3A and 3B only;
Sentinel-1A carries no DORIS package and has no fetchable notice, so it has no
Arm B. As T16b measured, the manoeuvre-free subset thins with horizon and is
gone by +30 d.

| Horizon | n | plain | corrected | gain | block 95% | intercept-only gain |
|---|---:|---:|---:|---:|---|---:|
| +1 d | 271 | 3.327 | 1.815 | 1.512 | [1.095, 1.797] | 1.501 |
| +3 d | 229 | 2.712 | 1.823 | 0.889 | [0.621, 1.437] | 0.895 |
| +7 d | 165 | 2.618 | 1.966 | 0.651 | [0.463, 1.159] | 0.618 |
| +10 d | 121 | 3.097 | 2.164 | 0.933 | [0.089, 1.262] | 0.763 |
| **+14 d** | **66** | **3.598** | **5.037** | **−1.440** | **[−1.735, −1.081]** | −0.475 |

**Two things at once.** The manoeuvre-free error is a different animal: at +14 d
it is 3.60 km against the as-flown 28.88 km, which is T16b's finding —
the operator's own burns are most of the error — measured again on a different
statistic. And **the correction that halves the as-flown error at +14 d makes
the manoeuvre-free error 40% worse**, with an interval entirely below zero.

The +14 d row rests on **66 test origins**, below the registered G2 minimum of
100; G2 as registered is evaluated on Arm A and did not fire there, and the
count is printed here so the row is read with it. At every horizon where Arm B
does gain, the intercept-only control gains the same amount to within a few
percent. **On intervals with no burn in them, the
covariates buy nothing at any horizon, and at +14 d the whole correction
reverses sign.** Gate **G6 fires**: the Arm A gain is the operator's schedule,
not forecasting, and under the registration's own interpretation rule it is a
pattern-of-life finding belonging beside T14 and must not be reported as a
forecasting gain. It is not reported as one here.

### 2.4 The placebos, and gate G5

**P1**, every covariate taken from 180 days earlier:

| Horizon | plain | corrected | gain | block 95% |
|---|---:|---:|---:|---|
| +7 d | 7.573 | 8.129 | −0.555 | [−1.361, 0.605] |
| **+14 d** | 28.875 | 21.918 | **+6.958** | **[5.488, 12.929]** |
| +30 d | 119.323 | 103.857 | +15.466 | [−2.512, 27.173] |

**The placebo gains at +14 d with a lower bound of 5.49 km. Gate G5 fires, and
the registration says the structure claim fails regardless of the real arm's
number. It does.**

**Why it gains, and this is a defect in the registered control rather than a
mystery.** The placebo shares its intercept with the real arm, and the
intercept alone gains 5.13 km at +14 d (§2.2). The placebo's 6.96 km is that
5.13 km plus 1.82 km — while the aligned model's increment over the same
intercept is 9.15 km. At +30 d the placebo does **worse** than the
intercept-only control (15.47 against 51.82), i.e. the misaligned covariates
actively destroy part of the bias correction. **The registered placebo as
written cannot discriminate**, because it was specified against the whole
model rather than against the model's own intercept. The fire is reported as a
fire; the reading is given beside it; the registration is not edited.

**P2**, only the space-weather and Fourier covariates shifted, object state
left aligned: +14 d gain 13.088 [11.088, 19.900], +30 d 73.911 [58.619,
93.921] — within a kilometre or two of the full model at +14 d and 6.5 km below
it at +30 d. **Misaligning the space weather and the Fourier terms costs the
model almost nothing.** That is the same conclusion §1 reached spectrally,
reached again from the regression side.

**The NRLMSIS ablation.** Dropping the published density model and keeping the
raw indices changes the +14 d gain from 14.284 to 14.696 and the +30 d gain
from 80.399 to 80.825 — **the density model buys nothing over F10.7 and ap
here**, which is what one would expect of a covariate that is itself a smooth
function of F10.7 and ap.

### 2.5 The catalogue arm — the general-catalogue version, and it is worse than plain SGP4 everywhere

The residual against the **next element set**, needing no truth. Registered
rule applied: **5,535 payloads** carry at least 600 element sets in 2023, of
which **5,066** also sit in the registered mean-motion band; every 17th was
taken for 298 objects, and **69 of those cleared the 80% instant-coverage
bar**. The rest were dropped by the registered rule and not by a choice made
afterwards.

| Horizon | plain | corrected | gain | gain % | object-clustered 95% (68 clusters) |
|---|---:|---:|---:|---:|---|
| +1 d | 2.598 | 3.378 | −0.780 | −30.0% | [−1.252, −0.377] |
| +7 d | 7.283 | 15.826 | −8.544 | −117.3% | [−23.417, −3.453] |
| +14 d | 28.382 | 64.996 | −36.614 | −129.0% | [−72.976, −18.761] |
| +30 d | 142.682 | 265.500 | −122.818 | −86.1% | [−256.190, −50.612] |

**On 68 ordinary LEO payloads the identical procedure is worse than plain SGP4
at every single horizon**, by 30% to 129%, with an object-clustered interval
that here rests on 68 clusters and means something. The transfer arm — fitted on
2023, evaluated on the same 69 objects through 2024 with no refitting — is worse
too, at every horizon (−26% at +1 d to −17% at +30 d). The catalogue placebo is
worse again.

**This arm is catalogue self-consistency and not truth**: the later element set
is the archive's own estimate, and nothing here says which side is closer to
reality. But the sign is unambiguous, and it is the arm that speaks for the
catalogue rather than for three calibration spacecraft. A candidate mechanism,
offered as an interpretation and not as a measurement: these objects manoeuvre
often and irregularly, so the training-half bias is not the test-half bias, and
extrapolating a fitted offset is worse than extrapolating none.

---

## 3. Screens and gates

### 3.1 The registered pass screen

| Clause | Registered bar | Measured | Verdict |
|---|---|---|---|
| 1 — gain at +14 d | lower bound > 0 | block [11.653, 19.256]; object-clustered [2.243, 25.312] | **satisfied**, both bootstraps |
| 2 — non-inferiority at every horizon | lower bound > −0.10 × median plain, all nine horizons | no horizon fails, pooled | **satisfied** |
| bootstrap disagreement rule | if they disagree, NOT PASSED | they agree | not triggered |

**The screen reads PASS.** It is printed here, unedited, because it was
registered. It is not the verdict.

### 3.2 The gates

| Gate | Verdict |
|---|---|
| G1 truth-sample offset bar | did not fire — **0 of 8,811 comparisons dropped**, 0 propagator failures |
| G2 thin test rows | did not fire — every object-horizon row has ≥ 141 test origins |
| **G3 failed to fit** | **FIRED** — 4 rows (3A and 3B at +7 d and +10 d) where the training median absolute error rose |
| **G4 penalty at the grid edge** | **FIRED** — 15 of 27 object-horizon fits selected λ = 1000, the top of the registered grid |
| **G5 placebo gains** | **FIRED** — §2.4. Under the registration this fails the structure claim |
| **G6 gain is schedule** | **FIRED** — Arm A gains at +14 d, Arm B does not (§2.3) |

**G3's reason is worth stating**, because it is a specification mismatch and not
a numerical accident: the fit minimises squared error while the estimand is a
**median** absolute error, and on a skewed residual distribution subtracting the
least-squares mean can raise the median. Four rows show it directly. The grid
was not extended and the loss was not changed.

**G4 is corroboration of the null, read the right way round.** λ = 1000 is the
most shrinkage the registered grid allows, and the inner cross-validation —
which never saw a test row — chose it in **15 of 27** fits. The selection
procedure is asking for the covariates to be turned off. The three fits that
chose little shrinkage are Sentinel-1A at +30 d (λ = 0.1), whose standardised
coefficients then reach ±57 on `bstar` and `ndot` — two nearly collinear
columns with large opposing weights, the signature of a fit held together by
cancellation.

---

## 4. Deviations from the registration

1. **A post-registration intercept-only control was added** (§2.2), after the
   placebo fired, because without it the placebo result cannot be read: every
   arm carries an intercept and the intercept alone gains. Labelled
   post-registration everywhere.
2. **A post-registration spectral diagnostic at the published repeat periods**
   was added (§1.4) after the registered derivation disagreed with the
   published cycle.
3. **The inner cross-validation metric was under-specified.** The registration
   named the procedure (forward chaining, five folds, embargo) and the λ grid
   but not the metric. Median absolute error was used, matching the estimand.
   Recorded as an under-specification resolved at implementation, not as a
   choice made after seeing a result.
4. **The registered §6.1 test 2 described the wrong symptom.** It said a
   covariate built from the future target, forced past the guard, "produces a
   train/test gap that the split check flags". A covariate carrying the target
   leaks it on *both* sides of the split and shows **no gap at all** — it shows
   an implausible gain. The implemented check tests for either symptom and the
   test drives both; the registered wording is recorded here as wrong.
5. **An index-archive gap is dropped, not defaulted.** The GFZ file carries
   F10.7 = −1.0 on 2024-08-26 (a genuine one-day hole in the Penticton record).
   The parser refuses it as registered; the covariate builder now drops the
   affected *origin* rather than abandoning the whole object, which it did on
   the first run, taking the entire aligned catalogue arm with it. A robustness
   fix, no registered quantity changed, a test added for it.
6. **A degenerate covariate column takes the minimum-norm solution.** A column
   that is constant over an object's training rows makes the normal equations
   singular at zero penalty; the least-squares minimum-norm solution gives it a
   coefficient of zero. Stated rather than silently patched.
7. **The Starlink self-consistency arm was NOT RUN, and cannot be** with what is
   archived. T16a fetched 250 operator ephemeris files on a single day
   (2026-09-22); scoring a predicted file against a *later* file needs at least
   two fetch epochs separated in time, and only one exists. Starlink objects do
   enter the catalogue arm through the general-perturbation archive, which is a
   different and weaker thing, and is labelled as such.
8. **The transfer arm ran on the catalogue arm only**, as the registration
   said it would: the precise-orbit products cover 2023 alone and a second year
   was not fetched.

The registration file was not edited after it was committed.

---

## 5. What these numbers may not be used for

- **Three sun-synchronous, cooperative, exceptionally well-tracked spacecraft
  are not a census**, and T16b already recorded that their forward-error curve
  is a best case. The catalogue arm's 68 objects are closer to ordinary and they
  say the correction is harmful.
- **The Arm A gain may not be called a forecasting improvement.** G6 fired. On
  intervals with no burn it is absent at every horizon and negative at +14 d.
- **The bias correction may not be called structure.** It is a per-object,
  per-horizon offset learned from the past. It has no period, no covariate and
  no mechanism attached to it here.
- **The catalogue arm is self-consistency, not accuracy.** It cannot rank the
  two sides against reality.
- **No claim is made at GEO, beyond +30 d, or for objects sparser than the
  registered coverage rule.**
- Every threshold here — the 10% non-inferiority margin, the 95th-percentile
  surrogate floors, the ±6 h pairing window, the 0.02-revolution repeat
  tolerance, the 80% coverage bar, the 300-object cap — is a **chosen screen**,
  not a physical law.

---

## 6. Unproven items, in those words

- **The Starlink self-consistency arm is UNRUN**, and with one fetch epoch in
  the archive it is **unrunnable** today. Two fetches separated by at least a
  day are required and were not made.
- **Whether Sentinel-1A's large covariate increment is atmosphere or schedule is
  UNMEASURED.** Sentinel-1A has no fetchable manoeuvre notice, so it has no
  Arm B, and it is the object carrying most of the pooled gain.
- **The same-object-different-year transfer on TRUTH is UNPROVEN.** It ran on the
  catalogue arm only; a second year of precise orbits was not fetched.
- **Whether a periodic term exists below the amplitude this measurement can see
  is UNMEASURED.** The floor is the floor; a null above it says nothing about
  what is beneath it.
- **The diurnal hypothesis is UNTESTED and was ruled untestable in advance** on
  this object set — aliased by daily sampling and frozen by sun-synchronous
  design.
- **The annual term is UNIDENTIFIABLE in one year** and was excluded in advance.
- **No cause is established for the catalogue arm's harm.** The mechanism
  offered in §2.5 is an interpretation and was not tested.

---

## 7. What this changes for the programme

1. **T18's E2 now has its classical baseline, and the bar is specific.** A
   learned model must beat, on Arm A, a gain of **14.28 km at +14 d and
   80.40 km at +30 d** — and it must beat the **intercept-only** control's
   5.13 and 51.82 km, because anything up to that line is a bias and not a
   model. More importantly it must survive the same two controls: a learned
   model that gains on as-flown intervals and loses on manoeuvre-free ones has
   learned the operator's calendar, and T18 §3.4 already says that finding
   belongs to E3.
2. **A cheap, honest correction exists and is worth registering on its own**: a
   per-object, per-horizon median-offset correction, fitted on past data, cuts
   the +30 d as-flown along-track median by 43% pooled and by 56% on both
   Sentinel-3 spacecraft. It carries no mechanism, no covariate and no periodic
   claim, and on the catalogue arm it is **harmful** — so its registration would
   have to name the object class it applies to and measure the boundary.
3. **The site's LEO ribbon question is untouched by this.** T16b's
   recommendation to redraw it from the measured quantiles still stands; nothing
   here licenses a narrower ribbon.
4. **The operator's intuition is answered, and the answer has a number.** The
   corrections do not repeat. What they do is *lean* — one way, per object, by
   an amount the past predicts — and the rest of what looked like structure was
   a spacecraft operator keeping a schedule.

---

## 8. Method notes that carry the numbers

- **Propagator**: `satellite.js` through T16b's `tools/truthset_sgp4.mjs`,
  unmodified; the same SGP4 the site's globe runs.
- **Frame chain**: T16b's, unmodified — TEME → PEF by GMST at UT1 → ITRF by
  polar motion, IERS `finals2000A.all`. For the catalogue arm neither rotation
  is applied, and that is a property of a difference rather than an
  approximation: both sides are propagated to the same instant, so the
  Earth-rotation angle is common to them and to the frame the difference is
  resolved in, and cancels exactly.
- **Catalogue reference velocity**: a centred finite difference over 60 s. The
  chord of a centred difference is parallel to the tangent to first order.
- **Space weather**: GFZ Helmholtz Centre for Geosciences,
  `Kp_ap_Ap_SN_F107_since_1932.txt`, SHA-256
  `acfc6a5dfb24f15b069d4674ee608370394843447f9392f9c9d795c0d0ac3e9a`,
  5,504,674 bytes, fetched once from the VPS; 28,420 usable UT days of 34,598
  rows read, 6,178 dropped for a missing value in a field this track uses.
  Cite: Matzka, Stolle, Yamazaki, Bronkalla & Morschhauser (2021), *Space
  Weather*, doi:10.1029/2020SW002641; data publication doi:10.5880/Kp.0001;
  F10.7 from the Dominion Radio Astrophysical Observatory per Tapping (2013),
  *Space Weather* 11, 394. **CelesTrak was deliberately not used**: the
  estate's routing rule forbids any CelesTrak request from the analysis host,
  and one archive file from a source with no such constraint is cheaper and
  safer than spending the VPS lane's budget.
- **Density model**: NRLMSIS 2.0 as published, through `pymsis` 0.12.0, already
  present on the host; no dependency was installed for this track. **NRLMSIS
  expects an 81-day average centred on the day of interest; a centred average is
  half future and is not knowable at the origin, so the trailing 81-day mean is
  supplied instead.** That biases the absolute density the model returns and
  does not bias the covariate's causality, which is the property this track
  needs. Stated here and in the results JSON rather than hidden in a keyword.
- **Periodogram**: classical normalised Lomb–Scargle (Lomb 1976, *Ap&SS* 39,
  447; Scargle 1982, *ApJ* 263, 835), implemented directly — the host carries
  NumPy and no SciPy, and no dependency was added for one transform.
- **Reproduction**:
  `python3 tools/residual_forecast.py residuals`, then `spectra`, then
  `fit --catalogue`; `python3 -m unittest tests.test_residual_forecast`
  (28 tests, all pass). Tool SHA-256 hashes, seeds and every screen value are in
  the results JSON.
