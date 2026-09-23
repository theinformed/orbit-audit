# BURN STRUCTURE

That is the verdict word of the registered decision rule in
`docs/harmonic-mechanism-preregistration-20260922.md` section 3.4, and the
family is named: **the carriers' second harmonic is inverted because their
drift-rate ramp runs the OTHER WAY — a one-burn sawtooth of the opposite sign,
not a burn pair, not archive smoothing, and not our pipeline.** The sign is a
property of the SLOT: the triaxial longitude acceleration changes sign every 90
degrees of longitude, so a fleet spread around the ring carries both directions,
and 53 of the 91 carriers that have one stable slot and a readable phase run one
way while 38 run the other.

> **THE MODEL IS NOT SMOOTHING IT.** That was the operator's question and it is
> answered three independent ways below — by an injection that comes back
> upright, by an upper bound on the archive's averaging span that is five times
> too small, and by the fact that smoothing is common to every object while the
> measured sign is not.

Written 2026-09-22. Registration `baea6f3`, committed **alone** 478 lines ahead
of any instrument or number; instrument `6bf0237` (42 tests), post-hoc time
domain `3349d84` (4 more), post-hoc slot arm `45f7408` (11 more). Data:
`docs/harmonic-mechanism-results-20260922.json`,
`docs/harmonic-mechanism-slots-20260922.json`.

---

## 0. The findings, in the order a reader should take them

1. **The floor is at zero and the ceiling is at 0.973.** Pure synthetic noise on
   the carriers' real epochs returns `R_2 = 0.005`; the same noise with a
   one-burn sawtooth injected at the design's derived amplitude returns
   `R_2 = 0.973` at a mean angle of `+0.00 rad`. The instrument has no `psi`
   bias of its own, and PREDICTION 0 — `psi_k = 0` for a one-burn sawtooth — is
   confirmed at every harmonic (section 2.1).
2. **Injected into the REAL passive series, the sawtooth comes back UPRIGHT.**
   `psi_2 = +0.02 rad` at `R_2 = 0.902`, 93% of the positive control's
   concentration, over 33,035 segments. **The pipeline does not invert anything**
   (section 2.2). The registered OBSERVABLE rule does not fire.
3. **The archive's effective averaging span is at most 2.16 days on the
   carriers**, against the 11.21-14.00 d that PREDICTION (a) derived as the only
   band in which a boxcar can flip `k = 2` while `k = 3` tracks. The smoothing
   hypothesis needs a span five times larger than the data admits, and the
   bound is an OVER-estimate by construction (section 2.5).
4. **Of ten candidate waveform families pushed through the identical pipeline,
   exactly one reproduces the measured `(pi, 0, pi, 0)` at all four
   harmonics**: the sign-flipped one-burn sawtooth, at `(3.13, -0.01, 3.14,
   0.01)`. Every two-burn split reset fails — as the registration derived in
   advance that it must, at every separation and every impulse ratio — and the
   symmetric triangle has no second harmonic to invert (section 2.3).
5. **The sign is PER OBJECT, which kills every common-cause explanation
   outright.** Of 208 carriers, 126 have a readable per-object `psi_2`: **43
   near 0, 68 near `pi`, 15 elsewhere.** The plain resultant of those angles is
   0.170 and the doubled-angle resultant is 0.852 — scattered on the circle,
   concentrated on the axis, which is what a two-mode population looks like. The
   same objects' `psi_3` is **unimodal: 84 near 0, ZERO near `pi`**, pooled
   resultant 0.932. An archive filter or a pipeline convention acts on every
   object identically and cannot do that (section 2.4).
6. **POST HOC, and it is the finding that settles it: the mode is a function of
   the slot.** Taking each carrier's mean geographic longitude from the
   archive's own angular elements, a single 180-degree-periodic sign function
   separates the two modes **91 out of 91 — accuracy 1.000**, against a
   permutation null whose median is 0.593 and whose maximum over 2,000 shuffles
   is 0.736 (exceedance 0/2000). The fitted turn-over longitudes are **73.0 E,
   163.0 E, 17.0 W, 107.0 W**; the accuracy is also **1.000 with NO free
   parameter at all**, using the published geostationary stationary longitude
   75.1 E (section 3).
7. **POST HOC, independently, in the time domain**: the skew of the differenced
   series — many small steps of the ramp, a few large ones of the reset — agrees
   with the phase-domain mode **111 times out of 111, with zero disagreements**.
   Every upright object's ramp falls and resets upward, which is design 1.1's
   case; every inverted object's ramp rises and resets downward (section 3.2).

**What this does to the design.** Design 1.1 wrote the drift acceleration as
`A = A_max |sin(2(lambda_slot - lambda_22))|` — with an absolute value — and
then derived a single waveform from it. The absolute value is where the sign
went. Roughly three fifths of the 14.00 d line's carriers fly the mirrored
cycle, so a template bank that fixes the harmonic phases to one sign is fighting
the majority of its own population. **That accounts for the prototype's
`-2.715 dB` of RESPONSE and for nothing else** — the T5a redesign measured, on
an independent instrument, that correcting the inverted harmonic is worth
`+1.9 dB` of response and **no separation at all, because the control gains
more**
<!-- src: docs/t5a-redesign-results-20260922.md, via docs/research-program-runbook-20260921.md T5a REDESIGN block -->.
A mechanism is not a detector, and this document does not claim it is one.

---

## 1. What ran, and what it cost

| | |
|---|---|
| arms | 34 registered (A, B, C, C2, D x 15, E x 10, F x 2, G, H x 2) + 2 post hoc |
| ladder | `L = 42 d`, 3.00 cycles, the one the rung-2 controls license <!-- src: docs/matched-filter-rung2-results-20260922.md section 3.3 --> |
| passive population | 331 same-shell geostationary passive objects, **33,035** admitted segments of 72,570 offered (36,443 rejected on sample count, 2,826 on span, 266 on gap) |
| carrier population | 208 east-west carriers, **25,658** admitted segments |
| slot arm | 91 carriers with one stable slot and a readable mode; 20 dropped as relocated, 97 with no readable mode |
| device | **none.** Host CPU, 8.2 minutes of arm time for the whole 34-arm sweep. Eleven frequency points per fit; claiming a card would have been theatre |
| seed | 20260922 throughout |

**Nothing here is inferential.** No p-value decides anything, no gate fires, no
object is relabelled. The one permutation test in the document exists to price a
single fitted parameter in a post-hoc arm and is reported as such.

**The pipeline is imported, not re-implemented.** Every segment comes from
`tools/matched_filter_phase.object_segments` and every phase from its
`fit_harmonics`; `tests/test_orbit_harmonic_mechanism.TestPipelineIdentity`
reads the instrument's own source and fails if either name is redefined there.
The strongest single check of that: arm G reproduces
`docs/matched-filter-rung2-results-20260922.md` section 3.4's published table
exactly — `R_2 = 0.084` at `pi`, `R_3 = 0.255` at 0, `R_4 = 0.051` at `pi`,
`R_5 = 0.116` at 0 — on a different code path, in a different module, written
after the registration.

---

## 2. The registered arms

### 2.1 Floor and ceiling, read first, as section 3.1 of the rung-2 results insists

| arm | `F_1` median | `R_2` / angle | `R_3` / angle | `R_4` / angle | `R_5` / angle |
|---|---:|---|---|---|---|
| **B** null floor — synthetic noise, no injection | 1.41 | 0.005 / — | 0.010 / — | 0.002 / — | 0.006 / — |
| **A** positive control — one-burn sawtooth into synthetic noise | 69.25 | **0.973 / +0.00** | **0.923 / -0.01** | **0.826 / -0.01** | **0.730 / +0.01** |

The floor's angles are not quoted because a resultant of 0.005 is not an angle;
the registration fixed that rule in section 3.3 before the run.

**PREDICTION 0 is confirmed.** A one-burn sawtooth has `psi_k = 0` at every
harmonic, the pipeline recovers it at 0 to within 0.01 rad, and the harmonic
concentration falls with `k` exactly as an amplitude of `1/k` against a fixed
noise floor requires. **The instrument has no phase bias to blame.**

### 2.2 Arm C — the decisive injection, and it comes back upright

| arm | `F_1` | `R_2` / angle | `R_3` / angle | `R_4` / angle | `R_5` / angle |
|---|---:|---|---|---|---|
| **C** one-burn into the REAL passive series, `3.3067e-5 rev/day` | 43.03 | **0.902 / +0.02** | 0.818 / -0.02 | 0.664 / -0.04 | 0.552 / +0.01 |
| **C2** the same at `1.85e-5 rev/day` (results 3.5 bracket) | 25.47 | **0.769 / +0.04** | 0.642 / -0.02 | 0.465 / -0.05 | 0.365 / +0.01 |

A waveform that is upright by construction, carried on real geostationary
element series with their real epochs, real gaps, real archive treatment and
real noise, is recovered upright to **0.02 rad** — against a registered
tolerance of 0.40 and a measured carrier value of `pi`. Halving the amplitude
changes the angle by 0.02 rad and nothing else. **The registered OBSERVABLE rule
requires arm A or arm C to return `pi`; both return 0, so it does not fire.**

**The limit of this arm, declared in the registration before it ran and repeated
here.** The injection is added to element values the archive has ALREADY
produced, so arm C tests our pipeline and NOT the archive's own fit smoothing.
Nothing in this section is offered as exonerating the archive. That is sections
2.5 and 2.4's work.

### 2.3 Arm E — ten families, one match

Each family injected into the same 331 passive objects at the same amplitude,
normalised to the sawtooth's own fundamental so that `R` is comparable across
rows.

| injected family | `psi_2` | `psi_3` | `psi_4` | `psi_5` | `R_2` | matches `(pi, 0, pi, 0)`? |
|---|---:|---:|---:|---:|---:|---|
| one-burn sawtooth (design 1.1) | +0.02 | -0.02 | -0.04 | +0.01 | 0.902 | no — this is the template |
| **sign-flipped one-burn** | **+3.13** | **-0.01** | **+3.14** | **+0.01** | **0.910** | **YES, at all four** |
| two-burn `s = 0.20`, `rho = 1` | +0.06 | -3.13 | +3.11 | -3.13 | 0.680 | no |
| two-burn `s = 0.30`, `rho = 1` | +3.10 | +3.13 | +3.12 | -2.69 | 0.708 | no — `k = 3` inverted |
| two-burn `s = 0.40`, `rho = 1` | -3.14 | +3.14 | -0.05 | -0.02 | 0.864 | no — `k = 3` inverted |
| two-burn `s = 0.50`, `rho = 1` | +3.12 | -3.11 | -0.04 | +0.05 | 0.320 | no — and `F_1 = 0.50`, the odd harmonics are gone |
| two-burn `s = 0.35`, `rho = 0.5` | -1.53 | -1.45 | -1.69 | -3.03 | 0.890 | no |
| two-burn `s = 0.50`, `rho = 0.5` | -0.01 | -0.02 | -0.04 | -0.02 | 0.851 | no |
| symmetric triangle | -0.39 | +3.13 | -2.03 | +0.05 | **0.056** | no — `R_2` is at the floor, there is no `k = 2` |
| bank sawtooth, duty 0.5 | +1.18 | +1.47 | +2.23 | +2.73 | 0.872 | no |
| bank sawtooth, duty 0.7 | +0.29 | +0.68 | +0.88 | +1.14 | 0.859 | no |

**PREDICTION (b2) is confirmed by measurement as well as by algebra.** The
registration derived, before any number existed, that no two-burn split reset at
any separation and any second-impulse size can put `psi_2` at `pi` while `psi_3`
stays at 0 — 0 of 5,940 scanned cells — and the eight two-burn arms run here
agree: every one that inverts `k = 2` also inverts `k = 3`. **"A burn pair" was
the first explanation the rung-2 results offered for this, and it is wrong.**

**PREDICTION (b3) is confirmed.** The triangle's `R_2 = 0.056` sits at eleven
times the floor's 0.005 only because a truncated triangle is not exactly
even-free on 42 d segments; against the positive control's 0.973 it is 6%, and
its mean angle is meaningless at that concentration. A triangle has no second
harmonic to invert.

**PREDICTION (b4) is confirmed, and it is the only family that is.** The
sign-flipped sawtooth reproduces the measured signature at all four harmonics
simultaneously, with no parameter fitted, at 94% of the positive control's
`R_2`, 87% of its `R_3`, 81% of its `R_4` and 74% of its `R_5`.

### 2.4 Arm G — the sign is PER OBJECT, and that is what closes the case

208 east-west carriers, no injection, `psi_k` computed per object across its own
25,658 segments. An object whose resultant falls below its own Rayleigh level
`3/sqrt(n)` is not given an angle at all.

| | `psi_2` | `psi_3` |
|---|---:|---:|
| readable objects | 126 of 208 | 104 of 208 |
| near 0 (within 0.40 rad) | **43** | **84** |
| near `pi` (within 0.40 rad) | **68** | **0** |
| elsewhere | 15 | 20 |
| plain resultant of the object angles | **0.170** | **0.932** |
| doubled-angle (axial) resultant | **0.852** | 0.804 |
| pooled angle | 3.121 (`pi`) | 6.185 (`-0.10`) |

Read the two columns against each other, because that is the whole argument.

**`psi_2` is bimodal**: a low plain resultant with a high doubled-angle
resultant is the signature of a population split between 0 and `pi` — scattered
on the circle, concentrated on the axis. The angle histogram is two piles and
almost nothing between them: 70 objects in the two bins adjoining `pi`, 45 in
the two adjoining 0, 11 spread over the remaining eight bins.

**`psi_3` is unimodal**: 84 objects near 0, **not one** near `pi`, plain
resultant 0.932. The same objects, the same segments, the same fit.

**No common cause can produce that pair.** An archive fit span applies to every
object; a pipeline convention applies to every object; an integration order
applies to every object. Any of them would move all 126 objects' `psi_2`
together, exactly as all 104 objects' `psi_3` moved together. The measurement
says `k = 2` splits the fleet in two and `k = 3` does not — which is precisely
what a per-object SIGN does, because negating a waveform shifts `psi_k` by
`pi(1 - k)`: `pi` at even `k`, nothing at odd `k`.

PREDICTION (b4-pop) also put a number on the split in advance: from the pooled
`R_2 = 0.084` against the ceiling's 0.532 it predicted a fraction
`p = 0.579` inverted. The per-object count gives **68 of 111 = 0.613**, and the
slot arm's stable-slot subset gives **53 of 91 = 0.582**. The prediction was
made before the count existed.

### 2.5 Arms D and H — the archive smoothing question, answered

**Arm D pushes an analytically boxcar-averaged sawtooth through the whole
pipeline at fifteen spans.** The derived transfer `H(nu) = sinc(nu W)` is
confirmed end to end, sign for sign:

| `W` (d) | `|H(f)|` derived | `psi_2` | `psi_3` | `psi_4` | `psi_5` | `R_2` |
|---:|---:|---:|---:|---:|---:|---:|
| 0 | 1.0000 | +0.02 | -0.02 | -0.04 | +0.01 | 0.901 |
| 3 | 0.9261 | +0.03 | -0.04 | -0.28 | +3.05 | 0.850 |
| 5 | 0.8029 | +0.06 | **-2.95** | -3.04 | +3.00 | 0.668 |
| 7 | 0.6365 | — | -3.10 | — | +0.17 | **0.065** (the `sinc` null at `W = P/2`) |
| 9 | 0.4459 | **+3.07** | -3.00 | -0.10 | +2.86 | 0.537 |
| 11 | 0.2523 | +3.09 | +0.06 | -2.96 | +2.90 | 0.446 |
| **12** | **0.1609** | **+3.11** | **+0.07** | **-3.06** | +0.10 | 0.322 |
| **13** | **0.0760** | **-3.07** | **+0.03** | **-3.09** | -0.11 | 0.180 |

Every sign change lands where the `sinc` puts it, including the exact collapse
of `R_2` to 0.065 at `W = 7 d = P/2`, where `sinc(2 f W) = sinc(1) = 0` and the
second harmonic is annihilated rather than inverted. **The registration's
PREDICTION (a) is therefore vindicated as physics: a boxcar CAN flip `k = 2`
while `k = 3` tracks, and only inside `[11.21, 14.00) d`.** Arm D reproduces the
full `(pi, 0, pi, 0)` at `W = 12` and `W = 13`, both inside that band, and
nowhere else on the ladder.

**And the price is exactly the one the registration named.** At `W = 12 d` the
injected fundamental's own amplitude is `0.1609` of the true one; at `W = 13 d`
it is `0.0760`. A smoothing that produces the measured signature destroys 84% to
92% of the fundamental's amplitude — and the fundamental is the thing that is
demonstrably there, at `F = 11.81` median and coherent over 568 days at a fixed
template and beyond 1,008 days per object
<!-- src: docs/matched-filter-rung2-results-20260922.md section 3.3 -->.

**Arm H measures the archive's effective averaging span and it is nowhere near
that band.** The roughness estimator `W_eff = dt / r^2` with
`r = RMS(diff x) / (sqrt(2) RMS(x))` inverts the autocovariance `1 - |tau|/W` of
boxcar-smoothed noise; it is proved against boxcar-smoothed white noise of known
width in `tests/test_orbit_harmonic_mechanism.TestRoughnessEstimator`, and
proved there to move UP, never down, when real smooth signal is added. It is an
upper bound.

| population | median element spacing | median roughness ratio | **`W_eff` upper bound** | fraction of segments inside the smoothing band |
|---|---:|---:|---:|---:|
| 208 east-west carriers | 0.63 d | 0.513 | **2.16 d** | 1.8% |
| 331 same-shell passives | 0.98 d | 0.216 | 16.66 d | 7.0% |

**The carriers are the population whose `k = 2` is inverted, and their upper
bound is 2.16 days — a fifth of the 11.21 d the smoothing hypothesis needs.**
The archive treats both classes with the same process, so the smaller of two
upper bounds binds, and the passive figure is an over-estimate for the obvious
reason: a passive object has no burns, so its mean-motion series is dominated by
genuinely smooth dynamics, which is exactly the inflation the estimator is built
to admit. Its own deciles run from 1.22 d to 70.1 d, which is the shape of a
statistic measuring real signal, not archive processing.

**SMOOTHING is refuted three times over**: the span is five times too small
(arm H); the signature is per-object while smoothing is common to every object
(arm G); and the band that could do it would take the fundamental with it (arm
D plus the measured coherence). The registered SMOOTHING rule requires all three
of arm C inverted-free, arm H inside the band, and arm D reproducing it; only
the third holds.

### 2.6 Arm F — the observable, closed

| injected | `psi_2` | `psi_3` | `psi_4` | derived prediction | matches? |
|---|---:|---:|---:|---|---|
| first integral of the sawtooth | **-1.53** | **+3.14** | **+1.59** | `(-pi/2, pi, +pi/2)` | the derivation is confirmed; the measurement is not matched |
| second integral | +3.11 | -0.06 | -3.11 | `(pi, 0, pi)` | phase matches |

The registration derived that a single integration or differentiation — the only
element-to-element confusions physically available between mean motion,
longitude and drift rate — puts `psi_3` at `pi`, and arm F measures exactly
that: `+3.14`. **The measured carriers have `psi_3 = -0.10`, so the observable
is not off by one order in either direction.**

Two integrations do match in phase, because the second integral of a sine is the
negated sine over `(2 pi k f)^2` — it IS a sign flip. It is separable by
amplitude and the registration said so in advance: `A_2/A_1` is `0.125` for two
integrations and `0.500` for a sign-flipped sawtooth. Arm F's `R_3 = 0.213`
against arm C's 0.818 and arm A's 0.923 is the `1/k^3` suppression showing.
There is in any case no physical route by which a twice-integrated drift rate is
recorded as a mean motion: one integration of `lambda_dot` is longitude, two is
not an element. **(c) is closed.**

---

## 3. POST HOC — not registered, and it is what makes the answer definitive

Both arms below are **outside** the registration, which was committed alone at
`baea6f3` before any instrument existed. They decide no verdict: section 4
evaluates the registered rule without them. They are here because the phase
algebra and the physical world should agree, and disagreement would have
mattered more than agreement does.

### 3.1 The mode is a function of the slot

Mean geographic longitude per carrier from the archive's own angular elements,
`lambda = Omega + omega + M - theta_GMST`, median over the object's history with
an interquartile-spread screen at 5 degrees so that a relocated object is never
given a single slot. 91 carriers have one stable slot and a readable `psi_2`
mode; 20 are dropped as relocated and 97 have no readable mode.

> **A single 180-degree-periodic sign function of longitude separates the two
> modes 91 times out of 91. Accuracy 1.000.**
>
> Permutation null, the same one-parameter maximisation on shuffled labels,
> 2,000 shuffles: median **0.593**, 95th percentile **0.648**, maximum
> **0.736**, exceedance **0 / 2000**.

The one fitted parameter puts the turn-over longitudes at **73.0 E, 163.0 E,
17.0 W and 107.0 W**. Those are the geostationary equilibria. And the parameter
turns out not to be needed at all:

> **At the published stationary longitude 75.1 E, with NO free parameter, the
> accuracy is also 1.000** — as it is at 74.9 E and at 75.3 E, so the result
> does not depend on which published value is used.

The closest object to a sector boundary sits 0.80 degrees from it and is still
classified correctly; the fifth percentile of the distance to a boundary is 8.3
degrees and the median is 28.4 degrees, so the separation is not a boundary
artefact. Median eccentricity across the 91 is `3.19e-4` and median inclination
0.046 degrees, which is where the mean-longitude approximation is good to better
than a tenth of a degree.

**This is the mechanism, stated physically.** The triaxial longitude
acceleration `d^2 lambda / dt^2 = -K sin(2(lambda - lambda_22))` points toward
the nearest stable longitude. A slot on one side of it has the drift rate
ramping down between burns and reset upward; a slot on the other side has the
drift rate ramping up and reset downward. The waveform is the same sawtooth with
the opposite sign, and negating a waveform inverts every even harmonic's phase
relation and leaves every odd one alone.

### 3.2 The time domain says the same thing, 111 times out of 111

A one-burn cycle spends most of a period ramping slowly one way and is reset by
one impulse the other way, so the differenced series is asymmetric: many small
steps carrying the ramp's sign, a few large ones carrying the reset's. Design
1.1's falling ramp therefore skews POSITIVE; a rising ramp skews NEGATIVE. This
reads the direction of the burn with no harmonic fit at all.

| | skew positive (falling ramp) | skew negative (rising ramp) |
|---|---:|---:|
| `psi_2` upright (design 1.1's sign) | **43** | 0 |
| `psi_2` inverted | 0 | **68** |

**111 agreements, 0 disagreements.** Every object whose second harmonic is
upright has a ramp that falls and a burn that pushes up; every object whose
second harmonic is inverted has a ramp that rises and a burn that pushes down.
Objects whose skew is inside two standard errors of zero are not read: none were.

---

## 4. The registered decision rule, evaluated

Section 3.4 of the registration, in order, using only registered arms.

1. **OBSERVABLE** — requires arm A or arm C to return `psi_2` within 0.40 rad of
   `pi` for an injected one-burn sawtooth. Arm A returns **+0.00**, arm C
   returns **+0.02**. **Does not fire.**
2. **SMOOTHING** — requires all three of: arm C within 0.40 of 0 (**holds**,
   +0.02); arm H's upper bound inside `[11.21, 14.00]` or `[25.21, 28.00]` d
   (**fails** — 2.16 d on the carriers); arm D reproducing `(pi, 0, pi, 0)`
   inside the band (**holds**, at `W = 12` and 13). Two of three. **Does not
   fire.**
3. **BURN STRUCTURE** — requires arm C within 0.40 of 0 (**holds**), arm H's
   bound excluding the band (**holds**), and arm E naming a family matching
   `(pi, 0, pi, 0)` within 0.40 rad at all four harmonics (**holds** — the
   sign-flipped one-burn sawtooth at `(3.13, -0.01, 3.14, 0.01)`, every `R_k`
   above the registered quarter of the positive control: 0.94, 0.87, 0.81,
   0.74). The rule's additional clause is met as well: arm G returns a bimodal
   per-object `psi_2` with both modes populated far above the floor, so **the
   sign is a per-object property**. **FIRES.**
4. **UNRESOLVED** — not reached.

> **VERDICT: BURN STRUCTURE.** The family is the one-burn sawtooth of design 1.1
> with the opposite sign, and the sign is set per object by the slot's side of
> its triaxial equilibrium.

**One word of care about the verdict word.** "Burn structure" here does NOT mean
a burn pair — the registration refuted that family in advance and arm E refuted
it in measurement. It means the structure of the single-burn cycle: which way
the ramp runs and which way the impulse pushes. A reader who prefers to call
that a sign convention is describing how it SHOWS UP in a filter that carries a
non-negative amplitude; arms A and C establish that it is not a convention in
OUR code, and section 3.1 establishes that it is a property of the sky.

---

## 5. What this changes, and what it does not

**For the prescribed statistic.** Section 3.6 of the rung-2 results prescribed
"the `k = 2` relative phase treated as a FREE parameter rather than fixed by the
sawtooth, because the data put it at `pi`". That prescription is correct and now
has a mechanism, and it can be sharpened: the free parameter is not continuous,
it is a **per-object SIGN**, `+1` or `-1`, and it is PREDICTABLE from the slot
longitude at 91 of 91 on the stable-slot set. A filter that carries a two-valued
sign — or equivalently a sign-free amplitude — recovers the full harmonic
structure of both halves of the fleet instead of fighting three fifths of it.
**No such filter is built in this document and none is registered here.**

**And the redesign's cross-check, which limits all of it.** The T5a redesign
(`ab4fee9`, `e3b9d5c`) measured independently that an inverted even harmonic is
invisible to a matched filter allowed a NEGATIVE amplitude, so the free `k = 2`
phase buys response and not separation. Both statements are true at once and
they are about different things: the redesign measured what a detector gains
from knowing the sign, which is nothing, and this document measures what the
sign IS, which is the slot. The value here is explanatory and diagnostic — the
14.00 d line's carriers are now known to fly two mirrored versions of one
cycle — and it should not be re-sold as a detection improvement, because the
measurement that would license that has been made and came back negative.

**For the design.** `docs/matched-filter-design-20260922.md` section 1.1's
`A = A_max |sin(2(lambda_slot - lambda_22))|` needs its absolute value removed
and the sign carried forward, and section 1.3 gains a fourth consequence: the
line's carriers come in two sign classes whose boundary is the triaxial
equilibrium. Section 2's template family needs no new member — the member it
needs is the one it has, with a sign.

**What remains UNPROVEN, in that word.**

1. **The slot arm is POST HOC.** It was not registered and no verdict rests on
   it. A registered replication on an independent object set is owed before it
   is quoted as a measurement rather than as a demonstration.
2. **The 97 carriers with no readable per-object `psi_2` are not accounted
   for.** They are 47% of the fleet. Nothing here says their sign is
   distributed like the readable half's, and a selection effect toward objects
   with strong harmonics is plausible and unmeasured.
3. **The archive's fit span is BOUNDED, not measured.** Arm H gives an upper
   bound of 2.16 d on the carriers. The programme still has no measurement of
   the actual fit span, and no citation for it is asserted anywhere in this
   document.
4. **The `k = 4` and `k = 5` harmonics remain below the archive's noise for a
   perfect sawtooth at the design's amplitude**, as the rung-2 results measured;
   their agreement here is read from arms in which the amplitude was injected,
   not from the carriers.
5. **The sector fit is a sign function, not a dynamical model.** A single
   `sin(2 lambda)` cannot reproduce the real geopotential's four equilibria
   exactly — the published ones are not 90 degrees apart — and the perfect
   accuracy owes something to no carrier in this set sitting in the few degrees
   where the models differ.
6. **Recall remains UNMEASURED**, as it is everywhere in this programme, and
   the element weights remain the screen design 3.3 declares.
7. **This is not T5a.** There is still no `docs/t5a-preregistration-<date>.md`
   of the kind design section 12 sketches; this is a mechanism measurement taken
   so that one can be written with the mechanism in hand.

---

## 6. Deviations from the registration, each named

1. **The smoothing band's edges are exact, not gridded.** The registration
   quoted `[11.205, 14.000)` and `[25.205, 28.000)` from a 0.005 d scan at
   `P = 14.00 d`. The exact edges are `4P/5` and `P`, and `9P/5` and `2P`,
   i.e. 11.200 and 25.200 d — the binding constraint is the `k = 5` sign change
   at `5W/P = 4` and `= 9`. The difference is 0.005 d, it changes no verdict,
   and `tests/test_orbit_harmonic_mechanism` asserts both the enumeration and
   the agreement.
2. **The synthetic arms' noise scale was not fixed by the registration.** It
   says "pure synthetic Gaussian noise carried on the passive objects' REAL
   epochs" without naming `sigma`. The implementation uses each object's own
   robust white-noise scale, `MAD(diff) x 1.4826 / sqrt(2)`, so that arms A and
   B sit at the same signal-to-noise as arm C. Any other choice would move the
   `R_k` values of arms A and B and none of the angles.
3. **Two post-hoc arms were added** (sections 3.1 and 3.2), both labelled in the
   code, in the emitted JSON field and here. Neither enters section 4.
4. **A pre-run exposure probe was run before the registration was committed**:
   object count, element-set count, segment count at `L = 42 d` and the fitting
   wall clock for one arm. No estimand was computed. It is named here because
   the registration did not name it.
5. **The run was executed twice.** The first execution predates commit
   `3349d84`, which added the post-hoc skew field; the second is the one
   reported and is the one the committed JSON holds. Both are deterministic
   under seed 20260922 and every registered number is identical between them.
6. **No GPU was used**, as the registration said would be the case.
