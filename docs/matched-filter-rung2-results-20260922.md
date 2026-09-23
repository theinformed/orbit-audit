# T5a: the Rung-2 transfer test and the phase-coherence diagnostic — RESULTS

> **REGISTERED RUN. STILL NOT T5a.** Both measurements were fixed in writing
> before either produced a number, by
> `docs/matched-filter-rung2-preregistration-20260922.md`, committed **alone**
> at `3729b47` and amended **alone** at `03df5c8` while no number governed by
> the amendment existed. Nothing below is a T5a result: there is still no
> `docs/t5a-preregistration-<date>.md`, no p-value is published, no gate is
> evaluated, no object's status changes, and design section 10's scope fence is
> unchanged and binding.

Measured 2026-09-22 on `pc`, beside resident training and beside several other
sessions' work. Every quantity taken from a committed artifact carries an inline
`<!-- src: -->`; every quantity computed here carries `derivation:`. Thresholds
are **screens**, not laws. Blind spots were declared in the registration and are
restated where they bite.

Documents of record: `docs/matched-filter-design-20260922.md` (`e51bcce`), whose
section 5.3 fixed the Rung-2 screen before any measurement existed;
`docs/matched-filter-prototype-20260922.md` (`b2c7665`), whose Finding 1 this
work explains and whose Finding 2 it re-prices.

---

## 0. The findings, first, in the order a reader should take them

1. **THE TEMPLATE FAILED BECAUSE THE SECOND HARMONIC IS INVERTED.** On the 208
   east-west carriers' segments the harmonic-to-fundamental phase residual
   `psi_2 = theta_2 - 2 theta_1` is concentrated at **3.19 rad** -- `pi` to
   within 0.05 -- against the **0.04 rad** an ideal one-burn sawtooth returns
   through the identical code path. A harmonic that sits `pi` from the template's
   contributes a NEGATIVE term to the matched response while contributing its
   full positive share to the fitted norm. That is the `-2.715 dB` the prototype
   measured, mechanically explained (section 3.4). The third harmonic, by
   contrast, **does** track the sawtooth -- `psi_3` at 6.18 rad, i.e. `-0.10`,
   at 81% of the ceiling's concentration.

2. **THE COHERENCE TIMESCALE IS 568 DAYS AT A FIXED 14.00 d TEMPLATE AND
   UNBOUNDED ONCE EACH OBJECT GETS ITS OWN PERIOD.** On the 42 d ladder the
   carriers hold phase for **568 d -- about 41 cycles** -- against a passive-
   control floor of 117 d and a ceiling that does not decohere at all. Refining
   each object's fundamental removes the decay entirely (**> 1,008 d**, the full
   measured baseline) while leaving the floor arm at 122 d. The measured
   refinement spans **13.89 d to 14.10 d**, which is design 1.3(a)'s
   slot-dependent period prediction, so the 568 d is **period dispersion across
   the fleet, not phase noise** (section 3.3).

3. **THE RUNG-2 SCREEN FAILS, AND THE DECOMPOSITION SAYS RUNG 3 WOULD NOT FIX
   IT.** The held-out passive exceedance at the nominal 1% level is **9.658%**
   `[8.943%, 10.362%]` against the design'''s registered screen of
   **[0.5%, 2.0%]** -- outside by a factor of **4.83**. By the registered rule,
   **Rung 2 is not admissible and Rung 3 is selected**. But the calibration-half
   self-application this session registered and the design did not asks the
   question the screen cannot: applying the same class thresholds to the
   calibration half -- nothing held out -- gives **8.764%** `[7.525%, 10.130%]`.
   **The geometry class transfers; the null does not calibrate.** Holding out an
   object-level split costs 0.9 points of a 9.7-point failure, so the ~8,860
   GPU-hours a sweep that Rung 3 costs would be spent buying a per-object
   look-elsewhere factor that is not what is broken (section 2.3).

4. **A card-speed folklore, corrected.** One job per card, simultaneous,
   byte-identical program: card 0 **56.2 windows/s**, card 1 **58.1 windows/s**
   -- a **3.3%** difference, not the 2.1x or 3.47x that two earlier occasions
   recorded. The cards do differ in one static field nobody had queried -- card 0
   negotiates **PCIe 3.0 x4** against card 1'''s **PCIe 4.0 x16**, 8.0x in
   host-interface bandwidth -- and in this workload it costs 3.3%. The asymmetry
   the pilot and the prototype saw was concurrency (section 4).


## 1. What ran, and what it cost

Everything through `/home/sdegan/gpu-broker/gpu-run`, class `standard`,
`--estimate-mib 1800` against the prototype's measured peak of 1,601.3 MiB,
beside resident training and beside several other sessions' work.
`CUDA_VISIBLE_DEVICES` arrived as a GPU UUID and was never parsed as an integer.

| stage | windows | wall | grid | reduction | peak CuPy pool | card |
|---|---:|---:|---:|---:|---:|---|
| held-out audit, shard 0 | 53,477 | 1,910.9 s | 1,700.9 s | 124.7 s | 1,437.8 MiB | 1 |
| held-out audit, shard 1 | 53,464 | 1,918.0 s | 1,707.8 s | 125.2 s | 1,437.8 MiB | 1 |
| calibration control, shard 0 | 13,978 | 669.4 s | 603.5 s | 48.4 s | 1,233.0 MiB | 1 |
| calibration control, shard 1 | 14,032 | 673.7 s | 603.1 s | 51.6 s | 1,233.2 MiB | 1 |
| S-AR1 surrogates, shard 0 | 36,000 | 620.0 s | 551.0 s | 53.7 s | 1,027.9 MiB | 1 |
| S-AR1 surrogates, shard 1 | 36,000 | 640.1 s | 558.0 s | 57.0 s | 1,028.0 MiB | **0** |
| S-WHITE surrogates, shard 0 | 36,000 | 1,058.2 s | 956.2 s | 86.6 s | 1,027.9 MiB | 1 |
| S-WHITE surrogates, shard 1 | 36,000 | 1,062.5 s | 952.6 s | 86.8 s | 1,028.0 MiB | 1 |
| **total** | **278,951** | | | | **max 1,437.8 MiB** | |

<!-- src: /home/sdegan/t5a-matched-filter/*.jsonl.summary.json -->

**The device-pool claim held.** The largest recorded peak was **1,437.8 MiB**
against a claim of 1,800 and design section 4.5's 2 GiB cap. No run exceeded its
own claim; the prototype's opposite experience -- a 900 MiB claim against a
1,601 MiB truth, caused by reading the pool after `free_all_blocks()` -- is the
reason `matched_filter_run` records the pool while the batch is live, and this
program inherits that line.

**The reduction stage collapsed, and that is the one-harmonic statistic showing
its price.** It is **6.5%** of compute here (125 s of 1,826 s on the audit
shards) against the prototype's measured **43.6%-50.2%** for a four-member bank
<!-- src: docs/matched-filter-prototype-20260922.md section 4.1 -->. The
template-reduction cost is linear in the bank and quadratic in the retained
harmonic count, and this run carries one member at `k_max = 1`.

**Phase 2 of the phase-coherence measurement ran on the CPU and is not dressed
as GPU work.** Its registered estimands need eleven frequency points per fit --
`nu_m = m f` for `m = 0..10` -- and not the 13,377-point band sweep, so all eight
arms of section 3 complete in minutes of host time. Claiming a GPU for it would
have been theatre.

**A wasted three hours, recorded because the estimate discipline cuts both
ways.** The first audit pair ran under a dense-axis sizing that carried all five
harmonics through a one-harmonic statistic -- 1.74x the frequency axis and 25
Gram terms where one was needed -- and was killed at 4 h 55 m, unfinished, after
the corrected sizing completed the identical measurement in 32 minutes. The
correction is exact and
`tests/test_orbit_matched_filter_rung2.test_the_one_harmonic_axis_returns_the_identical_statistic`
proves it; the three hours were the price of not having looked.
## 2. MEASUREMENT 1 — the Rung-2 transfer test

The design fixed this screen in section 5.3 before any T5a measurement existed:
**Rung 2 is used only if the held-out passive exceedance at the nominal 1% level
lands within [0.5%, 2.0%]; otherwise Rung 3.** It is executed as registered.
What this run added, and registered before running, is the level at which the
exceedance is read, the class definition, the surrogate mechanism, the budget,
and the decomposition diagnostic (pre-registration section 0.2).

### 2.1 The sampling-geometry classes, as built

| | |
|---|---:|
| Passive windows, `mean_motion`, admitted by `cadence_core.window_admissible` | **217,323** |
| calibration half | **110,382** windows / 5,627 objects |
| held-out audit half | **106,941** windows / 5,485 objects |
| Registered cells before merging (`4 x 4 x 3 x 3`) | 144 |
| **Classes after the registered merge ladder** | **60** |
| Smallest class, calibration windows | **200** (the registered minimum, exactly) |
| Audit windows judged on rung 1 (full `g1 g2 g3 g4` cell) | 104,525 — **97.74%** |
| rung 2 / rung 3 / rung 4 | 712 / 417 / 1,197 |
| **Abstentions** — windows whose class has no admissible calibration exposure at any rung | **191** (0.088%), counted and attributed, never folded into a rate |

<!-- src: docs/matched-filter-rung2-classes-20260922.json -->

The window counts reproduce the prototype's independently taken reading exactly
-- 110,382 and 106,941
<!-- src: docs/matched-filter-prep-20260922.json passiveCalibrationHalf -->
-- which is the first end-to-end check that this program is reading the pilot's
own population.

**The measured AR(1) parameter is the headline of this subsection.** The class
median lag-1 autocorrelation of the post-cubic residual, over calibration
windows, has deciles p10 = 0.9906, p50 = **0.9958**, p90 = 0.9975, with a range
of 0.7638 to 0.9982. **The passive class's post-cubic residual is very nearly a
random walk.** That is measured, not assumed, and it is why the pre-registration
named the AR(1) surrogate PRIMARY on a-priori grounds before any threshold
existed: a white null on this channel would have set thresholds that are wrong
for a reason that has nothing to do with geometry-class transfer. Both
mechanisms are published below regardless, as design 5.3 requires.

**A defect in the class construction, found and fixed before any threshold
existed.** The merge ladder first counted every calibration window carrying a
coarse label, including windows already split off into finer cells at a higher
rung, so the leftover class a rung actually creates could hold **one**
calibration window while the rule believed it held two hundred. The first run
produced 81 classes with a minimum of 1. Counting only windows still unresolved
at each rung gives the 60 classes above with a minimum of exactly 200.
`tests/test_orbit_matched_filter_rung2.TestMergeLadder` asserts the difference
on a case built to expose it.

### 2.2 THE VERDICT

The registered screen, executed exactly as design section 5.3 fixed it before
any T5a measurement existed:

> **Held-out passive exceedance at the nominal 1% level: 9.658%**
> `[8.943%, 10.362%]`, clustered object bootstrap, 2,000 resamples, object
> records sorted by NORAD before the estimator saw them.
>
> **Screen: [0.5%, 2.0%]. The result is OUTSIDE it, above the upper bound by a
> factor of 4.83**
> <!-- derivation: 0.09658 / 0.020, computed for this document -->
>
> # **RUNG 2 IS NOT ADMISSIBLE. THE REGISTERED RULE SELECTS RUNG 3.**

The surrogate budget's own contribution to that number is **0.416 percentage
points** wide (p05 9.491%, p95 9.907%, from 500 nested bootstrap resamples of
each class's 1,200 surrogate draws) against a screen 1.5 points wide, so the
pre-registration's "unresolved at this budget" clause is **not** triggered: the
verdict is resolved, and it is a fail.

| arm | band | median threshold `tau` | held-out window exceedance | 95% clustered interval | object-level (max over windows) |
|---|---|---:|---:|---|---:|
| **S-AR1 (PRIMARY)** | **registered [2, 143.75] d** | **374.66** | **9.658%** | [8.943%, 10.362%] | 25.08% |
| S-AR1 | T3 [2, 219.51] d | 806.73 | 13.118% | [12.393%, 13.859%] | 45.53% |
| S-WHITE (secondary) | registered [2, 143.75] d | 24.31 | 78.033% | [77.445%, 78.582%] | 97.50% |
| S-WHITE | T3 [2, 219.51] d | 24.31 | 97.193% | [97.017%, 97.360%] | 99.71% |

<!-- src: docs/matched-filter-rung2-results-20260922.json -->

Exposure: **106,851** held-out audit windows over **5,482** objects were judged;
**90** abstained because their class carries no admissible calibration exposure
at any rung, counted and attributed and never folded into the rate.

**The comparators, both published as the registration requires.** T3's
equivalent figure was **9.316%** of held-out passive objects
<!-- src: docs/matched-filter-design-20260922.md section 5.1 -->; this run's
window-level figure is **9.658%**, a ratio of **1.037**
<!-- derivation: computed for this document -->. The object-level
max-over-windows comparator is **25.08%**, which must be read against the
**15.706%** a *perfectly calibrated* window-level null produces under the same
aggregation at a median of 17 windows per object (pre-registration 2.3) -- a
factor of 1.60, not of 25.

**The two surrogate mechanisms bracket the answer and the bracket is enormous.**
The white null's median threshold is **24.31** against the AR(1) null's
**374.66**, a factor of **15.4**, and it flags 78% of held-out passive windows.
The pre-registration named S-AR1 primary on a-priori grounds -- *"a white null on
a channel whose residuals are temporally correlated sets thresholds that are
wrong for a reason that has nothing to do with geometry-class transfer"* -- and
the measured class-median lag-1 autocorrelation of 0.9958 (section 2.1) is why.
Had S-WHITE been primary the verdict would have been the same FAIL for a reason
that says nothing about the question.

**The band-top fix helps, and not nearly enough.** Moving from T3's band to the
registered `[2 d, 143.75 d]` takes the exceedance from 13.118% to 9.658%, a
**26.4% reduction**
<!-- derivation: 1 - 0.09658/0.13118, computed for this document -->. Design
section 3.4's diagnosis was right in direction; the prototype's section 6 warning
that the effect is about three times weaker at GEO than in the pooled population
the diagnosis came from is confirmed here on the whole passive class.

### 2.3 The decomposition — and it moves the design's own diagnosis

This is why the pre-registration registered a calibration-half self-application
(section 2.7) that the design never asked for. Applying the identical class
thresholds to a registered 25% subsample of **calibration**-half objects -- the
half the thresholds were built from, not held out at all:

| | windows | objects | window exceedance | 95% clustered interval |
|---|---:|---:|---:|---|
| **calibration half** (not held out) | 27,989 | 1,407 | **8.764%** | [7.525%, 10.130%] |
| **audit half** (held out) | 106,851 | 5,482 | **9.658%** | [8.943%, 10.362%] |

**The two are indistinguishable.** The calibration interval contains the audit
point estimate and the audit interval contains the calibration point estimate;
the ratio is 1.10 against intervals a tenth of the way apart.

By the decomposition table fixed in the pre-registration before either number
existed, that is the **third** row, not the second:

> | calibration | audit | reading |
> |---|---|---|
> | ~1% | >> 1% | the class does not transfer -- the T3 failure |
> | **>> 1%** | **>> 1%** | **the surrogate model is wrong, and the transfer question is unanswered either way** |

> **THE GEOMETRY CLASS TRANSFERS. THE NULL DOES NOT CALIBRATE.** Holding out an
> object-level split costs 0.9 percentage points on a 9.7-point failure. What
> fails is the surrogate itself: the passive class's real windows carry far more
> power in the registered band than any surrogate built from that class's own
> geometry and its own measured noise colour reproduces.

**And that is a finding against the cluster ask, not for it.** The design's
ladder answers a failed Rung-2 screen with **Rung 3 -- per-object surrogates at
`B = 200`, 947 GPU-hours a sweep in the design's arithmetic and about 8,860 in
the prototype's corrected one**
<!-- src: docs/matched-filter-prototype-20260922.md section 5.3 -->. Rung 3 buys
a **per-object look-elsewhere factor**. The measurement above says the
look-elsewhere factor is not what is broken: borrowing across objects inside a
geometry class costs nine tenths of one percentage point, and the remaining 8.8
points are already present when nothing is borrowed at all.

**Paying 8,860 GPU-hours a sweep to fix a 0.9-point term in a 9.7-point failure
is the single most expensive thing this programme could now do, and the
registered rule would have sent it there unexamined.** The registration executed
the rule and reports Rung 3 as selected, because that is what was registered;
the decomposition is reported beside it because a number without an explanation
is what `docs/phase3-results-20260921.md` draws against itself.

### 2.4 What the residual 8.8 points could be, none of it measured here

Three readings, none chosen, all consistent with the design's own declared
blind spots:

1. **Real in-band structure in the passive class.** Design section 6(6) declares
   it in advance -- ETALON 1 and 2 sit on the 27.5 d line on 35 of 35 and 30 of
   35 windows and carry no propulsion, and the 75.25 d Cosmos line is the
   half-beta period of its shell. No surrogate contains those lines. Every
   exceedance in this document is therefore an **upper bound** on the
   miscalibration, and T3's 9.32% carries the identical defect, which is why the
   comparison to it is fair.
2. **AR(1) is not the right noise model.** The class-median lag-1
   autocorrelation is 0.9958 -- so close to a unit root that the post-cubic
   residual is nearly a random walk -- and a one-parameter model of a
   nearly-non-stationary process will misplace the tail of `max F` even when it
   matches at lag one.
3. **`E[F]`-style normalisation is not a calibrated null for a maximum.** The
   statistic is maximised over roughly 13,377 fundamentals; the surrogate
   captures that maximisation exactly, so this reading is the weakest of the
   three, and it is named only because it is testable.

Separating them is an experiment, not an argument: generate surrogates that
carry the passive class's measured in-band lines and re-run the identical
screen. That is a prototype-scale job on the instrument that now exists.

---
## 3. MEASUREMENT 2 — the phase-coherence diagnostic

Every estimand and threshold in this section was registered in section 3 of the
pre-registration and its Amendment 1, both committed before any number existed.
Nothing here is inferential: no p-value, no gate, no object relabelled.

### 3.1 Read the floor and the ceiling FIRST, because neither is where it was assumed

The two control arms of prereg 3.7 exist so that a coherence number can be read
at all, and both of them moved the reading.

**The ceiling works, and it is a lower bound.** A fully coherent ideal sawtooth
of design 1.1, injected at the design's derived amplitude `3.3067e-5 rev/day`
into the real carrier series -- real epochs, real gaps, real noise -- returns
`C2 = 0.922` at the shortest lag and never falls below `0.86` out to 1,008 days
on the 42 d ladder, and `psi_2 = 0.532`, `psi_3 = 0.313`. **The instrument can
see coherence that is there**, so prereg 3.7's instrument-limited verdict is not
triggered. The ceiling is a LOWER bound on the achievable numbers, because the
injection is added on top of whatever the carriers already carry, and section
3.4 measures that the carriers' own second harmonic is in ANTI-phase to the
injected one -- which can only suppress the ceiling's `psi_2`, never inflate it.

**The floor is not a floor.** The same-shell GEO passive control returns a mean
debiased power of **9.65 per segment** at `L = 42 d` against a median `F` of
**1.761** -- a distribution whose mean is an order of magnitude above its median,
which is a right tail of passive objects carrying real 14 d-band power, not a
calibrated null. Its `C2` is therefore **0.528** at the shortest lag rather than
zero, and its registered `T_coh` is a finite **117 d**. Amendment 1 declared this
possibility in advance -- *"if the floor arm returns `|z|^2` far from 1 on the
passive control, that number is published and the coherence values are read
against it rather than against 1"* -- and that is what is done below. **Every
`C2` in this section is read as a comparison between arms at the same ladder,
never as an absolute coherence.**

| arm | median `F` at the fundamental, `L = 42 d` | mean debiased power per segment |
|---|---:|---:|
| same-shell GEO passive control (FLOOR) | 1.761 | 9.65 |
| 208 east-west carriers | **11.808** | **26.29** |
| 56 north-south carriers (`inclination`) | 11.686 | — |
| carriers + injected ideal sawtooth (CEILING) | 43.273 | 31.58 |

<!-- src: docs/matched-filter-phase-coherence-20260922.json, arms.*.ladders.42 -->

### 3.2 Estimand (a): phase across an object's own T3 windows

The quantity the brief names, computed on the registered 1080 d windows with the
registered cubic, phases referred to the absolute epoch. **The 720 d overlap
between consecutive T3 windows is a confound and is declared rather than
corrected**: a 360 d step on a 1080 d window means two thirds of any pair is the
same data, so these numbers are a description of the T4 hand-off product and are
NOT the coherence timescale. That is what section 3.3 is for.

| arm | objects | median circular variance | fraction with `R > 0.5` |
|---|---:|---:|---:|
| east-west carriers, fixed `f0` | 208 | **0.4475** | 0.524 |
| east-west carriers, per-object refined `f` | 208 | 0.4036 | 0.577 |
| north-south carriers | 56 | 0.3200 | 0.714 |
| passive control (FLOOR) | 318 | 0.6753 | 0.261 |
| ceiling | 208 | 0.1168 | 0.981 |

The carriers sit between the floor and the ceiling on every column, and the
north-south channel is the more coherent of the two. The phase channel exists,
carries a number, and separates the classes -- which is the most that overlapping
windows can establish.

### 3.3 Estimand (b): the coherence timescale, and it depends on one choice

`T_coh` is the registered 1/e crossing of `C2(d)` relative to its shortest-lag
value, from disjoint segments tiled over each object's whole history.

| ladder | arm | `T_coh` |
|---|---|---:|
| `L = 42 d` (3.00 cycles) | east-west carriers, FIXED `f0` | **568 d** |
| | east-west carriers, per-object REFINED `f` | **> 1008 d** (no crossing) |
| | north-south carriers, fixed | > 1008 d (no crossing) |
| | passive control (FLOOR), fixed | **117 d** |
| | passive control, refined | 122 d |
| | ceiling | > 1008 d (no crossing) |
| `L = 210 d` (15.00 cycles) | east-west carriers, fixed | 843 d |
| | passive control (FLOOR), fixed | **1586 d** |
| | north-south carriers, fixed | 1952 d |
| | east-west carriers, control and ceiling, all REFINED | > 5040 d (no crossing) |
| | north-south carriers, refined | 2096 d |

**Two of those rows disqualify their own ladder or variant, and both were
anticipated by the registered control arms.**

1. **At `L = 210 d` the control is MORE coherent than the carriers** -- 1,586 d
   against 843 d. A ladder on which a population with no station-keeping
   out-scores the population that carries the line is measuring the red noise
   both share, not the line. The 210 d ladder is reported and **not read**.
2. **Under the per-object refinement the control's `T_coh` goes from 1,586 d to
   beyond 5,040 d at `L = 210`**, because choosing the frequency that maximises
   an object's own windowed `F` over 30 candidates selects for exactly the
   long-baseline coherence that `C2` then measures. Variant B at the coarse
   ladder is **circular and is not read**. At `L = 42 d` the same refinement
   moves the control by nothing at all -- 117 d to 122 d -- so variant B **is**
   readable there, and that is the arm the verdict uses.

**The reading, at the one ladder and the one pair of variants the controls
license:** at `L = 42 d`, a single common 14.00 d template holds phase for
**568 days -- about 41 cycles** -- against a floor of 117 d and a ceiling that
does not decohere at all. Giving every object its **own** fundamental removes the
decay entirely (> 1,008 d, about 72 cycles, the full measured baseline), while
leaving the floor untouched.

**What that difference is.** The per-object refined indices span 1915 to 1944 on
the instrument's grid -- periods **14.10 d down to 13.89 d** -- with 106 of 208
carriers at 1928-1929 and a real spread around it
<!-- src: docs/matched-filter-phase-coherence-20260922.json arms.ew-carriers-refined.refinedIndexHistogram -->.
That is `+/- 0.105 d`, which is T3's published core half-width of `+/- 0.109 d`
almost exactly, and it is the asymmetric, slot-dependent period distribution
design 1.3(a) predicts from `T = 4 sqrt(dLambda / A)`. The control's refined
indices, by contrast, **pile up on the two edges of the search window** -- 61 at
1915 and 62 at 1944 of 331 -- which is what fitting noise to a boundary looks
like and is the second reason variant B needs its floor arm.

**So the 568 d is not phase noise. It is period dispersion between objects**, and
a fixed 14.00 d template pays for it.

### 3.4 Estimand (c): the harmonics do not track, and one of them is inverted

> **ERRATUM 2026-09-22 — THE MECHANISM IS NOW MEASURED. Nothing below is
> rewritten and no number below is withdrawn; every measurement in this section
> reproduces exactly on an independent code path.** Section 6 item 8 left open
> whether the anti-phase second harmonic is a burn pair, an archive smoothing or
> something else. It is none of the first two. The registered experiment in
> `docs/harmonic-mechanism-preregistration-20260922.md` (`baea6f3`, committed
> alone) and its results, `docs/harmonic-mechanism-results-20260922.md`
> (`ace55c3`), return the verdict **BURN STRUCTURE**: the carriers' drift-rate
> ramp runs the OTHER WAY — the same one-burn sawtooth with the opposite sign —
> and the sign is set per object by which side of its triaxial equilibrium the
> slot sits on. A one-burn sawtooth injected into 331 real passive series comes
> back at `psi_2 = +0.02 rad`, so the pipeline inverts nothing; the archive's
> effective averaging span is bounded above at 2.16 d against the 11.21-14.00 d
> a boxcar would need; no two-burn split reset matches at any separation or
> impulse ratio; and the per-object `psi_2` is BIMODAL, 43 upright against 68
> inverted, while the same objects' `psi_3` is unimodal with not one object at
> `pi`. Two post-hoc arms name the cause: a 180-degree-periodic sign function of
> geographic longitude separates the two modes 91 of 91, and the skew of the
> differenced series agrees with the phase mode 111 of 111.
>
> **What to correct when reading below.** Where this section says the second
> harmonic is "in ANTI-PHASE to the one the sawtooth template asks for", read
> "in anti-phase for the three fifths of the fleet whose slot puts the ramp the
> other way, and in phase for the rest" — the pooled `R_2 = 0.084` is the small
> difference between two opposed populations, not one weak concentration. The
> `k = 2`-free prescription of section 3.6 stands and is sharpened: the free
> parameter is a per-object SIGN, and it is predictable from the slot longitude.

`psi_k = theta_k - k theta_1`, each harmonic fitted **alone** so the relation is
measured rather than imposed. Resultant length `R_k` pooled over carrier
segments, `L = 42 d` (the `L = 210 d` figure follows in brackets):

| `k` | FLOOR (control) | **east-west carriers** | CEILING (ideal sawtooth) | carriers' mean angle | registered verdict |
|---|---:|---:|---:|---:|---|
| 2 | 0.038 (0.028) | **0.084** (0.088) | 0.532 (0.595) | **3.19 rad** (3.08) | scrambled |
| 3 | 0.048 (0.006) | **0.255** (0.195) | 0.313 (0.398) | 6.18 rad (6.08) | partial |
| 4 | 0.014 (0.008) | 0.051 (0.076) | 0.224 (0.299) | 2.93 rad | scrambled |
| 5 | 0.027 (0.010) | 0.116 (0.142) | 0.131 (0.237) | 6.16 rad | partial |

<!-- src: docs/matched-filter-phase-coherence-20260922.json arms.*.ladders.*.psi -->

Read against the ceiling rather than against 1, the second harmonic reaches
**16%** of the concentration an ideal sawtooth achieves at the same exposure and
the third reaches **81%**. And the angles are the finding:

> **The ceiling's `psi_2` and `psi_3` both sit at 0.04 rad, which is what a
> one-burn sawtooth requires -- every harmonic in sine phase relative to the
> burn. The carriers' `psi_3` sits at 6.18 rad, i.e. `-0.10` rad, agreeing with
> the sawtooth. The carriers' `psi_2` sits at 3.19 rad, which is `pi` to within
> 0.05 rad: the second harmonic is present and it is in ANTI-PHASE to the one
> the sawtooth template asks for.**

**This is a direct, mechanical explanation of the prototype's Finding 1.** The
matched response is `R = sum_k Re(W_k c_k e^{-i k phi})`; a harmonic whose data
phase is `pi` from the template's contributes a NEGATIVE term to the numerator
while contributing its full positive share to the fitted norm `G`. The
five-harmonic sawtooth therefore subtracts response and adds norm at `k = 2`,
which is a loss twice over -- and the prototype measured exactly that loss,
`-2.715 dB`, on the windows that carry the line
<!-- src: docs/matched-filter-prototype-20260922.md, Finding 1 -->.

**And the harmonics are faint even in the ceiling.** Median `F` at the
harmonics, `L = 42 d`, against a null mean of 2:

| | `k = 2` | `k = 3` | `k = 4` | `k = 5` |
|---|---:|---:|---:|---:|
| east-west carriers | 3.01 | 1.39 | 1.19 | 0.90 |
| CEILING, ideal sawtooth at `3.3067e-5 rev/day` | 6.52 | 3.61 | **2.18** | **1.62** |
| FLOOR, passive control | 0.80 | 0.60 | 0.58 | 0.57 |

**A perfect one-burn sawtooth at the design's own derived amplitude puts median
`F = 2.18` at `k = 4` and `1.62` at `k = 5`** -- at and below the null mean of 2.
Harmonics four and five are not measurable in this archive at this amplitude,
by construction, whatever the template says. That is prototype section 4.3's
reading 2 -- *"the harmonics are present in the true `delta n` but below the
archive's own noise at `k >= 2`"* -- measured rather than offered.

The north-south channel is its own case: `psi_2 = 0.163` at a mean angle of
**2.08 rad**, neither the sawtooth's 0 nor the east-west channel's `pi`. North-
south keeping is a different manoeuvre and this measurement says so rather than
assuming it.

### 3.5 An amplitude screen the programme has never had, and its defect

Design section 11 item 1 says the derived `3.3067e-5 rev/day` cannot be turned
into a signal-to-noise ratio because no per-element uncertainty exists. The
ceiling arm supplies a back door: it injects a KNOWN amplitude into the SAME
windows and reports the same statistic. Under power additivity with independent
phases, `F - 2` adds, so

> `A_real / A_injected = sqrt( (F_carrier - 2) / (F_ceiling - F_carrier) )`
> <!-- derivation: computed for this document -->
> `L = 42 d`: `sqrt(9.81 / 31.47) = 0.558` -> **`1.85e-5 rev/day`**
> `L = 210 d`: `sqrt(7.64 / 97.00) = 0.281` -> **`0.93e-5 rev/day`**

**The two ladders disagree by a factor of two and the screen is reported as a
bracket, not a number: the measured 14.00 d line amplitude is between about
0.28 and 0.56 of the design's derived one-burn value, i.e. roughly
`0.9e-5` to `1.9e-5 rev/day`.** The disagreement is itself informative -- a
coherent signal's `F` should scale with segment length and the carriers' does
not, which is the same partial coherence section 3.3 measured -- but it means
this screen cannot be quoted as a measurement, and it is not.

### 3.6 THE STATISTIC VERDICT, stated plainly

The brief asked which of three statistics the measured coherence derives. It
derives a fourth, and the parts are separable:

1. **On the fundamental, and only with a per-object fundamental, the signal is
   coherent across the whole measured baseline** -- more than 1,008 days, about
   72 cycles, with the floor arm unmoved by the same procedure at that ladder.
   Coherent cross-window stacking (design 3.6's SECONDARY aggregator) is
   therefore **licensed on the fundamental**, and it is licensed **only** if the
   fundamental is fitted per object rather than fixed at 14.00 d.
2. **With a single fixed 14.00 d template the coherence length is 568 days,
   about 41 cycles.** A fixed-template filter must be **semi-coherent**: coherent
   inside about 570 d, incoherently summed above it. The cause is measured to be
   period dispersion across the fleet -- 13.89 to 14.10 d -- which is design
   1.3(a)'s prediction, not a defect.
3. **On the harmonics the answer is the opposite. Do not run a phase-locked
   harmonic template.** `k = 2` is present at 16% of the achievable concentration
   and in ANTI-phase to the sawtooth; `k = 3` tracks at 81%; `k = 4` and `k = 5`
   are below the archive's noise even for a perfect sawtooth at the design's own
   amplitude. A template that imposes the one-burn sawtooth's harmonic phases
   loses more in norm than it gains in response -- which is what the prototype
   measured and this section explains.

> **The statistic the measurement derives: a per-object refined fundamental,
> coherently stacked across the whole history, with the harmonics entering as an
> incoherent POWER sum at `k <= 3` and not at all above it -- and with the
> `k = 2` relative phase treated as a FREE parameter rather than fixed by the
> sawtooth, because the data put it at `pi`.**

That is neither the design's five-harmonic sawtooth matched filter nor the
pilot's bare sinusoid. It is a two-parameter semi-coherent filter, and every
element of it is a measured quantity rather than a preference.

---

## 4. The card-speed aside — the paired slice, and a folklore retired

Ten minutes were asked for and rather more were spent, because the first answer
was wrong. The pilot measured card 0 running **2.1x** slower than card 1 on
identical work and the prototype measured **3.47x**
<!-- src: docs/cadence-results-20260921.md section 1.2; docs/matched-filter-prototype-20260922.md section 4.1 -->.
**Nothing was changed, nothing is proposed, and no scheduling was altered.**

### 4.1 The paired slice

`gpu-run` places by largest eligible remainder and gives the caller no way to
request a card. Asked twice for two byte-identical jobs it put both copies on
the same card, twice. The paired slice arrived instead on the third attempt,
when the broker split the two AR(1) surrogate shards one to each card: the same
program, the same 60-class registry, 30 classes and 36,000 surrogate windows
each, launched in the same second, each with its card to itself.

| shard | card | windows | wall clock | grid stage | rate |
|---|---|---:|---:|---:|---:|
| S-AR1 shard 0 | **1** | 36,000 | 620.0 s | 551.0 s | **58.1 windows/s** |
| S-AR1 shard 1 | **0** | 36,000 | 640.1 s | 558.0 s | **56.2 windows/s** |

<!-- src: /home/sdegan/t5a-matched-filter/surro-ar1-{0,1}.jsonl.summary.json -->

> **Card 0 is 3.3% slower than card 1**
> <!-- derivation: 640.1 / 620.0, computed for this document -->
> **on simultaneous, equal-sized work with one job per card. Not 2.1x. Not
> 3.47x.**

The grid stages -- the part that is neither Python nor scheduling -- are
**558.0 s against 551.0 s, 1.3% apart.**

Two earlier deterministic checks point the same way: the two byte-identical
`cardprobe` jobs, which the broker placed on the same card, returned **902,626**
and **901,709** dense evaluations per second, 0.10% apart, so the instrument's
cost is deterministic and the asymmetry was never in our code.

### 4.2 What the telemetry says, sampled on both cards while our work ran

| | card 0 | card 1 |
|---|---|---|
| part / `vbios_version` | RTX 4080 / 95.03.33.00.57 | RTX 4080 / 95.03.33.00.57 |
| `clocks.max.sm` | 3105 MHz | 3105 MHz |
| `clocks.sm` under our load | **2775 MHz** | 2715-2730 MHz |
| `power.limit` / `enforced.power.limit` | 320.00 W | 320.00 W |
| `power.draw` under our load | 66-68 W | 103-235 W (shared with other work) |
| `temperature.gpu` under our load | 45-49 C | 49-64 C |
| `clocks_event_reasons.active` while our job ran | **0x0** | **0x0** |
| `compute_mode` / `persistence_mode` | Default / Enabled | Default / Enabled |

<!-- src: /home/sdegan/t5a-matched-filter/cardprobe-smi.csv, rung2-smi.csv -->

**Nothing in clocks, thermals, power limits or throttle reasons distinguishes
them.** Card 0 runs its SMs 2.2% *faster* and 5-15 C cooler. No throttle reason
was ever active on the card running our job. Our workload draws 66-68 W of a
320 W limit at "100% utilisation", so it is bandwidth and occupancy bound, and
`utilization.gpu` at 100% means only that a kernel was resident.

### 4.3 The one field that does differ, and it was not queried before

| | card 0 | card 1 |
|---|---|---|
| `pci.bus_id` | 0000:04:00.0 | 0000:07:00.0 |
| `pcie.link.gen.current` / `max` | **3** / **3** | **4** / 4 |
| `pcie.link.width.current` / `max` | **4** / 16 | **16** / 16 |
| theoretical host-interface bandwidth | **3.94 GB/s** <!-- derivation: PCIe 3.0 x4 = 4 x 0.985 GB/s --> | **31.5 GB/s** <!-- derivation: PCIe 4.0 x16 = 16 x 1.969 GB/s --> |

Card 0's link is not merely negotiated down: its `gen.max` is **3**, so the slot
itself is Gen 3, and it runs four of its sixteen lanes. **That is 8.0x in
host-interface bandwidth**
<!-- derivation: 31.5 / 3.94, computed for this document -->
**and it costs this workload 3.3%**, which is what a device-resident,
batch-oriented kernel should cost: the link carries the per-batch upload of a
padded window block and the per-chunk read-back of the `F` surface, and neither
is the inner loop.

### 4.4 Where the folklore came from

Concurrency and process age, not the part. Three observations, all from this
session:

1. While two long-lived AR(1) processes shared card 0, they ran at **3.6
   windows/s** each. Restarted, one per card, the same program on the same work
   ran at **56.2** on the same card 0 -- a **15.6x** swing with no hardware
   change.
2. Two jobs sharing card 1 ran at 34.0 and 33.9 windows/s, an aggregate of
   **67.9** against a single job's **58.1** -- so a second tenant costs each job
   41% and *gains* the card 17%. A card that looks "100% utilised" at 66 W has
   room for another tenant, which is exactly how one session's job halves
   another's rate while the telemetry shows nothing.
3. During the earlier slices, the card our job was NOT on carried somebody
   else's work every time -- 33-42% utilisation on 606 MiB in one, an 11,264 MiB
   claim at 227-235 W in the other.

**UNPROVEN, in that word.** The causal attribution of the 3.3% to the PCIe link
is not proven: it is a mechanism and a coincidence of sign, not a controlled
experiment, and no host-to-device bandwidth benchmark was run on either card.
What IS measured is that on simultaneous equal work with one job per card, the
two cards are 3.3% apart.

---

## 5. Deviations from the registration, each named

1. **The pre-registration's printed period for the registered grid index is a
   slip in the division.** Section 3.4 prints `P0 = 13.99657 d` for index 1929.
   `1929 x 3.703704e-5 = 0.07144444 c/d` and `1 / 0.07144444 =` **13.99689 d**.
   The REGISTERED object is the grid index, which is unchanged and is still the
   nearest grid point to 14.00 d; no number depends on the printed value; and
   `tests/test_orbit_matched_filter_rung2.test_the_fundamental_is_the_nearest_grid_point_to_14_days`
   asserts the corrected figure with the slip named in a comment.
2. **Amendment 1**, committed alone at `03df5c8` before any number governed by
   section 3 existed: the registered off-line noise band lay inside a 42 d
   segment's own resolution element -- 643 grid steps -- and would have estimated
   the signal rather than the noise. Replaced by the statistic's own `E[F] = 2`.
   Recorded in the registration itself rather than here.
3. **Three arms were added to the section 3 run after the first arms returned**:
   `control-floor-refined`, `ns-carriers-refined` and `ceiling-refined`. They are
   the registered FLOOR and CEILING arms of prereg 3.7 evaluated under the
   registered variant B of prereg 3.4, and they were run because a variant-B
   carrier number cannot be read without them. **They made the carrier result
   weaker, not stronger** -- they are what disqualified variant B at the 210 d
   ladder (section 3.3) -- so the addition cannot be read as a number chosen with
   a result in view. The arm list in the driver was incomplete; the registration
   was not.
4. **The dense frequency axis is sized for one harmonic**, and the harmonic Gram
   is read at `2 f` rather than `2 k_max(f) f`. This is exact, not an
   approximation: harmonics 2 to 5 carry weight zero in this statistic and
   multiply out either way, and
   `tests/test_orbit_matched_filter_rung2.test_the_one_harmonic_axis_returns_the_identical_statistic`
   asserts the two paths return the identical `F` to `1e-9`. Every number in
   section 2 was produced under the reduced sizing; the first audit pair, run
   under the original sizing, was killed unfinished and contributed nothing.
5. **Surrogates of one representative share its window function**, so the eight
   nuisance reductions are computed once per representative rather than once per
   draw -- two reductions per (window, sample, frequency) instead of ten. Also
   exact, also asserted:
   `test_the_shared_geometry_path_is_the_same_statistic` and
   `test_y_dense_reductions_matches_the_verified_kernel`, the latter to bit
   equality against `matched_filter.dense_reductions`.
6. **A defect in this session's own class construction, found and fixed before
   any threshold existed.** The merge ladder counted every calibration window
   carrying a coarse label, including windows already split off into finer cells
   at a higher rung, so the leftover class a rung actually creates could hold a
   single calibration window while the rule believed it held two hundred. The
   first run produced 81 classes with a minimum of 1; counting only windows
   still unresolved at each rung gives 60 classes with a minimum of exactly 200.
   `TestMergeLadder` asserts the difference on a case built to expose it.
7. **`nuisance_moments` normalises time by the registered 1080 d window width**,
   so a 42 d segment's polynomial basis is evaluated on `u` in `[-1, -0.92]`.
   That is a conditioning question and not a correctness one: every section 3 fit
   runs in float64 and the segment path is asserted against
   `matched_filter.reference_profile_statistic` -- an explicitly constructed
   design matrix solved with `numpy.linalg` -- to `1e-6` in `F` and `1e-4` rad
   in phase.
8. **An intermediate card-speed reading was wrong and is withdrawn here rather
   than quietly dropped.** Mid-run, two long-lived AR(1) surrogate processes on
   card 0 were measured at 3.6 windows/s against 34 on card 1, and the PCIe
   difference of section 4.3 was found while looking for the cause. The clean
   paired slice that arrived afterwards put the two cards 3.3% apart. The 9.4x
   was concurrency and process age, the PCIe difference is real and costs 3.3%
   in this workload, and the first reading is recorded as an error because a
   session that reports only its final numbers is not reporting its method.

## 6. What remains UNPROVEN, in that word

1. **What the residual 8.8 points of the Rung-2 failure ARE is UNPROVEN.**
   Section 2.4 names three readings and chooses none. The experiment that
   separates them -- surrogates that carry the passive class's measured in-band
   lines -- is not run.
2. **The Rung-2 verdict is UNPROVEN for the 18-member bank.** It was measured
   with the one-harmonic statistic, whose look-elsewhere factor is the smallest
   in the family. A bank of 18 members searches more, and the transfer question
   must be re-asked before a registered sweep uses it.
3. **Whether Rung 3 would calibrate is UNPROVEN.** Section 2.3 shows that the
   term Rung 3 buys is 0.9 of 9.7 points, which is an argument against spending
   8,860 GPU-hours a sweep on it, not a measurement of what per-object
   surrogates would return. No Rung-3 calibration was run.
4. **The causal link between the PCIe difference and any throughput number is
   UNPROVEN** (section 4.3). An 8.0x link difference costing 3.3% is consistent
   with a device-resident workload, but no host-to-device bandwidth benchmark was
   run on either card and none is proposed.
5. **Recall remains UNMEASURED**, as it is everywhere in this programme.
   Nothing here bounds a null.
6. **The coherence timescale below 42 days is UNRESOLVED** and the ladder cannot
   see it; prereg 3.8(1) fixed that wording before the run.
7. **The amplitude screen of section 3.5 is a bracket, not a measurement**, and
   the two ladders disagree by a factor of two.
8. **Whether the anti-phase second harmonic is a burn pair, an archive
   smoothing, or something else is UNPROVEN.** Section 3.4 measures that it is
   there and that it is inverted; the injection-recovery arm of design 7.3 is
   still the measurement that would say which.
9. **The element weights remain a screen**, per design 3.3, so every interval
   this detector will ever publish inherits that status until per-element
   covariances exist.
10. **No p-value, no gate, no object relabelled.** Neither measurement is
    inferential and neither is T5a. There is still no
    `docs/t5a-preregistration-<date>.md`.

## 7. Honest summary

Two measurements were registered before either produced a number, and both came
back against the design -- one against its null, one against its template -- and
in both cases the control arms the registration insisted on are what made the
result readable.

The Rung-2 screen fails at **9.658%** against **[0.5%, 2.0%]**, so the
registered rule selects Rung 3. The calibration-half control the registration
added says that is the wrong lesson: the same thresholds applied to the half
they were built from give **8.764%**, statistically the same number, so the
**geometry class transfers and the null does not calibrate**. The design read
T3's 9.32% as a transfer failure and priced a 947-GPU-hour-a-sweep per-object
null to fix it; the prototype repriced that at 8,860; this measurement says the
transfer term is 0.9 points of a 9.7-point failure. The expensive fix addresses
the small term.

The phase diagnostic explains the prototype's Finding 1 mechanically. The
14.00 d line's fundamental is coherent -- **568 d, about 41 cycles, at a fixed
template, and beyond the full 1,008 d measured baseline once each object is
given its own period**, with the measured periods spanning 13.89 to 14.10 d
exactly as design 1.3(a) predicts. The harmonics are not. The second harmonic
sits at **`pi`** from where a one-burn sawtooth puts it, which subtracts
response while adding norm; the third tracks; the fourth and fifth are below the
archive's noise even for a perfect sawtooth injected at the design's own derived
amplitude. The statistic the data derives is a **per-object refined fundamental,
coherently stacked, with harmonics entering as an incoherent power sum at
`k <= 3` and the `k = 2` relative phase left free** -- which is neither the
design's five-harmonic matched filter nor the pilot's sinusoid.

And a piece of folklore is retired: on a clean paired slice the two cards are
**3.3%** apart, not 2.1x or 3.47x. They do differ -- PCIe 3.0 x4 against PCIe
4.0 x16 -- and in this workload that costs 3.3%.

Nothing here is T5a. Every number above is a prototype reading taken so that a
registration can be written with them in hand rather than after cluster time has
been spent, which is the one lesson `docs/phase3-results-20260921.md` draws
against itself and the reason both of these measurements were run at all.
