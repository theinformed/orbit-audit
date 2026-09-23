# T8b pre-registration: LEO/MEO/HEO approach events from plane matching and phasing

Registered 2026-09-22, **before any T8b plane separation, pair, event, count or
lead time exists**. This document is committed **alone**, ahead of everything
T8b will ever produce, exactly the way `docs/proximity-preregistration-20260922.md`
was committed ahead of T8a and `docs/cadence-preregistration-20260921.md` ahead
of T3. The git history of this file is the timestamp. Nothing below may be
changed once a T8b number exists; an awkward outcome is reported, not edited
away.

T8b is the regime layer of track T8 of `docs/research-program-runbook-20260921.md`:
it extends approach-event detection beyond the geostationary belt, into LEO,
MEO and HEO. It registers what T8b estimates, on which objects, with which
thresholds, against which nulls, and what would make it uninformative. It
implements nothing.

Three estate rules this document is written under, restated because they are
the reason most of what follows is derivation rather than assertion:

- **Physical assumptions are not facts — derive or cite every physical claim;
  thresholds are screens, not laws.** T8a added a corollary that this document
  is built around: *a derivation is not a validation either.* Every threshold
  below that a control depends on is registered together with the procedure
  that must validate it against data before it is used, and with the gate that
  fires if the validation fails (§10).
- **The instrument is ownership-agnostic mathematics.** Catalogue registry
  codes and object-type codes are carried as ordinary metadata columns on every
  event row so that later analysis is possible, and they enter **no** detector
  decision. Nothing in T8b's outputs may carry intent language — no inspection,
  spying, threat, adversary, hostile, shadowing or stalking vocabulary — and
  T8b produces no per-nation narrative. The attribution rule from the
  programme's earlier design holds unchanged: **the object whose elements
  changed is the approacher; facts, never intent.** Publication and site
  framing for this track is reserved to Sean and is not a T8b output. Results
  land in `docs/` only; nothing is written to `src/`, `data/`, `public/` or any
  site surface. These rules are enforced by tests, not merely intended, in the
  manner of `tests/test_proximity_geo.py::TestPolicyGuards`.
- **The propulsion/fuel overlay stays commercial-civil-only.** T8b reports
  plane-change magnitudes in **degrees** and semi-major-axis changes in
  **kilometres and nothing else**; §2.6 derives the degrees-to-ΔV constants
  once, as physics, and T8b computes no per-object ΔV, propellant or
  consumables figure for any object.

### T8a's four named failures, and where each is answered

T8a is the pilot this document inherits. Its results
(`docs/proximity-results-20260922.md`) name four failures. Each is answered
here by construction, and the answer is registered, not promised:

| T8a failure | Where T8b answers it |
|---|---|
| **Gate B leak** — the registered event definition was a *geometry* detector, and GEO geometry is produced by free libration as readily as by manoeuvring. | Manoeuvre corroboration is a **first-class criterion of the primary arm** (§4, arm M), not a filter added afterwards. The geometry-only arm G is retained *as the leak measurement*, with its leak pre-registered as **expected** (§10, gate B). |
| **The dwell bound measured nominal rather than own-equilibrium** — the triaxiality bound that chose D = 30 d computed distance from the *nominal* stable longitudes and was falsified 5/5. | The LEO analogue — the chance-co-planarity dwell bound, §2.5 — is computed **only** from each pair's **own measured nodal rates over its own history**, never from a nominal J2 rate at a nominal altitude; and §10 gate G registers the validation it must pass against held-out never-manoeuvred pairs **before** any threshold is set from it. |
| **The dead-payload-contaminated control** — the real uncontrolled population is dominated by dead *payloads*, which `object_type` labels PAYLOAD and the control could not see. | The control class is **manoeuvre-history-based** (§3.4): objects with **zero detected manoeuvres of any kind over their whole archive history**, measured by the detector registered in §5.4. `object_type` is retained only as a second, *comparison* class so the size of T8a's contamination can be measured directly. |
| **The Gate A self-contradiction** — the registration wrote a formula (`X/10` over `D`) and a number (0.0033) beside it that disagreed by 10×, and the results had to be reported both ways. | Every gate in §10 is stated as **a formula and its evaluated number computed in this document**, with the arithmetic shown, so the two cannot disagree. §10.0 states the rule that decides a gate if they ever do. |

A fifth, undeclared T8a blind spot is also answered: **the look-back window
truncated the lead-time distribution.** T8b registers a 1,095-day look-back and
registers a **Kaplan–Meier survival curve** as the primary presentation of lead
time, with percentiles secondary and labelled (§5.7, §10 gate F).

---

## 0. What was measured BEFORE this registration, and why it is not a result

Two pre-scans were run before this document was written. Both are disclosed in
full, because concealing a pre-scan is how a registration quietly becomes a
post-hoc rationalisation. Neither computed a plane separation, an orbit normal,
a pair, a co-planarity, a manoeuvre or an event. Every threshold below is
derived in §2 from orbital mechanics and from the archive's *sampling* pattern,
never from its element *values* — with the two exceptions flagged in §5.2 and
§5.3, where noise floors are **calibrated** by a procedure registered here and
run before any event is formed.

### 0.1 Regime census (one sequential pass, three columns plus epoch)

A single sequential pass over `element_set` read
`(norad, epoch_ms, mean_motion_q, eccentricity_q, inclination_q)` and binned
each element set by the regime rule of §3.1. 217,026,192 element sets were
scanned in 616 s (352 k rows/s, `nice`-d). Per element set, not per object:

| Regime (§3.1) | Element sets | Distinct objects | Object-days |
|---|---:|---:|---:|
| **LEO** | 177,780,726 | 61,861 | 112,828,396 |
| **MEO** | 4,288,937 | 1,084 | 3,332,027 |
| **HEO** | 23,307,057 | 8,532 | 17,150,632 |
| near-GEO (T8a's band, **excluded**) | 11,627,368 | **1,768** | 7,674,219 |
| perigee below 100 km (decaying/re-entering) | 22,104 | 1,052 | 9,308 |

The near-GEO object count of **1,768** reproduces T8a's population exactly
<!-- src: docs/proximity-results-20260922.md §1 -->, which is the one check
this census buys: the regime rule of §3.1 and T8a's §3.1 screen agree on the
belt they share, so T8b's regimes partition the archive without overlapping the
pilot.

The two facts this census buys, and the only uses made of them below: **LEO is
the archive** (82% of its element sets), and **the LEO object-day count is
1.13e8**, which is what §8 sizes the screening pass from.

The pass also re-measures T8a's provenance discrepancy: 217,026,192 element
sets scanned against `month_rollup`'s 183,352,638. The rollup is stale by
33.7 M rows and T8b, like T8a, takes the scan as ground truth.

### 0.2 Sampling geometry per regime (epochs only, no element values)

Objects were assigned a regime from their **single most recent** element set —
a lower-bound screen, exactly T8a's §0.1 method and carrying the same caveat
(an object that was LEO for years and has since decayed or been re-orbited is
not counted) — and then a stride-sampled subset of each regime had **nothing
but `epoch_ms`** read for its whole history.

Objects by most-recent element set: LEO 60,595, HEO 4,599, MEO 639, near-GEO
1,587, decaying 669. Sampled at stride 40 (LEO, 1,488 objects), 4 (MEO, 160)
and 10 (HEO, 452); 41.8 s.

| Quantity | Regime | p5 | p25 | **p50** | p75 | p95 |
|---|---|---:|---:|---:|---:|---:|
| Within-object median epoch spacing (d) | **LEO** | 0.260 | 0.389 | **0.528** | 0.956 | 2.349 |
| | MEO | 0.544 | 0.819 | **0.939** | 0.997 | 1.193 |
| | HEO | 0.469 | 0.835 | **0.972** | 1.185 | 5.775 |
| Element sets per object | **LEO** | 6 | 101 | **894** | 2,977 | 17,423 |
| | MEO | 212 | 2,846 | **6,986** | 9,996 | 13,953 |
| | HEO | 11 | 297 | **2,104** | 6,046 | 13,744 |
| Archive span per object (d) | **LEO** | 3.2 | 71.8 | **804** | 2,607 | 15,141 |
| | MEO | 636 | 3,136 | **6,780** | 13,519 | 22,155 |
| | HEO | 42.8 | 1,212 | **3,941** | 8,730 | 18,340 |

Fraction of objects with median spacing ≤ 1 d: **LEO 0.803, MEO 0.788,
HEO 0.593**. ≤ 2 d: **LEO 0.939, MEO 0.975, HEO 0.876**.

Two consequences are taken from this table and nothing else is: the **0.4
element sets per day** occupancy requirement and the **5-day maximum internal
gap** of §4.4 (≈9.5 median LEO spacings), which together exclude the sparsely
sampled tail — about 5% of LEO objects and 5% of HEO objects have a median
spacing that cannot meet the occupancy bar, and that exclusion is reported as a
count, not hidden; and the **1.0-day fast-angle propagation limit** of §5.1,
which is roughly twice the median LEO spacing and is therefore satisfiable for
the great majority of epochs while refusing the tail outright.

The facts this buys, and the only uses made of them below: the within-object
epoch spacing sets the **loiter occupancy and maximum-gap requirements** of
§4.4, and the **fast-angle propagation limit** of §5.1. Nothing else in this
document reads them.

---

## 1. What T8b is for (four declared uses, registered before the result)

1. **An event catalogue per regime.** A dated, reproducible list of historical
   LEO, MEO and HEO approach events: object A ran a plane-matching campaign
   against object B's orbit plane, phased along-track, and then held a bounded
   relative position for at least D days. Facts about published orbital
   elements, with the provenance of each row recorded.
2. **A lead-time measurement — the headline.** For each event, how many days
   elapsed between the initiating manoeuvre first becoming *confirmable* in the
   public element archive and the arrival. T8a measured a median **36.1 d** at
   GEO. §2 derives why the LEO number is plausibly **longer** — plane changes
   are expensive and slow, and the cheap route to a plane change is a
   months-long J2 phasing campaign — and T8b measures it rather than asserting
   it. If the LEO lead time comes back *shorter* than GEO's, that is the
   result and it is reported as such.
3. **A precision measurement.** The fraction of detected plane-matching
   campaigns that end in an event — the unflattering half of an early-warning
   capability, registered here precisely so it cannot be omitted, as T8a's
   §5.6 was.
4. **A regime comparison.** Whether the event class, its lead time and its
   precision differ between LEO, MEO and HEO. The same machinery runs on all
   three; the regimes are reported separately and never pooled.

### 1.1 What T8b is explicitly NOT

- **T8b does not measure miss distance, and does not deliver the conjunction
  instrument the T8a results anticipated.** This is a registered change of
  scope against `docs/research-program-runbook-20260921.md`, which recorded
  "T8b owns miss distance", and the reason is derived in §2.7: two circular
  orbits of similar radius **always intersect** regardless of plane separation,
  so a miss distance is decided entirely by the fast angle, at a positional
  accuracy public two-line elements do not have. T8b's estimand is a
  **co-orbital station**: matched plane, matched altitude, bounded relative
  phase, sustained. Its scales are **tens of kilometres and are stated as
  such** (§4.2). **No T8b number is a conjunction, a miss distance or a
  collision risk.** A miss-distance instrument needs special-perturbations
  ephemerides and belongs to track T6, not here.
- It is not a manoeuvre detector in the Paper A/Paper B sense. §5.4 registers a
  deliberately simple, own-history manoeuvre detector for two internal
  purposes — corroboration and the control class — and it reuses none of
  Paper A's thresholds and makes none of its claims. Its own false-alarm rate
  is a registered output (§6.3), not an assumption.
- It does not cover the near-geostationary belt: that is T8a's, and §3.1
  excludes it explicitly so the two catalogues cannot double-count.
- It is not an all-vs-all study. The registered scope is **active-payload
  approachers against the full catalogue** (§3.3). What an HPC-scale
  all-vs-all would add is registered in §11 as the T5b handoff spec, before any
  result exists, so that it cannot later be presented as a finding.

---

## 2. The physics, derived

Every constant used by T8b is derived here from WGS-84/EGM-96 values
(μ = 398600.4418 km³/s², R_e = 6378.137 km, J₂ = 1.08262668e-3) and the
sidereal Earth rotation rate ω_E = 360.9856473 deg/day. Numbers are quoted to
the precision the derivation supports, and each is recomputed inside the
instrument from these primitives so a reader can check the arithmetic without
leaving the file.

### 2.1 The plane-separation metric

An orbit's plane is fixed by the direction of its angular momentum. Rotating
the polar axis into the orbit normal,

&nbsp;&nbsp;&nbsp;&nbsp;`ĥ = R_z(Ω) R_x(i) ẑ = (sin i sin Ω, −sin i cos Ω, cos i)`.

The dihedral angle between two orbit planes is the angle between their
normals, so the **plane separation** is

&nbsp;&nbsp;&nbsp;&nbsp;**`cos θ = ĥ_A · ĥ_B = cos i_A cos i_B + sin i_A sin i_B cos(Ω_A − Ω_B)`**,

which is the spherical law of cosines on the triangle with sides i_A, i_B and
included angle ΔΩ = Ω_A − Ω_B. Two immediate consequences, both used below:

&nbsp;&nbsp;&nbsp;&nbsp;`|i_A − i_B| ≤ θ ≤ min(i_A + i_B, 360° − i_A − i_B)`,

with the **lower bound attained exactly when ΔΩ = 0**. Since T8b works at
θ of order a tenth of a degree, the cosine form loses precision, so the
instrument evaluates the algebraically identical half-angle form, obtained by
subtracting both sides from 1 and halving:

&nbsp;&nbsp;&nbsp;&nbsp;**`sin²(θ/2) = sin²((i_A − i_B)/2) + sin i_A sin i_B sin²(ΔΩ/2)`**.

Both terms are non-negative, which re-derives `θ ≥ |Δi|` directly, and the
expression is accurate to full double precision at small θ.

θ is computed from the **mean** elements a TLE publishes. It is a plane
coordinate: it says the two orbits share a plane to within θ. It is **not** a
distance and **not** a miss distance (§1.1, §2.7).

The linear scale of a plane separation is the cross-track excursion it permits,
which at orbital radius r is at most `r sin θ`. At a 500 km LEO altitude
(r = 6878.137 km): **0.05° = 6.0 km, 0.1° = 12.0 km, 0.2° = 24.0 km,
0.5° = 60.0 km, 1.0° = 120.0 km, 5.0° = 599.5 km.**

### 2.2 Why a plane change is the expensive, slow, visible part

For a rotation of the velocity vector through θ at speed v, the impulse needed
is the third side of an isoceles triangle with two sides v:

&nbsp;&nbsp;&nbsp;&nbsp;`ΔV_plane = 2 v sin(θ/2)`.

At a = 6878.137 km, `v = sqrt(μ/a) = 7.6126 km/s`, so **one degree of direct
plane change costs 132.9 m/s**. Compare the in-track manoeuvre that raises the
orbit by δa: from the vis-viva relation `v² = μ(2/r − 1/a)`, a tangential
impulse on a near-circular orbit gives `Δa/a = 2ΔV/v`, i.e.

&nbsp;&nbsp;&nbsp;&nbsp;`ΔV_intrack = (v/2)(δa/a) = 0.5534 m/s per km of δa` at 500 km,

so a **100 km altitude change costs 55.3 m/s** — 2.4 times *less* than a single
degree of direct plane change. In MEO the plane change is cheaper in absolute
terms but still dominant: at the GPS radius (a = 26578 km, v = 3.8726 km/s),
one degree costs 67.6 m/s.

This asymmetry is the whole physics of LEO early warning, and §2.3 completes
it: there is a cheap route to a **RAAN** change, and it is slow.

### 2.3 The J₂ nodal regression, and the cheap route to co-planarity

The Earth's oblateness makes the orbit plane regress. To first order in J₂,
averaged over an orbit, the secular rate of the right ascension of the
ascending node is the standard Brouwer result

&nbsp;&nbsp;&nbsp;&nbsp;**`Ω̇ = −(3/2) n J₂ (R_e/p)² cos i`,&nbsp;&nbsp;`p = a(1 − e²)`**,

n the mean motion. The instrument recomputes this from its primitives; three
values are quoted here as the anchors of every claim below, with the sign
convention that a prograde orbit regresses westward:

| Orbit | Ω̇ (deg/day) |
|---|---:|
| 300 km, i = 0° | **−8.483** |
| 500 km, i = 53.0° | **−4.605** |
| 800 km, i = 98.6° | **+0.985** |

The third line is the derivation's own validation: it reproduces the
sun-synchronous condition, `Ω̇ = +0.9856 deg/day`, the mean rate of the Sun's
right ascension, to 0.1%. A derivation that reproduces a known orbit to 0.1%
has earned the arithmetic below.

**The differential.** Since `Ω̇ ∝ n a⁻² ∝ a^(−7/2)`,

&nbsp;&nbsp;&nbsp;&nbsp;`∂Ω̇/∂a = −(7/2) Ω̇ / a`,&nbsp;&nbsp;
`∂Ω̇/∂i = −Ω̇ tan i`.

At 500 km and i = 53°, `|∂Ω̇/∂a| = 3.5 × 4.605 / 6878.137 =` **0.002343 deg/day
per km**. So:

> **A 100 km altitude offset buys 0.234 deg/day of relative nodal drift, for
> 55.3 m/s. Buying the same one degree of RAAN directly costs 132.9 m/s and
> buying ten degrees costs 1,329 m/s; buying ten degrees through J₂ costs the
> same 55.3 m/s and 43 days of waiting, and buying ninety degrees costs the
> same 55.3 m/s and 384 days.**

This is the derived reason a LEO plane-matching campaign is *slow*, and the
derived reason T8b's lead time is plausibly longer than T8a's 36.1 days. It is
registered as an expectation to be measured, not as a result.

Note the asymmetry the instrument must respect: **J₂ moves Ω and does not move
i.** An inclination change has no cheap route — `∂i/∂t` has no secular J₂ term
— so a campaign that must close an inclination difference pays §2.2's full
price, and a campaign that must close only a RAAN difference does not. The
event definition of §4 therefore does not assume which of the two the
approacher used; it measures the closure of θ and attributes it (§4.5).

### 2.4 The false-alarm mechanism, derived: chance co-planarity by J₂ alone

This is the LEO analogue of T8a's chance co-location null, and it is stronger,
because it is not merely probable but **certain**:

> For any pair whose inclinations differ by less than a threshold θ_p, the
> plane separation θ(t) is a periodic function of ΔΩ(t) whose **minimum over
> the relative nodal cycle is exactly `|i_A − i_B|`** (§2.1). Two such objects
> therefore become co-planar to within θ_p — **twice per relative nodal
> cycle, with certainty, with no manoeuvre whatever.**

The cycle period is `360° / |ΔΩ̇|` where `ΔΩ̇ = Ω̇_A − Ω̇_B`. The **dwell** of one
crossing follows from inverting §2.1's half-angle form at θ = θ_p:

&nbsp;&nbsp;&nbsp;&nbsp;`sin²(ΔΩ_half/2) = [sin²(θ_p/2) − sin²(Δi/2)] / (sin i_A sin i_B)`,

&nbsp;&nbsp;&nbsp;&nbsp;**`t_dwell = 2 ΔΩ_half / |ΔΩ̇|`,&nbsp;&nbsp;
`ΔΩ_half = 2 arcsin( sqrt( [sin²(θ_p/2) − sin²(Δi/2)] / (sin i_A sin i_B) ) )`**,

defined only when `|Δi| < θ_p` (otherwise the pair never becomes co-planar).
Worked, for a pair of i = 53.0° objects with `Δi = 0` at θ_p = 0.2°:
`ΔΩ_half = 2 arcsin(sin(0.1°)/sin 53°) = 0.2505°`, so
`t_dwell = 0.5010° / |ΔΩ̇|` days.

Three consequences, each registered as a design constraint:

1. **A pair with a small enough differential nodal rate produces a ≥ D-day
   chance co-planar window.** Setting `t_dwell ≥ D` gives
   `|ΔΩ̇| ≤ 2 ΔΩ_half / D`; at the numbers above and D = 30 d that is
   `|ΔΩ̇| ≤ 0.0167 deg/day`, which by §2.3's differential is an **altitude
   offset below 7.1 km** at 500 km. Objects in the same constellation shell sit
   well inside that. **Chance co-planarity within a shell is not rare, it is
   the normal state**, and the event definition must not count it: §4.3's prior
   separation criterion and §4.5's attribution exist for exactly this.
2. **The rate of chance co-planar windows for a pair is `2|ΔΩ̇|/360` per day**,
   which is the analytic null of §6.1 — derived per pair from each object's own
   measured Ω̇, never from a nominal rate.
3. **`ΔΩ̇ = 0` is a singular case** (identical shells): the pair is either
   permanently co-planar or permanently not. Those are **standing co-planar
   pairs**, counted separately and never events, in the manner of T8a's
   standing co-locations.

**This is where T8a's second failure is answered.** T8a derived a dwell bound
from a nominal quantity (distance from the nominal stable longitude) and it was
falsified 5/5. T8b's dwell bound is computed **per pair, from each object's own
Ω̇ fitted over its own history preceding the window** (§5.3) — and, because a
derivation is still not a validation, §10 gate G registers the validation it
must pass against held-out never-manoeuvred pairs before it is used to set
anything.

### 2.5 Phasing: cheap, fast, and the second half of the signature

Once the planes match, the objects must meet along-track. Differentiating
`n = sqrt(μ/a³)` gives `dn/da = −3n/(2a)`, so a semi-major-axis offset δa
produces a relative along-track angular rate

&nbsp;&nbsp;&nbsp;&nbsp;**`γ̇ = 360 · δn = −(3/2)(360 n / a) · δa` deg/day**, n in rev/day,

which at a = 6878.137 km (n = 15.2194 rev/day) is

&nbsp;&nbsp;&nbsp;&nbsp;**`∂γ̇/∂δa = −1.19487 deg/day per km`,&nbsp;equivalently
`−0.83691 km of δa per (deg/day)`.**

So 1 km of altitude offset sweeps 1.195 deg/day of relative phase — about
143 km/day of along-track displacement at that radius — and closing a 180°
phase angle takes 151 days at 1 km of offset or 1.5 days at 100 km. Combining
with §2.2, the phase-closing manoeuvre costs 0.553 m/s per km of δa and is
reversed for the same price.

**Phasing is cheap and fast; plane matching is expensive and slow.** The
registered consequence is §5.7: the lead time is expected to be dominated by
the plane-matching phase, and T8b measures the two phases separately so the
claim can be checked rather than assumed.

**The phase-confinement bound.** Holding the relative phase inside a band of
half-width Γ for D days requires, from the same relation,

&nbsp;&nbsp;&nbsp;&nbsp;**`|δa| ≤ Γ / (|∂γ̇/∂δa| · D)`**.

At Γ = 5° and D = 30 d in LEO: `|δa| ≤ 5 / (1.19487 × 30) =` **0.1395 km**.
This is a *derived consequence* of the event definition, not an independent
threshold, and it is how §8's screen is made cheap: the instrument sorts on a
and windows on it, and the window is provably admissive because any pair
violating it cannot satisfy §4.4.

### 2.6 The ΔV constants (stated once, computed for nothing)

§2.2's `ΔV_plane = 2 v sin(θ/2)` and `ΔV_intrack = (v/2)(δa/a)` are recorded so
that a reader can convert a published degree or kilometre figure if they wish.
**T8b computes no ΔV, no propellant and no fuel figure for any object**, in
keeping with the commercial-civil-only overlay policy. The instrument carries
these two expressions in a module docstring and in no executable path, and a
registered test asserts that no event row contains a velocity field.

### 2.7 Why T8b cannot measure a miss distance, derived

Two circular orbits of radii r_A and r_B whose planes differ by any non-zero θ
intersect the same line of relative nodes twice per revolution. At those two
points the cross-track offset is zero by construction and the separation is
exactly `|r_A − r_B|`. **The minimum distance between the two orbit *rings* is
therefore `|r_A − r_B|`, independent of θ.** Whether the two *objects* are ever
simultaneously near a relative node is decided entirely by the fast angle
(mean anomaly), which advances at 15.2 rev/day in LEO — 5,479 deg/day — so a
one-second timing error is 0.063° of phase, i.e. 7.6 km of along-track
position.

A miss distance therefore demands positional accuracy that published two-line
elements do not carry. The public figures for SGP4-from-TLE accuracy are of
order one kilometre at epoch degrading by kilometres per day
<!-- cite: Vallado & Crawford, "SGP4 Orbit Determination", AIAA 2008-6770; Kelso, CelesTrak TLE accuracy notes -->,
and T8b additionally **measures the archive's own fit-to-fit scatter** (§5.2)
rather than trusting a literature figure. The registered consequence:

> **T8b's proximity scale is tens of kilometres, stated, and T8b's estimand is
> a co-orbital station — matched plane, matched altitude, bounded relative
> phase, sustained — not a close approach.** Sub-kilometre proximity is a
> declared blind spot (§9.1), not a negative result.

### 2.8 Regime-specific physics

- **MEO.** §2.1–§2.5 hold unchanged; only the numbers move. At the GPS radius
  `Ω̇ = −0.0387 deg/day`, so relative nodal cycles are ~25 years and chance
  co-planarity is correspondingly rare — but also means a pair that *is*
  co-planar stays co-planar for a long time, so the prior-separation criterion
  (§4.3) does almost all of the work there. `∂γ̇/∂δa = −0.0407 deg/day per km`
  at a = 26578 km, so phase confinement is far looser in δa than in LEO.
- **HEO.** The orbit plane is still exactly §2.1, and J₂ nodal regression still
  applies with `p = a(1 − e²)`, which for a Molniya orbit (a = 26308 km,
  e = 0.739, i = 63.4°) gives `Ω̇ = −0.152 deg/day`. Two eccentric orbits in
  the same plane are, however, **not** co-orbital unless their apsides also
  align, because the radius at a given argument of latitude differs. T8b
  therefore carries the **apsidal separation** `|Δω|` as a reported column for
  every HEO event and registers, in §9.4, that an HEO event with a large `|Δω|`
  is a plane coincidence and not a co-orbital station. The event definition is
  **not** changed for HEO — a single definition runs on all three regimes so
  the regime comparison of §1 item 4 is meaningful — and the `|Δω|` column is how a
  reader discounts the HEO rows.

---

## 3. Population, regimes and classes

### 3.1 Regime membership, evaluated per element set

From each element set: `n` from `mean_motion_q`, `e` from `eccentricity_q`,
`a = (μ/(2πn/86400)²)^(1/3)`, perigee altitude `h_p = a(1−e) − R_e`, apogee
altitude `h_a = a(1+e) − R_e`. Then, in this order:

1. `h_p < 100 km` → **decaying**, excluded from all analysis and counted.
2. `n ∈ [0.95, 1.05]` rev/day and `e ≤ 0.01` and `i ≤ 25°` → **near-GEO**,
   **excluded** — this is T8a's registered band verbatim, so the two
   catalogues cannot double-count.
3. `h_a ≤ 2000 km` → **LEO**. The 2000 km line is the conventional one and is
   used as a convention, not a law; §9.6 declares the regime edge as a blind
   spot.
4. `e ≤ 0.25` and `h_p ≥ 2000 km` and `a ≤ 0.95 a_GEO` → **MEO**
   (a_GEO = 42164.1696 km, §2 of T8a's registration).
5. everything else → **HEO** (eccentric orbits of every altitude, plus
   circular orbits above the near-GEO band).

An **object** enters a regime if it has at least one element set in it. Objects
move between regimes over their lives, and all analysis below is on the
regime *intervals*, never on whole object histories.

### 3.2 The time grid

All slow elements (a, e, i, Ω, ω) are evaluated on a **daily grid** per object,
taking the first element set of each UTC day. §0.2 establishes that this
discards little; §4.4 registers the occupancy and gap requirements that make
the discard explicit. Fast-angle quantities (§5.1) are **never** evaluated on
the daily grid: they are evaluated at element-set epochs only, because a
15 rev/day angle is aliased by daily sampling beyond recovery.

### 3.3 Classes and the registered scope

- **Payload class**: `object_type = 'PAYLOAD'`.
- **Catalogue-passive class**: `pipeline.orbit_events.PASSIVE_TYPES`
  (DEBRIS, ROCKET BODY), borrowed rather than restated so a later change cannot
  leave a divergent copy behind. **This is T8a's failed control and is retained
  only for comparison** (§3.4).
- `object_type` NULL or UNKNOWN: excluded from both and counted.

**Registered scope of the measurement**: **approachers are payload-class
objects; targets are the full catalogue in the same regime** — every object
with a regime interval, payload or not, live or dead, catalogued or debris.
Because an approach event requires an attributable plane-matching campaign
(§4.5), and because §8's compute budget is finite, the primary arm's approacher
set is further restricted by a rule registered **here, in advance**:

> **Arm M approachers** = payload-class objects with **at least one detected
> plane-type manoeuvre** (§5.4) anywhere in their history. An object with none
> cannot satisfy §4.5's arm-M criterion, so this restriction removes no
> admissible event; it is a compute economy, not a screen, and the instrument
> asserts the implication in a test.
>
> **Arm G approachers** (the geometry-only arm, whose purpose is the leak
> measurement of §6.2 and which therefore may **not** be restricted by
> manoeuvre history) = the full never-manoeuvred class (§3.4), plus a
> registered random sample of **2,000 payload-class objects per regime**,
> stratified proportionally by inclination band (10° bins) and altitude band
> (100 km bins at LEO, 1000 km at MEO/HEO), drawn with **seed 20260922**.
> Sampled exposure in object-days is reported next to every arm-G rate, and
> rates, never counts, are compared.

### 3.4 The control, FIXED: manoeuvre-history-based passivity

T8a's third failure was that its control inherited `object_type`, and the real
uncontrolled population is dominated by dead *payloads*, which the catalogue
labels PAYLOAD. T8b registers the control T8a's §10.3 said must be constructed:

> **Never-manoeuvred class** = objects with **zero detected manoeuvres of any
> kind — in-track or plane-type — over their entire archive history** per the
> detector of §5.4, subject to a minimum evidence requirement: **≥ 200 element
> sets and ≥ 365 days of archive span** in the regime, so that "no manoeuvre
> detected" means "looked at properly and found none" and not "barely
> observed". Objects failing the evidence requirement are excluded from the
> control and counted.

This class is defined by **measured behaviour over the object's own history**
and by nothing else. `object_type` does not enter it. A dead payload lands in
it, which is the point; a manoeuvring rocket body (they exist — upper stages
perform disposal burns) is kept out of it, which is also the point.

Three populations are reported side by side, and their **overlap is the direct
measurement of the size of T8a's contamination**:

| Reported population | Definition |
|---|---|
| `never_manoeuvred` | §3.4 above — **the control** |
| `catalogue_passive` | `object_type ∈ PASSIVE_TYPES` — T8a's failed control, for comparison only |
| `payload_manoeuvring` | payload class with ≥ 1 detected manoeuvre |

Registered cross-tabulation, reported whatever it says: the count of
payload-class objects in `never_manoeuvred` (T8a's invisible dead payloads),
and the count of `catalogue_passive` objects **not** in `never_manoeuvred`
(catalogue-passive objects that did manoeuvre).

Country, object type, name, `object_id` and launch date are attached to every
event row as metadata. **No detector branch reads any of them except
`object_type`, and only to assign the payload/catalogue-passive labels above.**
A registered test asserts this by source inspection, as T8a's does.

---

## 4. The registered event definition

For an ordered pair (A, B) of objects with overlapping regime intervals in the
same regime, and with the daily grid of §3.2:

- `θ(t)` = plane separation (§2.1), from both objects' gridded (i, Ω);
- `γ(t)` = relative along-track angle, evaluated **only** at element-set epochs
  per §5.1;
- `δa(t)` = semi-major-axis difference.

### 4.1 The event, in words

**A T8b approach event is a plane-matching campaign, followed by phasing,
followed by a sustained co-orbital station**, attributable to one of the two
objects, and — in the primary arm — corroborated by that object's own detected
manoeuvres.

### 4.2 The registered scales, and their honesty statement

All thresholds are registered as **angles**, because the instrument's estimands
are angular; the kilometre figures beside them are the linear scales at
r = 6878.137 km (a 500 km LEO orbit) and are stated so that the honesty
requirement is legible:

| Symbol | Meaning | **Primary** | Linear scale at 500 km | Sensitivity arms |
|---|---|---:|---:|---|
| `θ_p` | plane matched | **0.2°** | 24.0 km cross-track | 0.05°, 0.1°, 0.5°, 1.0° |
| `Γ` | relative phase confined, half-width | **5.0°** | 599.5 km along-track | 1.0° (120 km), 0.2085° (25.0 km) |
| `D` | dwell | **30 d** | — | 14 d, 60 d |
| `θ_far` | prior plane separation | **5.0°** | 599.5 km | — |
| `Γ_far` | prior phase separation | **60°** | 7194 km | — |
| `T_look` | look-back | **1095 d** | — | — |

**The honesty statement, registered in these words and required verbatim in the
results document**: *T8b's primary arm finds pairs whose orbit planes agree to
0.2° and whose along-track phase stays inside ±5° for at least 30 days. At a
500 km LEO altitude that is a box roughly 24 km across-track, 600 km
along-track and — by §2.5's phase-confinement bound — 0.14 km in altitude.
That is a co-orbital station, not a close approach, and no figure in this
document is a miss distance.*

The tightest registered arm, Γ = 0.2085° = 25.0 km along-track, is the closest
T8b goes, and §2.5 gives its implied altitude tolerance: 7.0 m at D = 30 d,
which is at or below what public elements resolve. §10 gate A decides whether
that arm is reportable at all.

### 4.3 Criterion 1 — prior separation

At some epoch in `[t_a − T_look, t_a]`, **either** `θ ≥ θ_far` **or**
`|γ| ≥ Γ_far`. A pair that was never separated in plane **and** never separated
in phase inside the look-back is a **standing co-orbital pair** (§2.4
consequence 3): it is counted separately, reported, and is never an event.
Standing pairs are the crowding denominator the null of §6.1 is drawn from,
exactly as T8a's standing co-locations were.

### 4.4 Criterion 2 — the dwell

A contiguous interval `[t_a, t_e]` of length ≥ **D** over which, at every
retained epoch, `θ(t) ≤ θ_p` **and** `|γ(t)| ≤ Γ`, containing at least
`0.4 · (t_e − t_a)/1 d` retained element-set epochs of the approacher, with no
internal gap longer than **5 days** in either object's element series.
Interpolation of the slow elements is refused across any gap longer than 5 days
and those epochs are dropped and counted; the fast angle is never interpolated
(§5.1).

The 0.4-per-day occupancy and the 5-day gap bound are taken from the measured
sampling geometry of §0.2 and from nothing else, exactly as T8a's were.

### 4.5 Criterion 3 — the campaign, and attribution

Let `t_0` be the last epoch before `t_a` at which criterion 1 was satisfied.
Over `[t_0, t_a]`:

**(a) The closure must be attributable to A**, by a counterfactual that models
the natural J₂ dynamics explicitly — because §2.4 established that planes drift
together by themselves, and an attribution rule that ignores that would credit
J₂ to a satellite.

> For each object, construct the **no-manoeuvre counterfactual plane**: from
> that object's state at `t_0`, propagate `i` as constant and `Ω` at the
> secular rate `Ω̇` predicted by §2.3 from **that object's own measured
> (a, e, i) at t_0**, to `t_a`. Let `θ_noA(t_a)` be the plane separation that
> would have obtained had A followed its counterfactual while B evolved as
> observed, and `θ_noB(t_a)` the mirror image.
>
> Write the total closure `C = θ(t_0) − θ(t_a)` and the closure attributable to
> A as `C_A = θ_noA(t_a) − θ(t_a)`, and likewise `C_B`.
>
> **A is the approacher iff `C > 0` and `C_A ≥ 0.8 C`.** If both `C_A ≥ 0.8 C`
> and `C_B ≥ 0.8 C`, the pair is recorded with `attribution: "ambiguous"` and
> is excluded from every headline. If neither reaches 0.8 C, the closure was
> J₂'s and the pair is recorded as `attribution: "natural"` and is **not an
> event** — it is counted, and its count is one of the headline numbers of
> §6.1.

The 0.8 bar is T8a's, reused unchanged so the two pilots are comparable.

**(b) Phasing.** The relative phase rate `|γ̇|` must be arrested: its median
over the last 10 days before `t_a` must be at most **0.2 ×** its maximum over
`[t_0, t_a]`. This is the registered operational form of "the approacher
stopped the along-track drift"; the factor 0.2 is a screen, not a law, and it
is reported with the distribution of the ratio so a reader can see where it
cut.

**(c) Manoeuvre corroboration — arm M only.** A has at least one **confirmed**
detected manoeuvre (§5.4) with epoch in `[t_0, t_a]`, of which at least one is
**plane-type** if `C > θ_p` (i.e. if a plane change was actually required).
Arm G omits this criterion entirely and records its value as a column.

### 4.6 Criterion 4 — departure (recorded, not required)

The first epoch after `t_e` at which criterion 1's separation test is satisfied
again, or `null` if the archive ends first or it never happens.

### 4.7 The two arms, and what each is for

| Arm | Criteria | Purpose |
|---|---|---|
| **M** (primary) | 1, 2, 3(a), 3(b), 3(c) | The event catalogue and every headline. |
| **G** (geometry only) | 1, 2, 3(a), 3(b) | The leak measurement (§6.2) and the null (§6.1). Its yield on the never-manoeuvred control is the number gate B reads. |

**A registered warning against a tautology.** In arm M the never-manoeuvred
control's yield is **zero by construction**, because criterion 3(c) requires a
detected manoeuvre and the control is defined by having none. That is a
definitional property and it is **not** evidence that arm M is clean. Arm M's
validation is therefore §6.3's two measurements — the manoeuvre detector's own
false-alarm rate, and the time-shuffled corroboration control — and the results
document is required to say, in these words, that *the never-manoeuvred yield
in arm M is zero by construction and validates nothing.*

---

## 5. Estimators

### 5.1 The relative along-track angle γ, and the fast-angle rule

`γ` is the angle between the two objects' position directions:
`cos γ = r̂_A · r̂_B`, with

&nbsp;&nbsp;&nbsp;&nbsp;`r̂ = R_z(Ω) R_x(i) R_z(ω + ν) x̂`,

ν the true anomaly from the mean anomaly M by Kepler's equation
(Newton iteration to 1e-12 rad; for `e ≤ 0.01` the equation-of-the-centre
series `ν = M + 2e sin M + (5/4)e² sin 2M` is used and its agreement with the
Newton solution is asserted by a registered test).

**The fast-angle rule, registered because daily sampling cannot carry a
15 rev/day angle**: γ is evaluated **only at an element-set epoch of the
approacher**, with the target's elements taken from **its own nearest element
set within 1.0 day** and its mean anomaly advanced from that set by its own
mean motion over that sub-day interval. If no target element set lies within
1.0 day of the approacher's epoch, **γ is not computed at that epoch, the epoch
is dropped, and the drop is counted.** γ is never interpolated across a longer
gap and never evaluated on the daily grid. Registered bound on the residual
error: an error δn in mean motion over a gap Δt gives `360 δn Δt` degrees of
phase; at Δt = 1 d and the measured mean-motion scatter of §5.2 this must come
back below `Γ/10` or §10 gate A fires.

### 5.2 The two calibrated quantities, and how they are calibrated

Their values are unknown at registration time. They are properties of the
archive's *fit noise*, not of any approach event, and no event definition in §4
depends on them — they enter only §5.4's detector floors and §10's gates.

- **`σ_θ`** — the plane-direction fit noise. Over element-set pairs consecutive
  in time within a **quiet segment** (§5.3), the angle between the two orbit
  normals is computed and the **second difference** is taken, which annihilates
  any smooth secular rotation and leaves fit-to-fit scatter. `σ_θ` is the
  median absolute deviation of that second difference scaled by 1.4826/√6 to a
  per-sample σ, pooled per regime. Its p95 is also reported.
- **`σ_n`** — the mean-motion fit noise, per regime, by the same construction
  on the second difference of `n` inside quiet segments (the second difference
  annihilates the secular drag trend as well as any constant offset), scaled by
  1.4826/√6. Reported both in rev/day and, through §2.5, in kilometres of δa
  and degrees/day of γ̇.

Both are **pooled by object first, then across objects** (median of per-object
medians), because objects contribute wildly unequal numbers of element sets and
pooling over element sets would let one Starlink satellite outvote a thousand
others — the clustering defect `docs/matched-filter-design-20260922.md` §5.2(b)
registers against.

### 5.3 Quiet segments, and the own-history rule

A **quiet segment** of an object is a contiguous interval of ≥ 60 days over
which the object's residuals from its own local secular model are within the
model's own scatter — operationally: no detected manoeuvre (§5.4) using a
provisional floor of `5 × ` the running MAD, iterated once. Quiet segments are
used for calibration (§5.2) and for fitting each object's **own** secular rates:

> **`Ω̇_own`, `i̇_own` and `ṅ_own` are fitted per object over its own history,
> by Theil–Sen slope over a trailing window, and every bound, floor, and
> counterfactual in this document that needs a rate uses the object's own
> fitted rate. No nominal rate at a nominal altitude enters any threshold.**
> This sentence is the registered form of T8a's second failure not being
> repeated.

The J₂ prediction of §2.3 is used in exactly one place — §5.4's plane-manoeuvre
detector, as the *model* whose residual is tested — and there it is evaluated
from the object's own measured (a, e, i) at each epoch, never from a regime
nominal.

### 5.4 The manoeuvre detector (registered, simple, own-history)

Two channels. Both require **two consecutive confirming element sets**, so a
single bad fit cannot fire either; the flag time is the epoch of the **second**
set, because that is the first instant a causal observer possessed the
evidence. This is T8a's §5.5 rule, reused unchanged.

**In-track channel.** LEO has drag, so the baseline is not flat. The statistic
is the residual of `n(t_k)` from a Theil–Sen fit over the preceding 10 element
sets of the same object, which removes the local drag trend. A flag fires when

&nbsp;&nbsp;&nbsp;&nbsp;`|residual| > max(5 σ_n,&nbsp; 3 · |ṅ_own(t_k)| · Δt_k,&nbsp; n_floor)`,

with `Δt_k` the local epoch spacing. The middle term is the **own-drag term**
and it is the anti-repeat of T8a's failure: an object's own measured decay rate
sets its own floor, so a fast-decaying object is not flagged for decaying. The
third term, `n_floor`, is derived rather than chosen: it is the mean-motion
change corresponding to `δa = 0.050 km` at the object's own a, i.e.
`n_floor = 1.5 n · 0.050 / a` — 50 m of semi-major axis, below which a change
cannot be called deliberate at TLE quality and which by §2.5 is 0.060 deg/day
of relative phase in LEO.

**Plane channel.** Two sub-statistics, either of which fires the flag:
`|Δi|` between consecutive element sets exceeding `max(5 σ_θ, i_floor)`, and
the residual of the observed `ΔΩ` from the J₂ prediction of §2.3 evaluated at
the object's own (a, e, i), exceeding `max(5 σ_θ, i_floor)` over the same
interval. `i_floor` is registered at **0.01°**, which is the TLE's own
published resolution for inclination and RAAN and is therefore a resolution
floor, not a taste.

**A manoeuvre is plane-type if the plane channel fired, in-track if the in-track
channel fired; both may fire at one epoch.**

### 5.5 Campaign assembly and the initiating manoeuvre

For an event, the **campaign** is the set of confirmed manoeuvres of the
approacher inside `[t_a − T_look, t_a]`. Its **initiating manoeuvre** is the
earliest confirmed manoeuvre of the campaign that is **contiguous** with it,
where contiguity is defined as: no gap longer than **180 days** between
consecutive campaign manoeuvres. (T8a's "last flag before t_0" rule is *not*
reused, because in LEO the campaign is the slow J₂ drift *between* two
manoeuvres and the interesting instant is the first one, not the last. The
change is registered here with its reason, before any number exists.)

### 5.6 Lead times

Three, all recorded per event; the first is the headline:

- **`lead_causal = t_a − t_confirm(initiating)`** — from the confirmation of
  the initiating manoeuvre to arrival. **THE headline.**
- `lead_ideal = t_a − t_first(initiating)` — from the first changed element set.
- `lead_plane_match = t_a − t_plane` — from the first epoch at which
  `θ ≤ θ_p` was achieved to the arrival. This isolates the phasing phase and,
  with `lead_causal − lead_plane_match`, isolates the plane-matching phase, so
  §2.5's expectation (the plane phase dominates) is measured rather than
  assumed.

`lead_causal ≤ 0` is possible and is reported as such, never dropped. Events
with no initiating manoeuvre inside the look-back are reported as
`lead_causal: null` **with their count and inside every denominator**;
suppressing them would inflate the headline, as T8a registered.

### 5.7 Censoring: the survival curve is primary

T8a's undeclared blind spot was that its 180-day look-back truncated the
lead-time distribution. T8b registers:

> **The primary presentation of lead time is a Kaplan–Meier survival curve of
> `lead_causal`, with events whose initiating manoeuvre is absent from the
> 1,095-day look-back treated as right-censored at 1,095 days.** Percentiles
> are reported as secondary and are labelled with the fraction of the sample at
> or beyond 1,050 days. §10 gate F fires if that fraction exceeds 20%, and then
> percentiles are withdrawn and only the curve is reported.

### 5.8 Precision — the unflattering half, registered so it cannot be omitted

Every confirmed **plane-type** manoeuvre of a payload-class object that begins a
campaign closing at least `θ_far − θ_p` of plane separation against *any*
object is a **plane-change alert**. T8b reports the fraction of plane-change
alerts that end in a §4 arm-M event — the precision of the hypothetical
service — alongside the lead time, with a Wilson 95% interval. A long lead time
at a low precision is not an early-warning capability, and the results document
is required to say so in those terms if that is the outcome.

---

## 6. Nulls and controls

### 6.1 The J₂-chance-co-planarity null (the primary null)

Two forms, both registered, both reported:

**(a) Analytic, derived per pair from measured rates.** By §2.4, a pair with
`|Δi| < θ_p` produces chance co-planar windows at rate `2|ΔΩ̇|/360` per day,
each of dwell `2ΔΩ_half/|ΔΩ̇|`; the expected number of windows of dwell ≥ D over
an exposure E days is

&nbsp;&nbsp;&nbsp;&nbsp;`E · (2|ΔΩ̇|/360) · 1[ 2ΔΩ_half/|ΔΩ̇| ≥ D ]`,

with `ΔΩ̇` computed from **each object's own fitted `Ω̇_own`** (§5.3). Summed
over all screened pairs this is the derived expectation for arm G's yield in
the absence of any manoeuvre. It is reported against the observed arm-G yield.

**(b) Empirical, crowding- and stratum-matched.** T8a's permutation shape,
stratified because LEO's crowding is structured (sun-synchronous shells,
constellation shells) in a way GEO's is not:

> **1,000 permutations, seed 20260922.** Each real arrival (approacher, `t_a`,
> and the approacher's **entire element history preserved exactly**) is
> re-assigned a target drawn uniformly from the objects present at that epoch
> **within the same stratum** — stratum = (regime × inclination band 10° ×
> altitude band 100 km at LEO / 1000 km at MEO and HEO) — and the §4 criteria
> are re-applied by the identical code. Only the target changes; the crowding,
> the shell structure and therefore the natural differential-J₂ dynamics are
> preserved. Strata with fewer than 10 candidate targets at an epoch are
> **labelled gaps**, never zeros, with their weight stated, in the manner of
> `docs/matched-filter-design-20260922.md` §5.2(a).

Reported: observed against the null mean and its 95% interval, per regime, for
the primary arm and every sensitivity arm, in both arms M and G.

### 6.2 The never-manoeuvred control (arm G)

The identical detector, unchanged, on the never-manoeuvred class of §3.4,
compared **per unit exposure in object-days**, never as raw counts, with a
Wilson 95% interval on each rate and on the ratio.

**Registered expectation, stated before the measurement**: §2.4 derives that
chance co-planarity is *certain* for any pair with `|Δi| < θ_p` and a small
enough differential nodal rate. **Arm G is therefore expected to leak, and gate
B is expected to fire.** Registering that in advance is the point: arm G is not
a candidate event catalogue, it is the instrument by which the leak is
*measured*, and its leak rate is the number that says how much of a
geometry-only LEO proximity claim is J₂.

Reported separately for the never-manoeuvred class and the catalogue-passive
class, because the difference between those two rates is the direct measurement
of how wrong T8a's control was.

### 6.3 The two validations of arm M

Registered because §4.7 warns that the never-manoeuvred yield in arm M is zero
by construction and validates nothing.

**(a) The manoeuvre detector's own false-alarm rate.** §5.4's detector is run
over the whole never-manoeuvred class **as re-derived with a one-object
hold-out** — i.e. the class membership is defined from all objects except the
one being tested, and the tested object's flags are then counted — and the flag
rate per object-year is reported per regime, with a Jeffreys interval where
`scipy` is available and a Wilson interval otherwise (T8a found `scipy` absent
on `pc` and this registration inherits the fallback). A detector whose
false-alarm rate is comparable to the real campaign rate cannot corroborate
anything, and §10 gate H says so.

**(b) The time-shuffled corroboration control.** Arm M is re-run with each
approacher's **manoeuvre epochs shifted by a random offset** drawn uniformly
from ±T_look (seed 20260922, 200 draws), preserving each object's manoeuvre
*rate* and *type mix* exactly while destroying the causal link between its
manoeuvres and the closure. If the shuffled arm-M yield is inside the 95%
interval of the real arm-M yield, **the corroboration criterion is decorative
and the results document must say so** (§10, gate B′).

### 6.4 Standing co-orbital pairs

Reported as a separate count per regime (§4.3). They are not events and are in
no headline; their number is the crowding measurement the §6.1(b) null is drawn
from, and at LEO it is expected to be dominated by constellation shells.

---

## 7. Estimands, stated as a list

Per regime (LEO, MEO, HEO), primary arm and every sensitivity arm:

1. Event count, distinct approachers, distinct targets, distinct arrivals;
   counts of `ambiguous` and `natural` attributions; standing co-orbital pairs.
2. Distributions (p5/p25/median/p75/p95/max) of: dwell duration, closest plane
   separation during the dwell, median plane separation during the dwell,
   closest and median `|γ|`, implied `|δa|`, campaign duration, plane-closure
   magnitude `C`, and for HEO additionally `|Δω|`.
3. **Lead time**: Kaplan–Meier curve of `lead_causal` (primary), percentiles
   (secondary, labelled), and the `lead_plane_match` split that separates the
   plane phase from the phasing phase.
4. **Precision** (§5.8) with Wilson intervals.
5. The null comparison (§6.1 a and b), the control comparison (§6.2), and both
   arm-M validations (§6.3).
6. The class cross-tabulation of §3.4.
7. Repetition, reported at the **count level only**: approachers with ≥ 2, ≥ 3,
   ≥ 5 events and with ≥ 2 distinct targets, against the §6.1(b) null.
   T8a measured leave-one-out predictive skill of +0.137 and +0.008 and
   concluded the point prediction is weak; T8b does **not** re-run the ICC and
   leave-one-out machinery, and registers that omission here rather than
   silently dropping it.
8. Worked named examples: **factual timelines only** — dates, elements,
   manoeuvre epochs, angles — with no interpretation of purpose, and with the
   contaminated cases included deliberately so the failure modes are visible,
   as T8a's §8 did.

---

## 8. Compute, provenance and reproducibility

### 8.1 The screen, and why it is provably admissive

The plane-separation screen runs on a **coarse time grid of step `D/2`**. The
admissibility is a counting argument, not an approximation: criterion 2
requires `θ ≤ θ_p` continuously over an interval of length ≥ D, and any
interval of length D contains at least `⌊D/(D/2)⌋ = 2` grid points. **A screen
that keeps every pair with `θ ≤ θ_p` at one or more grid points therefore
cannot reject an admissible event**, with no inflation of the threshold at all.
At the primary D = 30 d the grid step is 15 days, reducing the ~24,700-day
archive span to ~1,650 screening epochs; the D = 14 d arm uses a 7-day step.

Two further screens, both provably admissive, applied per screening epoch
before any θ is evaluated:

- `|Δi| ≤ θ_p`, from §2.1's exact lower bound `θ ≥ |Δi|`;
- `|δa| ≤ 1.5 × Γ/(|∂γ̇/∂δa| · D)` from §2.5, generous by 1.5× so the screen can
  only admit, never reject.

Every survivor is then decided by the exact registered arithmetic of §4 on the
element-set epochs, never on the grid.

### 8.2 CPU versus GPU, measured

The screen is a sequence of small dense products — at each screening epoch,
`H_approachers (N_A × 3) · H_targets (3 × N_T)` followed by an on-device
reduction to "was θ ever below θ_p" — which is a shape a GPU may or may not
win, depending on how much of the cost is the reduction and the host transfer.
**T8b registers that this is measured and not assumed**, in the manner of
Phase 3:

> A fixed sub-problem — a registered contiguous slice of the screening grid and
> a registered subset of objects, both fixed here by rule (**the 200 screening
> epochs beginning at the median epoch of the LEO regime, all LEO objects alive
> throughout that slice**) — is run on CPU (NumPy, `nice`-d) and on GPU
> (CuPy through `/home/sdegan/gpu-broker/gpu-run` with an honest
> `--estimate-mib`, `--class standard`, **beside resident training, never
> deferring it**), and the winner by wall-clock runs the full screen. Both
> timings and the chosen path are reported; the GPU path is chunked to keep the
> device pool at or below **2 GiB** and the chunking is asserted by a test that
> computes the pool size from the chunk shape.

If the GPU path is chosen, the resulting lane is a one-off run ledgered by the
broker, not a recurring consumer; no `gpu-consumers.json` row is owed by a
one-off, and if T8b ever becomes a recurring lane its v7 row is owed in that
change.

### 8.3 Provenance

- `tools/proximity_plane.py`, stages `extract` / `screen` / `analyze` / `all`,
  on `pc`, `nice`-d. Read-only against the archive through
  `pipeline.orbit_campaigns.open_archive_for_reading` with
  `PRAGMA query_only=1`. Provenance recorded in the receipt: archive path,
  byte size, mtime, page count, `month_rollup` span and row total, the
  sequential-scan row total (which §0.1 shows disagrees with the rollup), plus
  SHA-256 of `tools/proximity_plane.py` and of every pipeline module it
  imports.
- Outputs: `docs/proximity-leo-events-20260922.jsonl` (one JSON object per
  event, with the metadata columns of §3.4),
  `docs/proximity-leo-20260922-receipt.json`,
  `docs/proximity-leo-results-20260922.md`. **Nothing is written to `src/`,
  `data/`, `public/` or any site surface.**
- Determinism: seed 20260922 for the permutation null, the arm-G sample and the
  time shuffle; no other randomness.
- Tests in `tests/test_orbit_proximity_plane.py` must cover, at minimum: the
  orbit-normal construction against a hand-computed case; the equivalence of
  the cosine and half-angle forms of §2.1; `θ ≥ |Δi|` with equality at ΔΩ = 0;
  the J₂ rate reproducing the sun-synchronous condition; `∂Ω̇/∂a` against a
  numerical derivative; the phase-confinement bound of §2.5 against a
  numerically integrated pair; the coarse-grid admissibility argument of §8.1
  on a synthetic dwell; a synthetic plane-matching campaign that must be
  detected; a synthetic J₂-only drift-together that must **not** be; a
  synthetic standing co-orbital pair that must not become an event; the
  attribution counterfactual on a synthetic pair where the *target* manoeuvred;
  the fast-angle refusal across a gap > 1 day; the never-manoeuvred class
  excluding an object with a synthetic burn; the GPU chunk-size bound; and the
  framing guards (no intent vocabulary in the module, no detector branch
  reading a registry code, no velocity field on an event row).

---

## 9. Declared blind spots

Stated now so that they cannot later be presented as findings.

1. **Sub-kilometre proximity is invisible, and T8b measures no miss distance**
   (§1.1, §2.7). The minimum distance between two similar-radius rings is
   `|r_A − r_B|` regardless of plane separation, and whether the objects are
   simultaneously there is decided by a 5,479 deg/day angle at TLE accuracy. A
   genuine conjunction instrument needs special-perturbations ephemerides
   (track T6).
2. **Continuous low-thrust plane changes are invisible or nearly so.** §5.4's
   detector is a *step* detector. A continuous electric-propulsion plane change
   produces a smooth, sustained departure of `Ω̇` and `i` from their J₂
   predictions with no step at any single epoch, and the Theil–Sen baseline
   will partly absorb it. T8b's arm M will therefore **miss** exactly the class
   of vehicle most capable of a cheap plane change, and its catalogue is a
   **lower bound on events, never a census**. The registered partial mitigation:
   the plane channel's Ω̇-residual sub-statistic is also evaluated over a
   **90-day** trailing window and reported as a separate `slow_plane_change`
   column, but it is **not** admitted as arm-M corroboration and no headline
   depends on it.
3. **Cadence and gaps.** The 5-day interpolation refusal and the 1-day
   fast-angle refusal (§5.1) convert gaps into dropped epochs, not into
   evidence. A manoeuvre-and-reverse inside a gap is invisible.
4. **Motion below the floors.** In-track changes below 50 m of semi-major axis
   and plane changes below 0.01° are undetectable by §5.4.
5. **Catalogue completeness.** Objects absent from the public catalogue,
   objects whose elements are withheld or degraded, and epochs before the
   archive's back-fill coverage are invisible. **Absence of an event is not
   evidence of absence of an approach.**
6. **The regime edges are conventions.** The 2000 km LEO ceiling, the e ≤ 0.25
   MEO/HEO line and the near-GEO exclusion band are conventions; objects near
   an edge change regime as their elements drift and are analysed in whichever
   regime their interval falls. Cross-regime events (an approacher in HEO
   closing on a target in LEO) are **not detected** and are declared out of
   scope here rather than reported as absent.
7. **HEO apsidal alignment is reported, not required** (§2.8): an HEO event
   with a large `|Δω|` is a plane coincidence, not a co-orbital station.
8. **The arm-G sample is a sample** (§3.3): its rates carry sampling
   uncertainty and its exposure is stated with every rate. Counts from arm G
   are never compared to counts from arm M.
9. **Screening scope.** The registered scope is active-payload approachers
   against the full catalogue. All-vs-all — including passive-on-passive pairs,
   which is where a genuinely unbiased chance-co-planarity measurement lives —
   is not done here and is §11's handoff.

---

## 10. Gates: what makes this study uninformative

Registered before any measurement. Each is a statement the results document
must make explicitly, in these words, if it fires.

**§10.0 The rule that decides a contradictory gate.** T8a's registration wrote
a formula and a number beside it that disagreed by 10×, and its results had to
be reported both ways. Every bar below is therefore stated as a **formula**
together with **its number evaluated in this document from the registered
primaries**. If a future reader finds any disagreement between the two, **the
formula governs**, and the results document reports both readings anyway.

| Gate | Registered meaning | Bar (formula) | Bar (evaluated here) |
|---|---|---|---|
| **A** | **the instrument is unfit** | `σ_θ(p95) ≤ θ_p/10` and `σ_n → |δa| ≤ (Γ/(kD))/10` and the §5.1 fast-angle residual `≤ Γ/10` | `σ_θ(p95) ≤ 0.02°`; `|δa|` noise `≤ 0.01395 km` (13.95 m); fast-angle residual `≤ 0.5°` |
| **B** | **the geometry arm leaks** | arm-G never-manoeuvred yield per object-day `> 0.10 ×` arm-G payload yield per object-day | ratio `> 0.10`. **Expected to fire** (§6.2) — the number it returns is the measurement |
| **B′** | **the corroboration is decorative** | time-shuffled arm-M yield inside the 95% interval of the real arm-M yield | as stated |
| **C** | **the null explains the catalogue** | arm-M observed count inside the §6.1(b) null's 95% interval, per regime | as stated. Not a failure of the study; it is the finding that LEO co-orbital stations are indistinguishable from stratum-matched crowding |
| **D** | **underpowered** | fewer than **20** arm-M events in LEO at the primary arm | as stated. Then every distribution is reported with its interval and labelled UNDERPOWERED, and no lead-time claim is made |
| **E** | **no lead time** | median `lead_causal ≤ 0`, or `lead_causal` null for `> 50%` of arm-M events | as stated. Then public elements do not support early warning for this event class and T8b says so; that is a publishable negative result |
| **F** | **the lead time is censored by its own window** | fraction of arm-M events with `lead_causal ≥ 1050 d` or right-censored `> 20%` | as stated. Then percentiles are **withdrawn** and only the Kaplan–Meier curve is reported |
| **G** | **the dwell bound is unvalidated** | more than **5%** of held-out never-manoeuvred pairs exceed their own-history chance-co-planarity dwell bound (§2.4, §5.3) | as stated. Then the bound is reported as falsified, **D is not justified by it**, and every statement that would have rested on it is withdrawn — the explicit non-repeat of T8a's §7.2 |
| **H** | **the manoeuvre detector cannot corroborate** | §6.3(a) false-alarm rate per object-year `≥ 0.5 ×` the measured campaign rate per object-year among payload approachers | as stated |

Any of these firing is reported in the results document's first screen. None of
them may be revised after a number exists.

---

## 11. The T5b handoff spec: what an HPC-scale version adds

Registered **before any T8b result exists**, so that the gap between what our
cards support and what a cluster would support cannot later be presented as a
finding. T8b at the registered scope (§3.3) measures active-payload approachers
against the full catalogue on a `D/2` grid at the thresholds of §4.2. A
cluster-scale T5b would add exactly four things, and nothing else:

1. **All-vs-all, including passive-on-passive.** The registered scope screens
   payload approachers only. The unbiased measurement of chance co-planarity —
   the empirical version of §2.4's derivation, on pairs where *neither* object
   can manoeuvre — requires every pair of the ~61,861 LEO objects, i.e.
   1.91e9 unordered pairs against the registered scope's much smaller
   approacher-by-catalogue product. This is the measurement that would turn
   §6.1(a)'s analytic null from a derivation into a validated one, and it is
   the single most valuable thing a cluster buys this track.
2. **A finer time grid, and therefore shorter dwells.** §8.1's grid step is
   `D/2`, so the minimum detectable dwell is the registered D. A cluster can
   afford a daily or sub-daily grid, which opens dwells of days rather than
   weeks — the regime in which a short rendezvous, as opposed to a sustained
   station, becomes visible.
3. **Finer thresholds, and the arm §4.2 could not afford.** The tightest
   registered arm (Γ = 0.2085°, 25 km) implies a 7.0 m altitude tolerance and
   may be unreportable under gate A. A cluster does not fix TLE accuracy — that
   needs T6's SP ephemerides — but it does afford the **full two-dimensional
   sweep of (θ_p, Γ, D)** rather than the registered one-at-a-time arms, which
   is what a threshold-stability claim actually requires.
4. **Per-object nulls instead of per-stratum nulls.** §6.1(b) borrows within a
   stratum. `docs/matched-filter-design-20260922.md` §5.3 measured that
   borrowing across objects failed by 9.3× in T3 and registers a three-rung
   ladder ending in per-object surrogates. T8b's null is the stratum rung by
   compute necessity; the per-object rung — each approacher's own window
   function, its own gap structure, its own shell — is a cluster ask, and its
   size is `B` surrogates × the registered screen.

What a cluster does **not** add, stated so the ask is honest: it does not make
T8b a conjunction instrument (§2.7 is a statement about the data, not the
compute), it does not make continuous low-thrust visible (§9.2 is a statement
about the detector's form), and it does not fill catalogue gaps (§9.5).

---

## 12. What is committed with this document

Nothing. This registration is committed **alone**. `tools/proximity_plane.py`,
its tests, the event catalogues, the receipt and
`docs/proximity-leo-results-20260922.md` all follow in later commits, and the
ordering in `git log` is the evidence.
