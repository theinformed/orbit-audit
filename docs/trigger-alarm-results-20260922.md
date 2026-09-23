# T8d results: the trigger-time predictor — the alarm's real denominator, and the one clause it may now speak

> **Registration:** `docs/trigger-alarm-preregistration-20260922.md`, sha256
> `53a4a6f7cc28000d4a110142bf6cde7c0e7c516371ecdd6590dc8b96cd2fc8d3`,
> committed **alone** as `154c53f` before any measurement code existed.
>
> **Design only. Nothing is deployed, nothing is scheduled, nothing is on any
> site surface, no alert has been emitted, and nothing here is written to
> `src/`, `data/` or `public/`.** Every operator decision of
> `docs/alarm-lane-design-20260922.md` §10 remains reserved and untaken.

---

## 0. The headline, before anything else

> **An alarm that fires on a confirmed drift-rate change at GEO would have
> fired 97,784 times over 1959–2026 and been right 101 times: 0.103%
> precision, Wilson 95% [0.085%, 0.125%].**
>
> **The trigger-time taxonomy is real, it is reproducible, and it separates
> those 97,784 alerts into a class of 96,962 at 0.075% [0.060%, 0.095%] and a
> class of 822 at 3.41% [2.37%, 4.88%] — a 45-fold lift that carries 28 of
> the 101 true alerts in 0.84% of the volume, with a median 22.1 days of
> warning.**
>
> **So the lane's supportable sentence is per-CLASS, not per-OBJECT.
> `gate H FIRED`: the per-object predictor registered in §8.1 is worse than
> the population base rate at every prior-event count, and the prior-event
> threshold that would say who the alarm can speak about individually
> DOES NOT EXIST.**
>
> **And one design claim is corrected rather than confirmed. The alarm-lane
> design's §4.3 says the trigger-time precision floor "is already known" and
> is T8a's 32.8%. It is not. T8a's 32.8% is measured over 1,483 relocation
> alerts, each of which required a ≥ 2° relocation to have ALREADY HAPPENED.
> At trigger time that population does not exist. The measured trigger-time
> figure is 0.103%, and the best reproducible class reaches 3.41% — an order
> of magnitude below what the design assumed it could quote.**

| Gate | Registered meaning | Verdict |
|---|---|:--:|
| **Gate A** | fewer than 200 resolvable triggers or fewer than 50 positives → underpowered | **not fired** (97,784 and 101) |
| **Gate B** | the classes do not separate precision | **not fired** (spread 0.0333 > widest Wilson width 0.0251) |
| **Gate C** | `skill_A` lower bound ≤ 0 → the taxonomy does not predict arrival | **not fired** (+0.0082 [+0.0023, +0.0141]) |
| **Gate D** | any class below 20 resolvable triggers | **not fired** (96,962 and 822) |
| **Gate E** | median per-class bootstrap Jaccard < 0.5 → not classes | **not fired** (0.633 and 0.620) |
| **Gate F** | ARI against the cadence split ≥ 0.5 → re-describing cadence | **not fired** (0.015) |
| **Gate G** | M2-L's hybrid ≤ 0.157 → T8c's D2 was a fluctuation | **not fired** (+0.2012 [+0.1212, +0.2675]) |
| **Gate H** | the per-object predictor's lower bound ≤ 0 in EVERY stratum | **FIRED** |
| **Gate W** | median 30-day propagation error > 2.0° → forward geometry unfit | **not fired** (0.408°) |
| **Gate L** | the leakage audit fails → the study is void | **not fired** — `tests/test_trigger_alarm.py`, 100 tests, OK |

---

## 1. What ran, where, and for how long

| | |
|---|---|
| host | `pc` (bigmem-PC), CPU, one core |
| archive | `/home/sdegan/space-orbit-history/orbit-history.sqlite3` |
| extract | **T8a's own cached 293.5 s pass**, reused after asserting its three published numbers: `rowsScanned = 217,007,154`, `rowsKept = 11,626,494`, `objectsKept = 1,768`. sha256 `ff19d32e…` |
| σ_n | **6.038533519066339e-4 deg/day**, read from the committed events file's provenance record — recalibrated nowhere |
| element histories | 1,652 built (of 1,768 kept; 116 objects carry fewer than two near-GEO element sets), **1,308 active-class** |
| stages | element load 5.3 s · triggers 4.5 s · **features 1,052.3 s** · audits 52.8 s · k sweep 1,014.0 s · folds 617.7 s |
| total | **wall 3,307.7 s, CPU 3,296.6 s** |

**The measurement was run twice, end to end, and every statistic reproduced
bit-identically** — the two receipts differ only in wall-clock fields and the
tool's own hash. The trigger table is cached between runs and the cache is
keyed on the sha256 of the code that produced it, so an edited extractor
cannot silently be analysed against a stale table and an edited analysis
cannot silently rebuild one.

### 1.1 The registered compute expectation was exceeded, and the GPU was not taken

§10 of the registration expected under 600 s and said that a stage measured
above it would be **considered** for `gpu-run`. Wall came to 3,307.7 s. The
consideration, stated rather than skipped:

- The largest single cost is **1,052 s of per-trigger arithmetic** — an RK4
  integration and a band intersection per trigger, in a Python loop over
  226,422 triggers. It is embarrassingly parallel across CPU cores and is not
  a BLAS problem; a GPU buys nothing a second core would not.
- The second is **1,014 s of k-means over a 97,784 × 22 matrix** for the
  nine-k sweep, which a GPU would genuinely accelerate.
- **The GPU was not taken.** 56 minutes of one core, once, against a GPU whose
  time on this machine is committed elsewhere, does not earn it; and taking it
  would owe a `gpu-consumers.json` row in the same change. **No such row is
  owed, because no GPU was used.** The measurement is recorded here either way.

---

## 2. TWO DECLARED COMPUTE DEVIATIONS, and one that was not needed

The registration was written expecting a trigger population of the order of
T8a's 1,483 alerts. The measured population is **226,422**. Two steps of the
registered procedure do not scale to that, and both deviations are named here,
on the face of the document, with their arithmetic.

**D1a — the silhouette is evaluated on a subsample.** `alarm_pattern.silhouette`
materialises two n × n matrices; at n = 97,784 that is 2 × 78 GB. The mean
silhouette is a sample statistic, so **the k-means is fit on every row, as
registered, and only the silhouette is evaluated** on 6,000 rows drawn with
the registered seed. **Three independent draws are reported for every k** so a
reader can see whether the chosen k depends on the draw. It does not: the
spread across draws is at most 0.013 at any k, against a gap of 0.53 between
the winner and the runner-up.

**D1b — leave-one-object-out becomes grouped 20-fold over approachers.**
Leave-one-object-out needs one k-means refit per approacher. The measured cost
of one refit at this size is ~31 s (617.7 s for 20 folds); 1,217 approachers
is **10.4 hours per arm**, and there are two arms. It is replaced by **object-disjoint 20-fold
cross-validation**: the approachers are partitioned with the registered seed,
each fold's scaler, imputation medians and k-means are fit on the other folds'
rows, and the held-out rows are assigned by their own features. **No object
appears in both halves of any fold — a test asserts it.** Each fold trains on
95% of approachers where leave-one-out trains on 99.9%, so the estimate is
**strictly the more conservative of the two**.

**Where leave-one-object-out is affordable it is used unchanged.** M2-L, on
T8c's 487 events over 112 approachers, is leave-one-object-out exactly as
registered, and so is its prior-event stratification.

**No deviation was needed for anything else**: the 200-draw bootstrap
stability, the 2,000-draw object-level bootstrap intervals, the Wilson
intervals, the outcome rules and the full-population precision tables are all
computed on every row, as registered.

---

## 3. The trigger population — the single biggest thing T8d found

### 3.1 The counts

| population | count |
|---|---:|
| flag chains (prereg 3.1), active-class approachers | **226,422** |
| approachers carrying at least one | 1,291 |
| **eligible** — the causal "was at a slot" proxy, \|ḋ_base\| ≤ 0.020 deg/day | 98,720 |
| **resolvable** — observed through t_trig + 180 d + 30 d | 224,780 |
| **not assessable**, counted and never scored as negatives | **1,642** |
| **PRIMARY ARM** (eligible **and** resolvable) | **97,784** over **1,217 approachers** |

**226,422 flag chains, not 1,483 alerts.** That is a **mean of 175 and a
median of 125 chains per triggering object** over its catalogued life, and the
volume is concentrated where the catalogue is dense:

| decade | 1960s | 1970s | 1980s | 1990s | 2000s | 2010s | 2020s (to 2026) |
|---|---:|---:|---:|---:|---:|---:|---:|
| triggers | 15 | 1,121 | 14,227 | 37,327 | 56,019 | **71,661** | 46,052 |

**about 7,200 confirmed drift changes a year across the GEO belt in the
2010s.** At GEO that is what east-west station-keeping looks like through a
detector whose floor is
0.010 deg/day: T8a's own threshold corresponds to a semi-major-axis change of
about 0.78 km (`0.010 / |DRIFT_PER_KM|`, and `DRIFT_PER_KM =
−1.5 ω_E / a_GEO = −0.01284 deg/day/km`), which a routine 0.05 m/s east-west
correction exceeds. **The confirmed drift-rate change is not a rare event at
GEO. It is the normal operation of a stationed satellite.**

### 3.2 Precision, both outcome rules, both arms

All intervals **Wilson 95%**; `scipy` is absent on `pc` and T8a §4.1 recorded
the same substitution for its registered Jeffreys interval.

| population | n | O1 positives, arrival **after** the announce | precision | Wilson 95% |
|---|---:|---:|---:|---|
| **PRIMARY ARM** | 97,784 | **101** | **0.1033%** | **[0.0850%, 0.1255%]** |
| primary arm, O1 all matches | 97,784 | 138 | 0.1411% | [0.1195%, 0.1667%] |
| primary arm, **O2** (window rule) | 97,784 | 655 | 0.670% | [0.621%, 0.723%] |
| all resolvable triggers | 224,780 | 156 | 0.0694% | [0.0593%, 0.0812%] |
| all resolvable, O1 all matches | 224,780 | 216 | 0.0961% | [0.0841%, 0.1098%] |
| all resolvable, **O2** | 224,780 | 904 | 0.402% | [0.377%, 0.429%] |

**37 of the 138 primary-arm O1 matches arrived BEFORE the announce time** and
are excluded from the headline, counted here rather than hidden. An alarm that
speaks after the arrival has warned nobody.

### 3.3 This denominator is NOT T8a's, and the two numbers are not comparable

Registered in advance (prereg §3.6) and repeated because it is the easiest
mistake a reader could make:

- **T8a's 32.8% [30.5%, 35.3%]** is `487 events / 1,483 relocation alerts`,
  where a relocation alert is a **segment-to-segment longitude change of
  ≥ 2° that contains a flag**. The ≥ 2° move is a fact about what the object
  *subsequently did*.
- **T8d's 0.103%** is `101 arrivals / 97,784 flag chains`. The flag chain is
  what an alarm sees at the moment it must speak.
- **Neither number is wrong and neither replaces the other.** T8a's remains the
  published figure for T8a's estimand. What T8d establishes is that **the
  trigger-time figure is three orders of magnitude smaller**, and that the
  design document's §4.3 was mistaken to treat T8a's as the floor an alert
  could quote.

### 3.4 The alert's D — the arrival-time distribution

Measured from `t_announce`, so the five-day confirmation latency is charged to
the alarm rather than hidden.

| population | n | p5 | p25 | **p50** | p75 | p95 |
|---|---:|---:|---:|---:|---:|---:|
| primary arm | 101 | 1.5 d | 8.0 d | **25.7 d** | 58.8 d | 157.7 d |
| all resolvable | 156 | 1.8 d | 11.0 d | **32.6 d** | 76.5 d | 157.7 d |
| **class 1** (§5.3) | 28 | 0.7 d | 7.0 d | **22.1 d** | 47.5 d | 90.0 d |
| class 0 | 73 | 2.2 d | 9.4 d | 29.4 d | 62.9 d | 158.8 d |

T8a's median **causal lead** is 36.1 days from the initiating flag. T8d's
32.6 days over all resolvable triggers is the same quantity minus the 5-day
confirmation wait and measured on a wider population; they are consistent. The
**p95 of 157.7 days sits just under the 180-day horizon**, which is the
registered right-censoring showing itself: T8a attributes an initiating flag
only within `T_LOOK_DAYS` of an arrival, so no longer lead can appear here by
construction. Blind spot §14.2, as declared.

### 3.5 The eligibility proxy, audited against T8a's own segmentation

The primary arm's "the object was at a slot when it moved" test is a **causal
proxy**: `|ḋ_base| ≤ 0.020 deg/day`. T8a's `station_segments` is not available
to an alarm, because it interpolates a daily grid from element sets on **both**
sides of the trigger.

| | in a T8a station segment | not |
|---|---:|---:|
| **proxy says stationed** | 78,135 | 20,585 |
| **proxy says not** | 11,424 | 116,278 |

**Cohen's κ = 0.709.** Substantial agreement, and 32,009 disagreements. This is
reported, and it repairs nothing: the proxy is what an alarm can compute and
the segment is not.

---

## 4. The forward propagation, and its own measured error

The registration derived the propagation rather than asserting it:
`dλ/dt = ḋ`, `dḋ/dt = −K sin(2(λ − 75.1°))` with `K = 1.70e-3 deg/day²` from
**T8a's own tesseral constants**, integrated by RK4 at a one-day step over the
180-day horizon. The single-harmonic form places its stable points at 75.1°
and −104.9°; T8a's independently registered `STABLE_LONGITUDES_DEG` are
(75.1°, −104.7°). Agreement to 0.2° is the check that the form is right, and
`tests/test_trigger_alarm.py::TestResonanceDerivation` asserts it.

**Gate W measured the assumption instead of trusting it.** Over the 49,318
primary-arm triggers with no further flag inside 30 days and an element set at
the far end:

| | median | p75 | p95 |
|---|---:|---:|---:|
| \|λ_predicted − λ_observed\| at +30 d | **0.408°** | 0.898° | 2.080° |

**Gate W does not fire** (bar 2.0° on the median). The registration's reason
for integrating rather than linearising is also confirmed as arithmetic: a
constant-drift propagation omits a term of up to `½ K H² = 27.5°` at
H = 180 d, which is not a correction but a quantity comparable to the signal.

**What the propagation is not:** it assumes the object does nothing further —
no station-keeping, no second burn, no luni-solar or solar-radiation-pressure
correction. That is the point (it is what the trajectory *would* reach), and
it remains an assumption about the future, not a fact. Its error is measured
above; it is not removed.

---

## 5. M1 — the trigger-time taxonomy

### 5.1 The cluster count, by the registered criterion and nothing else

Maximum mean silhouette over k ∈ {2 … 10}, ties toward the smaller k.

| k | silhouette (draw 1, **governing**) | draw 2 | draw 3 | sizes |
|---:|---:|---:|---:|---|
| **2** | **+0.7565** | +0.7519 | +0.7543 | 96,962 / 822 |
| 3 | +0.1949 | +0.1820 | +0.1900 | 69,741 / 27,235 / 808 |
| 4 | +0.1664 | +0.1546 | +0.1626 | 66,612 / 28,251 / 807 / 2,114 |
| 5 | +0.1952 | +0.1890 | +0.1886 | — |
| 6 | +0.1901 | +0.1954 | +0.1914 | — |
| 7 | +0.2117 | +0.2048 | +0.2059 | — |
| 8 | +0.2138 | +0.2108 | +0.2137 | — |
| 9 | +0.2213 | +0.2208 | +0.2216 | — |
| 10 | +0.2251 | +0.2247 | +0.2250 | — |

**k = 2.** The criterion is not close: 0.757 against 0.225 for the best
alternative, and the three subsamples agree to within 0.005 at k = 2. **No
elbow was eyeballed and no k was chosen for interpretability** — this is the k
the registered rule returned, and the very high silhouette is itself the
finding: the trigger-time feature space has one dominant split and a weak
continuum underneath it, exactly the shape T8c §7.5 predicted the programme
should expect.

### 5.2 Stability

200 bootstrap resamples **of approachers**, seed 20260922, matched to the
full-sample partition by greedy maximum Jaccard.

| class | size | bootstrap Jaccard |
|---|---:|---:|
| 0 | 96,962 | **0.633** |
| 1 | 822 | **0.620** |

**Gate E does not fire.** Both classes recover about 62–63% of their members
under resampling. That is the weakest kind of pass — it is the same bar T8c's
six-class taxonomy met at a median of 0.501 — and it is a pass for **both**
classes rather than for three of six.

### 5.3 The two classes, and what names them

Both classes are named by the same five features, which is what a two-class
partition of a single dominant axis looks like:

> `trig_drift_abs`, `fwd_path_length_deg`, `fwd_slots_reached`,
> `init_drift_change_mag`, `fwd_plane_compatible_slots`

— the post-burn drift rate, how far the propagated trajectory travels in 180
days, how many occupied slots it would pass, the size of the drift change, and
how many of those slots share the object's plane. **Class 1 is "a large drift
change that leaves the object crossing many occupied longitudes"; class 0 is
everything else.** Neither name is a behaviour, a purpose or a mission: they
are positions in a feature space this study fixed before it looked
(blind spot §14 and T8c §10.6).

### 5.4 Per-class precision — the table the design said must exist

| class | n | positives | **precision** | **Wilson 95%** | underpowered? |
|---|---:|---:|---:|---|:--:|
| **0** | 96,962 | 73 | **0.0753%** | **[0.0599%, 0.0947%]** | no |
| **1** | **822** | **28** | **3.406%** | **[2.367%, 4.879%]** | no |
| whole primary arm | 97,784 | 101 | 0.1033% | [0.0850%, 0.1255%] | — |

**Gate B does not fire**: the spread between the classes, 0.0333, exceeds the
widest Wilson interval width among them, 0.0251.

**And the gate's weakness must be said out loud rather than left implicit.**
Gate B is a *statistical* separation test, and at n ≈ 100,000 almost any
difference clears it. What matters operationally is the magnitude, and the
magnitude is genuinely large: **a 45-fold lift, 3.41% against 0.075%**, with
class 1 carrying **28 of the 101 true alerts (27.7% recall) in 0.84% of the
alert volume**. Over the whole 1959–2026 archive class 1 fires **822 times**, at a median
**22.1 days** of warning. Averaged over the archive that is about twelve
alerts a year across the entire GEO belt; because the trigger volume is
concentrated after 1990 (§3.1), **the rate in a recent decade is several times
that** — pro-rated by trigger volume, of the order of 25–30 a year in the
2010s. The pro-rating is arithmetic on §3.1's table, not a measurement, and is
labelled as such.

**3.41% is still about 29 false alerts for every true one.** It is an order of
magnitude below T8a's published 32.8%, and §3.3 explains why that comparison
is not available to an alarm.

### 5.5 skill_A — the alarm's actual question

> **`skill_A` = +0.0082, bootstrap 95% over approachers [+0.0023, +0.0141];
> n = 97,784 predictions over 1,217 approachers, 101 positives; AUC 0.546.**
>
> **Gate C does not fire.** The interval excludes zero.

Brier skill score of the trigger class's positive rate against the fold's base
rate, object-disjoint throughout, every held-out trigger assigned by its own
features. It is **positive, reproducible and tiny**: at a base rate of 0.1%,
a Brier score is dominated by the 99.9% of rows that are negative, and 0.8% of
that error is what a two-class partition removes. **The honest reading is that
the class changes the rate a great deal on a very small slice and barely at
all elsewhere, which is exactly what §5.4's table shows directly.** The
per-class precision table, not `skill_A`, is what an alert should quote.

**And one number in the secondary arm is worth more than the headline.** The
same measurement with the forward-geometry block removed scores a *lower*
Brier skill, **+0.0034 [+0.0019, +0.0046]**, but a far *higher* **AUC: 0.751
against 0.546**. The two disagree because they ask different questions — the
Brier score rewards calibrated probability on the whole population, the AUC
rewards ranking. **Without the forward block the taxonomy ranks triggers much
better and calibrates worse; with it, the reverse.** Neither is a registered
estimand beyond `skill_A`, and no verdict here rests on the AUC; it is
reported because concealing it would flatter the forward block.

### 5.6 The partition is not re-describing cadence

**Gate F does not fire.** Adjusted Rand index between the taxonomy and the
"has this object triggered before" split: **0.015**. Between-class η² of the
arrival indicator: 0.009.

### 5.7 Feature availability

No feature is missing for more than 9.5% of triggers. The worst are
`init_ramp_days` and `init_abruptness` at **9.44%**; then
`fwd_days_to_first_slot` and `fwd_first_slot_deg` at 2.16%,
`cad_days_since_prev_trigger` at 0.61% and `ctx_nearest_occupied_deg` at
0.04%. The other sixteen are complete. **The rich vector is not mostly
imputation** — the failure mode T8c's gate U existed to catch did not occur
here.

---

## 6. M2 — the per-object predictor

### 6.1 M2-A — arrival, on the trigger population. THE OUT-OF-SAMPLE ARM

This is the arm that can test T8c's post-registration D2 hypothesis honestly:
a **different outcome** (did an arrival follow) on a **different population**
(flag chains, not arrivals) that did not exist when D2 was computed.

Brier skill score against the fold's base rate, object-disjoint, 2,000
bootstrap resamples of approachers. `n = 96,567` predictions, 84 positives,
over triggers whose object had at least one earlier trigger.

| predictor | definition | **Brier skill** | 95% CI | AUC |
|---|---|---:|---|---:|
| **P1 per-object** | `(k+1)/(n+2)` over the object's earlier triggers | **−5.419** | [−7.030, −4.348] | **0.674** |
| **P2 per-class** | the trigger class's training-fold rate | **+0.0058** | [−0.0011, +0.0120] | 0.544 |
| **P3 hybrid** | `0.5 (P1 + P2)` | **−1.324** | [−1.735, −1.051] | **0.715** |

**Read this carefully, because the two columns say opposite things and both
are true.**

1. **The registered per-object predictor is catastrophically mis-calibrated,
   and the registration is where the fault lies.** §8.1 fixed a Beta(1,1)
   smoother, `(k+1)/(n+2)`, in advance — chosen because `0/0` and `0/1` are
   common and an unsmoothed rate would publish 0% and 100% from one
   observation. Against a base rate of **0.1%**, that prior predicts about 14%
   for an object with five clean prior triggers: a hundredfold
   over-prediction. Its Brier skill of −5.4 is the price. **The registered
   [fix] was wrong for this base rate, it was fixed before the number existed,
   and it is not being revised now.**
2. **As a RANKER the object's own history clearly beats the class** — AUC
   0.674 against 0.544 — and **the hybrid beats both, at 0.715.** That is
   T8c's D2 complement finding reappearing on a genuinely out-of-sample
   outcome: the class knows something the object's history does not, and vice
   versa. **It survives as an ordering and it does not survive as a
   probability.**
3. The `causal` variant, which additionally requires an earlier trigger to
   have fully *resolved* before the current one fires — what an alarm would
   actually know — is weaker throughout: P1 −7.830 (AUC 0.570), P2 +0.0030,
   P3 −1.959 (AUC 0.622), n = 92,324 with 60 positives. **The stricter and
   more honest version of the object's history is the worse predictor**,
   because 210 days of resolution lag removes most of what the object recently
   did.

### 6.2 The prior-event threshold — GATE H FIRED

> **The threshold DOES NOT EXIST.** There is no number of prior events at
> which the registered per-object predictor beats the population baseline.

| prior triggers | n | positives | P1 Brier skill | 95% CI |
|---:|---:|---:|---:|---|
| 1 | 1,210 | 10 | −13.37 | [−34.17, −7.94] |
| 2 | 1,199 | 7 | −10.95 | [−39.37, −6.04] |
| 3 | 1,189 | 3 | −16.84 | [−40750, −6.99] |
| 4 | 1,169 | 2 | −17.35 | [−28648, −6.68] |
| ≥ 5 | 91,800 | 62 | −2.58 | [−3.52, −1.96] |

Every stratum's **upper** bound is below zero. The registered rule — *the
smallest `n_prior` at which the lower bound exceeds 0 and that stratum and
every one above it carry at least 20 predictions* — is satisfied by no
stratum. **Gate H fires, and its registered meaning stands: the alarm may
speak about no object individually.**

The same question asked of the loiter arm agrees, for the opposite reason —
there the intervals are too wide rather than the point estimate too low:

| prior events (M2-L, loiter) | n | OWN skill | 95% CI |
|---:|---:|---:|---|
| 1 | 112 | +0.140 | [−0.050, +0.310] |
| 2 | 53 | +0.193 | [−0.074, +0.407] |
| 3 | 30 | +0.154 | [−0.204, +0.417] |
| 4 | 19 | +0.047 | [−0.418, +0.328] |
| ≥ 5 | 49 | +0.168 | [−0.097, +0.335] |

Every interval contains zero. **Neither outcome supports a per-object clause
at any prior-event count.** That is the answer to the task's question "how many
prior events does an object need before the per-object claim beats the
population baseline", and the answer is **more than this archive contains**.

### 6.3 M2-L — loiter duration, the +0.137-comparable arm

**Leave-one-object-out exactly as registered**, on T8c's committed 487-event
table, T8c's causal taxonomy (k = 5), skill = `1 − MAE_model/MAE_population`
in natural-log space. 375 predictions over 112 approachers — the identical
protocol and the identical predictions T8a's +0.137 and T8c's +0.128 were
measured on.

| predictor | skill | 95% CI |
|---|---:|---|
| **OWN** — the object's own other events (T8a's baseline) | **+0.1366** | [+0.0098, +0.2403] |
| **CLS** — the modal causal class of the object's other events | +0.1166 | [+0.0519, +0.1756] |
| **HYB** — `0.5 (OWN + CLS)` in log space, **the registered rule** | **+0.2012** | **[+0.1212, +0.2675]** |

**Gate G does not fire**: +0.2012 clears the registered 0.157 bar, which is
the same bar T8c's gate P set and E1a missed. OWN reproduces T8a's published
+0.137 to four decimal places, so the comparison is like-for-like.

With T8c's **full** 37-feature taxonomy instead — D2's own setup, reported
beside the registered headline — HYB is **+0.2060 [+0.1292, +0.2712]**, which
reproduces T8c's post-registration D2 of **+0.206 [+0.127, +0.272]** exactly.

The registered weight curve, reported and governing nothing:

| w (weight on CLS) | 0 | 0.25 | **0.5** | 0.75 | 1 |
|---|---:|---:|---:|---:|---:|
| skill | +0.1366 | +0.1901 | **+0.2012** | +0.1829 | +0.1166 |

> **DECLARED IN THE REGISTRATION, BEFORE THE NUMBER, AND REPEATED HERE:
> M2-L IS NOT OUT OF SAMPLE.** D2 was computed on this same 487-event table
> and generated this hypothesis. What T8d adds is that the rule, the weight,
> the protocol and the bar were fixed before the run and the interval is an
> honest object-level bootstrap. **A number near +0.206 here confirms nothing
> about generalisation**, and the curve peaking at the registered w = 0.5 is
> not independent evidence either, because 0.5 is the weight D2 used. The arm
> that could generalise is M2-A, and §6.1 is what it said.

### 6.4 M2-D — days to arrival. UNDERPOWERED

Only **16 predictions over 7 approachers** exist: an object must have two
positive triggers inside the same fold's held-out set, and with 101 positives
spread over 1,217 approachers almost none do.

| predictor | n | skill | 95% CI |
|---|---:|---:|---|
| OWN | 16 | −0.127 | [−0.633, +0.353] |
| CLS | 16 | −0.138 | [−0.270, −0.070] |
| HYB | 16 | +0.020 | [−0.274, +0.292] |

**Labelled UNDERPOWERED under prereg §1.5 and no rate is drawn from it.** The
one interval that excludes zero, CLS at −0.138, says the class median is
*worse* than the population median for predicting how long the wait will be —
on sixteen predictions, which is not enough to conclude anything.

---

## 7. Post-registration diagnostics

**Labelled as such throughout, in the manner of T8a §7.4, T8b §7.3 and
T8c §6.** Added at measurement time, they change no registered verdict, no
gate reads them, and they are not registered estimands.

### 7.1 What a single ordered feature buys

Precision by decile of the primary arm, 9,774–9,784 triggers per decile.

| decile of `trig_drift_abs` (deg/day) | n | positives | precision | Wilson 95% |
|---|---:|---:|---:|---|
| 1 – 9 (≤ 0.0320) | 88,005 | 27 | 0.031% | — |
| **10 (0.0320 – 15.51)** | **9,779** | **74** | **0.757%** | **[0.603%, 0.949%]** |

| decile of `init_drift_change_mag` | n | positives | precision | Wilson 95% |
|---|---:|---:|---:|---|
| 1 – 9 (≤ 0.0280) | 88,004 | 24 | 0.027% | — |
| **10 (0.0280 – 15.38)** | **9,780** | **77** | **0.787%** | **[0.630%, 0.983%]** |

| decile of `fwd_slots_reached` | n | positives | precision |
|---|---:|---:|---:|
| 1 – 9 (≤ 44) | 87,427 | 28 | 0.032% |
| **10 (44 – 536)** | **10,357** | **73** | **0.705%** |

Three different features cut the same way, which is what §5.3 said: they are
one axis. **A single ordered feature reaches 0.76–0.79% precision at ~75%
recall; the two-class taxonomy reaches 3.41% at 27.7% recall.** The taxonomy
is buying a much sharper, much smaller slice, not a different kind of
information.

`ctx_nearest_occupied_deg` is nearly flat by comparison (0.031% in the top
decile, 0.225% at its best), and `fwd_days_to_first_slot` concentrates in its
lowest bin (85 of 101 positives among the 28,702 triggers whose propagated
path meets an occupied slot within 3.07 days, 0.296%).

### 7.2 The causal analogue of T8a's relocation requirement

T8a's alert required a ≥ 2° relocation to have happened. The causal version of
that requirement, available at trigger, is that the post-burn drift could
cover 2° inside the registered horizon:
`|ḋ| ≥ X_FAR / H = 2.0 / 180.0 = 0.01111 deg/day`, derived from two constants
T8a already registered rather than tuned.

| | n | positives | precision | Wilson 95% |
|---|---:|---:|---:|---|
| passes the screen | 54,772 | 85 | **0.155%** | [0.126%, 0.192%] |
| excluded by it | 43,012 | 16 | 0.037% | — |

**The derived bar is a poor screen**: it keeps 56% of the volume to gain 1.5×.
§7.1 shows the signal actually lives near |ḋ| ≳ 0.032 deg/day, roughly three
times higher. **No bar is tuned here**; the derived one is reported because it
is the honest bridge between T8a's denominator and T8d's, and it shows that
the bridge is not a short one.

---

## 8. What the alarm may now say — verbatim, and what it still may not

The design document's §6 vocabulary ladder held **"matches pattern P"**
WITHHELD, because §4.1's trigger-time taxonomy was unbuilt and had no measured
per-class precision. It is now built and measured, and gates B, C, D and E all
fail to fire for it.

**PERMITTED, for a trigger the frozen taxonomy assigns to class 1:**

> Object NORAD `<id>` executed a drift-rate change of `<Δḋ>` deg/day,
> confirmed at `<t_confirm>` UTC (second consecutive element set showing the
> change), and announced at `<t_confirm + 5 d>` once the change had stopped.
>
> **The trigger matches pattern `<P>`** — a large drift change leaving a
> trajectory that would cross many occupied mean longitudes. **822 of the
> 97,784 confirmed drift changes in the 1959–2026 archive match it.**
>
> **In those 822, the object arrived within 0.1° of another satellite's mean
> longitude and stayed there ≥ 30 days in 28 — 3.4%, Wilson 95%
> 2.4%–4.9%. Median time from this point to arrival: 22.1 days,
> p25–p75 7.0–47.5 days.**
>
> **Base rate for a confirmed drift change of any kind: 0.10%
> (101 of 97,784).**
>
> Mean longitude is a slot coordinate. This is not a miss distance and not a
> conjunction warning. Pattern assignment is mathematics on public element
> sets. No purpose is attributed.

**STILL WITHHELD, and now for measured reasons rather than for want of a
measurement:**

| clause | status | why |
|---|---|---|
| "matches pattern P" **for class 0** | **WITHHELD** | 0.075% [0.060%, 0.095%]. It is a measurement, not a warning; 96,962 of 97,784 triggers land here and quoting it would be an alert that says nothing |
| **"this object has previously done X, N times; those ended in Y within D days"** | **WITHHELD** | **gate H fired.** The per-object predictor is worse than the base rate at every prior-event count and the threshold does not exist. §6.1 and §6.2 |
| any predicted dwell duration or closest separation | **WITHHELD** | T8c +0.128 and +0.038; M2-D is 16 predictions |
| a point value of D | **WITHHELD** | the distribution and its spread, always. p25–p75 spans 7.0–47.5 days for class 1 |
| **"manoeuvre"** | **WITHHELD** | `manoeuvreLabelPermitted` is false in the shipped pipeline |
| "approach", "approached" for an individual alert | **WITHHELD** | T8a §7.4, T8b §12.4 |
| any purpose, motive, mission or actor | **FORBIDDEN** | prereg §1.1 |
| **T8a's 32.8% as the alert's precision** | **FORBIDDEN, newly** | §3.3. It is a different denominator and the design was wrong to treat it as the trigger-time floor |

---

## 9. Registered blind spots, as they actually bit

Each was declared in prereg §14 before measurement.

1. **The trigger population is not an operator's alert population** — and this
   bit hardest. 226,422 chains is 150× the size the registration anticipated,
   and it is the reason both compute deviations of §2 exist.
2. **O1 inherits T8a's 180-day attribution window.** §3.4's p95 of 157.7 days
   sits just under it: the lead-time distribution is right-censored by
   construction and T8d cannot repair it.
3. **The forward propagation assumes no further manoeuvre.** Measured at a
   median 0.408° of error over 30 days (§4) — small, and still an assumption.
4. **The occupancy set is a causal proxy for stationing.** κ = 0.709, 32,009
   disagreements, reported in §3.5 and repaired nowhere.
5. **A trigger is a detector event.** Every trigger here has a visible burn by
   construction, so T8d says nothing at all about the 33% of T8a's events with
   no confirmable initiating change. **Absence of a trigger is not absence of
   an approach.**
6. **M2-L is not out of sample.** §6.3, declared in advance and repeated there.
7. **Small sample for the dimension** — inverted in practice: the sample was
   enormous and the **positives** were tiny. 101 positives in a 22-dimensional
   space is what limited M2-D to 16 predictions and made every prior-event
   stratum of §6.2 a handful of events.
8. **No LEO arm.** Not attempted; T8b's plane-noise floor is still unrepaired.
9. **`month_rollup` is 15% stale.** Nothing here is sized from it.

**And one that was not declared, stated plainly because it was not foreseen:**
the registered Beta(1,1) smoother of §8.1 was chosen against an imagined base
rate of tens of percent and is grossly wrong against 0.1%. It was fixed before
the number existed, the number is reported as it came out, and the gate it
fired is reported as fired. **What a future registration should fix is the
prior's strength relative to the measured base rate — not the gate.**

---

## 10. Reproduction

```
# the registration, committed ALONE, before any measurement code existed
git show 154c53f -- docs/trigger-alarm-preregistration-20260922.md

# the instrument and its 100 offline proofs
python3 -m unittest tests.test_trigger_alarm          # 100 tests, no archive, no network

# the measurement (CPU, ~56 min on pc; the trigger table is cached and
# re-keyed on the hash of the code that produced it)
python3 tools/trigger_alarm.py --stage all \
    --work /home/sdegan/t8d-work --out docs --date 20260922
```

| artifact | |
|---|---|
| `docs/trigger-alarm-20260922-receipt.json` | every number in this document |
| `docs/trigger-alarm-triggers-20260922.jsonl` | **a bounded subset — 5,904 rows**: all 904 rows positive under O1 or O2, plus a seed-20260922 uniform sample of 5,000 others. The full 226,422-row table is **230 MB** (sha256 `f4c3ca9b…`), is written beside the run, and its sha256, byte count and row count are in the subset's provenance record — this repository is a teaching-aid source tree, not an archive. The sampling rule reads only the outcome, so **the positives are complete rather than sampled** and every precision in this document can be checked against the committed file |
| `tools/trigger_alarm.py`, `tests/test_trigger_alarm.py` | the instrument and its proofs |

Source hashes are in the receipt under `sourceSha256`, including the
registration's, T8a's events file (`b2e6b364…`) and T8c's feature table
(`88499a77…`).
