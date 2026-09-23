# T5a — Matched-filter manoeuvre detection: DESIGN

> **STATUS: DESIGN ONLY. NOTHING HERE IS REGISTERED, NOTHING HERE IS
> IMPLEMENTED, AND NO NUMBER BELOW IS A MEASUREMENT OF T5a.** The day T5a
> runs, a separate `docs/t5a-preregistration-<date>.md` is committed **alone
> and ahead of every T5a number**, in the manner of
> `docs/cadence-preregistration-20260921.md` (`1a51afe`, committed 32 minutes
> before any T3 code existed) and `docs/phase3-preregistration-20260921.md`
> (`7eab5a4`). Section 12 is a skeleton of that future registration, not the
> registration itself.

Written 2026-09-22. Every quantity taken from a committed artifact carries an
inline `<!-- src: -->` naming the document and field; every quantity computed
for this document carries `derivation:`; every forward design choice that no
measurement supports is marked **ESTIMATE** and is not dressed as a derivation.
Thresholds proposed here are **screens**, not laws, and each says what it
screens for.

Measured inputs this design is built on:

- `docs/cadence-results-20260921.md` — the T3 pilot: what failed, why, and at
  what cost.
- `docs/synchrony-design-20260921.md` — T4, which requires the fitted phase T3
  discards.
- `docs/phase3-results-20260921.md` — the covariate transfer failure that any
  new detector must clear.
- `docs/paper-b-draft-20260921.md` §§2.1–2.7 — the acceptance harness.
- `docs/hpc-access-request-20260921.md` §5 — the measured throughput this
  document's arithmetic scales from.

---

## 0. The design in one paragraph

T3 measured three specific defects and priced the fourth thing everybody
assumed was the problem. Compute is **not** the bottleneck: two consumer cards
evaluated 316,028 window-periodograms over a 2,676-point frequency grid —
8.457e8 sinusoid fits — in 17.6 minutes of wall clock beside an unrelated
training job, and the uncontended shard's rate implies one RTX 4080 sweeps the
whole catalogue in about 7.5 minutes
<!-- src: docs/cadence-results-20260921.md §§1.2, 7 -->. The defects are
(i) template mismatch — a sinusoid against a sawtooth; (ii) trend leakage, with
87.64% of passive window peaks landing above 100 days and a calibration-half
99th percentile of normalised power at 0.9641; (iii) a window-level threshold
that does not transfer across an object-level split, the held-out passive class
firing 9.32% against the payloads' 3.36% where 1% was nominal
<!-- src: docs/cadence-results-20260921.md §§2.2, 4 -->. This design changes the
template to a physically derived sawtooth family with explicit phase, replaces
the max-normalised-power statistic with a profile statistic that carries the
detrend basis inside it, and makes per-covariate-stratum false-alarm control a
first-class registered output rather than a retrofit. It retains the fitted
phase, which is both the matched filter's own free parameter and T4's first
declared dependency. It is accepted or rejected by the same mechanical gate
Paper B describes, unchanged.

**The single most important honest statement in this document:** the template
change alone is worth about 1.6 dB (§3.5). The measured failure was dominated by
trend leakage and by the choice of aggregator, not by the sinusoid. A design
sold on "matched filters are better templates" would be sold on the smallest of
the three effects.

---

## 1. What the physics says the template is

### 1.1 The east-west deadband cycle, derived

T3's §5.3 derives the longitude acceleration at the geostationary ring from
Earth's triaxiality,

> `d²λ/dt² = −18 n² J22 (R_e/a)² sin(2(λ − λ22))`,

and evaluates its amplitude at `J22 = 1.8154e-6`, `a = 42164.2 km`,
`n = 2π/86164.0905 s⁻¹` as `A_max = 3.976e-15 rad s⁻² = 1.7006e-3 deg/day²`
<!-- src: docs/cadence-results-20260921.md §5.3; cadence-results-20260921-lines.json derivations.geoLongitudeAccelerationDegPerDay2 -->.
This design takes that derivation as given and carries it one step further,
because the *shape* of the observable — not its period — is what the template
family has to match.

Write the drift in longitude as `λ̇`. Over a deadband whose half-width `Δλ` is
small enough that `sin(2(λ − λ22))` is constant across it, the acceleration is a
constant `A = A_max |sin(2(λ_slot − λ22))|`, and the station-keeping cycle used
at a non-equilibrium slot is the one-sided cycle: the satellite is placed at one
edge of the box with a drift rate directed across it, the triaxial acceleration
decelerates the drift, reverses it, and carries the satellite back to the
starting edge, where one impulsive burn restores the initial drift rate.

Over one cycle of duration `T`, the drift rate runs linearly from `+v₀` to
`−v₀` and is then reset by a single impulse of size `2v₀`, so

> `v₀ = A·T/2`, one-way excursion `= v₀²/(2A) = A·T²/8 = 2Δλ`, hence
> `Δλ = A·T²/16` and `T = 4·sqrt(Δλ/A)`
> <!-- derivation: constant-acceleration kinematics; reproduces the T = 4·sqrt(Δλ/A) relation already published in docs/cadence-results-20260921.md §5.3 -->

and therefore, **in the drift-rate channel the cycle is an exact sawtooth: a
linear ramp with a discontinuous reset, duty 1, one impulse per period.** In the
longitude channel it is a single parabolic arch across the box, continuous with
a slope discontinuity at the burn.

This matters because T3 measured the **energy channel** (`mean_motion`), and
longitude drift rate *is* the energy channel: `λ̇ = n − ω_E`, so the mean-motion
residual `δn` is the sawtooth itself, not its integral. A sinusoid is the wrong
template for it, which is the conclusion T3 §4 reached from the other direction.

### 1.2 The amplitude the template is looking for

At the max-acceleration longitude with `T = 14.0 d`:

| Quantity | Value |
|---|---:|
| `Δλ = A·T²/16` | **±0.02083°** <!-- src: docs/cadence-results-20260921.md §5.3 table, ±0.0208° --> |
| `v₀ = A·T/2` | **±1.1904e-2 deg/day** <!-- derivation: 1.7006e-3 × 7 --> |
| `δn = v₀` in rev/day | **±3.3067e-5 rev/day** <!-- derivation: 1.1904e-2 / 360 --> |
| `δn/n` | **3.298e-5** <!-- derivation: ÷ 1.00273896 rev/day --> |
| `δa = −(2/3)·a·(δn/n)` | **∓0.927 km**, peak-to-peak 1.854 km <!-- derivation: (2/3) × 42164.2 × 3.298e-5 --> |

**This amplitude cannot yet be turned into a signal-to-noise ratio, and the
design says so rather than inventing one.** The programme has no measured
per-element uncertainty on catalogue mean motion for geostationary payloads;
honest per-element covariances are precisely what T5c is for
<!-- src: docs/hpc-access-request-20260921.md §6, T5c: "No per-re-fit cost has ever been measured in this programme." -->.
Until T5c or an equivalent measurement exists, the element weights in §3.3 are a
screen, not a measurement, and the design's predicted sensitivity is UNMEASURED
(§11, item 1).

### 1.3 Three consequences that make the template family falsifiable

**(a) The period is slot-dependent and the line should be one-sided.** Since
`T = 4·sqrt(Δλ/A)` and `A = A_max|sin(2(λ_slot − λ22))|`, a fleet of satellites
all holding the same `±0.0208°` box shows `T = 14.0 d` only at the
max-acceleration longitudes and *longer* periods everywhere else — `T` grows as
`A^(−1/2)`, reaching 19.8 d at half the maximum acceleration and diverging at
the stable nodes. **The prediction is a sharp lower edge at 14 d with a tail to
longer periods, not a symmetric line.** T3's measured 14.00 d feature has a core
half-width of ±0.109 d, which is exactly three grid steps
<!-- derivation: 3 × 1.85185e-4 c/d = 5.556e-4 c/d, which at f = 1/14 d is ±0.109 d; grid from docs/cadence-s1s2-preregistration-20260922.md §"Frequency grid" -->
— it is grid-limited, so the pilot could not have seen the asymmetry either way.
§4.1's refined grid can.

**(b) Natural longitude libration is out of band, which strengthens any in-band
GEO detection.** Near a stable node, `λ̈ ≈ −2A_max·Δλ` in radians, so the
libration is simple harmonic with `ω = sqrt(2 × 3.9756e-15) = 8.917e-8 rad/s`
and

> `T_lib = 2π/ω = 7.046e7 s = 815.6 days`, and longer still at finite amplitude
> <!-- derivation: computed for this document from the A_max published in docs/cadence-results-20260921.md §5.3 -->.

The registered band tops out at 220 days, so **triaxial libration cannot produce
an in-band GEO line in the energy channel.** The remaining in-band natural terms
at GEO are lunar: T3 measured the half-sidereal (13.661 d) and half-synodic
(14.765 d) months at payload excesses of 0.72x and 0.44x — absent — and the
27.5 d family at 8.17x in the passive control
<!-- src: docs/cadence-results-20260921.md §§5.1, 5.2 -->. The natural in-band
content at GEO is therefore short and enumerable, which is why the 14.00 d line
at 10.16x with the control at 0.94x is the cleanest known template target
<!-- src: docs/cadence-results-20260921.md §5.3 -->.

**(c) A symmetric two-burn cycle is indistinguishable from a one-burn cycle at
half the period.** Real east-west keeping is sometimes executed as a burn pair.
Superposing two sawtooths offset by a fraction `d` of the period multiplies the
`k`-th harmonic weight by `(1 + e^(−2πikd))`, which vanishes for odd `k` when
`d = 1/2`: a symmetric two-burn 28-day cycle has **only even harmonics** and is
spectrally a 14-day one-burn cycle
<!-- derivation: linearity of the Fourier transform under time shift; computed for this document -->.
The template family must carry the duty parameter explicitly, the degeneracy
must be declared in the registration rather than discovered, and the 28 d
alias sits uncomfortably close to the 27.5 d natural line T3 already attributed
to ETALON — which is the reason §5.2 of T3 exists.

---

## 2. The template family

Registered in advance, closed, and small enough that every member can be listed
in the registration.

| Parameter | Grid | Basis |
|---|---|---|
| Fundamental period `P` | the frequency grid of §4.1 | search parameter |
| Shape | `{sawtooth, two-burn, step-train}` | §1.1, §1.3(c), and the step-train for cycles whose reset is not instantaneous on the sampling |
| Duty `d` | `{0.5, 0.6, 0.7, 0.8, 0.9, 1.0}` | fraction of the period between successive resets; `d = 1.0` is the one-burn cycle of §1.1 |
| Asymmetry `ρ` | `{1.0, 0.5}` | relative size of the second impulse where there is one; `ρ = 1` is the symmetric pair of §1.3(c) |
| Phase `φ` | **continuous, maximised in closed form** — §3.2 | not a grid |
| Harmonics retained `k` | `1 … k_max(f)`, §4.2 | derived, not chosen |

**18 shape members** (`sawtooth` × 6 duties is degenerate with the two-burn
family at `d = 1`; the enumerated set is 3 shapes × 6 duties, with the redundant
members retained rather than pruned so the registration can list them literally)
<!-- ESTIMATE: the duty and asymmetry grids are forward design choices. Nothing measured fixes their spacing. -->

Every member's harmonic weights `w_k(shape, d, ρ)` are closed form, so the
family is specified by a formula in the registration rather than by a file of
fitted coefficients. That is a deliberate constraint: a template bank read from
a data file is a free parameter that can be edited after a number is visible.

### 2.1 Phase is retained, and this is a hand-off, not a by-product

T3 computes the fitted phase inside `gls_power` and discards it. T4 names
recovering it as its **first implementation task**, and names the terms that
already exist (`YC`, `YS`, `CC`, `SS`, `CS`) as giving the fitted amplitude and
phase in closed form
<!-- src: docs/synchrony-design-20260921.md §3.5, "DOES NOT EXIST — T3 computes it inside gls_power and discards it" -->.
This design does not merely retain phase; **the complex harmonic amplitude is
the core data product**, because §3.2 maximises the matched-filter statistic
over phase analytically from those amplitudes. The T5a output artifact therefore
carries, per window per channel, the complex amplitude at each retained harmonic
referred to **one absolute epoch** — which is T4's §3.2 requirement, stated
there as "phase is only meaningful relative to a common clock" — and T4's phase
channel becomes a read of a T5a artifact rather than a separate pass.

---

## 3. The statistic

### 3.1 Why the registered statistic failed, restated as a design constraint

T3's per-object statistic was `max P_max` over an object's windows, `P_max`
being the maximum normalised generalised-Lomb-Scargle power over the 2–220 day
band. Three measured facts constrain the replacement:

1. **87.64% of passive window peaks and 63.93% of payload window peaks land
   above 100 days**, and the calibration-half pooled 99th percentile of `P_max`
   is **0.9641** — one window in a hundred fit to 96% of its variance by a single
   sinusoid <!-- src: docs/cadence-results-20260921.md §4(a) -->. A smooth
   residual does that; a manoeuvre rhythm does not.
2. **The band's top is a shoulder, not a line.** At 180.75 d the excess over
   local background is 20.4x in payloads and **38.4x in the passive control**,
   with a core half-width of ±18.2 d <!-- src: docs/cadence-results-20260921.md §4(b) -->.
   A feature 37 days wide is the unfitted curvature of drag decay surviving the
   per-window cubic.
3. **`max` over windows rewards the control.** Passive objects carry a median of
   17 usable windows against payloads' 4, and their max-over-windows statistic
   is *higher* — median 0.374 against 0.161 — even within matched window-count
   bands, because a payload's history is broken up by the very manoeuvres being
   searched for <!-- src: docs/cadence-results-20260921.md §§4(c), 6 -->.

### 3.2 Per window: a profile statistic with the nuisance basis inside it

For window `w`, channel `c`, fundamental frequency `f` and template member `s`,
form one weighted least-squares design matrix

> `X = [ N(t) | H(t; f, k_max(f)) ]`

where `N(t)` is the **nuisance basis** — the registered detrend basis of §3.4,
carried *inside* the fit rather than subtracted beforehand — and
`H = {cos(2πkft), sin(2πkft)}` for `k = 1 … k_max(f)`.

The fit returns complex harmonic amplitudes `c_k = a_k + i b_k`. For template
weights `w_k(s)` the matched response at phase `φ` is
`R(φ) = Σ_k w_k · Re(c_k · e^(−ikφ))`, a trigonometric polynomial of degree
`k_max`. **Maximising over `φ` is therefore a one-dimensional maximisation over
`k_max` complex numbers, not a search over a phase grid**: the derivative is a
polynomial in `e^(iφ)` and can be rooted, or scanned densely on already-reduced
quantities at negligible cost.

This is the design's main computational result and it deletes a multiplier the
programme's own compute request carries. The request's sizing assumes a 128x
"shape × phase" factor on the grounds that "a sawtooth or step-train template
does not admit [analytic phase marginalisation], so phase must be correlated
explicitly", with 16 phases enumerated
<!-- src: docs/hpc-access-request-20260921.md §5.2, marked ESTIMATE there -->.
It does admit it, harmonic by harmonic. §4.3 re-derives the budget without it.

The reported statistic is a **profile ratio**, not a normalised power:

> `F(s, f) = [RSS(N) − RSS(N, s, f, φ̂)] / [RSS(N, s, f, φ̂) / (n − p)]`

with `RSS(N)` the residual sum of squares under the nuisance basis alone. Two
properties follow, and both are responses to measured failures:

- The denominator is the residual **after** the nuisance basis, so a smooth
  trend that the basis nearly absorbs cannot inflate the numerator. `P_max` was
  normalised against the raw window variance, which is why a trend that the
  cubic left behind could reach 0.9641.
- The numerator costs the degrees of freedom the template actually uses —
  amplitude and phase, two — not `2·k_max`, because the harmonic weights are
  fixed by the template rather than fitted. A detector that fitted `k_max` free
  harmonics would buy its own significance.

### 3.3 Weights, and what they are not

Elements are weighted by their per-element uncertainty where the archive
supplies one, and equally otherwise. **That is a screen, not a measurement.**
Honest per-element covariances are T5c's product and do not exist
<!-- src: docs/hpc-access-request-20260921.md §6 -->, so every error bar this
detector publishes inherits that status until they do, and the registration must
say so in those words rather than in a limitations paragraph.

### 3.4 Detrending: the band top is measured, not argued

T3's registration removed a cubic per 1080-day window and justified a 220-day
band top by "W/3 = 360 d resolution, a factor 1.64 of margin". **The measurement
says 1.64 was not enough** <!-- src: docs/cadence-results-20260921.md §4(b) -->.
Raising the polynomial order is not the fix on its own: a basis flexible enough
to absorb all the residual curvature begins absorbing the signal at the band's
long end, and the trade is not resolvable by argument.

The registered rule is therefore empirical, and the measurement that fixes it
**already exists in a committed artifact and has never been read out**:

> The band top `P_top` is set to the longest period at which the *passive*
> excess over local background falls to unity, read from
> `docs/cadence-results-20260921-lines.json` `payloadOnlyLineSweep`, and the
> registered band is `[2 d, P_top]`.

The bracket is already visible in T3's own table: the passive excess is 0.18x at
75.25 d and 9.2–38.4x across 163–200 d
<!-- src: docs/cadence-results-20260921.md §5 table -->, so `P_top` lies between
75.25 d and 163 d. Reading the exact crossover is a CPU-minutes job on a
committed file and is the **first prototype deliverable** (§7.1). It is named
here, before any T5a number exists, so that it cannot later be chosen with a
result in view.

Two further registered elements of the nuisance basis:

- `N(t)` is the registered detrend basis — cubic at minimum, extended to a
  natural cubic spline with knots at a registered spacing if the crossover read
  above puts `P_top` below 100 d, which would cost more of the band than the
  spline costs in absorbed signal. The choice is fixed by the crossover reading,
  in advance, by a rule written before the reading is taken.
- The passive control is analysed through the **identical** basis. T3's line
  sweep is readable only because the control ran the identical pipeline
  <!-- src: docs/cadence-results-20260921.md §0 -->; that property is not
  negotiable here.

### 3.5 What the template change is actually worth

An ideal sawtooth's `k`-th harmonic carries amplitude `∝ 1/k`, so power `∝ 1/k²`
and `Σ 1/k² = π²/6 = 1.644934`. The fraction of the sawtooth's power a matched
filter recovers with `k_max` harmonics
<!-- derivation: partial sums of Σ1/k², computed for this document -->:

| `k_max` | 1 | 2 | 3 | 5 | 7 |
|---|---:|---:|---:|---:|---:|
| power recovered | 60.79% | 75.99% | 82.75% | **88.98%** | 91.91% |

A sinusoid — `k_max = 1` — already recovers 60.8%. Moving to `k_max = 5` is a
factor 1.464 in power, **1.65 dB**, or 21% in amplitude signal-to-noise.

**That is the honest size of the template effect, and it is the smallest of the
three changes in this design.** The trend-leakage fix (§3.4) addresses a
measured contamination that put 87.64% of passive peaks above 100 days and drove
a pooled 99th percentile to 0.9641; the aggregator fix (§3.6) addresses a
measured *sign inversion* in which the control fired three times as often as the
treated class. A document that led with the matched filter would be leading with
1.65 dB.

### 3.6 Per object: an aggregator that cannot be bought with window count

Two candidates, both registered, one named primary in advance:

- **PRIMARY — fixed-count aggregation against a per-object null.** Each object's
  window statistics are converted to per-window p-values against **that object's
  own** null (§5), then combined over a **registered fixed number** `m` of
  windows — the `m` largest, with `m` fixed in advance and objects holding fewer
  than `m` windows judged on a declared fallback rung whose exposure is
  reported, exactly as T3's matching ladder does
  <!-- src: docs/cadence-results-20260921.md §2.4: 28.32% of payload objects were judged on a fallback rung, and the registration requires that figure be stated every time -->.
  Fixing `m` removes the mechanism measured in §3.1(3): an object with 40
  windows and an object with 4 contribute the same number of terms.
- **SECONDARY — coherent cross-window stacking.** Because the phase is retained
  on a common absolute epoch (§2.1), an object's windows can be stacked
  coherently at a common `(f, s)` rather than combined as independent maxima.
  This is strictly more powerful where the cadence is stable across the whole
  history and strictly weaker where it is not, and it is reported in its own
  table, never promoted.

---

## 4. Grid sizing, with the compute arithmetic

### 4.1 Frequency grid: the refinement factor is derived, not estimated

The pilot grid is `df = 1.85185e-4 c/d = 1/(5W)` over 2–220 d, 2,676 points
<!-- src: docs/cadence-s1s2-preregistration-20260922.md, "Frequency grid | prereg 4" -->
— five-fold oversampling relative to `1/W` at `W = 1080 d`.

For a *sinusoid*, that is generous: a half-step frequency error gives a coherent
response of `sinc(δf·W) = sinc(0.1) = 0.9836`, a 1.6% amplitude loss
<!-- derivation: sin(0.1π)/(0.1π), computed for this document -->. For a
*harmonic* template it is not, because an error `δf` in the fundamental becomes
`k·δf` at the `k`-th harmonic: at `k = 5` and `δf = df/2` the response is
`sinc(0.5) = 0.6366`, a 36% loss.

> **The grid must be refined by `k_max`.** At `k_max = 5`,
> `df' = df/5 = 3.70370e-5 c/d`.
> <!-- derivation: coherence of the highest retained harmonic, computed for this document. This replaces the "4x frequency oversampling" ESTIMATE in docs/hpc-access-request-20260921.md §5.2 with a derived factor; the numerical change is small, the change in status is not. -->

The refinement is independently checkable against the data: T3's 14.00 d line
core is exactly three grid steps wide (§1.3(a)), i.e. unresolved, and §1.3(a)
predicts a specific asymmetry the refined grid either shows or does not.

### 4.2 Harmonic ceiling: set by the sampling, and frequency-dependent

Harmonics above the sampling's Nyquist frequency are not measurable. The
payload median element-set spacing is 0.3989 d
<!-- src: docs/synchrony-design-20260921.md §7 item 4, citing T3 prereg §0.1 -->,
giving `f_Ny = 1/(2 × 0.3989) = 1.25345 c/d`
<!-- derivation: computed for this document -->. Therefore

> `k_max(f) = min(5, floor(f_Ny / f))`,

so a 14-day fundamental retains all five harmonics while a 2-day fundamental
retains two and the filter **degenerates toward the pilot's sinusoid at the
short-period end of the band.** That is a blind spot, it is derived rather than
discovered, and it is declared in §6.

The per-object spacing distribution — as opposed to the population median — is
not published anywhere this design could find (§11, item 5), so `k_max` is
computed per object from its own epochs at run time and the *distribution* of
`k_max` across the catalogue is a reported output, not an assumption.

### 4.3 One grid, read many times

Because harmonic `k` of fundamental `f` is a frequency like any other, the
implementation evaluates **one dense complex-amplitude grid per window per
channel**, spanning `f_min = 1/220 = 4.54545e-3 c/d` to `f_Ny = 1.25345 c/d` at
`df' = 3.70370e-5 c/d`:

> `N_f' = (1.25345 − 0.0045455)/3.70370e-5 = 33,721 points`
> <!-- derivation: computed for this document -->
> — **12.60x** the pilot's 2,676.

Every fundamental in the 2–220 d search band then reads its harmonics off that
one grid. There is no phase axis (§3.2) and no separate per-shape pass over the
data: the 18 shape members are 18 weightings of the same `k_max` complex
numbers.

### 4.4 The cost of one sweep

From the measured rate of **1.876e6 template evaluations per second per card**
<!-- src: docs/hpc-access-request-20260921.md §5.1, derived there from the pilot's 8.457e8 evaluations in 450.8 s -->,
measured on a card that was concurrently hosting an unrelated training job and
therefore understating rather than flattering:

| | |
|---|---:|
| Windows (pilot population) | 316,028 <!-- src: docs/cadence-results-20260921.md §1.3 --> |
| Frequencies | 33,721 (§4.3) |
| Evaluations, one channel | **1.06568e10** <!-- derivation: 316,028 × 33,721 --> |
| Wall clock, one card, one channel | **5,681 s = 1.578 h** <!-- derivation: ÷ 1.876e6 --> |
| Three channels (`mean_motion`, inclination, eccentricity) | **3.19703e10 evals = 4.734 GPU-hours** <!-- derivation: × 3 --> |

The template-reduction stage of §3.2 operates on `k_max ≤ 5` complex numbers per
(window, fundamental) and is **ESTIMATED at under 10% of the grid stage**; the
flop split between the two is not measured and measuring it is a prototype
deliverable (§11, item 7).

For comparison, the compute request's per-sweep figure is 192.4 GPU-hours, built
from a 1,536x multiplier of which 128x is the phase enumeration this design
removes <!-- src: docs/hpc-access-request-20260921.md §5.2 -->. **The search
itself is 40x cheaper than the request assumed.** What the request did not price
at all is the false-alarm control, and that is where the compute case actually
lives (§5.3).

### 4.5 Device memory: a constraint the refinement creates

The pilot held a peak CuPy pool of 1,145.2 MiB per shard at `N_f = 2,676`, with
1,544 batches over 157,957 windows — about 102 windows per batch
<!-- src: docs/cadence-results-20260921.md §1.2 -->. If the working set scales
with `batch × N_f`, a 12.60x grid at the same batch size would need roughly
14.4 GiB, which is not admissible beside resident training claims. The
requirement is therefore explicit: **the frequency axis is chunked so the pool
stays at or below 2 GiB**, which is a loop, not an algorithm change, and the
claimed `--estimate-mib` is the measured peak rather than an a-priori guess — the
discipline the pilot already demonstrated when it lowered a 2,500 MiB claim to a
measured 1,145 MiB peak rather than forcing it through
<!-- src: docs/cadence-results-20260921.md §1.2 -->.

---

## 5. Null calibration: per covariate stratum, from the first line of code

### 5.1 The two failures this must clear

**T3's window-level threshold did not transfer.** 9.316% of held-out passive
objects exceeded their matched 99th-percentile threshold against 3.361% of
payloads — the control firing three times as often as the treated class, and
9.3 times its nominal rate. The diagnosed cause is that thresholds were computed
over calibration-half *windows* treated as exchangeable, and they are not: a
passive object contributes up to 50 strongly correlated windows, and passive
objects carry a median of 17 against payloads' 4
<!-- src: docs/cadence-results-20260921.md §2.2 -->.

**Phase 3's covariate-matched gate is shut on the point estimates themselves.**
The reweighted separation is 5.3560x against a required 10x, and with all
uncertainty removed from both sides it is 9.8135x — so no additional exposure
can open it <!-- src: docs/phase3-results-20260921.md, "Why the gate is shut" -->.
The lesson Phase 3 draws against itself is sharper than the verdict: *"Nobody
computed the point-estimate separation in advance. Had they, they would have
seen that clause 2 was the binding one and that exposure was the wrong lever."*
<!-- src: docs/phase3-results-20260921.md, "What a reviewer still attacks", item 2 -->

### 5.2 The design responses, all three registered before any run

**(a) Per-stratum false-alarm rates are a reported output, not a diagnostic.**
Every registered covariate stratum — the 5-factor cell T3 already fixed
(perigee × inclination × eccentricity × cadence × window-count band), with its
four-rung fallback ladder and the requirement to state fallback exposure
<!-- src: docs/cadence-results-20260921.md §2.4 -->, aligned to Paper B's
stratification so the two are comparable — publishes its passive flag rate with
a Jeffreys interval, its payload rate with a Jeffreys interval, and its
bound-versus-bound separation. Strata without enough passive exposure are
**labelled gaps**, never zeros, with their payload weight stated, in the manner
of Phase 3's 3.621% labelled gap of which 46.33% is permanently
atmosphere-limited <!-- src: docs/phase3-results-20260921.md, M7 -->.

**(b) The object-level estimator is clustered, always.** Rates and thresholds
are estimated by resampling **objects**, not windows, with the object records
sorted by NORAD before the bootstrap sees them — the defect Phase 3 found and
fixed at `d4e9090`, where the object list's read order had silently become part
of the estimator's input <!-- src: docs/phase3-results-20260921.md, "One defect found and fixed before any result existed" -->.

**(c) The point-estimate separation is computed and published before the run.**
The registration fixes, in advance and in the same commit as the rules: the
expected point-estimate separation from the prototype, and the **minimum
detectable separation** at the registered exposure. If the point-estimate
separation from the prototype is already below the 10x gate, the scale run is
not a power problem and the registration says so before the cluster time is
spent. This is the single most transferable lesson in `phase3-results`, and it
costs nothing to apply.

### 5.3 The per-object null, and the compute ladder it creates

The statistic is maximised over roughly 33,721 frequencies × 18 shape members,
so the per-object p-value must account for a look-elsewhere factor that depends
on **that object's own window function** — its gaps, its spacing, its span.
That dependence is object-specific and cannot be borrowed; borrowing it across
objects is exactly what failed by 9.3x. Three rungs, with their measured or
derived costs:

| Rung | Null | Extra cost per sweep | Status |
|---|---|---:|---|
| **1** | Pooled passive class + clustered object bootstrap on already-computed statistics | ≈ 0 GPU-h (Phase 3's 2,000-draw bootstrap took **86 s** of CPU <!-- src: docs/phase3-results-20260921.md, "Cost" -->) | **MEASURED TO FAIL**, 9.3x <!-- src: docs/cadence-results-20260921.md §2.2 --> |
| **2** | Surrogates per **sampling-geometry class** (a registered clustering on epoch spacing, gap structure and span) | ≈ 3.16x one sweep = **15.0 GPU-h** <!-- derivation: 200 classes × 500 surrogates × 10 windows = 1.0e6 surrogate windows against the sweep's 316,028, × 4.734 GPU-h --> | Borrows within a class. Admissible **only** if the prototype measures that it transfers (§7.2) |
| **3** | Surrogates per **object**, `B = 200`, with a generalised-extreme-value tail fit for p-values below `1/(B+1)` and the extrapolation's uncertainty carried | `200 × 4.734 =` **947 GPU-h** <!-- derivation: computed for this document --> | Does not borrow. **This is the cluster ask.** |

Rung 3 at `B = 200` gives p-values directly resolvable to 5e-3; BH at `q = 0.05`
over 7,884 payloads needs the smallest threshold at `0.05/7884 = 6.34e-6`
<!-- derivation: computed for this document -->, which is why the tail fit is
part of the design rather than an afterthought, and why its extrapolation
uncertainty is a published quantity. T3's receipt already records
`pValueAtFloorPayloads`, so the programme has the habit of checking this
<!-- src: docs/cadence-results-20260921.md §2.1 -->.

The registered rule that decides between rungs is fixed before the prototype
runs: **Rung 2 is used only if the prototype's held-out passive exceedance at
the nominal 1% level lands within [0.5%, 2.0%]** — a screen, not a law, chosen
so that the measured 9.32% failure would be rejected by it with a wide margin —
**otherwise Rung 3.** Either way the held-out exceedance is published.

---

## 6. Blind spots, declared in advance

1. **Continuous low-thrust is invisible, by construction and by measurement.**
   Thrust that continuously cancels the triaxial acceleration gives `λ̈ = 0` and
   therefore a *constant* `δn` — zero power at every non-zero frequency
   <!-- derivation: from §1.1, with the acceleration nulled -->. T3 measured
   this prediction: **0 of 2,809 Starlink and 0 of 618 OneWeb objects** have a
   single window over threshold, with medians at 203.4 d and 0.04% / 0.00% below
   30 days <!-- src: docs/cadence-results-20260921.md §6.1 -->. No matched filter
   over a periodic impulsive template changes that. The two largest actively
   manoeuvring constellations in orbit remain outside this detector.
2. **Objects at stable longitudes are invisible.** `A → 0` at the stable nodes,
   so `T → ∞` and the cycle leaves the band (§1.3(a)).
3. **Aperiodic manoeuvres are outside the template family.** Collision
   avoidance, orbit raising, relocation and end-of-life disposal are single
   events; they belong to the existing self-history step detector
   <!-- src: docs/paper-b-draft-20260921.md §2.1 -->, and a periodic matched
   filter neither sees them nor claims to.
4. **The short-period end degrades to the pilot.** `k_max(f) → 1` as `f`
   approaches the sampling Nyquist (§4.2), so below roughly 5 days the filter is
   a sinusoid again and inherits the pilot's 1.65 dB-worth of mismatch.
5. **North-south keeping is invisible in the energy channel by construction**,
   which is why the design runs three channels; T3's S1 and S2 are **unexercised**
   in those words <!-- src: docs/cadence-results-20260921.md §8 -->.
6. **A natural line will be matched happily.** ETALON 1 and 2 are catalogued
   PAYLOAD, carry no propulsion, and sit on the 27.5 d line on 35 of 35 and 30 of
   35 windows; without the control that line would have been the headline
   finding and it would have been wrong
   <!-- src: docs/cadence-results-20260921.md §5.2 -->. A better template makes
   this hazard larger, not smaller.
7. **A pooled control is not a same-shell control.** The 75.25 d Cosmos line is
   absent from the pooled passive class (0.18x) and is nonetheless natural — the
   half-beta period of that shell, 75.7–77.6 d against a measured 75.25 d
   <!-- src: docs/cadence-results-20260921.md §5.4 -->. The registration must
   carry a same-shell control arm, as T4 §3.1 already argues.
8. **Recall is unmeasured everywhere in this programme.** Paper B and Phase 3
   measure the false-alarm side exhaustively and the recall side not at all
   <!-- src: docs/synchrony-design-20260921.md §5.2 -->. Until §7.3's
   injection–recovery arm runs, a null from this detector bounds nothing.
9. **The element weights are a screen** (§3.3), so the published intervals are
   screens until T5c measures per-element covariances.
10. **The duty/asymmetry degeneracy of §1.3(c)** means a 28 d two-burn cycle and
    a 14 d one-burn cycle are spectrally the same object. Declared, not
    discovered.

---

## 7. Prototype and scale: what runs where

The split is decided by arithmetic, not by preference. The search is cheap
(§4.4); the false-alarm control is not (§5.3).

### 7.1 Runs on our cards, before anything is asked of a cluster

| Task | Cost |
|---|---:|
| Read the passive calibration-half window count from `cadence-results-20260921.jsonl` (§11 item 3) | CPU minutes |
| Read the band-top crossover `P_top` from `cadence-results-20260921-lines.json` (§3.4) | CPU minutes |
| Complex-amplitude kernel + phase retention, validated against the pilot's `gls_power` on frozen windows | — |
| Six development sweeps, three channels | **28.4 GPU-h** <!-- derivation: 6 × 4.734 --> |
| Rung-2 geometry-class surrogates and the transfer test of §7.2 | **15.0 GPU-h** |
| Rung-3 per-object surrogates at `B = 200` on the bounded 14.00 d GEO set (214 payloads plus a shell-matched control, ≈2% of windows) | **18.9 GPU-h** <!-- derivation: 200 × 0.02 × 4.734 --> |
| Injection–recovery at reduced scale (5 amplitudes, ≈5% of objects) | **1.2 GPU-h** |
| **Prototype total** | **≈ 63.5 GPU-hours** |

At full duty on two cards that is about 32 wall-hours; in practice it runs
beside resident training, as the pilot's two shards did
<!-- src: docs/cadence-results-20260921.md §1.2 -->, and takes longer. Device
pool held to ≤2 GiB by §4.5's frequency chunking.

**What the prototype has to establish before the cluster is worth asking for:**
the crossover `P_top`; the measured grid-stage/reduction-stage flop split; the
Rung-2 transfer verdict; the point-estimate separation of §5.2(c); whether the
14.00 d line resolves into the one-sided distribution §1.3(a) predicts; and the
per-surrogate cost, measured rather than assumed.

### 7.2 The measurement that sets the size of the cluster ask

The Rung-2 transfer test is the prototype's most valuable single output and it
is the same test T3 failed. Compute geometry-class surrogate thresholds from the
passive **calibration** half; apply them to the held-out passive **audit** half;
report the exceedance at the nominal 1% level. T3's equivalent number was
**9.32%**. A result inside [0.5%, 2.0%] takes the cluster ask from 947 GPU-hours
per calibrated sweep to 15; a result outside it does not, and the registration
fixes that before the number is visible.

### 7.3 Genuinely needs the rented cluster

| Item | Cost | Why it cannot run here |
|---|---:|---|
| 3 registered calibrated sweeps at Rung 3 (`B = 200`) | **2,855 GPU-h** <!-- derivation: 3 × (946.8 + 4.734) --> | On two cards at *exclusive* full duty this is 1,428 wall-hours — 59 days — and the cards are not exclusive: the SR training programme and the space page's GPU jobs hold them, and the standing operator ruling is that those jobs get whatever room they need. |
| Injection–recovery recall surface over the registered amplitude × cadence × regime grid, 5 realisations | **244 GPU-h** <!-- derivation: 24 amplitudes × 5 realisations × 0.43 (passive calibration-half share of windows, WORKING FIGURE, §11 item 3) × 4.734 --> | The programme has never measured recall at all; this is the first measurement of it and it wants the full grid, not a corner. |
| Development on the cluster's own devices (portability, scaling, restart) | **95 GPU-h** <!-- derivation: 20 × 4.734 --> | Measured on the target hardware by definition. |
| T5c exploratory block | **500 GPU-h** | Unchanged and unmeasured, as the request states <!-- src: docs/hpc-access-request-20260921.md §6 --> |
| Subtotal | 3,694 GPU-h | |
| +15% contingency | **4,248 GPU-h** | |

**This lands inside the 5,000 GPU-hours already requested**
<!-- src: docs/hpc-access-request-20260921.md §4 -->, by a different route: the
request's 1,536x search multiplier is replaced by an analytic phase maximisation
that makes the search 40x cheaper, and the freed budget is spent on a
false-alarm control the request did not price. If the prototype's §7.2 verdict
admits Rung 2, the calibrated sweeps cost 59 GPU-hours instead of 2,855 and the
campaign collapses to roughly 900 GPU-hours, most of it recall and T5c. **Both
outcomes are stated here, before the measurement, so that neither can be
presented afterwards as the plan.**

### 7.4 What must not be sent to the cluster

Extraction (283.2 s of wall clock for 161,234,467 element sets, one read-only
streaming pass) and aggregation (86 s in Phase 3) are local work
<!-- src: docs/cadence-results-20260921.md §1.1; docs/phase3-results-20260921.md, "Cost" -->.
The archive itself does not travel: the cluster receives a frozen, hashed input
bundle (§8).

---

## 8. Portability requirements for the HPC package

Binding on the implementation, not aspirations.

1. **Self-contained.** CUDA and CuPy only, no new framework and no vendor
   dependency beyond those — the property the pilot already has
   <!-- src: docs/hpc-access-request-20260921.md §7 -->. No estate services: no
   GPU admission broker, no repository tooling, no host-specific paths, no
   network access at run time. A pinned dependency lock and a container recipe
   ship with the package.
2. **Batch-first.** One array job, sharded by object, no inter-shard
   communication, no multi-GPU collectives, no interactive session required.
   Per-task device memory ≤ 2 GiB (§4.5), so the workload fits any current
   datacentre part. The pilot's 2-way split is arbitrary and the shard count is
   a parameter.
3. **Input is a frozen bundle, not a database.** Extraction runs locally and
   produces a hashed input set; the cluster job reads it and records every input
   SHA-256 in its receipt. Nothing on the cluster reaches back to the archive.
4. **Deterministic and resumable.** Fixed seed; per-shard checkpoints; results
   provably invariant to how the work was divided, with the object records
   sorted before any estimator sees them (§5.2(b)). A partition must be verified
   to sum to the object count with no overlap, as Phase 3's did.
5. **Never pools two detectors.** A checkpoint predating a rule change finishes
   its whole sweep under the old rule, and merging incompatible non-empty sweep
   policies raises rather than averages
   <!-- src: docs/paper-b-draft-20260921.md §2.7 -->.
6. **Every run emits a receipt.** Input digests, seed, grid parameters, band,
   detrend basis, `k_max` distribution, per-shard counts, wall clock, device
   identity, peak device memory, and the rejection and abstention counters — a
   bound that removes data owes the reader a number
   <!-- src: docs/paper-b-draft-20260921.md §2.5 -->.
7. **Offline self-test runs on the cluster before the primary run**, including a
   synthetic end-to-end case that returns a PASS, so the harness is shown capable
   of producing the favourable answer before it is pointed at real data — the
   discipline `tools/phase3_selftest.py` already establishes with 50 offline
   assertions <!-- src: docs/phase3-results-20260921.md, "Validation, before the numbers" -->.
8. **Portable failure reporting.** Wall-clock overruns, resource-limit kills and
   non-zero exits are recorded with their shard identity, not retried silently.
   This is also the instrumentation the meta-paper of
   `docs/hpc-eval-preregistration-draft-20260922.md` reads.

---

## 9. The acceptance harness

**The new detector is accepted or rejected by the same apparatus, unchanged.**
Nothing in this design proposes a new gate, a new constant, or a new wording
rule.

- `sufficientToLabel` is computed on every run from four conditions, all of
  which must hold: at least 200 passive intervals; the passive Jeffreys upper
  bound below 0.001; the payload excess significant at `p < 0.01`; and the bound
  separation at least 10x. When any fails, a `blockingReason` states which, in
  publishable English <!-- src: docs/paper-b-draft-20260921.md §2.4 -->.
- The separation is an **effect size compared bound to bound**, not a
  significance test; at full-archive exposure the significance clause is
  near-vacuous and carries no weight in any full-population verdict
  <!-- src: docs/paper-b-draft-20260921.md §§2.3, 2.4 -->.
- The gate is **mechanical and recomputed from the run's own control**, so it
  cannot be inherited from a better run; zero denominators mean *unmeasured*,
  never zero <!-- src: docs/paper-b-draft-20260921.md §2.4 -->.
- T3's three-gate ladder applies unchanged, and **Gate A's pass is vacuous when
  the procedure rejects nothing in either class** — the word "vacuously" travels
  with it <!-- src: docs/cadence-results-20260921.md §2.3 -->.
- **One clause passing is not a partial win.** Phase 3 passed clause 1
  decisively and failed clause 2, and reports "the covariate-aware gate does not
  yet ship" rather than a half-victory
  <!-- src: docs/phase3-results-20260921.md, "The headline" -->. The same rule
  binds T5a.
- Abstentions are counted and attributed, never folded into the flag count
  <!-- src: docs/paper-b-draft-20260921.md §2.6 -->, and a physical bound belongs
  at every call site that prices a change — a bound computed but not applied is
  not a bound <!-- src: docs/paper-b-draft-20260921.md §2.5 -->.
- **Registered failure is a result.** Both current papers carry a FAIL verdict
  in their abstracts <!-- src: docs/hpc-access-request-20260921.md §8 -->, and
  T5a is reported PASS or FAIL either way.

The precedent to keep in view is §2.8 of Paper B: the apsidal channel was
written, tested, measured on the passive control, and **shipped off**, because
the control said so. A detector that this apparatus rejects does not ship, and
the design does not acquire a second gate for the occasion.

---

## 10. Scope fence

T5a changes no shipped threshold, relabels no object, touches no other track's
files, and does not alter `INCLINATION_CORROBORATION_MIN_DEG` or
`MIN_SEPARATION_BOUND_RATIO`. The site's wording is governed by the production
control and is unaffected either way, per the standing operator ruling that the
site keeps its wording and these measurements gate the papers, not the site
<!-- src: docs/phase3-results-20260921.md, "The registered response" -->.

---

## 11. Measured inputs that do not exist

Named, not invented. Each is a real hole and none is filled with a plausible
number.

1. **Per-element uncertainty on catalogue mean motion, inclination and
   eccentricity.** Without it the derived ±3.3067e-5 rev/day sawtooth amplitude
   of §1.2 cannot be converted into a signal-to-noise ratio, so this design
   cannot predict its own sensitivity. T5c's product; unmeasured
   <!-- src: docs/hpc-access-request-20260921.md §6 -->.
2. **Detection recall `r`.** "DOES NOT EXIST anywhere in this programme"
   <!-- src: docs/synchrony-design-20260921.md §3.5 table and §5.2 -->. §7.3
   budgets its first measurement.
3. **The passive calibration-half window count**, and the per-class window-count
   distribution. Present per object in `docs/cadence-results-20260921.jsonl`;
   tabulated in no committed document. This design uses **q = 0.43** as a
   WORKING FIGURE for the passive calibration half's share of the 316,028
   windows, derived from the published class medians (17 against 4) and object
   counts, and every number that depends on it is flagged. The prototype reads
   the true value in its first hour (§7.1).
4. **GEO-ring passive exposure per stratum.** Phase 3's coarsest perigee band is
   `>2000 km` (4,345,041 passive against 11,667,613 payload intervals, ratio
   0.372) <!-- src: docs/phase3-results-20260921.md, M7 table -->; the
   geostationary ring is not broken out, so the same-shell GEO control of §6(7)
   cannot be sized from any committed artifact.
5. **Per-object element-set spacing distribution.** Only the payload population
   median, 0.3989 d, is published
   <!-- src: docs/synchrony-design-20260921.md §7 item 4 -->. `k_max(f)` of
   §4.2 is computed per object at run time for exactly this reason.
6. **The band-top crossover `P_top`.** Bracketed between 75.25 d and 163 d by
   T3's own line table and computable today from
   `docs/cadence-results-20260921-lines.json`; stated nowhere (§3.4).
7. **The flop split between the grid stage and the template-reduction stage.**
   The 1.876e6 evaluations/s/card figure is measured; its decomposition is not,
   so §4.4's "under 10%" is an ESTIMATE.
8. **Peak device memory at the refined grid.** §4.5 scales the pilot's measured
   1,145.2 MiB by the grid factor under an assumption of linearity that has not
   been measured.
9. **Historical geomagnetic and solar-flux series.** The archive's `geomagnetic`
   table holds 25 rows spanning about six hours of 2026-08-05
   <!-- src: docs/synchrony-design-20260921.md §3.4 -->. Not required by this
   design, but it bounds any attempt to condition the null on space weather.

---

## 12. Skeleton of the registration that would be committed before any T5a number

Each heading is a decision fixed in writing, alone, ahead of every T5a result.

1. **Template family.** The closed enumeration of §2, by formula, with the
   duty/asymmetry degeneracy of §1.3(c) declared. *Drafted.*
2. **Statistic.** The profile ratio of §3.2, its nuisance basis, its degrees of
   freedom, and the per-object aggregator of §3.6 with `m` fixed. **OPEN:** `m`
   is not derived here.
3. **Detrend basis and band.** The rule of §3.4, with `P_top` read from the
   committed line artifact **before** any T5a code runs, and the spline fallback
   condition fixed in advance. *Drafted; the reading is not taken.*
4. **Frequency grid.** `df' = df/k_max`, derived (§4.1); `k_max(f)` per §4.2.
   *Drafted.*
5. **Null and stratification.** The three rungs of §5.3, the screen that selects
   between them, the 5-factor cell and its fallback ladder, the clustered
   object-level estimator, the GEV tail fit and its published extrapolation
   uncertainty. *Drafted.*
6. **Pre-computed separation.** The point-estimate separation and the minimum
   detectable separation, published before the scale run (§5.2(c)). *Drafted.*
7. **Recall.** The injection–recovery amplitude × cadence × regime grid, and the
   statement that an injected instantaneous step is not a real burn so the
   measured `r` is an **upper bound** on true recall
   <!-- src: docs/synchrony-design-20260921.md §5.2 -->. **OPEN:** the amplitude
   grid is not fixed here.
8. **Controls.** Pooled passive plus a same-shell arm (§6(7)). **OPEN:** the
   shell definition and its minimum size.
9. **Multiple testing.** Across frequencies, shapes, channels, objects and
   strata. T3's three-level treatment is the template. **OPEN.**
10. **Acceptance.** Paper B's four-condition gate and T3's A/B/C ladder,
    unchanged (§9), with the rule that a clause passing alone is not a win.
    *Drafted.*
11. **Blind spots**, §6, declared in advance. *Drafted.*
12. **Resource bounds and portability**, §8, plus the honest `--estimate-mib`
    discipline. *Drafted.*
13. **Scope fence**, §10. *Drafted.*
14. **Stop rules**, including the prohibition on re-running with a different
    band, basis, `k_max` or null after a number is visible, and the rule that an
    unwelcome result is reported. **OPEN.**

---

## 13. Honest summary

The pilot bought three measurements and this design spends all three. The
template change is derived from the triaxial deadband cycle rather than assumed,
and it is worth 1.65 dB — the smallest of the three effects, stated first so it
cannot be oversold. The detrending change addresses the failure that actually
produced the null, and its critical parameter is read from a committed artifact
rather than argued. The false-alarm change is the expensive one: per-object
surrogates at 947 GPU-hours a sweep, which is the whole cluster case, and it
exists because a threshold that borrowed across objects was measured to fail by
a factor of 9.3. The search itself turns out to be 40x cheaper than the compute
request assumed, because a harmonic template's phase can be maximised in closed
form; the freed budget goes to the control and to the first recall measurement
this programme has ever made. The design retains the fitted phase, which T4
requires and T3 discards, so the two tracks share one artifact.

Nine measured inputs do not exist and are named in §11 rather than estimated.
Ten blind spots are declared in §6 rather than discovered. And the detector is
accepted or rejected by the apparatus that has already shut its own gate twice —
at 8.83x on a sample and 5.3560x on the whole archive — with no new gate built
for the occasion.

None of this is registered. When it is, it will be registered alone, first.
