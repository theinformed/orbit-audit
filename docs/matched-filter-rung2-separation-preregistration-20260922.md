# T5a Rung-2 SEPARATING EXPERIMENT: PRE-REGISTRATION

**Status: REGISTRATION. Committed ALONE, before any number of this experiment
exists, before the instrument that produces them is written.**

Registered 2026-09-22. Parent documents, all committed before this one:

- `docs/matched-filter-design-20260922.md` (`e51bcce`) — the null ladder, the
  Rung-2/Rung-3 screen `[0.5%, 2.0%]` fixed in section 5.3 before any T5a
  measurement existed.
- `docs/matched-filter-rung2-preregistration-20260922.md` (+ Amendment 1,
  `03df5c8`) — the Rung-2 transfer test as registered.
- `docs/matched-filter-rung2-results-20260922.md` (`f634a0e`) — the failed
  screen, the decomposition, and section 2.4's three unseparated candidates.
- `docs/cadence-results-20260921.md` and `docs/cadence-results-20260921-lines.json`
  — the pilot's measured line census, from which this experiment's injected
  line periods and its a-priori amplitude bound are taken.

Nothing here is T5a. This is a **calibration experiment about a null**, not a
detector measurement, and it produces no p-value, no gate and no object label.

---

## 0. The question, in one paragraph

Rung 2 failed its screen at **9.658%** `[8.943%, 10.362%]` against `[0.5%, 2.0%]`,
and the calibration-half control the Rung-2 registration added returned
**8.764%** `[7.525%, 10.130%]` on the half the thresholds were *built from*.
The geometry class transfers; the null does not calibrate. Holding out an
object-level split costs **0.9 points of a 9.7-point failure**, and the
registered ladder answers that failure by buying **Rung 3 — a per-object null,
about 8,860 GPU-hours a sweep** in the prototype's corrected arithmetic. The
remaining **8.8 points are unmeasured**: results section 2.4 names three
candidates and chooses none. This experiment separates them, and asks the
question the ladder never asks — **does a per-object null calibrate AT ALL on
this archive** — at about 1/1,600 of the price of finding out by buying Rung 3.

**Registered decision role.** The outcome of this experiment is a precondition
on the Rung-3 spend. Section 7 fixes, before any number, what each outcome means
for that decision.

---

## 1. What is already bound, and what is newly registered here

### 1.1 Bound by the parents. Not restated, not softened, not re-derived.

- The **statistic**: `F(f)` of design 3.2 with the one-harmonic weight vector,
  the registered cubic nuisance basis inside the fit, `p = 6`, phase maximised
  in closed form; per window the reported quantity is `peak F` over the
  fundamentals of the registered band. `tools/matched_filter.py` kernels,
  unchanged.
- The **band**: PRIMARY `[2 d, 143.75 d]` only. The T3 band `[2, 219.51]` is
  **not** re-run here; one band, so that no arm can be read at whichever band
  flatters it.
- The **population**: every window of every `passive`-class object admitted by
  `cadence_core.window_admissible` on `mean_motion`, the T3 object-level
  calibration/audit split as committed in `docs/cadence-results-20260921.jsonl`.
- The **percentile**: 99.0, `numpy.percentile(..., method="linear")`.
- The **screen**: `[0.5%, 2.0%]`, design 5.3. Reused unchanged so that every
  number in this document is commensurable with the 9.658% it explains.
- The **estimator**: window-level exceedance with a clustered object bootstrap,
  2,000 resamples, object records sorted by NORAD before the estimator sees
  them.
- The **class thresholds** `tau_c`: the committed Rung-2 AR(1) thresholds, for
  the 60 committed classes, recomputed from the committed surrogate artifacts
  (`surro-ar1-0.jsonl`, `surro-ar1-1.jsonl`, sha256 in
  `docs/matched-filter-rung2-results-20260922.json`). `tau_c` is the 99th
  percentile of a set and is therefore independent of read order. The
  instrument **asserts** that the recomputed class-median `tau` equals the
  committed **374.66** before it is allowed to judge a single window; if it does
  not, the run aborts and the discrepancy is published instead of a result.

### 1.2 Newly registered here

The arms, the generators, the two exposures, the a\* amplitude rule, the
decomposition arithmetic, the instrument-validity gates, the acceptance bands,
the seed, and the Rung-3 decision table. All of section 2 onward.

### 1.3 What this document does NOT register

- It does not register a T5a detector, a template family, or a recall
  measurement. **Recall remains UNMEASURED**, here as everywhere in this
  programme; section 6.3 states precisely what the one injected-line arm does
  and does not bound.
- It does not re-open the Rung-2 verdict. That verdict stands as published.
  This experiment explains it.
- It does not register the redesigned statistic. That is another session's
  `docs/t5a-preregistration-*.md` and `tools/matched_filter_v2.py`, and this
  document touches neither.

---

## 2. Seed, exposure and the two families of arms

**Seed: `20260923`.** Distinct from the parent's `20260922` so that no draw of
this experiment can collide with a draw the committed run already made. Every
random choice below — object subsampling, AR(1) innovations, injected line
periods and phases — derives from it by a stated, reproducible rule.

### 2.1 Family I exposure — the class-threshold arms

Objects are drawn, not windows, because the estimator clusters on objects.

> Take the audit-half passive NORADs, **sorted ascending**. Permute them with
> `numpy.random.default_rng(20260923)`. Walk the permutation, accepting each
> object **whole** (all of its admitted audit windows), and stop after the
> accepted window total first reaches or exceeds **20,000**.

Expected: about 1,030 objects and about 20,000 windows, from the committed
106,941-window / 5,485-object audit half. The realised counts are published.
At `p = 1%` and about 20 windows per object this exposure resolves a difference
of **0.5 percentage points** between two arms; that is the smallest term this
experiment claims to see, and it is stated before any term is measured.

### 2.2 Family II exposure — the per-object (Rung-3 preview) arms

> From the Family-I object set, draw **300** objects with the same generator
> (`default_rng(20260923)`, a second, separately named stream), and from each
> take its **first 4** admitted audit windows in window order (all of them if it
> has fewer).

Expected: about 1,200 windows over 300 clusters. Each window gets `B = 200`
surrogates **on its own epochs** — the design's own Rung-3 budget — so this is
Rung 3, executed at prototype exposure rather than argued about.

### 2.3 The generators

Every arm produces a value series on a window's epochs and hands it to the
**identical** `peak F` path. The arms differ only in the generator. `F` is
exactly invariant to an affine-in-the-nuisance-span transformation of the values
(`tools/matched_filter_run._detrend_and_normalise` docstring; asserted by
`tests/test_orbit_matched_filter`), so a pre-detrend of pseudo-data cannot
change any number below and none is applied to generated series, exactly as the
committed surrogate stage does not apply one. **The pipeline-asymmetry worry —
"real windows are pre-detrended and surrogates are not" — is therefore closed
analytically and is not an arm.** The offline tests assert the invariance
numerically on a fixture rather than trusting this paragraph.

| id | generator | epochs |
|---|---|---|
| **C0** ORACLE | AR(1) at the class's committed `phi_c`, `R = 24` representatives x `S = 50` draws, fresh under seed `20260923` | the class's **representative calibration windows'** own epochs |
| **C1** GEOM | AR(1) at `phi_c` | the Family-I **audit** window's own epochs |
| **C2** PHI | AR(1) at `phi_w`, the **window's own** lag-1 autocorrelation of its post-cubic residual, clipped to `[0, 0.999]` exactly as the committed code clips the class median | own |
| **C3** ARP | AR(8), Yule-Walker coefficients fitted to the window's **own** post-cubic residual, generated in index order | own |
| **C4** LINES | C1's generator **plus one injected sinusoid** (section 3), amplitude ladder `a in {0.05, 0.10, 0.20, 0.40}` | own |
| **C4b** LINE-14 | as C4 at `a*`, but at the **treated** class's measured 14.00 d period and dispersion. DECLARED SECONDARY | own |
| **C5** ARP+LINES | C3's generator plus the section-3 line at `a*` | own |
| **CR** REAL | the real `mean_motion` series, through `_detrend_and_normalise` exactly as the committed audit stage reads it | own |
| **CZ0** FLOOR | AR(1) at `phi = 0` (white) | own |
| **CZ+** CEILING | AR(1) at `phi in {0.9990, 0.9999}`, a two-point ladder | own |
| **P0** PREVIEW-CONTROL | AR(1) at `phi_w` — the **pseudo-data**, judged by the per-window null built from the same `phi_w` | own |
| **P1** PREVIEW-REAL | the **real** series, judged by the per-window null built from that window's own `phi_w` | own |

C0's draws reproduce the committed budget exactly — `R = 24`, `S = 50`,
`B_s = 1,200` per class — under a different seed. It is therefore a fresh sample
from the **same distribution the threshold was estimated from**, which is what
makes it a positive control that must calibrate by construction.

`phi_w` for an audit window is computed by the committed
`matched_filter_rung2.lag1_autocorrelation` on the committed
`_detrend_and_normalise` residual. It is a Rung-3 ingredient, used here as a
*generator* in C2/P0 and as a *null parameter* in P0/P1; it never enters a
Family-I threshold, which remains the committed class threshold throughout.

### 2.4 The Family-II null

For each Family-II window: `B = 200` AR(1) draws at `phi_w` on that window's own
epochs, `peak F` for each, `tau_w` = the 99th percentile, same method. P1 tests
the **real** window against `tau_w`; P0 tests a **201st, independent** AR(1)
draw at the same `phi_w` on the same epochs against the same `tau_w`.

`B = 200` puts two draws above the 99th percentile, so `tau_w` is an order
statistic with real sampling error. That error is reported as the spread the
budget alone induces on the pooled exceedance, by the same nested bootstrap the
Rung-2 registration used (500 resamples of each window's 200 draws). **If that
spread alone is comparable to the width of `[0.5%, 2.0%]`, the Family-II verdict
is declared UNRESOLVED AT THIS BUDGET rather than reported as a pass or a fail.**

---

## 3. The injected line — periods, dispersion, and the amplitude rule

### 3.1 Which line, and why it is not the 14.00 d one

The class being screened is **passive**. Its measured in-band line content, from
the pilot's own committed census
<!-- src: docs/cadence-results-20260921-lines.json profile.passive.targets -->,
restricted to the registered band `[2 d, 143.75 d]`:

| target | period (d) | local excess | core peaks | local expectation |
|---|---:|---:|---:|---:|
| anomalistic month | 27.555 | **8.171** | 2,336 | 285.9 |
| sidereal month | 27.322 | 7.337 | 2,068 | 281.9 |
| solar rotation (synodic Carrington) | 27.275 | 7.337 | 2,068 | 281.9 |
| half synodic month | 14.765 | 1.608 | 121 | 75.2 |
| half sidereal month | 13.661 | 1.122 | 93 | 82.9 |
| synodic month | 29.531 | 0.565 | 300 | 530.9 |
| controls 21 d / 40 d / 70 d | — | 0.511 / 0.761 / 0.162 | — | — |

The three 27 d targets lie within **0.28 d** of one another against a core
half-width of **0.4218 d**: on this grid they are one unresolved line, and the
census cannot say which of the three physical periods it is. The thermospheric
semiannual line at 182.6 d, the largest excess in the passive class at 38.4x,
is **outside** the registered band, which is what the band top at 143.75 d was
chosen to do.

**REGISTERED: the injected line is the 27.5 d family.** Its period is drawn
**per object**, uniformly on the measured family span `[27.275 d, 27.555 d]`,
from a stream seeded by `(20260923, norad)`; its phase is drawn uniformly per
window. That implements per-object period dispersion on the class that is
actually being screened.

**DEVIATION FROM THE BRIEF, DECLARED.** The task that commissioned this
experiment names the 14.00 d east-west and north-south lines with per-object
dispersion 13.89-14.10 d. Those are the **treated** class's lines — the 208
station-kept east-west carriers and the 56 north-south comsats. The screen whose
residual is being attributed is computed on the **passive control class**, in
which the census measures the 14.00 d neighbourhood at an excess of 1.6x and
1.1x (the half-month lines) and gives 14.00 d itself no target at all. Injecting
a 14.00 d carrier line into a passive-class surrogate would attribute a residual
to a feature the class is not measured to have. The 14.00 d line is therefore
run as **C4b, a declared secondary arm** whose purpose is sensitivity, not
attribution, and whose result is excluded from the decomposition of section 4 by
this registration.

### 3.2 The amplitude, and why it must be calibrated rather than cited

**No amplitude is published anywhere in this programme for these lines.** The
census publishes *prevalence* — how many windows peak in the line's core — not
power. An amplitude cannot be cited, so it is **calibrated to reproduce the
published prevalence**, on a registered ladder, and the calibration is part of
the result rather than an input to it.

> **REGISTERED `a*` RULE.** For each ladder rung `a`, define the arm's
> **line-core prevalence**: the fraction of C4 pseudo-windows whose `peak F`
> fundamental lies within `+-0.4218 d` (the census's own core half-width) of that
> window's injected period. `a*` is the **smallest** ladder rung whose line-core
> prevalence reaches or exceeds the census's measured passive core prevalence,
> **2,336 / 217,323 = 1.0749%**. If no rung reaches it, `a* = 0.40` and the
> shortfall is published as a shortfall. If the lowest rung already exceeds it,
> `a* = 0.05` and the overshoot is published. The ladder's full prevalence and
> exceedance curve is published either way, so the reader sees the floor
> (`a = 0`, which is arm C1) and the ceiling (`a = 0.40`).

`a` is in units of the generated series' own RMS, i.e. a line-to-noise amplitude
ratio, which is the only scale `F` responds to.

### 3.3 The a-priori bound this registration commits to BEFORE running

Design 5.2(c)'s lesson — *compute the point estimate before buying the compute* —
applied to the line candidate. Under the assumption that a window can only be
pushed over its threshold **by the line** if its peak lands **on** the line, the
census bounds the line term directly:

| | extra windows over local expectation | of 217,323 |
|---|---:|---:|
| 27.5 d family (anomalistic month row) | 2,336 - 286 = **2,050** | **0.943%** |
| half synodic + half sidereal | (121-75) + (93-83) = **56** | 0.026% |
| **total in-band line excess** | | **0.969 pp** |

> **REGISTERED PREDICTION: `T_lines <= 0.97` percentage points.** The line
> candidate of results 2.4(1) **cannot** account for more than about one of the
> 8.8 residual points. If the measurement returns `T_lines` materially above
> 0.97 pp, that is a finding against the census's own reading and is reported as
> one, not quietly absorbed.

This prediction is falsifiable, it is committed before the instrument exists,
and it is the reason the line arms are not the centre of this experiment.

---

## 4. The decomposition — registered arithmetic, fixed before any number

Write `e(X)` for arm `X`'s window-level exceedance against its arm's threshold,
with its clustered 95% interval. All terms are differences of point estimates;
each carries an interval from a **paired** object-level bootstrap over the
Family-I object set (the arms share windows, so the pairing is exact and is what
makes a 0.5-point difference readable at all).

| term | arithmetic | what it is | would Rung 3 buy it? |
|---|---|---|---|
| `T_geom` | `e(C1) - e(C0)` | within-class sampling-geometry heterogeneity: the class's thresholds were built on 24 representative windows' geometry and are applied to every geometry in the class | **YES** |
| `T_phi` | `e(C2) - e(C1)` | within-class noise-parameter heterogeneity: one `phi_c` per class applied to windows whose own `phi_w` varies | **YES** |
| `T_family` | `e(C3) - e(C2)` | AR(1) is the wrong noise **family**, independent of whose `phi` it uses | **ONLY IF** Rung 3's surrogate is richer than AR(1) — which the design does not specify |
| `T_lines` | `e(C4 at a*) - e(C1)` | real in-band line structure | **NO** — no rung contains a line |
| `E_total` | `e(C5)` | everything the richest pseudo-generator reproduces | — |
| `U` | `e(CR) - e(C5)` | **UNEXPLAINED** | — |

**Two honesty clauses, registered in advance.**

1. **C3's generator is fitted to the real residual**, so an 8-pole model will
   absorb whatever real in-band structure it can represent, including a line.
   Therefore `T_family` is an **upper bound** on the pure noise-family term and
   `T_lines` a **lower bound** on the pure line term. The terms are not
   orthogonal and this registration does not claim they are.
2. **The design does not define Rung 3's surrogate mechanism.** Design 5.3 says
   "surrogates per object, `B = 200`" and names no noise model. This experiment
   therefore measures an **AR(1) Rung 3** directly (P1) and reports `T_family`
   as the increment a richer family would have to buy. Any claim about "Rung 3"
   below means the AR(1) construction unless it says otherwise.

---

## 5. Instrument-validity gates — read the floor and the ceiling FIRST

The phase diagnostic's lesson, in this experiment's own terms: *"The floor is
not a floor"* (results 3.1). No arm in section 4 may be interpreted until all
four gates below have been read and published.

| gate | arm | requirement | if it fails |
|---|---|---|---|
| **G-ORACLE** | C0 | its 95% clustered interval **contains 1.00%** | the class-threshold instrument is defective; **no Family-I number is interpretable** and the document says so in that word |
| **G-PREVIEW** | P0 | its 95% clustered interval **contains 1.00%** | the per-object instrument is defective; the Rung-3 verdict is **UNRESOLVED** |
| **G-FLOOR** | CZ0 | `e(CZ0) < 0.5%` | the diagnostic has no room to fall; every attribution is saturated and is reported as UNRESOLVED |
| **G-CEILING** | CZ+ | `e` at `phi = 0.9999` **> 2.0%**, and monotone across `{0, phi_c, 0.9990, 0.9999}` | the exceedance is insensitive to noise colour near the unit root; `T_phi` and `T_family` are then reported as **bounded below only** and the insensitivity is the finding |

G-ORACLE and G-PREVIEW are the **positive controls** the experiment is required
to carry: nulls that must calibrate by construction. CZ0 is the **negative
control**: a null known to be wrong, in a known direction (white pseudo-data
judged by thresholds built for `phi = 0.9958` noise must fall far below 1%). CZ+
is the negative control in the opposite direction.

---

## 6. Blind spots, declared in advance

1. **This experiment cannot distinguish "real in-band structure the census did
   not name" from "noise colour AR(8) reproduces".** C3 is fitted to the real
   residual; that is the price of a generator that is not a guess. The
   unexplained term `U` is what neither reaches.
2. **AR(p) in index order is not AR(p) in time** on an irregularly sampled
   window. The committed Rung-2 registration declared the same approximation for
   AR(1) (its 2.8(2)); it is inherited, not newly excused. The median passive
   spacing is 0.95 d and admissibility bounds the largest gap at 45 d.
3. **`B = 200` and `R x S = 1,200` are prototype budgets**, below any published
   Rung-3 cost model. Section 2.4's unresolved clause is the guard.
4. **The one-harmonic statistic is not the design's detector**, and a verdict
   obtained with it does not automatically transfer to an 18-member bank whose
   look-elsewhere factor is larger. Inherited from the parent registration 2.8(3)
   and restated because this experiment's verdict is about to price a decision.
5. **Passive is not payload.** Nothing here measures what the treated class does.
6. **The Family-II object set is a 300-object subsample.** If a per-object null
   calibrates on it, that is evidence it calibrates, not proof it calibrates on
   all 5,485 audit objects; the interval carries that.
7. **Wall-clock timings in the result are NOT a throughput measurement.** The
   broker may co-tenant these jobs with another session's work, and co-tenancy
   has been measured on this host to cost 15.6x. No card-speed or
   windows-per-second claim will be made from this run.

---

## 7. THE RUNG-3 DECISION TABLE — fixed before any number exists

The acceptance band for "calibrates" is design 5.3's own screen, `[0.5%, 2.0%]`,
read from the **point estimate**, with the interval published beside it and any
straddle of a boundary stated in those words.

| outcome | reading | what it means for the Rung-3 spend |
|---|---|---|
| **P0 gate fails** | the per-object machinery is not validated | **UNRESOLVED.** No recommendation. Do not spend. |
| **P1 inside `[0.5%, 2.0%]`**, P0 gate passes | a per-object AR(1) null **calibrates** on this archive | The ladder's answer was right and the decomposition's 0.9-point reading was measuring something else. **Rung 3 is bought**, and this experiment says so against its own prior. |
| **P1 > 2.0%**, P0 gate passes | a per-object null does **not** calibrate although its machinery is sound | **Rung 3 is REFUSED.** The miscalibration is structural and 8,860 GPU-hours a sweep buys none of it. |
| **P1 < 0.5%**, P0 gate passes | the per-object null is over-conservative at `B = 200`: thresholds too high, detector blind | **Rung 3 is REFUSED** as specified, with the budget named as the suspect and the re-run at larger `B` named as the cheap next step. |
| `T_family >= 0.5 x (e(CR) - 1%)` | AR(1) is the wrong family, and the design's Rung 3 is AR(1) | **Rung 3 is REFUSED even if P1 is borderline.** The surrogate family is redesigned before any rung is bought. |
| `T_lines > 0.97 pp` (the section-3.3 prediction broken) | the line candidate is larger than the census says | the census is re-read; no rung buys a line, so this is a **detector** problem (a line veto), not a **null** problem. |
| `U` is the largest single term | the residual is not any of results 2.4's three candidates | published as **UNRESOLVED** in that word, with `U`'s size, and no rung is recommended. |
| **G-FLOOR or G-ORACLE fails** | the diagnostic itself is not readable | **UNRESOLVED.** Everything above is withheld. |

**The registered rule that binds this session:** whichever row fires, it is
reported. A second run is permitted only to fix a **defect**, must be reported
as a defect fix with the defect named, and the superseded number is published
alongside. Re-running any arm with a different generator, amplitude, exposure,
band or percentile after a number is visible is prohibited.

---

## 8. Resources, and the honest estimate

All GPU work goes through `/home/sdegan/gpu-broker/gpu-run`, class `standard`,
`--estimate-mib 1800` against the parent run's measured peak of 1,437.8 MiB and
the design's 2 GiB device cap. `CUDA_VISIBLE_DEVICES` arrives as a GPU UUID and
is never parsed as an integer. The measured peak CuPy pool is published per
stage; if any stage exceeds its claim that is reported as a defect.

| family | windows evaluated | derivation |
|---|---:|---|
| Family I, single-draw arms (C1, C2, C3, C4b, C5, CR, CZ0, CZ+ x2) | ~180,000 | 9 arms x 20,000 |
| Family I, C4 amplitude ladder | ~80,000 | 4 rungs x 20,000 |
| Family I, C0 oracle | 72,000 | 60 classes x 24 x 50 |
| Family II, P0 + P1 nulls | ~480,000 | 1,200 windows x 200 draws x 2 arms |
| **total** | **~812,000** | |

Against the parent's measured rates — 28 windows/s on the mixed-geometry apply
path, 58 windows/s on the shared-geometry surrogate path — that is about
**5 to 6 GPU-hours**, shardable across the two cards.

> **STOP RULE.** If the total exceeds **10 GPU-hours**, the run stops, the
> completed arms are published with their exposure, and the incomplete arms are
> named as incomplete. A calibration experiment that costs a tenth of what it is
> auditing has failed at its own purpose.

Compare: **one Rung-3 sweep is about 8,860 GPU-hours.** This experiment is about
**1/1,600** of it.

---

## 9. Deliverables

1. This registration, committed **alone**.
2. `tools/rung2_separation.py` and `tests/test_orbit_rung2_separation.py` —
   offline tests only: no archive, no GPU, no network. Committed before any
   registered arm runs.
3. `docs/matched-filter-rung2-separation-results-<date>.md` and its JSON
   receipt, carrying every gate, every arm, every term of section 4, the
   Rung-3 decision row that fired, the realised exposure, the measured GPU cost
   and peak pool, and every deviation.
4. A discharge row in `docs/research-program-runbook-20260921.md` section T5.

---

## 10. Honest summary of what this document commits to

A failed screen was explained by a control arm, and the explanation cost 0.9
points out of 9.7. The programme's registered ladder answers the failure by
buying the 0.9-point term for 8,860 GPU-hours a sweep. This experiment builds
pseudo-data whose generator is known, one ingredient at a time, and asks which
ingredient the 8.8 unexplained points belong to — and it runs the per-object
null the ladder would buy, at prototype exposure, so that the answer to *"does
Rung 3 calibrate"* is a measurement rather than an inference from a ladder.

Two positive controls must calibrate by construction or nothing is read. A
negative control must fall far below 1% or the diagnostic is saturated. The line
candidate carries a falsifiable a-priori bound of 0.97 percentage points,
committed here, before the instrument that tests it exists.
