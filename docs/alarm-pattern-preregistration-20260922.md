# T8c pre-registration: a behavioural pattern taxonomy, and the estimand that decides whether the alarm's "categorized before" clause is supportable

Committed **alone**, before any T8c measurement code exists and before any
T8c number exists. `tools/alarm_pattern.py`, its tests, the feature table,
the taxonomy, the receipt, `docs/alarm-pattern-results-20260922.md` and
`docs/alarm-lane-design-20260922.md` all follow in later commits, and the
ordering in `git log` is the evidence. Nothing below may be revised after a
number exists.

Written against, and constrained by:

- `docs/proximity-preregistration-20260922.md` and
  `docs/proximity-results-20260922.md` (T8a, GEO, discharged).
- `docs/proximity-leo-preregistration-20260922.md` and
  `docs/proximity-leo-results-20260922.md` (T8b, LEO/MEO/HEO, discharged).
- `docs/proximity-priorart-20260922.md` — its **eight forbidden phrasings**
  and **thirteen must-cites** bind every T8c output, including this one.

---

## 0. Why T8c exists, in one paragraph, and what would make it fail

T8a measured a real 36-day median causal lead time at GEO and found that an
approacher's events resemble each other (ICC 0.277–0.679 across six profile
components) — but that the **operationally meaningful** version of that
resemblance is nearly worthless: leave-one-out predictive skill of **+0.137**
for loiter duration and **+0.008** for closest separation. T8a named the cause
in its §5.2 and §12: the profile was described by only **two crude features**
per outcome. T8c tests that diagnosis directly. It extracts a rich feature
vector per event, builds an unsupervised taxonomy over it with the cluster
count chosen by a criterion fixed **in this document**, and measures whether
predicting an approacher's next event from its prior events' **cluster
membership** beats T8a's +0.137.

**A second null is a legitimate and publishable result and is registered as
such.** If the rich features do not buy skill, the finding is that GEO
approach behaviour is repeatable in *character* (the ICC) and not in *number*
(the skill), and the programme learns — from a measurement rather than from an
assumption — that the behavioural alarm's "seen N times before, outcome Y
within ~D days" clause cannot be supported today at GEO. That is a finding the
alarm design (T8c task 2) must be written to survive, and §9 says how.

---

## 1. Framing rules, binding and test-enforced

Inherited verbatim in force from T8a §0 and T8b §0, restated because they
constrain every line of output:

1. **The instrument is ownership-agnostic mathematics.** Catalogue registry
   codes (`country`) are metadata columns carried on rows and enter **no**
   feature, no transform, no distance, no cluster assignment and no
   prediction. A test asserts that no feature-extraction, clustering or
   prediction function in `tools/alarm_pattern.py` contains the substring
   `country` or `registry`.
2. **Facts, never intent.** No cluster may be named, described or summarised
   with a purpose. A cluster name is a mechanical description of element
   behaviour ("fast single-burn transfer, sharp arrival, tight dwell"), never
   a mission, a motive or an actor. A test asserts the banned intent
   vocabulary is absent from the tool and from the cluster-name table.
3. **No miss distance.** Every separation figure is mean-longitude
   separation, a slot coordinate (T8a §1.1). A test asserts no feature is
   named or documented as a distance, range or miss.
4. **No propellant, delta-V, mass or consumables figure** is computed for any
   object. A test asserts no such quantity appears in any emitted row.
5. **No per-nation narrative.** Exactly one registry-related figure is
   permitted in the results document — the adjusted Rand index between the
   partition and the approacher registry code, reported as arithmetic with no
   interpretation, in the manner of T8b §3.4 — and it is reported because
   omitting it would also be a choice. Whether registry codes ever appear on
   any surface at all is an operator decision reserved to Sean and is not
   taken here.
6. **The prior-art bans apply.** No "first", no "at catalogue scale", no
   "validated" before the corresponding gate has run, no intent/threat
   vocabulary, and the Soret/Leyva-Mayorga/Popovski "plane matching"
   false friend is not cited.

---

## 2. Inputs, fixed

| Input | Path | Fixed content |
|---|---|---|
| Event catalogue | `docs/proximity-events-20260922.jsonl` | the committed T8a primary arm (X = 0.1°, D = 30 d); sha256 recorded in the receipt |
| Archive | `/home/sdegan/space-orbit-history/orbit-history.sqlite3` | read-only, `PRAGMA query_only=1` |
| Calibration | `sigma_n_deg_per_day` = **0.0006038533519066339** | read from the catalogue's provenance record, **never recalibrated** — T8c must not move a T8a threshold |

**Population, primary arm.** The **487** events whose `approacherClass` is
`active` and whose `attribution` is `resolved` — T8a's registered headline
catalogue, exactly. **224** distinct approachers, **112** with ≥ 2 events.

**Population, secondary arm (registered here, never promoted).** The **326**
events carrying a confirmed initiating drift-change flag (T8a §7.4,
`initiatingFlagMs` non-null). T8a showed the unflagged 161 are contaminated by
free libration; the secondary arm exists so the taxonomy cannot be read as a
contamination detector by accident, and §8's gate R tests for exactly that.

**Element histories.** For every NORAD appearing as approacher or target
(409 objects), all rows of `element_set` for that NORAD, filtered by T8a's
§3.1 near-GEO rule (0.95 ≤ n ≤ 1.05 rev/day, e ≤ 0.01, i ≤ 25°) applied to the
same quantised columns with the same scale constants. Mean longitude λ, its
drift-informed unwrap, and drift rate ḋ are computed by **importing T8a's own
functions** from `tools/proximity_geo.py` — not reimplemented — so no
definition can silently drift. A test asserts the import path, not a copy.

**IMPL, declared now.** T8a built one global daily grid over all near-GEO
objects; T8c builds a per-object grid. The grid *sample points* are identical
by construction (absolute `day_index · 86400000 + 43200000` ms), so station
segments are identical except where a segment would have been clipped by the
global span, which cannot occur for an object inside its own span. The
interpolation rule, its 5-day refusal and `station_segments` are T8a's
functions, imported.

---

## 3. The feature set — FIXED HERE, before extraction

Thirty-two features in seven blocks, plus five missingness indicators.
**Nothing may be added, removed or redefined after extraction begins.** Every
definition below is complete enough to implement without a further choice;
where a choice remained it is made here and marked **[fix]**.

Notation: `λ_a`, `λ_t` are the unwrapped mean longitudes of approacher and
target; `ḋ` is the approacher's drift rate (deg/day) at each of its own
element-set epochs; `t_s` = `transferStartMs`, `t_a` = `arrivalMs`,
`t_e` = `loiterEndMs`, `t_d` = `departureMs`. **Flags** are the confirmed
drift-change flags of T8a §5.5 (`drift_change_flags`, threshold
`max(5σ_n, 0.010) = 0.010 deg/day`, flag time = the epoch of the **second**
consecutive departing element set), computed with the σ_n of §2.

Four **disjoint** flag-counting windows are fixed here so that no flag is
counted twice and no window edge is chosen later:

| Window | Interval |
|---|---|
| initiation | `[t_s − 5 d, t_s + 1 d]` |
| transit | `(t_s + 1 d, t_a − 2 d)` |
| arrival | `[t_a − 2 d, t_a + 5 d]` |
| dwell | `(t_a + 5 d, t_a + 30 d]` |

**The dwell block is computed over the FIRST 30 DAYS of the dwell only.**
Every registered event dwells at least 30 days by construction (D = 30 d), so
this window exists for all 487, and it removes the leakage that would
otherwise let a dwell-block feature encode the dwell *length*, which is the
outcome. This is the single most important design decision in §3 and it is
made before any number exists.

### 3.1 Baselines used by several features

- `ḋ_base` **[fix]** = median of ḋ over the **10** element sets immediately
  preceding `t_s` (T8a's `BURN_BASELINE_SAMPLES`); NaN if fewer than 10 exist.
- `ḋ_plateau` **[fix]** = the value of ḋ at the element set in
  `[t_s − 5 d, t_a]` maximising `|ḋ − ḋ_base|`; if `ḋ_base` is NaN, maximising
  `|ḋ|`.
- `A` **[fix]** = `|ḋ_plateau − ḋ_base|`, the transfer's drift-rate amplitude.
- `s(t)` = `λ_a(t) − λ_t(t)`, both unwrapped, evaluated on the union of the
  two objects' element epochs by T8a's interpolation rule (refused across a
  gap > 5 d, refusals counted and never silently dropped).
- `σ_dir` **[fix]** = `sign(s(t_s))`; the direction the gap is closed from.

### 3.2 Initiation block (4 features)

| # | Name | Definition |
|---:|---|---|
| 1 | `init_drift_change_mag` | `|initiatingDriftChangeDegPerDay|` from the catalogue; NaN when no flag |
| 2 | `init_ramp_days` | searching forward from `t_s − 5 d`: the epoch at which `|ḋ − ḋ_base|` first reaches `0.9 A`, minus the epoch at which it first reaches `0.1 A`. NaN if either is not reached by `t_a` |
| 3 | `init_stage_count` | flags in the **initiation** window |
| 4 | `init_abruptness` | `A / max(init_ramp_days, 0.5)` deg/day². **[fix]** the 0.5 d floor is below the archive's 0.865 d median near-GEO epoch spacing, so it binds only when the ramp is unresolved |

### 3.3 Transit block (6 features)

| # | Name | Definition |
|---:|---|---|
| 5 | `transit_days` | `transferDays` (catalogue) |
| 6 | `transit_drift_median` | `|transferDriftDegPerDay|` (catalogue) |
| 7 | `transit_drift_peak` | `max |ḋ|` over element sets in `[t_s, t_a]` |
| 8 | `transit_drift_flatness` | `mean|ḋ| / max|ḋ|` over `[t_s, t_a]`; 1 means a flat plateau (impulsive in, impulsive out), a small value means a single-peaked or ramped profile |
| 9 | `transit_midcourse_count` | flags in the **transit** window |
| 10 | `transit_longitude_span` | `|approacherMotionDeg|` (catalogue) |

### 3.4 Arrival block (5 features)

| # | Name | Definition |
|---:|---|---|
| 11 | `arrival_brake_mag` | `max |ḋ_{k+1} − ḋ_k|` over consecutive element sets in `[t_a − 5 d, t_a + 5 d]` |
| 12 | `arrival_brake_days` | from the **last** epoch in `[t_s, t_a + 5 d]` with `|ḋ| ≥ 0.5 · transit_drift_peak` to the **first** subsequent epoch with `|ḋ| ≤ 0.1 · transit_drift_peak`; NaN if no such epoch exists by `t_a + 15 d` |
| 13 | `arrival_overshoot_deg` | `max(0, max over t ∈ [t_a, t_a + 15 d] of (−σ_dir · s(t)))`. Positive = the approacher crossed past the target's longitude; 0 = it stopped short or on |
| 14 | `arrival_residual_drift` | median `|ḋ|` over `[t_a, t_a + 5 d]` |
| 15 | `arrival_flag_count` | flags in the **arrival** window |

### 3.5 Dwell block (5 features, first 30 days only)

| # | Name | Definition |
|---:|---|---|
| 16 | `dwell_sk_tightness` | MAD of the residual of `λ_a` about a least-squares straight line, over `[t_a, t_a + 30 d]`, in degrees |
| 17 | `dwell_rel_amplitude` | `0.5 · (p95 − p5)` of `s(t)` over `[t_a, t_a + 30 d]`, in degrees |
| 18 | `dwell_rel_period_days` | the lag of the **first local maximum** of the autocorrelation of linearly-detrended `s(t)` resampled to a 1-day grid over `[t_a, t_a + 30 d]`, searched over lags **2–15 d** **[fix]**; NaN if fewer than 20 finite daily samples exist or no local maximum is found |
| 19 | `dwell_rel_osc_fraction` | variance of the least-squares sinusoid at `dwell_rel_period_days` divided by the variance of detrended `s(t)`, same window; NaN when 18 is NaN |
| 20 | `dwell_correction_rate` | flags in the **dwell** window, per 30 days (the window is 25 days, so the count is scaled by 30/25) |

### 3.6 Departure block (4 features)

| # | Name | Definition |
|---:|---|---|
| 21 | `departure_observed` | 1 if `departureMs` is non-null, else 0 |
| 22 | `departure_drift_abs` | `|departureDriftDegPerDay|`; NaN when not observed |
| 23 | `departure_reverses` | `+1` if `sign(departureDriftDegPerDay) = sign(λ_a(t_a) − λ_a(t_s))`, else `−1`; NaN when not observed |
| 24 | `departure_dest_distance_deg` | `|wrap180(λ̄ of the approacher's first station segment beginning after t_d − loiterLongitudeDeg)|`; NaN when no such segment exists |

### 3.7 Cadence block (4 features)

| # | Name | Definition |
|---:|---|---|
| 25 | `cadence_days_since_prev` | `t_a` minus the arrival of the approacher's most recent **earlier** event (any target); NaN for the object's first event |
| 26 | `cadence_prior_events` | number of the approacher's events with an earlier arrival |
| 27 | `cadence_prior_targets` | number of **distinct** targets among those |
| 28 | `cadence_prior_arrivals` | number of distinct prior `(approacher, arrival-month)` arrivals, T8a §3.1's arrival grouping |

### 3.8 Context block (4 features)

| # | Name | Definition |
|---:|---|---|
| 29 | `lead_causal_days` | `leadCausalDays` (catalogue); NaN when no flag |
| 30 | `has_initiating_flag` | 1 if `initiatingFlagMs` is non-null, else 0 — T8a §7.4's discriminator, included **because** gate R must be able to catch a taxonomy that is merely re-describing it |
| 31 | `libration_zone` | the catalogue's `libration_zone` flag, 0/1 |
| 32 | `separation_at_start_deg` | `separationAtTransferStartDeg` (catalogue) |

### 3.9 Missingness indicators (5, carried as features)

`miss_init_flag`, `miss_ramp`, `miss_brake_days`, `miss_dwell_period`,
`miss_departure`, each 1 where the corresponding feature is NaN. They are
features because "this event has no visible initiating burn" is itself a
behavioural fact (T8a §7.4), not merely an absence.

### 3.10 Outcome variables — explicitly NOT features

`loiterDays` and `closestSeparationDeg` are the two outcomes of §6 and are
**excluded from every clustering feature vector**. A test asserts that neither
name appears in the feature table's column list.

### 3.11 Transform and standardisation, fixed

- **Log transform**, `x → log(x + ε)` with `ε = 1e-9`, applied to exactly
  these strictly-positive heavy-tailed features: 1, 2, 4, 5, 6, 7, 11, 12, 13,
  14, 16, 17, 18, 20, 22, 24, 25, 28, 29, 32. The remaining features (3, 8, 9,
  10, 15, 19, 21, 23, 26, 27, 30, 31 and the five indicators) are used raw.
  **[fix]** feature 10 (`transit_longitude_span`) is left raw because every
  event has ≥ 2° by the registered event definition, so its dynamic range is
  bounded below and the log buys nothing.
- **Imputation**: each NaN is replaced by the **training fold's median** of
  that feature after transform. Never the full-sample median inside a
  leave-one-out fold — that is the leak this clause exists to prevent.
- **Standardisation**: z-score with the training fold's mean and standard
  deviation; a zero-variance feature in a fold is dropped in that fold and the
  drop is counted.
- **Distance**: Euclidean on the standardised vector. No feature weighting.

---

## 4. The taxonomy

**Algorithm.** k-means (Lloyd), k-means++ initialisation, `n_init = 50`,
`max_iter = 300`, `tol = 1e-10`, seed **20260922**. Implemented in NumPy
(`scipy` and `scikit-learn` are not installed on `pc`; that is stated here so
the absence is not mistaken for a choice) and unit-tested against a synthetic
three-blob fixture with a known answer.

**The cluster count is chosen by this criterion and by nothing else.**

> **PRIMARY CRITERION:** over `k ∈ {2, 3, …, 10}`, choose the `k` maximising
> the **mean silhouette coefficient** (Euclidean, over all events of the
> primary arm, on the full-sample standardised matrix). Ties — differences
> below 1e-6 — are broken toward the **smaller** k.

No elbow is eyeballed, no k is chosen for interpretability, and the k this
criterion returns is the k the taxonomy has, whatever it is.

**Two secondary criteria are computed and reported and govern nothing:** the
**gap statistic** (Tibshirani et al., `B = 50` uniform reference draws inside
the PCA-aligned bounding box, seed 20260922) and the within-cluster
sum-of-squares curve. **If a secondary criterion disagrees with the primary,
both are reported and the primary governs**; the disagreement is a finding
about the feature space, not a licence to switch.

**Characterisation.** Each cluster is reported with: its size; its feature
centroid in **original units** (not z-scores) with the population median
beside it; the five features whose standardised centroid deviates most from
zero, which are what name it; and its **outcome distribution** —
loiter-duration and closest-separation percentiles, the fraction of its events
carrying an initiating flag, the fraction in the libration zone, and the
distribution of `cadence_days_since_prev`.

**Stability.** 200 bootstrap resamples **of approachers, not of events**
(events within an object are not independent), seed 20260922; the clustering
is refit on each resample and matched to the full-sample partition by greedy
maximum-Jaccard assignment. Per-cluster Jaccard is reported. This feeds
gate Q.

---

## 5. The taxonomy's causal subset

The taxonomy of §4 uses features an observer possesses only **after** the
dwell has begun. An alarm cannot. A **second** clustering, fit by the
identical procedure with its own silhouette-chosen k, is therefore registered
over the **causal subset**: features 1–15, 25–32 and the indicators
`miss_init_flag`, `miss_ramp`, `miss_brake_days` — everything observable by
the moment of arrival. The dwell and departure blocks are excluded.

Both taxonomies are reported. The §4 taxonomy is the behavioural one and
answers "what kinds of approach are there". The §5 taxonomy is the alarm's
and answers "what can be recognised in time to say anything".

---

## 6. THE MEASUREMENT THAT DECIDES T8c

### 6.1 The baseline, restated exactly

T8a §5.2, implemented in `tools/proximity_geo.py::repetition_stats`:

> For each of the 112 repeat approachers, and each of its events, predict
> `log(loiterDays)` from the **median of that object's other events'**
> `log(loiterDays)`, and separately from the **median over all 487 events**.
> `skill = 1 − mean(|error_own|) / mean(|error_population|)`, n = 375.
> Measured: **+0.137** for loiter duration, **+0.008** for closest separation.

### 6.2 Gate V — the reproduction check, run FIRST

T8c recomputes that number from the committed catalogue with its own code
before it computes anything else. **If the reproduction differs from +0.137 by
more than ±0.005, the comparison is not like-for-like**, gate V fires, and
every skill number in the results document is labelled as not directly
comparable to T8a's. This check exists because a headline comparison against a
baseline one has not reproduced is worthless.

### 6.3 Estimand E1a — the registered headline, like-for-like

Identical protocol to §6.1 — same population (repeat approachers), same
leave-one-**event**-out structure, same population denominator, same n — with
one substitution:

> The held-out event's predicted `log(loiterDays)` is the **median
> `log(loiterDays)` of every event in the predicted cluster, excluding every
> event of the held-out object.**
> The predicted cluster is the **modal cluster of the held-out object's other
> events**; ties are broken toward the cluster whose centroid is nearest, in
> standardised space, to the mean of those other events' vectors.

**Leakage control, registered:** for each held-out object the entire
clustering is **refit with that object's events removed** (leave-one-object-out
refit, 112 refits), and the transform/imputation/standardisation constants of
§3.11 come from that fold only. The held-out object's events are then assigned
to the nearest fold centroid. Nothing about the held-out object touches the
model that predicts it.

**`skill_E1a = 1 − MAE_cluster / MAE_population`**, MAE in natural-log space,
population denominator identical to §6.1's.

> **The number T8c exists to produce is `skill_E1a` for loiter duration,
> reported beside +0.137.**

### 6.4 Estimand E1b — the causal version

As E1a, but the predicted cluster is the modal cluster of the object's
**strictly prior** events only, and the prediction is made only for events
with at least one prior event. A smaller n, and the only version an alarm
could actually have run. Reported beside E1a and never substituted for it.

### 6.5 Estimand E2 — the alarm's own estimand

Using the §5 **causal** taxonomy: the held-out event is assigned to a cluster
by its **own causally-available features** (fold-refit, held-out object
excluded as in §6.3), and `log(loiterDays)` is predicted from that cluster's
median over other objects' events. This is what an alarm firing at arrival
could say about the dwell that is about to happen. Reported for the full
primary arm, not only repeat approachers, with its n.

### 6.6 Estimand E3 — closest separation

E1a, E1b and E2 repeated verbatim with `log(closestSeparationDeg)` as the
outcome. Baseline **+0.008**. T8a's §5.2 predicted this one would stay near
zero; the prediction is recorded here so that confirming it counts.

### 6.7 Estimand E4 — cadence, the clause the alarm actually needs

The alarm's stated shape is "outcome Y within ~D days". D is a **time**, and
neither T8a estimand is a time. So, registered here as a first-class estimand:

> Predict `log(cadence_days_since_prev)` — the interval to the approacher's
> **next** event — from the object's prior events' cluster membership, by the
> E1a protocol, against the population-median baseline. Report the skill and
> the within-cluster percentile spread of the interval, which is the width the
> alarm would have to quote.

There is no T8a baseline for E4; its baseline is the population median and its
skill is reported against that alone.

### 6.8 Uncertainty

Every skill figure carries a **bootstrap 95% interval over approachers**
(2,000 resamples of the 112 repeat approachers, seed 20260922), because the
events are clustered within objects and an event-level interval would be too
narrow. A skill whose interval straddles zero is reported as straddling zero.

---

## 7. Compute

CPU, on `pc`, `nice`-d, read-only against the archive. Expected cost, stated
before measurement so an overrun is visible: the per-object indexed history
load is **measured at 9.8 s** for all 409 objects (the table is
`WITHOUT ROWID` on `(norad, epoch_ms)`, so no full scan is needed and T8a's
293-second sequential extract is not repeated); feature extraction over 487
events is seconds; the clustering is k-means over ≤ 487 points in ≤ 37
dimensions, and the heaviest single item is the 112 leave-one-object-out
refits × 9 candidate k × 50 initialisations ≈ 50,400 k-means runs on ≤ 487
points, which is an estimated **low single-digit minutes**.

**No GPU stage is registered.** The measurement that would justify one is
recorded anyway: the wall clock of the full leave-one-object-out loop is
reported in the receipt, and if it exceeds **600 s** the GPU is exercised
through `/home/sdegan/gpu-broker/gpu-run` on the same sub-problem and both
timings are published, in the manner of T8b §1.2 — which found the CPU won by
12.8×. A GPU is used only if it wins a measured race, never because it is
available.

Determinism: seed **20260922** for k-means++ initialisation, the gap
statistic's reference draws, the bootstrap stability resamples and the
bootstrap skill intervals. No other randomness. Source sha256 of the tool, its
tests, this registration and every module imported goes in the receipt.

---

## 8. Gates — the acceptance criteria, fixed now

Each is a condition that, if met, **fires** and must appear in the first
screen of the results document in the registered words.

| Gate | Fires when | Registered meaning |
|---|---|---|
| **P** | `skill_E1a` (loiter) **≤ 0.157** — i.e. the rich taxonomy fails to beat T8a's +0.137 by at least +0.02 absolute | **the taxonomy does not beat feature poverty.** A second null. The alarm's "categorized before → outcome Y" clause is not supportable at GEO today, and the alarm design must say so on its face |
| **Q** | median per-cluster bootstrap Jaccard **< 0.5** at the chosen k | **the taxonomy is not stable.** The clusters are a partition of this sample, not classes of behaviour |
| **R** | adjusted Rand index between the §4 partition and the `has_initiating_flag` split **≥ 0.5** | **the taxonomy is re-describing T8a's known contamination**, not behaviour. The secondary arm of §2 becomes the reportable one |
| **S** | between-cluster η² of `log(loiterDays)` **< 0.05** | **outcome degeneracy.** The clusters carry no outcome information, so an alert could not quote a per-pattern outcome distribution at all |
| **T** | fewer than **20** events in the smallest cluster at the chosen k, **or** fewer than **50** leave-one-out predictions | **underpowered.** Every affected figure is labelled UNDERPOWERED and no predictive claim is made from it |
| **U** | more than half the 32 features are NaN for more than 30% of events | **feature poverty was not repaired**, only relocated; the rich vector is mostly imputation |
| **V** | the §6.2 reproduction of T8a's +0.137 is outside ±0.005 | **the comparison is not like-for-like**; every skill number is labelled as such |

**None of these firing invalidates T8c.** P firing is the null result the task
brief explicitly licensed and is the single most consequential thing T8c could
report to the programme. What is forbidden is discovering a gate has fired and
revising the gate.

---

## 9. What the alarm-lane design document may and may not assume

`docs/alarm-lane-design-20260922.md` is written **after** this registration
and **before or after** the numbers, but it is bound either way:

- It is a **design**. Nothing is deployed, nothing is written to `src/`,
  `data/`, `public/` or any site surface, and no alert is emitted anywhere.
- Its alert template must be writable under **both** outcomes of gate P. If P
  fires, the template's outcome clause degrades to a per-pattern **outcome
  distribution with its measured spread and its measured precision**, and must
  not degrade to a point prediction.
- It inherits the **measured** lead-time budget — GEO median 36.1 d at 32.8%
  precision, LEO median 195.9 d at 44.1% precision for **in-track phasing
  campaigns** (T8b §3.3's qualification travels with the number, always).
- It inherits the **false-alarm accounting** as a publication requirement: a
  precision figure per pattern class, published beside every alert, never
  suppressed, never aggregated away.
- It gates its own vocabulary the way `pipeline/orbit_events.py` gates the
  word "manoeuvre" — `manoeuvreLabelPermitted` is **false** in the shipped
  pipeline because the passive control stands at 34 flags in 1,941 intervals
  against a design target of one in a thousand, and `confidence` is hard-wired
  to `"candidate"` or weaker. T8c's design may not invent a stronger word than
  the shipped detector has earned.
- It names the decisions **reserved to Sean** and takes none of them:
  publication surface, framing, and whether registry codes ever appear.

---

## 10. Declared blind spots, before they bite

1. **487 events is a small sample for a 37-dimensional feature space.** The
   ratio is ~13 events per dimension and k-means in that regime finds
   partitions in noise as readily as in structure. Gate Q is the only defence
   registered and it is a weak one.
2. **The outcome may be intrinsically unpredictable.** T8a's ICC says events
   *resemble* each other; nothing in T8a says the resemblance is in the
   quantity anyone wants forecast. A null at gate P cannot distinguish "the
   features are still too poor" from "loiter duration is not a predictable
   quantity", and the results document must say so in those words rather than
   choose.
3. **The taxonomy inherits every T8a contamination.** 161 of 487 events have
   no visible initiating burn and T8a §7.4 shows they are dominated by free
   libration of pre-1995 objects. Gate R tests whether the clusters merely
   rediscover this; nothing repairs it, because repairing it is T8b's
   manoeuvre-history control and applying that at GEO is not registered here.
4. **The dwell block sees 30 days of a dwell whose median is 57 days.** The
   leakage control of §3 costs exactly this, knowingly.
5. **No LEO arm.** T8b's 71 arm-M events across 55 approachers cannot support
   a 37-dimensional taxonomy, and its feature set is a different physical
   vocabulary (plane angle, relative phase, δa). A LEO taxonomy is a separate
   registration and is **not** attempted here; the alarm design carries LEO's
   lead-time budget as an input and nothing more.
6. **Cluster membership is not a behaviour.** It is a position in a feature
   space this document fixed. A different fixed feature set would give
   different clusters, and no result here licenses the phrase "the behaviour
   classes of GEO approach".
7. **The archive's `month_rollup` is 15% stale** (T8a §1, T8b §1). T8c reads
   `element_set` directly and never sizes anything from the rollup.

---

## 11. What is committed with this document

**Nothing.** This registration is committed alone. `tools/alarm_pattern.py`,
`tests/test_alarm_pattern.py`, the feature table, the taxonomy, the receipt,
`docs/alarm-pattern-results-20260922.md` and
`docs/alarm-lane-design-20260922.md` all follow in later commits, and the
ordering in `git log` is the evidence.
