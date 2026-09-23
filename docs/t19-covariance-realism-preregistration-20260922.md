# T19 — registration: covariance realism of a megaconstellation's public ephemerides

**Status:** registration. Committed alone, before any code, any fetch beyond the 251 files
T16a already holds, and any number.
**Date:** 2026-09-22
**Track:** T19 of the research programme runbook (`docs/research-program-runbook-20260921.md`,
listed there as NEW, PROPOSED, not started).
**Origin:** thread #1 of `docs/oh-wow-assessment-20260922.md` §5–§6 — the adversarial review's
top-ranked thread, with its three honesty conditions carried into this document as binding
clauses (§10).
**Scope:** measurement only, on files this installation fetches for itself. No site surface, no
cron entry, no systemd timer, no raw redistribution, nothing wired into
`pipeline/orbit_release.py`, `src/`, `public/` or `runtime/`.

---

## 1. The one sentence

For overlapping issues of the same spacecraft's public ephemeris, this track measures how
often the **earlier** issue's prediction of a later instant falls inside the **earlier issue's
own published covariance** at that lead — and, separately, how many distinct covariance values
the operator publishes per lead per axis across a whole issue.

**The word is SELF-CONSISTENCY, never accuracy.** A later issue is a later prediction, not a
measurement. Nothing in this track ranks either issue against truth, and the results document
may not use the words "accuracy", "error", "truth" or "correct" for the residual defined in
§4. This is a binding clause, not a stylistic preference: the residual is a disagreement
between two predictions and attributes to neither.

---

## 2. Prior art, and exactly which part is unoccupied

**Occupied — the self-consistency residual itself.**

- **arXiv:2510.11242.** Compares each three-day Starlink ephemeris against overlapping
  segments from newer issues, over roughly 1,500 spacecraft and two months, reporting about
  300 m position RMSE for stable spacecraft and about 600 m for deorbiting ones. This is the
  same residual this track computes. It is not new here and is not claimed as new.
- **arXiv:2605.19850.** The sibling experiment with the next element set as the reference,
  over 24,641 pairs.
- **`Kira-Ryan/ephemera`** (public archive project, started August 2026). Collects these files
  daily and names its metric "self-consistency, contaminated by re-plans" in those words. Prior
  art both for the archive and for the contamination caveat this track's §6 addresses.

**The method, occupied and applied by providers to their own data.**

- **Park, E. S. et al., "Statistical Covariance Realism [for] a Commercial Space Situational
  Awareness Radar Network", AMOS 2019 (LeoLabs).** Mahalanobis distance of overlap residuals
  against a chi-square expectation; reports 95.2% of distances at or below 4.0, with realism
  holding through seven days. This track uses that method unchanged and cites it as the method.
- Related realism literature: Poore et al., *Covariance and Uncertainty Realism in Space
  Surveillance and Tracking* (2016).

**Unoccupied, and the only thing this track claims as new.** Nobody located has taken the
overlap self-consistency residual of the **public** megaconstellation files and tested it
against the **operator's own published covariance at the same lead**. The residual is
occupied; the covariance is published; the pairing of the two is not. That pairing, plus the
distinct-value census of §7, is the whole of the contribution.

**Deduction against interest, kept deliberately.** The conjunction-assessment literature
describes screening organisations as routinely checking owner/operator ephemeris covariances
for realism. This measurement may therefore be well known inside that practice and simply
unpublished. The framing throughout is **"first public statement"**, never "discovery", and
the results document must carry this paragraph.

---

## 3. The data, and why no frame chain is needed

Source, route, etiquette, storage and redistribution posture are those already registered in
`docs/t16a-ingest-registration-20260922.md` §2.2, §3, §4.3, §5 and §6, unchanged except where
§9 below amends the per-run file ceiling. Files are fetched from `pc`, stay private on `pc`
under `/home/sdegan/space-supplemental-history/starlink/`, gzipped, and only derived facts
leave.

Both sides of every comparison are **the same operator's files, in the same frame** (the header
line the operator writes as `UVW`, states in km and km/s, mean-equator mean-equinox of J2000,
60 s tabulation, 72 h span). **No frame transformation, no time-scale conversion and no
propagation library enters the residual of §4.** T16b needed a TEME→ITRF chain and derived its
residual at ≤ 0.1 m; this track needs none of it, and that absence is the measurement's
cleanest property. Epochs are the file's own `YYYYDDDHHMMSS.sss` tokens, parsed by the reader
already in the repository (`tools/starlink_ephemeris.py`, reused, not forked).

Positions are printed to 1e-10 km (0.1 mm). The state quantisation floor is therefore below
every quantity reported here by at least four orders of magnitude, and is not a floor on
anything in this track.

---

## 4. The statistic, fixed here

### 4.1 A pair

An ordered pair of issues `(A, B)` of the **same spacecraft** — the catalogue field is the
second underscore-separated field of the filename (T16a §7 deviation 2 measured this field
against an independent name join and found 249 of 249 agreements, zero disagreements) — with:

- `created_B > created_A`;
- `start_B > start_A`;
- both files parsing in full, with 21 covariance terms on every record;
- an overlap `[start_B, stop_A]` of at least **12 h**.

`Δ = start_B − start_A` is the pair's **publication cadence**, recorded per pair.

### 4.2 The comparison instants

The comparison instants are the record epochs of issue **A** that lie inside the overlap and
that coincide with the requested lead grid of §5.

The two issues' 60 s grids are generally **offset**, because each issue's grid is anchored on
its own `ephemeris_start` and the seconds field differs between issues. Registered handling,
in this order:

1. If an issue-B record exists within **1e-6 s** of the instant, that record's state is used
   directly.
2. Otherwise issue B is interpolated onto the instant with an **8th-order Lagrange polynomial**
   over the 9 nearest B records (the interpolation degree CCSDS OEM recommended practice names
   for 60 s tabulations), component-wise on position.
3. The interpolation is **not assumed to be free**. Every run performs a leave-one-out
   self-test: for a registered sample of B records, the record is removed, the remaining
   tabulation is interpolated onto its epoch, and the residual is reported as a distribution.
   If the 95th percentile of that self-test residual exceeds **1 m**, the interpolated results
   are reported as interpolation-limited at every lead whose reported residual is within a
   factor of 10 of it, and the affected leads are named.

Issue A is **never** interpolated: the instants are its own record epochs, chosen to be within
±30 s (half a grid step) of the nominal lead.

### 4.3 The residual and its frame

At each instant `t`:

- `d(t) = r_B(t) − r_A(t)`, in metres.
- The covariance frame is built from **issue A's own state at `t`**:
  `Û = r_A/|r_A|`, `Ŵ = (r_A × v_A)/|r_A × v_A|`, `V̂ = Ŵ × Û`. The residual components are
  `d_1 = d·Û`, `d_2 = d·V̂`, `d_3 = d·Ŵ`.
- The identification of covariance column index 1/2/3 with this radial / in-track / cross-track
  triad is **the assumption carried from the operator's `UVW` label**. T16a §6.1 discharged it
  as *consistent* (measured growth ordering axis 2 ≫ axis 1 > axis 3 over 0–12 h matches what
  the label predicts) but not as an independent determination. Every table in the results
  document carries the **column index** beside the axis name, and the results document repeats
  this sentence.
- `P(t)` is the 3×3 position block of issue A's published covariance at `t`, taken from lower-
  triangle indices 0,1,2,3,4,5 as `C11; C21 C22; C31 C32 C33`, in km² and converted to m².
  Issue A's covariance is used at issue A's own record epoch — the covariance is **not**
  interpolated, which is why the instants are A's grid points.

### 4.4 Containment

- `m²(t) = d(t)ᵀ P(t)⁻¹ d(t)`, three degrees of freedom.
- **Primary containment:** the fraction of pairs with `m² ≤ χ²₃(0.95) = 7.8147`. Nominal value
  under a calibrated covariance: 0.95.
- **Comparability containment:** the fraction with `m ≤ 4.0`, the statistic Park et al. report
  (95.2%). For three degrees of freedom `m ≤ 4.0` is `m² ≤ 16`, which is the 99.89th percentile
  of χ²₃; the two numbers are reported side by side and the difference in strictness is stated
  rather than glossed.
- **Per axis:** `z_i(t) = d_i(t)/σ_i(t)` with `σ_i = √P_ii`. Reported: the fraction with
  `|z_i| ≤ 1.96` (nominal 0.95), and the RMS and median of `|z_i|`.
- **Non-positive-definite covariance** (a failed Cholesky factorisation, or any non-positive
  diagonal) excludes that instant, which is **counted and reported**, never silently dropped.

### 4.5 The unit of replication, and the intervals

Instants inside one pair are massively correlated — the residual is a smooth function of time
along one orbit. **The unit is the (pair, lead): exactly one residual per pair per lead.**
`n` at a lead is the number of pairs contributing at that lead, and the interval on every
containment fraction is a **Wilson score interval at 95%** on that `n`. Pooling instants would
manufacture an interval ten to a hundred times too narrow and is forbidden here.

A second, weaker figure is reported for transparency only: the same fraction pooled over all
instants, explicitly labelled as having no valid interval.

### 4.6 The scale factor that would make it calibrated

- **Overall, robust (primary):** `k = √( median(m²) / χ²₃(0.50) )`, `χ²₃(0.50) = 2.3660`.
- **Overall, tail-matched:** `k₉₅ = √( q₉₅(m²) / χ²₃(0.95) )`.
- **Per axis, robust:** `k_i = √( median(z_i²) / χ²₁(0.50) )`, `χ²₁(0.50) = 0.45494`.
- **Per axis, tail-matched:** `k_i,₉₅ = q₉₅(|z_i|) / 1.95996`.

`k > 1` means the published covariance is too small at that lead; `k < 1` means it is too
large. Both are reported with their sign of departure spelled out in words, because "the
covariance is wrong" is not a direction.

**The residual carries both issues' state errors.** If the two issues' errors at the instant
were independent and each had covariance `P`, the residual's covariance would be `2P` and a
containment test against `P` alone would be pessimistic by a factor √2 in `k`. Issue B's lead
at the instant is shorter than issue A's by exactly `Δ`, so B's contribution is smaller than
A's, and the true inflation lies in `(1, √2]`. Every reported `k` is therefore accompanied by
`k/√2` as the **lower bound** on the scale factor attributable to issue A alone. Neither is
presented as the answer; the pair of numbers is the answer.

---

## 5. The lead grid, and what the cadence makes unreachable

Leads from issue A's `ephemeris_start`: **1, 3, 6, 12, 24, 48, 72 h**, tolerance ±30 s.

**Registered in advance:** the shortest reachable lead is the publication cadence `Δ`, because
issue B's span begins at `start_B = start_A + Δ`. The operator publishes roughly three issues
per day, so `Δ ≈ 8 h` and the leads **1, 3 and 6 h are expected to be unreachable**. They are
reported as **UNREACHABLE, n = 0** — never as a number, never silently omitted, and never
filled by pairing an issue with a non-adjacent later issue in order to manufacture a short
lead (which would change the meaning of `Δ` mid-table).

The measured distribution of `Δ` is reported. A second, **native** lead grid is also reported —
the achievable grid `8, 12, 16, 24, 36, 48, 60, 72 h` — so that the table is not mostly empty.
Both grids are declared here, before the data, so neither can be chosen after seeing it.

---

## 6. The re-plan exclusion rule, registered before the data

The files carry **no manoeuvre flag**. A re-plan — the operator revising the planned trajectory
between issues — puts a discontinuity into the residual that is not a covariance matter, and
including it would measure the operator's planning, not the operator's uncertainty. The rule
that identifies one is fixed here.

### 6.1 The physical discriminant, derived

Between two issues that differ only by an initial-condition error, both trajectories are
propagations under the same force model with no impulse applied to either. The difference in
**osculating semi-major axis** between them,
`Δa(t) = a_B(t) − a_A(t)` with `a = ( 2/|r| − |v|²/μ )⁻¹`, is then set by that initial-condition
error and changes over the span only through the *difference* in the non-conservative
(principally drag) decay of two nearby states — a second-order quantity over 72 h.

A manoeuvre inside the overlap changes issue B's orbital energy and not issue A's, and
therefore puts a **step** into `Δa(t)`.

The discriminant is therefore `S = |Δa(t_end) − Δa(t_0)|`, evaluated at the last and first
common instants. This is a derivation with stated assumptions (same force model both sides;
drag differential second-order over 72 h at these altitudes), not a law, and the assumptions
are restated in the results document.

### 6.2 The threshold, and how it is set without looking at the answer

`S` is compared against a threshold `S*`. `S*` is **not** chosen from the measured
distribution of the pairs that will be reported. It is set on a **pre-registered calibration
hold-out**: the pairs whose catalogue field ends in the digit **0** (approximately one pair in
ten, fixed by a property of the spacecraft and not of the data). On that hold-out,

  `S* = 3 × q₉₉( S )`

and the hold-out pairs are then **excluded from every containment and census number reported**.
They buy the threshold and nothing else.

### 6.3 The three exclusion classes, all counted

| Class | Rule | Disposition |
|---|---|---|
| **RE-PLAN** | `S > S*` | excluded from containment; counted; the count and fraction reported per lead |
| **OFF-CADENCE RE-ISSUE** | `\|Δ − median(Δ)\| > 2 h` — an issue published off the operator's own rhythm, which is the operator's own signal that something changed | excluded; counted separately from RE-PLAN |
| **CALIBRATION HOLD-OUT** | catalogue field ends in `0` | excluded; counted; used only for §6.2 |

**Containment is reported both with and without the RE-PLAN exclusion**, so a reader can see
exactly what the rule did. If excluding re-plans moves the headline containment by more than
5 percentage points at any lead, that is itself reported as a primary finding, because it
would mean the rule is doing more work than the covariance is.

---

## 7. The constant-column census

Independent of §4–§6, and computed over **every file of every issue the archive holds**.

An **issue** is a publication cycle, assigned per file from its `created` timestamp by the
8-hourly cycle the operator's own timestamps fall into; the assignment rule and the resulting
cycle boundaries are reported, and files that fall outside any cycle are counted.

For each issue, each lead in `0, 1, 3, 6, 12, 24, 48, 72 h` after that file's own
`ephemeris_start`, and each covariance column index 1, 2, 3:

- `n` = number of files contributing;
- **the number of distinct values of `√C_ii`**, exactly as printed in the file (no rounding,
  no tolerance — distinctness is of the published decimal string's float value);
- the five most frequent values and each one's share of the files;
- the median, and the 5th and 95th percentiles.

Also, per issue:

- the fraction of files with `σ₂(48 h) < σ₂(24 h)` — the non-monotonicity T16a saw at the
  median, now measured per file;
- the same for every adjacent lead pair, so the non-monotonicity is located rather than
  assumed to be a 24/48 property.

**The word "placeholder" is licensed only** if, in **every** issue measured, a lead's distinct-
value count is below **1%** of that issue's file count. Otherwise the finding is stated as
*low cardinality* with the numbers, and nothing is inferred about the operator's intent. The
operator's public ephemeris README (T16a, opened 2026-09-22) documents no covariance
generation method, no default and no cap; the absence of documentation is reported as an
absence and is not evidence of a default.

---

## 8. The consequence: what a placeholder covariance does to a collision probability

Derived, not asserted, and reported with the derivation in the results document.

### 8.1 Method

**Alfano/Foster two-dimensional Pc** (Foster & Estes, NASA JSC-25898, 1992; Alfano, 2005): for
a short-duration encounter, project the combined position covariance and the miss vector onto
the **encounter plane** (perpendicular to the relative velocity), and integrate the resulting
2-D Gaussian over the disk of the combined hard-body radius `R`:

  `Pc = ∬_{|x−x₀|≤R} (2π σ_x σ_z)⁻¹ exp( −½ (x²/σ_x² + z²/σ_z²) ) dx dz`

in the principal axes of the projected covariance. Evaluated numerically, with the quadrature's
own convergence reported.

**The relative speed cancels.** It sets the orientation of the encounter plane and the
short-encounter validity, but it does not appear in the integrand. The **ratio** this section
reports is therefore independent of the crossing geometry's speed, which is stated and shown
rather than assumed.

### 8.2 The geometry, stated

- **Intra-constellation**: both objects are spacecraft of the same constellation, each carrying
  the operator's published covariance at the same lead. This is the case that needs no
  assumption about a third party's covariance, and it is the case the operator screens most
  often.
- Orbital radius: the **median `|r|`** over the collected issue set, reported as a number.
- Crossing angle `θ`: reported over the family `30°, 60°, 90°, 120°, 150°`, with
  `v_rel = 2 v sin(θ/2)` and `v = √(μ/r)` shown, so that the short-encounter assumption can be
  checked by a reader. `θ = 90°` is the representative case, **a chosen representative, not a
  measured typical value**.
- Combined hard-body radius `R = 10 m`. **A chosen conservative screen, not a measured
  dimension**, and labelled as such everywhere it appears.
- Miss distance: a family `0, 100, 300, 1,000 m`, placed along the projected in-track axis and,
  separately, along the projected radial axis.

### 8.3 The two regimes, derived before the numbers

Write `Pc(k)` for the probability computed with the covariance scaled by `k` (the §4.6 scale
factor). In the limit `R ≪ σ`,

  `Pc(k) ≈ (R² / (2 k² σ_x σ_z)) · exp( −d²/(2k²) )`,  `d² = x₀²/σ_x² + z₀²/σ_z²`

so

  `Pc(1)/Pc(k) = k² · exp( −(d²/2)(1 − 1/k²) )`.

- **Near-field (`d → 0`):** the ratio tends to `k²`. A covariance that is too **large**
  (`k < 1`) **understates** Pc.
- **Far-field (`d ≫ 1`):** the exponential dominates and the sign reverses — a too-large
  covariance **overstates** Pc at large miss.

Both regimes are reported. A single ratio would be a misrepresentation, and this document
forbids quoting one without its miss distance.

### 8.4 What is reported

`Pc` with the published covariance and `Pc` with the self-consistent covariance
(published × `k` from §4.6, and the `k/√2` bound), at leads **24, 48 and 72 h**, for the miss
family, with the ratio and its derivation. Leads where `k` is not measurable (§5 unreachable,
or `n` below the §11 floor) produce no Pc number.

**Framing clause, binding:** this is the sentence operators, space-traffic-management
regulators and — weakly, as a governance fact rather than a rating fact — insurers would care
about. It is reported as a **first public statement**, not as a discovery (§2), and it is not
described as showing that anyone's data is wrong.

---

## 9. Collection, and the collector that has no timer

### 9.1 The amendment to T16a

T16a §4.3 caps a run at **250 files** sampled from the manifest. The census of §7 is a
statement about *all files of an issue* and cannot be made from a sample: a distinct-value
count is a function of `n`. **T19 amends the ceiling to the whole manifest, once per
publication cycle** — which is exactly the provider-etiquette principle T16a already applies to
CelesTrak ("download only once per actual update"). Every other T16a rule stands unchanged:
`pc` only, 0.5 s between file requests, no retries, no redirects, no proxy, 32 MiB body
ceiling, attempt timestamp written before the socket, halt on anything unexpected, one ledger
line per attempt including refusals.

Two rules are added:

| Rule | Value |
|---|---|
| Manifest | at most **one fetch per 2 h** |
| Passes | at most **4 per day** (the operator publishes ~3 issues/day; a fourth is slack, not appetite) |

### 9.2 The collector

`tools/starlink_collect.py` — a **daily collector, shipped with no timer and no cron entry**.
It takes a clock, so that its cadence logic can be driven rather than waited for. The operator
decides scheduling; this track installs nothing.

**The estate rule applies and is discharged in this track, not deferred:** the collector is
**exercised now, at two injected clocks, against real files**, and the observed output is
reported. "It will prove itself on tomorrow's run" is not evidence and does not appear in the
results document.

### 9.3 Disk

Raw files stay gzipped under `/home/sdegan/space-supplemental-history/starlink/`. `pc` is at
85% before this track. **Disk free is reported before and after**, and the per-pass footprint
is reported as a measured number, not an estimate.

---

## 10. The three honesty conditions, carried verbatim from the review

1. **A later prediction is not truth.** The word throughout is *self-consistency*, never
   *accuracy*. (§1, binding.)
2. **Re-plans contaminate the residual.** Declared — here, inferred, since nothing is declared —
   manoeuvre epochs are excluded and the excluded fraction is reported. (§6, binding.)
3. **The constant-column claim must be re-measured over more than one deterministic 250-file
   sample before the word "placeholder" is used anywhere.** (§7, binding, with the licence
   condition written out.)

---

## 11. Floors and cuts, fixed before the run

- **No quantiles, no containment fraction and no scale factor are printed for `n < 30` pairs**
  at a lead. Counts only.
- Pairs with overlap under 12 h are excluded and counted.
- Instants whose issue-A covariance fails a Cholesky factorisation are excluded and counted.
- Files that fail to parse are excluded and counted, with the parse error class.
- The census reports `n` files at every cell.
- **A later issue is not truth** — the residual attributes to neither issue.
- **The covariance is unvalidated** against any independent measurement, by anyone in this
  programme. It is the operator's *formal* covariance of a blended solution: a statement about
  a filter. A containment failure is a statement about the pair (residual, published
  covariance) and not about the operator's true uncertainty.
- **The axis-order label is discharged only as consistent** (T16a §6.1), not independently
  determined.
- The publication cadence `Δ` is measured, not assumed; if the measured `Δ` differs materially
  from ~8 h, §5's unreachability statement is re-derived from the measurement and the
  difference is reported as a deviation.

---

## 12. Deliverables

1. This registration, committed alone, before anything else.
2. `tools/covariance_realism.py` — the pairing, the residual, the containment, the scale
   factors, the re-plan rule, the census and the Pc consequence. Reuses
   `tools/starlink_ephemeris.py` as the reader; does not fork it.
3. `tools/starlink_collect.py` — the collector of §9, with no timer.
4. `tests/test_covariance_realism.py` — offline, on fixtures, under the repository's existing
   `python3 -m unittest discover -s tests -p 'test_*.py'`. Three tests assert the bug before
   they assert the fix: (a) a synthetic re-plan discontinuity **must** be excluded and counted,
   and the same pair with the rule disabled must reproduce the contaminated number; (b) a
   constant covariance column **must** be detected as such, and a non-constant one must not;
   (c) containment on a synthetic **calibrated** Gaussian must return the nominal fraction
   within its own Wilson interval.
5. `docs/t19-covariance-realism-results-<date>.md` and `docs/t19-covariance-realism-<date>.json`
   in the receipt shape the programme uses (`study`, `registration`, `registrationCommit`,
   `generated`, `host`, `archive`, `runs`, `sourceSha256`).
6. A T19 row in `docs/research-program-runbook-20260921.md`, replacing the candidate line.

## 13. What this track does not do

- No cron entry, no systemd timer, no scheduled caller.
- No site surface, no `public/data/`, no `src/`, no generated page.
- No raw file from any source is republished, committed, or copied off `pc`.
- No claim about accuracy, about which issue is closer to truth, about the operator's intent,
  or about anyone's data being wrong.
- No claim of discovery — §2's framing is first public statement.
