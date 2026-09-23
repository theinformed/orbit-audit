# The behavioural alarm lane: BUILT, EXERCISED, NOT SCHEDULED

> **STATUS: BUILT AND EXERCISED. NOTHING IS SCHEDULED, NOTHING IS DEPLOYED,
> NOTHING IS ON ANY SITE SURFACE.** No timer and no cron entry exists. No
> alert has left this machine. Nothing here is written to `src/`, `data/` or
> `public/`. The design's own rule stands: **nothing is scheduled until the
> replay has run and the operator has decided.** The replay has now run. The
> decision has not been asked for and nothing in this document implies one.
>
> Six of the design's seven reserved decisions (§10) **remain reserved and
> untaken**. The seventh — §10.6, whether the LEO arm is built — was
> **answered by the operator: it is live**, and this document records the
> answer rather than assuming it.

This discharges items **3, 4, 5 and 6** of the design's §11 build order, plus
the operator's two scope additions: an **operating-point curve** rather than a
single threshold, and a **live LEO arm**.

| §11 item | state |
|---|---|
| 1. a registration for the trigger-time taxonomy | DONE (T8d, `154c53f`) |
| 2. per-class precision | DONE (T8d) |
| **3. a frozen-artifact format, versioned** | **DONE** |
| **4. the sidecar, with the vocabulary gate as a function** | **DONE** |
| **5. the alert ledger's own audit** | **DONE** |
| **6. a synthetic exercise before anything is scheduled** | **DONE** |
| + operating-point curve (operator, 2026-09-22) | **DONE** |
| + live LEO arm (operator, 2026-09-22) | **DONE** |

Built 2026-09-22 on `pc`, **CPU only — no GPU was taken, so no
`gpu-consumers.json` row is owed.**

---

## 1. What was built

| file | what it is |
|---|---|
| `docs/alarm-lane-model-20260922.json` | the GEO arm's **frozen artifact** — taxonomy, scaler constants, outcome tables, versioned and checksummed |
| `docs/alarm-lane-operating-points-20260922.json` | the **operating-point curve** — 108 measured rows over a registered grid, four named settings |
| `docs/alarm-lane-leo-model-20260922.json` | the **LEO arm's** frozen artifact, in the same shape so the ledger contract is identical |
| `tools/alarm_lane.py` | the read-only **sidecar**: clock, element sources, state file, ledger, the §6 **vocabulary gate as a function that returns the permitted words**, the renderer, the resolver and the **ledger's own audit** |
| `tools/alarm_lane_curve.py` | the registered grid and the curve builder (committed **alone**, before the table existed) |
| `tools/alarm_lane_replay.py` | the GEO **synthetic exercise** — injected clock, N operating points end to end |
| `tools/alarm_lane_leo.py` | the LEO arm: its trigger, its frozen table, its operating points, its replay and its control |
| `tests/test_alarm_lane.py` | the offline proofs, including the framing guards |

Nothing else was touched. `pipeline/`, `src/`, `data/` and `public/` are
untouched by construction and by test.

---

## 2. The frozen artifact (§11.3)

**Version `trigger-time-taxonomy/20260922/1`, checksum
`9cf012aab4e2501117c8a50c13c26b263b3ab7500eb8e80149319e67c66a0a13`.**

The checksum is a sha256 over a canonical serialisation (sorted keys, no
whitespace, no NaN) of everything in the file except the checksum itself, so a
reader recomputes it from the file alone and a single flipped digit in a
precision figure is refused at load time. A test flips one and asserts the
refusal; another flips a centroid coordinate by `1e-9` and asserts the same.

**What it freezes**, and why each part has to be in it:

- the **22 feature names** in registration order and the log-transform subset;
- the **scaler constants** — 22 medians, 22 means, 22 standard deviations and
  the keep mask — because the assignment is a distance in a standardised space
  and a lane that re-derived them would move every boundary;
- the **two centroids** in that space;
- both **classes** with `n`, positives, precision, Wilson interval, bootstrap
  Jaccard and the full arrival-time distribution;
- the **whole-population base rate**, 101 of 97,784, which every alert must
  print beside its class figure;
- the **detector constants** — σ_n, the threshold, the merge and confirm
  windows, the horizon, the eligibility floor, the resonance constants — read
  from the T8d instrument rather than retyped, and asserted equal to it by
  test;
- `earnedBy`: the sha256 of the registration, the results document, the
  receipt, the instrument and the event record. **A test re-hashes all four
  and fails if any has changed since the freeze.**

**The freeze refuses to write a model that did not earn the published
figures.** It re-fits the partition from the measured trigger table and
requires the sizes to reproduce **exactly** — `[96962, 822]` against the
receipt's `[96962, 822]` — and every class's positives to match (73 and 28).
Then it asserts that the frozen constants reproduce their own labels, writes
the file, reloads it, and re-classifies 5,000 rows through the *written*
artifact to prove the round trip. Any disagreement is a `SystemExit`, not a
warning.

---

## 3. The sidecar (§11.4)

**Read-only by construction.** Every handle is `mode=ro` plus
`PRAGMA query_only = 1`; a test asserts it on both element sources. There is
no write path into `orbit-release`, the shards or the publish gate, and no
code path anywhere in the lane that sends anything to anything — a test bans
`smtplib`, `urllib.request`, `requests`, sockets, webhooks and bare URLs from
all four tools.

**Where it attaches.** The design chose a separate timer reading `element_set`
directly. `element_set`'s `PRIMARY KEY (norad, epoch_ms) WITHOUT ROWID` makes
the table its own index, so a per-object history is one indexed read — a
measured **3 ms** for a 804-element history.

**Cadence is derived, not chosen.** `derive_cadence()` takes the median
element-set spacing, the number of confirming element sets the detector's own
rule requires, the median causal lead and the host timer's period, and returns
the arithmetic:

- the confirmation rule needs 2 consecutive element sets, so a confirmable
  change becomes visible about **2 × spacing** after it happens;
- re-reading more often than one median spacing re-reads element sets that
  have not changed, so the **work floor is one median spacing**;
- against the median causal lead, that latency is a stated percentage of the
  warning budget, and the host timer's own period is a smaller percentage that
  **buys nothing**.

The **measured** spacing on the near-GEO watch is **0.7564 d** — not the
0.865 d the design cites — and the lane uses what it measured, records both in
the state file, and cites the design for the comparison. `--cadence-hours`
overrides it and the override is recorded as an override. Tests change the
inputs and assert the outputs move, and assert that no period is hard-coded in
the sidecar.

**The work gate is the design's own rule**: do work only when the object's
newest element-set epoch has advanced. One correction was found while building
it — the gate must not also defer the *announcement* of a chain already
detected, because a chain becomes announceable five days after it closes and
making that wait on the object's next element set charges the cadence for
latency it does not cause. Before the fix the median announcement lag was
1.06 d with a p95 of 3.71 d; after it, **0.378 d with a p95 of 0.718 d**,
bounded by the tick as it should be.

**The vocabulary gate returns the words.** `permitted_vocabulary()` returns
the permitted clause ids, **the literal phrases they license**, the withheld
clauses each with its reason, the never-say list, the labels the output must
carry, and the figures the alert may quote. The renderer may use nothing the
gate did not return.

`class_may_be_spoken()` is an **arithmetic rule, not a stored verdict**. A
class may speak when it is a reproducible cluster (bootstrap Jaccard at or
above the registered 0.5 bar), when the numbers being quoted rest on at least
20 supporting events, and when the precision is **separated above the base
rate of the same population** — its Wilson lower bound above the base
population's Wilson upper bound. On today's numbers:

| class | figure | verdict |
|---|---|---|
| WIDE-CROSSING | 3.406% [2.367, 4.879] vs base 0.103% [0.085, 0.126] | **PERMITTED** |
| RESIDUAL | 0.075% [0.060, 0.095] vs the same base | **WITHHELD**, and the reason is returned with it |

The withheld class is not withheld for want of a measurement — it has 96,962
supporting events and a measured rate. It is withheld because that rate
straddles the base rate, and an alert that fires on 99.2% of all confirmed
drift changes and is right about once in 1,300 is not a warning.

**Standing withholds**, returned on every assessment: the object's own history
(gate H fired), the word the shipped detector has not earned, "approach" for
an individual alert, any point forecast, and any borrowed precision. A test
asserts that no rendered alert at any setting contains the borrowed figures.

---

## 4. The ledger and its own audit (§11.5)

The ledger is append-only JSONL with a provenance first line carrying both
structural caveats, the never-say list and the reserved decisions. Every
assessment is written, including the ones that did not pan out and the ones
the gate refused — §7.9 forbids silent suppression, and a setting that waits
also records what it **withdrew**.

`audit_ledger()` computes the running precision **on this lane**: per class,
assessed / spoken / resolved / arrivals / misses / not-assessable / pending /
withdrawn / below-this-setting's-evidence, the Wilson interval, and the lead
distribution measured here. The frozen figure is printed **beside** it,
labelled as the figure the model earned elsewhere, never in place of it.

The doctrine holds at every step:

- **a labelled gap is never a zero** — nothing resolved yet prints
  `NOT ASSESSABLE … a labelled gap, not a zero`, and a test asserts the string
  `0.000%` does not appear;
- **under 20 resolutions is UNDERPOWERED** and no rate is drawn from it;
- **an outcome record that ends before an alert's horizon closes** resolves to
  `not-assessable`, not to a miss;
- **an arrival before the announce warned nobody** and is counted as a miss
  with the reason recorded;
- **both structural caveats are printed on every output** — every rendered
  alert, every labelled gap, every audit report. Tests assert it on all three.
---

## 5. The operating-point curve (operator addition)

**`docs/alarm-lane-operating-points-20260922.json`, version
`operating-points/20260922/1`, checksummed and naming the frozen model that
earned it.** Loading it against a different model is refused.

The grid was **committed alone, before the table existed** (`13e80ed`). Four
evidence axes, none of which reads an outcome:

| axis | values | what it is |
|---|---|---|
| `minDriftChangeDegPerDay` | 0.010, 0.10, 1.0 | the size of the confirmed drift-rate change; 0.010 is the detector's own floor |
| `minSlotsReached` | 0, 5, 20 | the **reachable-set size**: occupied mean longitudes the propagated 180-day trajectory would pass within 0.1° of |
| `persistenceSweeps` | 1, 2, 3 | consecutive firings that must still see the object drifting. N > 1 **delays the announcement** by N − 1 firings |
| `leadHorizonDays` | 90, 180 | the window in which an arrival counts; it may not exceed the 180 days the outcome record's attribution window allows |

54 points × 2 classes = **108 rows**, each with alerts, arrivals, precision
with its Wilson interval, the lead distribution, alerts per year (archive mean
and a real 2010s count), the supporting-event count with the UNDERPOWERED
label below 20, the gate's verdict at that setting, and a recall **proxy**.

**Recall is not measurable and the artifact says so in those words.** The
outcome record is a lower bound, a transfer below the detector's floor is
invisible, and a third of the catalogued events carry no confirmable
initiating change. `recallProxy` is one row of the table divided by another —
this setting's arrivals over the loosest setting's at the same horizon — and
it is not the fraction of real approaches caught.

### 5.1 The four named settings, each with its own measured numbers

| setting | evidence | class | alerts (archive) | /yr in 2010s | precision | median warning | speakable |
|---|---|---|---:|---:|---|---:|:--:|
| **everything** | 0.010, 0 slots, 1 sweep, 180 d | WIDE-CROSSING | 821 | 27.7 | **3.410%** [2.370, 4.885] | 22.1 d | yes |
| | | RESIDUAL | 95,425 | 3,292.3 | 0.076% [0.061, 0.096] | 29.4 d | **no** |
| **balanced** | 0.10, 5 slots, 1 sweep, 180 d | WIDE-CROSSING | 717 | 23.8 | 3.208% [2.147, 4.767] | 28.0 d | yes |
| | | RESIDUAL | 1,202 | 33.7 | **3.661%** [2.738, 4.878] | 31.3 d | **yes** |
| **high-confidence** | 1.0, 5 slots, 2 sweeps, 180 d | WIDE-CROSSING | 373 | 12.7 | 2.681% [1.463, 4.864] | 39.6 d | yes |
| | | RESIDUAL | 53 | 0.7 | 1.887% [0.334, 9.943] | 125.0 d | yes |
| **very-high** | 1.0, 20 slots, 3 sweeps, 180 d | WIDE-CROSSING | 367 | 12.5 | 2.725% [1.487, 4.942] | 38.9 d | yes |
| | | RESIDUAL | 46 | 0.7 | 2.174% [0.385, 11.335] | 124.2 d | yes |

### 5.2 Two findings the curve was built to make visible

**A tighter setting is NOT automatically a more precise one, and this table is
the evidence.** On the class that already speaks, the loosest setting reaches
**3.410%** and the tightest reaches **2.725%**. Tightening bought fewer alerts
— 821 down to 367 — and a different warning time. It did **not** buy a higher
hit rate, and every interval overlaps every other. The artifact carries a
`monotonicityNote` saying so, every description states the three measured
quantities instead of claiming confidence, and **a test refuses any output
string containing "more certain", "higher confidence", "more reliable",
"more accurate", "certainty" or their neighbours** — in the curve, in every
rendered alert at every setting, and in the LEO arm.

**The evidence thresholds carry information the partition does not.** The
class the gate withholds on its whole-population numbers — 0.075% over 96,962
triggers — reaches **3.661% [2.738, 4.878] over 1,202 triggers** once the
drift-size and reachable-set thresholds are applied, and **becomes speakable**
because its Wilson lower bound then clears the base rate's upper bound. The
gate is asked again at every setting, against the base rate at that setting's
horizon; it is never a stored verdict.

**One reconciliation, stated rather than smoothed over.** The loosest grid
point holds 96,246 triggers where the frozen artifact's primary arm holds
97,784, because the grid applies the 0.010 deg/day floor to the *chain's net*
drift change while the flag threshold applies it to each element set's
departure from its trailing baseline. **No positive is lost by the
difference** — both carry the same 101 — and the artifact records it.

---

## 6. THE SYNTHETIC EXERCISE (§11.6)

> **The estate rule is that a lane which would run later is exercised now.
> It has been.** No timer was installed. The job a timer would run was driven
> over ten years of history with an injected clock, at two operating points,
> end to end.

**The window rule, fixed before any number and outcome-blind:** the decade
with the most confirmed drift changes, which T8d §3.1 reports as the **2010s**
(71,661 of 226,422 flag chains). Chosen on **alert volume**, which says
nothing about what those alerts turned into.

**The tick is the derived cadence**, not a period anyone chose: the median
element-set spacing measured over all 1,652 watched objects' element sets,
**0.7564 d**. **4,828 ticks**, 2010-01-01 to 2020-01-01. The lane is
warm-started — every chain that closed before the window is treated as already
announced — and the state file records that.

### 6.1 Does the clock-driven sidecar reproduce the offline detector?

**Yes, exactly.**

| | |
|---|---:|
| offline primary-arm triggers the replay should have seen | **33,719** |
| live assessments | **33,599** |
| in both | **33,595** |
| **class disagreements** | **0** |
| only offline | 124 — **all 124 explained** by the design's own §5.3 labelled-gap rule, which the offline measurement does not apply (short look-back) |
| only live | 4 — **all 4 explained**: the offline table drops them as not resolvable, a property that needs 210 days of *future* element sets and that **no live lane can know** |
| **unexplained, either direction** | **0** |

### 6.2 The two settings, end to end

| | **everything** | **high-confidence** |
|---|---:|---:|
| assessments | 71,551 | 71,551 |
| labelled NOT ASSESSABLE (outside the measured population) | 37,952 | 37,952 |
| below this setting's evidence | 601 | 33,431 |
| **withdrawn** by the persistence check, recorded | 0 | **36** |
| **alerts spoken** | **272** | **132** |
| hits | 14 | 7 |
| **precision on this lane** | **5.147%** [3.090, 8.453] | **5.303%** [2.592, 10.542] |
| median warning, by the announce rule | **22.1 d** | **47.4 d** |
| median warning, from the tick it actually spoke | 21.7 d | 46.6 d |
| p25–p75 warning | 9.5 – 37.6 d | 28.5 – 69.0 d |

**Against the frozen figures**, printed beside and never instead:

| | frozen (whole archive) | curve (this setting) | **replay (2010s)** |
|---|---|---|---|
| WIDE-CROSSING precision | 3.406% [2.367, 4.879] | 3.410% [2.370, 4.885] | **5.147%** [3.090, 8.453] |
| WIDE-CROSSING median lead | 22.1 d | 22.1 d | **22.1 d** |
| RESIDUAL precision | 0.075% [0.060, 0.095] | 0.076% [0.061, 0.096] | 0.141% [0.106, 0.187] |
| alerts/yr, WIDE-CROSSING | ~12 (archive mean) | 27.7 (2010s) | **27.2** |

**The median lead reproduces to the decimal.** The precision runs high in the
2010s — 5.1% against 3.4% — with heavily overlapping intervals; the decade is
a denser slice of the archive than the archive's mean, which is also why the
alert rate is 27.2 a year against an archive mean of about twelve. T8d
pro-rated that rate at "of the order of 25–30 a year in the 2010s" and called
the pro-rating arithmetic rather than measurement. **The replay measured it:
27.2.**

### 6.3 What the second setting actually bought

**Half the alerts, at an indistinguishable hit rate, with roughly twice the
warning** — and the warning is longer because the persistence requirement
selects longer transfers, **not** because waiting produces warning. The delay
itself costs 0.76 d per sweep and is charged in the lag figures below.

| | everything | high-confidence |
|---|---:|---:|
| alerts | 272 | **132 (−51%)** |
| precision | 5.147% [3.090, 8.453] | 5.303% [2.592, 10.542] |
| median warning | 22.1 d | 47.4 d |

The intervals overlap almost completely. **On this evidence the tighter
setting did not buy measurable precision**, which is exactly what the curve
predicted and exactly what the lane's output strings are forbidden to
misdescribe.

### 6.4 The cadence's own cost, measured

| | median | p75 | p95 |
|---|---:|---:|---:|
| delay between the announce time the detector defines and the tick the lane actually spoke | **0.378 d** | 0.568 d | **0.718 d** |

Bounded by the 0.7564 d tick, as it must be. Against a 22.1-day median
warning that is **1.7%** of the budget.

### 6.5 The live path, exercised against the archive

The replay uses the cached extract, so the **live** path — one indexed read
per watched object against `element_set`, read-only — was exercised
separately, with an injected clock, on the real archive:

| | |
|---|---|
| two firings, 2026-09-01 and 2026-09-08 | 74 s and 61 s, 1,768 objects watched |
| assessments | 1,067 |
| **alerts raised** | **17**, each with the full template |
| measured element-set spacing on the live watch | **0.7721 d** — derived again, from that firing's own data |
| `resolve` | 552 resolutions appended |
| `audit` | every one **NOT ASSESSABLE**: the outcome record ends before a 2026 alert's 180-day horizon closes. **A labelled gap on live data, not a zero** |
| re-announcement on the second firing | **none** — the state file's per-object announce watermark held |

---

## 7. The LEO arm, live (operator decision on §10.6)

**`docs/alarm-lane-leo-model-20260922.json`**, the same artifact shape as the
GEO arm so the ledger contract is identical and one consumer reads both.

**The scope is on the face of every output**: *in-track phasing campaigns
between objects that already share an orbit* — what T8b's catalogue contains,
not a claim about the regime generally. The second channel is blinded until
its noise floor is re-derived, so this arm ships **no matching product against
it and uses none of its vocabulary in any printable string**; a test walks
every string literal in the tool and every human-readable field of the frozen
table.

**T8b's published figures are frozen as measured** — 161 alerts, 71 hits,
**44.1%** [36.7, 51.8], **195.9 d** median causal lead, and the
never-manoeuvred control at **0 events over 18.79M object-days** — and they
are **explicitly not this arm's precision**, because they were measured on
T8b's own alert channel, which is a different detector. Quoting them would be
the same error §7.10 forbids at GEO.

**The trigger** is a campaign-initiating confirmed **in-track** manoeuvre of a
payload-class object, decided by `proximity_plane.detect_manoeuvres` — T8b's
own arithmetic, reused. A campaign is a chain with no internal gap longer than
180 days, and the alert is its first flag.

### 7.1 The replay

Window **2020-01-01 → 2023-06-01** by a declared outcome-blind rule (the
earliest span of the decade holding the largest payload population for which
every alert's 1,095-day horizon still closes inside the outcome record).
**2,528 ticks at a derived 0.4935 d cadence** — measured on this regime's own
element sets, matching T8b's reported 0.53 d median spacing.

| | |
|---|---:|
| objects in the band | 26,190 (6,287 payload-class) |
| objects carrying a confirmed in-track flag | 15,683 |
| **alerts** | **5,327** (≈1,558 a year) |
| resolved | 5,327 |
| hits | 27 |
| **precision on this arm's own trigger** | **0.507%** [0.349, 0.736] |
| median warning | **684.4 d** (p25 447.0, p75 926.3, p95 1,035.7 — right-censored by the 1,095-day horizon) |

### 7.2 The two findings, and the gate's verdict

**1. The LEO trigger has the same enormous-denominator problem T8d found at
GEO.** Its own measured precision is **0.507%** against the published
**44.1%** — an eighty-seven-fold gap, for exactly the reason T8d gave: the
published figure's denominator is an alert channel defined by a different
detector, and a campaign-initiating in-track manoeuvre in the constellation
era is routine rather than rare. **The arm does not quote 44.1%.**

**2. The arm fails its own passive control, and that is what withholds its
clause.** Run over objects that *physically cannot manoeuvre*, the same
detector raised **13,443 alerts** — **0.797 of the per-object rate it raises
on objects that can**, against the shipped detector's design target of **one
in a thousand**. `pipeline/orbit_events.py` withholds its own label for a
control of 34 in 1,941; this is far worse, and the gate is held to the same
bar rather than a softer one.

**So the LEO arm ships LIVE and says nothing it has not earned.** The
sequence is the one the rest of this track uses: the arm was frozen at
version `/1` with **no** measured precision and the gate withheld for want of
one; the replay measured it; the arm was re-frozen at version `/2` carrying
its own numbers; and the replay was **re-run under `/2`**. Under its own
measured table the lane runs, classifies, ledgers and audits — and raises
**zero alerts**, because the gate withholds the pattern clause with a measured
reason printed:

> *its own passive control fires at 0.797 of the rate it fires on objects
> that can manoeuvre, against a design target of 0.001; the detector has not
> earned a clause about what its flag means.*

That is the design working, not the design failing. The audit under `/2`
reproduces the arm's own figures — 27/5,327 = 0.507%, median lead 684.4 d —
and prints them as the frozen figure beside the lane's own, which are the same
numbers because this arm has been measured exactly once.

### 7.3 The arm's own operating points

Nine settings, from T8b's own registered sensitivity arms, with T8b's own
numbers: event counts from 24 to 170, KM median leads from 4.4 d to 220.8 d,
and the never-manoeuvred control from 0 to 6. **Precision was measured for the
primary arm only**, so the other eight rows carry
`NOT ASSESSABLE … a labelled gap, not a zero` and a test asserts it. Each row
carries the same recall note: true recall is not measurable here either.

**One diagnostic worth recording.** An exact epoch match between this arm's
campaign starts and T8b's `campaignStartMs` returns **zero** matches, because
T8b estimated each object's noise floor over the whole archive and this arm
estimates it over the replay's own span; two slightly different thresholds put
the confirming element set in slightly different places. The campaign
**boundary** is the robust quantity, so the boundary is what is matched, the
exact-match count is reported rather than hidden, and the relaxation is stated
in the tool's own docstring.
---

## 8. The §10 decisions, and how this build leaves them open

Six remain reserved. The build does not pick a default for any of them; where
one would be needed, the lane refuses the behaviour instead.

| § | decision | how it is left open |
|---|---|---|
| 10.1 | publication surface | there is none. Nothing is written to `src/`, `data/` or `public/`; a test bans those paths from all four tools |
| 10.2 | framing | the lane emits facts and counts. Every description states measured quantities; a test refuses any output string that dresses a threshold up as certainty |
| 10.3 | whether registry codes ever appear | no detector, gate, feature, transform, distance, assignment or renderer reads one — a word-boundary test over every such function. The words appear only inside the never-say list, and a test asserts they appear nowhere else in the sidecar |
| 10.4 | whether object names appear | NORAD numbers only. No catalogue name column is read; the element query reads `element_set` and joins nothing |
| 10.5 | whether an alert ever leaves the machine | nothing sends. A test bans every transport in all four tools |
| 10.7 | ledger retention | nothing deletes. The ledger is append-only and no retention policy is implemented |

**§10.6 was answered.** The operator ruled the LEO arm live, and the LEO
frozen artifact records the answer explicitly: `leoArmIsBuilt` is removed from
its reserved set and the note says it was answered rather than assumed. A test
asserts that the other six are still present and still `null`.

The frozen artifacts, the state file, the ledger provenance and every audit
report all carry the reserved-decision block, so a reader of any single
artifact can see what has not been decided.

---

## 9. What is unexercised, in those words

Stated as the estate rule requires, naming exactly what is unproven.

1. **No timer or cron entry has been installed, and none has been exercised,
   because none exists.** The design says nothing is scheduled until the
   operator decides, and that is where this stops. What HAS been exercised is
   the job the timer would run, over a decade of history, at a derived
   cadence, with an injected clock.
2. **The archive-wide LEO measurement for this arm's own trigger has not been
   run.** The LEO precision figure in this document is measured over the
   declared replay window only. Running it over 1959–2026 needs a full LEO
   extract of the whole archive and was not attempted here.
3. **The plane channel of the LEO arm is unbuilt and stays unbuilt.** Its
   noise floor is still 145× too large, so there is no matching product
   against it and none of its vocabulary reaches any output string. Nothing
   here re-derives that floor.
4. **A live resolver has not been exercised past the end of the outcome
   record.** Resolution uses the committed event catalogues; for an alert
   whose horizon closes after those records end, the lane returns a labelled
   gap, which is exercised, but the arrival detector that would fill that gap
   for a genuinely live lane is T8a's and T8b's offline pass and has not been
   wired into the sidecar.
5. **The MEO and HEO regimes have no arm and none was built.** T8b measured
   MEO at 2 events (UNDERPOWERED) and HEO at zero, so no alert class exists
   for either.
6. **Nothing in this lane has been exercised against a concurrent writer.**
   The sidecar's state file and ledger are written by one process; two lanes
   running at once against the same state file have not been tested and the
   lane does not lock.
---

## 10. Tests

| suite | tests |
|---|---|
| `tests/test_proximity_geo.py` (T8a) | 35 |
| `tests/test_orbit_proximity_plane.py` (T8b) | 74 |
| `tests/test_alarm_pattern.py` (T8c) | 60 |
| `tests/test_trigger_alarm.py` (T8d) | 100 |
| **`tests/test_alarm_lane.py` (this build)** | **183** |
| **total across the five T8 suites** | **452** |

All offline: no archive, no network. The framing guards are the point of the
new file, and they are built the way T8a's were — **the banned vocabulary is
IMPORTED from T8c's suite, never copied**, so one canonical list cannot drift
out of step with itself.

What the guards assert, rather than intend:

- no purpose language anywhere in any of the four tools;
- **no registry code read by any detector, gate, feature, transform,
  distance, assignment, renderer or query** — word-boundary matched, because
  `inclination` is a physical quantity and not a registry code;
- those words appear **only** inside the never-say list, and a count asserts
  they appear nowhere else;
- no velocity-change, consumable, mass or remaining-life quantity is computed;
- no miss-distance, range or collision quantity is computed;
- **no borrowed precision in any rendered alert at any setting**;
- both structural caveats on every rendered alert, every labelled gap and
  every audit report;
- **no output string dresses a threshold up as certainty** — at any setting,
  in the curve, in the LEO arm;
- **no blinded-channel vocabulary in any printable string of the LEO arm** —
  the test walks every string literal in the tool;
- no timer, no cron entry, no transport, no published tree;
- every database handle read-only;
- the six remaining reserved decisions present and `null`.

Two guards found real defects while being written. The never-say list
contained the blinded channel's own word inside a GEO clause, which the LEO
arm then inherited — reworded. And the cadence gate was deferring
announcements it had no reason to defer, which the lag measurement caught.

---

## 11. Reproduction

```
# the frozen artifact, from the measured trigger table
python3 tools/alarm_lane.py freeze --work /home/sdegan/t8d-work --out docs

# the operating-point curve (the grid was committed alone, first)
python3 tools/alarm_lane_curve.py --work /home/sdegan/t8d-work --out docs

# the GEO synthetic exercise, two operating points end to end
python3 tools/alarm_lane_replay.py --work /home/sdegan/alarm-lane-work \
    --out docs --settings everything,high-confidence

# the LEO arm
python3 tools/alarm_lane_leo.py freeze --out docs
python3 tools/alarm_lane_leo.py replay --work /home/sdegan/alarm-lane-leo \
    --out docs
python3 tools/alarm_lane_leo.py freeze --out docs \
    --measured docs/alarm-lane-leo-replay-20260922-receipt.json

# one firing of the live path, against the archive, with an injected clock
python3 tools/alarm_lane.py run --source archive --now <iso> \
    --warm-start-at <iso> --state <path> --ledger <path>
python3 tools/alarm_lane.py resolve --ledger <path>
python3 tools/alarm_lane.py audit --ledger <path>

# the proofs
python3 -m unittest tests.test_alarm_lane        # 183, no archive, no network
```
