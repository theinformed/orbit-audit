# T13 — the manoeuvre library v1: RESULTS

**Date:** 2026-09-22. **Registration:** `docs/manoeuvre-library-preregistration-20260922.md`
(commit `d86b93d`, committed alone before any number below existed).
**Instrument:** `tools/manoeuvre_library.py` with `tests/test_manoeuvre_library.py`
(commit `343a112`, 90 offline proofs). **Design:** `docs/kinematic-reach-design-20260922.md` §5.

**Frozen artifact:** `docs/manoeuvre-library-v1-20260922.json`
`libraryVersion` **v1**
`rulesSha256` **`164a5fd11e4c63744615bbf58c02289cc812c46b630458a85b84f9aee35024f6`**
`artifactSha256` **`eb287e809c0cd1b2f0de0b5bbb80ba33e811a692ca794944ae3dda614abef465`**
A consumer pins both. **Per-burn ledger:** `docs/manoeuvre-library-ledger-20260922.jsonl`
— 10,326 rows (every matched burn plus a seeded uniform sample of the rest) of a
full table of **3,914,621** rows, sha256
`dc2a2ccd1cc00258df5aeef797aa14db2c2d88e587d5f397b60bfe76e52b6e6b`, 981 MB, not committed.

---

## READ THIS BEFORE ANY NUMBER

**Every figure below is agreement between rule sets.** Each label class in the
matrix is another instrument's output on the same element sets — T8a's arrivals,
T8b's campaigns, T10a's legs, T10b's north-south ledger — not a record of what
an operator did. Agreement is not accuracy, not validation and not a detection
rate, and nothing downstream may call it one.

**Every threshold in this library is a screen, not a law.** The floors come from
other tracks' registrations, where each was fixed for that track's own purpose.
A burn just above a floor and a burn just below it are not two kinds of thing;
they are one kind of thing observed on two sides of an instrument limit. §2
below is the demonstration of exactly that, and it is this run's most important
result.

---

## 1. Headline

| | value |
|---|---:|
| burns typed | **3,914,621** |
| UNLABELLED, overall | **23.62%** (924,463) |
| UNLABELLED, arm G (near-GEO) | **90.41%** (920,618 of 1,018,263) |
| UNLABELLED, arm P (outside near-GEO) | **0.13%** (3,845 of 2,896,358) |
| burns firing two rules (Gate P) | 84, **2.15e-5** of all burns — bar 5%, **not fired** |
| burns matching a committed label inside the 5.0-day tolerance | **5,326** of 3,914,621 (0.14%), against 2,350 epoch-carrying labels in total |
| wall time, both arms, one CPU core | **524 s** |

**Gate P did not fire: the rule set is a partition in practice**, 84 multi-fire
burns in 3.9 million, all of them the one overlap the registration anticipated
(G2+G5 57, G3+G5 27 — a drift stop that barely crosses the stationed band while
the inclination moves). **Gate N is the story: the two arms label at opposite
extremes**, 9.6% at GEO against 99.87% outside it, and the reason is a single
measured fact in §2.

Gates fired: **Gate U** (underpowered) for `north-south keeping` (19 matched) and
`inclination adjust` (17 matched). **Gate F** (falsification) for `drift stop`,
`station acquisition` and `orbit lower`. **Gate L** (leak) for `inclination
adjust` and `orbit lower`. Each is worked through below at the same prominence
as the types that passed.

---

## 2. Why arm G labels one burn in ten — the measurement, not an excuse

906,864 of the 920,618 unlabelled arm-G burns — **98.5%** — fail for one
reason: **both channels moved**. The drift changed by at least the registered
0.010 °/day floor *and* the inclination changed by at least the registered
5σ_i = 8.35e-4° bar, so rules G1 (drift start) and G4 (east-west keeping), which
both require the inclination to be quiet, cannot fire, and G5 (north-south
keeping), which requires the drift to be quiet, cannot either.

The full breakdown of the arm-G no-rule burns:

| why no rule fired | burns |
|---|---:|
| both channels moved | 906,864 |
| drift moved, outside every band case | 13,009 |
| inside the band but outside a station segment | 399 |
| below the drift floor and the inclination bar | 262 |

**The inclination channel is not measuring burns at GEO. It is measuring the
Moon and the Sun.** Measured over all 1,018,263 arm-G burns:

| quantity | p5 | p25 | p50 | p75 | p95 |
|---|---:|---:|---:|---:|---:|
| \|Δi\| (deg) | 0.00110 | 0.00635 | **0.01575** | 0.0294 | 0.0696 |
| \|Δḋ\| (deg/day) | 0.01139 | 0.01403 | 0.01821 | 0.02687 | 0.07815 |
| differencing span (days) | 4.27 | 9.99 | **18.04** | 29.92 | 60.87 |

The median \|Δi\| across a detected GEO burn is **0.01575°, which is 18.9× the
registered 8.35e-4° bar**. It is not noise and it is not a burn. The
repository's own registered bound on how much luni-solar gravity alone can turn
a geostationary orbit plane — `pipeline/orbit_events.py::lunisolar_inclination_bound_deg`,
(2π / 53 yr) × (\|i\| + 7.44°) × span/365.25 — evaluated at i = 0.05° over this
run's **measured** median differencing span of 18.04 days gives **0.0438°**. The
measured median is 36% of that bound. The natural motion accounts for the
observed inclination change with room to spare.

The 8.35e-4° bar is 5σ on the archive's inclination **fit scatter**
(`docs/orbit-history-design.md` §2: σ_i = 1.67e-4° at GEO and above, already
floored at the 1e-4° publication quantum). That is the right bar for the
question "did the number move more than the catalogue's arithmetic wobbles". It
is the wrong bar for the question "did an operator move the plane", because
between two element sets eighteen days apart the plane moves on its own by
twenty times that much. **The design's clause "Δi below quantum" (§5, rules for
drift start and east-west keeping) does not test whether a burn changed the
inclination; at this sampling it tests whether the two element sets are close
together in time.** That is a fact about the registered rule, measured, and it
is published here rather than fixed quietly: fixing it is a new version.

**What a v2 must do, and the instrument that already does it.** T10b's
station-keeping tool does not difference raw inclination: it carries
`incPredictedDeg` — the natural motion propagated forward — and reports
`deltaIncNetDeg` = observed − predicted, together with `naturalFraction`
(`docs/stationkeeping-ns-20260922.jsonl`). A T13 v2 inclination clause must be
written on the NET inclination change against a natural-motion prediction, with
the prediction's own uncertainty as the bar, exactly as T10b does. That is a
rule change, so it is a new registration, a new `rulesSha256` and a new matrix.

Arm P does not have this problem, and the same table shows why: outside GEO the
median differencing span is 5.35 days and the median \|Δi\| is 0.0008°, below
the registered 0.01° plane floor, so the plane channel is quiet on almost every
in-track burn and the in-plane rules are free to fire.

---

## 3. The type set as it came out

### Arm G — near-GEO, 1,018,263 burns

| type | burns | share |
|---|---:|---:|
| UNLABELLED | 920,618 | 90.41% |
| station acquisition | 37,324 | 3.67% |
| drift stop | 31,095 | 3.05% |
| east-west keeping | 17,500 | 1.72% |
| drift start | 4,555 | 0.45% |
| graveyard raise | 3,638 | 0.36% |
| north-south keeping | 3,533 | 0.35% |

### Arm P — outside the near-GEO band, 2,896,358 burns

| type | burns | share |
|---|---:|---:|
| orbit raise | 1,506,973 | 52.03% |
| orbit lower | 1,005,132 | 34.70% |
| phasing | 345,419 | 11.93% |
| decaying | 34,394 | 1.19% |
| UNLABELLED | 3,845 | 0.13% |
| inclination adjust | 595 | 0.02% |

Arm P's no-rule burns: plane flags with no inclination change (node-dominant)
2,211; plane flags carrying a semi-major-axis change 1,188; both channels fired
396; in-track flags below the in-track floor 50.

**Episodes.** 829 relocations (a drift start closed by a stop ≥ 2.0° away) and
323,405 transfer-leg runs (≥ 2 consecutive same-direction in-plane burns inside
the 180 d campaign window). Neither changes any burn's type.

**Stage-0 precedence, audited.** 34,279 burns were assigned by a stage-0 rule
(graveyard raise, decaying) and *would also* have satisfied a stage-1 rule. The
registration fixed that precedence before any number; the count is published
rather than hidden, and §5 reads it.

---

## 4. The agreement matrix

Rows are T13 types, columns the committed label classes, cells the number of
burns of that type whose nearest label inside the registered 5.0-day tolerance
is of that class. 1,474 matches were contested (more than one label inside the
tolerance); the nearest was taken.

| T13 type | t8aInitiatingFlag | t8aArrival | t10aTransferInterval | t10aPostTransferEndpoint | t10bNorthSouth | t8bCampaignStart | matched | unmatched |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| drift start | **28** | 5 | – | – | 17 | – | 50 | 4,505 |
| drift stop | 11 | **87** | – | – | 106 | – | 204 | 30,891 |
| station acquisition | 90 | 534 | – | **0** | 87 | – | 711 | 36,613 |
| east-west keeping | – | 20 | – | – | 42 | – | 62 | 17,438 |
| north-south keeping | 3 | 6 | – | – | **10** | – | 19 | 3,514 |
| graveyard raise | 35 | – | – | – | 14 | – | 49 | 3,589 |
| orbit raise | 2 | 1 | **293** | – | 83 | 155 | 534 | 1,506,439 |
| orbit lower | – | 1 | **8** | – | 41 | 20 | 70 | 1,005,062 |
| phasing | – | – | 5 | – | 5 | **21** | 31 | 345,388 |
| inclination adjust | 1 | – | 14 | – | 2 | – | 17 | 578 |
| decaying | – | – | 15 | – | 5 | – | 20 | 34,374 |
| UNLABELLED | 1,251 | 560 | 23 | – | 1,725 | – | 3,559 | 920,904 |

Bold is the cell the rule was written against. Label-set sizes: t8aInitiatingFlag
328, t8aArrival 493, t10aTransferInterval 267, t10aPostTransferEndpoint 84,
t10bNorthSouth 1,107, t8bCampaignStart 71.

### Forward agreement — the confidence each type carries

| type | expected label class | agreeing / matched | forward agreement | Wilson 95% | verdict |
|---|---|---:|---:|---|---|
| phasing | t8bCampaignStart | 21 / 31 | **0.677** | [0.501, 0.814] | — |
| drift start | t8aInitiatingFlag | 28 / 50 | **0.560** | [0.423, 0.688] | — |
| orbit raise | t10aTransferInterval | 293 / 534 | **0.549** | [0.506, 0.590] | — |
| north-south keeping | t10bNorthSouth | 10 / 19 | 0.526 | [0.317, 0.727] | **UNDERPOWERED** (n < 20) |
| drift stop | t8aArrival | 87 / 204 | 0.426 | [0.361, 0.495] | **Gate F** |
| orbit lower | t10aTransferInterval | 8 / 70 | 0.114 | [0.059, 0.210] | **Gate F**, **Gate L** |
| station acquisition | t10aPostTransferEndpoint | 0 / 711 | 0.000 | [0.000, 0.005] | **Gate F** |
| east-west keeping | t10cEastWestObject | — | — | — | labelled gap: object-level class (§5) |
| inclination adjust | t8bPlaneFlaggedObject | — | — | — | labelled gap + **UNDERPOWERED**, **Gate L** |
| graveyard raise, decaying | none committed | — | — | — | no expected class exists |

**Only three types earn a confidence in v1: phasing 0.677, drift start 0.560,
orbit raise 0.549.** Every other type is a gate, a gap, or underpowered. A burn
typed anything else carries its type and no number, and may not lend its name to
an alert.

### Object-level agreement, for the two label classes with no epoch

Base rates over all 3,914,621 burns: 1.47% lie on one of the 136 objects in
T10c's east-west ledger, 22.75% on one of the 2,343 objects T8b's plane channel
flagged.

| type | on a T10c east-west object | on a T8b plane-flagged object |
|---|---:|---:|
| *base rate* | *1.47%* | *22.75%* |
| east-west keeping | **25.9%** (17.6×) | 96.6% |
| drift start | 22.1% (15.0×) | 93.4% |
| north-south keeping | 14.1% (9.6×) | 92.9% |
| graveyard raise | 6.5% | 91.6% |
| drift stop | 5.6% | 78.9% |
| station acquisition | 5.3% | 75.7% |
| UNLABELLED | 5.0% | 81.2% |
| inclination adjust | 4.7% | **100.0%** |
| orbit raise / lower / phasing | 0.05% / 0.02% / 0.03% | 1.2% / 3.2% / 2.5% |

The east-west column is the only positive result the east-west rule has:
**a burn T13 types `east-west keeping` is 17.6× more likely than the population
base rate to sit on an object T10c independently identified as an east-west
station-keeper.** That is an object-level statement and nothing more; T10c's
detected per-burn ledger has a recall of 1.81% (`docs/stationkeeping-efficiency-results-20260922.md`),
so there is no per-burn east-west label in the repository to score against and
the burn-level cell is a gap, not a zero. The 100.0% for `inclination adjust` is
tautological — the rule requires a plane flag — and is printed only to show it.

---

## 5. Every gate that fired, worked through

### Gate F — `station acquisition`, 0 / 711 against its expected class

The registration wrote `station acquisition` against
`t10aPostTransferEndpoint`, of which there are 84. The matrix says the rule is
measuring something else: 534 of its 711 matches (**75.1%**) are T8a **arrivals**.
That is coherent, not broken. A T8a arrival is a stop within 0.1° of another
satellite's mean longitude, held 30 days — almost always a longitude the mover
has not held before, which is exactly what rule G3 tests. **The rule is sound
and the registration's expected-class mapping was wrong.** It is not corrected
here: the mapping is part of the rule table, so changing it is a new version.
The number to carry forward is that 75.1%, and it is an agreement figure with
the class the matrix names, not the class the registration guessed.

### Gate F — `drift stop`, 87 / 204, beaten by t10bNorthSouth at 106

The competing class is T10b's north-south windows. Those are *windows*, up to
several hours wide, on 66 heavily-manoeuvred commercial GEO objects, and there
are 1,107 of them against 493 T8a arrivals — a denser label set on a smaller
population. A drift stop on one of those objects is very likely to land inside
some north-south window within 5 days. **This is a property of the label set's
density, not evidence that the drift-stop rule is measuring inclination.** The
honest reading is that the 5.0-day tolerance is too loose for a label set this
dense, and that is a registered constant this version may not move.

### Gate F and Gate L — `orbit lower`, 8 / 70, 14.0% passive

`orbit lower` is the type most exposed to the one thing the archive cannot
separate: **a semi-major axis that falls is exactly what drag does.** The
registration declared (§4.5) that v1 does not reimplement the pipeline's
cohort drag prediction, so every unexplained decrease outside the terminal-decay
perigee is typed `orbit lower`. The leak control says so plainly: 14.0% of
`orbit lower` burns are on catalogue-passive objects — debris and spent stages
that cannot burn — against 4.7% for `orbit raise`, the mirror type, which is
physically unambiguous because **drag cannot raise an orbit**. The asymmetry
between those two numbers is the measurement of how much of `orbit lower` is
atmosphere. **`orbit lower` may not be used as a propulsive type by any
consumer of v1.**

### Gate L — `inclination adjust`, 36.3% passive, n = 595

The highest passive fraction of any type, on the smallest propulsive type. Two
things drive it, both already known to the programme. First, T8b's plane channel
is coarse: its confirmed bar is max(5σ_θ, 0.01°) = **3.4969°**, not the 0.01°
the rule carries, so the rule's floor never binds and the flags it sees are
whatever cleared three and a half degrees. Second, that bar is set by the fit
scatter of a channel T8b itself reports as blind (Gate A; the diagnostic floor
0.000148° says it need not be — the standing plane-noise re-derivation, reach
design M6). Until M6 lands, **`inclination adjust` is a labelled gap with a
leak, not a measured type.**

### Gate U — underpowered

`north-south keeping` (19 matched) and `inclination adjust` (17) fall below the
registered n ≥ 20. Neither publishes a confidence and neither may name an alert.
`north-south keeping` is one match short, and its point estimate against its own
expected class — 10/19, and t10bNorthSouth is also its most frequent class — is
the only reason to think a v2 with a net-inclination clause (§2) would land it.

### Gate P — did not fire

84 multi-fire burns in 3,914,621, all G2+G5 (57) or G3+G5 (27). The rule set is
a partition in practice as well as in construction.

---

## 6. The external check — 34 published events, listed, never a precision

`data/orbit_manoeuvre_truth.json` holds 34 hand-cited manoeuvres that operators
and agencies published themselves. **Erratum: the registration §6.1 says twelve
objects; the file holds 34 events over TEN distinct NORADs.** All ten are
low-Earth-orbit objects and the vocabulary is operational, so this scores
detection only and no type, exactly as registered.

**23 of the 34 published events have a detected burn within the 5.0-day
tolerance.** What the library typed those burns, by published kind:

| published kind | events | typed `orbit raise` | typed `phasing` | typed other | no burn within 5 days |
|---|---:|---:|---:|---:|---:|
| reboost | 17 | 12 | 1 | – | 4 |
| collision-avoidance | 9 | 3 | 1 | – | 5 |
| deorbit | 2 | – | 1 | 1 (`decaying`) | – |
| orbit-lowering | 2 | – | 1 | 1 (`orbit lower`) | – |
| station-keeping | 2 | – | – | – | 2 |
| deboost | 1 | – | 1 | – | – |
| disposal | 1 | – | – | 1 (`graveyard raise`) | – |

Twelve of seventeen published ISS-class reboosts come back as `orbit raise`, the
one published disposal comes back as `graveyard raise`, and the one published
orbit-lowering comes back as `orbit lower`. Nothing here is a precision: the set
is ten objects, the dates are day-exact at best, and four of the eleven misses
are reboosts on an object whose element sets the detector may simply not have
flagged. It is listed because it is the only evidence in this repository that
does not come from another instrument reading the same elements.

---

## 7. Controls

| type | burns | on catalogue-passive objects | passive fraction |
|---|---:|---:|---:|
| east-west keeping | 17,500 | 25 | **0.14%** |
| drift start | 4,555 | 19 | **0.42%** |
| drift stop | 31,095 | 384 | 1.23% |
| decaying | 34,394 | 1,102 | 3.20% |
| station acquisition | 37,324 | 1,342 | 3.60% |
| orbit raise | 1,506,973 | 71,047 | 4.71% |
| phasing | 345,419 | 21,646 | 6.27% |
| north-south keeping | 3,533 | 246 | 6.96% |
| graveyard raise | 3,638 | 255 | 7.01% |
| orbit lower | 1,005,132 | 140,335 | **13.96%** |
| inclination adjust | 595 | 216 | **36.30%** |
| UNLABELLED | 924,463 | 179,709 | 19.44% |

Gate L's bar is 0.10. The four cleanest types are the four arm-G in-plane types,
all under 1.3% except station acquisition; the two that fire the gate are the
two §5 works through. **T8b's never-manoeuvred class cannot test this
instrument**: that class is *defined* as having produced no flag, so it produces
no burn, so it can never leak into a typing rule. Recorded because a control that
cannot fail is not a control, and the catalogue-passive class above is the one
that can.

---

## 8. Deviations, errata and what this run corrected

| # | what | why |
|---|---|---|
| E1 | The registration §6.1 says the external file holds twelve objects. It holds **ten**. | miscount in the registration; asserted at its true value in `test_the_external_events_are_read_and_counted_honestly` |
| E2 | `a` at GEO is Kepler's third law on the object's own mean motion, not `proximity_geo.semi_major_offset_km` | that function's own docstring says it is "interpretive only … never inside a detector decision", and a rule reads the value. The two forms differ by more than 0.5 km at the 235 km graveyard bar, so which one a rule reads changes the answer |
| E3 | Both burn builders measure the DETECTOR'S own statistic — the trailing median baseline (arm G) and the rolling-fit residual of mean motion (arm P) — not a one-step difference across the flag | the registered detectors flag the SECOND confirming element set, so a one-step difference measures a different quantity and comes out near zero on a real step. Found by a seeded test; before the fix arm P's unlabelled fraction was 48.3% and 1,394,630 in-track flags read as "below the in-track floor". After: 0.13% and 50 |
| E4 | The object-level label classes are reported as object-level agreement and as labelled gaps at burn level | registration §6.2. The first arm-G run printed 0/62 for east-west keeping and fired Gate F on it — a zero where there is a gap |
| E5 | T3's 14.00-day east-west carrier NORAD list is not published as a list in the committed T3 artifacts read here, so T3 contributes no label column in v1 | a labelled gap. T10c's 136-object ledger carries the east-west object-level column alone |
| D1–D6 | the six deviations from design §5 | recorded in the registration §9, unchanged |

Population notes. `build_series` drops objects with fewer than two element sets,
so arm G ran over **1,652** of the near-GEO population's 1,768 objects. **427,174**
burns detected by the plane detector fell inside T8a's near-GEO band on their
pre-burn element set and were excluded from arm P as belonging to arm G's
detector domain, per registration §2. **Zero** committed flag epochs were missing
from the element cache — the append-only reasoning in registration §2 held.

The arm-P element cache is a mechanical re-run of the committed T8b extract
stage, 217,046,214 rows in 876 s, built while the registration was being
written; it produced no T13 quantity before the registration was committed.

---

## 9. What this library may and may not be used for

**May.** A burn may be given its type from the ledger, pinned by
`libraryVersion` **and** `rulesSha256`. Three types carry a confidence:
`phasing` 0.677 [0.501, 0.814], `drift start` 0.560 [0.423, 0.688],
`orbit raise` 0.549 [0.506, 0.590]. The routine-operations null of the
sequential ladder (design §3.3) may use the arm-G types as written, with §2's
caveat carried verbatim. The episode records may be read as multi-burn facts.

**May not.** `orbit lower` may not be treated as propulsive (§5). `inclination
adjust` may not be used at all until the plane-noise floor is re-derived (M6).
`north-south keeping` and `inclination adjust` may not name an alert
(UNDERPOWERED). `station acquisition`'s number is its agreement with T8a
arrivals, 75.1%, not with the class the registration named, and it carries Gate
F wherever it is printed. No type may be attached to an UNLABELLED burn, and
90.4% of near-GEO burns are UNLABELLED.

**What T13 owes M0.** The design's class-conditional next-burn size (§2.4) needs
a type per burn and a size distribution per type. Three types can supply one
today. The rest wait on a v2 whose inclination clause reads the net change
against a natural-motion prediction, which is the single change that would move
arm G's 90.4%.

---

## 10. Reproduction

```
python3 tools/manoeuvre_library.py --stage all --out <dir>
python3 -m unittest tests.test_manoeuvre_library      # 90 proofs, no archive, no network
```

Inputs, all hashed in the artifact's `inputs` block: the near-GEO element
extract `runtime/proximity-geo/near-geo.npz`
(`ff19d32e…`, the same 217,007,154-row snapshot T8a and T8d measured on), the
committed T8b detect flags (`3df0e824…`, 54,588 objects carrying at least one
flag), the arm-P element cache, and the five committed label files. Tool sha256
`8451cb7cca140c22d59cc80b9fb6342249f70130cd40bc8766fc15c7a2d9f0c1`.
CPU only, one core, 524 s. No GPU consumer, no timer, no scheduled job, nothing
published to any surface.
