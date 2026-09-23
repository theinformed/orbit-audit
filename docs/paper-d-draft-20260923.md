# A public, audited record of orbit changes: episodes, their reading, and the numbers that license every entry

**Sean D. Egan and Derek Conklin**
*The Informed — theinformed.org. Corresponding author: sean@theinformed.org*

Preprint, 23 September 2026.

<!--
AUTHORS' COMMENT — PROVENANCE.
Every numeric claim is followed by an HTML comment naming the committed
repository document, receipt or artifact it was taken from. Nothing was
recomputed while drafting. Primary sources:
  docs/orbit-changes-record-20260923.json      (a count of the published record)
  docs/orbits-section-design-20260922.md       (what the surface shows)
  docs/change-ledger-and-reading-design-20260922.md (episodes and the reading)
  docs/kinematic-inputs-results-20260922.md + -20260922.json  (M0, M1, M2)
  docs/manoeuvre-library-results-v2-20260922.md + -v2-20260922.json
  docs/t16b-truthset-results-20260922.md + -recall-20260922.json
  docs/t18-floor-results-20260922.md + t18-floor-20260922.json
  docs/t21-differential-results-20260923.md + -20260923.json
  docs/t22-scheduled-null-results-20260923.md + -receipt.json
  docs/t19-covariance-realism-results-20260923.md
  docs/proximity-results-20260922.md + -20260922-receipt.json
  docs/proximity-leo-results-20260922.md + -20260922-receipt.json + -events.jsonl
  docs/trigger-alarm-results-20260922.md + -20260922-receipt.json
  docs/alarm-lane-build-20260922.md + alarm-lane-operating-points-20260922.json
      + alarm-lane-replay-20260922-receipt.json + alarm-lane-leo-replay-*-receipt.json
  docs/geo-libration-epoch-control-results-20260922.md + -receipt.json
  docs/t27-per-object-noise-results-20260923.md
  docs/t28-geo-sign-control-results-20260923.md
  docs/research-program-runbook-20260921.md    (the deployment record, T12)
A small number of comments are marked `derivation:` rather than `src:`. Those
are arithmetic performed for this draft — quotients and sums — from numbers that
are themselves traced. They are marked so that no reader mistakes a derivation
for a receipt.
Scoping language follows the committed adversarial prior-art sweeps of
2026-09-20 and 2026-09-22. The phrases "first at catalogue scale", "first open
catalogue of GEO approach events", "first quantification of early-warning lead
time", "physically guaranteed", "proves operators avoid proximity" and "shows
deliberate avoidance" are forbidden and do not appear. Neither does any
intent, purpose, threat or actor vocabulary, and no catalogue registry code
appears anywhere in this paper.
-->

---

## Abstract

This is a measurement paper about a public record. The record is a browsable ledger of orbit changes, published from a catalogue of two-line element sets, in which the unit is an **episode** rather than an event: a change opens when an object's elements depart its own baseline beyond a derived floor, is *in progress* while they are still moving, and *completes* when they have held still for a derived dwell. Every entry carries an initial state, a current state, a lifecycle state, and a four-line reading whose every clause is either a measured figure with its interval or a printed statement of the measurement that is missing. The record as published holds **1,992 episodes assembled from 2,058 detected change steps, with 130 steps that opened no episode counted rather than dropped** <!-- src: docs/orbit-changes-record-20260923.json, episodes 1992, changeSteps 2058, stepsWithoutEpisode 130 -->.

Four numbers govern what such a record may say, and we report them together because separately each one flatters. **Detection recall, against 1,134 operator-reported manoeuvres on eleven geodetic and altimetry spacecraft, is 7.94%, Wilson 95% [6.50, 9.66]** — an outlier on the low side of published recalls on overlapping spacecraft, for a reason the same measurement identifies: 977 of those 1,134 burns move the semi-major axis by less than the 102.2 to 126.0 m the shipped threshold requires <!-- src: docs/t16b-truthset-results-20260922.md, sections 0 and 3.1-3.3 -->. **Two thirds of what the detector does catch is reachable from the archive's sampling schedule alone**: a model shown nothing but the timing of the element sets recovers 58 of the detector's 90 hits at the same false-flag rate, a recall of 5.115% [3.977, 6.555] against the detector's 7.937% <!-- src: docs/t18-floor-results-20260922.md, section 0 -->. **The propagated path that lets the record say what a change reaches is resolvable to +20 days and no further**: the measured median forward error crosses the 0.100 degree co-location tolerance at +15 days and the measured 0.394 degree median spacing of occupied longitudes at +30 days <!-- src: docs/kinematic-inputs-results-20260922.md, sections 0 and 2.5 -->. And **an alarm built on the record's own triggers is right 0.103% of the time**, [0.085, 0.125], over 97,784 historical firings; its single reproducible class reaches 3.41% [2.37, 4.88] at a 45-fold lift and a median 22.1 days of warning <!-- src: docs/trigger-alarm-results-20260922.md, section 0 -->.

Two structural limits bound everything above and are printed on the record itself. The first is that **the geostationary belt admits no leak-free passive control, and the reason is physics**: a stationed object that is not being controlled is a free librator, a slow librator dwells near occupied longitudes for months, and the approach detector's own registered dwell criterion is therefore met by motion no one commanded. Measured on 517,391 object-days of provably uncontrolled motion — 30.9 times the exposure one expected event requires — the approach detector fires at 1.845 times the active-payload rate [1.377, 2.431] and the trigger detector at 0.288 [0.279, 0.298], against a registered bar of 0.10, with none of nine pre-specified readings leak-free <!-- src: docs/geo-libration-epoch-control-results-20260922.md, sections 0, 4 and 5 -->. The second is that **the alerts are a research instrument and not a warning product**: no timer runs, every alert on the public surface is a labelled replay of 2010 to 2020 on an injected clock, and the low-orbit arm publishes its own withheld gate rather than an alert, because its passive control fires at 0.797 of the rate it fires on objects that can manoeuvre against a design target of 0.001 <!-- src: docs/alarm-lane-build-20260922.md, sections 6 and 7.2 -->.

The record refuses to name a purpose, a target or a nation, and we report that refusal as a design result rather than as a limitation: what the surface can say is fixed by what has been measured, and every clause it cannot fill prints the measurement it is waiting for.

---

## 1. Introduction

### 1.1 Why a public record of orbit changes needs its own audit

A catalogue of orbital element sets is public, free, continuous and old. Anyone may difference it and get a list of things that changed. The difficulty is not producing the list; it is saying anything true about an entry on it.

Three properties make that hard, and all three are properties of the instrument rather than of the sky. A step detector run on fitted elements flags catalogue noise, observation gaps and re-fits alongside real manoeuvres. A detector's sensitivity floor is set by whatever noise statistic it was calibrated on, so the population it can see is a property of that calibration and not of what operators do. And a geometric criterion — two objects sharing a slot, two orbits sharing a plane — is satisfied by natural motion as readily as by commanded motion, which means the interesting fraction of any such catalogue is decided by a control that has to be built rather than assumed.

A record that publishes such a list to readers therefore owes them more than the list. It owes, per entry, the floor the entry cleared; the rate at which the same arithmetic fires on objects that cannot manoeuvre; the horizon beyond which its own forward path stops resolving; and, where a rate is quoted, the denominator it was measured against. This paper is the audit of a record that carries those four things, and it reports the numbers that license every entry on it, including the several that are unflattering.

The record is published at a public address as a section of an existing teaching surface, and the deployment is itself a committed record: 1,992 index rows, a 1,551-object belt file, 272 replay alerts, four operating points and 628 per-event files, served from a content-addressed manifest <!-- src: docs/research-program-runbook-20260921.md, T12 row, "DEPLOYED 2026-09-22T21:39Z, commit abbb153" -->.

### 1.2 What the surface refuses to say, and why that is a design result

The record contains no statement of purpose, no attribution of an object to an operator's intention, no per-nation aggregate, and no registry or country code in any artifact, row, list or filter. That absence was verified by a field walk over all four published artifacts and a search of the shipped bundle rather than asserted <!-- src: docs/research-program-runbook-20260921.md, T12 row, and the deployment's own verification table -->. It also holds inside the instruments: no detector, gate, feature, transform, distance, assignment, renderer or query in the alarm lane reads a registry code, and a word-boundary test asserts that those words appear only inside the lane's own never-say list <!-- src: docs/alarm-lane-build-20260922.md, section 10 -->.

We put this in the introduction rather than in the limitations because it is a result about what the measurements support, not a policy about what we prefer to publish.

Consider what a per-nation aggregate would require. It would require, first, that the event catalogue be a census rather than a lower bound; it is not — 161 of 487 near-geostationary approach events, 33%, have no confirmable initiating change at all <!-- src: docs/proximity-results-20260922.md, section 4 -->, and the low-orbit catalogue is explicitly a lower bound because its plane channel was switched off by a bad noise floor <!-- src: docs/proximity-leo-results-20260922.md, section 10 -->. It would require, second, that the detector's sensitivity be uniform across the population being compared; it is not — recall varies from 0.0% to 20.0% across eleven cooperative spacecraft purely as a function of their own burn sizes <!-- src: docs/t16b-truthset-results-20260922.md, section 3.4 -->. And it would require, third, a control; at the geostationary belt there is none (§5.5). An aggregate assembled over a lower bound with non-uniform sensitivity and no control is a number about the instrument wearing the costume of a number about the world.

The same argument disposes of intent. The per-object predictor that would license a sentence about an individual object's habits was registered in advance and measured: it is worse than the population base rate at every prior-event count, in every stratum, and the registered gate fired <!-- src: docs/trigger-alarm-results-20260922.md, section 6.2 -->. The record therefore says nothing about any object's own past, and the surface's string table is generated from the frozen model's permitted clause words so that the page has no vocabulary of its own <!-- src: docs/orbits-section-design-20260922.md, section 3 -->.

What is left after those refusals is narrow and checkable: which public element sets changed, by how much, what the same arithmetic has done before, how often it ended beside another object, and — printed in the same breath — how often it is wrong.

### 1.3 Prior art, and what is and is not ours

Two committed adversarial sweeps govern the scoping language here, and both were written to be unflattering.

**Occupied: the control idea and the scale.** Using a physically passive class as a no-manoeuvre reference is a granted patent (Tack & Nezda, 2023). Catalogue-scale processing of element sets is published (Lemmens & Krag, 2014; Fu, 2026). Neither is claimed, and the phrase "first at catalogue scale" does not appear in this paper <!-- src: docs/proximity-priorart-20260922.md, Claim 4 and the forbidden-phrasings list -->.

**Occupied, and this is the correction that matters most for §4.** Recall of a detector against mission-published manoeuvre histories has been measured and published repeatedly, on the same spacecraft this paper measures: Kelecy et al. (2007) report roughly 95% detection at a 6% false-detection rate on an energy channel and 85% at 7% on an inclination channel; Decoto and Loerch (2015) recover all eight reported manoeuvres of one spacecraft from public elements with two false positives; Cipollone, Raviola and Di Lizia (2025) publish full precision and recall against operator histories with per-spacecraft recalls from 0.35 to 1.000; and Shorten et al. released a fifteen-satellite ground-truth benchmark with threshold-swept precision-recall curves. **Against those, this paper's 7.94% is a low outlier, and no priority is claimed for it** <!-- src: docs/oh-wow-assessment-20260922.md, section 2, first row, and section 4 -->.

**Occupied in direction for the taxonomy.** Classification of geostationary manoeuvres from public elements, with published confusion matrices, is in print (Roberts, 2021), as is behavioural clustering of 918 geostationary satellites over a decade (Roberts et al., 2023) and a released labelled pattern-of-life benchmark (Siew et al., 2023). Station-keeping cadence at the fourteen-day line, and deadbands read off element-derived longitude histories, are likewise published, including a modal manoeuvre interval measured across 1,707 geostationary objects (Pastor et al., 2021). §3 makes no novelty claim for its type set.

**Adjacent, narrower, and better controlled at small N.** An evidence-tiered, cross-source-verified manoeuvre ground-truth dataset for low orbit exists and is the label set §4 measures against (Guo et al., 2026). It validates individual manoeuvre labels; it does not address approach detection, and its own element-set noise floor of about 24 m against a median real response of 20.3 m makes the same point §4.1 makes from the other side <!-- src: docs/oh-wow-assessment-20260922.md, section 2 -->.

**Not located by either sweep, stated as a limit of the search and never as a proof of originality.** No published lead-time distribution for approach detection from a public element archive was found by two independent sweeps; the best public precedent located is anecdotal, on the order of ten days for a single named event pair. No published chance-co-location null for relocation behaviour was found. No standing, published, gating false-alarm audit applied to an *approach* detector — one that runs a never-manoeuvred control through the identical detector, reports its leak against the same exposure denominator, and publishes the failure — was found <!-- src: docs/proximity-priorart-20260922.md, Claims 1, 2, 3 and 4 -->. The defensible phrasing, and the one used throughout, is "the only one this search located".

The gap this paper occupies is therefore narrower than the record itself: **a public record of orbit changes in which every entry's licence is a committed measurement, the measurements that do not exist are printed as gaps, and the audits that fired are published at the prominence of the results they contradict.**

### 1.4 Contributions

1. **The record (§2).** Episodes rather than events, with a state machine whose thresholds are derived from the archive's own measured noise; a four-line reading in which every clause is either a measured figure or a printed gap; and a forward horizon cut to what the forward error actually resolves.
2. **The type library (§3),** its agreement matrix against other instruments, and the five types that may carry a confidence against the several that may not — including one type that may not be treated as propulsive at all.
3. **The detection floor and the recall (§4),** placed beside the published recalls it is an outlier against, together with the two measurements that explain it: that the working floor is set by real non-manoeuvre variation rather than by noise, and that two thirds of the recall is reachable from the sampling schedule alone.
4. **The approaches and the alarm (§5),** with every gate that fired printed: the near-geostationary control that leaks at parity, the low-orbit control that returns exactly zero on 18.79 million object-days, the trigger-time denominator correction from 32.8% to 0.103%, the finding that tightening the evidence dial does not raise precision, and the low-orbit alarm arm withheld by its own control.
5. **A statement of what the record cannot say (§6)** in which each refusal is tied to the measurement that forces it.

### 1.5 Who a record like this is for

The same three-form argument the companion papers make applies here and is not repeated at length. Government situational awareness is restricted; commercial awareness is accurate, proprietary and priced for institutions; compliance reporting is public, annual and retrospective. What is missing is free, continuous, catalogue-scale activity characterisation carried alongside a published error rate.

This paper adds one clause to that framing, and it is the clause the rest of the paper is about. A public record of orbit changes is legible to a student, a journalist and a small operator for exactly the reason it is usable at all: **the interval estimates, the abstentions and the blocking reasons are visible on the entry they govern.** Where the record cannot support a statement it prints the sentence that says so, and the sentence names the measurement that is missing. That is not a decoration on the data product; on this record it is most of the data product, because most clauses are currently gaps.

---

## 2. The record

### 2.1 Episodes, not events

The operator's brief for the surface asked for a ledger that a reader can scroll, click into, and inspect — and, crucially, that distinguishes a change that has finished from one that is still happening. That distinction is the unit.

A **change episode** opens when an element set departs the object's own pre-change baseline beyond a registered floor; it is **in progress** while the elements are still trending; and it **completes** when they have held still for a registered dwell. Each state carries an *initial* — the baseline the detector itself used — and a *current*, which is the newest element set while the episode is open and the settled state once it is closed <!-- src: docs/change-ledger-and-reading-design-20260922.md, sections 0 and 1.2 -->.

Two further fields are carried beside the state and are not states: a *closure* in {open, settled, lapsed} and a *reopened* count. A **lapsed** episode is one whose object stopped being tracked before it completed — a tracking gap of 3 days or more, a decay below 200 km of perigee, or the end of the archive. It keeps its last state, greyed, with the stamp *tracking ended*, and it is never promoted to completed <!-- src: docs/change-ledger-and-reading-design-20260922.md, section 1.2 -->.

The record as published holds 1,992 episodes assembled from 2,058 detected change steps <!-- src: docs/orbit-changes-record-20260923.json, episodes 1992, changeSteps 2058 -->:

| | count |
|---|---:|
| episodes | 1,992 |
| …initiated | 119 |
| …in progress | 20 |
| …completed | 1,853 |
| closure settled / open / lapsed | 1,853 / 133 / 6 |
| episodes reopened at least once | 0 |
| kind: impulsive / campaign / onset not observed | 1,760 / 71 / 161 |
| regime: low orbit / geostationary / high-eccentricity / medium orbit / transfer / near-geostationary | 1,211 / 491 / 227 / 35 / 19 / 9 |
| ladder stage assigned / none | 500 / 1,492 |
| routine-check verdict measured | 0 |
| detected steps | 2,058 |
| …from the catalogue step detector | 1,500 |
| …slot co-locations, near-geostationary | 487 |
| …co-orbital stations, low orbit | 71 |
| **steps that opened no episode** | **130** |

<!-- src: docs/orbit-changes-record-20260923.json: episodes, byState, byClosure, reopenedEpisodes, byKind, byRegime, byStage, byVerdict, changeSteps, changeStepsByFamily, stepsWithoutEpisode -->

Three of those rows are the substance of this section and each is discussed below: the 130 steps that opened nothing, the 161 episodes whose onset was never observed, and the 1,992 rows whose routine-check verdict is *unmeasured*.

The record is a function of the archive up to a stated instant rather than a state file: it is recomputed each run from the registered instruments' outputs, with the present moment injected, so that the replay used to exercise it and the live product are the same function <!-- src: docs/change-ledger-and-reading-design-20260922.md, section 4.2 -->. The published record runs to 2026-09-22T17:13:02Z <!-- src: docs/orbit-changes-record-20260923.json, recordToMs 1790097182667 -->.

That instant is itself a measurement rather than a clock reading, and the reason is a defect the surface's own pixel review caught. The record's "to" date is the largest update time on any episode; an open episode takes the build's present moment as its update time; and that present moment was originally the newest epoch in the archive. But a general-perturbations element set is a fit with a reference time, and a small number are issued ahead of the moment they are published: on 2026-09-22, ten of the archive's 68,089 objects carried an epoch the clock had not reached, the furthest on 2026-09-26, so the header said the record ran two days into the future <!-- src: docs/research-program-runbook-20260921.md, T12 row, and the deployment's own account of the defect -->. The present is now the newest epoch the archive holds *that the clock has already reached*. We report this because it is the kind of defect no unit test finds and no reader could detect, and because the forward-dated element sets are still read by every window that spans them — they simply no longer decide what "now" means.

![What the record holds and what it refused to open. Left: the 2,058 detected change steps by the family of instrument that produced them, with the 130 that opened no episode drawn as a bar of its own rather than folded into the total. Right: the 1,992 episodes by lifecycle state (upper three rows) and by kind (lower three). Every count is a tally over the published record's own rows; nothing in this figure is a measurement.](latex/paper-d/figs/record-states.pdf)

<!-- figure: docs/latex/paper-d/figs/record-states.pdf, drawn by tools/make_figures.py from docs/orbit-changes-record-20260923.json: changeSteps, changeStepsByFamily, stepsWithoutEpisode, episodes, byState, byKind -->

### 2.2 The state machine, and thresholds that are derived rather than chosen

No threshold in the state machine is a round number someone liked. Each is either the archive's own measured noise or a constant already registered by the instrument that supplies the episode's onset.

**Onset, near-geostationary.** A confirmed drift-rate flag chain: a departure of at least `max(5σ_d, 0.010)` degrees per day from the trailing baseline, confirmed at the second consecutive departing element set, with chains merged within 5 days <!-- src: docs/change-ledger-and-reading-design-20260922.md, section 1.1 -->. The drift-rate noise floor is measured, not assumed: σ_d = 0.0006039 degrees per day, from the median absolute deviation of consecutive differences inside stationed segments over 3,740,056 consecutive pairs <!-- src: docs/proximity-results-20260922.md, section 2.2 -->. Five times that is 0.0030 degrees per day, so **the derived physical floor of 0.010 dominates and the noise calibration never binds the detector** — which is worth saying plainly, because a floor set by a physical argument and a floor set by a noise statistic fail in different ways. That floor corresponds to about 0.78 km of semi-major axis <!-- src: docs/proximity-results-20260922.md, section 2.2 -->.

**Onset, outside the geostationary band.** The shipped step detector's candidate events, at a multiplier of 8 on the object's own residual scatter with a two-day persistence rule and a cohort screen <!-- src: docs/change-ledger-and-reading-design-20260922.md, section 1.1 -->.

**Routine keeping must not open an episode.** An object whose drift rate stays inside the stationed band — 0.020 degrees per day, which is six times 0.1 degrees over 30 days — opens nothing, and neither does north-south keeping without a drift change <!-- src: docs/change-ledger-and-reading-design-20260922.md, section 1.1 -->. This is the clause that keeps the ledger from becoming a list of every station-keeping burn in the belt, and §5.2 measures how large that list would be.

**Completion.** Near the geostationary band, a new station segment: drift inside 0.020 degrees per day and mean longitude inside ±0.3 degrees for 30 days — the same rule that defines a station everywhere else in this programme. Outside it, the trend test returns "still" for three consecutive five-day blocks, which is the shortest baseline the step detector itself will screen against; shorter, and the completed state would be measured against noise it cannot yet size <!-- src: docs/change-ledger-and-reading-design-20260922.md, section 1.4 -->.

**Re-opening rather than double-counting.** A confirmed step arriving after completion but inside the campaign window re-opens the same episode instead of opening a new one, and the re-open count is the false-completion rate, measured rather than guessed <!-- src: docs/change-ledger-and-reading-design-20260922.md, section 1.4 -->. On the published record that count is **zero across all 1,992 episodes** <!-- src: docs/orbit-changes-record-20260923.json, reopenedEpisodes 0 -->. We report that as a count and not as a verdict: the measurement that would turn it into one — an episode-state classifier run over a replay, with the false-completion rate at the registered dwell and at twice it — has a registration and no result, which is why the record's own header prints that state rates are unmeasured <!-- src: docs/change-ledger-and-reading-design-20260922.md, section 5, M8; docs/orbit-changes-record-20260923.json, stateRatesMeasured false -->.

### 2.3 What opened nothing, and what opened with no onset

**130 of the 2,058 detected steps opened no episode**, and the record counts them rather than dropping them <!-- src: docs/orbit-changes-record-20260923.json, stepsWithoutEpisode 130 -->. They divide cleanly: 59 come from the catalogue step detector and 71 from the low-orbit co-orbital station catalogue <!-- src: docs/orbit-changes-record-20260923.json, stepsWithoutEpisodeByFamily -->. The second group is structural rather than anomalous — the 71 co-orbital stations are carried as the 71 **campaign** episodes of the record and are not, in addition, steps that opened an episode of their own <!-- derivation: byKind campaign = 71 equals stepsWithoutEpisodeByFamily leoStation = 71, from docs/orbit-changes-record-20260923.json; the identity is arithmetic on that file and is stated here as such -->.

The complementary failure is a change whose *onset* was never seen. 161 episodes carry the kind `onset not observed` <!-- src: docs/orbit-changes-record-20260923.json, byKind, not-observed-onset 161 -->. These are arrivals with no open episode: the record writes them with an onset of *not observed* and an initial state taken from the object's last station, as a labelled gap <!-- src: docs/change-ledger-and-reading-design-20260922.md, section 1.6 -->. The mechanism is measured elsewhere in this programme and it is not small: 33% of the near-geostationary approach catalogue had no visible initiating flag inside the look-back <!-- src: docs/proximity-results-20260922.md, section 4 -->, and §4 measures the floor that makes that so.

One failure mode has no instrument at all and the record says so on its face. The programme's only continuous-thrust detector is confined to the drag regime — it requires at least four five-day blocks, at least 80% agreement in sign, a median block rate above eight times its own standard error, and it is gated to an apogee at or below 1,400 km, where a passive sweep produced zero claims on 10,020 non-propulsive objects <!-- src: docs/change-ledger-and-reading-design-20260922.md, section 1.1 -->. Above that ceiling there is nothing: an electric orbit raise appears in the record only if a step happens to trip, and the surface prints *continuous changes above 1,400 km are not detected by this record* <!-- src: docs/change-ledger-and-reading-design-20260922.md, section 1.6 -->. The scale of the miss is measured on one transfer, where the step detector saw 91 of 2,176 metres per second <!-- src: docs/change-ledger-and-reading-design-20260922.md, section 1.6 -->.

### 2.4 The reading: four lines, and the gap strings that fill most of them

At onset and at every state change the record prints a **reading**: four lines in a fixed order, every slot filled from a measured field by a template. There is no generated prose and no optional decoration, which is what makes the gate on the wording enforceable — nothing composes a sentence, so nothing can slip one past a check <!-- src: docs/change-ledger-and-reading-design-20260922.md, section 2 -->.

**R1, the type.** The change's type from the library of §3, with that type's published agreement figure and its support count. Where a type has fewer than twenty matched changes the line prints that instead of a figure; where the library's agreement table has not been measured for a type, the line prints *Type: not yet labelled. The library's agreement table has not been measured.* <!-- src: docs/change-ledger-and-reading-design-20260922.md, section 2.1 -->

**R2, the routine check.** Whether the change is consistent with a pattern this class of object has shown before, with the count of times it has been seen. When it is not consistent, the line names the feature, its value, the class range it falls outside, and the rate at which routine objects of that class exceed that deviation. When the pattern baselines have not been measured, it prints *Routine check: not yet measured*. **On the published record this line is a gap on every one of the 1,992 episodes**: the verdict field reads `unmeasured` for all of them <!-- src: docs/orbit-changes-record-20260923.json, byVerdict, unmeasured 1992 -->.

**R3, the reach.** Printed only when R2 is *not routine* or *not measured*. It gives the number of catalogued objects whose stations the change reaches inside the horizon, the ladder stage, and that stage's measured precision with its Wilson interval — followed, verbatim, by the sentence *No figure exists for any particular satellite.* Above the first rung the line prints *no number until the replay* <!-- src: docs/change-ledger-and-reading-design-20260922.md, section 2.1 -->. On the published record, 500 of the 1,992 episodes carry a stage at all, and every one of those is the first rung <!-- src: docs/orbit-changes-record-20260923.json, byStage, S1 500 -->.

**R4, the denial.** Two structural caveats and a statement of what the section is not, printed byte for byte on every reading, every labelled gap and every alert: that mean longitude is a slot coordinate and not a miss distance, so this is not a conjunction warning; that the catalogue is a lower bound, so absence of an entry is not evidence of absence; and that the section is ownership-agnostic arithmetic on public element sets which attributes no purpose to anyone <!-- src: docs/orbits-section-design-20260922.md, sections 3 and 4 -->.

The proportion matters more than the templates. Of the four lines, one is currently a gap on every episode, one is a gap above the first rung on every episode, and the two that are filled are a type and a denial. **A record whose reading is mostly gaps is the honest state of this instrument**, and the gaps are printed with the identifier of the measurement each is waiting for so that a reader can tell a missing number from a small one.

### 2.5 The horizon: +20 days, and the bands that fixed it

The record draws, for a near-geostationary object, the path its mean longitude would follow if it did nothing further. That path is an integration of the resonant equation of motion rather than a straight line, and the difference is not a correction: a constant-drift propagation omits a term reaching 27.5 degrees at a 180-day horizon <!-- src: docs/trigger-alarm-results-20260922.md, section 4 -->.

The path's error was measured rather than assumed. Over 49,318 triggers with no further flag inside 30 days and an element set at the far end, the median error at +30 days is 0.408 degrees, p75 0.898 and p95 2.080 <!-- src: docs/trigger-alarm-results-20260922.md, section 4 -->. That measurement was then extended to nine further horizons under its own registration, and the extension reproduced the published figure exactly as its first gate required: 49,318 triggers and a median of 0.40836 degrees <!-- src: docs/kinematic-inputs-results-20260922.md, section 2.1 -->.

| horizon (days) | qualifying triggers | median (deg) | p75 | p95 |
|---:|---:|---:|---:|---:|
| 5 | 158,758 | 0.0365 | 0.0897 | 0.551 |
| 10 | 131,987 | 0.0817 | 0.203 | 0.865 |
| 15 | 96,631 | 0.1406 | 0.356 | 1.183 |
| **20** | **73,970** | **0.2027** | **0.485** | **1.441** |
| 30 | 49,318 | 0.4084 | 0.8982 | 2.080 |
| 45 | 33,720 | 0.8154 | 1.592 | 2.653 |
| 60 | 24,373 | 1.0762 | 2.074 | 3.720 |
| 90 | 15,664 | 1.5197 | 3.862 | 7.345 |
| 120 | 11,501 | 1.9244 | 6.306 | 12.34 |
| 180 | 6,882 | 2.6514 | 12.06 | 25.77 |

<!-- src: docs/kinematic-inputs-results-20260922.md, section 2.2, Arm A -->

The qualifying set shrinks by a factor of 23 from the first row to the last, which is why the registration demanded a second arm: the 6,193 triggers that qualify at every primary horizon, re-measured on that one fixed set. **The two arms agree to within 18% at every horizon, and the matched cohort is slightly worse at +30 days than the full set — 0.481 against 0.408** <!-- src: docs/kinematic-inputs-results-20260922.md, section 2.3 -->. The growth is therefore a property of the propagation rather than of which objects stayed quiet, which is the confound the second arm existed to catch, and its not materialising is itself the finding.

Three screens then decide the horizon, and each is a measured or registered quantity rather than a preference. The co-location tolerance the estimand is defined at is 0.100 degrees. The median gap between adjacent occupied longitudes, measured at the archive's final epoch over the 538 objects the lane's own eligibility proxy calls stationed, is 0.394 degrees, with quartiles 0.155 and 0.905 and a p95 of 2.005 <!-- src: docs/kinematic-inputs-results-20260922.md, section 2.4 -->. And the registered bar above which the forward geometry is declared unfit is 2.0 degrees. The Arm A median crosses them at +15, +30 and +180 days respectively <!-- src: docs/kinematic-inputs-results-20260922.md, section 2.4 -->.

Applying the registration's own decision rules to that table gives the two horizons the record draws to:

**Set membership is resolvable to +20 days.** Beyond it the median forward error exceeds the median gap between occupied longitudes, so the path cannot distinguish one candidate longitude from the next — the *membership* of the reachable set, not merely its timing, is unresolved.

**Arrival timing may be stated to co-location precision only to +10 days.** At +15 days the median error is already 1.4 times the 0.1-degree tolerance the estimand is defined at <!-- src: docs/kinematic-inputs-results-20260922.md, section 2.5 -->.

Two consequences are carried onto the surface. The error bands beyond +30 days may now be drawn as measured bands rather than hatched as unmeasured, **but the path itself still stops at +20 days**, because beyond that the ribbon is wider than the belt's own slot spacing and a ribbon covering several occupied longitudes invites a reader to conclude a reach the geometry cannot support. Drawn honestly, the ribbon grows past the objects it is drawn among, and that is the picture the record shows <!-- src: docs/kinematic-inputs-results-20260922.md, section 2.5 -->. And the 180-day arm is unfit by the alarm's own registered bar — its median of 2.651 degrees exceeds 2.0 — which does not invalidate that arm's committed table, whose gate was registered and discharged at +30 days, but does mean the reach layer may not use it <!-- src: docs/kinematic-inputs-results-20260922.md, section 2.5 -->.

One number is worth keeping in view while reading all of this. **At +30 days the measured error is 22 times the element-set noise floor** of 0.018 degrees, and the ratio worsens with horizon: at +180 days the noise floor is 0.11 degrees against a measured 2.65, a factor of 24 <!-- src: docs/kinematic-inputs-results-20260922.md, section 2.5 -->. The error is not the elements failing to measure the orbit. It is what the object does next, and no arithmetic removes it.

![The measured forward error against the three screens it has to clear. The heavy line is the median of each horizon's own qualifying set; the bands are that set's p75 and p95; the open squares are the median of the matched cohort that qualifies at every primary horizon. The three dashed rules are the co-location tolerance the estimand is defined at, the measured median spacing of occupied longitudes, and the registered bar above which the forward geometry is declared unfit. The two vertical rules are the horizons the registration's own decision rules return when they are applied to this table.](latex/paper-d/figs/error-bands.pdf)

<!-- figure: docs/latex/paper-d/figs/error-bands.pdf, drawn by tools/make_figures.py from docs/kinematic-inputs-20260922.json: M1.armA.byHorizon, M1.armB.byHorizon, M1.crossings.colocationDeg, M1.crossings.slotSpacingMedianDeg, M1.crossings.gateWBarDeg -->

### 2.6 The low-orbit half of the same question

Outside the geostationary band the record draws element series rather than a slot coordinate, and the corresponding horizon is per object rather than per regime.

Against precise orbits for three well-tracked spacecraft over one calendar year, an element set from this archive propagated with a standard general-perturbations propagator has a median along-track error of 0.32 to 0.69 km at +1 day, 2.1 to 7.1 km at +7 days, 90 to 99 km at +30 days and 844 to 876 km at +90 days. The growth from +30 to +90 days is by factors of 8.5, 9.6 and 8.8 over a factor 3 of time — an exponent between 1.95 and 2.06, which is quadratic <!-- src: docs/t16b-truthset-results-20260922.md, sections 0 and 2.4 -->. The error is along-track and almost nothing else: at +30 days the along-track median is 68 to 160 times the radial and 74 to 152 times the cross-track <!-- src: docs/t16b-truthset-results-20260922.md, section 2.2 -->.

That measurement immediately falsified the ribbon the surface's own design had specified. The design drew the low-orbit ribbon from a noise statistic alone, which is linear in time; the error is quadratic. Measured against it, the ribbon is 4 to 9 times too wide at +1 day, agrees within 4 to 17% at +30 days, and is 3.3 times too narrow at +90 days <!-- src: docs/t16b-truthset-results-20260922.md, section 2.4 -->. **A ribbon that is right at one horizon and wrong on both sides of it is not a conservative ribbon.** The measurement is reported here; the surface is unchanged.

The per-object horizon was then measured across 1,295 sampled objects. A horizon is meaningful for an object if that object's median along-track phase error at that horizon stays inside the registered 5-degree half-box. At +90 days that holds for 610 of the 1,048 objects with a usable window — **58.2%**, or 47.1% of the 1,295 sampled, with 247 objects having no usable window at all and reported separately rather than counted as passes <!-- src: docs/kinematic-inputs-results-20260922.md, section 3.4 -->. By stratum the single number dissolves: 85.9% for the objects the reach layer would actually name, 87.3% for never-manoeuvred objects, 69.3% for payloads and **17.3% for catalogue-passive objects** <!-- src: docs/kinematic-inputs-results-20260922.md, section 3.4 -->.

The stratum comparison is confounded and the confound is the finding. The strata differ in drag as much as in class: median drag coefficient 3.39e-4 for the passive stratum against 6.93e-5 for payloads, and median secular rate of change of mean motion 1.72e-5 against 1.16e-6 revolutions per day squared, a factor of 15. They differ in altitude too, and in the *opposite* direction — median 854 km for the passive stratum against 540 km for payloads — so altitude does not explain the ordering and area-to-mass does <!-- src: docs/kinematic-inputs-results-20260922.md, section 3.4 -->. **Read the strata as drag populations, not as behaviour classes.** The rank correlation of the per-object error against the archive's own fitted drag term is +0.878, against the catalogue's asserted drag coefficient +0.661, and against the fit-to-fit scatter statistic +0.603; the last breaks monotonicity at two of ten deciles, so the noise statistic is not a substitute for a drag term <!-- src: docs/kinematic-inputs-results-20260922.md, section 3.5 -->.

---

## 3. The manoeuvre library

### 3.1 What a type is, and what an agreement figure is not

Every entry in the record carries a type, drawn from a versioned library whose rules are thresholds on registered floors — no learned classifier, and no Gaussian multiplier anywhere, because the archive's ratio of the 99th percentile to the scatter is 116 at the geostationary belt and 3,558 below 500 km <!-- src: docs/research-program-runbook-20260921.md, T13 row -->.

Each type's confidence is its measured agreement against label sets produced by *other* instruments in this programme — the approach catalogue's arrivals and initiating flags, the transfer ledger's legs, the north-south keeping ledger. **Every agreement figure below is agreement between rule sets.** It is not accuracy, not validation and not a detection rate, and nothing downstream may call it one <!-- src: docs/manoeuvre-library-results-v2-20260922.md, "Read this before any number" -->.

The library is pinned by two hashes — a version and a rules hash — and a consumer must pin both. The two versions may not be mixed in one population <!-- src: docs/manoeuvre-library-results-v2-20260922.md, header -->.

### 3.2 The measured mix, and a registered bar that was missed

Version 2 types 3,914,621 burns. Overall, 20.91% are unlabelled (818,416); in the arm covering the geostationary belt, 79.996% are unlabelled (814,571 of 1,018,263); in the arm outside it, 0.13% (3,845 of 2,896,358) <!-- src: docs/manoeuvre-library-results-v2-20260922.md, section 1 -->.

**The registration fixed the bar at an unlabelled fraction below 50% for the geostationary arm. It came out at 80.0%. The registered expectation failed, and the clause was not adjusted to reach it** <!-- src: docs/manoeuvre-library-results-v2-20260922.md, section 1 -->.

The change nevertheless did what it was written to do, and the two facts sit together. The version-2 clause replaced a raw inclination test with a *net* test — the observed inclination change minus a natural-motion prediction over the same span — on a floor derived from the two errors that make that quantity, with no multiplier applied to either term. The prediction removes 80.1% of the raw inclination change at the median: the median raw change is 0.01575 degrees and the median net change 0.00323, against a median floor of 0.00441 <!-- src: docs/manoeuvre-library-results-v2-20260922.md, sections 2 and 3.2 -->. Burns failing because both channels moved fell from 906,864 to 273,264, a drop of 69.9% <!-- src: docs/manoeuvre-library-results-v2-20260922.md, section 1 -->.

What the change uncovered is that the next wall is bigger. Burns failing because the drift moved but fits no registered band case rose from 13,009 to 528,609 — **64.6% of everything the library cannot label** <!-- src: docs/manoeuvre-library-results-v2-20260922.md, section 1 -->. Those burns were always there; under the previous version they failed at the inclination clause first. So the unlabelled fraction is now a statement about the registered drift bands — the 0.010 and 0.020 degrees-per-day floors and the station-segment definition — which do not between them describe half a million detected near-geostationary drift changes. That is published rather than fixed quietly, and fixing it is a new registration with a new rules hash and a new matrix <!-- src: docs/manoeuvre-library-results-v2-20260922.md, sections 1 and 9 -->.

One registered discrimination also failed on its own terms, and it is reported as a failure. The registration predicted that if the change fixed the mechanism, the unlabelled fraction would become markedly flatter in the differencing span. It is lower everywhere — by 19.8 points in the shortest-span bin — but it **climbs by 33.9 points across the bins against the previous version's 19.3** <!-- src: docs/manoeuvre-library-results-v2-20260922.md, section 3.1 -->. The honest reading is that the version fixed the clause it changed and left a larger, differently-sourced span dependence standing, and **no figure from it may be read as though span dependence had been removed**.

A third registered discrimination came back reassuring, and we report it because it bounds the model risk. Adding the oblateness term on top of the secular rotation moves 34 burns in a million, 0.004% of the arm; evaluating the prediction at an independently calibrated geometry instead moves the headline from 80.0% to 81.2% <!-- src: docs/manoeuvre-library-results-v2-20260922.md, section 3.3 -->. The answer is not a model artefact.

### 3.3 The agreement matrix, and the five types that may carry a confidence

| type | burns | matched | agreement | Wilson 95% |
|---|---:|---:|---:|---|
| station acquisition | 37,336 | 711 | 0.751 | [0.718, 0.781] |
| phasing | — | — | 0.677 | [0.501, 0.814] |
| drift start | 37,910 | 241 | 0.643 | [0.581, 0.701] |
| orbit raise | — | — | 0.549 | [0.506, 0.590] |
| north-south keeping | 2,563 | 20 | 0.500 | [0.299, 0.701] |
| drift stop | 31,103 | 204 | 0.426 | [0.361, 0.495] |

<!-- src: docs/manoeuvre-library-results-v2-20260922.md, sections 5.1, 5.2 and 9 -->

Each of those cells travels with a sentence, and the sentences are the point.

**Station acquisition's 0.751 is a corrected mapping, not a prediction.** The previous version scored this rule against one label class and measured 0 of 711, firing the falsification gate, with 534 of the 711 matches landing in a *different* class. Version 2 maps the rule to that class and scores 534 of 711 <!-- src: docs/manoeuvre-library-results-v2-20260922.md, section 6 -->. The rule's clauses are untouched and the matched set is exactly the same 711 burns, so the correction moved the score and not the burns — but **a mapping corrected to match a measured outcome cannot then be scored as a successful prediction**, and that sentence travels with the number wherever it is printed. The original zero is retained as a column in the matrix, because removing it would hide the correction.

**Drift start is the clearest gain and it got dirtier.** Its matched count went from 50 to 241 on a population 8.3 times larger, and its agreement rose to 0.643 with an interval half as wide. Its fraction of burns on catalogue-passive objects — objects that cannot burn — rose from 0.42% to 3.99%, from 19 burns to 1,514 <!-- src: docs/manoeuvre-library-results-v2-20260922.md, sections 5.2 and 5.4 -->. That is well inside the registered leak bar of 0.10, and it is stated because a rule that labels eight times as many burns and stays clean is a different claim from one that labels eight times as many burns and gets ten times dirtier. **A reader of this type under version 2 is reading a type that includes 1,514 burns on objects that cannot manoeuvre.**

**North-south keeping clears the underpowered bar by one event.** It has exactly 20 matched against a registered minimum of 20, so it publishes a confidence — 0.500 with an interval spanning 40 points. It earns a number, not a strong one, and it may not name an alert on that width. Its real gain is elsewhere: its catalogue-passive fraction fell from 6.96% to 1.44%, a factor of 4.8, which is the cleanest evidence in the library that the net clause selects better <!-- src: docs/manoeuvre-library-results-v2-20260922.md, sections 5.2 and 5.4 -->.

**East-west keeping has no burn-level agreement figure at all**, and its cell is a labelled gap rather than a zero, because there is no per-burn east-west label in the repository — the relevant ledger's per-burn recall is 1.81%. At object level, a burn of this type is 8.7 times more likely than the population base rate to sit on an object independently identified as an east-west station-keeper, down from 17.6 times in the previous version. **The rule now labels 5.2 times as many burns and each one carries half the enrichment**, and that cost is reported rather than netted against the gain <!-- src: docs/manoeuvre-library-results-v2-20260922.md, section 5.2 -->.

### 3.4 The forbidden types, and why

Three types may not be used in the ways a reader would most want to use them, and the record enforces each refusal.

**`orbit lower` may not be treated as propulsive.** It carries both the falsification gate and the leak gate. The mechanism is measured: in the first version of the library this type leaked 13.96% on passive objects against 4.71% for its mirror type, and the asymmetry is drag rather than propulsion <!-- src: docs/oh-wow-assessment-20260922.md, section 2, manoeuvre-library row -->. A sustained fall never opens an episode by construction, and a step lowering inside the drag regime prints *not separable from drag* unless the cohort screen says otherwise <!-- src: docs/change-ledger-and-reading-design-20260922.md, section 1.6 -->.

**`inclination adjust` may not be used at all** until the plane-noise floor of §5.3 is re-derived. It is underpowered at 17 matched events and its leak fraction is 36.30%, well above the registered 0.10 bar <!-- src: docs/manoeuvre-library-results-v2-20260922.md, section 9 -->.

**`drift stop` carries its falsification gate wherever it is printed.** Its agreement is 0.426 [0.361, 0.495], and its most frequent matched class is not the class its rule was written against but the north-south keeping windows — which the library reads as the density of a label set of 1,107 windows over 66 heavily-manoeuvred objects rather than as evidence that a drift stop measures inclination <!-- src: docs/manoeuvre-library-results-v2-20260922.md, section 5.2 -->.

And the largest refusal is the plainest: **80.0% of near-geostationary burns are unlabelled, and no type may be attached to an unlabelled burn** <!-- src: docs/manoeuvre-library-results-v2-20260922.md, section 9 -->.

### 3.5 What the library is not

It does not claim that a type is correct. It does not claim the natural-motion model is right — only that the model choice does not move the headline and that the model's own measured rate error sits inside the floor. It does not claim any difference between versions is significant, and no such test may be run on two runs that share their burns and their labels. And it does not claim the residual 80% is irreducible; it locates it, in the registered drift bands <!-- src: docs/manoeuvre-library-results-v2-20260922.md, section 8 -->.

---

## 4. Detection: the floor and the recall

### 4.1 The floor is a property of the calibration, not of the sky

The shipped low-orbit detector's threshold is set by a fit-noise term computed as the median over 61,861 low-orbit objects: 6.2747e-5 revolutions per day <!-- src: docs/t16b-truthset-recall-20260922.json, shippedSettings.pooledSigmaN -->. Propagated through the detector's own derivation, that gives a smallest detectable semi-major-axis change of **102.2 to 126.0 m**, or 54.0 to 58.7 mm/s of along-track impulse, across the eleven spacecraft the recall is measured on. Substituting each object's own noise makes the binding term the registration's 50 m floor instead <!-- src: docs/t16b-truthset-results-20260922.md, section 3.1 -->.

The gap between those two numbers is the whole of §4. These eleven spacecraft are tracked far better than the population median: their own fit-noise statistic comes back at 1.3 to 5.0e-7 revolutions per day, **130 to 470 times smaller** than the pooled term that sets their threshold <!-- src: docs/t16b-truthset-results-20260922.md, section 3.1 -->. The shipped threshold for any well-tracked object is therefore set by a population floor that has nothing to do with the object under test.

### 4.2 Recall, and the published figures it must be read beside

Run at its shipped settings over 1,134 operator-reported manoeuvres on eleven geodetic and altimetry spacecraft, the detector flags 90: a **recall of 7.94%, Wilson 95% [6.50, 9.66]**, with zero labels not evaluable <!-- src: docs/t16b-truthset-results-20260922.md, section 3.2 -->. The per-object noise arm gives 11.29% [9.57, 13.26] on the same labels with no change at all in the labelled-quiet flag count <!-- src: docs/t16b-truthset-results-20260922.md, sections 3.2 and 3.5 -->. **That arm has itself been registered and measured, and §4.7 reports why it is refused.**

A placebo control, added after registration and labelled as such, applies the identical association rule to the same windows displaced by ±30, ±60 and ±90 days: 5,610 placebo windows, of which those landing within two days of another label were discarded. It returns 0.30%, so a flag is **26.2 times** more likely inside a labelled manoeuvre window than beside one <!-- src: docs/t16b-truthset-results-20260922.md, section 3.2 -->. Without that control a single-digit recall could not be told from the background density of flags on frequently-flagged objects.

**This number is an outlier on the low side and we say so before a referee does.** Recalls of 0.35 to 1.000 against operator-published manoeuvre histories are in print on overlapping spacecraft (§1.3). The figure here is the calibration of one shipped detector at one operating point, not a property of the observable, and this paper makes no priority claim of any kind for it <!-- src: docs/oh-wow-assessment-20260922.md, section 2, first row -->.

Two further figures must never be printed apart from it. **The plane channel recalled zero of 1,134 manoeuvres** at both arms <!-- src: docs/t16b-truthset-results-20260922.md, section 3.2 -->. And the alarm lane does not speak per flag — it speaks at a campaign start, a flag chain with no internal gap longer than 180 days — so over these eleven spacecraft the whole archive contains 33 campaign starts against 1,134 manoeuvres, a structural ceiling of 2.9%, and the **measured campaign-level recall is 15 of 1,134, or 1.32%** <!-- src: docs/t16b-truthset-results-20260922.md, section 3.6 -->. Neither number may be printed without the other.

### 4.3 Split at the floor: the number is not a detector that misses

Split at the detector's own measured floor, the same 1,134 labels give **51.6% [43.8, 59.3] above the floor and 0.9% [0.5, 1.7] below it** <!-- src: docs/t16b-truthset-results-20260922.md, section 3.3 -->. **977 of the 1,134 manoeuvres — 86% — move the semi-major axis by less than the shipped threshold requires.** The detector does not miss most of what these operators do; it cannot see it.

| burn size, semi-major-axis change | labels | shipped recall | per-object recall |
|---|---:|---:|---:|
| under 20 m | 576 | 1.0% | 1.4% |
| 20 to 50 m | 342 | 0.6% | 3.5% |
| 50 to 100 m | 53 | 1.9% | **39.6%** |
| 100 to 200 m | 27 | 37.0% | 51.9% |
| 200 to 500 m | 36 | 58.3% | 61.1% |
| 500 m and above | 100 | 50.0% | 51.0% |

<!-- src: docs/t16b-truthset-results-20260922.md, section 3.3 -->

The 50-to-100 m row is the floor moving: 1.9% under the shipped threshold, 39.6% once the threshold drops to 50 m. And recall does not keep climbing above 200 m — it plateaus near half — which says the remaining misses are not a sensitivity problem <!-- src: docs/t16b-truthset-results-20260922.md, section 3.3 -->.

The same structure appears per spacecraft, and it is burn size rather than any property of the detector. The spacecraft with a recall of 0.0% has a median labelled change of 9.7 m and **not one** of its 58 labelled manoeuvres reaches the shipped threshold; the spacecraft at 1.4% has 145 of 147 below it <!-- src: docs/t16b-truthset-results-20260922.md, section 3.4 -->.

The false-flag count is reported on the same windows and is an upper bound, not a rate. Across 1,139 labelled-quiet windows totalling 1,423.8 window-days the detector raises 18 flags, of which 9 fall in windows the label set itself marks as suspected unreported manoeuvres; 10 of 1,139 windows carry at least one flag. A further 321 flags inside the labelled span are unmatched and are reported as a count and **not** called a false-alarm rate, because the completeness of the published manoeuvre history is not something this measurement verified <!-- src: docs/t16b-truthset-results-20260922.md, section 3.5 -->.

![Recall against burn size, with the detector's own floor drawn on the same axis. Each horizontal segment spans the bin it belongs to; the heavy segments are the shipped settings and the light ones the per-object noise arm. The shaded column is the span of the shipped arm's minimum detectable change across the eleven spacecraft, and the dashed rule is the per-object arm's floor. The label count is printed on each bin so that a high rate on a thin bin cannot read as a strong one.](latex/paper-d/figs/recall-by-burn-size.pdf)

<!-- figure: docs/latex/paper-d/figs/recall-by-burn-size.pdf, drawn by tools/make_figures.py from docs/t16b-truthset-recall-20260922.json: arms.pooled and arms.perObject .windows.madleoEventWindow.byDaBin (n, recall), and arms.*.perSpacecraft.*.floor.minDetectableDaMetres -->

### 4.4 The working floor is real variation, not noise

The obvious reading of §4.1 is that a quieter statistic would lower the floor. A registered measurement tested that directly on the best available test case — two spacecraft flying the same orbit, whose element-set errors ought to share a common mode a differential detector could cancel — and refuted it.

The pair's geometry was measured rather than assumed: a median semi-major-axis difference of −1.80 m, a plane agreement of 0.0063 degrees in node, and a median along-track separation of 2,352 seconds, which is 39 minutes <!-- src: docs/t21-differential-results-20260923.md, section 1 -->. Their own five-sigma detector noise floors are **1.25 m and 2.77 m of semi-major axis** — 40 to 100 times below the shipped detector's 102 to 126 m <!-- src: docs/t21-differential-results-20260923.md, section 4 -->.

And yet, to reach the shipped detector's own false-flag rate of 0.012642669 flags per labelled-quiet window-day, the single-object detector on this pair needs a multiplier of **2,543.9**, not 5 — putting its operating floor at **273.8 m** <!-- src: docs/t21-differential-results-20260923.md, section 5 -->. **The operating floor is therefore not set by noise.** It is set by real, non-manoeuvre variation in these spacecraft's element series, and a scheme that cancels a noise term already two hundred times below the binding term cannot move it.

The correlation measurement says the same thing from the other side. The derivation fixed in the registration is that differencing lowers the floor if and only if the correlation between the two objects' detector residuals exceeds one half. Measured on 447 near-coincident element-set pairs with nothing interpolated, that correlation is **0.0230, 95% [−0.056, 0.407]**; matching the passbands raises it to 0.0352 and moves nothing <!-- src: docs/t21-differential-results-20260923.md, section 3 -->. A non-co-orbital control 17.8 km lower correlates with the same spacecraft **eight times more strongly**, 0.196 with a 95% lower bound of 0.004 — the only non-zero lower bound in the control table — so whatever common mode exists is not the co-orbital one <!-- src: docs/t21-differential-results-20260923.md, section 6 -->. At the geostationary belt, over 1,151 committed episodes, the east-west differential floor is 0.926 of the single-object floor [0.833, 0.995], while the north-south differential is **1.439 times worse**, which is the square root of two to within 1.8% — the value the derivation gives for no common mode at all <!-- src: docs/t21-differential-results-20260923.md, section 8.1 -->.

One clause of that conclusion was narrowed by the measurement's own adversarial pass and the narrowing is kept. What is measured is the correlation of **the error the detector actually reacts to** — the residual after its own baseline — and not of the raw element-set error; a shared error the baseline removes cannot raise a flag in either arm, and so cannot be what a differential detector would be cancelling <!-- src: docs/t21-differential-results-20260923.md, section 13 -->.

The result that matters for the record is the second-order one. The shipped detector's own drag term, which the registered sweep dropped from both arms symmetrically, turns out to be load-bearing: the shipped detector with that term kept recalls 19 of 241 on this pair against the swept arm's 8 of 241 at a comparable rate <!-- src: docs/t21-differential-results-20260923.md, section 5 -->. **Removing it cost more than differencing could ever have returned.**

### 4.5 Two thirds of the recall is the sampling schedule

The second measurement that bounds what the record's detections mean is the least comfortable in this paper.

A model shown the archive's **sampling schedule and nothing else** — no element value, no regime, no catalogue number, no name — flags 58 of the same 1,134 manoeuvres at the shipped detector's own false-flag rate, a recall of **5.115% [3.977, 6.555]** against the detector's 7.937% <!-- src: docs/t18-floor-results-20260922.md, section 0 -->. The operating point is matched exactly rather than approximately: the swept threshold produces 18 flags over 1,423.75 quiet window-days, which is the shipped figure to every digit, because it is the same 18 flags in the same windows <!-- src: docs/t18-floor-results-20260922.md, section 2 -->.

**So 64.4% of the shipped detector's recall on this labelled set is reachable from timing and residual magnitude alone, with no representation of behaviour anywhere in the model.**

Three cells of the comparison keep that from being read as more than it is. The schedule-only flags are **5.52 times** more likely inside a labelled manoeuvre window than beside one; the shipped detector's are 26.2 times. The schedule-only model finds real manoeuvres, far less specifically — which is what an artefact floor should look like <!-- src: docs/t18-floor-results-20260922.md, section 2.1 -->. Split at the shipped detector's own threshold, the two are indistinguishable below it — 0.82% against 0.92% — and the entire deficit is on the burns the detector can actually see, 31.85% against 51.59% <!-- src: docs/t18-floor-results-20260922.md, section 2.2 -->. And in one bin the sign reverses: in the 50-to-100 m bin the schedule-only model catches four of 53 against the shipped detector's one, 7.55% against 1.89% — exactly the bin where the pooled threshold bites, because a statistic conditioned on the object's own sampling cadence is not held up by a population term 130 to 470 times too large <!-- src: docs/t18-floor-results-20260922.md, section 2.3 -->.

The schedule-only statistic is also twice as geometry-driven as the deterministic rules: its flag rate varies by a factor of 6.900 across the committed sampling-geometry classes against the shipped detector's 3.433 on the identical objects and windows <!-- src: docs/t18-floor-results-20260922.md, section 3.1 -->.

We report this in a paper about a public record because it changes what an entry means. An entry in this record is evidence that the elements changed in a way the detector's rules trip on. **It is not, by itself, evidence that the change was large, unusual, or seen for the reason a reader would assume** — and on this labelled set, two thirds of the same catch is available to a model that knows only when the archive looked.

### 4.6 One discriminator that does work, and the physics that does not

For completeness, and because it is the one per-flag discriminator in this programme that separates cleanly, a registered sign test measured whether a burn that holds a slot pushes the drift rate against the triaxial acceleration. Over 29,836 flag chains on 207 east-west carriers, **82.94% obey the rule [0.8251, 0.8336]; over 7,160 chains on 239 same-shell passive objects, 15.15% do [0.1434, 0.1600]** — two intervals separated by 67 percentage points, exactly as the registration predicted in advance from the sign of free motion under the same acceleration <!-- src: docs/t22-scheduled-null-results-20260923.md, sections 0 and 7.3 -->. **The false rate on objects that cannot manoeuvre is about one in seven.** It is a measurement on this population, not a detector, and no operating point is proposed for it.

The same registration's main estimand failed, and the failure is instructive about what physical reasoning buys here. Predicting *when* the next east-west keeping burn must occur, from the deadband cycle, gives an on-schedule fraction of 0.0697 [0.0647, 0.0750] against a random-phase null drawing from the population's own observed spacings that reaches 0.2438, 95th percentile 0.2502 — **three and a half times worse than knowing nothing except how often this population burns** <!-- src: docs/t22-scheduled-null-results-20260923.md, section 5 -->. The ingredients are not wrong: the derived triaxial acceleration is unbiased at the median across 29,315 arcs, the post-burn drift rate is within 5% of what the flown cycle needs, and the deadband that rate implies is 0.02547 degrees against the registered 0.02633, a 3% agreement between two instruments sharing no arithmetic <!-- src: docs/t22-scheduled-null-results-20260923.md, section 6 -->. The exit epoch is a **bifurcation**: the optimal one-burn cycle is tangent to the far edge of its own deadband, so a ten-per-cent error in the drift rate decides between a half cycle and a full one. 65.1% of pairs are predicted out of the far edge and 34.9% out of the burn-side edge, and conditioning on the branch makes the prediction 46 times better and still leaves it at 0.19 <!-- src: docs/t22-scheduled-null-results-20260923.md, section 6 -->.

One incidental agreement is worth recording. That measurement never computes a periodogram — it counts the days between consecutive flag chains — and its median is **14.35 days** over 9,289 pairs on 187 carriers, against an independently measured spectral line at 14.00 days. Two instruments, one number, and this one was not tuned to it <!-- src: docs/t22-scheduled-null-results-20260923.md, section 4 -->.

### 4.7 The cheap improvement, measured and refused

**The per-object-noise detector arm is refused on its own passive control.** The registered arm raises recall on the same 1,134 labels from 90 to 128 — 7.937% to 11.287%, an increment of 3.351 points with an object-clustered 95% interval of [1.120, 5.537] against a minimum detectable effect of 2.208 points — with the labelled-quiet false-flag count unchanged at 18. But run over the archive's own low-orbit population, the flag rate on the physically passive class, 9,915 objects over 86,859,654 object-days, rises from 0.0017565 to 0.0044933 flags per object-day, and the registered bound-versus-bound test is not close: the per-object arm's lower bound of 0.0044792 stands above the shipped arm's upper bound of 0.0017653, a point ratio of 2.558. The registered verdict is **NOT SHIPPED** <!-- src: docs/t27-per-object-noise-results-20260923.md, verdict paragraph -->. The mechanism is measured: on the control's own admitted population the median per-object scale of the passive class is 0.062 of the pooled value — sixteen times smaller — against 0.948 for payloads, because ballistic objects have tiny fit-to-fit scatter while payloads carry the very manoeuvres the estimator's own statistic absorbs. **The estimator is contaminated by the signal it is meant to help detect**, and the measured consequence is that asymmetry: passive in-track flags rise from 151,543 to 379,720 while payload in-track flags *fall* from 1,573,393 to 1,527,134 <!-- src: docs/t27-per-object-noise-results-20260923.md, verdict paragraph -->. **This is why §4.2 reports the per-object arm and does not recommend it.** It is not a cheap improvement waiting to be taken; it is a change that buys its recall hardest on the one class of object that cannot manoeuvre at all.

---

## 5. Approaches and the alarm

### 5.1 What the approach catalogues contain

The record carries two frozen families of approach material alongside its catalogue steps, and each is a different estimand.

**Near-geostationary slot co-locations.** 487 events on a primary arm of 0.1 degrees of mean longitude held for 30 days, over 224 distinct approachers and 262 distinct targets, corresponding to 427 distinct arrivals — an arrival into a slot already shared by several objects yields one event per object <!-- src: docs/proximity-results-20260922.md, section 3.1 -->. The estimand is **mean longitude, a slot coordinate**; the median event closes to 0.00030 degrees, which is 0.22 km of along-arc longitude. **No figure in that catalogue is a miss distance**: two objects sharing a mean longitude are routinely tens of kilometres apart and are deliberately kept so by eccentricity- and inclination-vector separation, which the instrument does not model <!-- src: docs/proximity-results-20260922.md, sections 1.1 and 3.2 -->. Rejections at each registered criterion are counted rather than dropped: 4,191,020 candidate loiters too short, 2,669 broken by a gap, 1,797 with no prior separation, and 79 symmetric mutual approaches that the registered definition assigns to no one and therefore discards — a real 14% addition the definition refuses <!-- src: docs/proximity-results-20260922.md, section 3.1 -->.

**Low-orbit co-orbital stations.** 71 events on a primary arm of 0.2 degrees of plane agreement, ±5 degrees of relative phase, held 30 days — which at 500 km is a box roughly 24 km across-track, 600 km along-track and 0.14 km in altitude <!-- src: docs/proximity-leo-results-20260922.md, section 1.1 -->. 44% of the raw geometric dwells are the oblateness term's doing and are removed by a counterfactual that propagates each object at its own fitted nodal rate: 1,127 of 2,565 <!-- src: docs/proximity-leo-results-20260922.md, section 3.1 -->.

**And the low-orbit catalogue is not what its own registration set out to build.** The registered plane-noise statistic came back 145 times too large — a p95 of 2.9026 degrees against a bar of 0.02 — because second-differencing the angle between consecutive orbit normals measures the irregularity of the archive's sampling rather than the fit <!-- src: docs/proximity-leo-results-20260922.md, sections 2.2 and 2.3 -->. That set the plane-manoeuvre threshold to 3.5 degrees and switched the plane channel off: `planeManoeuvresInCampaign` is **zero for every one of the 71 events**, the median plane closure is 0.0357 degrees against a 5-degree prior-separation bar, and the median semi-major-axis difference is 6.5 m <!-- src: docs/proximity-leo-results-20260922.md, sections 3.2 and 3.3 -->. **These objects did not match planes; they were already co-planar and they closed the along-track phase.** The record labels every such row an *in-track phasing campaign*, everywhere it appears <!-- src: docs/orbits-section-design-20260922.md, section 2.3 -->.

A diagnostic measured at the same time says the registered statistic and the deciding statistic disagree by three orders of magnitude: the residual of inclination and node from a centred five-point median, which annihilates smooth motion at any spacing, gives a plane-direction scatter with a median of 0.000148 degrees and a p95 of 0.000741 — 135 times inside the gate's bar at the median <!-- src: docs/proximity-leo-results-20260922.md, section 2.4 -->. **A noise estimator is not a noise floor**, and no care in the downstream code could recover from choosing the wrong one.

### 5.2 Lead times, and the denominator that corrected itself

The record's warning half rests on three measured lead-time distributions and one corrected denominator.

**Near-geostationary, from the event's own initiating change.** 326 of 487 events — 66.9% [62.6, 71.0] — had an initiating drift-change flag inside the 180-day look-back, and the other 161 are carried with a null lead and counted in every denominator. The causal lead, measured from the confirmation of that flag to arrival, has a median of **36.1 days**, p25 10.6, p75 96.0, p95 162.7 <!-- src: docs/proximity-results-20260922.md, section 4 -->. The upper tail is mildly right-censored: 12 of the 326 sit within 10 days of the look-back wall, so the p95 is a lower bound <!-- src: docs/proximity-results-20260922.md, section 4 -->.

**Low orbit.** 71 of 71 events had an initiating manoeuvre inside a 1,095-day look-back, and the causal lead has a median of **195.9 days**, with the survival estimate agreeing to the decimal. One event of 71 — 1.4% — sits at or beyond the wall, against a registered censoring bar of 20% <!-- src: docs/proximity-leo-results-20260922.md, section 4 -->. That is the direct repair of the near-geostationary measurement's one undeclared blind spot: a 180-day look-back would have missed the initiating manoeuvre of **53.5% of these events**, 38 of 71 <!-- src: docs/proximity-leo-results-20260922.md, section 4 -->.

**And the lead belongs to the loose phase band, not to the regime.** Across the registered sensitivity arms it is stable at 196 to 221 days for a 5-degree phase box and every dwell, and it **collapses to 17.5 days at 1 degree and 4.4 days at 0.2085 degrees** <!-- src: docs/proximity-leo-results-20260922.md, section 3.5 -->. A tightly phase-locked station is reached by an arresting burn immediately before arrival; a loosely confined one is the end of a long chain. Both are true of different event classes and neither generalises to the other. A second split says the same: the interval from the first epoch at which the planes agree to the arrival has a median of 46.8 days against the 195.9-day total, so a median event spends about 76% of its warning window with the planes already matched and the phase still closing <!-- src: docs/proximity-leo-results-20260922.md, section 4.2 -->.

**The denominator correction is the most instructive number in this section.** The alarm's design document asserted that the trigger-time precision floor "is already known" and was the near-geostationary catalogue's 32.8% [30.5, 35.3] — a figure measured over 1,483 relocation alerts, each of which required a relocation of at least 2 degrees **to have already happened** <!-- src: docs/proximity-results-20260922.md, section 4.1 -->. At trigger time that population does not exist. Measured on what an alarm actually sees — a confirmed drift-rate change — the population is **226,422 flag chains**, of which 97,784 are both eligible and resolvable, and **101 of them ended in an arrival: 0.1033% precision, Wilson 95% [0.0850, 0.1255]** <!-- src: docs/trigger-alarm-results-20260922.md, sections 0, 3.1 and 3.2 -->. Thirty-seven further matches arrived *before* the announce time and are excluded from the headline and counted rather than hidden, because an alarm that speaks after the arrival has warned nobody <!-- src: docs/trigger-alarm-results-20260922.md, section 3.2 -->.

The reason the two numbers differ by three orders of magnitude is a fact about the belt rather than about the detector. There were 71,661 confirmed drift changes in the 2010s alone — **about 7,200 a year across the geostationary belt** — because at that belt a 0.010 degree-per-day threshold corresponds to about 0.78 km of semi-major axis, which a routine 0.05 m/s east-west correction exceeds. **A confirmed drift-rate change is not a rare event at the geostationary belt; it is the normal operation of a stationed satellite** <!-- src: docs/trigger-alarm-results-20260922.md, section 3.1 -->.

![Four lead-time distributions, drawn as the quantiles that were measured. A box spans p25 to p75, the heavy rule is the median, and the whiskers are p5 and p95 where the source carries them. The four populations are different estimands measured on different denominators and are never pooled.](latex/paper-d/figs/lead-times.pdf)

<!-- figure: docs/latex/paper-d/figs/lead-times.pdf, drawn by tools/make_figures.py from docs/proximity-20260922-receipt.json leadTime.leadCausalDays and leadTime.withFlag; docs/trigger-alarm-20260922-receipt.json classes[cluster 1].arrivalDays; docs/alarm-lane-replay-20260922-receipt.json runs[everything].classes[class 1].leadDaysFromAnnounceRule; docs/proximity-leo-events-20260922.jsonl leadCausalDays over the rows with armM true -->

### 5.3 The class that may speak, and the class that may not

A registered clustering of the trigger-time feature space returned two classes by its own criterion — a mean silhouette of 0.7565 at two clusters against 0.2251 for the best alternative, with three independent subsamples agreeing to within 0.005 <!-- src: docs/trigger-alarm-results-20260922.md, section 5.1 -->. Both classes recover 62 to 63% of their members under resampling of approachers, which is the weakest kind of pass and is reported as one <!-- src: docs/trigger-alarm-results-20260922.md, section 5.2 -->.

| class | triggers | arrivals | precision | Wilson 95% |
|---|---:|---:|---:|---|
| 0 | 96,962 | 73 | 0.0753% | [0.0599%, 0.0947%] |
| **1** | **822** | **28** | **3.406%** | **[2.367%, 4.879%]** |
| whole primary arm | 97,784 | 101 | 0.1033% | [0.0850%, 0.1255%] |

<!-- src: docs/trigger-alarm-results-20260922.md, section 5.4 -->

**A 45-fold lift, carrying 28 of the 101 arrivals in 0.84% of the alert volume, at a median 22.1 days of warning** with quartiles 7.0 and 47.5 <!-- src: docs/trigger-alarm-results-20260922.md, sections 3.4 and 5.4 -->. It is also still about 29 false alerts for every true one, and the statistical separation gate that it passes is nearly vacuous at a hundred thousand rows — what matters is the magnitude, and the magnitude is reported as the magnitude <!-- src: docs/trigger-alarm-results-20260922.md, section 5.4 -->.

The class that does not speak is withheld for a measured reason rather than for want of a measurement. It has 96,962 supporting events and a measured rate; it is withheld because that rate straddles the base rate of the same population, and **an alert that fires on 99.2% of all confirmed drift changes and is right about once in 1,300 is not a warning** <!-- src: docs/alarm-lane-build-20260922.md, section 3 -->. The rule is arithmetic evaluated at every setting, never a stored verdict: a class may speak when it is a reproducible cluster at or above the registered bootstrap bar, when at least twenty supporting events stand behind the figures quoted, and when its precision's Wilson lower bound clears the base population's Wilson upper bound <!-- src: docs/alarm-lane-build-20260922.md, section 3 -->.

**And the sentence about an individual object is withheld by a gate that fired.** The registered per-object predictor is worse than the population base rate at every prior-event count — every stratum's *upper* bound is below zero — so the threshold at which an alarm could speak about one object individually **does not exist** in this archive <!-- src: docs/trigger-alarm-results-20260922.md, section 6.2 -->. The registration's own smoothing prior is where the fault lies, and it is reported rather than revised: a prior chosen against an imagined base rate of tens of per cent predicts about 14% for an object with five clean prior triggers, against a real base rate of 0.1% <!-- src: docs/trigger-alarm-results-20260922.md, sections 6.1 and 9 -->. The one thing the object's own history does do is *rank*: it beats the class as a ranker, 0.674 against 0.544 by area under the curve, and a half-and-half hybrid beats both at 0.715. **It survives as an ordering and it does not survive as a probability** <!-- src: docs/trigger-alarm-results-20260922.md, section 6.1 -->.

### 5.4 The replay, and the finding that tighter is not more precise

Nothing about the alarm is scheduled. What exists is the job a timer would run, exercised over a decade of history at a derived cadence with an injected clock — 4,828 ticks from 2010-01-01 to 2020-01-01, at a tick of 0.7564 days measured as the median element-set spacing over all 1,652 watched objects rather than chosen <!-- src: docs/alarm-lane-build-20260922.md, section 6 -->.

The clock-driven lane reproduces the offline detector exactly. Of 33,719 offline triggers and 33,599 live assessments, 33,595 are in both, with **zero class disagreements**; the 124 offline-only are all explained by a labelled-gap rule the offline measurement does not apply, the 4 live-only are all explained by a property that needs 210 days of future element sets and that no live lane can know, and **zero are unexplained in either direction** <!-- src: docs/alarm-lane-build-20260922.md, section 6.1 -->.

| | loosest setting | tighter setting |
|---|---:|---:|
| assessments | 71,551 | 71,551 |
| labelled not assessable | 37,952 | 37,952 |
| below this setting's evidence | 601 | 33,431 |
| withdrawn by the persistence check | 0 | 36 |
| **alerts spoken** | **272** | **132** |
| arrivals | 14 | 7 |
| **precision on this lane** | **5.147%** [3.090, 8.453] | **5.303%** [2.592, 10.542] |
| median warning | 22.1 d | 47.4 d |
| quartiles of the warning | 9.5 – 37.6 d | 28.5 – 69.0 d |

<!-- src: docs/alarm-lane-build-20260922.md, section 6.2 -->

**The median lead reproduces to the decimal** against the frozen figure of 22.1 days. The precision runs high in that decade — 5.147% against the whole-archive 3.406% — with heavily overlapping intervals, because the decade is a denser slice of the archive than its mean; the alert rate of 27.2 a year against an archive mean of about twelve says the same thing, and it *measures* a rate the earlier work could only pro-rate at "of the order of 25 to 30 a year" <!-- src: docs/alarm-lane-build-20260922.md, section 6.2 -->.

The lane's own latency is charged against the warning budget rather than hidden: the delay between the announce time the detector defines and the tick the lane actually spoke has a median of 0.378 days and a p95 of 0.718, bounded by the tick as it must be — **1.7% of a 22.1-day median warning** <!-- src: docs/alarm-lane-build-20260922.md, section 6.4 -->.

**The finding the operating-point curve was built to make visible is that a tighter setting is not automatically a more precise one.** Across 108 measured rows over a grid fixed before the table existed, on the class that already speaks, the loosest setting reaches 3.410% and the tightest reaches 2.725%; tightening bought fewer alerts — 821 down to 367 — and a different warning time, but **not a higher hit rate, and every interval overlaps every other** <!-- src: docs/alarm-lane-build-20260922.md, section 5.2 -->. The artifact carries a note saying so, and a test refuses any output string containing "more certain", "higher confidence", "more reliable", "more accurate", "certainty" or their neighbours, in the curve, in every rendered alert at every setting, and in the low-orbit arm <!-- src: docs/alarm-lane-build-20260922.md, section 5.2 -->.

The same table carries the complementary finding: the evidence thresholds carry information the partition does not. The class the gate withholds on its whole-population numbers reaches **3.661% [2.738, 4.878] over 1,202 triggers** once the drift-size and reachable-set thresholds are applied, and becomes speakable, because its Wilson lower bound then clears the base rate's upper bound at that setting <!-- src: docs/alarm-lane-build-20260922.md, section 5.2 -->.

![The operating-point table as a plot. Left: each named setting's measured precision with its Wilson interval, for both classes, against the whole-population base rate. Right: what tightening buys and costs -- the median warning moves and the alert count, printed beside each marker, falls -- while the intervals on the left keep overlapping. Tightening the evidence does not raise the hit rate on the class that already speaks.](latex/paper-d/figs/operating-points.pdf)

<!-- figure: docs/latex/paper-d/figs/operating-points.pdf, drawn by tools/make_figures.py from docs/alarm-lane-operating-points-20260922.json: namedSettings[].classes[] alerts, precision, wilson95, className, leadDays.p50; basePopulationByHorizon["180.0"].precision -->

One reconciliation is stated rather than smoothed over: the loosest grid point holds 96,246 triggers where the frozen artifact's primary arm holds 97,784, because the grid applies the floor to the chain's net drift change while the flag threshold applies it to each element set's departure from its trailing baseline. **No positive is lost by the difference** — both carry the same 101 — and the artifact records it <!-- src: docs/alarm-lane-build-20260922.md, section 5.2 -->.

### 5.5 The controls: one that holds, one that fires, and one that was withheld

**The low-orbit control holds, and it is the strongest number in this programme.** Built on manoeuvre history rather than on a catalogue field — zero detected manoeuvres over a whole history, with at least 200 element sets and at least 365 days of span — it returns **exactly zero events across 18,792,698 object-days**, Wilson 95% [0, 2.04e-7], against a payload rate of 2.028e-6 per object-day. **Leak ratio 0.000 against a registered bar of 0.10** <!-- src: docs/proximity-leo-results-20260922.md, section 6.1 -->. The registration predicted in advance that this gate *would* fire, on the strength of its own proof that chance co-planarity is certain for any pair whose inclinations differ by less than the plane tolerance. It did not.

Two things did it, and both were built in on purpose. The control is manoeuvre history rather than object type, so the **855 payload-class objects that have never manoeuvred in their whole recorded history** are inside it — and those are exactly the population that broke the near-geostationary control <!-- src: docs/proximity-leo-results-20260922.md, section 2.5 -->. And the phase-confinement criterion is a requirement no uncontrolled object can meet: holding ±5 degrees of relative phase for 30 days needs a semi-major-axis difference below 158 m, which drag alone destroys <!-- src: docs/proximity-leo-results-20260922.md, section 6.1 -->.

The control also switches on exactly where the physics says it should. The leak ratio is 0.000 at plane tolerances of 0.05, 0.1 and 0.2 degrees, **0.0953 at 0.5 degrees and 0.1206 at 1.0 degrees, where the gate fires** <!-- src: docs/proximity-leo-results-20260922.md, section 6.2 -->. The primary arm sits on the safe side of a boundary derived before it was measured, and a reader who prefers a wider plane tolerance is entitled to know it costs the control.

**The near-geostationary control fires, at parity.** The passive class produces events at 0.01701 per stationed segment, and so does the active class: a ratio of **0.9995, 95% [0.43, 2.30], against a registered bar of 2%** — the gate fires by a factor of 21 even at the lower end of its interval <!-- src: docs/proximity-results-20260922.md, section 7.1 -->. The derivation that was supposed to make that impossible was falsified by the data it was supposed to exclude: a dwell bound computed from the distance to the *nominal* stable longitude was exceeded by **5 of 5** passive events, which dwelled 30 to 67 days where the bound allowed 13 to 22 <!-- src: docs/proximity-results-20260922.md, section 7.2 -->. The error is identifiable — the quantity that governs a real object's turnaround is its distance from its *own instantaneous* equilibrium, which for an old, high area-to-mass object is displaced by radiation pressure and modulated by third-body terms — and the lesson generalises: **deriving a threshold is not validating it.**

The registered control was also the wrong control. The passive class has 294 stationed segments against the active class's 24,391, and the real uncontrolled population at that belt is dominated by dead *payloads*, which the catalogue labels as payloads and which the control therefore cannot see. The evidence is inside the catalogue: 141 of the 487 events have a transfer drift below 0.025 degrees per day — slower than any deliberate relocation and consistent with free libration — and 66 of them belong to objects launched before 1995 <!-- src: docs/proximity-results-20260922.md, section 7.3 -->.

A discriminator added after that registration does separate the catalogue, and it is labelled as post-registration: the 326 events carrying an observed drift-change flag have a median transfer drift of 0.1677 degrees per day against 0.0227 for the 161 without one — a factor of 7.4 — and the fraction of approachers launched before 1995 goes from 14 to 78 <!-- src: docs/proximity-results-20260922.md, section 7.4 -->. It converts a catalogue in which the control does not separate into one where the contamination is concentrated in a nameable third.

**The low-orbit alarm arm was withheld by its own control, and the record publishes the withholding.** Run over objects that physically cannot manoeuvre, the same detector raised 13,443 alerts — **0.797 of the per-object rate it raises on objects that can**, against a design target of one in a thousand. The arm ships live, classifies, ledgers and audits, and raises **zero alerts**, printing the measured reason in place of a clause <!-- src: docs/alarm-lane-build-20260922.md, section 7.2 -->. Its own trigger's precision was measured too, and it is not the published 44.1%: over a 2020 to 2023 replay of 2,528 ticks at a derived 0.4935-day cadence, 5,327 alerts produced 27 arrivals, **0.507% [0.349, 0.736]**, with a median warning of 684.4 days right-censored by the horizon <!-- src: docs/alarm-lane-build-20260922.md, section 7.1 -->. That is the same enormous-denominator problem, an eighty-seven-fold gap, for the same reason: the published figure's denominator is an alert channel defined by a different detector. **The arm does not quote 44.1%** <!-- src: docs/alarm-lane-build-20260922.md, section 7.2 -->.

### 5.6 The near-geostationary control problem, named and measured

The near-geostationary control failure has since been attacked directly, and the answer is a negative one with the exposure to mean it.

The idea was to build a control on **epochs of free libration inside a history** rather than on whole objects, so that a payload counts as a control during the intervals when it was not holding a station. It works as exposure: the previous whole-object control had 232 pair-exposure-days against the 540,990 a single expected episode requires — one part in 2,330 — while the epoch class gives **23,960,622 pair-epoch-days against the 2,523,960 one expected episode needs, and 517,391 object-days against 16,747** <!-- src: docs/geo-libration-epoch-control-results-20260922.md, header -->. The exposure problem is solved. What replaces it is a measured leak.

| reading | events | exposure (object- or pair-days) | exposure ÷ meaningful zero | leak ratio | 95% |
|---|---:|---:|---:|---:|---|
| approach events | 57 | 517,391 | 30.9× | **1.845** | [1.377, 2.431] |
| tandem episodes | 6 | 23,960,622 | 9.5× | 0.632 | [0.232, 1.379] |
| trigger chains | 3,812 | 517,391 | 13,229× | **0.288** | [0.279, 0.298] |

<!-- src: docs/geo-libration-epoch-control-results-20260922.md, section 5 -->

**The bar is 0.10 in every row, none of the nine pre-specified readings is leak-free, and the best ratio in the full table is 0.256 — 2.6 times the bar, with a lower interval end still 2.35 times it** <!-- src: docs/geo-libration-epoch-control-results-20260922.md, section 5 -->. The registered verdict is printed verbatim: *a GEO epoch control does not exist* — and the registered reason is a **leak**, not an absence of exposure. The tandem row is flagged unstable by its own parity split and is read as nothing <!-- src: docs/geo-libration-epoch-control-results-20260922.md, sections 0 and 3 -->.

**And the mechanism is measured rather than argued, and it is broader than the one the registration named.** The registration stratified on the turnaround; the leak instead falls monotonically with the libration amplitude — that is, with speed — by a factor of twelve from the slowest band to the fastest, and epochs containing no turnaround at all leak on their own at 1.63 times the active-payload rate <!-- src: docs/geo-libration-epoch-control-results-20260922.md, sections 0 and 6 -->.

| implied half-amplitude | epochs | object-days | events | leak ratio | days to cross 0.1 degree at peak rate |
|---|---:|---:|---:|---:|---:|
| 0 to 1 degrees | 48 | 8,120 | 0 | unevaluable | 12.98 |
| 1 to 5 | 336 | 59,250 | 26 | **7.349** | 2.60 |
| 5 to 20 | 462 | 89,820 | 18 | 3.356 | 0.66 |
| 20 to 90 | 1,759 | 360,201 | 13 | **0.604** | 0.23 |

<!-- src: docs/geo-libration-epoch-control-results-20260922.md, section 6 -->

The arithmetic is the whole explanation. The approach definition requires a **30-day** dwell inside 0.1 degrees. An object librating with a half-amplitude of 5 degrees crosses 0.1 degrees in 2.6 days *at its fastest* and far more slowly everywhere else in its swing, so it satisfies the dwell criterion over most of its trajectory. One at 1 degree takes 13 days at its fastest. **It is not that a librator dwells at its turnaround; it is that a slow librator dwells everywhere, and the turnaround is where every librator is slow** <!-- src: docs/geo-libration-epoch-control-results-20260922.md, section 6 -->.

The lowest band is drawn as a labelled gap and not as a zero: its zero sits on 48% of the exposure a single expected event requires, and this paper reads it as nothing <!-- src: docs/geo-libration-epoch-control-results-20260922.md, section 5 -->.

![The near-geostationary control's leak, against the speed of the motion it admits. Each point is one band of implied libration half-amplitude, with its event count and exposure printed beneath it; the heavy rule is the registered bar. The lowest band carries no event on 48 per cent of the exposure one expected event needs, so it is drawn as a labelled gap rather than as a zero. The dashed rule at the foot is the low-orbit control, which returns no event at all on 18.8 million object-days -- what a control that does not leak looks like on the same axis.](latex/paper-d/figs/geo-leak-by-amplitude.pdf)

<!-- figure: docs/latex/paper-d/figs/geo-leak-by-amplitude.pdf, drawn by tools/make_figures.py from docs/geo-libration-epoch-control-20260922-receipt.json postRegistrationDiagnostics.leakByImpliedAmplitudeBand: impliedUMaxDegFrom, impliedUMaxDegTo, epochObjectDays, t8aEvents, reading.leakRatio, reading.leakRatioCi95, reading.bar, reading.evaluable; and docs/proximity-leo-results-20260922.md section 6.1 for the low-orbit control's exposure -->

Two registered validations of that control were also missed and are reported as misses rather than repaired. Synthetic free librators had to be admitted at 200 of 200 and were admitted at 191; the bar was unattainable against the registration's own family-wise test level of 0.10 per run, so a 4.5% loss is *better* than the ceiling and the bar was the defect <!-- src: docs/geo-libration-epoch-control-results-20260922.md, section 3 -->. Synthetic station-keepers had to be excluded at 200 of 200 and one survived, 0.241 degrees from an unstable longitude — which exposed that the registration had solved its blind-band condition only near the stable side, when the restoring acceleration vanishes at the unstable longitudes too, making the blind band 16.32% of longitude rather than the 8.16% stated <!-- src: docs/geo-libration-epoch-control-results-20260922.md, section 3 -->.

A second near-geostationary control, registered separately and built on a derived sign-and-persistence clause rather than on libration epochs, returns the same registered verdict: *a leak-free GEO control does not exist*. Its approach-event reading is the first leak-free one in this programme — 0 events on 25,714 object-days, 1.535 times the exposure one expected event needs, with an exact 95% interval of [0.0000, 2.4116] that says plainly one event would have ended it — but its tandem reading sits at 0.061 of the exposure a meaningful zero requires and is read as nothing, and **its trigger-chain reading is worse than the control it was built to improve: 318 chains on the same 25,714 object-days, a leak of 0.4837 [0.4319, 0.5399] against a bar of 0.10 and against the 0.288 above** <!-- src: docs/t28-geo-sign-control-results-20260923.md, section 0 -->. Its registration predicted that rise in advance, for the reason that a class demanding positive evidence of free motion is selected for containing exactly the chains the consumer counts.

The mechanism behind that failure is measured and is the more transferable half: **persistence does not buy what independence would buy.** Six consecutive free-sign chains were derived to occur at one part in 6,900 under independence and occur at a factor of 2.66, because the conditional probability of a free sign given the previous one is 0.5994 against a marginal of 0.2660. A sign that is misread is misread again, since the misreading is a property of where the object sits and how it is sampled rather than of a coin <!-- src: docs/t28-geo-sign-control-results-20260923.md, section 0 -->.

One limitation bounds what that control's clauses may be said to have established, and it is stated in its own results document: on the real archive neither its sign clause nor its amplitude clause refused anything, and all of the classifier's work was done by a persistence requirement that refused 2,466 of 2,605 epochs for carrying fewer than six chains. The substrate is the reason — an epoch is admitted only where the rule that predicts and subtracts free motion already raises no flag, so keeper-like motion has been excluded before the sign clause is asked. The sign test is validated on synthetics there and unexercised on the archive <!-- src: docs/t28-geo-sign-control-results-20260923.md, section 0, limitation block -->.

So §6's statement that the near-geostationary catalogues remain uncontrolled rests on two independently registered controls rather than one.


### 5.7 The aggregate null, scoped hard

One aggregate result belongs on the record's front page and it is a caution rather than a finding. Over 2,956 relocations and 1,000 permutations in which each real arrival keeps its approacher, its epoch and its entire drift history and is given an arrival longitude drawn from the distribution of longitudes occupied at that epoch, the observation is **1,091 against a null mean of 2,385.7, 95% interval [2,203, 2,589], with the null exceeding the observation in 1,000 of 1,000 permutations** <!-- src: docs/proximity-results-20260922.md, section 6 -->. Relocations end up within 0.1 degrees of another object about 2.2 times *less* often than that null predicts.

**That is arithmetic about slot availability and licenses no statement about anyone's behaviour.** The occupied-longitude distribution is heavily clustered, and an object relocating for ordinary reasons is choosing a slot it can actually occupy, which is by construction one of the emptier ones. Drawing an arrival longitude from the *occupied* distribution asks whether objects move to occupied slots, and they cannot, because an occupied slot is occupied. The committed prior-art sweep forbids reading it as avoidance, and this paper does not <!-- src: docs/proximity-priorart-20260922.md, forbidden phrasings -->. What it does establish is that the **aggregate** event count carries no evidence of excess proximity-seeking; if there is structure in that catalogue it is per-object, and the per-object skill is 13.7% for predicting a loiter duration and 0.8% for predicting a closest separation <!-- src: docs/proximity-results-20260922.md, sections 5.2 and 6 -->.

The low-orbit mirror image is reported with the same scoping. There the observation is about **18 times above** a stratum-matched null, with zero of 1,000 permutations reaching it — but the excess is objects inside a constellation deliberately holding position relative to one another, which the null does not model because it models where objects are and not who flies in formation <!-- src: docs/proximity-leo-results-20260922.md, section 5.1 -->.

---

## 6. What the record cannot say, and why

Each refusal below is tied to the measurement that forces it. None is a preference.

**It cannot resolve a reachable set beyond +20 days, or an arrival time beyond +10.** §2.5. Beyond +20 days the median forward error exceeds the median gap between occupied longitudes, so the *membership* of the set is unresolved, not merely its timing <!-- src: docs/kinematic-inputs-results-20260922.md, section 2.5 -->.

**It cannot offer a 180-day reach horizon**, because the alarm's own registered fitness bar fires there: the Arm A median of 2.651 degrees exceeds 2.0 <!-- src: docs/kinematic-inputs-results-20260922.md, section 2.5 -->.

**It cannot claim a validated near-geostationary detection, because there is no control.** §5.6. Every reading of the best available control leaks, the best ratio is 2.6 times the bar, and the registered words are that the catalogues remain uncontrolled <!-- src: docs/geo-libration-epoch-control-results-20260922.md, sections 0 and 5.1 -->.

**It cannot say anything about an individual object's own past.** §5.3. The per-object predictor's gate fired in every stratum and the threshold does not exist <!-- src: docs/trigger-alarm-results-20260922.md, section 6.2 -->.

**It cannot use the word the detector has not earned.** The shipped bundle's label permission is false — a passive control of 34 flags in 1,941 intervals — so the section's rail label, its rows and its alerts do not use it <!-- src: docs/orbits-section-design-20260922.md, section 1; docs/orbit-changes-record-20260923.json, manoeuvreLabelPermitted false -->.

**It cannot quote a velocity change, a propellant figure, a mass or a remaining life** on any surface of the section. The one occurrence of a velocity-change term in the section's own sources is inside the never-say list, which is the gate itself <!-- src: docs/orbits-section-design-20260922.md, section 4 -->.

**It cannot say a miss distance or a collision risk.** Mean longitude is a slot coordinate; the low-orbit estimand is a plane angle, a phase angle and a semi-major-axis difference. The registration derives why a miss distance is not obtainable from public two-line elements at all: two near-circular orbits of similar radius always cross, whatever their plane separation, so the miss is decided entirely by a 5,479 degree-per-day fast angle at a positional accuracy public elements do not carry <!-- src: docs/proximity-leo-results-20260922.md, section 1.1 -->.

**It cannot treat absence as evidence.** The catalogue is a lower bound: 33% of the near-geostationary events had no confirmable initiating change, the low-orbit plane channel was blind, and 86% of the burns on the best-labelled spacecraft available fall below the detector's floor. Catalogue completeness is untested and untestable from inside <!-- src: docs/proximity-results-20260922.md, section 9; docs/proximity-leo-results-20260922.md, section 10 -->.

**It cannot report continuous thrust above the drag regime at all.** §2.3. There is no onset instrument, and the surface prints that rather than implying the objects are quiet <!-- src: docs/change-ledger-and-reading-design-20260922.md, section 1.6 -->.

**It cannot report a state rate.** The episode-state classifier that would measure the share of initiated episodes reaching completion, the false-completion rate at the registered dwell and at twice it, and the count of episodes opened on never-manoeuvred objects has a registration and no result. The record prints that state rates are unmeasured <!-- src: docs/change-ledger-and-reading-design-20260922.md, section 5, M8 -->.

**And the alerts are a research instrument rather than a warning product.** Every alert on the public surface is a labelled replay of 2010 to 2020 on an injected clock; no timer and no scheduled entry exists; the low-orbit arm draws its own withheld gate with the number that withheld it; and nothing on the surface is a statement about what is happening today <!-- src: docs/research-program-runbook-20260921.md, T12 row; docs/alarm-lane-build-20260922.md, section 9 -->. The programme's own adversarial assessment recommends against shipping the alarm as a product on exactly these numbers — 0.103% overall precision, 3.41% at best, no gain from tightening, a failed low-orbit control and no leak-free control at the belt — and we report that recommendation here rather than leaving a reader to infer it <!-- src: docs/oh-wow-assessment-20260922.md, section 7 -->.

One further limit is not a property of this record but of the data underneath any such record, and it is reported as a companion note rather than as a chapter of this paper. A registered measurement of a megaconstellation operator's own public ephemerides found that beyond a lead of exactly 48.000 hours a newer issue republishes the previous issue's states verbatim; that across 11,137 files the number of distinct published one-sigma values collapses to 12, 13 and 13 from 58 hours out to 72; that the in-track value *decreases* with lead in 66.3% of files between 24 and 36 hours, which no propagated uncertainty can do; and that containment against the operator's own published covariance holds to 36 hours and then falls to 16.1% [15.0, 17.4] at 48 hours <!-- src: docs/t19-covariance-realism-results-20260923.md, section 1 -->. The word throughout that measurement is *self-consistency*, never accuracy, because a later issue is a later prediction and not a truth. It bears on this record only as a caution about a class of input that a reader might assume is better than the catalogue: at long lead, the published uncertainty on those files is not a propagated uncertainty at all.

---

## 7. Reproducibility

### 7.1 Registrations precede results

Every measurement reported here was governed by a registration that fixed its estimand, its thresholds, its gates and its decision rules, and that was recorded in the repository before its instrument existed and before any of its numbers did. The ordering is therefore a property of the repository's history rather than a claim made in prose, and Appendix A gives each measurement's registration and result identifiers so that a reader holding the repository can check it.

Where a measurement departed from its registration, the departure is declared in that measurement's own results document and is reported as a departure in this paper: the registered bar the type library missed (§3.2), the smoothing prior that was wrong for a base rate of one in a thousand (§5.3), the validation bars the libration-epoch control could not meet (§5.6), and the sweep grid the differential measurement had to extend (§4.4) are all of that kind. No threshold, gate or decision rule was altered after a number existed.

The analysis code, every artefact this paper cites and the verification commands are published in the release repository at https://github.com/theinformed/orbit-audit.

### 7.2 The external anchor, and exactly what it proves

The registration documents are anchored by an external timestamping service. Two manifests of cryptographic hashes — listing each registration document's hash and, for the recorded set, the repository identifiers of the registrations themselves — were stamped to a public blockchain on 21 September 2026, and the manifests with their proof files are published, alongside the analysis code and every artefact the companion papers cite, in the public release repository at https://github.com/theinformed/orbit-audit, together with the verification commands. Both attestations are complete <!-- src: docs/research-program-runbook-20260921.md, "PUBLISHED + SUBMITTED" block -->.

What the anchor proves is bounded and we state the bound. It establishes that every registration document existed, byte for byte, no later than the stamp date. It does **not** retroactively prove that each registration preceded its results, because the stamps postdate the experiments they govern. That finer ordering rests on the repository's history, whose registration identifiers the anchored manifest names; the anchor ensures any future rewriting of that record cannot go unnoticed. Registrations made after the stamp date are stamped before their experiments run, which closes the gap prospectively. The word *verifiable* is reserved for what a reader can check themselves: the documents against the manifests, and the manifests against the public attestations.

Several of the registrations in Appendix A postdate that stamp. Those rest on the repository's history alone, and this paper says so rather than implying a coverage the anchor does not have.

### 7.3 The release gate

The record's own publication passes a gate before it reaches a reader, and the gate is procedural rather than aspirational. The release is built outside the repository tree, the frontend and the data half are deployed together, and the served bundle is verified byte-identical to the built copy on both the loopback interface and the public address. The deployment held a mutation claim for two minutes, kept a rollback snapshot, rebuilt only the web service, and verified the container healthy with zero restarts <!-- src: docs/research-program-runbook-20260921.md, T12 row -->.

The test gates run at that release were: the full frontend suite at 2,589 of 2,589 across 138 files; the section's own suites at 83 and 34; the release step's own tests at 35 of 35; every test reaching the changed module at 65 of 65; and the five programme modules at 439 of 439 <!-- src: the deployment's own gate table, carried in the change record referenced by docs/research-program-runbook-20260921.md, T12 -->.

### 7.4 Figures

Every figure in this paper is drawn from an artifact held in the repository, by one program held there with it, deterministically: no randomness is used anywhere, the creation timestamp is suppressed, and two runs on the same artifacts produce byte-identical output. The provenance of each figure — the source file and the fields read — travels with it as a comment in both this draft and its typeset form, so a reader can check a plotted value against a receipt without running anything. The counts in Figure 1 come from a census of the published record that pins that record's own hash and performs no measurement of its own <!-- src: tools/make_figures.py and tools/orbit_changes_record_census.py -->.

### 7.5 What is not reproducible, in those words

1. **No timer has been installed and none has been exercised, because none exists.** What has been exercised is the job a timer would run, over a decade of history, at a derived cadence, with an injected clock <!-- src: docs/alarm-lane-build-20260922.md, section 9 -->.
2. **A live resolver has not been exercised past the end of the outcome record.** For an alert whose horizon closes after those records end, the lane returns a labelled gap, which is exercised; the arrival detector that would fill that gap for a genuinely live lane has not been wired into the sidecar <!-- src: docs/alarm-lane-build-20260922.md, section 9 -->.
3. **The archive-wide low-orbit measurement for that arm's own trigger has not been run.** Its precision figure is measured over the declared replay window only <!-- src: docs/alarm-lane-build-20260922.md, section 9 -->.
4. **Nothing in the lane has been exercised against a concurrent writer.** Its state file and ledger are written by one process, and the lane does not lock <!-- src: docs/alarm-lane-build-20260922.md, section 9 -->.
5. **The plane channel of the low-orbit arm is unbuilt and stays unbuilt**; its noise floor is still 145 times too large, so no matching product exists against it and none of its vocabulary reaches any output string <!-- src: docs/alarm-lane-build-20260922.md, section 9 -->.
6. **The medium- and high-eccentricity regimes have no arm.** Two events and zero events respectively, both labelled underpowered <!-- src: docs/proximity-leo-results-20260922.md, section 9 -->.
7. **The ladder replay has a registration and no result.** Until it is measured, every reach stage above the first prints *no number until the replay*, and §2.4's third line carries that string rather than a figure on all but 500 of the record's episodes.

---

## 8. Conclusion

A public record of orbit changes is easy to build and hard to justify. The arithmetic that produces the entries is a few pages; the measurements that say what an entry means run to a dozen registrations, and most of them came back with answers their authors did not want.

The record described here holds 1,992 episodes assembled from 2,058 detected steps, with 130 steps that opened nothing and 161 episodes whose onset was never seen, all counted on the face of the record. Its forward path stops at +20 days because that is where the measured error stops resolving one occupied longitude from the next. Its type library leaves 80.0% of near-geostationary burns unlabelled and says so. Its detection recall is 7.94% on the best-labelled population available, which is a low outlier against published figures on the same spacecraft, and the same measurement shows why: 86% of those operators' burns fall below a threshold set by a population statistic 130 to 470 times coarser than the objects under test. Two thirds of the recall that remains is reachable from the archive's sampling schedule alone. Its alarm fires 0.103% true at the population level and 3.41% in its one reproducible class, tightening the evidence does not improve that, and its low-orbit arm publishes a withheld gate instead of an alert because its own control fires at 0.797 of the treated rate.

And the belt at the centre of most of it has no leak-free passive control, for a reason that is physics rather than engineering: a slow librator dwells near occupied longitudes for months, which is precisely the shape an approach detector is built to find. That is measured on 517,391 object-days with the leak falling by a factor of twelve as the libration gets faster, and it caps every near-geostationary statement in this programme at *reported, not claimed*.

None of that was repaired to make the record look better. The registered bars that were missed are printed as missed, the derivations that were falsified are printed with their errors identified, and the two gates that withhold the most interesting sentences — the one about an individual object and the one about a low-orbit alert — remain shut. What the record offers a reader is not a better list than a commercial service would sell. It is a list whose every entry names the measurement that licenses it, and prints the measurement that is missing where there is none.

---

## Appendix A. Registration and result identifiers

Identifiers are those of the repository from which this paper is written; each registration is a single document and each result a single results document with its machine receipt.

| measurement | registration | result |
|---|---|---|
| Near-geostationary approach events (§5.1, §5.2, §5.5, §5.7) | `c898397` | `4182a98` |
| Low-orbit co-orbital stations (§5.1, §5.2, §5.5) | `23d4776` | `7a515fd` |
| Trigger-time predictor and its classes (§5.2, §5.3) | `154c53f` | `c7e5d5e` |
| Operating-point curve and the replay (§5.4) | `13e80ed` | `be5166c` |
| Libration-epoch control (§5.6) | `86e80c3` | `a84b0ed` |
| Sign-and-persistence control (§5.6) | `b56c8b6` | `cb25357` |
| Manoeuvre-type library, version 2 (§3) | `b648755` | `c2e0b9d` |
| Truth set, detection floor and recall (§4.1 to §4.3) | `9df7675` | `7bdf09a` |
| Per-object-noise arm (§4.7) | `b85df25` | `804b046` |
| Differential detection (§4.4) | `ca7ce73` | `34c9904` |
| Schedule floor (§4.5) | `2618343` | `c62b298` |
| Physics-scheduled null and the sign test (§4.6) | `1f27ef5` | `978d5f4` |
| Kinematic inputs, the horizon and the phase (§2.5, §2.6) | `3f8bcab` | `518cddb` |
| Covariance realism of public ephemerides (§6) | `d246fb4` | `8327443` |
| Ladder replay (§2.4, §7.5) | `bb0eb17` | none |
| The published record (§2.1, §7.3) | none | `abbb153` |

<!-- src: identifiers read from the repository's own history; the registration column is the commit that carries the registration document alone, the result column the commit that first carries the results document -->

## Acknowledgments

The authors used large language models to assist with manuscript preparation and analysis tooling, and take full responsibility for the content. The authors thank David Robinson and Taylor Wulff-Morrison for code development and draft review.

## References

Brown, L. D., Cai, T. T., & DasGupta, A. (2001). Interval estimation for a binomial proportion. *Statistical Science*, 16(2), 101–133. https://doi.org/10.1214/ss/1009213286

Cipollone, R., Raviola, A., & Di Lizia, P. (2025). Machine-learning approaches to manoeuvre detection from two-line element data. In *Proceedings of the 9th European Conference on Space Debris (ESA SDC9)*, paper 249.

Decoto, W., & Loerch, A. (2015). Maneuver detection of satellites using two line element (TLE) data. In *Proceedings of the Advanced Maui Optical and Space Surveillance Technologies Conference (AMOS 2015)*. https://amostech.com/TechnicalPapers/2015/Orbital_Debris/Decoto.pdf

Flohrer, T., Krag, H., & Klinkrad, H. (2008). Assessment and categorization of TLE orbit errors for the US SSN catalogue. In *Proceedings of the Advanced Maui Optical and Space Surveillance Technologies Conference (AMOS 2008)*. https://amostech.com/TechnicalPapers/2008/Orbital_Debris/Flohrer.pdf

Fu, Y. (2026). Multi-tier labeling and physics-informed learning for orbital anomaly detection at scale. *arXiv preprint* arXiv:2605.09790.

Guo, Z., Shi, Q., Xu, X., Ge, L., Zhu, H., Ben, L., Nie, B., Zhao, Y., & Li, X. (2026). MAD-LEO: a maneuver-annotated orbital dataset for LEO satellites with tiered multi-source evidence. *arXiv preprint* arXiv:2609.08556.

Jeffreys, H. (1946). An invariant form for the prior probability in estimation problems. *Proceedings of the Royal Society of London A*, 186, 453–461. https://doi.org/10.1098/rspa.1946.0056

Kelecy, T., Hall, D., Hamada, K., & Stocker, D. (2007). Satellite maneuver detection using two-line element (TLE) data. In *Proceedings of the Advanced Maui Optical and Space Surveillance Technologies Conference (AMOS 2007)*. https://amostech.com/TechnicalPapers/2007/Modeling_Analysis_Simulation/Kelecy.pdf

Lemmens, S., & Krag, H. (2014). Two-line-elements-based maneuver detection methods for satellites in low earth orbit. *Journal of Guidance, Control, and Dynamics*, 37(3), 860–868. https://doi.org/10.2514/1.61300

Oltrogge, D. (2023). Addressing the debilitating effects of maneuvers on SSA accuracy and timeliness. In *Proceedings of the Advanced Maui Optical and Space Surveillance Technologies Conference (AMOS 2023)*. https://amostech.com/TechnicalPapers/2023/SDA/Oltrogge.pdf

Pastor, A., Escobar, D., Sanjurjo-Rivo, M., & Agueda, A. (2021). Statistical and machine learning methods for satellite manoeuvre detection from TLE data. In *Proceedings of the 8th European Conference on Space Debris (ESA SDC8)*, paper 233.

Roberts, T. G. (2021). Geosynchronous satellite maneuver classification via supervised machine learning. In *Proceedings of the Advanced Maui Optical and Space Surveillance Technologies Conference (AMOS 2021)*. https://amostech.com/TechnicalPapers/2021/Machine-Learning-for-SSA-Applications/Roberts.pdf

Roberts, T. G., Siew, P. M., Jang, D., & Linares, R. (2023). A deep dive into the geosynchronous belt: analyzing patterns of life of the geosynchronous satellite population. In *Proceedings of the Advanced Maui Optical and Space Surveillance Technologies Conference (AMOS 2023)*.

Shorten, D., Yang, Y., Maclean, C., & Roughan, M. (2022). Towards a benchmark dataset for satellite manoeuvre detection. *arXiv preprint* arXiv:2212.08662; and *Journal of Spacecraft and Rockets*. https://doi.org/10.2514/1.A35642

Siew, P. M., Jang, D., Roberts, T. G., & Linares, R. (2023). Space-based sensor tasking and pattern-of-life benchmarking for geosynchronous satellites. In *Proceedings of the Advanced Maui Optical and Space Surveillance Technologies Conference (AMOS 2023)*.

Tack, J., & Nezda, C. (2023). Space object maneuver detection (Raytheon Company, assignee). *U.S. Patent No. 11,649,076 B2*, filed February 20, 2020, issued May 16, 2023.

Vallado, D. A., Crawford, P., Hujsak, R., & Kelso, T. S. (2006). Revisiting Spacetrack Report #3. In *AIAA/AAS Astrodynamics Specialist Conference and Exhibit*. https://doi.org/10.2514/6.2006-6753

<!-- Reference list. Entries for Kelecy et al. 2007, Flohrer et al. 2008, Lemmens & Krag 2014, Tack & Nezda 2023, Fu 2026, Guo et al. 2026, Brown et al. 2001, Jeffreys 1946 and Vallado et al. 2006 were verified against live external sources on 2026-09-21 for the companion papers and are reused unchanged. Decoto & Loerch 2015, Oltrogge 2023, Pastor et al. 2021, Roberts 2021, Roberts et al. 2023, Shorten et al. 2022 and Siew et al. 2023 are taken from the committed prior-art sweeps of 2026-09-20 and 2026-09-22, which verified each at title and venue level; where a sweep recorded that a full text could not be read, the citation is used at abstract level only and this paper makes no claim about those papers' methods beyond what the sweeps recorded. This is a bibliography, not a measured claim, so entries carry no docs/ src: provenance comment. -->
