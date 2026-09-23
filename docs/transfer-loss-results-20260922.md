# Transfer loss fractions — measured

Measured 2026-09-22 UTC. Track T10a of `docs/research-program-runbook-20260921.md`
— the first of the three fuel-efficiency studies the T10 charter asks for.
Registered **before any number below existed** in
`docs/transfer-loss-preregistration-20260922.md`, committed alone at `83c5cd4`;
the instrument and its proofs followed at `ac6e002`; this document is the result
the registration binds.

Analysis run, **not a production change**. No detection ran: the event set is
T2's, hash-pinned. No production pricing, published artifact, site number or
label gate was touched. Population is `data/propulsion-catalog-v1.json`, whose
own `policy` field is `commercial-civil-only`, and nothing outside it was read.

---

## The verdict, stated first

Over **58** detected multi-burn orbit-raising transfers on catalogued
commercial-civil satellites, the observed path costs a median of **0.340%** more
delta-v than the direct first-principles transfer between its own observed
endpoints — a median excess of **3.40 m/s**, bootstrap 95% interval
0.137%–0.515% and 1.61–7.91 m/s <!-- src: docs/transfer-loss-20260922-receipt.json, byClass.chemical.medianLossFraction 0.003402760879630873, bootstrap.ci95, excessMpsBootstrap -->.
The four registered acceptance criteria A1–A4 all pass and the tool's computed
verdict for the chemical arm is **INFORMATIVE**
<!-- src: docs/transfer-loss-20260922-receipt.json, byClass.chemical: A1_power true, A2_excludesZero true, A3_aboveNoiseFloor true, A4_notDriftDominated true, verdict "INFORMATIVE" -->.

**But the registered endpoint-robustness check of §5.2 fires**: the median moves
**+54.8%** relative under the registered endpoint-median variant, against a
registered ceiling of 25%
<!-- src: docs/transfer-loss-20260922-receipt.json, endpointSensitivity.registeredRelativeShift 0.5482631011857785 -->.
Registration §5.2 says that when it fires, "the result is reported as
**endpoint-sensitive** and no population claim is made". So:

> **The population median is reported and NOT claimed.** Across the three
> endpoint treatments it lies between **0.229% and 0.527%**
> <!-- src: docs/transfer-loss-20260922-receipt.json, endpointSensitivity: unregisteredOneSidedVariant 0.002287979506317872, baseMedian 0.003402760879630873, registeredCentredMedianVariant 0.005268369112090943 -->.
> That is a range, not an estimate, and it is reported as one.

The reason is not a failure of the instrument: it is that **the median loss is
genuinely tiny**. A 0.34% loss on a 1,400 m/s transfer is 3.4 m/s, which is the
same order as the ambiguity in which archived element set marks the endpoint of
the transfer. The measurement is at the scale of its own ruler, and the
registration's rule is the correct verdict on that.

What **is** robust is the tail and the per-event numbers. **20 of the 58**
events have all three endpoint treatments within ±25% of the primary value
<!-- src: computed from docs/transfer-loss-20260922.jsonl: count of informative rows with min(lossFraction, lossFractionEndpointMedian, lossFractionOneSidedMedianUnregistered) > 0 and spread <= 0.25 * lossFraction -->,
and those carry a median loss of **0.545%** and a median excess of **8.26 m/s**
<!-- src: same computation over docs/transfer-loss-20260922.jsonl -->. Named
examples are in §6.

Summed over all 58 transfers the measured excess is **3,021.3 m/s** of delta-v
and **2,459.3–2,480.8 kg** of propellant at the two edges of the catalogued
raising-leg Isp bands
<!-- src: computed from docs/transfer-loss-20260922.jsonl, sum of excessMps and of excessPropellantKgBand over informative rows -->.

**The electric arm is empty and that is the result.** Of **14** catalogue
objects with a catalogued electric orbit-raising leg, **3** have any detected
raising phase at all, and **0** survive the screens
<!-- src: docs/transfer-loss-20260922-receipt.json, diagnostics.catalogueElectricRaisingObjects 14 and diagnostics.electricArm (3 rows, all screened) -->.
The Edelbaum machinery is derived, implemented, tested and has nothing to
measure. Verdict **UNDERPOWERED**, n = 0. §7.

---

## What this instrument can and cannot see

Restated from registration §0 because it decides what every number below means.

Element sets record the orbit change that **was achieved**. The propellant that
produced the shortfall of a finite burn arc left no trace in them. Therefore:

* **Gravity loss is invisible.** Not small — invisible. No TLE-differencing
  instrument can measure one, and this document does not describe any number in
  it as a gravity loss.
* **In-burn steering loss is invisible**, for the same reason.
* **What survives is the path.** The estimand is the excess of the observed
  multi-burn path over the direct ideal between its own observed endpoints.

Both sides of the ratio are computed by the same function, so the comparison
carries no pricing-convention difference. Both are exact: no first-order
expansion appears anywhere in this track, after T2's screen measured the
first-order tangential relation overstating the cost by up to **127%** on
exactly these transfer events
<!-- src: docs/repricing-20260921.md, "The first-order screen found something larger than the burn point": max 1.26891595 -->.

---

## The minima, derived

Three relations, all from registration §1, all reproduced at run time against
independently computed closed forms before any data is read
<!-- src: docs/transfer-loss-20260922-receipt.json, runtimeProofs -->.

**One impulse joining two orbits at a shared radius**, plane rotated about the
radius vector (registration eq. 3):

    dv^2 = (v_rB - v_rA)^2 + (v_tB - v_tA)^2 + 4 v_tA v_tB sin^2(di/2)

At an apsis of both orbits the radial terms vanish and this is the **combined-burn
law of cosines**, eq. (4):

    dv^2 = vA^2 + vB^2 - 2 vA vB cos(di)

**Two impulses, apsis to apsis, with the plane change split optimally**
(eq. 5–6). With `J(d1) = dv1(d1) + dv2(di - d1)`, the optimum satisfies

    (vA1 vt1 sin d1) / dv1  =  (vt2 vB2 sin d2) / dv2

— **the marginal cost of an extra radian of rotation is equal at the two
burns.** The registered impulsive minimum (eq. 7) is the smaller of these over
the shared-radius single impulse and the four apsis pairs.

**Edelbaum, for low thrust** (eq. 9), from T. N. Edelbaum, "Propulsion
Requirements for Controllable Satellites", *ARS Journal* **31**(8), 1079–1089,
1961:

    DV = sqrt( v0^2 + vf^2 - 2 v0 vf cos( (pi/2) di ) ),   v = sqrt(mu/r)

The averaged rate equations and their `2/pi` inclination factor are derived in
the registration; the `pi/2` inside the cosine is Edelbaum's and is cited, not
claimed. The registration then derives the property the electric arm depends on:
(9) is the Euclidean distance between `(v0, (pi/2) i0)` and `(vf, (pi/2) if)` in
polar coordinates, so it obeys the triangle inequality **exactly** and the
electric path loss is non-negative by construction.

Run-time reproduction, computed by the tool and not asserted here:

| Closed form | Independent value | Instrument |
| --- | ---: | ---: |
| GTO (185 × 35,786 km, 28.5°) → GEO combined apogee kick | 1,837.4396175374018 m/s | 1,837.4396175374022 m/s |
| Hohmann 7,000 → 42,164 km, coplanar | 3,770.728927574946 m/s | 3,770.728927574945 m/s |
| Edelbaum LEO(300 km, 28.5°) → GEO | — | 5,950.768 m/s |
| Split condition (6) residual, worst of 200 randomised cases | 0 | 8.88e-16 |
| Dense-grid cross-check, worst gap over the same 200 | ≤ 0 | 0.0 km/s |
| Interior optimum strictly beats both endpoints | 200 of 200 | 200 |

<!-- src: docs/transfer-loss-20260922-receipt.json, runtimeProofs -->

---

## Why the median is so small — a derivation, not a shrug

A reader's first reaction to a 0.34% median path loss on transfers that are
routinely flown in three to five burns should be that the instrument is not
measuring anything. It is; the reason the number is small is algebra.

Consider **N successive tangential burns at the same apsis**, raising the
semi-major axis monotonically through `a1 -> a2 -> ... -> aN`. Each costs
`|v(r, a_k) - v(r, a_{k+1})|` by vis-viva at that fixed radius, and `v(r, a)` is
monotone in `a`. So the sum telescopes:

    sum_k |v_k - v_{k+1}|  =  |v_1 - v_N|

**exactly** — splitting an apogee kick into any number of burns at the same
apogee costs precisely what doing it in one burn costs. It is free. This is why
a multi-burn transfer does not, by itself, pay a splitting penalty, and it is
the reason this study's tail rather than its centre is where the information is.

What the transfers do pay for is everything that breaks that telescoping: the
plane change distributed across burns at speeds other than the optimum, burns at
radii that are not the apsis, apogee walking away from the node, and detours. A
median of 3.4 m/s is the measured size of all of that together, and it says
something worth saying: **commercial GTO-to-GEO transfers are flown very close
to the impulsive optimum.**

---

## Census and screens

| Stage | Count |
| --- | ---: |
| Catalogue objects carrying a NORAD id | 151 |
| With a catalogued raising leg and launch date | 136 |
| With at least one detected raising-signature interval in the 18-month window | 84 |
| Transfer events built | 84 |
| **Primary population after all screens** | **58** |

<!-- src: docs/transfer-loss-20260922-receipt.json, census and primaryPopulation -->

| Screen | Removed | What it is |
| --- | ---: | --- |
| S1 single-burn identity | 16 | `L = 0` by construction (registration §4.3), so these carry no path information. They are also the count of transfers executed as **one detected impulse** |
| S6 detection incomplete | 9 | `L < -3 sigma_L`: the path is cheaper than the direct minimum, so burns were missed |
| S2 below transfer magnitude | 5 | `D < 100 m/s` |
| S3 not a raise | 2 | `a` did not increase over the phase |
| S5 eccentric electric | 2 | Edelbaum is circle-to-circle and these start at `e > 0.76` |

<!-- src: docs/transfer-loss-20260922-receipt.json, screenCounts -->

The registered `K = 1` identity was asserted at run time on all 16 single-burn
phases and held exactly on every one
<!-- src: docs/transfer-loss-20260922-receipt.json, singleBurnIdentityChecked 16; the run aborts under D4 otherwise -->.

### The nine incomplete detections, which are the selection effect made visible

| NORAD | Name | Path m/s | Ideal m/s | `L` |
| --- | --- | ---: | ---: | ---: |
| 43488 | SES-12 | 90.8 | 2,176.2 | −95.83% |
| 48838 | XM-8 | 540.0 | 2,177.8 | −75.20% |
| 44307 | Yamal 601 | 284.8 | 702.1 | −59.44% |
| 20523 | Intelsat 603 | 97.9 | 132.2 | −25.91% |
| 43562 | Telstar 19V | 1,762.4 | 2,235.6 | −21.17% |
| 38331 | JCSAT-13 | 1,076.0 | 1,370.8 | −21.51% |
| 32729 | DirecTV-11 | 1,283.6 | 1,300.6 | −1.31% |
| 41866 | GOES-16 | 996.3 | 996.8 | −0.05% |
| 35696 | AsiaSat 5 | 2,234.33 | 2,234.36 | −0.0013% |

<!-- src: docs/transfer-loss-20260922-receipt.json, diagnostics.negativeLossValues -->

The top six are transfers the archive only partly watched — exactly the failure
mode the fuel odometer named when three of its twelve dry-mass objects recovered
only 1.4%–12.9% of the catalogued mass drop
<!-- src: docs/fuel-odometer-20260920.md, "Sanity anchor 2" -->. The bottom three
are a different thing and are reported as such: at |L| below 0.1% they are the
restricted minimum family of registration §1.4 being slightly slack, not missing
burns. S6 removes both, as registered, and the distinction is named rather than
blurred.

---

## A defect the registration did not anticipate, found and fixed

**The instrument was charging operators for the nodal regression the Earth's
oblateness provides free.**

Registration §1.2 says `di` is "the angle between their planes", and the first
implementation computed exactly that from the archived nodes. That is wrong for
a cost: J2 drags the node westward at about a degree a day in low Earth orbit,
and billing that as a plane change bills nature's work to the operator. The
production detector has always known this — its node channel reads only the
residual after the predicted J2 regression is removed, and its own docstring
calls a channel fed the raw difference "very much worse than having no channel
at all"
<!-- src: pipeline/orbit_events.py, Interval.raan_residual_deg docstring -->.

The case that caught it: **Intelsat 603**, 1990-03-17, in the 6,703 km parking
orbit the Titan III left it in. Over 4.54 hours its elements moved 0.24 km in
`a`, 9e-5 in `e` and 0.0088° in inclination — and its node moved about 1.25°,
all of it predicted J2. The uncorrected instrument priced that interval at
**89.45 m/s** against the shipped detector's **1.18 m/s**.

The fix reuses the production module rather than re-deriving it: the plane angle
is now `pipeline.orbit_events.plane_rotation_deg` (whose half-angle form
independently avoids the same `acos`-of-nearly-one trap this instrument hit),
and the node history is reduced by integrating
`j2_secular_rates_deg_per_day` along the **observed** element sets — piecewise,
because over a GTO-to-GEO phase `a` nearly doubles and the regression rate falls
with it, so no single rate describes the phase.

Size of the defect, measured both ways:

| Quantity | Uncorrected | Corrected |
| --- | ---: | ---: |
| Median chemical loss fraction | 0.356% | 0.340% |
| Intelsat 603 phase, detected path | 1,304.8 m/s | 97.9 m/s |

<!-- src: docs/transfer-loss-20260922-receipt.json, j2NodeReduction.uncorrectedMedian 0.0035622676353853633 vs correctedMedian 0.003402760879630873, factor 1.0468756875363494; and diagnostics.negativeLossValues row 20523 against the pre-fix run -->

The median J2 node drift accumulated over a transfer phase is **0.709°**
<!-- src: docs/transfer-loss-20260922-receipt.json, j2NodeReduction.medianJ2NodeDriftDegOverPhase -->.
So the defect is worth 4.7% on the population median and an order of magnitude
on any object that spent time in a low parking orbit. Every number in this
document is the corrected one, and the uncorrected value travels beside it in
the JSONL as `lossFractionRawNode` for every event.

Two further numerical defects were found by the test suite before any data was
read, and are recorded in the instrument's commit message and pinned as
regressions: the law of cosines written in its textbook form let the minimiser
find a GTO-to-GEO transfer 1.3e-5 m/s **cheaper** than the closed form it was
meant to reproduce, and `acos` of two identical orbit poles returned 1.5e-8 rad
of plane change — 2.4e-5 m/s — out of rounding. Both are fixed with algebra, not
with tolerances.

---

## The distribution

| Chemical arm, `n = 58` | Loss fraction | Excess m/s |
| --- | ---: | ---: |
| Minimum | 0.0030% | 0.05 |
| 25th percentile | 0.051% | 0.67 |
| **Median** | **0.340%** | **3.40** |
| 75th percentile | 1.006% | 14.23 |
| 90th percentile | 3.888% | 34.29 |
| Maximum | 74.755% | 1,630.79 |
| Mean | 3.467% | 52.09 |

<!-- src: docs/transfer-loss-20260922-receipt.json, byClass.chemical.lossQuantiles and excessMpsQuantiles -->

The excess in propellant, from the rocket equation at both edges of each
object's catalogued raising Isp band and its catalogued launch mass: median
**3.34–3.37 kg**, 90th percentile **38.9 kg**, maximum **1,204 kg**
<!-- src: docs/transfer-loss-20260922-receipt.json, diagnostics.excessPropellantKgLowEdgeQuantiles and excessPropellantKgHighEdgeQuantiles -->.

### The two measured controls

| Control | Value | Registered bar |
| --- | ---: | --- |
| `sigma_L` from the measured element-noise floor, median | 3.38e-06 | A3 needs median `L` ≥ 3 × this; it is ~1,000 × |
| Coast-arc cost as a fraction of the path, median | 0.083% | A4 needs < 25% |
| Coast-arc fraction, 90th percentile | 1.01% | — |
| Events above the 25% coast fraction | 2 of 58 | — |

<!-- src: docs/transfer-loss-20260922-receipt.json, byClass.chemical.medianLossSigma and medianCoastFraction; diagnostics.coastFractionQuantiles and eventsWithCoastFractionAboveA4Threshold -->

The coast-arc control is the only **empirical** delta-v noise measurement this
track has, and it is an upper bound on the noise floor, not a sigma: it contains
fit noise, but also real J2, lunisolar and drag drift and any sub-threshold burn
(registration §5.3). Its median of 0.083% of the path is the honest statement
that the path sums are not made of drift.

---

## Loss against burn count, and the drift orbit

| Detected burns `K` | Events | Median loss |
| ---: | ---: | ---: |
| 2 | 15 | 0.056% |
| 3 | 13 | 0.231% |
| 4 | 13 | 0.214% |
| 5 | 10 | 1.484% |
| 6 | 4 | 0.508% |
| 7 | 2 | 0.494% |
| 8 | 1 | 0.611% |

<!-- src: docs/transfer-loss-20260922-receipt.json, lossByBurnCount -->

Theil–Sen slope: **+0.099 percentage points of loss per additional detected
burn**
<!-- src: docs/transfer-loss-20260922-receipt.json, theilSenSlopeLossPerBurn 0.0009890888466096814 -->.
Descriptive and explicitly not a significance claim, because `K` is a detection
outcome as well as an operational choice (registration §2.4). The §"Why the
median is so small" derivation says the slope should be near zero for coplanar
splitting, and it is: a tenth of a percentage point a burn.

Drift-orbit overshoot — the path's semi-major axis exceeding the final value by
more than ten times the band noise floor, the signature of walking to an
assigned longitude slot — fires on **2 of 58**, whose median excess is
**15.03 m/s** against **3.40 m/s** for the other 56
<!-- src: docs/transfer-loss-20260922-receipt.json, driftOrbit -->. Two events is
not a population and no claim is made from it; it is reported because it is the
mechanism a reader will ask about.

---

## Vehicle families

Families with at least five transfer events; the others are in the receipt with
their counts and no summary statistic, as registered.

| Family | Events | Median loss | Median excess m/s |
| --- | ---: | ---: | ---: |
| SSL-1300 | 21 | 0.214% | 2.98 |
| BSS-702 | 14 | 0.204% | 2.58 |
| Eurostar-3000 | 9 | 0.411% | 6.03 |
| A2100 | 5 | 0.515% | 4.35 |

<!-- src: docs/transfer-loss-20260922-receipt.json, busFamilies -->

**This table is not a ranking and must not be read as one.** The four medians
span 0.204%–0.515%, i.e. about 2 m/s, which is inside the endpoint sensitivity
that made §"The verdict" withhold the population median in the first place. The
within-family spread swamps the between-family difference: Eurostar-3000's own
range is 0.045%–74.76%, SSL-1300's is 0.0030%–35.46% and A2100's is
0.0038%–45.89%
<!-- src: docs/transfer-loss-20260922-receipt.json, busFamilies.EUROSTAR-3000.quantiles, busFamilies["SSL-1300"].quantiles, busFamilies.A2100.quantiles -->.
What the table establishes is that **no family is an outlier**, which is itself
worth a line.

A registration discrepancy, named rather than resolved silently: registration
§2.3's prose described the family normalisation as stripping "after the last
hyphen", while its two worked examples (`BSS-702SP` → `BSS-702`,
`SSL-1300` → `SSL-1300`) define a different rule — truncate after the first run
of digits. The implementation follows the examples, because they are
unambiguous and the prose is not.

---

## Worked examples

Three commercial transfers, all in the endpoint-robust subset.

### Alphasat / Inmarsat-4A F4 (NORAD 39215), Alphabus, Ariane 5, July 2013

Four burns over 5.8 days out of a 229 × 35,834 km, 3.454° transfer orbit into a
35,703 × 35,805 km, 0.021° geostationary orbit. Detected path **1,557.6 m/s**;
direct ideal for the same change **1,478.5 m/s**; excess **79.1 m/s = 5.351%**,
which is **102.5–105.0 kg** of Alphabus propellant
<!-- src: docs/transfer-loss-20260922.jsonl, norad 39215 -->. Its three endpoint
treatments agree to 0.01 percentage points (5.351 / 5.361 / 5.353%), its coast
arcs are 5.3% of the path and its plane backtracking is 0.175°, so the 79 m/s is
not drift and is not an artefact: it is the price of spreading a 3.475° plane
change across four burns at four different speeds.

### Galaxy 11 (NORAD 26038), Boeing BSS-702, December 1999

Five burns over 15.7 days from a 263 × 39,872 km, 5.634° supersynchronous
transfer orbit. Path **1,405.8 m/s** against an ideal **1,379.5 m/s**: excess
**26.4 m/s = 1.911%**, **23.9–24.6 kg**
<!-- src: docs/transfer-loss-20260922.jsonl, norad 26038 -->. Coast arcs are
0.6% of the path. This is what a well-flown five-burn transfer looks like, and
it is the evidence for the telescoping derivation above: five burns, and the
splitting itself costs nothing.

### Inmarsat 4-F3 (NORAD 33278), Eurostar-3000GM, Proton-M/Briz-M, August 2008

The population maximum and the only event whose excess is measured in tonnes of
propellant: five burns from a 428 × 35,820 km, **45.617°** transfer orbit; path
**3,812.3 m/s** against an ideal **2,181.5 m/s**; excess **1,630.8 m/s =
74.755%**, **1,204–1,207 kg**
<!-- src: docs/transfer-loss-20260922.jsonl, norad 33278 -->.

The mechanism is visible in the elements and is named without being explained
away: the fourth burn takes the inclination from 7.469° **up** to 22.203°, and
the fifth brings it back down to 3.079°. Total plane angle walked 75.80° against
a net 42.855° — a backtrack of **32.944°**, against a second-largest of 2.589°
(Thuraya 2), so the largest in the population by a factor of twelve
<!-- src: docs/transfer-loss-20260922-receipt.json, diagnostics.planeBacktrackDegQuantilesUnregistered: max 32.94446287404922, p90 0.5512576616521332 -->.

**This instrument cannot tell whether that excursion was flown or mis-fitted.**
A 14.7° inclination excursion and reversal mid-transfer is not a manoeuvre any
transfer design calls for; it is equally consistent with an element set fitted
to the wrong object during a Briz-M ascent, which is a documented failure mode
of this archive. It is reported at full value, flagged, and not used to support
any population statement. Its endpoint treatments agree to 0.13 percentage
points, so whatever it is, it is in the archive and not in the endpoints.

---

## The electric arm: an empty measurement, reported as one

| Electric arm | Count |
| --- | ---: |
| Catalogue objects with an electric raising leg | 14 |
| With any detected raising phase | 3 |
| Surviving the screens | **0** |

<!-- src: docs/transfer-loss-20260922-receipt.json, diagnostics.catalogueElectricRaisingObjects and diagnostics.electricArm -->

| NORAD | Name | Burns | Screen | `L` |
| --- | --- | ---: | --- | ---: |
| 43175 | SES-14 | 1 | S1, S5 | 0 by construction |
| 43488 | SES-12 | 2 | S5, S6 | −95.83% |
| 54755 | O3b mPOWER F1 | 2 | S2 (`D` = 7.6 m/s) | +82.56% |

<!-- src: docs/transfer-loss-20260922-receipt.json, diagnostics.electricArm -->

Verdict **UNDERPOWERED**, `n = 0`, per acceptance criterion A1. This is the
registered low-thrust blind spot appearing for the third time in this programme
and the first time in a fuel measurement: the fuel odometer called the electric
station-keeping odometer "not merely low, it is structurally blind"
<!-- src: docs/fuel-odometer-20260920.md, "Sanity anchor 1" -->, and T3's
independent cadence channel found 0 of 2,809 Starlink and 0 of 618 OneWeb
payloads
<!-- src: docs/research-program-runbook-20260921.md, T3 -->.

Two things follow, and both are worth more than the null. First, the two
electric transfers the detector *did* see both start at `e > 0.76` — they are
chemically-boosted supersynchronous injections followed by an electric spiral,
so **Edelbaum's circle-to-circle form does not apply to them** and S5 is not a
technicality. A registered follow-up would need the eccentric low-thrust
generalisation, which is a different derivation. Second, SES-12's −95.83% says
the detector caught 91 m/s of a transfer that needed at least 2,176 m/s: the
spiral is not merely under-detected, it is essentially invisible.

---

## Registered secondary: what the shipped detector's pricing is worth

Over the 267 burn intervals in these phases, the shipped detector's own priced
total divided by the exact minimum-impulse cost of the same element change
<!-- src: docs/transfer-loss-20260922-receipt.json, shippedPricingConservatism -->:

| Statistic | Value |
| --- | ---: |
| Median | 0.942 |
| 25th / 75th percentile | 0.821 / 1.009 |
| 90th percentile | 1.258 |
| Minimum | 0.072 |
| Maximum | 93.40 |

So the production price is, at the median, **6% below** the cheapest impulse
that could have produced the observed element change — consistent with its
documented status as a lower bound — with a long tail in both directions. The
extreme is **Galaxy 3C, 2002-06-22**, priced at **629.1 m/s** against an exact
minimum of **6.73 m/s** for an element change of −108 km in `a`, +0.0032 in `e`
and −0.086° in inclination
<!-- src: docs/transfer-loss-20260922.jsonl, norad 27445, interval 2002-06-22T16:29:34Z -->.

This is a **detector audit, not a fuel measurement**, and it is labelled so. It
generalises T2's 127% first-order finding from the tangential channel to the
event total, and it is reported here and acted on nowhere: this track changes no
production pricing (registration §2.5).

---

## Selection effects and the direction of every bias

Registered before the result (§7) and unchanged by it.

**Recall on transfers is high where the archive watched the transfer.** The
measured evidence: of the 12 catalogue objects carrying both a detected transfer
burn and a catalogued dry mass, **9 recover 50.0%–107.5%** of the catalogued
launch-to-dry mass drop, and the other 3 recover 1.4%–12.9% because the archive
began after the transfer
<!-- src: docs/fuel-odometer-20260920.md, "Sanity anchor 2" -->; under T2's
re-pricing that band is 45.5%–105.5%
<!-- src: docs/repricing-20260921.md -->. The cohort's largest genuine single
burn, 1,502 m/s, sits exactly where a textbook apogee kick sits
<!-- src: docs/fuel-odometer-20260920.md -->.

**What could still be missed, and which way it pushes:**

| Missed class | Effect on the measured loss |
| --- | --- |
| Two burns inside one interval, seen as one net change | **down** |
| Sub-threshold trim burns | **down** |
| Continuous low thrust | **down**, to zero — the electric arm above |
| Burns inside archive coverage holes (every one of the 151 objects has at least one) | **down**, and can push `L` negative, which S6 caught 9 times |
| Element change masked by a simultaneous drag or J2 signal | **down** |

**What could manufacture a false positive, and its control:**

| Source | Effect | Control, measured |
| --- | --- | --- |
| Element fit noise inside a detected interval | up | `sigma_L` median 3.38e-06, A3 passes by ~1,000× |
| Real environmental drift charged to the path | up | coast-arc median 0.083% of the path, A4 passes by ~300× |
| Endpoint artefacts | either way | **fired**: §5.2, population median withheld |
| The restricted minimum family making `D` too large | **down** | stated; biases the headline conservatively |

**Net: the measured loss fraction is a lower bound.** Every recall failure
removes delta-v from the numerator and the denominator approximation inflates
the denominator; both push the same way.

---

## Blind spots, named and not filled

1. **There are no per-element uncertainties in this programme.** T5a's design
   says it in those words — "The programme has no measured per-element
   uncertainty on catalogue mean motion for geostationary payloads; honest
   per-element covariances are precisely what T5c is for" — and lists it first
   under "Measured inputs that do not exist"
   <!-- src: docs/matched-filter-design-20260922.md §1.2 and §11 item 1 -->.
   T2's receipt carries no per-event uncertainty either, so **there were no T2
   receipt uncertainties to carry forward**
   <!-- src: docs/repricing-20260921-receipt.json, the perEvent block has no sigma field -->.
   What this track used instead is a **band-level** measured element scatter
   (`CATALOGUE_NOISE_FLOOR`, measured on 787 three-epoch triples on 2026-08-07
   <!-- src: pipeline/orbit_history.py -->) propagated by a 200-draw Monte
   Carlo, and the empirical coast-arc control. Neither is a per-element sigma
   and neither is described as one. **The per-event delta-v uncertainty of this
   instrument remains unquantified in the sense T5c will quantify it.**
2. **The impulsive minimum is a restricted-family minimum**, not the global
   optimum over all transfer geometries (registration §1.4). It is an upper
   bound on the true minimum, so the losses reported are lower bounds. How much
   slack the family carries is **unmeasured**; the three marginal negative
   values in §"The nine incomplete detections" (|L| < 0.1%) are the only
   evidence of its size and they suggest it is small, which is evidence and not
   a bound.
3. **The apse line is ignored.** Neither the minimum nor the path pricing reads
   the argument of perigee, so a transfer that rotated its apse line is priced
   as if it had not. This makes `D` and every path step too cheap by the same
   mechanism; the net effect on the ratio is **unknown in sign** and unmeasured.
4. **Gravity and steering losses are outside the instrument entirely**, §2. Any
   reader who wants those needs telemetry, not element sets.
5. **The endpoint-median sensitivity fired and the population median claim is
   withheld.** A properly posed endpoint-robustness rule — the registered one
   smears each endpoint across the first and last burns, which is why an
   unregistered one-sided variant was computed and reported beside it — is owed
   to a follow-up registration. It is **not** fixed here, because fixing a
   registered check after seeing the number it returns is exactly what
   registration exists to prevent.

---

## Provenance

| Input | sha256 | Verified at run time |
| --- | --- | --- |
| `/tmp/t2-repricing-20260921/events.jsonl.gz` (T2's event set) | `6804c147…3d49e66f`† | yes |
| `/tmp/eol-study-20260920/archive.sqlite3` (13.9 GB, `mode=ro`) | `ffc4c4e5…5b734c3` | yes, re-hashed in full |
| `data/propulsion-catalog-v1.json` | `7f7a50bc…cc72711a9` | yes |

<!-- src: docs/transfer-loss-20260922-receipt.json, inputs.sha256; the run stops under registration §8.3 on any mismatch -->

† The event-set hash is the value T2's **committed** receipt records as
`detectionReceipt.extractionSha256`
<!-- src: docs/repricing-20260921-receipt.json -->, so this track's input is
cryptographically tied to a committed artifact.

**Compute.** The whole study cost **103.1 s wall and 93.8 s CPU** on one core,
including re-hashing the 13.9 GB archive, the 200-draw Monte Carlo on every
phase and two 10,000-draw bootstraps
<!-- src: docs/transfer-loss-20260922-receipt.json, wallSeconds 103.133, cpuSeconds 93.772, executionMode "cpu" -->.
**No GPU arm was built, so no GPU comparison was measured** — the CPU figure is
the entire cost of the study and there is nothing outstanding to prove later.

**Seeds.** Monte Carlo and bootstrap both 20260922, 200 and 10,000 draws
<!-- src: docs/transfer-loss-20260922-receipt.json, seeds -->.

**Instrument.** `tools/transfer_loss.py`,
sha256 `b57c64a0…f9da4087`, which is the value the receipt records as
`sourceSha256` and the value of the committed file
<!-- src: docs/transfer-loss-20260922-receipt.json sourceSha256 against `sha256sum tools/transfer_loss.py` at 31c3b6c -->.

**Suite.** `python -m unittest discover -s tests -p 'test_orbit*.py'` in a clean
worktree at `31c3b6c`: **889 tests, OK, 5 skipped**, against an 837 baseline
<!-- src: git worktree at 31c3b6c, run of 2026-09-22 -->. This track added
**52** tests.

The live tree, which carries 217 uncommitted paths from other sessions, reports
933 tests with 2 errors — `test_orbit_parallel.test_release_passes_worker_override_to_sweep`
and `test_orbit_sweep_gpu.test_build_cache_forwards_execution_without_publication`,
both `sweep.call_args` being `None`. Both reproduce **identically in the clean
worktree** when those two modules are invoked directly rather than through
discovery, so they are order-dependent tests unrelated to this track and not a
regression from it
<!-- src: `python -m unittest tests.test_orbit_parallel tests.test_orbit_sweep_gpu` fails the same way in both trees, while `discover` is green in the clean one -->.

## What a mission designer takes from this

1. **Splitting an apogee kick costs nothing.** Not approximately — exactly, by
   the telescoping identity above, for burns at the same apsis. Burn-duration
   limits are free in delta-v terms and should be chosen on thermal, power and
   coverage grounds alone.
2. **The plane change is where the money is.** Every measured excess above a few
   m/s in this population traces to how the rotation was distributed, not to how
   the raising was split. The equal-marginal-cost condition (6) is the rule that
   prices it, and Alphasat's 79 m/s is what a four-burn distribution of 3.475°
   costs when it is not that rule.
3. **The industry is already close to optimal.** A median path loss of a few m/s
   on a 1,400 m/s transfer, with no bus family an outlier, means the remaining
   margin in GTO-to-GEO chemical transfers is not in flight strategy.
4. **The one place with real money in it is the launch inclination.** The
   population's largest measured excess, 1,631 m/s and over a tonne, is on a
   transfer that started at 45.6° — and the mechanism is a plane excursion, not
   a splitting choice.
5. **If you fly electric, nobody outside your operations centre can audit your
   transfer.** That is a privacy property and a verification gap at once, and it
   is measured here: 14 catalogued electric raising legs, zero measurable
   transfers.
