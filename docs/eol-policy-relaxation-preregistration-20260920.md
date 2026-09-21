# EOL policy-relaxation feasibility probe — registration, 2026-09-20

Transcribed from the user's pre-registration before reading per-object retirement
histories. Analysis only; no detector, publication, timer or ingestion changes.

Hypothesis: GEO objects approaching a detected graveyard raise stretch their
north–south station-keeping (NSK) intervals and/or reduce per-correction Delta-v
in their final twelve months relative to their own earlier history.

Frozen outcomes:

- `R_interval`: median final-year NSK inter-correction spacing divided by the
  median prior-baseline spacing.
- `R_dv`: median final-year per-NSK-event lower-bound total Delta-v divided by
  the median prior-baseline value.
- Exactly the same ratios and calendar windows for matched GEO controls with
  no detected graveyard raise in those windows.

Retirement time is the start of the first published self-history
`geo-graveyard-raise` for an object. Retain every raise in the census, but count
each object once. Final year is [T minus one calendar year, T); baseline is all
available history before that year. Leap-day anniversaries clamp to February 28.
Only events wholly within their window qualify. Use a single frozen published
release, self-history events only, without mixing cohort or fresh detections.

First stop rule: fewer than 15 usable distinct retirees means **underpowered**;
do not run controls, a significance test, effect-size estimation or confidence
intervals after that stop. First calculate an intentionally generous eligibility
upper bound: a detected NSK event at least three calendar years before T. If
even that count is below 15, the stop follows without imposing extra coverage
thresholds. Otherwise require three years of gap-qualified observed exposure,
NSK detections in baseline and final year, and estimable medians in both windows.
Report calendar depth and observed exposure separately; a long calendar span
alone never demonstrates three years of usable history.

Cadence must reuse `MAXIMUM_JOINABLE_GAP_DAYS`, `intervals_from_rows`, and
`_segments` from `pipeline.orbit_campaigns`. Consecutive NSK starts must belong
to the same observed segment; do not discard a long spacing merely for being
long when observations continue throughout. Require at least three events and
two retained spacings per window, matching the existing cadence doctrine.
Do not bridge window boundaries. Missing medians/ratios are null, never zero or
infinity. Coverage is read only from the SSD through `open_archive_for_reading`;
check that the database exists before calling its missing-file fallback.

If the census passes, match one distinct control per retiree without replacement
using baseline-only GEO geometry, archive coverage and NSK cadence; freeze the
match specification before reading final-year outcomes. Primary significance:
one-sided matched-pair label-permutation test on the mean within-pair difference
in log R_interval, alpha 0.05. This is a two-group test respecting the matching;
do not use an independent-observation test on matched pairs. Primary effect is
the exponentiated mean log-ratio difference, with a 95% confidence interval by
resampling whole matched pairs (10,000 draws, seed 20260920). Report raw group
distributions as well. Delta-v is secondary/descriptive and cannot rescue a
failed interval hypothesis. Fifteen is the requested feasibility floor, not a
formal guarantee of statistical power.

The permitted published release may predate commit 56eef64. Its own false-alarm
context must accompany the census; never substitute the newer code's calibration
for older published events. Detected retirement labels are operational study
labels, not independent operator-confirmed ground truth.
