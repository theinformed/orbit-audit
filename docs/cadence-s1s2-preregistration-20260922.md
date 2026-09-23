# T3 supplementary pre-registration: secondary channels S1 (inclination) and S2 (eccentricity)

Registered 2026-09-22, **before any S1 or S2 periodogram, threshold, count or
result exists**. Committed alone, ahead of every artifact this channel pair will
ever produce, exactly the way `docs/cadence-preregistration-20260921.md` was
committed alone at `1a51afe` ahead of the primary channel. The git history of
this file is the timestamp.

This document is **supplementary, not a replacement**. The T3 registration of
2026-09-21 remains binding in every particular. Section 1 lists, with citations,
the S1/S2 choices it has already made — those are followed exactly and **no new
registration was needed for them**. Sections 2 onward register only the things
the original document is genuinely silent about, and each one says why the
silence had to be filled before a number could be produced.

Estate rule this document is written under, and the reason sections 3 and 4 are
derivations rather than assertions: **physical assumptions are not facts —
derive or cite every physical claim; thresholds are screens, not laws.**

---

## 0. Disclosure: what is already known, and why it cannot have shaped this

Concealing what the author had already seen is how a supplementary registration
becomes a post-hoc rationalisation. In full:

1. **The primary-channel result exists and has been read.**
   `docs/cadence-results-20260921.md` (`da957ba`) reports the registered
   per-object test as NULL in both classes, a window-threshold transfer failure
   (passive 9.32% against payload 3.36%), and a descriptive 14.00 d east-west
   GEO line at 10.16x local background in payloads and 0.94x — absent — in the
   passive control. Section 5 of that report is the reason the headline question
   of this document is phrased the way it is.
2. **The S1 and S2 *inputs* already exist on disk.** The single extraction pass
   of 2026-09-21 wrote `inclination.bin` and `eccentricity.bin` beside
   `mean_motion.bin` under `/home/sdegan/t3-cadence/full/`, because the
   registration named three channels and extraction is one streaming pass.
3. **No S1 or S2 periodogram has ever been computed.** Both shard summaries
   record `"channels": ["mean_motion"]` and nothing else
   (`/home/sdegan/t3-cadence/full/mm-shard{0,1}.npz.summary.json`). There is no
   S1 or S2 power value, peak frequency, threshold, count or verdict anywhere in
   this repository or on this host at the moment this file is committed. Every
   number registered below is therefore a rule stated before its own evidence.
4. **Population-level census quantities are known** (20,338 objects extracted,
   8,841 payload / 11,497 passive, and the per-regime object counts in
   `docs/cadence-results-20260921-receipt.json`). These are counts of objects,
   not values of the S1/S2 channels, and are the same class of information the
   original registration's section 0 disclosed for the primary. No S1/S2 element
   value entered any choice below.

## 1. What the 2026-09-21 registration already binds — followed exactly, no new registration needed

Cited so that a reader can check this document did not quietly re-open a settled
question. Each of these is applied verbatim and is **not** re-registered here:

| Question | Where it is already answered | What is applied |
|---|---|---|
| Which elements are S1 and S2 | prereg 3.2 | S1 = inclination in degrees, S2 = eccentricity, both as archived |
| Why they exist at all | prereg 3.2, 9.3 | N-S GEO station-keeping is invisible in the energy channel; GEO eccentricity control moves `e` with little `n` signature |
| Threshold percentile | prereg 6.3 | 99th percentile, primary and only primary; 95th and 99.9th displayed, never promoted |
| Whose distribution sets it | prereg 3.2, 6.1, 6.2 | each channel carries its **own independent** calibration, from the passive **calibration half only**, split by the same `sha256("t3-20260921:<norad>")` object hash |
| Matching cells and fallback ladder | prereg 6.3, 6.4 | the same 5-factor cell (perigee x inclination x eccentricity x cadence x N-band), the same 200-window minimum, the same four fallback rungs, the same requirement to report fallback exposure |
| Frequency grid | prereg 4 | identical: 2–220 d, `df = 1.85185e-4` c/d, 2,676 points |
| Windows | prereg 5.1 | identical: `W = 1080 d`, `S = 360 d` |
| Detrending | prereg 5.2 | identical: least-squares **cubic** in time, per window, "fitted to the channel" — section 3.2 below derives that this is adequate for inclination rather than assuming it |
| Multiple testing | prereg 8.2, 8.4 | object-level statistic against object-level null, window-count-band matched; **independent BH at q = 0.05 per channel**; no "significant in at least one channel" statistic is computed |
| Reporting separation | prereg 3.2 | S1 and S2 results appear in tables separate from the primary, and a secondary result is never quoted as if it were a primary one |
| Acceptance criteria | prereg 3.2, 10 | **Gates A/B/C are evaluated on the primary channel only.** Gate-shaped quantities computed for S1/S2 are reported as descriptive shape and carry no acceptance meaning |
| Change-points | prereg 7 | computed **only on the primary channel**; S1/S2 produce no E2 result |
| Resources | prereg 13 | `gpu-run`, honest `--estimate-mib`, class `standard`, beside resident training on Sean's authorization, `CUDA_VISIBLE_DEVICES` as a UUID, no recurring lane and therefore no `gpu-consumers.json` row |
| No shopping | prereg 11 | seed 20260921, **one measurement pass**, an unwelcome number may not be re-run |

## 2. What this document registers, and why the original is silent on it

The original registration named S1 and S2 and fixed their statistical treatment.
It did not — and could not, without doing the physics — fix five things:

- **S2a.** What natural, in-band signal content the inclination and eccentricity
  channels are *expected* to carry. Prereg 6.5 derives this list for mean motion
  only, and says so in those words ("a passive object's mean motion can
  legitimately carry"). Without the analogous derivation a line in S1 cannot be
  told from a lunar term. **Section 3.3 and section 4.2.**
- **S2b.** Whether the registered cubic detrend is adequate against the secular
  lunisolar inclination drift, which is a far larger and differently shaped
  trend than the drag rise the cubic was justified against. **Section 3.2.**
- **S2c.** What a "north-south analogue of the 14-day east-west line" would have
  to look like to count as one. Declared in advance, or the answer is whatever
  the plot suggests. **Section 5.**
- **S2d.** How the archive's inclination quantisation interacts with a
  *controlled* GEO satellite's very small inclination excursion, which is a
  class-asymmetric resolution effect with a predictable direction.
  **Section 6.**
- **S2e.** Which population the GEO headline is measured on, and against which
  control. The primary report's own section 5.4 established that a **pooled**
  passive control's silence is not sufficient evidence of an operational origin.
  **Section 5.2.**

Nothing else is registered here. In particular this document changes **no**
threshold, band, window, percentile, correction or gate of the 2026-09-21
registration, and touches no shipped pipeline threshold (prereg 11).

## 3. The inclination channel, derived

### 3.1 The secular lunisolar drift at GEO

A third body of gravitational parameter `mu_3` at distance `r_3` precesses a
near-circular satellite orbit's pole about the third body's own orbit pole at
the doubly-averaged secular rate

&nbsp;&nbsp;&nbsp;&nbsp;`omega_prec = (3/4) * (n_3^2 / n) * cos(i_rel)`, with
`n_3^2 = mu_3 / r_3^3`,

the classical Kozai/Allan-Cook result for the lunisolar problem (Kozai 1959,
*Smithsonian Contr. Astrophys.* 5, 53; Allan & Cook 1964, *Proc. R. Soc. A* 280,
97; Kaula 1962, *Astron. J.* 67, 300). With `n = 2*pi/86164.0905 s = 7.2921e-5
rad/s` for a geostationary orbit:

| Body | `mu_3` (km^3/s^2) | `r_3` (km) | `n_3` (rad/s) | `omega_prec` |
|---|---:|---:|---:|---:|
| Sun | 1.32712440018e11 | 1.495978707e8 | 1.99098e-7 | **0.73717 deg/yr** |
| Moon | 4902.800118 | 384,400 | 2.93798e-7 | **1.60520 deg/yr** |

For an orbit that starts in the equatorial plane, the pole's speed across the
sky is `omega_prec * sin(theta)`, where `theta` is the angle between the
equatorial pole and the perturber's orbit pole:

- **Sun**, `theta = eps = 23.4393 deg`: `di/dt = 0.2932 deg/yr`.
- **Moon**, whose orbit is inclined `5.145 deg` to the ecliptic and whose node
  regresses with an 18.6-year period, so `theta` runs from `18.29` to
  `28.58 deg`: `di/dt = 0.5039` to `0.7680 deg/yr`.

The two perturber poles lie near the same great circle, so the contributions add
nearly along one direction, giving a total of **0.797 to 1.061 deg/yr**, mean
**0.932 deg/yr**. The standard literature figure is 0.75–0.95 deg/yr with a mean
near 0.85 (Soop, *Handbook of Geostationary Orbits*, 1994, ch. 4); the derivation
above runs about 8% high because it omits the coupling to Earth oblateness,
whose nodal regression at GEO is `dOmega/dt = -(3/2) J2 (R_e/a)^2 n =
-4.8995 deg/yr` — five times the lunisolar rate, which is what tilts the GEO
Laplace plane to roughly 7.4 deg instead of 23.4 and reduces the drift.

**Registered value.** `di/dt = 0.85 deg/yr` is used as the central figure and
**0.75 to 0.95 deg/yr** as the interval, i.e. the cited literature range, which
the derivation above brackets. Every period predicted from it in section 3.4 is
quoted as an interval, never as a point. This is a screen, not a law.

### 3.2 The registered cubic is adequate for the inclination trend — derived

Prereg 5.2 fixes a least-squares **cubic in time per 1080-day window**, applied
to "the channel". It justified degree 3 against the drag rise in mean motion. It
did not derive whether a cubic can follow the *inclination* trend, which is a
different shape. That derivation is owed and is given here.

Under the precession of section 3.1, an initially equatorial GEO orbit's pole
traces a circle about the Laplace pole, which for GEO sits `L = 7.4 deg` from
the equatorial pole with a full-circuit period `T_prec ~= 53 yr`. The inclination
magnitude is then

&nbsp;&nbsp;&nbsp;&nbsp;`i(t) = 2 * L * sin(pi * t / T_prec)`.

Over one registered window, `t = 1080 d = 2.9569 yr`, the argument runs from 0 to
`x_max = pi * 2.9569 / 53 = 0.17527 rad`, and `i` reaches **2.581 deg** — a mean
rate of **0.873 deg/yr**, which independently reproduces the section 3.1 figure
and is the check that the Laplace-plane picture and the direct torque
calculation agree.

A cubic in `t` is a cubic in `x`. The Taylor remainder of `sin(x)` after the
cubic term is `x^5/120`, so the *interpolation* error over the window is at most

&nbsp;&nbsp;&nbsp;&nbsp;`2 * L * x_max^5 / 120 = 2.04e-5 deg`,

and the standard bound on the **least-squares** degree-3 error over an interval
of half-width `h = x_max/2` for a function with `|f''''| <= 1`,
`2 * L * h^4 / (2^3 * 4!) = 4.55e-6 deg`, is smaller still.

**Both are below the archive's own inclination quantum of `1e-4 deg`.** The
registered cubic therefore removes the secular lunisolar inclination precession
of a near-equatorial GEO object to below the resolution at which the archive
records inclination at all. **No new detrending is registered, and none is
needed**; prereg 5.2 is applied to S1 unchanged.

Two honest limits on that statement, registered as such:

- It is derived for a **near-equatorial GEO** orbit, which is the population the
  headline question is about. For an object already at appreciable inclination,
  or in LEO or MEO where nodal regression is fast, `i(t)` over a window is still
  a smooth arc of the same 53-year-class precession but its magnitude trace can
  pass near a minimum, where `|i|` has a shallow V. That deposits power at the
  **lowest** frequencies of the band — the same band-top shoulder the primary
  run measured and diagnosed in its section 4(b) — and it is absorbed by the
  empirical passive null, which is measured through the identical cubic. It is
  not corrected for.
- The 18.6-year lunar-node modulation makes `di/dt` itself vary; over a 2.96-year
  window that is a slow amplitude change on a term the cubic already removes.

### 3.3 In-band natural content of S1 — the prereg 6.5 analogue, derived and cited

The list below is what a *passive* object's inclination can legitimately carry
inside the registered 2–220 d band. As in prereg 6.5, **none of it is subtracted
or excluded**: the model list is not complete, and the empirical passive null
carries the listed and unlisted alike. The list exists so a line landing on one
of these is recognised instead of being called a discovery.

**(a) Lunisolar periodic terms.** Kaula's (1962) development of the lunisolar
disturbing function, and Cook (1962, *Geophys. J. R. astr. Soc.* 6, 271), give
periodic inclination terms at the perturber's period and its half:

| Term | Period | Order-of-magnitude amplitude ceiling at GEO |
|---|---:|---:|
| half sidereal month | 13.6609 d | 9.6e-3 deg |
| half synodic month | 14.7653 d | 1.0e-2 deg |
| sidereal month | 27.3217 d | 1.9e-2 deg |
| anomalistic month | 27.5546 d | 1.9e-2 deg |
| synodic month | 29.5306 d | 2.1e-2 deg |
| solar semiannual | 182.6 d | 5.9e-2 deg |
| solar annual | 365.25 d | **out of band by prereg 4** |

The amplitude column is the ceiling `omega_prec * P / (2*pi)` — the excursion a
torque of the section 3.1 magnitude could produce if it reversed fully at that
period — using the lunar `omega_prec` for the lunar rows and the solar one for
the semiannual row. It is an **upper bound, not a prediction**; the true
amplitudes are smaller because of cancellation in the averaging, and this
registration does not claim to know them. It is stated because its size is the
whole problem: **the ceiling at 13.66 d, ~0.01 deg, is the same order as a tight
north-south deadband.** S1's confusion risk is not hypothetical.

**(b) The grid separates 14.0 d from the lunar half-months, and that must be
checked at the measured period rather than assumed.** At `P = 14.0 d` the
registered grid's core half-width (3 resolution elements, the same definition
`tools/cadence_lines.py` already uses) is `3 * df * P^2 = +/-0.1089 d`. The half
sidereal month at 13.6609 d is **3.11** core half-widths away and the half
synodic month at 14.7653 d is **7.03** away. A line at exactly 14.00 d is
therefore separable from both — but a line at 13.7 d is **not**, and this
registration commits in advance to calling such a line a lunar term.

**(c) The thermospheric family has no route at GEO.** Prereg 6.5's 27.3 d solar
rotation, 81 d F10.7 mean and 182.6 d semiannual density terms all reach the
elements through *atmospheric drag*. At `a = 42,164 km` drag is negligible, so
for the GEO population those routes are closed and the only natural in-band
mechanism is gravitational, i.e. list (a). That is a genuine strengthening of the
GEO null and is derived here rather than hoped for. It does **not** hold for the
LEO and MEO parts of the S1 population, where the drag routes are open and
prereg 6.5's full list applies.

**(d) J2 and tesseral terms** produce inclination oscillations at the orbital
and half-orbital period — 1.0 and 0.5 sidereal days at GEO — which are at or
above the band's `f_max = 0.5` c/d and are **out of band** (prereg 0.2, 9.2).

### 3.4 The predicted north-south cadence — registered before the measurement

North-south station-keeping holds the inclination vector inside a deadband while
the section 3.1 drift carries it across. For a deadband of half-width `R` and a
strategy that places the vector at one edge and lets the drift carry it to the
other, the cycle is `T = 2R / (di/dt)`. With the registered interval 0.75–0.95
deg/yr:

| Deadband `R` | `T` at 0.95 deg/yr | at 0.85 | at 0.75 |
|---:|---:|---:|---:|
| +/-0.010 deg | 7.69 d | **8.59 d** | 9.74 d |
| +/-0.025 deg | 19.22 d | **21.49 d** | 24.35 d |
| +/-0.05 deg (standard tight box) | 38.45 d | **42.97 d** | 48.70 d |
| +/-0.10 deg (standard loose box) | 76.89 d | **85.94 d** | 97.40 d |
| +/-0.25 deg | 192.24 d | **214.85 d** | 243.50 d |

Inverted, so the results report can read a deadband off whatever it measures
(at 0.85 deg/yr): `T = 14.0 d -> R = 0.0163 deg`; `21.0 d -> 0.0244 deg`;
`43.0 d -> 0.0500 deg`; `86.0 d -> 0.1001 deg`.

**Registered predictions, stated now:**

- **P1.** If GEO north-south keeping leaves a cadence fingerprint at all, the
  most likely places are **38–49 d** (the `+/-0.05 deg` latitude box) and
  **77–97 d** (the `+/-0.10 deg` box), because those are the two boxes standard
  GEO practice actually uses. Neither interval contains any natural line of
  section 3.3.
- **P2.** A north-south line at **14.0 d**, coincident with the primary
  channel's east-west line, is *plausible but is a different claim*: it would
  mean operators run north-south burns on the same operational cycle as
  east-west ones rather than at the cadence the deadband alone requires. The two
  cadences are driven by unrelated accelerations (triaxiality against lunisolar
  torque) and there is **no physical reason for them to coincide**. If 14.0 d is
  what S1 shows, that is an operational-scheduling finding, not a deadband
  measurement, and it will be written that way.
- **P3.** At 86 d the grid's core half-width is `+/-4.11 d` and the 0.75–0.95
  deg/yr spread alone is `+/-10 d`, so the `+/-0.10 deg` box predicts a **band,
  not a line**, and no narrow-line test can confirm it. This is registered now so
  that a broad, weak excess near 86 d is not later promoted to a detection.

## 4. The eccentricity channel, derived

### 4.1 What moves `e` at GEO

Solar radiation pressure drives the eccentricity vector around a circle whose
radius, for `C_R = 1.3` and the standard `P_SR = 4.56e-6 N/m^2`, is
`e_SRP = (3/2) * a_SRP / (n_sun * v_GEO)` with `n_sun = 1.99098e-7 rad/s` and
`v_GEO = 3074.7 m/s`:

| `C_R * A/m` | `a_SRP` | `e_SRP` |
|---:|---:|---:|
| 0.01 m^2/kg | 5.93e-8 m/s^2 | 1.45e-4 |
| 0.02 m^2/kg | 1.19e-7 m/s^2 | 2.91e-4 |
| 0.05 m^2/kg | 2.96e-7 m/s^2 | 7.26e-4 |

**Its period is the Sun's apparent year, 365.25 d, which prereg 4 places out of
band.** That is registered as a *hazard*, not a relief: 365.25 d is 2.96 cycles
in a 1080-day window, which a cubic whose resolution is `W/3 = 360 d` **cannot
remove**, and its skirt leaks into the top of the searched band. **Registered
expectation: S2's 160–220 d region carries an annual-SRP shoulder at least as
strong as the primary channel's, in both classes** — passive objects have larger
and more variable `A/m` and therefore larger SRP circles. Any excess in that
region is the shoulder until shown otherwise, and the core half-width at 182.6 d
is `+/-18.5 d`, which is not a line by any reading.

### 4.2 In-band natural content of S2

The same lunisolar periodic family as section 3.3(a) — 13.66, 14.77, 27.32,
27.55, 29.53 and 182.6 d — appears in eccentricity as well as inclination, from
the same disturbing function. For LEO objects, drag circularises the orbit,
which is a monotone trend the cubic removes, and the thermospheric lines of
prereg 6.5 modulate that trend, so the full prereg 6.5 list applies below 2,000
km. At GEO, as in section 3.3(c), the drag routes are closed.

### 4.3 The registered S2 prediction

An east-west station-keeping burn is **tangential**, so it changes `a` and `e`
together: a burn of `dV` changes the eccentricity vector by `|de| = 2*dV/v`. At a
typical GEO east-west budget of 2 m/s/yr, a 14-day cycle means 26 burns/yr of
0.0767 m/s, so `|de| = 4.99e-5` per burn — about 5,000 archive quanta
(`1e-8`), and about a sixth of the SRP circle radius for a typical `A/m`.

**P4 (registered).** The 14.00-day east-west line that the primary channel shows
descriptively in 208 GEO payloads **should also appear in S2**, in the same
objects, because the burns that produce it move `e` as well as `n`. This is an
independent-element corroboration test of the primary report's strongest
descriptive claim, and it is registered before it is run. If S2 does **not**
carry 14.0 d in the GEO payload class, that is evidence against the primary's
east-west interpretation and will be reported as such, not explained away.

## 5. The GEO headline — what counts as an answer, declared in advance

### 5.1 The measurement

A **descriptive** peak-frequency line profile, of exactly the kind
`tools/cadence_lines.py` already computes and which the primary report labelled
"NOT A REGISTERED TEST" — restricted to the GEO population. It carries no
p-values, feeds no gate, and no inferential claim rests on it. The registered
inferential result for S1 and S2 is the section 1 machinery (thresholds, BH,
payload-versus-passive rates), reported whatever it says.

Sweep parameters are **borrowed, not restated**, from the committed
`tools/cadence_lines.py` (`1ac5050`, committed before any T3 number existed):
`CORE_STEPS = 3`, background annulus `GAP_STEPS = 8` to `OUTER_STEPS = 40`, the
same local-annulus expectation, the same `excess = core / local expectation`.

### 5.2 Populations

- **GEO payload** — payload-class objects whose `regime(...)` is `"GEO"` under
  `tools.cadence_analyze.regime`, i.e. median perigee `>= 30,000 km`, median
  eccentricity `< 0.1`, median inclination `< 25 deg`. **Borrowed from committed
  code, not restated**, so this document cannot drift from the primary report's
  own regime labels.
- **GEO passive — the registered control.** Passive-class objects in the same
  `"GEO"` regime. The primary report's section 5.4 measured, in its own lane,
  that a **pooled** passive control's silence is *not* sufficient evidence of an
  operational origin: the 75.25 d line was absent from the pooled control only
  because passive objects scatter across altitudes. A same-regime control is the
  direct remedy and is registered here as the primary control for the GEO
  headline.
- The **pooled** passive excess is reported beside it, for continuity with the
  primary report — never in place of it.

### 5.3 D1 — the registered definition of "a north-south analogue exists"

A north-south analogue of the primary channel's 14.00-day east-west line exists
**iff all four hold** in the S1 channel on the GEO populations of section 5.2:

1. a local excess at some period `P` in the registered band with **payload
   excess `>= 5.0`** over its local background. The primary's east-west line
   measured 10.16x; 5.0 is set at half that, in advance, as the bar for
   "comparable in strength";
2. **GEO-passive excess `<= 1.5`** at the same `P`. The primary's control
   returned 0.94x; 1.5 is the bar for "the control does not carry it";
3. `P` separated from **every** natural line of section 3.3(a) by **more than
   the grid's core half-width at `P`**, `3 * df * P^2`;
4. carried by **`>= 20` distinct GEO payload objects**.

Every one of these four is a screen, not a law. A candidate failing any clause is
reported as **"no analogue meeting the registered definition D1"**, with the
measured numbers printed in full — never as "absent", and never with the clause
relaxed to admit it. A candidate passing all four is reported as a **descriptive
consistency statement** and explicitly not as a significance claim, in the same
words the primary report used for its own 14.0 d line.

### 5.4 Named examples

The results report names **3 to 5** carrier objects with the most windows on
whichever line the sweep returns, and states for each whether the catalogue name
identifies a **known station-kept commercial or government communications
satellite**. This is the ETALON discipline: the primary run's strongest payload
line turned out to be carried by two propulsion-free laser-ranging spheres
catalogued as PAYLOAD, and only naming the carriers exposed it. Any carrier that
is not a plausibly propelled satellite is reported as such and the line is
downgraded accordingly.

## 6. Resolution, quantisation, and a class-asymmetric confound registered in advance

Prereg 5.3(4) admits a window only if "the channel is not constant to within the
archive's quantisation", and gives `1e-8 rev/day` for `n`. The per-channel
quanta `1e-4 deg` for inclination and `1e-8` for eccentricity are the same rule's
application — each is `1/SCALE` for that element in `pipeline/orbit_history.py` —
and were committed in `tools/cadence_measure.CHANNEL_QUANTUM` at `1ac5050`,
**before any T3 number existed**. They are applied unchanged.

What prereg 5.3(4) did not anticipate is that **for inclination the two classes
sit on opposite sides of that quantum by construction**:

- a *controlled* GEO payload holds inclination inside a deadband of order 0.02–
  0.2 deg, i.e. **200 to 2,000** archive quanta of raw range per window;
- an *uncontrolled* GEO passive object drifts 0.85 deg/yr, i.e. **~25,000**
  quanta per window.

After the registered cubic removes the drift the two residual ranges are much
closer, but the *effective number of levels available to the periodogram* is
systematically smaller in the treated class than in the control. That is a known,
directional confound and it is registered rather than discovered.

Registered response, in three parts:

1. **The registered screen is not changed.** Prereg 5.3(4) is binding; the
   admission test stays `range <= quantum -> reject`.
2. **A diagnostic is required.** The results report must tabulate, by class and
   by regime, the distribution of `levels = raw window range / channel quantum`.
   A report of S1 without it is not permitted by this registration.
3. **A pre-registered sensitivity re-analysis**, reported *beside* the headline
   and never in place of it: the identical S1 analysis restricted to windows with
   `levels >= 10`. Ten is the point below which a series is a staircase whose
   Fourier content is the step pattern rather than the signal; it is a screen,
   not a law, and both numbers are reported whichever way they come out.

## 7. Blind spots specific to S1 and S2, declared in advance

Additional to prereg 9, which applies unchanged.

1. **The window set is the primary channel's.** `tools/cadence_measure.py`
   (committed `1ac5050`) evaluates prereg 5.3's sample-count, gap and span tests
   on **mean motion**, then applies only the constancy test per channel. S1 and
   S2 are therefore measured on exactly the windows the primary was measured on.
   That is a feature for comparability and a limitation for coverage: a window
   inadmissible in `n` is never examined in `i` or `e`, even if `i` and `e` are
   perfectly well sampled there. The count of windows this costs is not known in
   advance and is not corrected for.
2. **Inclination is stored as float32** in the extraction artifact. Its relative
   spacing is `1.19e-7`, so at `i = 180 deg` the absolute spacing is
   `1.5e-5 deg` — below the archive's own `1e-4 deg` quantum everywhere in the
   range. float32 storage therefore loses nothing the archive had not already
   lost; this is asserted here so that a test can be required to hold it.
3. **`e` is also a matching factor.** Prereg 6.3 bands windows by median
   eccentricity, and S2 analyses eccentricity. The band is a *level* and the
   periodogram is a property of the detrended *variation*, so this is not
   circular — but it is stated, because the two are not independent in general.
4. **The annual SRP term is out of band and cannot be removed** (section 4.1).
   S2's band-top is expected to be shoulder-dominated and no S2 excess above
   ~160 d may be read as a line.
5. **Near-equatorial inclination magnitude is a non-negative quantity.** For an
   object whose inclination vector passes near the origin, `|i|` has a V, which
   is not a sinusoid and is not a polynomial. It is slow (53-year class), so it
   lands at the band's low end with the other shoulder power, and it is present
   in the passive class more than the payload class — a confound whose direction
   is *against* finding a payload excess, i.e. conservative for the headline.
6. **No synchrony, phase or cross-channel claim is licensed.** Prereg 8.4 forbids
   a "significant in at least one channel" statistic, and
   `docs/synchrony-design-20260921.md` is a DRAFT design, not a registration.
   The section 4.3 P4 corroboration is a *descriptive* comparison of two line
   profiles and carries no joint statistic.

## 8. Stop rules

- Seed **20260921** is unchanged; the calibration/audit split is the identical
  object hash, so an object is in the same half for every channel.
- **One measurement pass** for S1 and S2 together. A pass that fails technically
  may be re-run; a pass that completes and produces an unwelcome number may not.
- **No threshold in shipped code changes on this registration's evidence**
  (prereg 11). S1/S2 write documentation and dated artifacts only.
- **T3 does not touch T1's or T2's files**, and `pipeline/*` and
  `tools/paperb_strata.py` are imported, never edited.
- Gates A/B/C are **not** evaluated for S1 or S2 (prereg 3.2). Their shapes may
  be printed as descriptive context and must carry that word.

## 9. Deliverables

1. This supplementary registration, committed **alone**, ahead of every S1/S2
   artifact.
2. `docs/cadence-s1-results-20260922.jsonl` and
   `docs/cadence-s2-results-20260922.jsonl` — one row per object per channel,
   the same schema the primary produced, with their `-receipt.json` companions.
3. `docs/cadence-s1-lines-20260922.json` and
   `docs/cadence-s2-lines-20260922.json` — the descriptive pooled line profiles.
4. `docs/cadence-s1s2-geo-20260922.json` — the GEO-restricted profiles, the D1
   evaluation, the resolution diagnostic of section 6, and the derivations of
   sections 3 and 4 recomputed in code so every number above has a machine
   witness.
5. `docs/cadence-s1s2-results-20260922.md` — the report, every number carrying
   inline `<!-- src: -->` provenance, with S1 and S2 in tables separate from the
   primary, the D1 verdict in the registered words, the blind spots of section 7
   restated as measured or unmeasured, and the fallback-rung exposure line that
   prereg 6.4 requires every time these numbers are quoted.
6. Offline tests for any new code, leaving `python3 -m unittest discover -s tests
   -p 'test_orbit*.py'` green against its 681-test baseline.

## Commit references

- `1a51afe` — the T3 pre-registration this document supplements, committed alone
  before any T3 code or number existed.
- `1ac5050` — the T3 implementation and its 51 offline tests, including the
  per-channel quantum table and the three-channel extractor this document's
  section 0 and section 6 rely on.
- `da957ba` — the primary-channel results, whose section 8 records S1 and S2 as
  **unexercised** in those words, and whose sections 5.3 and 5.4 set the
  headline question and the same-regime-control requirement of section 5.2.
- `ec89303` — the research-programme runbook that assigns T3.
- `f317a28`, `7626c55` — Paper B's registration and its pooled-floor transfer
  finding, the ancestor of prereg 6.3's matching.
