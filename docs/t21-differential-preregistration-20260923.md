# T21 preregistration — differential (common-mode-rejecting) manoeuvre detection

**Registered 2026-09-23, before any T21 number exists and before any T21 code exists.**
This file is committed **alone**. Nothing in it is a measurement; every quantity below is either
a derivation from first principles, a threshold chosen here in advance, or a rule that resolves
against data at run time. The instruments, the results and the artefacts follow in later commits.

**Track:** T21, opened by the conductor 2026-09-23. **Programme:** the orbit research programme,
`docs/research-program-runbook-20260921.md`.

---

## 0. The hypothesis, in the conductor's terms

> The dominant errors in public element sets — atmospheric-density mismodelling, fit-span
> artefacts, epoch-cadence effects — are **common** to objects sharing an orbit at the same epoch.
> Differencing a satellite's elements against a co-orbital reference cancels the common-mode term,
> lowering the manoeuvre-detection floor well below the semi-major-axis floor T16b measured, and
> raising recall at fixed false-flag rate.

That is the claim under test. This registration fixes, in advance, the arithmetic that would
support it, the arithmetic that would refute it, and the controls that separate "the common mode
cancelled" from "differencing any two well-tracked objects helps" and from "nothing cancelled".

**Survival is a complete result.** If the measurement sustains the hypothesis, it is reported
unchanged and unhedged; if it refutes it, that is reported as the result, not as a failure of the
track. A challenge is pressure, not evidence. An adversarial pass over the finished document is
required (§8.4) and ships with a capitulation ledger entry — `survived` / `revised` / `retracted` —
so that a rising retraction rate would indict the wording of the challenge rather than the answers.

---

## 1. Read the floors first — the numbers T21 is measured against

No T21 number may be printed before these, and every T21 recall cell must be printed beside the
population-matched comparator, not only the pooled one.

| Floor | Value | Source |
|---|---|---|
| Shipped LEO detector, semi-major-axis floor, pooled σ arm | **102.2 – 126.0 m** of *a* (54.0 – 58.7 mm/s along-track) | `docs/t16b-truthset-results-20260922.md` §3.1 |
| Shipped LEO detector, per-object σ arm | **50.0 m** of *a*, set by the registered `DA_FLOOR_KM` term and not by noise | ibid. |
| Shipped detector recall, 11 spacecraft, MAD-LEO event window | **90/1134 = 7.937%** [6.502, 9.656] | `docs/t16b-truthset-recall-20260922.json` |
| Shipped detector false-flag rate (the operating point every arm is matched to) | **0.012642669 flags / quiet-window-day** (18 flags / 1,423.75 window-days) | `docs/t18-floor-20260922.json` `E1.matchedOperatingPoint` |
| Cadence-only "schedule" floor, 11 spacecraft | **5.115%** [3.977, **6.555**] at that same rate | `docs/t18-fail-record-20260922.md` §0, §2.1 |
| **Population-matched shipped recall, Sentinel-3A + 3B only** | **10/292 = 3.425%** (3A 2/147 = 1.361%, 3B 8/145 = 5.517%) | `docs/t16b-truthset-recall-20260922.json`, `arms.pooled.windows.madleoEventWindow.bySpacecraft` |
| **Population-matched schedule floor, Sentinel-3A + 3B only** | **5/292 = 1.712%** (3A 0/147, 3B 5/145) | `docs/t18-floor-20260922.json`, `E1.A1_unseenObjectAnyEra.bySpacecraft` |

**The primary comparators for the LEO arm are the two population-matched rows**, because the LEO
differential arm can only be evaluated on Sentinel-3A and Sentinel-3B. The pooled 7.937% and
5.115% are printed as cross-population reference and **do not compose** with a two-spacecraft
number; §7 binds this.

**A fact about the shipped floor that shapes this design.** T16b measured that these spacecraft's
own fit noise is 130–470× smaller than the pooled `σ_n = 6.2747e-5` rev/day that sets the shipped
threshold, and that in the per-object arm the binding term is the chosen 50 m `DA_FLOOR_KM`
constant. **On these two objects the shipped 102–126 m floor is therefore a population constant,
not a noise floor**, and reducing noise by differencing cannot move it. §3.5 registers how the
swept arms handle this, in advance, and §5 registers that a floor which does not move because a
constant pins it is reported as exactly that.

---

## 2. The noise model, and the floor ratio it derives

### 2.1 The model

Let the detector's in-track statistic for object X at epoch t be the residual r_X(t) left after
the shipped rolling Theil–Sen baseline is removed from the mean-motion series. Write

  r_X(t) = c(t) + ε_X(t)

where **c(t)** is any error term shared by two objects observed at the same epoch — density
mismodelling, fit-span convention, epoch-cadence artefact, space-weather index error — with
variance σ_c², and **ε_X(t)** is the object-specific term with variance σ², taken independent
between objects and across epochs. Equal variances are assumed for the two members of a
co-orbital pair; §5 registers what happens if the measurement contradicts that.

### 2.2 The derivation

Single object: Var(r_X) = σ_c² + σ².

Differential, at matched epochs: D(t) = r_A(t) − r_B(t) = ε_A(t) − ε_B(t); the common term
cancels identically. Var(D) = 2σ² + σ_i², where σ_i² is the variance the interpolation of the
partner series injects (§3.3).

Define the **equal-time cross-correlation** of the two objects' residuals,
ρ ≡ Corr(r_A, r_B) = σ_c² / (σ_c² + σ²). Then σ² = (1 − ρ)(σ_c² + σ²) and, neglecting σ_i²,

  **R ≡ s_diff / s_single = √(2(1 − ρ))**

with the interpolation term carried it is R = √((2(1 − ρ)(σ_c²+σ²) + σ_i²)/(σ_c²+σ²)).

**Therefore R < 1 if and only if ρ > 1/2.** Differencing lowers the noise floor only when the
common-mode term carries **more than half** the residual variance. If ρ = 0, R = √2 ≈ 1.414 and
the differential is 41% **worse**. This is a derivation from the stated model, not a measured
fact, and the model itself is falsifiable: §5 registers the agreement test between the R predicted
from a measured ρ and the R measured directly.

### 2.3 From a noise ratio to a floor in metres

T16b's derivation, reused unchanged: a = (μ/(2πn/86400)²)^(1/3) gives da/a = −(2/3)dn/n, so the
smallest detectable semi-major-axis step at an in-track threshold thr_n (rev/day) is
**|δa|min = (2/3)(a/n)·thr_n**, and for a near-circular orbit da = 2·dv/n_ang gives
**dv = δa·n_ang/2**. When the threshold is k·σ in both arms, the floor ratio in metres of *a*
equals R exactly. When a constant (the 50 m `DA_FLOOR_KM` term) or the drag term binds instead,
it does not; **which term binds is reported for every arm**, and a floor pinned by a constant is
reported as pinned, never as measured.

---

## 3. Arm A — LEO, Sentinel-3A vs Sentinel-3B

### 3.1 Input, reused not refetched

- **Element sets:** this programme's own archive, `/home/sdegan/space-orbit-history/orbit-history.sqlite3`,
  read-only, via the same query T16b's `truthset_recall.load_elements` uses (epoch_ms, mean motion,
  eccentricity, inclination, RAAN, and additionally argument of perigee and mean anomaly where the
  GEO arm needs them). NORAD 41335 (Sentinel-3A) and 43437 (Sentinel-3B).
- **Labels:** the MAD-LEO mission-reported subset already on the analysis host at
  `~/t16b-truth/madleo` (CC BY 4.0, doi 10.6084/m9.figshare.33446503.v1) — **147** Sentinel-3A and
  **145** Sentinel-3B manoeuvre annotations, **292** in total, with their own event windows
  (−6 h / +24 h) and the labelled-quiet ("stable") windows. Nothing is refetched and nothing is
  redistributed.
- **Corroboration only:** the live IDS/DORIS histories `s3aman.txt`, `s3bman.txt` at `~/t16b-truth/ids`,
  already shown by T16b §3.7 to match all 292 labels. No headline number comes from them.

**The pair's geometry is an input to be checked, not an assumption.** The conductor's brief states
Sentinel-3A and 3B share a ground track "~140 s apart". T21 **measures** and reports, from the
archive: the median difference in semi-major axis, in inclination, in RAAN, and the along-track
phase difference implied by the mean-longitude-like argument; and it reports whether the measured
separation matches the brief. No claim in this document depends on the 140 s figure being right,
and the figure is not asserted anywhere as fact.

### 3.2 The differential series

Four differential channels are formed: **Δa, Δe, Δi, Δn**. The detector's in-track channel runs on
**Δn** (mean motion, rev/day), which is what the shipped in-track channel reads; Δa is reported as
its metre-scale interpretation via §2.3; Δe and Δi are formed, their quiet-window noise scales and
correlations reported, and Δi is the LEO plane channel's input. The shipped plane channel recalled
**zero of 1,134** manoeuvres (T16b §3.2), so no recall claim is made from Δi at LEO; its floor
ratio is reported and nothing else.

**Epoch matching, registered.** The two objects' epochs do not coincide. Two differential series
are formed, not one:

- **D_A**: evaluated at **Sentinel-3A's own epochs**, with Sentinel-3B linearly interpolated onto them.
- **D_B**: evaluated at **Sentinel-3B's own epochs**, with Sentinel-3A linearly interpolated onto them.

Each host series carries its own object's values **exactly**, so a step by the host spacecraft is
sharp in its own series and only a step by the partner is smeared by interpolation. Flags are the
**union** of the two series' flags. This is registered because interpolating one member only would
make that member's burns systematically harder to see, and the asymmetry would be mistaken for a
per-spacecraft result.

**Interpolation is refused across gaps.** An output epoch whose bracketing partner epochs are more
than **MAX_GAP_DAYS = 5.0** apart (the constant already registered in `tools/proximity_plane.py` /
`proximity_geo.py`) yields NaN. Refused points are **counted and reported**, never silently
dropped, and a label window containing no usable differential sample is counted as *not evaluable*
rather than as a miss (§3.7, gate G4).

### 3.3 The interpolation error, derived and measured

**Derived.** Linear interpolation of a twice-differentiable series across a bracket of width h
carries a curvature error bounded by h²·max|y″|/8. Independently, if the two bracketing values
carry independent noise of variance σ_B², the interpolate at fraction f carries
σ_B²(f² + (1−f)²), which lies in [σ_B²/2, σ_B²] — so interpolation **reduces** the partner's
per-sample noise variance by up to a factor two while **correlating neighbouring samples**. The
two-consecutive-confirmation rule assumes no such correlation, so the **lag-1 autocorrelation of
the differential residual is measured and printed** beside every false-flag number.

**Measured.** A hold-one-out estimate, registered here and computed before any recall cell: for
every interior element set of each object, interpolate its value from its two neighbours and
record (measured − interpolated). Report the median |error| and the MAD-derived σ, in rev/day and
converted to metres of semi-major axis by §2.3, for both objects. Gate G2 requires this to be
printed first.

### 3.4 The detector shape

The shipped in-track channel (`tools/proximity_plane.detect_manoeuvres`, prereg 5.4 of T8b) is:
rolling Theil–Sen residual of the series with a 10-sample window; threshold
max(5σ_n, 3|ṅ|·spacing, 1.5·n·`DA_FLOOR_KM`/a); confirmation requiring **two consecutive** samples
over the bar **agreeing in sign**; the flag epoch is the **second** sample's.

T21 applies **the same shape** to the differential. The shipped functions
`rolling_theil_sen_residual`, `second_difference`, `mad_sigma`, `sliding_median`,
`semi_major_axis_km` are **imported, never edited**; the confirmation rule is reimplemented in the
new module (it is a closure inside the shipped function and cannot be imported), and a registered
test asserts the reimplementation reproduces the shipped in-track flags **exactly** on a single
object when given the same thresholds (§8.2, test T5).

The differential's own noise scale is `mad_sigma(second_difference(D), √6)` — the shipped
`object_sigma_contributions` arithmetic applied to the differential series.

### 3.5 The arms, and the operating point

Five arms, all evaluated on the same 292 labels and the same quiet windows:

| Arm | threshold | note |
|---|---|---|
| **S1 shipped** | `pp.detect_manoeuvres` at the pooled σ, untouched | the published 10/292 |
| **S2 per-object** | `pp.detect_manoeuvres` at each object's own σ, untouched | T16b's per-object arm |
| **S3 single, swept** | k·σ_X on the single series, k swept | the noise-matched single-object comparator |
| **D1 differential, k = 5** | 5·σ_D on D_A and D_B | the shipped multiplier, no sweep |
| **D3 differential, swept** | k·σ_D, k swept | the arm P2 is read on |

**Registered instrument change, stated in advance.** The **swept** arms S3 and D3 drop the 50 m
`DA_FLOOR_KM` term and the 3|ṅ|·spacing drag term, so that the threshold is set by the measured
noise **alone**. This is necessary because §1 establishes that on these two objects the shipped
threshold is pinned by a population constant, and a floor pinned by a constant cannot test a
hypothesis about noise. It is a change of instrument and is labelled as one everywhere it is used.
The guard against it is the false-flag match: removing the drag term can only raise the flag rate,
and the sweep must then pick a larger k, which costs recall. S1 and S2 are reported unchanged
beside them.

**The sweep and its tie-break** follow T18 §2 verbatim in shape: *the smallest threshold whose
false-flag rate on the labelled-quiet windows does not exceed the baseline's* **0.012642669 per
quiet-window-day**. k is swept over a grid fixed here: k ∈ {1.0, 1.25, 1.5, …, 12.0} in steps of
0.25, and the chosen k, the achieved rate, and whether the achieved rate is stricter or looser than
the baseline's, are printed for every swept arm.

**The quiet-window denominator for the differential** is the **intersection** of a Sentinel-3A
labelled-quiet window with a Sentinel-3B labelled-quiet window: an interval in which *both* members
are labelled quiet. The single-object swept arm S3 is matched on the **same intersections**, so the
comparison is like for like. Fallback, registered: if the intersections total fewer than **50
window-days**, the match is instead made on the union of the two spacecraft's stable windows and
the substitution is reported; if even the union is under 50 window-days, gate **G7** fires and
**no recall claim is made** (the floor result stands on its own).

### 3.6 The floor measurement

On the quiet intervals of §3.5, and before any recall cell:

1. **s_single** — the MAD-derived σ of the single-object residual, per object and pooled over the two.
2. **s_diff** — the same statistic on D_A and D_B.
3. **R = s_diff / s_single**, measured, with a 95% interval from a **block bootstrap over 30-day
   blocks, 1,000 resamples, seed 20260923**.
4. **ρ** — the equal-time correlation of the two objects' residuals on the same intervals (the
   partner interpolated), with the same block bootstrap.
5. **R_derived = √(2(1 − ρ))**, and the ratio R_measured / R_derived.
6. Both floors in **metres of semi-major axis** and **mm/s** via §2.3, with the binding term named.

### 3.7 Recall and false flags

Association is MAD-LEO's own event window (event − 6 h / + 24 h), exactly as T16b. A label is a
**hit** if any flag of the arm falls inside its window. Reported for every arm: overall recall over
292 with Wilson 95%; per spacecraft; **per burn-size bin** on T16b's registered bins
(<20, 20–50, 50–100, 100–200, 200–500, ≥500 m of archive-bracketed |Δa| — a stratifier, never
evidence); split at each arm's **own** measured floor; the count not evaluable; and the placebo
control (the same association rule on windows displaced by ±30, ±60, ±90 days, those landing within
2 days of another label discarded), with its lift.

**The increment** is reported three ways, in this order: (i) against **S2/S3 on the same 292
labels** — the primary; (ii) against the population-matched shipped **3.425%** and schedule floor
**1.712%**; (iii) against the pooled **7.937%** and **5.115%**, labelled *cross-population, does
not compose*. Each increment carries a **paired 95% bootstrap over 90-day time blocks, 1,000
resamples, seed 20260923**. An object-clustered bootstrap is **not** available here — there are two
clusters — and the substitution is registered now, in advance, with its limitation: labels within a
spacecraft are not independent, so the block bootstrap over time is the arm of record and the
label-level bootstrap is printed beside it as the looser of the two.

**The minimum detectable increment** — the half-width of the paired interval — is computed and
printed, so that a null can be read as "this design could not have shown an increment smaller than
X" rather than as "no effect".

### 3.8 Controls

**C1 — non-co-orbital, similar altitude.** The comparison object is selected by a rule fixed here
and resolved at run time: *among the other nine MAD-LEO spacecraft, the one whose median
semi-major axis over the archive is closest to Sentinel-3A's*. The object the rule picks, its
median a, its inclination and its RAAN drift are reported. Sentinel-3A is differenced against it
by the identical procedure.

**C2 — different altitude and plane.** CryoSat-2 (NORAD 36508), named here. Its measured
semi-major axis and inclination relative to Sentinel-3A's are reported rather than asserted.

**C3 — shuffled epochs.** Sentinel-3A differenced against Sentinel-3B with Sentinel-3B's epochs
shifted by **+180 days** and, separately, **−180 days** (neither is an integer multiple of the
~14-day keeping interval T16b §2.5 reports for these spacecraft), plus a third arm in which
Sentinel-3B's residual sequence is randomly permuted (seed 20260923). Time alignment is destroyed,
so no common mode can cancel.

**Registered predictions.** If the hypothesis holds: the co-orbital pair shows ρ > 0.5 and R < 1;
C3 shows ρ ≈ 0 and R ≈ √2; C1 and C2 show R not below 1. **A third outcome is registered in
advance rather than discovered:** if C1 or C2 *also* shows a gain, the hypothesis's *co-orbital*
premise is wrong, and the result is restated as *differencing against any contemporaneous
well-tracked object cancels a common mode* — a different and weaker claim about where the common
mode comes from, reported as such and not as a confirmation of T21's hypothesis.

### 3.9 The sign question and the attribution rule

A step in D = n_A − n_B is ambiguous between "A stepped by +s" and "B stepped by −s". The rule
registered here resolves it from the sign alone, using a **direction screen** that is measured, not
assumed:

> **Direction screen.** These two spacecraft's station-keeping manoeuvres are taken to raise the
> semi-major axis (reduce mean motion). This is a *screen*, not a law. It is measured: the fraction
> of the 292 labels whose signed archive-bracketed Δa is positive is computed and printed, per
> spacecraft, **before** the attribution rule is read.
>
> **Attribution rule.** Under that screen, A raising a makes n_A fall, so D falls: **a confirmed
> negative step in D attributes to Sentinel-3A; a confirmed positive step attributes to
> Sentinel-3B.**

**Measurement.** Among differential flags falling inside the event window of exactly one
spacecraft's label (the unambiguous subset), report the fraction the sign rule names correctly,
with Wilson 95%, against the 50% chance level. If the direction screen is measured at below 70% one-sided
on either spacecraft, the attribution rule is reported **unusable** and no attribution claim is
made; the screen's measured value is printed either way.

---

## 4. Arm B — GEO, the T11 co-located pairs

### 4.1 Input, reused not rebuilt

T8a's committed near-GEO extract at `space-teaching-aid/runtime/proximity-geo/near-geo.npz`,
hash-pinned by its three published counts (217,007,154 rows scanned, 11,626,494 kept, 1,768
objects) exactly as T11's gate F pins it — **the same gate runs here and stops the run on a
mismatch**. The pairs and episodes are T11's committed
`docs/persistent-pairs-20260922.jsonl`: **1,317 episodes over 239 distinct pairs**. No episode is
re-detected; T21 reads the committed list.

The estimand is **mean longitude λ**, a slot coordinate (T11 §1.1). **No number in the GEO arm is a
miss distance.** The GEO instrument is ownership-agnostic: registry codes, names and launch dates
are metadata, enter no detector decision, and no sentence attributes a purpose to any measured
motion.

### 4.2 The channels

Per episode, over its `[startMs, endMs]`, for members A and B, using the shipped
`proximity_geo` estimators unchanged (`mean_longitude_deg`, `unwrap_longitude`,
`drift_rate_deg_per_day`):

- **Mean longitude** λ (unwrapped) — differenced, Δλ.
- **Drift rate** λ̇ (deg/day) — differenced, Δλ̇. This is the **E-W** channel.
- **Inclination** i (deg) — differenced, Δi; the detector runs on the rate di/dt. This is the
  **N-S** channel.

Epoch matching is the same union-host scheme as §3.2, with the same 5-day gap refusal and the same
hold-one-out interpolation-error measurement, reported before any GEO detection cell.

### 4.3 The detector shape

**E-W, single object:** the shipped `proximity_geo.drift_change_flags` — departure of λ̇ from its
trailing 10-sample median by more than max(5σ_n, 0.010 deg/day) at two consecutive element sets,
flag epoch the second. Imported, never edited.

**E-W, differential:** the same shape on Δλ̇, with σ measured on the differential by the same
`calibrate_sigma_n` arithmetic, and with the 0.010 deg/day floor treated the same way as §3.5
treats `DA_FLOOR_KM`: kept in the shipped arm, dropped in the swept arm, and labelled.

**N-S:** the same two-consecutive-exceedance shape applied to di/dt against its trailing 10-sample
median, single and differential, with σ measured the same way and a floor of `I_FLOOR_DEG = 0.01`
(the registered TLE-resolution constant). The N-S channel is **new** to this programme at GEO and
is labelled as such; it is registered here before it is run.

### 4.4 The quiet intervals, and the floor ratio

**There is no manoeuvre truth at GEO.** A quiet interval is therefore defined here as an interval
inside an episode containing no single-object flag from **either** member within **±7 days** — a
chosen screen, not an operator's declaration, and every GEO floor number carries that qualifier.

Reported: s_single (pooled over both members), s_diff, **R = s_diff/s_single** with the 30-day
block bootstrap, ρ, R_derived = √(2(1−ρ)), pooled over episodes and also per episode with the
distribution of R across the 239 pairs. Converted to an equivalent semi-major-axis offset by
`semi_major_offset_km` (interpretive only, never inside a detector decision) and to metres.

### 4.5 Agreement and lift — not accuracy

With no truth, the GEO detection result is an **agreement** measurement in T13's shape:

- **Agreement:** the fraction of differential flags with a single-object flag on either member
  within **±2 days**, and the reverse — the fraction of single-object flags with a differential
  flag within ±2 days.
- **Lift:** the rate of single-object flags inside ±2 days of a differential flag, over the base
  rate of single-object flags inside episodes.
- **Control:** the identical agreement computed after displacing the differential flag times by
  **±30 days** within the episode. The lift over that control is the number that means anything.

**The word "recall" does not appear in the GEO arm**, and no GEO number is reported as accuracy.

---

## 5. Decision rules — what makes the claim, what falsifies it

### 5.1 The primary claim

> **P — "Differential detection lowers the manoeuvre-detection floor."**

It is made only if **all three** of the following hold.

**P1 — the floor moves.** On Sentinel-3A/3B quiet intervals, the measured **R** has a 95%
block-bootstrap **upper** bound **< 1.000**; **and** the measured R agrees with the derived
√(2(1−ρ)) within a factor of **1.25** in either direction. If the measured and derived R disagree
by more than that factor, the noise model of §2.1 is reported **wrong** and the claim is
**withheld** regardless of the other screens — a floor that moves for a reason the model does not
contain is not evidence for the model.

**P2 — recall rises at matched false-flag rate.** At an achieved false-flag rate on the shared
quiet intervals not exceeding **0.012642669 per quiet-window-day**, arm **D3**'s recall over the
292 Sentinel-3A/3B labels exceeds arm **S3**'s recall on the same 292 labels at its own matched
rate, with a paired 90-day-block bootstrap **lower** bound **above zero**.

**P3 — the controls separate.** Neither C3 (shuffled epochs) nor C1/C2 (non-co-orbital) produces a
floor ratio whose 95% upper bound is below 1.000. If a control does, the claim is **restated**, not
made: see §3.8's third registered outcome.

### 5.2 Falsification

The hypothesis is **refuted** if any one of:

- **F1** — the measured **ρ** on quiet intervals has a 95% **upper** bound ≤ **0.500**. The common
  mode is then too small for differencing to help, by §2.2's derivation, and the derived R ≥ 1.
- **F2** — the measured **R** has a 95% **lower** bound ≥ **1.000**.
- **F3** — the paired recall increment (D3 − S3) has a 95% **upper** bound ≤ **0**.

A refutation on F1 or F2 is a **measured negative result about the structure of element-set error**,
and is written up as the result of the track, with the measured ρ and R as its content.

### 5.3 Withheld

Any mixed outcome — the floor moves but recall does not, recall rises but the interval straddles
zero, the model disagrees with its own derivation — is reported as **NOT DEMONSTRATED**, never as a
trend, following T18's registered reading. The minimum detectable increment (§3.7) is printed
alongside so that a null is readable.

### 5.4 The GEO arm's own rule

GEO has no truth and therefore makes **no detection claim**. It makes at most a **floor** claim:
the GEO differential floor is reported as lower than the single-object floor only if R's 95% upper
bound is below 1.000 on the pooled quiet intervals, with the same derived-vs-measured agreement
test. The agreement/lift numbers are descriptive and are reported with their ±30-day control in the
same table; a lift whose interval includes 1.0 is reported as no lift.

---

## 6. Gates

| Gate | Fires when | Consequence |
|---|---|---|
| **G1** detector untouched | `git diff` over `tools/proximity_plane.py` and `tools/proximity_geo.py` is non-empty at run time | the run stops; blob hashes are recorded in the results JSON either way |
| **G2** interpolation error printed first | any recall or agreement cell is computed before §3.3's hold-one-out numbers exist | the run stops |
| **G3** floors printed first | any recall cell precedes §3.6's floors and ρ | the run stops |
| **G4** evaluability | more than **10%** of the 292 labels are not evaluable in the differential | the recall comparison is restricted to the evaluable subset and **every** comparator, including S1 and S2, is recomputed on that same subset |
| **G5** tests | either registered instrument test (§8.2, T1/T2) fails | no number is reported |
| **G6** sample | fewer than **200** usable quiet-interval differential samples | the floor ratio is reported **without a claim** |
| **G7** operating point | the shared quiet windows total fewer than 50 window-days even after the union fallback | **no recall claim is made**; the floor result stands alone |
| **G8** GEO input | T11's three pinned extract counts do not match | the GEO arm does not run |

Every gate's verdict — fired or not — is printed in the results document.

---

## 7. Composition limits, binding on every sentence of the results

- **The LEO arm is two spacecraft and one operator.** Sentinel-3A and Sentinel-3B share a ground
  segment, an orbit-determination process, a manoeuvre-planning system and a mission. A gain
  measured on this pair is a statement about **this pair**, and says nothing about a co-orbital
  pair that does not share those. The 292 labels are not independent of one another.
- **Two clusters is not enough for an object-clustered interval.** The arm of record is a time-block
  bootstrap, and its limitation (§3.7) is stated wherever its interval is printed.
- **The pooled 7.937% and 5.115% are eleven-spacecraft numbers and do not compose** with a
  two-spacecraft recall. The population-matched 3.425% and 1.712% are the primary comparators.
- **Nothing here is about constellations, about Starlink, or about any operator whose manoeuvre log
  is not public.**
- **GEO has no truth**; agreement is agreement.
- **Every threshold in this document is a chosen screen, not a physical law** — the 5σ multiplier,
  the 50 m and 0.010 deg/day and 0.01° floors, the ±7-day quiet screen, the ±2-day agreement
  window, the 1.25 model-agreement factor, the 0.500 correlation bar, the 5-day gap refusal, the
  burn-size bins, the 180-day epoch shift, the 70% direction-screen bar.
- **The MAD-LEO "labelled-quiet" windows are mined from a TLE archive, not declared quiet by an
  operator** — T16b §3.5 — so every false-flag count remains an **upper bound**, and the phrase
  "false-alarm rate" is not used.

---

## 8. Instruments, tests, reproduction

### 8.1 What will be built

`tools/differential_detect.py` — one module, both arms, importing the shipped estimators from
`tools/proximity_plane.py` and `tools/proximity_geo.py` and editing neither. Artefacts:
`docs/t21-differential-results-<date>.json` and `docs/t21-differential-results-<date>.md`.

### 8.2 The tests, registered before they are written (`tests/test_differential.py`)

1. **T1 — a common-mode error cancels.** Inject an identical synthetic error series into two
   otherwise independent element series. Assert: the differential's measured σ is **not** inflated
   by it (within a stated tolerance), while each single series' σ **is**. *This test asserts the
   bug it is meant to catch*: it fails if the differential is formed at mismatched epochs, or if a
   sign is wrong.
2. **T2 — an independent step survives.** Inject a step into **one** series only. Assert it is
   flagged in the differential at the same epoch as in the single series, and with the registered
   sign.
3. **T3 — the sign/attribution rule.** A step injected into A and the same step injected into B
   produce differential steps of **opposite** sign, and the §3.9 rule names the right spacecraft in
   both cases.
4. **T4 — interpolation is refused across a gap.** A gap longer than 5 days yields NaN and is
   counted, not dropped.
5. **T5 — the detector shape is the shipped one.** The reimplemented confirmation rule reproduces
   `pp.detect_manoeuvres`'s in-track flag indices **exactly** on a single object when given the
   same threshold.
6. **T6 — the floor derivation.** `|δa|min = (2/3)(a/n)·thr_n` and `dv = δa·n_ang/2` reproduce
   T16b's published 102.2–126.0 m and 54.0–58.7 mm/s from its published inputs.
7. **T7 — no vocabulary leak.** The instrument, the results document and the JSON contain no
   word from the programme banned list and no tool or vendor name, as this programme's other instruments already
   assert.
8. **T8 — the shuffled control really is shuffled.** The ±180-day arm's epoch alignment differs
   from the true pairing on every sample.

### 8.3 Reproduction

`python3 tools/differential_detect.py --arm leo|geo|all --out docs/t21-differential-results-<date>.json`,
then `python3 -m unittest tests.test_differential`. Host: `pc`, CPU only, `nice`. No GPU stage is
declared and none is expected; if one is ever added, its `gpu-consumers.json` row ships in the same
change. Disk before and after is reported.

### 8.4 The adversarial pass

One adversarial read of the finished results document is required before the track is discharged.
Its prompt must state that **sustaining the conclusion unchanged is a complete and expected
response, and that a challenge is not evidence**; its outcome is recorded as
`survived` / `revised` / `retracted` in `docs/t21-capitulation-ledger-<date>.jsonl`.

---

## 9. What is registered, in one paragraph

Form Δn (and Δa, Δe, Δi) between Sentinel-3A and Sentinel-3B on each other's epochs with linear
interpolation refused across 5-day gaps; measure the interpolation error by hold-one-out; measure
the two objects' residual correlation ρ and the differential-to-single noise ratio R on
labelled-quiet intervals; check R against the derived √(2(1−ρ)); convert both floors to metres of
semi-major axis by T16b's derivation and name the binding term; sweep the differential and the
single-object detector to the shipped 0.012642669 flags per quiet-window-day on the intervals where
both spacecraft are labelled quiet; report recall over the 292 Sentinel-3 labels per burn-size bin
against the population-matched 3.425% and 1.712%; run the shuffled-epoch and non-co-orbital
controls; measure the sign-attribution rule against the 50% chance level; repeat the floor half at
GEO on T11's 1,317 co-located episodes with agreement and lift in place of recall. Claim P requires
P1, P2 and P3 together; F1, F2 or F3 refutes; anything mixed is NOT DEMONSTRATED.
