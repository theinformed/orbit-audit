# T18 — a learned model over element-set histories — DESIGN ONLY

**Date:** 2026-09-22. **Status:** design. Nothing here is built, trained, measured or registered; no code accompanies
this document. **Track:** T18 of `docs/research-program-runbook-20260921.md`. **Scope:** one learned sequence model
over the general-perturbation element-set archive, evaluated against ground truth, as a candidate for (a) continuous
low-thrust manoeuvre detection, (b) pattern-of-life representations with a measured anomaly score, (c) a learned
forecast residual on top of SGP4. **Inherits unchanged:** the audit apparatus of `docs/paper-b-draft-20260921.md` §2,
registration-before-results, the vocabulary gate and never-say list, the fuel policy, the ownership-blindness rule of
`docs/kinematic-reach-design-20260922.md` §6, and every reserved operator decision. Every number is quoted from a
committed artifact with its source, or measured for this document and labelled.

## 0. The answer in one paragraph

The archive is a 217-million-row, 68,749-object, 67-year sequence corpus and the programme has never put a learned
model on it. The case for doing so is narrow: there is exactly one place where the deterministic lanes have **no
instrument at all** — continuous low-thrust above the drag regime (`change-ledger-and-reading-design` §1.6). The case
against is this programme's own measurement: **sampling geometry, not behaviour, is the dominant structure in this
corpus** (60 geometry classes transfer perfectly while the null fails to calibrate, §2.3), and **every capacity
enrichment measured here has raised the control more than the treated class** (`t5a-redesign-results` §3.5). A learned
model is the largest capacity enrichment yet proposed, so it rediscovers the artefact first unless the artefact is a
pre-registered control that can fail it. This design therefore makes the geometry control the PRIMARY gate, not a
robustness check: an embedding that separates sampling classes better than behaviour classes is a FAIL and is not
published. The model predicts the **residual after SGP4**, never the raw state; it is judged on three pre-registered
screens against truth that does not come from this programme's own instruments; it is ~10^6 parameters because the
evaluation is label-bound at ~10^3 labels; it costs ~120 GPU-hours on one card beside SR training; it requests **no
cluster time**; and it **never gates a deterministic lane — it may only propose.**

## 1. What this track is, and what it is not

T18 is a **candidate detector** in the sense `paper-b-draft` §2 uses the word — not an upgrade path for T13
(rule-based by design: *"no learned classifier"*), not a replacement for T14's score or the reach layer, not a site
feature. T13's published types are T18's **behaviour-class probe target** (§2.3) and the source of its weak labels
(§2.5); T14's anomaly score is a **competitor measured on T14's own controls** (§3.5), and if T14 wins the learned
score is withdrawn; T5a supplies the populations and the geometry classes; the shipped detectors are the **baselines**
(§3.3); T16(b) is a hard prerequisite.

**The standing constraint, first because it governs everything.** The learned model decorates; it never gates: its
output is an additional column beside a rule's verdict, never a filter in front of one. No deterministic lane — the
step detector, `sufficientToLabel`, `class_may_be_spoken()`, the T13 rules, the release step — acquires a dependency
on it, and if the model is absent or wrong every existing lane produces exactly what it does today (§6.3).

## 2. DATA

### 2.1 The corpus, measured

| | | source |
|---|---:|---|
| Element sets (direct sequential scan) | **217,026,192** | `docs/proximity-leo-20260922-receipt.json` `archive.sequentialScanRowTotal` |
| Distinct objects | **68,749** | same, `extract.objects` |
| Epoch span | **1959-01 → 2026-09** | same, `archive.monthRollupSpan` |
| Objects by regime (overlapping, NOT a partition) | LEO **61,734** / MEO **1,044** / HEO **8,404** | same, `extract.byRegime` |
| Near-GEO objects / rows | **1,768** / **11,626,494** | `docs/proximity-20260922-receipt.json` |
| Store | `/home/sdegan/space-orbit-history/orbit-history.sqlite3`, ~13.9 GB, `element_set` keyed `(norad, epoch_ms)` | same, `archive.path` |

**A trap for the registration.** The archive's own `object_rollup` metadata undercounts the row total by
**33,654,516** rows (`archive.rollupUnderstatesScanBy`, same receipt), so a training-set size read from the rollup is
silently 15% short. Every T18 count comes from a direct scan with its receipt, never the rollup.

### 2.2 The input representation

Per object, a causal sequence of element sets at **irregular** epochs, in two channel groups.

**A — the physics residual (target and primary input).** For consecutive sets `i`, `i+1`: propagate set `i` with SGP4
to `epoch_{i+1}` and express the difference in the orbit frame as `(delta_a, delta_e, delta_i, delta_raan, delta_argp,
delta_M)`, reduced to the registered element units the deterministic lanes already work in (the 1e-4 deg quantum, the
0.010 deg/day drift floor, the 0.05 km in-track floor; `kinematic-reach-design` §5).

**B — fit and cadence covariates, carried explicitly.** `bstar_q` (present in `element_set`; schema verified live for
this document), `ndot_q`, and the epoch-to-ingest latency from `ingest_hour`. `B*` is both a drag/attitude channel and
a known carrier of fit artefacts, so it is a channel **and** a named ablation (§3.6).

**Why the residual and not the raw state — four reasons, the fourth decisive.** (i) SGP4 already carries the
overwhelming majority of the variance, so a model predicting raw mean motion spends capacity relearning secular J2 and
drag and its error floor is set by dynamic range, not by the manoeuvre signal. (ii) An impulsive burn *is* a step in
the residual: the predicted quantity is the quantity the science is about. (iii) The deterministic lanes threshold in
exactly these units, so E1 is like-for-like on one axis. (iv) **The failure mode is bounded: with a zero head the
model IS SGP4** — a forecast that cannot be worse than its baseline by construction is the only kind that should go
near the reach layer. Stated honestly and repeated in the registration: the SGP4 residual is **not** a physical
acceleration but the difference between two fits over different observation spans, so it carries fit noise and the
sampling geometry of §2.3 along with whatever the object did.

### 2.3 The sampling-geometry control — the primary gate, not a robustness check

`docs/matched-filter-rung2-results-20260922.md` §2 is why this is the longest section. Measured there on 217,323
admissible passive `mean_motion` windows (calibration half 110,382 windows / 5,627 objects; audit half 106,941 /
5,485): a registered `4 x 4 x 3 x 3` construction merges to **60 sampling-geometry classes**; held-out passive
exceedance at the nominal 1% level is **9.658% [8.943, 10.362]** against a registered `[0.5%, 2.0%]` screen; and the
**calibration-half self-application gives 8.764%**, statistically the same number on the half the thresholds were
built from. Object holdout costs only **9.3%** of the failure. **The geometry class transfers; the null does not
calibrate.** The class-median lag-1 autocorrelation of the post-cubic residual is **0.9958**: the passive channel is
nearly a random walk. A learned model finds that structure first because it is the strongest structure present. Four
layers of control, in increasing order of how far each may be trusted:

1. **Stratification.** The split (§2.4) is stratified by Rung-2 class, regime and era, so every class appears in
   train, validation and test, and every evaluation is reported **per class and pooled**. The class assignment is the
   committed one (`docs/matched-filter-rung2-classes-20260922.json`), reused verbatim — refitting it on T18's split
   would fit class definitions on test objects.
2. **Adversarial removal.** A gradient-reversal head predicts the window's Rung-2 class from the embedding.
   Registered limitation: adversarial removal frequently fails, and a model that defeats its own adversary has not
   thereby been cleaned. That is why 3 and 4 exist, and why neither is the adversary's own loss.
3. **The cadence-only positive control — the primary artefact measurement.** An identical model trained on the
   **timing channels alone** (the `delta_t` sequence and the fit-latency covariate; nothing about where the object is
   or what it did). Whatever it achieves on E1 and E3 is the **sampling-geometry floor**, and every headline number is
   reported as the **increment above that floor, with the floor printed beside it**. It is a positive control in the
   sense of `tests-that-assert-the-bug`: it must SUCCEED at recovering geometry class and FAIL at detection. If it
   matches the full model's detection score, T18 has measured the archive's sampling schedule and says so.
4. **The geometry probe — a pre-registered FAIL condition.** Linear probes on the frozen embedding predict (a) the
   Rung-2 sampling class and (b) the behaviour class (T13 type where assigned, T14 class baseline otherwise), each
   normalised against its own majority-class rate, with object-clustered bootstrap intervals. **If the normalised
   sampling-class probe exceeds the normalised behaviour-class probe, the embedding FAILS and is not published — no
   tuning, no second attempt on the same split, a fail-record.**

### 2.4 Splits — by object, by time, and by constellation group

- **By object:** disjoint NORAD sets, 60/20/20, seeded hash, stratified as §2.3(1).
- **By constellation group, because object-level is not enough.** Starlink members share a bus, a plane and an
  operations schedule, so a sibling's future is effectively the object's own future. The split unit is the
  **(operator-derived constellation, plane)** group where catalogued, the object otherwise. Build step B3 publishes
  the nearest-neighbour similarity distribution of test windows to training windows rather than asserting the split
  worked.
- **By time:** a fixed `T_cut`. The model sees **no element set with `epoch_ms >= T_cut` for any object**; the test
  arm reads only `epoch_ms >= T_cut`. Two arms: **A1** unseen object / seen era (diagnostic) and **A2** unseen object
  / unseen era (**the headline**). Normalisation statistics, bin edges and every derived constant come from the
  training partition alone. The split assignment is written once to JSON with a SHA-256, committed with the
  registration, never regenerated.

### 2.5 The truth sets, and exactly what each licenses

| Set | Size | Licenses | Does NOT license |
|---|---|---|---|
| **MAD-LEO** (arXiv 2609.08556) | 6,785 Starlink objects, 107 h, **1,134 operator-evidenced manoeuvres** | Recall and false-flag rate **on the MAD-LEO window**; a head-to-head with the shipped detector on those same element sets | Any recall figure for the archive, for GEO, for another operator, bus, era or window. One operator, one bus family, one regime, one 107-hour window |
| **Sentinel-1/2/3 Copernicus POD** (cm-level SP3) + published manoeuvre notices | a handful of spacecraft | Per-object forecast-error curves vs truth at +7…+90 d; the burn-detection floor on those objects | Any population claim. `n` is single digits **in objects**, so the estimand is per-object curves with object-clustered intervals, never a pooled mean presented as a population figure |
| **This programme's own catalogues** (T8a flags, T8d chains, T10b events, T13 types, step-detector candidates) | 10^2–10^5 | Stratification; an auxiliary pre-training target; a published **agreement** matrix | **Nothing about detection** — another instrument's output on the very element sets the model reads, circular by construction |

**Weak-label rules, binding.** (i) A programme catalogue may never be the evaluation label for a detection claim.
(ii) If used as an auxiliary pre-training target, E1 is reported **both with and without** that pre-training, because
agreement with a rule set is agreement, not detection. (iii) Any confusion matrix against them is published in T13's
own wording — *agreement between independent rule sets* — never as precision and recall. (iv) An object whose weak
labels entered training may not appear in the T16(b) truth evaluation set.

## 3. OBJECTIVES AND EVALUATIONS

### 3.1 Objective (i) — self-supervised next-residual prediction

Causal and single-step: given channels up to step `k`, predict the distribution of the step-`k+1` residual. Loss is
heteroscedastic negative log-likelihood with a **Student-t head of learned degrees of freedom**, reported per channel.
Not Gaussian, for a measured reason: the archive's element scatter has `p99/sigma = 116` at GEO and **3,558 below
500 km** (`kinematic-reach-design` §5, "heavy tails rule"), so a Gaussian likelihood is mis-specified by orders of
magnitude exactly where a manoeuvre lives. The learned `df` is published; a `df` drifting toward Gaussian is itself a
finding about the channel. The detection statistic that falls out is the **surprisal** of the observed residual under
the model's own predicted distribution, `-log p` — a proper score whose threshold is set by a *measured* false-alarm
rate on a control population, not by a chosen sigma multiple, which is the discipline the T13 rules already keep by
refusing Gaussian `k·sigma`.

### 3.2 Objective (ii) — a contrastive behaviour embedding per object-window

One embedding per (object, window) over a registered window length. Two arms, fixed before any run. **Arm B
(PRIMARY), behaviour-anchored:** positives are windows from **different objects** in the same T13 episode type, so the
invariance learned is behaviour, not identity. **Arm A (diagnostic), identity-anchored:** positives are disjoint
windows of the **same** object inside one station segment; Arm A is expected to be contaminated — same object means
same sampling class, so identity and cadence are the same shortcut — and it is run precisely to measure how large that
shortcut is, via the §2.3(4) probe. The E3 anomaly score is the embedding's distance to its class baseline, carried in
T14's own units so the two are directly comparable: `max` over dimensions of `-log10(two-sided class tail rank)`,
class = `regime x era x bus family` where catalogued (`data/propulsion-catalog-v1.json`) else `regime x era`,
calibration and application halves exactly as T14 §6.

### 3.3 Evaluation E1 — manoeuvre detection on labelled burns

**Population:** the MAD-LEO window, held-out objects only. **Baseline that must be beaten:** the **shipped step
detector** (`pipeline/orbit_events.py`, production `kappa = 32` with its persistence test) and
`proximity_plane.detect_manoeuvres` on the in-track channel, on the same element sets over the same window.
**Explicitly NOT the alarm lane's LEO arm**, which is re-frozen at `/2` and ships zero alerts because its own passive
control fired at **0.797 of the rate it fires on objects that can manoeuvre** against a design target of 0.001
(`alarm-lane-build` §7): a withheld detector is not a baseline. **Equal-false-flag-rate protocol:** the learned
threshold is swept until its false-flag rate on the never-manoeuvred control equals the shipped detector's on the same
control; recall is compared only at that matched rate, never at the model's preferred operating point.

**Screen (registered):** the learned model's recall **Wilson lower bound must exceed the shipped detector's recall
Wilson upper bound** at matched false-flag rate, reported pooled and **per burn-size decile**; if any decile reverses
sign, the pooled claim is WITHHELD and the reversal is the result. **Arms that must also run:** the cadence-only
floor; a **label-shuffled** arm (MAD-LEO labels permuted within object) that must lose all skill; and the
never-manoeuvred passive control (T8b: **0 events over 18.79M object-days**), where a false-flag rate of exactly zero
is reported as *unmeasured at this exposure*, never as zero (`paper-b-draft` §2.4).

### 3.4 Evaluation E2 — forecast error vs Sentinel POD

**Estimand:** median along-track position error against Copernicus POD SP3 at **+7, +14, +30, +60, +90 d**, per
object, over rolling origins, with cross-track and radial beside it. **Baseline:** plain SGP4 from the same element
set. **Screen (registered):** a reduction in median along-track error at +30 d whose object-clustered bootstrap lower
bound is above zero, **plus a non-inferiority clause** — no increase at any of the five horizons; a forecast better on
average and worse sometimes is unusable to the reach layer, so "better on average" does not pass alone. **Two arms,
separated before running:** *primary*, manoeuvre-free intervals only per the published notices, which measures
forecasting; *secondary*, all intervals — a model that wins there is anticipating an operator's schedule, a
pattern-of-life finding belonging to E3, and is reported as such. **Scope limit, from the certainty doctrine:** no GEO
forecasting claim; the +30 d GEO error is what the object does next, not measurement noise.

### 3.5 Evaluation E3 — anomaly false-alarm rate on controls

**Population (a), the null:** the never-manoeuvred / passive class, where the operating threshold is fixed at a
registered false-alarm rate. **Population (b), routine operations:** the T3 cadence carriers — objects carrying the
14.00 d inclination line (234 peaks at **15.85x** local background, 56 named GEO comsats) and the T10b north-south
keepers (738 manoeuvres over 66 commercial GEO satellites). **These objects are manoeuvring constantly and correctly.
Routine keeping must NOT be anomalous.**

**Screen (registered):** at the threshold fixed on (a), the flag rate on (b) may not exceed the rate on (a) by more
than a registered factor; if routine keepers score anomalous, the score is detecting station-keeping — ordinary
operations — and the anomaly claim is withdrawn, not rescaled. **Dispersion screen:** the anomaly rate may not be a
function of Rung-2 class; the between-class dispersion is reported with its interval, and a score whose rate is
predicted by sampling class is measuring sampling class. **Comparator:** T14's own tail-rank score on the identical
populations and threshold; if T14 wins, the learned score is withdrawn.

### 3.6 The pre-registered screen table, and the ablation set

| # | Estimand | Screen | Failing means |
|---|---|---|---|
| E1 | Recall at matched false-flag rate, MAD-LEO window | Wilson lower bound > shipped detector's Wilson upper bound; no burn-size decile reverses | The rules are not beaten; publish the number, close the detection claim |
| E1c | Cadence-only floor | Full model's increment above the floor has a bootstrap lower bound > 0 | The model measures the sampling schedule |
| E2 | Median along-track error at +7…+90 d vs POD | Reduction at +30 d with lower bound > 0 AND no increase at any horizon | No forecast claim; SGP4 stands alone |
| E3 | Flag rate on routine keepers vs passive null | Ratio below the registered factor; between-class dispersion within its interval | The score detects routine operations, or geometry |
| G | Geometry probe | Normalised behaviour probe ≥ normalised sampling probe | **The embedding is not published.** Hard fail |

**The ablation set, fixed in advance:** cadence-only; no-adversary; no-`B*`; Arm A vs Arm B; with and without
weak-label pre-training; two seeds. All on the same frozen split, all priced into §4.2.

## 4. MODEL SIZE AND COMPUTE

### 4.1 Order of magnitude: 10^6 parameters, and why more buys nothing

A causal sequence model — a dilated temporal convolution stack or a small causal transformer, 4–8 layers, `d_model`
128–256: **roughly 2–6 million parameters.** Not 10^8, not 10^9. Three registered reasons, the first arithmetic.

1. **The evaluation is label-bound at ~10^3.** The largest labelled set the programme will hold after T16(b) is
   MAD-LEO's 1,134 burns; a Wilson interval on recall at `n = 1,134` near `p = 0.8` is about ±2.3 points wide. **A
   model whose advantage is smaller than that interval cannot be demonstrated at all**, whatever its size.
2. **This programme's own measurement of what extra capacity does.** `t5a-redesign-results` §3.5: *"every template
   enrichment measured in this programme raises the control more than it raises the treated class"* — true of the
   sawtooth under both sign conventions, of the step-train and two-burn members, and of the free-phase harmonic power
   sum. §3.2 is the sharpest case: per-object refinement lifted the carrier median **1.81x** and the control median
   **4.33x**, taking separation from **115.006 to 48.069**, because choosing the best of 30 candidates is an order
   statistic that a structureless population collects in full. **A larger model is a larger order statistic.**
3. **Geometry dominates (§2.3).** Extra capacity is spent on the strongest available structure, and here that is the
   artefact.

### 4.2 GPU budget on bigmem's cards, beside SR training

Measured for this document, 2026-09-22: two **RTX 4080, 16,376 MiB each**; broker `reserve_mib` 512; admissible at
read time **14,731 MiB** (card 0) and **11,554 MiB** (card 1). An SR training claim of **11,264 MiB** has been
observed on one card, leaving roughly **4.6 GiB admissible** beside it. **Registered ceiling: peak ≤ 4,096 MiB, one
card**, bounded in-process, requested as `gpu-run --estimate-mib 4096 --class standard -- <cmd>`. Broker contract
observed: the granted card arrives in `CUDA_VISIBLE_DEVICES` as a **UUID**, never parsed as an index; wait-budget
exhaustion exits **124**, which means "try later", never licence to run unqueued. Two-card splits are authorised by
the execution rules but are not requested — this model fits on one card.

**Cost — ESTIMATE, labelled as such, arithmetic shown.** A 3M-parameter model at `6 x params x tokens` FLOP over
~2 x 10^9 residual steps per full pass is ~3.6 x 10^16 FLOP; at a 4080's fp16 throughput and a conservative 15%
achieved utilisation that is **~7 GPU-hours per training run**. One pre-training run plus the §3.6 ablation and seed
arms — **8 to 12 runs** — plus inference over the evaluation sets (~2 GPU-h): a budget of **≤ 120 GPU-hours**. For
scale, T5a's sweep was repriced to ~44 GPU-h and Rung 3 to ~8,860 GPU-h per sweep. **A stop rule, because this
programme has repriced compute upward before:** the T5a prototype found the real sweep cost ~9x its design estimate,
so build step B6 measures the achieved step rate in the first 30 minutes of the first run and re-prices the budget
from it; if the re-priced total exceeds **2x** 120 GPU-h, the campaign stops and the registration is amended before
any further run.

### 4.3 The gpu-consumers.json row and usage ledger — a build step, not a follow-up

T18 is a multi-run campaign, not a one-off hand run, so it owes its estate registry row in the **same change** as its
first training run (B5). The row on the estate's `workspace/infrastructure/gpu-consumers.json` carries the mandatory
fields: `id: space-t18-learned-model`, `machine: bigmem`, `resource: ["gpu-direct"]` (so it renders on `/brain/gpu` at
all), `invocation`, `callerEvidence`, `category`, a plain-English `plainDescription`, and a `usageLedger` of
`kind: "jsonl"` at `state/space-t18-learned-model-usage.jsonl` with start and duration per run — unmeasured GPU use is
a defect, and an alive-but-silent consumer is flagged by the nightly watchdog. The `/brain/gpu` schedule timeline is
checked for conflicts **before** the first run. If a fail-record closes the track, the row is retired in the same
change.

### 4.4 The saved HPC allocation: T18 does not request cluster time

**Registered position: no.** (1) **A sweep cannot certify what the labels cannot resolve** — §4.1(1)'s interval is
±2.3 points, and cluster-scale hyperparameter search buys resolution below that, which nobody may quote. (2) **The
programme has already measured what a big null buys:** Rung 3 at ~8,860 GPU-h per sweep would have bought the
per-object look-elsewhere factor, which the decomposition showed is **not what is broken** (object holdout is 9.3% of
the failure); spending a cluster on the small term is the exact mistake T18 would repeat. (3) **The certainty doctrine
ranks compute fourth**, behind different data (T16), time via the ladder and better-precision data — and records that
the whole-history stacking gain came from a *cheaper* statistic, not a bigger run. (4) **The one thing a cluster could
buy is affordable here:** a 20-seed distribution of the §2.3(4) probe gate — how often the adversary actually removes
the artefact — is ~160 GPU-h and fits on our own cards inside a week. If and only if the geometry gate passes and E1
beats the shipped detector does the cluster question re-open, as a **separate registration with its estimand stated
first**.

## 5. WHAT IT COULD SEE THAT RULES CANNOT

Four hypotheses, each with the measurement that would confirm it and the confound that would refute it. **All four
are ownership-blind. Why ownership is never an input feature:** (i) an ownership-blind model that nevertheless groups
objects by operator is **evidence of a behavioural habit**, whereas a model given the operator label that does the
same is a tautology, and after the fact the two are indistinguishable; (ii) a registry code is a fact about *who*, not
about *what the object did*, and a model handed it uses it as a shortcut for behaviour it should be reading from the
elements, so the finding can no longer be separated from the label; (iii) the operator's standing rule — outputs are
behaviour and measured precision, and any per-nation reading is the reader's to make. Registry codes enter no input
tensor, no grouping of any score and no output column; they may appear only as an **evaluation grouping computed
after the embedding is frozen**.

**H1 — propulsion type from burn signature.** T10a's electric arm was empty (`n = 0`: both detected electric legs
start at `e > 0.76`, so Edelbaum's circle-to-circle form genuinely does not apply, and an eccentric low-thrust
generalisation does not exist in-programme). *Measurement:* cluster the learned per-burn embedding and test whether
the clusters predict a **held-out** propulsion label from `data/propulsion-catalog-v1.json`, on objects whose
catalogue entry was never an input. *Screen:* balanced accuracy with a clustered bootstrap lower bound above the
majority-class rate. *Confound, reported in the same table:* bus family and launch era, either of which would produce
the same clustering.

**H2 — bus-family behaviour fingerprints.** T10b measured bus families running monotone in north-south placement:
Spacebus-4000 `eta = 0.950` at 11 deg, BSS-702 0.955 at 14, A2100 0.931 at 24, SSL-1300 0.876 at 25, Eurostar-3000
0.861 at 32. *Measurement:* with the placement-efficiency feature **removed from the input**, can the embedding
predict bus family above chance on held-out objects? *Screen registered in advance:* **recovering T10b's ordering is
the NULL, not the result** — a claim requires information beyond the known rule.

**H3 — low-thrust campaigns above the drag regime. T18's single most valuable hypothesis, because the programme has
no instrument there at all.** `change-ledger-and-reading-design` §1.6 states the gap: electric raising above the drag
regime has **no onset detector** — `orbit_campaigns.sustained_thrust` declines above 1,400 km apogee by design, and
the step detector saw **91 of SES-12's 2,176 m/s**. *Measurement:* the cumulative surprisal of §3.1 over a sliding
window should rise through a campaign the step detector misses; validate on SES-12-class known raises and on MAD-LEO's
Starlink low-thrust labels, threshold fixed on the never-manoeuvred control. *Screen:* detection on campaigns the step
detector misses, at a passive-control false-flag rate no worse than the step detector's own.

**H4 — operator-level habits, measured ownership-blind.** *Measurement:* leave-one-object-out — does the frozen
embedding of object A's windows predict object B's behaviour better when A and B share an operator than for a matched
control set from other operators in the same regime and era? The operator label only *forms the groups after
freezing*. *Screen:* paired difference with an object-clustered interval. *Confound:* shared bus and shared launch,
which the matched control must equalise on, or the result is H2.

## 6. THE AUDIT

T18 is a candidate detector and passes `paper-b-draft` §2 without modification.

### 6.1 Registered gates

Committed alone, ahead of the analysis code and ahead of every result file, so the ordering is in the repository
history rather than asserted in prose.

- **G1 — geometry.** §2.3(4). Hard fail; the embedding is not published.
- **G2 — cadence floor.** The full model's increment above the cadence-only floor must have a bootstrap lower bound
  above zero.
- **G3 — the negative control, in `sufficientToLabel`'s own terms.** Any interval rate the model publishes carries a
  passive control of at least 200 intervals, a passive Jeffreys upper bound below 0.001, a payload excess at
  `p < 0.01`, and **10x bound separation** (payload Jeffreys lower ≥ 10x passive Jeffreys upper). A failed condition
  prints a `blockingReason` in publishable English. Zero denominators are *unmeasured*, never zero.
- **G4 — label shuffle.** The permuted-label arm must lose all skill.
- **G5 — leakage.** The §2.4 constellation-group audit publishes its nearest-neighbour distribution.
- **G6 — routine operations.** §3.5. Routine keeping is not anomalous.
- **G7 — underpowered.** Fewer than 20 supporting events in a stratum makes it UNDERPOWERED and it lends its name to
  nothing — T13's rule, unchanged.

Every control is a positive control or it is not a test: the cadence-only model must succeed at recovering geometry
class and fail at detection; the label-shuffled arm must fail; the geometry probe must fire on a synthetic embedding
built to carry sampling class. A comment claiming an ordering or a guarantee is a claim to verify, not documentation.

### 6.2 The challenge rule and its capitulation metric

Every adversarial pass over T18 — falsification turns, refuter panels, the verification read — must state in its own
prompt that **sustaining the result unchanged is a complete and expected answer, and that a challenge is pressure, not
evidence**. Each pass writes one row to a `survived-unchanged / revised / retracted` ledger committed with the
results, so a rising retraction rate indicts the *wording of the challenge* rather than the answers. No adversarial
pass may run without that ledger row.

### 6.3 Reproducibility, and the publication fence

Seeds fixed in the registration and recorded in every receipt. The split assignment frozen as JSON with a SHA-256. The
trained weights frozen as a checkpoint with a recorded SHA-256, versioned in the alarm lane's style
(`t18-learned-model/<date>/<n>`), with an `earnedBy` hash over the registration, the results document, the receipt and
the instrument — re-hashed by a test on every freeze and refusing to load on a flipped digit. **Every published number
carries the model version that earned it.** Receipts record selection SQL, source hashes, counts, timings, seeds and
every decision outcome against the registered rules; a result whose model version cannot be reproduced is withdrawn.

The model may propose; it may not gate. **No output reaches any page until that output has a replay-measured
precision** on the alarm lane's own replay harness (`tools/alarm_lane_replay.py`, injected clock), measured the way
the shipped classes were measured; until then the clause is WITHHELD and the page says so in words. The model never
appears in `class_may_be_spoken()`, never filters what a rule emits, and never suppresses an alert a rule raises. A
labelled gap is never a zero.

## 7. ORDER

### 7.1 What must land first

1. **T16(b) — the truth set. Hard blocker.** Without Sentinel POD error growth and MAD-LEO recall there is no ground
   truth, and E1 and E2 are not weak but undefined. T16(a) ingest is registered (`fc7d445`); T16(b) is not yet
   written. **T18 is not registered before T16(b) has results.**
2. **T13 v1 library**, for G1's behaviour-class probe target.
3. The committed Rung-2 class assignment — already in hand.

### 7.2 The registration outline

`docs/t18-preregistration-<date>.md`, committed **alone**, before any code. Contents: the three estimands of §3.3–3.5
with their populations named; the screen table of §3.6 verbatim; the split seed, the split artifact checksum and
`T_cut`; the ablation set fixed so no arm can be added after seeing a number; the gates of §6.1; the stop rule of
§4.2; and the single sentence that falsifies the track:

> **"The learned model adds information" is FALSE if, at matched false-flag rate, its recall lower bound does not
> exceed the shipped detector's upper bound; AND the forecast non-inferiority clause fires; AND the anomaly score's
> flag rate is not separable from Rung-2 sampling class. If all three hold, T18 is a fail-record, the numbers are
> published, and the track closes.**

### 7.3 Build plan, each step with its check

| | Step | Check |
|---|---|---|
| B0 | T16(b) lands | Truth-set results committed with receipts |
| B1 | Registration committed alone | Commit precedes all code, visible in history |
| B2 | Residual extractor + split artifact | Offline tests: SGP4 round-trip; disjointness by object AND constellation group; checksum stable across two runs |
| B3 | Leakage audit | Nearest-neighbour similarity distribution published, not asserted |
| B4 | Cadence-only model trained FIRST | The artefact floor exists before any full-model number does |
| B5 | First full run + `gpu-consumers.json` row + usage ledger, same change | Row renders on `/brain/gpu`; ledger carries a real start/duration line |
| B6 | Step-rate measurement at 30 min; re-price | Budget re-priced from measurement; stop rule applied if > 2x |
| B7 | Geometry probe G1 | Pass, or fail-record; no second attempt on the same split |
| B8 | E1, E2, E3 with all ablation arms | Screens applied as registered; fired screens reported as fired |
| B9 | Results document + frozen checkpoint + `earnedBy` | Freeze refuses to load on a flipped digit; every number carries its version |

B4 and B7 are deliberately ahead of every headline number: the artefact floor and the geometry gate are measured
before there is a result to protect.

### 7.4 Out of scope, stated so no session widens it

No site surface. No generated text anywhere in the lane. No ownership or registry feature. No gating of any
deterministic lane. No cluster request (§4.4). No GEO forecasting claim (§3.4). No conjunction or miss-distance work —
T8b's scope change stands: co-orbital station, not miss distance. No intent language, ever. No replacement of T13's
rules or T14's score; T18 competes with T14 on measured controls and loses gracefully if it loses.
