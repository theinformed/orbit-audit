# T22 results: the physics is right in the aggregate and useless per burn

**Registration:** `docs/t22-scheduled-null-preregistration-20260923.md`, committed
**ALONE** at `1f27ef5` (2026-09-22 20:29:55 −0400), eighteen minutes before any
instrument existed and before any number below.
**Instrument:** `tools/scheduled_null.py` with `tests/test_scheduled_null.py`,
**54 offline proofs**, no archive and no network.
**Artifacts:** `docs/t22-scheduled-null-20260923-receipt.json`,
`docs/t22-scheduled-null-20260923.jsonl`.
**Compute:** CPU on `pc`, one core, **182 s wall**. No GPU was taken, so **no
`gpu-consumers.json` row is owed**. Nothing is scheduled, nothing is deployed,
nothing reaches `src/`, `data/`, `public/` or any site surface.

---

## 0. The verdict, stated first

> **REGISTERED VERDICT: `VOID -- UNDERPOWERED`.** The composite PASS ladder stops
> at its own power gate: clause P3 needs 50 horizon-matched passive pairs and the
> archive yields **20**. No passive fraction is read from fewer, and the cell is
> printed as **a labelled gap, not a zero**.
>
> **On the clause that IS powered, the registered falsifier is MET.** Over
> **9,289 admitted east-west keeping pairs on 187 carriers**, the on-schedule
> fraction is **0.0697, Wilson 95% [0.0647, 0.0750]**, against a random-phase
> null that reaches **0.2438, 95th percentile 0.2502** at the identical derived
> windows. **The physics-scheduled prediction is three and a half times WORSE
> than drawing an interval at random from the population's own spacings.** In
> the slate's own words: *the on-schedule fraction is not above what a
> random-phase null gives.*
>
> **And the reason is not that the physics is wrong.** Every ingredient is right
> in the aggregate — the derived triaxial acceleration is unbiased at the median
> (`a_fit/a_derived = 0.961` over 29,315 arcs), the post-burn drift rate is
> within 5% of what the flown cycle needs, and the band that rate implies is
> `0.02547 deg` against the registered `0.02633 deg`. **The exit epoch is a
> BIFURCATION**: the optimal one-burn cycle is tangent to the far edge of its own
> deadband, so a 10% error in the drift rate decides between a half cycle and a
> full one. Measured: **65.1% of pairs are predicted out of the FAR edge at a
> median 1.22 days and 34.9% out of the burn-side edge at a median 6.96 days**,
> and the flown interval is 14.35 days.

**One registered prediction held, and it is the usable result of this track.**

> **The ramp-direction-versus-slot-side test separates a controlled object from
> a free one: 0.8294 [0.8251, 0.8336] of 29,836 carrier flag chains obey the
> rule, against 0.1515 [0.1434, 0.1600] of 7,160 passive ones. The false rate on
> passives is 15.2%.** The registration predicted in advance that the passive
> fraction would be at or below 0.5, because free motion under the same
> acceleration carries the OPPOSITE sign. It is 0.15.

**One registered prediction failed in the opposite direction.** Off-schedule
burns were predicted to be ENRICHED for relocation types. They are DEPLETED:
`drift start` odds ratio **0.717 [0.520, 0.988]**, and the three-type union
**0.328 [0.282, 0.381]**.

**E5 removes nothing.** The alarm lane's class-1 precision on the committed
2010s replay is **14/272 = 5.147% [3.090%, 8.453%] before and 14/272 = 5.147%
[3.090%, 8.453%] after**, with **0 alerts removed**. The join is live and the
chain is printed in §7 rather than asserted: 271 of the 272 spoken alerts match
a chain pair, 15 match an admitted pair, 3 have an east-west keeping
predecessor, and none of those 3 is on-schedule.

---

## 1. What ran

| | |
|---|---|
| host | `pc`, CPU, one core |
| wall | **182.1 s** (the published run; two earlier end-to-end runs at 178.1 s and 165.1 s reproduce every statistical block) |
| seed | 20260923 throughout |
| element extract | `runtime/proximity-geo/near-geo.npz`, T8a's cached pass, its three published numbers asserted at load: 217,007,154 rows scanned, 11,626,494 kept, 1,768 objects |
| burn types | the T13 **v2** arm-G ledger, regenerated on this host (deviation V1) and **reproducing the committed artifact's arm-G block field for field** at `rulesSha256` `e2e0cbbd…`: 1,018,263 burns, 91,142 `east-west keeping`, 37,910 `drift start`, 31,103 `drift stop`, 37,336 `station acquisition`, 814,571 `UNLABELLED` |
| burn unit | T8d's flag chain, `trigger_alarm.flag_baselines` + `chain_flags` at `MERGE_DAYS = 5.0`, `sigma_n = 6.038533519066339e-4`, **imported, and a proof fails if either name is redefined in this instrument** |
| disk | **125 GB free before, 124 GB free after** (87% -> 88% used); the regenerated arm-G ledger is 369 MB and the three run directories are 17 MB, all outside the repository |

**Determinism, measured rather than assumed.** The instrument was run **three
times** end to end: once as written, once after changing only how much of the
pair ledger is written to the published file, and once after adding the
post-registration diagnostics block of §6. **Every statistical block of the
three receipts is identical** — `E0`, all three centre arms' `E1`, `E1b`, `E2`,
`E3`, `E4`, `E5`, `MC1` and every verdict — leaving only the timestamp, the wall
clock, the tool hash and the thinning step to differ. Every seed in this track
is fixed and three runs prove it.

### 1.1 Exposure, printed for both arms

| | carrier arm | passive arm |
|---|---:|---:|
| roster | 208 | 331 |
| objects with a usable series | **207** | **239** |
| element sets | 1,841,245 | 1,623,047 |
| **object-days** | **1,555,008** | **2,376,162** |
| flag chains | 40,578 | 47,571 |
| consecutive-chain pairs offered | 40,371 | 47,340 |
| **pairs admitted** | **22,486** | **40** |
| ... of which the chain is typed `east-west keeping` | **9,289** | — |

**The passive arm is not a clean control and this track did not make it one.**
The runbook's own T8e line says no passive control exists at GEO because slow
librators dwell like keepers, and the numbers above are that statement in
another form: 239 objects that cannot manoeuvre carry **more** flag chains than
207 that can.

---

## 2. Why pairs were not admitted, counted rather than dropped

| screen | carrier | passive |
|---|---:|---:|
| **admitted** | **22,486** | **40** |
| too few element sets between the chains (screen 2) | 7,155 | **34,430** |
| the burn is outside its own band (screen 6) | 5,193 | 291 |
| an element-set gap longer than 5 d inside the pair (screen 3) | 3,380 | 5,748 |
| relocating: 5 deg of spread across the pair (screen 7) | 1,636 | 6,405 |
| acceleration within 4 deg of an equilibrium (screen 4) | 521 | 424 |
| slot window too thin (screen 5) | 0 | 2 |

**The passive arm dies on screen 2**, which requires ten element sets between
one chain and the next so that the two fits of registration §2.4 are causal. A
passive object's element cadence is sparser and its chains are closer together,
so 72.7% of its pairs cannot be given a causal fit at all. That is a property of
the archive's sampling of these objects, it is printed here, and it is why P3's
power gate fires.

---

## 3. E0 — the derived acceleration against the measured one

Registration §2.4 required `sigma_a` to be MEASURED in a pass that computes no
estimand. It was, over **29,315 admitted arcs** on the carrier arm.

| quantity | p5 | p25 | **p50** | p75 | p95 |
|---|---:|---:|---:|---:|---:|
| `a_fit / a_derived` | −0.941 | 0.592 | **0.961** | 1.221 | 1.903 |

| | |
|---|---:|
| robust scatter of the ratio (`1.4826 MAD`) | **0.437** |
| **`sigma_a` = robust scatter of `a_fit - a_derived`** | **5.899e-4 deg/day²** |
| ... as a fraction of `A` | **0.347** |

**The triaxial model is unbiased at the median and hopeless per arc.** The
median ratio is `0.961` — the derived acceleration is right to 4% across
twenty-nine thousand arcs — and the fifth percentile is `-0.941`, i.e. **one arc
in twenty measures the acceleration with the WRONG SIGN**. A ten-element fit
over about five days cannot measure a curvature of `1.7e-3 deg/day²` against
this archive's scatter, and this number is what the derived tolerance of §4 is
mostly made of.

---

## 4. The derived tolerance, and MC1

The window is `w = 2 sqrt(sigma_tau^2 + sigma_obs^2)` with `sigma_tau` from the
registered propagation. It is per burn, it has no floor, no minimum and no grid,
and a proof asserts that the source contains none.

| centre arm | median window | median observed interval | W1 defect rule |
|---|---:|---:|---|
| `k = 0.00` (the registration's plain median) | 1.010 d | 14.332 d | does not fire |
| `k = 0.25` | 0.781 d | 14.337 d | does not fire |
| **`k = 0.50` (V3, the derived centre)** | **0.638 d** | **14.350 d** | **does not fire** |

The registered defect rule W1 fires when the median window exceeds a third of
the median observed interval. At `k = 0.50` that would be 4.78 d and the window
is 0.638 d, so **the window is not what is failing here**, which is the point of
having registered the rule in advance.

**MC1 passes.** Over 200 admitted pairs the Monte-Carlo propagation returns
`1.0124` times the linear one at the median, well inside the registered 10%
tolerance, so the linearisation of eqs. (7)–(12) is kept and no deviation is
owed.

**And the observed interval reproduces T3's line on a different instrument.**
T3's east-west line sits at **14.00 d** from a Lomb-Scargle periodogram over mean
motion. This track never computes a periodogram: it counts the days between
consecutive flag chains, and the median is **14.35 d** over 9,289 pairs on 187
carriers. Two instruments, one number, and this one was not tuned to it.

---

## 5. E1 and E1b — the measurement, and the null that prices the window

| centre arm | on-schedule | pairs | **fraction** | Wilson 95% | objects |
|---|---:|---:|---:|---|---:|
| `k = 0.00` | 602 | 10,153 | **0.0593** | [0.0549, 0.0641] | 187 |
| `k = 0.25` | 624 | 9,937 | **0.0628** | [0.0582, 0.0677] | 188 |
| **`k = 0.50`** | **647** | **9,289** | **0.0697** | **[0.0647, 0.0750]** | **187** |

| null, at the identical windows | median | **95th percentile** |
|---|---:|---:|
| **N1 random phase** — a draw from the arm's own observed spacings | 0.2438 | **0.2502** |
| N2 shuffle of `tau*` within one object's own pairs | 0.0376 | 0.0393 |

**P2 fails by a factor of three and a half.** The registered clause asks the
measured Wilson lower bound to exceed N1's 95th percentile: 0.0647 against
0.2502. It does not; it is not close; and the direction is the informative one —
**knowing nothing except how often this population burns beats computing when
physics says it must.**

**N2 is the one place the predictor earns something.** Shuffling `tau*` among one
object's own pairs returns 0.0393 at the 95th percentile against a measured
0.0697, so the per-pair `tau*` does carry information about which of that
object's own gaps is which. Its LEVEL is wrong, not its ordering.

**The error is systematic, not scattered.** The median signed error is
**+11.35 d**: the burn arrives eleven days after the physics says it must. The
median `tau*` is 2.17 d against a median remaining horizon of 12.99 d, a ratio
of **0.123**.

---

## 6. Where the eleven days go — the bifurcation

**This is the mechanism, and it is measured, not argued.** Section 2.2 of the
registration wrote the predictor as the first exit of the parabola from the
band, and section 2.3 wrote down before the run that the optimal one-burn cycle
is TANGENT to the far edge. A tangency is a bifurcation: an object whose
turning point falls a hair inside the band flies a full cycle, and one whose
turning point falls a hair outside is predicted to leave at the far edge in half
the time.

Post-registration diagnostics, labelled as such, over the `k = 0.50` arm's
east-west pairs in the published ledger:

All 9,289 admitted east-west pairs of the `k = 0.50` arm; the block is in the
receipt as `postRegistrationBranchDiagnostics`, labelled there in those words.

| | p25 | **p50** | p75 |
|---|---:|---:|---:|
| post-burn drift rate, `\|lambdadot\|` (deg/day) | 0.003512 | **0.012147** | 0.014604 |
| the rate the OBSERVED cycle needs, `\|a\| T / 2` | 0.009524 | **0.011237** | 0.013062 |
| needed / measured | 0.743 | **0.951** | 3.578 |
| **the band that rate implies**, `lambdadot^2 / (4 \|a\|)` (deg) | 0.002499 | **0.025471** | 0.036372 |
| `\|lambda_n - lambda_c\|` at the fit epoch (deg) | 0.005789 | **0.011445** | 0.017334 |
| chain span, `t_trig - t_first` (d) | 0.952 | **1.220** | 1.799 |
| `tau*` over the remaining horizon | 0.065 | **0.124** | 0.326 |

**Read the second, third and fourth rows together.** The drift rate the archive
reports just after a detected east-west burn is within **5%** of what the flown
14.3-day cycle needs, and the deadband that rate implies is **0.02547 deg**
against the registered **0.02633 deg** — a **3%** agreement between two
instruments that share no arithmetic. **The ingredients are right.**

And the exit still lands on the wrong side of the bifurcation two times in three:

| predicted exit edge | pairs | share | median `tau*` | median observed | **on-schedule** |
|---|---:|---:|---:|---:|---|
| the burn-side edge (a full cycle) | 3,244 | **34.9%** | 6.96 d | 15.05 d | **0.1917 [0.1786, 0.2056]** |
| the far edge (a half cycle) | 6,045 | **65.1%** | 1.22 d | 14.18 d | **0.00414 [0.00280, 0.00610]** |

**A prediction conditioned on the branch is forty-six times better than one that
is not, and it is still 0.19.** The branch itself is decided by whether
`lambdadot^2 / (2|a|)` exceeds the distance from `lambda_n` to the far edge — a
comparison of two quantities the archive measures to about a tenth, across a
boundary that a tenth straddles.

> **The registered consequence C3, evaluated.** C3 predicted that the
> physics-scheduled interval of eq. (6) would run LONGER than the observed one.
> **For eq. (6) it held**: `4 sqrt(D/A) = 15.739 d` against a measured median of
> 14.350 d. **For the eq. (4) predictor the run went the other way**, and hard:
> `tau*` is an eighth of the remaining horizon. C3 was written about the closed
> form and the track was run on the root; both are reported, and the
> registration's own §2.2 warned in advance that the two are not the same test.

---

## 7. E2 to E5, each reported whatever it shows

### 7.1 E2 — the passive leak, with its exposure

| arm | on-schedule | pairs | fraction | Wilson 95% |
|---|---:|---:|---:|---|
| **E2a**, pooled deadband | 1 | 40 | 0.0250 | [0.0044, 0.1288] |
| **E2b**, horizon-matched to the carriers' `tau*` interquartile range (0.98–5.72 d) | 0 | **20** | — | **NOT ASSESSABLE — 20 pairs against a registered bar of 50; a labelled gap, not a zero** |

Exposure printed beside it, as the registration required: **239 objects,
1,623,047 element sets, 2,376,162 object-days, 47,571 flag chains, 47,340 pairs,
40 admitted.** §2 says where the other 47,300 went.

**P3 cannot be evaluated and the registered verdict is therefore `VOID`.** What
can be said is that the passive arm produced one on-schedule pair in forty, and
that nothing in that number is a measurement.

### 7.2 E3 — the enrichment, refuted in the opposite direction

| type set | off-schedule with / without | on-schedule with / without | **odds ratio** | 95% |
|---|---:|---:|---:|---|
| **`drift start`** (primary) | 342 / 20,274 | 43 / 1,827 | **0.717** | [0.520, 0.988] |
| union `{drift start, drift stop, station acquisition}` | 936 / 19,680 | 237 / 1,633 | **0.328** | [0.282, 0.381] |

The hypothesis said off-schedule burns would be ENRICHED for relocation types.
Both odds ratios are below 1 and the union's interval excludes 1 decisively.

**A mechanism is available and it is not flattering to the estimand.** The
median `tau*` is 2.17 d, so "on-schedule" in this run largely means *the next
burn came within a couple of days* — which is what a relocation looks like from
the outside: a drift start closed by a stop. The on-schedule set is therefore
enriched for multi-burn campaigns by construction. **The odds ratio is reported
as measured and is not offered as evidence about relocations.**

**Two sentences travel with the union wherever it is printed**, as the
registration fixed: `drift stop` carries Gate F; and `station acquisition`'s
0.751 is a mapping corrected to match a measured outcome and may not be scored
as a successful prediction.

### 7.3 E4 — the sign test, and the one thing here that works

Registered rule (14): a burn that holds a slot pushes the drift rate AGAINST the
triaxial acceleration.

| population | chains | obey (14) | **fraction** | Wilson 95% |
|---|---:|---:|---:|---|
| **207 east-west carriers** | 29,836 | 24,745 | **0.8294** | [0.8251, 0.8336] |
| **239 same-shell passives** | 7,160 | 1,085 | **0.1515** | [0.1434, 0.1600] |
| carriers, off-schedule pairs | 20,616 | 18,203 | 0.8830 | [0.8785, 0.8873] |
| carriers, on-schedule pairs | 1,870 | 1,525 | 0.8155 | [0.7973, 0.8324] |

> **The registered prediction P-SIGN held.** It said, before the run, that a
> passive object's flagged drift change is the acceleration's own work and
> carries the OPPOSITE sign, so the passive pass-fraction would be at or below
> 0.5 and materially below the carriers'. It is **0.1515**: 85% of passive drift
> changes run WITH the acceleration and 83% of carrier ones run against it. The
> two Wilson intervals are separated by 67 percentage points.

**The false rate on passives is 0.1515 [0.1434, 0.1600].** That is the number the
brief asked for: an object that cannot manoeuvre passes the burn rule about one
time in seven.

**What this is and is not.** It is a per-flag discriminator between a controlled
and a free object on the east-west channel, measured on 36,996 flag chains. It
is not a detector, no threshold is proposed here, and the passive population it
is measured against is the one T8e says is not clean. The carriers' 0.83 is a
ceiling set by the same measurement noise §3 measured: the sign of a small drift
change is not always readable.

**The on-schedule and off-schedule splits go the wrong way for the hypothesis**
too — off-schedule burns obey the sign rule slightly MORE often (0.883) than
on-schedule ones (0.816), which is the same multi-burn-campaign contamination
§7.2 names.

### 7.4 E5 — the alarm lane's class-1 precision, re-scored

Registered up front as estimand E5, so this is not a post-registration reading.

| | hits | alerts | precision | Wilson 95% |
|---|---:|---:|---:|---|
| **before** | 14 | 272 | **5.147%** | [3.090%, 8.453%] |
| **after**, on-schedule burns removed from the denominator | 14 | 272 | **5.147%** | [3.090%, 8.453%] |
| removed | — | **0** | — | — |

**The join is live, and the chain is printed rather than asserted:**

| | count |
|---|---:|
| spoken class-1 alerts on the committed 2010s replay | 272 |
| ... matching a consecutive-chain pair on their object, on `(norad, tTrigMs)` | **271** |
| ... whose pair is ADMITTED by §3.4's screens | **15** |
| ... whose predecessor chain is typed `east-west keeping` | **3** |
| ... and on-schedule | **0** |

So the re-scoring removes nothing, and it removes nothing for a reason the
counts name: **the alarm's class-1 triggers are almost never the second burn of
an admitted east-west keeping pair.** 256 of the 271 matched alerts fail a screen
— mostly the causal-fit and the relocation screens, which is what a
wide-crossing trigger is: an object that has left its slot. The one alert that
matched nothing at all stays in the denominator as a labelled gap, exactly as the
registration required.

---

## 8. Deviations, each declared

| # | what | why, and what it cost |
|---|---|---|
| **V1** | The T13 v2 arm-G ledger was **regenerated** on this host before the registration was committed, because the 1,068 MB table was not kept. | A reproduction of a committed instrument at a pinned rule hash, not a measurement. The regenerated arm-G block equals the committed artifact's field for field and the `rulesSha256` is identical. Declared in registration §1.2 in advance |
| **V2** | An **exposure probe** ran before the registration was committed. | Counts, spacings and object-days only; no estimand. Declared in registration §9 in advance, with its table |
| **V3** | **The registration's centre estimator is biased by half a band, and the run sweeps the bias instead of using it alone.** A cycle that burns at `lambda_c + sD` and turns at `lambda_c - s f D` has median longitude `lambda_c + sD[(1+f)/4 - f]`, so the plain median is the centre only when the apex reaches a third of a band past it; at the optimal cycle the bias is exactly `D/2`. | **Derived from the same parabola as the predictor, not fitted.** An offline proof asserts that the plain median admits NOTHING on a planted optimal cycle. All three arms `k = 0, 0.25, 0.50` are run and all three are reported in every table; **the verdict is the same in all three** |
| **V4** | **An exit is a crossing, not a touch.** The optimal one-burn cycle is tangent to the far edge; without an outward-velocity clause eq. (4) returns the half cycle of eq. (6) instead of the cycle. The double root is detected by comparing the discriminant against its own terms. | Floating-point hygiene on an exact algebraic condition, asserted by two proofs. Without it every closed-form check in §5 of the registration fails |
| **V5** | **The instrument and its proofs did not get a commit of their own.** A concurrent session's broad commit `f5a2b31` absorbed `tools/scheduled_null.py` and `tests/test_scheduled_null.py` between this session's `git add` and its `git commit`, so the proof file is attributed to that commit; the instrument was touched once afterwards, to add the diagnostics block of §6, and rides with this document. | Nothing was lost and no history was rewritten. **The property that matters is intact and checkable: `1f27ef5` contains the registration and nothing else, and it precedes `f5a2b31` by eighteen minutes and these results by thirty-eight** |
| **V6** | The published pair ledger is **thinned** by systematic sampling, **every 14th admitted pair of 71,762** across the three centre arms (5,126 rows, 5.6 MB), with the step recorded in its provenance line. | Every pair is in every statistic above; only the file is thinned, and §6's diagnostics are computed over the WHOLE population and carried in the receipt so that nothing quoted here needs the thinned file |

---

## 9. What is owed, and what is UNPROVEN in that word

1. **A passive control that survives a causal fit.** 72.7% of passive pairs
   cannot be given ten causal element sets between one chain and the next, so
   **P3 was never evaluated and the leak test of this track is UNPROVEN.** The
   number needed is the fraction of free-drifting objects that land on a physics
   schedule, and this run does not have it.
2. **The branch, decided from data rather than predicted.** §6 measures that a
   prediction conditioned on the exit edge is forty-six times better than one
   that is not. Nothing here predicts the edge; a registration that did would be
   a different track and it is not written.
3. **A per-object deadband.** The pooled `0.02633 deg` is T10c's median flown
   excursion across 207 carriers, and §6 shows individual pairs implying
   anywhere from `0.0026` to `0.0364`. T5c owes the per-element covariances that
   would give each object its own band and its own `sigma`.
4. **The sign test is not a detector and no operating point is proposed.** Its
   0.8294 against 0.1515 is a measurement on this population, its recall is
   UNMEASURED as it is everywhere in this programme, and the passive arm it is
   measured against is the one T8e says is not clean.
5. **Nothing in this track has been exercised as a scheduled lane, because
   nothing here is a lane.** No timer, no cron entry, no state file, no alert,
   no surface. The instrument is a one-shot measurement and it was run twice.
6. **This is not a blind analysis.** Every constant was read before the
   registration was written; only the combination and the decision rule were
   fixed in advance.

---

## 10. Reproduction

```
python3 -m unittest tests.test_scheduled_null          # 54 proofs, no archive, no network
python3 tools/manoeuvre_library.py --library-version v2 --stage geo \
    --out /home/sdegan/t22-work                        # the arm-G ledger, V1
python3 tools/scheduled_null.py --out docs             # 182 s, CPU, one core
```

The receipt carries the extract provenance, both input hashes, the tool's own
sha256, every screen count, all three centre arms and every estimand with its
interval.
