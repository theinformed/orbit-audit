# T8a results: GEO approach events from longitude and drift rate

Measured 2026-09-22. Registration: `docs/proximity-preregistration-20260922.md`,
committed **alone** at `c898397` before any measurement code existed; the
instrument and its tests followed at `7fb814c`. The ordering in `git log` is
the evidence. Every threshold below was fixed in that registration and none
was changed after a number existed.

Framing, restated because it constrains this document: the instrument is
**ownership-agnostic mathematics**. Catalogue registry codes are metadata
columns on the event rows and enter no detector decision; this document
contains no intent language and no per-nation narrative, and the per-registry
breakdown available in the event catalogue is not analysed here because that
framing is an operator decision reserved to Sean. The object whose elements
changed is the approacher — **facts, never intent**. Drift-rate changes are
reported in deg/day; no fuel figure was computed for any object.

**Read §1.1 before any number in this document.** The estimand is *mean
longitude*, a slot coordinate. **No figure here is a miss distance.** Two
objects sharing a mean longitude are routinely tens of kilometres apart and
are deliberately kept so by eccentricity- and inclination-vector separation,
which T8a does not model.

---

## 0. The five registered gates, discharged

| Gate | Registered meaning | Verdict |
|---|---|---|
| **A** | the instrument is unfit | **SPLIT — the registration contradicts itself; see §2.3. Under the arithmetic reading it FIRES; under the literal number it does not. The directly relevant quantity, which the registration did not name, is measured in §2.4 and is comfortable.** |
| **B** | the detector leaks | **FIRED. §7.** |
| C | the null explains the catalogue | Not fired — but the catalogue sits **below** the null, not above it. §6. |
| D | underpowered repetition | Not fired: 112 repeat approachers against a bar of 10. §5. |
| E | no lead time | Not fired: median causal lead **36.1 d**. §4. |

**The one-sentence pilot verdict.** The mathematics works, the lead time is
real and substantial, and the repetition structure exists — but **the
registered event definition does not separate objects that manoeuvred from
objects that merely drifted to a stop**, and the derivation that was supposed
to guarantee that separation is falsified by the data. T8a therefore delivers
a lead-time number worth building on and an event catalogue that must not be
read as a catalogue of deliberate approaches without the §7.4 corroboration
filter.

---

## 1. What ran, where, and for how long

| | |
|---|---|
| Host | `pc` (`bigmem-PC`), CPU only, `nice -n 15` <!-- src: docs/proximity-20260922-receipt.json, host/executionMode --> |
| GPU | none. The registration declared no GPU stage and none was needed. |
| Extract pass | **293.5 s**; 217,007,154 element sets scanned, **11,626,494 kept** over **1,768 objects** |
| Analysis pass | **2,022.0 s wall / 2,019.3 s CPU** (33.7 min, single core) |
| Archive | `/home/sdegan/space-orbit-history/orbit-history.sqlite3`, 13,890,236,416 bytes, read-only with `PRAGMA query_only=1` |
| Archive span | `month_rollup` 1959-01 … 2026-09 |
| Outputs | `docs/proximity-events-20260922.jsonl` (sha256 `b2e6b364…70deef`), `docs/proximity-20260922-receipt.json` |

**A provenance discrepancy, reported because it was found.** The sequential
pass counted **217,007,154** element sets; `month_rollup` reports
**183,352,638**. The rollup understates the archive by 33.65 M rows, i.e. it
is stale with respect to some writer. Nothing in T8a depends on the rollup —
the scan is the ground truth and every T8a figure comes from it — but any
other study that sizes the archive from `month_rollup` is reading a number
that is 15% low.

### 1.1 What the estimand is, and is not

λ = RAAN + argument of perigee + mean anomaly − GMST (prereg §2.2). The
derivation shows both correction terms — the equation of the centre (2e sin M)
and the inclination term (−(i²/4) sin 2u) — are periodic with zero mean, so λ
carries no eccentricity or inclination content by construction. That makes it
the classical geostationary **mean longitude**: a slot coordinate.

It is **not** a position and **not** a miss distance. A T8a "closest approach"
of 0.0003° means the two objects' *slots* coincided to 0.2 km of along-arc
longitude; their actual separation is set by their eccentricity and
inclination vectors, which T8a never reads. Miss distance is T8b's problem.

---

## 2. Population and calibration

### 2.1 Population
Of 1,768 objects with at least one near-GEO element set (prereg §3.1:
0.95 ≤ n ≤ 1.05 rev/day, e ≤ 0.01, i ≤ 25°), **1,613 carry a usable class**:
**1,308 active** (`object_type = PAYLOAD`) and **305 passive** (DEBRIS,
ROCKET BODY). 155 objects had a null or unknown `object_type` and were
excluded and counted, as registered.

Daily grid: **22,642 days**. **24,685 stationed segments** (prereg §5.3:
confined within ±0.3° of the segment median for ≥ 30 d), of which 24,391
belong to active-class objects and 294 to passive-class objects.

### 2.2 The drift-rate noise floor, measured
σ_n = **0.0006039 deg/day**, from the MAD of consecutive `ḋ_n` differences
inside stationed segments over **3,740,056 consecutive pairs** (prereg §5.4).

The registered burn threshold is `max(5σ_n, 0.010 deg/day)`. Since
5σ_n = 0.0030 deg/day, **the derived physical floor of 0.010 deg/day
dominates and the noise calibration never binds the detector.** By prereg
§2.3 that floor corresponds to 0.78 km of semi-major axis.

### 2.3 Gate A, and a defect in the registration

Prereg §5.4/§10 wrote: *"requires σ_n to come back below X/10 in drift-rate
terms over a 30-day arc, i.e. below 0.0033 deg/day."* **The formula and the
number disagree**: X/10 = 0.01° accumulated over 30 d is 0.01/30 =
**0.000333** deg/day, not 0.0033. The implementation encoded the formula.

Reported both ways, because choosing the flattering reading after the fact is
exactly what a registration exists to prevent:

| Reading of the registered bar | Bar | σ_n = 0.0006039 | Gate A |
|---|---:|---|---|
| the formula, `X/10/D` | 0.000333 deg/day | 1.81× the bar | **FIRES** |
| the literal number written beside it | 0.0033 deg/day | 0.18× the bar | does not fire |

The second registered clause of gate A — that the `ḋ_n − ḋ_λ` bias must not
exceed `d_floor` = 0.020 deg/day — **passes**: the measured bias is
**−0.0074 deg/day** with a robust scatter of 0.0035 deg/day over 2,639
stationed segments. (The bias is real and is the expected consequence of the
Kozai/Brouwer convention of a TLE's mean motion; it is 37% of `d_floor`
and sits below the 0.010 deg/day burn floor, so it never reaches a detector
decision.)

### 2.4 The quantity gate A should have named
Gate A asks whether λ is accurate enough for a 0.1° estimand. σ_n does not
answer that — the event definition of prereg §4 never reads `ḋ_n`; it reads λ.
The registration did not register a λ noise floor, so one is measured here and
labelled as a **descriptive diagnostic added at measurement time**, not a
threshold:

Second differences of λ over consecutive element sets inside stationed
segments (which annihilate any smooth motion and leave only fit-to-fit
scatter), 561 segments:

| p5 | p25 | median | p75 | p95 |
|---:|---:|---:|---:|---:|
| 0.00037° | 0.00070° | **0.00112°** | 0.00170° | 0.00493° |

Median **0.83 km**. The primary threshold X = 0.1° is **89×** the median and
**20.3×** the p95. On the quantity that actually decides an event, the
instrument is not close to its noise floor.

---

## 3. The event catalogue

### 3.1 Primary arm: X = 0.1°, D = 30 d

| | count |
|---|---:|
| Raw events | **493** |
| Active-class approacher, attribution resolved | **487** |
| Passive-class approacher, attribution resolved | **5** |
| Attribution ambiguous (both objects moved comparably) | 1 |
| Flagged `libration_zone` (within ±3.75° of a stable longitude) | 72 |
| Standing co-locations (never 2° apart; **not** events) | 1 |
| Distinct approachers | **224** |
| Distinct targets | **262** |
| Distinct (approacher, arrival-month) arrivals | **427** |
| … of which arrivals with more than one co-located target | 49 |
| Target `object_type` | PAYLOAD for **all 487** |

An arrival into a slot already shared by several satellites yields one event
per target, which is why 487 events correspond to 427 arrivals. Both numbers
are reported; the headline count is the registered one, 487.

**Rejections at each registered criterion**, counted rather than dropped in
silence: 4,191,020 candidate loiters too short; 2,669 broken by a gap > 5 d;
1,797 with no prior separation ≥ 2° inside the 180-day look-back; **79 in
which neither object met the 80% attribution bar** — a symmetric mutual
approach, which prereg §4.3 assigns to no one and which is therefore not an
event. That last figure is a property of the registered definition, not of the
code, and is stated here because it is a real 14% addition to the catalogue
that the definition discards.

### 3.2 Distributions (487 active-resolved events)

| Quantity | p5 | p25 | **median** | p75 | p95 | max |
|---|---:|---:|---:|---:|---:|---:|
| Loiter duration (d) | 31.1 | 36.9 | **57.2** | 111.4 | 413.3 | 2,834 |
| Closest separation (°) | 7.9e-13 | 6.4e-05 | **0.00030** | 0.00193 | 0.0435 | 0.0725 |
| Closest separation (km) | 5.8e-10 | 0.047 | **0.22** | 1.42 | 32.0 | 53.4 |
| Median separation during loiter (°) | 0.0084 | 0.0183 | **0.0312** | 0.0510 | 0.0765 | 0.0908 |
| Transfer duration (d) | 2.2 | 6.6 | **42.8** | 101.4 | 160.7 | 177.9 |
| Transfer drift rate (°/day) | 0.0131 | 0.0226 | **0.0668** | 0.458 | 1.334 | 154.8 |
| Approacher longitude change (°) | 1.91 | 1.99 | **2.19** | 2.65 | 10.2 | 119.4 |

Departure was observed for **413 of 487** events; the arrival-to-departure
interval has a median of **194.7 d** (p25 100.5, p75 796.4, max 5,123). The
remaining 74 had not departed by the end of the archive.

The closest-separation distribution is the striking one: the median event
closes to **0.0003° = 0.22 km of mean longitude**, which is co-location inside
a shared station-keeping box, not an approach to a few hundred kilometres.
Again — this is slot coincidence, not miss distance (§1.1).

Structural metadata split, reported without interpretation: **286 of 487
(58.7%)** events have the same catalogue registry code on approacher and
target.

### 3.3 Sensitivity arms

| Arm | X | D | Raw | Active | Passive | Ambiguous | Libration flag | Passive-exclusion status (prereg §2.6) |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| **primary** | 0.1° | 30 d | 493 | **487** | 5 | 1 | 72 | holds outside ±3.75° |
| | 0.05° | 30 d | 361 | 361 | 0 | 0 | 47 | holds outside ±1.87° |
| | 0.2° | 30 d | 1,192 | 1,126 | 41 | 25 | 347 | holds outside ±7.57° |
| | 0.5° | 30 d | 4,806 | 4,037 | 290 | 479 | 2,529 | holds outside ±20.4° |
| | 0.1° | 14 d | 1,464 | 1,386 | 48 | 30 | 717 | **weak** (±18.4°) |
| | 0.1° | 7 d | 4,403 | 3,885 | 166 | 352 | **4,403** | **void everywhere** |

The D = 7 d arm flags every one of its events as libration-zone because the
bound is void at that duration — the registration predicted this in advance
and it is why D = 30 d, not D = 14 d, was made primary. The passive-class
count rises from 0 to 290 as X widens from 0.05° to 0.5°, which is the
drift-through contamination becoming visible.

---

## 4. Lead time — the headline number of the T8 track

For each event, the registered `lead_causal` is the interval from the
**confirmation** of the initiating drift-change flag (the second consecutive
element set showing the change, i.e. the first instant a causal observer
possessed the evidence) to arrival within X of the target's mean longitude.

**326 of 487 events (66.9%, Wilson 95% [62.6%, 71.0%]) had an initiating flag
inside the 180-day look-back.** The other 161 are reported with
`lead_causal: null` and are counted in every denominator below; suppressing
them would inflate the headline.

| | p5 | p25 | **median** | p75 | p95 | max | mean |
|---|---:|---:|---:|---:|---:|---:|---:|
| `lead_causal` (d), n = 326 | 2.27 | 10.6 | **36.1** | 96.0 | 162.7 | 177.4 | 56.3 |

| ≤ 0 d | 0–7 | 7–14 | 14–30 | 30–60 | 60–120 | 120–180 |
|---:|---:|---:|---:|---:|---:|---:|
| 2 | 60 | 39 | 50 | 56 | 60 | 59 |

**Read as:** of the 487 registered events, 264 (54%) would have been visible
in the public element archive **at least seven days** before arrival, and 175
(36%) at least thirty days before. Two events had a non-positive lead (minimum
−0.90 d): the drift change was only confirmable after arrival.

**Censoring, stated plainly.** 12 of the 326 sit within 10 days of the
180-day look-back wall, so the upper tail is mildly right-censored and the
p95 of 162.7 d is a lower bound. The **secondary** `lead_first_flag` — the
*first* flag of the same transfer rather than the last, added at
implementation time and explicitly **not** the registered headline — has a
median of 146.3 d, but 86 of 326 sit at or beyond 170 d against a 180-day
wall. **That secondary number is heavily censored by the look-back window and
should not be quoted as a lead time**; it says only that the initiating
manoeuvre of a typical event is visible for longer than T8a looked.

### 4.1 The unflattering half: what an alert would have cost

Registered in prereg §5.6 precisely so it could not be omitted. Over the full
archive there were **2,956 active-class relocations** (a stationed segment
followed by another ≥ 2° away) and **1,483 relocation alerts** (a relocation
whose drift change actually tripped the registered flag).

| | value | Wilson 95% |
|---|---:|---|
| Alerts ending in a registered event | 487 / 1,483 = **32.8%** | [30.5%, 35.3%] |
| Alerts ending in a distinct arrival | 427 / 1,483 = **28.8%** | [26.5%, 31.2%] |

So a public-element early-warning surface built on this detector would have
raised **1,483 alerts across the whole archive**, and about one
alert in three would have ended within 0.1° of another satellite for a month
or more. The other two in three are ordinary relocations to empty longitudes.
**That is the honest shape of the capability: a median 36-day warning at a
one-in-three hit rate**, before any of §7's contamination is removed.

(The receipt's `alertPrecisionJeffreys95` field is `null`: scipy is not
installed on `pc`, so the Jeffreys interval could not be computed. Wilson
score intervals are reported in its place throughout, computed in
`tools/proximity_geo_report.py`.)

---

## 5. Repetition — does past behaviour predict the next event?

| | count |
|---|---:|
| Distinct approachers | **224** |
| with ≥ 2 events | **112** (50.0%, Wilson [43.5%, 56.5%]) |
| with ≥ 3 events | 53 |
| with ≥ 5 events | 19 |
| with ≥ 2 events against **distinct** targets | **78** (34.8%, [28.9%, 41.3%]) |

Gate D is not fired: 112 repeaters against a registered bar of 10.

### 5.1 Intraclass correlation of the profile vector (log scale)

| Profile component | ICC |
|---|---:|
| Approacher longitude change | **0.679** |
| Loiter duration | 0.436 |
| Departure drift rate | 0.386 |
| Transfer drift rate | 0.350 |
| Closest separation | 0.305 |
| Transfer duration | 0.277 |

Every component is positive and well away from zero: **an object's approach
events resemble each other more than they resemble the population.** The
strongest is how far the object moves, which is the least surprising (an
object's neighbourhood is fixed by its mission) and the weakest are the
timings.

### 5.2 Leave-one-out predictive skill — the operational version

For each event of each repeat approacher, its loiter duration and closest
separation were predicted from the median of that object's **other** events,
and separately from the population median (n = 375 predictions):

| Predicted quantity | MAE from the object's own history | MAE from the population | **Skill** |
|---|---:|---:|---:|
| Loiter duration | 0.575 (log) | 0.666 (log) | **+0.137** |
| Closest separation | 3.270 (log) | 3.298 (log) | **+0.008** |

**Reported plainly: the skill is small.** Knowing an object's previous events
reduces the error in predicting its next loiter duration by 13.7%, and does
essentially nothing (0.8%) for the closest separation it will achieve. The ICC
is real but the point prediction it buys is weak, and any T8c pattern library
should be built expecting to forecast *whether* and *roughly when*, not *how
close* or *how long*.

### 5.3 Per-object significance
Poisson tail probability of each approacher's event count against the null
rate of **0.807 events per relocation** (§6), Benjamini–Hochberg at q = 0.05
across all **224** approachers: **9 objects survive**. Their NORAD numbers and
p-values are in the receipt (`repetition.fdrTop`). The number is small because
the null rate is large — under chance co-location alone an object that
relocates ten times is expected to land near something eight times.

---

## 6. The chance co-location null

2,956 relocation cases, 1,000 permutations, seed 20260922. Each real arrival
keeps its approacher, its epoch and its entire drift history, and is given an
arrival longitude drawn from the empirical distribution of longitudes occupied
by stationed objects at that epoch. Identical machinery decides the observed
and the null counts, so only the destination differs.

| | count |
|---|---:|
| Expected under a **uniform** belt (`N_s · 2X/360`, summed over arrivals) | 862.7 |
| **Observed**, segment-level | **1,091** |
| Null mean, excluding the drawn object itself | **2,385.7** |
| Null 95% interval | **[2,203, 2,589]** |
| Null mean, counting the drawn object (the literal registered draw) | 5,300.4 |
| Permutations in which the null exceeded the observation | **1,000 / 1,000** |

**The observation is 1,295 below the null mean and outside its 95% interval on
the low side.** Gate C — "the null explains the catalogue" — is not fired, but
not in the direction that would support an excess of proximity behaviour. The
finding is the opposite one:

> **Real GEO relocations end up within 0.1° of another satellite *less* often
> than chance draws from the occupied-longitude distribution predict — by a
> factor of 2.2.**

That is a sensible operational fact stated as arithmetic: the occupied
longitude distribution is heavily clustered, and an object relocating for
ordinary reasons is choosing a slot it can actually occupy, which is by
construction one of the emptier ones. It also means the **aggregate** event
count carries no evidence whatever of excess proximity-seeking at GEO. If
there is structure in this catalogue it is per-object (§5), not population
level.

The registered draw ("from the empirical distribution of longitudes occupied
by stationed objects") makes the drawn longitude itself occupied, so the
object defining it always matches. Both variants are published; the
excluding-self variant is used for gate C because an object cannot be
co-located with itself.

---

## 7. The control — gate B FIRED, and the derivation that failed

### 7.1 Gate B, in the registered words: **the detector leaks.**

| | events outside the libration zone | stationed segments | rate per segment | Wilson 95% |
|---|---:|---:|---:|---|
| Active class | 415 | 24,391 | 0.01701 | [0.01547, 0.01872] |
| **Passive class** | **5** | **294** | **0.01701** | [0.00729, 0.03919] |

Ratio passive:active = **0.9995**, 95% interval **[0.43, 2.30]**. The
registered bar was 2% — i.e. 0.00034. **The cannot-manoeuvre control produces
events at the same per-exposure rate as the manoeuvring population, and the
gate fires by a factor of 21 even at the lower end of its interval.**

Five passive-class events, all of them outside the flagged libration zone:

| Approacher | Type | Target | Arrival | Longitude | Loiter | Closest | Transfer drift |
|---|---|---|---|---:|---:|---:|---:|
| 14114 SL-12 R/B(2) | ROCKET BODY | 28937 HIMAWARI 7 | 2014-05-24 | 145.01° | 31 d | 0.0005° | 0.0411 °/d |
| 43645 FENGYUN 2H DEB | DEBRIS | 32478 EXPRESS AM-33 | 2020-09-11 | 96.54° | 31 d | 0.0001° | 0.0497 °/d |
| 22839 SL-12 R/B(2) | ROCKET BODY | 37816 EUTE 7 WEST A | 2021-03-19 | −7.29° | 67 d | 0.0000° | 0.0204 °/d |
| 14114 SL-12 R/B(2) | ROCKET BODY | 40875 EUTE 8 WEST B | 2021-12-18 | −8.02° | 31 d | 0.0001° | 0.0135 °/d |
| 43645 FENGYUN 2H DEB | DEBRIS | 42695 GSAT 9 | 2022-10-27 | 97.36° | 30 d | 0.0000° | 0.0512 °/d |

### 7.2 The derivation of prereg §2.6 is falsified

Prereg §2.6 derived, from the J₂₂ sectorial term, a maximum longitude
acceleration |λ̈| = 1.701e-3 deg/day², and from it a maximum dwell for an
uncontrolled object of `sqrt(2X / (|λ̈| |sin 2Δ|))`, Δ being the distance from
the nearest stable longitude. **That bound chose D = 30 d.** Checked directly
against the events it was supposed to exclude:

| Population | Events | Exceeding their own §2.6 dwell bound |
|---|---:|---:|
| Passive class (primary arm) | 5 | **5 of 5** |
| Active-class events with transfer drift < 0.025 °/day | 141 | **127 of 141** |

The passive events dwell 30–67 d where the bound allowed 13–22 d. **The bound
is not conservative and the registered ±3.75° libration flag under-covers.**

The derivation's error is identifiable: it computes Δ from the *nominal*
stable longitudes (75.1°E, 104.7°W) and assumes the restoring acceleration is
the full triaxial value at that Δ. The quantity that actually governs a real
object's turnaround is its distance from its *own instantaneous equilibrium*,
which for an old, high area-to-mass object is displaced by solar radiation
pressure and modulated by luni-solar terms. An object turning around close to
its own equilibrium has a much smaller restoring acceleration than its
distance from the nominal stable point implies, and dwells correspondingly
longer. **Deriving a threshold is not the same as validating it, and this one
was not validated before it was registered.**

An attempt to measure λ̈ directly is reported for completeness and is
**inconclusive**: over 3,692 200-sample windows from 308 never-stationed
objects, the median |λ̈| is 1.3e-5 deg/day² and the correlation with the
predicted J₂₂ pattern is 0.072. That is *not* evidence against the J₂₂
constant — a window spanning 100–400 days of a fast drifter covers tens of
degrees of longitude and averages λ̈ over a full sin 2λ cycle to nearly zero.
The measurement is the wrong shape for the question and is reported as such
rather than as a result.

### 7.3 The registered control was the wrong control

The passive class (DEBRIS, ROCKET BODY) has only 294 stationed segments
against the active class's 24,391 — it is a thin control to begin with. Worse,
**the real uncontrolled population at GEO is dominated by dead *payloads***,
which the catalogue labels `PAYLOAD` and which the registered control
therefore cannot see. The evidence is in the catalogue itself: 141 of the 487
active-class events have a transfer drift below 0.025 °/day — slower than any
deliberate relocation and consistent with free libration — and **66 of them
belong to objects launched before 1995**. The top contributors are
`22694 HGS 4 (GALAXY 4)` (11 events), `4250 SKYNET 1` (10), `4353 NATO 2A`
(8), `23448 RADUGA 32` (6), `8747 LES 9` (6), `8746 LES 8` (5),
`22927 TELSTAR 401` (4).

### 7.4 The discriminator that does work

The registered drift-change flag (prereg §5.5) — an observed change in the
object's own mean motion exceeding 0.010 deg/day, confirmed at two consecutive
element sets — splits the catalogue cleanly. This partition was **added after
the registration** and is labelled as such; it changes no registered verdict
and is offered as the T8b/T8c recommendation:

| | n | median loiter | median transfer drift | approachers launched pre-1995 | in libration zone | distinct approachers | repeaters |
|---|---:|---:|---:|---:|---:|---:|---:|
| With an observed drift-change flag | **326** | 68 d | **0.1677 °/day** | **14** | 22 | 170 | 76 (52 multi-target) |
| No flag in the 180 d look-back | **161** | 44 d | **0.0227 °/day** | **78** | 50 | 73 | — |

A factor of 7.4 in transfer drift rate; pre-1995 approachers go from 4.3%
of the flagged events to 48.4% of the unflagged ones. 2 of the 5 passive-class events carry a flag, so the filter is not
perfect — but it converts a catalogue in which the control does not separate
into one where the contamination is concentrated in a nameable, excludable
third.

Loiter duration is a second, weaker discriminator: 49% of active-class events
loiter ≥ 60 d against 20% (1 of 5) of passive ones, and the passive events
cluster at the 30-day floor.

---

## 8. Worked examples

Five, chosen for clarity, two of them from the contaminated class so the
failure mode is visible rather than described. All figures are from the
committed event catalogue; registry codes are the catalogue's own metadata
field. **Every "closest" figure is mean-longitude separation, not distance.**

### 8.1 NORAD 27632 — NIMIQ 2 (2002-062A, CA, launched 2002-12-29) — 13 events, 9 distinct targets
The largest event count in the catalogue, and a commercial communications
satellite. Its transfers are fast (0.45–1.64 °/day) and each is preceded by a
confirmed drift change.

| Flag | Transfer | Arrival | Longitude | Target | Loiter | Closest | Lead |
|---|---|---|---:|---|---:|---:|---:|
| 2013-10-17 | 5 d @ 0.555 °/d, 2.80° | 2013-10-21 | 39.01° | 27811 HELLAS-SAT 2 | 90 d | 0.0003° | **4.4 d** |
| 2016-03-25 | 3 d @ 0.763 °/d, 2.28° | 2016-03-27 | 148.02° | 24653 MEASAT 2 | 89 d | 0.0000° | 2.0 d |
| 2016-12-12 | 3 d @ 0.846 °/d, 2.38° | 2016-12-14 | 91.52° | 29648 MEASAT 3 (+ 3A, 3B) | 50–90 d | 0.0002° | 2.0 d |
| 2017-05-16 | 4 d @ 0.723 °/d, 3.18° | 2017-05-19 | −63.00° | 37602 TELSTAR 14R | 93 d | 0.0001° | 3.5 d |
| 2019-05-03 | 11 d @ 1.637 °/d, 17.86° | 2019-06-10 | 91.48° | 40147 MEASAT 3B (+ 3, 3A) | 87 d | 0.0002° | **38.4 d** |
| 2019-09-26 | 3 d @ 0.684 °/d, 2.06° | 2019-09-28 | 146.00° | 44048 NUSANTARA SATU | 209 d | 0.0000° | 2.7 d |
| 2020-05-05 | 5 d @ 0.466 °/d, 2.17° | 2020-08-13 | −91.11° | 38342 NIMIQ 6 | 228 d | 0.0000° | **99.9 d** |
| none | 4 d @ 0.453 °/d, 2.02° | 2022-03-06 | −109.19° | 26624 ANIK F1 | 982 d | 0.0000° | — |

This is the catalogue's most important interpretive example: **a high event
count is not by itself unusual.** A satellite that is repeatedly relocated
around a crowded belt accumulates events because the belt is crowded, which is
exactly what §6's null measures and why the null sits above the observation.

### 8.2 NORAD 40258 — LUCH (OLYMP) (2014-058A, CIS, launched 2014-09-27) — 12 events, 8 distinct targets
Every event is flagged, transfer drifts 0.018–0.744 °/day, loiters 31–104 d,
closest separations 0.0001°–0.0495° (0.1–36.4 km of mean longitude).

| Arrival | Longitude | Target | Loiter | Closest | Lead |
|---|---:|---|---:|---:|---:|
| 2016-05-01 | −1.06° | 28358 INTELSAT 1002 | 32 d | 0.0495° | 118.6 d |
| 2018-04-25 | 47.51° | 26766 INTELSAT 10 | 40 d | 0.0001° | 2.6 d |
| 2018-11-01 | 56.98° | 36032 NSS 12 | 51 d | 0.0022° | 6.1 d |
| 2019-02-19 | 59.92° | 41748 INTELSAT 33E | 36 d | 0.0306° | 2.2 d |
| 2019-09-14 | 65.94° | 37238 INTELSAT 17 | 32 d | 0.0033° | 75.1 d |
| 2019-10-21 | 68.46° | 41747 INTELSAT 36 | 31 d | 0.0151° | 2.8 d |
| 2021-02-17 | −8.08° | 40875 EUTE 8 WEST B | 55 d | 0.0096° | 2.2 d |
| 2021-05-27 | 45.18° | 43632 AZERSPACE 2/INTELSAT 38 | 45 d | 0.0371° | 10.1 d |
| 2021-08-14 | 56.95° | 36032 NSS 12 | 45 d | 0.0241° | 24.3 d |
| 2021-10-06 | 59.97° | 41748 INTELSAT 33E | 104 d | 0.0115° | 5.5 d |

### 8.3 NORAD 55841 — LUCH (OLYMP) 2 (2023-031A, CIS, launched 2023-03-12) — 10 events, 8 distinct targets in under two years
Arrivals at 8.94°, 8.95°, 3.19°, −0.59°, −0.91°, −0.89°, −0.94°, 62.00°;
loiters 31–83 d; transfer drifts 0.014–0.517 °/day; leads 4.6–142.4 d. Its
2024-09-18 arrival at −0.906° was within 0.0083° (6.1 km of mean longitude) of
two objects at once (28358 INTELSAT 1002 and 46113 MEV-2), which is one
arrival counted as two events (§3.1).

### 8.4 NORAD 22694 — HGS 4 (GALAXY 4) (1993-039A, US, launched 1993-06-25) — 11 events, **10 of them with no flag**
A contaminated example, included deliberately. Every transfer runs at
0.013–0.020 °/day over 95–165 days, and the arrivals cluster at 71.99°,
72.06–72.14° and 78.53–78.59° — **inside the 75.1°E libration zone**. Loiters
31–75 d, closest separations 0.0001°–0.0025°. Ten of its eleven events carry
no drift-change flag at all, and the eleventh has a "flag" of 0.0169 °/day,
barely over the 0.010 floor.

This object is drifting through a stable longitude and turning around near
occupied slots. It satisfies every registered criterion and it is not an
approach.

### 8.5 NORAD 4250 — SKYNET 1 (1969-101A, UK, launched 1969-11-22) — 10 events, **zero flags**
The clearest failure case. Transfers at 0.0114–0.0129 °/day over 149–169 days,
arrivals clustered at −103.30° and −107.11 to −107.29°, loiters 31–110 d,
closest separations down to 0.0000°. **An object launched in 1969 cannot be
manoeuvring**; it is librating about the 104.7°W stable point and its
turnarounds are landing on occupied longitudes. −107.3° is 2.6° from the
stable point and therefore inside the flagged libration zone; −103.30° is
1.4° from it and also inside. This object is why §7.2 matters: the bound was
supposed to make these impossible at D = 30 d, and it did not.

---

## 9. Registered blind spots, as they actually bit

Each was declared in prereg §9 before measurement. Reported here with what it
cost.

1. **Mean longitude is not miss distance.** Unchanged and unquantifiable
   within T8a. The median event's 0.22 km is a slot coincidence.
2. **Cadence.** 2,669 candidate loiters were broken by a gap > 5 d at the
   primary arm and are lost. Near-GEO median epoch spacing is 0.865 d.
3. **Motion below the noise.** The detector floor is 0.010 deg/day = 0.78 km
   of semi-major axis. **The catalogue is a lower bound on events, never a
   census**; a transfer executed below the floor is invisible, and 161 events
   (33%) have no visible initiating flag at all — some of those will be slow
   deliberate transfers rather than free drift.
4. **The libration zone.** 72 of 487 events flagged. §7.2 shows the flag is
   too narrow: events at −110.2° (5.5° from the stable point, outside the
   flag) belong to a 1970 object.
5. **Catalogue completeness.** Untested and untestable from inside. Absence of
   an event is not evidence of absence of an approach.
6. **Regime.** Near-GEO only, 1,613 of 68,089 archive objects.
7. **Interpolation.** Linear between element sets, refused across gaps > 5 d.

One blind spot was **not** declared and should have been: **the look-back
window truncates the lead-time distribution** (§4). T8b must register a
look-back long enough that the lead time is not censored by its own
measurement window, or must report a survival curve rather than percentiles.

---

## 10. What this means for the rest of T8

Stated as findings, not as a plan; T8b/T8c scope is Sean's.

1. **The lead time is real and is the track's asset.** Median 36 days of
   causal warning from public elements, at 33% precision, over 1,483 historical
   alerts. Nothing about that depends on the contamination in §7 — it is
   measured on the approacher's own mean motion.
2. **The registered event definition is not a behaviour detector.** It is a
   *geometry* detector, and GEO geometry is produced by free libration as
   readily as by manoeuvring. Any T8 surface must carry manoeuvre
   corroboration (§7.4) as a first-class requirement, not as a filter added
   afterwards.
3. **The right control is not the catalogue's passive class.** It is
   objects with no observed manoeuvre of any kind over the relevant span —
   which includes a large population of dead payloads. That control must be
   constructed, not inherited from `object_type`.
4. **Aggregate counts carry no signal** (§6). The population-level question is
   answered: negative. Per-object repetition is where the structure is, and it
   is modest (§5.2).
5. **A derived threshold that was never validated cost this pilot its
   control** (§7.2). The estate rule is that physical assumptions are not
   facts; the corollary this measurement adds is that a *derivation* is not a
   validation either, and a threshold that a control depends on should be
   checked against data that cannot have been used to set it.

---

## 11. Reproduction

```
# registration, committed alone, before any measurement code existed
git show c898397 --stat

# the instrument and its tests
python3 -m unittest tests.test_proximity_geo          # 35 tests
python3 tools/proximity_geo.py --stage all            # 293 s + 2,022 s, CPU
python3 tools/proximity_geo_report.py --timelines     # every figure above
```

Determinism: seed 20260922 for the permutation null; no other randomness.
Source hashes of the analysis module and of every pipeline module it imports
are in `docs/proximity-20260922-receipt.json` under `sourceSha256`
(`tools/proximity_geo.py` = `59c5270b…134480`).

Nothing from T8a was written to `src/`, `data/`, `public/` or any site
surface. Publication and site framing for this track is reserved to Sean.
