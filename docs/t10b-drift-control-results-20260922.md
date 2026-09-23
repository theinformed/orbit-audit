# The properly-posed drift-direction control for T10b — measured

**Registration:** `docs/t10b-drift-control-preregistration-20260922.md`,
committed alone at `2da0784` before any number below existed.
**Parent:** `docs/stationkeeping-efficiency-preregistration-20260922.md`
(`f0f2b41`), results `docs/stationkeeping-efficiency-results-20260922.md`.
**Instrument:** `tools/t10_followup_drift_control.py` (`2e55e18`), 39 offline
proofs in `tests/test_orbit_t10b_drift_control.py`.
**Artifacts:** `docs/t10b-drift-control-20260922.jsonl`,
`docs/t10b-drift-control-20260922-receipt.json`.
**Compute:** CPU only, 73.3 s wall / 57.0 s CPU / 473 MB peak RSS on `pc`. No
GPU arm, so no `gpu-consumers.json` row is owed.

---

## The verdict, stated first

The operator's question was **"how sure are you that 22 degrees off the node is
inefficiency?"** The registered control returns **outcome C — PARTIAL**, and
the registered sentence for that outcome is:

> **Partly explained.** The explained fraction is `1 - m_H2 / m_raw` and is
> **0.494**. No claim either way.

Three things follow, and the third was not expected.

**1. Half of the off-node placement IS drift management, and it is measured, not
argued.** The drift-cancellation hypothesis H2 — that a burn closing a
station-keeping cycle must be antiparallel to that object's own natural
inclination-vector drift — predicts each event's signed node departure with no
free parameter. Its through-origin Theil–Sen slope is **0.829, bootstrap 95%
interval [0.571, 1.008] over 62 objects**: it **contains 1 and excludes 0**. The
signs agree on **72.5%** of 695 events against 50% by chance, Pearson `r = 0.417`,
and the residual median falls from **21.92 deg to 11.09 deg**.

**2. It is half, not all, and the registration's threshold is what decides
that.** Outcome A — "inefficiency falsified" — required the residual median to
fall to **at most 0.5 × 21.92 = 10.96 deg**. It fell to **11.09 deg**. The
control misses the registered bar by **0.13 degrees**, and the bar was written
down before the number existed. **The verdict is C and it is reported as C.**
Rounding 11.09 down to "about half, so call it explained" is exactly the move
registration exists to prevent.

**3. The one thing T10b CLAIMED is WITHDRAWN.** The bus-family ordering —
BSS-702 0.955 / 13.9 deg monotone through Eurostar-3000 0.861 / 32.3 deg — does
not survive its own null. Permuting the family labels across objects 10,000
times produces a spread at least as large as the observed **0.0835** in
**31.6%** of permutations. The registered decision at `p >= 0.05` is
**WITHDRAWN**, in that word, and this document applies it.

**What T10b may say after this control**, replacing what its results document
says now:

| | Before | After |
| --- | --- | --- |
| Median 21.9 deg off-node | reported, not claimed | **reported, not claimed** (unchanged; outcome C) |
| ~half of it | — | **explained by inclination-vector drift management** (slope interval contains 1, excludes 0) |
| Bus-family ordering | **CLAIMED** | **WITHDRAWN** (p = 0.32) |
| "the instrument invents the structure" | untested | **ruled out** (passive null, §3) |
| "the drift model's known rate error carries it" | untested | **ruled out** (bound, §4) |

---

## 1. What the control does that the registered one could not

The parent's §3.3 control compared a **pooled** quiet-arc heading against a
**constant 270 deg**. Three things were wrong with it and the defect-fix commit
`a111504` named all three: 270 deg is the prediction only at zero inclination;
it is the prediction only in the **prograde** sense that `a111504` retired; and
it was posed on a population every member of which is actively cancelling the
drift being looked for.

This control is per event, at each object's own pole, under the measured
retrograde circuit, and it needs one quantity the parent estimator discards.

**The sign.** The parent's eq. (8) inverts `cos u`, so `arccos` returns
`[0, 180]` and a burn 22 degrees early is indistinguishable from one 22 degrees
late. **Sloppy timing is symmetric. Every objective other than pure inclination
removal predicts a direction.** The median of `|u_eff|` therefore cannot
separate the hypotheses at all, and no amount of re-running it would.

The signed form and the published magnitude are the same quantity: the worst
disagreement over all 695 events is **1.90e-5 deg**, and every one is inside the
derived `arccos` conditioning bound of the parent's own eq. (8) (§5.2). The
measured median node offset here is **21.9216058533 deg** against the parent's
published **21.9216058256 deg**.

---

## 2. The three hypotheses, and which one the data picks

Each is an objective, derived to a placement prediction, in registration §3.

| | Objective | Prediction for the signed node departure | Slope, 95% CI | Sign agreement |
| --- | --- | --- | ---: | ---: |
| **H1** | remove inclination magnitude at least cost | `delta = 0` for every event | — (this is the null the median measures) | — |
| **H2** | cancel the cycle's natural drift | `delta = fold(psi)` | **0.829 [0.571, 1.008]** | **72.5%** |
| **H2b** | one-cycle-optimal diameter targeting | `delta = fold(psi/2)` | **−0.085 [−0.306, 0.441]** | 47.9% |

`psi` is the argument of latitude at which a burn would push the pole the way
that object's own natural drift pushes it — a per-event quantity fixed by the
object's own inclination and node and by a circuit measured on 33 **different**
objects in `a111504`. Nothing in it is fitted.

**H2b is dead.** Its slope interval contains 0 and excludes 1, its sign
agreement is exactly chance, and its residual median (29.32 deg) is **worse**
than no model at all (21.92 deg). The textbook diameter strategy — place the
post-burn inclination vector at the upstream end of a diameter of the deadband
circle — is not what this population flies, and that is a measurement.

**H2 is half the story.** Its residual median is 11.09 deg against a raw 21.92,
so it removes 49.4% of the departure, and its slope is statistically
indistinguishable from the 1.0 the derivation predicts.

**The magnitude pre-check C0 passes**, which is what makes the question
decidable at all: the largest median departure drift management could produce is
`median |fold(psi)| = 27.57 deg`, comfortably above the `0.5 × 21.9 = 11.0 deg`
the registration required. Had it come out below 11 deg, drift management would
have been ruled out on magnitude alone whatever the slope said.

**Sensitivity, registered in §5.1.** Restricted to the 426 events on 53 objects
with `|psi| <= 90 deg`, where the two foldings cannot disagree about which node
is nearer: H2 slope **0.720 [0.204, 1.134]**, H2b **1.440 [0.409, 2.267]**,
raw median departure 17.73 deg, H2 residual 11.71 deg. H2b's interval moves
onto 1 in this subset, but its residual median (14.36 deg) still fails the 50%
bar and its ceiling (9.01 deg) fails C0 — so the subset changes no verdict, and
it is reported because it was registered, not because it helps.

### What this means in plain terms

Roughly half of the 22 degrees is a satellite pushing its inclination vector
back **upstream against its own drift**, which is what a station-keeping cycle
requires and is not waste. The other half is not explained by any objective
registered here. **Neither half licenses the word "inefficiency" on its own**,
and the parent's §7 limitation stands unchanged: this instrument measures a
magnitude where the operator's target is a vector.

---

## 3. The passive-object null — the instrument does NOT invent a node angle

T3's own roster, reused verbatim: **331 GEO objects of class `passive`**, none
of which carries a single detected event in T2's set (the registered S3
cross-check passed with zero contamination). **117** of them have archived GEO
pairs inside the parent's screens, giving **16,662 pseudo-events** treated
exactly as manoeuvres: the same natural-motion subtraction, the same N5 span,
the same N6 noise screen at the parent's measured `sigma_pole = 0.000968 deg`.

| | Kept population | Passive null |
| --- | ---: | ---: |
| Events | 695 | 16,662 |
| Objects | 62 | 117 |
| Axial concentration `R_2` | 0.454 | **0.101** |
| Mean axial direction | **8.08 deg** | **85.66 deg** |
| Median \|node departure\| | 21.92 deg | **51.08 deg** (uniform predicts 45) |
| Fraction beyond 45 deg | — | 55.7% |

The passive null **is** concentrated (`p = 2.8e-74`) — it is not uniform, and
the registration said uniformity was the prediction. But its axis sits at
**85.7 degrees**, which is **77.6 degrees away** from the kept population's
8.1 degrees, far outside the registered 20-degree artefact tolerance. So
outcome E does not fire, and the reading the registration fixed in advance for
this case applies:

> `R_2` significant with a direction **unlike** the kept population's → a
> drift-model residual of measured size; its size bounds how much of 21.9 deg it
> can carry.

**The direction is the finding.** When this estimator is given an object with no
control loop, it does not report a burn near the node — it reports one near the
**quarter-orbit point**, the placement that swings the node and changes the
inclination magnitude only at second order. That is the signature of a residual
in the *node* channel, and it is the opposite of where the kept population sits.
**Whatever the instrument invents, it is not near-node structure.** The 21.9 deg
is not an artefact of the estimator.

The passive arm's own inclinations are reported beside it because the arm is not
inclination-matched to the kept population and cannot be: passive GEO objects
have drifted, with quartiles **1.08 / 3.53 / 8.33 deg** against a kept-population
median of 0.053 deg. The arm bounds the instrument's tendency to invent a
preferred angle; it does not measure the exact bias at 0.05 deg, and the
registration said so before the run.

---

## 4. The drift-model residual bound — derived, and small

Registration eq. (11) bounds how far a **known** drift-rate error can rotate the
inferred burn displacement: `arcsin(d_rate x dt / |dP|)`, evaluated with
`d_rate = 0.8748 - 0.7373 = 0.1375 deg/yr`, the gap between the model's pole
speed and the one `a111504` measured on 33 free-drifting objects.

Over the 695 events: median **0.154 deg**, p90 **0.229 deg**, maximum
**0.269 deg**.

**The known imperfection of the drift model can account for at most about 0.7%
of the 21.9-degree median.** The reason is the cadence, not luck: these
intervals have a median span of half a day, over which a 0.14 deg/yr rate error
accumulates 2e-4 deg against a median pole displacement two orders larger. This
number is reported and subtracted from nothing.

---

## 5. Two registered checks that fired, and what they caught

### 5.1 The registration's own identity D1 is wrong, and the test suite found it before any data was read

Registration §2.1 asserts that in the flat chart `P = (p_x, p_y)` the pole
displacement makes a signed angle of **exactly** `u` with the inclination
vector. It does not. A plane change at argument of latitude `u` pushes the pole
along `-t_hat(u) = sin(u) n_hat - cos(u) m_hat`, and the flat chart shortens the
`m_hat` component by `cos i`, so the angle it returns is

    u_flat = u + (1 - cos i) sin(u) cos(u) + O((1 - cos i)^2),

exact only as `i -> 0`: **0.0044 deg at 1 deg of inclination, 0.435 deg at
10 deg, 2.68 deg at 25 deg** (asserted in the test suite against the closed
form to 0.1% relative).

The exact form is eq. (E1), `u = atan2(w . n_hat, -(w . m_hat))` in the tangent
frame at the pole, and it is exact for a **finite** rotation as well as an
infinitesimal one: a rotation about `r_hat(u)` carries the pole along a great
circle lying in the plane spanned by `p` and `-t_hat(u)`, so the chord lies in
that plane too and its tangential part is exactly parallel to `-t_hat(u)`.
Verified to **1.3e-9 deg** over inclinations to 25 deg, rotations to 0.1 deg,
every `u`, both senses. (E1) is the primary here; the registered flat chart is
computed for every event and published beside it, under the registration's own
§6.3 D1 rule — a defect is reported with its size, both forms are published, and
the registration is not edited.

**Measured size on this population: median 5.4e-6 deg, p90 2.5e-5 deg, maximum
0.071 deg**, and the flat-chart median node offset is **21.92161 deg** against
the exact **21.92161 deg**. The defect changes nothing here, because this
population's median inclination is 0.053 deg. **It is reported anyway**, because
"it did not matter this time" is a measurement and not a reason to leave a wrong
identity in a registration.

### 5.2 The parent's eq. (8) is the imprecise one, near the nodes, where this population lives

Registered stop rule S2 demanded that the signed magnitude agree with the
published `nodeOffsetDeg` within **1e-6 deg**. It does not: the worst
disagreement is **1.90e-5 deg**. The cause is not algebra. The parent's eq. (8)
forms `cos u` and takes an `arccos`, whose conditioning collapses as
`cos u -> +/-1` — at the nodes. The numerator is a difference of quantities of
order 1, so its absolute rounding is amplified by `1 / (sin theta sin i)`, and
near a node the angular error goes as the square root of that. The derived
bound,

    du <= degrees( sqrt( 8 eps / (sin theta sin i) ) ),

is computed per event, and **all 695 disagreements lie inside it**. S2 is
therefore DISCHARGED under §6.3 D1 rather than passed: the tolerance was
unachievable for a reason the registration did not anticipate, the run still
stops on any disagreement **outside** the derived bound, and none occurred.

### 5.3 The model-discrimination check FAILED as registered, and the reason is instructive

Registration §5.4 required the passive null's residual under the retired
**prograde** model to be at least **1.5x** larger than under the corrected
retrograde one, else "this control has no power to distinguish drift models and
says so, in those words".

**It says so: the registered ratio is 0.680, and the check FAILS.** Outcomes A
and B are withheld on that ground as well as on §5.2's.

The diagnosis, reported because it is a finding about the check and not about
the physics: **the registered statistic is conditioned on a threshold.** It is
the median plane rotation of the pseudo-events that **survive** screen N6, and a
worse model pushes far more arcs over that screen, diluting the survivors with
marginal ones. The unconditioned evidence points the other way and points hard:

| Drift model | Pseudo-events clearing N6 | Objects | Axial `R_2` | Mean axis |
| --- | ---: | ---: | ---: | ---: |
| M-model (retrograde, 53 yr, 7.4 deg) | **16,662** | 117 | 0.101 | 85.7 deg |
| M-measured (retrograde, 56.2 yr, 6.75 deg) | 17,135 | 117 | 0.064 | 86.4 deg |
| M-prograde (the retired sense) | **382,675** | 154 | 0.208 | 107.2 deg |

The wrong sense leaves **23.0 times** as many quiet arcs looking like
manoeuvres. That is the same evidence `a111504` found when the measured
pole-noise floor fell 2.3x on correcting the sense, and it is a stronger form of
it. The control discriminates powerfully; the registered **statistic** did not.
A follow-up registration owes the corrected statistic — the survival count, or
an unconditioned residual — and this document does not substitute one after the
fact.

---

## 6. The bus-family-blind arm — the ordering is withdrawn

T10b's results document claims the family ordering and calls it "ordered and
monotone in node offset". With five families over 62 labelled objects, that had
never been tested against a null.

**Registered permutation null**, labels shuffled across objects at object level,
`B = 10000`, seed `20260922`, families re-formed under the parent's own
`>= 5 objects` rule, statistics computed by code that receives the labels as an
opaque list and never reads the strings:

| Statistic | Observed | Permutation p |
| --- | ---: | ---: |
| **F1** spread of family median `eta` (max − min) | 0.0835 | **0.3158** |
| **F2** Spearman(family median `eta`, family median departure) | −0.600 | 0.5118 |

The permuted spread has median **0.0691** and p75 **0.0906**: the observed
spread sits inside the bulk of what label-shuffling produces. The registered
decision at `p(F1) >= 0.05` is **WITHDRAWN**, and it is applied here.

**This is a correction to a published claim of the parent track, and it is the
most consequential line in this document.** The families in this arm are
A2100 (8 objects), BSS-702 (5), Eurostar-3000 (16), Spacebus-4000 (9),
SSL-1300 (12) — the object counts differ slightly from the parent's table
(BSS-702 7, SSL-1300 14) because this arm requires an object to carry both an
`eta` and a defined node departure, and that difference is reported rather than
reconciled away.

What survives is what the parent's own text already said and did not claim:
burn placement varies by more than a factor of two **between objects**
(Rascom-QAF 1R at 3.1 deg, Astra 2E at 67.4 deg), and it is visible from
outside. What does not survive is that the variation lines up with the bus.

---

## 7. Census, provenance, and what the numbers rest on

* **Kept arm**: the committed `docs/stationkeeping-ns-20260922.jsonl`, whose
  `_provenance.sourceSha256` is asserted equal to the committed
  `c5d0b970...94cad4` before anything is read. 695 informative events carrying a
  node offset, on 62 objects — exactly the 695 values on 62 groups the parent's
  `nodeOffsetBootstrap` was computed from. Nothing is re-detected and no screen
  is re-evaluated.
* **Passive arm**: T3's committed `docs/cadence-results-20260921.jsonl` for the
  roster, and the hash-pinned archive for the element sets. The roster is 331
  objects, the number that file carries, and the run asserts it.
* **Inputs**: archive `ffc4c4e5...5b734c3`, event set `6804c147...49e66f`,
  catalogue `7f7a50bc...cc72711a9` — the parent's three, verified at run time.
* **Policy**: the passive arm reads catalogue-external objects, and for those
  objects it computes **angles and counts only**. A test asserts that no key any
  passive row carries can name a delta-v, a propellant mass or a fuel quantity.
  The commercial-civil-only policy of `data/propulsion-catalog-v1.json` is a
  stop rule and remains one.
* **Runtime tripwires**, in the receipt: exact `u` at `u = 30 deg` returns
  30.000000 at both 0.05 and 10 deg of inclination; the flat chart returns
  30.000016 and 30.382588; the retrograde circuit heads toward RAAN 90.000000
  and the prograde one toward 270.000000; the pole speed at zero inclination is
  0.874838 deg/yr.

---

## 8. What is owed after this

1. **The corrected model-discrimination statistic** (§5.3). The registered one
   is threshold-conditioned; the replacement is a survival count or an
   unconditioned residual, and it needs its own registration rather than a
   post-hoc substitution.
2. **The last 11 degrees.** Half the departure is unexplained by H1, H2 or H2b.
   Candidates named and not tested here: north-south keeping flown as a **pair**
   of burns a half-cycle apart, whose *sum* is antiparallel to the drift while
   neither member need be (registration §7 names this as the reason outcome C
   exists); the unmodelled periodic lunisolar terms, which the parent's §2.3(c)
   names as its largest unmodelled term at `1e-2` to `6e-2 deg`, comparable to a
   tight north-south deadband; and combined north-south/east-west manoeuvres.
3. **The inclination-VECTOR estimand**, still owed from the parent's own OWED
   list. This control measures the *direction* of the vector change and finds
   half of it predicted; it does not replace an estimator whose target is the
   vector.
4. **Nothing in this document licenses "wasted propellant".** It never could:
   no instrument built on element sets can see operator intent.

---

## 9. Blind spots, unchanged from the registration

* One burn per cycle is H2's assumption; a burn **pair** makes H2 a statement
  about the sum, and applied per event it is an approximation. Named in
  advance, not corrected, and it is the leading candidate for §8 item 2.
* `psi` uses the population drift model, not each object's own Laplace geometry.
  The three models bracket the spread `a111504` measured; they do not eliminate
  it, and the M-measured arm is published for exactly that reason.
* The passive roster is not inclination-matched to the kept population, and its
  own inclination quartiles are published beside its result.
* A small permutation `p` would have said the family spread is larger than
  shuffling produces. It is not small, so nothing about buses is said at all —
  in particular, this document does **not** say the families are the same.
  It says the data cannot tell them apart.
