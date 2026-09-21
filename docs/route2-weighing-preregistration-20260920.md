# Route 2: drag/SRP weighing — analysis registration, 2026-09-20

Registered before reading target orbital time series or computing their scatter.
The archive schema, month rollup, current catalog schema and candidate counts have
been inspected. No orbital trend or control outcome has been examined. This is a
feasibility probe, not a fuel estimate, and does not authorize a site claim.

Question: can the existing mean elements resolve 2–3%/year increases in effective
area/mass, corresponding roughly to a 10–25% lifetime increase? Drag measures
Cd*A/m and SRP measures Cr*A/m, not mass separately. Projected area, attitude,
surface properties and operations need not be fixed.

## Frozen selection and coverage

- Freeze the current local manifest/catalog and retain hashes. No provider calls.
- Closed interval: 2015-01-01 inclusive to 2026-01-01 exclusive. Do not connect
  this history to 2026 live data. Read only the SSD through
  `open_archive_for_reading`, first assert the file exists and query_only=1.
- LEO: up to 60 catalog civil/commercial payloads launched before 2015, current
  perigee 350–800 km, e<0.02. Exclude attached ISS modules (keep NORAD 25544)
  and explicitly passive calibration spheres. Stratify current perigee into
  350–550, 550–650, 650–800 km; up to 20 per band; ascending SHA256 of
  `route2-20260920:<NORAD>` within band. No outcome-based replacement.
- GEO: first 45 in the same hash ordering, commercial GEO payloads launched
  before 2015, current e<0.02. No tuning toward objects with visible annual cycles.
- Passive means archive DEBRIS or ROCKET BODY, never an assumed inactive payload.
  Select peers from their last 2024 elements, using indexed per-object reads.
  LEO reference matches: perigee within 50 km and inclination within 5 degrees;
  reserve nearest peer as held-out control and use up to 16 further peers as
  normalizers. Each epoch rechecks a tighter 25 km/5 degree match and requires
  >=8 peers. Controls are excluded from *all* normalization pools.
  GEO: one nearest unused passive per target, reference mean motion 0.95–1.05
  rev/day, e<0.05, inclination within 10 degrees; record the actual mismatch.
  Absence of an adequate match is a gap, never a flat control.
- Raw gaps >45 days split arcs. No monthly rate, annual harmonic, or secular
  fit crosses such a gap. Secular fits require >=5 consecutive valid years
  within one continuous raw arc. Keep longest eligible run, earliest on ties.

## Observables and scatter before inference

LEO: daily median semi-major axis from mean motion with WGS72 mu. Within each
calendar month, median of all daily pair rates separated by 3–10 days estimates
decay (negative slope reversed); >=15 observed days, >=20-day span, >=20 pairs.
Require positive decay >=1 m/day and median decay >2 robust pair-rate MAD/sqrt
(number of observed days), a descriptive signal screen, not a formal p-value.
Normalize rates by sqrt(a). Normalizer log rates have their own historical median
removed, preserving their secular drift. Subtract the median normalizer anomaly
in the same month from target log rate; annual median requires >=8 months,
including at least one in every quarter. Holdout uses the same factor with its
own epoch geometry checks. Report rejected months and peer counts.

GEO: compute inertial equatorial components of the eccentricity vector from
e, argument of perigee, RAAN and inclination; do not use scalar e amplitude,
which depends on free-vector orientation. Reduce to weekly medians. Within each
calendar year fit constant + linear nuisance + annual sine/cosine to each vector
component by Huber IRLS. Require >=35 weeks, >=300-day span, every quarter and
no raw gap >45 days. Annual amplitude is sqrt(sum of four annual coefficients
squared / 2), the RMS annual vector norm. Report amplitude, residual scatter,
delta-method amplitude uncertainty and conditioning. Require amplitude >2*SE
and design condition number <100. These are observable-quality screens, not
validation of a physical SRP separation from station-keeping/lunisolar terms.

For each eligible object's yearly log observable: fit a nuisance Theil–Sen line
only to estimate scatter; keep its slope out of inferential results until the
power gate is decided. Let s be the larger of detrended residual RMS (n-2 df),
1.4826*MAD, and first-difference MAD/sqrt(2). An optimistic IID 95% floor is
t(.975,n-2)*s/sqrt(sum((year-mean(year))^2)). Primary floor is the larger of this
and the 95th percentile absolute null Theil–Sen slope from 2,000 circular
moving-block residual bootstrap draws (two annual observations per block).
All bootstraps use a recorded deterministic per-NORAD seed. Log slopes are
converted by 100*expm1(slope) to annual percent. Report n/span and floor
distribution per LEO altitude class, GEO payload, and matched passive class.

A 95% interval excluding zero is not 95% detection power. Also report approximate
80% power minimum effect as primary log floor*(1+0.841621/t(.975,n-2)). This
approximation inherits the noise model and is explicitly not calibrated power.
Provide IID projections for 5/10/15 consecutive annual observations, using measured
s, labeled forecasts assuming stationary noise rather than measured longer arcs.

## Advance/stop rule, controls and cross-prediction

A lane is powered for the proposed cohort study only if >=30 payloads have valid
long arcs and primary 95% floor <=3%/yr, plus >=30 matched eligible controls.
Report the <=2% and <=3% counts regardless. Otherwise stop that lane as
UNDERPOWERED (or NOT ESTIMABLE where missing observables dominate); do not force
trends or correlation through missing years. A few sensitive objects can merit
follow-up without passing the preregistered cohort gate.

Expected control behavior, stated before looking: stable passive geometry implies
approximately zero secular log Cd*A/m or Cr*A/m drift. Tumbling, changing attitude,
HAMR evolution, catalog fits, altitude mismatch and breakup-related correlations
can produce real or apparent drift. Therefore passive != guaranteed constant A/m.
Test flatness using TOST alpha=.05 / 90% CI fully within ±log(1.02)/yr; a
nonsignificant trend is NOT equivalence. If the lane passes, report per-object
robust slopes with 95% block-bootstrap CIs, passive TOST, and Holm-adjusted
positive-trend tests across payloads; control failure blocks mass attribution.

Cross-prediction fixed now: within a physical mass class, larger cumulative
published lower-bound ledger Delta-v predicts larger cumulative log A/m growth
over the *same covered interval*. Delta-v already has units per mass through
specific impulse; do not divide m/s by kilograms. If powered and mass metadata
exist, use 0–500, 500–2000, >=2000 kg launch-mass bins, within-bin rank centering,
Spearman correlation and 2,000 object-bootstrap 95% CI. Report bin counts and
selection/censoring. If unpowered, unavailable or truncated ledger/mass metadata,
report correlation=null, CI=null and the exact reason, never 0 or an invented CI.

## Execution limits and audit

CPU only, nice 19, idle I/O, BLAS one thread. <=20,000 raw rows/page,
<=2,000,000 rows per object, <=1,000 full-history objects, 1,200-second phase
deadline. No archive writes, GPU, timer, ingest, production, src or narration
changes. Only new analysis script/test and dated documentation/artifacts.
Receipt records parameters, hashes, timings, input row digest and exclusions.
JSONL retains one record per target/control with annual measurements, coverage,
null reasons, floor, and inferential status. Offline tests must exercise the hole,
constant/vector annual signal, positive/negative drag and known slope/noise cases.
