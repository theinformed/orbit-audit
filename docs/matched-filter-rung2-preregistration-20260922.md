# T5a Rung-2 transfer test and phase-coherence diagnostic: PRE-REGISTRATION

> **COMMITTED ALONE AND AHEAD OF EVERY NUMBER IT GOVERNS.** No statistic in
> either measurement below has been computed at the time this document is
> committed. No threshold has been evaluated, no exceedance read, no coherence
> estimated. This registration is committed in its own commit, containing
> nothing else, in the manner of `docs/cadence-preregistration-20260921.md`
> (`1a51afe`) and `docs/phase3-preregistration-20260921.md` (`7eab5a4`).

Written 2026-09-22. Documents of record:

- `docs/matched-filter-design-20260922.md` (`e51bcce`) — the design. Its §5.3
  and §7.2 fix the Rung-2 screen **before any measurement**, and this document
  executes that rule rather than restating it.
- `docs/matched-filter-prototype-20260922.md` (`b2c7665`) — the instrument and
  its three development slices, including Finding 1 (the five-harmonic sawtooth
  template **loses** 2.715 dB on the pilot's line windows and **gains** 2.543 dB
  on the control) and Finding 2 (compute repriced 9.4x).
- `tools/matched_filter.py`, `tools/matched_filter_run.py` — the verified
  instrument, 41 offline tests. It is reused; it is not rewritten.

House rules this document is bound by: derive or cite every quantity;
thresholds are **screens**, never laws, and each says what it screens for;
blind spots are declared in advance rather than discovered.

---

## 0. What is already bound, and what is newly registered here

This distinction is the first thing in the document because it is the thing a
reader is entitled to check. Nothing below quietly re-registers a rule the
design already fixed, and nothing below pretends that a choice made today was
made in advance.

### 0.1 Already bound by the design registration. EXECUTED AS REGISTERED.

| Bound rule | Where |
|---|---|
| **The Rung-2 screen itself: Rung 2 is admissible only if the held-out passive exceedance at the nominal 1% level lands within [0.5%, 2.0%]; otherwise Rung 3.** | design §5.3, final paragraph |
| The screen's rationale — chosen so that T3's measured 9.32% would be rejected with a wide margin | design §5.3 |
| The construction: surrogate thresholds from the passive **calibration** half, applied to the held-out passive **audit** half | design §7.2 |
| Surrogates are built **per sampling-geometry class**, a clustering on epoch spacing, gap structure and span | design §5.3, Rung 2 row |
| The held-out exceedance is **published either way** | design §5.3 |
| The statistic is the profile ratio `F` of design §3.2 with the registered cubic carried inside the fit | design §3.2 |
| The registered band is `[2 d, P_top]`, `P_top` read before any T5a number | design §3.4 |
| Object-level (clustered) estimation, object records sorted by NORAD before any estimator sees them | design §5.2(b) |
| Strata without enough exposure are **labelled gaps**, never zeros, with their weight stated | design §5.2(a) |
| A fallback ladder for under-populated cells, with fallback exposure reported | design §5.2(a), citing T3 §2.4 |

The design's own words on why this matters: *"the registration fixes that before
the number is visible."* It did. This document does not touch it.

### 0.2 Newly registered here, because the design did not determine it

Each of these is a decision the design left open or did not contemplate. Each is
fixed here, in writing, before any number exists, with its derivation.

1. **The level at which the exceedance is read** (§2.3). The design's §7.2 text
   compares to T3's 9.32%, which is an *object*-level figure, while the nominal
   1% is a *window*-level rate. §2.3 derives that these two cannot both be
   intended and fixes the window-level reading as PRIMARY.
2. **The geometry-class feature set and the binning rule** (§2.2).
3. **The surrogate mechanism** — the design names "surrogates" and never says
   what one is (§2.4). Two are registered, one named primary in advance.
4. **The surrogate budget** `B_s` and the representative-window count `R`
   (§2.5), which are below the design's own cost-model figures and are declared
   as a prototype-budget reduction with their precision reported.
5. **The calibration-half self-application diagnostic** (§2.7), which decomposes
   a failure into "the surrogate model is wrong" versus "the class does not
   transfer". The design does not ask for it; without it a failed screen is a
   number without an explanation.
6. **Every estimand, ladder and threshold of the phase-coherence measurement**
   (§3). The design requires that complex harmonic amplitudes be retained on a
   common absolute epoch (§2.1) and hands them to T4; it registers no coherence
   measurement at all. All of §3 is new.

### 0.3 What this document does NOT register

It does not register T5a. There is still no `docs/t5a-preregistration-<date>.md`.
No object's status changes, no shipped threshold moves, no gate is evaluated, no
p-value is published, and the scope fence of design §10 is unchanged and binding.

---

## 1. The two measurements in one paragraph each

**Measurement 1 — the Rung-2 transfer test.** The design's §7.2 calls this "the
prototype's most valuable single output". Passive windows are assigned to
sampling-geometry classes; a null threshold at the nominal 1% level is built per
class from surrogates on **calibration-half** windows of that class; the
threshold is applied to the **held-out audit-half** passive windows of the same
class; the exceedance is reported and the registered screen is applied. The
statistic is the ONE-HARMONIC member — `tools/matched_filter_run.sinusoid_weights`,
the template the prototype measured to be the current best (Finding 1). A verdict
inside [0.5%, 2.0%] prices the future campaign's calibration at ≈140 GPU-h per
sweep; outside it, ≈8,860 <!-- src: docs/matched-filter-prototype-20260922.md §5.3 -->.

**Measurement 2 — the phase-coherence diagnostic.** Finding 1 says the
five-harmonic sawtooth loses response on exactly the windows that carry the
line. A matched filter over a harmonic template is only worth its extra norm if
the harmonics are phase-locked to the fundamental and the fundamental's phase is
stable over the baseline being coherently combined. This measurement asks both
questions of the data — across an object's history, and between harmonics inside
a segment — and reports the **coherence timescale**, which is the quantity that
derives the right statistic rather than being chosen for one.

---

## 2. MEASUREMENT 1 — the Rung-2 transfer test

### 2.1 Population, split and statistic

- **Population.** Every window of every `passive`-class object admitted by
  `cadence_core.window_admissible` on `mean_motion`, i.e. the pilot's own
  window population, reached through `tools/matched_filter_run`'s existing path
  so the two are comparable without a caveat.
- **Split.** The T3 object-level calibration/audit split exactly as committed in
  `docs/cadence-results-20260921.jsonl` (`half` field). It is not recomputed and
  not re-salted. Measured exposure, from the prototype's own reading
  <!-- src: docs/matched-filter-prep-20260922.json passiveCalibrationHalf -->:
  5,627 calibration objects / 110,382 windows; 5,485 audit objects / 106,941
  windows.
- **Statistic.** `F(f)` of design §3.2 with the **one-harmonic** weight vector,
  the registered cubic nuisance basis inside the fit, `p = 6`, phase maximised in
  closed form. Per window the reported quantity is `peak F` — the maximum of `F`
  over the fundamentals of the registered band.
- **Band.** PRIMARY `[2 d, 143.75 d]`, the registered band `[2 d, P_top]` with
  `P_top` as read before any T5a number
  <!-- src: docs/matched-filter-prep-20260922.json bandTopCrossover -->.
  SECONDARY `[2 d, 219.51 d]`, T3's band, reported alongside because T3's 9.32%
  comparator was measured there. Both maxima are read from the **same** computed
  `F` curve, so the secondary costs nothing and cannot be a separate run chosen
  after a number is visible.

### 2.2 The sampling-geometry classes — REGISTERED CLUSTERING

Geometry is a property of a **window**, so classes are assigned per window. Four
features, all computable from the window's epochs alone and none of them a
function of the channel values:

| Feature | Definition |
|---|---|
| `g1` | `log2(median epoch spacing in days)` |
| `g2` | `log2(n)`, `n` the admitted sample count |
| `g3` | largest gap in days (bounded above at 45 d by admissibility) |
| `g4` | gap burden: the fraction of the window's span lying inside gaps larger than `3x` the window's own median spacing |

**Binning.** Each feature is cut at quantiles computed on the **calibration half
only** — the audit half never contributes to a bin edge, a threshold, or a
merge decision. Cuts: `g1` at quartiles (4 bins), `g2` at quartiles (4 bins),
`g3` at tertiles (3 bins), `g4` at tertiles (3 bins). **144 cells.** Quantile
cuts rather than k-means so the clustering is deterministic, reproducible from
the committed edges, and cannot be re-seeded after a number is visible.

**Fallback ladder** (the shape of T3's matching ladder, design §5.2(a)). A cell
with fewer than `MIN_CLASS_CAL_WINDOWS = 200` calibration windows is merged
upward by dropping features in this fixed order: drop `g4`, then `g3`, then
`g2`, then `g1` (the last leaving a single pooled class). The rung on which each
class was formed and the **fraction of audit windows judged on each rung** are
reported, as T3's registration requires of its own ladder. 200 is the design's
own `MIN_CELL_WINDOWS` <!-- src: tools/cadence_core.py MIN_CELL_WINDOWS = 200, prereg 6.4 -->
and is a screen for "enough exposure to estimate a 99th percentile at all", not
a law.

**Labelled gaps.** An audit window whose class has no admissible calibration
exposure at any rung is an **abstention**, counted and attributed, never folded
into the exceedance numerator or denominator (design §5.2(a), Paper B §2.6).

### 2.3 At what level the exceedance is read — DERIVED, AND IT MATTERS

The design's §7.2 says "report the exceedance at the nominal 1% level" and gives
T3's comparator as 9.32%. T3's 9.32% is *"9.316% of held-out passive **objects**
exceeded their matched 99th-percentile threshold"* (design §5.1). The nominal 1%
is the threshold's own **window**-level tail mass. These two readings are not
the same quantity and the screen cannot be meant for both:

> A passive object carries a median of **17** windows (design §5.1, citing T3
> §2.2). Under a *perfectly calibrated* window-level null at the nominal 1%,
> with max-over-windows aggregation, the object-level exceedance is
> `1 - 0.99^17 = 15.70%`
> <!-- derivation: computed for this document; independence assumed, which
>      over-states nothing since positively correlated windows lower it only
>      toward 1% at full correlation -->
> — which is **outside [0.5%, 2.0%] by a factor of 7.9**. A screen that a
> perfectly calibrated null cannot pass is not a screen; it is a rejection.

Therefore, **REGISTERED PRIMARY: the window-level exceedance.** The fraction of
held-out audit-half passive **windows** whose `peak F` exceeds their class's
threshold. Under a correctly specified, correctly transferring null this is 1%
by construction, so [0.5%, 2.0%] is a two-sided factor-two screen around the
nominal, which is what the design's arithmetic requires.

**REGISTERED SECONDARY, published alongside and never used for the verdict:**
the object-level max-over-windows exceedance, the T3-comparable 9.32% quantity,
reported together with the 15.70% calibrated-null reference above so it cannot
be read as a failure when it is arithmetic.

**Interval.** The window-level exceedance carries a **clustered bootstrap**
interval: 2,000 resamples of **objects** with replacement, object records sorted
by NORAD before the estimator sees them (design §5.2(b), the defect Phase 3
found and fixed at `d4e9090`). The verdict is read from the **point estimate**
against the screen, as the design's wording requires; the interval is published
so a reader can see whether the verdict is close to a boundary, and if the
interval straddles a boundary that is stated in those words.

### 2.4 What a surrogate is — REGISTERED, TWO OF THEM, ONE PRIMARY

The design names "surrogates" and never defines one. Two are registered. Both
are built from **class-level and calibration-half information only**, which is
what makes them Rung-2 nulls: a surrogate that used the audit object's own
epochs or its own noise parameters would be a Rung-3 null wearing a Rung-2 name,
and the test would be vacuous.

- **S-AR1 — PRIMARY.** Gaussian AR(1) in index order, `x_j = phi x_{j-1} + e_j`,
  with `phi` the **class median** of the per-window lag-1 autocorrelation of the
  post-cubic residual over the class's calibration windows, scaled to unit RMS
  and placed on a class-representative calibration window's own epochs.
- **S-WHITE — SECONDARY.** The representative window's own post-cubic,
  unit-RMS residual, permuted uniformly at random across its own epochs.

**Why S-AR1 is primary, derived in advance and not after a number.** The
question this test asks is whether a *look-elsewhere factor* transfers within a
geometry class (design §5.3: "a look-elsewhere factor that depends on that
object's own window function"). A white null on a channel whose residuals are
temporally correlated sets thresholds that are wrong for a reason that has
nothing to do with geometry-class transfer, and would fail the screen while
telling the programme nothing about the question it asked. AR(1) is the minimal
noise-colour model, its single parameter is a class statistic, and it therefore
leaves the geometry question isolated. S-WHITE is published in the same table as
the bracket on the other side, so the reader sees both ends.

**Both exceedances are published**, per design §5.3. If they fall on opposite
sides of the screen that is stated plainly and the verdict is the primary's,
with the disagreement named as the finding.

### 2.5 Surrogate budget — REGISTERED, AND BELOW THE DESIGN'S OWN FIGURE

The design's Rung-2 cost model is 200 classes x 500 surrogates x 10 windows =
5,000 surrogate windows per class (design §5.3). This prototype registers:

- `R = 24` representative windows per class, drawn uniformly at random without
  replacement from the class's calibration windows, **after sorting by
  `(norad, window)`**, with seed `20260922`.
- `S = 50` surrogates per representative window.
- `B_s = R x S = 1,200` surrogate windows per class — **0.24x the design's
  figure**, a declared prototype-budget reduction.

`B_s = 1,200` puts 12 surrogate draws above the 99th percentile, so the
threshold is an order statistic with real sampling error. **That error is
measured, not assumed:** a nested bootstrap over the surrogate draws (500
resamples per class) publishes the per-class threshold's interval and the
induced spread on the pooled exceedance, and that spread is reported next to the
screen boundaries. If the induced spread alone is comparable to the width of
[0.5%, 2.0%], the verdict is declared **unresolved at this budget** rather than
reported as a pass or a fail.

### 2.6 The threshold

Per class `c`: `tau_c` = the 99th percentile of the surrogate `peak F`
distribution, computed with `numpy.percentile(..., 99.0, method="linear")`,
separately for each of the two bands of §2.1 and each of the two surrogate
mechanisms of §2.4. `PRIMARY_PERCENTILE = 99.0` is T3's own registered figure
<!-- src: tools/cadence_core.py PRIMARY_PERCENTILE = 99.0, prereg 6.3 -->.

### 2.7 The decomposition diagnostic — NEWLY REGISTERED

`tau_c` is applied to a registered random **25% subsample of calibration-half
objects' real windows** (seed `20260922`, objects sorted by NORAD before
sampling). This is not held out and is not the screen; it is the control that
separates two very different failures:

| Calibration-half exceedance | Audit-half exceedance | Reading |
|---|---|---|
| ~1% | ~1% | The null calibrates and transfers. Rung 2 is real. |
| ~1% | >> 1% | The **class does not transfer** — the T3 failure, reproduced under a better statistic. |
| >> 1% | >> 1% | The **surrogate model** is wrong (noise colour, or real in-band lines in the passive class), and the transfer question is unanswered either way. |
| << 1% | << 1% | The surrogate null is too conservative; thresholds are too high and the detector would be blind. |

The bottom-left cell is the one that would otherwise be reported as "Rung 2
fails" when the truth is "this null is not a null". It is registered here
because a failed screen with no decomposition costs the programme 8,720 GPU-h a
sweep on the strength of a number it cannot explain.

### 2.8 Blind spots of Measurement 1, declared in advance

1. **The test cannot separate a miscalibrated null from real in-band structure
   in the passive class.** Design §6(6) already declares that a natural line
   will be matched happily, and T3 measured the 27.5 d family at 8.17x in the
   passive control and a 75.25 d Cosmos line that is natural and absent from the
   pooled passive class. Those lines are in the audit windows and are not in any
   surrogate. Every exceedance reported here is therefore an **upper bound** on
   the miscalibration, and §2.7's decomposition is what bounds it from the other
   side. T3's 9.32% carries the identical defect, so the comparison is fair.
2. **AR(1) in index order is not AR(1) in time** on an irregularly sampled
   window. The approximation is declared; the median passive spacing is 0.95 d
   and admissibility bounds the largest gap at 45 d, so the index order is close
   to but not identical with the time order.
3. **The one-harmonic statistic is not the design's detector.** It is the
   statistic the prototype measured to be the current best (Finding 1). A Rung-2
   verdict obtained with one harmonic does not automatically transfer to the
   18-member bank, whose look-elsewhere factor is larger. This is stated as a
   limitation of the verdict and not as a caveat on the run.
4. **`B_s = 1,200` is below the design's cost model**, §2.5.
5. **Passive is not payload.** The screen is about the control class only. What
   the payload class does under the same thresholds is not measured here and is
   not claimed.
6. **Geometry classes are assigned per window, not per object.** An object whose
   sampling changes across its history contributes windows to different classes.
   That is the correct treatment for a window-level threshold and it is a
   departure from an object-level reading of "class"; it is declared.

### 2.9 Stop rules for Measurement 1

The band, the basis, the class features, the bin counts, the merge ladder, the
surrogate mechanisms, `B_s`, `R`, the percentile, and the level at which the
exceedance is read are **fixed by this document**. If the verdict is unwelcome
it is reported. Re-running with a different band, basis, class definition,
surrogate or percentile after a number is visible is prohibited. A second run is
permitted only to fix a defect, must be reported as a defect fix with the defect
named, and the superseded number is published alongside.

---

## 3. MEASUREMENT 2 — the phase-coherence diagnostic

**Every estimand and threshold in this section is newly registered.** The design
requires the complex amplitude on a common absolute epoch (§2.1) and registers
no coherence measurement.

### 3.1 Why this is the measurement the redesign needs

A matched filter earns its extra fitted norm only if the template's structure is
present coherently in the data. Finding 1 measured the opposite at the only line
this programme has. Three readings were offered and not chosen between
<!-- src: docs/matched-filter-prototype-20260922.md §4.3 -->. Two of the three
are phase statements, and phase is measurable today from the T4 hand-off product
the instrument already emits. The deliverable is the **coherence timescale**,
and it derives the statistic:

| Measured coherence | The statistic that follows |
|---|---|
| Coherent across the whole history | matched filter, coherent stacking across windows (design §3.6 SECONDARY) |
| Incoherent beyond about one cycle | per-window harmonic **power** sum — no phase, no template phase-locking |
| Partial, with a measured length `T_coh` | semi-coherent stacking in segments of `T_coh`, incoherent above it |

### 3.2 Population

The prototype's committed development set
<!-- src: docs/matched-filter-devset-20260922.json -->: **208** east-west
carriers (`mean_motion`), **56** north-south carriers (`inclination`), and the
**331**-object same-shell GEO passive control, which is the floor arm of §3.7.

### 3.3 Segments, not windows — REGISTERED, WITH THE DERIVATION

T3's windows are 1080 d wide and step 360 d, so consecutive windows **share 720
d of data**. A phase agreement between two such windows is 2/3 an identity and
cannot measure a coherence timescale. Coherence is therefore measured on
**disjoint segments tiled over the object's whole epoch history** from its first
epoch, and not on T3 windows.

- Registered ladder: `L in {42, 210} d`. At the 13.99657 d fundamental (§3.4)
  those are **3.00** and **15.00** cycles.
- Segment admissibility, registered: `n >= 24` samples, span `>= 0.9 L`, largest
  gap `<= L/4`. Exposure — segments offered, admitted, and rejected by reason —
  is reported.
- **Nuisance basis inside a segment: degree 1, not the registered cubic.**
  Derivation — worst-case retained power of a sinusoid after projecting out a
  polynomial basis, over the phase
  <!-- derivation: computed for this document; least squares on a 20,001-point
       grid, minimised over 36 phases -->:

  | cycles in segment | 2.00 | 3.00 | 4.82 | 9.64 | 19.3 | 38.6 |
  |---|---:|---:|---:|---:|---:|---:|
  | retained after **linear** | 0.848 | **0.932** | 0.980 | 0.998 | 0.9995 | 0.9999 |
  | retained after **cubic** | 0.712 | **0.824** | 0.921 | 0.990 | 0.9977 | 0.9993 |

  A cubic over a 42 d segment removes 17.6% of the fundamental's power in the
  worst phase, and the leakage is **phase-dependent**, so it biases the very
  quantity being measured. The linear basis costs 6.8% at the finest rung. Full
  1080 d windows keep the registered cubic (§3.6(a)).

### 3.4 The frequency, and two registered variants

The fundamental is the grid point nearest 14.00 d on the instrument's own
refined axis: index `i0 = 1929`, `f0 = i0 x 3.703704e-5 = 0.0714444 c/d`,
**`P0 = 13.99657 d`**
<!-- derivation: 1/14 / REFINED_DF = 1928.571, nearest integer 1929; computed for this document -->.
Harmonics are the exact grid points `k i0`, `k = 1..5`, i.e. 13.99657, 6.99829,
4.66552, 3.49914 and 2.79931 d — exact multiples by construction, which is why
design §4.3's grid anchoring matters here.

- **Variant A — FIXED FREQUENCY (primary).** All segments of all objects read at
  `f0`. This is what a fixed-template matched filter would actually get, and it
  is therefore the operationally relevant number.
- **Variant B — PER-OBJECT REFINED FREQUENCY.** Each object's fundamental is
  first refined to its own maximum of `F` inside T3's published 14.00 d core
  half-width of `+/- 0.109 d` <!-- src: design §1.3(a) --> using **all** of that
  object's data, and its segments are then read at that refined frequency.

The difference between A and B is registered as the estimand that **separates
period dispersion from phase noise**, and design §1.3(a) predicts period
dispersion on physical grounds: `T = 4 sqrt(dLambda / A)` is slot-dependent, so
a fleet holding the same box does not share one period. If A decoheres and B
does not, the finding is dispersion, not incoherence, and the statistic that
follows is a per-object refined filter rather than a shorter coherent segment.

### 3.5 The coherence estimator — REGISTERED

Per admitted segment `s`, the instrument's fitted complex amplitude at the
fundamental, referred to the **absolute epoch t_ref = Unix epoch 0**:
`A_s = |A_s| e^{i theta_s}`, `theta_s = theta_s^{local} - 2 pi f (t_s^{start} - t_ref)`,
wrapped to `[0, 2 pi)`. The sign convention is not asserted: an offline test
injects a signal of known absolute phase into two segments with different start
epochs and asserts that the recovered absolute phases agree to better than 0.01
rad. If that test fails the measurement does not run.

For a lag `d = m L`, over all within-object pairs of admitted segments whose
start epochs differ by `d`:

> `C(d) = SUM Re(A_i conj(A_j)) / SUM sqrt( max(|A_i|^2 - N_i, 0) x max(|A_j|^2 - N_j, 0) )`

with `N_s` the segment's **off-line noise power**: the mean `|A|^2` over the
registered reference set of grid points `i0 +/- 20 .. i0 +/- 60` (excluding the
core `+/- 5`), measured in the same segment with the same basis.

**Why this estimator and not the circular variance of the phase.** A 42 d
segment holds about 1/26 of a 1080 d window's samples, so the per-segment
signal-to-noise is low and an individual segment's phase is mostly noise; the
resultant length of noisy phases collapses toward the noise floor regardless of
the truth. `Re(A_i conj(A_j))` has **zero expectation under independent noise**
in disjoint segments, so the numerator is unbiased and averaging thousands of
pairs recovers the signal cross-power. The denominator's noise bias is removed
by the measured `N_s`. This is the standard cross-spectral coherence and it is
the only one of the two that can work at this exposure.

**The circular variance the brief names is also reported** (§3.6(a)), on full
1080 d windows where per-window signal-to-noise is adequate, with its 720 d
overlap stated as the confound it is.

### 3.6 The three reported estimands

**(a) Per-object circular variance of the fundamental's phase across its
windows.** On T3's own 1080 d line windows, registered cubic basis, phases
referred to `t_ref`. Per object: the circular variance `1 - R` of its window
phases. Across objects: the distribution (deciles, and the fraction with
`R > 0.5`). **Reported with the 720 d overlap declared in the table caption**;
it is a description of the hand-off product, not the coherence timescale.

**(b) The coherence timescale `T_coh`.** From `C(d)` on the `L = 42 d` ladder,
lags `d = 42 k` for `k = 1..24`, with the `L = 210 d` ladder as the coarse
cross-check. **Registered definition:** `T_coh` is the smallest lag at which
`C(d)` falls below `1/e = 0.36788` of `C(L)`, the shortest-lag value, with
log-linear interpolation between ladder rungs. Registered boundary cases,
fixed now so none can be chosen later:
- `C(d) >= (1/e) C(L)` at every measured lag -> report **`T_coh > 1008 d`**
  (coherent across the measured baseline).
- `C(L)` itself is not distinguishable from the §3.7 floor -> report
  **`T_coh < 42 d`**, i.e. **unresolved below three cycles**, in those words.
  The ladder cannot see below 42 d and the document will say so rather than
  extrapolating.
- `C(d)` non-monotonic -> the **first** crossing is `T_coh` and the curve is
  published in full.

**(c) The harmonic-to-fundamental phase relation.** For each admitted segment
and each `k = 2..5`, the independently fitted phase `theta_k` at grid point
`k i0` (each harmonic fitted **alone** with the nuisance basis, never jointly,
so the relation is not imposed by the fit), and the registered residual

> `psi_k = theta_k - k theta_1  (mod 2 pi)`.

A coherent sawtooth requires `psi_k` to be a **constant** across segments and
objects — design §1.1 puts every harmonic of the one-sided deadband cycle in
sine phase relative to the burn, so `psi_k` is fixed by the template and nothing
else. Reported: the resultant length `R_k` of `psi_k` pooled over carrier
segments, its per-object distribution, and the same on the §3.7 floor and
ceiling arms. **Registered screen:** `R_k >= 0.30` for `k = 2` and `k = 3` is
read as "the harmonics track the fundamental"; `R_k < 0.10` is read as
"scrambled"; between them is reported as **partial and inconclusive at this
exposure**, and the number is published either way. 0.30 and 0.10 are screens
chosen against the floor arm's own scatter and are not laws.

### 3.7 The floor and the ceiling — REGISTERED CONTROL ARMS

A coherence number with no floor and no ceiling is unreadable, and a challenge
that cannot be survived is not evidence
(`feedback-challenge-must-license-survival`). Both arms run the identical code
path on the identical segments:

- **FLOOR.** The 331-object same-shell GEO passive control. It carries no
  station-keeping, so its `C(d)` is the estimator's own null and its `R_k` is
  the scrambled reference. The screens of §3.6(c) are read against it.
- **CEILING.** A **fully coherent** ideal sawtooth of design §1.1, at the
  derived amplitude `delta n = 3.3067e-5 rev/day`
  <!-- src: design §1.2 -->, injected at a fixed absolute phase into the real
  carrier series (real epochs, real noise, real gaps) and run through the same
  path. A ceiling that does not return `C(d) ~ 1` at every lag and
  `R_k ~ 1` means the instrument cannot see coherence that is there, and the
  measurement is then reported as **instrument-limited** and no verdict is
  drawn. This arm is what licenses survival: it gives the measurement a way to
  be wrong that is visible before the carrier arm is read.

### 3.8 Blind spots of Measurement 2, declared in advance

1. **The ladder cannot resolve below 42 d — three cycles.** A decorrelation
   inside one cycle is reportable only as "below the ladder's floor". The
   brief's "incoherent beyond ~1 cycle" case is therefore detectable but not
   *resolvable* by this measurement, and §3.6(b) fixes that wording in advance.
2. **A 42 d segment's fitted amplitude is a weak per-segment estimate**; every
   conclusion at that rung rests on averaging over pairs, not on any one
   segment. The `L = 210 d` rung exists to show whether the two agree.
3. **The carrier set is selected by the pilot**, so carrier-side quantities are
   circular in the pilot's favour. That is why the floor arm is unselected and
   why every screen is read against it.
4. **TLE mean motion is a smoothed estimate** whose effective bandwidth is
   unpublished (prototype §4.3, reading 3). A measured decoherence at high `k`
   may be the archive's smoothing rather than the satellite's behaviour, and
   this measurement cannot separate the two. It is named, not filled.
5. **The injection ceiling injects an instantaneous ideal reset**, which is not
   a real burn; design §7.3 and T4 §5.2 already require that an injected step be
   read as an **upper bound**. The ceiling is therefore optimistic by
   construction.
6. **Variant A/B cannot separate period dispersion from a slow real period
   drift** within an object's own history. Both appear as decoherence in A and
   partially in B.
7. **No inference.** No p-value, no gate, no object relabelled. `T_coh` is a
   measured descriptive quantity that informs a future registration.

### 3.9 Stop rules for Measurement 2

The segment lengths, admissibility, basis degree, reference frequencies, the
estimator, the `1/e` definition, the `R_k` screens, and the floor and ceiling
arms are fixed by this document. If the ceiling arm fails, no verdict is drawn
and that is the report. Re-running with a different ladder, basis or threshold
after a number is visible is prohibited on the same terms as §2.9.

---

## 4. Resources, and the honest estimate

Both measurements run through `/home/sdegan/gpu-broker/gpu-run`, class
`standard`, beside resident training, with `CUDA_VISIBLE_DEVICES` arriving as a
GPU UUID and never parsed as an integer. The prototype **measured** a peak CuPy
pool of 1,601.3 MiB at its chunking
<!-- src: docs/matched-filter-prototype-20260922.md §4.1 -->; the claim is
**`--estimate-mib 1800`**, above the measurement and below design §4.5's 2 GiB
cap. If any run's recorded peak exceeds 1,800 MiB the run is reported as having
violated its own claim, in those words, as the prototype did of its 900 MiB
claim.

Registered aside, 10 minutes and not a study: the prototype and the T3 pilot
both measured card 0 running **2.1x–3.47x slower than card 1 on identical work**
<!-- src: docs/matched-filter-prototype-20260922.md §4.1; docs/cadence-results-20260921.md §1.2 -->.
`nvidia-smi` clocks, temperature, utilisation, power and enforced-clock reasons
are sampled on **both** cards during a paired slice and the difference is
reported. **No fix is attempted and none is proposed**; this is a measurement of
a standing asymmetry, nothing more, and it changes no scheduling.

Per the standing operator ruling, the space page's GPU jobs and the resident
training get whatever room they need; these runs queue behind them and never
confine another session's processes.

## 5. Deliverables

`docs/matched-filter-rung2-results-20260922.md`, plus committed JSON artifacts
carrying provenance comments, plus the offline tests the two tools need. The
orbit suite stays green (837 at the prototype's commit). The results document
reports, at minimum: the registration's commit hash; the Rung-2 window-level
exceedance against [0.5%, 2.0%] with its clustered interval and the surrogate
budget's induced spread; the object-level comparator against both 9.32% and the
15.70% calibrated-null reference; the §2.7 decomposition; `T_coh` with its floor
and ceiling arms; the `psi_k` result; the card asymmetry; and everything that
remains **unproven**, in that word.

---

## 6. AMENDMENT 1 — 2026-09-22, BEFORE ANY NUMBER OF EITHER MEASUREMENT EXISTS

> This amendment is committed **alone**, in its own commit, before the first
> coherence amplitude has been computed and before the first Rung-2 threshold
> has been read. No number governed by section 3 exists at the time it is
> written. It is recorded here rather than applied silently, because a
> registration that is quietly corrected is not a registration.

**The defect.** Section 3.5 registered the per-segment off-line noise power
`N_s` as the mean `|A|^2` over the grid points `i0 +/- 20 .. i0 +/- 60`. Those
offsets are **inside the segment's own resolution element** and are therefore
not off-line at all:

> A segment of length `L` has a frequency resolution of `1/L` cycles/day, which
> on the instrument's refined axis is `1/(L x 3.703704e-5) = 27000/L` grid
> steps. At `L = 42 d` that is **643 grid steps**; at `L = 210 d`, **129**.
> <!-- derivation: computed for this document -->

A reference band at `+/- 20 .. +/- 60` steps therefore samples the same spectral
peak as the line itself. `N_s` would have been an estimate of the signal, the
debiased power `max(|A|^2 - N_s, 0)` would have been driven to zero, and the
denominator of `C(d)` with it. The registered estimator could not have returned
a meaningful number. Widening the band is not available either: at `L = 42 d`
the line at `i0 = 1929` sits only 3.0 resolution elements above DC, so there is
no room below it for a clean reference.

**The correction, derived.** The noise scale is taken from the statistic's own
degrees of freedom instead of from a neighbouring band, which needs no spectral
room at all. The profile ratio `F` of design 3.2 is an explained sum of squares
over a post-fit residual mean square, and the template costs **two** degrees of
freedom — amplitude and phase — so under a pure-noise null
`E[F] = 2`. Define the **noise-normalised complex amplitude** of segment `s`:

> `z_s = sqrt(F_s / 2) x exp(-i phi_s^{abs})`,
> so that `E[|z_s|^2] = 1` under pure noise and `|z_s|^2 - 1` estimates the
> signal-to-noise power ratio
> <!-- derivation: F is chi-square-like on 2 numerator degrees of freedom
>      against the post-fit residual mean square; computed for this document -->

Both `F_s` and `phi_s` are already emitted by the unmodified instrument, so the
correction removes code rather than adding it.

**The corrected estimators**, replacing the single `C(d)` of section 3.5. Over
all within-object pairs of admitted disjoint segments whose start epochs differ
by `d`:

> **PRIMARY** `C2(d) = SUM Re(z_i conj(z_j)) / sqrt( SUM (|z_i|^2 - 1) x SUM (|z_j|^2 - 1) )`
>
> **SECONDARY** `C1(d) = SUM Re(z_i conj(z_j)) / SUM sqrt( max(|z_i|^2 - 1, 0) x max(|z_j|^2 - 1, 0) )`

`C2` is primary because its denominator sums the debiased powers **before** any
truncation, so independent noise averages toward zero in it rather than being
rectified into a positive bias; `C1` truncates per pair and is therefore biased
low at low per-segment signal-to-noise, which is precisely the regime the 42 d
rung sits in. Both are published. The numerator is common to both and has zero
expectation under independent noise in disjoint segments, which is the property
that makes this measurement possible at a per-segment `F` of order unity.

**What does not change.** The ladder (`L in {42, 210} d`), the segment
admissibility, the linear nuisance basis and its derivation, the fixed-frequency
and per-object-refined variants, the `1/e` definition of `T_coh` and its three
registered boundary cases, the `psi_k` estimand and its `0.30 / 0.10` screens,
and the floor and ceiling arms of section 3.7 are all unchanged. `T_coh` is read
from `C2`, with `C1` published beside it, and a disagreement between them is
reported as the finding rather than resolved by preference.

**Blind spot added.** `E[F] = 2` is exact for a linear model with Gaussian
noise and a fixed frequency; the phase is maximised in closed form rather than
fixed, and the residual is not known to be Gaussian. The normalisation is
therefore a **screen on the noise scale, not a calibrated null**, and the floor
arm of section 3.7 is what measures how far off it is. If the floor arm returns
`|z|^2` far from 1 on the passive control, that number is published and the
coherence values are read against it rather than against 1.
