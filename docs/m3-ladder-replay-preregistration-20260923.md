# M3 — the sequential precision ladder, calibrated on the archive — REGISTRATION, committed alone before any number

**Date:** 2026-09-23. **Status:** registration. **No measurement code for this
track exists at this commit** and no number below is a result; every figure
quoted is quoted from an already-committed document with its source, and every
threshold, stage rule, horizon, control and gate is fixed here before the data
is touched. **Scope:** M3 of `docs/kinematic-reach-design-20260922.md` §9 — the
§4 calibration replay of the sequential precision ladder S1–S4, per regime.

**What this registers.**

| Design item | Registered in |
|---|---|
| §3.2 the stages S0/S1/S2/S3/S4/E, and the set-enlarging rule | §2 |
| §2.1–2.5 the reachable set and its horizon | §3 |
| §4 estimands E1–E5 | §4 |
| §4 controls (a)(b)(c) and nulls N1/N2 | §5 |
| the cadence, the dial's role, whether GEO rungs are reported, the sign test | §6 — **all four decided here, before any number** |
| §4 decision rules, gates S/T/U, the falsifier | §7 |
| §3.5 addendum — the operating-point rows with `stage` as an axis | §6.2, §8 |

**Inherited unchanged and not re-opened:** the vocabulary gate and the
never-say list (`docs/alarm-lane-design-20260922.md` §6–§7); the prior-art
bans (`docs/proximity-priorart-20260922.md`); the fuel policy — no propellant,
mass, consumable or remaining-life figure is read, computed or published for
any object; the reserved operator decisions (alarm design §10, change-ledger
design §6); the T8d causal contract (only element sets with epoch ≤ the
stage's own trigger epoch feed any stage feature); the registered floors
(σ_ḋ = 6.0385e-4 °/day, the 0.010 °/day flag floor, the 0.020 °/day stationed
band, T8a's 0.1° / 30 d co-location, T8b's 0.2° / ±5° / 30 d co-orbital
station). **No registry or country code enters any rule, feature, grouping or
output column of this measurement.** Nothing here is a miss distance, a
conjunction or a statement of intent.

---

## 0. The estimand in one sentence

For each regime, each rung S1–S4 of the ladder and each class: **the fraction
of historical burn sequences that reached that rung and then ended in
co-location (GEO) or co-orbital station (LEO) with any catalogued object
inside the outcome horizon, counted with its Wilson 95% interval over a
denominator that includes every sequence that reached the rung and expired** —
together with the set size at the rung, the lead from the rung to arrival, the
fraction of eventual partners that were inside the set when the rung opened,
and the rate at which rungs expire.

---

## 1. Why this, and what each outcome changes

The single-burn number is already measured and it is bounded: 0.103% over the
whole population (101 of 97,784) and 3.406% [2.367, 4.879] for class 1
(28 of 822), `docs/alarm-lane-model-20260922.json`. The design's claim is that
the **burns that follow** carry information the first does not — the
operator's "this could result in X so we watch it, and when the second burn
comes, now we know". M3 is the measurement that decides whether that claim
earns a number.

| outcome | what it changes |
|---|---|
| a rung above S1 speaks (§7's rung rule met) | R3 of the change-ledger reading (`docs/change-ledger-and-reading-design-20260922.md` §2.1) prints a stage precision above S1; the operating-point table gains its `stage` axis with real rows; the "watching" card of kinematic design §7 has a ladder to climb |
| no rung above S1 speaks | the design's own falsifier fires (§7); the page prints the stage and the set and **no number above S1**, and the multi-burn framing is published as not earned, at the same prominence as a pass |
| Gate S fires (partner absent from R₁ in more than half of S4 events) | the reachable-set definition (its horizon or its budget) is wrong and the layer is withheld entirely |
| Gate U fires | that regime's ladder is void until the leak is named |

---

## 2. The stages, fixed before any number

An **episode** is the unit. It opens at an S1 and closes at S4 or at E. A rung
is *reached* once per episode: **each episode contributes at most one entry to
each rung's denominator**, at the first moment it satisfies that rung.

### 2.1 S0 and S1

**S0** — stationed, no confirmed change. Not an alert, not counted, no record.

**S1** — the first confirmed change. The trigger is unchanged from T8d and the
alarm lane: a maximal flag chain (`trigger_alarm.flag_baselines` +
`chain_flags`, `MERGE_DAYS = 5.0`) on an active-class object at GEO; a
campaign-initiating confirmed in-track flag of a payload-class object at LEO
(`proximity_plane.detect_manoeuvres` → `alarm_lane_leo.campaign_starts`,
`CAMPAIGN_MAX_GAP_DAYS = 180.0`). The announce time is the detector's own:
`tAnnounce = tTrig + CONFIRM_DAYS` (5 d at GEO; 0 d at LEO, where the confirm
rule is inside the flag), snapped forward to the first tick of §6.1.

At S1 the reachable set R₁ is computed from the mover's newest element set at
or before `tTrig` and from no other:

- **GEO.** λ and ḋ from the confirming element set; the J22 forward path
  `trigger_alarm.propagate(λ, ḋ, horizon_days = H_R)`; the occupied mean
  longitudes at `tTrig` from `trigger_alarm.OccupancySweep.at(tTrig, mover)`
  — the registered occupancy definition, causal by construction;
  `trigger_alarm.slots_reached(path, lons, tol_deg = 0.1)`. **R₁ = the set of
  catalogued objects whose station the path passes within 0.1° of inside
  H_R.** `setSizePlaneCompatible` = the members with |Δi| ≤ 0.5°
  (`PLANE_MATCH_DEG`). Both counts are recorded and both are printed wherever
  the set is printed.
- **LEO.** **R₁ = the set of catalogued LEO objects whose orbit plane agrees
  with the mover's to ≤ 0.2°** (T8b's θ_p) at `tTrig`, plane separation being
  the angle between orbit normals built from (i, Ω). This is the design's own
  §2.3(i) consequence, quoted: *"inside a shared plane, phasing is nearly free
  and fast: the LEO reachable set at any budget above ~1 m/s contains every
  object in the plane."* No cross-plane arm is computed (M6 is the standing
  dependency and the plane channel is blind); the LEO set therefore prints
  *cross-plane reach is not computed* wherever it appears.

An S1 whose trigger fails the lane's own labelled-gap rules (`alarm_lane.
Sidecar._gap_reason`: a look-back shorter than the baseline window, a
look-back shorter than 30 d, an element-set gap across the trigger longer than
the 5 d merge window, or a baseline drift outside the eligibility floor) is
**NOT ASSESSABLE** — recorded, counted, and excluded from every precision
denominator. A labelled gap is never a zero and never a miss.

The class is assigned at S1 by the frozen taxonomy
(`alarm_lane.classify` against `trigger-time-taxonomy/20260922/1`, checksum
`9cf012aa…`) at GEO; LEO has one class, `PHASING-CAMPAIGN`
(`leo-phasing-campaign/20260922/2`, checksum `d11552b6…`), because that arm has
no taxonomy.

### 2.2 S2, and the set-enlarging rule

**S2** — a second confirmed change announced while the episode is open (before
S4 and before E), with the mover not arrived. Let `reach(new)` be the set
computed by §2.1's rule at the new trigger.

- **The set-enlarging rule, registered in these two clauses.** The new burn
  opens a **fresh S1** — closing the current episode as `reopened-at-S1`, which
  counts as an expiry of the old episode and not as an arrival — **if either**
  `|reach(new)| > |R_prev|` **or** `R_prev ∩ reach(new) = ∅`. This is the
  design's "a burn that enlarges the set (a new drift start after a stop) opens
  a fresh S1", written as a checkable predicate.
- Otherwise the episode advances to S2 with **R₂ = R_prev ∩ reach(new)**.
  Members whose earliest arrival now exceeds the horizon are marked *no longer
  reachable* and **kept, labelled** — never deleted.
- A third and further shrinking burn re-enters S2. The episode's S2 denominator
  entry is made once, at the first S2.

An episode never advances a rung without a new confirmed element set: the
"silent upgrade" the alarm design forbids is structurally impossible here
because every rung transition is keyed to an element-set epoch.

### 2.3 S3 — deceleration with the propagated stop inside one member

Evaluated at each of the mover's element sets while the episode is open at S1
or S2, on that element set and on nothing later.

**GEO.** Let ḋ_k, ḋ_{k-1}, ḋ_{k-2} be the drift rates at the three newest
element sets at or before the clock. S3 requires **all** of:

1. |ḋ_k| < |ḋ_{k-1}| < |ḋ_{k-2}| — the drift is decelerating across ≥ 2
   successive element sets, as the design says;
2. |ḋ_{k-2}| ≥ 0.010 °/day — the deceleration starts above the detector's own
   floor, so it is not noise inside the stationed band;
3. the least-squares line through (t, ḋ) over those three points has a
   zero-crossing `t_s` with 0 < t_s − t_k ≤ H_R;
4. the **propagated stop longitude** λ_stop — the J22 RK4 of
   `trigger_alarm.propagate` run with the fitted constant deceleration added to
   the tesseral acceleration, integrated to `t_s` — lies within **0.1°** of the
   propagated station of **exactly one** member of R_prev, each member's station
   advanced from its own newest pre-clock element set at its own drift rate
   (the occupancy definition's own linear advance);
5. R₃ = {that one member}.

**LEO.** The along-track phase is not carried by this arm's element extract,
and the design's rule ("phase rate falling") is expressed in the coordinate
that drives it, δa, with the substitution **declared here before any number**:
S3 requires that the mover's semi-major-axis offset from exactly one member of
R_prev, |δa_j|, decreases monotonically across ≥ 3 successive element sets and
that its least-squares line reaches **|δa| ≤ 0.050 km** (T8b's own `DA_FLOOR`,
`proximity_plane`) within H_R, for exactly one member. *Phase rate is
proportional to δa; the substitution is a change of coordinate, not of rule,
and it is a declared deviation from the design's wording (§9).*

S3's announce time is the first tick at or after the epoch of the third
element set satisfying the rule. S3 may be reached from S1 directly (the
continuous-raise and two-burn cases of the change-ledger design §1.5).

### 2.4 S4, E, and the outcome

**S4** — the T8a / T8b event criteria met. The outcome rule is the alarm
lane's, unchanged (`alarm_lane.resolve_ledger`):

- **GEO**: a primary-arm event of `docs/proximity-events-20260922.jsonl`
  (`approacherClass == "active"`, `attribution == "resolved"`) on this object
  whose `initiatingFlagMs` lies in [tFirst, tTrig] of **any chain belonging to
  this episode**, and whose `arrivalMs` is **after the rung's announce time**.
  An arrival before the announce warned nobody and is counted as a miss with
  the reason recorded, exactly as the lane counts it.
- **LEO**: an `armM` event of `docs/proximity-leo-events-20260922.jsonl` on
  this object whose `campaignStartMs` falls inside the campaign this episode
  opened (window `tFirst − 180 d ≤ campaignStartMs < next campaign start`,
  `alarm_lane_leo.resolve_leo`'s own rule) and whose `arrivalMs` is after the
  rung's announce and inside the horizon.

The **partner** is `targetNorad` (GEO) / `target` (LEO).

**E — expiry** — the outcome horizon H_O passes with no S4, or the episode is
closed by the set-enlarging rule of §2.2. **Every expiry is counted in every
denominator of every rung the episode reached, and no expiry is ever deleted.**

**Not assessable.** Where the outcome record ends before the episode's horizon
closes, the episode resolves `not-assessable` — a labelled gap, never a miss —
excluded from n and reported with its count.

### 2.5 The ladder record

One JSON row per episode: `norad`, `regime`, `class`, per-rung
`{stage, tTrigMs, tAnnounceMs, announcedAtMs, setSize, setSizePlaneCompatible,
members[], n1ChanceMembership}`, `deepestStage`, `outcome`
(`arrival | none | not-assessable | reopened-at-S1`), `arrivalMs`,
`partnerNorad`, `partnerInR1`, `partnerInR2`, `earliestRungContainingPartner`,
`timeInStageDays[]`, `t13Type`, `modelVersion`, `tableChecksum`. No member is
dropped; a member that left the set carries `droppedAtStage`.

---

## 3. The two horizons, and why there must be two

M1 (`docs/kinematic-inputs-results-20260922.md` §2.5) is **binding** and cuts
the design's horizon: the GEO forward error's median is 0.408° at +30 d,
1.076° at +60 d, 1.520° at +90 d and 2.651° at +180 d against a measured median
slot spacing of 0.394° and Gate W's registered 2.0° bar, so *membership* of the
reachable set is resolvable only to **+20 d** and arrival timing to
co-location precision only to **+10 d**. The outcome horizon is a different
quantity: it is the window in which an arrival counts, and it is T8d's and the
lane's, unchanged, or the rung precisions could not be compared with S1's own
published figure.

| | GEO | LEO |
|---|---|---|
| **H_R — the set's horizon** (governing) | **20 d** (M1) | **90 d** (M2: 85.9% of arm-M objects keep the along-track phase inside Γ = 5° at +90 d) |
| H_R — the second arm, reported beside it | **180 d**, the horizon the committed operating-point table already uses, printed **with M1's finding that the +180 d arm is unfit by T8d's own registered bar** | 1,095 d, T8b's look-back |
| **H_O — the outcome horizon** (governing) | **180 d** (`trigger_alarm.H_DAYS`, the lane's own) | **1,095 d** (`proximity_plane.T_LOOK_DAYS`, the lane's own) |
| H_O — sensitivity arm | 90 d (class 1's p95 arrival) | — |

Both H_R arms are computed for every episode. **Gate S is evaluated on the
governing arm (H_R = 20 d at GEO, 90 d at LEO)**, and the second arm is printed
beside it so a reader can see whether a Gate S failure is driven by the
horizon. No member arrival window is drawn beyond +10 d at GEO; beyond it a
member carries *arrival window not measured beyond 10 days*. No LEO member
arrival window is drawn at all (M2's horizon is per object and this replay does
not compute per-object phase error).

---

## 4. Estimands

Per **regime × rung × class**, and pooled over classes:

| # | Estimand | Definition |
|---|---|---|
| **E1** | rung precision | k/n with Wilson 95%, where n = episodes that reached the rung and resolved (arrival or expiry), k = those whose S4 arrival is after that rung's announce time and inside H_O. `not-assessable` rows are excluded from n and their count printed. |
| **E2** | set size at the rung | p5/p25/p50/p75/p95 of `setSize` and of `setSizePlaneCompatible`, **split by whether the episode ended in S4**, as the design asks |
| **E3** | lead | days from the rung's announce to arrival: Kaplan–Meier median with p25/p75, look-back floor 1,095 d, censoring reported; and the raw percentiles beside it |
| **E4** | **recall of the set** | over every S4 event in the window: the fraction whose eventual partner was inside R₁ at S1, inside R₂ at S2, and the earliest rung whose set contained it. Reported on both H_R arms. |
| **E5** | expiry rate and time in stage | per rung: the share of episodes reaching it that expire without advancing, the share closed by the set-enlarging rule, and p25/p50/p75 of days spent in the stage |

Every cell prints its n. **n < 20 is UNDERPOWERED, in those words**
(`alarm_lane.MIN_SUPPORT_FOR_A_RATE`), the count is quoted and no rate is drawn
from it.

---

## 5. Controls and nulls

**(a) The never-manoeuvred control.** A rung reached by an object that cannot
burn is a leak.

- **LEO**: T8b's registered never-manoeuvred population — zero detected
  manoeuvres, ≥ 200 element sets, ≥ 365 d span
  (`proximity_plane.CONTROL_MIN_ELEMENT_SETS = 200`,
  `CONTROL_MIN_SPAN_DAYS = 365.0`), 3,011 objects, 0 arm-G events over
  18,792,698 object-days. **Declared in advance: this control is CIRCULAR for
  S1**, because "never-manoeuvred" is defined by the absence of a flag from the
  very detector that defines S1, so its zero at every rung is a tautology and is
  reported as a tautology and not as evidence. The substantive LEO leak control
  is therefore **(a′) the non-payload control the lane already uses** — objects
  the catalogue does not class as payloads — whose per-object alert rate the
  lane measured at **0.7971 of the payload rate against a bar of 0.001**. (a′)
  is run through the full ladder and its per-rung counts are printed.
- **GEO**: **control (a) DOES NOT EXIST**, in those words. T8e's verdict
  stands — *the GEO catalogues remain uncontrolled* — and its measured size is
  the leak of this very trigger: **3,812 flag chains inside 517,391 days of
  provably uncontrolled motion, 0.288 [0.279, 0.298] of the rate it fires on
  objects that can manoeuvre**, against a bar of 0.10
  (`docs/geo-libration-epoch-control-results-20260922.md`). M7 remains owed.

**(b) The routine-operations control.** Each episode's S1 burn is joined by
`(norad, epochMs)` to the committed v2 manoeuvre-library ledger
(`docs/manoeuvre-library-ledger-v2-20260922.jsonl`, `libraryVersion = "v2"`,
`rulesSha256 = e2e0cbbd…`), and the share of each routine type that climbs each
rung is reported: `station acquisition` (G3), `drift stop` (G2, the return to a
slot already held), `graveyard raise` (G6), `phasing` (P3), `east-west keeping`
(G4), `north-south keeping` (G5), and the episode type `relocation`.
**Declared in advance: the committed ledger is a SUBSET** — 10,326 rows of
3,914,621, every matched row plus a seeded uniform sample of the rest — so the
joined population is a sample of the ladder's episodes and its per-type n is
printed on every row; a type with fewer than 20 joined episodes is
UNDERPOWERED and lends its name to nothing. No type is re-implemented here: an
unjoined episode's type is a labelled gap, never an inferred label.

**(c) The time-shuffled control.** The flag-attribution rule of §2.4 cannot
survive a displacement of the arrival epochs — nothing would match — so Gate T
is evaluated on a **window-rule** pair, both arms computed the same way:

- *real arm*: an episode is a hit if an event of the same object has
  `arrivalMs` in (rung announce, rung announce + H_O];
- *shuffled arm*: for each of **200 draws**, seed **20260922**, every event's
  `arrivalMs` is displaced by a single common offset δ drawn uniformly from
  [−W/2, +W/2] and wrapped modulo the window length W inside the replay window;
  the episodes, their stages and their sets are unchanged.

Reported: the real window-rule precision per rung, the shuffled mean and its
p5–p95 across draws. The flag-rule precision of §2.4 remains the governing
headline; the window-rule pair exists only to discharge Gate T.

**N1 — chance membership.** Per rung, the median of |R_k| divided by the number
of stationed objects at that epoch (GEO: the occupancy table's own count; LEO:
the objects in band with a usable element set). This is the probability a
randomly drawn stationed object lies in R_k and it is printed beside every set
size.

**N2 — the analytic J2 co-planarity null** applies to LEO cross-plane members
only. **The cross-plane arm is not computed** (§2.1), so N2 is a labelled gap
whose owed measurement is M6.

---

## 6. The four decisions taken now, before any number

### 6.1 The persistence and announce cadence

The tick is the **derived cadence** — the median element-set spacing measured
on this run's own element sets, `alarm_lane.derive_cadence`'s work floor — and
not a period anyone chose. The lane measured **0.7564 d** on the near-GEO watch
and **0.4934633622685185 d** in the LEO band and window; this replay
re-measures it and uses what it measures, recording both the measured value and
the lane's for comparison.

A rung is spoken at the first tick at or after its announce time. The delay
between the announce time the rule defines and the tick the ladder actually
spoke is measured and reported per rung, as the lane reports it.

**Persistence sweeps = 1 in the primary arm.** A setting with
`persistenceSweeps > 1` delays the announcement by N−1 firings and withdraws a
trigger that stops drifting; that axis changes announce timing and is **not**
re-measured here. Registered consequence: the stage rows of §6.2 are measured
at `persistenceSweeps = 1` **for every setting**, and each row says so.

### 6.2 The dial's role

The operating-point table gains `stage` as a fourth axis, per kinematic design
§3.5. The rows are produced by **post-filtering the episodes on each named
setting's evidence axes at the episode's S1 trigger** — `minDriftChangeDegPerDay`
against the chain's drift change and `minSlotsReached` against
`fwd_slots_reached` at the table's own 180-day horizon, which is how the
committed curve defines them — for the four named settings `everything`,
`balanced`, `high-confidence`, `very-high`. The dial's stops are unchanged.
**A stage that has no row is not offered**, and a stage whose row is
UNDERPOWERED is offered with that label and no rate. The page may not
interpolate between stages and may not borrow one stage's precision for
another.

### 6.3 Whether GEO rungs are reported at all, given the leak

**Decision: GEO rungs ARE reported, with the leak ratio printed beside every
one of them, and never as a class precision.** The sentence that travels with
every GEO rung, fixed here:

> *The GEO catalogues remain uncontrolled. This trigger fires 3,812 times
> inside 517,391 days of provably uncontrolled motion — 0.288 [0.279, 0.298] of
> the rate it fires on objects that can manoeuvre, against a bar of 0.10. A
> rung precision measured here is a property of this detector on this
> catalogue, not a rate at which objects of a class do anything.*

The alternative — withholding GEO entirely — was considered and rejected
because the leak is measured and printable, and a measured caveat is stronger
than an absence. The alternative of printing the rungs bare was rejected
because a bare rung reads as a class rate.

### 6.4 The T22 sign test as an S2 feature — decided: NOT registered

The scheduled-null track's ramp-sign-versus-slot-side clause separates east-west
carriers (0.8294 [0.8251, 0.8336] of 29,836 flag chains) from same-shell
passives (0.1515 [0.1434, 0.1600] of 7,160). It is **not** made a feature of
any rung here, for three reasons fixed before any number:

1. its own results document states it is *not a detector, no threshold is
   proposed there*, and its recall is UNMEASURED;
2. the passive population it separates against is the one T8e says is not
   clean, so its separation is measured against a leaking comparator;
3. a rung whose definition mixed a kinematic predicate with an unvalidated
   discriminator could not be read as a kinematic fact about the trajectory,
   which is the only thing this ladder is permitted to say.

It is recorded per S1 burn as a **carried field and nothing else**, so a later
registration can test it without re-running the replay.

---

## 7. Decision rules, gates, and the falsifier

**The rung rule** (design §4, unchanged). A rung may speak if and only if:

1. **n ≥ 20**;
2. its **Wilson lower bound exceeds the previous rung's point precision**; and
3. **control (a) is zero** for that regime — which at GEO it cannot be, because
   control (a) does not exist; a GEO rung therefore speaks only under §6.3's
   printed caveat, and never as a class precision.

**Gate S.** If E4 shows the eventual partner absent from R₁ in **more than half**
of S4 events on the governing H_R arm, the reachable-set definition (its
horizon H or its budget B) is wrong and **the layer is withheld entirely**.

**Gate T.** If a rung's precision under the time-shuffle control of §5(c) is not
separated from the real one — the real window-rule point estimate inside the
shuffled p5–p95 band — that rung **re-describes geometry and is withheld**.

**Gate U.** Any rung reached by a never-manoeuvred object **voids that regime's
ladder until the leak is named**. Declared in advance: at LEO the control is
circular for S1 (§5a) and its zero is a tautology; the substantive reading is
control (a′), whose leak is reported rather than gated on, and the GEO ladder
carries §6.3's sentence in place of a gate it cannot discharge.

**What falsifies the sequential layer, in these words:**

> **S2/S3 precision not separated above S1** — the burns that follow carry no
> information beyond the first — **OR partner absent from R₁ in > 50% of S4
> events.**

Either result is published at the same prominence as a pass, and the verdict
line of the results document is the **first line** of §1 and reads exactly one
of **YES**, **NO** or **UNDERPOWERED**, per regime, to the question *does the
ladder earn a rung above S1*.

---

## 8. Outputs, and the gates on publishing them

| path | content |
|---|---|
| `tools/ladder_replay.py` | the instrument, committed **after** this document |
| `tests/test_ladder_replay.py` | the offline proofs; each opens with the bug it must catch |
| `docs/m3-ladder-20260923.json` | every rung table with its n, E1–E5, the controls, the nulls, the gates |
| `docs/m3-ladder-20260923-receipt.json` | provenance, input sha256s, window, tick, wall and CPU seconds |
| `docs/m3-ladder-episodes-20260923.jsonl` | a committed subset of the episode records: **every episode that reached S2 or above, every episode an arrival resolved, plus a seed-20260922 uniform sample of at most 1,000 of the rest**, with the full file's row count and sha256 in its provenance row |
| `docs/m3-ladder-operating-points-20260923.json` | the §6.2 rows, `stage` as an axis |
| `docs/m3-ladder-results-20260923.md` | the results, verdict on line 1 per regime |

**Publishing gates.** No rate is printed for a cell with n < 20 except as an
UNDERPOWERED count. No zero is printed where a channel is blind or a record
ends: a labelled gap, in those words. No GEO rung is printed without §6.3's
sentence. No number from one rung, class, regime or setting is printed for
another. No delta-v, propellant, mass or remaining-life quantity is computed or
printed for any object. No registry or country code appears in any row. No
intent vocabulary and no registry code appears anywhere in the instrument, the
tests, the data or the documents.

---

## 9. Declared deviations and blind spots

1. **LEO S3 is expressed in δa, not in phase** (§2.3). The element extract this
   arm reuses carries mean motion, eccentricity, inclination and right
   ascension, and not argument of perigee or mean anomaly, so the along-track
   phase is not available. Phase rate is proportional to δa and the
   substitution is a change of coordinate; it is declared here because a
   registration is a promise about what will be measured.
2. **The LEO reachable set has no phase coordinate and no cross-plane arm.** It
   is the in-plane population at θ_p = 0.2°, and it prints *cross-plane reach is
   not computed*. M6 remains the dependency.
3. **The routine control (b) is joined against a committed subset** of the
   manoeuvre library's ledger, 10,326 of 3,914,621 rows (§5b).
4. **The replay is IN SAMPLE for the GEO taxonomy**: the frozen partition was
   fitted on the whole 1959–2026 primary arm, which contains this window. Every
   precision measured here is in sample for the taxonomy and the document says
   so in those words, as the lane's own replay does.
5. **Recall of the initiating flag is UNMEASURED**: 33% of the co-location
   catalogue's events carry no visible initiating flag, so an episode that never
   opened cannot be counted. E4 measures the recall of the *set* given an
   episode, not the recall of the detector.
6. **The GEO ladder has no control that can be discharged** (§5a, §6.3).
7. **Nothing here is scheduled.** The replay is run to completion in the session
   that registers it, with an injected clock, and no timer or cron entry is
   installed by this or any other part of this track.
8. **The event-driven pass.** The ladder evaluates only at epochs at which the
   mover's newest element set has advanced — the lane's own cadence gate — and
   snaps every announce to the tick grid. A test asserts on a fixture that a
   full tick loop and this pass produce identical records; if the assertion
   fails the full loop is used and the substitution is withdrawn.

---

## 10. Compute

CPU only, on `pc`, `nice`-d, one core for the GEO arm and one for the LEO arm.
**No GPU is taken and no `gpu-consumers.json` row is owed.** The GEO arm reuses
the cached near-GEO extract under `runtime/proximity-geo` and the flag memo of
`alarm_lane.MemoisedFlags`; the LEO arm reuses the existing extract cache under
`/home/sdegan/alarm-lane-leo` for its own declared window, and writes no new
extract. Working files stay under `/home/sdegan/` and outside the repository;
only the artefacts of §8 are committed. Expected order, from the lane's own
measured runs: GEO minutes, LEO minutes plus the detect stage.

**Windows, both outcome-blind and both fixed before any number here, because
both are inherited:** GEO **2010-01-01 → 2020-01-01**, the decade with the most
confirmed drift changes (71,661 of 226,422 flag chains), chosen on alert volume;
LEO **2020-01-01 → 2023-06-01** with a look-back from 2017-01-01, the earliest
span of the decade holding the largest payload population for which every
alert's 1,095-day horizon still closes inside the archive.

---

## 11. What is committed with this document

**This file and nothing else.** The instrument, its tests, the JSON artefacts,
the episode ledger, the results document, the runbook row, the design's §9 M3
line and the notebook entry are all written afterwards, and the ordering in
`git log` is the evidence.

---

## 12. Sources

```
docs/kinematic-reach-design-20260922.md              §2, §3, §4, §7, §9
docs/kinematic-inputs-results-20260922.md            M0 §1.2, M1 §2.2/§2.4/§2.5, M2 §3.3/§3.4
docs/change-ledger-and-reading-design-20260922.md    §1.5, §2.1 R3, §4.1
docs/alarm-lane-design-20260922.md                   §2.3, §5.2, §6, §7
docs/alarm-lane-build-20260922.md                    §3, §5, §6, §7
docs/alarm-lane-model-20260922.json                  the frozen taxonomy and the base rate
docs/alarm-lane-operating-points-20260922.json       the four named settings
docs/alarm-lane-leo-model-20260922.json              the LEO arm's single class
docs/alarm-lane-leo-replay-20260922-receipt.json     the LEO window, tick and control
docs/trigger-alarm-results-20260922.md               §3.1, §3.4, §4 Gate W
docs/proximity-results-20260922.md                   the co-location catalogue
docs/proximity-leo-results-20260922.md               §2.5, §3.1, §4.3, §6.1, §7.2
docs/manoeuvre-library-results-v2-20260922.md        the v2 types and their agreement
docs/geo-libration-epoch-control-results-20260922.md the GEO leak, 0.288 [0.279, 0.298]
docs/geo-passive-control-results-20260922.md         the GEO catalogues remain uncontrolled
docs/t22-scheduled-null-results-20260923.md          §7.3, the clause not adopted here
tools/trigger_alarm.py  alarm_lane.py  alarm_lane_leo.py  proximity_geo.py  proximity_plane.py
```

Quoted above and not re-derived: 101/97,784 and 28/822 with their intervals;
the forward-error medians 0.408/1.076/1.520/2.651° and the 0.394° slot spacing;
the 20 d and 10 d horizons; 85.9% at +90 d; 3,011 objects and 0 events over
18,792,698 object-days; 0.7971 against a bar of 0.001; 3,812 chains in 517,391
object-days and 0.288 [0.279, 0.298]; 0.8294 and 0.1515 with their intervals;
71,661 of 226,422; 0.7564 d and 0.4934633622685185 d.

**Derived here and labelled as such at every appearance:** the set-enlarging
predicate of §2.2; the three-element-set deceleration rule and its
zero-crossing stop of §2.3; the δa substitution for LEO phase rate; the
two-horizon split of §3; the window-rule pairing of Gate T; the one-entry-per-
episode-per-rung counting rule of §2.
