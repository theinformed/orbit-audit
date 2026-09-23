# T13 — the manoeuvre library v2: PRE-REGISTRATION

**Date:** 2026-09-22. **Status:** registration. Nothing in this document is a
measurement of v2. Every figure quoted below is either a constant already
registered by a committed track (with the file and symbol it lives in), a
quantity derived here by arithmetic on such constants and labelled *derived*,
or a v1 figure already published in a committed results document
(`docs/manoeuvre-library-results-20260922.md`, commit `77eee17`). The v2
measurement this document fixes — the arm-G type mix, the v2 UNLABELLED
fraction, the v2 agreement matrix — does not exist yet and is forbidden to
exist until this file is committed alone.

**Supersedes nothing.** v1 is retained, runnable, and its artifact
`docs/manoeuvre-library-v1-20260922.json` stands unamended. v2 is an additional
version of the same instrument, not a correction applied to v1's numbers.

**v1 registration:** `docs/manoeuvre-library-preregistration-20260922.md`
(commit `d86b93d`). **v1 results:** `docs/manoeuvre-library-results-20260922.md`
(commit `77eee17`). **v1 instrument + 90 offline proofs:** commit `343a112`.

---

## 1. The one change

**v2 changes exactly one thing about what a rule tests: the GEO arm's
inclination clause.**

v1's arm-G rules G1 (drift start), G4 (east-west keeping) and G5 (north-south
keeping) each test the RAW inclination difference across the burn against a
fixed bar of 5σ_i = 8.35e-4 °, where σ_i = 1.67e-4 ° is the archive's
inclination **fit scatter** at GEO and above (`docs/orbit-history-design.md` §2,
n = 450, already floored at the 1e-4 ° publication quantum).

v1 measured that this clause does not test what it was written to test. Over all
1,018,263 arm-G burns the median |Δi| is **0.01575 °**, which is **18.9×** the
8.35e-4 ° bar, over a measured median differencing span of **18.04 days**;
the repository's own registered bound on how far luni-solar gravity alone turns
a geostationary plane — `pipeline/orbit_events.py::lunisolar_inclination_bound_deg`,
(2π/53 yr) × (|i| + 7.44°) × span/365.25, evaluated at i = 0.05° over 18.04 d —
is **0.0438 °**, and the measured median is 36% of it. 906,864 of the 920,618
unlabelled arm-G burns (98.5%) fail for the single reason that both channels
moved. **At this sampling the clause tests how far apart in time two element
sets are, not whether a burn moved the plane.** All of that is v1's published
measurement, not a v2 number.

**The replacement.** v2's arm-G inclination clause is on the **net** inclination
change: the observed inclination across the burn minus a natural-motion
prediction over the same span, thresholded on a floor derived in §3 from the
uncertainty of that quantity.

    deltaIncNetDeg  =  i_observed(t_flag)  -  i_predicted(t_flag)

This is T10b's form, taken from a committed instrument rather than invented
here: `tools/stationkeeping_efficiency.py` carries `incPredictedDeg` — the
pre-burn pole carried forward by the natural motion alone — and reports
`deltaIncNetDeg = i_after − i_pred` with `naturalFraction` beside it, published
per event in `docs/stationkeeping-ns-20260922.jsonl`.

**A threshold is a screen, not a law.** The v2 floor is no more a physical
boundary between kinds of burn than v1's was. It is the point below which the
net change cannot be told from the uncertainty of the two things that make it.
A burn just above it and a burn just below it are one kind of thing observed on
two sides of an instrument limit. Every v2 figure is read subject to that, and
this sentence is inherited verbatim from the v1 registration §1.

**Nothing else changes.** No new type, no retired type, no change to the type
set, to the arm dispatch, to the match tolerance, to the gates, to the episode
rules, to arm P, or to any other floor. §5 registers the mechanical assertion
that this is so.

---

## 2. The natural-motion prediction, and the provenance of every constant in it

### 2.1 The model

The prediction is the committed one, called by import and not reimplemented:
`tools/stationkeeping_efficiency.py::propagate_natural`, which carries the orbit
pole `p = (sin i sin Ω, −sin i cos Ω, cos i)` forward as a rigid rotation about
the secular angular-velocity vector of `natural_rate_vector`:

    dp/dt = s · ω_L (P_L × p),    ω_L = 360° / T_prec,
    P_L   = (0, −sin L, cos L)

the retrograde Laplace-plane circuit of T10b's registration eq. (9)
(`docs/t10b-drift-control-preregistration-20260922.md` §2.3 eq. 4).

| symbol | value | provenance |
|---|---:|---|
| `L` (Laplace-pole tilt at GEO) | 7.4 ° | `stationkeeping_efficiency.LAPLACE_TILT_DEG`, T10b registration §2.3(a) |
| `T_prec` (full circuit) | 53.0 yr | `stationkeeping_efficiency.LAPLACE_PRECESSION_PERIOD_YR`, same |
| `s` (sense) | **−1** (retrograde) | **measured**, `laplace_calibration`, commit `a111504`: 33 catalogue objects that had stopped north-south keeping were **all** retrograde, none prograde (`allRetrograde: true` in `docs/stationkeeping-efficiency-20260922-receipt.json`). The registered-as-written default `+1` is wrong and was retired by that measurement, not by preference |
| J2 nodal regression | **not added** | see §2.2 |

**Where the 7.4° and the 53 yr come from, and what they are not.** They are the
GEO Laplace-plane geometry as the programme's own cadence registration states it
(`docs/cadence-s1s2-preregistration-20260922.md` §3.1, cited by
`natural_rate_vector`'s own source). They are a **model**, not a measurement of
this archive: T10b's direct calibration on 33 objects measured tilt
**6.75 °** [p25 6.44, p75 7.48], period **56.2 yr** [52.8, 57.9] and pole speed
at i = 0 of **0.7373 °/yr** [0.711, 0.833] against the model's **0.8748 °/yr**
(`docs/stationkeeping-efficiency-results-20260922.md` §4 table,
`laplaceCalibrationUnregistered` in the receipt). **That discrepancy is not
noise to be averaged away: it is the prediction's own uncertainty, and §3 turns
it into the floor rather than discarding it.**

### 2.2 Why J2 is not added on top, stated as an assumption and not as a fact

T10b's tool records that **the registered sum double-counts the oblateness**,
and its primary path applies the Laplace rotation alone. The reason is in the
source the registration itself cites: the Laplace pole sits at 7.4° *precisely
because* J2's −4.8995 °/yr nodal regression competes with the luni-solar torque.
A Laplace-plane rotation is therefore already the combined secular motion; an
orbit sitting exactly on the Laplace plane does not precess, and adding a
separate J2 term would make it precess at 4.8995 sin(7.4°) = 0.63 °/yr, which
the Laplace plane's own definition forbids.

v2 takes that primary path. **This is an assumption about which model is
correctly posed, not a measured fact**, so v2 computes the J2-included variant
too and carries it on every arm-G burn record as `deltaIncNetJ2Deg`, a
**diagnostic that no rule reads**. The results document publishes the arm-G type
mix under both, so the size of the choice is measured rather than asserted.

### 2.3 The baseline pole, the baseline epoch, and the span

v1's arm-G burn record measures the pre-burn state as the **detector's own
trailing median** over the `BURN_BASELINE_SAMPLES = 10` element sets ending
strictly before the flag (`proximity_geo.BURN_BASELINE_SAMPLES`; v1 registration
§2 and v1 results erratum E3: the detector flags the SECOND confirming element
set, so a one-step difference measures a different quantity from the one that
was detected). v2 keeps that discipline and extends it to the pole:

* **baseline pole** `p_before` — the componentwise trailing median of the unit
  pole vectors of those same 10 element sets, renormalised to unit length. This
  is the vector form of the statistic v1 already uses on the inclination alone,
  and it is needed because the node Ω wraps and a median of a wrapping angle is
  not defined. That a componentwise median of unit vectors is not itself a unit
  vector, and is renormalised, is stated here and asserted in a test.
* **baseline epoch** `t_before` — the median of the epochs of those same 10
  element sets, under the same median convention, so the value statistic and
  the epoch statistic are the same statistic over the same samples.
* **natural span** `naturalSpanDays = (t_flag − t_before) / 86400000 ms`.
* **prediction** `incPredictedDeg` — the inclination of `p_before` carried
  forward by §2.1 over `naturalSpanDays`, using the burn's own `aBeforeKm` and
  the pre-flag eccentricity.
* **net change** `deltaIncNetDeg = incAfterDeg − incPredictedDeg`.

`naturalSpanDays` is **not** v1's `baselineSpanDays`. v1's field spans the whole
window plus one gap (flag epoch back to the sample before the window), and it is
the 18.04-day median v1 published. The natural span runs from the window's
median epoch to the flag and is therefore about half of it. Both are carried on
every v2 record and both are published, so no v2 span figure can be mistaken for
v1's.

All of this is **causal**: every element set read lies strictly before the flag
epoch except the flag element set itself, which is the burn being typed. No v2
rule reads any element set later than the burn it types. This is the T8d
discipline v1 registration §4 inherited, unchanged.

---

## 3. The floor, derived

**No κσ is applied, because a κ is a pick.** v1 registration §3 already refused
Gaussian tail bounds on this archive (p99/σ is 116 at GEO and 3,558 below
500 km; for a Gaussian it would be 2.58), and the two σ-multiples v1 carried
were inherited from other tracks' detector bars, quoted unchanged, not derived.
v2 derives its bar, so it may not import a multiple. **The v2 bar is the
quadrature sum of the measured uncertainty of the quantity itself**: the net
change must exceed the uncertainty of the net change. That is permissive by
construction, and §6 registers what that permissiveness means for the reading.

The net change has exactly two error sources, and they are independent by
construction — one is measured at zero span, the other grows with span.

### Term A — the fit scatter, propagated through the differencing

The registered value is the archive's inclination fit scatter at GEO and above,
σ_i = 1.67e-4 ° (`docs/orbit-history-design.md` §2, n = 450). `deltaIncNetDeg`
differences the post-burn element set against a prediction built from the
pre-burn element sets, so two independently fitted quantities contribute and
the scatter propagates as

    sqrt(2) · σ_i  =  2.3617e-4 °          (*derived*)

**But the repository holds a direct measurement of this exact composite**, and
it is larger. `tools/stationkeeping_efficiency.py::measure_sigma_pole` measured
the magnitude of `|p_after − p_predicted|` on **948,942 quiet GEO arcs** —
consecutive element-set pairs wholly outside every detected interval, median
span 0.502 d — and got

    σ_pole  =  9.683819956551464e-4 °
    <!-- docs/stationkeeping-efficiency-20260922-receipt.json, poleNoiseFloor.sigmaPoleDeg -->

At half a day the natural rotation is ~1.2e-3 ° and its own rate error is
negligible, so σ_pole is the residual of **this same predictor** at essentially
zero span: it contains the fit scatter of both element sets **and** the
unmodelled periodic luni-solar terms the secular model of §2.1 omits. Its own
committed note says so: *"an upper bound on pole noise, not a sigma: it contains
fit noise, the unmodelled periodic lunisolar terms and any sub-threshold burn."*

**Term A is taken as σ_pole = 9.6838e-4 °, not as √2 σ_i.** Using √2 σ_i alone
would ignore a measured error source four times larger. The two are not summed:
σ_pole contains the fit scatter, and adding √2 σ_i on top would count it twice.

Two consequences are registered now, before any number:

* v2's arm-G baseline is a median over 10 element sets, which would reduce the
  fit-scatter part of term A. **That reduction is not claimed.** σ_pole was
  measured on single-pair arcs, and it is used unreduced. The direction of that
  choice is conservative: it makes the floor larger and v2 label fewer burns.
* σ_pole contains any sub-threshold burn inside its quiet arcs. That also makes
  it an upper bound, in the same conservative direction.

### Term B — the prediction's own uncertainty

The prediction of §2.1 is a rotation at a rate this archive has measured against
the model and found to disagree. The measured pole speed at i = 0 is
0.7372991976588145 °/yr (median over 33 objects) against the model's
0.8748380144891058 °/yr, so the rate discrepancy is

    ε_ω  =  |0.8748380144891058 − 0.7372991976588145| / 365.25
         =  0.13753881683029134 °/yr
         =  3.7656075792003106e-4 °/day      (*derived*)

A rate error integrated over the span is a displacement error, and the predicted
inclination is one component of the predicted pole displacement, so

    B(Δt)  =  ε_ω · Δt      degrees, with Δt = naturalSpanDays

bounds the part of the prediction error that grows with the span. This is the
whole reason the floor is span-dependent and v1's was not: **a prediction's
error is a rate error times a time, and a fixed bar cannot express that.**

### The floor

    netFloorDeg(Δt)  =  sqrt( σ_pole²  +  (ε_ω · Δt)² )
                     =  sqrt( (9.683819956551464e-4)²
                              + (3.7656075792003106e-4 · Δt)² )   degrees

*Derived*, with both constants quoted from committed receipts by field name.
Evaluated at the quantiles of v1's published arm-G `baselineSpanDays`
distribution — quoted only so the scale is legible, and **not** the spans v2
will use (§2.3):

| Δt (days) | 1.00 | 4.27 | 9.99 | 18.04 | 29.92 | 60.87 |
|---|---:|---:|---:|---:|---:|---:|
| `netFloorDeg` (°) | 1.039e-3 | 1.877e-3 | 3.884e-3 | 6.862e-3 | 1.131e-2 | 2.294e-2 |

At zero span the floor is σ_pole = 9.684e-4 °, which is 1.16× v1's fixed
8.35e-4 ° bar. **The floor is not a loosening of v1's bar; it is the same order
of magnitude at zero span and grows only as fast as the prediction's own
measured error.** What changes the answer is not the floor but the quantity it
is applied to.

### The sensitivity arm, registered now

The model constants of §2.1 are a model. v2 therefore computes the arm-G type
mix a second time under **M-measured** — T10b's calibrated `T_prec = 56.2 yr`,
`L = 6.75 °`, `s = −1` — and publishes both. Under M-measured the model pole
speed is (360/56.23362481563609)·sin(6.747126521374816°) = 0.752140 °/yr, so
ε_ω computed the same way against the measured 0.7372992 °/yr is
1.4840e-2 °/yr = **4.0631e-5 °/day**, nine times smaller, and the floor is
correspondingly tighter at long spans. That M-measured is nearly
self-consistent is expected — its constants *are* the calibration medians — and
it is therefore a sensitivity on the floor, not an independent check of it.
**M-model is the primary**, because it is the dynamics T10b's own published
numbers were computed under and v2 must not silently re-pose the programme's
model. M-measured is reported beside it as a sensitivity, and it is a
sensitivity, not a second answer.

---

## 4. The v2 rule table

Changed clauses in **bold**. Everything else is byte-identical to v1 (§5).

| # | Type | v1 clause | v2 clause |
|---|---|---|---|
| G1 | drift start | \|Δḋ\| ≥ 0.010 °/d AND \|ḋ_after\| > 0.020 AND \|ḋ_before\| ≤ 0.020 AND **\|Δi\| < 8.35e-4 °** | …unchanged… AND **\|Δi_net\| < netFloorDeg(Δt)** |
| G2 | drift stop | unchanged | unchanged |
| G3 | station acquisition | unchanged | unchanged (clauses); **expected label class corrected, §7** |
| G4 | east-west keeping | …AND inside a station segment AND **\|Δi\| < 8.35e-4 °** | …unchanged… AND **\|Δi_net\| < netFloorDeg(Δt)** |
| G5 | north-south keeping | **\|Δi\| ≥ 8.35e-4 °** AND \|Δḋ\| < 0.010 °/d | **\|Δi_net\| ≥ netFloorDeg(Δt)** AND \|Δḋ\| < 0.010 °/d |
| G6, G7 | graveyard raise, decaying | unchanged | unchanged |
| P1–P5 | arm P | unchanged | unchanged |

The floor is a **function of the burn's own span**, not a constant, so the rule
table's threshold entry for it names the two constants and the form, and both
constants carry their source string into the checksum exactly as every v1 floor
does. A change to either constant, or to the form, changes `rulesSha256`.

**The partition is unaffected in construction.** G1 and G4 require
|Δḋ| ≥ 0.010 °/d; G5 requires |Δḋ| < 0.010 °/d; so G5 remains mutually exclusive
with G1 and G4 whatever the inclination clause says. G1 and G4 remain mutually
exclusive of each other by the stationed-band clauses. G2/G3 remain mutually
exclusive of each other by `priorStationHeld` and can still co-fire with G5, as
in v1. Gate P is nevertheless re-measured on v2 and re-reported, because a
partition that holds in construction is checked, not assumed (v1 registration
§4.1).

**Arm P is not touched.** No arm-P rule reads `incBarDeg`: P2's inclination
clause carries `planeFloorDeg` = 0.01 ° from T8b's registration, a different
constant for a different channel. v2 therefore does not rerun arm P, and the v2
artifact carries arm P's v1 counts unchanged, labelled as carried, with the
byte-identity of the arm-P rule entries asserted mechanically (§5). **The v2
overall UNLABELLED fraction is therefore a v2 arm-G result composed with a
carried arm-P result, and it says so wherever it is printed.**

---

## 5. All other rules are byte-identical to v1 — asserted, not claimed

`Rule.as_dict()` serialises a rule's id, type name, arm, clause strings,
thresholds (name, value, source string), expected label class, propulsive flag
and stage. v2 registers this assertion, to be run as a test and published in the
results:

> For every rule id in {**G2, G6, G7, P1, P2, P3, P4, P5**}, the sha256 of the
> canonical JSON (sorted keys, no whitespace, UTF-8) of that rule's `as_dict()`
> under v2 equals the sha256 of the same under v1.

and its complement:

> For every rule id in {**G1, G3, G4, G5**}, that per-rule sha256 **differs**
> between v1 and v2. A version that changed a rule without changing its hash
> would be unversioned.

The eight per-rule hashes are printed in the results document beside the two
`rulesSha256` values, so a reader can check the claim rather than take it.

**G3 is in the changed set for a reason that is not a clause.** Its rule body is
identical; only `expectedLabelClass` moves (§7). That field is scoring metadata
and no burn's assignment depends on it, but it is part of the rule table whose
hash is the library's identity, so moving it is a version change — which is
exactly why v1 declined to fix it. The results document states, as a measured
fact, that G3 types the same burns under v1 and v2 except where the G5 overlap
changes (§6.2).

---

## 6. The expected effect, registered before it is measured

### 6.1 Direction and size

**Registered expectation: arm-G UNLABELLED falls substantially, and the fall
comes almost entirely from the 906,864 burns v1 classified `both-channels-moved`.**

The mechanism is v1's own measurement, not a hope: the median raw |Δi| across an
arm-G burn is 36% of the repository's luni-solar bound over the same span, so
for most arm-G burns the inclination motion is natural motion, and removing the
prediction should leave a residual below a floor that is itself built from that
prediction's uncertainty. Burns whose inclination genuinely moved keep a net
change above the floor and go to G5 or stay unlabelled.

**The registered bar: arm-G UNLABELLED under v2 is below 50%** (v1: 90.41%).
This is a falsifiable statement fixed before the number exists. It is not a
target: if v2 lands above it, that is published as the headline, with §6.3's
discrimination, and the clause is not adjusted to reach it.

Second registered expectation, which can fail independently: **`north-south
keeping` clears Gate U.** It had 19 matched events in v1, one short of the
registered n ≥ 20, with t10bNorthSouth already its most frequent class. If v2's
G5 fires on a set that is smaller but better aligned, it may clear or it may
fall further; both are published.

### 6.2 The types this change moves, and how each moves

| type | rule | how v2 can move it |
|---|---|---|
| drift start | G1 | **up**: burns whose drift satisfies G1 but whose raw \|Δi\| exceeded the fixed bar can now fire |
| east-west keeping | G4 | **up**, same mechanism |
| north-south keeping | G5 | **down in count**: G5 now requires a net change, not a raw one, so burns whose inclination motion was natural no longer fire it |
| drift stop | G2 | **up**, indirectly: G2 has no inclination clause, but 57 of v1's 84 multi-fire burns were G2+G5. Where G5 stops firing, those burns cease to be multi-fire and become `drift stop` |
| station acquisition | G3 | **up**, indirectly: the same mechanism, 27 of v1's 84 multi-fire burns were G3+G5 |
| graveyard raise, decaying | G6, G7 | **unchanged in rule**; their counts may move only through stage-0 precedence bookkeeping, which is published as it was in v1 |
| arm P, all types | P1–P5 | **unchanged**, carried (§4) |

### 6.3 What would falsify the change, and what must be published either way

The v2 claim is that the net form tests the burn and the raw form tested the
sampling. Three published discriminations, fixed now:

1. **The dependence on span.** v1's clause is measuring spacing, so under v1 the
   arm-G UNLABELLED fraction must rise with `baselineSpanDays`. If v2's fixes
   the mechanism, its UNLABELLED fraction must be markedly flatter in span.
   Both curves are published in the same table, binned by v1's own published
   span quantiles. **A v2 UNLABELLED fraction that still climbs with span like
   v1's is the change failing, and is published as such.**
2. **The size of what is removed.** The quantiles of |Δi|, |Δi_net| and
   `netFloorDeg` are published side by side over all arm-G burns, with the
   median ratio |Δi_net| / |Δi|. If that ratio is near 1, the secular prediction
   is not removing the motion and the diagnosis of v1 §2 was wrong.
3. **The model sensitivity.** The arm-G type mix under M-model and under
   M-measured, and under the J2-included variant (§2.2). If the answer swings
   between them, v2's number is a statement about a model choice and says so at
   the same prominence as the headline.

### 6.4 Confusion and agreement protocol for the affected types

The protocol of v1 registration §6 is inherited **unchanged** — same label
classes, same committed sources, same 5.0-day `MAX_GAP_DAYS` tolerance, same
nearest-match rule, same contested-match count, same forward and reverse
marginals, same Wilson 95% interval, same Gate U at n < 20, same Gate F, same
Gate V vocabulary ban. v2 changes no matching constant.

What v2 adds, because the affected types' populations change:

* **The matrix is republished in full for arm G**, not patched. A v1 cell may
  not be read beside a v2 cell.
* **A paired table for the five affected types** (drift start, drift stop,
  station acquisition, east-west keeping, north-south keeping): v1 count, v2
  count, v1 matched, v2 matched, v1 forward agreement with its Wilson interval,
  v2 forward agreement with its Wilson interval, and the gate verdicts on both
  sides. The intervals are **not** compared by an overlap test, which is not a
  test; they are printed so the reader sees the precision of each.
* **The two runs are not independent**, because they are the same rule set over
  the same burns with one clause changed, and the same labels. No difference in
  agreement between v1 and v2 is given a p-value, a significance, or a
  confidence of its own. This is registered now so that no such number can be
  produced later.
* **Every v1 gate that fired is re-evaluated on v2 and republished**, including
  the ones v2 cannot move, so the v2 results document stands alone.
* **The leak control (Gate L) is recomputed for the affected types.** A change
  that labels many more burns must be shown not to have labelled catalogue-
  passive objects as propulsive. This is the control most exposed by the change
  and it is published per affected type, whatever it shows.

---

## 7. The mapping correction for station acquisition

v1 registration §4.1 wrote rule G3 (`station acquisition`) against the expected
label class `t10aPostTransferEndpoint`. v1 measured **0 / 711** against that
class and **534 / 711 = 75.1%** against **T8a arrivals**, and fired Gate F on
it. v1 results §5 concluded, and this registration adopts: *the rule is sound
and the registration's expected-class mapping was wrong.* A T8a arrival is a
stop within 0.1 ° of another object's mean longitude, held 30 days — almost
always a longitude the mover has not held before, which is exactly what G3
tests. A T10a post-transfer endpoint is the end of a transfer, of which there
are 84 in total; it was never the class G3's clauses describe.

**v2 maps G3's `expectedLabelClass` to `t8aArrival`.** G3's clauses are
untouched. Consequences registered before the number:

* G3's v2 forward agreement is its agreement with T8a arrivals, and it is a new
  figure over v2's G3 population, not v1's 75.1% carried forward.
* **Gate F is expected not to fire for G3 under v2**, because the class it is
  now written against was already its most frequent class in v1. That is an
  arithmetic consequence of the correction, not evidence that the correction was
  right, and the results document says so in those words. **A mapping corrected
  to match a measured outcome cannot then be scored as a successful prediction**,
  and G3's v2 agreement figure is published carrying that sentence wherever it
  appears.
* `t10aPostTransferEndpoint` remains a label class in the matrix and G3's cell
  against it is still printed. Removing the column would hide the correction.
* No other rule's mapping is changed. G2 keeps `t8aArrival`, so under v2 two
  arm-G rules are written against the same class; that is correct — both are
  stops — and the reverse marginal for `t8aArrival` is reported split by rule so
  the two are not pooled.

---

## 8. Versioning, artifacts, and what a consumer pins

### 8.1 Two versions, one instrument

`tools/manoeuvre_library.py` carries both rule sets. **The version is not
defaultable**: `assign_type`, `fired_rules`, `rule_table` and `rules_sha256`
take the version explicitly and there is no fallback, because v1 registration
§7.2 declares that reading a type without pinning the version is reading an
unversioned label. A test asserts that no call site omits it.

### 8.2 What v1 must still do, and the one thing it cannot

**Registered requirement:** with v2 in the file, running the instrument at
`--library-version v1` must reproduce v1's published rule-set identity and every
v1 measurement, bit for bit.

* `rules_sha256("v1")` must equal
  `164a5fd11e4c63744615bbf58c02289cc812c46b630458a85b84f9aee35024f6`. This is
  asserted by an offline test that needs no archive, so it runs on every commit.
* A full v1 rerun over the same inputs must reproduce the committed artifact
  `docs/manoeuvre-library-v1-20260922.json` field for field.

**And the one thing it cannot, registered here before the run rather than
explained after it:** the v1 `artifactSha256`
`eb287e809c0cd1b2f0de0b5bbb80ba33e811a692ca794944ae3dda614abef465`
**cannot be reproduced, by construction.** The artifact embeds
`inputs.toolSha256` — the sha256 of `tools/manoeuvre_library.py` itself — and
`wallSeconds`. Adding a second rule set changes the file's bytes, so
`toolSha256` must change, so `artifactSha256` must change. There is no honest
way around it: pinning `toolSha256` to the old value would be falsifying the
artifact's own provenance record, and that is not done.

What is done instead, registered now as the proof standard:

> **v1 reproduction proof.** Rerun v1. Compare the produced artifact to the
> committed one after removing exactly three fields — `inputs.toolSha256`,
> `wallSeconds` and `artifactSha256` — and require the remainder to be
> **identical**, by a recursive comparison that reports the first differing
> path. Publish the sha256 of the canonical JSON of that reduced object for
> both, and publish the reason those three fields are excluded. Any other
> difference, anywhere, is a v1 regression and stops the work.

This is a weaker proof than a matching `artifactSha256` and is labelled as such
wherever it is printed. It is the strongest proof available once the tool file
has to change, and the v1 artifact itself is not amended, reissued or
recomputed.

### 8.3 The v2 artifact

`docs/manoeuvre-library-v2-20260922.json`, carrying `libraryVersion: "v2"`, a
new `rulesSha256` over the v2 rule table, a new `artifactSha256`, the eight
per-rule byte-identity hashes of §5, the `inputs` block with its own
`toolSha256`, and — explicitly labelled — the arm-P block carried from v1 with
v1's `rulesSha256` recorded beside it as the version those counts were produced
under.

A consumer of a v2 type pins `libraryVersion` **and** `rulesSha256`, exactly as
for v1. **v1 and v2 types may not be mixed in one population.** A burn typed
under v1 and a burn typed under v2 are labels from two instruments.

### 8.4 What v1 remains good for

v1 is not withdrawn and nothing published from it is retracted. Its three
confidences (`phasing` 0.677, `drift start` 0.560, `orbit raise` 0.549) stand as
v1 figures. Its arm-P result is the same arm-P result v2 carries. Its arm-G
result stands as **the measurement that the raw clause tests sampling**, which is
the finding that produced this version and which a v2-only reader would not
have.

---

## 9. Order of work, and what may not happen before what

1. **This document, committed alone, by explicit pathspec.** No v2 number
   produced before this commit exists may enter the rule set, the matrix or the
   results.
2. `tools/manoeuvre_library.py` and `tests/test_manoeuvre_library.py`, committed
   together. **The tests assert the bug first**: a seeded arm-G burn whose
   entire |Δi| is the natural motion over its span, with a drift change that
   satisfies G1, must come out **UNLABELLED under v1** and **`drift start`
   under v2** — and the test file records that both states were observed, on the
   same record, in the same run.
3. The arm-G rerun over the same detected-burn set, then
   `docs/manoeuvre-library-results-v2-20260922.md`,
   `docs/manoeuvre-library-v2-20260922.json` and the ledger subset, committed
   together.
4. The runbook T13 row and the STATUS ledger entry updated with a v2 line.

No number from step 3 may be used to revise steps 1 or 2. If the run shows the
clause is wrong, that is a v3.

---

## 10. Deviations from the v1 registration, each with its reason

| # | v1 registration says | v2 does | Why |
|---|---|---|---|
| V1 | the arm-G inclination clause is \|Δi\| against a fixed 5σ_i bar | the clause is \|Δi_net\| against a span-dependent derived floor | v1 measured the fixed bar to be testing element-set spacing (v1 results §2). §1 |
| V2 | `station acquisition` is written against `t10aPostTransferEndpoint` | written against `t8aArrival` | v1 measured 0/711 against the first and 534/711 against the second, and concluded the rule is sound and the mapping wrong. §7 |
| V3 | a version's artifact is identified by `artifactSha256` and is never amended | v1's artifact is not amended, and its `artifactSha256` is declared unreproducible with the reason | the artifact embeds the tool file's own hash; a second rule set in the same file changes it by construction. §8.2 |
| V4 | every rule threshold is a constant another committed track registered | the v2 floor is *derived* here from two committed measured constants (σ_pole, the pole-speed discrepancy) by the arithmetic of §3 | v1 registration §3 permits a threshold "derived from a standard result cited here"; the derivation and both provenances are in §3, and no free multiple is introduced |
| V5 | arm G and arm P are both measured in a run | arm P is carried from v1, not rerun | no arm-P rule reads the changed floor; §5's byte-identity assertion is the proof, and the carry is labelled in the artifact. §4 |

---

## 11. Sources

```
docs/manoeuvre-library-preregistration-20260922.md     v1 registration (d86b93d)
docs/manoeuvre-library-results-20260922.md             v1 results (77eee17): section 2, the 90.41%, the span and |delta i| quantiles
docs/manoeuvre-library-v1-20260922.json                v1 artifact, rulesSha256 164a5fd1..., artifactSha256 eb287e80...
docs/t10b-drift-control-preregistration-20260922.md    section 2.3 eq. (4): the retrograde Laplace circuit and its sense
docs/t10b-drift-control-results-20260922.md            the 0.8748 vs 0.7373 pole-speed gap as that control uses it
docs/stationkeeping-efficiency-results-20260922.md     section 4: the calibrated tilt 6.75 deg, period 56.2 yr, pole speed 0.7373 deg/yr
docs/stationkeeping-efficiency-20260922-receipt.json   poleNoiseFloor.sigmaPoleDeg; laplaceCalibrationUnregistered
docs/stationkeeping-ns-20260922.jsonl                  incPredictedDeg / deltaIncNetDeg / naturalFraction, the committed form
docs/orbit-history-design.md                           section 2: sigma_i = 1.67e-4 deg at GEO+, n = 450; section 2.1: the tails
docs/cadence-s1s2-preregistration-20260922.md          section 3.1: why the GEO Laplace plane sits at 7.4 deg
pipeline/orbit_events.py                               lunisolar_inclination_bound_deg
tools/stationkeeping_efficiency.py                     propagate_natural, natural_rate_vector, laplace_pole, measure_sigma_pole
tools/proximity_geo.py                                 BURN_BASELINE_SAMPLES, drift_change_flags, the arm-G floors
```

Standard results used: the rotation of a unit vector about an axis (Rodrigues),
as `stationkeeping_efficiency.rotate_about` implements it; propagation of
independent errors in quadrature; the Wilson score interval for a binomial
proportion, unchanged from v1. Every other figure in this document is quoted
from a committed receipt or committed results document with its field name, or
labelled *derived* with the line it is derived from.
