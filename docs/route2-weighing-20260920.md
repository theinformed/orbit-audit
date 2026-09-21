# Route 2 feasibility: drag and sunlight weighing, 2026-09-20

**Verdict: the registered controlled cohort study is UNDERPOWERED in both lanes,
for different reasons. LEO lacks usable normalized long arcs. GEO has promising
observable precision, but too few usable matched controls. This is not evidence
that essentially all GEO satellites are too noisy to measure. No fuel or mass
loss is established.**

The question was whether existing orbital observables can resolve roughly
2–3%/year area/mass growth, before trying to interpret secular trends. For GEO,
30/45 payloads have a nominal 95% detectability floor at or below 3%/year;
21/45 are at or below 2%/year. For LEO, only 6/57 eligible selections have enough
consecutive annual measurements to estimate a floor, and 2/57 reach 3%/year.
Missing floors are **not estimable**, not infinity and not zero.

The [registration](route2-weighing-preregistration-20260920.md) preceded orbital
time-series extraction. The [identity audit](route2-weighing-identity-audit-20260920.md)
preceded floor inspection and removed three mislabeled/nonindependent LEO
selections without replacement. The [measurement JSONL](route2-weighing-20260920.jsonl),
[selection](route2-weighing-20260920-selection.json), and
[receipt](route2-weighing-20260920-receipt.json) contain the denominators, individual
annual measurements, rejected observations, coverage breaks, numerical floors,
hashes and resource accounting. These are analysis artifacts; no site surface
has been connected to them.

## Detectability floors — the primary result

All numerical floors below are **annual percentage increases in the observable**,
interpretable as area/mass changes only if other physical factors remain stable.
They are nominal 95% thresholds under the registered residual-noise model,
not calibrated mass-measurement uncertainty. `N` is the number of consecutive
annual observations; their center-to-center time span is `N−1` years.
Statistics describe only objects with measurable floors, never the missing ones.
Altitude classes use the frozen current catalog; historical months separately
pass the drag-regime and contemporaneous matching screens.

| Class | Eligible selections | Measured / missing floors | N, median [range] | Median annual log scatter | 95% floor, median [min–max], %/yr | ≤2 / ≤3% per year | Approx. 80%-power effect, median %/yr |
|---|---:|---:|---:|---:|---:|---:|---:|
| LEO payload, 350–550 km | 18 | 3 / 15 | 6 [5–6] | 0.1080 | **7.43 [5.88–26.53]** | 0 / 0 | 9.79 |
| Matched passive, 350–550 km | 17 | 3 / 14 | 5 [5–6] | 0.0565 | 5.85 [2.48–19.32] | 0 / 1 | 7.46 |
| LEO payload, 550–650 km | 20 | 3 / 17 | 5 [5–9] | 0.0672 | **2.79 [2.38–6.99]** | 0 / 2 | 3.80 |
| Matched passive, 550–650 km | 20 | 4 / 16 | 6 [5–7] | 0.1876 | 11.50 [3.59–24.62] | 0 / 0 | 15.40 |
| LEO payload, 650–800 km | 19 | 0 / 19 | — | — | **Not estimable** | 0 / 0 | — |
| Matched passive, 650–800 km | 19 | 1 / 18 | 10 [10–10] | 0.1068 | 2.75 [2.75–2.75] | 0 / 1 | 3.77 |
| GEO commercial payload | 45 | 45 / 0 | 11 [7–11] | 0.0975 | **2.12 [0.51–17.31]** | 21 / 30 | 2.93 |
| Matched GEO passive | 45 | 25 / 20 | 11 [5–11] | 0.0343 | 1.10 [0.11–16.04] | 17 / 20 | 1.51 |

GEO payload floor interquartile range: **1.22–4.59%/year**. The corresponding
passive range is **0.74–2.39%/year**. These are distributions of precision,
**not measured growth rates** and not evidence that the controls are flat.

For a ten-year time span, 10% cumulative growth is 0.958%/year and 25% is
2.257%/year, rather than 10% and 25% per year. Comparing each GEO object's floor
with its own measured span, **6/45** could nominally resolve a cumulative 10%
change and **24/45** a cumulative 25% change. The median GEO annual floor implies
about 23% cumulative change over ten years. The median approximate 80%-power
threshold implies about 33% over ten years. A 95% confidence threshold is not a
95% probability of detecting a true signal.

Only these six LEO payload selections support a numerical long-arc floor:

| NORAD | Object | Consecutive annual measurements | Floor, %/year |
|---|---|---|---:|
| 25560 | SWAS | 2021–2025 | 26.53 |
| 40014 | BUGSAT 1 | 2020–2025 | 7.43 |
| 39440 | CUBEBUG 2 | 2020–2025 | 5.88 |
| 39427 | TRITON 1 | 2017–2025 | 2.79 |
| 40012 | UNISAT 6 | 2021–2025 | 6.99 |
| 35685 | NANOSAT 1B | 2021–2025 | 2.38 |

Payload classification does not establish propulsion capability or historical
operation. In particular, this table does not establish that either sensitive
LEO object is a suitable fuel-burning test case. Propulsion/attitude curation is
still needed; an old payload is not automatically an old controlled spacecraft.

## Why the registered trend/control stage stopped

The recorded advance rule required at least 30 payloads with floor ≤3%/year
**and** at least 30 usable controls matched to those sensitive payloads.

| Lane | Sensitive payloads | Sensitive payloads with usable matched controls | Required | Decision |
|---|---:|---:|---|---|
| LEO | 2 | 2 | ≥30 and ≥30 | Stop |
| GEO | 30 | 15 | ≥30 and ≥30 | Stop |

LEO's problem is dominated by observation/matching availability. Among the 57
eligible payloads, 2,281 existing monthly groups failed the positive/strong decay
screen, 210 were outside the registered historical drag regime, and 10 failed
monthly coverage. Of the strong months, 2,709 lacked eight contemporaneously
matched passive peers. Another 103 year groups failed annual coverage/arc checks.
These are sequential filter counts with different denominators, not disjoint
causes assignable to whole satellites. Strong-drag missingness is solar-cycle-
and operation-dependent; it cannot be assumed random.

GEO produced 492 accepted payload-year amplitudes, with three more rejected as
unresolved. The selected passive sample produced 261 accepted amplitudes;
26 observed year groups failed coverage, nine crossed a raw gap and one had an
unresolved amplitude. Years with no raw data do not appear as rejected groups.
Only 25 controls formed five consecutive valid years, and only 15 matched a
payload with a ≤3%/year floor.

**The passive matching design itself is a limitation:** nearest reference-orbit
controls were not screened for long historical coverage before selection. A
recent debris object can be an excellent 2024 geometry match and a useless
2015–2025 control. This probe therefore does not prove the archive lacks enough
older passive controls. A separately registered coverage-aware match using
existing data may be sufficient; more precise tracking data are not the only
possible remedy. We did not replace inconvenient controls after seeing results.

Expected control behavior was recorded in advance: stable passive bodies should
show approximately zero secular effective area/mass drift, with exceptions for
tumbling, attitude evolution, HAMR behavior and catalog artifacts. Control
flatness would require TOST at alpha .05, a 90% CI wholly inside
±log(1.02)/year. **TOST was not performed, and no equivalence claim is made.**
Robust secular slopes, their inferential 95% CIs, and payload multiple-testing
results were withheld by the gate. A nuisance line used to estimate scatter is
not being promoted into a fuel-loss result.

## Ledger cross-prediction

The advance prediction remains positive: within a verified launch-mass class,
larger cumulative lower-bound ledger Δv should accompany larger cumulative
log effective-area/mass growth over the same covered arc.

**Spearman rho: not estimated. 95% CI: not estimated.** Machine fields are
`null`, not zero. Both registered cohort gates are closed, so there are no
accepted inferential growth estimates to correlate. This is an untested
prediction, not a null correlation or evidence against the prediction.

There is also an input trap: the frozen population event artifact contains
1,500 selected events out of 105,523 and is not a cumulative ledger. A future
join must use full per-object event histories, verify mass metadata, exclude
events crossing the fitted arc's boundaries/gaps, and retain the detector's
lower-bound/censoring interpretation. The expected local propulsion catalog
was absent at extraction. Do not divide a Δv in m/s by kilograms: mass-class
matching controls heterogeneity; Δv is already a specific kinematic quantity.

## Measurement and uncertainty recipe

The read interval is **2015-01-01 ≤ epoch < 2026-01-01**. The 2026 live segment
is excluded, so the known archive hole cannot enter any fit. Each object's raw
gap over 45 days creates a new arc; monthly, annual and secular reductions never
join those arcs. Only the longest run of at least five consecutive valid annual
measurements in one raw arc enters its floor. There is no interpolation or
filling a missing year with zero growth.

LEO semi-major axes come from mean motion using WGS72 μ. Daily medians feed
within-month median pair decay rates, using separations of 3–10 days. The rate
must exceed 1 m/day and the registered descriptive scatter screen. Rates are
divided by sqrt(a), proportional to density times Cd*A/m for the circular drag
approximation. A fixed set of up to 16 passive normalizers is selected in the
reference epoch; each month requires at least eight within 25 km perigee and
5° inclination. Each peer's log rate is centered on its historical median, and
the contemporaneous median peer anomaly is subtracted from the target log rate.
Annual medians require eight months and every quarter. All held-out controls
are excluded from every normalization pool, including other targets' pools.
The stored LEO annual value retains the arbitrary rate anchor in
`(m/day)/sqrt(km)` divided by a dimensionless cohort anomaly. Its within-object
log change is meaningful; its absolute value is not calibrated A/m. JSONL
includes explicit observable names, units, null mass classes and a prohibition
on mass inference for a future consumer.

For GEO, the fit uses equatorial inertial eccentricity-vector components:

`ex = e*(cos(Ω)cos(ω) − sin(Ω)sin(ω)cos(i))`

`ey = e*(sin(Ω)cos(ω) + cos(Ω)sin(ω)cos(i))`.

Weekly medians are fitted independently each year with a Huber constant,
linear nuisance term and annual cosine/sine in each component. The observable
is `sqrt((Cx²+Sx²+Cy²+Sy²)/2)`. This avoids mistaking changing free-vector
orientation for changing scalar eccentricity amplitude. At least 35 weeks,
300-day span, all quarters and no raw gap are required, with a conditioning and
amplitude/white-noise-SE screen. The white-noise SE is a quality diagnostic;
the long-arc floor uses measured **year-to-year** scatter, not thousands of
element sets treated as independent observations.

For each valid annual series let `y=log(observable)`, `t=year`, and estimate a
nuisance Theil–Sen line. Define `s` as the largest of detrended residual RMS
with N−2 degrees of freedom, scaled residual MAD, and scaled first-difference
MAD/√2. The IID log-slope threshold is

`F_IID = t_(0.975,N−2) * s / sqrt(sum((t−mean(t))²))`.

The primary log floor is the maximum of that threshold and the 95th percentile
of absolute null Theil–Sen slopes from 2,000 circular residual-bootstrap draws,
with two annual observations per block. Seeds are NORAD+20260920. Reported
percent thresholds are `100*expm1(F)`. The approximate 80%-power threshold
multiplies log F by `1 + 0.841621/t_(0.975,N−2)`; it is an analytic approximation,
not empirically calibrated detection power. No residual block crosses an archive
hole because it is drawn from one retained continuous arc.

## What more history would buy, conditional on the same noise

These are **IID projections**, not observed 15-year precision, not promises and
not cohort power. They reuse each measured object's annual scatter and assume
stationary noise and uninterrupted annual observations. Changing operations,
correlated errors, target survival and passive normalization can defeat them.

| Payload class | Measured-scatter objects | Projected median 95% floor, N=5 | N=10 | N=15 |
|---|---:|---:|---:|---:|
| LEO 350–550 km | 3 | 11.49%/yr | 2.78%/yr | 1.40%/yr |
| LEO 550–650 km | 3 | 6.99%/yr | 1.72%/yr | 0.87%/yr |
| LEO 650–800 km | 0 | Not estimable | Not estimable | Not estimable |
| GEO commercial | 45 | 10.31%/yr | 2.51%/yr | 1.27%/yr |

At GEO's median measured log scatter, 11 annual observations give a roughly
2.12%/year floor. To reach 2%/year under the IID formula would require annual
log scatter at most about 0.0918; to reach 1%/year, about 0.0461, compared with
the observed median 0.0975. These are noise targets, not instrument specifications.
For LEO, better cohort coverage and modeling weak-drag intervals matter before
simply collecting more nominal years. For GEO, coverage-aware controls and a
model separating SRP from eccentricity-control operations matter before a mass
interpretation.

## What a reviewer should attack

1. **A/m is not mass.** Physical panel dimensions can stay fixed while projected
   drag/Sun-facing area changes; Cd and Cr need not be constant. Drag observes
   their product with density and area/mass. This identifiability issue is
   explicit in NASA's [ballistic-coefficient mass-estimation paper](https://ntrs.nasa.gov/api/citations/20170005204/downloads/20170005204.pdf).
   Mass loss cannot be isolated by these precision numbers alone.
2. **An annual eccentricity harmonic is not a force-separated SRP estimate.**
   SRP gives an annual eccentricity-vector circle proportional to Cr*A/m, but
   gravity and changing attitude also act; see the CNES
   [eccentricity-management analysis](https://conference.sdo.esoc.esa.int/proceedings/sdc4/paper/83/SDC4-paper83.pdf).
   Commercial GEO operators deliberately control eccentricity, as demonstrated
   in [GEO collocation/station-keeping analysis](https://doi.org/10.1016/S0967-0661(99)00086-6).
   An apparently stable or growing annual amplitude can reflect control policy.
   The present fit includes no force integration, eclipse model, maneuver mask,
   or full lunisolar subtraction. HAMR dynamics require these additional
   perturbations in [Gkolias et al.](https://arxiv.org/abs/1611.08916).
3. **Density cancellation is incomplete.** Nearby perigee/inclination is not
   identical altitude distribution, local solar time, latitude sampling or Cd.
   The fixed normalizer pool changes its contributing membership by month;
   correlated debris families and common attitude changes can bias the median.
   Leave-out controls prevent direct self-normalization, not all common-mode
   error. This probe does not revalidate the atmosphere-factor idea globally.
4. **The control and payload selection need improvement.** Current-catalog
   survivorship, current sector labels, unknown propulsion and operation status,
   nearest-geometry controls without longevity matching, and the three identity
   exclusions limit generalization. In particular, a failed control-count gate
   is not proof that better controls do not exist in the archive.
5. **Nominal 95% is not calibrated coverage.** Five to eleven annual observations
   cannot establish a stable noise process. A two-year block bootstrap may miss
   longer correlations, and nuisance detrending can hide slow systematic drift.
   Using the larger IID and block threshold is a safeguard, not a coverage
   theorem. Quantization, shared orbit-fit errors, survivor selection and
   amplitude/drag censoring can invalidate either approximation. The floors are
   per object; they are not a familywise 95% discovery threshold.
6. **Mean elements and incomplete ledgers are proxies.** No tracking covariance,
   independent spacecraft masses or operator propellant telemetry was used.
   Ledger censoring/missed maneuvers and heterogeneous Isp would limit the
   cross-prediction even after power and controls improve. A positive association
   could reflect common operations or shared element errors.

## Reproduction and verification

Use the existing NumPy environment, CPU only, nice 19, idle I/O and one BLAS
thread. The extraction is capped at 1,200 seconds internally, 20,000 rows per
SQLite page, 2,000,000 rows per object and 1,000 full-history objects. It asserts
the SSD path exists before calling `open_archive_for_reading`, and verifies
`query_only=1`. A missing database cannot invoke the reader's create fallback.

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 \
  nice -n 19 ionice -c 3 timeout 1230 .venv-gpu/bin/python tools/route2_weighing_probe.py
OPENBLAS_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 \
  nice -n 19 .venv-gpu/bin/python tools/route2_weighing_report.py
OPENBLAS_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 \
  nice -n 19 .venv-gpu/bin/python -m unittest discover -s tests -p test_route2_weighing_probe.py -v
```

The finalizer applies the separately recorded identity exclusions and refuses to
emit a stopped-study result if a cohort power gate is open. Reproduction reads
the then-current local manifest; the stored selection/catalog hashes identify
this run, and a changed catalog is a different sample. The archive was not held
under one long transaction or copied; per-object row digests identify the
actual data read, but concurrent historical corrections could change a rerun.

Five offline fixture tests pass: a real temporary SQLite fixture rejects writes,
respects the closed read window and records raw gaps; no cross-hole/missing-year fitting; oriented
eccentricity vector and injected annual-amplitude recovery; decay sign and exact
common atmosphere cancellation with an insufficient-peer negative control;
and noise-floor scaling/trend invariance plus JSON receipt serialization.
A preliminary extraction failed only when serializing a NumPy count into its
receipt; the type conversion was fixed and the bounded extraction repeated.
The final extraction read **3,678,326 raw rows from 755 objects**, including
normalizers, in **335.84 seconds wall / 254.96 seconds CPU**, with peak RSS
**143,512 KiB (140.15 MiB)**. These are final-pass costs, excluding the failed
preliminary receipt run. SQLite reported **query_only=1, WAL**.

The final JSONL has **207 records**, including four explicitly identity-excluded
records (three payloads and one matched control); 203 records enter summaries,
and 84 have measured floors. Its SHA-256 is
`f2d7353613369d6482baa416fe08d04d034391cc8554f20522b6b5a8bc922350`.
An independent final check reconciled all summary counts, recomputed all 84
floors from retained annual measurements, checked each fitted run's continuity
and single-arc identity, verified zero overlap between controls and normalizers,
verified source/artifact/registration hashes, and confirmed every inferential
trend and ledger-correlation field obeys the closed gates. All checks passed.

Only new analysis/docs/test files were written. No GPU, model, timer, archive,
ingestion, production source, narration or deployment changes were made.
