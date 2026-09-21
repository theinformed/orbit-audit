# Paper B pre-registration: covariate-matched transfer and the inclination finding

Registered 2026-09-20, **before any measurement in this task was computed**. The
git history of this file is the timestamp: this document is committed in its own
commit, ahead of the analysis code and ahead of every result file. Nothing below
may be changed after a number exists. If a rule here turns out to be awkward, the
awkwardness is reported, not edited away.

This registers two analyses that answer two specific, paper-killing reviewer
objections to the audited false-alarm control:

1. **"The debris false-alarm rate does not transfer to payloads."** The passive
   and payload populations differ in altitude, inclination, eccentricity and TLE
   update cadence, so a passive floor measured on the passive covariate mix is
   not obviously a bound on payload behaviour.
2. **"Identical rates at 60-120 degrees is null-acceptance from p>0.05, and the
   30-degree band looks fitted."** A non-significant difference is not evidence
   of equivalence, and a boundary chosen by eye from a coarse table is a
   researcher degree of freedom.

Both objections are answered by construction below, and both answers are allowed
to come out against the paper.

## 0. Detector, population, and what a "flag" is

- Archive read **read-only** through `orbit_campaigns.open_archive_for_reading()`.
  No write path, no ingest, no release, no timer, no deployment.
- Detector source is the repository at the commit that carries this document's
  own commit as an ancestor, i.e. current `integration/space` HEAD, which
  **contains `56eef64`** and therefore runs with high-inclination energy
  corroboration ACTIVE.
- `kappa = 32` (production). `INCLINATION_FLOOR_TAIL_AWARE`,
  `MATCHED_CONTROL_STRATA_ENABLED` and `DECLINE_AFTER_TRACKING_GAP` all remain
  `False`. No threshold, boundary, switch or constant is changed by this task.
- **PASSIVE** = archive `object_type` in `('DEBRIS','ROCKET BODY')`.
  **PAYLOAD** = `object_type = 'PAYLOAD'`. Objects with a null or `UNKNOWN`
  type are out of scope for both populations, exactly as in the published control.
- **Flag** = a detected event whose signature is not in
  `orbit_events.NON_PROPULSIVE_SIGNATURES`. This is the numerator of the
  published control, unchanged.
- **Exposure** = usable intervals of admitted objects. The production admission
  rule applies: an object with fewer than nine usable intervals is excluded, and
  the exclusion is **counted and reported**, never silently dropped.
- The published target is `targetRatePerInterval = 0.001`, i.e. **1.0 flag per
  1,000 usable intervals**. Every "per 1,000" number below is per 1,000 usable
  intervals.

## 1. Sample

All archive objects with `norad % 5 == 0` and an in-scope `object_type`, across
their **entire retained histories**. This is a systematic 1-in-5 sample with a
**uniform inclusion probability in both populations**, so no sampling weights
are required and the reweighting below is a pure covariate reweighting rather
than a design reweighting. It is a superset in spirit, though not in membership
arithmetic, of the 1-in-25 Phase-2/2b diagnostic sample, and is roughly four
times its size.

Declared in advance: a systematic modulus sample is **not** a random confidence
sample over objects. Interval-level Jeffreys bounds therefore quantify
within-sample binomial uncertainty only. The clustered bootstrap registered in
section 4 is the estimator that carries object-level uncertainty, and it is the
primary interval for the headline number precisely because of this.

## 2. The covariate strata (Analysis 1)

Four factors, each assigned from the **interval's own** measured values, fixed
here before measurement. Bands reuse existing repository definitions wherever
one exists, so that no new cut point is introduced by this task.

| Factor | Bands | Source |
|---|---|---|
| Perigee | `<300 km`, `300-500 km`, `500-800 km`, `800-1200 km`, `1200-2000 km`, `>2000 km` | existing `orbit_campaigns._perigee_band` |
| Inclination | `0-1`, `1-5`, `5-15`, `15-30`, `30-60`, `60-90`, `90-120`, `120-180` degrees | existing Phase-2 edges |
| Eccentricity | `<0.001`, `0.001-0.01`, `0.01-0.1`, `>=0.1` | new, decade bands on a quantity the detector already carries |
| TLE cadence | `<0.25 d`, `0.25-1 d`, `1-2 d`, `>=2 d` | existing Phase-2 `spanDays` bins; interval span **is** the TLE update gap |

Bands are lower-inclusive and upper-exclusive; 180 degrees falls in the last
inclination band. 768 nominal cells, most of which will be empty. Interval span
is bounded above by the existing `MAXIMUM_JOINABLE_GAP_DAYS = 3.0` and below by
`MINIMUM_SPAN_DAYS = 0.1`, so the cadence factor spans the whole admissible range.

Eccentricity is the only new cut. It is registered as decade boundaries on
physical grounds - near-circular, slightly elliptical, elliptical, and
transfer/HEO - and not tuned: no alternative eccentricity banding will be tried,
and if the chosen banding leaves cells unsupported that fact is reported rather
than repaired by re-cutting.

## 3. Analysis 1 estimators

Let `n_s^P, k_s^P` be passive exposure and flags in stratum `s`, and `n_s^L` the
payload exposure in the same stratum.

- **Raw passive floor** `R_raw = (sum_s k_s^P) / (sum_s n_s^P)`.
- **Supported strata** `S = { s : n_s^P >= 1 }`. A stricter tier
  `S_1000 = { s : n_s^P >= 1000 }` is reported alongside, not instead.
- **Reweighted floor**
  `R_rw = sum_{s in S} w_s * r_s`, with `r_s = k_s^P / n_s^P` and
  `w_s = n_s^L / sum_{s in S} n_s^L`.
  That is: the passive per-stratum false-alarm rate, carried onto the **payload**
  population's covariate distribution, renormalised over the supported strata.
- **Unsupported coverage** = the share of total payload exposure lying in strata
  with `n_s^P = 0`, reported separately for the `< 1000` tier. These are
  **labelled gaps**. They are never imputed silently and never counted as zero.
- **Sensitivity A (worst case)**: unsupported strata are filled with the pooled
  passive Jeffreys 95% **upper** bound and `R_rw` recomputed over all payload
  exposure. This is deliberately pessimistic and is reported as such.
- **Sensitivity B (coarse)**: the whole calculation repeated on perigee x
  inclination only (48 cells), to show whether any conclusion is an artefact of
  768-cell fragmentation.

## 4. Analysis 1 uncertainty

- **Per stratum**: equal-tailed Jeffreys 95% interval via
  `orbit_events._jeffreys_interval`, the estimator already used by the published
  control. A stratum with zero observed flags gets a non-zero upper bound; a zero
  point estimate is never reported as a zero bound.
- **Composite, PRIMARY**: object-level clustered nonparametric bootstrap.
  2,000 resamples, drawing **passive objects** with replacement from the admitted
  passive sample, recomputing every `r_s` and hence `R_rw` on each resample,
  percentile 2.5 / 97.5. Seed **20260920**. The payload weights `w_s` are held at
  their observed values because the target of the estimate is the payload
  covariate distribution as it actually is, not a resampled version of it.
  This is the interval quoted in the abstract, because it is the only one that
  carries the fact that intervals within one object are not independent.
- **Composite, SECONDARY**: independent `Beta(k_s+0.5, n_s-k_s+0.5)` draws per
  supported stratum, 20,000 draws, weighted sum, percentile interval, same seed.
  Declared **conservative in advance**: with hundreds of occupied strata the
  Jeffreys prior contributes half a pseudo-flag per stratum, which inflates the
  composite upward. It is registered so that it cannot later be presented as a
  discovery, and both intervals are reported whichever is friendlier.

No third interval will be computed. No interval will be selected after seeing
the numbers.

## 5. Analysis 1 decision rule

Stated before computing:

- The paper's transfer claim **SURVIVES** if and only if
  (i) `R_rw` and its **primary bootstrap 95% upper bound** are both below the
  `0.001` per-interval target, **and**
  (ii) `R_rw <= 2 * R_raw`.
- If (ii) fails while (i) holds, the claim survives only in the weakened form
  "the floor transfers but is materially covariate-sensitive", and the paper must
  quote the reweighted floor, not the raw floor, as its operating number. The
  factor `R_rw / R_raw` is reported either way.
- If (i) fails, **the paper's claim does not transfer** and the control cannot be
  stated as a payload-applicable bound. This outcome is reported plainly and the
  paper's claims change.
- Independently of (i) and (ii): if unsupported payload exposure exceeds **20%**
  of total payload exposure, the transfer estimate is declared **not sufficient
  on its own**, whatever number it produced, and the shortfall is the headline.

## 6. Analysis 2a: the full rate-versus-inclination curve

Both populations, reported so that any corroboration boundary **falls out of the
data** instead of being asserted.

- Bins: **2 degrees** over [0, 180), plus a zoom set of **0.2 degrees** over
  [0, 2) for the geostationary population.
- Per bin and per population: usable intervals, all-channel flags,
  inclination-channel flags, **inclination-only** flags, the corresponding rates
  per 1,000 usable intervals, and Jeffreys 95% intervals for each.
- Payload/passive rate ratio per bin with an exact conditional 95% interval
  (section 8), and the same for pooled regions.
- **Data-driven boundary rule**, fixed now: on inclination-only rates, scan
  candidate boundaries `theta` in `{0, 2, 4, ..., 90}` degrees. For each, run the
  section-8 equivalence test at margin 1.5 on the pooled region `[theta, 180)`.
  Define `theta*` as the **smallest** `theta` on the grid such that equivalence
  passes at `theta` **and at every larger candidate on the grid** (a monotone
  stability requirement, so a single lucky bin cannot set the boundary). If no
  candidate qualifies, the registered report is **"no data-driven boundary exists
  at margin 1.5"** - not a relaxed margin.
- `theta*` is then compared with the shipped 30 degrees. Any disagreement is
  reported as a disagreement. The shipped boundary is **not** moved by this task
  under any outcome; moving it would be a detector change, which is out of scope
  here and would need its own acceptance.
- Discussion is required to engage Flohrer et al., AMOS 2008, on TLE
  out-of-plane error structure and its inclination dependence, and to state
  explicitly whether the measured curve agrees with, contradicts, or is simply
  silent about that literature's error peak. "Consistent with" is only permitted
  where the measured bounds actually exclude the alternative.

## 7. Analysis 2b: the equivalence test, and its margin

**Region**: inclination >= 30 degrees, the shipped corroboration boundary.
**Quantity**: **inclination-only** flags per 1,000 usable intervals, passive
versus payload - the same quantity as the Phase-2b gate, so the test is on the
statistic the shipped rule was actually justified by.

**Pre-registered equivalence margin: the rate ratio `theta = lambda_payload /
lambda_passive` lies within `[1/1.5, 1.5]`.**

Justification, written before the test is run:

- **It is not a new number.** 1.5 is the ceiling already registered in the
  Phase-2b diagnostic gate ("payload-to-passive high-inclination exposure rate
  ratio at most approximately 1.5"). Reusing it removes the degree of freedom.
- **Detection-utility grounds.** The inclination channel earns its place only if
  a catch on a payload is more likely under "a manoeuvre happened" than the same
  catch on a passive object is under "nothing happened". The exposure-normalised
  rate ratio is exactly that likelihood ratio at the channel level. A ratio
  inside 1.5 is a likelihood ratio below 1.5, under 0.6 bits of evidence; it
  cannot move a detection from *candidate* to *confirmed* at any prior this
  catalogue supports. For scale, the detector's own published acceptance
  requirement is a **10x** bound separation, so declaring "no useful
  discrimination" at 1.5x is a statement roughly 6.7 times stricter than the
  threshold the pipeline already lives by.
- **It is symmetric on the log scale**, so neither direction of difference is
  privileged.

**Test**: exact conditional binomial TOST. With `k_P, k_L` inclination-only
flags on exposures `E_P, E_L`, treat the counts as Poisson; conditional on
`k_P + k_L = N`, `k_L ~ Binomial(N, p(theta))` with
`p(theta) = theta*E_L / (theta*E_L + E_P)`. Run two one-sided exact tests, at
`theta = 1.5` and `theta = 1/1.5`, each at `alpha = 0.05`. **Equivalence is
declared if and only if both one-sided p-values are below 0.05**, which is the
same statement as the exact 90% conditional interval for `theta` lying wholly
inside `[1/1.5, 1.5]`. The exact 90% and 95% intervals are both reported.

The point of the test is that it can fail. If it fails, the correct reading is
"the data do not establish equivalence", which is **not** the same as "the rates
differ", and the paper may then claim neither. That third outcome - inconclusive -
is a registered, reportable result.

The superiority p-value is reported alongside purely so a reader can see that
the old `p > 0.05` was indeed null-acceptance. It carries no decision weight.

## 8. Ratio intervals

Everywhere a payload/passive rate ratio appears, the interval is the exact
conditional (Clopper-Pearson on the conditional binomial) interval mapped back to
`theta` by `theta = p/(1-p) * E_P/E_L`. Bins with zero flags in both populations
report no ratio and are labelled as such; bins with zero flags in one population
report a one-sided bound. No normal approximation is used for any ratio.

## 9. Analysis 2c: the SSO composition control

The objection is that high-inclination agreement is an artefact of both
populations being dominated by sun-synchronous orbits. Registered split of the
`>= 30 degrees` region:

`30-60`, `60-90 excluding SSO`, `SSO 96-100`, `90-120 excluding SSO`, `120-180`,
where **SSO is defined as inclination in [96, 100) degrees**, a fixed geometric
band, not a fitted one.

The section-7 equivalence test is repeated (a) within `SSO 96-100` alone and
(b) within `>= 30 degrees excluding 96-100`. Pre-registered reading:

- If equivalence holds **both** inside and outside the SSO band, the finding is
  not a composition artefact.
- If equivalence holds **only** when SSO is included, the finding is declared a
  **composition artefact** and the paper must say so.
- If equivalence holds outside SSO but not inside it, the SSO band is declared a
  separate regime requiring its own treatment.

Payload and passive SSO exposure shares are reported in every case, because a
matched rate on unmatched composition is the objection being answered.

## 10. Prohibitions

- No metric shopping. Every estimator, margin, bin edge, seed and decision rule
  above is fixed by this commit. Nothing is added afterwards to rescue a result.
- Jeffreys everywhere for single rates; exact conditional binomial everywhere for
  ratios; TOST for every equivalence claim; effect sizes always with intervals.
- An unfavourable result - a reweighted floor that jumps, an equivalence test
  that fails, a data-driven boundary that disagrees with 30 degrees - is a
  **result**, is reported in the same prominence as a favourable one, and
  changes the paper's claims.
- Absence of passive exposure in a stratum is a **labelled gap**, never a zero
  rate and never a silent drop.
- No production timer, release, deployment, checkpoint or running sweep is
  touched. The concurrently running `orbit_release` sweep is left alone.
- This task writes only `tools/paperb_*.py` and `docs/paperb-*`. It does not edit
  `src/**`, `narration/**`, `tools/eol_*`, the odometer work, or the detector.

## 11. Resource bounds

Read-only archive connection, `PRAGMA query_only=1`, WAL, `nice 19`, idle I/O,
**at most two concurrent readers**, per-reader bound **3,600 s cooperative /
3,660 s hard**, resumable object cursors written only under
`/tmp/paperb-20260920`. No GPU is required; if one is used it goes through
`/home/sdegan/gpu-broker/gpu-run --estimate-mib 320 --class standard`. The host
is under heavy unrelated load and that load has priority.

## 12. Deliverables

1. This pre-registration, committed first and alone.
2. `tools/paperb_strata.py`, `tools/paperb_measure.py`, `tools/paperb_analyze.py`
   and `tools/paperb_selftest.py`, with offline tests that do not touch the
   archive.
3. `docs/paperb-results-20260920.md` with every table above.
4. `docs/paperb-strata-20260920.jsonl` - one line per stratum-level measurement,
   both populations, with counts, rates and bounds.
5. `docs/paperb-results-20260920.json` - the machine receipt: selection SQL,
   source hashes, detector flags, counts, timings, seeds, and the decision
   outcomes against the rules in sections 5, 6, 7 and 9.

---

## Amendment 1, 2026-09-20: which detector state Analysis 2 is measured in

**Registered before any Analysis-1 or Analysis-2 result existed. Committed in
its own commit, ahead of every result file, exactly like the original.**

### What was wrong

Section 0 above fixes the detector for the whole task as current HEAD, which
carries `56eef64` and therefore runs with high-inclination energy corroboration
**active**. Sections 6, 7 and 9 then ask for **inclination-only** rates at and
above 30 degrees.

Those two requirements contradict each other. The corroboration rule is
precisely the rule that suppresses an inclination trip at or above 30 degrees
unless `semiMajorAxis` or `eccentricity` also survives persistence in the same
interval. An "inclination-only" catch at or above 30 degrees is therefore
**abstained by construction** under the active rule. Analysis 2 as originally
registered would measure zero against zero and report a tautology.

This was noticed from the in-flight measurement's progress log, which showed
`passiveInclinationOnly: 0` and `payloadInclinationOnly: 0` after 110 passive
and 87 payload flags. That is a **structural zero**, visible from the
arithmetic of the rule alone and identifiable without any analysis outcome: no
rate, ratio, equivalence test, boundary or reweighted floor had been computed,
and the measurement was stopped rather than continued. Nothing that this
amendment could be fitted to yet existed.

### What is amended

Analysis 1 (the covariate-matched transfer) is **unchanged**: it is a statement
about the false-alarm floor of the detector that actually ships, so it stays on
the production state with corroboration **active**.

Analysis 2 (sections 6, 7 and 9) is measured with
`detect_object_events(..., _inclination_corroboration=False)` — the existing,
unmodified keyword argument on the production function, not an edit to the
detector and not a new switch. That is the **pre-corroboration detector**: the
state in which the inclination finding under review was actually made, and the
state whose rate table the shipped 30-degree boundary was justified from. It is
the only state in which the reviewer's objections — "identical rates at 60-120
is null-acceptance" and "the band looks fitted" — are even answerable, because
it is the state those rates were measured in.

No source file is changed. `INCLINATION_CORROBORATION_MIN_DEG` stays 30,
`kappa` stays 32, all three optional detector switches stay `False`, and the
shipped detector is not altered by this task under any outcome.

### Consequences, all registered now

- The measurement runs the detector **twice per object**, once with
  corroboration active and once without, over the same in-memory rows. Both
  tallies are written for every stratum and every curve bin, so nothing has to
  be re-read and the two states cannot drift apart.
- Analysis 1's headline reweighted floor is the **corroboration-active** number.
  The corroboration-off reweighted floor is reported alongside as context, and
  is **not** the paper's operating number.
- Every margin, bin edge, seed, estimator and decision rule in sections 2
  through 9 is unchanged. This amendment changes **which detector state** a
  number is measured in, and nothing else.
- Any result that would have been reported under the original wording is still
  reported: the corroboration-active inclination-only counts appear in the
  results as the structural zeros they are, so a reader can verify the
  contradiction for themselves rather than taking this amendment's word for it.

### A limitation of section 6's boundary rule, found in offline testing

While testing `tools/paperb_strata.boundary_scan` against synthetic fixtures —
before any archive result existed — the registered pooled-region rule was found
to have a dilution property that is worth stating in advance rather than
discovering in review. The rule pools every bin at or above the candidate
boundary and tests the pooled ratio. If the matched high-inclination region
carries far more exposure and far more flags than the discriminating
low-inclination region, the pooled ratio can sit inside the margin even at a
candidate of zero degrees, and the rule then returns zero degrees.

The rule is **not** changed: it is registered, and changing it after seeing that
it can return an inconvenient answer is exactly the move this document exists to
prevent. Instead:

- the full per-candidate scan table is reported, as section 6 already required,
  so a reader sees where each candidate passes and fails;
- a clearly labelled **post-hoc, not pre-registered** bin-wise diagnostic is
  reported alongside it: the exact TOST outcome for each individual 2-degree
  bin. It has no decision weight and cannot set a boundary. It exists so that a
  diluted `theta*` can be recognised as dilution instead of being read as a
  physical edge at zero degrees.

The offline test suite pins both behaviours, so the dilution property is a
documented, tested characteristic rather than an anomaly noticed late.
