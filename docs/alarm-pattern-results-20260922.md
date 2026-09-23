# T8c results: a six-class taxonomy of GEO approach behaviour, and a second null on predictive skill

Measured 2026-09-22. Registration:
`docs/alarm-pattern-preregistration-20260922.md`, committed **alone** at
`daf7df4` before any measurement code existed; the instrument and its 57
tests followed at `65ae1b5`. The ordering in `git log` is the evidence. Every
threshold, every feature definition, the cluster-count criterion and the
comparison baseline were fixed in that registration and none was changed
after a number existed.

Framing, restated because it constrains this document: the instrument is
**ownership-agnostic mathematics**. No feature, transform, distance, cluster
assignment or prediction reads a catalogue registry code, and no row this
study writes carries one — a test asserts both. Cluster names below are
mechanical descriptions of element behaviour and are **facts, never intent**.
No delta-V, mass or consumables figure was computed for any object. **No
figure here is a miss distance**: every separation is mean-longitude
separation, a slot coordinate (T8a §1.1).

---

## 0. The seven registered gates, discharged

| Gate | Registered meaning | Primary arm (487) | Secondary arm (326 flagged) |
|---|---|---|---|
| **P** | **the taxonomy does not beat feature poverty** | **FIRED** — `skill_E1a` = **+0.128** against a bar of +0.157 | **FIRED** — **+0.001** |
| Q | the taxonomy is not stable | not fired — **at 0.501 against a bar of 0.5** | **FIRED** (0.443) |
| R | the taxonomy re-describes T8a's contamination | not fired (ARI 0.301 vs a bar of 0.5) | n/a — the arm is one class |
| S | outcome degeneracy | not fired (η² = 0.130 vs a bar of 0.05) | not fired, barely (0.051) |
| **T** | underpowered | **FIRED** — smallest cluster 13 < 20 | **FIRED** — smallest cluster 12 |
| U | feature poverty merely relocated | not fired | not fired |
| **V** | the comparison is not like-for-like | **not fired** — reproduction **+0.13656** against T8a's **+0.137** | FIRED by construction; §6.3 |

**The one-paragraph verdict.** T8a diagnosed its own weak predictive skill as
feature poverty — two crude features per outcome. T8c replaced them with
thirty-two, extracted from the element histories behind the catalogue, and
built the taxonomy the alarm's "categorized way P" clause needs. **The
taxonomy is real**: six classes, mechanically distinguishable, carrying 13.0%
of the between-event variance in loiter duration, and the registered gate for
"the clusters carry no outcome information" does not fire. **The predictive
skill is not there.** Predicting an approacher's next event from its prior
events' cluster membership scores **+0.128 [0.065, 0.187]**, against T8a's
own-history baseline of **+0.137** — a tie, not an improvement, and well
below the registered +0.157 bar. **Gate P fires, and the diagnosis that
feature poverty was the cause of T8a's weak skill is not supported.** The
honest statement of what the programme now knows is in §7, and the
consequence for the alarm is that its "seen N times before → outcome Y"
clause must be built as a *refinement of an object's own history*, never as a
substitute for it.

---

## 1. What ran, where, and for how long

| | |
|---|---|
| Host | `pc` (`bigmem-PC`), CPU only, `nice -n 15` <!-- src: docs/alarm-pattern-20260922-receipt.json, host/executionMode --> |
| GPU | **none, and the registered race was not triggered.** prereg §7 fixed a 600 s threshold above which the GPU would be exercised through `gpu-run`; the whole primary run is **143.8 s wall / 143.1 s CPU**, so the condition never arose and no GPU time was taken from another session |
| Element histories | **403 objects, 16.3 s** — by the `(norad, epoch_ms)` primary key, not by a scan |
| Leave-one-object-out refits | **91.5 s** for 224 folds × two feature sets |
| Archive | `/home/sdegan/space-orbit-history/orbit-history.sqlite3`, read-only, `PRAGMA query_only=1` |
| Inputs | `docs/proximity-events-20260922.jsonl`, sha256 `b2e6b364…70deef` — the committed T8a primary arm, unmodified |
| Outputs | `docs/alarm-pattern-features-20260922.jsonl` (sha256 `88499a77…16d05`), `docs/alarm-pattern-20260922-receipt.json`, `docs/alarm-pattern-flagged-20260922-receipt.json` |

### 1.1 The 293-second pass that was not repeated

T8a's extract stage scanned 217,007,154 element sets in 293.5 s to keep the
11.6 M near-GEO rows. T8c needs the histories of **409 objects**, not of
1,768, and `element_set` is `WITHOUT ROWID` on `(norad, epoch_ms)` — so 409
indexed range reads return the same rows, under the same quantised filter, in
**16.3 s**. 403 of the 409 have the two or more near-GEO element sets a series
requires; the other six are counted, not dropped in silence.

**This is the whole GPU story too.** The registration required a measured race
only if the run exceeded 600 s. At 143.8 s it did not, and the arithmetic says
why: k-means over 487 points in ≤ 36 retained dimensions is a 487 × 36 by
36 × 6 matrix product per iteration — about 100 kFLOP — and a kernel launch
costs more than that. The same shape of finding as T8b §1.2, reached without
needing to run the race: **the problem is too small for a GPU to win**, and
the honest way to say that here is that the registered trigger was measured
and did not fire, not that a race was run and lost.

---

## 2. The feature table

**487 events × 37 columns** (the registered 32 features plus five missingness
indicators), extracted by the definitions fixed in prereg §3 and by no others.

**Missingness, reported per feature rather than summarised**, because gate U
exists to catch a rich vector that is mostly imputation:

| Feature | missing | Feature | missing |
|---|---:|---|---:|
| `cadence_days_since_prev` | **46.0%** | `departure_dest_distance_deg` | 29.0% |
| `init_drift_change_mag` | **33.1%** | `departure_reverses` | 15.8% |
| `lead_causal_days` | **33.1%** | `departure_drift_abs` | 15.2% |
| `dwell_rel_period_days` | **33.7%** | `arrival_brake_days` | 11.7% |
| `dwell_rel_osc_fraction` | 33.7% | `init_ramp_days` | 10.1% |

Every other feature is complete. **Gate U does not fire**: 10 of 37 columns
exceed the 30% bar, against a bar of "more than half". The two largest are
structural rather than defects — 224 of 487 events are an approacher's first,
so they have no previous interval, and 161 have no confirmed initiating flag
at all (T8a §7.4), which is itself carried as the feature
`has_initiating_flag` and as the indicator `miss_init_flag`.

**One correction made before any number was kept.** A test written against the
registration found that feature 28, `cadence_prior_arrivals`, was raw in the
first implementation where prereg §3.11 lists it among the twenty
log-transformed features. The tool was corrected **to the registration**, and
every figure in this document is from the corrected run. The uncorrected run
gave `skill_E1a` = +0.090 at k = 7; it is recorded here only so that the
correction is visible rather than silent, and it is not a result.

---

## 3. The taxonomy

### 3.1 The cluster count, chosen by the registered criterion

prereg §4's primary criterion is the mean silhouette coefficient over
k ∈ {2…10}, ties toward the smaller k. Nothing was eyeballed.

| k | 2 | 3 | 4 | 5 | **6** | 7 | 8 | 9 | 10 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| mean silhouette | 0.1363 | 0.1327 | 0.1454 | 0.1467 | **0.15573** | 0.15568 | 0.1301 | 0.1428 | 0.1279 |

**k = 6**, and the margin over k = 7 is **5.1 × 10⁻⁵** — three orders of
magnitude above the registered 1e-6 tie threshold, so the tie rule did not
engage, but far too small to mean anything. **Reported plainly: the criterion
chose between 6 and 7 on a difference that is not a difference.** It is
reported because a registered criterion that produces a near-tie is exactly
the case in which a later reader is entitled to suspect the k was picked, and
the sweep above shows it was not.

The absolute level matters more than the argmax. **A mean silhouette of 0.156
is weak structure** — the value would be above 0.5 for well-separated classes.
The taxonomy is a partition of a continuum with soft modes, not a set of
disjoint behaviour types, and every statement below carries that.

**The registered secondary criterion disagrees and governs nothing.** The gap
statistic (B = 50, PCA-aligned box) never plateaus over k ∈ {2…10}: its gap
rises monotonically from 1.451 at k = 2 to 1.658 at k = 10, so its rule
selects the range's upper end. Two criteria pointing at 6 and at ≥ 10 is the
same finding from two directions — the feature space has no natural cluster
count — and prereg §4 fixed which one governs before either was computed.

### 3.2 Stability — the weakest possible pass

200 bootstrap resamples **of approachers**, greedy maximum-Jaccard matching to
the full-sample partition:

| Cluster | 0 | 1 | 2 | 3 | 4 | 5 | median |
|---|---:|---:|---:|---:|---:|---:|---:|
| Jaccard | 0.573 | 0.402 | 0.504 | 0.575 | 0.385 | 0.497 | **0.501** |

**Gate Q's bar is 0.5 and the median is 0.501.** This is a pass in the same
sense that T8b §7.1's gate G was a pass: at the bar, not above it. Two of the
six clusters (1 and 4 — the two smallest) recover below 0.4 of their members
under resampling and **should not be treated as classes at all**; clusters 0,
2 and 3 are the reproducible ones. This is stated here rather than in a
footnote because the alarm design in `docs/alarm-lane-design-20260922.md`
depends on which classes are real.

### 3.3 The six classes

Centroids are **medians in original units**; the "what names it" column is the
five features whose standardised centroid is furthest from zero. Every name is
a description of element behaviour. **None is a purpose.**

| | n | objects | what names it | transit | arrival | dwell & departure |
|---|---:|---:|---|---|---|---|
| **C0 — unresolved initiation, spiked transfer** | 45 | 28 | `miss_ramp` +2.92, `has_initiating_flag` −1.42, `init_abruptness` +1.12 | 32.3 d, median drift 0.073 °/d but **peak 1.064 °/d**, flatness **0.08** | brake 0.015 °/d, overshoot 0.041° | loiter median **105 d** (the longest), departs slowly |
| **C1 — repeat multi-target mover** | 38 | **9** | `cadence_prior_targets` +2.36, `cadence_prior_events` +2.03, `departure_drift_abs` +1.75 | **7.9 d at 0.425 °/d**, 4 staged flags, 2 mid-course | brake **0.297 °/d**, lead **19.0 d** | loiter 87 d, then **departs at 0.579 °/d, reversing**, to a longitude **47° away** |
| **C2 — single fast burn into an adjacent slot** | 126 | 104 | `transit_days` −1.20, `transit_drift_median` +1.04, `arrival_brake_mag` +1.03 | **4.0 d at 0.589 °/d**, flatness **0.82** (a plateau) | brake **0.525 °/d**, lead **9.9 d** | loiter 89 d, departs slowly to **2.0° away**; interval to next event **262 d** |
| **C3 — slow drift-through** | 105 | 38 | `init_abruptness` −1.58, `transit_drift_peak` −1.36, `miss_init_flag` +1.22 | **95 d at 0.020 °/d**, peak 0.033 °/d | brake **0.0006 °/d** over **36 d** | loiter median **37 d, p95 92 d** — the shortest; 32% in the libration zone; only **10% carry a flag** |
| **C4 — long-haul relocation** | **13** | 8 | `transit_longitude_span` +5.56, `separation_at_start_deg` +4.74 | 41.9 d at **1.297 °/d** over **62.5° of longitude** | lead 93.6 d | loiter 48 d |
| **C5 — staged, many-correction transfer** | 160 | 104 | `transit_drift_flatness` −0.95, `transit_midcourse_count` +0.68, `has_initiating_flag` +0.57 | **76 d**, median drift 0.037 °/d, peak 0.853, **11 mid-course flags** | lead 83.0 d | loiter 60 d, departs to **0.33° away** |

Read together, the axis the taxonomy actually found is **how the transfer was
flown**: one impulsive pair (C2), a long chain of corrections (C5), a
repeating fast shuttle (C1), a single very long haul (C4) — against two
classes with **no visible initiating burn at all** (C0 and C3), which is T8a's
§7.4 contamination showing up as geometry rather than as a label.

**C3 is the clearest single finding in the taxonomy.** 105 events, 90% with no
confirmed drift change, transfers at 0.020 °/day over 95 days — slower than
any deliberate relocation — a third of them inside the libration zone, and a
loiter distribution pinned at the 30-day floor (median 37 d, p95 92 d). This
is free libration turning around near an occupied longitude, exactly as T8a
§7.2/§7.3 described it, and the unsupervised taxonomy separated it **without
being told the flag existed as anything but one feature among thirty-two**.

### 3.4 Two partition comparisons, reported as arithmetic

| | ARI |
|---|---:|
| the six classes against the flagged/unflagged split (gate R) | **0.301** |
| the six classes against the five **causal** classes of prereg §5 | 0.774 |

Gate R's bar is 0.5 and does not fire: the taxonomy is correlated with T8a's
contamination split but is not a restatement of it. §6.4 shows how much of the
skill nonetheless lives there.

The registration also permits exactly one registry-related figure, reported as
arithmetic with no interpretation and no per-nation narrative, in the manner
of T8b §3.4. It is **not** reported here, and the reason is stated rather than
left implicit: T8c's feature table carries no metadata column at all, so
computing it would have required reading one back out of the T8a catalogue
solely to publish it. Whether registry codes ever appear on any T8 surface is
an operator decision reserved to Sean (prereg §1.5), and this document
declines to take a step toward it that the measurement did not need.

### 3.5 The causal taxonomy

prereg §5's second clustering, over the 23 features an observer possesses by
the moment of arrival: **k = 5**, sizes 13 / 97 / 188 / 143 / 46, between-class
η² for loiter duration **0.118** against the full taxonomy's 0.130. **The dwell
and departure blocks — everything the alarm cannot see — buy 0.012 of outcome
variance.** That is the most encouraging number in this document for the alarm
design, because it says the causal restriction costs almost nothing.

---

## 4. THE MEASUREMENT — gate V first, then the headline

### 4.1 Gate V: the baseline reproduces

prereg §6.2 required T8a's +0.137 to be reproduced before anything else, on
the grounds that a headline comparison against a baseline one has not
reproduced is worthless.

| | n | MAE own (log) | MAE population (log) | skill |
|---|---:|---:|---:|---:|
| T8a §5.2, as published | 375 | 0.575 | 0.666 | **+0.137** |
| T8c's reproduction | **375** | **0.5752** | **0.6662** | **+0.13656** |

Difference **0.00044**, against a tolerance of ±0.005. **Gate V does not fire
and the comparison below is like-for-like.** The closest-separation baseline
reproduces at **+0.00838** against T8a's +0.008.

### 4.2 The number this study exists to produce

> **`skill_E1a` (loiter duration) = +0.1276, bootstrap 95% over approachers
> [+0.065, +0.187], n = 375, 112 approachers.**
>
> **T8a's baseline is +0.1366 on the identical 375 predictions.**
>
> **Gate P fires.** The registered bar was +0.157.

Predicting an approacher's next loiter duration from the modal cluster of its
other events is **not better than predicting it from the median of those same
events**, and the point estimate is 0.009 *below* it. The rich thirty-two
feature vector, the six-class taxonomy and the leave-one-object-out refit buy
nothing over two numbers and a median.

### 4.3 Every registered estimand

All skills are `1 − MAE_model / MAE_population` in natural-log space;
intervals are 2,000 bootstrap resamples **of approachers**.

| Estimand | what it predicts, from what | n | skill | 95% CI | baseline |
|---|---|---:|---:|---|---:|
| **E1a** | loiter, from the modal cluster of the object's **other** events | 375 | **+0.128** | [+0.065, +0.187] | **+0.137** |
| E1b | loiter, from the object's **prior** events only (causal) | 263 | **+0.146** | [+0.069, +0.213] | +0.137 |
| E2 | loiter, from the **current** event's own causal features | 487 | +0.083 | [+0.031, +0.133] | +0.137 |
| E3a | closest separation, E1a protocol | 375 | +0.038 | [+0.014, +0.062] | +0.008 |
| E3b | closest separation, prior events only | 263 | +0.044 | [+0.016, +0.069] | +0.008 |
| E3c | closest separation, current event's causal features | 487 | +0.024 | [+0.006, +0.045] | +0.008 |
| **E4** | **interval to the object's next event**, E1a protocol | 185 | **+0.107** | [+0.024, +0.197] | none registered |
| E4′ | interval to the next event, prior events only | 136 | +0.074 | [−0.010, +0.164] | none |

Four things in that table are worth stating in words.

**E1b is nominally above the baseline and is not a rescue.** Using only the
object's prior events — the version an alarm could actually run — scores
+0.146 against +0.137. The gate is defined on E1a and E1a is what fires.
E1b's interval [+0.069, +0.213] contains the baseline comfortably, and n falls
from 375 to 263 because an object's first event has no prior. **A 0.009
difference on a quantity whose interval is 0.14 wide is not an improvement and
this document does not report it as one.**

**E2 is the alarm's own estimand and it is the weakest of the three.** +0.083
[+0.031, +0.133] over all 487 events, from features available at the moment of
arrival. It is positive and its interval excludes zero — the alarm *can* say
something about the dwell that is starting — but the something is worth about
8% of the error, not a forecast.

**E3 is a small, real improvement on the quantity T8a wrote off.** T8a
measured +0.008 for closest separation and concluded the profile "does
essentially nothing" for it. Against that, +0.038 [+0.014, +0.062] is a
five-fold increase whose interval excludes zero. It is also, in absolute
terms, tiny: the population MAE is **3.30 in log space** — a factor of e³·³ ≈
27 — because closest separation spans eleven orders of magnitude, from 8e-13°
to 0.07°. Reducing an error of that size by 4% is a measurement, not a
capability. **No alarm should quote a predicted separation.**

**E4 is the clause the alarm actually needs, and it is the widest.** The
interval to an approacher's next event is predicted at +0.107 [+0.024, +0.197]
— better than E2 and comparable to E1a. But the quantity itself is enormous:
over the 243 observed intervals the **median is 90.0 days with a p25–p75 of
34.3–729.6 days**. A 10.7% reduction in log-MAE on a quantity with a 21-fold
interquartile ratio means an alarm's "within ~D days" clause would have to
quote a range spanning more than an order of magnitude. §8 of the design
document is written against exactly this number.

---

## 5. The secondary arm — where the skill actually lives

prereg §2 registered a second arm over the **326 events carrying a confirmed
initiating drift-change flag** (T8a §7.4), so that the taxonomy could not be
read as a contamination detector by accident. Run in full, with the identical
procedure:

| | primary (487) | **flagged (326)** |
|---|---:|---:|
| k chosen by silhouette | 6 | 6 (sizes 95/20/12/127/17/55) |
| median bootstrap Jaccard | 0.501 | **0.443 — gate Q FIRES** |
| between-class η², loiter | 0.130 | **0.051** (gate S's bar is 0.05) |
| the arm's own T8a-protocol baseline | +0.1366 | +0.1269 |
| **`skill_E1a`** | **+0.128** | **+0.001** [−0.061, +0.066] |
| `skill_E1b` | +0.146 | +0.021 [−0.038, +0.082] |
| `skill_E2` | +0.083 | +0.020 [−0.025, +0.062] |
| `skill_E4` | +0.107 | −0.015 [−0.061, +0.019] |

> **Remove the events with no visible initiating burn, and the taxonomy's
> predictive skill goes to zero.** Not "falls" — **+0.001**, with an interval
> centred on nothing.

This is the most consequential finding in the document after the headline, and
it qualifies the headline rather than softening it. Gate R did not fire
(ARI 0.301), so the six classes are not a relabelling of the flagged split —
but **essentially all of the outcome information the clusters carry is
carried by the distinction between the events that show a burn and the events
that do not**, which is the distinction T8a already published as a
contamination filter. C0 (loiter median 105 d, 0% flagged) and C3 (loiter
median 37 d, 10% flagged) sit at the two ends of the loiter distribution, and
they are the two classes the flagged arm cannot contain.

**Gate V fires on this arm by construction and is not a defect.** The bar is
defined against T8a's +0.137, which was measured on the 487-event primary arm;
the flagged arm's own baseline is +0.1269, which is a different population's
number. The gate is a primary-arm check and the registration should have
scoped it as one. Stated as a defect in the registration, found at
measurement time, changing no verdict: **prereg §6.2 wrote a gate whose bar is
only meaningful for one of the two registered arms.**

---

## 6. Post-registration diagnostics

**Labelled as such throughout, in the manner of T8a §7.4 and T8b §7.3.** These
were added at measurement time, change no registered verdict and are not
registered estimands. They exist because gate P firing leaves a question the
registered estimands cannot separate, which prereg §10.2 declared in advance:
*is the feature space still too poor, or is the outcome not predictable?*

| Diagnostic | what it is | loiter skill | 95% CI |
|---|---|---:|---|
| **D1** | a **continuous** predictor over the same rich features — the median of the 10 nearest training events in the fold's standardised space | **+0.070** | [+0.012, +0.127] |
| **D2** | the cluster median and the object's own-history median **averaged in log space** | **+0.206** | [+0.127, +0.272] |
| D3a | between-**object** variance fraction of log loiter duration | **0.688** | — |
| D3b | between-**cluster** variance fraction of log loiter duration | 0.130 | — |

Three readings, each of which the registered measurement alone could not
support:

1. **The discretisation is not what costs the skill.** D1 replaces the
   six-class partition with a continuous nearest-neighbour predictor over the
   identical features and scores **+0.070 — worse than the clustered +0.128**.
   If the taxonomy were throwing away information by rounding a continuum into
   six boxes, D1 would beat it. It does not. **The feature space itself is
   weakly informative about this outcome**, and a finer taxonomy, a soft
   assignment or a supervised model over these features is not the repair.
2. **The taxonomy is a complement, not a substitute.** D2 — the cheapest
   possible way to use both predictors at once — scores **+0.206 [+0.127,
   +0.272]**, which beats T8a's +0.137 by +0.069 and clears the registered
   +0.157 bar that E1a missed. The cluster knows something the object's own
   history does not, and vice versa. **This is a post-registration diagnostic
   and it is not the headline**; what it licenses is a design decision, not a
   claim, and §7.3 of the design document is where it goes.
3. **Object identity carries 5.3× what pattern class does.** 68.8% of the
   variance in log loiter duration is between objects; 13.0% is between
   clusters. This is the arithmetic behind the headline: an approacher's own
   history is a far better description of it than any class it can be put in,
   and T8a's ICC of 0.436 for loiter duration was already saying so.

For closest separation the same diagnostics give D1 +0.053 [+0.017, +0.091],
D2 +0.082 [−0.001, +0.167] — an interval that touches zero — and a
between-object variance fraction of 0.598. The high between-object fraction
beside T8a's near-zero own-history skill is not a contradiction: the MAE is
dominated by an eleven-order-of-magnitude tail that no median predictor
reduces.

---

## 7. What this means for the programme

Stated as findings, not as a plan; scope beyond T8c is Sean's.

1. **T8a's diagnosis of its own weak skill is not supported.** T8a §5.2 and
   §12 attributed +0.137 to feature poverty. Sixteen times as many features,
   extracted from the same element histories, produce **+0.128**. Whatever
   limits the prediction of a GEO approach event's dwell duration, it is not
   the number of features describing the approach.
2. **The alarm's "categorized way P" clause is supportable; its "outcome Y"
   clause is supportable only as a distribution.** The taxonomy exists
   (six classes, three of them reproducible under resampling, η² = 0.130) and
   an event can be assigned to a class from causally available features at
   almost no cost (§3.5). What cannot be done today is turn that class into a
   point forecast of what happens next.
3. **The alarm's "within ~D days" clause is the widest part of it.** The
   measured interval between an approacher's successive events has a median of
   90 days and an interquartile range of 34–730 days, and the best registered
   predictor reduces its log error by 10.7%.
4. **Essentially all of the clusters' outcome information is the
   burn-visible / burn-invisible split** (§5). That split is already T8a's
   published contamination filter. An alarm built on this taxonomy would, for
   a large part of its confidence, be re-reporting whether an object's
   transfer was visible — which is a statement about the detector as much as
   about the object, exactly as T8b §7.2 said of its own corroboration flag.
5. **A weak silhouette is a result, not a nuisance.** 0.156 at the chosen k,
   a gap statistic that never plateaus, and two clusters below 0.4 Jaccard
   together say the feature space has soft modes rather than classes. The
   programme should not expect a later, better feature set to produce clean
   behaviour types at GEO; it should expect a continuum, and design the alarm
   to quote positions on it with their spread.
6. **The complement finding is where the next registration should go** (§6,
   D2). Averaging the class median with the object's own history beat the
   baseline by +0.069. That is a post-registration diagnostic and it is not a
   result — it is the hypothesis for a T8d registration, which would have to
   fix the combination rule before the number exists, exactly as this one did.

---

## 8. Registered blind spots, as they actually bit

Each was declared in prereg §10 before measurement.

1. **487 events in a 36-dimensional space is ~13 events per dimension.** It
   bit exactly where it was expected to: the silhouette is 0.156, two of six
   clusters are unstable, and gate T fired on a 13-member cluster.
2. **A null cannot distinguish "still too poor" from "not predictable".** The
   registration said this and said the results document must not choose.
   §6's D1 narrows it without closing it: a continuous predictor over the same
   features does *worse*, which rules out the discretisation and is consistent
   with either remaining explanation. **T8c does not know which it is and says
   so.**
3. **The taxonomy inherits T8a's contamination.** §5 measures the cost: the
   whole of the skill.
4. **The dwell block sees 30 days of a dwell whose median is 57 days.** The
   leakage control cost exactly this, knowingly, and it is why no dwell
   feature can encode the outcome.
5. **No LEO arm.** Unchanged. T8b's 71 arm-M events across 55 approachers
   cannot support this feature space, and the design document carries LEO's
   lead-time budget as an input and nothing more.
6. **Cluster membership is not a behaviour.** It is a position in a feature
   space this registration fixed. A different fixed feature set would give
   different clusters, and nothing here licenses the phrase "the behaviour
   classes of GEO approach".
7. **`month_rollup` is 15% stale.** T8c read `element_set` directly and sized
   nothing from the rollup.

**One consequence of a registered choice, reported because it shaped the
clusters.** prereg §3.11 fixed `log(x + 1e-9)`. Three features are legitimately
zero for many events — `arrival_overshoot_deg` when the approacher stopped
short, `dwell_correction_rate` when no flag fell in the window,
`cadence_prior_arrivals` for a first event — and a zero maps to −20.7 where a
typical value maps to about −4. Those events therefore sit far out along those
axes. The choice was registered and was not revised; a future registration
should use `log1p` on a scaled quantity or carry an explicit zero indicator
instead.

**One defect found in T8a's instrument, reported because it was found.**
`tools/proximity_geo.py` sets `s.grid_lo` to a **global-relative** day offset
(line 367), and `relocations`, `candidate_pairs` and `permutation_null` use it
that way correctly. Two other sites — `calibrate_sigma_n` (lines 423–424) and
the `ḋ_n − ḋ_λ` cross-check (lines 784–785) — use `(s.grid_lo + i) · DAY_MS`
as an **absolute epoch**, which it is not: it is short by `global_lo · DAY_MS`,
where `global_lo` is the day index of the earliest near-GEO element set in the
archive. The windows those two functions search are therefore displaced by
that constant. **Neither displacement can move a registered T8a verdict**:
T8a §2.2 records that the derived 0.010 deg/day floor dominates `5σ_n` by a
factor of 3.3, so the calibration never reaches a detector decision, and the
cross-check's registered clause passed with 2.7× of margin. T8c sidesteps it
entirely by storing an absolute day index in the same attribute (`attach_grid`,
prereg §2 IMPL), which is why T8c's station segments are usable for feature 24.

**`global_lo` measured directly**, by one filtered scan of the archive: the
earliest near-GEO element set is at epoch **−166,219,920,288 ms =
1964-09-25T03:48Z**, day index **−1,924**. So `s.grid_lo = first_day + 1924`
for every object, and the two affected windows are displaced **1,924 days
(5.27 years) later** than the stationed segment they were meant to measure.
For any object whose near-GEO history is shorter than 5.27 years the window
lands past the end of its series entirely and the segment contributes nothing,
which is consistent with T8a §2.3 reporting the cross-check over **2,639**
stationed segments where §2.1 counts **24,685**.

**One consequence for exact reproduction, declared rather than discovered
later.** The same scan counts **11,627,400** near-GEO element sets against the
**11,626,494** T8a kept at 03:02 UTC — **+906 rows** added by the hourly
`spacetrack-ingest` in the intervening hour. T8c's feature extraction
therefore saw a very slightly longer archive than the catalogue it describes.
The affected features are the trailing windows of events near the archive's
right edge, and the effect is bounded by one hour of ingest; it is declared
because "the archive is a moving target" is a reproducibility fact that any
re-run of this study will meet.

---

## 9. Reproduction

```
# the registration, committed ALONE, before any measurement code existed
git show daf7df4 --stat

# the instrument and its tests
python3 -m unittest tests.test_alarm_pattern                  # 57 tests
python3 tools/alarm_pattern.py --stage all --arm primary      # 16 s + 144 s, CPU
python3 tools/alarm_pattern.py --stage all --arm flagged      # 10 s + 99 s, CPU
```

Determinism: seed **20260922** for k-means++ initialisation, the gap
statistic's reference draws, the 200 bootstrap stability resamples and the
2,000 bootstrap skill intervals. No other randomness; two independent runs
returned identical figures to every digit reported here. Source sha256 of the
instrument, of `tools/proximity_geo.py` as imported, and of the registration
are in `docs/alarm-pattern-20260922-receipt.json` under `sourceSha256`
(`tools/alarm_pattern.py` = `71eeb14d…b756ac`).

Nothing from T8c was written to `src/`, `data/`, `public/` or any site
surface, and `docs/alarm-lane-design-20260922.md` is a design document with
nothing deployed. Publication and site framing for this track is reserved to
Sean.
