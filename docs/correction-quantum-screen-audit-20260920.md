# Pre-fit screening audit: stale archive rollups

Recorded during detection, before fitting any quantum slopes on 2026-09-20.
The initial screen trusted `object_rollup` after verifying that
`summary_is_dirty()` returned None. An indexed check subsequently found 2,765
actual rows versus 2,303 rollup rows for NORAD 634, with the same endpoints.
The object metadata has 68,711 entries, but the rollup has only 68,051. The
rollup reports 183,283,281 total rows. The clean flag does not establish that
these summaries are complete. Both sandboxed and ordinary read-only connections
give the same discrepancy. No archive repair is part of this analysis.

Before any slope is measured, audit the original screen against actual
`element_set` keys using indexed object seeks and first/last epoch reads, not
a full row scan. Apply exactly the registered latest-orbit geometry and
six-year history criteria. Include objects missing from the rollup. Preserve
the initial screen, report changed eligibility and actual input counts, and
freeze the corrected census before fitting. Reuse a prior detection only if
its NORAD, name/type, endpoints, and latest orbital geometry match the audited
screen exactly; otherwise run the same detector via the standard GPU broker.

This corrects the archive enumeration implementation, not the hypothesis or
selection thresholds. The >=40 NSK and >=80% occupancy rules, cluster choice,
fit, CIs, equivalence margin, controls, and stop rule remain unchanged. No
slopes have been seen or used to choose this correction.
