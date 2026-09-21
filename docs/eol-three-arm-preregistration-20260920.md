# EOL census and three-arm registration — 2026-09-20

Frozen before the new detector census or outcome computation. This extends the
published-artifact feasibility probe; it does not change its results. Analysis
only, current post-56eef64 detector, production kappa 32, self-history only.

## Population and provenance

Create a consistent SQLite backup using a source opened exclusively through
`open_archive_for_reading`; analyse that new snapshot through the same opener.
Scan every archive row for any positive mean motion <=2 rev/day, then re-detect
each selected object's ENTIRE history. This conservative screen cannot omit a
GEO/near-GEO event: that branch requires semi-major axis near 42,164 km or
perigee >25,000 km; at least one endpoint then has mean motion <2 rev/day.
No current-catalogue membership restriction, event cap, epoch cut, or payload
restriction on extraction. Preserve passive and unknown-type raise candidates.
Retain every raise with identity, launch date, NSK depth, and exact exposure.
Use broker `gpu-run --class standard`, nice 19 and idle I/O; no CPU fallback.

Freeze local SATCAT inputs by content hash. A raise at or before 18 calendar
months after launch is station-acquisition contamination for this study.
Unknown launch date is unadjudicated, never silently accepted. For each object,
use the first remaining raise as its candidate endpoint; retain all repeats.
This selection is independent of measured pre-event outcomes.

## External ground truth

Audit EVERY raise against the local CelesTrak operational SATCAT and Space-Track
SATCAT (launch/decay/current geometry), recording absence and snapshot date.
Current operational status contradicts TERMINAL retirement at an earlier raise,
but historical reuse/service restoration can explain it and must be reported.
Inactive status plus present perigee >=235 km above GEO is supporting evidence,
not independent confirmation of the historical event date. Active-only catalogue
absence is UNKNOWN, never proof of retirement. Decay alone is not a disposal
confirmation. No orbit-only corroboration is called independent ground truth.
Externally confirmed historical retirement requires dated documentary evidence;
all other analyses are explicitly detector-candidate sensitivity analyses.
Report supporting/contradicting/unknown counts, agreement among assessable and
among all audited candidates, and Wilson 95% intervals. Keep contradictory cases.

## Coverage, cessation and inclined operation

Reuse `eol_policy_probe.window_evidence`, `ratios`, calendar anniversaries and
the production interval builder/segments (maximum joinable gap 3 days). Never
measure a spacing or cessation duration across a broken observation segment.
Zero detections are not zero manoeuvres. Outcomes below refer to detected keeping.

An eligible cessation requires at least three preceding keeping events and two
within-segment spacings in the preceding two calendar years. Its timestamp is
the END of the last detected relevant keeping event; a cadence-free duration
must be >=max(180 days, 3 times the preceding median spacing). Require one
unbroken coverage segment from that last event through the endpoint. The endpoint
is a subsequent raise, or at least 24 calendar months of post-cessation coverage
for a non-raise classification. Record the retrospective confirmation date
separately; cessation cannot have been known on the last-event date.

NS cessation and total (NS+EW) cessation are different signals. Retain their
last-event-to-raise lead times separately, with per-case observation intervals.
Any subsequent relevant keeping restart invalidates a terminal-cessation label.
No observed restart only means through this snapshot; right censoring is explicit.

Post-NS-cessation outcomes, mutually exclusive in this order:

1. First uncontaminated raise within 24 calendar months (candidate disposal).
2. EW keeping extends >=24 calendar months, at least three post-NS EW events,
   with an EW event in the final 180 days and inclination trend 0.5–1.2 deg/year
   over those 24 months (inclined-operation-compatible; 0.85 is a reference,
   not a physical constant). Use monthly median inclination, OLS slope and CI.
3. All keeping ceases with >=24 months uninterrupted follow-up, no subsequent
   raise or detected restart (abandonment-compatible, not proof of death).
4. Otherwise unresolved/right-censored, including a raise later than 24 months.

Arm 2 independently enumerates total cessations without a later raise; it is
not restricted to prior NS cessation. Restrict study cohorts to payloads with
GEO/near-GEO keeping history and known age >18 months at their endpoint.

## Outcomes, controls and statistics — fixed margins

Same primary `R_interval` and secondary `R_dv` as arm 1: final twelve calendar
months / earlier baseline, using NSK detections. Require three years of observed
pre-endpoint exposure, >=3 years NSK calendar depth, and >=3 NSK events plus
two same-segment spacings in each window. Also report total-keeping cadence as
a separately labelled secondary trajectory and annual NSK/EW counts/exposure.

Controls: payloads with GEO keeping, no raise through the endpoint and detected
keeping after it; same calendar windows. Baseline-only nearest-neighbour matching,
without replacement within each arm, sorted by endpoint then NORAD. Require
baseline median inclination within 5 degrees, baseline coverage fraction within
0.15, and baseline NSK interval ratio in [0.5,2]. Minimize the sum of squared
differences scaled by those bounds (log(2) for cadence), NORAD breaks ties.
Outcome availability is reported after matching; do not rematch on final outcomes.

Effect: geometric mean within-pair ratio of R_interval (and separately R_dv),
95% paired bootstrap CI, 10,000 draws, seed 20260920. A cohort below 15 complete
pairs is underpowered: no confirmatory hypothesis test. Descriptive ratios and
bootstrap intervals may be shown for >=2 objects, explicitly exploratory; this
extension supersedes the original probe's stop on all effect estimation.

TOST equivalence margin is [0.8,1.25] on the between-group ratio of ratios,
equivalently +/-log(1.25). At alpha .05, both one-sided t tests must reject;
show its 90% CI. Non-significance never means equivalence. Primary superiority
uses a one-sided within-pair sign permutation of mean log differences, with
Holm correction across arms 1 and 2 if both are testable. Secondary Delta-v
cannot rescue a primary failure. No threshold tuning after looking at results.

Lead-time distributions: empirical n, median, IQR, range, bootstrap median 95%
CI (n>=2); one observation per object per signal. Do not treat censored durations
as observed leads or zero. No population prediction, fuel inference or calibrated
watch score without temporally held-out validation and independently dated labels.

## Deliverables and limits

Report arm 0 flow, three-arm table, both lead distributions, external agreement,
every contradiction, coverage exclusions, honest verdict and reviewer attacks.
Extended JSONL includes evidence, missingness, censoring, both signals, annual
trajectories and `watchEligible=false` unless a later validation earns that flag.
ESA totals constrain only their stated epochs/definitions; never force this
archive to match a historical count with a different denominator.
