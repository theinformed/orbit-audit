# Pre-registration: a cycle-resolved east-west deadband estimator

**Track:** T10 (fuel-burn efficiency), follow-up 3 of 3.
**Owed by:** `docs/stationkeeping-efficiency-results-20260922.md` §8 and the
runbook's T10c OWED item (2) — "a cycle-resolved deadband estimator, since
neither registered estimator measures the control box, only the slot envelope".
**Binding parent registration:**
`docs/stationkeeping-efficiency-preregistration-20260922.md` (commit `f0f2b41`),
§4. Its derivations of the triaxial acceleration and of the drift cycle are
reused unchanged and are not re-derived here.
**Status:** written and committed ALONE, before any number it describes exists.

---

## 0. What T10c established, and what it could not measure

T10c derived, and asserted to `1.3e-16` across four decades, that the annual
east-west station-keeping cost

    DV_year = a A T_year / 3                                              (19)

**does not contain the deadband.** A tighter longitude box buys the same
propellant bill in more, smaller manoeuvres: 16.8 a year at `+/-0.05 deg`, 26.1
at `+/-0.0208`, 53.3 at `+/-0.005`, all for 1.76 m/s/yr at the maximum-
acceleration longitude
<!-- src: docs/stationkeeping-efficiency-results-20260922.md §6.2, §6.3 -->.

What it could **not** do is measure the deadband itself. Both registered
estimators read the **slot envelope** over a whole station segment — the primary
from the spread of mean longitude (`0.5 (p97.5 - p2.5)`), the secondary from the
drift-rate excursion — and a segment is months to years long. Over that span the
envelope contains everything: the control box, longitude retargets inside the
0.3-degree segment rule, the periodic terms, and the fit scatter. The measured
median came out at **`+/-0.045 deg`**, roughly twice T3's `+/-0.0208 deg`
inferred from the 14.00-day line, and the two registered estimators disagreed
with each other.

The registered free-drift control returned **INPUT NOT VERIFIED**, and the
diagnosis was a timescale: the median arc between **detected** east-west events
is 73.8 days against a median theoretical cycle of 24.0, so one straight line
through three sawtooth cycles averages the ramp against the steps. An
unregistered adjacent-pair estimator added after that failure recovered 0.844
[0.804, 0.885] of the derived acceleration over 474 segments — good evidence
that the physics is there and the **window** was wrong.

**This registration measures the box cycle by cycle**, on the population T3's
line actually named, and it does not rely on the detected event ledger at any
point.

---

## 1. Inputs, population, and what is not touched

### 1.1 Inputs, hash-pinned

| Input | Path | sha256 |
| --- | --- | --- |
| Archive snapshot, read-only | `/tmp/eol-study-20260920/archive.sqlite3` | `ffc4c4e521ca0c4eb78d5ec48039e8c9032e2f05183e5b3f09fe703bc5b734c3` |
| T3 per-object artifact (the line roster) | `docs/cadence-results-20260921.jsonl` | verified at run time |
| Detected event set (T2's run) | `/tmp/t2-repricing-20260921/events.jsonl.gz` | `6804c147596fdf2c78c1c6671a97f8037bcd33202dac785db85aac943d49e66f` |
| Propulsion catalogue | `data/propulsion-catalog-v1.json` | `7f7a50bc4dff644705f52ec28fb2c52a7f8589c7be45433a7f4c23dcc72711a9` |

The event set is read for **one** purpose — deciding which objects are on the
commercial-civil catalogue and may therefore carry a delta-v number (§1.3). **No
part of the estimator uses a detected event.** That is the point: T10c's
registered control failed because it was anchored to a ledger whose cadence is
three times too slow.

### 1.2 The population — T3's 14.00-day line carriers

The line T3 measured is carried by **208 geostationary payloads of 214**
<!-- src: docs/cadence-results-20260921.md §5.3 -->, and the committed
per-object artifact makes that set exactly reproducible. **Registered
membership rule:** every row of `docs/cadence-results-20260921.jsonl` with

* `channel = "mean_motion"`, `class = "payload"`, and
* at least one entry of `windowPeriodsDays` within the line's own core
  half-width, `0.10888888888888887 d`, of `14.0 d`
  <!-- src: docs/cadence-results-20260921-lines.json, payloadOnlyLineSweep[periodDays=14.0].payload.coreHalfWidthDays -->,

which is `tools/cadence_lines.py`'s `_carriers` selection restated on the
committed artifact. The **primary population** is the subset with
`regime = "GEO"`. The run asserts the counts the committed artifact implies —
**214 objects, 208 GEO and 6 LEO** — and a mismatch is a stop (§6.3, S2). The 6
LEO objects are reported and excluded: a 14-day line in low Earth orbit is not
an east-west deadband and this registration does not pretend otherwise.

### 1.3 Policy — this is the part that needs stating plainly

The line-carrier roster is **not** the commercial-civil propulsion catalogue. It
contains objects outside it, including government payloads, because T3's line
sweep was over the whole public catalogue.

**Registered treatment, and a stop rule:**

* For **every** carrier, this track measures **angles and times only** — the
  deadband half-width in degrees, the cycle period in days, and the longitude
  acceleration in deg/day². These are geometric properties of a public orbit,
  not fuel quantities, and T3 already published the carrier list and its
  longitudes.
* **No delta-v, propellant mass, Isp, lifetime or fuel quantity is computed,
  reported or named for any object outside
  `data/propulsion-catalog-v1.json`.** The delta-v companion figures of §4 are
  computed **only** for carriers that appear in that catalogue, which is stated
  wherever they appear, and the code raises rather than returns if asked
  otherwise (§6.1 test 14).
* The catalogue's own `policy` field must read `commercial-civil-only` or the
  run stops, exactly as in both parent tracks.

### 1.4 What is NOT touched

Detection; the production sweep; the published site artifacts; Paper A and
Paper B; T3's own line result, which is read and never recomputed; the parent
registration's §4 derivations, which are imported from
`tools/stationkeeping_efficiency.py` rather than restated.

---

## 2. The estimator, derived

### 2.1 What a cycle looks like in the elements

Parent §4.2 derives the one-sided drift cycle: inside the box the longitude
acceleration is effectively constant, so `lambda(t)` is a parabola; the
satellite is placed at one edge with a drift rate directed across the box, the
parabola reaches its vertex at the far edge, and a burn fires when it returns to
the first edge. With `R` the deadband half-width and `A` the triaxial
acceleration at the slot,

    2 R = lambda_dot_0^2 / (2 A),   lambda_dot_0 = 2 sqrt(A R),           (15)
    T   = 2 lambda_dot_0 / A       = 4 sqrt(R / A).                       (16)

Two observable consequences, and they are in **different elements**:

* **In longitude.** Over one cycle `lambda` sweeps the full box and back, so its
  peak-to-trough excursion is exactly `2 R`.
* **In mean motion.** `lambda_dot = n(a) - omega_E` **ramps linearly** at
  `-A` through the cycle, from `+lambda_dot_0` to `-lambda_dot_0`, and is reset
  by the burn. The drift rate is therefore a **sawtooth**: monotone ramps
  separated by jumps.

**The cycle boundary is a turning point of `lambda_dot`.** That is the whole
segmentation rule, and it needs no detected event: it reads the manoeuvre off
the elements, which is what the ledger's 73.8-day cadence prevented.

### 2.2 The registered segmentation

Within each station segment (§2.4), the drift rate `lambda_dot` is computed from
mean motion with `tools/proximity_geo.drift_rate_deg_per_day`, imported. The
series is cut into **maximal monotone runs** by a swing filter with a single
threshold:

> walk the samples in time, holding the current direction and the running
> extremum; when `lambda_dot` reverses from that extremum by more than
> `P = k sigma_rate`, close the run at the extremum and open a new one.

`P` is a **prominence** threshold and nothing else; `sigma_rate` is **measured**
(§3.1), not assumed. **Registered `k = 5`**, with `k = 3` and `k = 8` reported as
sensitivities. One run is one **cycle**.

### 2.3 What each cycle yields — three reads, two of them independent

For each cycle, with samples `(t_j, lambda_j, lambda_dot_j)`:

1. **`R_pos`, the PRIMARY — positional and model-free.**

       R_pos = 0.5 ( max_j lambda_j - min_j lambda_j ).                   (20)

   It assumes only that the cycle sweeps the box once, which is what §2.1
   derives. It does not use `A`, it does not use (15), and it does not use a
   fitted rate.

2. **`R_rate` — the rate read, a cross-check through a different element.**
   From (15), the full ramp over a cycle is `2 lambda_dot_0 = 4 sqrt(A R)`, so

       R_rate = (Delta lambda_dot)^2 / (16 A_cycle),                      (21)

   with `Delta lambda_dot` the ramp amplitude and `A_cycle` the magnitude of the
   ordinary-least-squares slope of `lambda_dot` on time **within the cycle** —
   the object's own measured acceleration, not the derived one.

3. **`T_cycle`** — the run's duration, to be compared with (16) at the cycle's
   own `R` and `A`, and with T3's 14.00 d.

`R_pos` and `R_rate` come from **different elements of the same fit** — mean
longitude and mean motion — so their agreement is a real internal check and
their disagreement is a real finding. Parent §4.5 registered the same check at
segment scale, where it failed; this registers it at cycle scale, where §2.1
says it should hold.

**The derived per-object prediction, which is the honest comparison target.**
T3's `+/-0.0208 deg` is (16) inverted at the **maximum-acceleration** longitude;
at half that acceleration the same 14.00-day period implies `+/-0.0104 deg`
<!-- src: docs/cadence-results-20260921.md §5.3, the two-column table -->. A
single number is therefore the wrong comparison target for a population spread
over longitudes. The registered target is per object, at its own slot:

    R_pred = A(lambda_obj) T_measured^2 / 16,                             (22)

with `A(lambda) = A_max |sin(2(lambda - 75.1 deg))|` from parent §4.1. The
comparison against the single `+/-0.0208 deg` figure is **also** reported,
labelled as the max-acceleration special case that it is.

### 2.4 Screens, all registered here

| Screen | Rule | Why it is a screen, not a law |
| --- | --- | --- |
| **G1 GEO band** | `0.95 <= n <= 1.05 rev/day` and `e < 0.01` at the sample | The production GEO test, minus the inclination clause: **longitude keeping is inclination-independent**. `lambda = RAAN + argp + M - theta_GMST` is defined at any inclination and the triaxial torque on it does not involve `i` to first order, so screening on inclination would discard east-west-kept objects for a reason that has nothing to do with east-west keeping. The parent's inclination-bearing screen (`i < 25 deg`) is reported as a registered **sensitivity** |
| **G2 station segment** | T8a's rule, imported: `|lambda - median| <= 0.3 deg` throughout, length `>= 30 d`, a gap over 10 d breaking the run | The parent's own segment rule, reused verbatim |
| **G3 cycle samples** | at least **5** samples in the run | Four points cannot separate a ramp from noise and give a peak-to-trough |
| **G4 cycle duration** | at least **3 days** | Below the archive's own cadence times a few samples, a "cycle" is a sampling artefact |
| **G5 ramp above the floor** | `Delta lambda_dot >= 5 sigma_rate` | `sigma_rate` is MEASURED (§3.1) |
| **G6 above the deadband floor** | `R_pos >= 3 x` the measured floor of §3.2 | Cycles below it are reported as `at-floor`, **counted, and never silently dropped** |

Every screen reports how many cycles it removed and screened-out cycles stay in
the JSONL with their flag.

---

## 3. The floors — measured, never assumed

### 3.1 `sigma_rate`, the drift-rate noise

The programme has no per-element sigma on mean motion; T5a's design lists it
first under "measured inputs that do not exist"
<!-- src: docs/matched-filter-design-20260922.md §1.2 -->. Two figures are
therefore produced and both are published:

* **Propagated**, from the measured band floor: `lambda_dot = n(a) - omega_E`
  and `dn/da = -(3/2) n/a`, so `sigma_rate = (3/2)(n/a) sigma_a` with `sigma_a`
  the `CATALOGUE_NOISE_FLOOR` value for the GEO band. **Derived, not asserted.**
* **Measured on this population**, as `1.4826 x MAD` of the second difference of
  `lambda_dot` divided by `sqrt(6)` — the second difference of a locally linear
  series is pure noise with variance `6 sigma^2`, so this reads the scatter off
  the data without needing a quiet arc. MAD rather than a standard deviation for
  the reason `pipeline/orbit_history._mad_sigma` gives.

**The larger of the two is used**, and the ratio is reported. That is the
conservative choice and it is fixed here rather than after seeing which is
larger.

### 3.2 The deadband floor — noise-only cycles

A cycle finder run on noise returns cycles, and those cycles have a peak-to-
trough. That number is the floor, and this registration measures it two ways.

**F1 — the time-scrambled surrogate.** Within each station segment, replace
`lambda` by its median plus a **time permutation** of its residuals about the
segment median, and `lambda_dot` by its mean plus a time permutation of its
residuals about the segment mean, keeping the original epochs. Seed
`20260922`. Run the identical finder and estimator. This destroys the sawtooth
while preserving the marginal scatter and the sampling cadence exactly, so what
it returns is what the estimator manufactures from noise alone. **`F1` is the
floor screen G6 uses.**

**F2 — the never-manoeuvred arm.** The same estimator on the **331 GEO objects
of class `passive`** in the committed T3 artifact, none of which carries a
detected event (asserted; a contaminated roster is a stop, §6.3 S3). A passive
object near a stable longitude librates under the same triaxial torque with no
control loop at all, so F2 is not a noise floor — it is the answer to a
different and sharper question: **what does this estimator return for an object
that is inside a 0.3-degree slot for natural reasons?** If the kept population's
`R_pos` is indistinguishable from F2, then nothing in it is evidence of a
control box, and the registration says so in advance.

Both floors are reported with their counts, quantiles and object counts.

---

## 4. What is reported

* **Per cycle**, in the JSONL: `R_pos`, `R_rate`, `A_cycle`, `T_cycle`,
  `Delta lambda_dot`, the sample count, the slot longitude, `A(lambda)`,
  `R_pred` from (22), and every screen flag.
* **Per object**: the median `R_pos` over its resolved cycles, the median
  `T_cycle`, the cycle count, and the same for `R_rate`.
* **Population**: the distribution of per-object median `R_pos` over the GEO
  line carriers — quantiles, and the median with a non-parametric bootstrap 95%
  percentile interval, `B = 10000`, seed `20260922`, **resampling objects**.
* **Against `+/-0.0208 deg`**: the fraction of carriers whose median `R_pos`
  lies within a factor of two of it, i.e. in `[0.0104, 0.0416]`; and the same
  against each object's own `R_pred` from (22).
* **Against 14.00 days**: the distribution of `T_cycle`, and the fraction of
  carriers whose median cycle lies in `[7, 28] d`.
* **The internal check**: Theil–Sen slope of `R_rate` on `R_pos` with a
  bootstrap interval over objects. (15) makes them the same quantity read
  through different elements, so the registered prediction is **slope 1**.
* **The acceleration check**: Theil–Sen slope of `A_cycle` on the derived
  `A(lambda)`, registered prediction **slope 1**. This is the parent's failed
  §4.6 control, re-posed at the scale the physics happens on, and it is reported
  whatever it shows.
* **Delta-v, for the commercial-civil subset only** (§1.3): `DV_cycle` from
  parent (18) at each measured cycle's own `R` and `A`, and the implied annual
  total against (19)'s deadband-free prediction — a direct test, per object, of
  the claim T10c derived and could not confirm from the detected ledger.
* **The floors**, F1 and F2, with counts and quantiles, beside every
  distribution.

---

## 5. Acceptance criteria and the decision rule, fixed before the numbers

All of these are evaluated on the GEO line carriers.

* **D1 power.** At least **20** carriers carry at least **3** resolved cycles
  each. Otherwise **UNDERPOWERED**, in that word, and no population statement.
* **D2 floor separation.** The median resolved `R_pos` must exceed **3x** the
  F1 floor median. Otherwise **NOISE-DOMINATED**, in that word.
* **D3 not a natural libration.** The median resolved `R_pos` must differ from
  the F2 median by more than the bootstrap intervals on the two overlap.
  Otherwise the result is reported as **NOT DISTINGUISHABLE FROM AN
  UNCONTROLLED OBJECT IN A SLOT**, in those words, and nothing about deadbands
  is claimed.
* **D4 internal agreement.** The `R_rate`-on-`R_pos` slope interval contains 1.
  If it does not, the two elements disagree about the same quantity, that is a
  finding, and the positional estimator is reported alone with the disagreement
  stated.

**The comparison verdict**, which is what was asked for:

| Condition | Verdict, in these words |
| --- | --- |
| D1–D3 pass and the population median `R_pos` lies in `[0.0104, 0.0416] deg` | "The cycle-resolved deadband measured on T3's own line carriers is [value] [interval], **consistent with the `+/-0.0208 deg` the 14.00-day line implies**, and the agreement is per object against each slot's own acceleration, not against a single number." |
| D1–D3 pass and the median lies outside that window | "The cycle-resolved deadband is [value] [interval], **which the 14.00-day line does not predict**. The discrepancy is [factor] and it is reported, not explained." |
| D1, D2 or D3 fails | The named verdict word, and no comparison is made at all. |
| D4 fails | Reported alongside whichever row above applies, and the population statement carries the disagreement in the same sentence. |

**Registered in advance, because it is the obvious trap**: a 14.00-day *line* in
a periodogram is a statement about **periodicity**, not about box width. If the
measured cycles come out at 14 days but the measured box does not come out at
`+/-0.021 deg`, the line is still real and the inference `R = A T^2 / 16` is
what has failed — most likely through `A`, since (16) assumes one burn per cycle
and real east-west keeping is often flown as a **pair** half a cycle apart
(parent §4.3). That possibility is named here so it cannot be discovered
afterwards and presented as a result.

---

## 6. Implementation, proofs, compute

### 6.1 Offline proofs required before any result document is written

No archive, no network, no event set; every fixture constructed in the test.

1. **A synthetic sawtooth is recovered exactly.** Build `lambda(t)` as the exact
   one-sided parabolic cycle for a given `(R, A)`, sample it at a realistic
   cadence, and require `R_pos` within 2% of `R`, `R_rate` within 5%, and
   `T_cycle` within 5% of `4 sqrt(R/A)`, over `R` in
   `{0.005, 0.0208, 0.05, 0.1} deg` and `A` at a quarter, a half and the whole
   of `A_max`.
2. **The number of cycles found equals the number planted**, for 1, 3 and 7
   cycles.
3. **The finder is cadence-robust**: the same planted cycle sampled at 0.25, 0.5
   and 1.0 day spacing returns `R_pos` within 5% of each other.
4. **The finder is noise-robust**: with `2 sigma_rate` of noise added, the cycle
   count is unchanged and `R_pos` moves by less than 10%.
5. **The prominence threshold does what it says**: a reversal below
   `k sigma_rate` does not open a new cycle and one above it does.
6. **Noise alone returns cycles**, and their `R_pos` is the floor: on a pure-
   noise series the finder returns a non-zero count and a non-zero `R_pos`, and
   the test asserts both, because a floor that came out at zero would mean the
   floor was not being measured.
7. **`sigma_rate` propagation is the derived form**: `(3/2)(n/a) sigma_a`,
   asserted against a direct numerical derivative of `drift_rate_deg_per_day`.
8. **The second-difference estimator recovers a planted sigma** to within 10%
   on a locally linear series, and is not inflated by a ramp.
9. **(21) inverts (15)**: for exact synthetic cycles, `R_rate == R_pos` to 1e-6
   relative.
10. **(22) reproduces T3's table**: `A_max T^2 / 16` at `T = 14.0 d` gives
    `0.0208 deg` and at half `A_max` gives `0.0104 deg`, matching the committed
    `derivations.eastWestDeadbandDeg` to 1e-9.
11. **The parent's `A_max` is recomputed and the two independent forms agree**,
    which is the parent's own §4.1 check, re-asserted here because (22) depends
    on it.
12. **The surrogate preserves the marginal distribution and destroys the
    order**: the permuted series has the same sorted values and a different
    time order, asserted.
13. **The line-carrier membership rule reproduces the committed counts** from a
    constructed miniature artifact, and flags a mismatch.
14. **The policy gate**: asking for a delta-v on a NORAD outside the
    commercial-civil catalogue raises, and the catalogue's `policy` field is
    still a stop.

### 6.2 Compute

CPU only, on `pc`, read-only against the archive. The population is 208 GEO
carriers plus a 331-object passive arm, which is the same access pattern both
parent tracks used. No GPU arm is built, so no `gpu-consumers.json` row is owed.
Wall, CPU and peak RSS are recorded whatever they are.

### 6.3 Stop and defect rules

* **S1** — any input hash mismatch: stop.
* **S2** — the line-carrier rule does not reproduce 214 objects / 208 GEO / 6
  LEO from the committed artifact: stop, and report the rule as not
  reproducing T3.
* **S3** — any passive-roster object carries a detected event: stop the F2 arm,
  report the roster as not passive, and run the rest.
* **S4** — the archive opens writable: stop.
* **S5** — any object outside the commercial-civil catalogue acquires a delta-v,
  propellant or fuel quantity: stop.
* **D1** — a defect found in this registration's own algebra by the test suite
  is reported in the results document with its size, both forms are published,
  and the registration is not edited.

---

## 7. Blind spots, named before the measurement

* **One burn per cycle** is assumed by (15), (16) and (21). East-west keeping is
  often flown as a **pair** half a cycle apart so the eccentricity vector can be
  steered at the same time. A pair halves the apparent cycle and quarters the
  apparent `R_pos`, so a population flying pairs would return a box half the
  true one at twice the rate. The registered diagnostic is the `T_cycle`
  distribution against `R_pred` — a pair shows up as cycles that are too short
  **for their own measured box** — and it is reported whatever it shows.
* **The estimator cannot see a box the satellite does not fill.** An operator
  holding a `+/-0.05 deg` licence inside `+/-0.01 deg` of actual excursion is
  measured at `0.01`. This measures **flown excursion**, which is the honest
  estimand, and every sentence in the results document must say so.
* **Longitude retargets inside 0.3 deg** are not excluded by the segment rule
  and will appear as one very large "cycle". G4 and the `T_cycle` distribution
  expose them; they are not removed by hand.
* **The periodic terms are not subtracted.** Solar-radiation-pressure-driven
  eccentricity gives a longitude oscillation at the draconitic year whose
  amplitude is not modelled here. It is slow compared with a 14-day cycle, so it
  enters as a slowly-varying baseline rather than as a cycle, but it is part of
  `R_pos` and is named as such.
* **The line carriers are not a random sample of GEO.** They are the objects
  whose mean-motion periodogram carries a 14.00-day peak, which selects for
  objects that manoeuvre **regularly and detectably**. The measured box is
  therefore the box of a regular east-west keeper, not of GEO at large, and the
  direction of that bias is toward tighter, more disciplined boxes.
* **Three of T3's eight named top carriers sit at 9 to 16 degrees of
  inclination** — OPS 9437 (DSCS 2-7) at 15.88 deg, Gorizont 13 at 13.94, GSAT 1
  at 9.09 <!-- src: docs/cadence-results-20260921-lines.json, topCarriers -->.
  Those are not routinely east-west-kept geostationary communications
  satellites, and whatever carries their 14-day line may not be a deadband at
  all. G1 admits them deliberately (inclination is irrelevant to longitude
  keeping) and the results document must report their `R_pos` separately rather
  than letting them sit inside a population median unremarked.

---

## 8. Deliverables

* `docs/t10c-cycle-deadband-results-20260922.md` — the results document, with
  the §5 verdict in its first paragraph.
* `docs/t10c-cycle-deadband-20260922.jsonl` — per cycle, per object, and the
  two floors.
* `docs/t10c-cycle-deadband-20260922-receipt.json` — inputs and hashes, seeds,
  census, both floors, the acceptance criteria, the slopes with intervals, the
  runtime proofs, wall/CPU/RSS.
* `tools/t10_followup_deadband_cycles.py` — the instrument.
* `tests/test_orbit_t10c_cycle_deadband.py` — the §6.1 proofs.
* One row in `docs/research-program-runbook-20260921.md` under T10.
