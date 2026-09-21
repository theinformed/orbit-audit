# Correction-quantum drift: registration

Registered 2026-09-20, before examining candidate quantum/time relationships.
This operationalizes the user's pre-registered hypothesis; thresholds below are
analysis choices made before the census, not thresholds chosen from slopes.

## Population and selection

Use the read-only SSD archive through `open_archive_for_reading`, checked to
exist before opening. Start with all archive objects, not the teaching catalog.
GEO screening: the most recent retained element has mean motion 0.9–1.1 rev/day
and eccentricity <0.1. This includes inclined and graveyard GEO-region objects;
it can miss objects whose latest orbit left that region. Record this limitation.
Require at least six 365.25-day years between first/last retained epochs.
Re-detect whole histories with one current post-56eef64 detector, kappa 32,
unchanged flags and `gpu-run --class standard`; no mixed published events.

Payload candidates require >=40 positive finite `geo-north-south-keeping`
events. Apply the existing chronological running-median repeat algorithm,
relative tolerance 0.35 and absolute tolerance 0.02 m/s. The largest two repeat
clusters must contain >=80% of the object's NSK events. Rank clusters by count,
breaking ties by original creation order. Fit the dominant cluster only.
No exclusions based on slope, sign, CI width, mission name, or apparent class.
Freeze the census and exact selected event records before fitting slopes.

Controls: all DEBRIS and ROCKET BODY objects passing the same GEO/history screen;
first report the identical >=40/80% gate. Also report any dominant NSK pseudo-
cluster with >=10 events spanning >=3 years as an explicitly relaxed diagnostic,
not a replacement primary control. A missing control is not a zero slope.

## Estimands and inference

Fit log(total lower-bound Delta-v in m/s) against event start time in
365.25-day years, using the Theil–Sen median pair slope. Retain unrounded
detector costs. Report beta in log units/year, 100*beta (% log/year), and
100*expm1(beta) (% growth/year), plus residual 1.4826*MAD in log units.
Use 2,000 calendar-year pairs-cluster bootstrap replicates (whole years
resampled with replacement, original time coordinates), seeded 20260920+NORAD.
Report percentile 95% and 90% intervals; require >=6 represented years and
>=95% finite bootstrap replicates for inferential classification. Otherwise
retain the point estimate with an explicit insufficient-time-support status.

Flat-equivalent requires the entire 90% interval strictly inside
[-0.01,+0.01] log/year: CI dual of two one-sided tests at alpha .05.
Positive/negative drift requires a 95% interval strictly above/below zero;
flat-equivalent takes precedence, and all remaining cases are inconclusive.
These are exploratory per-object fingerprints without familywise correction,
not verified thruster hardware/command-policy classes. Report counts and the
population slope quantiles; do not equate failure to detect with flatness.

For each candidate, sum its own detected propulsive ledger within the dominant
cluster's first-to-last start-time window (exclude repository non-propulsive
signatures). Divide by elapsed years and scenario exhaust speed. Chemical
scenario: 2,000–3,500 m/s, reference 3,000; electric sensitivity: 10,000–30,000
m/s. These are explicit broad class priors, not catalog classifications or
measured Isp. The prediction beta = summed Delta-v/(elapsed years * v_e)
follows log(m_start/m_end)=summed Delta-v/v_e. Also report NSK-only sum.
Observed fixed-impulse expectation: positive 1–3%/year and positive association
with this ledger proxy; closed-loop expectation: equivalent to zero. Neither
prediction licenses a mass estimate without stable delivered impulse.

Report Spearman correlation between measured beta and the chemical-reference
ledger slope, with a 95% paired-object bootstrap CI, 10,000 resamples, seed
20260920. Require >=3 objects and >=95% nondegenerate resamples; otherwise
report the reason a CI is not estimable. This association shares the same
measurements on both axes and is not independent mass-loss validation.

## Power and predeclared sensitivity

CI floor means max(beta-L95,U95-beta). Stop as UNDERPOWERED if >=90% of
candidates have a floor >0.03 log/year or unestimable intervals. An empty
cohort is selection-limited UNDERPOWERED, not a scatter result. Report the
measured scatter even if the stop fires; do not loosen candidate thresholds.

For each fitted candidate, also fit all NSK events without cluster truncation,
and fit the dominant cluster restricted to epochs >=2013 and >=2021 where
there are >=10 events and >=3 years. These are point-estimate sensitivity
checks only, never rescue analyses or replacement primary results. Historical
element quality can change despite a consistent detector. Record cluster
span, coverage, gaps, and temporal concentration. Cluster selection on the
outcome can suppress real long-term drift and create artificially narrow CIs.

All runs use nice 19, idle I/O, bounded threads, paged selected-object reads,
one reader, broker admission, and resource receipts. No source, narration,
production timer, archive content, or deployment changes. New tools and docs
only. Retain per-object JSONL, the frozen census, input/source hashes, and
offline statistical/selection validation evidence.
