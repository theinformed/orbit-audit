# T8d pre-registration: the trigger-time predictor — a taxonomy an alarm can actually run, and the per-object predictor the variance decomposition points at

> **Committed ALONE and BEFORE any measurement code exists.** No tool, no
> feature table, no receipt, no results document and no edit to the alarm-lane
> design accompanies this commit. The ordering in `git log` is the evidence.
>
> **Design only. Nothing is deployed, nothing is scheduled, nothing goes on any
> site surface, no alert is emitted anywhere, and nothing here is written to
> `src/`, `data/` or `public/`.** Every operator decision of
> `docs/alarm-lane-design-20260922.md` §10 stays reserved.

Written 2026-09-22, after and bound by:

- `docs/alarm-pattern-preregistration-20260922.md` (T8c registration) and
  `docs/alarm-pattern-results-20260922.md` (T8c results): the 32-feature
  vector, the six-class taxonomy, `skill_E1a` = **+0.128** against T8a's
  **+0.137**, **gate P FIRED**, the flagged-only arm at **+0.001**, the
  between-object variance fraction **0.688** against the between-cluster
  **0.130**, and the post-registration hybrid **D2 = +0.206 [+0.127, +0.272]**.
- `docs/alarm-lane-design-20260922.md` §4.1, §6 and §11.1–11.2, which name the
  **trigger-time taxonomy and its per-class precision** as the measured blocker
  between the programme and a working behavioural alarm, and withhold the
  "matches pattern P" clause until it exists.
- `docs/proximity-preregistration-20260922.md` and
  `docs/proximity-results-20260922.md` (T8a): the geometry, σ_n, the
  drift-change flag, the event catalogue, 36.1 d median causal lead, 32.8%
  [30.5, 35.3] over 1,483 relocation alerts.
- `docs/proximity-leo-results-20260922.md` (T8b): the look-back requirement and
  the labelled-gap rule.
- `docs/proximity-priorart-20260922.md`: the eight forbidden phrasings and the
  thirteen must-cites, referenced and never copied.

---

## 0. Why T8d exists, in one paragraph, and what would make it fail

T8c built a taxonomy over features that exist only **after** an approach has
transited, arrived, dwelt and departed. An alarm has none of them: it must
speak at the moment a drift-rate change is confirmed, a median of 36 days
before the arrival it is trying to anticipate. T8d therefore builds the
taxonomy a second time over **only what is observable at trigger**, and asks
the alarm's own question — *did an arrival follow?* — rather than T8c's
question of how long a dwell that has already begun will last. Alongside it,
T8d registers the predictor that T8c's variance decomposition actually points
at: the object's **own history**, since 68.8% of the outcome variance is
between objects and 13.0% between classes. **T8d fails, and says so on its
face, if the trigger-time classes do not separate precision (gate B), if the
class predictor does not beat the base rate out of sample (gate C), or if the
per-object predictor does not beat the population baseline at any prior-event
count (gate H).** A failure is a result: it would mean the alarm may speak only
the population-precision sentence T8a already earned, and nothing more.

---

## 1. Framing rules, binding and test-enforced

Inherited verbatim in force from T8a §1, T8b §1 and T8c §1. Restated because a
registration that only points at its predecessors is not binding.

1. **No intent, purpose, motive, mission or actor** is attributed to any
   object, anywhere, in any artifact this study produces. The banned vocabulary
   is the canonical list in `docs/proximity-priorart-20260922.md` under
   "Forbidden phrasings"; its machine-readable form is the `BANNED` tuple of
   `tests/test_alarm_pattern.py::TestPolicyGuards`, which
   `tests/test_trigger_alarm.py` **imports rather than copies**, so the two
   cannot drift apart.
2. **Registry codes are metadata and enter no computation.** No feature, no
   transform, no distance, no cluster assignment, no prediction, no gate and no
   row this study writes reads `country`, `objectId`, `name` or `objectType`,
   with the single inherited exception of T8a §3.2's active/passive class,
   which is derived from `object_type` and is already part of the committed
   catalogue. A test asserts every function named in §12 is free of them.
3. **Every separation is mean-longitude separation — a slot coordinate.** It is
   not a miss distance, not a range, not a conjunction probability. No feature
   name may end in `_km`. (T8a §1.1.)
4. **No delta-V, propellant, mass, or consumables figure** is computed
   anywhere, by any path.
5. **No point forecast is published without its spread**, and no rate is drawn
   from a count below 20 (T8c gate T, T8b gate D).
6. **A labelled gap is never a zero.** A trigger that cannot be resolved, a
   class with no supporting triggers, an object with no usable look-back: each
   produces "not assessable", is counted, and is never rendered as 0%.
7. **Nothing is deployed.** §13.

---

## 2. Inputs, fixed

| Input | Fixed value | Provenance |
|---|---|---|
| element archive | `/home/sdegan/space-orbit-history/orbit-history.sqlite3` | T8a §1 |
| the near-GEO extract | `runtime/proximity-geo/near-geo.npz`, the **cached artifact of T8a's own 293.5 s pass** | its `extract-meta.json` must read `rowsScanned = 217,007,154`, `rowsKept = 11,626,494`, `objectsKept = 1,768`, identical to `docs/proximity-20260922-receipt.json`; **the run asserts all three and records the file's sha256**, and recomputes the extract from the archive if any disagrees |
| σ_n | **6.038533519066339e-4 deg/day**, read from the committed events file's provenance record | T8a §5.4; **never recalibrated here** |
| flag threshold | `max(5 σ_n, 0.010) = 0.010 deg/day` | T8a §5.5, unchanged |
| the event catalogue | `docs/proximity-events-20260922.jsonl`, primary arm, active-class approacher, attribution resolved — **487 events** | T8a; sha256 recorded |
| T8c's feature table | `docs/alarm-pattern-features-20260922.jsonl` — used **only** by M2-L (§8.2), never by M1 | T8c; sha256 recorded |
| seed | **20260922** | the same seed T8a, T8b and T8c used |
| geometry, unwrap, segmentation, flags | **imported** from `tools/proximity_geo.py`, never reimplemented | T8c §2's rule |
| clustering, scaling, bootstrap machinery | **imported** from `tools/alarm_pattern.py` (`transform`, `fold_scaler`, `apply_scaler`, `kmeans`, `silhouette`, `choose_k`, `assign`, `bootstrap_stability`, `bootstrap_skill`, `adjusted_rand`, `eta_squared`) | T8c's verified instrument; T8d adds no second copy of any of them |

---

## 3. The trigger population — fixed here, before it is built

### 3.1 A trigger

A **trigger** is a maximal chain of T8a confirmed drift-change flags on one
approacher in which consecutive flags are separated by **≤ 5.0 days**
(`MERGE_DAYS`, equal to T8a's registered `MAX_GAP_DAYS`). A multi-stage burn is
one trigger, not five.

- `t_first` = the epoch of the **first** flag of the chain.
- `t_trig` = the epoch of the **last** flag of the chain. **Every feature of §4
  is computed from element sets with epoch ≤ `t_trig` and from nothing else.**
- `t_announce` = `t_trig + 5.0 d` (`CONFIRM_DAYS` = `MERGE_DAYS`). This is the
  first instant at which a causal observer knows the chain has ended, and it is
  the instant the alarm could speak. **Every lead time this study reports is
  measured from `t_announce`, not from `t_trig` and not from `t_first`** — so
  the 5-day confirmation latency is charged to the alarm rather than hidden.

### 3.2 Which objects

**Active-class approachers only** (T8a §3.2), the registered headline
population. Occupancy (§4.5) is computed over **all** near-GEO objects of the
extract regardless of class, because a passive object at a stable longitude
occupies a slot exactly as an active one does.

### 3.3 Eligibility — the primary arm

A trigger enters the **primary arm** iff its pre-trigger drift baseline
`ḋ_base` (§4.1) satisfies **`|ḋ_base| ≤ 0.020 deg/day`** — T8a's registered
30-day drift floor `6 X / D = 6 × 0.1° / 30 d`, the drift that would carry an
object six station-keeping boxes in a month. This is a **causal proxy for "the
object was at a slot when it moved"**: it uses only element sets before the
trigger, where T8a's `station_segments` uses a daily grid interpolated from
element sets on both sides and is therefore not available to an alarm.

- The **secondary arm is every trigger**, eligible or not, and is reported in
  full beside the primary.
- **The proxy is audited, not assumed**: the run reports the agreement between
  `|ḋ_base| ≤ 0.020` and T8a's non-causal `station_segments` membership at
  `t_trig` (counts in all four cells and Cohen's κ). Disagreement is a finding
  about the proxy, reported; it revises nothing.

### 3.4 Resolvability, and the labelled gap

A trigger is **resolvable** iff the approacher has at least one near-GEO
element set at epoch **≥ `t_trig` + `H` + `D_PRIMARY`** where **`H` = 180.0 d**
(T8a's registered `T_LOOK_DAYS`) and `D_PRIMARY` = 30.0 d (T8a's registered
dwell). Reason, derived rather than chosen: T8a attributes an initiating flag
to an event only when the flag lies within `T_LOOK_DAYS` of the arrival, and an
arrival is only registered after a 30-day dwell — so 180 + 30 days of
subsequent observation is exactly the window in which a positive outcome could
have been recorded, and no longer.

**An unresolvable trigger is "not assessable".** It is counted, reported, and
excluded from every precision denominator. It is never counted as a negative.

### 3.5 The outcome — two rules, one headline

**O1 (PRIMARY, T8a's own attribution).** A resolvable trigger is **positive**
iff some registered event of the same approacher has `initiatingFlagMs` inside
`[t_first, t_trig]`. This reuses T8a's published causal linkage and invents no
new one. The **arrival time** of a positive trigger is
`D = (arrivalMs − t_announce) / 86400000`. If more than one event matches, the
**earliest arrival** is taken and the count of multiply-matched triggers is
reported.

**O2 (SECONDARY, window).** A resolvable trigger is positive iff some
registered event of the same approacher has `transferStartMs ∈
[t_first − 5 d, t_trig + H]` **and** `arrivalMs ≤ t_trig + H`. Reported in full;
it governs nothing.

**`D ≤ 0` is not a warning.** Positives whose arrival precedes `t_announce` are
counted as `arrivedBeforeAnnounce`, reported, excluded from the arrival-time
distribution, and the headline precision is computed **both** ways — over all
O1 positives, and over O1 positives with `D > 0` only. Both appear in the
results; the `D > 0` figure is the one an alarm may quote.

### 3.6 What this precision is NOT

T8a's 32.8% is `events / relocation-alerts`, where a relocation alert is a
segment-to-segment longitude change of ≥ 2° that contains a flag. **T8d's
denominator is different**: it is the flag chain itself, which is what an alarm
actually sees, and which includes chains that never produced a relocation at
all. **The two numbers are not comparable and the results document must say so
in those words wherever both appear.** T8a's 32.8% remains the published
figure for T8a's estimand.

---

## 4. The trigger-time feature vector — FIXED HERE, before extraction

**Nineteen features in five blocks plus three missingness indicators. Nothing
may be added, removed or redefined after extraction begins.** Every feature is
a function of element sets with epoch ≤ `t_trig` and of nothing else; §12
registers the test that asserts it.

`ḋ` is T8a's `drift_rate_deg_per_day(mean_motion)`; `λ` is T8a's
`mean_longitude_deg`.

### 4.1 Baselines

- `ḋ_base` **[fix]** = the trailing median of `ḋ` over the **10** element sets
  immediately preceding the flag that opened the chain — **exactly the array
  `drift_change_flags` already computes** (`base[k] = median(d[k−10:k])`), read
  at the chain's first flag. NaN if fewer than 10 exist, and a trigger with a
  NaN baseline cannot be eligible under §3.3 and is reported as such.
- `Δḋ_trig` **[fix]** = the flag magnitude `drift_change_flags` returns at
  `t_trig` (the chain's **last** flag): `ḋ(t_trig) − base(t_trig)`.

### 4.2 Initiation block (4)

| # | Name | Definition | log |
|---:|---|---|:--:|
| 1 | `init_drift_change_mag` | `|Δḋ_trig|` deg/day | ✓ |
| 2 | `init_ramp_days` | `t_trig` minus the **latest** epoch in `[t_first − 30 d, t_trig]` at which `|ḋ − ḋ_base| ≤ 0.1 |Δḋ_trig|`; NaN if no such epoch exists in that window | ✓ |
| 3 | `init_stage_count` | the number of flags in the chain | |
| 4 | `init_abruptness` | `|Δḋ_trig| / max(init_ramp_days, 0.5)` deg/day². **[fix]** the 0.5 d floor is T8c's, below the 0.865 d median near-GEO epoch spacing | ✓ |

### 4.3 Kinematic block (3)

| # | Name | Definition | log |
|---:|---|---|:--:|
| 5 | `trig_drift_abs` | `|ḋ|` at `t_trig` | ✓ |
| 6 | `trig_drift_sign` | `sign(ḋ)` at `t_trig`; `+1` eastward, `−1` westward, `0` if exactly zero | |
| 7 | `trig_baseline_drift_abs` | `|ḋ_base|` | ✓ |

### 4.4 Cadence block (4) — strictly before the trigger

| # | Name | Definition | log |
|---:|---|---|:--:|
| 8 | `cad_days_since_prev_trigger` | `(t_trig − t_trig of the object's previous trigger) / 1 d`; NaN for its first | ✓ |
| 9 | `cad_prior_triggers` | the count of that object's earlier triggers | |
| 10 | `cad_prior_events` | the count of that object's registered events with **`loiterEndMs < t_trig`** — an event is not known to have happened until its 30-day dwell has been observed, so `arrivalMs` is **not** the right cut and is not used | |
| 11 | `cad_prior_targets` | distinct `targetNorad` among those | |

### 4.5 Context block (3), and what "occupied" means

An object `o ≠ a` is an **occupied slot at `t`** iff all three hold, each from
element sets with epoch ≤ `t`:

1. its latest near-GEO epoch `t_o ≤ t` satisfies `t − t_o ≤ 5.0 d`
   (T8a `MAX_GAP_DAYS`);
2. its earliest near-GEO epoch is `≤ t − 30 d` (T8a `STATION_MIN_DAYS`);
3. `|ḋ_o(t_o)| ≤ 0.020 deg/day` (T8a `6 X / D`) — it is not going anywhere.

Its **slot longitude** is `wrap180(λ_o(t_o) + ḋ_o(t_o)(t − t_o))`, a
propagation of at most 5 days at at most 0.02 deg/day, i.e. at most 0.1°.

| # | Name | Definition | log |
|---:|---|---|:--:|
| 12 | `ctx_libration_zone` | `in_libration_zone(λ_a(t_trig), 0.1, 30)`, 0/1 | |
| 13 | `ctx_nearest_occupied_deg` | `min over occupied o of |wrap180(λ_o − λ_a(t_trig))|`; NaN if none | ✓ |
| 14 | `ctx_inclination_deg` | inclination at `t_trig`, degrees | ✓ |

### 4.6 Forward-geometry block (5), and its derivation

**This block is the "strictly-causal geometry" the design asks for: which
longitudes the post-burn trajectory would reach, computed from the post-burn
element set alone.** The propagation is derived here, not asserted.

**The equation.** The mean longitude of a near-geosynchronous object obeys, to
first order in the tesseral harmonics and neglecting everything else,

```
  dλ/dt  = ḋ
  dḋ/dt  = − K · sin( 2 (λ − λ_s) )
```

with `ḋ = 360 n − ω_E` (T8a's `drift_rate_deg_per_day`, `n` in rev/day,
`ω_E = 360.9856473 deg/day`) and

```
  K = LAMBDA_DDOT_MAX = 3 ω_E a_T / v_GEO × 86400,
  a_T = 6 J22 (μ / a²) (R_E / a)²,   J22 = 1.8155e-6
```

which is **the constant T8a already derives and uses** (`proximity_geo.py`,
prereg 2.6): `K ≈ 1.70e-3 deg/day²`. Setting `λ_s = 75.1°` places the zeros of
`dḋ/dt` at `75.1°`, `165.1°`, `−104.9°` and `−14.9°`, and the two at which
`d(dḋ/dt)/dλ < 0` — the stable ones — are `75.1°` and `−104.9°`. T8a's
independently registered `STABLE_LONGITUDES_DEG = (75.1, −104.7)` agree to
0.2°, which is the check that the single-harmonic form is the right one.

**Why it must be integrated rather than linearised.** A constant-`ḋ`
propagation over the registered horizon `H = 180 d` omits a term of up to
`½ K H² = 27.5°`, against a drift term of order `|ḋ| H` — for a typical
relocation drift of 0.2 deg/day, 36°. **The triaxial term is not a correction
at this horizon; it is comparable to the signal**, so the block integrates the
two equations with **RK4 at a 1-day step** from `(λ_a(t_trig), ḋ(t_trig))` over
`H = 180 d`. Step-size adequacy is asserted offline against a 0.1-day
integration of the same fixture (§12).

**What the propagation is and is not.** It is the trajectory the object would
follow **if it does nothing further** — no station-keeping, no second burn, no
luni-solar or solar-radiation-pressure correction. That is precisely the
quantity the alarm needs at trigger, and it is **an assumption about the
future, not a fact**; §11 registers gate W, which measures the assumption's
error against the archive rather than trusting it.

A slot is **reached** iff the propagated path passes within `X = 0.1°` (T8a's
registered X) of the slot longitude at some point in `(t_trig, t_trig + H]`.

| # | Name | Definition | log |
|---:|---|---|:--:|
| 15 | `fwd_path_length_deg` | `∫|ḋ| dt` along the propagated path over `H` | ✓ |
| 16 | `fwd_slots_reached` | the number of distinct occupied slots reached | |
| 17 | `fwd_days_to_first_slot` | days from `t_trig` to the first such pass; NaN if none | ✓ |
| 18 | `fwd_first_slot_deg` | path length travelled at that first pass; NaN if none | ✓ |
| 19 | `fwd_plane_compatible_slots` | of the reached slots, those whose inclination at their own `t_o` is within **0.5°** of `ctx_inclination_deg`. **[fix]** 0.5° is the inclination agreement a shared-slot geometry requires at GEO; it is a screen, not a law, and is reported with the distribution of `|Δi|` over all reached slots so a reader can see what a different screen would give | |

### 4.7 Missingness indicators (3, carried as features)

`miss_ramp`, `miss_prev_trigger`, `miss_fwd_slot`, each 1 where features 2, 8
and 17 respectively are NaN. They are features because "this object has never
done this before" is a behavioural fact, not merely an absence.

### 4.8 Explicitly NOT features

`loiterDays`, `closestSeparationDeg`, `leadCausalDays`, `transferDays`,
`arrivalMs`, and every T8c feature whose name begins `transit_`, `arrival_`,
`dwell_` or `departure_`. A test asserts none of these names appears in the
trigger feature table's column list, and §12 registers the stronger test.

### 4.9 Transform and standardisation — T8c's, unchanged

`x → log(x + 1e-9)` on the features marked ✓ above; the rest raw. NaN replaced
by the **training fold's** median after transform, never the full-sample
median. Z-score with the training fold's mean and standard deviation;
zero-variance features dropped in that fold and the drop counted. Euclidean
distance on the standardised vector, no feature weighting. All of this is
`alarm_pattern.transform`, `fold_scaler`, `apply_scaler`, imported.

---

## 5. M1 — the trigger-time taxonomy

**Algorithm.** `alarm_pattern.kmeans` — Lloyd, k-means++, `n_init = 50`,
`max_iter = 300`, `tol = 1e-10`, seed 20260922. Imported, not reimplemented.

**THE CLUSTER-COUNT CRITERION, FIXED BEFORE ANY RUN:**

> Over `k ∈ {2, 3, …, 10}`, choose the `k` maximising the **mean silhouette
> coefficient** (Euclidean, over all **primary-arm resolvable** triggers, on
> the full-sample standardised matrix). Ties — differences below 1e-6 — break
> toward the **smaller** k.

This is T8c's criterion verbatim, so a difference between the two taxonomies is
a difference in the feature space and not in the selection rule. **No elbow is
eyeballed and no k is chosen for interpretability.** The within-cluster
sum-of-squares curve and the silhouette curve are reported and govern nothing.

**Characterisation.** Each class is reported with its size; its centroid in
**original units** beside the population median; the five features whose
standardised centroid deviates most from zero, which are what name it; and its
outcome table of §6.

**Stability.** 200 bootstrap resamples **of approachers**, seed 20260922,
refit and matched to the full-sample partition by greedy maximum-Jaccard
(`alarm_pattern.bootstrap_stability`). Per-class Jaccard is reported and feeds
gate E.

---

## 6. M1 — the three measurements, per trigger class

### 6.1 Precision

For each class `c`: `precision(c) = positives(c) / resolvable(c)` under O1 with
`D > 0`, reported with a **Wilson 95%** interval. Wilson and not Jeffreys
because `scipy` is not installed on `pc`; T8a §4.1 recorded the same
substitution and T8d inherits it rather than pretending otherwise. The
population precision over all primary-arm resolvable triggers is reported in
the same table, and O2's figures beside it.

### 6.2 The arrival-time distribution — the alert's D

For the positives of each class, the distribution of
`D = (arrivalMs − t_announce) / 1 d`: **p5, p25, p50, p75, p95**, the count,
and the number of `D ≤ 0` cases excluded. **A class's D is published as a
distribution with its spread, never as a point** (T8c's finding that the
inter-event interval spans 34–730 days is why).

### 6.3 skill_A — the alarm's actual question

> **`skill_A` = the Brier skill score of the trigger-class positive rate for
> predicting THAT an arrival follows, leave-one-OBJECT-out.**

Fixed protocol, before any number:

- One refit per approacher (`alarm_pattern.fold_models`' shape): the fold's
  scaler, imputation medians and k-means are fit on the triggers of **all other
  objects**; the held-out object's triggers are standardised with the fold's
  constants and assigned to the **nearest fold centroid using their own
  features** — which is what an alarm does, since at trigger time there is no
  "modal class of the object's other events" to borrow.
- `p̂_i` = the positive rate of the assigned class among the **training-fold**
  resolvable triggers. A class empty in the training fold yields no prediction
  and is counted.
- `p̄` = the positive rate of the **training-fold** triggers (the base rate).
- `skill_A = 1 − Σ(y_i − p̂_i)² / Σ(y_i − p̄_i)²`.
- Interval: 2,000 bootstrap resamples **of approachers**, seed 20260922, the
  registered `alarm_pattern.bootstrap_skill` protocol.
- **Secondary, reported, governing nothing:** the area under the ROC curve of
  `p̂` against `y`, and the same Brier skill score over the secondary
  (all-trigger) arm.

### 6.4 The propagator's own error — registered, not optional

For every primary-arm trigger with **no further flag** in `(t_trig, t_trig +
30 d]` and an element set within 5 days of `t_trig + 30 d`: the absolute
difference between the propagated `λ` at +30 d and the observed `λ`. Reported
as p50/p75/p95 and fed to gate W. **This computation reads post-trigger element
sets and is therefore run in a function that produces no feature and is named
in §12's leakage test as a validation-only path.**

---

## 7. M1 — what is reported, in the registered words

The results document must carry, in its first screen: the chosen `k`, the
per-class precision table with Wilson intervals and `n`, the per-class arrival
time distributions, `skill_A` with its interval, and **every gate of §11 with
FIRED or not-fired beside it**.

---

## 8. M2 — the per-object predictor

Three arms. **All three are leave-one-OBJECT-out throughout and bootstrap over
approachers, 2,000 draws, seed 20260922.**

### 8.1 M2-A — arrival, on the trigger population (the out-of-sample arm)

Outcome: the binary O1 `D > 0` label of §3.5, over primary-arm resolvable
triggers of approachers with at least one prior trigger.

| Predictor | Definition, fixed now |
|---|---|
| **baseline** | `p̄`, the training-fold base rate |
| **P1 (per-object)** | `(k + 1) / (n + 2)`, where `n` is the number of that object's **strictly earlier** triggers and `k` how many were positive. **[fix]** the Beta(1,1) posterior mean, chosen because `0/0` and `0/1` are common and an unsmoothed rate would publish 0% and 100% from one observation |
| **P2 (per-class)** | the trigger class's positive rate in the training fold — `p̂` of §6.3 |
| **P3 (hybrid)** | `0.5 (P1 + P2)`, **arithmetic in probability space [fix]** — a log-space average of probabilities is not a probability, and T8c's D2 averaged log **durations**, which is a different object |

Scored by Brier skill score against the base rate, exactly as §6.3.

**This arm is the honest out-of-sample test of T8c's D2 hypothesis**: a
different outcome (arrival vs dwell length) on a different population
(triggers, not arrivals) that did not exist when D2 was computed.

### 8.2 M2-L — loiter duration, the +0.137-comparable arm

On **T8c's committed 487-event feature table**, with T8c's causal taxonomy
(`causalCluster`), leave-one-object-out, skill `= 1 − MAE_model/MAE_pop` in
natural-log space — **T8a's and T8c's protocol exactly**, so the number is
directly comparable to T8a's **+0.137** and T8c's E1a **+0.128**:

| Predictor | Definition |
|---|---|
| **OWN** | the median of `log(loiterDays)` over the object's **other** events (T8a's baseline, reproduced) |
| **CLS** | the median of `log(loiterDays)` over the training fold's members of the modal class of the object's other events (T8c's E1a) |
| **HYB** | `0.5 (OWN + CLS)` in log space — **the rule T8c's D2 used, fixed here before the number** |

**Registered weight curve, reported, governing nothing:** `w ∈ {0, 0.25, 0.5,
0.75, 1}` in `w·CLS + (1−w)·OWN`. The headline is `w = 0.5`.

> **DECLARED, BEFORE THE NUMBER: M2-L IS NOT OUT OF SAMPLE.** D2 was computed
> on this same 487-event table and generated this hypothesis. What T8d adds is
> that the combination rule, the weight, the protocol and the bar were fixed
> before the run, and that the interval is an honest object-level bootstrap.
> **A number near +0.206 here confirms nothing about generalisation**; the
> arm that can is M2-A. The results document must say this wherever M2-L's
> number appears.

### 8.3 M2-D — days to arrival

On positive triggers with `D > 0`, outcome `log D`. OWN = the median of the
object's other positives' `log D`; CLS = the trigger class's median; HYB = the
0.5/0.5 log-space average. Skill against the population median of `log D`, same
protocol.

### 8.4 The prior-event threshold — the number that sets who the alarm may speak about

For M2-A and, separately, M2-L, the skill is **stratified by the number of the
object's strictly prior events** (`n_prior ∈ {1, 2, 3, 4, ≥5}`), each stratum
reported with its `n`, its skill and its bootstrap interval.

> **THE THRESHOLD, DEFINED BEFORE IT IS MEASURED: the smallest `n_prior` at
> which the per-object predictor's bootstrap 95% lower bound exceeds 0, AND at
> which that stratum and every stratum above it contain at least 20
> predictions.** If no stratum satisfies both, **the threshold does not exist**
> and the results document says so in those words — the per-object clause is
> then unsupportable at every prior-event count, which is a result.

---

## 9. Uncertainty

- Proportions: **Wilson 95%** (§6.1), with `k/n` always printed beside the
  interval.
- Skills: **2,000 bootstrap resamples of approachers**, percentile interval,
  seed 20260922, via the imported `alarm_pattern.bootstrap_skill`. Approachers
  and not triggers, because an object's triggers are not independent.
- Distributions: percentiles, never a mean alone; `n` always printed.
- **No p-value is computed and no significance test is run.** Intervals and
  counts, the way T8a, T8b and T8c report.

---

## 10. Compute

CPU. T8c's full pass was 143.8 s on `pc` and T8d reuses its cached extract, so
the registered expectation is **under 600 s wall**. The forward propagation is
`n_triggers × 180` RK4 steps of two scalars — arithmetic, not a model.

> **No GPU is taken.** If a stage is measured above **600 s** the run records
> the measurement and the stage is considered for `gpu-run`; taking the GPU
> would then require a `workspace/infrastructure/gpu-consumers.json` row in the
> same change, per the estate rule. **The registered expectation is that it
> does not earn it**, and the receipt records the measured seconds either way.

---

## 11. Gates — the acceptance criteria, fixed now

| Gate | Fires when | Registered meaning |
|---|---|---|
| **A** | fewer than **200** primary-arm resolvable triggers, **or** fewer than **50** positives | **underpowered.** Every figure is labelled UNDERPOWERED and no precision is quoted as a rate |
| **B** | `max(precision) − min(precision)` over classes with ≥ 20 resolvable triggers is **≤ the width of the widest Wilson interval among those classes** | **the classes do not separate precision.** The "matches pattern P" clause buys nothing over the population figure and stays WITHHELD |
| **C** | `skill_A`'s bootstrap 95% **lower bound ≤ 0** | **the trigger-time taxonomy does not predict arrival.** A third null; the alarm may quote only the population precision |
| **D** | any class has fewer than **20** resolvable triggers | that class is labelled **UNDERPOWERED** and no rate is drawn from it (T8c gate T) |
| **E** | median per-class bootstrap Jaccard **< 0.5** | **not classes**, a partition of this sample (T8c gate Q) |
| **F** | adjusted Rand index between the taxonomy and the `cad_prior_triggers ≥ 1` split **≥ 0.5** | **the taxonomy is re-describing cadence**, not initiation behaviour |
| **G** | M2-L's `HYB` skill **≤ 0.157** | **the hybrid fails the bar T8c's E1a missed.** D2 was a fluctuation of the diagnostic, not a predictor |
| **H** | M2-A's P1 lower bound ≤ 0 in **every** prior-event stratum | **the per-object claim is unsupportable at any prior-event count.** The alarm may speak about no object individually |
| **W** | the median 30-day propagation error of §6.4 **> 2.0°** | **the forward-geometry block is unfit.** Features 15–19 are labelled unfit, the taxonomy is refit without them, and both are reported |
| **L** | the leakage test of §12 fails | **the study is void.** Not a caveat — the run aborts and nothing is reported |

**None of A–H, W firing invalidates T8d.** Every one of them is a result about
what the alarm may say. **What is forbidden is discovering a gate has fired and
revising the gate.**

---

## 12. The leakage audit — registered as a test, not as an intention

T8d's entire claim is that its features exist at trigger time. That claim is
asserted mechanically, three ways, in `tests/test_trigger_alarm.py`:

1. **The truncation test.** For a synthetic object with a known flag chain, the
   trigger feature vector is extracted **twice** — once from the full series,
   once from the series truncated at `t_trig` — and the two vectors must be
   **bit-identical**, including the occupancy and forward-geometry blocks.
2. **The mutation test.** The same series with **every element set after
   `t_trig` replaced by garbage** (drift multiplied by 17, longitude offset by
   123°) must give the **bit-identical** vector. A feature that reads the
   future cannot survive this.
3. **The name test.** No column of the trigger feature table may match
   `transit_`, `arrival_`, `dwell_`, `departure_`, `lead_`, `loiter`,
   `closestSeparation`, `_km`, or any banned phrase of §1.1.

**The validation-only path.** §6.4's propagator check reads post-trigger
elements by design. It lives in a function whose name begins `validate_`, it is
called by no feature path, and a test asserts that **no function reachable from
the feature extractor calls any `validate_*`**, and that the feature extractor
receives a series already truncated at `t_trig`.

A registry-code guard in the shape of T8c's is also registered: `country`,
`registry`, `owner`, `nation` appear in the source of no function named in the
feature, transform, distance, assignment or prediction paths.

---

## 13. What the alarm-lane design document may and may not assume

`docs/alarm-lane-design-20260922.md` will be **revised in place after** these
numbers, dated, and bound by all of the following:

- It remains a **design**. Nothing is deployed, nothing is scheduled, nothing
  is written to `src/`, `data/`, `public/` or any site surface, no alert is
  emitted anywhere, and no timer is installed.
- Its §6 vocabulary ladder may move **"matches pattern P"** from WITHHELD only
  if gates B **and** C both fail to fire, and only for classes that gate D does
  not label UNDERPOWERED. **If either fires, the clause stays WITHHELD and the
  design says why.**
- Its §1 sentence — *the pattern may modify a rate; it may not replace an
  object's own history* — may become a **per-object** sentence only if M2's
  §8.4 threshold exists, and then only for objects at or above it.
- Every precision it quotes carries its `n`, its Wilson interval, and the
  statement of §3.6 that T8d's denominator is not T8a's.
- The framing rules of §1 are unchanged, the registry-code decision stays
  reserved, and §10's operator decisions stay reserved and untaken.

---

## 14. Declared blind spots, before they bite

1. **The trigger population is not the alert population an operator would
   see.** It is every confirmed flag chain on an active near-GEO object over
   1959–2026. A deployed lane would watch a subset, and its precision would
   differ.
2. **O1 inherits T8a's attribution rule**, which takes the *last* flag within
   180 days before an arrival. A trigger that genuinely initiated a transfer
   more than 180 days before its arrival is scored **negative** here. T8a §8
   already records that its 180-day look-back censored the lead-time
   distribution; T8d inherits the censoring and cannot repair it.
3. **The forward propagation assumes no further manoeuvre.** For an object that
   is about to station-keep, it is wrong by construction. Gate W measures the
   error but cannot remove the assumption.
4. **The occupancy set is a causal proxy for stationing** and will disagree
   with T8a's segmentation. §3.3 reports the disagreement; nothing repairs it.
5. **A trigger is a detector event.** T8c §5 measured that most of the outcome
   information in its classes was the burn-visible / burn-invisible split. T8d
   removes that split by construction — **every** trigger has a visible burn —
   which is the point, but it also means T8d cannot speak at all about the 33%
   of T8a's events with no confirmable initiating change. **Absence of a
   trigger is not absence of an approach.**
6. **M2-L is not out of sample.** §8.2, declared there and repeated here.
7. **487 events and an unknown number of triggers is a small sample for a
   22-dimensional space.** Gate E is the only defence and it is weak.
8. **No LEO arm.** T8b's plane-noise floor is unrepaired; a LEO trigger
   taxonomy is a separate registration and is not attempted.
9. **`month_rollup` is 15% stale** (T8a §1). T8d sizes nothing from it.

---

## 15. What is committed with this document

**Nothing.** `tools/trigger_alarm.py`, `tests/test_trigger_alarm.py`, the
trigger table, the receipt, `docs/trigger-alarm-results-20260922.md` and the
revision to `docs/alarm-lane-design-20260922.md` all follow in later commits,
and the ordering in `git log` is the evidence.
