# The behavioural alarm lane: DESIGN ONLY

> **STATUS: DESIGN. NOTHING IS DEPLOYED, NOTHING IS SCHEDULED, NOTHING IS ON
> ANY SITE SURFACE.** No code in this document exists. No alert has been
> emitted. Nothing here is written to `src/`, `data/`, `public/` or any
> published artifact, and none of it may be until the operator decisions of
> §10 are taken. This document is the T8c task-2 deliverable
> (`docs/research-program-runbook-20260921.md`: "T8a catalogue/profiles →
> pattern taxonomy → T8c alarm lane on the 2-hourly sweep. Interpretive
> framing and public surface are operator decisions.").

Written 2026-09-22, after and constrained by:

- `docs/alarm-pattern-preregistration-20260922.md` §9, which fixed — before
  the numbers existed — what this document may and may not assume.
- `docs/alarm-pattern-results-20260922.md` (T8c): the six-class taxonomy, and
  **gate P fired** — the taxonomy does not beat T8a's baseline.
- `docs/proximity-results-20260922.md` (T8a): GEO, median 36.1 d causal lead,
  32.8% precision over 1,483 historical alerts.
- `docs/proximity-leo-results-20260922.md` (T8b): LEO, median 195.9 d lead,
  44.1% precision, **for in-track phasing campaigns** — the qualification
  travels with the number everywhere below.
- `docs/proximity-priorart-20260922.md`: its eight forbidden phrasings and
  thirteen must-cites bind every word of any alert this lane would emit.

---

## 0. REVISED 2026-09-22, later the same day, after T8d — what changed

`docs/trigger-alarm-preregistration-20260922.md` (committed alone as `154c53f`)
and `docs/trigger-alarm-results-20260922.md` built and measured the
**trigger-time taxonomy** that §4.1 below named as this design's blocker.
Five things are now different. Each is marked **[T8d]** where it appears, and
nothing else in this document has been touched.

1. **§1's closing sentence is REPLACED.** The clause this lane may speak is
   **per-CLASS, not per-object**: T8d's gate H fired, and the per-object
   predictor is worse than the population base rate at every prior-event
   count.
2. **§4 is REWRITTEN.** The third taxonomy exists, is reproducible, and has a
   measured per-class precision.
3. **§4.3 is CORRECTED, not extended.** It asserted that the trigger-time
   precision floor "is already known" and is T8a's 32.8%. **That was wrong.**
   T8a's 32.8% is measured over 1,483 relocation alerts, each of which
   required a ≥ 2° relocation to have already happened — a population that
   does not exist at trigger time. The measured trigger-time figure is
   **0.103%** over **97,784** confirmed drift changes.
4. **§5.1 gains the measured trigger-time rows**, which are the ones an alert
   would actually have to print.
5. **§6's "matches pattern P" moves from WITHHELD to PERMITTED — for exactly
   one of the two classes.**

**Nothing about the status line above has changed. Nothing is deployed,
nothing is scheduled, nothing is on any site surface, no alert has been
emitted, and every operator decision of §10 remains reserved and untaken.**

---

## 1. What the lane would say, and the one sentence that fixes it

The programme goal is an audited live lane that says *"X is behaving in a
categorized way P (seen N times); historical outcome Y within ~D days."*
T8c measured whether that sentence is supportable. The answer is **partly**,
and the design below is built around which part.

**The alert template, in full, with nothing omitted:**

> **Object NORAD `<id>` executed a drift-rate change of `<Δḋ>` deg/day,
> confirmed at `<t_confirm>` UTC** (second consecutive element set showing
> the change).
>
> **The transfer so far matches pattern `<P>`** — `<mechanical description:
> e.g. "single fast burn, flat drift plateau, short transit">`. **`<N>`
> events in the 1959–2026 archive match this pattern.**
>
> **In those `<N>` events, the object arrived within 0.1° of another
> satellite's mean longitude and stayed there ≥ 30 days in `<n_arr>` of them
> (`<precision>`%, Wilson 95% `<lo>`–`<hi>`%). Median time from this point to
> arrival: `<M>` days (p25–p75 `<a>`–`<b>`).**
>
> **Mean longitude is a slot coordinate. This is not a miss distance and not
> a conjunction warning.**
>
> **Alert class `<P>` precision to date: `<k>/<n>`.** *Pattern assignment is
> mathematics on public element sets. No purpose is attributed.*

Everything in that template is a **fact about the object's elements** or a
**count over a published catalogue**. Nothing in it is an inference about why.

**And the one sentence that fixes the design — REPLACED [T8d]:**

> **~~The pattern may modify a rate; it may not replace an object's own
> history.~~**
>
> **[T8d] The pattern is the only thing the lane may speak. The object's own
> history may not be spoken at all.**

T8c measured a class-only predictor of **dwell duration** at **+0.128**
against an own-history predictor at **+0.137**, and the two combined at
**+0.206** (post-registration diagnostic D2). That is what the old sentence
was built on, and T8d re-ran D2 as a registered rule and reproduced it:
**+0.2012 [+0.1212, +0.2675]**, clearing the 0.157 bar, **gate G did not
fire** — but on the same 487 events D2 was generated from, which T8d declared
in advance is **not out of sample**.

**The arm that IS out of sample says the opposite.** On the alarm's own
question — did an arrival follow this trigger — over 96,567 object-disjoint
predictions, the registered per-object predictor scores a Brier skill of
**−5.419 [−7.030, −4.348]** against the population base rate, and there is
**no prior-event count at which it beats the baseline**. **Gate H fired.**

The nuance that survives, and that the lane may act on internally while saying
nothing about it: **as a RANKER** the object's own history does beat the class
(AUC 0.674 vs 0.544) and the hybrid beats both (0.715). **The complement
finding survives as an ordering and dies as a probability**, and an alert
quotes probabilities.

---

## 2. Riding the existing sweep — and the cadence it actually has

### 2.1 What the sweep is

`orbit-release.timer` fires at **`:25` every 2 h UTC** on `pc`
(`docs/SYSTEM-MAP.md` §6). Each firing advances a resumable whole-archive
sweep by at most `--budget-seconds`; **only the firing that *finishes* a sweep
writes the 256 catalogue shards**, and a finished sweep then waits
`MINIMUM_SECONDS_BETWEEN_SWEEPS` = **20 h** (`pipeline/orbit_release.py`)
before another begins.

**So the sweep's period is not two hours; it is about a day.** Any design
that says "the alarm fires every two hours" is wrong about the system it
rides. The correct statement is: **the alarm lane can fire on every timer
firing, but the underlying element state it reads is refreshed by
`spacetrack-ingest` at `*:17` (+ jitter) and the shard rebuild it would ride
happens about once a day.**

### 2.2 Where the lane attaches

Three attachment points, in increasing order of coupling, with the reason each
is or is not chosen:

| Point | What it costs | Verdict |
|---|---|---|
| **A separate timer reading `element_set` directly** | one indexed read per watched object; T8c measured **16.3 s for 403 objects' entire histories**, so a 1,768-object near-GEO watch over a 180-day window is seconds | **CHOSEN.** It is decoupled from the shard rebuild, so it cannot delay or be delayed by the 0.53 GB/rebuild bandwidth decision, and it does not change `orbit-release`'s resumability |
| Inside `orbit_release`'s sweep tail | free arithmetic, but it inherits the 20-hour floor and lengthens the critical path of a job whose budget is already the thing that decides shipping cadence | rejected |
| A consumer of the published shards | no archive access needed | rejected — the shards carry events, not the per-object drift-rate series the detector needs |

**The lane is therefore a read-only sidecar**: its own timer, its own state
file, `PRAGMA query_only=1` against the archive, and no write path into
`orbit-release`, the shards or the publish gate. It cannot break the site by
construction, which is the property that makes it safe to build before the
operator has decided whether anything is published.

### 2.3 Cadence, derived rather than chosen

The detector's own confirmation rule (T8a §5.5) requires **two consecutive
element sets** showing the change. Near-GEO median epoch spacing is **0.865
days**, so a confirmable change becomes visible about **1.7 days** after it
happens, and running more often than daily cannot make an alert earlier.

Against a **median causal lead of 36.1 days** at GEO, a daily lane spends
2.8% of its warning budget on latency. **A 2-hourly lane would spend 0.2% and
buy nothing**, because the element sets it would re-read have not changed.
**The registered-equivalent design decision: fire on the existing `:25` timer,
but do work only when the object's newest element-set epoch has advanced.**
That is the same "cadence is a bandwidth decision, not a freshness one"
principle `orbit-release.timer` already states.

---

## 3. What the lane computes, and from what

Nothing new. Every quantity is one this track has already measured and tested.

| Stage | Reuses |
|---|---|
| near-GEO filter | `proximity_geo.py` §3.1 constants, unchanged |
| mean longitude λ, unwrap, drift rate ḋ | `proximity_geo.mean_longitude_deg`, `unwrap_longitude`, `drift_rate_deg_per_day` |
| the trigger | `proximity_geo.drift_change_flags` at the **published** σ_n = 6.0385e-4, threshold `max(5σ_n, 0.010) = 0.010` deg/day, flag time = the **second** consecutive departing element set |
| the feature vector | `alarm_pattern.py`'s **causal subset** (prereg §5): the 23 features available by arrival — but see §4, only the initiation and transit blocks are available at *trigger* time |
| the pattern assignment | nearest centroid of the T8c causal taxonomy, in the standardised space whose constants are frozen with the taxonomy |
| the outcome distribution | counted over the committed `docs/alarm-pattern-features-20260922.jsonl` |

**The lane trains nothing at run time.** The taxonomy, the scaler constants
and the per-class outcome tables are **frozen artifacts** shipped with the
lane and versioned with it. A lane that re-fit its clusters on each firing
would have a pattern vocabulary that drifts silently, and every published
precision figure would be about a model that no longer exists.

---

## 4. The trigger-time problem — SOLVED AND MEASURED [T8d]

T8c's causal taxonomy uses features available **at arrival**. An alert must
fire at **trigger** — the confirmed drift change — which is a median of **36
days earlier**. At that moment the lane possesses the initiation block, the
post-burn kinematic state, the cadence and context blocks, and the forward
geometry its own element set implies. It does **not** possess transit
duration, arrival braking, overshoot or lead time, because they have not
happened.

**[T8d] The third taxonomy has now been built, registered ahead of its
numbers, and measured.** Nineteen features in five blocks plus three
missingness indicators; the forward-geometry block integrates the J22
resonance equation rather than propagating at constant drift, because over a
180-day horizon the omitted term reaches 27.5°. Its 30-day propagation error
is a measured median of **0.408°**. A three-way leakage audit — truncation,
future-mutation, and a quarantined validation path — asserts that no feature
reads anything after the trigger.

**Four consequences, all now measured rather than anticipated:**

1. **[T8d] The taxonomy is k = 2, and it is reproducible.** The registered
   criterion returned two classes at a mean silhouette of **+0.757**, against
   +0.225 for the best alternative k; bootstrap Jaccard **0.633 and 0.620**,
   so **both** classes pass the stability bar that only three of T8c's six
   passed. They are named by the post-burn drift rate, the propagated path
   length, the number of occupied longitudes that path would reach, the size
   of the drift change, and how many of those longitudes share the object's
   plane.
2. **[T8d] Per-class precision exists, and it is what §6 was waiting for.**
   Class 1: **28 of 822 → 3.41% [2.37%, 4.88%]**. Class 0: **73 of 96,962 →
   0.075% [0.060%, 0.095%]**. A 45-fold lift, carrying 27.7% of the true
   alerts in 0.84% of the alert volume — about **twelve alerts a year across
   the whole GEO belt**, at a median **22.1 days** of warning.
3. **The alert still upgrades as the transfer proceeds.** Trigger-time class →
   transit-time class (once the drift plateau is resolvable) → arrival-time
   class. Each is a separate assignment with its own precision figure, and the
   lane publishes **which one** it is quoting. An alert that silently improves
   its own class while keeping a precision figure earned by a different one is
   the exact failure mode this design is built to prevent.
4. **[T8d] §4.3's floor was WRONG, and the correction is the most important
   thing on this page.** This document previously said: *"The trigger-time
   precision floor is already known and is not the taxonomy's. T8a measured
   it: 1,483 relocation alerts over the whole archive, 487 ending in a
   registered event — 32.8% [30.5%, 35.3%]. That is what the lane's first
   message is worth."* **It is not.** T8a's denominator is a
   segment-to-segment longitude change of **≥ 2° that already happened**, with
   a flag inside it. At trigger time no such population exists. The alarm's
   real denominator is the **flag chain**, and T8d measured it:

   | | n | ends in an arrival | precision |
   |---|---:|---:|---:|
   | every confirmed drift change, primary arm | **97,784** | 101 | **0.103%** [0.085%, 0.125%] |
   | all resolvable flag chains | 224,780 | 156 | 0.069% [0.059%, 0.081%] |
   | **class 1 only** | **822** | **28** | **3.41%** [2.37%, 4.88%] |

   **226,422 flag chains over 1959–2026 — about six a year per active
   near-GEO object.** At GEO a confirmed drift change is not a rare event; it
   is what a stationed satellite does routinely, because T8a's 0.010 deg/day
   floor corresponds to roughly 0.78 km of semi-major axis and an ordinary
   east-west correction exceeds it. **Quoting T8a's 32.8% on a trigger-time
   alert is now FORBIDDEN by §7.10.**

---

## 5. False-alarm accounting — inherited, not invented

The lane inherits the Paper B apparatus wholesale. Four requirements, each
traceable to a measurement that has already been published.

### 5.1 Precision is published per pattern class, beside every alert

| | value | source |
|---|---:|---|
| GEO, all relocation alerts | **32.8%** [30.5, 35.3] | T8a §4.1, 487/1,483 |
| GEO, alerts ending in a distinct arrival | 28.8% [26.5, 31.2] | T8a §4.1, 427/1,483 |
| LEO, plane-change alerts (**phasing campaigns**) | **44.1%** [36.7, 51.8] | T8b §4.3, 71/161 |
| MEO | **0.36%** [0.10, 1.32] | T8b §9 — and 2 events is UNDERPOWERED |
| HEO | **0.0%** [0, 0.20] | T8b §9 — **zero events; no alert class exists** |

**[T8d] And the rows an alert would actually print, which are the
trigger-time ones.** The five rows above are all measured on populations
defined by what an object subsequently did; none of them is available when an
alert must fire. These are:

| | value | source |
|---|---:|---|
| GEO, **every confirmed drift change** (primary arm) | **0.103%** [0.085, 0.125] | T8d §3.2, 101/97,784 |
| GEO, **trigger class 1** | **3.41%** [2.37, 4.88] | T8d §5.4, 28/822 |
| GEO, trigger class 0 | 0.075% [0.060, 0.095] | T8d §5.4, 73/96,962 |
| GEO, all resolvable flag chains | 0.069% [0.059, 0.081] | T8d §3.2, 156/224,780 |

**[T8d] Per-class precision is now measured**, and gates B, C, D and E all
failed to fire for it. Every alert quotes **its own class's** figure with its
`n` and its Wilson interval, **and the 0.103% whole-population base rate
beside it**, and says which is which. Wilson intervals throughout, because
`scipy` is not installed on `pc` and the Jeffreys interval T8a registered
could not be computed — T8a §4.1 records that substitution and this lane
inherits it.

### 5.2 Every class with fewer than 20 supporting events is labelled UNDERPOWERED

T8c's gate T fired on a 13-member cluster and T8b's gate D fired on MEO and
HEO. The rule is the same one: a count below 20 is quoted with its n and its
interval and **no rate is drawn from it**.

### 5.3 A labelled gap is never a zero

T8b §5.1 could not draw a null for 8 of 120 LEO arrivals and labelled them
rather than counting them as zero. Same rule here: an object with no usable
look-back, a gap > 5 days across the trigger, or a class with no supporting
events produces **"not assessable"**, never "no risk" and never a blank.

### 5.4 The two structural caveats are printed, not linked

Both appear on the face of every alert:

- **Mean longitude is a slot coordinate, not a miss distance.** Two objects
  sharing a mean longitude are routinely tens of kilometres apart, kept so by
  eccentricity- and inclination-vector separation this track does not model
  (T8a §1.1). **This lane is not a conjunction warning and does not replace
  one** — NASA CARA screens for miss distance and collision probability on a
  fixed cadence, and that is a different estimand for a different consumer
  (prior art must-cite 12).
- **The catalogue is a lower bound, never a census.** A transfer executed
  below 0.010 deg/day is invisible, and 33% of T8a's own events had no visible
  initiating flag. **Absence of an alert is not evidence of absence of an
  approach.**

---

## 6. Vocabulary gating — the word the lane has not earned

`pipeline/orbit_events.py` already solves this problem for the word
**"manoeuvre"**, and the solution is the precedent this lane must copy rather
than improve on:

> the published control stands at **34 flags in 1,941 intervals of objects
> that physically cannot manoeuvre**, against a design target of one in a
> thousand, **and `manoeuvreLabelPermitted` is false because of it**.
> `confidence` is hard-wired to `"candidate"` or weaker, always, and there is
> no code path that produces anything stronger.

`pipeline/orbit_release.py::_label_policy` then computes the permission per
detector basis and per stratum, refuses to let one detector lend certainty to
another, and ships a `reason` string when the word is withheld.

**The lane's vocabulary is gated the same way, with its own ladder:**

| Word | Permitted when | Today |
|---|---|---|
| "drift-rate change of Δḋ deg/day, confirmed at T" | always — it is arithmetic on published elements | **PERMITTED** |
| "matches pattern P" | the class is a **reproducible** cluster (bootstrap Jaccard ≥ 0.5) **and** the trigger-time taxonomy has a measured precision | **[T8d] PERMITTED FOR CLASS 1 ONLY.** Both trigger classes are reproducible (0.633, 0.620) and both have a measured precision. Class 0 stays WITHHELD **not** because it is unmeasured but because it is 0.075% over 96,962 triggers: an alert that fires on 99.2% of all drift changes and is right once in 1,300 is not a warning, and quoting it would be a labelled gap dressed as a result |
| **"this object has previously done X, N times; those ended in Y within D days"** | the per-object predictor beats the population baseline at some prior-event count | **[T8d] WITHHELD — gate H FIRED.** −5.419 [−7.030, −4.348] and no threshold exists. The per-object clause the programme goal asked for is **not supportable for any object in this archive** |
| "N prior instances" | the class has ≥ 20 supporting events (§5.2) | permitted for both trigger classes (822 and 96,962) and for 4 of T8c's 6 arrival classes |
| "arrival followed in D days, median M" | the class's outcome distribution is published beside it, as a **distribution with its spread**, never a point | permitted **as a distribution only** |
| **"manoeuvre"** | `manoeuvreLabelPermitted` is true in the shipped bundle | **WITHHELD — it is false today** |
| **"approach", "approached"** | never for an individual alert. T8a §7.4 and T8b §12.4: corroboration is informative **in aggregate and not per row** | **WITHHELD** |
| any purpose, motive, mission or actor | **never. §7.** | **FORBIDDEN** |

**The lane may not invent a word the shipped detector has not earned.** If
`manoeuvreLabelPermitted` is false, the alert says "drift-rate change",
because that is what was measured.

---

## 7. What the lane must NEVER say

Binding, and test-enforced in the same shape as T8a's, T8b's and T8c's suites
(`tests/test_alarm_pattern.py::TestPolicyGuards` already asserts the last of
these against this document).

1. **No intent, purpose, motive or mission.** The banned vocabulary is the
   one `docs/proximity-priorart-20260922.md` fixes under "Forbidden
   phrasings", and it is referenced rather than copied here **on purpose**:
   one canonical list cannot drift out of step with itself, and a second copy
   would. The machine-readable form of the same list is
   `tests/test_alarm_pattern.py::TestPolicyGuards.BANNED`, which is what
   enforces it against the tool, the feature names and this document. A class
   name is a description of element behaviour and nothing else.
2. **No attribution of purpose to an operator, a programme or a state.**
3. **No per-nation narrative, no country grouping, no registry-code
   aggregate.** Registry codes are metadata. **No detector branch, feature,
   transform, distance, cluster assignment or prediction may read one**, and
   whether they ever appear on a surface at all is §10's operator decision.
4. **No miss distance, no range, no conjunction probability, no collision
   risk.** The estimand cannot support any of them.
5. **No delta-V, propellant, mass or remaining-life figure.** Fuel inference
   is commercial-civil-only under standing policy and is a different track.
6. **No point forecast of dwell duration or of closest separation.** T8c
   measured +0.128 and +0.038; neither licenses a number without its spread.
7. **No "first", no "at catalogue scale", no "validated" before the
   corresponding gate has run** — the prior-art bans, in full.
8. **No claim that an individual event was deliberate.** The corroboration
   flag ranks; it does not assert (T8b §12.4).
9. **No silent suppression of an alert that did not pan out.** The precision
   ledger of §8 counts every alert, including the ones the lane would rather
   forget.
10. **[T8d] No quoting of T8a's 32.8%, or T8b's 44.1%, as the precision of a
    trigger-time alert.** Both are measured on populations defined by what the
    object subsequently did. The trigger-time figures are §5.1's second table
    and nothing else may stand in for them.
11. **[T8d] No sentence about an individual object's own history.** Gate H
    fired. The lane may rank internally on an object's history if it ever
    ships — §1 — but it may not say anything about it, because the only
    calibrated statement T8d could make about it is that it is worse than the
    base rate.

---

## 8. The lead-time budget, and what it sets

The measured numbers, which set every timing decision in the design:

| | GEO (T8a) | LEO (T8b, **in-track phasing**) |
|---|---:|---:|
| median causal lead | **36.1 d** | **195.9 d** |
| p25 – p75 | 10.6 – 96.0 d | 70.5 – 473.9 d |
| p95 | 162.7 d (right-censored) | 917.5 d |
| fraction with a confirmable initiating change | 66.9% | 100% |
| precision | 32.8% | 44.1% |
| look-back the detector needs | 180 d — **too short**, it censored the distribution | **1,095 d**, censored 1.4% |

**Four consequences:**

1. **The lane's look-back is 1,095 days, at GEO as well as in LEO.** T8b §12.3
   made this a standing requirement of the track, and T8a's undeclared blind
   spot is the reason. At GEO the cost is trivial: 1,768 objects × 3 years of
   element sets is seconds by the primary key.
2. **An alert's useful life is its class's lead-time distribution**, and it
   expires by arrival, by departure, or at the class p95 — whichever comes
   first. An alert that never resolves is counted as a miss, not dropped.
3. **A GEO alert is worth issuing the day it is confirmable.** At a 36-day
   median and a 10.6-day p25, a week of latency is a quarter of the warning
   for the fastest quartile. §2.3's daily cadence costs 2.8%.
4. **LEO's 196 days is not five times more warning; it is a different
   quantity.** It is the lead time of an **in-track phasing campaign inside an
   already-shared plane**, because T8b's registered plane-noise statistic came
   back 145× too large and blinded the plane channel (T8b §2.3). **Any LEO
   arm of this lane inherits that qualification in the alert text itself**,
   and a LEO arm should not be built until the plane-noise floor is re-derived
   (T8b §11's added item).

**And the honest counterweight.** The interval between an approacher's
successive events has a median of **90 days with a p25–p75 of 34–730 days**
(T8c §4.3, E4). The "within ~D days" clause of the programme goal is, on
today's measurements, **a range spanning more than an order of magnitude**.
The design's answer is to quote the range and the count, never a single D.

---

## 9. What T8c's null changes about this design

Gate P fired. Four specific design consequences, each traceable to a number:

1. **The pattern refines; it does not predict.** The alert's outcome clause is
   a **class-conditioned distribution published with its spread and its n**,
   never a forecast. (E1a +0.128 vs baseline +0.137.)
2. **The lane must carry the object's own history beside the class.** The
   cheapest combination of the two beat the baseline by +0.069 where the class
   alone did not beat it at all (post-registration diagnostic D2, +0.206
   [0.127, 0.272]). **That diagnostic is not a result and may not be cited as
   one**; what it licenses is the design choice to keep both, and a T8d
   registration that fixes the combination rule before its number exists.
3. **Two of the six classes are not classes.** Clusters 1 and 4 recover below
   0.4 of their members under bootstrap resampling. The lane ships **four**
   pattern names, and an event assigned to an unstable class is reported as
   "no stable pattern match" — which is a labelled gap, not a zero.
4. **A large part of what the classes know is whether the burn was visible.**
   Restricted to the 326 events that carry a confirmed initiating change, the
   taxonomy's skill is **+0.001** (T8c §5). So the lane's pattern clause is, in
   substantial part, re-reporting a property of the **detector**. The design's
   response is that **the alert says which**: the initiating change is quoted
   as a measured quantity with its epoch, and the pattern is quoted as a match
   count — the reader can see that the first is the evidence and the second is
   the context.

---

## 10. Operator decisions, reserved and not taken here

None of the following is decided in this document, and no part of the design
assumes an answer to any of them.

1. **Publication surface.** Whether this lane has any public surface at all;
   if it does, whether it is a page, a feed, a file, or an operator-only
   console. **Nothing is on any site today and nothing may be.**
2. **Framing.** Whether the lane is presented as space-situational-awareness
   context, as a research instrument, as a teaching surface, or not at all.
   The framing difference between this track (ownership-agnostic mathematics)
   and the CSIS/SWF literature (named-actor narratives) is a legitimate point
   of departure to state plainly, and stating it is a publication choice.
3. **Whether catalogue registry codes ever appear** — on an alert, in an
   aggregate, in a filter, or nowhere. The instrument reads none today and the
   tests keep it that way; making them visible is a decision, not a feature.
4. **Whether object names appear**, or only NORAD numbers.
5. **Notification.** Whether an alert ever leaves the machine — email, a
   channel, a file — and to whom. The standing estate rule that maintainers
   are never emailed is not the question; the question is whether anything is
   sent at all.
6. **Whether the LEO arm is built**, given §8.4's qualification.
7. **Retention.** How long the precision ledger of §5 is kept and whether it
   is published.

---

## 11. What would have to be built, in order, before anything runs

Stated so that the cost of the goal is visible rather than implied. **None of
this is started.**

1. ~~**A registration for the trigger-time taxonomy**~~ — **[T8d] DONE.**
   `docs/trigger-alarm-preregistration-20260922.md`, committed alone as
   `154c53f` before any measurement code existed.
2. ~~**Per-class precision**~~ — **[T8d] DONE.** Every alert the trigger-time
   detector would have raised over 1959–2026 — **226,422 flag chains,
   97,784 in the primary arm** — classed and followed to an arrival or to
   nothing. §5.1's second table.
3. **A frozen-artifact format** for the taxonomy, the scaler constants and the
   outcome tables, versioned so that a published precision figure names the
   model that earned it.
4. **The sidecar itself** — a read-only timer job, a state file, an alert
   ledger, and the vocabulary gate of §6 implemented as a function that
   *returns* the permitted words rather than as a convention.
5. **The alert ledger's own audit**: every alert, its class, its resolution,
   and the running precision, so that §5.1's figures are measured on this
   lane rather than borrowed from T8a's offline run.
6. **A synthetic exercise before anything is scheduled.** The estate rule is
   that a lane which runs later is exercised now: the sidecar would be driven
   over a **replay of a historical window** with an injected clock, and the
   alerts it produces compared against the committed event catalogue, before
   any timer is installed. Nothing in this document has been exercised,
   because nothing in it has been built.

---

## 12. Reproduction of the numbers this design quotes

Every figure above comes from a committed measurement. None was computed for
this document.

```
docs/proximity-results-20260922.md          §1.1, §4, §4.1, §5.5, §7.4
docs/proximity-leo-results-20260922.md      §2.3, §3.3, §4, §4.3, §9, §11, §12
docs/alarm-pattern-results-20260922.md      §0, §3.2, §3.3, §3.5, §4.2, §4.3, §5, §6
docs/trigger-alarm-results-20260922.md      §0, §3.2, §3.3, §3.4, §4, §5.1-5.5, §6.1-6.3, §8   [T8d]
docs/trigger-alarm-preregistration-20260922.md   §3, §4, §6, §8, §11                           [T8d]
docs/SYSTEM-MAP.md                          §6 (the timer and the 20-hour floor)
pipeline/orbit_events.py                    the passive control, 34/1,941
pipeline/orbit_release.py::_label_policy    the permission machinery
```
