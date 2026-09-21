# Phase 3 pre-registration: the covariate-aware gate

Registered 2026-09-21, **before any Phase 3 code, measurement or result
exists**. This document is committed alone, ahead of everything Phase 3 will
ever produce, exactly the way `docs/paperb-preregistration-20260920.md` was
committed ahead of Paper B's results at `f317a28`. The git history of this
file is the timestamp. Nothing below may be changed after a Phase 3 number
exists; an awkward outcome is reported, not edited away.

This document does **not** implement Phase 3. No source file is touched by
it. It registers what Phase 3 will estimate, the rule that will decide
whether the covariate-aware gate ships, the concrete passive-exposure
experiment the registered result says is needed, an open boundary question
that Phase 3 must not quietly resolve as a side effect, and the conditions
under which Phase 3 stops.

## 0. Why Phase 3 exists

`docs/paperb-preregistration-20260920.md` (committed `f317a28`, amended
`8604de2`) registered a covariate-matched transfer test for the pooled
selfHistory passive false-alarm floor. `docs/paperb-results-20260920.md`
(measured on the analysis code at `d4c09ee`/`46dee20`, over the archive pass
serialised at `dd93370`, and reported at `7626c55`) found:

- The raw pooled passive floor is **0.163 per 1,000** usable intervals.
- Reweighted onto the payload covariate mix it is **0.335 per 1,000**
  (2.0591x raw) — Analysis 1's own registered rule (i) and (ii) **both
  fail**: the primary clustered-bootstrap 95% upper bound is **26.19 per
  1,000**, 26x the 0.001 target, and the reweighted/raw ratio clears the
  registered 2x ceiling.
- Restricted to the registered stricter support tier (`S_1000`: strata with
  at least 1,000 passive intervals), the reweighted floor is **0.224 per
  1,000** (1.3737x raw) with clustered-bootstrap 95% interval **[0.154,
  1.846]** — narrower, but the upper bound is still above target, and 13.358%
  of payload exposure now sits in labelled gaps.
- Separately, Analysis 2b found the shipped 30-degree high-inclination
  corroboration boundary does not hold the equivalence it was justified by:
  the exact 90% interval at 30 degrees is [0.6316, 0.6865], and equivalence
  at the registered 1.5x margin does not hold continuously until roughly
  **54 degrees** ([54,180) through [74,180) all pass; the registered
  monotone-stability rule then finds no boundary at all because equivalence
  fails again at 76-82 degrees).

This task (2026-09-21) disclosed that finding in the shipped `selfHistory`
control block (commit disclosing `covariateTransfer`, this repository's
`integration/space` history immediately before this file) and corrected the
factually wrong abstention-gap justification string (the preceding commit on
the same branch). Neither of those changes altered any threshold, gate or
rate. **Phase 3 is the work item that would.** This document registers it
before any of that work starts.

## 1. Estimand

Phase 3's gate quantity is the **payload-covariate-reweighted passive false
alarm floor**, not the pooled passive floor `control_rates_by_object` ships
today. Concretely, reusing Paper B's registered machinery without
modification:

- Strata: the same four factors and bands registered in
  `docs/paperb-preregistration-20260920.md` §2 (perigee, inclination,
  eccentricity, TLE cadence) — no new cut point.
- Point estimate: `R_rw = sum_{s in S_1000} w_s * r_s`, where `r_s` is the
  per-stratum passive rate and `w_s` is that stratum's share of **payload**
  exposure, restricted to the **>=1,000-passive-interval support tier
  (`S_1000`) as the PRIMARY estimand** — not the `n_s^P >= 1` tier Analysis 1
  used as its headline. The results already show why: at `S_1000` the
  bootstrap upper bound is 1.846 instead of 26.19. A gate cannot be built on
  an estimator whose upper bound is a labelled-gap artefact of single-flag
  strata; the `S_1000` tier is Phase 3's registered floor, not a fallback.
- Uncertainty: the same **object-level clustered nonparametric bootstrap**
  registered in `docs/paperb-preregistration-20260920.md` §4 (draw passive
  objects with replacement, recompute every `r_s` and hence `R_rw` per
  resample, percentile 2.5/97.5), because it is the only registered interval
  that carries object-level non-independence rather than treating intervals
  as exchangeable. Phase 3 registers its own run of this estimator — **2,000
  resamples, seed 20260921** (this document's date, following the paperb
  convention of seeding by registration date) — rather than reusing Paper B's
  seed 20260920, so that no single bootstrap draw is ever reused across two
  registered decisions.
- Payload exposure weights `w_s` are held at their **observed** values, for
  the same reason Paper B held them: the target is the payload covariate
  distribution as it actually is.
- Unsupported payload exposure (payload weight in strata below `S_1000`) is
  reported every time this estimand is reported, **never imputed, never
  dropped**. Currently, on the archive Paper B measured, that share is
  **13.358%**.

Phase 3 measures nothing about the cohort detector's own control; this
estimand replaces only the selfHistory passive-side denominator that today's
`sufficientToLabel` gate checks.

## 2. Acceptance rule

Stated now, before any Phase 3 number exists, and reusing two numbers this
codebase already treats as load-bearing rather than inventing new ones:

**The covariate-aware gate may replace the pooled gate, and the shipped
wording may change to describe the reweighted floor, if and only if:**

1. **`R_rw`'s primary clustered-bootstrap 95% upper bound is below the
   existing published target, `targetRatePerInterval = 0.001`** (1 per 1,000
   usable intervals) — the same target `_control_rates` already checks
   against the pooled floor, unchanged.
2. **The reweighted separation is at least 10x**: the payload rate's
   reweighted lower bound divided by `R_rw`'s upper bound meets or exceeds
   `MIN_SEPARATION_BOUND_RATIO = 10.0` (`pipeline/orbit_events.py`), the same
   constant and the same bound-to-bound `separation_verdict` logic
   `_control_rates` already applies to the pooled rates today. Phase 3 does
   not invent a new separation standard; it applies the existing one to the
   reweighted quantity.

Both clauses must pass. Either clause failing means the covariate-aware gate
is **not** sufficient to ship, and the existing pooled-floor gate keeps
governing `sufficientToLabel` exactly as it does today — Phase 3 failing is
not a licence to relax the pooled gate, remove the disclosure this task
added, or quote the point estimate without its bound.

On the Paper B `S_1000` numbers alone (0.224 point, upper bound 1.846),
clause 1 already fails by nearly 2x. This is written down now, before any
Phase 3-specific measurement, so that a reader can see Phase 3 is not
expected to pass on today's exposure — it is registered as the test of
whether the exposure experiment in §3 changes that.

## 3. The named passive-exposure experiment

The registered reading of the Analysis 1 result (`docs/paperb-results-
20260920.md`) is explicit: *"What is missing is passive exposure in the
strata where payloads actually live... A denser or covariate-targeted passive
sample is the experiment this result asks for."* Phase 3 registers that
experiment's target list now, pulled directly from
`docs/paperb-strata-20260920.jsonl` (the stratum-level receipt, `policy:
"on"`, `passiveSupported: true` rows), not re-derived or rounded from the
prose report:

**Top 10 payload-weighted strata below the 2,000-passive-interval thin-tier
line** (150 such strata carry 18.212% of payload weight in total; these ten
alone carry 15.156%):

| Stratum | Passive intervals | Passive flags | Payload weight | Shortfall to `S_1000` (1,000 passive intervals) |
|---|---:|---:|---:|---:|
| `300-500 km \| 30-60 \| <0.001 \| 0.25-1 d` | 512 | 1 | 5.134% | 488 |
| `>2000 km \| 0-1 \| <0.001 \| 0.25-1 d` | 1,773 | 3 | 3.242% | 0 (already `S_1000`; still thin at the 2,000 line) |
| `500-800 km \| 30-60 \| <0.001 \| <0.25 d` | 1,206 | 0 | 1.952% | 0 (already `S_1000`) |
| `300-500 km \| 90-120 \| <0.001 \| 0.25-1 d` | 582 | 0 | 1.122% | 418 |
| `>2000 km \| 0-1 \| <0.001 \| 1-2 d` | 565 | 1 | 0.818% | 435 |
| `300-500 km \| 30-60 \| <0.001 \| <0.25 d` | 133 | 0 | 0.771% | 867 |
| `>2000 km \| 0-1 \| <0.001 \| <0.25 d` | 366 | 1 | 0.736% | 634 |
| `500-800 km \| 30-60 \| <0.001 \| 1-2 d` | 1,747 | 0 | 0.681% | 0 (already `S_1000`) |
| `300-500 km \| 30-60 \| <0.001 \| 1-2 d` | 38 | 0 | 0.390% | 962 |
| `300-500 km \| 90-120 \| <0.001 \| <0.25 d` | 162 | 0 | 0.310% | 838 |

Reading the table: the dominant regime is **low perigee (300-800 km),
30-120 degrees inclination, near-circular eccentricity (`<0.001`)** — exactly
the low-altitude operational-payload belt, and precisely the regime the
results report names. Six of the ten rows need real additional passive
exposure to clear even the `S_1000` primary tier; the other four already
clear `S_1000` but remain thin enough (under 2,000) to swing the bootstrap
the way the results report describes.

**The experiment Phase 3 registers**: a covariate-targeted passive sampling
pass — widening the `norad % 5 == 0` systematic sample specifically within
these low-perigee, near-circular, moderate-inclination strata (a stratified
oversample of the existing archive, not new tracking data) — run **read-only**
through the same `orbit_campaigns.open_archive_for_reading()` path Paper B
used, under the same resource bounds (§6). Its pre-registered success
condition is not a fixed interval count chosen now (that would be exactly the
kind of after-the-fact target the paperb prereg's §10 prohibits picking once
a number is visible); it is stated as a **stopping condition** in §5 below.
No stratum boundary, band edge, or the eccentricity cut is touched — this is
sampling depth only.

## 4. The boundary question, registered as a question and not a decision

Analysis 2b/2a (`docs/paperb-results-20260920.md`) measured the shipped
`INCLINATION_CORROBORATION_MIN_DEG = 30.0` boundary against its own
justification and found: the exact 90% ratio interval at 30 degrees is
[0.6316, 0.6865] — **not** equivalent at the registered 1.5x margin — and
equivalence holds continuously only from roughly **54 degrees** ([54,180)
through [74,180) all pass) before failing again at 76-82 and passing again at
84-86 (the registered monotone-stability rule therefore returns **no**
data-driven boundary at all, which is itself the honestly registered
outcome, not a defect in the scan).

**This is flagged here as an open question, not resolved here, and Phase 3
must not resolve it as an incidental side effect of building the
covariate-aware gate.** The reason is structural, not a matter of caution for
its own sake: `INCLINATION_CORROBORATION_MIN_DEG` is a **detector** constant
— it changes which intervals get flagged in the first place — while
everything in §§1-3 above is a **control** change, reweighting and
resampling flags the detector already produced. Moving the boundary changes
the numerator every downstream control measures. Concretely, if
`INCLINATION_CORROBORATION_MIN_DEG` is ever moved (to 54, to something else,
or removed), that change:

1. **requires its own pre-registration**, sibling to this one and to
   `docs/paperb-preregistration-20260920.md`, committed before any measurement
   under the new boundary exists;
2. **requires the pooled and covariate-aware selfHistory controls to be
   re-measured from scratch** against the new boundary — every number in
   `docs/paperb-results-20260920.md` and every number this document's §§1-3
   estimator would produce assumes 30 degrees, because the detector's flag
   population changes below the new line;
3. **is out of scope for whatever pull request implements this document**,
   even if that implementation happens to also touch
   `pipeline/orbit_campaigns.py` near the boundary constant for unrelated
   reasons. A Phase 3 change touching `INCLINATION_CORROBORATION_MIN_DEG` in
   the same commit as the covariate-aware gate is a registration violation of
   this document, not a convenience.

Phase 3, as registered here, takes the 30-degree boundary and the existing
corroboration rule **as given, unchanged inputs**. The measured 54-degree
matched region is recorded so that whoever eventually registers the boundary
re-evaluation does not have to re-derive it, and so that it is visible that
this document knew about it and chose not to act on it here.

## 5. Stop rules

Registered before any Phase 3 measurement, in the same spirit as
`docs/paperb-preregistration-20260920.md` §10 ("no metric shopping"):

- **Exposure-collection stop rule (primary).** The covariate-targeted passive
  pass in §3 stops and reports, honestly, as soon as **either**: (a) every
  one of the ten named strata reaches `S_1000` (>=1,000 passive intervals)
  and the resulting `R_rw` bootstrap 95% upper bound is recomputed against
  §2's acceptance rule, whatever that recomputation shows; or (b) the
  resource budget in §6 is exhausted first, in which case the partial result
  and the strata still short are reported exactly as thin, never silently
  filled or excluded. There is no third outcome where collection continues
  past (a) hunting for a friendlier number.
- **No re-running the bootstrap to taste.** The seed is fixed at 20260921
  (§1). If a resample run produces an unfavourable upper bound, that is the
  registered result; the seed is not changed and the estimator is not
  swapped for the Beta-draw composite (Paper B's registered secondary, which
  is itself declared conservative in advance) to rescue it.
- **The acceptance rule in §2 is binary and both clauses are required.** A
  result that clears clause 1 but not clause 2, or vice versa, is reported as
  **"the covariate-aware gate does not yet ship"**, not as a partial win
  quoted without its failing half.
- **The boundary question in §4 is never touched by a stop-rule failure
  here.** If the exposure experiment in §3 fails to clear the acceptance
  rule even after (a), the correct registered response is to report that the
  low-perigee, near-circular, 30-120-degree belt's passive floor still does
  not bound the payload population at 1-in-1,000 — not to fall back on moving
  the corroboration boundary as an alternate route to a shippable number.
  Any such move re-enters at the top of §4.
- **No production system is touched by any of the above.** Exactly as Paper
  B's own §11 required: read-only archive access, `PRAGMA query_only=1`, the
  running `orbit_release` sweep is left alone, no threshold in shipped code
  changes as a result of measurement alone — a threshold changes only through
  a separate, reviewed implementation commit that cites this registration and
  the measured result together.

## 6. Resource bounds

Identical in kind to `docs/paperb-preregistration-20260920.md` §11: read-only
connection, `PRAGMA query_only=1`, WAL, `nice 19`, idle I/O, at most two
concurrent readers, per-reader cooperative/hard wall-clock budgets, resumable
cursors under a dedicated `/tmp` prefix (`/tmp/phase3-20260921`, sibling to
Paper B's `/tmp/paperb-20260920`), no GPU required, and — should one ever be
needed — routed through `/home/sdegan/gpu-broker/gpu-run` exactly as before.
The host's unrelated load has priority over this experiment, exactly as it
did over Paper B's.

## 7. Deliverables (once Phase 3 work actually starts — not shipped by this commit)

1. This pre-registration, committed alone, ahead of every Phase 3 artefact —
   satisfied by this commit.
2. The covariate-targeted passive-exposure pass described in §3, with its own
   offline-testable module and a results table keyed to the same ten strata
   named here.
3. A `docs/phase3-results-<date>.md` reporting the estimand in §1 against the
   acceptance rule in §2, whichever way it comes out, with the stop condition
   that ended collection stated explicitly.
4. If and only if §2 passes: a separate, reviewed implementation change that
   swaps the gate's denominator and updates the shipped wording — never in
   the same commit as the measurement, and never touching
   `INCLINATION_CORROBORATION_MIN_DEG` (§4).

## Commit references

- `f317a28` — Paper B pre-registration (covariate-matched transfer and
  inclination analyses), committed ahead of every Paper B result.
- `8604de2` — Paper B amendment 1 (Analysis 2 measured pre-corroboration),
  committed ahead of every Analysis 2 result.
- `d4c09ee` — Paper B analysis modules, with offline tests, before any result
  existed.
- `46dee20` — `paperb_measure` resume-cursor double-count fix.
- `dd93370` — orbit sweep single-writer serialisation (the archive pass this
  measurement read).
- `7626c55` — Paper B results: the floor does not transfer, and the
  inclination band is not where the detector ships it.
- `dabf0f0` — Paper B draft, the audited false-alarm control, including the
  two tests it failed (the current tip of this branch as this document is
  written).
