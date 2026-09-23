# Pre-registration: station-keeping efficiency — north-south burn timing (T10b) and east-west deadband economics (T10c)

Registered 2026-09-22, **before any efficiency, deadband or delta-v number in
either study exists**. Tracks T10b and T10c of
`docs/research-program-runbook-20260921.md`, the two remaining fuel-efficiency
studies after T10a. This document is committed **alone**, ahead of every
artifact these two studies will produce, the same way
`docs/transfer-loss-preregistration-20260922.md` (`83c5cd4`),
`docs/cadence-s1s2-preregistration-20260922.md` (`ffe2242`) and
`docs/cadence-preregistration-20260921.md` (`1a51afe`) were committed ahead of
their results. The git history of this file is the timestamp. Nothing below may
be changed once a number exists; an awkward outcome is reported, not edited
away.

This document implements nothing and touches no source file. It registers the
estimands, the derivations of the first-principles ideals, the **natural-motion
subtraction** that must happen before anything is charged to an operator, the
selection rules, the controls, the acceptance criteria that decide whether each
measurement may be called informative, the defect and stop rules, and — at the
front, because it decides what each study is worth — an explicit statement of
what each instrument can and cannot see.

The estate rule both tracks run under: **physics assumptions are not facts.**
Every physical relation below is derived here or cited to its source. Every
screen below is a screen, not a law, and is labelled as such.

### The two lessons T10a paid for, and how they bind here

`docs/transfer-loss-results-20260922.md` cost two defects to learn, and both
are load-bearing for these studies. They are written into the design, not into
a caveat:

1. **Do not charge an operator for natural dynamics.** T10a's first cut priced
   J2 nodal regression as if it were a manoeuvre and billed Intelsat 603
   **89.45 m/s** for 4.54 hours of the Earth's oblateness doing its job
   <!-- src: docs/transfer-loss-results-20260922.md, "A defect the registration did not anticipate" -->.
   T10b's entire subject is inclination at GEO, where the *dominant* motion is
   lunisolar precession at ~0.85 deg/yr — larger, over a one-day interval, than
   a tenth of a typical north-south correction. §2.3 derives the predicted
   natural motion, §2.4 subtracts it as a **vector** before anything is
   attributed to a burn, and §2.3 imports the production node machinery
   (`pipeline.orbit_events.plane_rotation_deg`,
   `pipeline.orbit_events.j2_secular_rates_deg_per_day`) rather than
   re-deriving it, exactly as T10a's fix did.
2. **The shipped detector's price is not the exact minimum.** Over the 267
   burn intervals T10a examined, the production price is a median **0.942** of
   the exact minimum impulse for the same element change, with quartiles
   0.821/1.009, a minimum of 0.072 and a **maximum of 93.40**
   <!-- src: docs/transfer-loss-results-20260922.md, "Registered secondary: what the shipped detector's pricing is worth" -->.
   Where these studies need a delta-v they therefore **name which one they are
   using, in the same sentence as the number**. T10b's primary denominator is
   the **exact minimum impulse** computed here from the natural-motion-corrected
   element change (§2.5, PRIMARY); the shipped price is carried as a registered
   secondary and the two are reported side by side. T10c's numerator is the
   **shipped price**, because T10c's question is about the detected
   station-keeping ledger and there is no other ledger — and §4.6 registers the
   exact-minimum re-pricing of every east-west event as the mandatory companion.

---

## 0. What these instruments can measure, and what they structurally cannot

Both studies are built on **sequences of two-line element sets** and on the
detected-event set T2 froze. The consequences are the same ones T10a's §0
registered, and they are restated because they decide what every number means.

**Invisible to both:** gravity loss and in-burn steering loss. A finite burn arc
delivers less orbit change than the same impulse delivered instantaneously; the
propellant that produced the shortfall left no trace in the elements. No
TLE-differencing instrument can measure either, and **neither study may describe
any number in it as a gravity loss or a steering loss.**

**T10b specifically.** What survives differencing is the **achieved plane
rotation** and how it divides between inclination and node. So T10b measures a
**geometric placement efficiency**: what fraction of the plane rotation the
satellite bought went into changing inclination rather than rotating the node —
which is exactly the `cos u` burn-timing penalty of §2.2. It does **not**
measure whether the thruster was pointed well within the burn, and it does not
measure propellant. Registered consequence, stated now so it cannot later be
presented as a finding: with the exact-minimum denominator of §2.5, the
efficiency is an identity in the two measured angles,
`eta = sin(|di|/2) / sin(theta/2)`. That is the point — the *distribution* of
that ratio across 1,107 detected north-south events, and the burn placement it
implies, is the measurement. The number is not a tautology; the identity is the
estimator, and what is measured is where real operators put their burns.

**T10c specifically.** The east-west station-keeping ledger this programme owns
is a **detected** ledger with a measured recall problem: the fuel odometer found
the detected station-keeping delta-v accounts for a median of **1.81%** of the
~50 m/s/yr folklore budget over 54 chemically-kept GEO satellites, 46 of 54
below 10%
<!-- src: docs/fuel-odometer-20260920.md, "Sanity anchor 1" -->. §4.2 derives
that a routine east-west correction at the deadband T3 measured is
**~0.07 m/s**, which explains the recall rather than excusing it. So T10c's
measured arm is **recall-limited by construction**, the registration says so
before the measurement, and §5.3 registers what verdict that forces.

---

## 1. Population, inputs, and what is not touched

### 1.1 Inputs, hashed before the run

| Input | Path | sha256 |
| --- | --- | --- |
| Detected event set (T2's run) | `/tmp/t2-repricing-20260921/events.jsonl.gz` | `6804c147596fdf2c78c1c6671a97f8037bcd33202dac785db85aac943d49e66f` |
| Archive snapshot, read-only | `/tmp/eol-study-20260920/archive.sqlite3` | `ffc4c4e521ca0c4eb78d5ec48039e8c9032e2f05183e5b3f09fe703bc5b734c3` |
| Propulsion catalogue | `data/propulsion-catalog-v1.json` | `7f7a50bc4dff644705f52ec28fb2c52a7f8589c7be45433a7f4c23dcc72711a9` |

These are the same three inputs T10a pinned, with the same values, so all three
fuel-efficiency studies rest on one hash-tied foundation. The event-set hash is
the value T2's **committed** receipt records as
`detectionReceipt.extractionSha256`
<!-- src: docs/repricing-20260921-receipt.json -->. **All three are verified at
run time and a mismatch is a stop (§6.3).** The archive is opened `mode=ro` and
the run asserts it.

### 1.2 Population

`data/propulsion-catalog-v1.json`, whose own `policy` field is
`commercial-civil-only`. **No object outside that file is read, priced or
named, and no fuel quantity is inferred for any object outside it.** This is the
standing policy and it is not relaxed by either track.

### 1.3 What is NOT touched

Registered now so it cannot be relaxed later:

* **Detection.** The event set is T2's, frozen and hashed. No detector runs in
  either track. No detection threshold, screen, gate or label is changed.
* **The production sweep, the published site artifacts, the published event
  list, and every published control block.** Both tracks produce dated analysis
  artifacts only.
* **Paper A and Paper B**, both published with DOIs. If a number either quotes
  is contradicted here, the contradiction is reported in the results document
  and the papers are left alone pending an operator decision.
* **The fuel odometer's frozen rules**, including the 2,500 m/s own-propulsion
  ceiling and the launch-date rule, are reused unmodified
  <!-- src: tools/fuel_odometer.py docstring, rules frozen 2026-09-20 -->.
* **T10a's instrument.** `tools/transfer_loss.py` is read, not edited, and not
  imported: T10b's minimum-impulse geometry is near-circular-to-near-circular
  and is derived and implemented independently in §2.5 so that the two studies
  are cross-checkable rather than co-dependent. The one place they must agree —
  the combined-burn law of cosines — is asserted against T10a's published
  closed-form value in the test suite (§6.1 test 3).
* **T3's cadence artifacts and T8a's proximity instrument.** `tools/proximity_geo.py`
  is **imported** for mean longitude, GMST, longitude unwrapping and the
  triaxiality constants (§4.1); nothing in it is modified.

---

## 2. T10b — north-south burn-timing efficiency

### 2.1 The estimand

For one detected north-south manoeuvre: the **achieved inclination change per
unit spent delta-v, expressed as a fraction of what the same inclination change
would have cost at the node**.

    eta = DV_ideal(|di_net|) / DV_spent                                   (T10b)

where `di_net` is the inclination change **attributable to the burn**, i.e.
after the predicted natural inclination motion over the interval has been
subtracted (§2.3, §2.4), and `DV_spent` is defined in §2.5. `eta` is
dimensionless, is 1 for a perfectly placed burn, and is less than 1 for a burn
placed away from the node. Its companion is the implied burn location
`u_eff` (§2.2), and the two are reported together everywhere.

### 2.2 The ideal, and the exact penalty for burning away from the node — derived

Notation: `mu = 398600.8 km^3/s^2`, `RE = 6378.135 km`, the WGS-72 values the
archive's element sets are fitted against
<!-- src: pipeline/orbit_history.py, MU_WGS72 / RE_WGS72 -->. `v = sqrt(mu/a)`
is the circular speed. For the GEO population of this track (`e < 0.01` by
screen N1) the transverse speed `h/r` differs from `v` by at most `e`, i.e.
below 1% and typically below 0.1%; the registered pricing uses `v = sqrt(mu/a)`
and §6.1 test 8 bounds the error this introduces.

**(a) The ideal: a pure inclination change costs least at a node.** A pure
plane rotation by angle `theta` with the speed unchanged rotates the velocity
vector through `theta`, and the impulse is the chord of that rotation:

    DV_rot(theta) = 2 v sin(theta / 2).                                   (1)

This is exact — it is the isoceles-triangle chord, not a small-angle expansion —
and it is the same law of cosines T10a's eq. (4) reduces to when `vA = vB`.
The rotation is about the **radius vector** at the burn point, because an
impulse cannot move the satellite, so both orbit planes must contain the burn
point: the burn point lies on the line of intersection of the two planes, i.e.
on their **relative node**.

**(b) What a burn at argument of latitude `u` actually buys.** Put the burn at
argument of latitude `u`, measured from the ascending node along the orbit.
Let `h_hat` be the orbit pole, `r_hat` the radius unit vector and
`t_hat = h_hat x r_hat` the transverse unit vector. Rotating the plane by
`theta` about `r_hat` carries

    h_hat' = cos(theta) h_hat + sin(theta) (r_hat x h_hat)
           = cos(theta) h_hat - sin(theta) t_hat.                         (2)

The inclination is the angle between the pole and `z_hat`, and for an orbit of
inclination `i` at argument of latitude `u` the transverse unit vector has
`t_hat . z_hat = sin(i) cos(u)` (it is the in-plane direction 90 deg ahead of a
radius vector whose own `z` component is `sin(i) sin(u)`). Dotting (2) with
`z_hat`:

    cos(i') = cos(theta) cos(i) - sin(theta) sin(i) cos(u).               (3)

**Equation (3) is exact**, for any `i`, `theta` and `u`. Two limits check it:
at `u = 0` it is `cos(i') = cos(i + theta)`, i.e. `i' = i + theta` — the whole
rotation becomes inclination, which is the definition of a node burn; at
`u = 90 deg` it is `cos(i') = cos(theta) cos(i)`, which for small angles gives
`i'^2 = i^2 + theta^2` — a burn a quarter-orbit from the node changes the
*magnitude* of the inclination only at second order, and spends its rotation on
the node instead.

Expanding (3) for small `theta` gives the first-order statement the charter
quotes:

    di = theta cos(u) + O(theta^2),                                       (4)

and expanding (3) for small `i`, `i'`, `theta` together gives the planar law of
cosines that this track actually uses, because at GEO a north-south correction
is not small compared with the inclination it is correcting:

    i'^2 = i^2 + theta^2 + 2 i theta cos(u).                              (5)

(5) says the inclination **vector** — the pole's position on the sky in the
`(i cos Omega, i sin Omega)` plane — moves by `theta` in a direction making
angle `u` with the current inclination vector. `u = 180 deg` is the burn that
drives the inclination straight down; `u = 0` drives it straight up;
`u = 90 deg` swings the node and changes `|i|` only at second order.

**(c) The exact penalty factor.** To achieve an inclination change from `i` to
`i' = i + di` with the burn placed at argument of latitude `u`, solve (3) for
`theta`. Writing `R = sqrt(cos^2 i + sin^2 i cos^2 u)` and
`phi = atan2(sin(i) cos(u), cos(i))`, (3) is `cos(i') = R cos(theta + phi)`, so

    theta(u, i, di) = arccos( cos(i + di) / R ) - phi,                    (6)

and the **registered exact penalty factor** is

    P(u, i, di) = DV_rot(theta) / DV_rot(|di|)
                = sin(theta(u,i,di) / 2) / sin(|di| / 2).                 (7)

Its small-angle limit, from (4), is `P -> sec(u)`, and that is the form the
charter names. (7) is what the instrument computes; `sec(u)` is quoted only as
the limit it reduces to, never as the price.

**(d) Inverting for the burn location.** The instrument does not know `u` a
priori. It measures the pole before (after natural propagation, §2.4) and after,
so it has `i`, `i'` and the total plane rotation `theta`, and (3) inverts
exactly to

    cos(u) = ( cos(theta) cos(i) - cos(i') ) / ( sin(theta) sin(i) ).     (8)

`u_eff` from (8) is the **effective argument of latitude of the burn** implied
by the element change, and it is the second measured quantity of T10b. It is
degenerate as `i -> 0` (a satellite at zero inclination has no node), so screen
N6 requires `i >= 10 sigma_pole` before `u_eff` is reported for an event.

**(e) The relation between `eta` and `P` is an identity, and is registered as
one.** With the exact-minimum denominator of §2.5 and a pure plane rotation,
`DV_spent = DV_rot(theta)`, so `eta = 1/P` exactly. That is the estimator. The
measurement is the distribution of `eta`, `theta` and `u_eff` over real
detected burns, per operator and per bus — not the algebra that connects them.

### 2.3 The natural inclination motion, derived — because T10a proved this is where the defect lives

Two natural mechanisms move a GEO orbit pole, and **both are subtracted before
any element change is attributed to a burn.**

**(a) Lunisolar precession.** A third body of gravitational parameter `mu_3` at
distance `r_3` precesses a near-circular orbit's pole about the third body's own
orbit pole at the doubly-averaged secular rate
`omega_prec = (3/4)(n_3^2 / n) cos(i_rel)` with `n_3^2 = mu_3 / r_3^3` — the
Kozai/Allan-Cook result (Kozai 1959, *Smithsonian Contr. Astrophys.* 5, 53;
Allan & Cook 1964, *Proc. R. Soc. A* 280, 97; Kaula 1962, *Astron. J.* 67, 300).
`docs/cadence-s1s2-preregistration-20260922.md` §3.1 carried that arithmetic out
for GEO and **this track reuses its derivation verbatim rather than repeating
it**: Sun `0.73717 deg/yr`, Moon `1.60520 deg/yr`, giving a pole speed at `i = 0`
of `0.797` to `1.061 deg/yr` before the oblateness coupling, and `0.75-0.95
deg/yr` after it, mean near `0.85`, against Soop, *Handbook of Geostationary
Orbits*, 1994, ch. 4
<!-- src: docs/cadence-s1s2-preregistration-20260922.md §3.1 -->.

The same document's §3.2 gives the geometry this track needs, which a scalar
rate does not supply: the pole traces a **circle about the Laplace pole**, which
at GEO sits `L = 7.4 deg` from the equatorial pole with a full-circuit period
`T_prec ~= 53 yr`, reproducing `0.873 deg/yr` at `i = 0` and cross-checking the
direct torque calculation
<!-- src: docs/cadence-s1s2-preregistration-20260922.md §3.2 -->. The registered
model is therefore a **rigid rotation of the pole about the Laplace pole**:

    dp/dt = omega_L ( P_L x p ),     omega_L = 360 deg / 53 yr,
    P_L   = (0, -sin L, cos L),      L = 7.4 deg.                         (9)

`P_L` is the Laplace pole in the equatorial frame the elements use. Its
direction is fixed by the ecliptic/lunar mean pole lying at right ascension
270 deg, so `P_L` corresponds to `RAAN = 0 deg, inclination 7.4 deg`. A
consequence that is a **falsifiable prediction of the model and is registered as
one**: an initially equatorial GEO orbit drifts toward `RAAN ~= 270 deg`, since
`P_L x z_hat` points along `-x_hat`. §3.3 registers the control that tests it on
this archive.

Registered central value: `omega_L sin(L) = 0.8748 deg/yr` at `i = 0`.
Registered interval: `0.75` to `0.95 deg/yr`, applied by scaling `omega_L`, i.e.
`T_prec` in `[48.8, 61.8] yr`. **This is the cited literature interval, and it
is a screen, not a law.** Every T10b headline is recomputed at both edges and
the spread is reported (§3.2, R1).

**(b) J2 nodal regression.** The production module's own
`j2_secular_rates_deg_per_day(a, e, i)` is imported and evaluated on each
event's own elements — **not** a nominal GEO rate — and applied as a rotation
of the pole about `z_hat`:

    dp/dt |_J2 = RAAN_dot ( z_hat x p ).                                 (10)

At GEO `RAAN_dot = -4.8995 deg/yr`, but the pole speed it produces is
`|RAAN_dot| sin(i)`, which at `i = 0.05 deg` is `0.0043 deg/yr` — three orders
below the manoeuvre scale. It is included anyway, because T10a's defect was
precisely the assumption that a node rate could be ignored or, worse, charged,
and because for the `inclination-change` events that sit at appreciable
inclination it is not negligible. Its measured size is reported.

**(c) What is NOT modelled, stated now.** The periodic lunisolar terms of
§3.3(a) of the S1/S2 registration — half-month, monthly and semiannual
inclination oscillations with amplitude ceilings of `1e-2` to `6e-2 deg`
<!-- src: docs/cadence-s1s2-preregistration-20260922.md §3.3(a) -->  — are
**not** subtracted. They are real, they are of the same order as a tight
north-south deadband, and no averaged secular model removes them. They are
therefore part of the **measured** noise floor of §3.1 rather than of the
model, and the registration says so rather than pretending the secular
subtraction is complete. This is the largest known unmodelled term in T10b and
it is named again in §7.

### 2.4 The subtraction, as a vector — and the attribution rule

For an event with element states `s-` (before) and `s+` (after) separated by
`dt`:

1. Form the pole unit vectors `p- `, `p+` from `(i, RAAN)`:
   `p = (sin i sin RAAN, -sin i cos RAAN, cos i)`.
2. Propagate `p-` forward by `dt` under (9) + (10) — **as a finite rotation, not
   as a linear step**, by composing the two rotations, so that a long interval
   is not charged a first-order error. Call the result `p_pred`.
3. `i_pred = arccos(p_pred . z_hat)`. The **burn-attributable inclination
   change** is

       di_net = i+ - i_pred                                             (11)

   and the **burn-attributable plane rotation** is the angle between `p_pred`
   and `p+`:

       theta_net = angle(p_pred, p+).                                   (12)

   `theta_net` is computed with the production half-angle form
   `pipeline.orbit_events.plane_rotation_deg(i_pred, i+, RAAN+ - RAAN_pred)`,
   which returns exactly zero for exactly zero rather than a microdegree of
   `acos` rounding
   <!-- src: pipeline/orbit_events.py, plane_rotation_deg docstring -->, and is
   asserted against the direct vector angle in §6.1 test 5.
4. `u_eff` from (8) with `i = i_pred`, `i' = i+`, `theta = theta_net`.

**The uncorrected values `di_raw` and `theta_raw` are computed for every event
and published beside the corrected ones**, exactly as T10a published
`lossFractionRawNode`, so the size of the correction is visible per event and
cannot be hidden in a median.

### 2.5 `DV_spent`: two denominators, both named, one primary

**PRIMARY — the exact minimum impulse.** The cheapest single impulse that
produces the burn-attributable element change. For the near-circular GEO
population this is the combined-burn law of cosines on the velocity triangle,
which is T10a's eq. (4) and is derived there from the vector difference:

    DV_min^2 = v-^2 + v+^2 - 2 v- v+ cos(theta_net),                     (13)

with `v± = sqrt(mu / a±)`, and `a±` the Kozai mean semi-major axes from the two
element sets. (13) is exact for a burn at a shared radius that is an apsis of
both orbits; for `e < 0.01` the radial-velocity terms it omits are bounded by
`e v` and that bound is computed and reported per event as
`radialTermBoundMps`. When `theta_net` is the only change (`a+ = a-`), (13)
reduces to (1) exactly, so `eta = 1/P` (§2.2(e)).

**SECONDARY — the shipped detector price**, `deltaV.totalMetresPerSecond` from
T2's event record. Reported for every event beside the primary, with the ratio
`shipped / DV_min` published per event. This is the T10a lesson (b) discipline:
the two denominators give two efficiency distributions, both are published, and
the primary is named in every sentence that carries a number.

Registered expectation, so it is not a surprise: the shipped price includes the
tangential and eccentricity channels as well as the plane channel, so on a clean
north-south burn it should exceed `DV_min` slightly, and the `shipped/DV_min`
distribution should sit near but above T10a's 0.942 median for transfer
intervals. **A large departure is a finding about the detector and is reported
as a detector audit, never as a fuel measurement.**

### 2.6 Event selection — the screens, all registered here

The unit is **one detected event**, not one object.

| Screen | Rule | Why it is a screen, not a law |
| --- | --- | --- |
| **N1 GEO** | At both endpoints `|a - 42164.0| <= 300 km` and `e < 0.01` | The detector's own GEO test, reused verbatim <!-- src: pipeline/orbit_events.py GEO_SEMI_MAJOR_AXIS_KM, GEO_BAND_KM --> |
| **N2 signature** | `geo-north-south-keeping` or `inclination-change` | The two signatures whose subject is the orbit plane |
| **N3 not a transfer** | Event start later than 18 months after the catalogued launch date | The odometer's frozen raising window; orbit raising is T10a's and its plane changes are priced there |
| **N4 odometer exclusions** | Shipped price `<= 2500 m/s`, start at or after the catalogued launch date | The odometer's frozen rules 7 and 8, reused |
| **N5 span** | Interval span `<= 7 days` (primary); `<= 3 d` and `<= 21 d` reported as sensitivities | Over a long interval the natural motion dominates and the "burn" is a summary of many. 7 days is an operating point chosen to exceed a GEO element-set cadence with margin, **fixed before the span distribution was inspected**, and the two sensitivities are reported whatever they show |
| **N6 above the measured pole-noise floor** | `theta_net >= 5 sigma_pole` and, for `u_eff` only, `i_pred >= 10 sigma_pole` | `sigma_pole` is **measured** in §3.1, not assumed. Below it, `u_eff` from (8) is reading fit noise |
| **N7 finite** | `|di_net| > 0` and `theta_net > 0` and both finite | A zero denominator is not a measurement |

Every screen reports how many events it removed, and screened-out events remain
in the JSONL with their flag.

### 2.7 Reported distributions

* Per-event `eta`, `theta_net`, `di_net`, `u_eff`, `DV_min`, shipped price,
  the uncorrected companions, and every screen flag — in the JSONL.
* The distribution of `eta` and of `|u_eff|` over the primary population:
  quantiles, and **medians with non-parametric bootstrap 95% percentile
  intervals, `B = 10000`, seed 20260922**, resampling **objects** rather than
  events, because events on one satellite are not independent draws.
* **By operator family and by bus**, where the catalogue names a `bus`, on the
  same normalisation T10a's implementation used — upper-case, truncate after the
  first run of digits (`BSS-702SP -> BSS-702`, `SSL-1300 -> SSL-1300`). Families
  with fewer than 5 **objects** are reported with their count and no summary
  statistic. T10a's registration/implementation discrepancy on this rule is
  named there; this registration adopts the implemented rule explicitly so there
  is nothing to discover later.
* **The sign split**: events whose `di_net < 0` (inclination reduced — a
  north-south correction) against `di_net > 0` (inclination raised), with counts
  and separate medians. The primary distribution is over `|di_net|` and includes
  both; the split is a registered secondary.
* **The operator-facing number**: the annual delta-v penalty implied by the
  measured placement, `(1/eta - 1) x 45.6 m/s/yr`, where 45.6 m/s/yr is the
  north-south budget derived in §4.4 from the same 0.85 deg/yr drift. Reported
  as a band across the registered 0.75-0.95 deg/yr interval, and as propellant
  at both edges of each object's catalogued station-keeping Isp band.

---

## 3. T10b controls, noise floor, robustness

### 3.1 The pole-noise floor is MEASURED, not assumed

The programme has **no per-element uncertainty** on RAAN. T5a's design says the
programme has no measured per-element uncertainty on catalogue mean motion for
geostationary payloads and lists it first under "Measured inputs that do not
exist"
<!-- src: docs/matched-filter-design-20260922.md §1.2 and §11 item 1 -->, and
`CATALOGUE_NOISE_FLOOR` carries `sigma_a, sigma_e, sigma_i` but **no
`sigma_RAAN`** <!-- src: pipeline/orbit_history.py, CATALOGUE_NOISE_FLOOR -->.
At `i = 0.05 deg` a RAAN error of 10 deg is a pole error of only
`0.05 x sin(10 deg) = 0.0087 deg` — but that is a tenth of a typical correction,
so the node channel at near-zero inclination is exactly where a made-up sigma
would do damage.

**Registered measurement.** `sigma_pole` is measured on this archive, on this
population, from **quiet arcs**: consecutive element-set pairs of the same
catalogue objects, inside the same GEO screen N1, that lie **outside every
detected interval** of T2's event set for that object and are separated by at
most the same 7 days. For each such pair the natural motion of §2.3 is
propagated and subtracted and the residual pole displacement is recorded.
`sigma_pole` is `1.4826 x MAD` of that residual, per day of separation and
pooled, using the MAD rather than a standard deviation for the reason
`pipeline/orbit_history._mad_sigma` gives — one manoeuvre in the sample would
inflate a standard deviation enough to hide itself.

This is the same move T10a made with its coast-arc control and it carries the
same caveat, registered in the same words: **`sigma_pole` is an upper bound on
the instrument's pole noise, not a sigma.** It contains fit noise, but also the
unmodelled periodic lunisolar terms of §2.3(c) and any sub-threshold burn.

### 3.2 Registered robustness checks

* **R1 drift-rate sensitivity.** Every headline recomputed with the natural
  drift at `0.75` and at `0.95 deg/yr`. If the median `eta` moves by more than
  **25% relative** across that interval, the result is reported as
  **drift-model-sensitive** and no population claim is made — the same rule and
  the same threshold T10a's §5.2 used, and it fired there, so it is known to be
  a rule that bites.
* **R2 no-subtraction control.** Every headline recomputed with **no** natural
  motion subtracted at all. This is the T10a defect reproduced deliberately, and
  its size is the measurement of how much lesson (a) was worth in this track.
* **R3 denominator swap.** Every headline recomputed with the shipped price as
  denominator (§2.5).
* **R4 element-noise Monte Carlo.** 200 draws, seed 20260922, perturbing `i` by
  the band `sigma_i` from `CATALOGUE_NOISE_FLOOR` and RAAN by
  `sigma_pole / sin(i)` — the RAAN perturbation that produces the **measured**
  pole scatter, which is the honest way to use a measured pole floor when no
  RAAN sigma exists. `sigma_eta` per event is the standard deviation over the
  draws.
* **R5 span sensitivity.** N5 at 3 and 21 days.

### 3.3 The drift-direction control — a prediction the model can fail

§2.3(a) predicts that the natural pole motion at GEO points toward
`RAAN ~= 270 deg`. Registered control, computed on the **quiet arcs of §3.1**
and therefore on data containing no detected manoeuvre: the pooled direction of
the observed pole displacement, expressed as the RAAN it is heading toward, and
its scatter. If the measured direction is not within **20 deg** of the predicted
one, **the natural-motion model is reported as failing its own control and no
T10b population claim is made**; the per-event numbers are still published with
the failure stated. This control is registered *before* the number exists
precisely because a subtraction that is wrong in direction is worse than no
subtraction at all.

### 3.4 Acceptance criteria — when T10b may be called informative

All four required. Failing any one, the study is reported as **UNDERPOWERED** or
**NOISE-DOMINATED** in those words and no population claim is made:

* **B1 power.** At least **30** events survive N1-N7, on at least **10**
  distinct objects.
* **B2 separation.** The bootstrap 95% interval on the median `eta` excludes
  **1.0**. (An interval containing 1.0 is the measured statement that burns are
  placed at the node, which is a result and is reported as one.)
* **B3 above the noise floor.** The median `theta_net` is at least **5x**
  `sigma_pole`, and the R4 Monte Carlo moves the median `eta` by less than 25%.
* **B4 not drift-dominated.** The median of
  `|p_pred - p-| / |p+ - p-|` — the fraction of the observed pole motion the
  natural model claims — is below **0.25**.

A study that passes B1 and B4 but fails B2 or B3 is a **measured null**, with
its interval, and that is a result.

---

## 4. T10c — east-west deadband economics

### 4.1 The triaxial acceleration, derived and cited

Earth's triaxiality drives geostationary longitude with

    d2(lambda)/dt2 = -A_max sin( 2 (lambda - lambda_22) ),                (14)

with zeros at the two stable longitudes `75.1 deg E` and `104.7 deg W` and the
two unstable ones 90 deg away
<!-- src: tools/proximity_geo.py, STABLE_LONGITUDES_DEG, prereg 2.6 of docs/proximity-preregistration-20260922.md -->.
Two independent derivations of `A_max` already exist in this repository and
**both are recomputed by this track's code and asserted equal**:

* T3's form, `A_max = 18 n^2 J22 (RE/a)^2` with `J22 = 1.8154e-6`,
  `a = 42164.2 km`, `n = 2 pi / 86164.0905 s`, giving
  `3.976e-15 rad/s^2 = 1.7006e-3 deg/day^2`
  <!-- src: docs/cadence-results-20260921.md §5.3 and tools/cadence_lines.py, geo_longitude_acceleration_deg_day2 -->.
* T8a's form, `A_max = 3 omega_E a_T,max / v_GEO` with
  `a_T,max = 6 J22 (mu/a^2)(RE/a)^2`
  <!-- src: tools/proximity_geo.py, LAMBDA_DDOT_MAX -->.

Agreement of two independently-written forms is the check that the constant is
not a transcription. The registered value is the recomputed one and the run
records both.

`A(lambda) = A_max |sin(2(lambda - 75.1 deg))|` is the acceleration at an
object's own slot, and it is the physical quantity T10c's theory depends on.

### 4.2 The deadband cycle and its cost — derived exactly

Inside a deadband the acceleration is effectively constant, so `lambda(t)` is a
parabola. The standard one-sided strategy places the satellite at one edge with
a drift rate directed across the box, lets the parabola reach its vertex exactly
at the far edge, and burns when it returns to the first edge. The excursion is
the full box width `2 R` for a deadband of half-width `R`:

    2 R = lambda_dot_0^2 / (2 A)    =>    lambda_dot_0 = 2 sqrt(A R),     (15)
    T   = 2 lambda_dot_0 / A        =  4 sqrt(R / A).                     (16)

(16) is the relation T3 used to read `R = +/-0.0208 deg` off its measured
14.00-day line
<!-- src: docs/cadence-results-20260921.md §5.3, derivations.eastWestDeadbandDeg -->
and this track adopts it unchanged.

Each burn reverses the drift rate, so `|d(lambda_dot)| = 2 lambda_dot_0
= 4 sqrt(A R)`. The longitude drift rate is `lambda_dot = n(a) - omega_E`, and
`dn/da = -(3/2) n/a`, while a tangential impulse `dv` changes the semi-major
axis of a circular orbit by `da = 2 dv / n` (from vis-viva, `da/dv = 2a^2 v/mu`
with `v = n a`). Hence

    d(lambda_dot) = -(3/2)(n/a) da = -3 dv / a,                           (17)

which is the same relation T8a's `LAMBDA_DDOT_MAX` uses in reverse, and

    DV_cycle = (a / 3) |d(lambda_dot)| = (4 a / 3) sqrt(A R).             (18)

With `365.25 / T` cycles in a year and (16),

    DV_year = (4a/3) sqrt(A R) x (T_year / 4) sqrt(A / R)
            = a A T_year / 3,     T_year = 365.25 d = 3.15576e7 s.        (19)

**The deadband cancels.** Equation (19) is the registered headline prediction of
T10c and it is registered before any measurement:

> **To first order, an east-west deadband costs nothing per year. The annual
> east-west station-keeping budget is set by the slot's triaxial acceleration
> alone. A tighter box buys the same fuel bill in more, smaller burns.**

The cost of a tighter box is therefore **manoeuvre count**, which is
`365.25/T = (365.25/4) sqrt(A/R)`, proportional to `R^(-1/2)`.

Reference values at the maximum-acceleration longitude, computed here so the
results document has something registered to compare against:
`DV_year = 1.76 m/s/yr`; at T3's measured `R = 0.0208 deg`, `T = 14.0 d`,
`DV_cycle = 0.068 m/s`, **26.1 manoeuvres a year**. At `R = 0.005 deg` the same
slot costs the same 1.76 m/s/yr in **53.3** manoeuvres; at `R = 0.05 deg`, in
**16.8**. These are recomputed by the tool and asserted against the numbers in
this paragraph (§6.1 test 12).

### 4.3 What (19) assumes, stated before it is tested

(19) assumes: a single tangential burn per cycle; the acceleration constant
across the box (true to `O(R)` since `R <= 0.05 deg` against a 90 deg
half-period of (14)); no longitude relocation; and that the burn's only job is
longitude. Real east-west keeping is often flown as a **pair** of burns half a
cycle apart so that the eccentricity vector can be steered at the same time,
which changes the constant in (18) but **not** the `R`-independence of (19),
because `DV_cycle ~ sqrt(R)` and cycles-per-year `~ 1/sqrt(R)` whatever the
per-cycle split. The `R`-independence is the claim under test; the constant
`365.25 a A / 3` is the specific prediction, and a measured constant differing
from it by a bounded factor with the right `A` dependence is a **partial**
confirmation and will be reported as one.

### 4.4 The north-south budget, for scale — derived from the same drift

Correcting the §2.3 drift of `0.85 deg/yr` costs, by (1),
`2 v sin(0.425 deg) = 2 x 3074.7 x 0.0074176 km/s = 45.6 m/s/yr`
<!-- src: docs/cadence-s1s2-results-20260922.md §3.5, the same consistency check computed there -->,
26 times the east-west budget of §4.2, and `1.75 m/s` per burn on a 14-day
cycle against east-west's `0.068 m/s`. Registered consequence for the
interpretation of both tracks: **east-west corrections are 26 times smaller than
north-south corrections at GEO**, which is the physical reason the detected
east-west ledger is recall-limited, and it is derived rather than asserted.

### 4.5 The estimand, and how the deadband is measured

Unit: **one station segment** of one catalogue object — a maximal stretch in
which the object holds one slot.

* **Mean longitude** `lambda = RAAN + argp + M - theta_GMST`, computed with
  `tools/proximity_geo.mean_longitude_deg` and `gmst_deg` (IAU-1982), which is
  the rotation consistent with a TLE's RAAN, and unwrapped with that module's
  drift-informed `unwrap_longitude`. Imported, not re-implemented.
* **Station segments**: maximal stretches with `|lambda - median| <= 0.3 deg`
  throughout and length `>= 30 d`, the registered T8a rule
  <!-- src: tools/proximity_geo.py, station_segments, STATION_HALF_WIDTH_DEG, STATION_MIN_DAYS -->,
  evaluated on the object's own element epochs rather than a daily grid, with
  gaps longer than **10 days** breaking a segment.
* **Deadband half-width, primary estimator**: `R_lambda = 0.5 x (p97.5 - p2.5)`
  of `lambda` about the segment median. Registered sensitivities:
  `0.5 x (p99 - p1)` and `0.5 x (max - min)`.
* **Deadband half-width, independent estimator**: from the drift-rate
  excursion, `R_dot = lambda_dot_amp^2 / (4 A)` with `lambda_dot_amp` the
  p97.5 of `|lambda_dot - median(lambda_dot)|` inside the segment, `lambda_dot`
  from `drift_rate_deg_per_day(n)`. (15) makes the two estimators measurements
  of the same quantity through different elements, so their agreement is a
  registered internal check and their disagreement is a registered finding.
* **Annual detected east-west delta-v**: the sum of `deltaV.totalMetresPerSecond`
  over the object's `geo-east-west-keeping` events inside the segment, divided
  by the segment's **gap-aware observed years** — observed interval days summed,
  never the calendar span across a hole, which is the odometer's own rule
  <!-- src: docs/fuel-odometer-20260920.md, "Observed years are gap-aware" -->.
* **A(lambda)** at the segment's own median longitude, from §4.1.

**The measured relations, registered:**

* **M1.** Theil-Sen slope of annual detected east-west delta-v on `R_lambda`,
  with a bootstrap 95% interval over objects. **Registered prediction from (19):
  the slope is 0.**
* **M2.** Theil-Sen slope of the same on `A(lambda)`. **Registered prediction:
  positive, equal to `a T_year / 3` from (19), i.e. `1.764 m/s/yr` per unit of
  `A / A_max`.**
* **M3.** The **recall ratio** `measured / theoretical` per segment:
  quantiles and the IQR, which is the registered "residual spread".
* **M4.** The measured free-drift acceleration (§4.6) against `A(lambda)`.

### 4.6 Controls

* **The free-drift control, which tests the theory's own input.** Inside each
  station segment, between consecutive detected east-west events, fit
  `d(lambda_dot)/dt` by least squares on the quiet arc. Its magnitude is a
  **direct measurement of `A(lambda)`** from this archive, independent of any
  manoeuvre pricing. Registered check: the pooled regression of measured
  `|lambda_ddot|` on derived `A(lambda)` has slope 1 within its bootstrap
  interval. **If it does not, the theory's input is not verified on this data
  and §5.3's verdict says so.** This control is the strongest thing in T10c and
  it can fail.
* **Exact re-pricing of every east-west event.** The shipped price for each
  event is divided by the exact minimum impulse for the same element change
  (§2.5 (13) plus the tangential term), and the distribution is published beside
  T10a's 0.942 median — lesson (b), applied to a different event class.
* **Relocation exclusion.** A segment containing a longitude relocation — a
  sustained drift carrying `lambda` more than `0.3 deg` from the segment median
  — is ended by the segment rule itself; segments adjacent to a relocation are
  flagged and the relocation delta-v is reported separately and never counted as
  station-keeping.
* **The detectability confound, registered before the measurement.** By (18) the
  per-burn delta-v is proportional to `sqrt(R)`, so a tighter box produces
  *smaller* burns, which are *less* likely to clear the detector's threshold.
  **The measured relation therefore has a built-in positive bias of detected
  annual delta-v on `R`, purely from detectability, and it must not be read as
  "a looser box costs more fuel".** The registration states this now, the
  results document must state it wherever the M1 slope appears, and the size of
  the bias is bounded by publishing the detected event **count** per year
  against `R` alongside the delta-v.

### 4.7 Acceptance criteria — when T10c may be called informative

* **C1 power.** At least **20** station segments on at least **15** objects
  carry both a deadband estimate and a non-zero detected east-west delta-v.
* **C2 the deadband-independence test is decidable.** The bootstrap interval on
  the M1 slope is narrow enough to distinguish 0 from the slope a
  `DV_year ~ sqrt(R)` alternative would give. Otherwise M1 is reported as
  **NOT DECIDABLE**, in those words.
* **C3 the free-drift control passes**, i.e. §4.6's slope interval contains 1.
  If it fails, the whole theoretical arm is reported as **INPUT NOT VERIFIED**
  and no confirmation of (19) is claimed from this data.
* **C4 the recall ratio is reported whatever it is**, with its quantiles, and if
  its median is below **0.25** the measured arm is reported as
  **RECALL-LIMITED** in those words and the headline becomes the derivation
  plus the measured recall, not a measured confirmation of (19).

---

## 5. Selection effects, the direction of every bias, and the registered verdict shapes

### 5.1 T10b

| Source | Effect on measured `eta` | Control |
| --- | --- | --- |
| Pole fit noise inflates `theta_net` without inflating `di_net` | **down** | N6 screen at 5 `sigma_pole`; R4 Monte Carlo; `sigma_pole` measured |
| Unmodelled periodic lunisolar terms (§2.3(c)) leak into `theta_net` | **down** | inside the measured `sigma_pole`, reported as its dominant content |
| Natural drift over-subtracted (drift rate too high) | either way | R1 at both edges of 0.75-0.95 deg/yr |
| Natural drift **not** subtracted | either way, and it is the T10a defect | R2 measures it |
| Two burns inside one interval, seen as one net plane change | **up** — a net change is never larger than the sum | stated; biases the headline toward "efficient" |
| Only the largest burns are detected (1.81% recall) | unknown sign, **large** | §5.3; the population is conditioned on detectability and every T10b sentence must say so |

**Net: `eta` is measured on a detectability-selected sample of large plane
changes, and the noise sources push it down.** Both directions are stated with
every headline.

### 5.2 T10c

| Source | Effect | Control |
| --- | --- | --- |
| Sub-threshold east-west burns missed | detected delta-v **down** | M3 recall ratio, published |
| Smaller burns in tighter boxes are missed more often | M1 slope **up**, spuriously | §4.6, registered in advance |
| Relocation manoeuvres counted as station-keeping | detected delta-v **up** | segment rule + relocation flag |
| Element fit noise priced as a burn | detected delta-v **up** | exact re-pricing control; event counts published |
| Longitude slot misread | `A(lambda)` wrong | free-drift control measures `A` directly |

### 5.3 The verdict shapes, registered before the numbers

Registered so that neither study can be written into a better-sounding shape
afterwards. Exactly one of these is the T10c headline:

* **(i) Confirmation.** The free-drift control passes, the M1 slope interval
  contains 0, and the M2 slope is consistent with `365.25 a / 3`. Headline: the
  deadband-independence of the annual east-west budget is **measured**.
* **(ii) Recall-limited.** The free-drift control passes but the recall ratio
  median is below 0.25. Headline: **the theory's input is verified on this
  archive and its consequence is not measurable from this ledger** — reported in
  those words, with the derivation as the answer to the reader's question and
  the recall as the reason the measurement cannot confirm it.
* **(iii) Disagreement.** The free-drift control passes and the measured
  relation contradicts (19) beyond the registered biases. **The disagreement is
  the finding** and is reported as one, with the mechanism named or explicitly
  not named.
* **(iv) Input not verified.** The free-drift control fails. Nothing is claimed.

The fuel odometer's measured **1.81%** median recall
<!-- src: docs/fuel-odometer-20260920.md, "Sanity anchor 1" --> makes (ii) the
most likely outcome and the registration says so in advance rather than
discovering it.

---

## 6. Implementation, proofs, compute

`tools/stationkeeping_efficiency.py`, with
`tests/test_orbit_stationkeeping_efficiency.py` in the tracked orbit suite.

### 6.1 Tests that must pass before any result may be written

Listed here so the list cannot be trimmed afterwards.

1. **(3) at `u = 0`** reproduces `i' = i + theta` to 1e-12 over a randomised
   grid.
2. **(3) at `u = 90 deg`** reproduces `cos i' = cos theta cos i`, and its small
   angle limit `i'^2 = i^2 + theta^2` to the expected order.
3. **(1) against T10a's published closed form.** The combined-burn law of
   cosines (13) with `vA = vB` equals `2 v sin(theta/2)` to 1e-12, and (13)
   reproduces T10a's independently published GTO-to-GEO apogee-kick value
   **1,837.4396175374018 m/s**
   <!-- src: docs/transfer-loss-results-20260922.md, run-time proof table --> to
   1e-9 relative. This pins two instruments together across two registrations.
4. **(6) inverts (3)** and **(8) inverts (6)**: round-trip `u -> theta -> u` to
   1e-10 on a randomised grid away from the `i -> 0` degeneracy.
5. **`plane_rotation_deg` equals the direct vector angle** between poles to
   1e-9 deg, including the exactly-zero case.
6. **The natural-motion propagation is a rotation**: `|p_pred| = 1` to 1e-15,
   it is exactly the identity at `dt = 0`, and composing two half-steps equals
   one full step to 1e-12.
7. **The natural drift reproduces 0.8748 deg/yr at `i = 0`** and the
   S1/S2 registration's `0.873 deg/yr` mean over a 1080-day window to 3
   significant figures, and its direction points at `RAAN = 270 deg`.
8. **The `e` bound on `v`**: the radial-term bound of §2.5 is computed and
   asserted `<= e v` on randomised near-circular pairs.
9. **Each screen N1-N7 fires on a constructed case and does not fire on its
   neighbour.**
10. **Bootstrap and Monte Carlo determinism** under the registered seeds.
11. **The archive is opened read-only** and a write attempt raises.
12. **T10c's derivation chain**: (16) reproduces `T = 14.0 d` at
    `R = 0.0208 deg`; (18) reproduces `0.068 m/s`; (19) reproduces
    `1.76 m/s/yr`; and (19) is **independent of `R`** to 1e-12 across four
    decades of `R`. The two independent `A_max` derivations of §4.1 agree to
    1e-3 relative.
13. **Mean longitude** round-trips against a constructed element set, and the
    unwrap is exact across a constructed 180 deg gap.
14. **No government/military path**: a test asserts the tool reads its
    population only from the catalogue file and has no code path admitting an
    object absent from it.

### 6.2 Compute

Expected scale: ~1,100 north-south events and ~1.3M archive rows for the
151-object cohort — the same cohort the odometer read in **118.4 s wall on CPU
at nice 19** <!-- src: docs/fuel-odometer-20260920.md, "Cohort and detection" -->.
The arithmetic is expected to be CPU-trivial. The registered rule is the
estate's: **measure, then use what wins.** The run records wall and CPU seconds
and its execution mode in the receipt; **if a GPU is used it is obtained through
`/home/sdegan/gpu-broker/gpu-run` and the broker request id is recorded.** The
execution mode is never inferred. If no GPU arm is built, the results document
says so in those words and nothing is left outstanding to prove later.

### 6.3 Defect and stop rules

* **D1.** `eta > 1 + 3 sigma_eta` is a defect: a burn cheaper than the node-burn
  ideal is impossible under (1), so it means the natural subtraction over-removed
  or the elements are inconsistent. Flagged, counted, excluded from the primary
  distribution, cause named per object.
* **D2.** `theta_net < |di_net|` beyond floating tolerance is a defect: (3)
  forbids it. The run aborts.
* **D3.** The run-time reproduction of tests 1, 3, 7 and 12 runs as assertions
  before any data is read. A failure aborts the run.
* **D4.** The §3.3 drift-direction control failing is not a defect but a
  **verdict**: T10b is reported without a population claim.
* **S1.** Any of the three input hashes mismatching: **stop and report.**
* **S2.** The archive not opening read-only: **stop.**
* **S3.** Fewer than 10 surviving north-south events: stop, and report the
  census rather than a distribution.
* **S4.** No result in either track is credited as discharged until it appears
  in a committed artifact with its provenance.

---

## 7. Blind spots, named before the measurement

1. **The unmodelled periodic lunisolar terms** (§2.3(c)) are of the same order
   as a tight north-south deadband and are inside the measured `sigma_pole`
   rather than removed. This is the largest known systematic in T10b.
2. **There are no per-element uncertainties in this programme**, and in
   particular **no `sigma_RAAN`**. `sigma_pole` is measured from quiet arcs and
   is an upper bound, not a sigma, and is described that way wherever it appears.
3. **T10b's population is detectability-selected.** With a 1.81% median recall
   on station-keeping, the north-south events that exist in the ledger are the
   large ones. Nothing in T10b generalises to routine, sub-threshold corrections,
   and no sentence in the results may imply it does.
4. **Two burns inside one interval** are seen as one net plane change, which
   biases `eta` **up**. The instrument cannot separate them.
5. **`u_eff` is an effective, interval-averaged burn location**, not the
   argument of latitude of a real ignition. A two-burn pair straddling the node
   returns a `u_eff` neither burn had.
6. **T10c's east-west ledger cannot see a burn below the detector's threshold**,
   and §4.2 derives that the routine burn is 0.068 m/s. The recall ratio is
   published; the missing burns are not recoverable by this instrument.
7. **The eccentricity channel is not modelled in T10c.** Real east-west keeping
   is usually flown so as to steer the eccentricity vector at the same time,
   which changes the per-cycle constant and not the `R`-independence (§4.3).
   How much of the measured east-west delta-v is eccentricity control is
   **unmeasured**.
8. **Neither track validates against an operator-published propellant figure.**
   Every anchor is internal, which is weaker than ground truth, and is not
   described as calibration.

---

## 8. Deliverables

* `docs/stationkeeping-efficiency-results-20260922.md` — both studies, verdict
  first, every number carrying an inline `<!-- src: -->` provenance comment.
* `docs/stationkeeping-ns-20260922.jsonl` — one record per north-south event,
  with a leading `_provenance` record naming inputs, hashes, seeds and the
  registration commit.
* `docs/stationkeeping-ew-20260922.jsonl` — one record per station segment,
  same provenance convention.
* `docs/stationkeeping-efficiency-20260922-receipt.json` — input hashes, source
  hash, seeds, counts at every screen, execution mode, wall and CPU seconds, and
  the acceptance-criteria verdict per track, **computed by the tool rather than
  asserted by the author**.
* `tools/stationkeeping_efficiency.py` and
  `tests/test_orbit_stationkeeping_efficiency.py`.

Committed in that order: this registration alone first; then tool and tests;
then results.
