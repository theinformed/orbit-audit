# Mass ratio from correction-quantum drift: feasibility probe

Measured 2026-09-20 UTC. **Registered CI-width stop not triggered; mass-ratio interpretation remains unvalidated.**

12 payloads pass the pre-registered six-year, >=40 NSK-event, >=80% top-two-cluster occupancy selection. The per-object split is 1 positive drift, 1 flat-equivalent, 0 negative drift, and 10 inconclusive. There are 0 primary passive controls and 0 passive objects eligible for either primary or relaxed diagnostics. These are fits to detected lower bounds, not telemetry measurements of propellant or command policy.

All qualifying objects are reported, including negative and inconclusive results.

**Interpretation of this run:** THAICOM 6 is the sole nominal positive-drift case: +3.308% log/year, 95% CI [0.718, 5.958]. Its own chemical-prior ledger prediction [0.228, 0.399]%/year lies below that CI, so it does **not** satisfy the proposed own-ledger consistency check as measured. Missing burns could reconcile the discrepancy, but this dataset cannot establish that explanation. Its post-2021 point estimate drops to +0.400%/year, without a sensitivity CI. The nominal trend is not evidence of a stable mass odometer.

INSAT 3DR is the sole flat-equivalent case: −0.069% log/year, 90% CI [−0.493, +0.974]. It passes the registered ±1% margin narrowly; the upper endpoint is only 0.026 percentage points/year below the margin. This conditional bootstrap result is borderline, without multiplicity adjustment. Moreover its own chemical-prior ledger predicts [0.568, 0.994]%/year, mostly inside the equivalence band: this flatness result cannot discriminate closed-loop control from that small fixed-impulse mass-loss scenario. The population correlation is too uncertain to establish the predicted positive association, and the passive artifact control is unavailable.

## Registration and candidate census

[The registration](correction-quantum-preregistration-20260920.md) was saved before screening or slopes. It fixes the 80% occupancy cutoff, ±1%/year equivalence margin, bootstrap, priors, controls, and stop rule. The user supplied the physics and design first; these numerical operational choices were then frozen. The initial geometry/history screen was saved at `2026-09-20T18:21:52.756419+00:00`; the actual-key audit at `2026-09-20T18:50:35.184808+00:00`. The full candidate census and exact fitting inputs were written before the first regression, at `2026-09-20T18:56:42.080268+00:00`. No candidates were removed after viewing slopes.

| Stage | Objects |
| --- | --- |
| All actual archive object keys (indexed audit) | 68711 |
| At least six years first-to-last retained epochs | 21927 |
| Latest retained mean motion 0.9–1.1 rev/day, eccentricity <0.1 | 1553 |
| GEO/history payloads | 1194 |
| GEO/history debris | 60 |
| GEO/history rocket bodies | 260 |
| GEO/history unknown object type | 39 |
| Payloads with >=40 NSK events | 12 |
| Payloads also passing repeat occupancy | 12 |
| Passive objects passing identical primary gate | 0 |
| Passive objects passing relaxed >=10-cluster-event / >=3-year diagnostic | 0 |

| Object type | 0 NSK | 1–9 NSK | 10–39 NSK | >=40 NSK |
| --- | --- | --- | --- | --- |
| PAYLOAD | 573 | 470 | 139 | 12 |
| DEBRIS | 59 | 1 | 0 | 0 |
| ROCKET BODY | 255 | 5 | 0 | 0 |
| UNKNOWN | 39 | 0 | 0 | 0 |

The maximum payload NSK count is 76. The screened payloads contain 4462 NSK detections in total.

### Archive enumeration correction, before fitting

The initial rollup had 68,051 objects and 183,283,281 rows despite a clean dirty flag. Actual indexed key enumeration found 68,711 objects, including 660 absent from the rollup; 6,395 retained objects had a different first/last epoch pair than the rollup. The [pre-fit audit addendum](correction-quantum-screen-audit-20260920.md) records this discovery and the corrective rule before any slope fits. The same geometry/history thresholds selected 1,553 objects instead of 1,414. Exactly 1,364 completed detections had matching audited identity, endpoints and geometry and were reused; 139 new objects and 50 with corrected endpoints were re-detected with the same code. No original objects were removed, and no selection threshold changed. All counts and fits below use the audited cohort. The initial and supplementary input hashes and GPU receipts are retained separately; no archive summaries were repaired.

The [complete census JSONL](correction-quantum-20260920-census.jsonl) lists every screened object, history span, usable coverage, NSK count, every repeat-cluster count, top-two occupancy, and selection flags. It includes failures as well as successes. This is an archive cohort, not the current teaching catalog. Latest-orbit screening can miss past GEO spacecraft whose most recent retained orbit left the chosen region. Six years of endpoint span does not imply six complete years of observations.

All payloads reaching the count gate are listed below, including occupancy failures; no slopes are fitted for failures. This shows whether selection, temporal support, or scatter limits the probe.

| NORAD / name | History yr | NSK count | Repeat counts | Top two % | Selected? |
| --- | --- | --- | --- | --- | --- |
| 33056 TURKSAT 3A | 18.27 | 64 | 58, 3, 3 | 95.3 | True |
| 33436 ASTRA 1M | 17.87 | 40 | 36, 3 | 97.5 | True |
| 34941 SES 7 (PROTOSTAR 2) | 17.35 | 41 | 38, 3 | 100.0 | True |
| 35943 COMSATBW-1 | 16.97 | 76 | 60, 11, 4 | 93.4 | True |
| 36582 COMSATBW-2 | 16.33 | 49 | 34, 11, 3 | 91.8 | True |
| 37677 CHINASAT 10 | 15.24 | 75 | 55, 14, 4, 2 | 92.0 | True |
| 39216 INSAT 3D | 13.15 | 48 | 42, 5 | 97.9 | True |
| 39500 THAICOM 6 | 12.70 | 50 | 47 | 94.0 | True |
| 39522 TURKSAT 4A | 12.59 | 47 | 46 | 97.9 | True |
| 40880 GSAT 6 | 11.06 | 41 | 19, 16, 5 | 85.4 | True |
| 41029 BADR 7 | 10.86 | 48 | 40, 8 | 100.0 | True |
| 41752 INSAT 3DR | 10.03 | 40 | 40 | 100.0 | True |

## Per-object slopes and class split

All slopes and CI endpoints in tables are **100 × log slope per 365.25-day year**. Thus 1.7 means approximately +1.7% annual quantum growth; the JSONL also supplies exact `100*expm1(beta)` growth. Intervals are equal-tail calendar-year-block bootstrap percentiles (2,000 replicates, seed 20260920+NORAD), conditional on the selected cluster. The point estimator is the median of pairwise slopes, matching the [Theil–Sen definition](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.theilslopes.html). The implementation uses NumPy directly, not SciPy analytical confidence limits.

“Flat-equivalent” requires a 90% CI wholly inside [-1,+1]% log/year, the CI form of two one-sided tests at α=.05; it never means exactly zero. See the [TOST confidence-interval relation](https://support.sas.com/documentation/cdl/en/statug/66103/HTML/default/statug_ttest_details19.htm). Here this is an approximate bootstrap equivalence procedure, not an exact finite-sample test. Positive/negative drift requires a 95% CI excluding zero; flat-equivalent takes precedence. Inconclusive is retained separately. At least six represented calendar years and 95% valid resamples are needed for any inferential class. Classes are exploratory, without multiplicity correction, and do not establish fixed-pulse chemical or closed-loop hardware.

| NORAD / name | NSK / dominant | Top two % | Cluster years | β %/yr | 95% CI | 90% CI | Class |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 33056 TURKSAT 3A | 64 / 58 | 95.3 | 8.47 | 0.915 | [-3.342, 3.844] | [-2.720, 3.435] | inconclusive |
| 33436 ASTRA 1M | 40 / 36 | 97.5 | 14.00 | -0.209 | [-3.446, 2.824] | [-2.760, 2.650] | inconclusive |
| 34941 SES 7 (PROTOSTAR 2) | 41 / 38 | 100.0 | 15.62 | -2.476 | [-6.442, 2.561] | [-5.675, 1.437] | inconclusive |
| 35943 COMSATBW-1 | 76 / 60 | 93.4 | 14.31 | 0.557 | [-0.987, 1.921] | [-0.793, 1.616] | inconclusive |
| 36582 COMSATBW-2 | 49 / 34 | 91.8 | 14.74 | -0.903 | [-4.704, 1.884] | [-3.775, 1.430] | inconclusive |
| 37677 CHINASAT 10 | 75 / 55 | 92.0 | 8.68 | 1.199 | [-7.830, 8.968] | [-6.572, 6.472] | inconclusive |
| 39216 INSAT 3D | 48 / 42 | 97.9 | 8.99 | -0.130 | [-2.317, 2.343] | [-2.032, 2.000] | inconclusive |
| 39500 THAICOM 6 | 50 / 47 | 94.0 | 9.95 | 3.308 | [0.718, 5.958] | [1.125, 5.421] | positive-drift |
| 39522 TURKSAT 4A | 47 / 46 | 97.9 | 8.55 | 1.432 | [-2.926, 4.510] | [-2.252, 4.057] | inconclusive |
| 40880 GSAT 6 | 41 / 19 | 85.4 | 6.97 | 0.405 | [-2.480, 10.843] | [-2.158, 10.311] | inconclusive |
| 41029 BADR 7 | 48 / 40 | 100.0 | 7.47 | 0.175 | [-1.337, 2.048] | [-1.007, 1.549] | inconclusive |
| 41752 INSAT 3DR | 40 / 40 | 100.0 | 9.60 | -0.069 | [-0.563, 1.116] | [-0.493, 0.974] | flat-equivalent |

| Class | Objects |
| --- | --- |
| positive-drift | 1 |
| flat-equivalent | 1 |
| negative-drift | 0 |
| inconclusive | 10 |
| insufficient-time-support | 0 |

| Population quantile | β %/yr |
| --- | --- |
| min | -2.476 |
| 10% | -0.834 |
| 25% | -0.150 |
| median | 0.290 |
| 75% | 0.986 |
| 90% | 1.408 |
| max | 3.308 |

## Slope versus own-ledger prediction

For each dominant cluster, sum the same object’s detected propulsive ledger between its first and last event start (inclusive). The predictor is `sum(Δv) / elapsed_years / v_e`. This is the mean log mass-loss rate implied by that incomplete ledger under a stated exhaust-speed scenario; it follows the [ideal rocket equation](https://www1.grc.nasa.gov/beginners-guide-to-aeronautics/ideal-rocket-equation/). Chemical prior: 2.0–3.5 km/s, reference 3.0 km/s. Electric sensitivity: 10–30 km/s. These are registered scenario ranges, not measured propulsion classes. The observed quantum fit itself uses neither Isp nor mass catalogs.

| NORAD | Median quantum m/s | Ledger / NSK m/s | Ledger m/s/yr | Chemical β range %/yr | Electric β range %/yr | Observed β %/yr |
| --- | --- | --- | --- | --- | --- | --- |
| 33056 | 1.916 | 126.394 / 122.306 | 14.923 | [0.426, 0.746] | [0.050, 0.149] | 0.915 |
| 33436 | 1.853 | 79.687 / 75.726 | 5.691 | [0.163, 0.285] | [0.019, 0.057] | -0.209 |
| 34941 | 1.275 | 62.418 / 56.896 | 3.997 | [0.114, 0.200] | [0.013, 0.040] | -2.476 |
| 35943 | 2.269 | 193.075 / 189.513 | 13.489 | [0.385, 0.674] | [0.045, 0.135] | 0.557 |
| 36582 | 2.077 | 129.063 / 122.388 | 8.758 | [0.250, 0.438] | [0.029, 0.088] | -0.903 |
| 37677 | 3.265 | 200.220 / 194.541 | 23.059 | [0.659, 1.153] | [0.077, 0.231] | 1.199 |
| 39216 | 5.155 | 229.551 / 229.367 | 25.533 | [0.730, 1.277] | [0.085, 0.255] | -0.130 |
| 39500 | 1.638 | 79.330 / 78.991 | 7.976 | [0.228, 0.399] | [0.027, 0.080] | 3.308 |
| 39522 | 1.948 | 92.506 / 89.673 | 10.825 | [0.309, 0.541] | [0.036, 0.108] | 1.432 |
| 40880 | 3.880 | 176.450 / 176.087 | 25.303 | [0.723, 1.265] | [0.084, 0.253] | 0.405 |
| 41029 | 1.613 | 89.812 / 87.046 | 12.017 | [0.343, 0.601] | [0.040, 0.120] | 0.175 |
| 41752 | 5.003 | 190.856 / 190.792 | 19.878 | [0.568, 0.994] | [0.066, 0.199] | -0.069 |

**Spearman ρ = 0.231; 95% paired-object bootstrap CI [-0.607, 0.795]; n = 12.** 10,000 resamples, seed 20260920. Changing a common positive exhaust-speed prior does not change Spearman ranks. The CI resamples objects and does not deconvolve errors in their estimated slopes or ledger rates. Both axes use the same detected Δv values, so correlation is not independent mass validation. Missed thrust lowers the ledger; false flags can inflate it. Consequently the ledger sum is not a guaranteed lower bound on true total propulsive expenditure.

## Passive-population control

All 320 screened passive objects were re-detected identically. They contain 8 NSK-like flags. The largest passive NSK count is 3; no passive repeat group reached the two-event minimum. 0 pass the primary candidate rule. Relaxed controls require >=10 dominant-cluster events spanning >=3 years.

**No eligible passive slope is estimable under the registered primary or relaxed rules. This is a missing artifact control, not evidence that passive drift is zero.**

## Power and scatter

7 / 12 payload candidates have an unestimable CI or a CI floor above 3% log/year, where floor = max(β−L95,U95−β). The stop requires at least 90%, or an empty cohort. **Stop triggered: False.** Among estimable cases, median CI floor = 3.519%/year. Median residual fractional scatter = 16.484% (exp(1.4826 MAD of detrended log Δv)−1).

| NORAD | Residual scatter % | CI floor %/yr | Represented years | Coverage / span yr |
| --- | --- | --- | --- | --- |
| 33056 | 24.629 | 4.256 | 9 | 8.37 / 8.47 |
| 33436 | 20.389 | 3.237 | 11 | 11.14 / 14.00 |
| 34941 | 27.617 | 5.037 | 12 | 14.09 / 15.62 |
| 35943 | 10.137 | 1.544 | 12 | 13.25 / 14.31 |
| 36582 | 13.774 | 3.801 | 10 | 14.19 / 14.74 |
| 37677 | 20.425 | 9.029 | 8 | 8.42 / 8.68 |
| 39216 | 17.500 | 2.473 | 10 | 8.92 / 8.99 |
| 39500 | 12.046 | 2.650 | 10 | 9.81 / 9.95 |
| 39522 | 23.662 | 4.357 | 9 | 7.90 / 8.55 |
| 40880 | 9.740 | 10.438 | 7 | 6.90 / 6.97 |
| 41029 | 15.467 | 1.873 | 8 | 6.75 / 7.47 |
| 41752 | 7.081 | 1.186 | 10 | 8.81 / 9.60 |

This is the registered CI-resolution diagnostic, not an 80%-power calculation. Passing it does not demonstrate sensitivity to the expected 1–3% physical signal: selection and unmodelled systematic error can create falsely precise fits. Better orbit solutions and maneuver/command timing would help distinguish true delivered impulse from element-fit changes, resolve missing small burns, and calibrate the detector across epochs. A DOD-data pitch should request those measurements and blind validation targets, rather than promise a fuel gauge from tighter CIs alone.

## Predeclared sensitivity checks

These are point estimates only, not alternate tests or replacements for the primary fit. The all-NSK fit removes dominant-cluster truncation; the two epoch cuts address historical element-quality changes. A cut requires >=10 events and >=3 years of span. A blank is insufficient support.

| NORAD | Dominant β %/yr | All NSK β %/yr | Dominant since 2013 β %/yr | Dominant since 2021 β %/yr |
| --- | --- | --- | --- | --- |
| 33056 | 0.915 | 1.010 | 0.915 | 2.741 |
| 33436 | -0.209 | -0.648 | -0.894 | -2.330 |
| 34941 | -2.476 | -1.144 | -1.987 | -0.320 |
| 35943 | 0.557 | 1.826 | 0.651 | 0.999 |
| 36582 | -0.903 | 2.134 | -0.217 | 2.136 |
| 37677 | 1.199 | 4.152 | 1.199 | 3.638 |
| 39216 | -0.130 | -0.487 | -0.130 | -3.501 |
| 39500 | 3.308 | 3.182 | 3.308 | 0.400 |
| 39522 | 1.432 | 1.519 | 1.432 | 0.887 |
| 40880 | 0.405 | -4.249 | 0.405 | -2.963 |
| 41029 | 0.175 | -1.017 | 0.175 | 0.223 |
| 41752 | -0.069 | -0.069 | -0.069 | 0.364 |

## Limitations and interpretation

The physical ratio m(t1)/m(t2)=Δv2/Δv1 is conditional on the same **delivered impulse**, not merely similar detected corrections. Command duration, pressure, thrust, calibration, attitude, thruster selection, and operational policy may vary. A positive trend is not unique to mass depletion. A flat trend does not establish closed-loop control. Electric and chemical systems cannot be identified from these slopes alone.

Total detector Δv is the cheapest change consistent with public mean elements, with missing vector and timing information. It is not a measured thruster pulse. NSK flags can combine several burns or include fit artifacts. Detection thresholds censor small changes, and cadence, element rounding, tracking gaps, and natural plane dynamics can change apparent costs. The self-history detector flags departures from an object’s own behavior; it is not a pulse counter. Routine corrections absorbed into its baseline need not become detections, so a sparse NSK ledger does not demonstrate infrequent station-keeping or small true annual expenditure.

The repeat assignment is chronological and path-dependent. Both occupancy selection and dominant membership use the outcome, which truncates scatter and can attenuate long-term growth. Running-median groups can also mix correction families. Bootstrap CIs hold membership fixed and therefore omit selection uncertainty. Whole calendar years preserve within-year dependence but do not protect against multi-year calibration drift or guarantee reliable coverage with few independent years. The 90% equivalence results inherit all these limits.

Detector-era mixing was avoided: the three loaded detector/arithmetic files were independently SHA-256 checked equal to commit `56eef643f600af5635fbdf493eb3361bb1a4896c`; whole histories were processed with these sources, including replacement detections for corrected endpoints. Historical observation-era mixing remains; using one detector does not make pre-2013 and recent orbital solutions statistically identical. No older published-event ledger or newer aggregate false-alarm calibration was spliced into the sample.

The current archive is paged, not transactionally snapshotted for an hour. Each object’s latest allowed epoch was frozen at screening; concurrent backfills before that endpoint could still change a later reread. Exact consumed row hashes and all selected event inputs are retained. Rollup counts were used for initial planning only; the final screening denominator comes from actual indexed object keys/endpoints, and the detection receipt gives actual rows read.

## Artifacts and reproducibility

[Measurements JSONL](correction-quantum-20260920.jsonl) provides one row per screened object. Excluded objects have explicit reasons and null fits (never zero slopes). Eligible payload/control rows include β, 95%/90% CIs, class, scatter, ledger priors, sensitivity fits, and conditional exp(βT) mass ratios. Every row has `usable_as_fuel_odometer=false`: these conditional ratios must not be displayed as measured fuel remaining. They do not estimate initial fuel, dry mass, or propellant fraction. [Selected event inputs](correction-quantum-20260920-inputs.jsonl), [full census](correction-quantum-20260920-census.jsonl), and [receipt](correction-quantum-20260920-receipt.json) make the results inspectable.

The final cohort contains **12,344,058 input rows / 1,553 objects**. Total rows read including superseded detections: 12,552,450. Detection took 1763.4 s summed wall / 535.5 s CPU, nice 19, idle I/O, one reader, 8,192-row pages, WAL / query_only=1. GPU outcome `gpu`, 1599 GPU object passes (including audit replacements), 0 fallbacks. Standard broker queue, 320 MiB ceiling, logical device 0 on the broker-granted card; no GPU/model changes. Existing sweep code wrote its ordinary usage receipt. Source hashes, detector flags, complete cohort facts, I/O counters and artifact hashes are in the receipt.

Analysis tools: [probe](../tools/correction_quantum_probe.py), [report renderer](../tools/correction_quantum_report.py). Stages used were `screen`, brokered `detect`, `audit`, `supplement`, brokered `detect --work <work>/supplement`, `merge`, and `measure --work <work>/final`; the renderer reads only final artifacts. Eight [offline regression tests](../tests/test_correction_quantum_probe.py) pass: production cluster parity (including the absolute tolerance), sign-blind selection, count/occupancy boundaries, equivalence boundaries, known mass-ratio slope with an outlier, sparse-year abstention, tied/degenerate correlation, and refusal to fit an unaudited rollup cohort. No production source, narration, timer, archive contents, or deployments were changed.
