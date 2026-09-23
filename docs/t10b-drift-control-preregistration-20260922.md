# Pre-registration: the properly-posed drift-direction control for T10b

**Track:** T10 (fuel-burn efficiency), follow-up 1 of 3.
**Owed by:** `docs/stationkeeping-efficiency-results-20260922.md` §3 and the
runbook's T10b OWED item (1) — "a properly posed drift-direction control — the
registered one compares a POOLED heading against a CONSTANT 270 deg, which is
the prediction only at zero inclination, on a population every member of which
is cancelling the drift being looked for".
**Binding parent registration:**
`docs/stationkeeping-efficiency-preregistration-20260922.md` (commit `f0f2b41`).
Nothing here relaxes, re-scopes or re-runs any screen, seed or acceptance rule
of that document. This registration adds a control and states in advance what
the control is allowed to conclude.
**Status:** written and committed ALONE, before any number it describes exists.

---

## 0. The question this control answers, in one paragraph

T10b measured, over 738 detected north-south manoeuvres on 66 commercial-civil
geostationary satellites, a median effective burn location **21.9 degrees off
the nearest node** — 5.2 m/s/yr of a 45.6 m/s/yr north-south budget
<!-- src: docs/stationkeeping-efficiency-results-20260922.md, "The verdicts, stated first", T10b -->.
The registered drift-direction control fired, so that median is **reported and
not claimed**, and the ordering across bus families is what T10b claims instead.
The operator's question is the obvious one: *how sure are you that this is
inefficiency?* There are three ways a 22-degree median could arise that have
nothing to do with sloppy timing:

1. **It is optimal for a different objective.** A north-south operator's target
   is an inclination *vector*, not an inclination magnitude. A burn placed to
   manage where the vector sits relative to its own natural drift — the
   retrograde Laplace-plane circuit measured in commit `a111504` — sits off the
   node by a *predictable* amount. If the measured placement matches that
   prediction, the burns are well flown against an objective this instrument was
   not measuring, and "inefficiency" is the wrong word.
2. **It is an artefact of the instrument.** If the natural-motion subtraction is
   wrong in direction or in rate, the residual it leaves is itself a plane
   rotation, and the estimator will read a burn location off it. An object that
   never manoeuvres has no burn location; if the instrument returns a preferred
   one anyway, the 22 degrees is partly the instrument's own residual.
3. **The bus-family ordering is an accident of grouping.** Five families, five
   medians, monotone in placement — with 16 objects in the largest family and 7
   in the smallest, a monotone ordering is not by itself improbable.

This registration fixes, before looking, the derivation of (1), the measurement
of (2), and the null of (3), and states the decision rule that would falsify
"inefficiency".

---

## 1. What is fixed, what is new, what is not touched

### 1.1 Inputs, hash-pinned

| Input | Path | sha256 |
| --- | --- | --- |
| T10b per-event artifact | `docs/stationkeeping-ns-20260922.jsonl` | verified at run time against the value the run records, and the file's `_provenance.sourceSha256` `c5d0b9702646557ff12d9cfa3cd8346e19c1e32f6f3a567169aa0e64fd94cad4` is asserted unchanged |
| T3 per-object artifact (passive-object roster) | `docs/cadence-results-20260921.jsonl` | verified at run time |
| Archive snapshot, read-only | `/tmp/eol-study-20260920/archive.sqlite3` | `ffc4c4e521ca0c4eb78d5ec48039e8c9032e2f05183e5b3f09fe703bc5b734c3` |
| Detected event set (T2's run) | `/tmp/t2-repricing-20260921/events.jsonl.gz` | `6804c147596fdf2c78c1c6671a97f8037bcd33202dac785db85aac943d49e66f` |
| Propulsion catalogue | `data/propulsion-catalog-v1.json` | `7f7a50bc4dff644705f52ec28fb2c52a7f8589c7be45433a7f4c23dcc72711a9` |

The three hashes in the last three rows are the parent registration's own and a
mismatch is a stop. **The measured population of the control arm is the
committed T10b JSONL, not a re-measurement**, so the 738 events this control
speaks about are by construction the 738 events the published median is computed
from. Nothing is re-detected and no screen is re-evaluated.

### 1.2 What is NOT touched

* **The parent registration's verdict.** The registered §3.3 control fired; its
  registered consequence — no T10b population claim — stands until *this*
  registration's decision rule is discharged, and this document is the only
  thing that may discharge it.
* **Detection, the production sweep, the published site artifacts, Paper A and
  Paper B**, exactly as the parent registration §2.5 lists them.
* **The per-event numbers of the parent run.** `eta`, `theta_net`, `di_net` and
  `u_eff` are read, never recomputed with a different model. The one quantity
  this registration adds to each event is the **sign** of `u_eff` (§2.2), which
  the parent's eq. (8) discards because `arccos` returns `[0, 180]`.
* **Government and military objects.** The T10b population is
  `data/propulsion-catalog-v1.json`, policy `commercial-civil-only`. The passive
  null of §4 reads orbit *geometry* for catalogue-external objects and for those
  objects **no delta-v, propellant mass, fuel quantity or operator inference is
  computed, reported or named** — the null reports angles and counts only. That
  restriction is a stop rule (§7).

---

## 2. The geometry, derived

### 2.1 The inclination vector and the burn direction — an exact identity

Write the orbit pole as the unit vector the parent registration §2.4 uses,

    p = ( sin i sin RAAN,  -sin i cos RAAN,  cos i ),                    (1)

and let `P = (p_x, p_y)` be its equatorial projection, so `|P| = sin i` and the
direction of `P` carries the node. `P` is the inclination vector in the only
sense that matters here: it is a faithful (rotation-preserving) chart of the
pole's position on the sky for the inclinations this population lives at.

A plane change of angle `theta` at argument of latitude `u` rotates the pole
about the radius vector `r_hat(i, RAAN, u)`. Parent eq. (3),
`cos i' = cos(theta) cos(i) - sin(theta) sin(i) cos(u)`, is the `z` component of
that rotation. The statement this control needs is the *other* two components,
and it is exact in the same sense:

> **Identity D1.** For a rotation of the pole by `theta` about `r_hat(i,RAAN,u)`,
> the displacement `dP = P' - P` has `|dP| = theta` to first order in `theta`
> and makes a signed angle of exactly `u` with `P`.

D1 is the two-dimensional form of parent eq. (5),
`i'^2 = i^2 + theta^2 + 2 i theta cos(u)`, which is the law of cosines on the
triangle `(P, dP, P')` — and a law of cosines is a statement about a triangle,
so the angle it encodes is a real angle and can be read with a signed
`atan2` rather than an `arccos`. D1 is asserted numerically in §6.1 tests 1–2
over a grid of `i`, `RAAN`, `u` and both senses of `theta`, before any data is
read. **Its consequence, and the reason this control exists:** the parent
instrument's `u_eff` is `|` D1's angle `|`, and the sign is recoverable at no
cost from element sets the parent run already published.

**Registered signed estimator.** For each T10b event, with
`P_pred` the projection of the natural-propagated pre-burn pole
(`incPredictedDeg`, `raanPredictedDeg` in the committed JSONL) and `P_after`
that of the post-burn pole (`incAfterDeg`, `raanAfterDeg`):

    dP      = P_after - P_pred
    u_signed = atan2 angle from P_pred to dP, in (-180, 180]              (2)

and the **node departure**

    delta_obs = fold(u_signed),
    fold(x)  = the representative of x modulo 180 lying in (-90, 90].     (3)

`|delta_obs|` is the parent's `nodeOffsetDeg` and §6.1 test 3 asserts that
equality on every event of the committed artifact to `1e-6` deg. If it does not
hold on every event, this control **stops** (§7, S2): a disagreement would mean
the signed form is measuring something other than the published quantity.

### 2.2 Why a *signed* departure is the whole point

`arccos` cannot distinguish a burn 22 degrees early from one 22 degrees late.
Sloppy timing is symmetric — a control loop that fires around the node with
timing jitter produces early and late burns in equal numbers. **Every objective
other than pure inclination removal predicts a *direction*.** The median of
`|u_eff|` therefore cannot separate the hypotheses at all, and no amount of
re-running it would. The signed departure can.

### 2.3 The natural drift direction, per event, from the measured circuit

The natural pole motion is the retrograde Laplace circuit of commit `a111504`:

    dp/dt = s * omega_L ( P_L x p ),   s = -1,   omega_L = 360 deg / T_prec,
    P_L   = (0, -sin L, cos L),        L = 7.4 deg, T_prec = 53 yr.       (4)

The sense `s = -1` is not asserted here: it is the direct measurement of
`a111504`, in which **33 catalogue objects that had stopped north-south keeping
were all retrograde, none prograde**, with a measured median tilt 6.75 deg, a
median circuit rate −6.40 deg/yr, a median period 56.2 yr, and a measured pole
speed at zero inclination of 0.7373 deg/yr against the model's 0.8748
<!-- src: commit a111504, tools/stationkeeping_efficiency.py laplace_calibration -->.
This registration therefore runs the control at **three** drift models and
reports all three, exactly as the parent's R1 does with its rate interval:

* **M-model** — (4) with `T_prec = 53 yr`, `L = 7.4 deg`, `s = -1`: the
  parent run's own primary, so the control is posed on the same dynamics the
  published numbers were computed under. **This is the primary.**
* **M-measured** — (4) with the calibration medians `T_prec = 56.2 yr`,
  `L = 6.75 deg`, `s = -1`.
* **M-prograde** — (4) with `s = +1`, the registration-as-written sense the
  defect fix retired. Included because a control that cannot tell the corrected
  model from the broken one is not a control, and §5 registers that as a
  falsifiable expectation.

The **drift direction at an event** is the projection of (4) evaluated at that
event's own pole:

    D = projection of ( s * omega_L ( P_L x p_pred ) ) onto (x, y),
    psi = signed angle from P_pred to D, in (-180, 180].                  (5)

`psi` is a per-event quantity with **no free parameter**: it is fixed by the
object's own inclination and node and by a circuit whose geometry was measured,
not fitted, on a disjoint set of objects. This is what "properly posed" means
here, and it is the precise repair of the registered control's defect: the
registered control compared a pooled heading against the constant 270 deg, which
is `psi`'s prediction **only at `i = 0`**, and only in the prograde sense.

At `i = 0` exactly, (4) with `s = -1` gives `dP` along `+x_hat`, i.e. toward
`RAAN = 90 deg` — the mirror of the registered 270 deg, which is the same
statement `a111504` makes when it says the archive's uncontrolled objects walk
the node the opposite way. §6.1 test 5 asserts it.

---

## 3. The hypotheses, each derived to a placement prediction

All three are statements about **where a burn must sit**, derived from an
objective. Each yields a prediction for `delta_obs` and the predictions differ.

### H1 — pure inclination removal (what the T10b estimator's ideal assumes)

The cheapest way to change `|i|` by a given amount is to put the whole rotation
into the magnitude, i.e. `dP` collinear with `P`: `u = 180` for a reduction,
`u = 0` for an increase. Both are node crossings. **Prediction:**

    delta_H1 = 0  for every event.                                        (6)

The measured median `|delta_obs|` = 21.9 deg is the measured departure from (6),
and "inefficiency" is the reading that (6) was the operator's objective and was
missed.

### H2 — drift cancellation (the steady-state station-keeping objective)

A satellite being north-south kept is in a closed cycle: whatever the natural
drift does to the inclination vector over a cycle, the burns must undo, or the
vector would walk away. With one burn per cycle of length `T_c`,

    sum of burn displacements over a cycle = - (drift over the cycle)
      =>  dP = - D T_c,                                                   (7)

so **the burn displacement is antiparallel to the drift direction, whatever the
size, shape or centring of the deadband.** (7) has no free parameter and does
not depend on the box at all; that is what makes it a usable prediction.
Combining (7) with (5):

    u = 180 + psi,      delta_H2 = fold(psi).                             (8)

**Derived corollary, registered as the fuel statement:** by parent eq. (1) the
cost of a cycle is `2 v sin(|dP|/2)` with `|dP| = |D| T_c`, and the number of
cycles per year is `1/T_c`, so the annual cost is `v |D|` **independent of the
deadband width** — the north-south twin of T10c's exact deadband cancellation,
and the reason an operator flying H2 pays 45.6 m/s/yr whatever box it holds.
§6.1 test 8 asserts the cancellation to machine precision. It follows that an
operator flying H2 is **not** wasting propellant even when `delta_obs` is large:
the excess this instrument prices is the price of a magnitude change the
operator never asked for.

### H2b — one-cycle-optimal targeting (the textbook diameter strategy)

The variant in which the operator additionally maximises the cycle length for a
circular deadband of half-width `R` about the origin: place the post-burn vector
at the upstream end of the diameter parallel to the drift, `P_+ = -R D_hat`, so
the free drift carries it the full `2R` across the box. With `|P_pred| = R` at a
signed angle `psi` to `D_hat`, writing `D_hat = (cos psi, sin psi)` in a frame
where `P_pred = R(1, 0)`,

    dP = P_+ - P_pred = -R (1 + cos psi, sin psi),
    angle(dP) = 180 + atan2(sin psi, 1 + cos psi) = 180 + psi/2,

by the half-angle identity, so

    u = 180 + psi/2,    delta_H2b = fold(psi / 2).                        (9)

§6.1 test 6 asserts (9) against a brute-force numerical optimisation of cycle
length over post-burn targets, on synthetic geometry, before any data is read.

**H2 and H2b agree exactly when `psi = 0`, and so do H1 and both of them**: a
perfectly run cycle has the pre-burn vector already along the drift, and then
the drift-managing burn *is* a node burn. That coincidence is important and is
registered as such — **drift management explains an off-node median only to the
extent that `psi` is itself large**, which is measurable and is the subject of
the next paragraph.

### The magnitude ceiling — a pre-check that can settle the question alone

From (8) and (9), the largest median node departure drift management can produce
is

    ceiling_H2  = median |fold(psi)|,
    ceiling_H2b = median |fold(psi / 2)|,                                (10)

both computable from the committed artifact with no fitting. **Registered
pre-check C0:** if `ceiling_H2 < 0.5 x 21.9 deg = 11.0 deg`, then drift
management cannot account for even half the measured median *whatever* the
slopes of §5 turn out to be, and that is reported as the primary finding of the
control. (10) is reported whatever it shows.

---

## 4. The two null arms

### 4.1 The passive-object null — objects that never manoeuvre

**Roster, from a committed artifact.** Every object in
`docs/cadence-results-20260921.jsonl` with `channel = "mean_motion"`,
`class = "passive"` and `regime = "GEO"` — T3's own classification, reused
verbatim and not re-derived. The count is fixed by that file (it is 331; that
number is a property of a committed file and is stated here so the run can
assert it). **Cross-check, registered as a stop:** no object on that roster may
appear in T2's event set with a detected event of any signature. If one does,
the roster is not a passive roster and the arm stops (§7, S3).

**Pseudo-events.** For each roster object, every consecutive pair of archived
element sets that

* both pass the parent's GEO screen N1 (`|a - 42164| <= 300 km`, `e < 0.01`),
* are separated by `0 < span <= 7 days` (parent screen N5 primary), and
* pass the parent's N6 noise screen with the **parent's measured**
  `sigma_pole = 0.000968 deg` — `theta_net >= 5 sigma_pole` and
  `i_pred >= 10 sigma_pole`,

is treated as though it were a detected manoeuvre: the natural motion of (4) is
propagated and subtracted exactly as in parent §2.4, and `delta_obs` is computed
by (2)–(3). This is the parent's own quiet-arc machinery with the estimator
attached to it, and it uses no part of the burn model.

**Registered prediction.** A passive object has no control loop, so there is no
burn to be placed and the estimator is reading the residual of the drift model
plus element noise. If the drift model is right and the noise is isotropic,
`u_signed` is **uniform on `(-180, 180]`**, hence `|delta_obs|` is uniform on
`[0, 90]` with median 45 deg and the axial concentration
`R_2 = |mean(exp(2 i u_signed))|` is zero up to `1/sqrt(n)`.

**Registered statistics.** `R_2` with a Rayleigh test on the doubled angle (the
node is a 180-periodic feature, so the axial form is the correct one), the mean
axial direction, the median `|delta_obs|`, and the full quantiles. Reported at
all three drift models of §2.3.

**Registered readings, fixed now:**

* `R_2` **not** significant at `p < 0.01`, and median `|delta_obs|` within its
  own 95% interval of 45 deg → the instrument manufactures no preferred node
  angle. The 21.9 deg of the kept population is then not an instrument residual.
* `R_2` significant **and** its mean axial direction within 20 deg of the kept
  population's → the instrument manufactures the structure, and the T10b
  headline is an artefact in proportion to the passive concentration. This is
  the outcome that would kill the measurement, and it is registered as such.
* `R_2` significant with a direction **unlike** the kept population's → a
  drift-model residual of measured size; its size bounds how much of 21.9 deg it
  can carry, by §4.2, and that bound is reported.

### 4.2 The drift-model residual bound — derived, not assumed

If the drift model is wrong by a rate error `d_rate` (deg/yr of pole speed), an
interval of length `dt` leaves an unmodelled pole displacement `d_rate x dt`
along the drift direction, which adds vectorially to the true burn displacement
`|dP|` and rotates the inferred `dP` by at most

    delta_bound = arcsin( min(1, d_rate * dt / |dP| ) ).                 (11)

Registered evaluation: `d_rate` = the difference between the model's 0.8748
deg/yr and `a111504`'s measured 0.7373 deg/yr, i.e. **0.1375 deg/yr**; `dt` and
`|dP|` at the committed artifact's own medians. (11) is a **bound on the angular
damage a known rate error can do**, computed per event and reported as a
distribution. It is not subtracted from anything: it is reported beside the
measured median so a reader can see what fraction of 21.9 deg the known
imperfection of the drift model could produce in the worst case.

### 4.3 The bus-family-blind arm

T10b *claims* the family ordering (BSS-702 0.955 / 13.9 deg through
Eurostar-3000 0.861 / 32.3 deg, monotone in placement, spread 2.16–7.35
m/s/yr). With five families and 54 objects carrying a family label, a monotone
ordering is not self-evidently improbable, and the claim has never been tested
against a null.

**Registered permutation null.** The family labels are permuted across the
objects that carry one, **at object level** (events move with their object,
because events on one satellite are not independent draws — the same reason the
parent registration bootstraps objects), `B = 10000` permutations, seed
`20260922`. Families are re-formed from the permuted labels under the parent's
own `>= 5 objects` rule, and two statistics are recomputed on each permutation:

* **F1 spread** — `max - min` of the family median `eta`.
* **F2 monotonicity** — the Spearman rank correlation between family median
  `eta` and family median `|delta_obs|` across families, which is the
  "monotone in placement" claim stated as a number.

Reported: the observed value, the permutation distribution, and the one-sided
permutation p-value for each. **Registered decision: the family ordering remains
CLAIMED only if `p(F1) < 0.01`.** If `0.01 <= p(F1) < 0.05` it is reported as
**SUGGESTIVE, NOT CLAIMED**, in those words; if `p(F1) >= 0.05` the family
claim is **WITHDRAWN** and the results document says so in its first paragraph.

This arm is "blind" in the operational sense as well: the permutation statistic
is computed by code that receives the labels as an opaque list and never reads
the family strings, so no family can be favoured by the analyst's knowledge of
which one is which.

---

## 5. The decision rule — what angle distribution falsifies "inefficiency"

### 5.1 The registered regressions

Over the **informative** events of the committed T10b artifact (the 738 that
carry the published median), two Theil–Sen regressions through the origin,
each with a **non-parametric bootstrap 95% percentile interval resampling
objects, `B = 10000`, seed `20260922`**:

    S_H2  : delta_obs  =  c_H2  * delta_H2   + residual
    S_H2b : delta_obs  =  c_H2b * delta_H2b  + residual                  (12)

`delta_H2 = fold(psi)` and `delta_H2b = fold(psi/2)` from (8) and (9). Both are
run on the **whole** informative population and, as a registered sensitivity, on
the subset with `|psi| <= 90 deg`, where the two foldings cannot disagree about
which node is nearer; the count in each is reported.

Residual medians are reported beside the slopes:

    m_raw = median |delta_obs|,   m_H2 = median |delta_obs - delta_H2|,
    m_H2b = median |delta_obs - delta_H2b|.                              (13)

### 5.2 The decision rule, fixed before the numbers exist

| Outcome | Condition | Verdict, in these words |
| --- | --- | --- |
| **A. Inefficiency FALSIFIED** | (`c_H2` or `c_H2b`) interval **contains 1 and excludes 0**, AND the matching residual median `<= 0.5 m_raw`, AND `ceiling` for that hypothesis `>= 0.5 x 21.9 deg` | "The off-node placement is **explained by inclination-vector drift management**. It is optimal for a different objective than pure inclination removal, and the 21.9-degree median must not be read as inefficiency." |
| **B. Inefficiency SURVIVES** | **both** slope intervals **contain 0 and exclude 1**, AND both residual medians `>= m_raw`, AND the passive null shows no preferred node angle (§4.1 first reading) | "Drift management does not explain the placement. The median is a measurement of **burn placement relative to the node**, robust to the objective the burns were flown against." |
| **C. PARTIAL** | a slope interval excludes both 0 and 1, or a residual median falls strictly between `0.5 m_raw` and `m_raw` | "Partly explained; the explained fraction is `1 - m_H2/m_raw` and is reported. No claim either way." |
| **D. NOT DECIDABLE** | any slope interval contains both 0 and 1 | "**NOT DECIDABLE**" in those words, with the interval printed. |
| **E. ARTEFACT** | the passive null's `R_2` is significant at `p < 0.01` with a mean axial direction within 20 deg of the kept population's | "The instrument returns a preferred node angle on objects that never manoeuvre. The T10b headline is an instrument residual in proportion, and the population median is withdrawn." E **overrides** A–D. |

**The angle distribution that falsifies "inefficiency"**, stated plainly because
that is what was asked: a distribution of signed node departures that **tracks
each object's own `psi`** — i.e. one whose departures are *predicted*, event by
event, by where that satellite's inclination vector sits relative to its own
natural drift — falsifies it. A distribution of signed departures that is
**symmetric about zero and uncorrelated with `psi`** is timing scatter and does
not. A distribution that is **concentrated at a constant angle independent of
`psi`** is neither: it is a fleet convention or an instrument bias, and §4.1
decides which.

### 5.3 What may be claimed if outcome B is reached

Outcome B discharges the parent registration's §3.3 failure **for the
population median only**, and only with this wording registered in advance:

> The median effective burn location of 21.9 degrees off the nearest node
> [interval as published] is CLAIMED as a measurement of burn placement. It is
> NOT claimed as wasted propellant: this instrument cannot see operator intent,
> and an operator steering an inclination vector inside a latitude box is paying
> for a manoeuvre it chose. The corresponding 5.2 m/s/yr is the **price of the
> placement**, and the parent registration's §7 limitation — the estimand is a
> magnitude where the operator's target is a vector — is unchanged by this
> control.

Outcomes A, C, D and E claim nothing about the median, and in every one of them
the parent's "reported, not claimed" stands.

### 5.4 The model-discrimination check

Registered as a falsifiable expectation of this control's own construction: the
**M-prograde** drift model of §2.3 is known to be wrong, and a control with any
power must behave differently under it. Registered check: the passive null's
residual is expected to be **larger** under M-prograde than under M-model, and
the `a111504` measurement predicts the ratio — the measured pole-noise floor
fell 2.3x when the sense was corrected. If the passive null's residual scatter
under M-prograde is **not** larger than under M-model by at least a factor of
1.5, this control has no power to distinguish drift models and says so, in those
words, and outcomes A and B are both withheld.

---

## 6. Implementation and proofs

### 6.1 Offline proofs required before any result document is written

No archive, no network, no event set; every fixture constructed in the test.

1. **D1, magnitude.** For a grid of `i in {0.01, 0.05, 0.5, 2, 10} deg`,
   `RAAN in {0, 37, 123, 290} deg`, `u in {0, 30, 90, 150, 180, 210, 330} deg`
   and `theta in {1e-4 .. 0.1} deg`: `|dP| / theta -> 1` within `1e-6` relative.
2. **D1, angle.** On the same grid and for both senses of `theta`, the signed
   angle from `P` to `dP` equals `u` (for `+theta`) and `u + 180` (for
   `-theta`), within `1e-9` deg.
3. **Agreement with the parent.** For a set of constructed events spanning
   `u_eff` in `[0, 180]`, `|fold(u_signed)|` equals
   `stationkeeping_efficiency.node_offset_deg(argument_of_latitude(...))` within
   `1e-9` deg.
4. **`fold` is an involution on representatives** and maps `(-180, 180]` onto
   `(-90, 90]` with `fold(x) = fold(x + 180)`.
5. **Drift direction at `i = 0`.** Under (4) with `s = -1`, the pole
   displacement of an equatorial GEO orbit heads toward `RAAN = 90 deg`; under
   `s = +1`, toward 270 deg. Both within `1e-6` deg.
6. **H2b is the cycle-length optimum.** For a circular deadband of half-width
   `R`, a constant drift `D`, and a pre-burn vector at `|P| = R` and angle
   `psi`, a brute-force search over post-burn targets inside the box maximises
   the time to the boundary at `P_+ = -R D_hat`, and the resulting burn angle
   matches (9) within `1e-6` deg, for `psi in {0, 15, 45, 90, 135, 179} deg`.
7. **H2 is parameter-free.** For three different box radii and two different box
   centres, (7) returns the same burn *direction*; only the magnitude changes.
8. **The north-south deadband cancels.** Annual cost `= v |D|` to machine
   precision across four decades of `R`, the north-south twin of the parent's
   T10c assertion.
9. **`psi` is well defined and continuous** across `RAAN = 0/360` and returns
   `nan` (never a number) for `|P| = 0`.
10. **Theil–Sen through the origin** recovers a planted slope of 0, 0.5 and 1.0
    on synthetic data with 30% contamination, and its bootstrap interval covers
    the planted value in at least 90 of 100 synthetic replicates at seed
    `20260922`.
11. **The permutation null is exchangeable**: on synthetic data with labels
    assigned at random, the permutation p-value of F1 is uniform (KS test
    against uniform, `p > 0.05`, 200 synthetic datasets, seed `20260922`).
12. **The permutation moves events with their objects** — asserted by
    constructing an object with two events and checking that no permutation
    splits them.
13. **The Rayleigh axial statistic** returns `R_2 = 1` for a perfectly axial
    sample, `R_2 -> 0` for a uniform one within `3/sqrt(n)`, and is invariant
    under adding 180 deg to any subset of the angles.
14. **Eq. (11) is a bound**: for constructed events with a planted rate error,
    the inferred angular error never exceeds `delta_bound`.
15. **Policy**: the passive-arm code path raises if asked for any delta-v,
    propellant or catalogue-priced quantity for a catalogue-external object.

### 6.2 Compute

CPU only, on `pc`, read-only against the archive. The kept-population arm reads
a committed 1,108-line JSONL and does arithmetic; the passive arm reads 331
objects' element histories from the archive, which is the same access pattern
the parent run used for 151. No GPU arm is built, so no `gpu-consumers.json` row
is owed. Expected cost is minutes, and the receipt records wall, CPU and peak
RSS whatever it is.

### 6.3 Stop and defect rules

* **S1** — any input hash mismatch: stop.
* **S2** — `|fold(u_signed)|` disagrees with the committed `nodeOffsetDeg` on any
  informative event by more than `1e-6` deg: stop, and report the disagreement
  as a defect in this control, not in the parent.
* **S3** — any passive-roster object carries a detected event: stop the passive
  arm, report the roster as not passive, and run the remaining arms.
* **S4** — the run writes to the archive or opens it writable: stop.
* **S5** — any catalogue-external object acquires a delta-v or propellant
  number: stop.
* **D1** — if a defect is found in *this* registration's algebra by the test
  suite, it is reported in the results document with its size, the parent's
  numbers are recomputed under the corrected form, and both are published. The
  registration is not edited.

---

## 7. Blind spots, named before the measurement

* **One burn per cycle.** H2's derivation assumes the cycle's drift is cancelled
  by one burn. Real north-south keeping is sometimes flown as a pair a half-cycle
  apart. A pair splits `dP` into two displacements whose *sum* is antiparallel to
  `D`; each member can sit off that direction. H2 is therefore a prediction about
  the **sum**, and applied per event it is an approximation whose error is
  bounded by the angular spread of the pair. This is named, it is not corrected,
  and it is a reason outcome C exists.
* **`psi` uses the model's drift, not the object's own.** Each object's true
  Laplace geometry differs slightly from the population model; `a111504` measured
  that spread on 33 objects. The three drift models of §2.3 bracket it; they do
  not eliminate it.
* **The passive roster is not inclination-matched to the kept population.**
  Passive GEO objects have drifted to high inclination; kept ones sit near zero.
  The estimator's behaviour is inclination-dependent (parent screen N6 exists for
  exactly that reason), so the passive null bounds *the instrument's tendency to
  invent a preferred angle*, not the exact bias at 0.05 deg. The arm reports its
  own inclination distribution beside the result so the mismatch is visible.
* **No operator intent is observable.** Nothing in this control can distinguish
  an operator who *chose* a vector strategy from one who mis-timed a burn and
  happened to land where a vector strategy would. It distinguishes **whether the
  placement is predicted by the drift geometry**, which is the strongest thing
  available from outside, and the results document must say so wherever outcome
  A appears.
* **The family-blind arm tests grouping, not causation.** A small `p(F1)` says
  the spread is larger than label-shuffling produces; it does not say a bus
  causes it. The parent results document already says a bus does not choose when
  its thrusters fire, and that sentence stands whatever this arm returns.

---

## 8. Deliverables

* `docs/t10b-drift-control-results-20260922.md` — the results document, with
  the §5.2 verdict in its first paragraph.
* `docs/t10b-drift-control-20260922.jsonl` — per-event `u_signed`,
  `delta_obs`, `psi`, `delta_H2`, `delta_H2b`, the residuals, the (11) bound,
  and every passive pseudo-event, each with its flags.
* `docs/t10b-drift-control-20260922-receipt.json` — inputs and hashes, seeds,
  the three drift models, the two slopes with intervals, the ceilings, the
  passive null statistics, the permutation p-values, the runtime proofs, and
  wall/CPU/RSS.
* `tools/t10_followup_drift_control.py` — the instrument.
* `tests/test_orbit_t10b_drift_control.py` — the §6.1 proofs.
* One row in `docs/research-program-runbook-20260921.md` under T10.
