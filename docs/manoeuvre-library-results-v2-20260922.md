# T13 — the manoeuvre library v2: RESULTS

**Date:** 2026-09-22. **Registration:** `docs/manoeuvre-library-v2-preregistration-20260922.md`
(commit `b648755`, committed alone before any number below existed).
**Instrument:** `tools/manoeuvre_library.py` with `tests/test_manoeuvre_library.py`
(commits `57226f9`, `58f2471`, `0f38abf`; **141 offline proofs**, no archive, no
network). **v1 registration:** `d86b93d`. **v1 results:** `77eee17`.

**Frozen artifact:** `docs/manoeuvre-library-v2-20260922.json`
`libraryVersion` **v2**
`rulesSha256` **`e2e0cbbdeb50a09c37bbf84131e9dc4b9aa4e8d3b57aa46fbe0343a9ea5cba52`**
`artifactSha256` **`bb9877e034ded6421c11fcfaa930e3624e3dbf4c6ef826ea750fbebd2407445a`**
A consumer pins both. **v1 is retained**, runnable and unamended
(`rulesSha256` `164a5fd1…`); v1 and v2 types may not be mixed in one population.
**Per-burn ledger:** `docs/manoeuvre-library-ledger-v2-20260922.jsonl` — 10,326
rows (every matched burn plus a seeded uniform sample of the rest, seed
20260922) of a full table of **3,914,621** rows, sha256
`cfca5697eff384371d096055a69e0ad9f2d86409095a091dd19783341cb38107`, 1,068 MB,
not committed.

---

## READ THIS BEFORE ANY NUMBER

**Every agreement figure below is agreement between rule sets.** Each label
class is another instrument's output on the same element sets — T8a's arrivals,
T8b's campaigns, T10a's legs, T10b's north-south ledger — not a record of what
an operator did. Agreement is not accuracy, not validation and not a detection
rate, and nothing downstream may call it one.

**Every threshold in this library is a screen, not a law**, including v2's new
one. The floor below is the point at which a net change stops being separable
from the uncertainty of the two things that make it. A burn just above it and a
burn just below it are one kind of thing observed on two sides of an instrument
limit.

**v1's numbers are not superseded.** Nothing published from v1 is retracted.
Where this document prints a v1 figure beside a v2 figure, the two are the same
burns typed by two rule sets, not a before and an after.

---

## 1. Headline — the registered bar was NOT met

| | v1 | v2 |
|---|---:|---:|
| burns typed | 3,914,621 | **3,914,621** |
| UNLABELLED, overall | 23.62% (924,463) | **20.91%** (818,416) |
| **UNLABELLED, arm G (near-GEO)** | **90.41%** (920,618 of 1,018,263) | **79.996%** (814,571 of 1,018,263) |
| UNLABELLED, arm P | 0.13% (3,845 of 2,896,358) | **0.13% (3,845)** — identical, §4 |
| burns firing two rules (Gate P) | 84, 2.15e-5 | 64, **1.63e-5** — bar 5%, **not fired** |
| wall time, both arms, one CPU core | 524 s | 808 s |

**The registration fixed the bar at arm-G UNLABELLED below 50%. It came out at
80.0%. The registered expectation FAILED, and the clause was not adjusted to
reach it.**

**And the change nevertheless did what it was written to do.** The two facts sit
together and both are the result:

* The inclination channel is no longer the binding constraint. Burns that fail
  because **both channels moved** fell from **906,864 to 273,264**, a 69.9%
  drop, and the median net change is **0.00323 °** against a raw median of
  **0.01575 °** — the prediction removes **80.1%** of the raw inclination change
  at the median (§3.2).
* What the change uncovered is that the arm-G rule set's **drift** clauses were
  the next wall, and they are a bigger one. Burns failing because the **drift
  moved but fits no registered band case** rose from **13,009 to 528,609** —
  64.6% of everything v2 cannot label. Those burns were always there; under v1
  they failed at the inclination clause first and were counted in the 906,864.

**Gate N is still the story, and the story has changed owner.** v1's arm-G
UNLABELLED was an inclination-clause artefact. v2's is a statement about the
registered drift bands: 0.010 °/day, the 0.020 °/day stationed band, and the
station-segment definition do not between them describe half a million detected
near-GEO drift changes. That is a fact about the registered type set, measured,
and it is published here rather than fixed quietly. **Fixing it is a v3.**

Gates fired under v2: **Gate F** for `drift stop` and `orbit lower`. **Gate L**
for `inclination adjust` and `orbit lower`. **Gate U** for `inclination adjust`
alone. Gate P did not fire. Each is worked through in §5.

---

## 2. The change, and the floor it is thresholded on

v2 replaces the arm-G raw inclination clause with the **net** change — the
observed inclination minus a natural-motion prediction over the same span
(T10b's committed form: `incPredictedDeg`, `deltaIncNetDeg`) — on a floor
derived from the two errors that make that quantity:

    netFloorDeg(Δt) = sqrt( σ_pole²  +  (ε_ω · Δt)² )

| term | value | what it is |
|---|---:|---|
| σ_pole | **9.683819956551464e-4 °** | MEASURED residual of this same predictor over **948,942** quiet GEO arcs, median span 0.502 d (`docs/stationkeeping-efficiency-20260922-receipt.json` `poleNoiseFloor.sigmaPoleDeg`). Contains the fit scatter of both element sets and the periodic terms the secular model omits; its own committed note calls it an upper bound. Larger than the registered fit-scatter form √2·σ_i = 2.3617e-4 °, which it contains |
| ε_ω | **3.7656075792003106e-4 °/day** | MEASURED gap between the model pole speed (360/53)·sin(7.4°) = 0.8748380 °/yr and the calibration median 0.7372992 °/yr over 33 objects — the prediction's own uncertainty, which is a rate error and so grows with the span |

**No κ is applied to either term**, because a κ would be a pick and this
archive's p99/σ is 116 at GEO. The bar is that the net change exceed the
uncertainty of the net change. At zero span the floor **is** σ_pole, 1.16× v1's
fixed 8.35e-4 ° bar — v2 is not a loosening of v1's bar; it is the same order of
magnitude applied to a different quantity.

**Measured floor over the run** (`netFloorDeg`, all 1,018,263 arm-G burns):

| | p5 | p25 | p50 | p75 | p95 |
|---|---:|---:|---:|---:|---:|
| `netFloorDeg` (°) | 1.347e-3 | 2.577e-3 | **4.413e-3** | 6.899e-3 | 1.412e-2 |
| `naturalSpanDays` (d) | 2.48 | 6.34 | **11.43** | 18.14 | 37.40 |
| `baselineSpanDays` (d) | 4.27 | 9.99 | **18.04** | 29.92 | 60.87 |

The natural span runs from the baseline window's median epoch to the flag and is
about 63% of v1's published `baselineSpanDays` at the median, as the
registration said it would be. Both are carried on every record so neither can
be mistaken for the other. **The median floor is 4.41e-3 °, 5.3× v1's fixed
bar** — and the median quantity it is applied to fell by 4.9×, which is why the
comparison is not a loosening.

---

## 3. The three registered discriminations, published whatever they show

### 3.1 Discrimination 1 — the span dependence: **v2 still climbs, and more steeply**

The registration: *"v1's clause is measuring spacing, so under v1 the arm-G
UNLABELLED fraction must rise with `baselineSpanDays`. If v2 fixes the
mechanism, its UNLABELLED fraction must be markedly flatter in span. A v2
UNLABELLED fraction that still climbs with span like v1's is the change
failing, and is published as such."*

| `baselineSpanDays` bin | burns | v1 UNLABELLED | v2 UNLABELLED | v1 − v2 |
|---|---:|---:|---:|---:|
| 0 – 4.27 d | 50,893 | 76.27% | **56.49%** | 19.8 pt |
| 4.27 – 9.99 d | 203,443 | 80.56% | **58.88%** | 21.7 pt |
| 9.99 – 18.04 d | 254,927 | 91.90% | **80.29%** | 11.6 pt |
| 18.04 – 29.92 d | 254,947 | 95.58% | **90.46%** | 5.1 pt |
| 29.92 – 60.87 d | 203,134 | 95.17% | **91.95%** | 3.2 pt |
| > 60.87 d | 50,919 | 91.53% | **86.35%** | 5.2 pt |
| **rise, first bin to worst bin** | | **+19.3 pt** | **+33.9 pt** | |

**This discrimination fails on its own terms.** v2's curve is lower everywhere —
by 19.8 points at short span — but it climbs by 33.9 points across the bins
against v1's 19.3. v1 was near-saturated at 90%+, so it had little room to
climb; v2 has room and uses it.

**What that means, stated without rescuing it.** v2 removed the span dependence
that came through the inclination clause and did not remove the span dependence
that comes through the drift clauses, which is larger. A longer differencing
span means a larger drift excursion, so `driftBefore` and `driftAfter` are more
often outside the 0.020 °/day stationed band on both sides at once — the
`drift-moved-outside-every-band-case` state, which is 64.6% of v2's no-rule
burns. The registration wrote this discrimination expecting the inclination
clause to be the whole span mechanism. It was not. **The honest reading is that
v2 fixed the clause it changed and left a larger, differently-sourced span
dependence standing, and no v2 figure may be read as though span dependence had
been removed.**

### 3.2 Discrimination 2 — how much the prediction removes: **it removes 80%**

The registration: *"If that ratio is near 1, the secular prediction is not
removing the motion and the diagnosis of v1 §2 was wrong."*

| quantity, all arm-G burns | p5 | p25 | p50 | p75 | p95 |
|---|---:|---:|---:|---:|---:|
| \|Δi\| raw (°) | 0.00110 | 0.00635 | **0.01575** | 0.0294 | 0.0696 |
| \|Δi_net\| (°) | 0.000275 | 0.001463 | **0.003234** | 0.006747 | 0.02774 |
| `netFloorDeg` (°) | 0.001347 | 0.002577 | **0.004413** | 0.006899 | 0.01412 |
| **\|Δi_net\| / \|Δi\|** | 0.0186 | 0.0889 | **0.1987** | 0.658 | 4.099 |

**The median burn keeps 19.9% of its raw inclination change after the natural
motion is removed.** v1's diagnosis holds: the raw quantity at GEO is dominated
by luni-solar motion, and a secular Laplace-plane rotation accounts for four
fifths of it. The p95 ratio above 1 is real and is not an error: for a burn
whose own plane change opposes the natural drift, the net exceeds the raw, and
5% of arm-G burns are in that state.

At the median the net change, 0.00323 °, is **below** the median floor,
0.00441 ° — which is precisely why the `both-channels-moved` count fell by 70%.

### 3.3 Discrimination 3 — the model sensitivity: **the answer is not a model artefact**

Four arm-G type mixes over the same 1,018,263 burns, differing only in which
prediction the inclination clause was handed:

| type | v1 rule set | **v2 as registered** | v2 with J2 added on top | v2 at the calibrated circuit |
|---|---:|---:|---:|---:|
| UNLABELLED | 920,618 | **814,571** | 814,605 | 827,054 |
| drift start | 4,555 | **37,910** | 37,893 | 32,177 |
| drift stop | 31,095 | **31,103** | 31,103 | 31,102 |
| east-west keeping | 17,500 | **91,142** | 91,121 | 84,309 |
| north-south keeping | 3,533 | **2,563** | 2,567 | 2,651 |
| station acquisition | 37,324 | **37,336** | 37,336 | 37,332 |
| graveyard raise | 3,638 | **3,638** | 3,638 | 3,638 |

* **The J2 question does not matter here.** Adding the nodal regression on top
  of the Laplace rotation — which T10b's tool records as double-counting the
  oblateness — moves 34 burns in a million, 0.004% of the arm. The registration
  called this an assumption about which model is correctly posed rather than a
  fact; at this population and these inclinations it is an assumption with no
  measurable consequence, and that is now measured rather than argued.
* **The circuit geometry moves the answer by 1.5%.** At T10b's calibrated tilt
  6.747° and period 56.23 yr the arm-G UNLABELLED fraction is 81.2% against
  80.0%. The headline is robust to the constant that is least certain.

---

## 4. Arm P — registered as carried, actually rerun, and identical

The registration (§4, deviation V5) said arm P would be **carried** from v1
without rerunning it, on the strength of the rule-hash assertion. **It was rerun
instead**, because a measured identity is stronger evidence than a carried
count, and because rerunning removed the risk of a bookkeeping error in the
carry. Declared as deviation **V6** in §8.

Every arm-P block of the v2 artifact is **identical** to the committed v1
artifact's, checked field by field:

| block | identical |
|---|---|
| `population.byArm.P` (2,896,358 burns, 3,845 UNLABELLED, every per-type count) | **yes** |
| confusion rows for `orbit raise`, `orbit lower`, `phasing`, `decaying`, `inclination adjust` | **yes** |
| `unmatchedByType`, `controls`, `perTypePrecision` for those five types | **yes** |
| the four `P:` rows of `noRuleBreakdown` | **yes** |
| the `P:` rows of `deltaQuantiles` | **yes** |
| `episodes["transfer-leg run"]` = 323,405 | **yes** |
| the 34-row external published-event check | **yes** |
| `labelCounts`, and every `inputs` entry but `toolSha256` and `ledgerSha256` | **yes** |

**v2 does not touch arm P.** No arm-P rule reads either net constant; the five
arm-P rule objects are the same objects in both rule sets, not copies. The
registered §5 assertion is also reported mechanically in the artifact
(`byteIdenticalToV1`), and both halves hold:

| rule | v1 = v2 by canonical-JSON sha256? |
|---|---|
| G2, G6, G7, P1, P2, P3, P4, P5 | **identical** (registered unchanged) |
| G1, G3, G4, G5 | **differ** (registered changed) |

Per-rule hashes are printed in the artifact's `perRuleSha256` block for both
versions, so the claim can be checked rather than taken.

---

## 5. The arm-G type set, the gates, and the five affected types

### 5.1 The arm-G mix

| type | v1 | v2 | change |
|---|---:|---:|---|
| UNLABELLED | 920,618 (90.41%) | **814,571 (79.996%)** | −106,047 |
| east-west keeping | 17,500 | **91,142** | ×5.2 |
| station acquisition | 37,324 | **37,336** | +12 |
| drift start | 4,555 | **37,910** | ×8.3 |
| drift stop | 31,095 | **31,103** | +8 |
| graveyard raise | 3,638 | **3,638** | unchanged |
| north-south keeping | 3,533 | **2,563** | −970 |

**Episodes.** 10,705 relocations against v1's 829 — a drift start closed by a
stop 2.0 ° or more away, and there are 8.3× as many drift starts to open one.
323,405 transfer-leg runs, identical to v1 (arm P, §4). Neither changes any
burn's type.

`north-south keeping` falling is the registered direction (§6.2): G5 now
requires a change the plane's own motion does not explain, so burns whose
inclination moved naturally no longer fire it.

**Why the arm cannot label 80%**, from the artifact's own breakdown of the
818,352 no-rule burns (814,507 of them arm G):

| why no rule fired, arm G | v1 | v2 |
|---|---:|---:|
| drift moved, outside every band case | 13,009 | **528,609** |
| both channels moved | 906,864 | **273,264** |
| inside the band but outside a station segment | 399 | **11,402** |
| below the drift floor and the inclination bar | 262 | **1,232** |

The first two rows swapped places. The third and fourth rise for the same
reason: a burn whose net inclination is quiet now reaches a drift test it never
used to reach, and fails there.

### 5.2 The five affected types, paired

Both intervals are Wilson 95%. **The two runs are not independent** — the same
burns, the same labels, one clause changed — so **no difference below is given a
p-value, a significance or a confidence of its own**, as the registration fixed
before the numbers existed.

| type | v1 burns | v2 burns | v1 matched | v2 matched | v1 forward agreement | v2 forward agreement | v1 verdict | v2 verdict |
|---|---:|---:|---:|---:|---|---|---|---|
| **drift start** (vs `t8aInitiatingFlag`) | 4,555 | 37,910 | 50 | **241** | 0.560 [0.423, 0.688] | **0.643 [0.581, 0.701]** | — | — |
| **drift stop** (vs `t8aArrival`) | 31,095 | 31,103 | 204 | **204** | 0.426 [0.361, 0.495] | **0.426 [0.361, 0.495]** | Gate F | **Gate F** |
| **station acquisition** (v1 vs `t10aPostTransferEndpoint`; v2 vs `t8aArrival`, §6) | 37,324 | 37,336 | 711 | **711** | 0.000 [0.000, 0.005] | **0.751 [0.718, 0.781]** | Gate F | — |
| **east-west keeping** (vs `t10cEastWestObject`) | 17,500 | 91,142 | 62 | **475** | labelled gap | **labelled gap** | gap | **gap** |
| **north-south keeping** (vs `t10bNorthSouth`) | 3,533 | 2,563 | 19 | **20** | 0.526 [0.317, 0.727] | **0.500 [0.299, 0.701]** | UNDERPOWERED | **clears Gate U** |

Reading each:

* **`drift start` gains a confidence worth having.** Its matched count went from
  50 to 241 — a 4.8× better-powered figure on a 8.3× larger population — and its
  agreement with T8a initiating flags rose to 0.643 with an interval half as
  wide. Its most frequent class is still the class its rule was written against.
  **This is the clearest single gain of v2.**
* **`drift stop` is untouched, exactly.** Eight more burns, none of which matched
  anything, so the cell, the interval and Gate F are bit-identical to v1. The
  competing class is still T10b's north-south windows at 106 against 87, and
  v1's reading stands unchanged: that is the density of a label set of 1,107
  windows over 66 heavily-manoeuvred objects, not evidence that a drift stop
  measures inclination. The 5.0-day tolerance is a registered constant and v2
  did not move it.
* **`north-south keeping` clears Gate U by one event.** It has exactly 20 matched
  against the registered n ≥ 20, so it now publishes a confidence: **0.500
  [0.299, 0.701]**, against a class that is also its most frequent. It is one
  event above the bar and the interval spans 40 points; **it earns a number, not
  a strong one**, and it still may not name an alert on that width. The gain is
  not in the point estimate — it is that the type is now a cleaner population:
  its catalogue-passive fraction fell from **6.96% to 1.44%** (§5.4), which is
  the fifth-cleanest of any type in the library.
* **`east-west keeping` remains a labelled gap at burn level and its object-level
  enrichment halved.** T10c's per-burn recall is 1.81%, so there is still no
  per-burn east-west label in the repository. At object level a v2
  `east-west keeping` burn is **8.7×** more likely than the population base rate
  to sit on an object T10c independently identified as an east-west
  station-keeper (12.85% against a 1.47% base rate), where v1's figure was
  **17.6×**. **The rule now labels 5.2× as many burns and each one carries half
  the enrichment.** That is a real cost of the change and is not netted against
  the gain. Its most frequent matched class is T10b's north-south windows (405
  of 475), which is the same label-density effect that fires Gate F on
  `drift stop` and which cannot fire a gate here because the expected class is
  object-level.
* **`station acquisition`'s number is a corrected mapping, not a prediction.**
  See §6.

### 5.3 The gates

| gate | v1 | v2 |
|---|---|---|
| **Gate P** — partition | not fired, 84 multi-fire (2.15e-5) | **not fired**, 64 (1.63e-5); G2+G5 49, G3+G5 15 |
| **Gate N** — unlabelled | 23.62% overall, 90.41% arm G | **20.91% overall, 79.996% arm G** |
| **Gate U** — underpowered | `north-south keeping` (19), `inclination adjust` (17) | **`inclination adjust` (17) only** |
| **Gate F** — falsification | `drift stop`, `station acquisition`, `orbit lower` | **`drift stop`, `orbit lower`** |
| **Gate L** — leak | `orbit lower`, `inclination adjust` | **`orbit lower`, `inclination adjust`** (both arm P, both unchanged) |
| **Gate V** — vocabulary | held | **held** |

The multi-fire count fell because G5 fires less: the G2+G5 and G3+G5 overlaps
the v1 registration anticipated are the only two combinations that occur, in
both versions.

### 5.4 The leak control on the affected types

**Gate L's bar is 0.10.** No arm-G type approaches it under either version, and
the change did not make any of them dirtier than that:

| type | v1 passive fraction | v2 passive fraction |
|---|---:|---:|
| east-west keeping | 0.14% | **0.65%** |
| drift stop | 1.23% | **1.23%** |
| north-south keeping | 6.96% | **1.44%** |
| station acquisition | 3.60% | **3.59%** |
| drift start | 0.42% | **3.99%** |
| graveyard raise | 7.01% | **7.01%** |
| UNLABELLED | 19.44% | **21.73%** |

**`drift start`'s passive fraction rose nearly tenfold, from 0.42% to 3.99%**, on
a population 8.3× larger. It is well inside Gate L's bar and it is stated
because a rule that labels eight times as many burns and stays clean is a
different claim from one that labels eight times as many burns and gets ten
times dirtier. The absolute passive count went from 19 to 1,514. **A consumer
reading `drift start` under v2 is reading a type that now includes 1,514 burns
on catalogue-passive objects that cannot burn.**

`north-south keeping` moved the other way and is the cleanest arm-G evidence
that the net clause is selecting better: fewer burns, and a passive fraction
cut by a factor of 4.8.

---

## 6. The station-acquisition mapping correction

v1 wrote G3 against `t10aPostTransferEndpoint` and measured **0 / 711**, firing
Gate F, with 534 of its 711 matches being T8a **arrivals**. v1 concluded the
rule was sound and the registration's mapping wrong, and declined to fix it
because the mapping is part of the rule table whose hash is the library's
identity. **v2 maps G3 to `t8aArrival`.** Its clauses are untouched: the rule
object's `as_dict()` is identical between versions with `expectedLabelClass`
removed, and the two versions share the same test function.

v2's figure: **534 / 711 = 0.751 [0.718, 0.781]**, Gate F does not fire, and
`t8aArrival` is both the expected and the most frequent class.

**That Gate F does not fire is arithmetic, not evidence.** The class was chosen
because it was already the most frequent class in v1's matrix. **A mapping
corrected to match a measured outcome cannot then be scored as a successful
prediction**, and this sentence travels with the 0.751 wherever it is printed.
What the number does establish is the size of the agreement, with its interval,
on the v2 population — and the v2 population is 37,336 burns against v1's
37,324, with a matched set of exactly the same 711, so the correction moved the
score and not the burns.

`t10aPostTransferEndpoint` remains a column in the matrix and G3's cell against
it is still printed: it is **0 of 711**, the same zero v1 measured, out of 84
such labels in total. Removing the column, or the zero, would hide the
correction. G3's 711 matches are T8a arrivals 534, T8a initiating flags 90 and
T10b north-south windows 87.

---

## 7. v1 still runs, and the one thing it cannot reproduce

The registration fixed this proof standard **before the run** rather than
explaining it after.

**What reproduces.**

* `rules_sha256("v1")` = **`164a5fd11e4c63744615bbf58c02289cc812c46b630458a85b84f9aee35024f6`**,
  unchanged, asserted by an offline test that needs no archive.
* A full v1 rerun at `--library-version v1` over the same inputs, 606 s, produced
  an artifact **identical field for field** to the committed
  `docs/manoeuvre-library-v1-20260922.json` after removing exactly three fields.
  The reduced canonical-JSON sha256 is the same on both sides:

  | | value |
  |---|---|
  | reduced sha256, committed v1 artifact | **`9163fdb2e1c0df0af6fb69c2c938af15ce9cdacbfe0653a361b1d45c58ac58fd`** |
  | reduced sha256, fresh v1 rerun | **`9163fdb2e1c0df0af6fb69c2c938af15ce9cdacbfe0653a361b1d45c58ac58fd`** |

  That includes `inputs.ledgerSha256` = `dc2a2ccd1cc00258df5aeef797aa14db2c2d88e587d5f397b60bfe76e52b6e6b`
  — the 980,926,248-byte full v1 ledger came out byte-identical — and every
  count, every cell of the matrix, every gate and every quantile.
  Proof script: `tools/manoeuvre_library_v1_reproduction.py`, which prints the
  first differing path if there is one. There was none.

**What cannot, and why it is not faked.** The v1 `artifactSha256`
`eb287e809c0cd1b2f0de0b5bbb80ba33e811a692ca794944ae3dda614abef465`
**cannot be reproduced.** The artifact embeds `inputs.toolSha256`, the sha256 of
`tools/manoeuvre_library.py` itself, and `wallSeconds`. A second rule set in the
same file changes the file's bytes, so `toolSha256` changes, so `artifactSha256`
changes:

| field | committed v1 | fresh v1 rerun |
|---|---|---|
| `inputs.toolSha256` | `8451cb7cca140c22…` | `e6ccc46bbbeb3ef7…` |
| `wallSeconds` | 523.946 | 606.435 |
| `artifactSha256` | `eb287e80…` | `2d0c6641…` |

Pinning the old tool hash would falsify the artifact's own provenance record,
and it is not done — a test asserts that the string `eb287e80…` appears nowhere
in the tool. **This is a weaker proof than a matching `artifactSha256` and is
labelled as such here and in the registration.** The committed v1 artifact is
not amended, reissued or recomputed.

To keep this true, a v1 run had to be stopped from publishing the fields only v2
measures: the burn record is version-independent by design, so `geo_burns`
attaches the net-change fields whatever version is running, and without gating
they would have reached the v1 ledger and the v1 quantile block and broken the
reproduction silently. That was caught before any v2 number existed (commit
`58f2471`) and three proofs hold it there.

---

## 8. Deviations, and what this run does not claim

| # | what | why |
|---|---|---|
| **V6** | The registration (§4, V5) said arm P would be **carried** from v1 without a rerun. It was **rerun**. | A measured identity is stronger than a carried count and removes the risk of a carry bookkeeping error. §4 reports the field-by-field identity. The deviation is toward more measurement, not less |
| **V7** | The registration (§6.3) said the three discriminations would be published; it did not say where they would be computed. They are computed **inside the same pass**, off the same burn records, and land in the artifact as a `discriminations` block. | An analysis script run afterwards would have been a second pass over a second population. `_discriminations` reads a burn that is already typed and writes nothing back to it, and a test asserts that no variant can move an assigned type |
| **V8** | The registration's headline expectation (arm-G UNLABELLED below 50%) is **not met**: 79.996%. | Published as the headline, in §1. The clause was not adjusted, the floor was not moved, and no second bar was invented after the fact |
| **V9** | Registered discrimination 1 **fails**: v2's UNLABELLED fraction still climbs with the differencing span, by 33.9 points against v1's 19.3. | §3.1, with the mechanism — the residual span dependence is in the drift clauses, not the inclination clause. No v2 figure may be read as though span dependence had been removed |
| D1–D6, E1–E5 | v1's deviations and errata | unchanged; the v1 registration §9 and v1 results §8 still hold and are not restated here |

**What this run does not claim.**

* It does not claim that v2 labels a GEO burn correctly. Every figure in §5 is
  agreement between rule sets.
* It does not claim the natural-motion model is right. It claims the model
  choice does not move the headline (§3.3) and that the model's own measured
  rate error is inside the floor (§2).
* It does not claim any v1→v2 difference is significant. No such test was run
  and none may be run on these two runs, which share their burns and labels.
* It does not claim `north-south keeping`'s 0.500 is a good number. It is one
  matched event above the underpowered bar with a 40-point interval.
* It does not claim the residual 80% is irreducible. It locates it, in §5.1, in
  the registered drift bands.

---

## 9. What v2 may and may not be used for

**May.** A burn may be given its v2 type from the ledger, pinned by
`libraryVersion` **and** `rulesSha256` `e2e0cbbd…`. Types carrying a confidence
under v2: `station acquisition` **0.751 [0.718, 0.781]** (with §6's sentence
attached), `phasing` **0.677 [0.501, 0.814]**, `drift start` **0.643 [0.581,
0.701]**, `orbit raise` **0.549 [0.506, 0.590]**, `north-south keeping`
**0.500 [0.299, 0.701]** (one event over the bar, wide). The arm-P result is
v1's arm-P result and carries v1's readings.

**May not.** `orbit lower` may not be treated as propulsive. `inclination
adjust` may not be used at all until the plane-noise floor is re-derived (M6),
and may not name an alert (UNDERPOWERED, and Gate L at 36.30%). `drift stop`
carries Gate F wherever it is printed. `north-south keeping` may not name an
alert on a 40-point interval. `east-west keeping` has no burn-level agreement
figure — its cell is a labelled gap, not a zero — and its object-level
enrichment is **8.7×**, down from v1's 17.6×. No type may be attached to an
UNLABELLED burn, and **80.0% of near-GEO burns are still UNLABELLED**. v1 and v2
types may not be mixed in one population.

**What T13 still owes M0.** The design's class-conditional next-burn size needs
a type per burn and a size distribution per type. Five types can supply one
today, against v1's three, and `drift start`'s is now 8.3× better populated.
The rest wait on a v3 whose **drift** clauses describe the 528,609 near-GEO
burns that change the drift rate above the registered floor and fit no
registered band case. That is the single change that would move arm G's 80.0%,
and it is a rule change, so it is a new registration, a new `rulesSha256` and a
new matrix.

---

## 10. Reproduction

```
python3 tools/manoeuvre_library.py --library-version v2 --stage all --out <dir>
python3 tools/manoeuvre_library.py --library-version v1 --stage all --out <dir>
python3 tools/manoeuvre_library_v1_reproduction.py \
    docs/manoeuvre-library-v1-20260922.json <dir>/manoeuvre-library-v1.json
python3 -m unittest tests.test_manoeuvre_library   # 141 proofs, no archive, no network
```

The version is never defaulted; `--library-version` is required and a test
asserts that every entry point takes it with no default.

Inputs, all hashed in the artifact's `inputs` block and **identical to v1's**
except the tool and the ledger: the near-GEO element extract
`runtime/proximity-geo/near-geo.npz` (`ff19d32e…`, the same 217,007,154-row
snapshot T8a and T8d measured on), the committed T8b detect flags
(`3df0e824…`), the arm-P element cache, and the five committed label files.
Tool sha256 `e6ccc46bbbeb3ef7929b62cfdaf680685f4b6d5f79bd1822cfd1b4a3a35beaa9`.
CPU only, one core, 808 s for v2 and 606 s for the v1 rerun, on the workstation.
No GPU consumer, no timer, no scheduled job, nothing published to any surface.
