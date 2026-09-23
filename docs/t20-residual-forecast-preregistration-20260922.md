# T20 — a deterministic structured-residual forecast: preregistration

**Committed alone, before any number was computed.** Nothing in this file may be
edited after a result exists; departures are written into the results document
under their own heading, as deviations.

**The operator's question, in his words:** *"what if the corrections — not burns
but the corrections themselves — have periodic or repeating structure? Couldn't
you model them and give predicted orbits that drift much less?"*

**What this track is.** A *classical*, deterministic answer: measure the error
between a propagated element set and truth, test that error series for periodic
structure with a spectral test that has a floor, then fit a per-object linear
model of the error on physically-derived covariates and see whether it forecasts
out of sample. No neural model is built here. T20 is the baseline that the
learned model of T18 (§3.4, evaluation E2) must beat; a learned model that does
not beat a per-object linear regression on F10.7, ap and a low-order Fourier set
has not earned its parameters.

**What this track is not.** It is not a new propagator, not a manoeuvre
detector, not an orbit determination. It does not touch any site surface, adds
no timer, and consumes no GPU.

---

## 0. The claim under test, and what would falsify it

**Claim.** The residual between a propagated element set and the truth is not
white: it carries periodic and space-weather-driven structure that, once fitted
per object on past data, reduces the forecast error on held-out future data.

**Falsified if**, on the registered analysis: **no spectral line above the
surrogate floor in any object's residual series, AND no out-of-sample gain with
a lower bound above zero at +14 d.** Both halves must fail for the claim to be
withdrawn; one without the other is recorded as a partial result with the half
that failed named.

---

## 1. The residual series

### 1.1 Truth arm (the primary arm)

Three spacecraft, the same three T16b measured, with the same truth products
and the same frame chain, reused rather than rebuilt:

| Object | NORAD | Truth product |
|---|---:|---|
| Sentinel-1A | 39634 | Copernicus AUX_POEORB (Earth Explorer XML), EARTH_FIXED, UTC, 10 s |
| Sentinel-3A | 41335 | CNES/SSALTO POE SP3-c v30 (POE-G), ITRF, TAI, 60 s |
| Sentinel-3B | 43437 | CNES/SSALTO POE SP3-c v30 (POE-G), ITRF, TAI, 60 s |

Truth already fetched and cached for T16b at `/home/sdegan/t16b-truth/`; its
coverage is continuous across calendar 2023 with no gap longer than two hours
(verified before this registration was written; a coverage fact, not a result).

**Origin epochs.** The first archive element set of each UTC day, from
**2023-01-01** to **2023-12-01** inclusive. The end date is set by the
requirement that the longest horizon (+30 d) land inside the truth window and
not by anything measured.

**Horizon grid (registered, fixed):** `h ∈ {1, 2, 3, 5, 7, 10, 14, 21, 30}`
days.

**The residual.** For object `o`, origin `t0`, horizon `h`: propagate the
element set at `t0` with the programme's own SGP4 (`tools/truthset_sgp4.mjs`,
`satellite.js`, the propagator the site's globe runs) to `T = t0 + h`; rotate
TEME → PEF by GMST evaluated at UT1 and PEF → ITRF by polar motion, both from
IERS `finals2000A.all`; difference against the truth product's own nearest
sample; resolve into radial / along-track / cross-track about the truth state.

**The series analysed is the SIGNED along-track residual**
`δ(o, t0, h)`, in kilometres, positive meaning the propagated position is ahead
of truth along the velocity direction. Signed, because a residual that is a bias
and a residual that is scatter are different objects, and a model of a bias is
the whole point. Radial and cross-track are carried and reported but are not
modelled: T16b measured the along-track median at +30 d to be 68–160× the radial
and 74–152× the cross-track, so along-track is where the error is.

**Gate bars carried from T16b unchanged:** the truth sample used is the nearest
one and SGP4 is evaluated exactly there; a comparison whose sample offset
exceeds 5 s (AUX_POEORB) or 30 s (SP3) is dropped, and the dropped fraction is
reported. No truth interpolation.

**The epoch floor.** T16b measured a +0 d residual of 0.33–0.58 km — the
along-track offset a general-perturbation fit carries at its own epoch — and
showed it is a property of the element sets rather than of the pipeline. That
number is the floor of everything below and is printed beside every row. A
correction cannot be credited below it.

### 1.2 Catalogue arm (no truth needed)

The same construction with the later *element set* standing in for truth:

`δ_cat(o, t0, h)` = signed along-track difference at `T = t0 + h` between the
element set at `t0` propagated to `T`, and the element set of the same object
whose epoch is nearest `T` within **± 6 h**, propagated to `T`.

This needs no precise orbit and therefore runs on the whole catalogue. It is
**not truth**: it is the archive's disagreement with itself across a
propagation span, and T16a measured that self-disagreement at a median
4.99 km along-track over a 12.5 h lever on Starlink objects. Every number from
this arm is labelled *catalogue self-consistency* and never *error*.

**Object set (registered rule, applied before any number is read).** From
`/home/sdegan/space-orbit-history/orbit-history.sqlite3`: objects with
`object_type = 'PAYLOAD'`, mean motion between 11.0 and 16.0 rev/day at
mid-2023, at least 600 element sets with epoch in calendar 2023, and a
computable `δ_cat` at no fewer than 80% of the planned instants. Eligible NORAD
ids are sorted ascending and every ⌈N/300⌉-th is taken, capped at **300
objects**. The rule is deterministic and is recorded with its realised `N`.

### 1.3 Arms, separated before running

| Arm | Intervals | Objects | Horizons | Role |
|---|---|---|---|---|
| **A** | all intervals, as flown | 1A, 3A, 3B | full grid | **the pass-screen arm** |
| **B** | intervals containing no IDS-reported manoeuvre | 3A, 3B | h ≤ 14 d | separates forecasting from schedule anticipation |
| **C** | catalogue self-consistency | ≤ 300 payloads | full grid | the general-catalogue version; well-powered object clustering |

Arm B exists only where a manoeuvre notice exists. Sentinel-1A carries no
DORIS package and has no fetchable notice (T16b §2.5), so it has no Arm B; and
T16b measured that the Sentinel-3 manoeuvre-free subset **runs out at +14 d**,
because these spacecraft manoeuvre roughly every two weeks. Arm B therefore
cannot reach the horizons the pass screen is read at, which is why the screen is
read on Arm A.

**The interpretation rule, registered in advance:** a gain on Arm A that
disappears on Arm B is the model anticipating an operator's *schedule*, not
forecasting the physics. It is a pattern-of-life finding, it belongs beside
T14, and it must be labelled as such and never reported as a forecasting gain.

---

## 2. Structure hypotheses, each with its derivation or citation

Every hypothesis below is either derived here from first principles or cited to
a published model. **No coefficient of any density model is invented, quoted
from memory, or fitted and then described as physical.** Where a published
model is used it is *evaluated as published*, and where a functional form is
used its coefficients are fitted and called fitted.

### 2.1 Why the along-track residual should be quadratic in time, and what that means

For a near-circular orbit, `n = sqrt(μ/a³)`, so `dn/da = −(3/2)·n/a`. If the
propagator's semi-major axis is wrong in its *rate* by `ȧ_err` — constant over
the span — then `n(t) ≈ n0 − (3/2)(n0/a0)·ȧ_err·t`, the mean anomaly error is
`ΔM = −(3/4)(n0/a0)·ȧ_err·t²`, and the along-track displacement is

  **`s(t) ≈ −(3/4)·n0·ȧ_err·t²`**

A constant semi-major-axis *error* gives a displacement linear in `t`; a
constant error in the *rate* gives `t²`. T16b measured the exponent at
**t^1.95 / t^2.06 / t^1.98** on these three objects between +30 d and +90 d.
The measurement therefore says the dominant term is an error in the modelled
decay rate, and the decay rate is drag.

This is the hinge of the whole track: **if the residual is dominated by a
mis-modelled drag rate, and drag rate is driven by density, and density is
driven by measurable solar and geomagnetic indices, then the residual should be
predictable from those indices.** The registered model (§3) is the direct test
of that chain.

### 2.2 Density dependence on F10.7 and ap — cited, not invented

Empirical thermosphere models parameterise the exospheric temperature as
approximately affine in the solar radio flux and its long-run average and in the
geomagnetic index, and the density at a fixed altitude as approximately
exponential in that temperature; hence `log ρ` is approximately affine in
`F10.7`, `F̄10.7` and `ap` over moderate ranges. The published models this
statement is taken from, and their relevant structure:

- **NRLMSISE-00** — Picone, Hedin, Drob & Aikin (2002), *JGR Space Physics*
  107(A12), 1468, doi:10.1029/2002JA009430. Driven by daily `F10.7`, the
  81-day centred average `F10.7A`, and a 3-hourly `ap` history.
- **NRLMSIS 2.0** — Emmert et al. (2021), *Earth and Space Science* 8,
  e2020EA001321, doi:10.1029/2020EA001321. Same three drivers.
- **JB2008** — Bowman, Tobiska, Marcos, Huang, Lin & Burke (2008), AIAA
  2008-6438. Uses `F10.7`, `S10`, `M10`, `Y10` and `Dst`-driven storm terms.

**What is used here.** Rather than asserting an exponent, the density covariate
is obtained by **evaluating NRLMSIS 2.0 as published**, through `pymsis` 0.12.0
(already installed on the analysis host), at the object's own mean altitude and
inclination, with the drivers as known at the origin epoch. The model is used as
an instrument, not re-derived, and the linear-in-`log ρ` step is a *fitted*
regression coefficient, stated as fitted.

The direct `F10.7` and `ap` covariates are carried *beside* the MSIS density, so
that the results can say whether the published density model buys anything over
the raw indices. That comparison is registered as a reported quantity, not as a
screen.

### 2.3 The 27-day solar rotation term

The Sun's synodic rotation period at low latitudes is about **27.27 days**, and
the recurrence of solar activity at that period is the basis of the Bartels
solar rotation number, which the GFZ index file carries as its own column
(Bartels 1949; Matzka, Stolle, Yamazaki, Bronkalla & Morschhauser 2021, *Space
Weather*, doi:10.1029/2020SW002641). Active regions persisting more than one
rotation produce recurrent F10.7 and geomagnetic activity, therefore recurrent
density, therefore — by §2.1 — a recurrent drag-rate error. Registered as a
**cos/sin pair at 27.2753 d** and as a named band in the spectral test.

### 2.4 The semi-annual density variation

Thermospheric density at fixed altitude carries a well-documented semi-annual
variation with maxima near the equinoxes; it is represented explicitly inside
the empirical models cited in §2.2. Registered as a **cos/sin pair at
182.625 d** and as a named band. **Registered limitation:** one calendar year
contains two cycles of this term, so its periodogram peak rests on two cycles
and is reported as weakly resolved.

### 2.5 The annual term is NOT registered, and why

One calendar year contains a single cycle of an annual term. A single cycle is
not separable from the intercept plus a linear trend over the same span. The
annual cos/sin pair is therefore **deliberately excluded from the covariate
set**, and the annual band is **not** claimed either way by the spectral test.
This is a derivation about identifiability, not a measurement.

### 2.6 The diurnal term is NOT TESTABLE on this object set, and why

Two independent reasons, both derived before any number:

1. **Aliasing.** One origin per UTC day gives a Nyquist period of 2 days. A
   diurnal or semi-diurnal term aliases onto the daily grid and cannot be
   resolved from it.
2. **Frozen local time.** Sentinel-1A, Sentinel-3A and Sentinel-3B are
   sun-synchronous by design; the local solar time of the ascending node is held
   approximately constant by the mission. The diurnal density bulge is therefore
   sampled at approximately the same local time at every origin, and a diurnal
   covariate is degenerate with the intercept on this object set.

**Consequence, registered:** the diurnal hypothesis is **untestable on the truth
arm** and is not tested there. It is carried into the catalogue arm only, as the
mean local solar time of the ascending node at `t0` with its own cos/sin pair,
where objects whose node drifts give it something to vary against. Whether the
catalogue arm's object set contains enough non-sun-synchronous objects to
support it is itself reported.

### 2.7 Per-object drag scale

SGP4's drag term is the `B*` carried in the element set. The residual
drag-rate error of §2.1 scales with the product of the density error and the
object's own ballistic scale, so `B*` and its recent change are registered
covariates, *per object*. Because the model is fitted per object, the fixed part
of the ballistic coefficient is absorbed into the intercept and only its
variation carries information; that is stated so that a large fitted `B*`
coefficient is not read as a measurement of the ballistic coefficient.

### 2.8 Resonant tesseral terms — the ground-track repeat cycle

A satellite's encounter with the longitude-dependent (tesseral) part of the
geopotential repeats when its ground track repeats. The published repeat cycles
are **12 days / 175 orbits** for Sentinel-1 and **27 days / 385 orbits** for
Sentinel-3 (ESA mission specifications).

**Those published values are used only as a cross-check.** The period actually
registered and used is **derived from the archive's own measured mean motion**
at mid-2023: `P_repeat` is the smallest integer number of days `D ≤ 40` for
which `D·n` is within 0.02 revolutions of an integer, with `n` the object's
median mean motion over 2023. The derived value and the published value are both
reported, and a disagreement is reported as a disagreement.

**A confound registered in advance, and it is a serious one.** Sentinel-3's
ground-track repeat cycle is **27 days** and the solar synodic rotation is
**27.27 days**. On a single year of daily samples these two are **not
separable**: the frequency resolution of a 335-point one-year series is about
1/335 d⁻¹, which at a period of 27 d corresponds to a period resolution of
roughly 2.2 d — far wider than the 0.27 d that separates them. **Any 27-day line
found on Sentinel-3A or Sentinel-3B is therefore jointly a solar-rotation line
and a ground-track-resonance line, and this document forbids attributing it to
either alone.** Sentinel-1A, whose repeat cycle is 12 days, is the object that
can separate them: a 27-day line on Sentinel-1A cannot be its ground track, and
a 12-day line on Sentinel-1A cannot be the Sun. The disentangling rests on
Sentinel-1A and is stated as resting on one object.

### 2.9 The archive's own fit-span artefact

Element sets for these objects arrive roughly three times a day. A periodicity
at the update cadence would alias to zero frequency on a daily origin grid
(3 cycles/day folded into a 0.5 cycle/day band lands on DC) and is therefore
**not testable by the periodogram here**. The non-aliased handle on the
fit-span artefact is a *regression* covariate: the **age of the origin element
set**, i.e. the interval from the previous element set's epoch to `t0`, and the
**count of element sets in the trailing 7 days**. Both are registered
covariates. A large fitted coefficient on element-set age is evidence that part
of the residual is the archive's own update schedule rather than the
atmosphere, and is to be reported as such.

### 2.10 The operator's own manoeuvre cadence

Sentinel-3A and 3B perform orbit-control manoeuvres roughly fortnightly (T16b:
20 and 23 reported manoeuvres inside the 2023 truth window). A line near 14 days
is therefore expected on Arm A for those two objects and **is a schedule line,
not a physics line**. It is reported in its own row, and it is the reason Arm B
exists.

---

## 3. The model

### 3.1 Form

Per object, per horizon, ordinary least squares with an L2 (ridge) penalty:

  `δ̂(o, t0, h) = β₀(o,h) + Σₖ βₖ(o,h)·xₖ(o,t0)`

Fitted independently for each `(object, horizon)` pair. No pooling across
objects: the operator's question is whether the corrections have structure
**once fitted per object**, and pooling would answer a different question.

**A second, physically-constrained parameterisation is registered beside it**
and reported: `δ̂ = A(o,t0)·h + B(o,t0)·h²` with `A` and `B` each linear in the
same covariates, fitted jointly across all horizons for one origin. It carries
the §2.1 derivation as a constraint (the residual vanishes as `h → 0`, up to the
epoch floor) and uses roughly half the parameters. **The per-horizon form is the
primary**; the constrained form is reported beside it, and if the constrained
form wins, that is reported as a result about the derivation.

### 3.2 The covariate set — registered, fixed, sixteen terms

Every covariate carries a **`knownBy` time**, and the builder refuses any
covariate whose `knownBy` is later than `t0`. That refusal is code, not a
convention, and §6 registers the test that asserts it.

**Space weather, from the origin epoch backwards only (6):**

| # | covariate | knownBy |
|---:|---|---|
| 1 | `F10.7obs` on the last UT day completed before `t0` | `t0` |
| 2 | `F̄10.7` over the trailing 81 days ending at that day | `t0` |
| 3 | `ΔF = (1) − (2)` | `t0` |
| 4 | daily `Ap` on the last completed UT day | `t0` |
| 5 | `Āp` over the trailing 27 days | `t0` |
| 6 | `log₁₀ ρ` from NRLMSIS 2.0 at the object's mean altitude, evaluated with drivers 1/2/4 and the trailing 3-hourly `ap` history, averaged over 16 points equally spaced in argument of latitude around one orbit | `t0` |

**Deterministic Fourier terms, known at `t0` by construction (6):**

| # | covariate |
|---:|---|
| 7, 8 | `cos`, `sin` of `2π·t0 / 27.2753 d` (solar synodic rotation) |
| 9, 10 | `cos`, `sin` of `2π·t0 / 182.625 d` (semi-annual) |
| 11, 12 | `cos`, `sin` of `2π·t0 / P_repeat(o)` (derived ground-track repeat, §2.8) |

**Object and archive state at the origin (4):**

| # | covariate |
|---:|---|
| 13 | `B*` from the origin element set |
| 14 | `B*` minus the mean `B*` over the previous 10 element sets |
| 15 | `MEAN_MOTION_DOT` from the origin element set |
| 16 | element-set age: `t0` minus the previous element set's epoch |

On the **catalogue arm only**, two further terms (17, 18): `cos`, `sin` of the
ascending node's mean local solar time at `t0` (§2.6). They are **not** used on
the truth arm.

All covariates are standardised to zero mean and unit variance **using the
training rows only**; the standardisation constants are part of the fitted model
and are applied unchanged to the test rows.

### 3.3 The split, and the embargo

**Training origins:** `t0` in **2023-01-01 … 2023-06-01**.
**Test origins:** `t0` in **2023-07-01 … 2023-12-01**.
**Embargo:** the thirty days between them, so that no training target uses truth
from inside the test period. A training origin at 2023-06-01 with `h = 30 d`
reaches 2023-07-01, the first test origin, and no further. Without the embargo
the longest-horizon training targets would be measured on the test window's own
truth, which is leakage even though no test *origin* is in the training set.

**Ridge penalty selection.** `λ` is chosen from the registered grid
`{0, 10⁻³, 10⁻², 10⁻¹, 1, 10, 10², 10³}` by forward-chaining cross-validation
**inside the training half only**: five folds, each fold training on all origins
before a cut and validating on the next contiguous block, with the same 30-day
embargo applied at every inner cut. **No test row is touched by the selection**,
and §6 registers the test that asserts it.

### 3.4 The corrected forecast

`corrected along-track error = |δ(o,t0,h) − δ̂(o,t0,h)|`
`plain along-track error    = |δ(o,t0,h)|`

The corrected forecast is the plain SGP4 position displaced along-track by
`δ̂`. Radial and cross-track are left untouched; the model does not claim them.

---

## 4. The spectral test — reported BEFORE the fit

**Reported first, in its own section of the results document, before a single
regression coefficient appears**, so that the periodicity claim stands or falls
on its own.

**Series tested**, per object, on Arm A:
1. `δ(o, t0, h=+7 d)` as a function of `t0` — the residual series at a fixed
   horizon;
2. the same at `h = +14 d` and `h = +30 d`;
3. the per-origin quadratic coefficient `B(o,t0)` of §3.1, i.e. the fitted
   `h²` term of a single origin's own residual-versus-horizon curve — by §2.1
   the drag-rate error itself.

**Method.** The classical Lomb–Scargle normalised periodogram (Lomb 1976, *Ap&SS*
39, 447; Scargle 1982, *ApJ* 263, 835), implemented directly — the analysis host
has NumPy and no SciPy, and no dependency is added for this. The series is
mean-subtracted and linearly detrended before transforming; the detrending is
registered because a residual series with a secular trend would otherwise put
power at every low frequency.

**Frequency grid.** Periods from **2.0 days** (the Nyquist period of a daily
grid) to **200 days**, on a uniform frequency grid oversampled by a factor of 5
relative to `1/T_span`.

**The floor.** **200 phase-scrambled surrogates**: the series' own Fourier
amplitudes are preserved and its phases are replaced by uniform random phases,
then the periodogram is recomputed. This preserves the autocorrelation — the
redness — of the series, so the floor is a floor against *red* noise and not
merely against white noise. Seed **20260922**, recorded.

Two floors are reported:
- **per-frequency**, the 95th percentile of surrogate power at that frequency;
- **global**, the 95th percentile of the surrogate *maximum* power over the
  whole scanned band.

**A line is declared only above the GLOBAL floor.** The per-frequency floor is
reported for shape and is explicitly not a detection threshold, because scanning
~1,600 frequencies and reporting the largest is a multiplicity problem that the
per-frequency floor does not control.

**Named bands, declared before looking:** 27.2753 d (solar rotation),
182.625 d (semi-annual), `P_repeat(o)` (derived ground track), 14 d (the
Sentinel-3 orbit-control cadence, a schedule band). A line inside a named band
is reported as *consistent with* that band; §2.8's confound forbids attributing
a 27-day Sentinel-3 line to one cause.

---

## 5. Evaluation, screens, and controls

### 5.1 The estimand

**Median along-track error over test origins, at +7, +14 and +30 days,
corrected against plain**, per object and pooled; the full horizon grid is
reported beside them. The gain is

  `G(h) = median|plain|(h) − median|corrected|(h)`, positive meaning improvement.

### 5.2 Intervals

**Primary precision: a moving-block bootstrap over origins within object**,
block length **30 days**, 2,000 resamples, seed 20260922. Blocks, because the
residual series is strongly autocorrelated and an i.i.d. bootstrap over origins
would produce an interval that is too narrow by an amount nobody could state.

**Also computed, as the operator registered it: an object-clustered bootstrap**,
2,000 resamples over the three objects. **It is recorded in advance that three
clusters cannot support a 95% interval** — three objects admit only ten distinct
resample multisets — so this interval is reported as a spread across objects and
is labelled coarse. On the catalogue arm, where there are up to 300 clusters,
the object-clustered bootstrap **is** the primary.

**The disagreement rule, registered in advance:** if the block bootstrap
excludes zero at +14 d while the object-clustered interval includes it, the
screen is recorded as **NOT PASSED** and the disagreement is the headline.

### 5.3 The pass screen

Both clauses must hold, on **Arm A**:

1. **Gain at +14 d.** The lower bound of `G(+14 d)` is **above zero**.
2. **Non-inferiority at every horizon.** At each `h` in the registered grid,
   the lower bound of `G(h)` is **above `−0.10 × median|plain|(h)`**. A forecast
   that is better on average and materially worse sometimes is unusable, so a
   mean improvement does not pass alone. The 10% margin is a **chosen screen,
   not a physical law**, and is named as one.

Reported but not screened: +7 d and +30 d gains, the per-object gains, Arm B,
Arm C, the constrained parameterisation, and the MSIS-density-versus-raw-indices
comparison.

### 5.4 The placebo arms

**P1 (primary placebo).** Every covariate is taken from **180 days earlier**:
`x'(t0) = x(t0 − 180 d)`. Real values, real distributions, wrong alignment. The
whole pipeline is re-run unchanged.

**Screen:** `G_P1(+14 d)` must have a lower bound **at or below zero**. If the
placebo gains, the headline gain is not attributable to the alignment between
the covariates and the residual, and **the structure claim fails regardless of
the real arm's number**.

**P2 (secondary placebo).** Only the space-weather and Fourier covariates
(1–12) are shifted; the object/archive-state covariates (13–16) stay aligned.
P2 separates "the space weather is aligned with the residual" from "the object's
own recent state carries the information". It is reported, not screened.

**A caveat registered in advance:** `B*`, mean motion rate and the trailing
index means all vary slowly, so a covariate shifted by 180 days retains some
correlation with its aligned self. A small residual placebo gain is therefore
possible without any alignment information, and if one appears it is reported as
what it is — slowly-varying state leaking through the shift — rather than
dismissed or explained away.

### 5.5 The transfer arm — same object, different year

**On the truth arm this arm cannot be run**, and the reason is stated rather
than worked around: the precise-orbit products fetched for T16b cover calendar
2023 only, and extending to a second year means re-fetching on the order of
1.7 GB of daily AUX_POEORB per year from Copernicus. That fetch is not made
here.

**On the catalogue arm it can be run and is registered:** fit on 2023, evaluate
on the same objects in **2024**, with no refitting. A model that transfers across
a year with different solar conditions is making a claim about the mechanism; one
that does not is fitted to a year.

### 5.6 What the numbers may not be used for

- Three cooperative, exceptionally well-tracked, sun-synchronous spacecraft are
  not a census, and T16b already recorded that their forward-error curve is a
  best case.
- The catalogue arm is **self-consistency, not accuracy**; it cannot say which
  element set is closer to reality.
- No claim is made at GEO, at any horizon beyond +30 d, or for any object whose
  element sets are sparser than the registered rule requires.
- Every threshold here — the 10% non-inferiority margin, the 95th-percentile
  surrogate floors, the ±6 h catalogue pairing window, the 0.02-revolution
  repeat tolerance, the 300-object cap — is a **chosen screen**, not a physical
  law.

---

## 6. Instruments, data, and the tests that must exist

**Tools (new):** `tools/residual_forecast.py` (residual construction, spectral
test, fit, evaluation), `tools/residual_covariates.py` (the index-file parser,
the MSIS covariate, the `knownBy` guard).
**Tools reused unchanged:** `tools/truthset_truth.py`, `tools/truthset_sgp4.mjs`.
**Tests:** `tests/test_residual_forecast.py`.

**Space-weather source.** GFZ Helmholtz Centre for Geosciences,
`Kp_ap_Ap_SN_F107_since_1932.txt` — three-hourly `Kp` and `ap`, daily `Ap`,
Bartels rotation number, and daily `F10.7obs` / `F10.7adj` from the Dominion
Radio Astrophysical Observatory, since 1932. CC BY 4.0 for the geomagnetic
indices. Cite: Matzka, Stolle, Yamazaki, Bronkalla & Morschhauser (2021),
*Space Weather*, doi:10.1029/2020SW002641; data publication
doi:10.5880/Kp.0001; F10.7 per Tapping (2013), *Space Weather* 11, 394.

**Why not the site's own ingest.** `pipeline/msis_drivers.py` takes F10.7 from
NOAA SWPC's rolling `f107_cm_flux.json`, which carries roughly the last six
weeks, and derives `ap` from the published Kp series including NOAA's forecast;
the `geomagnetic` table in the orbit archive holds a single day. Neither reaches
2023. The GFZ archive file is used instead, and **CelesTrak is deliberately not
used for this**: the estate's standing routing rule forbids any CelesTrak
request from the analysis host, and the VPS lane's request budget is spent on the
element-set mirror. One archive file, fetched once, from a source with no such
constraint, is the cheaper and safer path.

**Density model.** NRLMSIS 2.0 via `pymsis` 0.12.0, already present on the
analysis host. No new dependency is installed for this track.

### 6.1 The tests, and what each asserts

Tests that assert the bug — each must **fail** if the guard is removed:

1. A covariate declared with `knownBy > t0` is **refused** by the builder.
2. A synthetic covariate constructed from the future target is refused; forced
   through a bypass, it produces a train/test gap that the split check flags.
3. The embargo excludes a training origin whose `t0 + 30 d` crosses the test
   start.
4. Ridge-penalty selection touches no test row (asserted by poisoning the test
   rows and showing the selected `λ` is unchanged).
5. A placebo on synthetic data with **no** structure shows no gain — lower bound
   at or below zero.
6. **The surrogate floor is not fooled by red noise.** An AR(1) series with no
   periodicity produces **no line above the global floor**, where a white-noise
   floor would have produced one. This is the test the whole spectral claim
   rests on.

Tests that assert the instrument:

7. Lomb–Scargle recovers a known injected period, on an irregular grid, to
   within the frequency resolution.
8. The `h`-quadratic fit recovers a synthetic `δ = A·h + B·h²`.
9. The along-track sign convention: a propagated position displaced along the
   velocity direction gives a positive residual.
10. GFZ parser: missing values (`−1.0` for F10.7, `−1` for ap) are refused and
    not defaulted; three-hourly `ap` slots align with the UT day; the
    definitive/preliminary flag is carried.
11. The trailing-window covariates (81-day mean, 27-day mean) use only days
    strictly before `t0`.
12. The block bootstrap's interval covers the truth on i.i.d. synthetic data.

### 6.2 Gates

| Gate | Fires when | Consequence |
|---|---|---|
| **G1** | more than 1% of planned truth comparisons dropped by the offset bar | the affected horizon's row is reported as incomplete with its `n` |
| **G2** | fewer than 100 test origins for an object at any horizon | that object's row at that horizon is reported as counts only |
| **G3** | the fitted model's *training* error is not below the plain error | the fit is reported as failed to fit, and the test numbers are reported anyway |
| **G4** | the selected `λ` sits at an end of the registered grid | reported; the grid is not extended after the fact |
| **G5** | a placebo arm gains (§5.4) | the structure claim **fails** |
| **G6** | Arm A gains and Arm B does not | the gain is reported as schedule anticipation, not forecasting |

### 6.3 Reproducibility

Every number in the results document must be reproducible from
`tools/residual_forecast.py` with the registered arguments, the cached truth at
`/home/sdegan/t16b-truth/`, the GP archive, and the GFZ index file whose
SHA-256 is recorded in the results JSON. The results JSON carries the
registration's commit hash, the tool blob hashes, the seeds, and every screen
value above.

---

## 7. Order of work

1. This registration, committed **alone**.
2. `tools/residual_covariates.py`, `tools/residual_forecast.py`, and the tests.
   Tests pass before any measurement is run.
3. The spectral test, on Arm A. Its output is written down **before** the fit is
   run.
4. The fit and the evaluation: Arm A, Arm B, the placebos, then Arm C and the
   transfer arm.
5. `docs/t20-residual-forecast-results-<date>.md` and its JSON, with the
   deviations section and the unproven-items section.
6. The T20 row in `docs/research-program-runbook-20260921.md`, inserted after
   T18.

Nothing here is wired to a timer, a site surface, or any live lane.
