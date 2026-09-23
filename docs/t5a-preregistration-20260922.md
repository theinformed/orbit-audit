# T5a PRE-REGISTRATION — the scaled matched-filter run

## FAIL-RECORD, and a single confirmatory experiment

**Committed: 2026-09-22 (UTC). Committed ALONE, ahead of any registered run.**

This registration is written after a prototype reading and before any scaled
run, which is the order `docs/matched-filter-design-20260922.md` section 5.2(c)
fixes: *"the point-estimate separation from the prototype is computed and
published BEFORE the scale run"*. That reading is
`docs/t5a-redesign-results-20260922.md`, commit `ab4fee9`, and its
first line is

> **THE NEW STATISTIC DOES NOT BEAT ONE HARMONIC ON THE TREATED CLASS.**

So this document is a **FAIL-RECORD** for the statistic the Rung-2
phase-coherence diagnostic prescribed, plus the one confirmatory experiment
that the same reading makes worth running. Every threshold below is set FROM
the measured numbers and every one of them is fixed here, before the
confirmatory arm exists.

Nothing was tuned. The prescribed statistic was implemented as written, run
once, and reported.

---

## 0. What is registered and what is refused

| | |
|---|---|
| **REFUSED** | the T5a scaled campaign on the prescribed statistic (per-object refined fundamental, coherent whole-history stacking, free-phase harmonic power sum at `k <= 3`). No HPC hour and no local GPU hour may be spent running it at catalogue scale. |
| **REFUSED** | the design's five-harmonic sawtooth matched filter, at any scale, on either amplitude-sign convention. |
| **REGISTERED** | ONE confirmatory experiment, section 4: does coherent whole-history stacking of the ONE-HARMONIC statistic at a FIXED 14.00 d fundamental hold its separation on channels and halves that did not generate the hypothesis? |
| **NOT REGISTERED** | anything else. In particular no recall measurement, no per-object null at any rung, and no Rung-3 spend. |

---

## 1. The measured numbers this registration is built on

All from `docs/t5a-redesign-results-20260922.json`, committed at
`ab4fee9`. Channel `mean_motion`; 208 east-west carriers against the
same-shell GEO passive control; separation is the ratio of the two populations'
median statistic, which is invariant to the degree-of-freedom convention
(`tests/test_orbit_matched_filter_v2.test_separation_is_invariant_to_the_dof_convention`).

**On the prototype's own footing — one number per T3 window:**

| arm | carrier median | control median | separation |
|---|---:|---:|---:|
| one harmonic, fixed 14.00 d (the pilot's template) | 4.4664 | 0.4034 | **11.072** |
| the prescribed statistic, `free3`, fixed 14.00 d | 4.3609 | 0.5672 | **7.689** |
| sawtooth `k = 5`, fixed 14.00 d | 6.2709 | 0.8053 | 7.787 |
| one harmonic, per-object REFINED | 6.8991 | 0.8762 | 7.874 |
| the prescribed statistic, per-object REFINED | 4.3238 | 0.6615 | 6.536 |
| *prototype's published one-harmonic separation* | *8.634* | *0.807* | *10.705* |
| *prototype's published sawtooth `k = 5`* | *13.271* | *1.611* | *8.239* |

**On the statistic's own footing — one number per OBJECT, whole history
coherently stacked:**

| arm | carrier median | control median | separation |
|---|---:|---:|---:|
| one harmonic, fixed 14.00 d | 42.0545 | 0.3657 | **115.006** |
| `free2` (`k <= 2`), fixed | 42.0122 | 0.6694 | 62.763 |
| the prescribed statistic `free3`, fixed | 32.7739 | 0.6343 | **51.666** |
| sawtooth `k = 5`, fixed, non-negative amplitude | 56.6633 | 0.7842 | 72.252 |
| sawtooth `k = 5`, fixed, amplitude sign FREE | 65.0026 | 1.0797 | 60.202 |
| one harmonic, per-object REFINED | 76.0593 | 1.5823 | 48.069 |
| `free2`, refined | 45.4359 | 0.9966 | 45.590 |
| the prescribed statistic `free3`, REFINED | 32.5482 | 0.8443 | **38.549** |
| sawtooth `k = 5`, refined | 61.8586 | 1.4359 | 43.081 |

Paired, within-unit, at the fixed fundamental on the stacked footing
(median dB, and the fraction of units the arm improves):

| arm over one harmonic | carriers | control |
|---|---:|---:|
| `free3` (the prescribed statistic) | **−2.757 dB** (16.8%) | +2.046 dB (63.1%) |
| `free2` | −1.573 dB (26.0%) | +1.858 dB (63.1%) |
| `free1` (consistency arm) | 0.000 dB | 0.000 dB |
| sawtooth `k = 5`, non-negative amplitude | −0.396 dB (47.1%) | +2.854 dB (79.9%) |
| sawtooth `k = 5`, sign free | +1.539 dB (85.1%) | +4.130 dB (94.2%) |

---

## 2. Why the prescribed statistic failed, clause by clause

The Rung-2 diagnostic prescribed four things together. Measured separately,
**two of the four cost separation and one of them is worth more than everything
else in the track put together.**

1. **Coherent whole-history stacking — the one clause that works, and it is
   large.** The one-harmonic statistic goes from 11.072 per window to
   **115.006 per object** when the object's disjoint 1080 d tiles are stacked
   coherently at a common absolute epoch. That is the entire gain available in
   this reading and it is not a matched filter: it is the pilot's own template,
   stacked.

2. **Per-object refinement — costs.** Choosing each object's own fundamental by
   maximising its own coherent power over the 30 candidates inside T3's
   published 14.00 d core lifts the CARRIER median 1.81x and the CONTROL median
   **4.33x**, so the separation falls from 115.006 to 48.069. The mechanism is
   plain and was anticipated: a maximum over 30 candidates is a selection, and a
   population with no line gains more from a selection than a population with
   one. Rung-2 section 3.3 flagged the same circularity for `T_coh`; it is here
   too, and for a detection statistic it is not recoverable by taking a
   different ladder.

3. **Harmonics as a free-phase power sum at `k <= 3` — costs, monotonically.**
   115.006 (`k = 1`) -> 62.763 (`k <= 2`) -> 51.666 (`k <= 3`). Every harmonic
   added costs separation. The paired reading says why: on the carriers `free3`
   is −2.757 dB against one harmonic while on the control it is **+2.046 dB**.
   The extra harmonic pairs pick up broadband structure both classes carry and
   charge both classes for it; the treated class, whose power is concentrated in
   the fundamental, pays more than it collects. This is the prototype's section
   4.3 mechanism measured on a different statistic.

4. **A free `k = 2` relative phase — buys nothing measurable, and the mechanism
   the diagnostic named is not the one that operates.** Rung-2 section 3.4 read
   the carriers' `psi_2 = pi` as a mechanical explanation of the sawtooth's
   loss. `tests/test_orbit_matched_filter_v2.TestTheAntiPhaseSecondHarmonic`
   shows on an exact synthetic that it is only half true. The template rotates
   harmonic `k` by `k phi`, so `phi -> phi + pi` flips every ODD harmonic and
   leaves the even ones: a waveform whose second harmonic is inverted is the
   same template at a half-period shift with the amplitude's sign flipped.
   Under a sign-free search the inversion costs **exactly nothing**
   (`test_but_a_sign_free_search_recovers_it_exactly_and_the_loss_vanishes`).
   It costs only under the non-negative-amplitude convention the prototype
   adopted for phase uniqueness — which is a MODEL constraint once a template
   carries harmonics of both parities, and was never registered as one.

   Measured on the archive, that correction is worth **1.935 dB** on the
   carriers (sawtooth `k = 5`: −0.396 dB with the sign constrained, +1.539 dB
   with it free) — and design section 3.5's own prediction for an ideal sawtooth
   is +1.65 dB. **The sawtooth template delivers about the response gain the
   design derived, once it is allowed a negative amplitude.** It still loses the
   SEPARATION, because the control gains +4.130 dB from the same freedom.

**The summary the registration acts on: response gain and separation are not
the same quantity, and every template enrichment measured in this programme
raises the control more than it raises the treated class.**

---

## 3. The instrument, frozen

| | |
|---|---|
| statistic | `tools/matched_filter_v2.py` at commit `77323f1` |
| driver | `tools/matched_filter_v2_run.py` at the same commit |
| offline proof | `tests/test_orbit_matched_filter_v2.py`, 47 assertions, no archive, no GPU, no network |
| segment geometry | DISJOINT 1080 d tiles from each object's first epoch; T3's four registered admissibility conditions applied to a tile |
| nuisance basis | the registered cubic, one block per tile, carried INSIDE the fit |
| conditioning | float64 host-side polynomial removal then unit residual RMS per tile |
| phase origin | the absolute epoch `T_REF_MS = 0` |
| fundamental | index 1929 on `df' = 1/(25 x 1080) c/d`, i.e. 13.99689 d |
| precision | float32 on the device for the reduction; float64 on the host for the stack |
| measured peak device pool | 220.0 MiB (stacked footing), 218.4 MiB (window footing), 701.9 MiB (dense band slice), 895.0 MiB (chunked device solve) -- every one sampled with the batch still live |

No parameter above may be varied under this registration. A change to any of
them is a different experiment and needs its own registration.

---

## 4. THE ONE CONFIRMATORY EXPERIMENT

### 4.1 The hypothesis, falsifiable, in one sentence

> Coherent whole-history stacking of the ONE-HARMONIC statistic at the FIXED
> 14.00 d fundamental separates station-keeping carriers from a same-shell
> passive control by a factor whose 95% lower bound exceeds 10, on populations
> and a channel that did not generate that hypothesis.

The alternative it is tested against is registered with it: that the separation
measured in section 1 is an artefact of the population the pilot selected, of
the control the prototype happened to use, or of the `mean_motion` channel.

### 4.2 Populations, fixed now

| arm | treated | control |
|---|---|---|
| **A (primary, held-out channel)** | the 56 north-south `inclination` carriers of `docs/matched-filter-devset-20260922.json` | the same-shell GEO passive control of the same file, restricted to the HELD-OUT passive audit half |
| **B (held-out control half)** | the 208 east-west `mean_motion` carriers | the same-shell GEO passive control restricted to the HELD-OUT passive audit half |
| **C (negative control)** | the same 208 carriers, `eccentricity` channel | the same held-out control |

Arm C must NOT separate. T3 measured eccentricity ABSENT at equal prominence
(`docs/cadence-results-20260921.md`), so a detector that separates the classes
in eccentricity is measuring the classes and not the line, and arm A's result
is void whatever it says. This is the instrument-validity gate and it is read
FIRST.

The passive half assignment is T3's own, carried in the `half` field of
`t3-cadence/full/index.json` from `core.SEED = 20260921` and
`core.SPLIT_SALT = "t3-20260921"`; it is not recomputed here. **Counted before
this registration was committed**, the 331-object same-shell GEO passive control
splits **183 calibration / 148 audit**, so every control arm above has
**n = 148 objects** before tile admissibility, against the 328 the reading used.
That is a real loss of control precision and it is accepted rather than traded
away: a control half that helped build the reading is not a control.

### 4.3 The statistic, fixed now

`tools/matched_filter_v2.template_power` with `W = (W_1,)`,
`positive_amplitude=True` (at one harmonic the two conventions are identical and
`test_the_two_conventions_agree_at_one_harmonic` asserts it), stacked over the
object's disjoint admissible tiles, at index 1929 and no refinement.

The prescribed statistic `free3` and the sawtooth `saw5` are run on the same
arms FOR THE RECORD, so the refutation of section 2 is itself tested out of
sample. They are not candidates.

### 4.4 Estimand and estimator

- **Estimand:** `S = median F(treated objects) / median F(control objects)`.
- **Estimator:** the plug-in ratio of medians. Interval: a nonparametric
  bootstrap resampling OBJECTS (never tiles and never windows — tiles within an
  object are not independent), 10,000 resamples, stratified by the rung-2
  sampling-geometry class of the object's median tile, percentile interval at
  95%.
- **Reported:** point estimate, interval, both population medians, both
  populations' deciles, and the object counts. No other quantity is reported as
  a result.

### 4.5 The null, and there are two

1. **Label permutation (is there a class difference at all).** Permute the
   treated/control labels across objects WITHIN sampling-geometry class,
   10,000 permutations, recompute `S`. Report the permutation p-value and the
   null's 99th percentile of `S`.
2. **Phase-destroying surrogate (is the STACKING gain real coherence).** For
   each object, circularly shift each tile's absolute clock independently by a
   uniform random offset in `[0, P0)`, which destroys the cross-tile phase
   relation and preserves every tile's own spectrum, sampling and noise;
   recompute `S`. 200 surrogates, the design's own `B`.

Null 2 is the one that matters, and it is registered in advance as the arbiter
of the stacking claim: **if `S` under the phase-destroying surrogate is not
materially below the measured `S`, the gain is not coherence and the claim
fails** whatever null 1 says. "Materially below" is fixed in 4.6, not judged
afterwards.

### 4.6 The bar, set FROM the measured numbers

Every threshold here is fixed before the confirmatory arm exists. Each is a
SCREEN, not a law; each names what fixes it.

| # | gate | threshold | where the number comes from |
|---|---|---|---|
| G1 | instrument validity: arm C (eccentricity) separation | point estimate **< 3.0** | T3 measured eccentricity ABSENT at equal prominence; 3.0 is well below the 10x gate and well above the 1.0 a perfectly null channel would give, so it screens a broken instrument without pretending to measure one |
| G2 | arm A (held-out channel) separation, 95% lower bound | **>= 10.0** | Paper B's registered separation gate, unchanged |
| G3 | arm A separation, point estimate | **>= 18.0** | the prototype measured the `inclination` line at 28.28x local excess against `mean_motion`'s 90.44x, a ratio of 0.313; 0.313 x 115.006 = 36.0 is the transfer this reading implies, and the bar is set at half of it. A SCREEN chosen for tolerance, not a prediction |
| G4 | arm B (held-out control half) separation, point estimate | **>= 57.5**, i.e. half of the 115.006 measured here | a held-out control half that halves the separation would mean the control the prototype used was unrepresentative; the factor 2 is a tolerance, not a derivation, and is declared as one |
| G5 | phase-destroying surrogate, arm A | measured `S` **>= 3x** the surrogate null's median `S` | if destroying the cross-tile phase costs less than a factor of 3, the "coherent stacking" claim is not supported by its own mechanism test. The factor is a screen; the DIRECTION is the registered content |
| G6 | the refutation, tested out of sample | `free3` separation **< ** `one` separation on arm A | section 2's finding, retested on data that did not generate it. If this fails, the FAIL-RECORD is itself refuted and section 2 must be rewritten |

**PASS requires G1 and G2 and G3 and G5.** G4 and G6 are recorded and reported
whatever they do; G4 failing alone downgrades the claim to "measured on this
control only" rather than voiding it.

### 4.7 Seed and budget

- Seed for every resample, permutation and surrogate: **20260922**, fixed here.
- Exposure: the development set plus the held-out passive audit half, one
  channel at a time.
- Budget, derived rather than asserted: the stacked history footing measured
  **25.8 s of device reduction and 220.0 MiB of peak pool for 3,162 tiles** on
  the 301-point refinement axis. Arm A is 56 + 148 = 204 objects, about 1,200
  admissible tiles, so one pass is about **10 s**. The 10,000 bootstraps resample
  already-computed per-object statistics on the host and cost no device time at
  all. The 200 phase-destroying surrogates each need a full re-reduction, so
  `200 x 10 s = 2,000 s`. Three arms and three channels put the whole
  confirmatory experiment **well under 2 GPU-hours**. It buys no HPC time and
  asks for none. EXTRAPOLATION from the measured rate, labelled as one.
- Device claim: `--estimate-mib` at or above the measured peak, `gpu-run`,
  never co-tenanted with another job of this programme's own when a timing
  number is being taken.

### 4.8 The decision table, fixed before any number

| outcome | what happens |
|---|---|
| G1 fails | arm A is VOID. Nothing is claimed; the instrument is debugged and a new registration is written. |
| G1 passes, G2+G3+G5 pass | the stacked one-harmonic statistic is a measured result. It is written into Paper C as what the matched-filter track actually produced, explicitly NOT as a matched filter. A scaled run may then be registered separately; this registration does not authorise one. |
| G2 or G3 fails | **T5a FAILS.** See section 5. |
| G5 fails | the separation is reported as a class difference of unknown mechanism, never as coherence, and T5a still FAILS as a matched-filter track. |
| G6 fails | section 2 of this document is wrong out of sample and is rewritten before anything else happens; the prescribed statistic is reinstated as a candidate and needs its own registration. |
| anything is UNRESOLVED at this exposure | it is reported as UNRESOLVED in those words. There is no third run to break a tie. |

---

## 5. What a FAIL means for Paper C

Paper C is the matched-filter detector-generation paper
(`docs/research-program-runbook-20260921.md`, T5 roster). If the confirmatory
experiment fails at G2 or G3, then:

1. **Paper C cannot claim a matched-filter detector improvement.** Two template
   families derived from the physics — the one-burn deadband sawtooth and the
   harmonic power sum the data's own phase structure prescribes — have now been
   measured against the pilot's bare sinusoid on the only line this programme
   has, on two footings, and both lose the separation. That is the result.
2. **The paper's content becomes the negative result plus the mechanism**, which
   is publishable and is not a consolation: a physically derived template family
   measurably HURTS detection because the archive's noise carries the harmonics
   the template weights, and the control gains more from template enrichment
   than the treated class does. Sections 1 and 2 above are that measurement.
3. **The T5a workload is withdrawn from the HPC package.** The compute posture
   in the runbook says the T5a campaign is invalidated until the prescribed
   statistic beats one harmonic on the treated class; it does not, so the
   withdrawal is now permanent for this statistic rather than pending. The HPC
   evaluation paper re-selects its workload from T5b or T5c.
4. **No third template family is proposed on this data.** Two have been
   falsified on the same 208 objects. A third fitted to the same objects would
   be a search over template families with no accounting, which is the failure
   mode this programme has a registration discipline to prevent.

If the confirmatory experiment PASSES, Paper C's claim is the stacking result
and it is stated as such: coherent whole-history stacking of the pilot's own
one-harmonic statistic, at a fixed fundamental, with the template question
answered in the negative.

---

## 6. Declared deviations, and what stays UNPROVEN

**Deviations from the design and from the Rung-2 prescription, each named:**

1. The prescribed statistic's harmonics are fitted JOINTLY (a `2K`-parameter
   free-phase least-squares fit) rather than as a literal sum of marginal
   harmonic powers. The two coincide when the harmonic columns are orthogonal;
   the reading measures that they are, at a median ratio of 1.003 on the
   carriers, so the deviation is numerically inert and is declared for the
   record.
2. The stacking segments are DISJOINT 1080 d tiles, not T3's overlapping
   windows. Stacking overlapping windows would count two thirds of every sample
   twice.
3. Each tile is scaled to unit residual RMS before stacking. That is an
   inverse-noise weighting and it is the convention
   `tools/matched_filter_phase` already uses, but it is a CHOICE: a tile that
   carries a large signal is divided by a larger number.
4. The sawtooth comparator is reported under BOTH amplitude-sign conventions.
   The prototype's numbers are the non-negative one.
5. Only `mean_motion` was measured in the reading. The `inclination` channel is
   the confirmatory arm precisely because it was held back.

**UNPROVEN, in that word:**

1. **Recall is unproven.** No injection-recovery arm was run, here or anywhere
   in this track. Every separation in this programme is a contrast between two
   populations and none of them is a detection probability.
2. **The carrier set is pilot-selected and the circularity is unproven to be
   harmless.** The 208 carriers are exactly the objects whose pilot peaks landed
   in the 14 d core. The paired within-unit comparisons are immune to it; the
   separations are not.
3. **The catalogue-wide admission rate for disjoint tiles is unproven.** The
   sweep cost divides T3's registered window count by the 1080/360 overlap
   factor. That is arithmetic on the registered geometry, not a tile census.
4. **The 18-member bank was never priced under this statistic** and is not
   registered; the reading compares four arms, not eighteen.
5. **The per-tile Nyquist ceiling uses median spacing**, which is not a window
   function. The prototype recorded the same defect and it is inherited.
6. **No null of any kind has been computed.** Section 4.5 registers two; neither
   has been run.
7. **The 0.313 channel-transfer ratio behind G3 is an analogy, not a
   derivation.** It is a ratio of line excesses, used to set a tolerance.
8. **Nothing about the HPC platform is proven.** No T5a workload has ever run on
   it.

---

## 7. Anti-tuning clauses, binding

1. No arm, threshold, population, statistic or channel may be added or changed
   after any confirmatory number exists.
2. If the confirmatory experiment fails, this registration does NOT license a
   re-parameterisation, a different `k` ceiling, a different segment length, a
   different weighting or a different refinement rule. Any of those is a new
   registration with its own bar, written before its own numbers.
3. The reading in section 1 is a PROTOTYPE READING and may never be cited as a
   registered result, including in Paper C.
4. This document is committed ALONE, before the confirmatory experiment is
   implemented.

---

## 8. AMENDMENT 1 — four resolutions, written before the confirmatory run

**Committed 2026-09-22 (UTC), ALONE, before the confirmatory experiment was run
and before any confirmatory number existed.** Written by a different session from
the one that wrote sections 0–7, which is deliberate: the experiment is executed
as registered, not improved. Section 7's anti-tuning clauses bind this amendment
too, and nothing here adds, removes or moves an arm, a population, a channel, a
statistic, a threshold, a gate or the seed. What it does is fix four places where
the registration does not say enough to be executed the same way twice, plus two
conventions that would otherwise be a judgement made after seeing a number.

### 8.1 The frequency axis carries the FIXED fundamental only

Section 4.3 registers the statistic at index 1929 "and no refinement". The
reduction therefore forms the harmonic axis of that one fundamental — orders
`m = 0 .. 2K` of index 1929, eleven grid points — rather than the 30-candidate
refinement axis the prototype reading used. This is the same arithmetic
restricted to the registered column: `refine()` is not called and no selection is
taken. The 30-candidate refinement arm is NOT part of this experiment and is not
computed.

### 8.2 The stratum of an object is the class of its MEDIAN TILE BY START EPOCH

Section 4.4 stratifies by "the rung-2 sampling-geometry class of the object's
median tile" without saying which tile is the median or how a class is attached
to a tile that was never a T3 window. Both are fixed here:

1. An object's admissible tiles are ordered by start epoch and the tile at index
   `(n - 1) // 2` is the median tile. Deterministic, and it uses no statistic.
2. That tile's four registered geometry features are computed with
   `tools/matched_filter_rung2.geometry_of` and cut at the PUBLISHED calibration
   quantile edges in `docs/matched-filter-rung2-classes-20260922.json`. The tile
   is then given the finest PUBLISHED class whose label it carries, walking the
   registered merge ladder `g1g2g3g4 -> g1g2g3 -> g1g2 -> g1 -> pooled`. Neither
   the edges nor the 60 classes are recomputed, and no new class is created.
3. A tile whose label appears in none of the published classes is placed in a
   stratum named `unclassified` and that stratum is REPORTED with its size. It is
   never folded into a class that means something else. The carriers were never
   in the rung-2 passive inventory, so this is the expected home for some of
   them, and it is a labelled gap rather than a silent merge.

### 8.3 The phase-destroying surrogate, stated as arithmetic

Section 4.5 null 2 says each tile's absolute clock is circularly shifted by an
independent uniform offset in `[0, P0)`. As arithmetic: one offset per admitted
tile, drawn independently, ADDED to that tile's absolute clock — the clock the
harmonic columns are built on — and to nothing else. The tile's samples, its
values, its own local nuisance clock, its polynomial, its unit-RMS scaling and
therefore its own spectrum are untouched, which is the property that makes this
null a test of the cross-tile phase relation and of nothing else.

The surrogate is computed on all three arms and on all three statistics because
it costs little to do so; **gate G5 is read exactly where section 4.6 puts it, on
arm A's one-harmonic statistic.** The other surrogate figures are reported for
the record and no gate is attached to them.

### 8.4 Tile preparation is computed once per arm and reused by the surrogates

The conditioned values of a tile depend only on that tile's LOCAL clock, so
re-reading the archive for each of the 200 surrogates would recompute identical
numbers. Each arm prepares its tiles once and every surrogate re-runs the full
reduction, stack and statistic on the shifted clock. The re-reduction is the
registered one; only the redundant host-side re-read is avoided.

### 8.5 The resampling cells, and the p-value

- **Bootstrap.** Objects are resampled with replacement inside each
  (population, class) cell to that cell's own size, so both populations keep
  their class composition. Tiles are never resampled. Percentile interval at 95%,
  10,000 resamples, as registered.
- **Permutation.** Within each class the treated/control labels are permuted
  across the objects of that class, preserving the class's own treated and
  control counts. A class holding only one population contributes no variation;
  the number of classes that do hold both is reported beside the p-value.
- **p-value.** One-sided in the direction of the registered claim:
  `(1 + #{S_null >= S_observed}) / (1 + draws)`.

### 8.6 The degree-of-freedom convention that is reported

`F` (the per-parameter normalised ratio) is the reported statistic and `Fproto`
(the prototype's convention) is reported beside it. The separation is a ratio of
the same statistic over two populations and is invariant to the choice, which
`tests/test_orbit_matched_filter_v2.test_separation_is_invariant_to_the_dof_convention`
asserts; reporting both is a check on that invariance, not a second arm.

### 8.7 What this amendment does NOT do

It does not change any threshold in 4.6, any population in 4.2, the statistic in
4.3, the estimator in 4.4, the nulls in 4.5, the seed in 4.7 or the decision
table in 4.8. Section 5 and section 7 stand unchanged. If any resolution above
turns out to matter to a verdict, that is a finding to report, not a licence to
re-resolve it after the fact.
