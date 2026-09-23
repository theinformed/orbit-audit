# Kinematic inputs M0, M1, M2 — REGISTRATION, committed alone before any number

**Date:** 2026-09-22. **Status:** registration. No measurement code exists at
this commit and no number below is a result; every figure quoted here is
quoted from an already-committed document with its source, and every threshold
is fixed here before the data is touched.

**What this registers.** The three tabulations `docs/kinematic-reach-design-20260922.md`
§9 owes before the WILL layer may compute a reachable set honestly:

| # | Design §9 | This document |
|---|---|---|
| M0 | class-conditional next-burn size quantiles from the committed ledgers (§2.4) | §2 |
| M1 | Gate W forward error at +60 / +90 / +180 d, GEO (§2.5) | §3 |
| M2 | per-object LEO phase-error growth vs σ_n and drag history (§2.5) | §4 |

They are a **supplement to T8d and T8b: no new claim, no new detector, no new
estimand of the programme's own.** Every instrument is imported from the tool
that already registered it; where this registration adds an arm the design did
not name, the arm is marked **ADDED HERE** with its reason.

**Inherited unchanged and not re-opened:** the fuel policy (no propellant, mass
or consumables figure for any object; §2.5 below states exactly how far a
delta-v figure may go), the never-say list and vocabulary gate
(`docs/alarm-lane-design-20260922.md` §6, §7), the prior-art bans, the surface
rule that a page prints element units rather than delta-v (design §2.6, a
reserved operator decision 10.8 — this registration produces ledger figures,
not page copy), and the ownership line (no registry or country code is read by,
grouped by, or carried on any output of this work).

---

## 0. The three estimands in one sentence each

- **M0.** For each manoeuvre class *as the committed ledgers already label it*,
  the empirical quantiles (p5 / p25 / p50 / p75 / p95) of the **size of one
  burn of that class**, in the element units the ledger carries, with the
  count *n* of burns the quantiles are taken over.
- **M1.** The absolute mean-longitude error of T8d's registered forward
  propagation, measured by T8d's own `validate_propagator` at horizons beyond
  the +30 d it has already published, with its own *n* at each horizon.
- **M2.** Per LEO object, the absolute along-track phase error of a
  constant-mean-motion propagation at +30 / +60 / +90 / +180 d, and the
  fraction of objects for which a 90 d horizon stays inside the T8b phase box.

None of the three is a prediction, a miss distance, a conjunction, or a
statement about any operator's intent.

---

## 1. Why these three, and what each outcome changes in the design

| Measurement | If it comes back as the design assumes | If it comes back otherwise |
|---|---|---|
| **M0** | `withinClassRange` (design §2.6) is computable: a candidate whose minimum additional cost exceeds the class p95 is labelled *outside this class's historical range*, never dropped | a class with **n < 20 is UNDERPOWERED** and supplies no B: the field prints "class range not measured" for every member of that class, and the design's §2.4 table row is struck through until a larger ledger exists |
| **M1** | the member arrival-time interval (design §2.2(iii), §2.5) can be drawn at each member's crossing time out to the class p95 arrival (90 d class 1, 158 d all triggers) | if the median error at a horizon exceeds Gate W's registered 2.0° bar, **the forward geometry is unfit at that horizon** and the design's horizon H is cut to the last horizon that passes; if it exceeds the slot spacing, the *membership* of the set, not merely its timing, is unresolved there and the set may not be drawn to that horizon at all |
| **M2** | the LEO per-object phase horizon of design §2.5 is drawable for most objects | if fewer than half the objects keep a 90 d horizon inside the phase box, the LEO member interval stays withheld by default and is drawn only for the objects that measure inside it — a per-object gate, not a regime-wide one |

**A number that is measured and then not read by the code that should refuse to
cross it is the defect class this programme has already found four times.**
Each of the three therefore names, above, the field that must read it.

---

## 2. M0 — class-conditional next-burn size

### 2.1 What "next-burn size" means here, and what it is not

The estimand is **the size of one burn of a class**, estimated by the empirical
distribution of burn sizes that objects of that class are *observed* to have
made in the committed ledgers. It is deliberately **not** remaining propellant:
`propellantRemainingUpperBoundKg` exists for 151 commercial-civil objects only
(`docs/fuel-odometer-20260920.jsonl`) and the fuel policy forbids the inference
for anything else. No propellant, mass or consumables figure is read, computed
or published by this measurement, and a test asserts that no output row carries
one.

**Three truncations are registered now, before the numbers exist, because they
are properties of the instruments and not of the objects:**

1. **Every distribution is conditional on detection.** A burn below its
   detector's floor is absent from its ledger. The floors are
   the published 0.010 °/day drift-change floor at GEO (design §1; T8a's
   σ_ḋ is 6.04e-4 °/day, so the floor sits well above the element noise),
   0.050 km of semi-major axis in-track at LEO
   (`DA_FLOOR_KM`), 0.01° in the LEO plane channel (`I_FLOOR_DEG`), and 5σ_i at
   the 1e-4° GEO inclination quantum. **A class p5 is therefore as much a
   statement about its floor as about its objects,** and the results document
   prints the floor beside every p5.
2. **The east-west ledger is recall-limited at a measured 1.81%**
   (`docs/stationkeeping-efficiency-results-20260922.md` §: the detected
   station-keeping delta-v is a median 1.81% of the ~50 m/s/yr the odometer
   expects). Its detected per-burn distribution is a distribution over *the
   largest burns only* and is published as such; the class's B stays the
   derived 0.0675 m/s per cycle of design §2.2 unless the measured p95 exceeds
   it, and the results document says which is being used.
3. **Recall of the initiating flag is UNMEASURED in those words** for the
   trigger population: 33% of T8a's events had no visible initiating flag
   (design §8), so the drift-change class is a distribution over the burns the
   detector saw, and nothing here estimates the ones it did not.

### 2.2 The classes, their sources, their fields, and their units

Classes are taken **as the ledgers already label them** — no new taxonomy is
invented here (that is T13, and it is not registered yet).

| # | Class | Committed source | Row selection | Size field (native units) |
|---|---|---|---|---|
| C1 | relocation stop, GEO | `docs/proximity-events-20260922.jsonl` | `approacherClass == "active"` and `attribution == "resolved"` (T8a's registered primary arm, 487) | `transferDriftDegPerDay`, absolute — the drift the stop burn must null, °/day |
| C2 | any confirmed drift change, GEO | `docs/trigger-alarm-triggers-20260922.jsonl` (committed 5,904-row subset; full table 226,422 rows, sha `f4c3ca9b…`) | every row, **weighted** per §2.3 | `init_drift_change_mag`, °/day |
| C2a | …conditioned on T8d cluster 1 | same | `cluster == 1`, weighted | same |
| C2b | …conditioned on T8d cluster 0 | same | `cluster == 0`, weighted | same |
| C3 | north-south keeping, GEO | `docs/stationkeeping-ns-20260922.jsonl` | `informative == true` (T10b's registered primary population, 738 events on 66 objects) | `dvExactMinimumMps`, m/s |
| C3a | …per bus family | same | same, grouped by `busFamily` | same |
| C4 | east-west keeping, GEO | `docs/stationkeeping-ew-20260922.jsonl` | segments with `detectedEvents > 0` | `detectedDvMps / detectedEvents`, m/s per detected burn; and `theoryDvPerCycleMps` as the derived comparison |
| C5 | transfer legs | `docs/transfer-loss-20260922.jsonl` | the `intervals[]` of every phase; the `informative == true` phases are the primary arm and the rest are reported separately | `exactMinimumImpulseMps` per interval, m/s |
| C6 | LEO phasing campaign | `docs/proximity-leo-events-20260922.jsonl` | `armM == true` (T8b's registered catalogue, 71) | `phaseRateMaxDegPerDay` → δa in km via `proximity_plane.phase_rate_deg_per_day_per_km(meanAKm)`; and `medianAbsDaKm` |
| C6i | LEO plane change in a campaign | same | same | `planeManoeuvresInCampaign` — **expected to be identically zero** (T8b §3.3); if it is, the class is reported as a **BLINDED CHANNEL, never as a zero-sized burn** |

**Conversions.** Where a size is quoted in m/s beside its native unit, the
conversion is the design's own derived one, labelled *derived* at every
appearance: at GEO 0.3522 °/day per m/s (`proximity_geo.DRIFT_PER_M_S`, from
da = 2 dv/n and ḋ = −(3/2)(ω_E/a) da), at LEO da = 1.807 km per m/s at
a = 6,878 km with the per-row `meanAKm` used in place of the reference value.
These are standard two-body results, cited to the repository's own
registrations, and they are arithmetic on elements — **not** a fuel figure.
Classes C3, C4 and C5 are priced in m/s by their own ledgers, whose registered
population is `data/propulsion-catalog-v1.json`, commercial-civil only; M0
inherits that population for those three classes without widening it, and
names no object in any output.

### 2.3 The weighting M0 must apply, registered before the arithmetic

The committed trigger subset is **not** a uniform sample: its registered rule
is "every O1- or O2-positive row, plus a uniform random sample of the rest,
seed 20260922" — 904 positives plus 5,000 of the 225,518 others. Unweighted
quantiles over those 5,904 rows would estimate the distribution of an
enriched sample, not of the 226,422-row population. C2 therefore uses
**weighted quantiles**: weight 1.0 for a positive row, weight
225,518 / 5,000 = 45.1036 for a sampled other, with the weighted quantile
defined as the smallest value whose cumulative weight reaches q·ΣW. The same
weights apply inside the cluster-conditional arms C2a and C2b.

**Cross-check, registered as a check and not as the result:** the same
quantiles are computed over the full 226,422-row table at
`/home/sdegan/t8d-work/trigger-alarm-triggers-20260922-FULL.jsonl` **only after
its sha256 is asserted to equal the committed `fullTableSha256`
`f4c3ca9b96fbb8fda1c1d719699ee4f9f24c192cb7c4f3dc89fcc8c7ff495c67`.** If the
sha disagrees the cross-check is reported as not performed. The committed-subset
weighted figure is the governing one either way; the full-table figure is
published beside it so a reader can see the weighting work or fail.

### 2.4 Power rule and reporting

- Every class reports **n**, and **n < 20 is UNDERPOWERED** (alarm design §5.2)
  — printed in those words, and such a class supplies no B.
- Quantiles reported: **p5, p25, p50, p75, p95**, plus n, min and max.
- A per-bus arm (C3a) prints one row per bus family with its own n and its own
  UNDERPOWERED flag; no bus family's quantiles are borrowed by another.
- No class's quantiles are pooled across classes, and no class's p95 is used as
  another's B.

---

## 3. M1 — Gate W forward error beyond +30 d

### 3.1 Instrument: T8d's own, imported and not re-implemented

M1 calls `tools/trigger_alarm.py::validate_propagator` — the function that
produced the committed +30 d figure (median 0.408°, p75 0.898°, p95 2.080°,
n = 49,318) — **unchanged, with its `check_days` argument varied.** It reads
post-trigger element sets by design, feeds no feature, and is named
`validate_` precisely so the leakage test can find it; that separation is not
weakened here. The trigger population is T8d's own cached table
(`/home/sdegan/t8d-work/t8d-triggers.pkl`, keyed on the feature-path sha256),
and the element histories are rebuilt from the committed T8a extract by
`proximity_geo.build_series` with T8d's three published extract numbers
asserted, exactly as `load_cached_extract` asserts them.

**Reproduction gate, registered before the new horizons are run:** the tool
first re-measures at `check_days = 30` and must reproduce
n = 49,318 and median 0.408° to the published precision. **If it does not, M1
reports the discrepancy and no longer-horizon figure is published** — a changed
instrument may not be compared against a published number.

### 3.2 The two arms, and why two

The +30 d figure is taken over triggers with **no further flag inside the
window** and an element set at the far end. That condition is horizon-dependent:
the set of triggers that survive 180 days without another flag is a quieter
population than the set that survives 30. Measuring growth on those different
sets confounds error growth with population change, so both are reported:

- **Arm A — as measured, per horizon.** Exactly the +30 d method at each
  horizon, each horizon with its own qualifying set and its own n. This is the
  arm that answers "what is the error at +90 d", and it is the governing arm
  for the design's member arrival windows, because a live alert is exactly a
  trigger with no further flag yet.
- **Arm B — matched cohort (ADDED HERE).** The triggers that qualify at *every*
  registered horizon, with all horizons re-measured on that one fixed set.
  Reason: it is the only arm in which the growth of the error with horizon is a
  statement about propagation rather than about which objects stayed quiet.
  Arm B's n is reported and will be smaller; where the two arms disagree, both
  are printed and the disagreement is the finding.

### 3.3 Horizons

Registered primary: **30 (reproduction), 60, 90, 180 days.**
Registered fine grid, for locating threshold crossings only: **5, 10, 15, 20,
45, 120 days.** The fine grid exists because the design asks at which horizon
the median error exceeds the co-location threshold, and the committed +30 d
median (0.408°) is already four times that threshold — so the crossing is
*inside* the measured window and must be located rather than extrapolated. No
quantity from the fine grid is used as a design input other than the crossing
horizons named in §3.4.

### 3.4 The two thresholds this measurement is read against

| Threshold | Value | Where it comes from | What it is |
|---|---|---|---|
| co-location | **0.1°** | T8a's registered X_primary: within 0.1° of a mean longitude, held ≥ 30 d | the estimand's own tolerance. Above it, an arrival *time* cannot be stated to co-location precision |
| slot spacing | **measured here** | the median gap between adjacent occupied mean longitudes of stationed objects | above it, the *membership* of the reachable set is unresolved: the error covers more than one occupied longitude |
| Gate W bar | **2.0°** | `trigger_alarm.GATE_W_DEG`, registered by T8d | above it on the median, T8d's registered verdict is that the forward geometry is unfit |

**Slot spacing, registered definition (ADDED HERE):** using T8d's own
`OccupancySweep` at the archive's final element epoch, the stationed set is
every object with a current element set inside the merge window, ≥ 30 d of
history and |ḋ| ≤ 0.020 °/day (the lane's registered eligibility proxy). Slot
spacing is the set of gaps between adjacent occupied longitudes on the wrapped
360° belt, reported as p5 / p25 / **median** / p75 / p95 with its n. It is a
description of today's belt, **not** a law and not a regulatory slot plan: the
document says so where it prints it.

**Both thresholds are screens, not physics.** Neither says the propagation
becomes wrong at a horizon; they say the error stops being small compared with
the quantity the layer wants to resolve. The design's horizon H is set to the
largest registered horizon whose **Arm A median** stays below the *slot
spacing*, and every member window beyond the largest horizon whose Arm A median
stays below 0.1° carries its own measured error rather than a co-location
claim.

### 3.5 What M1 does not do

It does not improve the propagation, add luni-solar or solar-radiation-pressure
terms, fit station-keeping, or re-derive K. T8d's §4 already states what the
propagation assumes — that the object does nothing further — and M1 measures
the consequence at longer horizons. The error is what the object *does next*
(the +30 d figure is 22× the element-noise floor), so it is not reducible by
better arithmetic and nothing here pretends otherwise.

---

## 4. M2 — LEO along-track phase-error growth

### 4.1 The quantity, defined before it is measured

For a LEO object at an element set with epoch t₀, mean motion n₀ (rev/day) and
argument of latitude u₀ = ω + M (degrees, near-circular), the registered
prediction is the same "it does nothing further" propagation the GEO arm uses,
with no drag model and no manoeuvre:

    u_pred(t) = u₀ + 360 · n₀ · (t − t₀)

and the **along-track phase error** is |u_pred(t) − u_obs(t)|, in degrees,
where u_obs is read from the object's own later element sets.

**Unwrapping, registered because it decides whether the number means
anything.** The error is evaluated at every element set in the window and the
sequence is unwrapped before the horizon value is read, so that an error which
has passed 180° is counted at its true size instead of aliasing back toward
zero. The unwrap is valid while the error moves by less than 180° between
consecutive element sets; the LEO median spacing is 0.53 d (p95 2.35 d) and the
p95 object's noise-implied rate is 1.94 °/day, so the assumption holds by a
wide margin at the median. **Every window in which any consecutive step exceeds
90° of error change is flagged `unwrapSuspect` and excluded from the
quantiles, with its count reported** — an excluded window is a labelled gap,
never a zero and never a small number.

### 4.2 Population, strata and sampling

Objects are taken from T8b's own detect stage output
(`/home/sdegan/t8b-work/detect-summary.json`, `detect-flags.json`,
`object-meta.json`; the T8b receipt is committed at
`docs/proximity-leo-20260922-receipt.json`). Eligible: `regimes == ["LEO"]`,
≥ 200 element sets and ≥ 365 d of span (T8b's own `CONTROL_MIN_*` evidence
bars, reused so that the never-manoeuvred stratum means what T8b means by it).

Strata, each sampled and reported separately, with seed **20260922**:

| Stratum | Definition | Target n |
|---|---|---|
| S-arm-M | every arm-M approacher and target of `docs/proximity-leo-events-20260922.jsonl` that is eligible | all |
| S-payload | `objectType == "PAYLOAD"`, at least one detected manoeuvre | 400 |
| S-never | T8b's `never_manoeuvred` control population | 400 |
| S-passive | `objectType` in the passive set, not never-manoeuvred | 400 |

Reason for the strata: the reachable set's LEO members are catalogued objects
of all four kinds, and a phase horizon measured only on manoeuvring payloads
would not describe the set. **If a stratum returns fewer than 20 objects with a
usable window at a horizon, that stratum is UNDERPOWERED at that horizon and
its quantiles are withheld.** Sampling is uniform without replacement within a
stratum at the registered seed; the realised n is reported per stratum per
horizon.

### 4.3 Windows

For each object and each horizon H ∈ {30, 60, 90, 180} days, windows are
non-overlapping, taken forward from the object's element sets at a stride of H
days, and a window is **usable** only if:

1. it contains **no detected manoeuvre flag** of either T8b channel (in-track
   or plane) strictly inside (t₀, t₀+H] — the same causal discipline T8d's
   propagator validation uses;
2. an element set exists within `MAX_GAP_DAYS` = 5.0 d of t₀ + H;
3. no gap inside the window exceeds 5.0 d (otherwise the unwrap is not
   supported);
4. it is not `unwrapSuspect` (§4.1).

Per object, the reported value at a horizon is the **median over that object's
usable windows**, so an object with many windows does not outvote one with
few. The across-object quantiles (p5 / p25 / p50 / p75 / p95) are then taken
over the per-object medians, per stratum and pooled, with n reported at every
cell. Windows and objects rejected at each of the four conditions are counted
and published.

### 4.4 The covariates: σ_n and the drag proxy

- **σ_n, per object:** `proximity_plane.object_sigma_contributions` — the
  registered MAD of the second difference of mean motion, the same function
  whose pooled median (6.2747e-5 rev/day) and p95 (5.3954e-3 rev/day) T8b
  published. Computed per object here; **the pooled T8b value is not
  substituted for a per-object one anywhere.**
- **Drag proxy, two of them, both reported:** (a) `bstar_q / 1e12` from the
  archive, median over the object's window — the catalogue's own drag term;
  (b) `ndot`, the Theil–Sen secular slope of mean motion from T8b's
  detect-summary, rev/day². (a) is what the element set asserts; (b) is what
  the archive measures. Where they disagree the disagreement is reported.
- **Relationship, reported as association and nothing more:** per horizon,
  the per-object error median is tabulated against deciles of σ_n and against
  deciles of each drag proxy, with Spearman rank correlation and its n.
  **No functional form is fitted and no drag model is built**; the design's
  standing statement that LEO drag is unmodelled is not discharged by this
  measurement and the results document repeats it.

### 4.5 The design's arithmetic that M2 exists to test

Design §2.5 states that σ_n = 6.27e-5 rev/day implies 18.9 m of semi-major
axis, 0.023 °/day of phase, **2.0° at 90 d** and 4.4° at 196 d, inside the
registered phase box Γ = 5° at the median but not for the p95 object
(5.4e-3 rev/day → 1.6 km → 1.9 °/day, "phase lost in days"), and that drag is
unmodelled. **That is a noise-propagation calculation, not a measurement**, and
M2 is registered to replace it. The comparison printed in the results is:
measured median error at 90 d versus the 2.0° the noise alone implies. A
measured value far above it is the expected outcome, because drag and
undetected manoeuvres are in the measurement and not in the arithmetic; it is
registered here as the expectation so that it cannot later be presented as a
surprise or as a defect of the instrument.

### 4.6 The meaningful-horizon fraction — the headline M2 owes

**Registered before the data:** a horizon H is **meaningful for an object** if
that object's median along-track phase error at H is **≤ Γ = 5°**, the
registered T8b phase half-box. The headline is the **fraction of objects with a
usable window at 90 d whose 90 d error is ≤ 5°**, reported per stratum and
pooled, with n. Secondary, reported beside it and not instead of it: the same
fraction at 30 / 60 / 180 d, and at the tighter Γ/2 = 2.5° and the tightest
registered sensitivity arm Γ = 0.2085°.

**Γ = 5° is a registered tolerance, not a physical limit.** It is the width of
the box T8b's estimand uses; an object outside it has not "lost its orbit", it
has lost the ability of this propagation to say where along the orbit it is to
the precision a co-orbital station is defined at. The denominator is objects
with a usable 90 d window — **objects with no usable window are reported
separately and are never counted as passes**, and the fraction of the sampled
population with no usable window is printed beside the headline.

---

## 5. Outputs, and the gates on publishing them

**Files (all written by one tool, `tools/kinematic_inputs.py`):**

| Path | Content |
|---|---|
| `docs/kinematic-inputs-20260922.json` | every number of M0, M1, M2, with its n |
| `docs/kinematic-inputs-m2-phase-20260922.jsonl` | one row per object per horizon: norad, stratum, n windows, median error, σ_n, both drag proxies. No registry code, no country, no name, no delta-v, no fuel figure |
| `docs/kinematic-inputs-20260922-receipt.json` | provenance: input sha256s, host, execution mode, wall and CPU seconds, the reproduction gate's verdict |
| `docs/kinematic-inputs-results-20260922.md` | the results document, with every floor and ceiling printed beside the quantity it truncates |

**Gates, fixed now:**

- **Gate K1 — reproduction.** M1's +30 d re-measurement must reproduce
  n = 49,318 and median 0.408°. Fails → no M1 number is published.
- **Gate K2 — weighting.** M0's C2 weighted quantiles are published only with
  the full-table cross-check or an explicit statement that the sha disagreed
  and the cross-check was not performed.
- **Gate K3 — power.** Any class, bus, stratum or cell with n < 20 is printed
  UNDERPOWERED in those words and supplies no design input.
- **Gate K4 — blinded, not zero.** A channel that is blind (the LEO plane
  channel, T8b §2.3) is reported as a labelled gap. Publishing a zero where a
  channel cannot see is a defect this registration names in advance.
- **Gate K5 — policy.** No output row carries a propellant, mass or
  consumables figure, a registry or country code, a miss distance, or any
  never-say word; a test asserts each of those over the emitted files.

**Recall is UNMEASURED, in those words,** for the GEO drift-change class (33%
of T8a's events had no visible initiating flag), for the east-west class
(1.81% detected recall), and for the LEO plane channel (blind). Nothing in this
registration estimates it, and no figure produced here may be read as if it had
been measured.

---

## 6. Compute, and what runs where

CPU only, on `pc`, `nice`-d. No GPU consumer row is owed: nothing here runs on
a GPU, by design §8 ("M0, M1, M2 | tabulations over committed files; Gate W at
three horizons over 49,318 triggers | CPU, minutes"). M0 reads committed files
only. M1 reads the committed T8a extract and T8d's cached trigger table. M2
reads the archive read-only (`PRAGMA query_only = 1`) for the sampled objects'
element sets and T8b's detect-stage outputs. Nothing is scheduled; the tool is
run to completion in the session that registers it, and the results document
reports the wall clock actually observed.

---

## 7. Sources

```
docs/kinematic-reach-design-20260922.md          §0, §2.2-2.6, §8, §9, §10
docs/orbits-section-design-20260922.md           §2.2 (the +30 d ribbon)
docs/trigger-alarm-results-20260922.md           §0 Gate W, §4
docs/trigger-alarm-preregistration-20260922.md   3, 4.6, 6.4, 12
docs/proximity-results-20260922.md               §1.1, §2.2, §3.2
docs/proximity-leo-results-20260922.md           §1.1, §2.2-2.5, §3.1-3.3, §7.2
docs/stationkeeping-efficiency-results-20260922.md  T10b population; the 1.81% recall
docs/transfer-loss-results-20260922.md           the exact-minimum form
docs/alarm-lane-design-20260922.md               §5.2 power, §6 vocabulary, §7 policy
tools/trigger_alarm.py, tools/proximity_geo.py, tools/proximity_plane.py
```

Quoted above and not re-derived: 0.408 / 0.898 / 2.080 at +30 d over n = 49,318;
Gate W's 2.0° bar; 0.1° and 30 d (T8a); Γ = 5°, θ_p = 0.2°, D = 30 d,
`DA_FLOOR_KM` = 0.050, `I_FLOOR_DEG` = 0.01, `MAX_GAP_DAYS` = 5.0 (T8b);
σ_ḋ = 6.04e-4 °/day; σ_n = 6.2747e-5 rev/day and its p95 5.3954e-3;
the 1.81% east-west recall; 738 events on 66 objects; 487; 71; 58; 267;
226,422 and the 5,904-row subset rule. **Derived here and labelled as such at
every appearance:** the 45.1036 weight of §2.3, the slot-spacing definition of
§3.4, the matched cohort of §3.2, and the unit conversions of §2.2.
