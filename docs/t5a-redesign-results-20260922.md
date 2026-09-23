# T5a redesign: the prescribed statistic, measured — RESULTS

**THE NEW STATISTIC DOES NOT BEAT ONE HARMONIC ON THE TREATED CLASS.**

That is the finding, in the words the work was commissioned to report it in, and
it is the first line of this document because
`docs/matched-filter-design-20260922.md` section 5.2(c) fixes the order: the
point-estimate separation from the prototype is computed and published BEFORE
the scale run, not after. The registration that accompanies this document,
`docs/t5a-preregistration-20260922.md`, is therefore a **FAIL-RECORD**. Nothing
was tuned to make the statistic pass; it was implemented as prescribed, run
once, and reported.

**Status: PROTOTYPE READING. Nothing here is a registered result.** No p-value,
no threshold, no gate verdict, no null, no recall. It exists so that a
registration could be written with numbers in hand rather than with assumptions.

**Every number in this document is read out of
`docs/t5a-redesign-results-20260922.json`, committed beside it.** That artifact
is built by `/home/sdegan/t5a-v2/aggregate.py` from the three run artifacts and
carries the arithmetic of every derivation, so no figure here rests on prose.

---

## 0. The findings, first, in the order a reader should take them

1. **The statistic the Rung-2 diagnostic prescribed loses.** On the prototype's
   own footing its carrier/control separation is **7.689** against the
   one-harmonic baseline's **11.072** and the five-harmonic sawtooth's
   **7.787**; on the windows the pilot put on the 14.00 d line it is
   **−3.284 dB** against one harmonic, which is a deeper loss than the
   **−2.776 dB** the sawtooth takes on the same windows. On its own stacked
   footing it is **51.666** against one harmonic's **115.006**. It loses on both
   footings, on the line windows and on the control, at a fixed fundamental and
   at a refined one. There is no reading of this measurement in which it wins.

2. **The instrument reproduces the prototype almost exactly, which is what
   licenses reading 1 at all.** Built independently, on a different footing
   (disjoint tiles, absolute-epoch clock, per-tile nuisance blocks), this
   module returns the sawtooth's paired loss on the pilot's line windows as
   **−2.776 dB** against the prototype's published **−2.715 dB**, its gain on
   the same-shell control as **+2.545 dB** against the published **+2.543 dB**,
   and the one-harmonic separation as **11.072** against the published
   **10.705**. Two independent implementations of two different statistics agree
   on the prototype's headline finding to within 0.06 dB.

3. **Of the four clauses the diagnostic prescribed, exactly one is worth
   anything — and it is not a matched filter.** Coherent whole-history stacking
   of the PILOT'S OWN one-harmonic statistic, at a fixed 14.00 d fundamental,
   takes the separation from **11.072 per window** to **115.006 per object**.
   Per-object refinement costs (115.006 -> 48.069). The `k <= 3` power sum costs,
   monotonically (115.006 -> 62.763 -> 51.666). A free `k = 2` relative phase
   buys nothing measurable at all.

4. **The mechanism Rung-2 section 3.4 named for the sawtooth's loss is not the
   mechanism that operates, and the correction is worth 1.9 dB.** The inverted
   second harmonic is invisible to a matched filter that is allowed a negative
   amplitude, because rotating the template's phase by `pi` flips its odd
   harmonics and leaves its even ones. The prototype's non-negative-amplitude
   convention — adopted for phase uniqueness at one harmonic — is a MODEL
   constraint at five, and it is most of what the "anti-phase" finding was
   measuring. Given the sign back, the sawtooth delivers **+1.539 dB** on the
   stacked carriers against design 3.5's predicted **+1.65 dB** for an ideal
   sawtooth. It still loses the separation, because the control gains
   **+4.130 dB** from the same freedom.

5. **Every template enrichment measured in this programme raises the control
   more than it raises the treated class.** That is now true of the sawtooth
   (both sign conventions), of the step-train and two-burn members the prototype
   measured, and of the free-phase harmonic power sum. Response gain and
   separation are different quantities and this track has been optimising the
   wrong one.

---

## 1. What was built, and what it is not

| File | What it is |
|---|---|
| `tools/matched_filter_v2.py` | the semi-coherent statistic of Rung-2 section 3.6: the two-clock reduction (absolute trigonometric clock, segment-local nuisance clock), the per-segment nuisance projection, the exact additive stack over an object's segments, the free-phase harmonic power sum, the fixed-template comparator under both amplitude-sign conventions, the per-object refinement, and the device-memory budget. Array-module agnostic, so the offline tests and the GPU run the identical code path. No cuBLAS and no cuSOLVER call anywhere. |
| `tools/matched_filter_v2_run.py` | the bounded reading on the prototype's own development set, and the sweep-cost timing slice. It takes an explicit object file and has no catalogue default, because no registered sweep exists. |
| `tests/test_orbit_matched_filter_v2.py` | 47 offline assertions: analytic power fractions, the stacked normal system checked against an explicitly constructed full design matrix solved with `numpy.linalg`, phase and amplitude recovery, float32/float64 peak agreement, the amplitude-sign derivation, and the invariances the driver relies on. |

**`tools/matched_filter.py` and its tests are untouched.** The prototype's
numbers have to stay reproducible from the code that produced them, and finding
2 above depends on this module being an independent implementation rather than
an edit of that one.

### 1.1 The statistic, in the four clauses it was prescribed in

Rung-2 section 3.6:

> a per-object refined fundamental, coherently stacked across the whole history,
> with the harmonics entering as an incoherent POWER sum at `k <= 3` and not at
> all above it -- and with the `k = 2` relative phase treated as a FREE parameter
> rather than fixed by the sawtooth, because the data put it at `pi`.

1. **Per-object refined fundamental.** The fundamental is chosen per object by
   maximising that object's own whole-history coherent fundamental power over
   the 30 candidate indices 1915-1944 inside T3's published 14.00 d core — the
   same grid the period dispersion was measured on
   (`tools/matched_filter_phase.refined_index_candidates`, asserted identical by
   test).
2. **Coherent whole-history stacking.** The object's archive is tiled into
   DISJOINT 1080 d segments — never T3's overlapping windows, which share 720 d
   and would count two thirds of every sample twice. Each tile carries its own
   registered cubic; the harmonic columns carry ONE amplitude and ONE phase on a
   common absolute clock. The normal equations of that fit are block-diagonal in
   the nuisance, so the whole-history quantities are EXACT sums over tiles of
   the per-tile nuisance-projected inner products. That identity is the licence
   for the whole step and
   `test_the_stack_equals_one_big_design_matrix` asserts it against an
   explicitly constructed full design matrix to 1 part in `1e8`.
3. **Harmonics as a free-phase power sum at `k <= 3`.** The `k = 1..3` harmonic
   pairs are fitted JOINTLY with every phase free, costing `2 K` parameters.
   When the harmonic columns are orthogonal that is exactly the incoherent power
   sum `sum_k |c_k|^2`; the joint form is used because it is also exact when they
   are not. Measured orthogonality on the carriers: median ratio of joint to
   marginal explained power **1.0028** (p10 0.9947, p90 1.0219), so the
   deviation is numerically inert.
4. **Nothing above `k = 3`.** Rung-2 section 3.4 measured `k = 4` and `k = 5` at
   and below the null mean of 2 even in the CEILING arm, so above `k = 3` a
   template can only add norm.

### 1.2 The degree-of-freedom convention, and why the separation is immune to it

The arms carry different parameter counts — six for `free3`, two for a fixed
template — so a paired dB comparison depends on whether the explained sum of
squares is divided by its own numerator degrees of freedom. Both conventions are
computed. **A separation is not affected at all**: it is a ratio of the same
statistic over two populations, so any constant factor cancels exactly, and
`test_separation_is_invariant_to_the_dof_convention` asserts that rather than
asserting it in prose. Every separation below is identical under both; every
paired dB figure below is the `F/q` convention, which is the one that charges
an arm for its own parameters.

---

## 2. The reading, on two footings

Both footings use the same 539 development-set objects, `mean_motion`, the same
conditioning, the same instrument and the same fundamental candidates.

| | history footing | window footing |
|---|---|---|
| unit | one per OBJECT | one per T3 WINDOW |
| segments per unit | the object's disjoint admissible 1080 d tiles | one |
| carriers | 208 objects | 3,535 windows |
| control | 328 objects | 5,579 windows |
| on the pilot's 14.00 d line | n/a | 1,221 windows |
| segments offered / admitted | 4,000 / 3,162 | 11,507 / 9,114 |
| what it measures | the statistic as prescribed | the TEMPLATE change alone, on the prototype's footing |

Three objects of the 331-object control carry no admissible tile at all and are
absent from the history footing; the count is 328 and is reported rather than
rounded back up.

### 2.1 The window footing — beside the prototype's published numbers

Separation is the ratio of the carrier and control population medians at the
fixed 14.00 d fundamental (index 1929).

| arm | carrier median | control median | **separation** | median on the pilot's line windows |
|---|---:|---:|---:|---:|
| one harmonic (the pilot's template) | 4.4664 | 0.4034 | **11.072** | 241.93 |
| `free2` (`k <= 2`, free phases) | 5.6116 | 0.6014 | 9.330 | 157.89 |
| **`free3` — the prescribed statistic** | 4.3609 | 0.5672 | **7.689** | 109.32 |
| sawtooth `k = 5`, non-negative amplitude | 6.2709 | 0.8053 | 7.787 | 146.34 |
| sawtooth `k = 5`, amplitude sign free | 7.9009 | 1.0452 | 7.559 | 288.44 |
| `free1` (consistency arm) | 4.4664 | 0.4034 | 11.072 | 241.93 |
| *prototype, one harmonic* | *8.634* | *0.807* | *10.705* | — |
| *prototype, sawtooth `k = 5`* | *13.271* | *1.611* | *8.239* | — |

Paired, within-window, against one harmonic (median dB, fraction of units
improved):

| arm | the pilot's line windows (n = 1,221) | all carrier windows (n = 3,535) | control (n = 5,579) |
|---|---:|---:|---:|
| **`free3`** | **−3.284 dB** (0.2%) | −1.997 dB (28.0%) | **+0.869 dB** (57.5%) |
| `free2` | −1.863 dB (3.3%) | −1.186 dB (32.2%) | +0.746 dB (56.5%) |
| `free1` | 0.000 dB | 0.000 dB | 0.000 dB |
| sawtooth `k = 5` | **−2.776 dB** (30.1%) | +0.696 dB (57.6%) | **+2.545 dB** (79.6%) |
| sawtooth `k = 5`, sign free | +1.047 dB (75.1%) | +1.866 dB (85.4%) | +3.653 dB (93.0%) |
| *prototype, sawtooth `k = 5`* | *−2.715 dB (30.8%)* | *+0.778 dB (59.0%)* | *+2.543 dB (79.6%)* |

**Read the sawtooth row against the prototype row.** A different statistic on a
different footing, sharing no arithmetic with the prototype's driver, returns
−2.776 dB where the prototype returned −2.715, +2.545 where it returned +2.543,
and 30.1% where it returned 30.8%. That agreement is what licenses the `free3`
row beside it to be believed, and the `free3` row is **worse than the sawtooth
on the very windows the sawtooth was condemned for**.

### 2.1.1 The cross-validation, on the prototype's own convention

The prototype reports `F = ESS / (RSS / dof)` without dividing by the numerator
degrees of freedom; at two parameters that is exactly twice the `F/q` figure
above, which is why the separations agree while the levels differ by a factor of
two. Put on the prototype's convention, the two instruments' **control**
distributions are the same distribution:

| decile of `F` at 14.00 d, one harmonic, same-shell control | this module | prototype, published |
|---|---:|---:|
| p10 | 0.10884 | 0.10886 |
| p25 | 0.30713 | 0.30701 |
| p50 | **0.80678** | **0.80654** |
| p75 | 1.86343 | 1.86326 |
| p90 | 3.77154 | 3.77283 |

<!-- src: /home/sdegan/t5a-v2/window-mm.json distribution.fixed.Fproto.one.control
     against docs/matched-filter-devrun-mm-20260922.json
     carrierVersusControlAtTheLine["sinusoid-comparator"].control -->

Agreement to four significant figures on every decile, through a different
reduction, a different nuisance-projection path and a different phase
maximiser. The carrier side is 8.9328 against 8.6339 — 3.5% higher, on 3,535
admitted carrier windows against the prototype's 3,757. That 5.9% difference in
the admitted set is a real difference in the two drivers' admission bookkeeping
and it is NOT chased down here; it is named because it is the one place the two
instruments do not coincide. The sawtooth control median is 1.6106 against the
published 1.6108.

**That is the whole licence for this document.** The same instrument that
reproduces the prototype's control to four figures says the prescribed statistic
loses.

`free1` returning exactly 0.000 dB against `one`, on every population, is the
consistency check the arm exists for: at one harmonic a free-phase `(cos, sin)`
pair IS a one-harmonic template with a free amplitude sign, and the two code
paths agree to ten significant figures.

### 2.2 The history footing — the statistic where it actually lives

At the fixed fundamental:

| arm | carrier median | control median | **separation** |
|---|---:|---:|---:|
| one harmonic, stacked | 42.0545 | 0.3657 | **115.006** |
| `free2` | 42.0122 | 0.6694 | 62.763 |
| **`free3` — the prescribed statistic** | 32.7739 | 0.6343 | **51.666** |
| sawtooth `k = 5`, non-negative amplitude | 56.6633 | 0.7842 | 72.252 |
| sawtooth `k = 5`, sign free | 65.0026 | 1.0797 | 60.202 |

With the prescribed per-object refinement:

| arm | carrier median | control median | **separation** |
|---|---:|---:|---:|
| one harmonic, stacked, refined | 76.0593 | 1.5823 | **48.069** |
| `free2`, refined | 45.4359 | 0.9966 | 45.590 |
| **`free3`, refined — the statistic exactly as prescribed** | 32.5482 | 0.8443 | **38.549** |
| sawtooth `k = 5`, refined | 61.8586 | 1.4359 | 43.081 |
| sawtooth `k = 5`, sign free, refined | 72.6533 | 1.7849 | 40.704 |

Paired, within-object, at the fixed fundamental:

| arm over one harmonic | carriers (n = 208) | control (n = 328) |
|---|---:|---:|
| **`free3`** | **−2.757 dB** (16.8%) | **+2.046 dB** (63.1%) |
| `free2` | −1.573 dB (26.0%) | +1.858 dB (63.1%) |
| sawtooth `k = 5` | −0.396 dB (47.1%) | +2.854 dB (79.9%) |
| sawtooth `k = 5`, sign free | +1.539 dB (85.1%) | +4.130 dB (94.2%) |

---

## 3. Clause by clause, because three of the four are refuted separately

### 3.1 Coherent whole-history stacking — the one clause that works

`11.072 -> 115.006`, a factor of **10.4**, from doing nothing to the statistic
except stacking the PILOT'S OWN one-harmonic template coherently over each
object's disjoint tiles at a common absolute epoch. It is licensed by Rung-2
section 3.6's own reading 1: at the 42 d ladder the carriers' phase holds across
the whole measured baseline under a per-object fundamental while the passive
floor arm does not move.

Two things that gain are NOT established by this reading and are named here
rather than implied:

- the gain is measured against a control that receives the identical treatment,
  so it is not the stacking of more data per se; but **no phase-destroying
  surrogate was run**, so "the gain is coherence" is an inference from the
  construction and not a measurement. The accompanying registration makes that
  surrogate a gate;
- the carriers are pilot-selected, so the level of the carrier median is
  circular in the pilot's favour. The control is not selected and the paired
  columns are immune, but the separation is not.

### 3.2 Per-object refinement — costs, and the mechanism is a selection

`115.006 -> 48.069`. The refinement lifts the carrier median 1.81x and the
control median **4.33x**. Choosing the best of 30 candidates is a maximum over
30 draws; a population with no line gains the full order statistic, a population
with a line gains much less because it was already near its own maximum. The
refined index histogram on the carriers is not noise — it peaks hard at index
1929 (42 of 208, with 70 of 208 at 1928-1929) and spreads across the core, which
is the period dispersion Rung-2 section 3.3 measured — but a real dispersion and
a useful detector statistic are different claims, and only the first is
supported.

### 3.3 The `k <= 3` power sum — costs, monotonically

115.006 (`k = 1`) -> 62.763 (`k <= 2`) -> 51.666 (`k <= 3`) at the fixed
fundamental; 48.069 -> 45.590 -> 38.549 refined; 11.072 -> 9.330 -> 7.689 on the
window footing. Every harmonic pair added costs separation on every footing and
at every fundamental variant. The paired columns say why: `free3` is −2.757 dB
on the carriers and **+2.046 dB** on the control. The extra pairs collect
broadband structure that both classes carry, and the treated class — whose power
sits in the fundamental — pays the parameter cost without collecting the return.

That is the prototype's section 4.3 mechanism, measured on a statistic that has
no template at all: it is not a property of the sawtooth's shape.

### 3.4 The free `k = 2` relative phase — buys nothing, and the diagnostic's stated mechanism is wrong

Rung-2 section 3.4 wrote:

> a harmonic whose data phase is `pi` from the template's contributes a NEGATIVE
> term to the numerator while contributing its full positive share to the fitted
> norm `G`

`tests/test_orbit_matched_filter_v2.TestTheAntiPhaseSecondHarmonic` measures that
claim on an exact synthetic and it is only half true.

> **Derivation.** The template is
> `T(phi) = sum_k Re(W_k e^{-i k phi}) cos_k - Im(W_k e^{-i k phi}) sin_k`, so
> `phi -> phi + pi` multiplies harmonic `k` by `(-1)^k`: it flips every ODD
> harmonic and leaves every even one. A waveform whose second harmonic alone is
> inverted is therefore `-T(phi + pi)` — the SAME template, at a half-period
> shift, with the amplitude's sign flipped. The statistic `R^2 / G` is
> invariant to that sign.

So under a sign-free search the inverted second harmonic costs **exactly
nothing** (`test_but_a_sign_free_search_recovers_it_exactly_and_the_loss_vanishes`
asserts equality to nine places, and the recovered phase lands within 0.02 rad of
a half period). It costs only under the non-negative-amplitude convention the
prototype adopted — section 7.6 of that document — for phase uniqueness at
`k_max = 1`, where the two conventions are provably identical
(`test_the_two_conventions_agree_at_one_harmonic`). At `k_max = 5` it is not a
phase convention at all: it is a model constraint that a station-keeping cycle
may not run the other way, and it was never registered as one.

Measured on the archive, the convention is worth **1.935 dB** on the stacked
carriers: the sawtooth goes from −0.396 dB (sign constrained) to +1.539 dB (sign
free) against one harmonic. **Design section 3.5 predicted +1.65 dB for an ideal
sawtooth**, and the sign-free measurement lands 0.11 dB from it. The template
does roughly what the physics said it would do, once it is allowed a negative
amplitude. It still loses the separation, by a wider margin than before
(72.252 -> 60.202), because the control gains +4.130 dB from the same freedom.

**Neither correction rescues anything, and the direction of the correction is
against the track**: the more freedom a template is given, the more the passive
control gains.

---

## 4. What it cost, and what a sweep would cost

Everything through `/home/sdegan/gpu-broker/gpu-run`, class `standard`,
`--card 0`, beside the two resident 11,264 MiB training claims that hold both
cards. `CUDA_VISIBLE_DEVICES` arrived as a GPU UUID and was never parsed as a
number. **The three slices ran strictly one at a time**, because Rung-2 section
4 measured that two long-lived jobs sharing one card run 15.6x slower than one
alone, and a timing number taken beside another job of this session's own is not
a timing number. Resident training was co-tenant throughout, as it was for every
previous measurement in this track, so the rates are comparable to the
prototype's and are NOT free-card rates.

| slice | units | device reduction | host statistic | **peak pool, measured live** |
|---|---:|---:|---:|---:|
| history footing | 3,162 tiles | 25.76 s | 25.31 s | **220.0 MiB** |
| window footing | 9,114 windows | 17.30 s | 181.41 s | **218.4 MiB** |
| sweep-cost timing slice, 3 replicates | 163 tiles, dense band axis | 17.01 / 39.89 / 50.75 s | 25.0-30.4 s | **701.9 MiB** |
| device-side solve, chunked | 163 x 13,217 systems | 3.0-7.1 s | — | **895.0 MiB** |

Every peak above is sampled **while the batch is still live, before any
`free_all_blocks()`** — the prototype's own instrumentation defect was the
opposite, and it produced a 900 MiB claim against a 1,601 MiB truth.

### 4.1 Two claim violations of this session's own, recorded

1. **A first sweep-timing probe held 3,602.1 MiB against an 1,800 MiB claim.**
   The frequency-chunk budget assumed four live `(batch, width, chunk)` arrays;
   the true count is six, because each of the ten reductions forms an
   elementwise product before the sum collapses it and the pool does not return
   them. `frequency_chunk_for_budget` now solves for six and the reported
   701.9 MiB is the corrected measurement. The estimate was wrong by 2x and an
   estimate wrong by 2x is not a budget.
2. **The device-side solve probe held 2,381.4 MiB against a 1,400 MiB claim**,
   above design section 4.5's 2 GiB device-pool cap. The `2K x 2K` system is
   formed for every (unit, fundamental) pair at once and at 13,217 fundamentals
   that is gigabytes. It is now chunked over the frequency axis.

Both are the same class of defect as the one the prototype recorded, both were
caught by measuring rather than by estimating, and both are reported here rather
than corrected silently.

### 4.2 The cost of one sweep — EXTRAPOLATION from a measured rate

**The rate had to be measured three times, and the spread is itself the
finding.** Three identical timing slices, run strictly one at a time, on the
same card, beside the same two resident 11,264 MiB training claims, returned
**7.08e7, 9.01e7 and 2.11e8** sample-frequency products per second — a spread of
**2.98x** between the fastest and the slowest, with nothing about the code
differing between them. That spread is the host's, not the code's. Every figure
below is quoted from the **SLOWEST** replicate, because a cost taken from the
fastest is a best case dressed as a measurement.

The dense band axis is 26,810 points covering `[2 d, 143.75 d]` at
`df' = 3.70370e-5 c/d`, with 13,217 fundamentals and `k_ceiling = 3`. Median tile
spacing 1.007 d, so `f_Ny = 0.4965 c/d` and the axis reach is `2 f_Ny` — the
prototype's own section 7.2 result, which the `k = 3` ceiling does not change,
because `k_max(f) f <= f_Ny` by construction.

> **Derivation, each factor named.**
> Disjoint tiles implied by T3's registered exposure:
> `316,028 admitted windows / 3` (the 1080 d window on a 360 d step)
> `= 105,342.7 tiles`.
> Samples per tile, measured on this slice: `134,057 / 163 = 822.44`.
> Sweep samples: `105,342.7 x 822.44 = 8.6638e7`.
> Reduction: `8.6638e7 x 26,810 / 7.0824e7 = 32,796 s = 9.110 h per channel`.
> Solve, on the device at the slowest measured `3.0386e5` solves/s:
> `20,338 objects x 13,217 fundamentals / 3.0386e5 = 885 s = 0.246 h per channel`.
> One sweep, three channels: `3 x (9.110 + 0.246) = 28.07 GPU-h`.

| | prototype, sawtooth `k = 5`, per window | this statistic, `k <= 3`, stacked |
|---|---:|---:|
| one channel | 14.77 h | **9.36 h** (slowest replicate) / 3.16 h (fastest) |
| one sweep, three channels | **44.3 GPU-h** | **28.07 GPU-h** (slowest) / **9.47 GPU-h** (fastest) |

**Use 28.07 GPU-h for planning.** The like-for-like comparison is the other one:
the prototype's 44.3 was quoted from ITS uncontended card-1 slice, and against
this statistic's fastest replicate that is **4.7x cheaper** — one third of the
exposure because tiles are disjoint where windows overlap, two harmonics fewer
in the Gram, and one arm instead of eighteen bank members. Either way it is the
only thing about the prescribed statistic that came out ahead, and a cheaper
detector that separates worse is not a saving.

**This is an EXTRAPOLATION and is labelled as one.** The rate is measured; the
exposure it multiplies is arithmetic on T3's registered window count divided by
the overlap factor, not a tile census of the catalogue. The catalogue-wide
admission rate for disjoint tiles is UNPROVEN; on the development set it was
3,162 of 4,000 offered.

### 4.3 What the refinement costs

The 30-candidate per-object refinement adds nothing to the sweep: the refinement
axis is 301 unique frequencies for 30 candidates at `k <= 3` (the union of
`m x i` for `m = 0..6`), against 26,810 for the band. Measured on the history
footing, the whole refinement over 539 objects' 3,162 tiles cost **25.76 s of
device time and 220.0 MiB**. Per object that is 48 ms. Refinement is
computationally free and expensively wrong, which is an unusual combination and
worth stating plainly: its cost is not compute, it is 115.006 -> 48.069 of
separation.

---

## 5. Offline validation

**47 assertions, `tests/test_orbit_matched_filter_v2.py`, no archive, no GPU, no
network.** The whole orbit suite was run in a clean `git worktree` at
`13e80ed`, so that other sessions' uncommitted edits to `pipeline/*` and
`src/*` could not be mistaken for this work's failures: **1,166 tests, OK,
5 skipped, 281.9 s**. What the 47 establish:

- **An exact synthetic proof with analytic power fractions.** On a commensurate
  uniform grid every harmonic column is exactly orthogonal to every other and to
  the mean, so each harmonic's explained sum of squares is `(n/2) A_k^2` in
  closed form; the module returns it to six decimal places at `k = 1, 2, 3`.
  With `|W_k| = 1/k` the fractions of an ideal sawtooth's power are asserted
  against `mf.sawtooth_power_fraction`: **0.6079** at `k = 1` and **0.8275** at
  `k <= 3`, so the statistic discards **6.23 points** of an ideal sawtooth's
  power above `k = 3` — the part Rung-2 measured below the archive's noise.
- **The stack against one big design matrix.** Three segments with different
  absolute epochs, block-diagonal per-segment cubics plus one global harmonic
  block, solved independently with `numpy.linalg.lstsq`; the stacked
  `rssNuisance` and the stacked explained sum of squares agree to 1 part in
  `1e9` and `1e8`. A flipped middle segment costs the coherent fit more than a
  factor of two, so the stack is demonstrably coherent and not an incoherent
  sum.
- **Phase and amplitude recovery.** An injected template at `k_max = 3` is
  recovered at phases 0.0, 1.0, 2.5, 4.7 and 6.0 to better than 0.02 rad and at
  amplitudes 0.5, 1.0 and 3.0 to better than 1 part in `1e6`, with the fit
  explaining more than `1 - 1e-9` of the post-basis variance.
- **The amplitude-sign derivation of section 3.4**, as four separate
  assertions, including that the two conventions are identical at `k_max = 1`
  and that a sign-free search lands within 0.02 rad of a half period.
- **float32 against float64.** The same refinement sweep in both precisions
  selects the **identical** refined index and the same injected period (1937),
  with a median relative difference in the statistic of under `1e-4`.
- **The invariances the driver relies on.** `F` is unchanged by adding anything
  inside the nuisance span and by rescaling a segment; a segment the basis
  already explains returns zero rather than a ratio of two rounding errors;
  a harmonic above the tile's own Nyquist contributes nothing to either the
  response or the norm; a separation is invariant to the degree-of-freedom
  convention.
- **That the tiles are disjoint**, and that T3's windows are not.

---

## 6. Deviations, each named

1. **The harmonics are fitted JOINTLY** (a `2K`-parameter free-phase
   least-squares fit) rather than as a literal sum of marginal harmonic powers.
   The two coincide when the harmonic columns are orthogonal; measured
   orthogonality on the carriers is a median 1.0028, so the deviation is
   numerically inert. It is used because the joint form is also exact when they
   are not.
2. **The stacking segments are DISJOINT 1080 d tiles**, not T3's windows.
   Stacking windows on a 360 d step would count two thirds of every sample
   twice.
3. **Each tile is scaled to unit residual RMS before stacking.** In a coherent
   stack the relative scale of the segments IS the weighting, and unit-RMS
   scaling is the inverse-noise weighting that weighting should be while the
   signal is a small part of the residual — which Rung-2 section 3.5's amplitude
   bracket says it is. Its cost is that a tile which DID carry a large signal is
   divided by a larger number. The `raw` alternative is implemented and was NOT
   run.
4. **The refinement criterion is the object's own coherent fundamental power**,
   shared by every arm, so the arms differ only in the statistic. Self-refining
   each arm on its own statistic would give each a different trials factor and
   was not done.
5. **The sawtooth comparator is reported under BOTH amplitude-sign
   conventions.** The prototype's published numbers are the non-negative one and
   that is the row compared against them.
6. **Only `mean_motion` was measured.** The `inclination` channel was held back
   deliberately, to be the confirmatory arm of the accompanying registration.
7. **`P_top = 143.75 d` is used for the sweep-cost band**, which is the
   prototype's measured band-top crossover, not T3's 220 d.

---

## 7. What remains UNPROVEN, in that word

1. **Recall is unproven.** No injection-recovery arm was run here or anywhere in
   this track. Every separation in this programme is a contrast between two
   populations and none of them is a detection probability.
2. **"The stacking gain is coherence" is unproven.** No phase-destroying
   surrogate was run. The gain is measured against a control that receives the
   identical treatment, which excludes "more data per unit" but not "shared red
   noise that the absolute clock happens to align".
3. **The carrier set is pilot-selected** and the circularity is unproven to be
   harmless for the separations. The paired columns are immune to it.
4. **The catalogue-wide admission rate for disjoint tiles is unproven.** The
   sweep cost divides T3's registered window count by the overlap factor.
5. **The 18-member bank was never priced under this statistic** and is not
   compared here; four arms were, not eighteen.
6. **The per-tile Nyquist ceiling uses median spacing**, which is not a window
   function. The prototype recorded the same defect and it is inherited
   unchanged.
7. **No null of any kind was computed** — no p-value, no threshold, no gate.
8. **The `free3` loss was measured on `mean_motion` only.** Whether it transfers
   is exactly what the accompanying registration's gate G6 tests.
9. **Nothing here was run at catalogue scale**, and no T5a workload has ever run
   on the HPC platform.

---

## 8. Honest summary

The statistic the Rung-2 phase-coherence diagnostic prescribed was implemented
as written, tested in 47 offline assertions including an exact synthetic proof,
and measured on the prototype's own development set on two footings. **It does
not beat one harmonic on the treated class**: 7.689 against 11.072 per window
and 51.666 against 115.006 per object, and −3.284 dB on the very windows the
pilot put on the line — a deeper loss than the −2.776 dB that condemned the
sawtooth.

The instrument that says so reproduces the prototype's headline numbers to
within 0.06 dB through arithmetic that shares nothing with it, which is the only
reason the verdict is worth reading.

Three of the diagnostic's four clauses are refuted separately: refinement costs
because a maximum over 30 candidates helps a population with no line more than
one with a line; the `k <= 3` power sum costs monotonically because extra
harmonic pairs collect broadband structure both classes carry; and the free
`k = 2` phase buys nothing, because an inverted even harmonic is invisible to a
matched filter that is allowed a negative amplitude — which also means the
mechanism Rung-2 section 3.4 published for the sawtooth's loss is not the
mechanism that operates, and correcting it is worth 1.9 dB of response and
nothing at all of separation.

The fourth clause is worth more than everything else this track has produced.
Coherent whole-history stacking of the pilot's own one-harmonic statistic takes
the separation from 11.072 to 115.006 — and it is not a matched filter, which is
the awkward shape of the only good news here. The accompanying registration
treats that as a hypothesis generated by this reading and binds the one
confirmatory experiment, on a channel and a control half that did not generate
it, with the gates fixed in advance.

No third template family is proposed. Two have now been falsified on the same
208 objects, and a third fitted to the same objects would be a search over
template families with no accounting.
