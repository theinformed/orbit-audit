# Pre-registration: measured transfer-loss fractions for catalogued commercial-civil orbit raising

Registered 2026-09-22, **before any loss fraction exists**. Track T10a of
`docs/research-program-runbook-20260921.md`. This document is committed alone,
ahead of every artifact T10a will produce, the same way
`docs/repricing-preregistration-20260921.md`,
`docs/phase3-preregistration-20260921.md` and
`docs/cadence-s1s2-preregistration-20260922.md` were committed ahead of their
results. The git history of this file is the timestamp. Nothing below may be
changed once a loss fraction exists; an awkward outcome is reported, not edited
away.

This document implements nothing and touches no source file. It registers the
derivations of the first-principles minima, the estimands, the event-selection
rule, the screens, the controls, the acceptance criteria that decide whether
the measurement may be called informative, the defect and stop rules, and — at
the front, because it decides what the whole study is worth — an explicit
statement of **which losses this instrument can and cannot see**.

The estate rule this track exists under: physics assumptions are not facts.
Every physical relation below is derived here or cited to its source. The
screens below are screens, not laws, and are labelled as such.

---

## 0. What this instrument can measure, and what it structurally cannot

T10's charter asks for "detected behavior vs first-principles ideal". The
detected behavior available here is a **sequence of two-line element sets**.
Differencing element sets gives the *achieved* orbit change across an interval,
and the cheapest impulse consistent with that change. Four consequences follow,
and three of them are limitations that must be stated before the estimand, not
after the result:

1. **Gravity loss is invisible.** A finite burn arc delivers less orbit change
   than the same impulse delivered instantaneously; the shortfall is the
   gravity loss. But the element sets record only the change that *was*
   achieved. The propellant that produced the shortfall left no trace in the
   elements. No TLE-differencing instrument can measure a gravity loss, and
   this one does not claim to.
2. **Steering loss within a burn is invisible**, for the same reason: the
   cosine loss of a mis-pointed thrust vector reduces the achieved element
   change, and the element change is all we see.
3. **Cheapest-impulse pricing is a lower bound per interval.** Both the
   numerator and the denominator below are built from the same
   minimum-impulse function, so the comparison is internally consistent, but
   neither side is the propellant the vehicle actually spent.
4. **What survives is the path.** A transfer executed as several burns with
   coast arcs between them traces a *path* through orbit-element space. The
   first-principles ideal is the *direct* transfer between the same endpoints.
   The excess of the path over the direct transfer is real, is caused by
   operational choices (how the apogee kick is split, how plane change is
   distributed across burns, whether a drift orbit is used to walk to an
   assigned longitude slot), and **is** measurable from element sets.

So the estimand of this track is the **path loss fraction**: how much more
delta-v the observed multi-burn transfer path costs than the direct
first-principles transfer between its own observed endpoints. It is not a
gravity-loss measurement and this document forbids calling it one.

A structural consequence, derived in §4.3 and registered now so it cannot be
presented later as a finding: **a transfer in which the detector found exactly
one burn interval has a path loss of exactly zero, by construction.** Such
phases carry no information about path loss and are excluded from the primary
distribution, with their count reported.

---

## 1. The first-principles minima, derived

Notation: `mu` = 398600.8 km^3/s^2 and `RE` = 6378.135 km, the WGS-72 values the
archive's element sets are fitted against
<!-- src: pipeline/orbit_history.py, MU_WGS72 / RE_WGS72 -->. An orbit state is
`(a, e, i)`: Kozai mean semi-major axis from the GP mean motion, eccentricity,
inclination. `r_p = a(1-e)`, `r_a = a(1+e)`.

### 1.1 Vis-viva, exactly, not to first order

For a two-body orbit of semi-major axis `a`, the speed at radius `r` is

    v(r, a) = sqrt( mu * (2/r - 1/a) ).                                  (1)

T2 shipped its primary pricing as the *differential* relation
`dv = mu da / (2 a^2 v)` and registered the exact finite-impulse form as a
screen; that screen measured the first-order relation overstating the
tangential cost by up to **127%** on the largest transfer events
<!-- src: docs/repricing-20260921.md, "The first-order screen found something larger than the burn point": n 4146, median 5.413e-05, max 1.26891595 -->.
This track therefore uses (1) directly everywhere. No first-order expansion
appears in any number this track publishes.

The transverse and radial components at radius `r` follow from the angular
momentum `h = sqrt(mu * a * (1 - e^2))`:

    v_t(r) = h / r,        v_r(r) = sqrt( max(0, v(r,a)^2 - v_t(r)^2) ).  (2)

### 1.2 One impulse between two orbits at a shared radius, with plane change

Let orbit A and orbit B share a radius `r` (i.e. `r` lies in
`[r_p, r_a]` of both) and let `di` be the angle between their planes. Put the
radius vector along `x`. In orbit A's plane the velocity is
`vA = (v_rA, v_tA, 0)`. Rotating the orbit plane about the radius vector by
`di` — which is the geometry when the burn is executed at the relative node —
carries orbit B's velocity to `vB = (v_rB, v_tB cos di, v_tB sin di)`.
The impulse is the vector difference, so

    dv^2 = (v_rB -/+ v_rA)^2
         + (v_tB cos di - v_tA)^2 + (v_tB sin di)^2
        = v_rA^2 + v_rB^2 -/+ 2 v_rA v_rB
         + v_tA^2 + v_tB^2 - 2 v_tA v_tB cos di.                         (3)

The sign choice is whether the burn happens on the ascending or descending
branch of each orbit; the minimum takes the matching branches, giving
`(v_rB - v_rA)^2`. At an apsis of both orbits `v_r = 0` and `v_t = v`, and (3)
collapses to the **combined-burn relation**

    dv^2 = vA^2 + vB^2 - 2 vA vB cos di,                                 (4)

the law of cosines on the velocity triangle. Equation (4) is the exact cost of
combining a speed change with a plane change in a single impulse, and it is the
reason a combined apogee kick beats a separate plane change: for small `di`,
`(4)` costs `|vB - vA| + (vA vB / (2|vB - vA|)) di^2 + O(di^4)`, i.e. the plane
change enters at **second** order, whereas a separate rotation costs
`2 vA sin(di/2)`, first order in `di`.

The single-impulse candidate is (3) minimised over `r` in the intersection
`[r_pA, r_aA] ∩ [r_pB, r_aB]`, when that intersection is non-empty.

### 1.3 Two impulses, apsis to apsis, with the plane change split optimally

Let the first impulse be at an apsis of orbit A at radius `r_A`, injecting into
a transfer ellipse of semi-major axis `a_t = (r_A + r_B)/2` whose other apsis is
at `r_B`, an apsis of orbit B; the second impulse at `r_B` circularises onto
orbit B. All four velocities are purely transverse (apsides of all three
orbits), so each impulse obeys (4). Splitting the total plane change `di` as
`d1 + d2 = di`:

    dv1(d1) = sqrt( vA1^2 + vt1^2 - 2 vA1 vt1 cos d1 )
    dv2(d2) = sqrt( vt2^2 + vB2^2 - 2 vt2 vB2 cos d2 )
    J(d1)   = dv1(d1) + dv2(di - d1)                                     (5)

with `vA1 = v(r_A, a_A)`, `vt1 = v(r_A, a_t)`, `vt2 = v(r_B, a_t)`,
`vB2 = v(r_B, a_B)`, all from (1).

**The combined-burn optimum.** Differentiating (5),

    dJ/dd1 = (vA1 vt1 sin d1) / dv1 - (vt2 vB2 sin d2) / dv2,

so the optimal split satisfies

    (vA1 vt1 sin d1) / dv1  =  (vt2 vB2 sin d2) / dv2.                   (6)

Equation (6) is the registered optimality condition: **the plane change is
split so that the marginal cost of an extra degree of rotation is equal at the
two burns.** Its qualitative content is the classical result — the burn where
the vehicle is moving slowly (the high apsis) should take almost all of the
plane change, because the marginal cost scales with the product of the two
speeds at that burn. It is solved numerically by bisection on `dJ/dd1` over
`[0, di]`, falling back to a golden-section minimisation of `J` if `dJ/dd1`
does not change sign on the interval (which happens when the optimum is at an
endpoint). The numerical solution is verified against (6) as a residual in the
per-event record, and against the closed forms in §6's tests.

### 1.4 The registered impulsive minimum

    DV_imp(A -> B, di) = min over the candidate family of
        { single impulse (3), minimised over shared radii, when one exists }
      ∪ { two-impulse (5) with the split (6), over the four apsis pairs
          (r_A in {r_pA, r_aA}) x (r_B in {r_pB, r_aB}) }.              (7)

This is a minimum over an **explicitly named restricted family**, not the
global impulsive optimum over all transfer geometries. It is therefore an
**upper bound** on the true minimum. Registered consequence for the direction
of bias: a denominator that is too large makes the measured loss fraction too
**small**, so this approximation biases the headline **downward** and the result
is a lower bound on this count as well as on the others in §7.

The family deliberately assumes **free burn geometry** — that an apsis may be
placed at the relative node. That is the textbook designer's ideal and what a
real GTO launch targets, so it is the right ideal to measure against; the price
of *not* achieving it is part of what the loss fraction is meant to contain.

### 1.5 Edelbaum's low-thrust minimum, derived and cited

For continuous low thrust the impulsive minimum is not the right ideal: a
low-thrust vehicle cannot deliver its delta-v at a single point, and the
correct first-principles floor is Edelbaum's.

Edelbaum (1961) treats a quasi-circular orbit under a constant-magnitude
acceleration `f` with out-of-plane yaw `beta`, the yaw sign reversed at the
nodes. Averaging over one revolution — the in-plane component works
continuously, the out-of-plane component's effect on inclination averages
`|cos u|` over the true argument of latitude `u`, whose mean is `2/pi` — gives

    dv/dt = - f cos beta,          di/dt = (2 / (pi v)) f sin beta,      (8)

with `v = sqrt(mu / r)` the local circular speed. Eliminating time,

    di / dv = - (2 / (pi v)) tan beta,

and optimal control of `beta` over the transfer integrates to the closed form

    DV_edel = sqrt( v0^2 + vf^2 - 2 v0 vf cos( (pi/2) di ) ),  di in rad. (9)

Source: T. N. Edelbaum, "Propulsion Requirements for Controllable Satellites",
*ARS Journal* **31**(8), 1079-1089, 1961. Equation (9) is quoted from that
result, not re-derived from the optimal-control problem here; the averaging
step (8) and the `2/pi` factor are derived above, and the `pi/2` inside the
cosine in (9) is Edelbaum's and is cited, not asserted as our own derivation.

**Two properties of (9) that this track uses and therefore states:**

* (9) is the **law of cosines** again, with the effective angle `(pi/2) di`.
  It is therefore the Euclidean distance between the points `(v0, (pi/2) i0)`
  and `(vf, (pi/2) if)` in a plane with those polar coordinates.
* Hence **Edelbaum's delta-v obeys the triangle inequality exactly**: the sum
  over a chain of sub-transfers is greater than or equal to the direct value.
  For the electric arm, therefore, the path loss fraction of §2 is
  **non-negative by construction**, and a negative value is a defect, not a
  finding (§8, D1).

Equation (9) is a **circle-to-circle** result. The circular radius used at each
state is that state's semi-major axis `a`, so `v = sqrt(mu/a)`; this is exact
for a circular orbit and is the registered approximation for a near-circular
one. It is applied only where every state in the phase is near-circular; the
screen is registered in §3.4 (S5).

---

## 2. Estimands

### 2.1 The unit: a transfer event

A **transfer event** is one object's orbit-raising phase. A **burn interval**
is one detected event inside it. The construction is in §3.

### 2.2 Primary estimand — the path loss fraction

For transfer event `T` with burn intervals `k = 1..K`, each with an archive
element state before (`s_k^-`) and after (`s_k^+`), and phase endpoints
`s_0 = s_1^-` and `s_1 = s_K^+`:

    N(T) = sum over k of  DV_class( s_k^- -> s_k^+ )        (numerator)
    D(T) = DV_class( s_0 -> s_1 )                           (denominator)
    L(T) = N(T) / D(T) - 1                                  (loss fraction)

`DV_class` is `DV_imp` from (7) for the chemical class and `DV_edel` from (9)
for the electric class, chosen by the catalogue's `raising_propulsion` entry
(§3.3). **Both sides use the same function**, so `L` is a pure path-versus-
direct comparison inside one physical model and carries no pricing-convention
difference.

`L` is reported as a fraction and as a percentage. Its absolute companion,
which is the number a mission designer actually spends, is reported beside it:

    X(T) = N(T) - D(T)            the excess delta-v, m/s
    M(T) = m_launch * ( exp(-D/(g0 Isp)) - exp(-N/(g0 Isp)) )     kg      (10)

with `g0 = 9.80665` m/s^2, `Isp` at both edges of the catalogued raising-leg
Isp band, and `m_launch` the catalogued launch mass. (10) is the rocket
equation applied to the same launch mass at the two delta-v values and
differenced; it is reported only for objects carrying `launch_mass_kg`, as a
band, never as a point.

### 2.3 Distributions and population statistics

* Per-event `L`, `X`, `M`, published for every transfer event in the JSONL.
* The distribution of `L` **by propulsion class** (chemical, electric), and
  **by vehicle family** where the catalogue names a `bus`, grouped on the bus
  string's platform prefix (registered normalisation: upper-case, strip
  trailing variant tokens after the last hyphen only when the remaining prefix
  still has at least four characters, e.g. `BSS-702SP` -> `BSS-702`,
  `SSL-1300` -> `SSL-1300`). Families with fewer than 5 transfer events are
  reported with their count and no summary statistic.
* **Population medians with bootstrap confidence intervals**: non-parametric
  bootstrap resampling transfer events with replacement, `B = 10000`,
  percentile 95% interval, **seed 20260922**, on the median of `L` and on the
  median of `X` for each class and for the pooled population.

### 2.4 Secondary estimands, reported but not primary

* **Loss against burn count.** `L` as a function of `K`, the number of detected
  burn intervals in the phase: medians per `K`, and a Theil-Sen slope of `L` on
  `K` with its bootstrap interval. Descriptive, explicitly not a significance
  claim, because `K` is a detection outcome as well as an operational choice.
* **The drift-orbit component.** For GEO-class transfer events, whether the
  path overshoots the final semi-major axis (`max_k a(s_k^+) > a(s_1)` by more
  than the band noise floor of §5.1) — the signature of a deliberate drift
  orbit walked to an assigned longitude slot — and the median `X` of phases
  with and without it.
* **Per-event pricing conservatism.** For each burn interval, the shipped
  detector's own priced total from T2's event set divided by
  `DV_imp(s_k^- -> s_k^+)`. This measures the production pricing's
  conservatism per interval and is the generalisation of T2's 127% first-order
  screen. It is a detector audit, not a fuel measurement, and is labelled so.
* **The raising-signature-only variant** of `N` (§3.2), as a sensitivity.
* **The endpoint-median variant** of `s_0` and `s_1` (§5.2), as a sensitivity.

### 2.5 What is NOT touched

Registered now so it cannot be relaxed later:

* **Detection.** The event set is T2's, frozen and hashed (§3.1). No detector
  runs in this track. No detection threshold, screen, gate or label is changed.
* **The production sweep, the published site artifacts, the published event
  list, and every published control block.** This track produces dated analysis
  artifacts only.
* **Paper A and Paper B.** Both are published with DOIs. Nothing in this track
  edits either. If a number either paper quotes is contradicted here, the
  contradiction is reported in this track's results document and the papers are
  left alone pending an operator decision.
* **The fuel odometer's frozen rules 1-8**, including the 2,500 m/s
  own-propulsion ceiling and the launch-date rule, are reused unmodified
  <!-- src: tools/fuel_odometer.py docstring, rules frozen 2026-09-20 -->.
* **Government and military objects.** The population is
  `data/propulsion-catalog-v1.json`, whose own `policy` field is
  `"commercial-civil-only"`. No object outside that file is read, priced or
  named, and no fuel quantity is inferred for any object outside it.

---

## 3. Population, event selection, and inputs

### 3.1 Inputs, hashed before the run

| Input | Path | sha256 |
| --- | --- | --- |
| Detected event set (T2's run) | `/tmp/t2-repricing-20260921/events.jsonl.gz` | `6804c147596fdf2c78c1c6671a97f8037bcd33202dac785db85aac943d49e66f` |
| Archive snapshot, read-only | `/tmp/eol-study-20260920/archive.sqlite3` | `ffc4c4e521ca0c4eb78d5ec48039e8c9032e2f05183e5b3f09fe703bc5b734c3` |
| Propulsion catalogue | `data/propulsion-catalog-v1.json` | `7f7a50bc4dff644705f52ec28fb2c52a7f8589c7be45433a7f4c23dcc72711a9` |

The event-set hash is the value T2's **committed** receipt records as
`detectionReceipt.extractionSha256`
<!-- src: docs/repricing-20260921-receipt.json -->, so the input to this track
is cryptographically tied to a committed artifact even though the extraction
itself lives in a scratch directory. The archive hash is the one T2's
registration §3 fixed. **All three are verified at run time and a mismatch is a
stop (§8).** The archive is opened `mode=ro` and the run asserts it.

### 3.2 The event-selection rule

Reusing T2's event set and the odometer's frozen leg rule, with no re-detection:

1. **Cohort.** Every catalogue object carrying a NORAD id, a `launch_date` and
   a `raising_propulsion` entry.
2. **Raising-leg intervals.** A detected event is on the raising leg when its
   start is at or before 18 months after the catalogued launch date **and** its
   signature is one of `orbit-raising`, `along-track-raise`,
   `inclination-change`. This is the odometer's rule, reused verbatim
   <!-- src: tools/fuel_odometer.py, RAISING_WINDOW_MONTHS = 18, RAISING_SIGNATURES -->.
3. **Phase window.** `t0` = earliest start among the object's raising-leg
   intervals; `t1` = latest end among them.
4. **Burn intervals of the phase.** *Every* detected event of that object whose
   interval lies entirely within `[t0, t1]` — not only the raising-signature
   ones. A path must be tiled to be compared with a direct transfer, and a
   station-keeping-signature interval inside the transfer window is part of the
   path. The raising-only variant is reported as a sensitivity (§2.4).
5. **Exclusions, from the odometer's frozen rules.** Any interval the odometer
   excludes as not the satellite's own propulsion — a shipped priced total above
   2,500 m/s, or a start before the catalogued launch date — is removed from the
   phase before `N` is formed, and its removal is recorded per event.
6. **Graveyard raises are out of scope.** `geo-graveyard-raise` is an
   end-of-life manoeuvre, not an orbit-raising transfer, and belongs to the EOL
   lane. Such events are excluded from phases and counted.

### 3.3 Class assignment

Chemical or electric is read from the catalogue's `raising_propulsion` entry
using the odometer's own test — the type or thruster model string containing
any of `electric`, `ion`, `hall`, `plasma`, `xips`, `spt`, `pps`, `arcjet`
<!-- src: tools/fuel_odometer.py, electric() -->, widened here from the
odometer's two-token test to this list and recorded per object so the
assignment is auditable. Any object whose class cannot be read is excluded and
counted.

### 3.4 Screens, all of them registered here

| Screen | Rule | Why it is a screen and not a law |
| --- | --- | --- |
| **S1 multi-burn** | The phase must contain at least 2 surviving burn intervals | §4.3 proves `L = 0` identically for `K = 1`; such phases carry no information |
| **S2 magnitude** | `D(T)` >= 100 m/s | A transfer must be a transfer. This cohort's genuine full apogee kicks cluster at 1,430-1,502 m/s <!-- src: docs/fuel-odometer-20260920.md, "the largest genuine single burns in this cohort cluster at 1,430-1,502 m/s" -->; a 100 m/s floor admits partially observed transfers and electric-spiral fragments while excluding station-keeping-scale phases. An operating point, not a physical boundary |
| **S3 raise direction** | `a(s_1) > a(s_0)` | This track measures orbit *raising* |
| **S4 endpoint coverage** | Both endpoint states are element sets the detector itself used as interval boundaries | Guarantees the endpoints are inside T2's screens rather than newly chosen by this track |
| **S5 Edelbaum validity** | Electric arm primary only where `max(e(s_0), e(s_1), e over the path) <= 0.05` | (9) is a circle-to-circle result; outside the screen the phase is reported with an `eccentric-electric` flag and no primary `L` |
| **S6 completeness** | `L(T) < -3 sigma_L(T)` (§5.1) is flagged `detection-incomplete` and excluded from the primary distribution | A path cheaper than the direct minimum means burns were missed or the restricted family (§1.4) is slack. Both are named; the count and the values are reported |

Every screen reports how many events it removed, and the screened-out events
remain in the JSONL with their flag.

---

## 4. Three properties of the estimator, derived now

### 4.1 Non-negativity for the electric arm is exact

By §1.5, `DV_edel` is a Euclidean distance, so for any chain
`s_0 -> s_1 -> ... -> s_K`, `sum DV_edel(s_{k-1}, s_k) >= DV_edel(s_0, s_K)`.
Therefore `L >= 0` exactly for any electric phase whose burn intervals tile the
phase without gaps. Gaps (coast arcs, §5.3) break the tiling, so the guarantee
is stated as: **`L >= -(the coast-arc cost)`**, and the coast-arc cost is
measured (§5.3).

### 4.2 Non-negativity for the chemical arm is expected but not guaranteed

The true global minimum-impulse cost obeys the triangle inequality on physical
grounds: a path through `B` is always available as a way of getting from `A` to
`C`, so `min(A->C) <= min(A->B) + min(B->C)`. But `DV_imp` (7) is a minimum over
a restricted family, and a restricted minimum need not inherit the inequality
exactly. Registered expectation: chemical `L >= 0` up to the coast-arc cost and
the noise floor; a violation beyond `3 sigma_L` is a defect (§8, D1) and is
reported as one.

### 4.3 A single-interval phase has `L = 0` identically

If `K = 1` then `s_0 = s_1^-` and `s_1 = s_1^+`, so
`N = DV_class(s_1^- -> s_1^+) = DV_class(s_0 -> s_1) = D` and `L = 0` for every
such phase whatever the data. This is a property of the estimator, not of the
satellites. Screen S1 removes these phases from the primary distribution and
their count is reported as a first-class number, because it is also the count
of transfers this cohort executed as a **single detected impulse** — which is
itself worth stating.

---

## 5. Controls and the noise floor

### 5.1 The element-noise floor, propagated — because per-element sigmas do not exist

**The programme has no per-element uncertainties.** T5a's design says so in
those words: "The programme has no measured per-element uncertainty on
catalogue mean motion for geostationary payloads; honest per-element
covariances are precisely what T5c is for", and lists it first under "Measured
inputs that do not exist"
<!-- src: docs/matched-filter-design-20260922.md §1.2 and §11 item 1 -->.
T2's receipt carries no per-event uncertainty either
<!-- src: docs/repricing-20260921-receipt.json: perEvent block has no sigma field -->,
so there are no T2 receipt uncertainties to carry forward. **This track
therefore has no per-event delta-v uncertainty available from the programme,
and says so rather than inventing one.**

What does exist is a **band-level** measured element scatter: `CATALOGUE_NOISE_FLOOR`,
`(sigma_a km, sigma_e, sigma_i deg)` by perigee-altitude band, measured on 787
three-epoch triples on the live catalogue on 2026-08-07
<!-- src: pipeline/orbit_history.py, CATALOGUE_NOISE_FLOOR and the measurement note above noise_floor_for() -->.
Registered use: a Monte Carlo that perturbs every element state entering `N`
and `D` by independent Gaussian draws at that band's sigmas, recomputes `L`,
and reports `sigma_L(T)` as the standard deviation over **200 draws, seed
20260922**. This is a floor propagated from a population-band measurement and
is **not** a per-element sigma; it is reported under that name and the
distinction is stated wherever `sigma_L` appears.

### 5.2 Endpoint sensitivity

The archive contains interleaved element sets during transfers — a post-burn
fit appearing between pre-burn fits. Registered sensitivity: recompute the
whole study with `s_0` and `s_1` replaced by the component-wise median of the
three element sets centred on each endpoint epoch, and report the change in
every headline. If the headline median `L` moves by more than 25% relative
under this variant, the result is reported as **endpoint-sensitive** and no
population claim is made.

### 5.3 The coast-arc control — an empirical, measured noise floor

Between consecutive burn intervals of a phase there are coast arcs in which the
detector found no manoeuvre. Registered control: price each coast arc with the
same `DV_class` function, applied between the element state at the end of one
burn interval and the state at the start of the next, and report

    C(T) = sum over coast arcs of DV_class(...)

as an absolute value and as a fraction of `N(T)`. `C` is an **upper bound** on
the delta-v noise floor of this instrument for that object over that phase: it
contains fit noise, but also real J2, lunisolar and drag drift, and any
sub-threshold burn. It is the only empirical noise measurement this track has
and it is reported as an upper bound, never as a sigma.

### 5.4 The single-burn population as a second control

The `K = 1` phases removed by S1 have `L = 0` by §4.3, so they cannot be a
control on `L`. They *are* a control on the machinery: `N` and `D` must agree
to floating-point tolerance on every one of them, and the run asserts it.

---

## 6. Implementation and proofs required before any number is read

`tools/transfer_loss.py`, with `tests/test_orbit_transfer_loss.py` in the
tracked orbit suite. The following tests must pass before the results document
may be written; they are listed here so the list cannot be trimmed afterwards:

1. **(4) against a hand-computed GTO->GEO apogee kick.** A 185 x 35786 km,
   28.5 deg transfer orbit circularised at apogee to 0 deg: the closed form (4)
   is computed independently in the test and matched to 1e-9 relative.
2. **The split condition (6) is satisfied** at the numerical optimum, to
   1e-8, on a randomised set of two-impulse cases.
3. **The numerical optimum beats both endpoints** (`d1 = 0` and `d1 = di`) on
   the same randomised set, and equals the smaller of them when the optimum is
   at an endpoint.
4. **All-plane-change-at-the-high-apsis is not always optimal**: at least one
   constructed case where the interior optimum strictly beats both endpoints,
   asserting the solver is not a dressed-up endpoint rule.
5. **Hohmann degenerate case**: with `di = 0` and both orbits circular, (7)
   reproduces the textbook Hohmann total to 1e-12.
6. **Edelbaum (9) reproduces the LEO-to-GEO textbook value** for the standard
   case, and reduces to `|v0 - vf|` at `di = 0`.
7. **Edelbaum's triangle inequality** holds on randomised chains (§4.1).
8. **`DV_imp` symmetry**: raising and lowering the same pair cost the same.
9. **`K = 1` identity**: `N == D` exactly (§5.4).
10. **Screens**: each of S1-S6 fires on a constructed case and does not fire on
    its neighbour.
11. **Bootstrap and Monte Carlo determinism** under the registered seeds.
12. **Archive is opened read-only** and a write attempt raises.
13. **No government/military path**: a test asserts the tool reads its
    population only from the catalogue file and has no code path that admits an
    object absent from it.

### 6.1 Compute

The expected scale is of order 10^2 transfer events and 10^3 burn intervals, so
the arithmetic is expected to be CPU-trivial. The registered rule is the
estate's: **measure, then use what wins.** The run records wall and CPU seconds
and its execution mode in the receipt, and if a GPU is used it is obtained
through `/home/sdegan/gpu-broker/gpu-run` and the broker request id is recorded.
The execution mode is never inferred.

---

## 7. Selection effects and the direction of every bias, stated before the result

**Detection recall on transfers is high where the archive watched the
transfer.** The measured evidence, not an assertion: of the 12 catalogue objects
carrying both a detected transfer burn and a catalogued dry mass, **9 recover
50.0% to 107.5%** of the catalogued launch-to-dry mass drop, and the remaining
3 recover 1.4%-12.9% because the archive's history of them begins after the
transfer was over
<!-- src: docs/fuel-odometer-20260920.md, "Sanity anchor 2" -->. Under T2's
exact re-pricing that band becomes 45.5%-105.5%
<!-- src: docs/repricing-20260921.md, "Paper A §4.2's transfer anchor, re-priced" -->.
The cohort's largest genuine single burn, 1,502 m/s, sits exactly where a
textbook apogee kick out of a standard transfer orbit sits, 1,430-1,502 m/s
<!-- src: docs/fuel-odometer-20260920.md -->.

**Classes of burn that could still be missed, and which way each one pushes:**

| Missed class | Why it is missed | Effect on `N` | Effect on `L` |
| --- | --- | --- | --- |
| Two burns inside one interval | Element differencing sees only the net change; a split burn is priced as one impulse | down | **down** |
| Sub-threshold trim burns | Below the detector's cohort/self-history threshold | down | **down** |
| Continuous low thrust | "A continuous low-thrust burn produces no step for a step detector to find, so their station-keeping odometer is not merely low, it is structurally blind" <!-- src: docs/fuel-odometer-20260920.md, "Sanity anchor 1", on the 84 electrically station-kept objects -->. T3's independent cadence channel found the same wall from the other side: 0 of 2,809 Starlink and 0 of 618 OneWeb payloads survive its per-object test <!-- src: docs/research-program-runbook-20260921.md, T3 "Starlink 0/2,809, OneWeb 0/618 = the registered low-thrust blind spot, confirmed" --> | down | **down** |
| Burns inside archive coverage holes | Every one of the 151 catalogue objects has at least one hole <!-- src: docs/fuel-odometer-20260920.md, "Objects with at least one coverage hole 151" --> | down | **down**, and it can push `L` negative, which S6 catches |
| Burns whose element change is masked by a simultaneous drag or J2 signal | The detector attributes the change to the environment | down | **down** |

**Biases that push the other way**, and are therefore the ones that could
manufacture a false positive:

| Source | Effect on `L` | Control |
| --- | --- | --- |
| Element fit noise inside a detected interval inflates the priced change | **up** | §5.1 Monte Carlo and §5.3 coast-arc control; acceptance A3 and A4 |
| Real environmental drift inside the phase, charged to the path | **up** | §5.3 measures it directly on the coast arcs |
| Interleaved/artefact element sets at the endpoints | either way | §5.2 endpoint-median sensitivity |
| The restricted minimum family (§1.4) makes `D` too large | **down** | stated; biases the headline conservatively |

**Net direction: the measured loss fraction is a lower bound**, because the
dominant recall failures all remove burns from `N`, and the denominator
approximation also pushes `L` down. The upward sources are bounded by the two
measured controls and gated by the acceptance criteria below.

---

## 8. Acceptance criteria, defect rules, stop rules

### 8.1 When the measurement may be called informative

Registered per class, all four required. Failing any one, the class is reported
as **UNDERPOWERED** or **NOISE-DOMINATED** in those words and no population
claim is made for it:

* **A1 — power.** At least **30** transfer events survive S1-S6 in that class.
* **A2 — separation from zero.** The 95% bootstrap percentile interval on the
  median `L` excludes 0.
* **A3 — above the propagated element-noise floor.** The class median `L` is at
  least **3x** the class median `sigma_L` from §5.1.
* **A4 — not drift-dominated.** The class median `C(T)/N(T)` from §5.3 is below
  **0.25**.

A class that passes A1 and A4 but fails A2 or A3 is reported as a **measured
null** for that class, with its interval, and that is a result.

### 8.2 Defect rules

* **D1.** Any `L < -3 sigma_L` is a defect: it is flagged, excluded by S6,
  counted, and its cause named as either missed detection or restricted-family
  slack, per object.
* **D2.** A chemical class median `L` above **3.0** (a 300% path loss) is
  reported as a **defect under investigation**, not as a finding, unless its
  cause is named in the results document.
* **D3.** The numerical minimiser must reproduce the closed forms of §6 tests
  1-5 at run time as assertions, not only in the test suite. A failure aborts
  the run.
* **D4.** If the `K = 1` identity of §5.4 fails for any phase, the run aborts.

### 8.3 Stop rules

* Any of the three input hashes in §3.1 mismatching: **stop and report**.
* The archive not opening read-only: **stop**.
* Fewer than 10 surviving transfer events in the chemical class: stop, and
  report the census rather than a distribution.
* No result in this track is credited as discharged until it appears in a
  committed artifact with its provenance.

---

## 9. Deliverables

* `docs/transfer-loss-results-20260922.md` — the results, verdict first,
  every number carrying an inline `<!-- src: -->` provenance comment.
* `docs/transfer-loss-20260922.jsonl` — one record per transfer event, with its
  burn intervals, `N`, `D`, `L`, `X`, `M`, `sigma_L`, `C`, every screen flag,
  the class and bus assignment, and the per-interval detail.
* `docs/transfer-loss-20260922-receipt.json` — input hashes, source hashes,
  seeds, counts at every screen, execution mode, wall and CPU seconds, and the
  acceptance-criteria verdict per class, computed by the tool rather than
  asserted by the author.
* `tools/transfer_loss.py` and `tests/test_orbit_transfer_loss.py`.

Committed in that order: this registration alone first; then tool and tests;
then results.
