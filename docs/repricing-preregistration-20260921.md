# Pre-registration: perigee-speed re-pricing of the tangential delta-v channel

Registered 2026-09-21, **before any re-priced number exists**. This document is
committed alone, ahead of every artifact Track T2 will produce, the same way
`docs/phase3-preregistration-20260921.md` and
`docs/paperb-preregistration-20260920.md` were committed ahead of their
results. The git history of this file is the timestamp. Nothing below may be
changed once a re-priced figure exists; an awkward outcome is reported, not
edited away.

This document does not implement the re-pricing and touches no source file.
It registers the derivation, the estimand, exactly which quantities are
re-priced and which are not, the expected direction, the stop and defect
rules, the reporting rule for Paper A, and the caveat that decides how much
the result is worth.

## 0. Why this exists

The adversarial physics review of 2026-09-20/21 (finding F3, implemented at
`dc06ce4`, with the related impulse-ceiling wording corrected at `aee7ed8`
and `066b205`) established that the detector's tangential channel computes

    dv = n * da / 2,        n = sqrt(mu / a^3)

which is the cheapest tangential impulse **evaluated at the circular speed for
that semi-major axis**. The algebra is right and the burn point is a choice.
On an eccentric orbit the cheapest burn point for a change in semi-major axis
is perigee, and the same `da` there costs less by a factor derived in §1. At
GTO eccentricity `e = 0.73` that factor is 2.5313.

`docs/paper-a-draft-20260921.md` currently states the circular-speed pricing
in §4.1, carries the `sqrt((1+e)/(1-e))` table in its limitations, and names
this re-pricing as **registered future work** in §4.3 rather than performing
it. Sean gave the GO on 2026-09-21 (`docs/research-program-runbook-20260921.md`,
track T2). This document is the registration §4.3 demands.

## 1. The derivation, not the assertion

Physics assumptions are not facts on this estate, so the factor is derived
here from vis-viva and cross-checked against the Gauss variational equation.
Anything below that is not derived is labelled a screen or an estimate.

### 1.1 First-order tangential cost at an arbitrary radius

Vis-viva for a two-body orbit of semi-major axis `a` at radius `r`:

    v^2 = mu * (2/r - 1/a).                                            (1)

An impulse is instantaneous, so `r` is the same immediately before and after
it. Differentiating (1) at fixed `r`:

    2 v dv = mu * da / a^2
    =>  dv = mu * da / (2 a^2 v).                                      (2)

Equation (2) is the whole derivation: the cost of a given `da` is inversely
proportional to the speed at the point where the impulse is applied.

Cross-check against the Gauss variational equation for `a` under a perturbing
acceleration with along-track (tangential) component `f_t`:

    da/dt = (2 a^2 v / mu) * f_t,

which for an impulse (`f_t` integrated to `dv`) gives `da = 2 a^2 v dv / mu`,
identical to (2). The two derivations agree, which is the check, not the
claim.

Two consequences follow from (2) and are used below:

* **Direction.** Only the velocity-parallel component of an impulse appears in
  (2), because only it does work against the orbit's energy. An impulse of
  the same magnitude in any other direction changes `a` by less, so tangential
  is the cheapest direction. This is why the channel is called tangential and
  it is unchanged by this work.
* **Burn point.** `dv` is minimised by maximising `v`, and by (1) `v` is
  largest at the smallest `r`, i.e. at perigee. So perigee is the cheapest
  burn point for a change in semi-major axis, for any bound orbit.

### 1.2 The circular price the pipeline computes

Setting `r = a` (a circular orbit) in (1) gives `v_c = sqrt(mu/a)`, and (2)
becomes

    dv_circ = mu * da / (2 a^2 sqrt(mu/a))
            = (da/2) * sqrt(mu / a^3)
            = n * da / 2,                                              (3)

which is exactly `tangential = 0.5 * n_rad_s * propulsive_metres` in
`pipeline/orbit_events.delta_v`. So the shipped figure is the `r = a` special
case of (2), and no arithmetic in the pipeline is in question.

### 1.3 The perigee price

At `r = r_p = a(1 - e)`, (1) gives

    v_p^2 = mu * (2 / (a(1-e)) - 1/a)
          = (mu/a) * (2/(1-e) - 1)
          = (mu/a) * (1+e)/(1-e)

    =>  v_p = v_c * sqrt((1+e)/(1-e)).                                 (4)

Substituting (4) into (2) and dividing by (3):

    dv_peri / dv_circ = v_c / v_p = sqrt((1-e)/(1+e)).                 (5)

**Equation (5) is the re-pricing factor.** It is 1 at `e = 0`, monotonically
decreasing in `e`, and at `e = 0.73` equals 0.3950561..., whose reciprocal is
2.5312857..., the 2.53 already quoted in Paper A's limitations. The same
substitution at `r = r_a = a(1+e)` gives the maximum over burn points,

    dv_apo / dv_circ = sqrt((1+e)/(1-e)),                              (6)

the reciprocal of (5); §2.3 registers why (6) is reported too.

### 1.4 What (2) is an approximation to, and by how much

Equation (2) is a differential relation. The exact finite-impulse cost of
moving `a1 -> a2` by a tangential burn at radius `r` follows from applying (1)
twice at the same `r`:

    dv_exact(r) = | sqrt(mu (2/r - 1/a2)) - sqrt(mu (2/r - 1/a1)) |.    (7)

The pipeline ships the first-order form, and this re-pricing changes only the
burn point, not the order of the expansion, so (2)/(5) remain primary. But
`da/a` is of order 1e-7 for a station-keeping correction and of order 1 for a
transfer burn, so (7) is evaluated alongside it as a registered **screen** and
reported per event: at perigee (`r = a1(1-e1)`) and at the circular point
(`r = a1`). A large first-order error on the transfer events would be a
separate finding about the pipeline, not about the burn point, and this
registration reserves the right to report it and not to act on it here.

## 2. Estimand

### 2.1 Primary

For every detected event `k` in the re-run population (§3), the re-priced
tangential channel

    tangential_peri(k) = tangential_circ(k) * sqrt((1 - e_k) / (1 + e_k))

with `e_k` the interval eccentricity the detector already carries
(`Interval.eccentricity`), and the re-priced event total formed by the
pipeline's own unchanged combination rule:

    in_plane = max(|tangential|, eccentricity_channel, apsidal_channel)
    total    = hypot(in_plane, plane_change).

Two per-object estimands, both already defined by the fuel odometer's
pre-registered rules (`tools/fuel_odometer.py` docstring, rules 1-8, frozen
2026-09-20 and reused here without modification):

1. **Per-object cumulative delta-v**, the sum over retained propulsive events.
2. **Per-object integrated propellant**, the sequential rocket-equation
   integration at both ends of the catalogued Isp band.

Both are computed twice — once from the circular-priced totals, once from the
perigee-priced totals — from the same event set, and reported side by side.

### 2.2 The three Paper A anchors, recomputed under both pricings

1. Station-keeping delta-v as a fraction of the 50 m/s/yr north-south folklore
   budget, over the gap-aware observed years (currently median 1.81% over 54
   chemically kept GEO satellites).
2. Transfer-burn integrated propellant as a fraction of the catalogued
   launch-to-dry mass drop (currently 50.0%-107.5% for 9 of 12 objects).
3. Sourced-graveyard-retiree burned fraction of launch mass (currently median
   0.85%, max 37.7%).

### 2.3 Secondary, reported but not primary

* **The apogee bracket.** Equation (6) applied to the same events gives the
  most any single tangential impulse could have cost. Perigee and apogee
  prices bracket the cost of a single tangential impulse that produced the
  observed `da`, and the bracket is reported per event and per object. It is a
  bracket over **burn points**, not a confidence interval, and it does not
  cover multi-burn or finite-arc manoeuvres, which cost more than either edge.
* **Exact finite-impulse screen.** Equation (7), per event, at both radii.
* **Screen admission delta.** The 2x-perigee-speed implausibility screen in
  `orbit_events.delta_v` drops intervals whose priced total exceeds it. Under
  a hypothetical production adoption of perigee pricing, some dropped
  intervals would be admitted. The count of intervals that the circular price
  rejects and the perigee price would not is measured and reported. It is
  **not** acted on: see §2.4.
* **Rule-7 exclusion delta.** The odometer excludes any single event priced
  above 2,500 m/s as not the satellite's own propulsion. That rule is a
  physical statement about the priced value, so it is applied to whichever
  pricing is being integrated, and the change in the excluded set is reported
  explicitly per object.

### 2.4 What is NOT touched

Registered now so it cannot be relaxed later:

* **The production sweep, the published site artifacts, and every published
  control block.** This track produces dated analysis artifacts only. No
  production pricing changes, no `manoeuvreLabelPermitted` gate is touched, no
  published number is restated from this run.
* **The event set.** Detection — channel tests, persistence, tracking-gap
  declination, inclination corroboration, the 2x-perigee implausibility screen
  — runs on the circular price exactly as production does, so the re-run's
  event set is identical to a production-code re-run's. The re-pricing is
  applied after detection. This is what makes the comparison a pricing
  comparison and not a detector comparison.
* **The plane-change channel**, already evaluated at apogee, which is already
  the true minimum over burn points for a rotation at constant speed.
* **The eccentricity channel.** It charges `v_c * de / 2` against an
  apsidal-tangential infimum of `v_c * de / (2 sqrt(1 - e^2))`, i.e. it
  already charges **less** than the infimum. Re-pricing it would raise costs
  and it is a different physical question; it stays as shipped and stays
  disclosed in Paper A's limitations.
* **The apse-line channel**, already the exact impulse at the crossing point.
* **The combination rule** (max over in-plane channels, quadrature with the
  out-of-plane one).
* **Paper B**, unless a number it quotes changes; if one does, it is corrected
  and the change is named.

## 3. Population, inputs and run

* **Population.** The propulsion catalogue cohort: every object in
  `data/propulsion-catalog-v1.json` carrying a NORAD id (151 objects), full
  retained history. This is exactly the population behind every fuel figure in
  Paper A §4.1 and §4.2, which are the sections this re-pricing changes.
* **Archive.** The same frozen read-only snapshot the EOL study and the
  2026-09-20 odometer used, `/tmp/eol-study-20260920/archive.sqlite3`,
  `sha256 ffc4c4e521ca0c4eb78d5ec48039e8c9032e2f05183e5b3f09fe703bc5b734c3`.
  Opened `query_only`; the run asserts that and aborts otherwise.
* **Detector.** Current `integration/space` code, kappa 32, self-history
  control basis, GPU execution via `pipeline/orbit_sweep_gpu.Execution` on
  bigmem through `/home/sdegan/gpu-broker/gpu-run`.
* **Artifacts.** `docs/repricing-20260921.md`, `docs/repricing-20260921.jsonl`
  and `docs/repricing-20260921-receipt.json`, each carrying source hashes,
  the archive snapshot hash and the broker's own record of the run.

## 4. The control arm, registered before the run

The re-run's **circular arm must reproduce the 2026-09-20 odometer**. Its
headline figures are fixed here so the comparison cannot be softened
afterwards (`docs/fuel-odometer-20260920.md`): 5,341 events detected, 4,888
priced, 4 excluded as not the satellite's own propulsion, median 1.81% of the
folklore budget over 54 objects, at least 130,740.9 kg integrated over 151
satellites, median 5.98% of launch mass.

Any difference is reported **before any re-priced number is interpreted**, and
its cause is named. The detector's source hashes have moved since 2026-09-20
(`aee7ed8`, `c6a7761`, `066b205` comment and prose changes; `061539e` diagnostics recording), so
an exact reproduction is the expectation and a small documented difference is
survivable; a large one stops this track until it is explained.

## 5. Expected direction and the defect rule

Registered predictions, so that agreement is evidence and disagreement is a
defect to chase rather than a finding to write up:

1. Every re-priced event total is **less than or equal to** its circular
   total, and strictly less wherever `e > 0` and the tangential channel is the
   binding in-plane term.
2. GEO station-keeping events sit at `e` of order 1e-4, where (5) is
   0.9998, so anchor 1 (§2.2) moves by **less than 0.1% relative**. If it
   moves more, something other than the burn point changed and the run is
   defective.
3. Transfer-phase events sit at transfer-orbit eccentricity, so anchor 2 falls
   by a factor between 1 and 2.53. A fall outside that range is a defect.
4. The re-priced figure remains a lower bound in the same direction as the
   circular one, so no anchor may **rise**. A rise is a defect.

Any of 1-4 violated: the number is reported with the violation named, and no
Paper A text changes until the violation is explained.

## 6. Reporting rule for Paper A

Fixed here, before the numbers exist:

* Paper A reports **both** pricings wherever a delta-v or propellant total
  appears, with the **perigee-priced figure primary** and the circular-priced
  figure retained beside it for comparability with everything already
  published and with the companion paper.
* §4.1 states the pricing as perigee-speed, derived, with the circular form
  named as the previous convention and the factor (5) given.
* §4.3's registered-future-work item is discharged by pointing at this
  registration and its results document — the item is not deleted, because a
  reader following the 2026-09-21 draft must be able to see that the work
  named there is the work that was done.
* The limitations entry keeps the `sqrt((1+e)/(1-e))` table, re-worded to
  describe what the old convention cost rather than what the current one does,
  and gains the §7 caveat.
* Every re-priced number carries an inline `<!-- src: -->` provenance comment
  in the same style as the surrounding text.

## 7. The caveat that decides what this is worth

**Real burn points are unknown to this pipeline.** It sees two element sets
and prices the cheapest impulse consistent with the difference. Therefore:

* The perigee price is a **lower-cost bound**: no single tangential impulse
  producing that `da` could have cost less, by (2) and (5).
* The circular price is an **upper-side convention**, not a bound: it is what
  the burn would have cost at `r = a`, which for `e > 0` is a point the
  spacecraft actually passes through twice per orbit, so it is a physically
  realisable price rather than an arbitrary one.
* The truth is mixed and in between, per event, and unknowable from this data.

And one sharp consequence that must be stated in Paper A rather than buried:
for the transfer intervals of §4.2 the burn point is **known on physical
grounds to be apogee**, because that is where a geostationary transfer orbit
is circularised. At apogee the same `da` costs `sqrt((1+e)/(1-e))` times the
circular price by (6) — 2.53x **more**, not less. So for exactly the events
where the re-pricing moves the number most, perigee pricing moves it **away**
from the physically expected burn point. That does not make the re-pricing
wrong: an infimum over burn points is what a lower bound means, and the
current text's claim of cheapest-consistent-manoeuvre is only true once the
infimum is taken. It makes the re-priced number a **valid but weaker** lower
bound, and §4.2's recovered fractions will fall for that reason and not
because the measurement improved. Paper A must say so in those words.

A corollary, registered now: the apogee bracket edge (6) is the right figure
to compare against a catalogued transfer propellant load, and §4.2's
consistency check is therefore reported against the bracket, with the primary
perigee figure stated as the bound it is.

## 8. Stop rules

* If the control arm (§4) does not reproduce the 2026-09-20 odometer within a
  difference whose cause can be named, this track stops and reports.
* If any prediction in §5 is violated and cannot be explained by the
  derivation in §1, this track reports the violation and changes no paper
  text.
* If the re-run cannot obtain a GPU grant, it runs on CPU and says so; the
  execution mode is recorded in the receipt either way and never inferred.
* No result in this track is credited as discharged until it appears in a
  committed artifact with its provenance.
