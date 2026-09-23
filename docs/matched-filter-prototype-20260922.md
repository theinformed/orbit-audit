# T5a matched filter: PROTOTYPE results

> **PROTOTYPE. NOT REGISTERED. NO T5a PRE-REGISTRATION EXISTS.** Nothing below
> is a registered result, no number here carries a p-value, no gate is
> evaluated, and no object's status changes. The design of record is
> `docs/matched-filter-design-20260922.md` (`e51bcce`), whose own banner says
> that when T5a runs, a `docs/t5a-preregistration-<date>.md` is committed alone
> and ahead of every T5a number. That has not happened. This document is the
> instrument and its validation slice — exactly what the design's section 7.1
> puts before a registration and before a cluster ask.

Measured 2026-09-22. Every quantity taken from a committed artifact carries an
inline `<!-- src: -->`; every quantity computed here names the run that produced
it or carries `derivation:`. Every departure from the design is stated where it
occurs and collected in section 7.

**What this is not.** Not the full-catalogue sweep, not a Rung-2 or Rung-3
calibration, not an injection–recovery recall measurement, and not any part of
the 63.5 GPU-hour prototype campaign the design budgets. Those are registered
runs. This is the instrument, 41 offline tests, and three bounded development
slices over 556 named objects.

---

## 0. The three findings, first, including the two that are unwelcome

1. **The design's first two prototype readings are taken and they hold.** The
   band-top crossover is `P_top = 143.75 d`, inside the design's own bracket of
   75.25–163 d, and because it exceeds 100 d the registered nuisance basis stays
   the cubic and the spline fallback is **not** triggered (§2.1). The passive
   calibration half holds **110,382** of 316,028 windows — a share of **0.3493**
   against the design's WORKING FIGURE of 0.43, which is therefore **1.231x
   high**, and every design figure derived from it is that much too large (§2.2).

2. **The five-harmonic sawtooth template does not improve the response at the
   only line this programme has.** On the 1,190 carrier windows whose pilot peak
   lands inside the 14.00 d core, the sawtooth's response is **−2.715 dB**
   against the same statistic's one-harmonic template — a *loss* — while on the
   5,579 same-shell passive control windows it is **+2.543 dB**, a gain. A gain
   the control takes and the treated class does not is not a gain. The design
   predicted +1.65 dB for an ideal sawtooth (§3.5 of the design); measured, on
   real windows, it is negative where it matters (§4.3). The same pattern holds
   in the inclination channel: **−1.771 dB** on carriers, **+2.080 dB** on the
   control.

3. **The design's compute arithmetic is light by about an order of magnitude,
   and the reason is the design's own statistic.** Measured on one card beside
   resident training, an exact profile ratio with the nuisance basis inside the
   fit costs a dense axis running to `2 f_Ny` rather than `f_Ny` (§7.2), and a
   template-reduction stage that is **43.6%–50.2% of compute**, not the "under
   10%" the design ESTIMATES. Scaled to the registered population and the full
   18-member bank, one three-channel sweep is **≈44 GPU-hours**, not the design's
   4.734 (§5.3). Rung 3 at `B = 200` would then be **≈8,900 GPU-hours per
   calibrated sweep**, not 947 — and three of them are about 26,700 GPU-hours
   against a 5,000-hour request. **This is the number that should decide whether T5a is registered at
   all in its present form**, and it is reported before any registration exists
   rather than after cluster time has been spent — which is precisely the lesson
   `docs/phase3-results-20260921.md` draws against itself.

The honest summary of the template question: the design already said the
template change was the smallest of its three effects and "a design sold on
'matched filters are better templates' would be sold on the smallest of the
three". The prototype measures the effect and finds it is not merely small. In
the energy channel, where the design derives the sawtooth from the triaxial
deadband cycle, the extra harmonics cost more in fitted norm than they return in
response. That is the standard matched-filter mismatch penalty, and it says the
real 14.00 d signature is not the one-burn sawtooth the design derives — which is
a physical statement about station-keeping, not a defect in the filter.

---

## 1. What was built

| File | What it is |
|---|---|
| `tools/matched_filter.py` | the template bank, the profile-ratio statistic, closed-form phase maximisation, `k_max(f)`, the refined grid, and the device-memory budgeting. Array-module agnostic, so the offline tests and the GPU run the identical code path. No cuBLAS and no cuSOLVER call anywhere — this environment's CuPy wheel set ships neither — so every contraction is a broadcast-and-sum over a named axis. |
| `tools/matched_filter_prep.py` | the design's section 7.1 CPU-minutes readings: `P_top`, the passive calibration-half window count, the bounded development set and its sampling geometry. |
| `tools/matched_filter_run.py` | the bounded run. It takes an **explicit object list** and has no catalogue default, because the full sweep is a registered run that does not exist. |
| `tools/matched_filter_lines.py` | the descriptive read of a run against the pilot, through `cadence_lines.local_excess` — borrowed, never restated. |
| `tests/test_orbit_matched_filter.py` | 41 offline tests: the bank's closed forms, the design's published power fractions as analytic assertions, the statistic against an independently constructed design matrix, synthetic injection and recovery, and the degeneracies the design declares in advance. |

Committed artifacts: `docs/matched-filter-prep-20260922.json`,
`docs/matched-filter-devset-20260922.json` (the object list, so the run is
reproducible from the repository), `docs/matched-filter-devrun-mm-20260922.json`,
`docs/matched-filter-devrun-s1-20260922.json`,
`docs/matched-filter-devrun-mm-ptop-20260922.json`.

### 1.1 The template family, in closed form

Registered by formula and never by a coefficient file, which is what design
section 2 asks for: a bank read from a data file is a free parameter that can be
edited after a number is visible.

| Shape | Complex harmonic weight `W_k` | Source |
|---|---|---|
| `sawtooth`, duty `d` | `-2i/(pi k) + (1 - e^{-2 pi i k d})/(pi^2 k^2 d)` | derivation: Fourier integral of the one-sided deadband cycle of design 1.1, computed for this module; at `d = 1` it reduces to `-2i/(pi k)`, the ideal sawtooth whose `\|W_k\| = 1/k` is design 3.5's premise |
| `two-burn`, offset `d`, asymmetry `rho` | `(-2i/(pi k)) (1 + rho e^{-2 pi i k d})` | design 1.3(c), the superposition factor stated there |
| `step-train`, duty `d` | `-i (1 - e^{-2 pi i k d})/(pi k)` | derivation: the zero-mean square wave, for a reset that is not instantaneous on the sampling (design section 2) |

The bank is the 18 members design section 2 commits to listing: 3 shapes x 6
duties. The design's parameter table also lists an asymmetry grid `{1.0, 0.5}`,
and 3 x 6 x 2 is 36, so the two statements cannot both be literal; the **count**
is taken as binding because it is what a registration would enumerate, and the
`rho = 0.5` members are exposed separately as `extended_bank()` so either
reading can be adopted without this code changing. The redundant members
(`two-burn` at `d = 1.0` reproduces `sawtooth` at `d = 1.0`) are retained rather
than pruned, as design section 2 requires, and a test asserts the redundancy.

**The weights had to be made complex, and the derivation is in section 7.1.**

### 1.2 The statistic

`F(s, f) = [RSS(N) - RSS(N, s, f, phihat)] / [RSS(N, s, f, phihat) / (n - p)]`,
with the registered cubic `N(t)` carried **inside** the fit, `p = 4 + 2`, and
`phihat` maximised in closed form. The template costs amplitude and phase, two
degrees of freedom, never `2 k_max`, because the harmonic weights are fixed by
the member rather than fitted — a detector that fitted `k_max` free harmonics
would buy its own significance.

Phase is maximised by the design's own second option: the response `R(phi)` and
the fitted norm `G(phi)` are trigonometric polynomials of degree `k_max` and
`2 k_max` in `phi`, evaluated densely on already-reduced quantities, then
refined parabolically and **re-evaluated exactly at the refined phase**. The
first option — rooting the derivative polynomial — is implemented as
`maximise_phase_exact` and is the oracle the tests hold the batched path to.
There is no phase grid in the search and no 128x multiplier anywhere; that part
of the design's compute result survives intact.

**Positive-amplitude convention.** `R^2/G` is invariant under any phase that
flips the sign of `R`, so at `k_max = 1` its maximum is exactly twofold
degenerate. The implementation maximises the signed `R / sqrt(G)` instead, which
fixes the amplitude non-negative and makes the reported phase unique. That
matters because design 2.1 makes the complex harmonic amplitude the core data
product and hands the phase to T4 on a common absolute epoch: a phase that can
silently be `pi` out is not a hand-off.

---

## 2. The readings design section 7.1 puts before any GPU time

### 2.1 The band-top crossover `P_top`

Design 3.4 fixes the band top, before any T5a number exists, as *the longest
period at which the passive excess over local background falls to unity*, and
says the measurement "already exists in a committed artifact and has never been
read out" — naming `docs/cadence-results-20260921-lines.json`
`payloadOnlyLineSweep`.

**That field is not a dense sweep; it holds the twelve strongest lines**
<!-- src: docs/cadence-results-20260921-lines.json payloadOnlyLineSweep, length 12 -->,
and a crossover cannot be read from twelve points chosen for being extreme. The
reading is therefore taken from the pilot's own per-window peak table through
`cadence_lines.local_excess` at the identical geometry — same core, same
annulus, same 0.25 d step — so this reading and the pilot's published line
profile cannot disagree. That is a deviation in provenance, not in rule, and the
rule was applied as written.

| | |
|---|---:|
| Longest period with passive excess at or below 1.0 | **143.75 d** (excess 0.8392) |
| Next step up | 144.00 d (excess 1.0613) |
| Interpolated crossing | 143.931 d |
| Design's bracket from T3's own line table | 75.25 – 163 d — **inside** |
| Spline fallback (design 3.4: triggered if `P_top < 100 d`) | **not triggered**; the basis stays the registered cubic |

<!-- src: docs/matched-filter-prep-20260922.json bandTopCrossover -->

The registered band would therefore be `[2 d, 143.75 d]` — 34.7% of the T3
band's period range removed. Section 6 measures what that does.

### 2.2 The passive calibration-half window count

Design section 11 item 3 carries `q = 0.43` as a WORKING FIGURE and flags every
number that depends on it. Measured:

| Class / half | Objects | Windows | Share |
|---|---:|---:|---:|
| payload | 7,884 | 98,705 | 0.3123 |
| passive, calibration | 5,627 | **110,382** | **0.34928** |
| passive, held-out audit | 5,485 | 106,941 | 0.3384 |
| total | | 316,028 | |

<!-- src: docs/matched-filter-prep-20260922.json passiveCalibrationHalf, derived from docs/cadence-results-20260921.jsonl -->

**The working figure is 1.231x high.** Design section 7.3 budgets the recall
surface at 244 GPU-h using `q = 0.43`; at the measured 0.34928 the same
expression gives **198 GPU-h**. Every other figure carrying that `q` moves by
the same factor.

### 2.3 The development set

| | Objects | Windows on the 14.00 d line |
|---|---:|---:|
| East-west carriers (primary channel, `mean_motion`) | **208** | 1,190 |
| North-south carriers (S1, `inclination`) | **56** | 234 |
| Union | **225** | — |
| In both carrier sets | 39 | — |
| Same-shell GEO passive control | **331** | 5,579 windows total |

<!-- src: docs/matched-filter-devset-20260922.json; recomputed from the pilot shard tables through cadence_lines core geometry, and reproducing the published 208 and 56 exactly -->

The 208 and 56 reproduce the published carrier counts exactly
<!-- src: docs/cadence-results-20260921.md §5.3; docs/cadence-s1s2-results-20260922.md §0 -->,
and the 39-object overlap reproduces the S1/S2 report's "39 of the 56 S1
carriers also carry the 14-day line in mean motion"
<!-- src: docs/cadence-s1s2-results-20260922.md §3.5 -->. That agreement is the
first end-to-end check that this instrument is reading the same population.

### 2.4 `k_max`, measured per object and not assumed

Design 4.2 requires the `k_max` distribution to be a reported output. Over every
(window, fundamental) pair in the development run:

| `k_max` | 0 | 1 | 2 | 3 | 4 | 5 |
|---|---:|---:|---:|---:|---:|---:|
| pairs (millions) | 3.02 | **41.99** | 21.71 | 12.67 | 7.61 | 30.32 |
| share | 2.6% | **35.8%** | 18.5% | 10.8% | 6.5% | 25.8% |

<!-- src: t5a-matched-filter/dev-mm.jsonl.summary.json kMaxHistogramOverWindowFrequencies -->

**Over a third of the searched band retains one harmonic and is therefore the
pilot's sinusoid**, which is design section 6 blind spot 4 measured rather than
argued. At the 14.00 d line itself the picture is the opposite: 224 of the 225
carriers and 330 of the 331 control objects retain all five harmonics
<!-- src: docs/matched-filter-prep-20260922.json samplingGeometry.*.kMaxAt14dHistogram -->,
so the line is measured with the full template and section 4's result is not a
`k_max` artefact. `k_max = 0` marks fundamentals above a window's own Nyquist;
those return `F = 0` rather than a fitted number.

---

## 3. Offline validation

41 tests, `tests/test_orbit_matched_filter.py`, no archive, no GPU, no network.
The whole orbit suite runs **837 tests and is green**, 5 skipped
<!-- src: .venv-gpu/bin/python -m unittest discover -s tests -p 'test_orbit*.py', 2026-09-22 -->
— these 41 plus everything else in the tree, including the T8b tests another
session committed while this work was running. No worktree was needed: the two
errors in `test_orbit_parallel` and `test_orbit_sweep_gpu` that other sessions'
uncommitted edits can produce are not present in the tree as it stands, and the
suite is green in the live tree with those sessions' uncommitted files in place.

What the tests establish, in the order the design earns it:

- **The design's published power fractions, as analytic assertions.** 60.79%,
  75.99%, 82.75%, 88.98% and 91.91% at `k_max = 1, 2, 3, 5, 7`, from partial
  sums of `sum 1/k^2` over `pi^2/6`; and the 1.464x power ratio, **1.65 dB**,
  that design 3.5 calls the honest size of the template effect.
- **The declared degeneracies, confirmed rather than discovered.** A symmetric
  two-burn cycle has only even harmonics (design 1.3(c)); an injected 28 d
  symmetric two-burn is recovered by a one-burn template at 14 d and not at 28 d;
  triaxial libration is at 815.6 d and so out of a band that tops at 220 d
  (design 1.3(b)); continuous low thrust gives a constant `delta n` and zero
  power at every non-zero frequency (design section 6 item 1).
- **Exact synthetic recovery.** An injected template is recovered at the exact
  injected fundamental, at phases 0.0, 1.0, 2.5, 4.7 and 6.0 to better than 0.02
  rad, at amplitudes 0.5, 1.0 and 3.0 to better than 1 part in 10^6, and with the
  template-constrained fit explaining more than `1 - 1e-9` of the post-basis
  variance. The **untruncated** physical sawtooth of design 1.1 is injected
  separately and five harmonics recover 88.98% of its power, which is the check
  that the design's number means what the design says it means rather than
  merely being arithmetic about `1/k^2`.
- **The batched path against an independent computation.** The batched path
  never forms a harmonic column: it reads every harmonic cross-product off one
  trigonometric axis at the sum and difference frequencies. Those reads are
  checked entry by entry against an explicitly constructed design matrix solved
  with `numpy.linalg`, and `F` and the phase are checked against the same.
- **Exactness of the invariances the driver relies on.** `F` is unchanged by
  adding anything inside the nuisance span and by any rescaling, which is what
  licenses the host-side float64 cubic removal that buys back the float32
  mantissa. A window the basis already explains returns `F = 0` rather than a
  ratio of two rounding errors.
- **The phase machinery.** Rooting the derivative polynomial and the dense scan
  agree to 1 part in 10^6; at `k_max = 1` the maximiser returns the closed-form
  arctangent with a positive amplitude; and a 64-point scan plus parabolic
  refinement matches a 2,048-point scan to 1 part in 10^5 in `F` and 5e-3 rad in
  phase, which is what licenses `--phase-points 64` in the production run.

**Numerical precision, measured not asserted.** The same 512 windows were run in
float32 and float64 through `gpu-run`. `F` at 14.00 d agrees to a median
relative difference of **1.6e-5** (p90 6.4e-5, max 2.5e-4); the peak period is
**identical in 512 of 512 windows**; the phase agrees to a median 9.6e-6 rad.
float32 is used for the reported runs on that evidence.

---

## 4. The development run

### 4.1 What ran, and what it cost

Three slices, all through `/home/sdegan/gpu-broker/gpu-run`, class `standard`,
beside a resident 11,264 MiB training claim. `CUDA_VISIBLE_DEVICES` arrived as a
GPU UUID and was never parsed as a number.

| | `mean_motion` | `inclination` | `mean_motion`, band capped at `P_top` |
|---|---:|---:|---:|
| Broker request | `294eee34-…` | `155dc658-…` | `d68c4fd8-…` |
| Card | 0 | 1 | 0 |
| Objects / windows | 556 / **9,336** | 556 / **9,336** | 556 / **9,336** |
| Band | 2 – 220 d | 2 – 220 d | 2 – **143.75 d** |
| Fundamentals per window (mean) | 12,568 | 12,568 | 12,503 |
| Dense-axis evaluations | 3.536e8 | 3.536e8 | 3.536e8 |
| Template evaluations (4 members) | 4.693e8 | 4.693e8 | 4.669e8 |
| Grid stage | 1,109.4 s | **351.3 s** | 884.9 s |
| Reduction stage | 1,117.2 s | **271.1 s** | 843.7 s |
| Reduction share of compute | **50.2%** | **43.6%** | **48.8%** |
| Wall clock | 2,252.4 s | **648.6 s** | 1,751.4 s |
| **Peak CuPy pool actually held** | **1,601.3 MiB** | **1,602.8 MiB** | **1,602.8 MiB** |

<!-- src: /home/sdegan/t5a-matched-filter/dev-{mm,s1,mm-ptop}.jsonl.summary.json -->

**The two full slices evaluate byte-for-byte the same amount of work** —
identical window set, identical grids, identical evaluation counts — and the one
on card 0 took **3.47x** as long as the one on card 1. That is the same
host-contention asymmetry the pilot measured at 2.1x and did not hide
<!-- src: docs/cadence-results-20260921.md §1.2 -->, larger here because a
second job of this programme's own was sharing card 0 for part of the window.
Every throughput figure below is quoted from the **card 1** slice, which is the
one that measures the instrument rather than the queue.

**A defect found in this session's own instrumentation, and fixed.** The first
GPU probe reported a peak pool of 110.5 MiB and that figure was used to claim
`--estimate-mib 900`. It was wrong: the pool was read *after*
`free_all_blocks()`, so it reported what was left rather than what was held. The
true peak is **1,601 MiB**, so the first sharded run executed under an
under-claimed estimate — a real violation of the honest-estimate discipline
design 4.5 requires, caused by measuring the wrong thing. `matched_filter_run`
now records the pool while the batch is still live, and every run reported in
the table above claimed **1,800 MiB** against a measured 1,601. The device pool
requirement of design 4.5 — at or below 2 GiB — **is met, by measurement**.

### 4.2 Does the line survive the change of template?

Line excess at 14.00 d, through the pilot's own `local_excess` geometry at the
**pilot's** grid resolution so the core half-width is the published ±0.109 d:

| `mean_motion` | core peaks | local expected | excess |
|---|---:|---:|---:|
| carriers — pilot (`gls_power`, T3's own peak table) | 1,190 | 13.02 | **91.43x** |
| carriers — this statistic, one harmonic | 1,187 | 13.12 | **90.44x** |
| carriers — sawtooth `d = 1.0`, `k_max = 5` | 1,183 | 10.06 | **117.57x** |
| carriers — step-train `d = 0.5` | 1,207 | 11.16 | 108.19x |
| carriers — two-burn `d = 0.5` | 205 | 0.88 | 234.29x |
| control — pilot | 31 | 7.55 | 4.11x |
| control — one harmonic | 30 | 7.44 | 4.03x |
| control — sawtooth | 27 | 7.77 | **3.48x** |

| `inclination` | core peaks | local expected | excess |
|---|---:|---:|---:|
| carriers — pilot | 234 | 8.31 | **28.15x** |
| carriers — one harmonic | 232 | 8.20 | **28.28x** |
| carriers — sawtooth | 216 | 5.47 | **39.50x** |
| control — pilot | 1 | 0.98 | 1.02x |
| control — sawtooth | 3 | 1.20 | 2.49x |

<!-- src: docs/matched-filter-devrun-{mm,s1}-20260922.json lineExcessAt14d -->

**The strongest single validation in this document is the second row of each
table.** Given the pilot's template — one harmonic — this statistic, which shares
no arithmetic with `gls_power`, puts 1,187 carrier windows on the line against
the pilot's 1,190, at 90.44x against 91.43x, and 232 against 234 in inclination
at 28.28x against 28.15x. Window by window rather than by count, **1,167 of the
pilot's 1,190 are the same windows — 98.1%** — and 230 of the 234 in inclination,
**98.3%**
<!-- src: recomputed from t5a-matched-filter/dev-{mm,s1}.jsonl against the pilot shard tables, (norad, window) set intersection inside the pilot core -->.
The instrument reproduces the pilot when it is asked to be the pilot, not merely
in aggregate but on the same objects' same windows. With the five-harmonic
sawtooth the agreement drops to 1,076 of 1,190 (90.4%) and 198 of 234 (84.6%):
the template moves about one carrier window in ten off the line.

**The excess rises with the sawtooth, but for a reason that is not a gain.** In
both channels the core count falls (1,190 → 1,183; 234 → 216) and the *local
background* falls further (13.02 → 10.06; 8.31 → 5.47). The template thins the
neighbourhood more than it thins the line, which raises a ratio. It does not put
more windows on the line, and section 4.3 shows it does not raise the response
of the windows that are on it.

**These excesses are not comparable to the published 10.16x and 15.85x.** Those
were computed over every payload (or every GEO payload) window; these are
computed over the 3,757 windows of 225 *selected* carriers, so the local
background is a different population. **The carrier set is selected by the
pilot**, which makes any carrier-side excess circular in the pilot's favour; the
unselected same-shell control rows and the paired per-window comparison of
section 4.3 are the ones that carry weight.

The two-burn `d = 0.5` member's 234.29x is an artefact and is reported as one:
its local expectation is 0.88 windows. A ratio against a background below one
window cannot exclude anything, which is the caveat
`docs/cadence-s1s2-results-20260922.md` §3.3 already had to make about the GEO
passive control.

### 4.3 The response gain at the line — the unwelcome result

The profile ratio's numerator is the explained sum of squares, so for a weak
signal `F` is proportional to explained **power** and the ratio of two members'
`F` at the same frequency on the same window is a power gain. This is a paired,
within-window comparison: the same statistic, the same nuisance basis, the same
windows, differing only in the template. Selection of the carriers cannot bias
it.

**Sawtooth `d = 1.0`, `k_max = 5`, against one harmonic, at 14.00 d:**

| Population | windows | median gain | mean gain | fraction above unity |
|---|---:|---:|---:|---:|
| `mean_motion`, all carrier windows | 3,757 | +0.778 dB | +1.178 dB | 0.590 |
| `mean_motion`, **windows the pilot put on the line** | 1,190 | **−2.715 dB** | −1.869 dB | **0.308** |
| `mean_motion`, same-shell control | 5,579 | **+2.543 dB** | +3.562 dB | 0.796 |
| `inclination`, all carrier windows | 3,757 | +0.663 dB | +1.261 dB | 0.591 |
| `inclination`, **windows the pilot put on the line** | 234 | **−1.771 dB** | −1.685 dB | **0.179** |
| `inclination`, same-shell control | 5,579 | **+2.080 dB** | +2.884 dB | 0.779 |
| design 3.5's prediction, ideal sawtooth | — | +1.65 dB | — | — |

<!-- src: docs/matched-filter-devrun-{mm,s1}-20260922.json responseGainAtTheLine -->

**The measured gain has the wrong sign on the treated class and the right sign
on the control, in both channels.** The step-train member is nearly neutral
(−0.038 dB on the mean-motion line windows); the symmetric two-burn member is
catastrophic (−10.5 dB), which is what design 1.3(c) predicts, since it deletes
the odd harmonics and the fundamental with them.

The mechanism is the ordinary matched-filter mismatch penalty and it is visible
in the statistic's own algebra: harmonics 2–5 enter the fitted norm `G` whether
or not the data carry them, so a template that weights absent harmonics divides a
response it did not increase. That the *control* gains from them says the extra
harmonics are picking up broadband structure that both classes have. The reading
is therefore that **the 14.00 d signature in these objects is not the one-burn
sawtooth the design derives from the triaxial deadband cycle.** Three readings are
available and this pass does not choose between them:

1. real east-west keeping at these slots is executed as a burn pair or a
   multi-burn schedule, whose odd harmonics are suppressed (design 1.3(c));
2. the harmonics are present in the true `delta n` but below the archive's own
   noise at `k >= 2`, so weighting them adds norm and no response — which is
   exactly the sensitivity question design section 11 item 1 says cannot be
   answered until per-element covariances exist;
3. the fitted TLE `delta n` is a smoothed estimate whose effective bandwidth
   attenuates the higher harmonics before the detector ever sees them.

All three are testable, none is tested here, and **the injection–recovery arm of
design 7.3 is the measurement that separates them.** Until it runs, the template
change is unsupported by this programme's only measured line.

### 4.4 Carrier versus control, and the separation design 5.2(c) wants published first

Design 5.2(c) says the point-estimate separation is computed and published
**before** the scale run, because "if the point-estimate separation from the
prototype is already below the 10x gate, the scale run is not a power problem
and the registration says so before the cluster time is spent."

Median `F` at 14.00 d, carriers against the same-shell GEO passive control,
`mean_motion`:

| Member | carrier median `F` | control median `F` | ratio |
|---|---:|---:|---:|
| one harmonic (the pilot's template) | 8.634 | 0.807 | **10.70** |
| sawtooth `d = 1.0` | 13.271 | 1.611 | **8.24** |
| step-train `d = 0.5` | 8.423 | 1.160 | 7.26 |
| two-burn `d = 0.5` | 6.660 | 1.253 | 5.32 |

<!-- src: docs/matched-filter-devrun-mm-20260922.json carrierVersusControlAtTheLine -->

**Read as a screen and never as the registered quantity.** It is a ratio of
medians, not the bound-to-bound separation Paper B's gate computes; there is no
clustered object-level estimator behind it, no Jeffreys interval, and the
carrier side is a pilot-selected population. With all of that said, what it says
is unambiguous and points the same way as section 4.3: **the sawtooth template
lowers the carrier/control separation from 10.70 to 8.24.** Whatever the
registered estimator eventually returns, nothing in this slice suggests the
template change moves the separation towards the 10x bar, and the design's own
rule says that is a fact to publish before asking for cluster time, not after.

### 4.5 Phase

The complex harmonic amplitude and the fitted phase at 14.00 d are retained and
written per window per member, which is design 2.1's requirement and T4's first
declared dependency. The circular mean resultant length of the phase at 14.00 d,
pooled over carrier windows, is 0.063 (`mean_motion`) and 0.075
(`inclination`) for the sawtooth member
<!-- src: docs/matched-filter-devrun-{mm,s1}-20260922.json phaseAtTheLine -->.
**That is not a synchrony statistic and is not registered as one** — it pools
windows across objects, which is not the quantity T4 defines — and it is
reported only to show the channel exists and carries a number. The two-burn
member's 0.31 is an artefact of that member's near-degenerate response and
should not be read as structure.

---

## 5. The compute case, recomputed from measurement

### 5.1 What survives of the design's result

The analytic phase maximisation is real and it works. There is no phase axis in
the search, and the 128x "shape x phase" multiplier the compute request carries
<!-- src: docs/hpc-access-request-20260921.md §5.2 --> is deleted, exactly as
design 3.2 argues. The 18 members are 18 weightings of the same `k_max` complex
numbers and share one pass over the data, which is design 4.3's structure and is
what this implementation does.

### 5.2 What does not

| | design 4.4 | measured / corrected |
|---|---:|---:|
| Dense axis | 33,721 points, sized to `f_Ny` | sized to **2 `f_Ny`** (section 7.2); in this population the measured mean is **37,876** points per window |
| Grid-stage rate, one card | 1.876e6 sinusoid fits/s | **1.0066e6** window-dense evaluations/s |
| Reduction stage | ESTIMATE "under 10% of the grid stage" | **43.6%** of compute at 4 members on card 1; **50.2%** on card 0 |
| Reduction scaling in bank size | not priced | measured **near-linear**: 2 members 43.89 s, 4 members 80.43 s on the same 512 windows, both on card 0 in the same command. Section 4.1's 3.47x placement asymmetry means a single pair of timings is a weak slope; it is an EXTRAPOLATION to 18 members and is flagged again in section 8 |
| Template-reduction rate | — | **1.7316e6** template evaluations/s |

<!-- src: /home/sdegan/t5a-matched-filter/dev-{mm,s1}.jsonl.summary.json; f32/f64/one-member slices -->

The grid-stage rate is **0.537x** the design's assumed figure, and honestly so:
the design's 1.876e6 is a rate for *sinusoid fits*, six reductions per
(window, sample, frequency). Carrying the detrend basis inside the fit costs ten:
two for the data and eight for the cubic's projection onto every harmonic column.
The ratio 6/10 = 0.6 brackets the measured 0.537 to within the cost of the
larger arrays, so the slowdown is the statistic's price and not an implementation
defect. **It is a price the design did not include.**

### 5.3 One sweep, recomputed

Per channel, at the registered population of 316,028 windows, taking the
uncontended card-1 rates:

> grid: 316,028 x 37,876 = 1.1968e10 dense evaluations / 1.0066e6 s^-1
> = **11,889 s = 3.302 h**
> <!-- derivation: computed for this document from the measured per-window dense
>      axis and the measured card-1 grid rate -->
>
> reduction, 18 members: 18 x 316,028 x 12,568 = 7.1497e10 template evaluations
> / 1.7316e6 s^-1 = **41,290 s = 11.47 h**
> <!-- derivation: same, with the measured near-linear member scaling of §5.2.
>      EXTRAPOLATION from a 4-member measurement, not a measurement at 18. -->

| | design 4.4 | corrected |
|---|---:|---:|
| One channel | 1.578 h | **14.77 h** |
| Three channels — one sweep | **4.734 GPU-h** | **44.3 GPU-h** |
| Rung 3, `B = 200`, one calibrated sweep (design 5.3) | 947 GPU-h | **≈8,860 GPU-h** |
| Three registered calibrated sweeps (design 7.3) | 2,855 GPU-h | **≈26,700 GPU-h** |
| Design's prototype total (design 7.1) | 63.5 GPU-h | **≈594 GPU-h** |

**The design's campaign does not fit the 5,000 GPU-hour request at Rung 3 once
its own statistic is priced.** Three responses exist and the prototype does not
choose between them; a registration must:

1. **Rung 2 becomes load-bearing rather than optional.** At 3.16x one sweep it is
   ≈140 GPU-h, and the whole campaign collapses to a few hundred hours. Design 7.2
   already fixes the screen that decides it — held-out passive exceedance inside
   [0.5%, 2.0%] — and that test is *not run here*.
2. **The bank shrinks.** The reduction stage is linear in members and members are
   most of the cost. Section 4.3 measured three of the four members as neutral or
   harmful on the only known line; a registration that enumerated 4 members
   instead of 18 would cost 2.55 GPU-h of reduction per channel, not 11.5.
3. **The statistic is approximated.** Taking the projected harmonic columns as
   orthogonal removes the Gram read, the `2 f_Ny` axis, and most of the reduction
   stage. That is a different detector and it must be registered as one; it is
   named here as an option and is **not** what this implementation does.

---

## 6. The band top, exercised

The design's section 3.4 rule was read in section 2.1 and it is exercised here
rather than left as a number no code has used: the whole `mean_motion`
development set was re-run with the band capped at `[2 d, 143.75 d]` and nothing
else changed.

**First, the check that the cap did only what it should.** `F` at a fixed
frequency cannot depend on where the band ends, and it does not: the
carrier-against-control median ratios at 14.00 d are **identical to five
significant figures** across the two runs — 8.24 for the sawtooth, 10.70 for one
harmonic, 7.26 for the step-train, 5.32 for the two-burn. Only the assignment of
each window's *peak* moves. That is an end-to-end confirmation that the band is a
search-range parameter in this implementation and not a hidden input to the
statistic.

**What moves.** Every peak above 143.75 d — 20.7% of carrier windows and 26.9%
of control windows under the pilot's own template — is pushed back into the
remaining band, which raises the local background everywhere, including at 14 d:

| `mean_motion`, 14.00 d | band 2–220 d | band 2–143.75 d |
|---|---:|---:|
| carrier core peaks, sawtooth | 1,183 | 1,188 |
| carrier local expected, sawtooth | 10.06 | 11.05 |
| **carrier excess, sawtooth** | **117.57x** | **107.54x** |
| control core peaks, sawtooth | 27 | 30 |
| control local expected, sawtooth | 7.77 | 10.83 |
| **control excess, sawtooth** | **3.48x** | **2.77x** |
| carrier/control excess ratio, sawtooth | 33.8 | **38.8** |
| carrier/control excess ratio, one harmonic | 22.4 | **25.7** |
| carrier peaks above 143.75 d, sawtooth | 20.6% | 0.0% by construction |
| control peaks above 143.75 d, sawtooth | 26.9% | 0.0% by construction |

<!-- src: docs/matched-filter-devrun-mm-20260922.json and docs/matched-filter-devrun-mm-ptop-20260922.json, lineExcessAt14d and peakPeriodDistribution -->

**The verdict on this bounded set: the cap helps, modestly, and in the direction
the design predicts.** Both excesses fall, the control's falls further, and the
payload-over-control excess ratio improves by 15% for the sawtooth and 15% for
the pilot's template. It does not transform anything.

**And the reason it does not is worth stating, because it qualifies the design's
own diagnosis.** Design 3.1 cites 87.64% of *passive* window peaks landing above
100 days. That figure is over the whole passive class, which is dominated by LEO
debris carrying real drag decay. Inside the geostationary ring, the same-shell
passive control puts only **32.4%** of its peaks above 100 d and 26.9% above
143.75 d, and the carriers only 23.6% and 20.7%. **The band-top contamination
the design's most important fix addresses is about three times weaker in the GEO
regime than in the pooled population the diagnosis was drawn from.** A
registration that expects the band-top rule to carry the detector at GEO should
expect the 15% measured here, not the 87.64% that motivated it. Whether it
carries more in LEO is untested: no LEO object was run.

---

## 7. Deviations from the design, each with its derivation

The design is the design of record and this is an implementation of it, not a
variant. Seven places needed a decision the design did not determine, or
determined in a way that measurement contradicts. Each is named, derived, and
reported rather than silently taken.

### 7.1 The harmonic weights had to be complex

Design 3.2 writes the matched response as `R(phi) = sum_k w_k Re(c_k e^{-ikphi})`
with **real** `w_k`. Real weights describe the waveform
`sum_k w_k cos(2 pi k f t - k phi)`, and with `w_k = 1/k` that waveform is
`-ln(2 sin(theta/2))` — a log-singular pulse train, not a sawtooth. The
sawtooth's harmonics are all in **sine** phase relative to the reset:

> `s(t) = -(2/pi) sum_k (1/k) sin(2 pi k f t)`, phase origin at the burn
> <!-- derivation: the standard sawtooth series (-1)^(k+1)/k sin(k x), shifted by
>      half a period, which turns (-1)^(k+1) into -1 for every k -->

A constant −90° offset common to every harmonic **cannot** be absorbed into
`phi`, because `phi` rotates harmonic `k` by `k phi` and not by a constant. The
weights are therefore complex, `R(phi) = sum_k Re(W_k c_k e^{-ikphi})`, which is
the design's expression with a complex `w_k`. The structure is untouched — still
a trigonometric polynomial of degree `k_max`, so the closed-form phase
maximisation stands — and so are the `|W_k| = 1/k` power fractions of design 3.5.
The notation needed widening to hold the family the design registers.

### 7.2 The dense axis runs to `2 f_Ny`, which doubles a published cost

Design 4.3 sizes the dense grid to `f_Ny`, on the grounds that the retained
harmonics satisfy `k f <= f_Ny`. That covers the harmonic **amplitudes**. It does
not cover the harmonic **Gram**: the exact profile statistic needs the inner
products between harmonic columns `k` and `l`, and by the product-to-sum
identities those are read at the **sum** frequency `(k + l) f`, which reaches
`2 f_Ny`. A grid stopping at `f_Ny` can only form a statistic that assumes the
harmonic columns are orthogonal, which on an irregularly sampled, gapped window
they are not. Section 5.3 carries the cost.

### 7.3 Fundamentals are integer multiples of `df'`

Design 4.3 has every fundamental "read its harmonics off that one grid". That
read is exact only if `k f` is itself a grid point for every retained `k`. The
pilot grid starts at `f_min = 1/220`, which is not an integer multiple of
`df' = 3.70370e-5 c/d`, so on that grid the harmonics land between points and the
read costs an interpolation error that is largest at the highest retained
harmonic — the exact error the refinement by `k_max` exists to remove. Anchoring
the grid at zero makes `f = i df'` and `k f = (k i) df'`, so every harmonic of
every fundamental is a grid point. The cost is that the band's low edge moves by
less than one grid step: the lowest fundamental is **219.51 d**, not 220.00 d.

### 7.4 The bank is 18 at `rho = 1`

Design section 2's parameter table lists an asymmetry grid `{1.0, 0.5}` and its
prose says "**18 shape members** … 3 shapes x 6 duties". 3 x 6 x 2 = 36. The
count is taken as binding, because it is what a registration would enumerate
literally, and the `rho = 0.5` members are implemented and exposed under
`extended_bank()` so a registration can adopt either reading without this code
changing.

### 7.5 `P_top` is read from the pilot's peak table

Design 3.4 names `payloadOnlyLineSweep` in
`docs/cadence-results-20260921-lines.json` as the source. That field holds twelve
lines, not a dense sweep, and a unity crossing cannot be read from twelve points
chosen for being extreme. The rule was applied as written to the pilot's own
per-window peak table through the same `local_excess` geometry. Section 2.1.

### 7.6 The phase carries a positive-amplitude convention

Section 1.2. `R^2/G` is degenerate under a sign flip of `R`; maximising the
signed `R/sqrt(G)` makes the reported phase unique. The design does not specify a
convention and T4 needs one.

### 7.7 A degenerate-window guard

A window the nuisance basis already explains to numerical precision has no
residual for any template to compete for, and `F` would be a ratio of two
rounding errors. Such windows return `F = 0` and are counted, rather than
publishing noise. The design does not mention the case; it arises on synthetic
inputs and on any window whose channel is a polynomial to within the archive
quantum.

---

## 8. What remains before the registered prototype campaign

Named, not estimated, and each is a real hole.

1. **The Rung-2 transfer test is not run.** Design 7.2 calls it the prototype's
   most valuable single output and it decides whether the cluster ask is 15
   GPU-h per calibrated sweep or 947 — now 140 or 8,860 (§5.3). It needs
   geometry-class surrogate thresholds from the passive calibration half applied
   to the held-out audit half. **UNPROVEN, and it is the single most valuable
   thing this prototype did not do.**
2. **No null, no p-value, no threshold, no gate.** Nothing in this document is
   inferential. The per-object null of design 5.3 is not implemented at any rung.
3. **Recall is unmeasured**, as it is everywhere in this programme. The
   injection–recovery arm of design 7.3 is also what would separate the three
   readings of section 4.3, so it is now load-bearing for the template question
   and not only for recall.
4. **The 14.00 d line's predicted one-sidedness is not tested.** Design 1.3(a)
   predicts a sharp lower edge at 14 d with a tail to longer periods, and says
   the refined grid can see it where the pilot's grid could not. The refined grid
   is built and the run is on it; the asymmetry test itself was not written.
5. **The 18-member cost is an extrapolation**, from a measured near-linear
   4-member scaling. It is not a measurement at 18.
6. **The full-catalogue sweep, any Rung-3 calibration, and the 63.5 GPU-h
   campaign were not run**, by instruction and by the design's own split.
7. **The element weights remain a screen**, per design 3.3, and every interval
   this detector will publish inherits that status until per-element covariances
   exist.
8. **The same-shell control is thin at the line in inclination** — 1 to 3 core
   windows against about one expected — so its silence there carries the same
   little weight `docs/cadence-s1s2-results-20260922.md` §3.3 already flagged.
9. **`k_max` is computed from each window's own median spacing.** Median spacing
   is not the same as a window function, and a gapped window's effective Nyquist
   is not its median-spacing Nyquist. The design asks for per-object `k_max` and
   that is what is implemented; a more careful ceiling would come from the
   spectral window, which `tools/cadence_spectral_window.py` already computes and
   which nothing here consumes.

---

## 9. Honest summary

The instrument is built, it is tested offline in 41 assertions, and it
reproduces the pilot exactly when asked to be the pilot — 1,187 of the same
1,190 carrier windows on the same line at 90.44x against 91.43x, through
arithmetic that shares nothing with `gls_power`. Two readings the design put
before any GPU time are taken: the band top is 143.75 d, inside the design's
bracket and above the spline threshold, and the passive calibration half is
110,382 windows, so the design's working figure was 1.231x high.

The two things the prototype was built to find out both came back against the
design. The sawtooth template does not improve the response at the only line
this programme has measured: −2.7 dB on the windows that carry it and +2.5 dB on
the control, where the design predicted +1.65 dB for an ideal sawtooth. And the
compute case is about 9.4x the design's figure once its own statistic is priced
exactly, which puts the registered Rung-3 campaign at about 26,700 GPU-hours
against a 5,000-hour request.

Neither is a reason to stop. The first says the 14.00 d signature is not a
one-burn sawtooth and points at the injection–recovery arm to say what it is.
The second says the registration should make Rung 2 load-bearing or enumerate a
smaller bank, and both of those are decisions a registration can take with these
numbers in hand rather than after cluster time is spent. The design asked for
exactly this: the point-estimate separation published before the scale run. It
is 10.70 for the pilot's template and 8.24 for the sawtooth, and the bar is 10.
