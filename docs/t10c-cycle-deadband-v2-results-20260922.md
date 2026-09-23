# The corrected floor, the derived multiple, and where the period went

**Registration:** `docs/t10c-cycle-deadband-v2-preregistration-20260922.md`,
committed alone at `cd2fc78` before any number below existed.
**Parent:** `docs/t10c-cycle-deadband-preregistration-20260922.md` (`0a49ba5`),
results `docs/t10c-cycle-deadband-results-20260922.md`.
**Instrument:** `tools/t10c_v2_deadband_floor.py` (`8105790`, published-file
thinning `3b70dfd`), 23 offline proofs in `tests/test_orbit_t10c_v2_floor.py`.
The parent's estimator is imported by reference and a test asserts the identity
of every imported function.
**Artifacts:** `docs/t10c-cycle-deadband-v2-20260922.jsonl`,
`docs/t10c-cycle-deadband-v2-20260922-receipt.json`.
**Compute:** CPU only on `pc`, 714 s wall / 668 s CPU / 1.38 GB peak RSS. No
GPU arm, so no `gpu-consumers.json` row is owed.
**Determinism, measured rather than assumed:** this instrument was run twice
end to end, the second time after changing only how much of the cycle ledger is
written to the published file. **Every statistical block of the two receipts is
byte-identical** — the census, both floors, the surrogate, the bootstraps, the
slopes, the sweeps and the verdict — leaving only the timestamp, the wall/CPU/RSS
and the sampling note to differ. Every seed in this track is fixed and the two
runs prove it.

---

## The verdict, stated first — and the agreement did not survive the repair

**Registered verdict: MEASURED AND CLAIMABLE; THE INTERVAL EXCLUDES T3's
±0.0208 deg.**

> The cycle-resolved flown-excursion box on T3's own 14.00-day line carriers is
> **0.02633 deg, bootstrap 95% interval [0.02572, 0.02667]**, over **41,436
> admitted cycles on all 207 GEO carriers with archived history**, measured by a
> registered estimator whose floor is derived from the measured element noise.
> **It excludes T3's independently derived ±0.0208 deg.** The measurement is
> CLAIMABLE and the disagreement is reported, not explained.
>
> **This registration was written after the first read of this quantity.** The
> agreement with T3 would have been an agreement between two independent
> instruments; the disagreement is likewise between two independent instruments.
> Neither is an independent analysis of these data, because this run shares its
> data, population and instrument with the first.

**And that is the point of the exercise.** The first run reported, as
UNREGISTERED and NOT CLAIMED, a box of `0.0203 [0.0188, 0.0212]` whose interval
contained T3's `0.0208`. That number came from dropping the floor screen
entirely. **This run reproduces it exactly** — the unscreened G3–G5 population
gives `0.020301 [0.018754, 0.021190]` on the same 207 carriers, to every digit
the first run published — and then shows what a *derived* floor does to it:
screening at a 1%-per-cycle false-admission rate admits 41,436 of 80,677 cycles
and raises the median to `0.02633`. **The floor screen selects the larger boxes,
because that is what a floor screen is for, and the pleasing agreement was a
property of the unscreened population.**

**The estimand is flown excursion, not licensed box.** An operator holding a
`±0.05 deg` licence inside `±0.01 deg` of actual motion is measured at `0.01`.
Every number in this document is a flown excursion.

**One registered check failed, and the registration said what to do.** D5 — the
corrected surrogate against its own derived expectation — came out at
`rho_5 = 0.632` against a band of `[0.70, 1.40]`. **The corrected surrogate is
reported as still not a noise floor**, in those words; the failure is in the
over-fitting direction the registration named, and the derived floor of §3,
which does not depend on the surrogate at all, remains the screen. §3 below.

**The period discrepancy is settled, and it is the strongest result here.**
Raising the prominence threshold moves the measured cycle monotonically from
10.98 d to 19.02 d and the box-to-prediction ratio monotonically from 3.22 to
1.29, and merging candidate splits moves all four registered indicators in the
registered directions. **The period discrepancy is cycle splitting by the
prominence filter, measured.** §5.

---

## 1. Census, and the floor that replaced the envelope

| | Value |
| --- | ---: |
| T3 line carriers reproduced from the committed artifact | **214** (208 GEO, 6 LEO) — asserted, S2 |
| GEO carriers with archived history | **208** |
| Cycles found | 184,591 |
| ... flagged `G3-too-few-samples` | 95,110 |
| ... flagged `G4-too-short` | 78,210 |
| Cycles passing G3–G5 (the population the floor screens) | **80,677** |
| ... flagged `G6v2-below-derived-floor` | 105,600 of all found |
| Cycles **admitted** | **41,436**, on 207 objects, all 207 with ≥ 3 cycles |
| Expected noise admitted at `alpha = 0.01` (eq. 27) | 806.8, a contamination of **1.95%** against a 10% bar |

**`sigma_lambda` re-measured at `0.0066540706667427025 deg`** by the
second-difference MAD on mean longitude over 1,858 segments — **identical to the
first run's published value in every digit**, so registration §7.3's D2 defect
rule does not fire. The drift-rate sigma is unchanged too: propagated
`1.598e-4 deg/day`, measured `1.091e-3`, the larger used, a ratio of 6.83.

**The derived floor.** The population's **modal** cycle sample count is `m* = 5`
and `med(W_5) = 2.2539`, so

    floor = 0.5 sigma_lambda med(W_5) = 0.5 x 0.0066541 x 2.2539
          = 0.0074988 deg.

**T3's `0.0208 deg` sits at 2.77 times that floor**, which is D2v2(a) and is
decidable before a single cycle is admitted. The screen's equivalent multiple at
`m = 5` and `alpha = 0.01` is `c = 2.033`, so T3's box passes it with room.

**A difference from the first run's derived floor, stated because the two
numbers are both called "the derived floor".** The first run quoted `0.010833`
from the **median** sample count (12) times the **mean** of the range statistic
(3.2562). This registration specifies the **modal** sample count and the
**median** of the range statistic, because a median floor is what a
false-admission rate is built on. Same construction, two conventions,
`0.0075` against `0.0108`; both are reported and neither is edited.

**Why the first registration's `3 x` could not work, measured rather than
argued.** `3 x med(W_12) = 9.60`, so that screen demanded a 9.6-sigma excursion
of the range statistic — a tail of order `10^-9`. The error was applying a
"3 sigma" intuition to a statistic whose mean is already `3.26 sigma` at
`m = 12`. The run asserts the 9.60 as a tripwire.

---

## 2. The measurement, and what it is not

| | Admitted (G6v2 at `alpha = 0.01`) | Unscreened (G3–G5 only) |
| --- | ---: | ---: |
| Cycles | 41,436 | 80,677 |
| Carriers with ≥ 3 cycles | 207 | 207 |
| Per-cycle median box | 0.02686 deg | 0.01827 deg |
| **Per-object median box** | **0.02633 [0.02572, 0.02667]** | **0.02030 [0.01875, 0.02119]** |
| Within a factor of two of ±0.0208 | **199 of 207** | 191 of 207 |
| Per-object median cycle | 11.67 d | 10.42 d |
| Per-object median `R_pos/R_pred` | 2.97 | 2.39 |

**The statistical interval is not the uncertainty.** The bootstrap interval is
±2% wide. The two registered knobs move the answer much further:

* **the false-admission rate** `alpha` — `0.05` gives `0.02468
  [0.02415, 0.02518]`, `0.01` gives `0.02633`, `0.001` gives `0.02830
  [0.02790, 0.02878]`;
* **the prominence threshold** `k` — from `0.02586` at `k = 3` to `0.03316` at
  `k = 20` (§5).

**So the honest statement of the flown excursion on these carriers is
`0.025 to 0.033 deg`, and every value in that range lies above T3's
`0.0208 deg`.** The registered primary is `0.02633 [0.02572, 0.02667]` and it is
reported as the registered primary; the systematic range is reported beside it
and must travel with it.

Registration §3.3 required this to be said in the first paragraph if the answer
moved materially across the `alpha` range. It moves by ±7% across a factor of 50
in `alpha`, monotonically and in the direction a selection effect predicts — a
stricter floor keeps larger boxes. **The screen is doing work, and the direction
of that work is known.** What does not move is the comparison: no value of
`alpha` in the registered range brings the interval down onto `0.0208`.

---

## 3. D5 — the corrected surrogate, and why it still fails

The corrected surrogate does what the registration asked: it fits the derived
cycle shape inside each run (a parabola in longitude, a straight ramp in drift
rate) and permutes the residuals, so the box's amplitude is removed rather than
shuffled. Test 1 asserts the repair offline — on a synthetic sawtooth with a
planted `sigma`, the fitted residuals return that `sigma` to within 15% while the
first registration's residuals-about-the-centre are more than three times larger.

On the archive it returns **164,029 cycles**, a modal sample count of 9, and a
median `R_pos` at that count of **0.006116 deg** against the derived expectation
`0.5 sigma_lambda med(W_9) = 0.009682`. **`rho_5 = 0.632`, below the registered
`[0.70, 1.40]` band, so D5 FAILS in the over-fitting direction** — the direction
the registration named in advance.

**Diagnosis, offered as a diagnosis and not as a repair.** A quadratic fitted
inside a run of 5 to 10 samples has 3 free parameters, so it absorbs a real
fraction of the noise even after the degrees-of-freedom correction the instrument
applies; and the surrogate's runs are short (modal 9 against the real
population's longer runs), which is where that shrinkage bites hardest. The
consequence is that the surrogate **understates** the floor, which would make the
screen too permissive were the surrogate the screen. **It is not the screen.**
The screen is the derived quantile of §1, which is built from `sigma_lambda` and
the range statistic and never touches the surrogate. The registration fixed that
fallback in advance precisely so this failure could not become a choice made
afterwards.

**What is owed and not done here:** a surrogate whose residual scale is unbiased
at small `m`. A leave-one-out or a jackknifed residual would be the obvious
candidates, and neither is registered, so neither is run.

---

## 4. The controls

| Control | Slope | 95% interval | Registered prediction | Outcome |
| --- | ---: | --- | ---: | --- |
| Measured `A_cycle` on derived `A(lambda)` | **0.933** | **[0.714, 1.069]** | 1 | **PASSES** |
| `R_rate` on `R_pos` (D4) | 0.235 | [0.195, 0.369] | 1 | **FAILS**, as registered in advance |
| D4 on the merge arm | **0.420** | [0.264, 0.488] | moves toward 1 | **MOVES, as predicted** |

**The free-drift control passes, and tighter than before.** T10c's registered
version of this control returned INPUT NOT VERIFIED at segment scale, recovering
about 1% of the derived triaxial acceleration. The first cycle-scale run
returned `0.922 [0.320, 1.094]`. This run returns **`0.933 [0.714, 1.069]` over
207 objects** — the same slope with an interval three times narrower, because
the corrected floor admits fifty-seven times as many cycles. The parent's
diagnosis — a timescale, not a physics failure — is now confirmed by a registered
estimator on a population that is not a tail.

**D4 fails, and the registration predicted that it would, and said what would
follow.** §5 of the registration wrote: *"D4 will fail again, at a slope well
below 1, because the splitting mechanism of §6 corrupts both the ramp amplitude
and the fitted acceleration that eq. (21) is built from ... if splitting is the
cause, the merge arm's D4 slope must move toward 1."* It fails at `0.235` and the
merge arm moves it to `0.420`. **The prediction was written down before the
number existed and it held.** The positional estimator is reported alone and this
disagreement is stated in the same sentence as the box: `0.02633 [0.02572,
0.02667] deg`, with the rate read through mean motion disagreeing with the
positional read through mean longitude by a factor of about four.

---

## 5. The period discrepancy — three mechanisms, and the data picks one

The registration derived three mechanisms to separating triples of (period, box,
`R_pos/R_pred`), as fractions of the true one-burn cycle:

| | apparent period | apparent box | `R_pos/R_pred` |
| --- | ---: | ---: | ---: |
| **M1** one burn per cycle, correctly segmented | `T*` | `R*` | **1** |
| **M2** a clean burn pair a half-cycle apart | `0.5 T*` | `0.25 R*` | **1** |
| **M3** cycle splitting by the prominence filter | `< T*` | `~ R*` | **> 1**, exactly **4** at a vertex split |
| **measured (registered primary)** | **0.83 x 14.00 d** | **1.27 x 0.0208** | **2.97** |

**M2 is refuted by algebra, and the registration wrote the prediction down
first.** A pair halves the cycle **and** quarters the box, because
`A (T*/2)^2/16 = R*/4`, so **`R = A T^2/16` is invariant under pairing and a
clean pair cannot move the ratio off 1 whatever it does to the period.** Test 7
asserts it on synthetic cycles: half the period, a quarter of the box, ratio 1
within 2%. A measured ratio of 2.97 refutes clean pairing as the explanation.

**That is the same conclusion the harmonic-mechanism track reached in this
channel by measurement**, and the agreement is registered rather than noticed
afterwards: `docs/harmonic-mechanism-results-20260922.md` scanned every two-burn
split reset at every separation and impulse ratio — 0 of 5,940 cells reproduce
the carriers' `(pi, 0, pi, 0)` signature — and its eight measured two-burn arms
all invert the third harmonic along with the second. Its symmetric case returns
`F_1 = 0.50` with the odd harmonics gone, which is (28) seen from the other side:
a clean pair is a one-burn sawtooth at half the period, so its fundamental moves
to `2/T*`. **Two independent routes exclude the same family in the east-west
channel.**

**M3 is confirmed, twice, in the registered directions.**

**The prominence sweep** (registration §6.5 predicted the period rises with `k`
and the ratio falls toward 1 under M3, and both are flat under M1 or M2):

| `k` | admitted cycles | box (deg) | period (d) | `R_pos/R_pred` |
| ---: | ---: | ---: | ---: | ---: |
| 3 | 38,053 | 0.02586 | 10.98 | 3.218 |
| **5 (primary)** | **41,436** | **0.02633** | **11.67** | **2.972** |
| 8 | 42,996 | 0.02699 | 12.37 | 2.459 |
| 12 | 41,119 | 0.02787 | 13.12 | 1.895 |
| 20 | 29,789 | 0.03316 | 19.02 | 1.291 |

**Monotone in both registered directions across a factor of 6.7 in `k`.** At
`k = 12` the measured cycle is 13.12 days against T3's 14.00 and the ratio has
fallen to 1.90; at `k = 20` the cycle overshoots to 19.02 days, which is what
over-merging looks like — a threshold high enough to absorb real burn resets as
well as noise reversals.

**The merge arm** (registration §6.4 required four indicators and all four are
reported whatever they show):

| Registered prediction | Unmerged | Merged (`rho = 0.5`) | Outcome |
| --- | ---: | ---: | --- |
| (a) median cycle rises toward 14.0 d | 11.67 | **12.01** | **yes** |
| (b) median box stays within 1.3x | 0.02633 | **0.02668** | **yes** (1.013x) |
| (c) median `R_pos/R_pred` falls toward 1 | 2.972 | **2.618** | **yes** |
| (d) D4 slope moves toward 1 | 0.235 | **0.420** | **yes** |

`rho = 0.25` and `rho = 0.75` are the registered sensitivities: at 0.25 the arm
barely fires (period 11.75 d, ratio 2.91); at 0.75 it merges harder (period
13.19 d, box 0.02805, ratio 2.03). The merge is not a blunt instrument — the
median run absorbs nothing, the mean absorbs 1.12 runs, and the maximum chain is
9.

**Registered reading, in the registered words: THE PERIOD DISCREPANCY IS CYCLE
SPLITTING BY THE PROMINENCE FILTER, MEASURED.** Merging candidate splits moves
the period from 11.67 to 12.01 days and the box-to-prediction ratio from 2.97 to
2.62, and the prominence sweep moves them from 10.98 d / 3.22 to 19.02 d / 1.29.

**What splitting does NOT explain.** The merge arm and the sweep both leave a
residual: at the registered primary the ratio is still 2.62 after merging, and
only at `k = 12`–`20` does it approach 1 — at which point the period has
overshot 14 days. **No single setting returns both a 14-day cycle and a ratio of
1 simultaneously.** The closest is `k = 12`: 13.12 days and 1.90. So splitting is
the mechanism and the mechanism is not fully removed by either arm, and the
remaining factor of about two in `R_pos/R_pred` is reported and not explained.

---

## 6. F2 — the never-manoeuvred arm, now on both populations

The registration owed the comparison on the unscreened population as well as the
screened one, which the first run left open.

| | Line carriers | Never-manoeuvred GEO passives |
| --- | ---: | ---: |
| Objects on the roster | 208 | 331 (**zero** carrying a detected event; S3 passed) |
| Objects forming cycles | 207 | 29 |
| **Admitted**: per-object median box | **0.02633 [0.02572, 0.02667]** | **0.17113 [0.16332, 0.18113]** |
| **Unscreened**: per-object median box | **0.02030 [0.01875, 0.02119]** | **0.17113 [0.15671, 0.18094]** |

**D3 passes on both populations and the intervals are disjoint by an order of
magnitude.** A passive object sitting near a stable longitude librates under the
same triaxial torque with no control loop at all and shows an excursion **6.5
times** the carriers'. Control tightens the box, the direction is the physical
one, and the conclusion no longer rests on both arms passing through the same
screen.

---

## 7. The carriers that are not east-west keepers, and the fuel figures

**17 of the 208 carriers sit at 5 degrees of inclination or more**, including
T3's top three named carriers — OPS 9437 (DSCS 2-7) at 15.88 deg, Gorizont 13 at
13.94, GSAT 1 at 9.09. Their median box is **0.04110 deg** against the
population's 0.02633: **1.6 times wider, and on the admitted population they are
now separable from the rest**, where the first run found them indistinguishable.
Whatever carries their 14-day line, this instrument measures a wider excursion
for it than for a routine east-west keeper, and that is reported rather than
resolved.

**Delta-v, for the commercial-civil catalogue only.** The line-carrier roster is
not the commercial-civil catalogue; it is T3's line sweep over the whole public
catalogue. Every carrier here carries **angles and times only**. **37** carriers
are also in `data/propulsion-catalog-v1.json`, and for those 37 — and only those
— the receipt carries `DV_cycle` and the annual budget. A test asserts that no
field of a cycle record can name a delta-v, a propellant mass, an Isp or a fuel
quantity, and the catalogue's `commercial-civil-only` policy is a stop rule the
run enforces. Those 37 show the same internal inconsistency §5 reports: measured
cycles of 10.0 to 15.1 days against the 16.8 to 28.3 days their own measured
boxes predict.

---

## 8. What is owed after this

1. **An unbiased surrogate at small `m`** (§3). D5 failed low; the fix is a
   residual scale that does not shrink with the fit, and it needs its own
   registration.
2. **The remaining factor of two in `R_pos/R_pred`.** Splitting is measured and
   removing it does not close the gap. No setting of either registered knob
   returns a 14-day cycle and a ratio of 1 at the same time.
3. **A blind measurement of this box.** Everything here is confirmatory on data
   already read once. The box is now a registered number produced by a derived
   floor; it is not an out-of-sample one.
4. **Per-object `sigma_lambda`.** One population figure makes the per-cycle
   screen slightly wrong in both directions, object by object. T5c owes the
   per-element covariances that would fix it.
5. **The dependence on `k`.** The box moves 28% across the registered prominence
   sweep. A segmentation rule whose threshold does not have to be chosen would be
   a better instrument, and this is not one.

---

## 9. Blind spots, from the registration and measured where possible

* **The estimand is flown excursion, not licensed box.** Restated wherever the
  box appears.
* **This is not a blind analysis**, and §0.3 of the registration says so at
  greater length than this document can.
* **The one-burn parabola is still the model.** The merge arm repairs a
  segmentation failure; it does not test whether the waveform is a one-sided
  parabolic cycle at all. The residual ratio of §5 is where that shows.
* **The line carriers are not a random sample of GEO.** They are the objects
  whose mean-motion periodogram carries a 14.00-day peak, which selects for
  regular, detectable manoeuvring; the bias runs toward tighter boxes.
* **The draconitic-year longitude oscillation is not subtracted.** It is slow
  against an 11-day cycle and enters as a baseline, but it is part of `R_pos`,
  and it is part of what the fitted parabola absorbs into the surrogate's
  residuals — which pushes `rho_5` up, not down, so it is not the explanation for
  D5's failure.
* **One cycle of 184,591 had more samples than the range table covers** and was
  screened at the table's `m = 256` threshold, which is conservative.
* **The published JSONL is thinned** by systematic sampling — every 2nd admitted
  cycle of 41,436, every 29th rejected of 143,155, every 6th merged of 42,478,
  every 42nd surrogate of 164,029, and all 617 passive cycles — with the step for
  each arm recorded in the receipt. Every cycle is in every statistic above; only
  the file is thinned, and it is thinned to keep it comparable in size with the
  first run's artifact.
