# T11 pre-registration: persistent pairs, arrival order and response hazard

Registered 2026-09-22, **before any T11 pair, count, dwell, phase, arrival gap
or hazard ratio exists**. This document is committed **alone**, ahead of
everything T11 will ever produce, the way `docs/proximity-preregistration-20260922.md`
was committed ahead of T8a, `docs/proximity-leo-preregistration-20260922.md`
ahead of T8b and `docs/cadence-preregistration-20260921.md` ahead of T3. The
git history of this file is the timestamp. Nothing below may be changed once a
T11 number exists; an awkward outcome is reported, not edited away.

T11 is track T11 of `docs/research-program-runbook-20260921.md`. It registers
what T11 estimates, on which objects, with which thresholds, against which
nulls and controls, and what would make each estimand uninformative. It
implements nothing.

Three estate rules this document is written under, restated because they are
the reason most of what follows is derivation rather than assertion:

- **Physical assumptions are not facts — derive or cite every physical claim;
  thresholds are screens, not laws.** Every threshold in §2 is derived from a
  committed prior measurement of this programme or from orbital mechanics, and
  the provenance of each is named at the point of use.
- **A derivation is not a validation.** T8a's §7.2 derived a dwell bound from
  the J22 sectorial term, registered it, and had it falsified 5 of 5 by the
  events it was supposed to exclude. T11 therefore does not rest any verdict on
  a derived exclusion; the exclusion is carried by a **measured control**
  (§6.3), built the way T8b built the only control in this programme that has
  ever passed its gate.
- **The instrument is ownership-agnostic mathematics.** Catalogue registry
  codes, object types, names, `object_id` and launch dates are carried as
  ordinary metadata columns and enter **no** detector decision. They are never
  used to group, rank, order, stratify or narrate any T11 output. Publication
  and site framing for this track is reserved to the operator and is not a T11
  output. **Nothing from T11 goes to any site surface.** Results land in
  `docs/` only.

---

## 0. Vocabulary, fixed here so that no later document may drift

T11 reports **measured facts only**. The following words are **banned** from
`tools/persistent_pairs.py`, from every T11 JSON row, from the case list and
from the results document, and a test in `tests/test_persistent_pairs.py`
asserts their absence by source and artefact inspection (the T8d lesson: the
registry-code guard must use **word boundaries**, because "nation" is a
substring of "inclination"):

> spy, spying, espionage, inspect, inspection, inspector, surveil,
> surveillance, shadow, shadowing, stalk, stalking, hostile, adversary,
> threat, attack, weapon, counterspace, intent, intention, deliberate,
> deliberately, avoid, avoidance, evade, evasion, defensive, suspicious,
> fishy, and **target** in any form.

**"target" is banned deliberately, and this is a departure from T8a.** T8a's
event rows call the approached object the `target`. T11 does not, because the
word imports a purpose the measurement cannot see. T11's role words are fixed
here:

| T11 word | meaning, measured |
|---|---|
| **member** | either object of a pair |
| **incumbent** | the member measured to have reached the shared station **first** (§4, E2) |
| **later arrival** | the member measured to have reached it **second** |
| **station** | a longitude at which both members are stationed per §3.3 |
| **episode** | a maximal interval satisfying §4's persistence definition |
| **relocation** | a ≥ 2.0° change of stationed longitude (T8a §5.6's construct, borrowed unchanged) |

"Relocated N days after the later arrival" is a fact and is permitted.
"Relocated because of" is not, and no T11 sentence may contain it.

---

## 1. What T11 is for (four declared estimands, registered before any result)

1. **E1 — PERSISTENT PAIRS.** A dated, reproducible catalogue of pairs of
   objects that hold the same geostationary station simultaneously for longer
   than a derived dwell, with the subset whose east–west station-keeping
   cycles are **phase-matched** measured against a null drawn from pairs that
   are not co-located.
2. **E2 — ARRIVAL ORDER.** For every persistent pair, which member reached the
   shared station first and by how long, from element-set history, with the
   resolution limit and the censored fraction stated.
3. **E3 — RESPONSE HAZARD.** Whether the incumbent relocates after the later
   arrival more often than its own baseline rate and more often than matched
   stationed objects with no later arrival. **This is the falsifiable claim of
   the track.** §6 registers the window, the control, the null, the leak
   checks that must pass before the ratio is read, and the decision rule that
   would falsify a response effect.
4. **E4 — HISTORICAL CASES.** The top pairs by a **composite evidence rank
   fixed in §7 before any number exists**, dated, with NORAD numbers,
   catalogue names and every underlying measurement beside each. The case list
   is a catalogue, not a test, and carries no interpretation sentences.

E1, E2 and E4 are **descriptive**. E3 is the hypothesis. A reader who takes
only one thing from the results document should take E3's verdict, and §6.6
registers in advance the exact words in which a null verdict is to be written.

### 1.1 What T11 is explicitly NOT

- **It is not a conjunction or miss-distance instrument.** The estimand is
  *mean longitude* (T8a §2.2), a slot coordinate. Two objects at the same mean
  longitude are routinely tens of kilometres apart and are kept so by
  eccentricity- and inclination-vector separation, which T11 does not model.
  **No T11 number is a miss distance or a collision figure.**
- It is not a causal instrument. E3 measures a hazard ratio with a control and
  a null. A hazard ratio is an association. §6.6 forbids the results document
  from writing any causal sentence whatever the number is.
- It is not a census. §8 states the floors; **recall is UNMEASURED** and the
  catalogue is a lower bound.
- It covers the near-geostationary regime only. §9 registers, in advance and
  with the reason derived, why the low-Earth arm is **not run**.

---

## 2. The thresholds, derived

Every T11 threshold comes from a committed prior measurement of this
programme or from a derivation already committed by it. None is chosen.

### 2.1 The proximity threshold `X_pair`, from the measured deadband

T3 measured a narrow line at **14.00 ± 0.11 d** in the mean-motion channel of
208 GEO payloads, absent from its passive control (0.94×), and derived the
deadband it implies from the Earth's sectorial term
(`docs/cadence-results-20260921.md` §5.3): with
`d²λ/dt² = −18 n² J22 (R_e/a)² sin 2(λ − λ22)`, `J22 = 1.8154e-6`,
`a = 42164.2 km`, the amplitude is

&nbsp;&nbsp;&nbsp;&nbsp;`A_max = 1.7006e-3 deg/day²`,

and a one-sided parabolic drift cycle across a deadband of half-width `Δλ`
takes `T = 4·sqrt(Δλ/A)`, hence `Δλ = A·T²/16`. At the maximum-acceleration
longitude and the measured 14.00-day cycle:

&nbsp;&nbsp;&nbsp;&nbsp;`Δλ_db = 1.7006e-3 · 14.00² / 16 = **0.0208324°**`.

Two objects held at **one** station each occupy a box of half-width `Δλ_db`
about the same nominal longitude, so their mean-longitude separation is
bounded by twice that:

&nbsp;&nbsp;&nbsp;&nbsp;**`X_pair = 2 Δλ_db = 0.0416647°`** ( = 30.66 km of
mean longitude at T8a §2.4's 735.904 km/deg).

`A_max` is the **largest** longitude acceleration anywhere on the belt, so
`Δλ_db` is the **widest** box consistent with the measured 14.00-day cycle.
The screen is therefore conservative in the direction that matters: a pair
holding a tighter box is inside it, and a pair needing a wider one is not
consistent with the measured cycle at all.

**Registered arms**, each with its provenance:

| Arm | `X_pair` | km | Provenance |
|---|---:|---:|---|
| **primary** | **0.0416647°** | 30.66 | `2 A_max T²/16` at T = 14.00 d (T3 §5.3) |
| tight | 0.0208324° | 15.33 | the same at half the maximum acceleration (T3 §5.3's second column) |
| loose | 0.0937456° | 69.00 | the same at T = 21.00 d, T3's measured Inmarsat-shaped line |
| T8a | 0.1000000° | 73.59 | T8a's registered primary X, for cross-catalogue comparability only |

**What the screen admits, stated now rather than discovered later.** Two
objects in *adjacent, touching, non-overlapping* boxes (nominal longitudes
`2 Δλ_db` apart) that are perfectly phase-locked can sit at a constant
separation of exactly `X_pair`. The screen cannot separate that case from one
shared station by separation alone. T11 therefore reports, for every pair, each
member's own measured longitude spread over the episode and the difference of
their episode-median longitudes, so the reader can see which case a row is,
and makes no claim that the two are separated.

### 2.2 The dwell threshold `D_pair`, from the cadence instrument

The persistence requirement must be long enough that the matched-cadence
clause of §5 is *measurable*, because a pair that cannot be phase-tested is
not evidence of anything T11 claims. T3's cadence instrument registers
`MIN_CYCLES_IN_WINDOW = 4.0` (`tools/cadence_core.py`, from
`docs/cadence-preregistration-20260921.md` §4): four complete cycles is the
minimum this programme's committed periodogram accepts in a window. Applied to
the measured east–west period:

&nbsp;&nbsp;&nbsp;&nbsp;**`D_pair = 4 · 14.00 d = 56.00 d`**.

**Registered arms:**

| Arm | `D_pair` | cycles | Provenance |
|---|---:|---:|---|
| **primary** | **56.00 d** | 4 | T3's registered `MIN_CYCLES_IN_WINDOW` × the measured 14.00 d line |
| short | 42.00 d | 3 | the shortest dwell at which a per-pair Rayleigh test of §5.4 can reach α = 0.05 at all: with n = 3 perfectly aligned phases, p = e⁻³ = 0.0498 |
| long | 112.00 d | 8 | two admissible cadence windows, which is the shortest dwell at which §5.5's per-pair phase-stability test exists |
| very long | 168.00 d | 12 | three admissible cadence windows |

`D_pair = 56 d` is also, and independently, **longer than T8a's D = 30 d**,
the duration whose derived passive-exclusion argument T8a's §7.2 falsified.
T11 does not rely on that argument in either direction; the exclusion is
carried by §6.3's measured control.

### 2.3 The phase-lock threshold `φ_lock`, from the archive's own sampling

Two objects whose east–west cycles are offset by less than one element-set
spacing are, at the archive's resolution, burning on the same schedule. T8a
§0.2 measured the near-GEO median within-object epoch spacing at
**0.865 d**. Expressed as a phase of the 14.00-day cycle:

&nbsp;&nbsp;&nbsp;&nbsp;**`φ_lock = 2π · 0.865 / 14.00 = 0.388214 rad = 22.244°`**.

A pair is **phase-locked** if `|Δφ| ≤ φ_lock`, **anti-phase-locked** if
`|Δφ − π|` (wrapped) `≤ φ_lock`, and **near-locked** if either holds at
`2 φ_lock`. All three counts are reported, and both locked categories count as
"matched cadence" for E1's headline because both are a common cycle held at a
fixed relative phase. They are never merged into one number and no T11
sentence says why an operator would fly either.

### 2.4 The response window `W`, from T8a's measured lead-time distribution

T8a measured, over 326 events with a confirmable initiating drift change, the
interval from the first instant a causal observer possessed the evidence of a
longitude change to the completion of that change
(`docs/proximity-results-20260922.md` §4): median 36.1 d, p75 96.0 d,
**p95 162.7 d**, max 177.4 d, with the upper tail mildly right-censored by
T8a's own 180-day look-back.

That distribution is the measured timescale on which a near-GEO longitude
change becomes visible in the public archive from end to end. E3's window is
therefore its upper tail:

&nbsp;&nbsp;&nbsp;&nbsp;**`W = 162.7 d`** (T8a's p95 `lead_causal`).

**Registered arms:** `W ∈ {36.1 d, 96.0 d, 162.7 d, 365.0 d}` — T8a's median,
p75, p95 (primary) and one arm deliberately beyond the measured distribution
so that a slow response, if one exists, is not excluded by the window's own
construction. Because T8a's p95 is a **lower bound** (§4 of that document
reports 12 of 326 within 10 days of the look-back wall), the 365-day arm is
registered as the one that cannot be blamed on censoring.

### 2.5 Floors and ceilings, listed before anything is interpreted

| Quantity | Value | Provenance | What it means for T11 |
|---|---:|---|---|
| drift-change detection floor | 0.010 deg/day | T8a §5.5, = 0.78 km of semi-major axis | a burn below it is invisible; the burn train T11 reads is a subsample |
| λ fit-to-fit noise, median | 0.00112° | T8a §2.4 (measured, descriptive) | `X_pair` is **37.2×** this median |
| λ fit-to-fit noise, p95 | 0.00493° | T8a §2.4 | `X_pair` is **8.45×** this p95 |
| near-GEO median epoch spacing | 0.865 d | T8a §0.2 | sets `φ_lock`; sets E2's resolution |
| interpolation refusal | gaps > 5 d | T8a §4 | long gaps become missing epochs, never evidence |
| loiter occupancy | ≥ 0.4 retained epochs per day | T8a §2.7/§4 | borrowed unchanged |
| archive span | 1959-01 … 2026-09 | T8a §1 | everything before coverage is invisible |

**RECALL IS UNMEASURED.** T11 has no ground truth for how many co-stationed
pairs exist, and no ground truth for how many east–west burns the 0.010
deg/day floor lets through. Every T11 count is a **lower bound**, and the
results document is required to use those words. Absence of a pair is not
evidence of absence of co-location.

---

## 3. Population, classes and inputs

### 3.1 Near-GEO membership and the pinned input

T11 reuses T8a's committed extract rather than re-detecting: the near-GEO
element sets selected per element set by `0.95 ≤ n ≤ 1.05` rev/day,
`e ≤ 0.01`, `i ≤ 25°` (T8a §3.1). The cache at
`runtime/proximity-geo/near-geo.npz` is **hash-pinned** to T8a's published
figures and the receipt records the assertion, the way T10a pinned to T2's
extraction: `rowsScanned = 217,007,154`, `rowsKept = 11,626,494`,
`objectsKept = 1,768`. If any of the three differs, the run **stops** and
reports the mismatch rather than measuring against an input T8a did not use.

Archive provenance (path, bytes, mtime, `month_rollup` span), the SHA-256 of
`tools/persistent_pairs.py` and of every module it imports, go in the receipt.
The archive is opened read-only with `PRAGMA query_only=1`.

### 3.2 λ, drift rate and station segments, all borrowed unchanged

`λ = Ω + ω + M − θ_G` (T8a §2.2), `ḋ_n = 360 n − ω_E` (T8a §2.3),
station segments = maximal intervals with `|λ − median λ| ≤ 0.3°` throughout
and length ≥ 30 d (T8a §5.3), drift-change flags at
`max(5 σ_n, 0.010 deg/day)` confirmed at two consecutive element sets
(T8a §5.5), `σ_n` re-measured on this run by T8a's registered procedure and
reported beside T8a's published 0.0006039 deg/day. T11 imports these from
`tools/proximity_geo.py` and **modifies none of them**; a test asserts the
import path rather than a copy, the discipline `tools/cadence_core.py` uses.

**A named trap, carried forward from T8c's finding.** `Series.grid_lo` is a
day offset **relative to the global grid origin**, not an absolute epoch;
T8c measured a 1,924-day displacement at two sites in T8a's instrument that
used it as one. T11 stores the global origin explicitly and converts with
`absolute_day = global_lo + grid_lo + i` at every site. A test asserts this
against a constructed two-object case whose first element set is not the
archive's first.

### 3.3 Classes, and the control this programme has learned to build

| Population | Definition |
|---|---|
| `payload` | `object_type = 'PAYLOAD'` |
| `catalogue_passive` | `pipeline.orbit_events.PASSIVE_TYPES` (DEBRIS, ROCKET BODY) — T8a's failed control, reported for comparison only |
| **`never_manoeuvred`** | **the control**: **zero** confirmed drift-change flags over the object's entire near-GEO history, subject to a minimum evidence requirement of **≥ 200 near-GEO element sets and ≥ 365 d of near-GEO span**, so that "no change detected" means "looked at properly and found none" and not "barely observed" |

`never_manoeuvred` is T8b §3.4's class transposed to GEO, and it is registered
because T8a's §10.3 said in those words that the right control "must be
constructed, not inherited from `object_type`" — the uncontrolled GEO
population is dominated by dead **payloads**, which `object_type` labels
PAYLOAD and cannot see. The registered cross-tabulation is reported whatever
it says: the count of payload-class objects inside `never_manoeuvred`, and
the count of `catalogue_passive` objects outside it.

E1's headline population is **pairs in which both members are payload-class
and neither is in `never_manoeuvred`**. Every other combination is counted and
reported; the never-manoeuvred combination is §6.3's leak measurement.

### 3.4 The descriptive family split (E1), and the registry-code rule

The task this track serves asks for a same-operator / different-operator
split. No operator column exists in the catalogue, so T11 registers a
**name-stem** proxy, computed from the catalogue `name` and used for **one
descriptive count only**:

> **name stem** = the leading run of the uppercased catalogue name up to but
> excluding the first decimal digit, with trailing spaces and punctuation
> stripped. Two members are **same catalogue family** if their stems are equal,
> non-empty and at least three characters long.

Reported: the count of persistent pairs that are same-family, the count that
are not, and — **as a separate column, never as a grouping** — the count whose
catalogue registry codes agree, which is the same descriptive statistic T8a
reported once (286 of 487) and did not analyse. **No T11 output is ordered,
ranked, stratified, filtered or narrated by a registry code, and no T11
sentence names a registry code.** A test asserts that the registry field is
absent from the case list and from every ranking key.

The stem proxy is a **screen, not a fact about ownership**: it will merge
distinct operators flying similarly named buses and split one operator's
differently named fleets. It is reported with that sentence attached.

---

## 4. The registered definitions (E1 and E2)

### 4.1 A persistent-pair episode (E1)

For an unordered pair {A, B} of near-GEO objects, let `Δλ(t) = wrap(λ_A − λ_B)`
be evaluated on the **union of their element-set epochs**, each series linearly
interpolated onto the other's epochs and **refused across any gap longer than
5 d in either series** (T8a §4). Retained epochs are those where both
interpolations succeed; refused epochs are dropped and counted.

**A T11 persistent-pair episode is a contiguous interval `[t_s, t_e]` with:**

1. **Both stationed.** A station segment of A (§3.2) and a station segment of B
   both cover `[t_s, t_e]` in full.
2. **Sustained proximity.** `|Δλ(t)| ≤ X_pair` at **every retained epoch** in
   `[t_s, t_e]`.
3. **Occupancy.** At least `0.4 · (t_e − t_s)/1 d` retained epochs, and no
   internal gap between retained epochs longer than 5 d (T8a §2.7/§4).
4. **Dwell.** `t_e − t_s ≥ D_pair`.

Episodes are maximal: `[t_s, t_e]` is extended in both directions until a
criterion fails. A pair may contribute more than one episode; both the episode
count and the distinct-pair count are reported, the way T8a reported 487 events
against 427 arrivals.

**Recorded per episode**, before any cadence or hazard computation: dwell days,
retained-epoch count, refused-epoch count, median and maximum `|Δλ|`, each
member's own longitude spread (max − min of its λ over the episode), the
difference of the members' episode-median longitudes, the episode-median
station longitude `λ_station`, and the distance of `λ_station` from the nearer
of the two stable longitudes 75.1°E and 104.7°W.

**The T8a libration flag is recorded and is NOT a screen.** The ±3.75° flag was
falsified by T8a §7.2 (5 of 5 passive events exceeded the bound it rests on).
T11 records the raw distance as a number and reports the distribution;
nothing is excluded by it.

### 4.2 Arrival order (E2)

For an episode, and for each member Z ∈ {A, B}:

- **`t_arr_station(Z)`** = the first day of the station segment of Z that
  covers the episode. This is entry into the ±0.3° slot envelope of T8a §5.3.
- **`t_arr_band(Z)`** = the first epoch, searching backwards from `t_s` within
  that station segment, at which Z's λ entered and thereafter stayed within
  `X_pair/2` of `λ_station`. This is entry into the pair band.

Both are recorded. **`t_arr_station` is the registered primary**, because it is
a committed construct of this programme; `t_arr_band` is the registered
secondary and is reported beside it, because a reader wanting "when did it get
to the slot" and a reader wanting "when did it get next to the other one" are
asking different questions and T11 should not decide for them.

- **`arrivalGapDays` = |t_arr(A) − t_arr(B)|**; the **incumbent** is the member
  with the earlier `t_arr`.
- **Resolution limit, registered:** the station-segment boundary is on the
  daily grid (±0.5 d) and the median near-GEO element spacing is 0.865 d, so
  the arrival epoch is resolved to no better than
  `max(1.0 d, 2 × 0.865 d) = **1.73 d**`. An arrival gap at or below 1.73 d is
  recorded as **`order: unresolved`** and is excluded from the arrival-gap
  distribution and counted.
- **Left-censoring, registered:** if `t_arr(Z)` falls within 1.0 d of Z's first
  near-GEO element set, Z may have been at the station before the archive saw
  it. The episode is recorded as **`order: censored`**, excluded from the
  arrival-gap distribution and from E3, and counted. The censored fraction is
  reported in the results document's first screen for E2.

### 4.3 What E2 is not

Arrival order is **not** an attribution of motion. T8a's approacher/approached
attribution required one object to have moved ≥ 80% of the closing distance;
T11's E2 asks only which member's station segment began earlier. A pair in
which neither member ever moved — two objects launched into the same slot — is
a persistent pair whose arrival order is a fact about launch dates and element
coverage, and the results document is required to say so where it reports the
same-family split.

---

## 5. The matched-cadence estimator (E1's second clause)

### 5.1 The series and the fit

For each member over the episode, take its own **drift-rate series**
`ḋ_n(t) = 360 n(t) − ω_E` at its own element-set epochs inside `[t_s, t_e]`
(T8a §5.2 primary estimator — single-sample, no window, which is why a 56-day
episode can carry it at all).

Remove a **linear** trend in t. Degree 1, not T3's cubic: an episode is four
cycles long, and a cubic over four cycles begins to absorb the fundamental,
whereas the quantity a linear term removes is the secular drift of the box
itself. The choice is registered here with that reason and is not revisited.

Fit, by ordinary least squares at the **fixed** frequency `f_EW = 1/14.00 d⁻¹`:

&nbsp;&nbsp;&nbsp;&nbsp;`y(t) ≈ a cos(2π f_EW t) + b sin(2π f_EW t)`,

with `t` measured in days from a **fixed common origin** (Unix epoch
1970-01-01T00:00:00Z), identical for both members so the phases are
comparable. Record amplitude `R = sqrt(a² + b²)` and phase
`φ = atan2(b, a) ∈ (−π, π]`.

**`Δφ = wrap(φ_A − φ_B)`** is the pair's cadence phase difference.

### 5.2 Whether each member carries the cycle at all

The frequency is fixed in advance, so there is **no look-elsewhere penalty**
and the single-frequency false-alarm probability of the least-squares
periodogram applies: with `N` retained samples and normalised power
`p = (χ²_0 − χ²_fit)/χ²_0` measured against the **null model of §5.1** (a
constant plus a slope, `k₀ = 2` parameters), the false-alarm probability under
Gaussian noise is

&nbsp;&nbsp;&nbsp;&nbsp;`FAP = (1 − p)^((N − k₀ − 2)/2) = (1 − p)^((N − 4)/2)`,

the standard normalisation result for a least-squares periodogram whose null
model carries `k₀` free parameters and whose alternative adds two sinusoid
coefficients. The exponent is `(N − 4)/2` here and **not** the more commonly
quoted `(N − 3)/2`, because §5.1's null model removes a slope as well as a
mean; a test asserts the exponent against the registered detrend degree so the
two cannot drift apart.

Registered: a member **carries the cycle** if `FAP ≤ 0.01`. α = 0.01 is a
screen, not a law, and is reported as one. A pair is **cadence-testable** only
if both members carry it; the count that do not is reported.

**A registered free-period variant**, run and reported in full: refit each
member's own period over the band `14.00 ± 0.109 d` — T3's measured core
half-width of the line — and require both fitted periods to lie in the band.
This exists because T3 measured a line of finite width and a fixed-frequency
fit alone would call a real 13.95-day cycle "absent". Both variants are
reported; the fixed-frequency one is primary.

### 5.3 The null: pairs that are not co-located

The phase-difference statistic means nothing without a distribution for it
under no co-location. Registered, seed **20260922**:

> For each cadence-testable episode, draw **M = 200** control pairs. Each
> control pair is two payload-class objects that are **both stationed over the
> identical interval `[t_s, t_e]`** and whose mean-longitude separation
> **exceeds `X_pair` at every retained epoch of that interval** — matched to
> the real pair on the epoch window exactly, and on each member's retained
> sample count to within a factor of two. `Δφ` is computed for each control
> pair by the identical code path.

Under no coordination `Δφ` is uniform on (−π, π]. Reported:

1. the observed `Δφ` distribution over all cadence-testable episodes, its
   Rayleigh mean resultant `R̄` and the Rayleigh p-value;
2. the control `Δφ` distribution and **its** `R̄` — **this is the leak check
   for the cadence clause**: a control that is not uniform means the estimator
   manufactures phase agreement, and §10 gate C is then read as firing;
3. the observed locked / anti-locked / near-locked fractions at §2.3's
   `φ_lock`, each against the control fraction, with Wilson 95% intervals and
   the ratio.

### 5.4 The per-pair statement, bounded in advance

A single episode yields **one** `Δφ`. One draw cannot establish that a
particular pair is phase-locked; the population statement in §5.3 can. The
results document is therefore required to label every per-pair lock flag as a
**descriptive category**, and is forbidden from writing that any individual
pair "is" phase-locked. This is the T8c lesson written down before the number
exists: an individual row may not carry a claim only the aggregate earns.

### 5.5 The per-pair test that does exist, for long episodes

For episodes of ≥ 112 d (§2.2's long arm, two admissible cadence windows),
split into consecutive blocks of four cycles (56 d), compute `Δφ` per block,
and record the **circular standard deviation** of `Δφ` across blocks. A pair
whose across-block circular s.d. is below the median per-block phase
uncertainty (§10 gate A) is recorded as **`phaseStable: true`**. The identical
blocking is applied to the control pairs, and the stable fraction is reported
against the control's. This is a per-pair statement with its own null and it
is the only per-pair cadence claim T11 may make.

---

## 6. E3 — the response hazard, its controls, its leak checks and its
falsification rule

### 6.1 The unit, the outcome, the exposure

**Unit of analysis:** one **later arrival** into a station where the incumbent
is already stationed — that is, one persistent-pair episode with a resolved,
uncensored arrival order (§4.2). Episodes with `order: unresolved` or
`order: censored` are excluded and counted.

**Outcomes, both registered, both reported:**

- **Primary — relocation.** The incumbent's stationed longitude changes by
  ≥ 2.0°: T8a's `relocations()` construct, borrowed unchanged (a station
  segment followed by another whose median longitude is ≥ 2.0° away). The
  event epoch is the last day of the pre-change station segment.
- **Secondary — station departure.** The incumbent's station segment
  containing the arrival ends, whatever follows. This has no requirement of a
  subsequent segment and therefore no right-censoring from the archive's end,
  but it also fires on an object that simply stops being catalogued near GEO.
  Both limitations are stated beside its number.

**Exposure.** For each later arrival, the incumbent's stationed days in
`(t_arr2, t_arr2 + W]`, censored at the outcome, at the end of the incumbent's
stationed span, or at the end of the archive, whichever comes first. Censored
observations are counted and reported; an incumbent that leaves and never
restations is a **censored** observation for the primary outcome, never a zero.

### 6.2 The three comparisons

| | Numerator | Denominator |
|---|---|---|
| **`HR_self`** | the incumbent's outcome rate per stationed day inside its exposed windows | the **same** incumbent's outcome rate per stationed day over all of its stationed time **outside** any exposed window |
| **`HR_ctrl`** | the same exposed rate, pooled | the matched-control rate per stationed day over identically shaped counterfactual windows |
| **null** | `HR_self` recomputed on permuted arrival epochs | — |

**The matched control**, registered: for each later arrival, up to **5**
control objects (seed 20260922), each a payload-class object, not either
member of the pair, that

- is stationed at `t_arr2` and whose station segment covers at least one day
  of `(t_arr2, t_arr2 + W]`;
- had **no** second object arrive within `X_pair` of its own station during
  `(t_arr2 − W, t_arr2 + W]`;
- matches on **crowding**: the number of stationed objects within ±5.0° of its
  episode longitude at `t_arr2`, binned into deciles of that quantity's
  distribution over all stationed object-days, same decile;
- matches on **tenure**: elapsed days since its station segment began, same
  quartile of that quantity's distribution;
- matches on **epoch**: same calendar year ± 2.

The number of arrivals for which fewer than 5, and for which zero, matches
exist is reported. Arrivals with zero matches are excluded from `HR_ctrl`,
counted, and **kept** in `HR_self`.

**Confidence intervals.** No scipy on the host (T8a §4.1 records this), so
intervals are computed exactly and from first principles: conditional on the
total event count `T = e₁ + e₂`, `e₁ ~ Binomial(T, ρ)` with
`ρ = HR·E₁/(HR·E₁ + E₂)` for exposures `E₁, E₂`; a Clopper–Pearson 95%
interval for `ρ` is inverted to an exact 95% interval for `HR`. The regularised
incomplete beta function is implemented by continued fraction and is checked in
the test suite against values computed independently. Wilson intervals are used
for proportions, as T8a used them.

**The permutation null**, 1,000 permutations, seed 20260922: each later-arrival
epoch is reassigned to an epoch drawn uniformly from the **same incumbent's own
stationed days**, preserving the incumbent, its exposure and its outcome
history; `HR_self` is recomputed by the identical code path. Reported: the
null's median and 95% interval, and the fraction of permutations reaching the
observed `HR_self`.

### 6.3 The leak checks, run and reported BEFORE the ratio is read

T8a's gate B fired at a ratio of 0.9995 against a bar of 0.02 and the pilot's
control was worthless. T11 registers three checks that must be reported, in
this order, **above** the hazard ratio in the results document. The results
document may not print a hazard ratio until all three are printed.

- **L1 — machinery bias.** The permutation null's median `HR_self` must lie in
  **[0.95, 1.05]** and its 95% interval must contain 1.0. If not, the estimator
  is biased by construction and **the ratio is not read**; the results document
  says so in those words and E3 reports the bias instead of a hazard.
- **L2 — control selection.** The matched controls' outcome rate inside their
  counterfactual windows, against the same controls' own all-archive stationed
  outcome rate: the 95% interval of that ratio must contain 1.0. If not, the
  matching selected on the outcome and **`HR_ctrl` is not read**.
- **L3 — detector leak (the gate-B analogue).** The §4.1 persistence detector,
  unchanged, on pairs in which **both** members are in `never_manoeuvred`
  (§3.3). Registered bar, borrowed from T8b's gate B — the only version of this
  gate in the programme that has ever passed: never-manoeuvred pair yield per
  pair-exposure-day **> 0.10 ×** the payload-pair yield per pair-exposure-day
  means **the pair detector leaks**. Then E1's count is reported as a geometry
  count and not as a station-keeping count, the matched-cadence clause is
  reported against the never-manoeuvred pairs' own cadence statistics, and
  **E3 is not read**.

Exposure for L3 is pair-days over which both members are simultaneously
stationed, computed identically for both populations; **rates, never counts,
are compared**, because the never-manoeuvred population is far smaller.

### 6.4 Power, registered before the count exists

`HR` is estimated from event counts. Registered: if the exposed windows
contain **fewer than 10** outcome events at the primary arm and primary
outcome, E3 is reported **UNDERPOWERED** — intervals printed, no claim made in
either direction, and the word UNDERPOWERED used in the results document's
first screen.

### 6.5 The registered decision rule

At the **primary arm** (`X_pair = 0.0416647°`, `D_pair = 56.00 d`,
`W = 162.7 d`, primary outcome), with L1, L2 and L3 all passed:

| Verdict | Condition |
|---|---|
| **SUPPORTED** | the 95% intervals of **both** `HR_self` and `HR_ctrl` exclude 1.0 **on the same side**, **and** the permutation null's 95% interval excludes the observed `HR_self` |
| **FALSIFIED** | the 95% interval of `HR_self` contains 1.0 **and** the 95% interval of `HR_ctrl` contains 1.0 |
| **INCONCLUSIVE** | anything else, including the two ratios disagreeing in direction |
| **UNDERPOWERED** | §6.4 |
| **NOT READ** | any of L1, L2, L3 fails |

Sensitivity arms are reported in full and **cannot change the primary
verdict**; an arm that disagrees with the primary is reported as a
disagreement, not as the answer.

### 6.6 The words a null result gets, fixed now

If the verdict is FALSIFIED, the results document is required to write, in the
first screen and in these words: *"No response effect is detected. The
incumbent's relocation hazard after a later arrival is consistent with its own
baseline and with matched stationed objects that had no later arrival."*

Whatever the verdict, **no T11 sentence may attribute a relocation to the
later arrival as a motive.** "Relocated N days after the later arrival" is the
only permitted form. The framing test of §0 enforces the vocabulary; this
clause binds the sentences the vocabulary would otherwise allow.

---

## 7. E4 — the case list, ranked by a rule fixed before any number exists

A "top cases" list chosen after the numbers exist is a cherry-pick. The rank is
registered here.

For each persistent-pair episode with a resolved, uncensored arrival order,
compute four component scores, each the **within-catalogue percentile rank**
(0 … 1) of a measured quantity:

1. **dwell** — episode dwell in days, longer ranks higher;
2. **cadence** — `max(0, 1 − d_lock/φ_lock)` where
   `d_lock = min(|Δφ|, π − |Δφ|)` is the circular distance to the nearer of
   in-phase and anti-phase; an episode that is not cadence-testable scores 0
   and is marked so;
3. **arrival gap** — `arrivalGapDays`, larger ranks higher (a larger gap is a
   better-resolved order);
4. **post-arrival relocation** — 1.0 if the incumbent's primary outcome
   occurred within `W`, scaled by `1 − latency/W` so a shorter latency ranks
   higher; 0.0 otherwise.

**Composite evidence rank = the unweighted mean of the four.** Equal weights
are registered because no basis exists for any other choice and a weighting
tuned after the fact is the thing this clause prevents.

The case list reports the **top 10** by the composite plus every episode whose
composite exceeds the 99th percentile, each row carrying: both NORAD numbers,
both catalogue names, the episode start and end dates, dwell days, median and
maximum `|Δλ|` in degrees and km, `Δφ` in degrees with its lock category and
FAP for each member, `t_arr` for each member with the arrival gap and which is
the incumbent, the primary and secondary outcome with its latency in days, and
the same-family flag. **No interpretation sentences.** A test asserts the case
list contains no sentence-final prose outside the registered column set and no
banned word of §0.

---

## 8. Declared blind spots

Stated now so they cannot later be presented as findings.

1. **Mean longitude is not miss distance.** Unchanged from T8a §9.1 and
   unquantifiable within T11.
2. **Recall is UNMEASURED.** §2.5. Every count is a lower bound.
3. **The burn train is a subsample.** T8d measured ~6 confirmed drift changes
   per year per active near-GEO object against a 14.00-day cycle that implies
   ~26; the fraction the 0.010 deg/day floor lets through is not measured here
   and T11 does not estimate it. The cadence estimator of §5 reads the drift
   *series*, not the flag train, which is why it can work at all — but a
   member whose box is tight enough that its sawtooth amplitude falls under
   the fit noise will fail §5.2 and be counted as not carrying the cycle.
4. **One cycle, one belt.** The estimator tests the 14.00-day line. T3 also
   measured a 21.00-day line on Inmarsat-shaped carriers. An object keeping a
   period outside §5.2's band is invisible to the cadence clause and is
   counted, not excluded from E1's proximity clause.
5. **Co-location by design is not separated from co-location by arrival**
   except through E2's arrival order, which is itself censored whenever a
   member's station segment starts at the edge of its element coverage. §4.2's
   censored count is the size of this blind spot and is reported first.
6. **Adjacent touching boxes** (§2.1) are admitted by the separation screen and
   are reported with the numbers that let a reader see them, not removed.
7. **The libration zone.** T8a's ±3.75° flag was falsified; T11 records the raw
   distance and screens on nothing.
8. **Catalogue completeness.** Objects absent from the public catalogue, or
   whose elements are withheld or degraded, are invisible.
9. **Regime.** Near-GEO only. §9.

---

## 9. The low-Earth arm is NOT RUN, and the reason is registered in advance

The task this track serves names a low-Earth arm (in-track co-orbital station
per T8b's definition). T11 registers, **before any measurement**, that it does
not run one, for two reasons that are facts about committed results rather
than about T11's convenience:

1. **The matched-cadence clause has no instrument in LEO.** T3's registered
   per-object test returned **0 of 2,809 Starlink and 0 of 618 OneWeb** — the
   registered low-thrust blind spot, confirmed. More fundamentally, there is no
   common LEO station-keeping period to phase-lock against: drag make-up
   cadence is set by each object's own ballistic coefficient and by the solar
   cycle, so two co-orbital LEO objects sharing a cadence would be sharing a
   *drag environment*, not a schedule. A phase-lock statistic there would
   measure the thermosphere.
2. **T8b has already committed the LEO co-orbital station catalogue**
   (`docs/proximity-leo-events-20260922.jsonl`, 2,565 rows, registration
   `23d4776`, results `7a515fd`). Re-deriving arrival order from it would
   restate T8b's attribution rule, not measure anything new: in T8b's
   definition the approaching object arrives second by construction.

What T11 **does** do with LEO, registered here and labelled as such: a
**descriptive re-expression** of T8b's committed catalogue as persistent pairs
— NORAD numbers, dwell days, arrival epoch, and T8b's own attribution — with
no new detection, no cadence clause and no hazard. It is hash-pinned to the
committed file, is reported in a clearly separated section, and **no LEO number
in T11 is a T11 measurement**. If T8b's file hash does not match its committed
value the section is omitted and the mismatch reported.

---

## 10. Gates: what makes each estimand uninformative

Registered before any measurement. Each is a statement the results document
must make explicitly, in these words, if it fires.

- **Gate A — the cadence clause is unmeasurable.** The median per-member phase
  uncertainty `σ_φ = σ_resid / (R · sqrt(N/2))` over cadence-testable members
  exceeds `φ_lock` = 0.388214 rad. Then §5's phase difference cannot resolve a
  lock at the archive's own sampling resolution, the matched-cadence clause is
  reported as **unmeasurable**, and E1 reports proximity and dwell only.
- **Gate B — the pair detector leaks.** §6.3 L3: never-manoeuvred pair yield
  per pair-exposure-day > 0.10 × payload-pair yield. Then E1 is a geometry
  count, not a station-keeping count, and E3 is **not read**.
- **Gate C — the null explains the cadence.** The observed `Δφ` Rayleigh `R̄`
  lies inside the control distribution's 95% interval, **or** the control's own
  `R̄` is itself outside uniformity's 95% interval. The first is the finding
  that matched cadence among co-stationed pairs is indistinguishable from
  chance; the second is the finding that the estimator manufactures agreement.
  They are different and are reported as different.
- **Gate D — underpowered.** Fewer than **20** persistent pairs at the primary
  arm (E1), or fewer than **10** outcome events in exposed windows (E3, §6.4).
- **Gate E — arrival order unresolvable.** More than **50%** of episodes are
  `order: censored` or `order: unresolved`. Then E2 reports the censoring and
  tie fractions and **no arrival-order distribution is claimed**, and E3 runs
  only on the resolved remainder with its reduced n stated.
- **Gate F — the input is not T8a's.** §3.1's hash pin fails. The run stops.

Any gate firing is reported in the results document's first screen. None may
be revised after a number exists.

---

## 11. Compute, provenance and reproducibility

- `tools/persistent_pairs.py`, **CPU only, on `pc`**, `nice`-d. No GPU stage is
  registered: T8b measured CPU at **0.534 s against a GPU's 6.823 s** on an
  identical 66,552-pair sub-problem, because the derived screen makes the pair
  problem sparse. If a GPU is later found necessary it goes through `gpu-run`
  with an honest `--estimate-mib`, the `gpu-consumers.json` v7 row is added in
  the same change, and the deviation is recorded in the results document.
- Memory-heavy work stays on `pc`. Nothing runs on the VPS.
- Read-only archive access through
  `pipeline.orbit_campaigns.open_archive_for_reading` with
  `PRAGMA query_only=1`.
- **Determinism:** seed **20260922** for the §5.3 control draw, the §6.2 match
  draw and the §6.2 permutation null. No other randomness.
- Outputs: `docs/persistent-pairs-20260922.jsonl` (one row per episode),
  `docs/persistent-pairs-20260922-receipt.json`,
  `docs/persistent-pairs-results-20260922.md`,
  `docs/persistent-pairs-cases-20260922.md`. **Nothing is written to `src/`,
  `data/`, `public/` or any site surface.**
- Tests in `tests/test_persistent_pairs.py` must cover, at minimum: the §2.1
  and §2.2 derivations against independently computed values; the phasor fit
  recovering a constructed phase and amplitude; `Δφ` invariance under a shared
  time shift of both members and its correct rotation under a shift of one;
  the FAP formula against a constructed pure-noise series; a synthetic pair
  that must be detected; a synthetic pair separated by more than `X_pair` for
  one epoch in the middle that must **not** yield a single long episode; a
  synthetic pair whose dwell is one day short of `D_pair` that must not be
  detected; the gap-refusal; the global-origin day-index conversion of §3.2
  against a case whose first element set is not the archive's first; the
  exact Clopper–Pearson beta inversion against independently computed values;
  the arrival-order resolution and censoring rules; the §0 vocabulary ban by
  source and artefact inspection with word boundaries; and an assertion that
  no detector branch reads a registry code, name, object id or launch date.

---

## 12. What is committed with this document

Nothing. This registration is committed **alone**. `tools/persistent_pairs.py`,
its tests, the episode catalogue, the receipt, the results document, the case
list and the runbook row all follow in later commits, and the ordering in
`git log` is the evidence.
