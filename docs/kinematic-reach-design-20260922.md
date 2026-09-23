# The kinematic reach layer, the manoeuvre library and patterns of life — DESIGN ONLY

**Date:** 2026-09-22. **Status:** design; nothing here is built, measured or
registered. **Scope:** the "will" layer of the early-warning capability (physical
reachability after a detected burn), the sequential test over burn sequences,
its calibration registration, and the two supporting tracks T13 (manoeuvre
library) and T14 (patterns of life). **Builds on:** the alarm-lane design
(`docs/alarm-lane-design-20260922.md`), the Orbit-changes section design
(`docs/orbits-section-design-20260922.md`), T8a/T8b/T8c/T8d, T10, T11.
**Inherits unchanged:** the vocabulary gate (alarm design §6), the never-say
list (§7), the prior-art bans, the fuel policy, and every reserved operator
decision (§10). Every number below is either quoted from a committed result
with its source, or derived here and labelled *derived*.

The operator's brief, which this document answers: *not just whether a
manoeuvre matches historical patterns that brought objects into contact, but
whether a manoeuvre WILL bring a satellite into orbit with another; the hard
part being a burn that sets up a second burn — "this could result in X so we
watch it", and when the second burn comes, "now we know"; and a library of
manoeuvre types and of patterns of life, documenting whether certain objects
or classes do anything odd worth studying.*

---

## 0. The answer to "can we say a burn WILL bring it to another satellite"

No — and the reason is the physics, not the data. A single burn fixes the
mover's new orbit; it does not fix where the mover will stop, because stopping
is a second burn the archive has not seen yet. What one burn does fix is the
**reachable set**: the catalogued objects whose station the new orbit can be
brought to within a horizon, with a second burn of a size this class routinely
makes. At GEO that set is almost never small: for the one class that may
already speak (T8d class 1), requiring the propagated path to cross at least
20 occupied longitudes removes 3 of 821 historical alerts
(`docs/alarm-lane-operating-points-20260922.json`, minSlotsReached 0 vs 20,
horizon 180 d). At LEO a plane-matching setup burn is ~40× cheaper flown as an
altitude change plus months of waiting (§2.3), so the setup burn is visible
long before the burn that resolves it. What CAN be said after one burn is a
fact with a measured precision: "this object's new orbit reaches the stations
of N catalogued objects within D days; k of n changes of this class at this
stage ended within 0.1° of any satellite's station for 30 days or more." Each
further burn shrinks N and moves the sentence to a later stage with its own
measured precision. The set collapsing to one object is a kinematic fact about
the trajectory, never a statement of intent, spoken only at the precision the
replay has measured for that stage — today, **no number until the replay**.

---

## 1. What already exists and is reused, not rebuilt

| Piece | Where | What it gives this design |
|---|---|---|
| Mean longitude λ, unwrap, drift rate ḋ, station segments, drift-change flags at the published σ_ḋ = 6.04e-4 °/d and 0.010 °/d floor | `tools/proximity_geo.py` | the GEO trigger and the belt occupancy |
| J22 forward propagation (`propagate`, RK4, K = 1.70e-3 °/d²), `slots_reached`, occupancy sweep, the 19 trigger-time features incl. `fwd_slots_reached`, `fwd_plane_compatible_slots` (0.5°) | `tools/trigger_alarm.py` | the GEO reachable set at trigger, already measured (Gate W 0.408° at +30 d) |
| Orbit normal, plane separation, `j2_nodal_rate_deg_per_day`, `j2_nodal_rate_d_da`, phase rate per km, phase-confinement bound, sparse screen (CPU 12.8× faster than GPU) | `tools/proximity_plane.py` | the LEO plane and phasing kinematics |
| Exact minimum impulse between two element states (`dv_impulsive`: one-impulse law of cosines, two-impulse apsis pair with optimal plane-change split), Edelbaum, node reduction | `tools/transfer_loss.py` | the dV pricing of "what a second burn would cost"; shipped price audited at median 0.942 of exact, max 93.4× — the exact form is used, never the shipped price |
| Frozen taxonomy (k = 2), scaler, per-class precision, never-say list, operating-point table (108 rows: horizon × drift × set-size × persistence) | `docs/alarm-lane-model-20260922.json`, `docs/alarm-lane-operating-points-20260922.json` | the stage-1 precision and the dial |
| 487 GEO co-locations (T8a), 71 LEO co-orbital stations (T8b), 226,422 flag chains (T8d, 5,904-row committed subset + full-table hash), 738 N-S and the E-W ledgers (T10b/c), 58 transfers / 267 burn intervals (T10a) | `docs/*-20260922.jsonl` | the labelled events T13 is scored against and the sequences §4 replays |
| Persistent pairs, arrival order, post-arrival response hazard | T11 (in flight) | the T14 response-to-arrival feature |

---

## 2. The WILL layer: the reachable set

### 2.1 Definition

Given a confirmed burn on mover *m* at t₀ with post-burn elements **x** and
their scatter, the reachable set R(t₀, H, B) is every catalogued object *j*
such that there exists a further impulse sequence of total exact-minimum cost
≤ B (§2.4) bringing *m* into **co-location** with *j* (T8a: within 0.1° of
*j*'s mean longitude, held ≥ 30 d) or **co-orbital station** with *j* (T8b:
plane agreement ≤ 0.2°, phase inside ±5°, ≥ 30 d) with arrival no later than
t₀ + H. Per member the layer outputs the minimum additional cost, the earliest
arrival, and an interval on each. Neither definition is a miss distance and
neither is a conjunction; that sentence prints wherever the set does.

### 2.2 GEO kinematics — derived, and checked against the repo's constants

A tangential impulse dv changes semi-major axis by da = 2 dv / n and the mean
longitude drift by ḋ = −(3/2)(ω_E / a) da (both from Kepler's third law; the
repo carries them as `DRIFT_PER_KM` and `DRIFT_PER_M_S`). At a = 42,164.17 km,
v = 3.0747 km/s:

| Quantity | Value | Note |
|---|---:|---|
| da per m/s | 27.43 km | derived |
| drift per m/s | **0.3522 °/day** | derived; equals `proximity_geo.DRIFT_PER_M_S` |
| detector floor 0.010 °/day | 0.028 m/s | T8d §3.1's "routine correction exceeds it" |
| E-W cycle burn at ±0.0208° deadband, 0.0675 m/s (T10c derived) | 0.024 °/day | above the floor, hence ~7,200 triggers/yr |
| stop burn for observed transfer drift, p5/p25/p50/p75/p95 of T8a §3.2 (0.0131/0.0226/0.0668/0.458/1.334 °/day) | 0.04 / 0.06 / **0.19** / 1.30 / 3.79 m/s | derived from committed quantiles |
| inclination match, per degree | 53.7 m/s | 2 v sin(Δi/2), derived |
| J22 term omitted by a straight line, ½KH² | 0.76° @30 d, 6.9° @90 d, 27.5° @180 d | T8d §4 |
| element noise alone, σ_ḋ · H | 0.018° @30 d, 0.11° @180 d | orbits design §2.2 |

**Consequences.** (i) Longitude is not a constraint at GEO: every stationed
longitude in the drift direction within ḋ·H (J22-corrected) is reachable with
a stop burn of under 4 m/s for 95% of historical transfers. The GEO reachable
set therefore IS `slots_reached` on the propagated path, which T8d already
computes, and the time-to-reach of member *j* is the propagated crossing time
of λ_j. (ii) Inclination is the only expensive coordinate: co-location as T8a
defines it does not read *i* at all, but a physical co-orbital station does,
and `fwd_plane_compatible_slots` (Δi ≤ 0.5°, i.e. ≤ 27 m/s) already splits the
set. Both counts are output; the page names which one it is printing. (iii) The
arrival-time interval for member *j* is the measured forward error divided by
the drift: at the median transfer drift 0.0668 °/day, T8d's 0.408° median
(p95 2.08°) at +30 d is **6 d (p95 31 d)** of arrival-time uncertainty; at
0.5 °/day it is 0.8 d (p95 4 d). That error is what the object does next, not
what the elements cannot resolve (22× the noise floor), so it cannot be
reduced by better arithmetic — only re-measured at longer horizons (§2.5).

### 2.3 LEO kinematics — derived, and checked against T8b's figures

At a = 6,878 km (500 km altitude), v = 7.6126 km/s, n = 15.22 rev/day, i = 53°:

| Quantity | Value | Note |
|---|---:|---|
| da per m/s | 1.807 km | derived |
| relative phase rate per km of δa | 1.195 °/day | `phase_rate_deg_per_day_per_km` |
| phase rate per m/s | 2.16 °/day | derived |
| phase 180° in 90 d / in 30 d | 0.93 / 2.78 m/s each way | derived |
| inclination change, per degree | 132.9 m/s | 2 v sin(Δi/2); T8b §4.1 quotes 133 |
| J2 nodal rate Ω̇ = −(3/2) J2 n (R/a)² cos i | −4.60 °/day | T8b §2.3 quotes 4.6 |
| dΩ̇/da = −(7/2) Ω̇ / a | 2.34e-3 °/day per km; 0.234 °/day per 100 km | T8b §4.1 quotes 0.234 |
| close ΔΩ = 10° in 180 d via altitude | δa 23.7 km, 13.1 m/s up + 13.1 down = 26 m/s | derived |
| the same 10° bought directly (plane angle ≈ ΔΩ sin i = 8.0°) | 1,061 m/s | derived — **40× dearer** |
| close ΔΩ = 1° in 180 d | 2.4 km, 2.6 m/s total | derived |

**Consequences.** (i) Inside a shared plane, phasing is nearly free and fast:
the LEO reachable set at any budget above ~1 m/s contains every object in the
plane (T8b's population — the in-track phasing campaigns whose 195.9 d median
lead is measured). (ii) Across planes, J2 does not touch inclination, so
|Δi| ≤ B / (133 m/s per degree) is the hard cut on the set; RAAN is closable
cheaply but slowly, at 2.34e-3 °/day per km of altitude offset. A LEO altitude
change of tens of kilometres with no phasing partner in its own plane is
therefore *exactly* the operator's "setup burn": its reachable set is every
object with |Δi| inside the budget and |ΔΩ| ≤ dΩ̇/da · δa · H, and it
resolves only when the reverse altitude burn arrives months later. (iii) The
plane-manoeuvre channel is blind today (T8b Gate A, 5σ_θ = 3.5°); the diagnostic
floor 0.000148° (T8b §2.4) says it need not be. **The LEO cross-plane arm of
this layer cannot be built until that floor is re-derived and registered** —
already the standing T8b/T5b item, restated here as a hard dependency.

### 2.4 The budget prior B — from committed ledgers, not invented

"Plausible remaining budget" is deliberately NOT remaining propellant: the
odometer's `propellantRemainingUpperBoundKg` exists for 151 commercial-civil
objects only (`docs/fuel-odometer-20260920.jsonl`) and the fuel policy forbids
inference for anything else. B is instead the **class-conditional size of the
next burn**, from what objects of the same manoeuvre class historically did:

| Manoeuvre class | Committed source | What is measured today | What is NOT yet tabulated |
|---|---|---|---|
| relocation stop | `docs/proximity-events-20260922.jsonl`, `transferDriftDegPerDay` (487) | drift quantiles → stop cost 0.04–3.79 m/s (§2.2, derived) | nothing further |
| any confirmed drift change | `docs/trigger-alarm-triggers-20260922.jsonl`, `init_drift_change_mag` (5,904-row subset; full table 226,422 rows, sha `f4c3ca9b…`) | present per row | its quantiles — **M0** |
| N-S keeping | `docs/stationkeeping-ns-20260922.jsonl`, `dvExactMinimumMps` (738 events, 66 objects) | T10b median achieved Δi 0.0346° → 1.86 m/s per burn (derived) | per-bus quantiles — **M0** |
| E-W keeping | `docs/stationkeeping-ew-20260922.jsonl`; T10c derivation | 0.0675 m/s per cycle at ±0.0208° (derived, `runtimeProofs`); detected ledger recall 1.81% | a measured per-burn distribution (recall-limited; may stay derived) |
| transfer legs | `docs/transfer-loss-20260922.jsonl` (58 chemical, 267 intervals) | `detectedPathMps`, `idealMps` per phase | per-leg quantiles — **M0** |
| LEO phasing / plane | T8b campaigns (`manoeuvresInCampaign`, `phaseRateMaxDegPerDay`) | phase rates per event | δa and Δi quantiles per campaign — **M0** |

B for a member candidate is the class p95 of the next-burn size (§5 supplies
the class); a candidate whose minimum additional cost exceeds the class p95 is
listed as *outside this class's historical range*, never dropped. M0 is one
tabulation over files already committed and is the first measurement owed.

### 2.5 The horizon H — bounded by measured error growth, reconciled with the +30 d ribbon

The site design derived a GEO ribbon from σ_ḋ alone (0.018° at 30 d), replaced
it with T8d's measured 0.408°/0.898°/2.08° (p50/p75/p95) at +30 d, and stops
there because nothing longer is measured. This design keeps that rule: the set
is drawn to the class p95 arrival time (90 d for class 1, 158 d for all
triggers, T8d §3.4), and each member's arrival interval uses the forward error
**at its crossing time** — which needs **Gate W re-measured at +60, +90,
+180 d (M1)** over the same 49,318 no-further-flag triggers. Until M1 lands,
members beyond +30 d carry "arrival window not measured beyond 30 days" and
no interval. At LEO, σ_n = 6.27e-5 rev/day is 18.9 m of semi-major axis →
0.023 °/day of phase → 2.0° at 90 d and 4.4° at 196 d, inside Γ = 5° at the
median but not for the p95 object (5.4e-3 rev/day → 1.6 km → 1.9 °/day, phase
lost in days), and drag is unmodelled (87.4% of passives trip the in-track
detector, T8b §7.2). The LEO phase horizon is therefore **per object**; the
plane (RAAN) horizon is long (scatter 0.000148°). No LEO member interval is
drawn until per-object phase-error growth is measured (**M2**).

### 2.6 Output contract, per burn

| Field | Content |
|---|---|
| `mover`, `tTrig`, `tConfirm`, `stage` | NORAD, trigger and confirmation epochs, sequential stage (§3) |
| `postBurnState` ± scatter | a, e, i, Ω, λ (GEO) or a, i, Ω, phase (LEO), with the per-object element scatter |
| `members[]` | NORAD; `earliestArrivalDays` + interval (§2.5); `minAdditionalCostMps` + interval (exact-minimum form; the interval from the element scatter propagated through `dv_impulsive`); `planeCompatible` (Δi ≤ 0.5° / 0.2°); `withinClassRange` (cost ≤ class p95 of §2.4); `basis` (co-location / co-orbital station) |
| `setSize`, `setSizePlaneCompatible` | counts, both printed |
| `stagePrecision` | k/n and Wilson 95% for (class, stage, evidence cell) from the replay table; absent → "no number until the replay" |
| `modelVersion`, `tableChecksum` | the frozen artefacts that earned every figure |

**Surface rule for the cost field.** A dV figure is a kinematic quantity here,
but the standing policy (alarm design §7.5) forbids delta-V, propellant or
mass on any surface for any object. The ledger carries `minAdditionalCostMps`;
the page prints the same physics in element units — the drift-rate change (GEO)
or semi-major-axis change (LEO) a stop would need — unless the operator rules
otherwise. That is a reserved decision, added to §10's list as 10.8.

### 2.7 What the committed table already says about set size — the uncomfortable fact

The operating-point table sweeps `minSlotsReached` ∈ {0, 5, 20}. For class 1
at 180 d, persistence 1: 821/28 alerts/arrivals at ≥ 0, 821/28 at ≥ 5,
818/28 at ≥ 20. **The reachable-set size does not discriminate at trigger
time; class 1 is by construction the large-set class** (T8d §5.3 names it by
path length and occupied longitudes crossed). A first burn at GEO leaves a set
of at least 20 candidates in 99.6% of the alerts that may speak. So the "will"
question is decided by the burns that follow, not by the first — which is the
operator's multi-burn framing, now with a number behind it.

---

## 3. The multi-burn problem: a sequential precision ladder

### 3.1 Ladder, not posterior — and why

A candidate-set posterior needs a prior over targets and a likelihood of the
observed burn under "heading for *j*" versus "routine"; neither is calibratable
from element sets (no operator intent is observed, and T8d Gate H showed a
mis-set prior producing a predictor worse than the base rate — the Beta(1,1)
smoother against a 0.1% base rate). A **ladder of measured precisions per
stage** needs no prior: each rung is a k/n over every historical sequence that
reached that rung, the T8d denominator discipline applied stage by stage. It is
the only construction whose every spoken number is a count over a committed
catalogue, and it composes directly with the existing operating-point table by
adding one axis, `stage`.

### 3.2 The stages

| Stage | Trigger condition (all at the mover's newest confirmed element set) | Set operation | What the page may say, once the rung's k/n is measured |
|---|---|---|---|
| S0 | stationed, no confirmed change | none | nothing (not an alert) |
| S1 | first confirmed change (T8d flag chain), class assigned | R₁ = reachable set of §2 | "N stations reachable within D days; k/n of class-c changes at S1 ended in co-location with any satellite" (today: 3.41% for class 1, 0.103% base) |
| S2 | a second confirmed change while R₁ is open and the mover has not arrived | R₂ = R₁ ∩ reach(new state); members whose earliest arrival now exceeds H drop to "no longer reachable" (kept, labelled) | "set reduced from N₁ to N₂; k/n at S2" — **no number until the replay** |
| S3 | drift decelerating (GEO: \|ḋ\| falling across ≥ 2 sets; LEO: phase rate falling) with the propagated stop inside 0.1° / ±5° of exactly one member | R₃ = {j} | "consistent with arrival at *j* within D days at k/n historical precision for this stage" — **no number until the replay** |
| S4 | T8a / T8b event criteria met | closed | a state, not a warning: the T11 vocabulary ("stationed beside X since <date>") |
| E | horizon passed, or mover re-stationed elsewhere | closed as miss | counted in every denominator; never deleted |

A burn that *enlarges* the set (a new drift start after a stop) opens a fresh
S1; it does not inherit the earlier stage's precision. An alert never advances
a stage without a new confirmed element set — the "silent upgrade" failure the
alarm design forbids.

### 3.3 Null and alternative, per class

Null H₀: *the sequence is consistent with routine operations of this object's
class* — station acquisition after launch or transfer (drift stop into a
longitude with no prior occupant within 0.1°), relocation to an empty slot
(T8a §6: relocations end near others 2.2× LESS than chance), graveyard raise
(pipeline `geo-graveyard-raise`), constellation phasing (T8b's in-plane
population), routine E-W/N-S keeping (§2.2's 0.024 °/day cycle). Alternative
H₁: *the sequence is consistent with reaching a specific catalogued object.*
The ladder does not test H₁ per object; it measures, per rung and per class,
how often sequences that looked like this ended in S4 with *any* object, and
prints that. The routine-operations null is what the false-alarm rate is
measured against: every routine sequence that reached rung S_k is a false
alarm at S_k, and the rung's precision is k/n over all of them.

### 3.4 Collapse

R collapses when S3 holds. The sentence is a fact about the trajectory: which
member, the predicted arrival window, and the rung's measured k/n. It carries
the two structural caveats verbatim (slot coordinate, not a miss distance;
catalogue is a lower bound), never a purpose, never "approach", never the
object's own history (Gate H). If the S3 rung is UNDERPOWERED (n < 20, alarm
design §5.2) the page prints the member and "insufficient historical cases to
state a precision" — a labelled gap, never a number borrowed from S1.

### 3.5 The hard case, honestly

*GEO two-burn relocation (T8c C2: 4 d at 0.589 °/day, 126 events).* Burn 1 sets
the drift; burn 2 is the stop and IS the arrival. No S2 or S3 exists; the only
warning is S1 at a median 9.9 d with ≥ 20 candidates, and after burn 1 the page
can say the set and the class precision, nothing else. *GEO staged transfer
(C5: 76 d, 11 mid-course flags, 160 events).* Every mid-course flag is an S2
with a shrinking set and the final deceleration an S3 — the class where the
ladder buys warning; its rung precisions are the replay's most important rows.
*LEO altitude-for-node (§2.3).* Burn 1 phases nothing in its own plane; its
set is every object with |Δi| in budget and |ΔΩ| closable in H — potentially
hundreds. Sayable: that set and "no phasing partner in plane". Not sayable:
whether or when a reverse burn will come. That burn, months later, is S2/S3
with a set of a few objects; until then the alert sits open at S1 and expires
at the horizon as a counted miss — an expiry rate the replay measures and the
page prints.

---

## 4. Calibration from history — registration outline (to be committed alone, first)

**Population.** Every flag chain in the GEO archive (226,422; primary arm
97,784) and every campaign-initiating in-track manoeuvre of a LEO payload
(T8b's 161 alerts plus the uncorroborated initiating flags), each replayed
causally: only element sets with epoch ≤ the stage's trigger epoch feed any
stage feature (T8d's three-way leakage audit reused).

**Estimands.** Per regime, class and rung S_k: E1 precision k/n with Wilson 95%
(arrival within H after the rung's announce time; arrivals before announce
counted and excluded as T8d §3.2 does). E2 the set size at each rung for
sequences that ended in S4 versus those that did not (medians, p25–p75).
E3 the lead from each rung's announce to arrival (Kaplan–Meier, look-back
1,095 d, censoring reported). E4 for every S4 event: the earliest rung at which
R contained the eventual partner, and the fraction of events whose partner was
in R₁ (the reachable set's *recall*). E5 the expiry rate per rung.

**Controls.** (a) The never-manoeuvred class (T8b §2.5: 3,011 LEO objects; at
GEO the 855-analogue is owed by the T8a v2 control) must produce **zero**
sequences past S1 — any rung reached by an object that cannot burn is a leak,
reported as T8b Gate B reports it. (b) The routine-operations sequences of §3.3
labelled by T13 form the false-alarm denominator per rung. (c) A time-shuffled
control: each S4 partner's arrival epoch displaced by the T8b §6.3 shuffle; the
rung precision under the shuffle bounds what geometry alone buys.

**Nulls.** N1 chance membership: the probability that a randomly drawn
stationed object lies in R_k, from the occupied-longitude (GEO) or
plane-stratum (LEO) distribution at that epoch, T8a §6 / T8b §5.1 machinery.
N2 the analytic J2 co-planarity null (T8b §5.2) for LEO cross-plane members.

**Decision rules, fixed before any number.** A rung may speak if n ≥ 20, its
Wilson lower bound exceeds the previous rung's point precision, and control
(a) is zero. Gate S: if E4 shows the partner absent from R₁ in more than half
of S4 events, the reachable-set definition (H or B) is wrong and the layer is
withheld entirely. Gate T: if a rung's precision under the time-shuffle
control is not separated from the real one, that rung re-describes geometry
and is withheld. Gate U: any rung reached by a never-manoeuvred object voids
that regime's ladder until the leak is named.

**What falsifies the sequential layer.** S2/S3 precisions not separated from
S1's (the burns that follow carry no information beyond the first), or Gate S
firing (the set does not contain the partner when it should). Either result is
published at the same prominence as a pass.

---

## 5. T13 — the manoeuvre library

A versioned taxonomy of manoeuvre **types** classified from element deltas by
derived rules, scored against the labelled events the programme already holds.
The pipeline's 17 signatures (`pipeline/orbit_events.py::SIGNATURES`) are the
starting vocabulary; T13 adds the sequence-level types the alarm needs and
publishes a confusion matrix for every type.

| Type | Derived rule on element deltas (thresholds from the registered floors) | Existing labelled events to score against |
|---|---|---|
| drift start (GEO) | \|Δḋ\| ≥ 0.010 °/d, \|ḋ_after\| > 0.020 °/d (leaves the stationed band), Δi below quantum | 326 T8a initiating flags; T8d flag chains |
| drift stop (GEO) | \|ḋ_before\| > 0.020, \|ḋ_after\| ≤ 0.020 °/d | T8a arrivals (487) |
| relocation | start–stop pair, \|Δλ\| ≥ 2° (T8a's relocation) | T8a 2,956 relocation cases |
| station acquisition | drift stop into a longitude the object never held, within 548 d of launch or after a transfer leg | T10a post-transfer endpoints |
| E-W keeping | \|Δḋ\| ≥ 0.010, both \|ḋ\| ≤ 0.020, inside a station segment, Δi below quantum; expected size ≈ 0.024 °/d (§2.2) | T10c E-W ledger; T3's 208 carriers |
| N-S keeping | Δi ≥ 5σ_i (GEO σ_i 1.67e-4°, quantum 1e-4°), \|Δa\| small; T10b median 0.0346° | 738 T10b events |
| inclination adjust (LEO) | Δi ≥ 0.01° (T8b `I_FLOOR_DEG`), \|Δa\| < 0.05 km | T8b plane flags (1,174 objects) |
| phasing (LEO) | \|Δa\| ≥ 0.05 km with sign reversal inside a campaign, plane unchanged | 71 T8b arm-M campaigns |
| orbit raise / lower, transfer leg | monotone \|Δa\| sequence; pipeline `orbit-raising`/`along-track-raise` etc.; leg membership from T10a phases | 58 transfers, 267 intervals |
| graveyard | pipeline `geo-graveyard-raise` rule, unchanged | pipeline events |
| drag make-up / decay / not separable / re-entry | pipeline rules, unchanged; **never propulsive** | pipeline passive control |
| UNLABELLED | anything else above the noise floor | — |

**Rules of the library.** (1) Every rule is a threshold on the registered
floors, written down with the floor it derives from; no learned classifier.
(2) The confusion matrix is measured per type against the column-3 labels —
which are themselves instrument outputs on the same element sets, not ground
truth, and the document says so: what T13 publishes is *agreement between
independent rule sets*, and the one external truth available (operator burn
logs) is absent from the repository. (3) Every detected burn gets a type and
a **confidence = the type's measured precision in the matrix**, never a
per-event score. (4) Heavy tails rule: the archive's element scatter has
p99/σ of 116 at GEO and 3,558 below 500 km (`docs/orbit-history-design.md`
§2.1), so no rule uses a Gaussian κσ; floors are the registered ones.
(5) UNLABELLED stays UNLABELLED; a type with fewer than 20 supporting events
is UNDERPOWERED and cannot lend its name to an alert. (6) Versioned with a
checksum like the frozen model; a rule change is a new version and a new
matrix. (7) Registry codes enter no rule.

---

## 6. T14 — patterns of life

**Profile, per object** (every feature a count or a rate over element sets):
trigger cadence (T8d `cad_days_since_prev_trigger`); E-W cycle period and
amplitude (T3 per-object fundamental, 13.89–14.10 d); N-S cadence and
placement efficiency η (T10b, per object); kinematic budget rate Σ\|Δḋ\| per
year (GEO) or Σ\|Δa\| per year (LEO) — element units, not fuel; relocation
frequency and typical \|Δλ\|; dwell per station segment; T13 type mix;
response-to-arrival (T11 E3 hazard, when it lands); flag-visible fraction
(T8c: whether an object's transfers are seen at all is a detector property and
is carried as a feature so it cannot masquerade as behaviour).

**Class baseline.** Class = regime × era × bus family where catalogued
(`data/propulsion-catalog-v1.json`, commercial-civil) else regime × era; the
baseline is the class's per-feature empirical distribution (median, p5–p95),
computed on a calibration half and applied to the other, T3-style.

**Anomaly score.** Per feature, the object's rank in its class distribution;
the score is the maximum over features of −log₁₀(two-sided tail rank), with
the feature named. No Gaussian distance (the tails table again). The threshold
is set by a registered false-alarm rate on the held-out half — the fraction of
routine object-years exceeding it — and the page prints that rate beside every
"unusual for its class" line. "Odd" is that measured deviation and nothing
else; an object over threshold is listed with its feature, its value, its
class range, and the rate at which routine objects exceed the same threshold.

**The ownership line.** Registry codes are metadata on the class baseline's
object page and are NEVER an anomaly feature, a grouping of the score, or a
column of any output table: the science is stronger ownership-blind (a
baseline that includes ownership would make "unusual for its nation" the
finding, which is a narrative, not a measurement) and the operator's own rule
keeps our prose to facts. The operator's interest in behaviour by government,
and in patterns worth studying, is served by letting a reader sort and group
published per-object facts however they wish; our outputs author no per-nation
narrative, and reserved decision 10.3 governs whether the codes are visible at
all.

---

## 7. What it looks like on the page

**A "watching" state on the Orbit-changes section.** An alert card gains a
stage stamp (S1 / S2 / S3, in the site's `.layer-status` style) and a
candidate strip: the reachable set drawn on the belt strip (GEO) or the plane
panel (LEO), members listed by earliest arrival, each with its arrival window
(or "not measured beyond 30 days"), its plane-compatibility mark, and the set
count printed as two numbers (all / plane-compatible). Beside the strip, the
rung's own sentence with its k/n and Wilson interval, the S1 base rate, and
the two structural caveats. When a new confirmed element set arrives the card
re-renders from the ledger: members that dropped out are struck through and
kept, the stage stamp moves only if the ledger row says so, and the previous
rung's precision is shown greyed above the current one so a reader sees the
ladder climbed. Closure (S4) hands the card to the T11 vocabulary; expiry
leaves it on the page as a counted miss.

**Composition with the dial.** The operating-point table gains a `stage` axis.
The dial's stops are unchanged — everything / balanced / high-confidence / very
high — but each stop's three numbers become those of its (evidence, stage)
row, and the page says "tighter settings show fewer candidates and later
warning" as it does today. A stage that has no row is not offered.

**A typical month, on today's measured numbers.** About 600 assessed GEO drift
changes appear as a withheld count; about two class-1 alerts are spoken, each
opening at S1 with a set of at least 20 stationed objects in 99.6% of cases
(§2.7) and carrying "3.4% of changes like this ended within 0.1° of any
satellite for 30 days or more; base rate 0.10%". How many advance to S2 or S3
within the month, and at what precision: **no number until the replay** — the
card shows the stage and the set and prints "stage precision not yet measured".
Roughly one alert a year resolves as a co-location (orbits design §8). The LEO
arm shows in-track phasing campaigns only (161 archive alerts at 44.1%, 195.9 d
median lead), with a per-object phase horizon and no cross-plane set until the
plane floor is re-derived.

---

## 8. Compute, order, and what is genuinely hard

| Piece | Size | Where | Basis |
|---|---|---|---|
| GEO reachable set per burn | 180 RK4 steps × 1,768 belt objects; well under 15 ms | CPU | T8d computed all 226,422 propagations inside a 3,308 s run |
| LEO reachable set per burn | a sparse neighbour list in (i, Ω, a); ~3 ms per screening epoch | CPU | T8b: 200 epochs in 0.534 s CPU vs 6.8 s GPU — **CPU won 12.8×** because the phase-confinement bound makes the problem sparse; the same bound applies here |
| live load | ~20 GEO triggers/day (7,200/yr); LEO in-track flags ≤ ~30/day | CPU, seconds | the lane's own sidecar timer, no new container, no GPU consumer row |
| §4 calibration, GEO | 226,422 chains × stage linking + per-rung sets; ≈ 2× T8d's 56 min | CPU, ~2 h | T8d §1 |
| §4 calibration, LEO | ~2.4e5 payload flags (18,865 objects × 0.64/yr × ~20 yr, an upper bound from the passive rate) × 3 ms | CPU, < 15 min | T8b §1.2 |
| T13 matrix, T14 profiles | one pass over the event tables and per-object histories | CPU, minutes | T8c: 403 objects' full histories in 16.3 s |
| M0, M1, M2 | tabulations over committed files; Gate W at three horizons over 49,318 triggers | CPU, minutes | T8d §4 |
| HPC candidate | **none of the above.** The only cluster-sized item this layer depends on is the existing T5b all-vs-all LEO grid (1.91e9 pairs, ~390 core-h) that validates the J2 null on passive pairs — already on the compute-posture list | — | T8b §11 |

**Build order — a registration before every measurement.** (1) M0/M1/M2
tabulations, registered as a supplement to T8d (no new claim). (2) T13
registration → matrix → frozen library v1. (3) §4 registration, committed
alone → replay → rung table (adds the `stage` axis to the operating-point
artefact). (4) Reachable-set fields added to the ledger contract, behind the
same vocabulary gate; page "watching" state built from the synthetic replay
with an injected clock — exercised now, never on a scheduled run. (5) T14
registration → baselines → anomaly rate → page. (6) LEO cross-plane arm only
after the plane-noise floor registration. Nothing is scheduled until (4)'s
replay has produced its rows, and nothing is spoken at a rung without them.

**Hard, or possibly impossible, with public element sets — in those words.**
Physically impossible: any miss distance or conjunction statement (T8b §1.1:
the 5,479 °/day fast angle is not carried). Impossible to observe: the second
burn before it happens, so the GEO two-burn relocation (C2) always gives S1
warning only. Hard and unproven: the LEO cross-plane set (plane channel blind
until re-derived); the LEO phase horizon under drag; the staged-transfer rung
precisions, which may come back unseparated from S1 — the design's own
falsifier. Unmeasured: true recall of the set (33% of T8a's events had no
visible initiating flag). **What T6 (SP ephemerides) would change:** miss
distance and conjunction become estimands; element scatter falls to the SP
covariance; LEO drag is fitted rather than guessed; burns below 0.028 m/s at
GEO become measurable. It would not change §3's logic — the second burn is
still unobserved until it happens — only the sharpness of each rung's set.

---

## 9. Measurements owed before anything here may speak

| # | Measurement | Feeds |
|---|---|---|
| M0 | class-conditional next-burn size quantiles from the committed ledgers (§2.4) | B, `withinClassRange` |
| M1 | Gate W forward error at +60/+90/+180 d, GEO | member arrival windows beyond 30 d |
| M2 | per-object LEO phase-error growth vs σ_n and drag history | LEO member windows |
| M3 | §4 replay: rung precisions, set sizes, recall of the set (E1–E5), controls (a)–(c), gates S/T/U | every S2/S3 sentence; the `stage` axis of the dial |
| M4 | T13 confusion matrix against the labelled events | every type label and its confidence |
| M5 | T14 class baselines and anomaly false-alarm rate on the held-out half | every "unusual for its class" line |
| M6 | plane-noise floor re-derivation and registration (T8b's standing item) | any LEO cross-plane set |
| M7 | T8a v2 dead-payload control at GEO | control (a) at GEO |

---

## 10. Sources of every number

```
docs/alarm-lane-design-20260922.md            §1, §2.3, §4, §5, §6, §7, §8, §10
docs/orbits-section-design-20260922.md        §2.2, §2.3, §3.5, §6, §8
docs/trigger-alarm-results-20260922.md        §0, §3.1–3.4, §4, §5.3, §8, §9
docs/alarm-lane-operating-points-20260922.json  class-1 rows, minSlotsReached 0/5/20
docs/proximity-results-20260922.md            §1.1, §2.2, §3.2, §4, §6, §7.4
docs/proximity-leo-results-20260922.md        §1.1, §1.2, §2.2–2.5, §3.2, §4, §7.2, §11, §12
docs/alarm-pattern-results-20260922.md        §3 (C2, C5)
docs/transfer-loss-results-20260922.md        the minima; the pricing audit (0.942 / 93.4×)
docs/stationkeeping-efficiency-results-20260922.md  T10b verdict; §1.4; §6.2–6.3
docs/orbit-history-design.md                  §2, §2.1 (787 triples; the tails)
docs/proximity-priorart-20260922.md           forbidden phrasings, must-cites
tools/proximity_geo.py, proximity_plane.py, trigger_alarm.py, transfer_loss.py
```
Derived here and labelled as such: every row of the §2.2 and §2.3 tables, the
arrival windows of §2.2(iii), 818/821 = 99.6%, and the compute sizes of §8.
Standard results used (Kepler's third law da = 2 dv/n, the J2 secular nodal
rate, the law-of-cosines impulse) are cited to the repo's own registrations.
