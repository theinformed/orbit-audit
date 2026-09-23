# T5a: WHY THE SECOND HARMONIC IS INVERTED — PRE-REGISTRATION

> **Committed ALONE and ahead of every number this experiment produces.** No
> instrument file, no results file and no run exists at this commit. The three
> candidate mechanisms below are DERIVED here, before any measurement, and each
> one is written as a prediction that the experiment can refute.

Written 2026-09-22. The question is
`docs/matched-filter-rung2-results-20260922.md` section 6 item 8, in its own
words: *"Whether the anti-phase second harmonic is a burn pair, an archive
smoothing, or something else is UNPROVEN. Section 3.4 measures that it is there
and that it is inverted; the injection-recovery arm of design 7.3 is still the
measurement that would say which."*

The operator's instruction is narrower and is the one this document answers:
**if the model is smoothing it, that is something we need to figure out
definitively.**

---

## 0. The measurement that provokes this, restated exactly

`psi_k = theta_k - k theta_1`, each harmonic fitted **alone**, pooled over
carrier segments at the `L = 42 d` ladder
<!-- src: docs/matched-filter-rung2-results-20260922.md section 3.4 -->:

| `k` | FLOOR `R_k` | carriers `R_k` | CEILING `R_k` | carriers' mean angle |
|---|---:|---:|---:|---:|
| 2 | 0.038 | 0.084 | 0.532 | **3.19 rad** (`pi` to 0.05 rad) |
| 3 | 0.048 | 0.255 | 0.313 | 6.18 rad (`-0.10` rad, i.e. 0) |
| 4 | 0.014 | 0.051 | 0.224 | **2.93 rad** (`pi` to 0.21 rad) |
| 5 | 0.027 | 0.116 | 0.131 | 6.16 rad (`-0.12` rad, i.e. 0) |

**The signature this document must explain is not "`k = 2` is inverted". It is
`(psi_2, psi_3, psi_4, psi_5) = (pi, 0, pi, 0)` — every EVEN harmonic inverted
and every ODD harmonic upright.** Section 3.4 reported `k = 2` and `k = 3`
because those are the two the registration screened; `k = 4` and `k = 5` are in
the same table and carry the same pattern, and reading all four is the single
most constraining thing this experiment can do, because it removes most of the
candidate space before a byte of data is touched.

## 1. The phase convention, fixed here so that no prediction can be reinterpreted afterwards

The instrument fits each harmonic alone with the single-harmonic member whose
complex weight is `W = -2i/pi` (normalised to `-i`), and
`tools/matched_filter.py:template_series` evaluates
`Re(W e^{-i k phi}) cos(2 pi k f t) - Im(W e^{-i k phi}) sin(2 pi k f t)`. With
`W = -i` and one harmonic that is

> `sin(2 pi f t - phi)`
> <!-- derivation: W e^{-i phi} = -i(cos phi - i sin phi) = -sin phi - i cos phi;
>      Re = -sin phi, Im = -cos phi; -sin phi cos x + cos phi sin x = sin(x - phi) -->

so **the fitted phase `theta_k` is defined by the model column
`sin(2 pi k f t - theta_k)`**, and this is the convention every prediction below
is written in. The one-burn drift-rate sawtooth of design 1.1, as
`tools/matched_filter.py:ideal_sawtooth` builds it, is
`s(t) = 1 - 2 frac(t/P - phi/2pi)`, whose Fourier series is

> `s(t) = sum_k (2/(pi k)) sin(2 pi k f t - k phi)`
> <!-- derivation: the standard series 1 - 2u = sum_k (2/(pi k)) sin(2 pi k u)
>      on u in [0,1), with u = t/P - phi/2pi -->

Therefore `theta_k = k phi` exactly, and

> **PREDICTION 0 (the template's own signature): `psi_k = 0` for every `k`, at
> every phase, for the one-burn sawtooth.**

Two structural facts follow and both are used below.

**(i) `psi_k` is invariant under any time shift.** A shift `tau` sends
`theta_k -> theta_k + 2 pi k f tau`, so `psi_k -> psi_k + 2 pi k f tau -
k (2 pi f tau) = psi_k`. **Nothing that acts as a pure delay can produce the
measured signature**, which disposes of a whole class of candidate explanations
(epoch conventions, the asymmetry of a fit span that ends at its epoch, a
constant light-time or clock offset) before the experiment starts.

**(ii) A real multiplicative factor `h_k` per harmonic shifts
`psi_k` by `pi (s_k - k s_1)` where `s_k = 1` if `h_k < 0` and `0` otherwise.**
Modulo `2 pi`, `pi k s_1` is `0` for even `k` and `pi s_1` for odd `k`, so

> `psi_2 shift = pi s_2`, `psi_3 shift = pi (s_3 + s_1)`,
> `psi_4 shift = pi s_4`, `psi_5 shift = pi (s_5 + s_1)`.
> <!-- derivation: arg(h_k) is 0 or pi; substitute into psi_k = theta_k - k theta_1 -->

**(iii) A global sign flip of the waveform** (`s_k = 1` for every `k`) gives
`psi_k shift = pi (1 - k)`, i.e. `(pi, 0, pi, 0)` for `k = 2..5`. **That is the
measured signature exactly.** So the question this experiment really asks is:
**what negates the waveform?** Three things can, and they are (a), (b) and (c).

## 2. The three candidate mechanisms, derived

Every prediction in this section was produced by algebra and by a model-only
numerical check (no archive, no element set) run before this document was
committed; `tools/harmonic_mechanism.py` and its tests, which do not yet exist,
will assert each derivation independently of the code that uses it.

### 2.1 Candidate (a) — ARCHIVE / FIT SMOOTHING, and our own processing chain

**(a1) The archive.** A catalogue element set is a fit over a span, not an
instantaneous sample. Model the recovered mean motion as a boxcar average of the
true mean motion over a span `W`. For a least-squares fit of a constant (plus a
rate, which is orthogonal to the constant on a symmetric span) against uniform
weights, the recovered constant IS the boxcar mean, so

> `H(nu) = sinc(nu W) e^{-i pi nu W_offset}`, `sinc(x) = sin(pi x)/(pi x)`
> <!-- derivation: Fourier transform of a unit-area boxcar of width W; the
>      exponential is the pure delay of a span whose epoch is not its centre -->

The exponential is a **pure delay** and by 1(i) cannot touch `psi_k`. `sinc` is
**real**, so by 1(ii) smoothing can only ever flip signs, never rotate phases by
an arbitrary angle. The sign pattern is `s_k = [sinc(k W / P) < 0]`.

**Spans considered, and why.** `W` is scanned from 0.05 d to 30 d in 0.005 d
steps. The lower end is below the element-set cadence (roughly daily for these
objects), which bounds any achievable resolution from below; the upper end is
twice the line period, beyond which the fundamental has already been nulled
twice. **The programme has no citation for the operational fit span used for
geostationary objects and does not assert one** — the scan is exhaustive over
the range instead, which is the honest substitute.

**Result of the scan (derived, pre-run):** the measured signature
`(pi, 0, pi, 0)` is produced **only** by

> `W in [11.205, 14.000) d` and `W in [25.205, 28.000) d`
> <!-- derivation: exhaustive sign enumeration of sinc(k W / P), P = 14 d -->

and on the FIRST of those bands the fundamental's own transfer is
`|sinc(W/P)| <= 0.2334`, falling to 0 at `W = 14 d`; on the second it is
`<= 0.1038`. So:

> **PREDICTION (a): smoothing CAN flip the sign of `k = 2` at a 14 d period — a
> flip, not merely an attenuation — but ONLY for a span between 11.21 and
> 14.00 days (or 25.21 to 28.00), and at that span it attenuates the FUNDAMENTAL
> to at most 23.3% of its true amplitude (a loss of at least 12.6 dB in power).
> A span short enough to leave the fundamental intact cannot flip `k = 2`: the
> `k = 2` flip alone needs `W > 7 d`, at which the fundamental is already down to
> 63.7%, and `k = 3` staying upright with `k = 1` upright needs `W < 4.66 d` or
> `W > 9.33 d`.**

This is a falsifiable prediction with a numeric consequence, and it is checked
two ways below: by measuring the archive's effective smoothing span directly
(arm H), and by pushing an analytically pre-smoothed sawtooth through the whole
pipeline at a ladder of spans (arm D).

A partial cross-check already exists in the record and is stated here so it
cannot be produced afterwards as a surprise: the amplitude bracket of
`docs/matched-filter-rung2-results-20260922.md` section 3.5 puts the measured
line amplitude at **0.28 to 0.56** of the design's derived value, and the
smoothing band requires `<= 0.233`. The bracket is a screen with two ladders
disagreeing by a factor of two and several competing explanations for a deficit,
so this is **tension, not refutation**, and it is not the basis of any verdict.

**(a2) Our own processing chain.** Three operations act between the archive and
`psi_k`, and each is derived rather than assumed:

1. **Polynomial detrend.** `tools/matched_filter_phase.py` removes a degree-1
   polynomial from each 42 d segment (degree 3 from each 1080 d window) and
   divides by the residual RMS. Division by a positive scalar has no phase. The
   polynomial projection is a real linear projection; the profile statistic
   carries the same basis in its Gram, so the harmonic is fitted **orthogonally
   to** the polynomials rather than after a separate subtraction. Its effect on
   `theta_k` is `O(1/(k n_cycles))` — a 42 d segment carries 3.00 cycles at
   `k = 1` and 15.0 at `k = 5` — and it is **the same sign of effect at every
   `k`, monotonically smaller with `k`**, so it can shrink `R_k` but has no
   mechanism for a `pi` rotation at even `k` only. **PREDICTION (a2-i): the
   detrend contributes `|psi_k| < 0.1 rad` at every `k`; measured directly by
   arm A (positive control on synthetic noise), where the recovered `psi_k` must
   come back at 0.**
2. **Window taper.** There is none. `dense_reductions` applies no apodisation;
   the only weighting is the mask. A symmetric taper would in any case be real
   and even, hence covered by 1(ii).
3. **Differencing.** The pipeline does not difference. If it did, 2.3 gives its
   exact `psi` signature and it is not `(pi, 0, pi, 0)`.

### 2.2 Candidate (b) — BURN STRUCTURE

Four families, each derived in closed form and each checked numerically against
a directly synthesised waveform before this document was committed.

**(b1) One-burn sawtooth** (design 1.1): `psi_k = 0` for all `k`
(PREDICTION 0). **Refuted by the measurement, which is why we are here.**

**(b2) Two-burn split reset, separation `s` (as a fraction of the period),
second impulse of relative size `rho`.** Superposing two sawtooths offset by `s`
multiplies harmonic `k` by `(1 + rho e^{-2 pi i k s})`
<!-- src: docs/matched-filter-design-20260922.md section 1.3(c) -->. At
`rho = 1` that is `2 cos(pi k s) e^{-i pi k s}`: a pure delay (invisible to
`psi` by 1(i)) times a REAL factor, so by 1(ii) the shift is again a sign
pattern, `s_k = [cos(pi k s) < 0]`. Requiring `psi_2 = pi` needs
`cos(2 pi s) < 0`, i.e. `s in (0.25, 0.75)`; requiring `psi_3 = 0` needs
`s_3 = s_1`, i.e. `s in (0, 1/6) U (5/6, 1)`. **The two are disjoint.** For
`rho != 1` the factor is genuinely complex and no longer restricted to sign
flips, so it was scanned exhaustively over `s in [0.01, 0.99]` step 0.005 and
`rho in [0.05, 1.50]` step 0.05, at a tolerance of 0.35 rad:

> **PREDICTION (b2): NO two-burn split reset, at any separation and any
> second-impulse size, produces `psi_2 = pi` together with `psi_3 = 0`. The
> family is refuted in advance — 0 of 5,940 scanned cells (198 separations x 30
> impulse ratios) match.**
> <!-- derivation: exhaustive scan of psi_k = -arg(1 + rho e^{-2 pi i k s}) + k arg(1 + rho e^{-2 pi i s}) -->

This matters because "a burn pair" is the first explanation section 6 item 8
offers, and the algebra says it cannot be right in this form.

**(b3) Symmetric triangle** (drift ramped both ways by two equal burns half a
period apart). Its Fourier series contains **only odd harmonics**; the numerical
check returns harmonic amplitudes `(0.811, 0.000, 0.090, 0.000, 0.032)`.

> **PREDICTION (b3): a symmetric triangle puts NO second harmonic in the data at
> all. `psi_2` is then undefined and `R_2` must fall to the floor arm's value.
> The measurement has `R_2 = 0.084` against a floor of 0.038 and a median
> `F = 3.01` against the floor's 0.80, so `k = 2` is present. The triangle is
> refuted by the existing measurement.**

**(b4) A one-burn sawtooth of the OPPOSITE SIGN.** Design 1.1 writes the
constant drift acceleration as `A = A_max |sin(2(lambda_slot - lambda_22))|` —
an **absolute value**. The underlying relation
`d^2 lambda / dt^2 = -18 n^2 J22 (R_e/a)^2 sin(2(lambda - lambda_22))`
<!-- src: docs/cadence-results-20260921.md section 5.3 --> changes sign with the
slot's position relative to the triaxial equilibria, and the sign of `A` is the
direction the drift ramp runs. With `A < 0` the parabolic arch in longitude
opens downward, the drift rate ramps from `+v0` to `-v0` and the burn is
positive — design 1.1's case. With `A > 0` the arch opens upward, the satellite
is placed at the far edge, **the drift rate ramps from `-v0` to `+v0` and the
reset impulse is negative**. That waveform is `-s(t)`, and by 1(iii)

> **PREDICTION (b4): a slot on the other side of its triaxial equilibrium gives
> `(psi_2, psi_3, psi_4, psi_5) = (pi, 0, pi, 0)` — EXACTLY the measured
> signature, at every harmonic, for free, with no parameter fitted.**
> <!-- derivation: negating the waveform adds pi to every theta_k; psi_k shift
>      = pi(1 - k); numerically confirmed against a synthesised -s(t) -->

**And (b4) makes a second, sharper prediction that (a) and (c) cannot make.**
The sign of `A` is a property of the SLOT, not of the pipeline. A fleet of 208
carriers distributed around the ring therefore contains **both** signs, so:

> **PREDICTION (b4-pop): under (b4) the per-object `psi_2` distribution is
> BIMODAL — one mode at 0 and one at `pi` — and the pooled resultant is the
> small difference between two populations rather than one weak concentration.
> Quantitatively, if a fraction `p` of segments carry the inverted sign and each
> object reaches the ceiling's per-segment concentration `R_ceil = 0.532`, the
> pooled resultant is `R = R_ceil |2p - 1|`; the measured `R_2 = 0.084` implies
> `p = 0.579`, i.e. roughly a 58/42 split.**
> <!-- derivation: the resultant of a two-component mixture of opposed unit
>      vectors, each of concentration R_ceil -->
>
> **Under (a) or (c) the cause is common to every object and the per-object
> `psi_2` distribution is UNIMODAL at `pi`.**

This is the decisive discriminator between "the data does it" and "we do it",
and it costs nothing: it is the same statistic, grouped by object.

### 2.3 Candidate (c) — WRONG OBSERVABLE

The channel analysed is `mean_motion`. Design 1.1 argues the sawtooth lives in
the drift-rate channel and that mean motion **is** that channel:
`lambda_dot = n - omega_E`, so `delta n` is the sawtooth itself and not its
integral. Take that as the claim to be tested rather than as a fact.

If a waveform `x(t)` is integrated, `int sin(2 pi k f t - theta) dt =
-cos(...)/(2 pi k f) = sin(... - pi/2)/(2 pi k f)`, so **every** `theta_k` gains
`+pi/2` and the amplitude gains a positive factor `1/(2 pi k f)`. Hence

> `psi_k -> psi_k + (1 - k) pi/2` per order of integration, and
> `psi_k -> psi_k - (1 - k) pi/2` per order of differentiation.
> <!-- derivation: theta_k -> theta_k + pi/2 for every k; substitute into
>      psi_k = theta_k - k theta_1 -->

| order `m` | `psi_2` | `psi_3` | `psi_4` | `psi_5` | matches `(pi, 0, pi, 0)`? |
|---|---:|---:|---:|---:|---|
| `m = +1` (one integration — longitude) | `-pi/2` | `pi` | `+pi/2` | 0 | **no** |
| `m = +2` (two integrations) | `pi` | 0 | `pi` | 0 | **YES** |
| `m = -1` (one differentiation) | `+pi/2` | `pi` | `-pi/2` | 0 | **no** |

> **PREDICTION (c): a single integration or differentiation — the only
> element-to-element confusions that are physically available (mean motion vs
> longitude vs drift rate) — produces `psi_2 = -pi/2` or `+pi/2` and
> `psi_3 = pi`. NEITHER matches. The ONLY integration order that reproduces the
> measured signature is `m = +2`, which is `(1 - k) pi` — identical to a sign
> flip, because the second integral of a sine is the negated sine divided by
> `(2 pi k f)^2`.**

So (c) survives only in a degenerate form, and it is separable from (b4) by
**amplitude**, not by phase: two integrations impose an extra real factor
`1/k^2` on top of the sawtooth's own `1/k`, giving harmonic amplitudes `1/k^3`.

> **PREDICTION (c-amp): if the signature is two integrations, the harmonic
> amplitude ratio `A_2/A_1` is `1/8 = 0.125`; if it is a sign flip of the
> sawtooth it is `1/2 = 0.500`. These differ by a factor of four and the
> existing measurement can already screen them: debiased power `F - 2` gives
> `A_2/A_1 = sqrt(1.01/9.81) = 0.32`, between the two and nearer the sawtooth.
> That number is a SCREEN taken from one ladder of an existing document, it is
> not re-derived here, and no verdict rests on it alone.**

There is also no physical route by which a doubly integrated drift rate would be
recorded as a mean motion: one integration of `lambda_dot` is longitude, two is
not an element. **(c) is therefore already the weakest of the three on physics,
and the experiment's job is to close it empirically rather than to argue it
closed.**

---

## 3. The experiment

### 3.1 Design

**INJECTION-RECOVERY.** A synthetic waveform of known phase is added to the
`mean_motion` series of REAL passive (non-manoeuvring) geostationary objects —
their real epochs, real gaps, real archive processing and real noise — and
pushed through the **identical** pipeline that produced the measurement in
section 0: `tools/matched_filter_phase.py`'s own `object_segments`,
`detrend_unit_rms` and `fit_harmonics`, imported and called, not reimplemented.
The recovered `psi_k` is then compared with the waveform's known `psi_k`.

**The passive class is the T3/T8 control class**, taken as built:
`docs/matched-filter-devset-20260922.json:sameShellGeoPassiveControl`, 331
same-shell geostationary passive objects, the identical set that supplied the
FLOOR arm of the measurement being explained. It is used because it carries the
class's own sampling geometry and archive treatment while carrying no
station-keeping signal of its own to interfere with the injected one — which is
precisely the defect of the existing CEILING arm, whose injection went into the
carriers and therefore landed on top of the very anti-phase harmonic under
investigation
<!-- src: docs/matched-filter-rung2-results-20260922.md section 3.1 -->.

**What injection-recovery can and cannot decide, stated before it runs.** The
injection is added to element values the archive has ALREADY produced.
Therefore it tests **our pipeline**, and it does NOT test the archive's fit
smoothing, which acted before those values existed. Any claim that injection
alone exonerates "the archive" would be false and this registration refuses it
in advance. The archive half of candidate (a) is carried by arms D and H
instead. **This is a named limitation, not a deviation.**

### 3.2 Arms

Ladder `L = 42 d` throughout (the ladder whose controls section 3.3 of the
results licenses); harmonics `k = 1..5`; fundamental fixed at the registered
grid index `I0 = 1929`, `P0 = 13.99657 d`; segment detrend degree 1; injected
amplitude `3.3067e-5 rev/day` (design 1.2, the same the ceiling arm used);
injected phase 1.0 rad; seed **20260922**.

| arm | content | what it decides |
|---|---|---|
| **A — POSITIVE CONTROL** | one-burn sawtooth injected into pure synthetic Gaussian noise carried on the passive objects' REAL epochs | the pipeline's own `psi_k` bias with no archive at all; must return `psi_k = 0` |
| **B — NULL FLOOR** | the same synthetic noise, no injection | the per-`k` resultant floor `R_k^floor`, read BEFORE any other number |
| **C — MAIN** | one-burn sawtooth injected into the REAL passive series | the decisive arm: does the pipeline plus the archived series invert `k = 2`? |
| **C2 — amplitude sensitivity** | arm C at `1.85e-5 rev/day` (the section 3.5 bracket's upper value) | whether the verdict depends on the injected amplitude |
| **D — SMOOTHING TRANSFER** | the ANALYTICALLY boxcar-averaged sawtooth (exact, harmonic by harmonic, `H(nu) = sinc(nu W)`) injected into the real passive series, for `W` in {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 11.5, 12, 13} d | measures `psi_k(W)` end to end and tests PREDICTION (a) against the pipeline rather than on paper |
| **E — BURN FAMILIES** | one-burn; NEGATED one-burn; two-burn `rho = 1` at `s` in {0.2, 0.3, 0.4, 0.5}; two-burn `rho = 0.5` at `s` in {0.35, 0.5}; symmetric triangle; bank sawtooth at duty 0.5 and 0.7 — each injected into the real passive series | tests PREDICTIONS (b1)-(b4) through the instrument |
| **F — OBSERVABLE** | the sawtooth's first and second integral injected into the same channel | tests PREDICTION (c) through the instrument |
| **G — PER-OBJECT SIGNATURE** | the 208 REAL east-west carriers, no injection, `psi_2` computed PER OBJECT | tests PREDICTION (b4-pop): bimodal at {0, `pi`} or unimodal at `pi` |
| **H — ARCHIVE SMOOTHING SPAN** | roughness estimator on the real passive series: `W_eff = dt / r^2` with `r = RMS(diff x) / (sqrt(2) RMS(x))` on each detrended segment | bounds the archive's effective boxcar span from ABOVE, against the 11.21-14.00 d band PREDICTION (a) requires |

Arm H's estimator is derived, not asserted: boxcar-smoothed white noise has
autocovariance `rho(tau) = 1 - |tau|/W`, so
`Var(diff) = 2 sigma^2 (1 - rho(dt)) = 2 sigma^2 dt/W` and
`r = sqrt(dt/W)`, giving `W_eff = dt / r^2`
<!-- derivation: computed for this document; asserted by the tests on a
     synthetic boxcar-smoothed series -->.
Any REAL smooth signal in the series lowers `r` and therefore INFLATES `W_eff`,
so `W_eff` is an **upper bound** on the archive's smoothing span. An upper bound
is exactly the right instrument here, because PREDICTION (a) needs a LARGE span.

### 3.3 Read the floors and the ceilings first

Section 3.1 of the results document is binding: no `psi` number in this
experiment is interpreted before arm B's per-`k` floor and arm A's per-`k`
ceiling are both printed. A recovered `R_k` is read as a fraction of arm A's
`R_k`, never against 1; a recovered mean angle at `R_k` below arm B's floor is
reported as **undefined**, not as an angle. Exposure (segments offered,
admitted, rejected by each registered criterion) is reported for every arm.

### 3.4 Decision rule, fixed before the run

The verdict line of the results document is one of four words. The rules are
mutually exclusive and are evaluated in this order. `ANGLE_TOL = 0.40 rad`;
`R_FRACTION_MIN = 0.25` of arm A's `R_k` (an arm whose recovery is fainter than
a quarter of the positive control is not read as an angle).

1. **OBSERVABLE** if arm A or arm C returns `psi_2` within `ANGLE_TOL` of `pi`
   for an injected ONE-BURN sawtooth. The pipeline then inverts a waveform that
   is upright by construction, and the inversion in the carriers is our own
   doing — an observable/convention fault, not physics. Arm F names the order.
2. **SMOOTHING** if arm C returns `psi_2` within `ANGLE_TOL` of 0 (so the
   pipeline is clean) **AND** arm H's upper bound `W_eff` for the passive class
   lands inside `[11.21, 14.00] d` (or `[25.21, 28.00] d`) **AND** arm D
   reproduces `(pi, 0, pi, 0)` at a span inside that band. All three are
   required: the band is where the algebra says a flip lives, arm H says whether
   the archive is plausibly there, and arm D says the pipeline transmits it.
3. **BURN STRUCTURE** if arm C returns `psi_2` within `ANGLE_TOL` of 0, arm H's
   upper bound excludes the smoothing band, and arm E identifies a waveform
   family whose injected `(psi_2, psi_3, psi_4, psi_5)` matches
   `(pi, 0, pi, 0)` within `ANGLE_TOL` at all four harmonics. The verdict then
   NAMES the family. If in addition arm G returns a bimodal per-object `psi_2`
   with both modes populated above arm B's floor, the verdict states that the
   sign is a per-object property — which is what (b4) requires and what (a) and
   (c) forbid.
4. **UNRESOLVED** in every other case, including: arm C upright and arm H
   excluding the smoothing band but no family in arm E matching at all four
   harmonics; arm G unimodal while arm E names a per-object mechanism; arms
   disagreeing; or any arm whose `R_k` falls below `R_FRACTION_MIN` where the
   rule needs an angle from it. **UNRESOLVED is a permitted outcome and will be
   reported in that word.**

A fifth possibility is named so that it cannot be presented as a discovery
afterwards: arms C and G may both be clean and arm E may match at `k = 2` and
`k = 3` but not at `k = 4` and `k = 5`. In that case the verdict is
**UNRESOLVED** and the results document reports which harmonics the family does
explain. The four-harmonic requirement is deliberate: `(pi, 0, pi, 0)` is far
more constraining than `(pi, 0)`, and the registration would rather return
UNRESOLVED than accept a family on half the evidence.

### 3.5 What is NOT being claimed

- No p-value, no gate, no object relabelled, no inferential statistic. This is a
  mechanism measurement, exactly as section 3 of the rung-2 results was.
- No recall is measured, nothing bounds a null, and the element weights remain
  the screen design 3.3 declares.
- This experiment does not revise the statistic prescribed by
  `docs/matched-filter-rung2-results-20260922.md` section 3.6. It explains a
  term in it. If the verdict is BURN STRUCTURE, the prescribed `k = 2`-free
  phase becomes a physically-understood free parameter rather than an unexplained
  one, and a future registration may replace it by a per-object SIGN — but that
  registration is not this one and no such filter is built here.
- Arm G reads REAL carrier data with no injection. It is descriptive, it is one
  of the estimands the previous registration already covered at population
  level, and its per-object decomposition is registered HERE before it is
  computed.

### 3.6 Reproducibility

Seed 20260922 for every synthetic series. Inputs: `/home/sdegan/t3-cadence/full`
(the T3 extraction, `index.json` plus the four memmapped columns) and
`docs/matched-filter-devset-20260922.json` at its committed contents. Host CPU
only — the frequency axis is eleven points per fit, as
`tools/matched_filter_phase.py` established, so claiming a device would be
theatre. **No GPU is requested and none will be used**; if that changes it goes
through `gpu-run` with an honest estimate and is recorded as a deviation.

Outputs: `docs/harmonic-mechanism-results-20260922.json` (every arm, every
exposure count, every floor) and `docs/harmonic-mechanism-results-20260922.md`
whose **first line is the verdict word**.

### 3.7 Order of commits

1. This document, ALONE.
2. `tools/harmonic_mechanism.py` and `tests/test_orbit_harmonic_mechanism.py`.
3. The run, the JSON and the results document.
4. The runbook row.

`tools/matched_filter_v2.py`, `tools/matched_filter_v2_run.py` and
`tools/rung2_separation*.py` belong to other sessions and are neither created
nor edited here; `tools/matched_filter.py` and `tools/matched_filter_phase.py`
are IMPORTED and not modified, so that "the identical pipeline" is a fact about
the code and not a claim about it.

---

## 4. Summary of what is predicted, in one table

| mechanism | `psi_2` | `psi_3` | `psi_4` | `psi_5` | extra requirement | matches? |
|---|---|---|---|---|---|---|
| (0) one-burn sawtooth, design 1.1 | 0 | 0 | 0 | 0 | — | no |
| (a) boxcar smoothing, `W < 4.66 d` | 0 | 0 | 0 | `pi` (`W>2.8`) | — | no |
| (a) boxcar smoothing, `W in [7, 9.33) d` | `pi` | `pi` | — | — | — | no |
| (a) boxcar smoothing, `W in [11.21, 14) d` | `pi` | 0 | `pi` | 0 | fundamental `<= 23.3%` | **yes, at a price** |
| (b2) two-burn, any `s`, any `rho` | — | — | — | — | — | **no cell** |
| (b3) symmetric triangle | undefined | `pi` | undefined | 0 | `k=2` absent | no |
| (b4) sign-flipped sawtooth | `pi` | 0 | `pi` | 0 | per-object bimodality | **yes, free** |
| (c) one integration | `-pi/2` | `pi` | `+pi/2` | 0 | — | no |
| (c) one differentiation | `+pi/2` | `pi` | `-pi/2` | 0 | — | no |
| (c) two integrations | `pi` | 0 | `pi` | 0 | `A_2/A_1 = 0.125` | **yes, no physics for it** |

Three of ten survive the phase algebra. Each of the three carries a distinct,
measurable extra requirement — a crushed fundamental, a per-object bimodality, a
fourfold harmonic amplitude deficit — and the experiment is built to read those
three requirements rather than to re-read the phases.
