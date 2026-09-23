# T18 PRE-REGISTRATION — a learned model over element-set histories

**Date:** 2026-09-22. **Status:** REGISTERED. **Track:** T18 of
`docs/research-program-runbook-20260921.md`. **Design of record:**
`docs/t18-learned-model-design-20260922.md` (`055e380`), runbook row `c789592`.

**This file is committed ALONE, before any T18 code and before any T18 number exists.** Nothing has been
extracted, trained, scored or probed. The ordering is in the repository history, not asserted in prose.
Once a number governed by a clause below exists, that clause is not edited — a departure is recorded as a
deviation in the results document, in the style of `docs/t16b-truthset-results-20260922.md` §5.

Every figure quoted here is from a committed artifact with its source, or is a census measured for this
registration and labelled as one. **Every threshold in this file is a chosen screen, not a physical law.**

---

## 0. The falsifier, first

> **"The learned model adds information" is FALSE if, at matched false-flag rate, its recall lower bound
> does not exceed the shipped detector's upper bound; AND the forecast non-inferiority clause fires; AND
> the anomaly score's flag rate is not separable from Rung-2 sampling class. If all three hold, T18 is a
> fail-record, the numbers are published, and the track closes.**

Verbatim from design §7.2. The fail-record is `docs/t18-fail-record-<date>.md`; it publishes every measured
number with its interval; the `gpu-consumers.json` row is retired in the same change; and no clause of this
registration is rewritten to rescue the track.

---

## 1. The prerequisite is discharged, and exactly what it licenses

Design §7.1 made T16(b) a hard blocker. It landed 2026-09-22 (`7bdf09a`,
`docs/t16b-truthset-results-20260922.md`, artifacts `docs/t16b-truthset-{growth,recall}-20260922.json`).

**The baseline this track must beat, measured, with its floor printed first**
(`t16b-truthset-recall-20260922.json`, arm `pooled`, window `madleoEventWindow`):

| | value | source |
|---|---|---|
| Shipped detector recall | **90/1,134 = 7.937%**, Wilson 95% **[6.502, 9.656]** | recall JSON `arms.pooled.windows.madleoEventWindow.overall` |
| Labels not evaluable | **0 of 1,134** | same, `notEvaluable` |
| False flags in labelled-quiet windows | **18** over **1,139** windows / **1,423.75** window-days | sum over `arms.pooled.perSpacecraft.*.falseFlags` |
| **The operating point** | **0.012642669007901668 flags per labelled-quiet window-day** | 18 / 1,423.75, derived here |
| Quiet windows carrying ≥ 1 flag | 10 of 1,139 (0.878%) | same |
| Detector floor, shipped settings | **102.2 – 126.0 m** of semi-major axis (**54.0 – 58.7 mm/s**) | recall JSON `floor.minDetectableDaMetres` per spacecraft |
| Labels above that floor | **81/157 = 51.592%** [43.83, 59.28] | `byFloor.aboveFloor` |
| Labels below that floor | **9/977 = 0.921%** [0.49, 1.74] | `byFloor.belowFloor` |
| Placebo control (post-registration in T16b, labelled there) | 17/5,610 = 0.303% | `placeboControl` |
| Campaign-level recall | 15/1,134 = 1.32%, structural ceiling 33 campaign starts = 2.9% | `campaignLevel` |

**Per burn-size bin, the baseline, on the committed `|Δa|` bins:**

| bin | k / n | recall | Wilson 95% |
|---|---:|---:|---|
| < 20 m | 6 / 576 | 1.04% | [0.48, 2.25] |
| 20–50 m | 2 / 342 | 0.58% | [0.16, 2.11] |
| 50–100 m | 1 / 53 | 1.89% | [0.33, 9.94] |
| 100–200 m | 10 / 27 | 37.04% | [21.53, 55.77] |
| 200–500 m | 21 / 36 | 58.33% | [42.20, 72.86] |
| ≥ 500 m | 50 / 100 | 50.00% | [40.38, 59.62] |

**REGISTERED DEPARTURE FROM THE DESIGN'S WORD, made before any T18 number exists.** Design §3.3 and the
screen table say *"per burn-size decile"*. T16(b) has since measured the burn-size distribution: 918 of
1,134 labels lie below 50 m, so five of ten deciles would fall entirely inside the `< 20 m` bin and three
more inside `20–50 m`, and a decile table would publish eight cells that are the same cell. **T18 therefore
reads the reversal clause on T16(b)'s six committed `|Δa|` bins, which are the bins the baseline is
published in**, and the deciles are not computed. This is registered as a departure here, not discovered
later.

### 1.1 Recall composition limits — stated in the words the results must use

**The labels are geodetic spacecraft, not constellations.** The 1,134 manoeuvres are mission-reported
histories of **eleven geodetic and altimetry spacecraft** — CryoSat-2, Sentinel-3A, Sentinel-3B, Jason-1,
Jason-2, Jason-3, SWOT, SARAL, HY-2A, TOPEX/Poseidon, Sentinel-6A — parsed from IDS/DORIS mission
publications (MAD-LEO, CC BY 4.0, doi 10.6084/m9.figshare.33446503.v1). MAD-LEO's Starlink subset **carries
no manoeuvre labels at all**; its authors state it is operator *prediction* and "never maneuver ground
truth" (`t16b-truthset-results` §1). The design's own §2.5 table, which described MAD-LEO as "6,785
Starlink objects", is **superseded** by that measurement and is not relied on anywhere in T18.

Binding on every T18 results document:

- No T18 recall figure is "the model's recall" without the qualifier *on this labelled set, these eleven
  geodetic and altimetry spacecraft, these burn sizes*.
- **Nothing T18 measures says anything about Starlink, about any constellation, or about any operator whose
  manoeuvre log is not public.** A Starlink-class labelled baseline remains **unmeasured**.
- Eleven cooperative, exceptionally well-tracked spacecraft are not a census. Precisely what makes them
  measurable — large, tracked by GNSS/DORIS/SLR, small frequent planned burns — makes them unrepresentative.
- Recall and precision do not compose across populations: T8b's 44.1% and the alarm lane's 0.507% were
  measured on different denominators and T18 may not multiply them together.
- The truth set holds **1,134** labels, so a Wilson interval near p = 0.8 is about ±2.3 points wide. **An
  advantage smaller than that interval cannot be demonstrated at all**, and T18 will not claim one.
- The eleven spacecraft span 1992-08-17 to 2026-07-05 (census measured for this registration on
  `mission_reported__annotations__maneuver_annotations.csv`). Any era-restricted arm reports its own `n`.

### 1.2 The archive, censused for this registration

Direct sequential `GROUP BY norad` scan of `element_set`, 2026-09-22, 51.4 s:
**68,749 objects, 217,046,214 element sets.** The design quoted 217,026,192 from
`proximity-leo-20260922-receipt.json`; the archive ingests hourly and has grown by 20,022 rows since. **The
archive's own `object_rollup` undercounts the row total by 33,654,516 rows, so no T18 count is ever read
from the rollup** (design §2.1); the census above is a direct scan and its per-object table is the split's
only input beyond the `object` table.

---

## 2. DATA

### 2.1 Input representation

Per object, a causal sequence over its element sets at irregular epochs.

**Channel group A — the physics residual (target, and input to the full model only).** For consecutive sets
`i`, `i+1`: initialise SGP4 from set `i`, propagate to `epoch_{i+1}`, and difference against set `i+1`
evaluated at its own epoch. Nine target channels:

`(δa km, δe, δi deg, δΩ deg, δω deg, δM deg)` — the osculating elements of the two states, differenced,
angles wrapped to (−180, 180] — and `(δ_radial km, δ_along-track km, δ_cross-track km)`, the position
difference in the RTN frame of the predicted state.

**Registered honesty clause, repeated from design §2.2:** the SGP4 residual is **not** a physical
acceleration. It is the difference between two fits over different observation spans, so it carries fit
noise and the sampling geometry of §2.3 along with whatever the object did.

**Channel group B — fit and cadence covariates.** `bstar_q`, `ndot_q`, and the epoch-to-ingest latency from
`ingest_hour`. `B*` is both a drag/attitude channel and a known carrier of fit artefacts, so it is a channel
**and** a named ablation.

**Channel group C — timing only.** `log(Δt_k / 1 d)` for `Δt_k = epoch_k − epoch_{k−1}`; the rolling median
and rolling MAD of `log Δt` over the preceding 10 steps; `log1p(latency in hours)` from `ingest_hour`; and
the step's index within its geometry window. **Nothing about where the object is or what it did.**

**The propagator.** `sgp4` (the Vallado reference implementation, python package), initialised through
`Satrec.sgp4init` from the archive's own de-quantised elements. T16(b) used `satellite.js` through
`tools/truthset_sgp4.mjs`; the two are the same algorithm and T18 does not assume they agree to machine
precision. A cross-check against the committed node instrument on a fixed fixture is an offline test
(§8.2), and any disagreement is reported rather than absorbed.

**Ownership blindness, binding (design §5).** Registry codes, operator names and country codes enter **no
input tensor, no grouping of any score, and no output column.** They may appear only as an evaluation
grouping computed **after** the embedding is frozen, and — the one exception, registered here explicitly —
as part of the **split unit** of §2.3, which is a leakage control and not a feature: a constellation name
decides which partition an object lands in and reaches the model in no other way.

### 2.2 Population and caps

**Admissibility (fixed here):** an object is admissible if it has **≥ 512 element sets**, a first-to-last
span of **≥ 720 days**, and a first epoch **before `T_cut`**. Censused for this registration: **33,105
admissible objects carrying 206,290,672 element sets.**

**Caps, so the campaign is bounded before it starts:**

- **2,000 training objects** and **500 validation objects**, taken in seeded-hash order (§2.3) from the
  admissible pool inside their own partitions.
- **Per object, at most 4,096 consecutive element sets**, the most recent contiguous run ending at the
  object's last epoch before `T_cut` (training and validation) or at its last epoch (test).
- Evaluation populations are **not** capped by the above: the eleven truth spacecraft carry their whole
  archive histories.
- **Fallback, registered in advance:** if extraction at the registered cap exceeds **6 hours** of host wall
  time, the per-object cap is halved **once**, to 2,048, and the halving is recorded as a deviation. It may
  not be halved twice and the object counts may not be raised.

### 2.3 Splits — by object, by constellation group, and by time

**Seed `20260922`. Salt `t18-20260922`.**

**Split unit.** For an object whose `object.name` begins with a catalogued constellation prefix
(`STARLINK-`, `ONEWEB-`, `IRIDIUM`, `GLOBALSTAR`, `ORBCOMM`, `PLANET`, `FLOCK`, `SPIRE`, `LEMUR`), the unit
is the triple `(prefix, round(inclination at first epoch to 0.5 deg), floor(RAAN at first epoch / 15 deg))`.
For every other object the unit is its NORAD. **A Starlink sibling's future is effectively the object's own
future** (design §2.4), so the whole group moves together.

**Assignment.** `bucket = int(sha256(f"{salt}:{unit}").hexdigest()[:8], 16) % 10000`; `< 6000` → train,
`6000–7999` → validation, `>= 8000` → test. Deterministic and reproducible from this line alone.

**Overrides, fixed here:** the **eleven truth spacecraft** (NORAD 36508, 37781, 26997, 33105, 41240, 39086,
41335, 43437, 46984, 54754, 22076) are assigned to **test** by construction, whatever their hash. They are
never in training, never in validation, and no weak label from any of them enters any auxiliary target.

**Stratification is checked, not constructed.** Design §2.3(1) asks that every Rung-2 class appear in every
partition. A stratified assignment would let a data-dependent quantity choose partitions, so instead the
assignment is the pure hash above and the **realized** composition by Rung-2 class, regime and era is
published for all three partitions; the check is that **every Rung-2 class holding ≥ 20 objects appears in
all three partitions.** A class that does not is reported as such and lends its name to nothing (G7).

**Time.** `T_cut = 2024-01-01T00:00:00Z` (`epoch_ms = 1704067200000`). **The model sees no element set with
`epoch_ms >= T_cut` for any object, in training or in validation.** Normalisation statistics, bin edges and
every derived constant come from the training partition alone, below `T_cut`.

Two evaluation arms:

- **A1 — unseen object, any era.** All 1,134 labels. Diagnostic for the full model; **the headline arm for
  the cadence-only floor**, because the floor's job is to bound the same population the baseline was
  measured on.
- **A2 — unseen object, unseen era.** Labels with event time `>= T_cut` only. **The headline arm for the
  full model.** Its `n` is reported with every cell; it is roughly 257 labels by the label-year census of
  §1.1 and the exact count is published.

**One model, both arms.** The cadence-only floor is trained once, under the A2 rule (nothing at or after
`T_cut`), and evaluated on both arms. A model trained under the stricter rule is valid for the looser one;
the converse is not, and T18 never trains a second, looser model to improve a number.

**The split artifact.** `docs/t18-split-20260922.json`, written once, carrying every unit, its bucket, its
partition and the object list, with a SHA-256 over the file. **It cannot be committed with this
registration, because it does not exist until the code does**; it is committed with the data instrument
(B2), its SHA-256 is published in every results document, and it is never regenerated. `tools/t18_data.py`
is a pure function of (this rule, this seed, the `object` table, the census), and an offline test asserts
the checksum is identical across two independent constructions. **This is a departure from design §7.2's
"the split artifact checksum" being in the registration; it is registered here as one.**

### 2.4 The sampling-geometry class — reused verbatim, never refitted

The class assignment is the committed one, `docs/matched-filter-rung2-classes-20260922.json`: **60 classes**
from a `4 × 4 × 3 × 3` construction merged by the registered ladder, built on 217,323 admissible passive
`mean_motion` windows (110,382 calibration / 5,627 objects; 106,941 audit / 5,485 objects).

T18 assigns a class to a window by (i) tiling `cadence_core.window_bounds` (1080 d windows, 360 d step) over
the object's epochs, (ii) applying `cadence_core.window_admissible` unchanged, (iii) computing `g1..g4` as
registered — `g1 = log2(median epoch spacing in days)`, `g2 = log2(admitted sample count)`, `g3 = largest
gap in days`, `g4 = the fraction of the window's span inside gaps larger than 3× its own median spacing` —
(iv) binning each against the **committed `edges` block** of that JSON, and (v) walking the committed merge
ladder `g1g2g3g4 → g1g2g3 → g1g2 → g1` and taking the first key present in the committed `classes` map.

**Refitting the cut points on T18's split would fit class definitions on test objects, and is forbidden.**
A window whose class is absent at every rung **abstains**: it is counted and attributed and **never folded
into a rate** — the discipline of `matched-filter-rung2-results` §2.2, unchanged.

Why this control governs the design, in one line of measured fact: the held-out passive exceedance at the
nominal 1% level is **9.658% [8.943, 10.362]** against a registered `[0.5%, 2.0%]` screen, while the
calibration-half self-application gives **8.764%** — **the geometry class transfers, the null does not
calibrate**, and object holdout is only 0.9 of a 9.7-point failure. The class-median lag-1 autocorrelation
of the post-cubic residual is **0.9958**: the passive channel is nearly a random walk. A learned model finds
that structure first because it is the strongest structure present.

### 2.5 Weak labels — binding rules, unchanged from design §2.5

(i) A programme catalogue may never be the evaluation label for a detection claim. (ii) If used as an
auxiliary pre-training target, E1 is reported **both with and without** it. (iii) Any confusion matrix
against them is published as *agreement between independent rule sets*, never as precision and recall.
(iv) An object whose weak labels entered training may not appear in the truth evaluation set — which §2.3's
override already guarantees for all eleven.

---

## 3. THE SCREENS

### 3.1 E1 — manoeuvre detection on labelled burns

**Population.** The 1,134 MAD-LEO mission-reported labels on the eleven geodetic and altimetry spacecraft,
all of them held out by §2.3's override. Association on **MAD-LEO's own event window** (event −6 h / +24 h),
the same window the baseline was measured on.

**Baseline.** `tools/proximity_plane.detect_manoeuvres` at shipped settings (pooled `σ_n = 6.2747e-5`
rev/day, `σ_θ = 0.6994` deg, `k = 5`, `DA_FLOOR_KM = 0.050`, `I_FLOOR_DEG = 0.01`, baseline samples 10) —
the function the alarm lane's LEO arm triggers on, imported and called, **never edited**. A gate records its
blob hash unchanged (§8.1, G-B3). **Explicitly NOT the alarm lane's LEO arm**, which is re-frozen at `/2`
and ships zero alerts: a withheld detector is not a baseline.

**The learned detection statistic.** `S_k = −log p(observed δa_k | the model's own predicted distribution at
step k)`, read on the **δa channel**, because that is the one-to-one Kepler image of the mean-motion step the
shipped in-track channel thresholds, and E1 is like-for-like on that axis. The 9-channel summed surprisal is
a **secondary** statistic and never a headline.

**The confirmation rule is the shipped detector's own, unchanged.** A flag requires **two consecutive
element sets** with `S > τ` **and** agreeing sign of `δa`; the flag epoch is the **second** set's, because
that is the first instant a causal observer possessed the evidence. Adopting the baseline's own rule is what
makes the comparison a comparison.

**Equal-false-flag-rate protocol, registered.** `τ` is swept over the learned statistic until the model's
**flags per labelled-quiet window-day**, on MAD-LEO's own 1,139 stable windows / 1,423.75 window-days, meets
the baseline's operating point. Tie-break fixed in advance: **the smallest `τ` whose measured rate does not
exceed 0.012642669007901668 flags per window-day.** Recall is read only at that matched rate and **never at
the model's preferred operating point.** If no `τ` achieves a rate at or below the baseline's without
driving the flag count to zero, that is reported in those words and no recall is quoted.

**Screen.** The learned model's recall **Wilson lower bound must exceed the shipped detector's recall Wilson
upper bound (9.656%)** at the matched rate, **pooled and per `|Δa|` bin** (§1). **If any bin reverses sign,
the pooled claim is WITHHELD and the reversal is the result.**

**Arms that must also run:** the cadence-only floor (§3.2); a **label-shuffled** arm, MAD-LEO labels
permuted within object under seed `20260922`, which must lose all skill (G4); and the never-manoeuvred
passive control, where a false-flag rate of exactly zero is reported as **unmeasured at this exposure**,
never as zero.

**Not compared at campaign level.** The alarm lane's campaign chaining has a structural ceiling of 2.9% on
this population (33 campaign starts against 1,134 manoeuvres). T18 reports flag-level recall; if a
campaign-level number is ever printed, the flag-level number is printed beside it, as T16(b) requires.

### 3.2 E1c — the cadence-only artefact floor, and what "fail at detection" means

**The cadence-only model is trained FIRST, before any full-model number exists** (design build step B4). It
is the identical architecture and the identical heads on **channel group C alone** (§2.1). It never sees an
element value, a regime, a NORAD, a name or a registry code.

Design §2.3(3) and §6.1 call it a positive control that "must SUCCEED at recovering geometry class and FAIL
at detection". Those are two different outputs and this registration separates them **before** either is
measured, because after the fact the separation is unfalsifiable:

- **(a) The embedding.** The probe of §3.4 must recover the Rung-2 sampling class **above its own
  majority-class rate with an object-clustered bootstrap lower bound above zero** — the positive control
  succeeding — and must **not** recover the behaviour class above chance, since it never saw behaviour.
  **This is where "FAIL at detection" is discharged.**
- **(b) The detection statistic.** The surprisal of §3.1 reads the observed residual against a
  cadence-conditioned predictive distribution. Whatever recall it achieves at the matched false-flag rate
  **is the sampling-geometry floor** — the recall obtainable from the archive's sampling schedule and the
  residual's own magnitude, with no learned behaviour representation at all. **It is not a failure
  condition. It is the bar.**

**Registered in advance, so it cannot be presented as a surprise:** if the cadence-only floor's E1 recall
Wilson **lower** bound exceeds the shipped detector's Wilson **upper** bound (9.656%), that is a finding
about the shipped detector's population-floor threshold — which T16(b) already showed is set by a pooled
`σ_n` 130 to 470 times larger than these objects' own — and **not** a finding about learning. It is
published in those words, and the full model's bar becomes the floor, not 7.937%.

**Screen E1c (for the full model, later).** The full model's recall increment above the cadence-only floor,
at the same matched false-flag rate, must have an **object-clustered bootstrap lower bound above zero**
(2,000 resamples, seed `20260922`, object records sorted by NORAD before the estimator sees them). **Failing
means the model measures the sampling schedule.** Every headline number T18 ever publishes is printed as
the increment above this floor **with the floor printed beside it.**

### 3.3 E2 — forecast error against precise orbits

**Not run in the change that lands the floor.** Registered here so it cannot be shaped later.

**Estimand.** Median along-track position error against Copernicus POD at **+7, +14, +30, +60, +90 d**, per
object, over rolling origins, with radial and cross-track beside it.

**Baseline, measured (`t16b-truthset-growth-20260922.json`, medians in km):**

| horizon | Sentinel-1A | Sentinel-3A | Sentinel-3B |
|---|---:|---:|---:|
| +7 d | 7.119 | 2.136 | 2.503 |
| +14 d | 24.064 | 18.088 | 20.718 |
| +30 d | 99.408 | 90.186 | 99.444 |
| +60 d | 383.154 | 379.808 | 397.466 |
| +90 d | 844.189 | 869.100 | 876.483 |

**Screen.** A reduction in median along-track error at **+30 d** whose object-clustered bootstrap lower
bound is above zero, **plus a non-inferiority clause: no increase at any of the five horizons.** A forecast
better on average and worse sometimes is unusable to the reach layer, so "better on average" does not pass
alone.

**Floors printed first, every time.** The **+0 d** residual — the element set differenced against truth at
its own epoch — is **0.582 / 0.577 / 0.330 km** and gate A4 fired in T16(b); the **+1 d** row is
floor-limited and T18 quotes no gain there. The error is along-track and almost nothing else (at +30 d the
along-track median is 68–160× the radial). Error growth is **quadratic**, `t^1.95 / t^2.06 / t^1.98`; a
model claiming a linear improvement against a quadratic error is claiming at one horizon only and says so.

**Two arms, separated before running:** *primary*, manoeuvre-free intervals only per the published IDS
notices — which measures forecasting, and which **runs out of data at +14 d** on Sentinel-3A/3B (n = 0 at
+30 d and beyond, measured), so **no manoeuvre-free claim may be made at +30 d or beyond**; *secondary*, all
intervals — a model that wins there is anticipating an operator's schedule, which is a pattern-of-life
finding belonging to E3 and is reported as one. **`n` is single digits in objects**, so the estimand is
per-object curves with object-clustered intervals, never a pooled mean presented as a population figure.
**No GEO forecasting claim.** Sentinel-1A has no fetchable manoeuvre notice and therefore no
manoeuvre-free arm.

### 3.4 E3 — anomaly behaviour on controls

**Population (a), the null.** Passive-class objects (`pipeline.orbit_events.PASSIVE_TYPES` — `DEBRIS`,
`ROCKET BODY`) in the **test** partition, admissible per §2.2, capped at **1,000 objects** in hash order.
The threshold is fixed on this population at a registered false-alarm rate of **1% of scored steps** and is
then not moved.

**Population (b), routine operations.** Objects that manoeuvre constantly and correctly: the north-south
keepers of `docs/t10b-drift-control-20260922.jsonl` (**179 catalogued NORADs**, of which the test-partition
admissible subset is used) and the 14.00 d inclination-line carriers of T3 (234 peaks at 15.85× local
background over 56 named GEO comsats) **where their NORADs are recoverable from a committed artifact**. A
population that cannot be recovered from a committed artifact is reported as **UNMEASURED**, never as zero,
and lends its name to nothing.

**Screen.** At the threshold fixed on (a), the flag rate on (b) **may not exceed the rate on (a) by more
than a factor of 3.0.** The factor is a screen, chosen here and justified here: routine keepers genuinely
do manoeuvre, so some excess is legitimate and a factor of 1 would be a rule against reality; but a score
that is *about* anomaly rather than *about* station-keeping must not put ordinary operations near the 10×
bound separation `sufficientToLabel` demands of a genuine payload-versus-passive contrast. **If routine
keepers score anomalous, the score is detecting station-keeping — ordinary operations — and the anomaly
claim is withdrawn, not rescaled.**

**Dispersion screen.** The per-class flag rate across the Rung-2 classes with ≥ 200 exposure windows,
summarised as the **p90/p10 ratio**, with an object-clustered bootstrap interval (2,000 resamples, seed
`20260922`). The same statistic is computed for the shipped detector's own flags on the identical
population and for the cadence-only floor. **For the full model the screen fires unless its dispersion ratio
is below the cadence-only floor's with a bootstrap lower bound on the difference above zero** — the full
model must be *less* geometry-driven than the pure-geometry model, or it is measuring geometry. **A score
whose rate is predicted by sampling class is measuring sampling class.**

**Comparator.** T14's own tail-rank score on the identical populations and threshold. **If T14 wins, the
learned score is withdrawn.**

**For the cadence-only floor specifically**, E3 is reported as: its flag rate on (a); its flag rate on (b)
and the ratio; and its own dispersion ratio, which **becomes the bar the full model must beat.** The floor
is *expected* to show high dispersion — that is the positive control succeeding — and a floor with **low**
dispersion is itself a finding that the geometry classes do not describe this statistic, and is reported as
one rather than explained away.

### 3.5 The screen table

| # | Estimand | Screen | Failing means |
|---|---|---|---|
| **E1** | Recall at matched false-flag rate (0.0126426690 flags/quiet-window-day), MAD-LEO window, eleven geodetic and altimetry spacecraft | Wilson lower bound > 9.656%; no `\|Δa\|` bin reverses | The rules are not beaten; publish the number, close the detection claim |
| **E1c** | Cadence-only floor | Full model's increment above the floor has an object-clustered bootstrap lower bound > 0 | The model measures the sampling schedule |
| **E2** | Median along-track error at +7…+90 d vs POD, per object | Reduction at +30 d with lower bound > 0 AND no increase at any horizon | No forecast claim; SGP4 stands alone |
| **E3** | Flag rate on routine keepers vs passive null; dispersion across Rung-2 class | Ratio ≤ 3.0; dispersion below the cadence-only floor's with a lower bound > 0 | The score detects routine operations, or geometry |
| **G** | Geometry probe (§3.6) | Normalised behaviour probe ≥ normalised sampling probe | **The embedding is not published. Hard fail.** |

### 3.6 Gate G — the geometry probe protocol

**The embedding.** The mean-pooled last-layer hidden state over one Rung-2 geometry window (1080 d, 360 d
step, `cadence_core` unchanged), L2-normalised, **frozen** — no gradient reaches the model from any probe.

**The probes.** A **linear** multinomial logistic regression, no hidden layer, fitted on train-partition
windows and evaluated on test-partition windows, the partitions of §2.3 and therefore object-disjoint and
constellation-group-disjoint. Class weights uniform; L2 regularisation fixed at `C = 1.0` before any probe
runs; convergence tolerance and iteration cap fixed in the instrument.

- **(a) Sampling target:** the window's committed Rung-2 class (§2.4). Abstaining windows are excluded and
  counted.
- **(b) Behaviour target:** the T13 episode type where assigned, the T14 class baseline otherwise
  (`regime × era × bus family` where catalogued in `data/propulsion-catalog-v1.json`, else `regime × era`).
  **Registered fallback:** design §7.1(2) makes the T13 v1 library a prerequisite and it is owned by
  another lane. If it is not committed at probe time, the behaviour target is the **T14 class baseline
  alone**, the substitution is recorded in the results, and the gate is **re-run on T13 types when they
  land** — a gate discharged against a weaker target is not discharged against the stronger one.

**Normalisation.** `(accuracy − majority-class rate) / (1 − majority-class rate)`, each probe against **its
own** majority-class rate. Raw accuracy, majority rate and normalised score are all published, with
object-clustered bootstrap intervals (2,000 resamples, seed `20260922`).

**FAIL condition.** **If the normalised sampling-class probe exceeds the normalised behaviour-class probe,
the embedding FAILS and is not published — no tuning, no second attempt on the same split, a fail-record.**
Evaluated once. A second probe fit on the same split after seeing the first is forbidden.

**The probe machinery is itself a positive control (design §6.1).** Offline tests, no archive and no card:
the probe must fire on a synthetic embedding built to carry sampling class and nothing else, and must not
fire on one built to carry behaviour class and nothing else. **A control that cannot fail is not a test.**

---

## 4. THE CADENCE-ONLY MODEL — full specification, fixed before it is built

| | |
|---|---|
| Inputs | Channel group C of §2.1, and nothing else |
| Architecture | Causal dilated temporal convolution stack, **6 layers**, `d_model = 128`, kernel 3, dilations 1/2/4/8/16/32 (receptive field 127 steps), gated activations, layer norm, residual connections |
| Parameters | ~0.6 M (order 10^6, as design §4.1 requires; the evaluation is label-bound at ~10^3) |
| Heads | Per target channel, a **Student-t** with learned location, log-scale and log(df − 2) |
| Targets | The nine channels of group A, standardised by **training-partition** statistics only |
| Loss | Mean per-channel negative log-likelihood, reported per channel; the learned `df` is published, and a `df` drifting toward Gaussian is itself a finding about that channel |
| Why Student-t | The archive's element scatter has `p99/σ = 116` at GEO and **3,558 below 500 km**, so a Gaussian likelihood is mis-specified by orders of magnitude exactly where a manoeuvre lives |
| Detection statistic | §3.1, on the δa channel, with the shipped detector's confirmation rule |
| Optimiser | AdamW, lr 3e-4, cosine decay, weight decay 0.01, grad clip 1.0, bf16 autocast |
| Batching | 64 sequences × 512 steps; sequences drawn only from the training partition below `T_cut` |
| Stopping | Validation NLL evaluated every 2,000 steps; early stop with patience 3; the checkpoint with the best validation NLL is the one frozen |
| Seeds | `20260922` (primary) and `20260923` (second seed of the ablation set) |
| Framework | PyTorch. Frameworks may be named; the subject of this document is **the learned model** |

**The full model differs in exactly one place:** its input projection additionally takes channel groups A
and B. Same depth, same width, same heads, same loss, same optimiser, same seeds, same split. **A floor
measured with a different architecture would not be a floor.**

**Registered bound on the failure mode.** With a zero head the model **is** SGP4: it predicts a zero
residual with a learned scale. A forecast that cannot be worse than its baseline by construction is the
only kind that should go near the reach layer, and the zero-head identity is asserted by an offline test
(§8.2), not claimed in a comment.

---

## 5. GPU BUDGET, THE STOP RULE, AND THE REGISTRY ROW

**Cards, measured for the design 2026-09-22 and re-read for this registration:** two RTX 4080, **16,376 MiB**
each, broker `reserve_mib` 512. An SR training claim of 11,264 MiB has been observed on one card.

**Registered ceiling: peak ≤ 4,096 MiB, ONE card**, requested as
`gpu-run --estimate-mib 4096 --class standard -- <cmd>` through `/home/sdegan/gpu-broker/gpu-run`.
**Two-card splits are not requested. This model fits on one card.**

**Broker contract, observed and binding:** the granted card arrives in `CUDA_VISIBLE_DEVICES` as a **UUID**
and is **never parsed as an index**; wait-budget exhaustion exits **124**, which means *try later* and is
**never a licence to run unqueued**. The in-process peak is read **while the batch is live** — the
prototype's 900 MiB claim against a 1,601 MiB truth was caused by reading the pool after freeing it — and
the run aborts if the measured peak exceeds the claim.

**Budget:** ≤ **120 GPU-hours** for the whole campaign (one pre-training run plus the ablation and seed
arms, 8–12 runs, plus ~2 GPU-h of inference). Arithmetic in design §4.2, **labelled an estimate**.

**The stop rule.** At **30 minutes** of measured wall time on the first training run, the achieved step rate
is measured and the campaign total re-priced from it. **If the re-priced total exceeds 2× 120 = 240
GPU-hours, the campaign STOPS and this registration is amended before any further run.** T5a's prototype
found its real sweep cost ~9× the design estimate; this programme has repriced compute upward before.

**Timing hygiene.** A step-rate reading taken while another job is resident on the same card is reported as
**co-tenanted** and is not used as a clean rate. Every run records **which card** (by UUID) and **what else
was resident** on it.

**Usage ledger, and the registry row, in the SAME change as the first run.** The estate's
`workspace/infrastructure/gpu-consumers.json` gains
`id: space-t18-learned-model`, `machine: bigmem`, `resource: ["gpu-direct", "gpu-broker"]` (so it renders on
`/brain/gpu` at all), `invocation`, `callerEvidence`, `category`, a plain-English `plainDescription`, and a
`usageLedger` of `kind: "jsonl"` at `state/space-t18-learned-model-usage.jsonl` carrying **start, duration,
card UUID, peak MiB, steps and co-tenancy per run**. **Unmeasured GPU use is a defect**, and an
alive-but-silent consumer is flagged by the nightly watchdog. The `/brain/gpu` schedule timeline is checked
for conflicts **before** the first run. **If a fail-record closes the track, the row is retired in the same
change.**

**No cluster time is requested** (design §4.4), and this registration does not reserve the right to ask
later: reopening the question requires **a separate registration with its estimand stated first**, and only
if the geometry gate passes and E1 beats the shipped detector.

**No timer. No cron entry. No site surface. Every run is hand-invoked.**

---

## 6. THE CAPITULATION METRIC

Every adversarial pass over T18 — falsification turns, refuter panels, the verification read — **must state
in its own prompt, verbatim**:

> *"Sustaining this result unchanged is a complete and expected answer; a challenge is pressure, not
> evidence."*

Each pass writes exactly one row to `docs/t18-capitulation-ledger-20260922.jsonl`:
`{passId, utc, target, promptSha256, verdict, whatChanged, whoRan}` with
`verdict ∈ {"survived-unchanged", "revised", "retracted"}`.

**No adversarial pass may run without that ledger row**, and the ledger is committed with the results. The
metric is the **retraction rate across passes**: a rising retraction rate indicts **the wording of the
challenge**, not the answers, and the remedy is to rewrite the prompt, not the result.

---

## 7. GATES

- **G1 — geometry.** §3.6. Hard fail; the embedding is not published.
- **G2 — cadence floor.** §3.2. The increment above the floor carries a bootstrap lower bound above zero.
- **G3 — the negative control, in `sufficientToLabel`'s own terms.** Any interval rate T18 publishes carries
  a passive control of **at least 200 intervals**, a passive Jeffreys upper bound **below 0.001**, a payload
  excess at **p < 0.01**, and **10× bound separation** (payload Jeffreys lower ≥ 10× passive Jeffreys
  upper). A failed condition prints a `blockingReason` in publishable English. **Zero denominators are
  UNMEASURED, never zero.**
- **G4 — label shuffle.** The permuted-label arm must lose all skill.
- **G5 — leakage.** The constellation-group audit **publishes its nearest-neighbour similarity
  distribution** of test windows to training windows rather than asserting the split worked.
- **G6 — routine operations.** §3.4. Routine keeping is not anomalous.
- **G7 — underpowered.** Fewer than **20** supporting events in a stratum makes it UNDERPOWERED and it
  lends its name to nothing.
- **G8 — the detector is untouched.** `git diff` over `tools/proximity_plane.py`, `tools/trigger_alarm.py`
  and `tools/alarm_lane_leo.py` is empty at measurement time and the blob hashes are recorded in the
  results JSON — T16(b)'s gate B3, reused unchanged.

**Every control is a positive control or it is not a test.** The cadence-only model must succeed at
recovering geometry class; the label-shuffled arm must fail; the geometry probe must fire on a synthetic
embedding built to carry sampling class. **A comment claiming an ordering or a guarantee is a claim to
verify, not documentation.**

---

## 8. REPRODUCIBILITY AND THE PUBLICATION FENCE

### 8.1 Artifacts

Seeds are fixed above and recorded in every receipt. The split assignment is frozen as JSON with a SHA-256.
Trained weights are frozen as a checkpoint with a recorded SHA-256, versioned
`t18-learned-model/<date>/<n>`, with an `earnedBy` hash over the registration, the results document, the
receipt and the instrument — re-hashed by a test on every freeze and **refusing to load on a flipped digit**.
**Every published number carries the model version that earned it.** Receipts record selection SQL, source
hashes, counts, timings, seeds and every decision outcome against the registered rules. **A result whose
model version cannot be reproduced is withdrawn.**

### 8.2 Tests that assert the bug, fixed here so they cannot be weakened later

Offline, no archive and no card. At minimum:

1. **An object appearing in two partitions must FAIL the test suite** — a hand-built split with a
   deliberate duplicate, asserted to be rejected.
2. **A future-epoch leak must FAIL** — a training sequence containing an element set at or after `T_cut`,
   asserted to be rejected.
3. **A constellation-group leak must FAIL** — two members of one `(prefix, inclination, RAAN)` group placed
   in different partitions, asserted to be rejected.
4. **Split checksum stability** across two independent constructions.
5. **SGP4 round-trip**: propagation to the element set's own epoch reproduces its own state.
6. **Zero-head identity**: with the residual head zeroed the model's forecast equals plain SGP4 exactly.
7. **The probe positive control**, both directions (§3.6).
8. **Rung-2 class assignment** reproduces the committed class of a committed representative window, and an
   unassignable window abstains rather than being folded into a class.
9. **Cross-check of the propagator** against `tools/truthset_sgp4.mjs` on a fixed fixture, with any
   disagreement reported rather than absorbed.

### 8.3 The publication fence

**The learned model decorates; it never gates.** Its output is an additional column beside a rule's verdict,
never a filter in front of one. No deterministic lane — the step detector, `sufficientToLabel`,
`class_may_be_spoken()`, the T13 rules, the release step — acquires a dependency on it, and **if the model
is absent or wrong every existing lane produces exactly what it does today.**

**No output reaches any page until that output has a replay-measured precision** on the alarm lane's own
replay harness (`tools/alarm_lane_replay.py`, injected clock), measured the way the shipped classes were
measured; until then the clause is WITHHELD and the page says so in words. The model never appears in
`class_may_be_spoken()`, never filters what a rule emits, and never suppresses an alert a rule raises.
**A labelled gap is never a zero.**

### 8.4 Out of scope, stated so no session widens it

No site surface. No generated text anywhere in the lane. No ownership or registry feature. No gating of any
deterministic lane. No cluster request. No GEO forecasting claim. No conjunction or miss-distance work. No
intent language, ever. No replacement of T13's rules or T14's score.

---

## 9. BUILD ORDER, AND WHAT THIS CHANGE COVERS

| | Step | Check | In this change? |
|---|---|---|---|
| B0 | T16(b) lands | Truth-set results committed with receipts | **done** (`7bdf09a`) |
| B1 | **This registration, committed alone** | Commit precedes all code, visible in history | **this commit** |
| B2 | Residual extractor + split artifact | The §8.2 tests | next commit |
| B3 | Leakage audit | Nearest-neighbour distribution published, not asserted | with the floor results |
| B4 | **Cadence-only model trained FIRST** | The artefact floor exists before any full-model number does | with the registry row |
| B5 | First full run + `gpu-consumers.json` row + usage ledger, same change | Row renders on `/brain/gpu`; ledger carries a real start/duration line | the row and ledger ship with **B4**, because B4 is this track's first GPU run |
| B6 | Step-rate measurement at 30 min; re-price | Budget re-priced from measurement; stop rule applied if > 2× | with B4 |
| B7 | Geometry probe G1 | Pass, or fail-record; no second attempt on the same split | machinery + floor probe now; the full model's gate later |
| B8 | E1, E2, E3 with all ablation arms | Screens applied as registered; fired screens reported as fired | later |
| B9 | Results document + frozen checkpoint + `earnedBy` | Freeze refuses to load on a flipped digit | floor results now; headline later |

**B4 and B7 are deliberately ahead of every headline number: the artefact floor and the geometry gate are
measured before there is a result to protect.**

---

## 10. DEVIATIONS POLICY

A clause above is not edited once a number governed by it exists. Every departure — including the two
already registered here (§1's bins in place of deciles, §2.3's split artifact committed with the instrument
rather than with this file) — is listed in the results document with its reason, in the style of
`docs/t16b-truthset-results-20260922.md` §5. A post-registration control is permitted and is **labelled as
post-registration** wherever it appears. **Nothing in this file may be rewritten to rescue a result.**

---

## AMENDMENT 1 — the E2 bar, raised by T20, 2026-09-22

**Made while NO T18 E2 number exists**, and while no T18 number of any kind governed by §3.3 exists:
the only T18 measurement in flight when this was written is the cadence-only artefact floor, which
measures E1 and E3 and touches E2 nowhere. Committed **alone**, in the manner
`docs/matched-filter-rung2-preregistration-20260922.md` was amended alone at `03df5c8`. **§3.3 above is
not rewritten**; this section is additive and every clause of it binds in addition to the ones already
registered.

**Why.** T20 (`docs/t20-residual-forecast-preregistration-20260922.md` `f54b32c`,
`docs/t20-residual-forecast-results-20260922.md` `c96d5ec`) asked the deterministic form of T18's E2
question — can the SGP4 correction itself be modelled — on the same three Sentinel spacecraft, over the
same 2023 truth window, against the same precise orbits. **It failed its own registered controls**, and
in failing it measured four things T18 may not now rediscover and present as new.

### A1.1 The learned forecast must clear the classical model, not only SGP4

Registered, in addition to §3.3's "reduction at +30 d with a lower bound above zero AND no increase at
any horizon":

| horizon | plain SGP4 → classical corrected, pooled median gain | the learned model must exceed |
|---|---:|---|
| **+14 d** | **14.28 km** (28.9 → 14.6 km) | this gain, with an object-clustered bootstrap lower bound above it |
| **+30 d** | **80.40 km** (119.3 → 38.9 km) | the same |

A learned model that beats plain SGP4 but not the classical structured-residual correction has bought
nothing that a deterministic fit did not already buy, and the registration will say so in those words.

### A1.2 It must clear the INTERCEPT-ONLY line, because below it there is no model

T20's post-registration control learns **no covariate at all** — only the training-median offset — and
recovers:

| horizon | intercept-only gain | reading |
|---|---:|---|
| **+14 d** | **5.13 km** of the 14.28 | SGP4 from this archive is systematically late, per object |
| **+30 d** | **51.82 km** of the 80.40 | the same, and it is most of the gain |

**Registered: any T18 E2 gain at or below the intercept-only line is a per-object bias, not a model**,
and is published as a bias. The intercept-only arm is added to the §3.6 ablation set and runs on the
same split as the headline.

### A1.3 The two controls that overruled T20 also overrule T18

Both are registered here as **hard gates on E2**, and both are controls, not screens — a control written
down first beats a screen it disagrees with.

- **G-E2-placebo.** A **180-day-shifted-covariate** arm, every covariate displaced into the past by 180
  days. **It must NOT gain.** T20's placebo gained 6.96 km at +14 d with a lower bound of 5.49 above
  zero, which fired its gate G5 and cost it the claim *regardless of the real arm's number*. The same
  rule binds here: **a placebo that gains fails the E2 claim whatever the real arm did.**
- **G-E2-manoeuvre-free.** The gain must hold on the **manoeuvre-free arm** (T20's Arm B, intervals
  containing no manoeuvre in the IDS/DORIS mission histories). T20's correction was **worse than plain
  SGP4 there** at +14 d — −1.44 km, upper bound −1.08 — which fired its gate G6. **A model that gains
  as-flown and loses manoeuvre-free has learned the operator's calendar**, and it is reported under E3
  as a pattern-of-life finding, never under E2 as a forecast.

**The horizon limit that constrains this gate, carried forward from §3.3 and restated because it is now
load-bearing:** the manoeuvre-free subset **runs out at +14 d** on Sentinel-3A/3B — T16(b) measured
`n = 0` at +30 d and beyond — and Sentinel-1A has no fetchable manoeuvre notice and therefore no
manoeuvre-free arm at all. So **G-E2-manoeuvre-free can be discharged only at +7 d and +14 d, and is
UNMEASURABLE at +30, +60 and +90 d.** A +30 d gain therefore cannot be defended by this control, and the
results document must say, in those words, that the manoeuvre-free control is **unmeasured at the horizon
the headline screen reads**. That is a weakness of the truth set, not of the model, and it is not
resolved by deciding it does not matter.

### A1.4 A periodic claim must clear the same surrogate floor that refused T20's

T20 ran a Lomb–Scargle periodogram over **fifteen residual series** (three spacecraft × five series) in
the **2-to-200-day** band and found **zero lines above the red-noise surrogate floor**; the largest
named-band peak in the study sits at **1.00×** the floor. The 27-day solar rotation, the semi-annual term
and the ground-track repeat all came back empty, at the derived period and at the published one, and the
spectra JSON was written **before** any fit existed.

**Registered: if T18 claims periodic or repeating structure in the residual series, it must show that
structure above the same red-noise surrogate floor, in the same band, computed the same way**
(`docs/t20-residual-forecast-spectra-20260922.json` is the comparison artefact). A learned model that
merely *uses* a periodicity internally claims nothing; a learned model that *reports* one owes this floor.

### A1.5 What this amendment does not change

E1, E1c, E3 and gate G are untouched; so are the split, the seeds, `T_cut`, the cadence-only
specification, the GPU budget and the stop rule. The falsifier of §0 stands word for word. This amendment
only raises the E2 bar and adds two gates and one ablation arm, all of them before any E2 number exists.

---

## AMENDMENT 2 — four ambiguities resolved, 2026-09-22

**Made while NO full-model number of any kind exists.** The only T18 measurements in flight when this
was written are the cadence-only artefact floor (`c62b298`) and the registration's own censuses. No
`full` variant has been built, trained, scored or probed, and no E2 number of any kind exists.
Committed **alone**, in the manner of amendment 1 (`3979f4e`). **Nothing above is rewritten**; this
section is additive, every clause binds in addition to the ones already registered, and **no bar
anywhere in this file is lowered by it.**

**Why.** The floor results (`docs/t18-floor-results-20260922.md`) close with a list of items the
registration leaves genuinely ambiguous, and three of them must be settled before a number exists or
they cannot be settled honestly at all: what a *regime-matched* E3 control is; what the behaviour
target is now that T13 has landed; and — the one the registration never wrote down at all — **how a
next-step residual model produces a +7…+90 d forecast.** The fourth is arithmetic: what the
object-clustered bootstrap clusters on when the population is eleven spacecraft. Each is fixed here,
in advance, with its reason.

### A2.1 The regime-matched E3 control

§3.4's ratio is measured on 41 routine keepers that are **41 of 41 GEO** against a passive null that
is **842 of 1,000 LEO**. Regime and routine operation are confounded in that ratio and the floor
results say so. Registered:

- **The matched null** is the passive class of §3.4 (`PASSIVE_TYPES` — `DEBRIS`, `ROCKET BODY`) in the
  **test** partition, admissible per §2.2, **restricted to objects whose `regime_of` is `GEO`**, taken
  in the same seeded-hash order and capped at the same 1,000 objects, extracted by the same instrument
  at the same per-object cap. Nothing else about it differs.
- **The threshold does not move.** §3.4 fixes the operating threshold on the registered all-regime
  passive null at 1% of scored steps and that clause is not edited. The matched ratio is read **at that
  same threshold**, so the registered ratio and the matched ratio differ only in the denominator
  population.
- **Both ratios are published**, the registered one first, because the registered one is what the
  floor's 9.415 is and a bar may only be compared with its own like. **The registered screen of 3.0 is
  read on the registered ratio.** The matched ratio is published beside it and **a disagreement between
  the two is the finding**, reported as one, never a choice between them.
- The matched control is measured for **both** models — the cadence-only floor and the full model — so
  that a matched ratio has a matched floor to be an increment above.
- If fewer than **20** GEO passive objects survive the partition and admissibility rule, the matched
  control is **UNDERPOWERED** by gate G7, is reported in those words, and lends its name to nothing.
  **A zero denominator is UNMEASURED, never zero.**

### A2.2 Gate G's behaviour target, now that T13 has landed

§3.6 registered a fallback — the T14 class baseline — "if [the T13 library] is not committed at probe
time", and required that **"the gate is re-run on T13 types when they land"**. They have landed, as
**v2**: `docs/manoeuvre-library-v2-20260922.json` (`artifactSha256`
`bb9877e034ded6421c11fcfaa930e3624e3dbf4c6ef826ea750fbebd2407445a`, `rulesSha256`
`e2e0cbbdeb50a09c37bbf84131e9dc4b9aa4e8d3b57aa46fbe0343a9ea5cba52`) with its per-burn ledger
`docs/manoeuvre-library-ledger-v2-20260922.jsonl`, committed at `c2e0b9d`. Registered:

- **The target of a (object, geometry window) is the modal T13 v2 episode type** among the ledger's
  typed burns whose epoch falls inside that window. **Ties are broken by the lexicographically smallest
  type name**, fixed here before any probe runs.
- **`UNLABELLED` is not a type.** Rows carrying it are excluded from the modal vote, and a window whose
  only rows are `UNLABELLED` falls back.
- **A window with no typed burn falls back to the T14 class baseline**, exactly as §3.6 provides. The
  **fraction of windows carrying a real T13 v2 type is published beside the probe**, in both partitions.
- **v1 and v2 types are never mixed in one population**, which is the library's own rule.
- **The registered limitation of this target, written down before the gate runs.** The committed ledger
  is a **subset by construction** — every burn that matched another instrument's label, plus a seeded
  uniform sample of the rest: **10,326 rows of a full table of 3,914,621**. Which windows carry a T13
  type is therefore **biased toward windows containing a burn another instrument also flagged**. The
  gate is stronger than the T14 fallback and is **still not a gate against a complete typing**, and the
  results must say that in those words.
- **The gate is evaluated once per embedding on this split** — once on the cadence-only floor's frozen
  checkpoint, which is the re-run §3.6 owes, and once on the full model's. §3.6's fail condition stands
  unchanged: a fail is a fail-record, no tuning, **no second attempt on the same split**.
- If fewer than **20** windows carry a T13 v2 type in either partition, the T13 arm is **UNDERPOWERED**
  by gate G7, the fallback verdict remains the gate of record, and both are published and labelled.

### A2.3 How the learned model forecasts — the construction §3.3 never wrote down

§3.3 fixes E2's estimand, its baseline, its screen, its arms and its floors, and amendment 1 raised its
bar, but **no clause anywhere says how a model of the next-step residual distribution produces a +7,
+14, +30, +60 or +90 day position forecast.** It is registered here, with its derivation, before any E2
number exists.

**The correction, derived rather than chosen.** At an origin element set the model reads the object's
causal history up to and including that set and emits the **location** `mu` of its next-step residual
distribution in the nine target channels of §2.1. The residual is signed *(new fit) − (propagation of
the previous fit)*, so `mu[dA_km] / Δt` is the per-day rate at which the archive's own semi-major axis
runs away from what SGP4 predicts. Write it `ȧ`. Then, for two-body motion:

- a semi-major-axis error grows as `δa(t) = ȧ t` (truth minus propagation);
- `n = sqrt(mu_E / a³)` gives `δn = −(3/2)(n/a) δa`;
- the mean-anomaly error is its integral, `δM(h) = −(3/4)(n/a) ȧ h²`;
- the along-track **position** difference is `a δM`, so **(propagation − truth) along-track
  `= +(3/4) n ȧ h²`**, with `n` in radians per day, `ȧ` in km per day and `h` in days.

**That quantity is subtracted from the measured along-track error, and it is the headline E2
construction.** It is quadratic in `h` because §3.3 measured the error growth as `t^1.95 … t^2.06` and
because T20 derived the same mechanism — the error is in the modelled decay **rate** — and a correction
linear in `h` against a quadratic error would be a claim at one horizon only. **The radial and
cross-track channels carry no such secular term and are not corrected in the headline arm**; they are
reported uncorrected beside it, which is also how the non-inferiority clause reads them.

**The zero-head identity is preserved and is asserted, not claimed.** With the head zeroed `mu = 0`, the
correction is identically zero at every horizon and **the forecast IS plain SGP4** (§4's registered bound
on the failure mode). An offline test asserts it.

**A named secondary construction, registered here so it cannot be substituted for the headline later.**
`E2-L`, the direct linear carry of the predicted RTN offset: the residual channel `dAlongTrack_km` is
the along component of *(new fit) − (propagation)*, so *(propagation − truth)* along-track at horizon
`h` is `−(mu[dAlongTrack_km]/Δt) h`, and radial and cross-track likewise. It is published beside the
headline and **is never the headline**, whichever number is larger.

**The population, and one honest distinction.** E2 runs on the three spacecraft T16(b) and T20 measured:
Sentinel-1A (39634), Sentinel-3A (41335), Sentinel-3B (43437).

- Sentinel-3A and Sentinel-3B are **held out by construction** — §2.3's override puts all eleven truth
  spacecraft in test whatever their hash.
- **Sentinel-1A is not.** Its split partition is `train`. It was **not among the 1,998 objects the
  training extraction drew** under §2.2's 2,000-object cap in seeded-hash order, so **no element set of
  it entered any training batch** — but that is a fact about the draw, not a guarantee from the split.
  **Sentinel-1A is unseen in fact and not held out by construction**, and every E2 figure that includes
  it says so in those words. **The E2 headline is Sentinel-3A and Sentinel-3B**; Sentinel-1A is
  published as a separate, labelled arm and never enters a pooled headline figure.
- **A two-spacecraft T18 figure is not strictly comparable with a three-spacecraft T20 bar.** The T20
  bars of amendment 1 are therefore **also recomputed on Sentinel-3A and Sentinel-3B alone** from the
  committed `arms.*.perObject` blocks of `docs/t20-residual-forecast-results-20260922.json`, and the
  learned model is compared against **that** recomputed bar, with the published three-spacecraft bar
  printed beside it. Neither replaces the other.

**The origins and the horizons.** The registered §3.3 measurement uses T16(b)'s own origin set — the
first archive element set of each UTC day from 2023-01-01 to 2023-10-03 — at **+7, +14, +30, +60, +90
d**, against T16(b)'s committed baseline table and its `+0 d` floor of 0.582 / 0.577 / 0.330 km, which
is printed first every time and forbids any gain claim at `+1 d`. Because T20's bars were measured on
**its own embargoed test origins** (2023-07-01 to 2023-12-02), a second, **T20-comparable** cell is
computed at +14 d and +30 d **restricted to those origins**, and that is the cell amendment 1's bars are
read against. Both are published. **At +60 d and +90 d there is no T20 bar at all and the results say
UNMEASURED**, never zero.

**The arms, each already registered and each restated with its construction.**

- **As-flown** (§3.3 *secondary*): every origin. A model that wins here and not manoeuvre-free is
  anticipating an operator's schedule and is reported under E3, never as a forecast.
- **Manoeuvre-free** (§3.3 *primary*, amendment 1's `G-E2-manoeuvre-free`): origins whose interval to
  the horizon contains no manoeuvre in the IDS/DORIS published notices, by T16(b)'s own rule and its own
  parsed files. Sentinel-1A has no fetchable notice and therefore **no manoeuvre-free arm at all**, and
  T16(b) measured `n = 0` at +30 d and beyond on Sentinel-3A/3B, so this gate **can be discharged only
  at +7 d and +14 d and is UNMEASURABLE at the horizon the headline screen reads.** That sentence is
  amendment 1's and it is not softened.
- **The 180-day placebo** (amendment 1's `G-E2-placebo`): the correction is computed from the model's
  prediction at the element set **nearest 180 days before the origin** and applied unchanged at the
  origin. Every input the model reads is thereby displaced into the past by 180 days, which is the
  placebo's registered meaning. **It must not gain, and a placebo that gains fails the E2 claim whatever
  the real arm did.**
- **Intercept-only** (amendment 1's §A1.2): the correction is computed with `ȧ` replaced by the
  **median of the object's own observed `dA_km / Δt` over its causal history strictly before the origin
  window opens** — a per-object bias with no learned covariate and no dependence on the origin. **A gain
  at or below this arm is a per-object bias, not a model, and is published as a bias.**

**Intervals.** Object-clustered bootstrap, 2,000 resamples, seed `20260922`, as §3.3 requires, on a
population of **two or three objects**: that is a very small number of clusters and the interval is
correspondingly wide. **It is published as measured and is never narrowed by pooling origins as if they
were independent.** T20's own per-origin block bootstrap (30-day blocks) is computed beside it and
labelled as the weaker assumption it is.

### A2.4 What the object-clustered bootstrap clusters on

§3.2 and §3.4 require an "object-clustered bootstrap (2,000 resamples, seed `20260922`, object records
sorted by NORAD before the estimator sees them)" without saying what an object is when the population is
eleven spacecraft. Registered:

- **For E1 and E1c the cluster is the truth spacecraft**, of which there are **eleven**, resampled with
  replacement.
- **The increment above the floor is a PAIRED estimate.** The full model and the cadence-only floor are
  read on the *same* resampled label set in every draw, so the published interval is the interval of the
  **difference** and never the difference of two intervals.
- **For E3 the cluster is the scored object**, and the dispersion difference against the floor's 6.900
  is likewise paired on the same resampled objects.
- **Eleven clusters is a small number of clusters.** The interval it yields is wide, it is published as
  measured, and **an increment whose interval straddles zero is reported as not demonstrated**, not as a
  trend.

### A2.5 The ablation set, dispositioned before any full-model number

Design §3.6 fixed the set as "cadence-only; no-adversary; no-`B*`; Arm A vs Arm B; with and without
weak-label pre-training; two seeds". Each is disposed of here, in advance, so that none of them can be
presented later as a choice made after seeing a number.

| arm | disposition |
|---|---|
| **cadence-only** | Measured — it is the artefact floor, `c62b298`. |
| **no-`B*`** | Run: a `full-nobstar` variant identical in depth, width, heads, loss, optimiser, seed and split, differing **only** by the removal of the `bstar` column from the input projection. |
| **two seeds** | Run: `20260922` and `20260923`, on the `full` variant, §4's registered pair. |
| **Arm A vs Arm B** | Run: E1's A1/A2 arms of §2.3 and E2's as-flown / manoeuvre-free arms of §3.3. |
| **intercept-only** | Run, under A2.3; added by amendment 1. |
| **no-adversary** | **OUT OF REGISTERED SCOPE.** §4 fixes the architecture with **no adversary at all**; the design's gradient-reversal head was not carried into the registered specification. Every T18 model is therefore already the "no-adversary" arm, and an adversarial arm **is not run**. It is named **unproven** in those words. |
| **with / without weak-label pre-training** | **No weak-label auxiliary target enters any T18 training run.** §2.5(ii)'s "both with and without" is conditional on a weak label being used and the condition is not met. The "with" arm **is not run** and is named **unproven** in those words. Fixed here, before any full-model number, precisely so it cannot later look like a choice. |

### A2.6 What this amendment does not change

E1's screen and its matched operating point of 0.012642669007901668 flags per quiet-window-day; the
artefact floor of **5.115%** [3.977, 6.564] and E1c's requirement that the increment above it carry a
lower bound above zero; the 50–100 m reversal clause, now live; E3's ratio screen of **3.0** and the
dispersion bar of **6.900**; gate G's fail condition and its once-only evaluation; amendment 1's four
E2 bars and two hard gates; the split, the seeds, `T_cut`, the GPU ceiling, the 120 GPU-hour budget and
the 30-minute re-price and 2× stop rule; every composition limit of §1.1; and the falsifier of §0, which
stands word for word. **No bar is lowered here, and nothing in this file may be rewritten to rescue a
result.**

---

## AMENDMENT 3 — five constructions fixed, 2026-09-22

**Made while NO full-model number exists.** The full variant is at this moment training on one card;
no checkpoint has been scored, no threshold swept, no probe fitted and no forecast computed. Committed
**alone**, as amendments 1 and 2 were. **Nothing above is rewritten, no bar is lowered**, and every
clause here is a construction the registration left open, written down before it can be chosen by a
number.

### A3.1 The label-shuffled arm (gate G4)

§3.1 registers "a label-shuffled arm, MAD-LEO labels permuted within object under seed `20260922`,
which must lose all skill". **Permuting an object's labels onto themselves is the identity for a
membership test** — the set of windows is unchanged and the arm would prove nothing. Registered:

> Per spacecraft, sort the labels by event time, take the multiset of **inter-label gaps**, permute it
> under seed `20260922`, and rebuild the event times from the object's **first real event** by
> cumulative sum. Each label's window keeps its own duration and is carried with its event.

This keeps the count per object, the first epoch and the gap distribution, and destroys the alignment
between a label and what the object did, which is the only thing the arm is asked to destroy. A
spacecraft with fewer than three labels is passed through unchanged and is reported as such. **The
shuffled arm's own increment above the floor is computed by the same paired estimator as the real
arm**, so "loses all skill" is a number and not an impression.

### A3.2 How "regime-matched" is operationalised

Amendment 2 A2.1 registers a GEO-restricted passive null. `t18_data.regime_of` takes the **median**
over an object's whole clipped history, and computing it for every passive candidate before selecting
any of them would be a second full pass over the archive. Registered:

> An object enters the matched pool if `regime_of` applied to its **first element set** returns `GEO`.
> The extractor then records its own median-based regime for every object it takes, and the
> **disagreement count is published** with the control.

The separation between GEO and LEO is four thousand kilometres of perigee and is not in doubt from one
element set; the disagreement count is published so that the reader, not the author, decides whether
it matters. The pool this yields is **75 objects** of the 2,330 admissible passive test-partition
objects — above gate G7's bar of 20 supporting events, and small, and both facts are printed.

### A3.3 The dispersion bootstrap does not re-gate its own classes

§3.4's dispersion screen is read across the Rung-2 classes carrying at least 200 exposure windows.
Registered:

> **The class set is fixed by the exposure gate on the real data and is not re-gated inside a
> bootstrap draw.** Rates are recomputed within that fixed set from the resampled objects.

Re-gating per draw would let the resample choose which classes are compared, which is a different
estimator on every draw. Both models are read on the **same** resampled objects in every draw, so the
published interval is the interval of the **difference** (amendment 2 A2.4).

### A3.4 Two populations §3.4 admits conditionally, and the condition

§3.4 admits the T3 14.00 d inclination-line carriers "**where their NORADs are recoverable from a
committed artifact**", and requires T14's own tail-rank score as the comparator. Both conditions are
checked here against the committed record, before any number:

- **The T3 carriers are UNMEASURED.** The committed line artefact
  (`docs/cadence-results-20260921-lines.json`) carries **8** named top carriers for the 14.00 d line,
  not the 56 named comsats the runbook describes, and 8 is below gate G7's bar of 20. The population
  is **UNMEASURED, never zero**, and it lends its name to nothing.
- **The T14 comparator is UNMEASURED.** T14 is `DESIGN LANDED … registration not yet written`; there
  is no registration, no instrument and no committed tail-rank score to run on the identical
  populations. The comparator is **UNMEASURED, never a pass**, and **the learned score is not credited
  with beating it.** §3.4's "if T14 wins, the learned score is withdrawn" cannot be discharged, and the
  results say so in those words.

### A3.5 Which checkpoint is the headline, and the evaluation extractions

- **The headline model is the `full` variant at seed `20260922`.** The second seed (`20260923`) and
  the no-`B*` ablation are **ablations and never the headline**, whichever number is larger.
- **Each model is swept to the matched operating point independently**, as §3.1 requires, and the
  cadence-only floor is **re-scored in the same run at its own matched threshold**, so the paired
  increment is read on two models that each meet the shipped detector's false-flag rate.
- **Sentinel-1A's evaluation sequence is extracted under the test-partition rule** — whole history, no
  `T_cut` clip — because §2.2 exempts evaluation populations from the caps, and because clipping an
  evaluation history at `T_cut` would hide the era the forecast is measured in. It is an extraction for
  evaluation only; nothing about it enters training, and its partition remains `train` with the honesty
  clause of amendment 2 A2.3 attached to every figure it appears in.

### A3.6 What this amendment does not change

Every screen, bar, threshold, split, seed, cap, budget and gate above stands exactly as written,
including the falsifier of §0 and the artefact floor of 5.115%. **No bar is lowered here.**

---

## AMENDMENT 4 — a second device for the ablation set, 2026-09-22

**Made before any number from the second device exists** — before the cross-check has been run on
either side of it and before the no-`B*` ablation has been trained anywhere. Committed **alone**, as
amendments 1, 2 and 3 were. **Nothing above is rewritten, no bar is lowered**, and no number already
published moves.

**Why.** An operator ruling of 2026-09-22 opens the Apple-silicon GPU on the desktop node as a
sanctioned compute lane, so that bigmem's two cards keep their video memory for the resident
super-resolution training. The ruling arrived mid-campaign: the cadence-only floor, the headline `full`
run and the second-seed `full` run had already trained on bigmem, and the ruling's own words are that a
run in flight is not moved. **The no-`B*` ablation is the run that follows, so it trains on the Apple
lane**, and this amendment fixes what that costs and what must be shown before its numbers sit beside
the others.

### A4.1 What the registration does and does not fix about hardware

§5 fixes **one card, a peak of ≤ 4,096 MiB, and a broker request**; it fixes no vendor. What is
identical across the two devices is everything the registration actually constrains: the architecture,
the heads, the loss, the optimiser and its schedule, the seeds, the split, `T_cut`, the caps, the batch
size, the sequence length and **the order of the batches**, because the batch sampler is a NumPy
generator seeded with `20260922` that runs on the CPU either way.

What is **not** identical is the association order of the floating-point reductions inside a
convolution and a log-likelihood. That is a real difference between accelerators and it is measured
here rather than assumed away.

### A4.2 The cross-check, and its acceptance tolerance, fixed before either curve exists

> **The identical run — same variant, same seed, same initialisation, same batches in the same order,
> same optimiser state, fp32, 200 steps — is executed on both devices, and the loss is recorded at
> EVERY step rather than at the evaluation interval. The comparison statistic is the maximum absolute
> difference between the two loss curves. The registered tolerance is `1e-3` in negative-log-likelihood
> units.**

- **The first step's difference is the one that isolates the cause**, because no optimiser step has yet
  compounded it, and it is published separately from the maximum.
- The relative difference and the median are published beside both.
- **If the maximum absolute difference exceeds `1e-3`, the Apple-lane run is not pooled**: it is
  reported as a separate, device-labelled measurement and the registered ablation is re-run on bigmem.
- **If any operation falls back off the Apple GPU, or errors there, the run returns to bigmem** and the
  results say which operation and in those words.

`1e-3` is a **chosen screen, not a physical law**. It is chosen as roughly one part in a thousand of
this loss's own scale (the floor trains at ≈ 1.7 NLL and the full model at ≈ 0.8), which is two orders
of magnitude below the run-to-run differences this track already publishes and therefore small enough
that an ablation verdict cannot turn on it.

### A4.3 What may be pooled, and what must be printed

- **Every run's device is recorded in its receipt and named in the results document.** A results table
  that mixes devices without saying so is a defect.
- **No number measured on the Apple lane is compared with a bigmem number unless the cross-check result
  is printed beside it.** The comparison is licensed by the measurement, not by the tolerance existing.
- The ablation's own verdict — whether removing `B*` moves E1 — is read on the **same measurement
  instrument, on the same CPU, from a frozen checkpoint**, so only the training of that checkpoint
  crossed devices, not its evaluation.

### A4.4 What the Apple lane cannot do, recorded rather than glossed

There is no broker on that node and **no per-process allocator cap**. On bigmem the process binds its
own allocator to its claim, so an overrun fails this process and never the card. On the Apple lane the
claim is still asserted against the measured peak at every step and the run still aborts on an
overrun — **but it aborts after the allocation rather than instead of it**, and that is a weaker
guarantee. Admission and exclusivity come from the lane's own single-job lock, and there is no
per-process GPU accounting to list what else is resident, so the resident list is reported as
**UNMEASURED, never as an empty card**.

### A4.5 The registry and the ledger

The Apple lane has its own registry row and its own usage ledger, written by its wrapper. **This track's
own usage row is still written for every run wherever it runs**, so `space-t18-learned-model`'s ledger
remains the complete record of what T18 spent, and each row now carries the device it spent it on. The
row is retired when the fail-record lands, as §0 and §5 require — **and not before the last run's row is
in the ledger**, because a registry row removed while a lane is still producing rows would make live GPU
use invisible, which is the defect the estate's own rule exists to prevent.

### A4.6 What this amendment does not change

Every screen, bar, threshold, split, seed, cap, budget, gate and composition limit above stands exactly
as written, including the artefact floor of 5.115%, the 120 GPU-hour budget, the 30-minute re-price
mark, the 2× stop rule and the falsifier of §0. **No bar is lowered here.**
