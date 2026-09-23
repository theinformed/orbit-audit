# Station-keeping efficiency — measured

Measured 2026-09-22 UTC. Tracks **T10b** (north-south burn-timing efficiency)
and **T10c** (east-west deadband economics) of
`docs/research-program-runbook-20260921.md` — the two remaining fuel-efficiency
studies after T10a. Registered **before any number below existed** in
`docs/stationkeeping-efficiency-preregistration-20260922.md`, committed alone at
`f0f2b41`; the instrument and its 79 offline proofs followed at `0a2d70b`; this
document is the result the registration binds.

Analysis run, **not a production change**. No detection ran: the event set is
T2's, hash-pinned. No production pricing, published artifact, site number or
label gate was touched. Population is `data/propulsion-catalog-v1.json`, whose
own `policy` field is `commercial-civil-only`, and nothing outside it was read.

---

## The verdicts, stated first

### T10b — north-south burns are flown a median of 22 degrees away from the node, and it costs about 5 m/s a year

Over **738** detected north-south manoeuvres on **66** catalogued
commercial-civil geostationary satellites, the achieved inclination change costs
a median of **1 / 0.898 = 1.113 times** what the same change would have cost at
a node crossing
<!-- src: docs/stationkeeping-efficiency-20260922-receipt.json, t10b.etaBootstrap.median 0.8984067592559668 -->,
implying an effective burn location a median of **21.9 degrees** from the
nearest node
<!-- src: same, t10b.nodeOffsetBootstrap.median 21.92160582559663, ci95 16.066-30.248 -->.
On the 45.6 m/s/yr north-south budget the same lunisolar drift implies (§1.4),
that is **5.2 m/s a year** at the median and **23.9 m/s a year** at the
tenth percentile of efficiency
<!-- src: same, t10b.annualPenalty.medianPenaltyMpsPerYear 5.157998672874796 and p90PenaltyMpsPerYear 23.9182717956321 -->.
All four registered acceptance criteria B1–B4 pass
<!-- src: same, t10b.acceptance: B1_power true, B2_excludesUnity true, B3_aboveNoiseFloor true, B4_notDriftDominated true -->.

**But the registered drift-direction control of §3.3 fires**, and its registered
consequence is that **no population claim is made**. So:

> **The population median is reported and NOT claimed.** The control, the reason
> it fires, and the properly-posed statistic that passes at **0.92** are in §3.
> What is robust — and is claimed — is the per-object and per-bus ordering of
> §5, which survives every registered robustness check by three orders of
> magnitude.

### T10c — theory says a tighter east-west box costs nothing per year, and the detected ledger cannot confirm it

The derivation of §6 ends in

    DV_year = a A(lambda) T_year / 3

**in which the deadband half-width cancels exactly.** A tighter east-west box
does not cost propellant; it costs **manoeuvres**, as `R^-1/2`: at the
±0.021° deadband T3 derived from its 14.00-day line, **26.1 a year**; at
±0.005°, **53.3**; at ±0.05°, **16.8** — all for the same
**1.76 m/s a year**
<!-- src: docs/stationkeeping-efficiency-20260922-receipt.json, runtimeProofs.dvPerYearMpsAtAMax 1.7636107020534197, manoeuvresPerYearAt0p0208Deg 26.110299599056653; the 53.3 and 16.8 are asserted in tests/test_orbit_stationkeeping_efficiency.py -->.

The registered free-drift control, which tests whether `A(lambda)` itself is
real on this archive, **fails as registered** and the registered verdict is
therefore **INPUT NOT VERIFIED**
<!-- src: same, t10c.acceptance: C3_freeDriftControlPasses false, verdict "INPUT NOT VERIFIED" -->.
§7.3 diagnoses why — the registered control fits one straight line across a
median **73.8-day** arc between detected burns, when the theoretical cycle is
**24.0 days** — and an unregistered estimator at the cycle scale recovers
**0.844** of the derived acceleration with a 95% interval of 0.804–0.885 over
474 segments
<!-- src: same, t10c.M4c_freeDriftAdjacentPairUnregistered slope 0.8436604446993932 ci95 [0.8039757277601285, 0.8849752955807899]; t10c.quietArcDaysQuantiles.median 73.82869921874999; t10c.theoryCycleDaysQuantiles.median 24.030085161903912 -->.

And the measured relation between deadband and annual detected delta-v comes out
**positive** — +9.35 m/s/yr per degree of deadband, interval 1.95–23.57
<!-- src: same, t10c.M1_slopeDvOnDeadband -->  — against the theory's zero. **That
is not evidence a looser box costs more.** The registration wrote the reason
down in advance (§4.6): a tighter box makes every burn smaller, and a smaller
burn is less likely to clear the detector's threshold, so the detected ledger
carries a built-in positive slope on deadband whatever the physics does. The
honest statement is in §8.

---

## What these instruments can and cannot see

Restated from registration §0 because it decides what every number below means.

Element sets record the orbit change that **was achieved**. The propellant that
produced the shortfall of a finite burn arc left no trace in them. Therefore
**gravity loss and in-burn steering loss are invisible** — not small, invisible —
and no number in this document is either.

What T10b measures is a **geometric placement efficiency**: what fraction of the
plane rotation the satellite bought went into changing its inclination rather
than swinging its node. What T10c measures is a **detected** east-west ledger
whose recall was already known to be poor: the fuel odometer measured the
detected station-keeping delta-v at a median **1.81%** of the ~50 m/s/yr
folklore budget over 54 chemically-kept GEO satellites
<!-- src: docs/fuel-odometer-20260920.md, "Sanity anchor 1" -->. §6.3 derives
why: a routine east-west correction at the deadband T3 measured is **0.068 m/s**
<!-- src: docs/stationkeeping-efficiency-20260922-receipt.json, runtimeProofs.dvPerCycleMpsAt0p0208Deg 0.06754463675771602 -->,
which is 26 times smaller than a north-south correction on the same cycle.

---

## 1. The ideals, derived

### 1.1 The node burn, exact

A pure plane rotation by `theta` with the speed unchanged rotates the velocity
through `theta`, and the impulse is the chord of that rotation:

    DV_rot(theta) = 2 v sin(theta / 2).

Exact — the isoceles-triangle chord, not a small-angle expansion. The rotation
is about the **radius vector**, because an impulse cannot move the satellite, so
both planes must contain the burn point: the burn point is on the relative node.

### 1.2 What a burn away from the node actually buys, exactly

Rotating the pole about the radius vector at argument of latitude `u` gives
`h' = cos(theta) h - sin(theta) t`, and `t . z = sin(i) cos(u)`, so

    cos(i') = cos(theta) cos(i) - sin(theta) sin(i) cos(u).          (exact)

At `u = 0` this is `i' = i + theta`: the whole rotation becomes inclination,
which is the definition of a node burn. At `u = 90 deg` it is
`cos i' = cos theta cos i`, i.e. `i'^2 = i^2 + theta^2` for small angles — a
burn a quarter-orbit from the node changes the *magnitude* of the inclination
only at second order and spends its rotation on the node instead. Expanded for
small `theta` it gives the first-order statement `di = theta cos(u)`; expanded
for small `i`, `i'` and `theta` together it gives the planar law of cosines
`i'^2 = i^2 + theta^2 + 2 i theta cos(u)`, which is what this population needs,
because a north-south correction at GEO is **not** small against the inclination
it is correcting.

The **exact penalty factor** is `sin(theta/2) / sin(|di|/2)` with `theta` the
solution of the exact relation; its small-angle limit is `sec(u)`, which is
quoted as a limit and never as a price. The instrument inverts the same relation
to read the effective burn location off the element change:

    cos(u) = ( cos(theta) cos(i) - cos(i') ) / ( sin(theta) sin(i) ).

Run-time reproduction, computed by the tool before any data was read
<!-- src: docs/stationkeeping-efficiency-20260922-receipt.json, runtimeProofs -->:

| Closed form | Independent value | Instrument |
| --- | ---: | ---: |
| `i' = i + theta` at `u = 0`, worst of 20 cases | 0 | 3.71e-11 deg |
| T10a's GTO(185 × 35,786 km, 28.5°) → GEO apogee kick | 1,837.4396175374018 m/s | 1,837.4396175374025 m/s |
| Laplace-circuit pole speed at `i = 0` | 0.8748 deg/yr | 0.8743 deg/yr |
| Triaxial `A_max`, T3's form vs T8a's | — | 1.70060e-3 vs 1.70070e-3 deg/day² |
| **`DV_year` independent of deadband, four decades of `R`** | 0 | **1.26e-16 relative** |

The GTO-to-GEO row pins **two instruments under two registrations to one closed
form**: T10a published 1,837.4396175374018 m/s from its own independently
written law of cosines
<!-- src: docs/transfer-loss-results-20260922.md, run-time proof table -->, and
this one reproduces it to 4e-16 relative.

### 1.3 The natural inclination motion — because T10a proved this is where the defect lives

T10a's first cut billed Intelsat 603 **89.45 m/s** for 4.54 hours of the Earth's
oblateness doing its job
<!-- src: docs/transfer-loss-results-20260922.md, "A defect the registration did not anticipate" -->.
T10b's entire subject is inclination at GEO, where the dominant motion is
lunisolar precession. The registered model is a rigid rotation of the orbit pole
about the **Laplace pole**, which at GEO sits `L = 7.4 deg` from the equatorial
pole with a circuit period of about 53 years — the geometry
`docs/cadence-s1s2-preregistration-20260922.md` §3.1–3.2 derived from the
Kozai/Allan-Cook rates (Sun 0.73717 deg/yr, Moon 1.60520 deg/yr) and checked
against Soop's 0.75–0.95 deg/yr. The J2 nodal regression is taken from the
production module `pipeline.orbit_events.j2_secular_rates_deg_per_day` and the
plane geometry from `pipeline.orbit_events.plane_rotation_deg`, imported rather
than re-derived, exactly as T10a's fix did.

The motion is subtracted as a **vector**, and the uncorrected companion travels
beside every corrected number in the JSONL.

### 1.4 The north-south budget, for scale

Correcting 0.85 deg/yr costs `2 v sin(0.425 deg) = 45.61 m/s/yr`
<!-- src: docs/stationkeeping-efficiency-20260922-receipt.json, runtimeProofs.northSouthBudgetMpsPerYear 45.61308250437111 -->,
the standard published figure, and **26 times** the east-west budget of §6. On a
14-day cycle that is 1.75 m/s a burn against east-west's 0.068 m/s. This is the
derived reason the detected east-west ledger is recall-limited and the detected
north-south ledger is not empty.

---

## 2. Two defects in the registered natural-motion model, found and fixed

Both are reported the way T10a reported its J2 defect: named, measured, and with
the registered-as-written value published beside every corrected one as
`etaRegisteredAsWritten`.

### 2.1 Registration eq. (10) double-counts the oblateness — found by the test suite before any data was read

Registration §2.3(b) adds the production J2 nodal regression on top of the
Laplace-plane rotation. That is wrong, and the source the registration itself
cites says why: the Laplace pole sits at 7.4° **because** J2's −4.8995 deg/yr
competes with the lunisolar torque — "which is what tilts the GEO Laplace plane
to roughly 7.4 deg instead of 23.4 and reduces the drift"
<!-- src: docs/cadence-s1s2-preregistration-20260922.md §3.1 -->. A Laplace-plane
rotation is therefore **already** the combined secular motion. Adding eq. (10)
makes an orbit lying exactly on the Laplace plane precess at
`4.8995 sin(7.4°) = 0.63 deg/yr`, which that plane's own definition forbids, and
a test asserts both halves of that statement.

Measured size on this population: median plane-rotation difference **9.9e-7 deg**
before the second defect was fixed and **1.11e-3 deg** after, against a median
plane rotation of 0.0400 deg — 2.8% — with a maximum of 3.61e-3 deg
<!-- src: docs/stationkeeping-efficiency-20260922-receipt.json, t10b.registrationDefects_naturalModel -->.
The median efficiency moves from 0.8984 to 0.8989: **0.06%**.

### 2.2 Registration eq. (9) did not state the SENSE of the circuit, and its unstated default is backwards — found by the registered control

Eq. (9) is `dp/dt = omega_L (P_L x p)` with `omega_L = 360 deg / 53 yr`, which
reads as a prograde circuit. That sends an initially equatorial GEO pole toward
**RAAN 270 deg**. The registered drift-direction control of §3.3 exists to test
exactly that prediction, and it fired.

**The archive settles it.** Eleven retired commercial-civil GEO satellites, all
of which stopped north-south keeping and then drifted freely, were measured
directly — and the calibration was then run over the whole catalogue, where
**33 objects qualify and every one of them is retrograde**
<!-- src: docs/stationkeeping-efficiency-20260922-receipt.json, laplaceCalibrationUnregistered.allRetrograde true, n 33 -->:

| Measured on 33 catalogue objects | Median | p25 / p75 | Model |
| --- | ---: | ---: | ---: |
| Laplace-pole tilt | **6.75°** | 6.44 / 7.48 | 7.4° |
| Signed circuit rate | **−6.40 deg/yr** | −6.82 / −6.21 | +6.79 deg/yr |
| Circuit period | **56.2 yr** | 52.8 / 57.9 | 53 yr |
| Pole speed at `i = 0` | **0.7373 deg/yr** | 0.711 / 0.833 | 0.875 deg/yr |

<!-- src: docs/stationkeeping-efficiency-20260922-receipt.json, laplaceCalibrationUnregistered -->

Worked instances, none of them fitted — each is one object's own element history
<!-- src: same, laplaceCalibrationUnregistered.perObject -->:

| NORAD | Name | Years uncontrolled | Inclination | Tilt | Circuit rate | Pole speed |
| ---: | --- | ---: | --- | ---: | ---: | ---: |
| 20315 | Intelsat 602 | 21.5 | 3.00° → 14.37° | 7.07° | −6.673 deg/yr | 0.821 deg/yr |
| 20523 | Intelsat 603 | 20.9 | 3.00° → 14.08° | 6.78° | −6.667 deg/yr | 0.787 deg/yr |
| 21222 | Anik E2 | 20.2 | 3.00° → 14.15° | 6.89° | −6.591 deg/yr | 0.791 deg/yr |
| 21765 | Intelsat 601 | 18.9 | 3.00° → 13.48° | 6.42° | −6.506 deg/yr | 0.728 deg/yr |

An uncontrolled GEO orbit climbs to **twice the Laplace tilt** and comes back,
and its node walks from about 75° down through 45° to 0° as it does. The archive
shows exactly that, and the prograde model shows the mirror image of it.

**Three independent confirmations that the corrected sense is right:**

1. All 33 calibrated objects are retrograde, none prograde.
2. The **measured pole-noise floor fell by a factor of 2.3** when the sense was
   corrected, from 0.00227 deg to **0.000968 deg**
   <!-- src: docs/stationkeeping-efficiency-20260922-receipt.json, poleNoiseFloor.sigmaPoleDeg 0.0009683819956551464; the 0.00227 is the same field measured in this session's pre-fix development run, whose artifacts are not published -->.
   The residual left after removing a model gets smaller when the model gets
   right, and that is 948,942 quiet arcs saying so.
3. The properly-posed per-arc control statistic changes sign, from **−0.92** to
   **+0.92** on arcs where the object is not being north-south kept
   <!-- src: same, driftDirectionControl.unregisteredUnkeptSubsets["inclinationAtLeast0.5deg"].projectedRateRatio 0.9207191524249946 -->.

**Measured against the registration's own interval:** the calibrated pole speed,
0.7373 deg/yr, sits **just below** the registered 0.75–0.95 deg/yr and well
below the 0.85 central figure the registration carried from Soop. That is
reported as a measurement, not used to change the registered model; the
registered R1 sensitivity spans 0.75–0.95 and an **unregistered** R1 variant at
the measured 0.7373 is published beside it (§4).

---

## 3. The registered drift-direction control, which fired

| | Measured | Registered bar |
| --- | ---: | --- |
| Pooled heading of observed quiet-arc pole motion | **55.4°** | within 20° of 270° |
| Separation from the prediction | **145.4°** | ≤ 20° |
| Arcs | 948,942 | — |

<!-- src: docs/stationkeeping-efficiency-20260922-receipt.json, driftDirectionControl -->

**The registered consequence is applied: no T10b population claim is made.**

The diagnosis, which is the useful part. The registered control compares a
*pooled* heading against a *constant* 270°. That constant is the predicted
heading only at zero inclination; an object already carrying inclination drifts
along its own circle about the Laplace pole, in a direction that depends on
where on that circle it sits. The control is therefore mis-posed for a
population spread over inclinations — and the population is worse than that:
**every object in it is actively cancelling the very drift the control is trying
to see**, and the corrections live inside the quiet arcs because almost all of
them are below the detector's threshold.

The properly-posed statistic is per-arc, not pooled: project each arc's observed
pole displacement onto its own predicted displacement. Unregistered, reported as
such, and it does not change the verdict
<!-- src: docs/stationkeeping-efficiency-20260922-receipt.json, driftDirectionControl.unregisteredProjectedRateRatio and unregisteredUnkeptSubsets -->:

| Arc population | Projected rate ratio | n |
| --- | ---: | ---: |
| All quiet arcs | 0.115 | 948,942 |
| Arcs at inclination ≥ 0.5° (not being north-south kept) | **0.921** | 163,621 |
| Arcs at inclination ≥ 1.0° | 0.916 | 154,767 |
| Arcs at inclination ≥ 2.0° | 0.903 | 139,843 |

Where the object is not being kept, the observed pole motion is **92% of the
predicted magnitude in the predicted direction**. Where it is being kept, the
ratio collapses to 0.115 — which is the station-keeping showing up in a control
designed to measure nature.

**A properly posed drift-direction control is owed to a follow-up registration.
It is not fixed here**, because fixing a registered check after seeing the
number it returns is exactly what registration exists to prevent. The same rule
was applied, for the same reason, to T10a's endpoint check.

---

## 4. T10b: the measurement

### Census and screens

| Stage | Count |
| --- | ---: |
| Catalogue objects with a NORAD id and an event record | 151 |
| Detected `geo-north-south-keeping` + `inclination-change` events | 1,107 |
| **Primary population after all screens** | **738 on 66 objects** |

<!-- src: docs/stationkeeping-efficiency-20260922-receipt.json, census and t10b.n/objects -->

| Screen | Removed | What it is |
| --- | ---: | --- |
| N1 not GEO | 343 | the production detector's own GEO test, reused verbatim |
| N3 inside the raising window | 265 | the odometer's frozen 18 months; those plane changes are T10a's |
| N4 above the odometer ceiling | 4 | shipped price > 2,500 m/s |
| N4 starts before launch | 1 | the odometer's frozen rule |
| N5 span, N6 pole noise, N7 degenerate | **0** | none fired — see below |

<!-- src: docs/stationkeeping-efficiency-20260922-receipt.json, screenCounts -->

Three screens removed nothing, and that is itself a measurement. The **span**
screen at 7 days removed nothing because the events are short: median span
**0.280 days**, maximum 0.779
<!-- src: same, t10b.spanDaysQuantiles -->, so both registered span sensitivities
(3 d and 21 d) return the identical population and the identical median
<!-- src: same, t10b.R5_spanSensitivity -->. The **pole-noise** screen removed
nothing because the median plane rotation is **41 times** the measured floor.

### The distribution

| `n = 738` | Efficiency `eta` | Node offset | Plane rotation | Achieved `|di|` |
| --- | ---: | ---: | ---: | ---: |
| Minimum | 0.264 | 0.03° | 0.0113° | 0.0102° |
| 25th percentile | 0.793 | 11.09° | 0.0333° | 0.0271° |
| **Median** | **0.898** | **21.92°** | **0.0400°** | **0.0346°** |
| 75th percentile | 0.965 | 43.95° | 0.0474° | 0.0398° |
| 90th percentile | 0.993 | 63.64° | 0.0554° | 0.0469° |
| Maximum | 0.99999 | 89.95° | 6.853° | 6.842° |

<!-- src: docs/stationkeeping-efficiency-20260922-receipt.json, t10b.etaQuantiles, nodeOffsetQuantiles, thetaNetQuantiles, diNetQuantiles -->

Bootstrap over **objects**, not events, because events on one satellite are not
independent draws: median `eta` **0.898**, 95% interval **0.873–0.925**; median
node offset **21.9°**, interval **16.1–30.2°**
<!-- src: same, t10b.etaBootstrap and nodeOffsetBootstrap -->.

The median exact-minimum impulse is **2.148 m/s** against an ideal node burn of
**1.854 m/s**, and the excess summed over all 738 events is **252.7 m/s**
<!-- src: computed from docs/stationkeeping-ns-20260922.jsonl over informative rows -->.

**A cross-check the registration did not ask for, and it lands.** The median
achieved inclination change, 0.0346°, is what a 14.8-day north-south cycle
requires at the registered 0.85 deg/yr drift, or a 17.1-day cycle at the
calibrated 0.7373. T3's secondary channel found a north-south line at
**14.00 days carried by 56 named geostationary satellites**
<!-- src: docs/cadence-s1s2-results-20260922.md §3.1 -->. Two instruments with
nothing in common — a Lomb-Scargle line search on inclination, and a
manoeuvre-by-manoeuvre delta-v ledger — put the north-south cadence in the same
place.

### The controls and robustness checks, all five

| Check | Registered rule | Measured | Verdict |
| --- | --- | ---: | --- |
| **B3** noise floor | median `theta` ≥ 5 × `sigma_pole` | 0.0400 vs 0.000968 → **41×** | PASS |
| **B4** not drift-dominated | median natural fraction < 0.25 | **0.0172** | PASS |
| **R1** drift rate 0.75–0.95 deg/yr | median moves < 25% | **0.074%** | insensitive |
| **R1** at the calibrated 0.7373 (unregistered) | — | median 0.8989 | insensitive |
| **R2** no natural subtraction at all | — | median 0.9001 vs 0.8984 | the subtraction is worth 0.19% at the median |
| **R3** shipped price as denominator | — | median **1.0005** | §5.3 |
| **R4** Monte Carlo on the measured floor, 200 draws | median moves < 25% | **0.065%** | PASS |
| **R5** span at 3 d and 21 d | — | identical population | no effect |

<!-- src: docs/stationkeeping-efficiency-20260922-receipt.json, t10b.acceptance, R1_driftRateSensitivity, R1_maxRelativeShift, R2_etaNoNaturalSubtractionQuantiles, R3_etaShippedDenominatorQuantiles, R4_monteCarlo, R5_spanSensitivity; poleNoiseFloor -->

The **pole-noise floor is measured, not assumed**: 1.4826 × MAD of the residual
pole displacement on **948,942 quiet arcs** of these same objects, after the
natural motion is removed — **0.000968 deg**, or 0.000794 deg on arcs under
1.5 days
<!-- src: same, poleNoiseFloor -->. It is an **upper bound on the instrument's
pole noise, not a sigma**: it contains fit noise, but also the unmodelled
periodic lunisolar terms and any sub-threshold burn. The programme has no
`sigma_RAAN` and this track did not invent one.

### The sign split, which says what the estimand really is

**369 events lowered the inclination and 369 raised it**, with median
efficiencies of 0.919 and 0.883
<!-- src: docs/stationkeeping-efficiency-20260922-receipt.json, t10b.signSplit -->.
An exact half-and-half split is not what a ledger of corrections looks like, and
it is the clearest evidence in this study for the limitation named in
registration §7: **a north-south operator's target is an inclination VECTOR, not
an inclination magnitude.** The standard strategy places the vector at one edge
of a latitude box, lets the lunisolar drift carry it across through the origin
to the other edge, and flips it back — a manoeuvre that changes the vector by
the full box width and the *magnitude* by nothing at all.

Where that is what an operator is doing, part of what this instrument prices as
off-node loss is purposeful steering. The measurement stands; the reading
"wasted propellant" does not follow from it without operator intent, and this
document does not make it.

---

## 5. Who flies them where

### 5.1 By bus family

Families with at least 5 objects, on T10a's implemented normalisation
(upper-case, truncate after the first run of digits):

| Family | Objects | Events | Median `eta` | Median node offset | Implied penalty |
| --- | ---: | ---: | ---: | ---: | ---: |
| BSS-702 | 7 | 19 | **0.955** | 13.9° | 2.16 m/s/yr |
| Spacebus-4000 | 9 | 145 | **0.950** | 11.1° | 2.41 m/s/yr |
| A2100 | 8 | 105 | 0.931 | 23.8° | 3.40 m/s/yr |
| SSL-1300 | 14 | 84 | 0.876 | 24.6° | 6.48 m/s/yr |
| Eurostar-3000 | 16 | 335 | **0.861** | 32.3° | 7.35 m/s/yr |

<!-- src: docs/stationkeeping-efficiency-20260922-receipt.json, t10b.busFamilies -->

Unlike T10a's bus table — where the four family medians spanned about 2 m/s and
the honest conclusion was "no family is an outlier" — this one **is ordered and
the ordering is monotone in node offset**, which is the mechanism: the families
that burn closer to the node are the efficient ones. The spread, 2.16 to
7.35 m/s/yr, is 11% of the north-south budget.

**It must still not be read as a bus ranking.** A bus does not choose when its
thrusters fire; an operator's flight dynamics team does, and the Eurostar-3000
group is dominated by one operator's fleet (nine Astra and Eutelsat objects of
the sixteen). What the table establishes is that **burn placement is a fleet
practice, not a physical constant**, and that is visible from outside.

### 5.2 Three named commercial examples

All three are operational commercial geostationary communications satellites,
with at least ten surviving events each. Bus and name are the catalogue's own
fields; no external registry was consulted, the same disclosure T3's §3.6 made
for its carrier list
<!-- src: computed from docs/stationkeeping-ns-20260922.jsonl, per-object medians over informative rows -->:

**Rascom-QAF 1R** (NORAD 36831, Spacebus-4000B3) — 23
events, median node offset **3.1°**, median `eta` **0.977**. Its north-south
burns land essentially on the node; it pays about 1.1 m/s a year for placement.

**Türksat 3A** (NORAD 33056, Spacebus-4000B2) — 64 events, the largest
per-object sample in the study, median node offset **9.5°**, median `eta`
**0.958**. A large, consistent, well-placed set: about 2.0 m/s a year.

**Astra 2E** (NORAD 39285, Eurostar-3000) — 10 events, median node
offset **67.4°**, median `eta` **0.535**. At that placement the same inclination
change costs 1.87 times the node-burn price, about **39.6 m/s a year** on the
45.6 m/s/yr budget. It is also the clearest candidate for the inclination-vector
reading of §4: a burn two-thirds of the way to the quarter-orbit point is what
steering the vector rather than the magnitude looks like from outside.

### 5.3 What the shipped detector's north-south pricing is worth

Over the same 738 events, the production price divided by the exact minimum
impulse for the same element change has median **0.900**, quartiles 0.793/0.965,
and maximum 1.034
<!-- src: docs/stationkeeping-efficiency-20260922-receipt.json, t10b.shippedOverExactMinimum -->.
Under the shipped price as denominator the efficiency is **1.0005** at the median
<!-- src: same, t10b.R3_etaShippedDenominatorQuantiles -->, and that near-exact
unity is the finding:

> **The production detector prices every north-south manoeuvre as if it had been
> flown at the node.** Its price for these events is the plane-change channel
> alone — the plane channel is 100% of the total at the median — and that channel
> is `2 v sin(theta/2)` on its own plane rotation
> <!-- src: computed from /tmp/t2-repricing-20260921/events.jsonl.gz over the 1,107 north-south events: median planeChange/total 1.0, median (2 v sin(planeRotation/2))/planeChange 1.00036 -->.
> It cannot see the off-node penalty, because the penalty lives in the split
> between the inclination and node components and the price is taken on the
> total.

This is a **detector audit, not a fuel measurement**, and it is acted on
nowhere: this track changes no production pricing. It does, however, sharpen the
fuel odometer's own directionality statement: for the north-south events the
odometer *does* catch, its delta-v is low by a further median factor of
**1/0.900 = 1.11** on top of the 1.81% recall.

---

## 6. T10c: the deadband economics, derived

### 6.1 The triaxial acceleration

Earth's triaxiality drives geostationary longitude with
`d2(lambda)/dt2 = -A_max sin(2(lambda - 75.1 deg))`, zero at the two stable
longitudes and maximal midway. Two independently written derivations already in
this repository — T3's `18 n^2 J22 (RE/a)^2` and T8a's
`3 omega_E a_T,max / v_GEO` — are recomputed by the tool and required to agree:
**1.70060e-3** against **1.70070e-3 deg/day²**
<!-- src: docs/stationkeeping-efficiency-20260922-receipt.json, runtimeProofs.aMaxDegPerDay2T3 and aMaxDegPerDay2T8a -->.

### 6.2 The cycle, and why the deadband cancels

A one-sided parabolic drift across a deadband of half-width `R`:

    lambda_dot_0 = 2 sqrt(A R),      T = 4 sqrt(R / A)

which is the relation T3 used to read ±0.0208° off its 14.00-day line. Each burn
reverses the drift rate, and a tangential impulse changes it by
`d(lambda_dot) = -3 dv / a` — from `da = 2 dv / n` and `dn/da = -(3/2) n/a` — so

    DV_cycle = (4 a / 3) sqrt(A R),     manoeuvres per year = (T_year / 4) sqrt(A / R)

and therefore

    DV_year = a A T_year / 3.

**The deadband cancels.** The tool asserts the cancellation across four decades
of `R` at 1.26e-16 relative before it reads any data.

### 6.3 What that means in numbers

| At the maximum-acceleration longitude | Value |
| --- | ---: |
| Annual east-west budget | **1.764 m/s/yr**, at any deadband |
| Per-burn impulse at ±0.0208° (T3's 14.00-day line) | **0.0675 m/s** |
| Manoeuvres per year at ±0.005° / ±0.0208° / ±0.05° | **53.3 / 26.1 / 16.8** |
| North-south budget, for comparison | 45.61 m/s/yr |

<!-- src: docs/stationkeeping-efficiency-20260922-receipt.json, runtimeProofs -->

**A tighter east-west box is not bought with propellant. It is bought with
manoeuvres, as `R^-1/2`.** Halving the box multiplies the manoeuvre count by
1.41 and leaves the annual budget untouched. That is the answer to the question
this track was set, and it is a derivation, not a measurement.

---

## 7. T10c: the measurement, and what it can and cannot say

### 7.1 Census

| | |
| --- | ---: |
| Station segments built on catalogue objects | 834 |
| Segments carrying at least one detected east-west event | **212 on 106 objects** |
| Detected `geo-east-west-keeping` events in the cohort | 2,556 |
| Observed years per segment, median | 1.51 (p75 8.10, max 23.3) |

<!-- src: docs/stationkeeping-efficiency-20260922-receipt.json, t10c and census -->

### 7.2 The measured deadbands, and the two estimators disagreeing

| Deadband half-width | Median | p25 / p75 | p90 |
| --- | ---: | ---: | ---: |
| From longitude excursion (registered primary) | **±0.0452°** | 0.0362 / 0.0589 | 0.0917 |
| From drift-rate amplitude (registered independent) | ±0.0518° | 0.0299 / 0.1608 | 2.945 |
| Ratio of the two | 1.125 | 0.711 / 3.123 | 40.5 |

<!-- src: docs/stationkeeping-efficiency-20260922-receipt.json, t10c.deadbandDegQuantiles, deadbandFromDriftQuantiles, deadbandEstimatorRatio -->

The measured median, ±0.045°, sits exactly where standard GEO practice puts the
east-west box — inside ±0.05°, and wider than the ±0.021° T3 derived from its
14-day line, which is consistent with a 24-day median theoretical cycle rather
than a 14-day one.

The two estimators agree at the median and **disagree badly in the tail**, and
registration §4.5 registered that disagreement as a finding rather than
something to average away. The mechanism is visible in the worked case below:
over a multi-year segment the longitude percentile spread measures the **slot
envelope** — including every slow re-targeting of the nominal longitude — and
not the control box the satellite is actually held in from cycle to cycle.
**Neither registered estimator measures the control deadband, and this is the
largest interpretive limitation of T10c.**

### 7.3 The registered free-drift control fails, and the reason is a timescale

| Estimator of `d(lambda_dot)/dt` against the derived `A(lambda)` | Slope | 95% interval | Segments |
| --- | ---: | ---: | ---: |
| **M4, registered**: one line per arc between detected burns | **0.0097** | 0.0054–0.0145 | 834 |
| M4b, unregistered: sliding 10-day windows | 0.0971 | 0.0691–0.1254 | 718 |
| **M4c, unregistered**: median adjacent-pair slope | **0.8437** | **0.8040–0.8850** | 474 |

<!-- src: docs/stationkeeping-efficiency-20260922-receipt.json, t10c.M4_freeDriftControl, M4b_freeDriftShortWindowUnregistered, M4c_freeDriftAdjacentPairUnregistered -->

The registered control returns 1% of the derived acceleration, so **C3 fails and
the registered verdict is INPUT NOT VERIFIED**. The diagnosis is measured, not
argued: the median arc between *detected* east-west events is **73.8 days**
against a median theoretical cycle of **24.0 days**
<!-- src: same, t10c.quietArcDaysQuantiles.median and theoryCycleDaysQuantiles.median -->.
A satellite's drift rate is a **sawtooth** — it ramps at the triaxial
acceleration and is stepped back by each burn — and almost every burn is below
the detector's threshold, so one straight line through three cycles averages the
ramp against the steps and returns nothing. That is a statement about arc
length, not about physics.

The adjacent-pair estimator is the same quantity measured robustly: the slope
between consecutive element sets lies inside one ramp unless the pair happens to
straddle a step, and the median rejects the steps. It recovers **84%** of the
derived acceleration, and the shortfall is in the conservative direction — the
pairs that do straddle a step pull the median toward zero.

Four named worked cases, each one object's own longitude history against the
acceleration its slot implies
<!-- src: docs/stationkeeping-efficiency-20260922-receipt.json, t10c.M4c_namedExamples; docs/stationkeeping-ew-20260922.jsonl -->:

| NORAD | Name | Slot | Derived `A` | Measured `A` | Ratio |
| ---: | --- | ---: | ---: | ---: | ---: |
| 37393 | Yahsat 1A (Al Yah 1) | +52.50° | +1.207e-3 | **+1.268e-3** | 1.05 |
| 37775 | Astra 1N | +19.20° | +1.579e-3 | **+1.494e-3** | 0.95 |
| 35696 | AsiaSat 5 | +100.50° | −1.318e-3 | **−1.609e-3** | 1.22 |
| 37776 | BSAT-3c | +109.96° | −1.595e-3 | **−1.867e-3** | 1.17 |

Sign and magnitude both, on four satellites in four different slots, two of them
on each side of the stable longitude. **`A(lambda)` is real on this archive.**

Astra 1N is also the worked case for §7.2. Its drift rate runs the sawtooth
plainly — climbing from −0.00734 to +0.00001 deg/day over 4.19 days, then
stepped back — which is a cycle of about 5 days and a control box near
±0.003°, while the longitude percentile spread over its 11.8-year segment reads
±0.051°. The envelope is not the box.

### 7.4 The relation the track was set to measure

| Registered relation | Measured slope | 95% interval | Theory |
| --- | ---: | ---: | ---: |
| **M1** annual detected dV on deadband | **+9.35 m/s/yr per deg** | 1.95 – 23.57 | **0** |
| M1b detected events per year on deadband | −6.20 per deg | −29.97 – 10.79 | negative (`R^-1/2`) |
| **M2** annual detected dV on `A/A_max` | **+0.053 m/s/yr** | −0.350 – 0.311 | **+1.764** |

<!-- src: docs/stationkeeping-efficiency-20260922-receipt.json, t10c.M1_slopeDvOnDeadband, M1b_slopeEventRateOnDeadband, M2_slopeDvOnAcceleration, M2_theoreticalSlope -->

Three things, in order of how much they matter.

**M2 is the decisive one and it is a null.** The detected east-west ledger shows
**no dependence at all** on the triaxial acceleration of the object's own slot —
the interval 
−0.35 to +0.31 excludes the theoretical 1.76 comfortably — even though §7.3 has
just measured that acceleration directly on the same objects and found it real
to within 16%. A ledger that does not track the only quantity that sets the
east-west budget is **not measuring east-west station-keeping**.

**M1's positive slope is the registered confound, not a result.** The
registration wrote it down in advance: per-burn impulse scales as `sqrt(R)`, so a
tighter box makes every burn smaller and less detectable, and the detected
ledger acquires a positive slope on deadband from detectability alone. The
measured slope, 9.35, is larger than the 5.76 that a `DV_year ~ sqrt(R)`
alternative would produce at this population's own medians
<!-- src: same, t10c.M1_sqrtAlternativeSlope 5.761098329008842 -->, and the
registered decidability criterion C2 fails: the interval is too wide to separate
zero from the alternative
<!-- src: same, t10c.acceptance.C2_decidable false -->.

**The residual spread is the real finding.** The ratio of measured to theoretical
annual delta-v, per segment
<!-- src: same, t10c.M3_recallRatio -->:

| Recall ratio (measured / theoretical annual dV) | Value |
| --- | ---: |
| Minimum | 0.009 |
| 25th percentile | 0.169 |
| **Median** | **0.477** |
| 75th percentile | **4.50** |
| 90th percentile | 12.94 |
| Maximum | 69.96 |

That spans **four orders of magnitude**, and **42.9% of segments record more
detected east-west delta-v in a year than the entire theoretical annual budget
for their slot**
<!-- src: computed from docs/stationkeeping-ew-20260922.jsonl, 91 of 212 usable segments with recallRatio > 1 -->. Detected events run at a median **3.20 a year** against a
theoretical **15.2**
<!-- src: same, t10c.detectedEventsPerYearQuantiles and theoryManoeuvresPerYearQuantiles -->.
So the ledger is **both** under-counting routine corrections **and** charging
something else — longitude relocations, larger operational manoeuvres, and
element-fit noise — and the two errors do not cancel, they widen.

The exact re-pricing of the same events says the same thing from the other side:
the production price for an east-west event is a median **0.852** of the exact
minimum impulse for the element change, with a maximum of 8.68
<!-- src: same, t10c.shippedOverExactMinimum, n 1976 -->.

---

## 8. What T10c is allowed to conclude, in the registration's own words

Registration §5.3 wrote four verdict shapes before any number existed, and
**the computed verdict is (iv) INPUT NOT VERIFIED**, because the registered
free-drift control failed.

Stated plainly, and labelled as not one of the four: **none of the registered
shapes fits what was measured.** Shape (ii) requires the control to pass and the
recall-ratio median to be below 0.25; the control failed and the median is 0.477
<!-- src: docs/stationkeeping-efficiency-20260922-receipt.json, t10c.acceptance.C4_recallLimited false; t10c.M3_recallRatio.median 0.4765088293387922 -->.
The registration did not anticipate a control that fails on **timescale** rather
than on physics, and a follow-up registration is owed one that does not. The
substantive position, with the registered verdict standing:

> **The theory's input is verified on this archive and its consequence is not
> measurable from this ledger.** `A(lambda)` is measured directly at 0.84 of its
> derived value on 474 segments and at 0.95–1.22 on four named satellites. The
> deadband-independence of `DV_year` follows from `A(lambda)` by algebra that is
> asserted to 1.26e-16. But the detected east-west ledger carries a median 0.48
> of the theoretical annual budget with an interquartile range of 0.17 to 4.50
> and no measurable dependence on `A(lambda)` at all, so it cannot confirm or
> refute the deadband-independence, and the positive slope it does show is the
> detectability confound the registration named in advance.

**Nothing here licenses the sentence "a looser east-west box costs more fuel."**

---

## 9. Compute, provenance, and what was not built

| Input | sha256 | Verified at run time |
| --- | --- | --- |
| `/tmp/t2-repricing-20260921/events.jsonl.gz` (T2's event set) | `6804c147…3d49e66f`† | yes |
| `/tmp/eol-study-20260920/archive.sqlite3` (13.9 GB, `mode=ro`) | `ffc4c4e5…5b734c3` | yes, re-hashed in full |
| `data/propulsion-catalog-v1.json` | `7f7a50bc…cc72711a9` | yes |

<!-- src: docs/stationkeeping-efficiency-20260922-receipt.json, inputs.sha256, archiveHashVerified true; the run stops under registration §6.3 S1 on any mismatch -->

† The event-set hash is the value T2's **committed** receipt records as
`detectionReceipt.extractionSha256`
<!-- src: docs/repricing-20260921-receipt.json -->. All three inputs are the ones
T10a pinned, with the same values, so the three fuel-efficiency studies rest on
one hash-tied foundation.

**Compute.** Both studies together cost **565.3 s wall and 548.3 s CPU on one
core, 937 MB peak RSS**, including re-hashing the 13.9 GB archive, reading the
whole element history of 151 objects, 948,942 quiet arcs, a 200-draw Monte
Carlo, and five bootstraps
<!-- src: docs/stationkeeping-efficiency-20260922-receipt.json, wallSeconds 565.295, cpuSeconds 548.302, maxRssKb, executionMode "cpu" -->.
**No GPU arm was built, so no GPU comparison was measured** — the CPU figure is
the entire cost of both studies and there is nothing outstanding to prove later.
The compute was measured, not estimated, and nothing here creates a recurring
lane, so no `gpu-consumers.json` row is owed.

**Seeds.** Bootstrap and Monte Carlo both 20260922, 10,000 and 200 draws
<!-- src: same, seeds -->.

**Instrument.** `tools/stationkeeping_efficiency.py`, sha256
`c5d0b970…`, which is the value the receipt records as `sourceSha256`
<!-- src: same, sourceSha256 -->.

**Suite.** `python -m unittest discover -s tests -p 'test_orbit*.py'` in a clean
worktree: **889 tests, OK, 5 skipped** at `f0f2b41` (this registration alone, so
the pre-track baseline) and **968 tests, OK, 5 skipped** at `a111504`
<!-- src: git worktrees at f0f2b41 and a111504, runs of 2026-09-22 -->. This
track added **79** and neither of the two order-dependent errors T10a reported
in the live tree appeared in either run. The live tree, which carries other
sessions' uncommitted work, runs 1,012 and is also green.

**Artifacts.** `docs/stationkeeping-ns-20260922.jsonl` (one record per
north-south event, with a leading `_provenance` record),
`docs/stationkeeping-ew-20260922.jsonl` (one record per station segment, same
convention), `docs/stationkeeping-efficiency-20260922-receipt.json`.

---

## 10. Selection effects and the direction of every bias

Registered before the result and unchanged by it.

### T10b

| Source | Effect on `eta` | Control, measured |
| --- | --- | --- |
| Pole fit noise inflates the rotation without inflating the inclination change | down | `sigma_pole` measured at 0.000968°, median rotation 41× it; R4 moves the median 0.065% |
| Unmodelled periodic lunisolar terms leak into the rotation | down | inside the measured `sigma_pole`, named as its dominant content |
| Drift rate wrong within 0.75–0.95 deg/yr | either way | R1 moves the median 0.074% |
| Drift not subtracted at all (the T10a defect) | either way | R2: 0.19% at the median |
| Two burns inside one interval, seen as one net rotation | **up** | stated; biases the headline toward "efficient" |
| Eq. (13) omits the radial terms, bounded by `e v` | **up** | median bound **1.024 m/s** against a median priced 2.148 m/s — §11 item 1 |
| Only the largest burns are detected (1.81% recall) | unknown sign, large | §11 item 2 |

<!-- src: docs/stationkeeping-efficiency-20260922-receipt.json, t10b.radialTermBoundMpsQuantiles.median 1.0240057421778928, R1_maxRelativeShift, R2_etaNoNaturalSubtractionQuantiles, R4_monteCarlo -->

### T10c

| Source | Effect | Control, measured |
| --- | --- | --- |
| Sub-threshold east-west burns missed | detected dV **down** | M3 recall ratio, median 0.477, published in full |
| Smaller burns in tighter boxes missed more often | M1 slope **up**, spuriously | registered in advance, §7.4 |
| Relocations and large operational manoeuvres counted as station-keeping | detected dV **up** | the segment rule bounds them; a quarter of segments exceed the whole theoretical budget |
| Element fit noise priced as a burn | detected dV **up** | exact re-pricing: shipped is a median 0.852 of the exact minimum |
| Longitude slot misread | `A(lambda)` wrong | measured directly, §7.3 |

---

## 11. Blind spots, named and not filled

1. **The radial terms eq. (13) omits are bounded by `e v`, and that bound is
   half the priced impulse.** Median **1.024 m/s** against a median priced
   2.148 m/s
   <!-- src: docs/stationkeeping-efficiency-20260922-receipt.json, t10b.radialTermBoundMpsQuantiles -->.
   It is an **upper bound on a term whose actual size is unmeasured**: it is the
   worst case, reached only if the radial velocity differs by its full
   eccentric maximum across the burn, and both the ideal and the spent price are
   built from the same plane rotation, so the ratio is far less sensitive to it
   than either side is. The direction is nevertheless known: including the
   omitted term can only raise the denominator, so **the reported efficiency is
   an upper bound and the reported off-node penalty is a lower bound.** This is
   the largest un-eliminated pricing uncertainty in T10b.
2. **T10b's population is detectability-selected.** With a 1.81% median recall on
   station-keeping, the north-south events in this ledger are the large ones —
   median 2.1 m/s, where the derived routine correction on a 14-day cycle is
   1.75 m/s, so they are at least the right size, but nothing here generalises to
   sub-threshold corrections and no sentence above implies it does.
3. **The estimand is the inclination MAGNITUDE, and an operator's target is the
   inclination VECTOR** (§4, the sign split). Where an operator is steering the
   vector, part of the measured off-node placement is purposeful. Separating the
   two needs the operator's target, which no element set carries.
4. **`u_eff` is an effective, interval-averaged burn location**, not the argument
   of latitude of a real ignition. A two-burn pair straddling the node returns a
   `u_eff` neither burn had.
5. **The registered drift-direction control is mis-posed** and a properly posed
   one is owed to a follow-up registration (§3). It is not fixed here.
6. **Neither registered deadband estimator measures the control box** (§7.2);
   both measure the slot envelope over the segment. A cycle-resolved deadband
   estimator is owed to a follow-up registration.
7. **The eccentricity channel is not modelled in T10c.** Real east-west keeping
   is usually flown so as to steer the eccentricity vector at the same time,
   which changes the per-cycle constant and not the deadband-independence. How
   much of the measured east-west delta-v is eccentricity control is
   **unmeasured**.
8. **The calibrated pole speed, 0.7373 deg/yr, sits below the registered
   0.75–0.95 interval.** The registered interval was the cited literature range;
   this archive measures something slightly slower on 33 objects. Which is right
   is **not settled here**; the headline is insensitive to it either way (R1).
9. **Neither track validates against an operator-published propellant figure.**
   Every anchor is internal, which is weaker than ground truth, and is not
   described as calibration.

---

## 12. What a satellite operator takes from this

**From T10b — north-south burn timing:**

1. **Burn placement is worth about 11% of your north-south budget, and it is
   measurable from outside.** The median satellite in this population burns
   21.9° from the node and pays 5.2 m/s a year for it; the tenth percentile pays
   23.9. Nobody needs your telemetry to work that out — two public element sets
   either side of the burn are enough.
2. **The penalty is `sec(u)` to first order, so it is cheap to be nearly right
   and expensive to be badly wrong.** Ten degrees off the node costs 1.5%; thirty
   degrees costs 15%; sixty degrees costs 100%. The whole of the useful margin is
   in the last thirty degrees.
3. **Your fleet's practice shows.** Bus families in this catalogue run from a
   median 11° off-node to a median 32° off-node, and the efficiency ordering
   follows the placement ordering exactly. Whatever sets that is operational, not
   physical.
4. **Your own ledger understates it.** A step detector that prices a north-south
   manoeuvre from its total plane rotation charges you the node-burn price
   whatever you did; the off-node cost is invisible to it by construction, and
   for these events it is a further 11% on top of everything the detector misses.

**From T10c — east-west deadband:**

5. **A tighter east-west box does not cost propellant.** `DV_year = a A T_year/3`
   has no deadband in it. Choose the box on payload pointing, interference and
   co-location grounds; the fuel argument for a loose box does not exist.
6. **A tighter box costs manoeuvres, as the inverse square root of its width.**
   ±0.05° is 17 a year; ±0.021° is 26; ±0.005° is 53. The cost of a tight box is
   flight-dynamics workload and operational availability, and it should be argued
   on those terms.
7. **Your slot sets your east-west bill, not your box.** From 0 at 75.1°E and
   104.7°W to 1.76 m/s a year midway between them — a factor that runs from
   nothing to the whole budget, decided the day the slot was assigned.
8. **Nobody outside can audit your east-west keeping.** A routine correction is
   0.068 m/s and produces no step a public-element-set detector can find. That is
   a privacy property and a verification gap at once, and this study measures it:
   a ledger with 2,556 detected east-west events shows no dependence whatsoever
   on the acceleration that actually sets the bill.
