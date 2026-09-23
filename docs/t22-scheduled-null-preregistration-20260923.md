# Pre-registration — T22: the physics-scheduled null for GEO east-west keeping

**Date:** 2026-09-23. **Track:** T22 of `docs/research-program-runbook-20260921.md`
(HYPOTHESIS SLATE, conductor 2026-09-23). **Host:** `pc`, CPU only. **Seed:**
20260923 throughout.

**This document is committed ALONE, before any instrument exists and before any
number of this track has been computed.** The only thing that has been run
beforehand is the exposure probe of §9.1, declared there, which computed counts
and spacings and no estimand; and a reproduction of an already-committed
instrument's output, declared in §1.2.

---

## 0. What this track is, and the one thing it is not

The programme's certainty doctrine names, as the cheapest and largest lever,
**different data that shrinks the routine null**
<!-- src: docs/research-program-runbook-20260921.md, HOW CERTAINTY IS BOUGHT, item 1 -->.
This track builds that lever out of physics rather than out of a filing: if the
epoch of the next east-west station-keeping burn is **predictable from measured
dynamics**, then a burn that arrives on that schedule is routine BY
CONSTRUCTION, and only the burns that do not arrive on it are candidates for
anything else.

**What it is not.** It is not a detector, it is not an alert, and it is not a
statement about what any operator did. Every burn in this study is **a detected
drift-rate change**, which is another instrument's output on element sets and
never a record of an operator's action — T13's sentence, carried here verbatim
because it binds every number below:

> *Every agreement figure is agreement between rule sets. Each label class is
> another instrument's output on the same element sets, not a record of what an
> operator did. Agreement is not accuracy, not validation and not a detection
> rate, and nothing downstream may call it one.*
> <!-- src: docs/manoeuvre-library-results-v2-20260922.md, READ THIS BEFORE ANY NUMBER -->

**And it is not blind.** The deadband half-width this predictor uses, the
acceleration constant, the slot-sign rule and the burn population were all
measured and published before this registration was written. Nothing here is an
out-of-sample measurement of any of them. What IS new, and what this
registration fixes in advance, is the **joint** claim: that those quantities,
combined through the parabolic cycle, place the next burn in time.

---

## 1. Inputs, pinned

### 1.1 Physical constants, cited not assumed

| symbol | value | where it comes from |
|---|---:|---|
| `A` | `1.7006955627927864e-3` deg/day² | `tools/proximity_geo.py` `LAMBDA_DDOT_MAX`, derived in that module from `J22 = 1.8155e-6`, `mu`, `R_e`, `a_GEO`, `omega_E` as `3 omega_E A_t,max / v_GEO` with `A_t,max = 6 J22 (mu/a^2)(R_e/a)^2`. **Imported, never retyped**; a test asserts the identity of the imported name |
| `lambda_s` | `75.1 E`, `104.7 W` | `tools/proximity_geo.py` `STABLE_LONGITUDES_DEG` |
| `acc(lambda)` | `-A sin 2(lambda - lambda_s)` | `tools/geo_passive_control.py` `free_acceleration`, imported |
| `D` | `0.02633 deg` | the registered primary of `docs/t10c-cycle-deadband-v2-results-20260922.md` §2, bootstrap 95% `[0.02572, 0.02667]`, systematic range `0.025 to 0.033` |
| `sigma_lambda` | `0.0066540706667427025 deg` | the same document §1, the second-difference MAD on mean longitude over 1,858 segments |
| `sigma_n` | `6.038533519066339e-4` deg/day | the committed T8a events file's provenance record, reused by T8d and T13 and **recalibrated nowhere** |
| `MERGE_DAYS` | `5.0` d | `tools/trigger_alarm.py`, `= proximity_geo.MAX_GAP_DAYS`; the registered rule that consecutive flags within it are ONE trigger |
| `BURN_BASELINE_SAMPLES` | `10` | `tools/proximity_geo.py`, the detector's own baseline window length |

### 1.2 Data, pinned

| input | pin |
|---|---|
| near-GEO element extract | `runtime/proximity-geo/near-geo.npz`, sha256 `ff19d32e…`, the 217,007,154-row snapshot T8a, T8d and T13 measured on (11,626,494 rows kept, 1,768 objects) |
| burn types | the T13 **v2** arm-G ledger, `rulesSha256` `e2e0cbbdeb50a09c37bbf84131e9dc4b9aa4e8d3b57aa46fbe0343a9ea5cba52` |
| carrier roster | `docs/matched-filter-devset-20260922.json` `eastWestCarriers`, 208 objects |
| passive roster | the same file's `sameShellGeoPassiveControl`, 331 objects |
| alarm replay (E5) | `/home/sdegan/alarm-lane-work/alarm-lane-replay-everything-ledger.jsonl`, model `trigger-time-taxonomy/20260922/1`, checksum `9cf012aa…`, and the committed receipt `docs/alarm-lane-replay-20260922-receipt.json` |

**Declared beforehand (V1).** The T13 v2 arm-G ledger was **regenerated** on
this host before this registration was written, because the full table was not
kept. It is a reproduction of a committed instrument at a pinned rule hash, not
a measurement: the regenerated artifact's arm-G block must equal the committed
`docs/manoeuvre-library-v2-20260922.json` arm-G block field for field, and the
run asserts that equality and records it. No estimand of this track was
computed from it before this document was committed.

### 1.3 Policy

Angles and times only. No delta-v, propellant, Isp, mass or lifetime quantity
is computed for any object. No registry code, no ownership, no purpose, motive
or intent vocabulary anywhere in the instrument, its output or this document. A
test walks the instrument's source for both lists, importing the banned
vocabulary from the existing suite rather than copying it.

---

## 2. The predictor, derived

### 2.1 The cycle equation

At geostationary altitude the tesseral term drives a longitude acceleration
toward the nearer stable longitude,

    (1)   d^2 lambda / dt^2  =  acc(lambda)  =  -A sin 2(lambda - lambda_s).

Over one keeping cycle the object moves at most `2D = 0.0527 deg`, so the
argument of the sine moves by at most `0.105 deg` and the relative change in
`acc` is

    (2)   |delta acc / acc|  =  2 |cot 2u| * (2D) * pi/180,   u = lambda - lambda_s,

which is `5.1e-3` at `u = 10 deg` and `5.3e-2` at `u = 1 deg`. **Constant
acceleration over one cycle is therefore good to better than 1% everywhere
except within a couple of degrees of an equilibrium**, and §3.4 screens those
objects out in advance rather than discovering them afterwards. Equation (2) is
a derivation, not an assumption, and a test asserts it against a numerical
integration.

### 2.2 The burn epoch

Write `a = acc(lambda_c)`, constant over the cycle by (2). After a burn at
`t_n` leaving the object at longitude `lambda_n` with drift rate `lambdadot_n`,

    (3)   lambda(tau)  =  lambda_n  +  lambdadot_n tau  +  (1/2) a tau^2.

The band is `[lambda_c - D, lambda_c + D]`. The next burn is required at the
first exit from the band, so for each edge `lambda_e` solve

    (1/2) a tau^2 + lambdadot_n tau + (lambda_n - lambda_e) = 0

    (4)   tau  =  [ -lambdadot_n  +/-  sqrt( lambdadot_n^2 + 2 a (lambda_e - lambda_n) ) ] / a

and take

    tau*  =  min over both edges of the real, strictly positive roots,
    t_pred  =  t_n + tau*.

Equation (4) is the whole predictor. Two closed forms follow from it and are
asserted offline by test:

**(a) A burn at the exit edge.** If `lambda_n = lambda_e` (the operator burns
when the object reaches the edge it is being pushed toward), then
`Delta = 0`, the square root is `|lambdadot_n|`, and

    (5)   tau*  =  2 |lambdadot_n| / |a|.

**(b) The optimal one-burn cycle.** If in addition the burn is sized so the
parabola's apex just touches the far edge, `lambdadot_n^2 = 2|a|(2D)`, so
`|lambdadot_n| = 2 sqrt(|a| D)` and

    (6)   tau*  =  4 sqrt( D / |a| ).

### 2.3 A consequence, derived before the run

Equation (6) at `D = 0.02633 deg` gives **15.74 d** at `|a| = A` and **22.26 d**
at `|a| = A/2`. Inverting it, a **14.00 d** cycle requires

    |a|  =  16 D / T^2  =  16 * 0.02633 / 196  =  2.149e-3 deg/day^2,

which is **1.26 times A** and therefore **unreachable at any longitude**.

> **REGISTERED CONSEQUENCE C3.** The 14.00-day east-west line of T3 cannot be
> the optimal one-burn cycle of a `+/-0.02633 deg` band at any slot on this
> triaxial model. One of the three must give: the flown band is narrower than
> the flown-excursion box measured on these carriers, or the cycle is not the
> optimal one-burn cycle, or `A` is low. This is arithmetic on already-published
> numbers and it is written down here, before the run, because it predicts the
> direction of the first failure: **the physics-scheduled interval of (6) will
> run LONGER than the observed inter-burn interval.** The run reports the median
> ratio `tau* / observed interval` whatever it shows.

**Equation (5), not (6), is the predictor** — the run uses the MEASURED
post-burn drift rate, not the optimal one — precisely so that a narrower flown
band is absorbed by the measurement instead of biasing the prediction. `D`
enters only through `Delta = lambda_e - lambda_n`, i.e. only to the extent the
burn is not at the exit edge. This is stated so no reader mistakes (6) for what
is being tested.

### 2.4 The quantities measured per burn, and their uncertainties

Let `t_trig` be the closing flag of the burn's chain (§3.1). Over the **first
`BURN_BASELINE_SAMPLES = 10` element sets at or after `t_trig`** — the
detector's own window length, imported and not picked — the instrument fits two
straight lines by ordinary least squares in `tau = t - t_trig`:

* on `series.drift` (the mean-motion channel, `360 n - omega_E`):
  intercept `lambdadot_n`, slope `a_fit`, with `sigma(lambdadot_n)` and
  `sigma(a_fit)` from the fit covariance scaled by the fit's own residual
  variance;
* on `series.lam_unwrapped`: intercept `lambda_n`, with `sigma(lambda_n)` from
  its residuals.

| quantity | how measured | uncertainty |
|---|---|---|
| `lambdadot_n` | intercept of the drift fit at `t_trig` | fit `sigma`, per burn |
| `lambda_n` | intercept of the longitude fit at `t_trig` | fit `sigma`, per burn |
| `lambda_c` | circular median of `series.lam_unwrapped` over `[t_n - 45 d, t_n + 45 d]`, local so a relocation cannot poison it | `1.253 sigma_lambda / sqrt(m)` over the `m` samples in the window |
| `a` | `acc(lambda_c)` from (1), **derived, not fitted** — this is the physics arm | `sigma_a`, MEASURED in pass 1, below |
| `D` | `0.02633 deg` | `sigma_D = (0.033 - 0.025) / (2 * 1.96) = 2.04e-3 deg`, i.e. T10c's own published systematic range read as a 95% interval. The `+/-2%` bootstrap interval is NOT used, because that document says in its own words that the statistical interval is not the uncertainty |
| `t_{n+1}` observed | the next chain's `tFirst` | `sigma_obs = s / sqrt(12)`, `s` = that object's median element spacing, the uniform-quantisation `sigma` of an epoch known only to the element that revealed it |

**`sigma_a` is measured, not assumed — PASS 1.** The run makes one pass over
every admitted arc and forms `a_fit - a_derived`. `sigma_a` is the robust
scatter `1.4826 * MAD` of that difference, pooled over the carrier arm.
**Pass 1 computes no estimand of §3**: no prediction, no tolerance, no
on-schedule fraction, no odds ratio, no precision. Its outputs are `sigma_a` and
the E0 diagnostics, and the ratio `a_fit / a_derived` is reported whatever it
shows.

### 2.5 Propagation, and the tolerance that follows from it

With `s = sign(a)`, `Delta = lambda_e - lambda_n` at the selected edge and
`Q = sqrt(lambdadot_n^2 + 2 a Delta)`:

    (7)   d tau*/d lambdadot_n  =  ( -1 + s lambdadot_n / Q ) / a
    (8)   d tau*/d lambda_n     =  -s / Q
    (9)   d tau*/d lambda_c     =  +s / Q
    (10)  d tau*/d D            =  +1 / Q
    (11)  d tau*/d a            =  s Delta / (Q a)  -  tau* / a

and, treating the five as independent,

    (12)  sigma_tau^2  =  sum over x of ( d tau*/d x )^2 sigma_x^2.

At the exit edge (`Delta = 0`, `Q = |lambdadot_n|`) these reduce to
`|d tau*/d lambdadot_n| = 2/|a|` and `|d tau*/d a| = tau*/|a|`, so the
acceleration term is relative and the drift term is not — which is why `sigma_a`
must be measured rather than guessed.

**The tolerance is derived, not picked:**

    (13)  w_n  =  2 * sqrt( sigma_tau,n^2 + sigma_obs,n^2 ).

Two standard deviations, two-sided, i.e. nominal 95% coverage under a normal
error. There is no floor, no minimum, no rounding and no grid. `w_n` is
**per burn** and its distribution over the admitted population is reported with
the headline.

**A registered check on (12), MC1.** A Monte-Carlo propagation of (4) — 2,000
draws of the five inputs at their `sigma`, seed 20260923 — must agree with (12)
to within 10% at the median of the admitted population. Asserted offline on a
fixture by test, and reported on the real population as a diagnostic. If it
disagrees by more than 10% on the real population, the Monte-Carlo `sigma` is
the one used for (13) and the deviation is declared; the linearisation is never
silently kept.

**A registered defect rule, W1.** If the median `w_n` exceeds one third of the
median observed inter-burn interval on the same arm, **the first paragraph of
the results document must say so in those words**, because a window that wide
makes the raw on-schedule fraction a statement about the window and not about
the physics. The verdict is then carried entirely by the null of E1b.

---

## 3. Population, units and estimands

### 3.1 The unit of analysis

* **Burns** are the **flag chains** of T8d — `trigger_alarm.flag_baselines`
  followed by `trigger_alarm.chain_flags` at `MERGE_DAYS = 5.0`, at
  `sigma_n = 6.038533519066339e-4`, **imported and not reimplemented**; a test
  reads the instrument's source and fails if either name is redefined in it.
  A chain opens at `tFirst` and closes at `tTrig`.
* **A chain's type** is the T13 v2 type of the arm-G burn whose `epochMs`
  equals the chain's `tTrig` exactly. Both come from the same flag epochs of
  `proximity_geo.drift_change_flags`, so the match is an identity and not a
  tolerance; where no row exists the chain is typed `unmatched` and counted.
* **A pair** is two consecutive chains `(n, n+1)` on one object. It is
  **admitted** when every screen of §3.4 passes.
* **On-schedule** means `|t_{n+1} - t_pred| <= w_n`, with `t_{n+1}` the next
  chain's `tFirst` and `w_n` from (13).

### 3.2 Populations

| arm | roster | what it is |
|---|---|---|
| **carrier** | the 208 `eastWestCarriers` | T3's 14.00-day east-west line carriers |
| **passive** | the 331 `sameShellGeoPassiveControl` | same-shell geostationary passive objects. **Not a burn-free population**: the runbook's own T8e line says no passive control exists at GEO because slow librators dwell like keepers, and §9.1's probe measured 47,571 chains on 239 of them |

### 3.3 The estimands

**E0 — the derived acceleration against the measured one** (a measurement, gates
nothing). Median and robust scatter of `a_fit / a_derived` per arc and per
object, both arms; the same for `a_fit - a_derived`, whose scatter is `sigma_a`.

**E1 — the on-schedule fraction (PRIMARY).** Over admitted carrier pairs whose
chain `n` is typed `east-west keeping`: the fraction on-schedule, pooled, with a
Wilson 95% interval, and per object with the per-object distribution reported.

**E1b — the random-phase null, which prices the window.** Two nulls, both at the
same `w_n`, seed 20260923, 1,000 draws each:

* **N1 (registered primary null):** replace `tau*` by a draw from the pooled
  empirical distribution of OBSERVED inter-chain intervals on the same arm.
* **N2:** shuffle `tau*` among the admitted pairs of the same object.

Report each null's median and 95th percentile of the on-schedule fraction.

**E2 — the passive leak, with exposure printed.** The identical chain on the
passive arm.

* **E2a:** the pooled `D`, as-is.
* **E2b (the fair comparison):** restricted to passive pairs whose `tau*` lies
  inside the carriers' admitted interquartile range of `tau*`, so the two arms
  are compared at matched predicted horizons.

Exposure printed beside both: objects with a series, element sets, object-days,
chains, admitted pairs.

**E3 — the enrichment of off-schedule burns.** Over admitted carrier pairs, the
odds ratio that chain `n+1` carries a relocation-associated type, off-schedule
against on-schedule.

* **primary type:** `drift start` — the only one of them carrying a usable
  agreement figure, `0.643 [0.581, 0.701]` against T8a initiating flags.
* **secondary union:** `{drift start, drift stop, station acquisition}`. Both
  of the two added types carry a sentence that travels with them and is printed
  in the results: `drift stop` **carries Gate F** wherever it is printed; and
  `station acquisition`'s `0.751` is **a mapping corrected to match a measured
  outcome and may not be scored as a successful prediction**.
* 95% interval from the log-odds standard error, with a Haldane-Anscombe 0.5
  added to every cell if any cell is zero, declared when applied.

**E4 — the sign test against the slot side.** A burn that holds a slot must push
the drift rate AGAINST the triaxial acceleration, so the registered rule is

    (14)   sign( driftChange )  =  -sign( acc(lambda_c) )  =  sign( A sin 2(lambda_c - lambda_s) ).

Report the fraction obeying (14): on carriers, on passives, and split by
on-schedule against off-schedule. **The false rate on passives is defined as the
fraction of passive chains that PASS (14)**, and it is reported with its Wilson
interval.

> **REGISTERED PREDICTION P-SIGN.** A passive object has no control loop, so a
> flagged drift change on one is the acceleration's own work and carries
> `sign(Delta lambdadot) = sign(a)`, which FAILS (14). The passive pass-fraction
> is therefore predicted to be **at or below 0.5**, and materially below the
> carriers'. A passive fraction at or above the carriers' refutes the sign test
> as a discriminator and must be reported as such.

**E5 — the alarm lane's class-1 precision, re-scored.** Registered HERE, up
front, so that it is not a post-registration reading. On the committed 2010s
replay at the `everything` operating point, class 1 (the spoken class) measured
**14 / 272 = 5.147%, Wilson [3.090%, 8.453%]**. Join each spoken class-1
assessment to a chain on `(norad, tTrigMs)` exactly. Remove from the DENOMINATOR
every spoken alert whose chain is on-schedule by E1's rule, and from the
NUMERATOR every arrival whose alert was so removed. Report `before -> after`
with both Wilson intervals, the number removed, the number of removed alerts
that were hits, and the number of spoken alerts that could not be joined or
could not be scheduled (no admitted predecessor) — those stay in the
denominator, because an unjoined alert is a labelled gap and not an on-schedule
burn.

### 3.4 Screens, fixed in advance

A pair is admitted only if all hold. Each is a screen, not a law.

1. **`tFirst(n+1) > tTrig(n)`** and the gap `t_{n+1} - t_n` is finite.
2. **At least 10 element sets** at or after `t_trig(n)` and before
   `t_{n+1}`, so the two fits of §2.4 are defined on data that precedes the
   observed outcome. **Causality:** every quantity entering `t_pred` is a
   function of element sets at epochs `<= t_trig(n) + the fit window`, and the
   fit window is truncated at `t_{n+1}` so that no element set at or after the
   observed next burn can enter the prediction of it. A test asserts the
   truncation.
3. **No element-set gap longer than `MAX_GAP_DAYS = 5 d`** inside
   `[t_n, t_{n+1}]` — the archive's own registered gap rule.
4. **`|a| >= A sin(8 deg) = 0.1392 A`**, i.e. the slot is at least 4 degrees
   from an equilibrium. Below that, (2)'s constant-acceleration approximation
   degrades and `tau*` diverges. Objects screened here are counted and reported.
5. **`lambda_c` is defined** — at least 20 element sets in the +/-45 d window.
6. **`tau*` is finite and `tau* <= 365 d`**. A prediction beyond a year is not a
   schedule; those pairs are counted as `unpredictable` and reported, not
   silently dropped and not counted as off-schedule.
7. **The object is not relocating across the pair**: the interquartile spread of
   `series.lam_unwrapped` over `[t_n - 45 d, t_{n+1} + 45 d]` is at most
   `5.0 deg`, the same screen the slot arm of the harmonic track used. Counted.

Screens 6 and 7 are **outcome-blind in construction but not in effect** —
screen 7 reads element sets after `t_{n+1}`. It is therefore applied to the
population and the population is reported both with and without it; the primary
is WITH, and the difference is printed.

---

## 4. The decision rule, fixed before the numbers

**PASS — "physics schedules the routine"** requires ALL THREE:

* **P1** E1's pooled point estimate `>= 0.80`.
* **P2** E1's pooled Wilson LOWER bound exceeds the 95th percentile of null N1.
* **P3** E2b's passive Wilson UPPER bound is below E1's carrier Wilson LOWER
  bound.

**PARTIAL** if P2 and P3 hold and P1 fails: reported in the words *"the
schedule is measured and does not reach the registered 0.80 bar"*, with the
measured fraction as the headline.

**FAIL** if P2 fails: reported in the words *"the physics adds nothing over a
window of that width"*. This is the falsifier the slate names.

**FAIL** if P3 fails: reported in the words *"passives are on-schedule at the
same rate"*. The second falsifier the slate names.

**VOID — UNDERPOWERED** if fewer than 200 admitted carrier pairs or fewer than
50 admitted passive pairs at E2b. No fraction is read from fewer.

**E0, E3, E4, E5 gate nothing and are reported whatever they show.** No bar is
set on them and none may be invented after the numbers exist.

**No re-roll.** Every seed is fixed above. The instrument is run, and the first
value the registered procedure produces is the value published. A knob moved
after a number exists is a deviation and is declared on the face of the results.

---

## 5. Offline proofs required before any result document is written

`tests/test_scheduled_null.py`, no archive, no network:

1. **The algebra.** (4) reproduces (5) at `Delta = 0` and (6) for the optimal
   one-burn cycle, both signs of `a`, to 1e-9.
2. **(2) against a numerical integration** of (1): the constant-acceleration
   error over one cycle is within the bound (2) predicts.
3. **A synthetic sawtooth with a planted `A` and `D`** on real element epochs:
   the chain recovers the planted burn epochs and the on-schedule fraction is
   at least 0.95 at the derived tolerance. **This is the assert-the-bug test:**
   a predictor that ignored `lambdadot_n`, or that used (6) instead of (4),
   fails it, and the test asserts that too by construction.
4. **A librator produces no on-schedule prediction.** Free libration integrated
   with the existing `geo_passive_control` integrator, flagged by the same
   detector: the on-schedule fraction must not exceed the N1 null's 95th
   percentile on the same fixture.
5. **MC1**: the linear propagation (12) agrees with a 2,000-draw Monte Carlo
   within 10% on the fixture.
6. **Sign test** (14): the synthetic keeper passes at 1.00, the librator does
   not exceed 0.5 + its own Wilson half-width.
7. **Imported-identity guards**: `trigger_alarm.flag_baselines`,
   `trigger_alarm.chain_flags`, `proximity_geo.LAMBDA_DDOT_MAX`,
   `proximity_geo.STABLE_LONGITUDES_DEG` and
   `geo_passive_control.free_acceleration` are read from their modules and the
   test fails if any is redefined inside this instrument.
8. **Causality guard**: no element set at an epoch `>= t_{n+1}` enters any
   quantity of the prediction of `t_{n+1}`.
9. **Wilson and log-odds** against hand-computed values.
10. **Vocabulary guards**: no purpose, motive or intent word; no registry code
    read by any function; no tool or model name in the instrument, in the
    emitted JSON or in the ledger.
11. **Policy guard**: no delta-v, propellant, Isp, mass or lifetime quantity is
    computed anywhere.
12. **Nothing is written** to `src/`, `data/`, `public/` or `pipeline/`.

---

## 6. Compute

CPU on `pc`, one core, no GPU. **No `gpu-consumers.json` row is owed**, and the
results document will say so. Expected wall under 1,200 s; a stage measured
above that is reported, not hidden. Nothing is scheduled, no timer is installed,
nothing is deployed and nothing reaches any site surface. Disk before and after
is reported.

---

## 7. Deliverables

1. This registration, committed **alone**.
2. `tools/scheduled_null.py` + `tests/test_scheduled_null.py`, committed
   together, after this document.
3. `docs/t22-scheduled-null-results-20260923.md`,
   `docs/t22-scheduled-null-20260923.jsonl` (per-pair ledger, thinned if large
   with the thinning step recorded) and
   `docs/t22-scheduled-null-20260923-receipt.json`.
4. The T22 row in `docs/research-program-runbook-20260921.md`, after T21 if that
   heading exists by then and after T20 otherwise.
5. `docs/notebook/ORB-T22/2026-09-23-physics-scheduled-null.md`.

---

## 8. Blind spots, named before the measurement

1. **`D` is a flown-excursion box, not a licensed band.** T10c says so in its
   own words and this track inherits it. An operator flying inside a wider
   licence is measured at what it flies, and applying one pooled number to every
   carrier is a screen.
2. **`D` moves 28% across T10c's registered prominence sweep** (`0.02586` to
   `0.03316`). `sigma_D` of §2.4 covers that range by construction; it is not a
   claim that the range is resolved.
3. **The burn set is a detector's output.** Its recall is UNMEASURED, here as
   everywhere in this programme. A burn below the detector's floor is invisible
   and would appear as an off-schedule gap.
4. **The `east-west keeping` type has no burn-level agreement figure** — T13
   calls its cell a labelled gap, not a zero, and its object-level enrichment is
   `8.7x`, down from v1's `17.6x`. Every E1 figure inherits that.
5. **`80.0% of near-GEO burns are UNLABELLED` under T13 v2.** A chain typed
   `unmatched` or `UNLABELLED` is not evidence of anything and is counted, never
   folded into a type.
6. **The passive arm is not a clean control.** It carries as many flag chains as
   the carrier arm (§9.1). If it scores on-schedule at the carriers' rate, that
   is the registered FAIL of P3 and not a nuisance to be explained away.
7. **`a` is derived from a single `sin 2(lambda - lambda_s)` term.** The real
   geopotential has four equilibria that are not 90 degrees apart; the harmonic
   track said so and this track repeats it. Screen 4 keeps the population away
   from the region where that matters most, and does not remove the
   approximation.
8. **This is not a blind analysis.** Every constant was read before this
   registration was written. The only thing fixed in advance is the combination
   and the decision rule.
9. **`sigma_obs` treats the epoch quantisation as uniform**, which understates
   the error when an object's element cadence is irregular.
10. **E5 is in sample for the taxonomy**, as the replay receipt says of itself,
    and the re-scored figure inherits that exactly.

---

## 9. Deviations declared in advance

**V1 — the T13 v2 arm-G ledger was regenerated before this registration.**
§1.2. A reproduction of a committed instrument at a pinned rule hash; the
equality of the arm-G block is asserted by the run and recorded in the receipt.

**V2 — an exposure probe was run before this registration was committed.**
§9.1 below. It computed counts, element-set totals, object-day totals, median
element spacings and inter-chain gap quantiles on both rosters. **No estimand of
§3 was computed**: no prediction, no tolerance, no on-schedule fraction, no odds
ratio, no precision, no sign test. It is named here because the registration
would otherwise not name it.

### 9.1 What the probe measured

| | carrier arm | passive arm |
|---|---:|---:|
| roster | 208 | 331 |
| objects with a usable series | 207 | 239 |
| element sets | 1,841,245 | 1,623,047 |
| object-days | 1,555,008 | 2,376,162 |
| flag chains | 40,578 | 47,571 |
| objects with at least 3 chains | 207 | 212 |
| inter-chain gap, p25 / p50 / p75 (d) | 13.28 / 15.07 / 27.73 | 10.99 / 18.00 / 32.46 |

These are the exposure figures the power gate of §4 is read against, and the
median carrier inter-chain gap of **15.07 d** is the denominator the defect rule
W1 of §2.5 compares the derived window to.
