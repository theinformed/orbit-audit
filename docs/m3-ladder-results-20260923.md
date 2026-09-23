# M3 results — the sequential precision ladder, calibrated on the archive

**Does the ladder earn a rung above S1? Near-geosynchronous regime: the
registered rung rule returns YES, and then the registered time control and a
post-hoc comparison both withhold it, so the operative answer is NO. Low-Earth
regime: NO, and Gate S fires, so that regime's reach layer is withheld
entirely.**

Measured 2026-09-23 on `pc`, CPU only, `nice`-d, no GPU. Registration:
`docs/m3-ladder-replay-preregistration-20260923.md`, committed **alone** at
`bb0eb17` before any instrument for this track existed; the instrument and its
41 offline tests followed. The ordering in `git log` is the evidence. Every
stage rule, horizon, control, gate and decision below was fixed in that
document and none was changed after a number existed. Four changes were made
after numbers existed — three of them labels or arithmetic over counts the
artifact already carried, one of them a trim of the committed ledgers — and all
four are named in §9. None touches a rule, a threshold or a gate.

Artifacts: `docs/m3-ladder-20260923.json` (every table with its n),
`docs/m3-ladder-20260923-receipt.json` (provenance and input checksums),
`docs/m3-ladder-episodes-geo-20260923.jsonl` and
`docs/m3-ladder-episodes-leo-20260923.jsonl` (the committed episode subsets).

**Framing, restated because it constrains this document.** No propellant, mass
or consumable figure is read, computed or published for any object. No registry
or country code enters any rule, feature, grouping or output column. Nothing
here is a miss distance or a conjunction. Nothing here states an intent. Every
precision is a property of a detector on a catalogue, never a rate at which
objects of a class do anything.

**The sentence that travels with every near-geosynchronous rung, fixed in the
registration §6.3 and repeated here:**

> The GEO catalogues remain uncontrolled. This trigger fires 3,812 times inside
> 517,391 days of provably uncontrolled motion — 0.288 [0.279, 0.298] of the
> rate it fires on objects that can manoeuvre, against a bar of 0.10. A rung
> precision measured here is a property of this detector on this catalogue, not
> a rate at which objects of a class do anything.

---

## 0. The answers, one line each

| | Answer |
|---|---|
| **GEO, rung rule** | **YES** — S2's Wilson lower bound 0.374% exceeds S1's point precision 0.253% on n = 3,254 resolved episodes |
| **GEO, Gate T** | **FIRES on S2 and S3** — under the registered time-shuffle their window-rule precisions sit inside the shuffled band, so both rungs are **withheld** |
| **GEO, Gate S** | **does not fire** — the eventual partner was inside R₁ in 47 of 74 arrivals (63.5% [52.1, 73.6]) at the governing 20-day horizon, and 66 of 74 (89.2%) at the 180-day arm |
| **GEO, post-hoc** | S2 is reachable **only** from an episode whose first burn reached a station, and S1 restricted to that same population is **0.781% [0.603%, 1.010%]** on 7,299 — **above** S2's 0.584%. The separation is the set-size condition, not the second burn |
| **GEO, net** | the ladder separates S2 above the *pooled* S1, the separation **does not survive the time control**, and it **does not survive conditioning on S2's own eligible population**. Nothing above S1 may print a precision today, and the registered falsifier — *S2/S3 precision not separated above S1* — is **met** once the comparison is made on like populations |
| **LEO, rung rule** | **NO** — S2 resolved 440 times with nothing arriving (95% upper bound 0.866%), S3 298 times (upper bound 1.273%) |
| **LEO, Gate S** | **FIRES** — the partner was inside R₁ in 14 of 33 arrivals (42.4% [27.2, 59.2]), below half, so **that regime's reach layer is withheld entirely** |
| **LEO, control** | objects the catalogue does not class as payloads climb the same ladder: 507 reach S2 and 346 reach S3, a per-episode leak of about 0.44 against a bar of 0.10 |

---

## 1. The population, and the cross-check that says it is the right one

The ladder's S1 is the alarm lane's own trigger, and the two populations agree
where they must.

| | the alarm lane's replay | **this replay** |
|---|---:|---:|
| window | 2010-01-01 → 2020-01-01 | **the same** |
| derived tick | 0.7564 d | **0.7564237 d** |
| assessments announced inside the window | 71,551 | **71,649** |
| assessable (inside the measured population) | 33,599 | **33,629** |
| announcement lag, median | 0.378 d | **0.376 d** |

The residual is the lane's warm start, which treats every chain that closed
before the window as already announced; this replay opens an episode for a
chain whose announce falls inside the window whether or not the chain began
before it. The difference is 98 assessments in 71,649 and it is reported
rather than tuned away.

The low-Earth arm agrees with its own lane in the same way: 28 arrivals over
4,882 episodes here against 27 over 5,327 alerts there, and a median lead of
687.1 d against 684.4 d. The counts differ because an episode merges campaign
starts that the lane counts separately.

---

## 2. GEO — the rungs

Pooled over classes. `n` is every episode that reached the rung and resolved;
an expiry is in the denominator; the outcome record never ended before a
horizon closed, so there are no labelled gaps in these rows.

| rung | reached | resolved | k | precision | Wilson 95% | separated above the previous rung |
|---|---:|---:|---:|---:|---|---|
| **S1** | 24,111 | 24,111 | 61 | **0.253%** | [0.197%, 0.325%] | — |
| **S2** | 3,254 | 3,254 | 19 | **0.584%** | [0.374%, 0.910%] | **yes** |
| **S3** | 2,059 | 2,059 | 10 | **0.486%** | [0.264%, 0.892%] | no |

Per class, with the frozen taxonomy's own names:

| class | rung | k/n | precision | Wilson 95% |
|---|---|---:|---:|---|
| 0 RESIDUAL | S1 | 46/23,844 | 0.193% | [0.145%, 0.257%] |
| | S2 | 18/3,224 | **0.558%** | [0.353%, 0.881%] |
| | S3 | 8/2,026 | 0.395% | [0.200%, 0.777%] |
| 1 WIDE-CROSSING | S1 | 15/267 | **5.618%** | [3.434%, 9.061%] |
| | S2 | 1/30 | 3.333% | [0.591%, 16.670%] |
| | S3 | 2/33 | 6.061% | [1.678%, 19.606%] |

**The separation is entirely the residual class's, and §3.4 shows it is not
the second burn's.** Class 1 — the one class
the vocabulary gate already lets speak — gains nothing from a second burn: its
S2 and S3 cells hold thirty and thirty-three resolved episodes and intervals
four times wider than the difference they would have to show. The class that
separates is the one the gate withholds on its whole-population numbers, and
it separates for the same reason the operating-point curve found it separating
under an evidence threshold: a second confirmed change is itself a filter on
the residual class.

Class 1's S1 precision here is 5.618% against the frozen artifact's archive-wide
3.406% and the lane's own 2010s replay figure of 5.147%. The decade is a denser
slice of the archive than its mean, the intervals overlap heavily, and the
figure is not a new estimate of anything.

---

## 3. GEO — the sets, the leads, the expiries

### 3.1 Set size, and the horizon that decides it

| rung | set size p25/p50/p75, governing 20-day horizon | same, 180-day arm | plane-compatible p50 | chance membership p50 |
|---|---|---|---:|---:|
| S1 | **0 / 0 / 1** | 28 | 0 | 0.000 |
| S2 | 1 / 1 / 2 | 24 | 1 | 0.0030 |
| S3 | 1 / 1 / 1 | 1 | — | — |
| S1, class 1 only | 41 / **66** / 98 | 370 | 7 | 0.163 |

**The median first burn reaches nothing inside the horizon the forward-error
measurement leaves resolvable.** That is the single hardest number in this
document. The horizon is 20 days because beyond it the median propagated
longitude error exceeds the median gap between occupied longitudes; inside it,
a routine drift change of 0.0156 °/day — the measured median of the class —
moves the object 0.31°, which crosses about one occupied longitude at a
measured median spacing of 0.394°. The 180-day arm, which the committed
operating-point table already uses, gives a median of 28, and the forward error
at that horizon is 2.651°, above Gate W's own 2.0° bar. Both numbers are
printed and neither is the other's correction: the set is either resolvable and
almost always empty, or populous and drawn past the horizon its own error
measurement allows.

Class 1 is the exception by construction — it is named by path length and
occupied longitudes crossed — and its median set is 66 even at 20 days.

### 3.2 Lead

The Kaplan–Meier median lead is **not reached at any rung**: with 99.4% to
99.7% of episodes expiring, the survival curve never falls to one half, and the
quantile is reported as absent rather than as the largest observed time. The
raw distribution over the episodes that did arrive:

| rung | n arrivals | lead p25 | **p50** | p75 |
|---|---:|---:|---:|---:|
| S1 | 61 | 13.8 d | **31.3 d** | 62.7 d |
| S2 | 19 | 30.6 d | **53.5 d** | 96.0 d |
| S3 | 10 | 34.5 d | **49.0 d** | 73.8 d |

A longer lead at a later rung is selection, not warning bought by waiting: the
episodes that receive a second confirmed change are staged transfers, which are
long. The lane found the same thing when its persistence setting bought a
47.4-day median against 22.1 — "the warning is longer because the persistence
requirement selects longer transfers, not because waiting produces warning" —
and the same sentence governs here.

### 3.3 Expiry, time in stage, and the cadence's own cost

| rung | expiry rate | days in stage p50 | announcement lag p50 | arrivals before the announce, counted as misses |
|---|---:|---:|---:|---:|
| S1 | **99.747%** | 174.5 | 0.376 d | 13 |
| S2 | 99.416% | 174.8 | 0.381 d | 23 |
| S3 | 99.514% | 172.0 | 0.373 d | 10 |

The lag is bounded by the 0.7564 d tick, as it must be, and against a 31-day
median lead it is 1.2% of the budget.

---

## 3.4 The comparison the headline needs — POST-HOC, NOT REGISTERED

The registered set-enlarging predicate closes an episode and opens a fresh S1
whenever the new burn's set is larger than the old one **or disjoint from it**.
An empty set is disjoint from everything, so an episode whose first burn reached
nothing can never advance: **16,812 of 24,111 episodes opened with an empty set,
21,835 closed as reopened, and every one of the 3,254 episodes that reached S2
had a non-empty first set.** S2's population is therefore conditioned on a
condition S1's is not, and the two are not comparable as printed.

The comparison on like populations, computed after the registered numbers
existed and changing no rule, threshold or gate:

| population | k/n | precision | Wilson 95% |
|---|---:|---:|---|
| S1, every episode | 61/24,111 | 0.253% | [0.197%, 0.325%] |
| **S1, episodes whose first burn reached a station** | **57/7,299** | **0.781%** | **[0.603%, 1.010%]** |
| S1, episodes whose first burn reached nothing | 4/16,812 | 0.024% | [0.009%, 0.061%] |
| S2 (which only this population can reach) | 19/3,254 | 0.584% | [0.374%, 0.910%] |

**S2 is not above the S1 it should be compared with; it is below it, with
overlapping intervals.** The lift the registered rule found is the reachable
set being non-empty — the `minSlotsReached` axis the operating-point table
already carries — and not the arrival of a second burn. Stated as the design's
own falsifier puts it: **S2/S3 precision is not separated above S1.**

---

## 4. GEO — recall of the set (E4)

Over the 74 arrivals the outcome record attributes to an episode inside the
window:

| | k/n | share | Wilson 95% |
|---|---:|---:|---|
| partner inside R₁ at S1, **governing 20-day horizon** | 47/74 | **63.5%** | [52.1%, 73.6%] |
| partner inside R₁ at S1, 180-day arm | 66/74 | **89.2%** | [80.1%, 94.4%] |
| partner inside R₂ at S2 | 37/42 | 88.1% | [75.0%, 94.8%] |
| earliest rung containing the partner | S1 in 47, never in 27 | | |

**Gate S does not fire.** The reachable set, drawn at the horizon the forward
error leaves resolvable, contains the eventual partner in a clear majority of
arrivals — and the twenty-seven it never contained are the reason the second
arm is printed beside it: widening the horizon to 180 days recovers nineteen of
them, at the cost of a propagation whose own gate fires there.

This is the recall of the **set**, given an episode. The recall of the
**detector** is UNMEASURED, in those words: a third of the catalogue's arrivals
carry no confirmable initiating change, so a sequence that never opened an
episode cannot appear in any denominator here.

---

## 5. Controls

### 5.1 Control (a) — the never-manoeuvred class

**At GEO, control (a) DOES NOT EXIST**, in those words. The measured size of
what is missing is the leak of this very trigger: 3,812 flag chains inside
517,391 days of provably uncontrolled motion, 0.288 [0.279, 0.298] of the rate
it fires on objects that can manoeuvre, against a bar of 0.10. Gate U cannot be
discharged at this regime and every rung carries the registration's §6.3
sentence instead.

**At LEO the control is CIRCULAR and its zero is a tautology**, declared in
advance and confirmed: "never-manoeuvred" is defined by the absence of a flag
from the very detector that defines S1, so those 3,011 objects produce no
trigger, reach no rung, and their zero is a property of the definition rather
than evidence about the ladder.

### 5.2 Control (a′) — objects that cannot manoeuvre, run through the same ladder

The substantive leak control, at the regime that has one. Episodes on objects
the catalogue does not class as payloads:

| rung | control episodes reaching | share | payload share | **leak ratio** |
|---|---:|---:|---:|---:|
| S1 | 12,927 | 100% | 100% | 1.00 by construction |
| S2 | 507 | 3.92% | 9.01% | **0.435** |
| S3 | 346 | 2.68% | 6.10% | **0.439** |

Against a bar of 0.10, **the ladder itself leaks at this regime**: an object
that cannot burn reaches the deepest rung 346 times. Its precision there is a
measured zero — 4 of 12,927 at S1, 0 of 507 at S2, 0 of 346 at S3 — so the leak
is in the **climbing**, not in the outcome. That is exactly the shape the lane
already reported for this detector, whose per-object passive control fires at
0.797 of the payload rate against a design target of 0.001.

### 5.3 Control (b) — the routine-operations types

192 of 24,111 GEO episodes joined the committed manoeuvre-library ledger
(version `v2`, rules `e2e0cbbd…`), because that ledger is a **subset** — 10,326
rows of 3,914,621 — and, worse for this purpose, a subset that keeps **every
matched row**. Its joined episodes are therefore enriched toward the labelled
outcomes by construction, and no population rate may be read off them.

| type | joined n | climbed to S2 | to S3 | ended in S4 |
|---|---:|---:|---:|---:|
| UNLABELLED | 127 | 44 | 27 | 33 |
| east-west keeping | 29 | 6 | 3 | 1 |
| drift start | 22 | 8 | 3 | 10 |
| station acquisition | 9 | — | — | — UNDERPOWERED |
| drift stop | 4 | — | — | — UNDERPOWERED |
| graveyard raise | 1 | — | — | — UNDERPOWERED |

Three of six types are UNDERPOWERED, in those words, and the three that are not
are enriched. **The routine-operations control is NOT DISCHARGED**, and what it
needs is a full-table join, which is a re-run of the library's own instrument
and is owed. The one reading that survives the enrichment is directional and is
stated as such: routine east-west keeping climbs to S2 at about a fifth of its
joined episodes and reaches the outcome once, while a drift start reaches it
ten times in twenty-two — the routine class climbs and the initiating class
arrives.

### 5.4 Control (c) — the time shuffle, and Gate T

Both arms use the window rule, restricted to the same universe (the replay
window plus one outcome horizon), because the flag-attribution rule of the
headline cannot survive a displacement of the arrival epochs. 200 draws, seed
20260922, a single common offset per draw — a null that preserves the arrival
record's own clustering and is therefore conservative.

| rung | n | real | shuffled mean | shuffled p5–p95 | separated |
|---|---:|---:|---:|---|---|
| S1 | 24,111 | **1.207%** | 0.889% | [0.593%, 1.175%] | **yes** |
| S2 | 3,254 | 2.520% | 1.574% | [0.830%, 3.170%] | **no** |
| S3 | 2,059 | 2.914% | 1.710% | [0.826%, 3.205%] | **no** |

**Gate T fires on S2 and S3, and both rungs are withheld.** The first rung's
alignment with the outcome record survives a shifted archive; the deeper rungs'
does not. The band widens with depth because the deeper rungs sit on objects
that burn often and therefore carry more arrivals of their own, and the shuffle
inherits every one of them — which is precisely the confound the control was
registered to expose.

At LEO nothing separates, S1 included: real 0.594% against a shuffled p95 of
0.615%.

---

## 6. LEO — the rungs, and the gate that withholds them

Window 2020-01-01 → 2023-06-01, look-back from 2017-01-01, derived tick
0.4934634 d, 55,222,252 element sets reused from the lane's own extract,
26,190 objects in band, 18,770 campaign starts, 17,809 episodes of which 4,882
are on payload-class objects.

| rung | reached | resolved | k | reading |
|---|---:|---:|---:|---|
| S1 | 4,882 | 4,882 | 28 | **0.574%** [0.397%, 0.828%] |
| S2 | 440 | 440 | 0 | **0 of 440 resolved; nothing arrived, and the 95% upper bound is 0.866%** |
| S3 | 298 | 298 | 0 | **0 of 298 resolved; nothing arrived, and the 95% upper bound is 1.273%** |

A measured zero is a bound, not a rate and not a labelled gap, and it is
printed as a bound.

Set sizes: the in-plane population at θ_p = 0.2° is 33 objects at the median at
S1, 5 at S2 and 1 at S3. Median lead at S1 is 687.1 d, right-censored by the
1,095-day horizon. **Cross-plane reach is not computed** — the plane channel's
noise floor is still 145× too large and its re-derivation is the standing owed
item.

**Gate S fires.** The eventual partner was inside R₁ in 14 of 33 arrivals,
42.4% [27.2%, 59.2%], below half. The in-plane population at the trigger epoch
is not where the partner is: a co-orbital station is usually reached by closing
a plane, and the plane the mover will share is not the plane it shares when it
burns. Per the registration, **the reach layer at this regime is withheld
entirely** until the cross-plane set can be computed — which is the same
dependency the design named before any of this was measured.

---

## 7. The dial — `stage` as a fourth axis

The operating-point table gains its `stage` axis by post-filtering episodes on
each named setting's evidence axes at S1, at `persistenceSweeps = 1` for every
setting; the persistence axis changes announce timing and is not re-measured
here, and every row says so. Every row carries the leak sentence. The pooled
rows the dial would read:

| setting | stage | k/n | precision | Wilson 95% |
|---|---|---:|---:|---|
| everything | S1 | 60/23,663 | 0.254% | [0.197%, 0.326%] |
| | S2 | 18/3,192 | 0.564% | [0.357%, 0.890%] |
| | S3 | 10/2,019 | 0.495% | [0.269%, 0.909%] |
| **balanced** | S1 | 43/543 | **7.919%** | [5.932%, 10.497%] |
| | S2 | 10/97 | 10.309% | [5.697%, 17.946%] |
| | S3 | 6/83 | 7.229% | [3.355%, 14.887%] |
| high-confidence | S1 | 8/161 | 4.969% | [2.539%, 9.498%] |
| | S2 | 2/17 | — | **UNDERPOWERED** |
| | S3 | 1/19 | — | **UNDERPOWERED** |
| very-high | S1 | 8/156 | 5.128% | [2.621%, 9.792%] |
| | S2 | 2/14 | — | **UNDERPOWERED** |
| | S3 | 1/17 | — | **UNDERPOWERED** |

**No setting shows a stage above S1 separated from its own S1.** At `balanced`
S2's Wilson lower bound is 5.697% against an S1 point of 7.919%; the two
tightest settings put fewer than twenty resolved episodes in every stage above
the first, and those cells are UNDERPOWERED in those words and carry no rate.
The `balanced` setting is also the clearest statement of what the set-size axis
alone is worth: applying `minSlotsReached = 5` at S1 lifts the first rung from
0.254% to 7.919% without any second burn at all.

**A stage that has no row is not offered, a stage whose row is UNDERPOWERED is
offered with that label and no rate, and — on today's numbers — no stage above
S1 is offered at all, because Gate T withholds both.**

---

## 8. What the page may print at each stage, today

| stage | what may be printed |
|---|---|
| **S1, GEO, class 1** | unchanged from the committed artifact: the set count at both horizons, the class figure with its interval, the base rate beside it, both structural caveats, and the leak sentence |
| **S1, GEO, class 0** | the set counts and the stage stamp; the class's own precision stays withheld by the vocabulary gate, as it is today |
| **S2, GEO** | the stage stamp, the set before and after, the members that dropped out struck through and kept — **and "stage precision withheld: this rung is not separated from a time-shuffled archive, and not separated from the first rung once both are measured on the same population"**. Not a number |
| **S3, GEO** | the single member, the propagated stop and its window, and the same withholding sentence. Not a number |
| **any stage, LEO** | the in-plane count and *cross-plane reach is not computed* — **and nothing else: the layer is withheld at this regime because the eventual partner is outside the set in more than half of the arrivals** |
| **everywhere** | both structural caveats, verbatim; at GEO the leak sentence; no borrowed precision; no arrival window beyond +10 days |

The change-ledger reading's R3 line therefore keeps its "no number until the
replay" form above S1 — but the reason has changed, and the page must say the
new one: not *unmeasured*, but *measured and withheld*.

---

## 9. Defects, deviations and blind spots

1. **The set-enlarging predicate degenerates on an empty set, and it is the
   reason the registered verdict and the operative one differ.** An empty set
   intersects nothing, so the registered predicate makes every later burn
   "set-enlarging" and reopens the episode. 16,812 of 24,111 episodes opened
   with an empty set, 21,835 closed as reopened, and **S2 is reachable only for
   an episode whose first burn reached at least one station** — a condition S1's
   own denominator does not carry. §3.4 makes the like-for-like comparison. The
   predicate is not changed here: it was registered, it is reported as it
   behaved, and a restatement — one that distinguishes "a larger set" from "a
   set where there was none" — is owed before any re-measurement.
2. **Three reporting changes were made after numbers existed, and none touches
   a rule**: the label for a measured zero (it prints as a bound, not as
   `0.000%`); the per-rung leak ratio of §5.2; and the like-population table of
   §3.4, which is labelled POST-HOC, NOT REGISTERED wherever it appears. All
   three are arithmetic over counts the artifact already carried.
   A fourth change dropped four duplicated or working-state fields from the
   committed episode ledgers, which held the same member lists twice and made a
   ten-megabyte file of a five-thousand-row subset; the dropped names and the
   reason are in each ledger's own provenance row.
3. **LEO S3 is expressed in semi-major-axis offset, not in phase** — declared in
   the registration §9.1 before any number, because this arm's element extract
   carries no along-track phase.
4. **LEO staleness rule**: an element set older than 5 days is not treated as a
   current state when the plane set is built. That is an implementation choice,
   not a registered threshold, and it is stated here rather than buried.
5. **The replay is IN SAMPLE for the GEO taxonomy.** The frozen partition was
   fitted on the whole 1959–2026 primary arm, which contains this window.
6. **Recall of the initiating flag is UNMEASURED**, in those words.
7. **Control (b) is not discharged** (§5.3).
8. **Control (a) does not exist at GEO** and is circular at LEO (§5.1).
9. **The event-driven pass** of the registration §9.8 was used: work is done
   only at epochs where the mover's newest element set has advanced, and every
   announce is snapped to the tick grid. Its equivalence to a full tick loop is
   asserted on a fixture by the suite, and the measured announcement lag
   (median 0.376 d against the lane's 0.378 d) is the second check.
10. **Two registered output paths were consolidated, and the difference is
    named here rather than left for a reader to find.** The registration §8
    listed `docs/m3-ladder-operating-points-20260923.json` and a single
    `docs/m3-ladder-episodes-20260923.jsonl`. The stage rows are instead inside
    `docs/m3-ladder-20260923.json` under `arms.GEO.operatingPointRows` — the
    same rows, in one artifact rather than two — and the episode ledger is
    written per regime, `…-episodes-geo-…` and `…-episodes-leo-…`, because the
    two regimes carry different fields and one file would have had to hold
    both. No content promised by the registration is missing.
11. **Nothing is scheduled.** No timer and no cron entry exists. The replay was
    run to completion in the session that registered it, with an injected clock,
    and the wall clocks reported are the ones actually observed.

---

## 10. Reproduction

```
python3 tools/ladder_replay.py --arms geo,leo --out docs --date 20260923
python3 -m unittest tests.test_ladder_replay      # 41, no archive, no network
```

---

## 11. Sources

```
docs/m3-ladder-replay-preregistration-20260923.md   the registration, bb0eb17
docs/kinematic-reach-design-20260922.md             sections 2, 3, 4, 7, 9
docs/kinematic-inputs-results-20260922.md           the 20 d and 10 d horizons
docs/alarm-lane-build-20260922.md                   sections 3, 5, 6, 7
docs/alarm-lane-model-20260922.json                 the frozen taxonomy
docs/alarm-lane-operating-points-20260922.json      the four named settings
docs/alarm-lane-leo-replay-20260922-receipt.json    the other regime's lane
docs/geo-libration-epoch-control-results-20260922.md the leak, 0.288
docs/proximity-results-20260922.md  proximity-leo-results-20260922.md
docs/manoeuvre-library-results-v2-20260922.md       the routine types
tools/ladder_replay.py  alarm_lane.py  trigger_alarm.py  proximity_plane.py
```
