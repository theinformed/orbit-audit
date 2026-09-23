# T8a pre-registration: GEO approach events from longitude and drift rate

Registered 2026-09-22, **before any T8 approach event, count, lead time or
pair exists**. This document is committed alone, ahead of everything T8a will
ever produce, exactly the way `docs/cadence-preregistration-20260921.md` was
committed ahead of T3 and `docs/phase3-preregistration-20260921.md` ahead of
Phase 3. The git history of this file is the timestamp. Nothing below may be
changed once a T8a number exists; an awkward outcome is reported, not edited
away.

T8a is the pilot of track T8 of `docs/research-program-runbook-20260921.md`.
It registers what T8a estimates, on which objects, with which thresholds,
against which nulls, and what would make the pilot uninformative. It
implements nothing.

Two estate rules this document is written under, restated because they are the
reason most of what follows is derivation rather than assertion:

- **Physical assumptions are not facts — derive or cite every physical claim;
  thresholds are screens, not laws.**
- **The instrument is ownership-agnostic mathematics.** Catalogue country and
  object-type codes are carried as ordinary metadata columns on every event
  row so that later analysis is possible, and they enter **no** detector
  decision. Nothing in T8a's outputs may carry intent language — no
  inspection, spying, threat, adversary, hostile or shadowing vocabulary — and
  T8a produces no per-nation narrative. The attribution rule from the
  programme's earlier design holds unchanged: **the object whose elements
  changed is the approacher; facts, never intent.** Publication and site
  framing for this track is reserved to Sean and is not a T8a output. Results
  land in `docs/` only.
- The propulsion/fuel overlay stays commercial-civil-only. T8a therefore
  reports drift-rate changes in **deg/day and nothing else**; §2.5 derives the
  deg/day-to-tangential-ΔV constant once, as physics, and T8a computes no
  per-object ΔV or propellant figure for any object.

---

## 0. What was measured BEFORE this registration, and why it is not a result

Two pre-scans were run before this document was written. Both are disclosed in
full, because concealing a pre-scan is how a registration quietly becomes a
post-hoc rationalisation. Both are stated here as the exact code that produced
them so that each number is reproducible.

Neither pre-scan computed a longitude, a drift rate, a pair, a separation or
an event. Nothing in either could have been used to shop for a favourable
threshold, because every threshold below is derived in §2 from orbital
mechanics and from the archive's *sampling* pattern, never from its element
*values* — with the single exception flagged in §5.4, where a noise floor is
**calibrated** by a procedure registered here and run before any event is
formed.

### 0.1 Population sizing (element values read: three columns of one row per object)

For each of the 68,089 objects in `object_rollup`, the single most recent
element set was read and screened:

```sql
SELECT mean_motion_q, eccentricity_q, inclination_q
  FROM element_set WHERE norad = ? ORDER BY epoch_ms DESC LIMIT 1
```

| Screen on the most recent element set | Objects |
|---|---:|
| Archive objects with at least one element set | 68,089 |
| mean motion in [0.9, 1.1] rev/day | 1,871 |
| …and e < 0.01 and i < 15° | 1,601 |
| …and ≥ 100 element sets in the archive | 1,575 |
| mean motion in [0.9,1.1], e < 0.01, i < 25° (the §3.1 screen) | 1,626 |

This is population sizing — "how many objects are there" — and it is a
**lower bound only**, because an object that was near-GEO for years and has
since been re-orbited, decayed or lost its elements is not counted by a screen
on its last row. §3.1 screens per element set, not per object, and will find
more.

### 0.2 Sampling geometry for near-GEO objects (epochs only, no element values)

Every fifth object of the 1,626 (324 objects), all epochs read, **nothing but
`epoch_ms`**:

| Quantity | p5 | p25 | p50 | p75 | p95 |
|---|---:|---:|---:|---:|---:|
| Within-object median epoch spacing (d) | 0.357 | 0.469 | 0.865 | 0.997 | 1.019 |
| Element sets per object | 551 | 5,588 | 8,459 | 9,478 | 10,840 |
| Archive baseline per object (d) | 674 | 3,353 | 7,911 | 13,065 | 18,013 |

Fraction of objects with median spacing ≤ 1 d: **0.796**. ≤ 2 d: **0.997**.

The one fact this buys, and the only use made of it below: **the near-GEO
catalogue is re-fitted on a roughly daily rhythm, with a median object
observed 8,459 times over 21.7 years.** §2.7 derives the loiter sample-count
and gap requirements from this and from nothing else.

### 0.3 Archive-wide facts used for provenance only

183,352,638 element sets, epochs spanning 1959-01 to 2026-09, 68,089 objects
(`month_rollup`, `object_rollup`). A full sequential pass over `element_set`
reading three columns was timed at 1.04 M rows/s on `pc`, i.e. about 180 s for
the whole archive — which is why T8a is registered as a CPU study with no GPU
stage (§8).

---

## 1. What T8a is for (three declared uses, registered before the result)

1. **An event catalogue.** A dated, reproducible list of historical near-GEO
   approach events: object A moved in longitude and came to rest within X
   degrees of the mean longitude of object B, and stayed for at least D days.
   Facts about published orbital elements, with the provenance of each row
   recorded.
2. **A repetition measurement.** Whether individual objects produce *more than
   one* such event, and whether the shape of one event by a given object
   predicts the shape of the next. This is the scientific question: is there
   per-object behavioural structure, or is the catalogue a pile of
   independent coincidences?
3. **A lead-time measurement.** For each event, how many days elapsed between
   the initiating drift-rate change first becoming visible in the public
   element archive and the arrival within X degrees. This is the headline
   number of the whole T8 track: it bounds what an early-warning surface built
   on public elements could ever offer.

T8a is a **pilot**. Its verdict may be that the estimands are not measurable
at TLE quality, or that the null explains the catalogue. §10 registers what
each of those outcomes looks like, in advance.

### 1.1 What T8a is explicitly NOT

- **It is not a conjunction or miss-distance instrument.** The estimand is
  *mean longitude*, a slot-level quantity (§2.2). Two objects at the same mean
  longitude are routinely tens of kilometres apart and are deliberately kept
  so by eccentricity- and inclination-vector separation, which T8a does not
  model. A T8a event says two objects occupy the same longitude slot; it says
  nothing whatever about how close they physically passed. Miss distance is
  T8b's problem, not T8a's, and no T8a output may be read as a collision risk.
- It is not a manoeuvre detector in the Paper A/Paper B sense. It reuses none
  of that detector's thresholds and makes none of its claims.
- It covers the near-geostationary regime only (§3.1). Everything else is out
  of scope and is a declared blind spot (§9), not a negative result.

---

## 2. The physics, derived

Every constant used by T8a is derived here from WGS-84/IERS values
(μ = 398600.4418 km³/s², R_e = 6378.137 km) and the sidereal Earth rotation
rate ω_E = 360.9856473 deg/day = 7.2921158540e-5 rad/s. Numbers are quoted to
the precision the derivation supports.

### 2.1 The geostationary radius

n = sqrt(μ/a³); setting n = ω_E gives

&nbsp;&nbsp;&nbsp;&nbsp;`a_s = (μ / ω_E²)^(1/3) = 42164.1696 km` (35786.033 km above the
equatorial radius).

### 2.2 Mean longitude from TLE mean elements

For a Keplerian orbit the right ascension α of the satellite satisfies
`tan(α − Ω) = cos i · tan u`, with `u = ω + ν` the argument of latitude and ν
the true anomaly. Writing `α − Ω = u + δ` and linearising in δ:

&nbsp;&nbsp;&nbsp;&nbsp;`tan u + δ sec²u = cos i · tan u`
&nbsp;⇒&nbsp;`δ = (cos i − 1) sin u cos u = −(i²/4) sin 2u + O(i⁴)`.

And from the equation of the centre, `ν = M + 2e sin M + O(e²)`. So

&nbsp;&nbsp;&nbsp;&nbsp;`α = Ω + ω + M + 2e sin M − (i²/4) sin 2u + O(e², i⁴)`.

**Both correction terms are periodic with zero mean over an orbit.** The
quantity

&nbsp;&nbsp;&nbsp;&nbsp;**`λ ≡ Ω + ω + M − θ_G(t)`,&nbsp;&nbsp;wrapped to (−180°, +180°]**

is therefore the classical geostationary **mean longitude**: it carries no
eccentricity or inclination periodic content by construction, which is exactly
why T8a uses it rather than an instantaneous sub-satellite longitude. TLE
elements are already mean (Brouwer–Lyddane/Kozai) elements with short-period
terms removed, so no further averaging is applied. The consequence — that λ is
a slot coordinate and not a position — is registered in §1.1 and repeated in
the results document.

θ_G is Greenwich Mean Sidereal Time in the IAU-1982 formulation, which is the
rotation SGP4's TEME→pseudo-Earth-fixed conversion uses, and therefore the one
consistent with a TLE's Ω:

&nbsp;&nbsp;&nbsp;&nbsp;`θ_G [s] = 67310.54841 + (876600·3600 + 8640184.812866)·T + 0.093104·T² − 6.2e-6·T³`,

T in Julian centuries of UT1 from J2000.0, converted to degrees at 1/240 deg/s
and wrapped. Two approximations are made here and both are registered:
UT1 ≈ UTC (|UT1−UTC| < 0.9 s ⇒ < 0.0038° of longitude) and polar motion
neglected (< 0.5 arcsec ⇒ < 0.00014°). Both are more than two orders of
magnitude below the primary threshold of §4.

### 2.3 Drift rate, and its relation to semi-major axis

Drift rate is defined eastward-positive as

&nbsp;&nbsp;&nbsp;&nbsp;**`ḋ = 360·n − ω_E` deg/day**, n in rev/day,

which is the exact statement that a satellite's longitude advances at its own
mean motion while the Earth turns underneath at ω_E. Differentiating
n = sqrt(μ/a³) gives `dn/da = −3n/(2a)`, so near a_s

&nbsp;&nbsp;&nbsp;&nbsp;`dḋ/da = −(3/2)(ω_E/a_s) = −0.0128421 deg/day per km`,
equivalently `−77.8686 km per (deg/day)`.

A satellite one kilometre above the geostationary radius drifts **west** at
0.0128 deg/day. This is the relation the task asked to be derived rather than
assumed; it is used for interpretation and for §2.6, never inside a detector
decision.

### 2.4 Angular and linear scale

`1° of longitude at a_s = 2π a_s / 360 = 735.904 km`. Hence the thresholds of
§4 in kilometres of along-slot separation: 0.05° = 36.8 km, 0.1° = 73.6 km,
0.2° = 147.2 km, 0.5° = 367.9 km, 2.0° = 1471.8 km.

### 2.5 The ΔV constant (stated once, computed for nothing)

For a tangential impulse on a circular orbit, `Δa/a = 2ΔV/v` with
`v = sqrt(μ/a_s) = 3.07466 km/s`, so `Δa = 27426.88 km per km/s`. Combining
with §2.3, a tangential impulse changes the drift rate by

&nbsp;&nbsp;&nbsp;&nbsp;`Δḋ = −0.35222 deg/day per m/s` (prograde impulse ⇒ westward drift).

This is recorded so that a reader can convert a published deg/day figure if
they wish. **T8a computes no ΔV, no propellant and no fuel figure for any
object**, in keeping with the commercial-civil-only overlay policy.

### 2.6 Triaxiality: why a dead object cannot hold a slot, and where it can

The Earth's sectorial J22 term makes the geostationary belt a pendulum in
longitude with stable points near 75.1°E and 104.7°W. The equatorial
longitude-dependent acceleration from
`U₂₂ = (μ/r)(R_e/r)²·3·J₂₂·cos²φ·cos 2(λ − λ₂₂)` is

&nbsp;&nbsp;&nbsp;&nbsp;`a_t = (1/r)·∂U₂₂/∂λ`, `|a_t|max = 6 J₂₂ (μ/a_s²)(R_e/a_s)²`

with J₂₂ = 1.8155e-6 (unnormalised sectorial magnitude): **|a_t|max = 5.5885e-8 m/s²**.
Converting a tangential acceleration to a longitude acceleration by
differentiating §2.3 and §2.5,

&nbsp;&nbsp;&nbsp;&nbsp;`λ̈ = −(3/2)(ω_E/a_s)·(2 a_s a_t / v) = −3 ω_E a_t / v`,

giving **`|λ̈|max = 1.701e-3 deg/day²`**, i.e.
`λ̈(λ) ≈ −1.701e-3 · sin 2(λ − λ_stable)` deg/day². (The customary textbook
figure is ≈1.8e-3 deg/day²; the residual difference is the normalisation and
latitude convention of J₂₂ and does not affect any conclusion below, all of
which are order-of-magnitude-safe.)

**This is the physical basis of the cannot-manoeuvre control.** An
uncontrolled object placed at rest in longitude at a generic longitude falls
out of a ±X band in `t = sqrt(2X/|λ̈|)`; for X = 0.1° that is **10.8 days**.
Requiring a loiter of D days therefore excludes a passive object unless
`|sin 2Δ| < 2X/(|λ̈| D²)`, where Δ is its distance from a stable point:

| X | D | Passive object can hold the band only within ±Δ of a stable point | Fraction of the belt |
|---:|---:|---:|---:|
| 0.1° | **30 d** | **±3.75°** | 4.2% |
| 0.1° | 14 d | ±18.43° | 20.5% |
| 0.1° | 7 d | everywhere (bound void) | 100% |
| 0.05° | 14 d | ±8.73° | 9.7% |
| 0.2° | 14 d | everywhere (bound void) | 100% |

**This table chose D, before any data was touched.** D = 30 d is registered as
primary in §4 because it is the shortest registered duration at which the
passive-exclusion argument holds across 95.8% of the belt. D = 14 d and
D = 7 d are carried as sensitivity arms and are labelled in the results as
having a weak and a void passive exclusion respectively. Events whose loiter
longitude lies within the primary arm's ±3.75° of a stable point are flagged
`libration_zone: true` and every headline is reported both with and without
them.

### 2.7 Station-keeping confinement, and the drift floor it implies

East–west station-keeping holds a satellite in a box of half-width ΔL
(typically 0.05°–0.1°; T8a assumes the generous 0.1° for every bound below)
over a cycle of order one to two weeks. Inside the box the mean longitude is
bounded but not constant, so a slope estimator sees a spurious drift. For
samples spread over a window W, the ordinary-least-squares slope obeys

&nbsp;&nbsp;&nbsp;&nbsp;`|slope| ≤ (range of λ)·Σ|t−t̄| / Σ(t−t̄)² = 2ΔL·(W/4)/(W²/12) = 6ΔL/W`.

With ΔL = 0.1°: **W = 15 d ⇒ 0.040 deg/day; W = 30 d ⇒ 0.020 deg/day.** These
are the `d_floor` values of §5.4 — derived bounds on how much apparent drift a
confined object can show, not fitted numbers.

From §0.2, the near-GEO median epoch spacing is 0.865 d and 99.7% of objects
are sampled at ≤ 2 d. A 30-day loiter therefore contains ≈35 element sets for
a median object. §4 registers the loiter occupancy requirement directly from
this: at least `0.4 · (interval length in days)` element sets, and no internal
gap longer than 5 days (≈5.8 median spacings).

---

## 3. Population

### 3.1 Near-GEO membership, evaluated per element set

An element set is **near-GEO** if all three hold:

- mean motion `n ∈ [0.95, 1.05]` rev/day — equivalently `ḋ ∈ [−18.99, +17.01]`
  deg/day by §2.3, a band wide enough to contain any drift orbit an object
  could use to relocate within the belt, and narrow enough to exclude GTO,
  MEO and supersynchronous disposal;
- eccentricity `e ≤ 0.01`;
- inclination `i ≤ 25°` — chosen to retain long-abandoned objects whose
  inclination has librated up over decades (the passive control needs them),
  not to admit them to the payload analysis. λ of §2.2 is inclination-free by
  construction, so the bound costs no accuracy.

An **object** enters T8a if it has at least one near-GEO element set. Objects
move in and out of membership over their lives and all analysis below is on
the near-GEO *intervals*, never on whole object histories.

### 3.2 Classes

- **Active class**: `object_type = 'PAYLOAD'`.
- **Passive class** (the cannot-manoeuvre control): `pipeline.orbit_events.PASSIVE_TYPES`
  (DEBRIS, ROCKET BODY), borrowed rather than restated so a later change cannot
  leave a divergent copy behind — the same discipline `tools/cadence_core.py`
  uses.
- `object_type` NULL or UNKNOWN is excluded from both and counted.

Country, object type, name, `object_id` and launch date are attached to every
event row as metadata. **No detector branch reads any of them except
`object_type`, and only to assign the class above.**

---

## 4. The registered event definition

For an ordered pair of near-GEO objects (A, B), let `Δλ(t) = wrap(λ_A(t) − λ_B(t))`
be evaluated on the union of their element-set epochs by linear interpolation
of each object's λ onto the other's epochs (interpolation is refused across
any gap longer than 5 days in either series; those epochs are dropped and
counted).

**A T8a approach event is:**

1. **Loiter.** A contiguous interval `[t_a, t_e]` of length ≥ **D** over which
   `|Δλ(t)| ≤ X` at every retained epoch, containing at least
   `0.4·(t_e − t_a)/1 d` retained epochs, with no internal gap > 5 d (§2.7).
2. **Prior separation.** At some epoch in `[t_a − T_look, t_a]` with
   T_look = **180 d**, `|Δλ| ≥ X_far` with X_far = **2.0°** (§2.4: 1472 km).
3. **Approacher motion.** Over `[t_0, t_a]`, where t_0 is the last epoch
   before t_a at which `|Δλ| ≥ X_far`, object A's own longitude change
   satisfies `|λ_A(t_a) − λ_A(t_0)| ≥ 0.8 · |Δλ(t_0) − Δλ(t_a)|` **and**
   `|λ_A(t_a) − λ_A(t_0)| ≥ X_far − X`. A is then **the approacher** and B
   **the target**, by the programme's standing rule: the object whose elements
   changed is the approacher. If both objects satisfy the 0.8 bar (both moved
   comparably), the pair is recorded with `attribution: "ambiguous"` and is
   excluded from every headline.
4. **Departure** (recorded, not required). The first epoch after t_e at which
   `|Δλ| ≥ X_far`, or `null` if the archive ends first or it never happens.

**Registered thresholds.** Primary: **X = 0.1°, D = 30 d**. Sensitivity arms,
run and reported in full: X ∈ {0.05°, 0.2°, 0.5°} at D = 30 d, and
D ∈ {7 d, 14 d} at X = 0.1°, each labelled with its passive-exclusion status
from §2.6. X = 0.1° is registered as primary because it is the scale of a
shared station-keeping box — the regime in which two operators must coordinate
— and because §5.4's noise calibration is required to come back at least
10× below it (§10, gate A).

**Co-location versus approach.** Two objects *assigned* to a common slot never
satisfy criterion 2 or 3: they were never 2° apart and neither of them
travelled 1.9° to reach the other. The distinction is drawn by observed motion
alone and never by operator, country or name. Pairs that are within X for the
whole overlap of their near-GEO intervals are counted separately as
**standing co-locations** and reported, because their number is the
denominator the null of §6 needs.

---

## 5. Estimators

### 5.1 Longitude series
λ per §2.2 from `(raan_q, arg_perigee_q, mean_anomaly_q)` at scale 1e4, 1e4,
1e4 and `epoch_ms`, unwrapped along each object's near-GEO interval before any
slope or interpolation is taken, and re-wrapped for reporting.

### 5.2 Drift rate — two estimators, one of them primary, cross-checked
- **`ḋ_n`** (primary, single-sample): `360·n − ω_E` from `mean_motion_q` at
  scale 1e8 (§2.3). It needs no window, which is the whole reason lead time is
  measurable at all (§5.5).
- **`ḋ_λ`** (geometric check): Theil–Sen slope of λ over a trailing window W.
- **Registered cross-validation, reported whatever it says:** on station-kept
  segments (§5.3), report the median bias and the robust scatter of
  `ḋ_n − ḋ_λ`. If the bias exceeds `d_floor` (§2.7) the primary estimator is
  declared unfit and the pilot reports that instead of an event catalogue
  (§10, gate A).

### 5.3 Station segmentation (used for calibration and for profile shapes)
An object is **stationed** over an interval if `|λ − median λ| ≤ 0.3°`
throughout — the generous 0.1° box of §2.7 tripled, so that legacy wide-box
control is retained — and the interval is ≥ 30 d. Otherwise it is **drifting**.

### 5.4 The one calibrated quantity, and how it is calibrated
σ_n, the noise floor of `ḋ_n`, is **measured, not assumed**: the median
absolute deviation of `ḋ_n(t_{k+1}) − ḋ_n(t_k)` over consecutive element-set
pairs inside stationed segments, scaled by 1.4826/√2 to a per-sample σ,
pooled over the active class. Its value is unknown at registration time. It
is a property of the archive's *fit noise*, not of any approach event, and no
event definition in §4 depends on it. Registered gate: §10 gate A requires
`σ_n` to come back below `X/10` in drift-rate terms over a 30-day arc, i.e.
below 0.0033 deg/day.

### 5.5 Burn detection and lead time
A **drift-change flag** fires at element set k when
`|ḋ_n(t_k) − median(ḋ_n over the preceding 10 element sets)| > max(5·σ_n, 0.010 deg/day)`
**and** the same condition holds at k+1 (two-consecutive-sample confirmation,
so a single bad fit cannot fire it). The floor of 0.010 deg/day is derived, not
chosen: by §2.6 it is the drift a passive object accrues in six days, and by
§2.3 it corresponds to 0.78 km of semi-major axis — below the level at which a
change can be called deliberate. The flag time is the epoch of element set
**k+1**, because that is the first instant a causal observer possessed the
evidence.

For each approach event, the **initiating flag** is the last drift-change flag
on the approacher strictly before t_0 + 1 d, searched back to t_a − T_look.
Two lead times are recorded:

- `lead_ideal = t_a − t_k`  (first changed element set to arrival);
- **`lead_causal = t_a − t_{k+1}`  (confirmation to arrival) — the headline.**

`lead_causal ≤ 0` is possible and is reported as such, never dropped. Events
with no initiating flag inside the look-back are reported as
`lead_causal: null` with their count; suppressing them would inflate the
headline.

### 5.6 Early-warning precision, registered because it is the unflattering half
Every drift-change flag on an active-class object that begins a drift segment
of ≥ 2° of longitude change is a **relocation alert**. T8a reports the
fraction of relocation alerts that end in a §4 event — the precision of the
hypothetical service — alongside the lead time. A long lead time with a 2%
precision is not an early-warning capability, and the results document is
required to say so in those terms if that is the outcome.

---

## 6. Nulls and controls

### 6.1 The chance co-location null (the primary null)
The geostationary belt is crowded, and this null is registered because the
pre-registered expectation is that it will explain much of the raw catalogue.
Under uniformity, the expected number of stationed objects within ±X of an
arbitrary longitude is `N_s · 2X / 360`; with N_s of order 800 and X = 0.1°
that is ≈0.44 — **a relocation that stops anywhere lands within 0.1° of some
object almost half the time by chance alone.** Real longitudes are clustered,
not uniform, so the true figure is higher still.

The null is therefore empirical and paired: **1,000 permutations, seed
20260922.** Each real arrival (approacher, t_a, drift history preserved
exactly) is re-assigned an arrival longitude drawn from the empirical
distribution of longitudes occupied by stationed objects at that epoch — the
same crowding, the same epoch, a different destination — and the §4 criteria
are re-applied. Reported: observed event count against the null mean and its
95% interval, for the primary and every sensitivity arm.

### 6.2 The cannot-manoeuvre control
The identical detector, unchanged, on the passive class of §3.2. By §2.6 it
should return essentially nothing at D = 30 d outside the libration zone.
Registered in advance: a passive yield above **2%** of the active yield, per
unit of exposure, means the detector is admitting drift-through and the pilot
reports a leak rather than a catalogue (§10, gate B). The passive rate inside
and outside the ±3.75° libration zone is reported separately, because §2.6
predicts they differ and a control that fails to show that difference has
falsified its own premise.

### 6.3 Standing co-locations
Reported as a separate count (§4). They are not events and are not in any
headline; they are the crowding measurement the §6.1 null is drawn from.

---

## 7. The repetition estimand (the early-warning seed)

For approachers with ≥ 2 events, each event gets a **profile vector**:

`(|drift rate| during transfer, transfer duration, |net longitude change|,
  closest |Δλ| during loiter, loiter duration, |departure drift rate|)`,

each component log-transformed (all are positive scales; the log makes
"twice as long" the unit of difference rather than "a day longer"). Registered
statistics:

1. **Repeat counts.** Number of objects with ≥2, ≥3, ≥5 events; number with
   ≥2 events against **distinct** targets. Each compared to the §6.1 null,
   which supplies the same per-object relocation counts.
2. **Intraclass correlation** per component:
   `ICC = (MS_between − MS_within)/(MS_between + (n̄−1)·MS_within)`, one-way
   random effects over approachers with ≥2 events. ICC ≈ 0 means an object's
   events are drawn from the population; ICC ≫ 0 means objects have profiles.
3. **Leave-one-out predictive skill**, which is the operationally meaningful
   version of 2: for each event of each repeat approacher, predict loiter
   duration and closest approach from the *median of that object's other
   events*, and separately from the population median. Report
   `skill = 1 − MAE_own / MAE_population` per component. A positive skill is
   the pilot's evidence that past behaviour predicts the next event; a
   negative or zero skill is reported as plainly.
4. **Per-object significance**: Poisson tail probability of each approacher's
   event count against the per-object rate from the §6.1 null, with
   **Benjamini–Hochberg FDR at q = 0.05** across all approachers with ≥1
   event. Multiplicity is handled here and nowhere else, because §4's
   catalogue is descriptive and carries no p-values. The number of objects
   tested is reported with the number surviving.

The pair space is not O(N²): only objects stationed within X_far of an
approacher's arrival are ever compared, so the tested-hypothesis count is the
number of arrivals, not the number of pairs, and it is reported explicitly.

---

## 8. Compute, provenance and reproducibility

- `tools/proximity_geo.py`, CPU, on `pc`, `nice`-d. One sequential pass over
  `element_set` in NORAD order (§0.3: ≈180 s) filtered to §3.1, then all
  analysis in memory. **No GPU stage is registered**; if one is later found
  necessary it goes through `gpu-run` and the deviation is recorded in the
  results document.
- Read-only: the archive is opened through
  `pipeline.orbit_campaigns.open_archive_for_reading` with `PRAGMA query_only=1`,
  the pattern `tools/cadence_extract.py` uses. Provenance recorded in the
  receipt: archive path, byte size, mtime, page count, `month_rollup` span and
  row total, plus SHA-256 of `tools/proximity_geo.py` and of every pipeline
  module it imports.
- Outputs: `docs/proximity-events-20260922.jsonl` (one JSON object per event,
  with the metadata columns of §3.2), `docs/proximity-20260922-receipt.json`,
  `docs/proximity-results-20260922.md`. Nothing is written to `src/`, `data/`,
  `public/` or any site surface.
- Determinism: seed 20260922 for the permutation null; no other randomness.
- Tests in `tests/test_proximity_geo.py` must cover, at minimum: the GMST
  formula against an independently computed epoch, λ against a constructed
  element set at a known longitude, the §2.3 drift relation, wrap-around at
  ±180°, a synthetic approach that must be detected, a synthetic drift-through
  that must **not** be, a synthetic standing co-location that must not become
  an event, and the attribution rule on a synthetic pair where the target
  moved instead.

---

## 9. Declared blind spots

Stated now so that they cannot later be presented as findings.

1. **Mean longitude is not miss distance** (§1.1). T8a cannot see radial or
   cross-track separation and models no eccentricity- or inclination-vector
   separation strategy. No T8a number is a collision or proximity *distance*.
2. **Cadence.** Median near-GEO spacing 0.865 d (§0.2), but the distribution
   has a tail; any manoeuvre-and-reverse inside a gap is invisible, and the
   5-day interpolation refusal converts long gaps into missing epochs rather
   than into evidence.
3. **Motion below the noise.** Drift changes below `max(5σ_n, 0.010 deg/day)`
   are undetectable by §5.5; by §2.3 that floor is ≈0.78 km of semi-major
   axis. A slow approach executed below it would be missed entirely, and the
   catalogue is therefore a **lower bound on events, never a census**.
4. **The libration zone** (§2.6): within ±3.75° of 75.1°E and 104.7°W at the
   primary arm, the passive-exclusion argument does not hold and events there
   are flagged, not trusted.
5. **Catalogue completeness.** Objects absent from the public catalogue,
   objects whose elements are withheld or degraded, and epochs before the
   archive's back-fill coverage are invisible. Absence of an event is not
   evidence of absence of an approach.
6. **Regime.** Non-GEO entirely out of scope; drift orbits outside §3.1's
   mean-motion band are not followed.
7. **Interpolation.** λ is linearly interpolated between element sets; during
   a fast transfer at several deg/day this is a real error of order the drift
   rate times half the spacing (≈0.4 d), which is why criterion 1 requires the
   bound at *every retained epoch* rather than at interpolated instants alone.

---

## 10. Gates: what makes this pilot uninformative

Registered before any measurement. Each is a statement the results document
must make explicitly, in these words, if it fires.

- **Gate A — the instrument is unfit.** `σ_n` (§5.4) ≥ 0.0033 deg/day, or the
  `ḋ_n − ḋ_λ` bias (§5.2) exceeds `d_floor`. Then λ or `ḋ_n` is not accurate
  enough at TLE quality for a 0.1° estimand and T8a reports the calibration
  and stops; it does not quietly widen X to rescue a catalogue.
- **Gate B — the detector leaks.** Passive-class yield per unit exposure
  > 2% of active-class yield outside the libration zone (§6.2). Then the
  events are drift-through, and T8a reports that.
- **Gate C — the null explains the catalogue.** Observed event count inside
  the §6.1 null's 95% interval. This is **not** a failure of the pilot; it is
  the finding that GEO approach events at X = 0.1° are indistinguishable from
  crowding, and §7's repetition statistics — which the null also supplies —
  become the whole result.
- **Gate D — underpowered repetition.** Fewer than 10 approachers with ≥2
  events. Then ICC and leave-one-out skill are reported with their intervals
  and labelled UNDERPOWERED, and no predictive claim is made.
- **Gate E — no lead time.** Median `lead_causal` ≤ 0, or `lead_causal` null
  for > 50% of events. Then public elements do not support early warning for
  this event class and T8a says so; that is a publishable negative result for
  T8 and the track's later stages are re-scoped on it, not around it.

Any of these firing is reported in the results document's first screen. None
of them may be revised after a number exists.

---

## 11. What is committed with this document

Nothing. This registration is committed **alone**. `tools/proximity_geo.py`,
its tests, the event catalogue, the receipt and
`docs/proximity-results-20260922.md` all follow in later commits, and the
ordering in `git log` is the evidence.
