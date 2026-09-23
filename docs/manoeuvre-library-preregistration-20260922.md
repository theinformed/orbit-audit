# T13 — the manoeuvre library: PRE-REGISTRATION

**Date:** 2026-09-22. **Status:** registration. Nothing in this document is a
measurement. No number below is a result: every figure quoted here is either a
constant already registered by another track (with the file and symbol it lives
in), a quantity derived here from a standard result and labelled *derived*, or a
population count already published in a committed receipt. The measurement this
document fixes — the agreement matrix, the UNLABELLED fraction, the per-type
precisions — does not exist yet and is forbidden to exist until this file is
committed alone.

**Design:** `docs/kinematic-reach-design-20260922.md` §5 (commit `ad16551`),
runbook row T13 (commit `62fc32a`). **Feeds:** the reach layer's
class-conditional next-burn size (M0), the sequential ladder's
routine-operations null (design §3.3), T14's type mix (design §6).

---

## 1. What this instrument is, and what it is not

T13 assigns a **kinematic type** to a detected burn. A type is a name for what
the elements did across the burn. It is not a purpose, a mission, an intent, a
task, an objective or an operator decision, and no word of that kind appears in
any rule, any type name, any field name or any output string of this instrument.
The never-say list of the alarm-lane design §7 is inherited unchanged and applies
verbatim to every string T13 emits.

T13 is a **rule set**, not a classifier. Every rule is a threshold comparison on
element deltas. There is no fitting, no training, no learned parameter, no
weight, no score, no probability model and no tuned cut. Every threshold is a
constant already registered by a track whose registration is committed, quoted
below with the file and symbol that holds it. A threshold that cannot be traced
to such a constant, or derived from a standard result cited here, is not
permitted in the rule set.

**A threshold is a screen, not a law.** None of these floors is a physical
boundary between kinds of burn. Each is the point below which this archive's
elements cannot resolve the change, or the point a prior registration fixed for
its own purpose. A burn just above a floor and a burn just below it are not two
kinds of thing; they are one kind of thing observed on two sides of an
instrument limit. Every figure this library publishes is read subject to that.

---

## 2. Population — the detected-burn set

T13 types the burns the programme's two registered detectors have already
detected. T13 does not detect burns and adds no detection rule.

**Arm G (near-GEO).** Every confirmed drift-change flag of
`tools/proximity_geo.py::drift_change_flags` over the near-GEO population of the
T8a registration (`docs/proximity-preregistration-20260922.md` §3.1: mean motion
0.95–1.05 rev/day, e < 0.01, i < 25°), on the cached element extract at
`runtime/proximity-geo/near-geo.npz` — 1,768 objects, 11,626,494 element sets,
217,007,154 archive rows scanned (`runtime/proximity-geo/extract-meta.json`).
This is the same extract snapshot T8a and T8d measured on
(`tools/trigger_alarm.py::T8A_ROWS_SCANNED = 217_007_154`), so the labels and
the rules see identical elements and no snapshot reconciliation is required.

**Arm P (LEO / MEO / HEO and the rest).** Every confirmed in-track flag and
every confirmed plane flag of `tools/proximity_plane.py::detect_manoeuvres`, as
committed by the T8b detect stage: `/home/sdegan/t8b-work/detect-flags.npz`,
68,749 objects, 2,958,287 in-track flags and 368,065 plane flags, calibration
σ_θ = 0.6993807 °, σ_n = 6.2747e-5 rev/day
(`/home/sdegan/t8b-work/detect-meta.json`, receipt
`docs/proximity-leo-20260922-receipt.json`).

The flag EPOCHS are taken from that committed detect output and are not
recomputed, so T13 types exactly the burns T8b registered. The element sets
either side of each flag epoch are read from a fresh element cache built by the
same `proximity_plane.extract` code over the live archive. The orbit archive is
append-only in epoch, so a later snapshot contains every element set the T8b
snapshot contained; the run nevertheless checks, for every flag, that the flag
epoch is present in the cache for that object, and reports the count that is not
as a labelled gap rather than dropping it silently.

An object appears in both arms only if its regime changed; the arm is decided
per burn from the element set before it, by the registered regime rule
(`proximity_plane.regime_of`, and T8a's near-GEO band for arm G).

---

## 3. The registered floors, and where each one comes from

No other numeric threshold may appear in any rule.

| Symbol | Value | Registered in | What it is |
|---|---:|---|---|
| `BURN_FLOOR_DEG_PER_DAY` | 0.010 °/day | `tools/proximity_geo.py` (T8a prereg 5.5) | the GEO drift-change detection floor |
| σ_ḋ | 6.0385e-4 °/day | measured, `docs/proximity-20260922-receipt.json` `calibration.sigma_n_deg_per_day`, 3,740,056 samples | GEO drift fit noise; 5σ_ḋ = 3.019e-3 °/day, below the 0.010 floor, so the floor binds |
| `SLOT_DRIFT_FLOOR` | 0.020 °/day | `tools/trigger_alarm.py` = 6·X/D = 6 × 0.1° / 30 d | the stationed band: a drift that would carry an object six co-location half-widths across the registered dwell window |
| σ_i (GEO and above) | 1.67e-4 ° | `docs/orbit-history-design.md` §2 table, n = 450 | inclination fit scatter, already floored at the 1e-4° publication quantum (§2 of that document: "σ(i) is therefore floored at the quantum") |
| 5σ_i | **8.35e-4 °** | *derived* from the row above | the GEO inclination-change bar |
| `X_PRIMARY_DEG` | 0.1 ° | `tools/proximity_geo.py` (T8a prereg 4) | co-location half-width; also the "same longitude" test |
| `X_FAR_DEG` | 2.0 ° | `tools/proximity_geo.py` (T8a prereg 4) | the relocation size bar |
| `STATION_HALF_WIDTH_DEG` / `STATION_MIN_DAYS` | 0.3 ° / 30 d | `tools/proximity_geo.py` (T8a prereg 5.3) | the station-segment definition |
| `MAX_GAP_DAYS` | 5.0 d | `tools/proximity_geo.py` (T8a prereg 4); the same value is T8d's `MERGE_DAYS` and `CONFIRM_DAYS` | the interpolation gap, the flag-chain merge window, and — §6 — the epoch-match tolerance |
| `DA_FLOOR_KM` | 0.050 km | `tools/proximity_plane.py` (T8b prereg 5.4) | the in-track floor outside GEO |
| `I_FLOOR_DEG` | 0.01 ° | `tools/proximity_plane.py` (T8b prereg 5.4) | the plane floor outside GEO |
| σ_θ (T8b calibration) | 0.6993807 ° | committed T8b detect stage | plane fit noise; the T8b detector's own confirmed plane bar is max(5σ_θ, `I_FLOOR_DEG`) = **3.4969 °** (*derived*) |
| `CAMPAIGN_MAX_GAP_DAYS` | 180.0 d | `tools/proximity_plane.py` (T8b prereg 5.5) | the run/campaign linkage window |
| `GEO_GRAVEYARD_MINIMUM_RAISE_KM` | 235.0 km | `pipeline/orbit_events.py` | the graveyard raise bar above `GEO_SEMI_MAJOR_AXIS_KM` = 42,164.0 km |
| `TERMINAL_DECAY_PERIGEE_KM` | 200.0 km | `pipeline/orbit_events.py` | below this, nothing propulsive is asserted |

**Derived constants used to express the same physics in two unit systems.**
A tangential impulse changes semi-major axis by da = 2 dv / n and the GEO mean
longitude drift by ḋ = −(3/2)(ω_E / a) da, both from Kepler's third law; the
repository carries them as `proximity_geo.DRIFT_PER_KM`
(−0.012843 °/day per km, *derived* from ω_E = 360.9856473 °/day and
a_GEO = 42,164.1696 km) and `proximity_geo.DRIFT_PER_M_S`. The library converts
between Δḋ and Δa with `DRIFT_PER_KM` and with nothing else. Outside GEO,
a = (μ / (2πn/86400)²)^(1/3) (`proximity_plane.semi_major_axis_km`). No delta-v
figure, no propellant figure and no mass figure is computed, stored or printed
by this instrument for any object: element units only, which is the surface rule
of the reach design §2.6 applied here at the ledger as well as at the page.

**No Gaussian κσ anywhere.** The archive's element scatter has p99/σ of 116 at
GEO and 3,558 below 500 km (`docs/orbit-history-design.md` §2.1). A Gaussian
tail bound on this distribution is wrong by two to three orders of magnitude, so
no rule in this library is of the form "more than k standard deviations". The
two places where a σ appears — 5σ_i at GEO and the T8b plane bar — are the
registered detector bars of tracks that already fixed them for their own
detection step, quoted unchanged; they are inherited, not re-derived, and they
are screens.

---

## 4. The type set and the rule for each type

A type is assigned to a burn from (i) the element sets immediately either side
of the burn epoch and (ii) the object's own history strictly BEFORE the burn
epoch. No rule reads any element set later than the burn it types. This is the
T8d causal discipline (`docs/trigger-alarm-preregistration-20260922.md` §12)
applied burn by burn, and it is why two of the design's types are episode types
in §4.3 rather than burn types.

Notation: ḋ is the mean-longitude drift rate, λ the mean longitude, i the
inclination, a the semi-major axis, Ω the right ascension of the ascending node.
`Δ` is the change across the burn — the difference between the element set at
the flag epoch and the one before it — computed exactly as the detector that
produced the flag computes it.

### 4.1 Arm G (near-GEO) burn types

The arm-G rules form a partition by construction: the conditions are mutually
exclusive, so no arm-G burn can fire two of them. That the partition holds is
checked and reported (Gate P, §8), not assumed.

| # | Type | Rule | Floors used |
|---|---|---|---|
| G1 | **drift start** | \|Δḋ\| ≥ 0.010 °/d AND \|ḋ_after\| > 0.020 °/d AND \|ḋ_before\| ≤ 0.020 °/d AND \|Δi\| < 8.35e-4 ° | burn floor; stationed band; 5σ_i |
| G2 | **drift stop** | \|ḋ_before\| > 0.020 °/d AND \|ḋ_after\| ≤ 0.020 °/d AND the arrival longitude is one this object has held before: a station segment strictly earlier than the burn whose median λ is within 0.1 ° of the post-burn λ | stationed band; X_PRIMARY; station segment |
| G3 | **station acquisition** | as G2, but NO earlier station segment of this object lies within 0.1 ° of the post-burn λ | as G2 |
| G4 | **east-west keeping** | \|Δḋ\| ≥ 0.010 °/d AND \|ḋ_before\| ≤ 0.020 AND \|ḋ_after\| ≤ 0.020 °/d AND the burn epoch is inside a station segment AND \|Δi\| < 8.35e-4 ° | burn floor; stationed band; station segment; 5σ_i |
| G5 | **north-south keeping** | \|Δi\| ≥ 8.35e-4 ° AND \|Δḋ\| < 0.010 °/d | 5σ_i; burn floor |
| G6 | **graveyard raise** | (a_before − 42,164.0 km) < 235.0 km ≤ (a_after − 42,164.0 km) | graveyard bar |
| G7 | **decaying** | perigee altitude before the burn < 200.0 km | terminal decay perigee |

G6 and G7 are tested first, in that order, because each names a condition on the
orbit itself that the drift-rate rules cannot see; G1–G5 are then tested and are
mutually exclusive among themselves. Anything else is UNLABELLED (§5).

The expected size of a G4 burn is *derived* at 0.024 °/day for the ±0.0208°
deadband of the reach design §2.2, which is above the 0.010 °/day floor. That
number is a property of the population, not a condition of the rule: **no rule
tests it**, and it is quoted only so the results document can say whether what
the rule caught is the size the physics expects.

### 4.2 Arm P (outside near-GEO) burn types

| # | Type | Rule | Floors used |
|---|---|---|---|
| P1 | **decaying** | perigee altitude before the burn < 200.0 km | terminal decay perigee |
| P2 | **inclination adjust** | plane-channel flag AND \|Δi\| ≥ 0.01 ° AND \|Δa\| < 0.050 km | I_FLOOR; DA_FLOOR |
| P3 | **phasing** | in-track flag AND \|Δa\| ≥ 0.050 km AND the plane channel is silent at this epoch AND the previous in-track flag on this object within 180 d exists and has the OPPOSITE sign of Δa | DA_FLOOR; campaign gap |
| P4 | **orbit raise** | in-track flag AND Δa ≥ +0.050 km AND the plane channel is silent AND P3 does not hold | DA_FLOOR; campaign gap |
| P5 | **orbit lower** | in-track flag AND Δa ≤ −0.050 km AND the plane channel is silent AND P3 does not hold | DA_FLOOR; campaign gap |

P1 is tested first. P2–P5 are mutually exclusive by construction (P2 requires
the in-track channel silent in a; P3/P4/P5 require the plane channel silent, and
P3 excludes P4/P5 by its own clause). A burn on which BOTH channels fired
satisfies none of P2–P5 and is UNLABELLED with both channels named — the design
§5(5) discipline, and the honest answer for a burn that moved the plane and the
period at once.

**The plane channel is coarse, and this is stated wherever P2 is reported.** The
T8b detector's confirmed plane bar is max(5σ_θ, `I_FLOOR_DEG`) = 3.4969°, not
0.01°. So although the P2 rule carries the registered 0.01° floor as the design
writes it, the floor is not what binds: every burn P2 can ever see has already
cleared 3.4969° in inclination or in node residual. The finer channel is blind
until the plane-noise floor is re-derived and registered (T8b's standing item,
reach design M6). P2's measured agreement is therefore a statement about the
coarse channel only, and it says so on its own row.

### 4.3 Episode types

Two of the design's types cannot be decided from a single burn without reading
the future. They are emitted as separate EPISODE records over pairs or runs of
already-typed burns, and they do not change any burn's type.

| # | Episode type | Rule |
|---|---|---|
| E1 | **relocation** | a G1 drift start and the first following G2/G3 stop on the same object, where the median λ of the station segment before the start and of the station segment after the stop differ by ≥ 2.0 ° |
| E2 | **transfer-leg run** | a maximal run of ≥ 2 consecutive P4 burns, or of ≥ 2 consecutive P5 burns, on the same object with no gap longer than 180 d and no intervening P2 or P3 |

### 4.4 UNLABELLED

Everything else. See §5.

### 4.5 What is deliberately NOT in v1, and why

* **The pipeline's drag/thrust separation** (`drag-decay`, `drag-make-up`,
  `drag-and-thrust-not-separable`) is not reimplemented. It needs the cohort
  drag prediction of `pipeline/orbit_events.py::predict_drag`, which is a
  different instrument with its own inputs. v1 applies only the registered
  terminal-decay perigee rule and types everything else it cannot separate as
  UNLABELLED. Any later version that adds these types is a new version with a
  new checksum and a new matrix (§7).
* **`node-change` / `apsidal-change`** as separate types. The design's §5 type
  list does not carry them; a node-dominant or apse-dominant plane flag
  therefore fails P2 and is UNLABELLED, with the reason named. That is a real
  cost of the registered type set and is reported as part of the UNLABELLED
  fraction rather than papered over.

---

## 5. UNLABELLED — what it means, and that it stays

A burn is **UNLABELLED** when, on its arm, either

* **no rule fires** — the change is above the detector's floor but matches no
  registered rule; the record carries `reason: "no-rule"` and the measured
  Δ values that placed it outside every rule; or
* **two or more rules fire** — the record carries `reason: "multi-fire"` and
  `competingRules: [...]` naming every rule that fired, in the order the rule
  table lists them.

A type is assigned **only when exactly one rule fires**. There is no
tie-break, no priority ordering among the mutually-exclusive rules, no
nearest-rule rule, no default type and no fallback. UNLABELLED is a terminal
state of this instrument: nothing downstream may re-type an UNLABELLED burn,
infer a type from its neighbours, or treat it as any type's member. It is not a
residual bucket to be cleaned up in a later version by widening a threshold;
widening a threshold is a new version (§7) and it re-publishes the whole matrix.

The UNLABELLED fraction is a **headline result** of this track, reported per arm
and overall in the first table of the results document, above every per-type
number. A library that labels little is a fact about this archive and this rule
set; it is not a defect to be hidden behind the types that did fire.

---

## 6. The agreement protocol — and why it is not accuracy

### 6.1 The standing of the labels

The events T13 is scored against are **the outputs of other instruments run on
the same element sets**, not ground truth. T8a's arrivals, T8b's campaigns,
T10a's legs and T10b's north-south ledger are all rule sets over this archive,
each with its own registered floors, its own detector and its own published
gates. Agreement between T13 and one of them is agreement between two rule sets
that share an input. It is not accuracy, it is not validation, it is not a
detection rate, and no document produced from this artifact may call it any of
those (Gate V, §8).

**The one external truth in the repository is LEO-only and cannot score any GEO
rule.** `data/orbit_manoeuvre_truth.json` holds 34 hand-cited, operator- and
agency-published manoeuvres over 12 objects. Every one is a low-Earth-orbit
object (ISS 25544 and eleven others); none is near-GEO. Its `type` vocabulary
(reboost, collision-avoidance, deorbit, disposal, station-keeping,
orbit-lowering, deboost) is operational, not kinematic, and does not map onto
this library's type set. It is therefore used for ONE thing and stated as such:
a detection check — was a burn detected within the epoch tolerance of each
published event, and what did T13 type it — reported as a listed table of 34
rows, never as a precision, never aggregated into the matrix. The design §5(2)
sentence that operator burn logs are "absent from the repository" is corrected
here: they are present, they are small, they are LEO, and they are scorable for
detection and not for type.

### 6.2 The label sets, and the granularity of each

| Label class | Committed source | Granularity | n |
|---|---|---|---|
| T8a initiating flag | `docs/proximity-events-20260922.jsonl`, `initiatingFlagMs` | burn epoch | 326 |
| T8a arrival | same, `arrivalMs` with `transferDriftDegPerDay` | episode endpoint | 487 |
| T8a relocation episode | recomputed by `proximity_geo.relocations` on the cached extract under the registered rule (receipt figure: 2,956 active relocations over 24,685 stationed segments) | episode | 2,956 |
| T10a transfer leg | `docs/transfer-loss-20260922.jsonl`, `intervals[].startAt/endAt` with the pipeline `signature` on each | burn window | 267 over 58 transfers |
| T10a post-transfer endpoint | same, `phaseEnd` | episode endpoint | 58 |
| T10b north-south keeping | `docs/stationkeeping-ns-20260922.jsonl`, `startAt`/`endAt`, `signature = geo-north-south-keeping` | burn window | 1,107 rows (the informative subset is the T10b headline 738 over 66 objects) |
| T10c east-west carrier | `docs/stationkeeping-ew-20260922.jsonl` | **object** — the T10c detected ledger's recall is 1.81%, so there is no per-burn east-west label in the repository | 834 objects |
| T3 east-west cadence carrier | `docs/cadence-s1-geo-20260922.json` GEO payload carrier population | **object** | published carrier set |
| T8b in-track campaign (arm M) | `docs/proximity-leo-events-20260922.jsonl`, `armM`, `campaignStartMs`, `manoeuvresInCampaign` | episode | 71 arm-M campaigns |
| T8b plane-flagged payload | committed detect stage, plane channel | object / flag | 1,174 objects |

Granularity is heterogeneous and the matrix says so on every row. An
object-level label can support only an object-level agreement statement, and
the two east-west rows are reported that way and are excluded from the
burn-level matrix.

### 6.3 Matching

A T13-typed burn at epoch t matches a label whose epoch is within
**`MAX_GAP_DAYS` = 5.0 days** of t, or whose window [start, end] contains t or
lies within 5.0 days of it. The tolerance is not chosen here: it is the
detector's own interpolation gap, the T8d flag-chain merge window and the T8d
announce delay, all the same registered constant. If more than one label of the
same class is inside the tolerance, the nearest in epoch is taken and the count
of contested matches is reported.

### 6.4 What is computed

For every (T13 type × label class) cell: the number of burns of that type whose
nearest match within tolerance is a label of that class. Both marginals are
published:

* **forward agreement** — of the burns T13 typed `t` that matched any label,
  the fraction whose label is the class this rule was written against. This
  number, with its Wilson 95% interval, is the type's **confidence** and is the
  only confidence any downstream consumer may attach to a burn of that type. It
  is never a per-event score: every burn of a type carries its type's number and
  nothing else, exactly as design §5(3) requires.
* **reverse agreement** — of the labels of class `c`, the fraction that matched
  a T13 burn at all, and the fraction whose T13 type is the one written against
  that class. This is where a rule that is too narrow shows up.
* **unmatched, both ways** — burns of type `t` with no label inside tolerance,
  and labels with no detected burn inside tolerance. Reported as counts, never
  redistributed.

### 6.5 Controls

* **Control C1 — objects that cannot burn.** T8b's never-manoeuvred class
  (3,011 objects, zero events over 18.79 M object-days in T8b's own control) and
  the catalogue-passive class. Any propulsive type assigned to one of these is a
  leak of the rule that assigned it. Reported per rule, per class.
* **Control C2 — the arm-G passive population.** T8a's gate figures give
  0.01701 events per stationed segment for actives and 0.01701 for passives —
  the leak T8a's own Gate B fired on. T13 inherits that population property and
  reports the per-type split by T8a's active/passive class so the leak is
  visible per rule rather than pooled.

Controls are diagnostics on the rule set. `objectType` and the T8b
manoeuvre-history class are read HERE and only here, and they are not read by
any rule (§7.3).

---

## 7. Versioning, the frozen artifact, and the ownership line

### 7.1 Version

The library version is `v1`. A version is the pair (rule table, type set). Any
change to a rule's threshold, to a rule's clauses, to the type set, to the
regime dispatch or to the tolerance of §6.3 is a **new version**, which requires
a new registration document and re-publishes the whole matrix. A version is
never edited in place and an artifact is never amended.

### 7.2 Checksums

The frozen artifact is `docs/manoeuvre-library-v1-<date>.json`. It carries:

* `rulesSha256` — sha256 over the canonical JSON (sorted keys, no whitespace,
  UTF-8) of the rule table: for each rule, its id, its type name, its clause
  list as written strings, every threshold with its value and the file and
  symbol it came from. This is the identity of the rule set. Two runs with the
  same `rulesSha256` applied the same rules.
* `toolSha256` — sha256 of `tools/manoeuvre_library.py`.
* `inputsSha256` — sha256 of every input file read: the GEO extract npz, the
  T8b detect-flags npz, and every label file of §6.2.
* `artifactSha256` — sha256 over the canonical JSON of the artifact with the
  `artifactSha256` field itself removed. Printed in the results document.

A consumer of this library pins `libraryVersion` **and** `rulesSha256`. A
consumer that reads a type without pinning both is reading an unversioned label
and is in breach of this registration.

### 7.3 Registry codes enter no rule

No rule in this library reads, and no output field of this library carries, an
object's country, registry code, national designator, operator, owner or name.
The rule inputs are exactly: epoch, mean motion (hence a and ḋ), eccentricity,
inclination, RAAN, argument of perigee, mean anomaly (hence λ), the object's own
earlier station segments, and the object's own earlier flags. Nothing else.
`objectType` and the T8b manoeuvre-history class are read only by the controls
of §6.5 and are absent from the rule table. This is the design §5(7) rule and
the design §6 ownership line, applied at the level of the source file: the rule
table is checked against this list mechanically by a test, not by inspection.

---

## 8. Gates and decision rules, fixed before any number

| Gate | Condition | Consequence |
|---|---|---|
| **Gate L** — leak | a propulsive type assigned to a never-manoeuvred object at more than the T8b Gate-B leak ratio of 0.10 relative to the payload rate for the same rule | that rule's agreement figure is published as LEAKING and may not be used as a confidence |
| **Gate P** — partition | more than 5% of burns on an arm fire two or more rules | the rule set is mis-specified for that arm; the multi-fire fraction is the headline and the arm's per-type confidences are published as PROVISIONAL |
| **Gate U** — underpowered | a type with fewer than 20 matched events | UNDERPOWERED: no confidence is published for it, it may not lend its name to an alert, and the gap is printed as a gap |
| **Gate N** — unlabelled | — | the UNLABELLED fraction is published per arm above every per-type number, whatever its value |
| **Gate V** — vocabulary | — | no output of this track uses "accuracy", "correct", "truth", "validated", "ground truth" or "detection rate" for an agreement figure |
| **Gate F** — falsification | a type whose most frequent matched label class is NOT the class its rule was written against | the rule is published as measuring something other than what it was written for, at the same prominence as a passing rule |

**What falsifies the library.** (a) Gate P firing on both arms: the rule set is
not a partition and the types are not distinct things. (b) Every type's forward
agreement being indistinguishable from the base rate of its label class in the
matched population: the types carry no information beyond "a burn happened".
(c) Gate F firing on a majority of types. Any of these is published in the
results document's first section, with the same prominence as a pass.

---

## 9. Deviations from design §5, each with its reason

| # | Design §5 says | This registration does | Why |
|---|---|---|---|
| D1 | station acquisition is a drift stop into a new longitude "within 548 d of launch or after a transfer leg" | station acquisition is a drift stop into a longitude this object has NOT previously held, by the registered station-segment rule; no launch-date clause | the figure 548 d appears nowhere in the repository except that one design line — it is an uncited threshold, and this registration admits only floors traceable to a committed registration. The replacement uses only the registered station segment (0.3°, 30 d) and X_PRIMARY (0.1°), reads no launch date, and is causal |
| D2 | relocation and transfer legs are types | they are EPISODE types (§4.3); the member burns keep their own burn types | typing a burn as "relocation" requires the stop that has not happened yet. Burn typing stays causal; the episode record carries the multi-burn fact |
| D3 | LEO phasing is "\|Δa\| ≥ 0.05 km with sign reversal inside a campaign" | the reversal is tested against the PREVIOUS in-track flag within 180 d only | "inside a campaign" needs the whole campaign, including its future. The previous-flag form is the same physics, decided causally |
| D4 | the pipeline's drag rules are carried "unchanged" | only the registered terminal-decay perigee rule (200 km) is applied; the drag/thrust separation is not reimplemented | it needs the cohort drag prediction, a separate instrument with separate inputs. The cost is a larger UNLABELLED fraction outside GEO, which is reported, not hidden |
| D5 | "the one external truth available (operator burn logs) is absent from the repository" | `data/orbit_manoeuvre_truth.json` exists: 34 hand-cited operator/agency events over 12 objects, all LEO, operational vocabulary | it is present but cannot score a GEO rule and cannot map onto kinematic type names; used for a 34-row detection check only (§6.1) |
| D6 | the LEO inclination rule's floor is `I_FLOOR_DEG` = 0.01° | the floor is carried as written, and the results state that the binding constraint is the T8b detector's own plane bar of 3.4969° | the rule cannot see anything the detector did not flag. Stating the floor without stating the bar would overstate the channel's resolution |

---

## 10. Order of work, and what may not happen before what

1. This document, committed alone, by explicit pathspec. No number produced
   before this commit exists may enter the library, the matrix or the results.
2. `tools/manoeuvre_library.py` and its tests, committed together. The tests
   assert the bug first: each seeded rule violation must FAIL against the
   instrument before the instrument is fixed to make it pass, and the test file
   records that both states were observed.
3. The run over the full detected-burn set of §2, then
   `docs/manoeuvre-library-results-<date>.md` and
   `docs/manoeuvre-library-v1-<date>.json`, committed together with the
   checksums of §7.2.
4. The runbook T13 row discharged.

The element cache of arm P (§2) is a mechanical re-run of the committed T8b
extract stage and produces no T13 quantity; it was built while this document was
being written and the results document records that, with its wall time and its
snapshot.

## 11. Sources

```
docs/kinematic-reach-design-20260922.md        §5 (the type set, rules 1-7), §2.2, §2.3
docs/proximity-preregistration-20260922.md     §3.1, §4, §5.3, §5.4, §5.5
docs/proximity-20260922-receipt.json           sigma_n, populations, relocation counts
docs/proximity-leo-preregistration-20260922.md §3.1, §5.4, §5.5
docs/proximity-leo-20260922-receipt.json       detect stage, calibration, control classes
docs/trigger-alarm-preregistration-20260922.md §12 (causality), the merge/confirm window
docs/orbit-history-design.md                   §2 (the sigma table), §2.1 (the tails)
docs/stationkeeping-efficiency-results-20260922.md  T10b, T10c
docs/transfer-loss-results-20260922.md         T10a legs
docs/cadence-s1s2-results-20260922.md          T3 carriers, the inclination quantum
tools/proximity_geo.py, tools/proximity_plane.py, tools/trigger_alarm.py
pipeline/orbit_events.py                       SIGNATURES, the graveyard and decay constants
data/orbit_manoeuvre_truth.json                the 34 external events
```

Standard results used: Kepler's third law (da = 2 dv / n and the GEO drift
relation), cited to the repository's own registered constants `DRIFT_PER_KM` and
`DRIFT_PER_M_S`; the Wilson score interval for a binomial proportion. Every
other figure in this document is quoted from a committed receipt with its field
name, or labelled *derived* with the line it is derived from.
