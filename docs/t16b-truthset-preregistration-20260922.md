# T16b pre-registration — the truth set: element-set error growth against precise orbits, and burn-detection recall against labelled manoeuvres

**Registered 2026-09-22. Committed alone, before any number is computed.**
Track T16(b) of the research programme runbook
(`docs/research-program-runbook-20260921.md`, T16 row, feasibility verdict
STRONG). This document fixes two measurements, their data, their decision
rules, their gates and the sentences they are allowed to produce. It contains
no result. Where it quotes a number, that number is a constant already
committed elsewhere in this repository or a property of a published product,
and its source is named at §8.

---

## 0. Why this track exists, and what it is not

Every element set this programme has ever used is a fit to observations we
cannot see, published without an error bar. Two quantities that the results
documents mark UNMEASURED follow from that:

1. **How wrong a propagated element set is, and how fast it gets wrong.**
   The orbit-section design draws a LEO phase ribbon from `σ_n` alone —
   0.023 °/day at the median, `docs/orbits-section-design-20260922.md` §2.2 —
   and states in the same table that **no forward error is measured for LEO**.
   The kinematic design carries the same hole as **M2** (§9, "per-object LEO
   phase-error growth vs σ_n and drag history"), and forbids drawing any LEO
   member interval until it is measured.
2. **What fraction of real manoeuvres the detector sees.** T8b measured
   precision (44.1% on its own alert channel), a lead time (195.9 d) and a
   never-manoeuvred control (0 events / 18.79 M object-days), and states that
   **recall is not measurable there**. The alarm lane repeats it for every one
   of its nine operating points. Paper B says the same. Nothing in the
   programme has ever compared a flag against an operator's own record of a
   burn.

Ground truth for both exists in public, open products. This registration is
the design for using it.

**What this is not.** It is not a census of anything. Both measurements are
**benchmarks on a small, non-random set of spacecraft** — a handful of
European and international science and altimetry missions, chosen because
they carry GNSS/DORIS/SLR and therefore have published precise orbits and
published manoeuvre histories. Precisely the properties that make them
measurable make them unrepresentative: they are large, cooperative, well
tracked, and they manoeuvre in small, frequent, planned increments. No number
produced under this registration transfers to the catalogue at large, and no
output may be written as though it did.

---

## 1. Data — verified reachable before this registration was written

Access was probed read-only on 2026-09-22 from the analysis host. Product
type, frame, time system, sampling and provenance are recorded for each; a
fetch manifest (`manifest-*.json`, URL + byte count + SHA-256 per file) is
written by `tools/truthset_fetch.py` and is the provenance of record.

| Role | Product | Frame / time | Sampling | Source | Verified |
|---|---|---|---|---|---|
| Truth, Sentinel-1A | **AUX_POEORB** precise orbit ephemerides, Earth-Explorer XML (`.EOF`) | `EARTH_FIXED` (ITRF), UTC tags | 10 s, one file per day, ~26 h validity | Registry of Open Data on AWS, bucket `s1-orbits`, anonymous | listed and downloaded |
| Truth, Sentinel-3A / 3B | **CNES/SSALTO precise orbit ephemerides (POE)**, SP3-c, version `30` = POE-G standards, the distributor's own "current (recommended)" | ITRF, **TAI** tags | 60 s, ~10 d per arc | International DORIS Service data centre, `ftp://doris.ign.fr/pub/doris/products/orbits/ssa/{s3a,s3b}/`, anonymous | listed and downloaded |
| Earth orientation | IERS **finals2000A.all** (polar motion, UT1−UTC) | — | daily | `datacenter.iers.org`, anonymous | downloaded |
| Labels (B), primary | **MAD-LEO** mission-reported subset, annotation tables (CSV) | — | 1,134 events, 11 spacecraft, 1992–2026 | figshare `10.6084/m9.figshare.33446503.v1`, **CC BY 4.0** | downloaded |
| Labels (B), corroboration | **IDS/DORIS mission-reported manoeuvre histories** `s3aman.txt`, `s3bman.txt` — the source MAD-LEO parses | — | through 2026 day 254 | `ids-doris.org/documents/BC/satellites/` | downloaded |
| Elements under test | this repository's own element archive, `element_set` | TLE mean elements, TEME | per object | `/home/sdegan/space-orbit-history/orbit-history.sqlite3` | in place |

**What could not be fetched.** *The Sentinel-2 precise orbit product could not
be fetched.* The Copernicus Data Space catalogue lists
`S2A_OPER_AUX_POEORB_*.EOF` anonymously — the entry, its size and its checksum
are visible — but the download endpoint answers an anonymous request with
HTTP 401 `Token not found`, and a token requires a registered account this
session does not hold. The ESA STEP auxiliary-orbit mirror, which serves
Sentinel-1 POEORB openly, has **no Sentinel-2 tree** (HTTP 404). **Sentinel-2
is therefore excluded from measurement (A) for want of a fetchable truth
product, not for any scientific reason**, and the results document will repeat
that sentence. Sentinel-1B is excluded because the spacecraft was lost in
December 2021 and has no truth in any span where it is also flying.

**Licence and handling.** MAD-LEO is CC BY 4.0: attribution is given in the
results document and in every artefact that quotes it; the tables themselves
stay on the analysis host outside the repository and are **not
redistributed**. Nothing under this registration writes to `src/`, `data/`,
`public/` or any site surface.

**A correction to the T16 row, recorded here because it changes the design.**
The runbook row reads "MAD-LEO (arXiv 2609.08556) — 6,785 Starlink objects,
107 h, 1,134 operator-evidenced manoeuvres", which merges two different
subsets. The dataset's own metadata is explicit: the **1,134 labelled
manoeuvres are from eleven geodetic and altimetry satellites** (CryoSat-2,
Sentinel-3A, Sentinel-3B, Jason-1/2/3, SWOT, SARAL, HY-2A, TOPEX/Poseidon,
Sentinel-6A), taken from IDS/DORIS mission-published histories; the
**Starlink subset carries no manoeuvre labels at all** and is stated by its
authors to be operator *predictions*, "never maneuver ground truth". The
recall measurement therefore runs on the eleven labelled spacecraft, and
**no recall number is claimed for Starlink or for any constellation**.

---

## 2. Measurement A — element-set error growth against precise orbits

### 2.1 Estimand

For a spacecraft with a public precise orbit, take an element set from this
programme's archive, propagate it forward with the programme's own propagator
from its own epoch, and difference the predicted position against the precise
orbit at a set of horizons. The estimand is the **distribution over epochs of
the radial / along-track / cross-track error at horizon h**, per spacecraft.

It is *not* a measurement of SGP4, and not of the archive's fit quality alone:
it is the error a consumer of this archive actually suffers, which includes
whatever the spacecraft did after the epoch. That is deliberate — it is the
quantity the site ribbon and the kinematic member intervals need — and §2.6
separates the two contributions where labels allow.

### 2.2 Spacecraft and spans (registered, fixed here)

| Spacecraft | NORAD | Truth window | Epoch window (propagation starts) |
|---|---:|---|---|
| Sentinel-1A | 39634 | 2023-01-01 → 2024-01-01 | 2023-01-01 → 2023-10-03 |
| Sentinel-3A | 41335 | 2023-01-01 → 2024-01-01 | 2023-01-01 → 2023-10-03 |
| Sentinel-3B | 43437 | 2023-01-01 → 2024-01-01 | 2023-01-01 → 2023-10-03 |

The epoch window ends 90 days before the truth window so that the longest
horizon closes inside the truth. The calendar year 2023 is chosen before any
number is seen, for one reason stated in advance: it is a complete, recent
year in which all three spacecraft are operational and all three truth
products are final (no near-real-time or extrapolated arcs).

**Propagation epochs**: the **first archive element set of each UTC day**
inside the epoch window. One per day, so that a dense-tracking day cannot
outvote a sparse one.

**Horizons**: **+1, +3, +7, +14, +30, +60, +90 days** after the element set's
own epoch. No horizon beyond the truth window is evaluated and none is
extrapolated.

### 2.3 Propagator and frames (derived, with the residual bounded)

- **Propagator**: SGP4 as the programme itself propagates — `satellite.js`,
  the SGP4 implementation every object on the site's globe is computed with
  (`src/orbit-worker.ts`, `src/ground-stations.ts`), driven through
  `json2satrec` from the archive's own stored elements (mean motion,
  eccentricity, inclination, RAAN, argument of perigee, mean anomaly, B*),
  de-quantised with the archive's own scales.
- **Frame chain**: SGP4 returns TEME of date. TEME → PEF is a rotation about
  Z by Greenwich **Mean** Sidereal Time evaluated at **UT1**; the neglected
  kinematic term of the equation of the equinoxes is ≤ 0.003″, i.e.
  ≤ 0.003″ × (π/648000) × 7.2 × 10⁶ m ≈ **0.1 m** at these radii. PEF → ITRF
  applies polar motion (x_p, y_p). UT1−UTC and (x_p, y_p) are taken from IERS
  `finals2000A.all`, interpolated linearly in MJD.
- **Why the Earth-orientation terms are not optional**: neglecting UT1−UTC
  alone rotates the Earth by up to |ΔUT1| × 15.041 ″/s; at the 2023 value of
  |ΔUT1| ≲ 0.05 s that is ≲ 0.75″ ≈ 26 m, and at the treaty limit of 0.9 s it
  is 13.5″ ≈ 470 m — the same order as the errors at the shortest horizon.
  Neglecting polar motion alone is ≤ 0.3″ ≈ 10 m. Both are applied, so the
  frame residual is the 0.1 m term above. These are derivations, not quoted
  tolerances: r·θ with θ in radians.
- **No interpolation of the truth.** The comparison instant is the **truth
  product's own nearest sample** to (epoch + h); SGP4 is then evaluated at
  exactly that instant. The offset (≤ 5 s for the 10 s product, ≤ 30 s for the
  60 s product) is recorded per comparison, and gate A1 bounds it.
- **Time systems**: EOF tags are UTC and used as such. SP3 tags are **TAI**
  and are converted with the leap-second count in force over the span
  (TAI − UTC = 37 s for the whole of 2023); the conversion is unit-tested
  against a known leap-second epoch.

### 2.4 The error decomposition

With `r_t`, `v_t` the truth position and velocity in ITRF and `r_p` the
propagated position in ITRF, the truth's inertial velocity in ITRF components
is `v_i = v_t + ω × r_t`, ω = 7.292115 × 10⁻⁵ rad/s about Z (the product's
velocities are Earth-fixed; the SP3 documentation and the EOF header both say
so). The basis is

```
R = r_t/|r_t|        C = (r_t × v_i)/|r_t × v_i|        T = C × R
```

and the reported components of `Δ = r_p − r_t` are **radial** `Δ·R`,
**along-track** `Δ·T`, **cross-track** `Δ·C`, in kilometres, plus the
along-track error as a **phase angle** `(Δ·T)/|r_t|` in degrees, which is the
form the site ribbon and T8b's Γ are written in.

### 2.5 Statistics and the horizon

Per spacecraft and per horizon: **n**, and the **p25 / p50 / p75 / p95** of
|radial|, |along-track|, |cross-track|, and of the along-track phase angle.
Quantiles, not means: the distribution is expected to be heavy-tailed and a
mean would be a fiction.

**The registered headline quantity is the horizon at which the median
along-track error first exceeds the co-orbital station threshold T8b uses**,
Γ = **5°** of relative along-track phase
(`docs/proximity-leo-results-20260922.md` §3.1, primary arm), reported in
degrees and in kilometres as `s = |r| · Γ · π/180` at the spacecraft's own
radius. The tight registered arm, Γ = **0.2085° (25 km)**, is reported
alongside. **Interpolation rule, fixed in advance**: the crossing is found by
linear interpolation of log(median error) against log(horizon) between the two
bracketing measured horizons. **If the median does not cross inside
[+1 d, +90 d] the result is reported as "not reached within the measured
horizons" and no extrapolated number is given** — not a larger horizon, not a
fitted power law, nothing.

### 2.6 Manoeuvres inside the span — registered treatment

**Primary arm: manoeuvres are NOT excluded.** The measurement is as-flown, and
that is what the consuming surfaces need.

**Secondary arm, Sentinel-3A / 3B only: manoeuvre-free intervals.** These two
spacecraft have a published manoeuvre history (IDS/DORIS, and the same events
in MAD-LEO). A comparison is *manoeuvre-free* when no labelled manoeuvre epoch
lies in the open interval (element-set epoch, comparison instant). The same
quantiles are reported on that subset, with its own n. Sentinel-1A has **no
public manoeuvre notice that could be fetched** (it carries no DORIS package,
and `ids-doris.org` returns 404 for it), so it has no secondary arm and its
table is labelled as-flown only.

**Reported either way, for all three**: the count of labelled manoeuvres inside
the truth window (Sentinel-3A/3B), and — for all three — a **truth-derived
orbit-change count**: the number of days on which the daily-mean semi-major
axis of the *truth product itself* steps by more than 20 m. That 20 m is a
**screen**, taken from MAD-LEO's own `suspect_unreported_maneuver` flag, not a
physical threshold and not a detection claim; it is reported as "days on which
the precise orbit itself shows a step above the screen".

### 2.7 Truth-product properties to report (not assumed)

The results document must state, **measured from the fetched files, not quoted
from documentation**: the product's own arc length / validity span, its
sampling interval, and its **latency** — the distribution of
(product creation time − end of validity) for Sentinel-1A, taken from the
file names, and the equivalent for the SP3 arcs from the distributor's
listing. No accuracy figure for the truth is asserted from vendor literature;
instead the results document states the derived frame residual (§2.3) and
notes that any decimetre-level truth error is negligible against the scales
the table actually reports, **if** the table's own numbers bear that out.

---

## 3. Measurement B — recall of the LEO burn detector against labelled manoeuvres

### 3.1 The detector, at its shipped settings

The programme's LEO manoeuvre detector is
`tools/proximity_plane.detect_manoeuvres` — T8b's own arithmetic, and the same
function the alarm lane's LEO arm triggers on
(`docs/alarm-lane-build-20260922.md` §7). It is **read-only** for this track;
not one character of it, of `tools/trigger_alarm.py` or of
`tools/alarm_lane_leo.py` is edited.

At its shipped settings:

- **in-track channel**: residual of mean motion from a rolling robust local
  fit over the preceding `BURN_BASELINE_SAMPLES = 10` element sets, flagged
  when |residual| exceeds
  `max(5σ_n, 3|ṅ_own|·Δt, 1.5·n·0.050 km/a)`;
- **plane channel**: per-pair inclination step and RAAN residual against the
  object's own J₂ nodal rate, flagged above `max(5σ_θ, 0.01°)`;
- both channels require **two consecutive element sets over the bar and
  agreeing in sign**, and the flag epoch is the **second** set's, "because
  that is the first instant a causal observer possessed the evidence".

**Primary arm — pooled σ, exactly as T8b ran it**: `σ_n = 6.2747e-5` rev/day
and `σ_θ = 0.6994°`, the pooled LEO medians in
`docs/proximity-leo-results-20260922.md` §2.2. This is what "shipped settings"
means and it is the arm the headline recall is quoted from.

**Secondary arm — per-object σ**: `σ_n`, `σ_θ` from the detector's own
`object_sigma_contributions` applied to the object under test. Registered in
advance because these eleven spacecraft are far better tracked than the pooled
LEO median, so the pooled bar is expected to be loose for them; the pair of
arms separates "the detector is blind" from "the detector is being run at a
population's floor rather than this object's".

### 3.2 Read the floor first (registered as a precondition, not a result)

Before any recall is read, the instrument computes and the results document
prints, per spacecraft and per arm, the **smallest semi-major-axis step the
in-track channel can flag**, from the threshold that governs it:

```
a = (μ/(2πn/86400)²)^(1/3);   da/a = −(2/3)·dn/n   ⟹   |δa|min = (2/3)·(a/n)·thr_n
```

and the impulsive along-track Δv that produces it, from `δa = 2·Δv/n_ang` for
a near-circular orbit (`Δv = δa·n_ang/2`). Both are derivations, shown in the
results document, not quoted constants. **A recall number that is not printed
beside its floor is not a result under this registration.**

### 3.3 Labels, scope, and what counts as evaluable

- **Label set**: the 1,134 MAD-LEO mission-reported manoeuvres, all eleven
  spacecraft, over the whole of each spacecraft's archive coverage. Each label
  carries `event_time_utc`, `event_time_role` (`first_impulse_time` or
  `reported_operation_end_time`), `time_uncertainty_seconds`, `impulse_count`,
  a 30-hour analysis window (event −6 h / +24 h) and a
  **confidence tier A / B / C** (A = TLE + precise orbit + SLR present;
  B = TLE + orbit; C = otherwise incomplete) — evidence completeness, not
  quality, in the dataset's own words.
- **Spacecraft → NORAD** mapping is fixed in the instrument and asserted by a
  test against the archive's own `object` table names.
- **Evaluable**: a label is evaluable when this archive holds element sets
  bracketing its association window — at least one epoch at or before the
  window start and one at or after its end — and the object has at least
  `BURN_BASELINE_SAMPLES + 3 = 13` element sets, the detector's own minimum.
  **A label that is not evaluable is reported as not evaluable and is excluded
  from both numerator and denominator.** A gap in our evidence is not a miss.

### 3.4 Association rule

**Primary**: a label is **recalled** when a confirmed flag epoch (either
channel) falls inside the dataset's own event window, `[event − 6 h,
event + 24 h]`. This window is used because it is the labelled set's own, was
fixed by its authors before we saw it, and already accommodates the detector's
one-element-set confirmation lag at the ~0.5–1 d spacing these objects are
tracked at.

**Registered sensitivity variants**, reported in the same table:
`event ± 1 d`; `event ± 3 d`; and a **spacing-aware** window
`[event − 6 h, event + 2 × (this object's median element-set spacing)]`.

**Channel split**: recall is reported for in-track flags, plane flags, and
either.

**Campaign-level recall, reported separately**: the alarm lane does not speak
per flag — it speaks at a **campaign start**, a flag chain with no internal gap
longer than 180 days (`CAMPAIGN_MAX_GAP_DAYS`). The fraction of labels
associated with a *campaign start* is therefore reported beside the flag-level
recall, with the arithmetic reason printed: a spacecraft that manoeuvres every
few weeks for a decade is one campaign, so the ceiling on campaign-level recall
is (campaigns / labels) and is expected to be very small. Neither number is
allowed to be printed without the other.

### 3.5 Stratification

Recall with a **Wilson 95% interval** overall, and split by: **spacecraft**;
**confidence tier** A/B/C; **impulse count**; and **burn size**.

**Burn size.** The labels carry no Δv column — stated plainly rather than
worked around. Two size proxies are registered, both labelled as proxies:
(i) the **mission-reported operation duration**, `reported_operation_end −
reported_operation_start`, from the label itself; (ii) the **archive-bracketed
|Δa|**: the change in semi-major axis between the last element set before the
window and the first after it, which is MAD-LEO's own quality-flag statistic
(its 20 m screen) and is measured from the *same* elements the detector reads
— so it is a stratifier, never evidence that a manoeuvre happened. Bins for
(ii) are fixed here: < 20 m, 20–50 m, 50–100 m, 100–200 m, 200–500 m, ≥ 500 m,
and the per-object floor of §3.2 is drawn on the same axis.

### 3.6 False flags, on the same window

The denominator problem is the whole story at LEO (T8d at GEO; the alarm
lane's LEO arm fails its passive control at 0.797 of the payload rate), so
recall is reported only beside a false-flag count:

1. **Labelled-quiet false flags**: confirmed flags whose epoch falls inside a
   MAD-LEO **stable window** (`event_label = no_event`, 1,139 windows),
   reported as a count, as a rate per stable-window-day, and as the fraction
   of stable windows carrying at least one flag. **Caveat, registered in
   advance**: the stable windows are constructed from TLE-archive coverage
   mining, not from a mission declaration of quiet, and the dataset flags some
   of them `suspect_unreported_maneuver`; the count is therefore an **upper
   bound on false flags**, and the subset carrying that flag is reported
   separately so the reader can subtract it.
2. **Unmatched flags over the labelled span**: all confirmed flags in each
   spacecraft's archive inside the span the labels cover, minus those matched
   to a label. Reported as a count and per object-year, and explicitly **not**
   called a false-alarm rate, because the completeness of the published
   manoeuvre history is not verified by us.

### 3.7 Sentinel manoeuvre notices

The IDS/DORIS histories `s3aman.txt` / `s3bman.txt` are fetched and parsed
independently of MAD-LEO. Their use is fixed in advance as **corroboration
only**: the results document reports whether the events MAD-LEO carries for
Sentinel-3A/3B agree with the current IDS files over the same span (count,
and epoch agreement), and reports any events the live file carries beyond
MAD-LEO's cut. No recall headline is computed from them; they exist here to
show that the labelled set has not drifted from its own upstream source, and
to supply the §2.6 manoeuvre-free arm.

---

## 4. Gates — what must hold before either measurement may speak

| Gate | Clause | Bar | If it fires |
|---|---|---|---|
| **A1** | truth sample offset from the requested instant | ≤ 5 s (10 s product), ≤ 30 s (60 s product), for ≥ 99% of comparisons | drop the offending comparisons, report the count; if > 1% are dropped the horizon row is labelled a gap, not a number |
| **A2** | truth coverage | every horizon row has n ≥ 30 comparisons | rows below the bar print n and are labelled "too few to quantile", never a number |
| **A3** | frame residual against the reported scale | derived residual (≤ 0.1 m, §2.3) ≤ 1/10 of the smallest reported quantile | the affected cells are labelled frame-limited |
| **A4** | propagator sanity | the +0 d residual (element set differenced against truth at its own epoch) is reported; it is the instrument's own noise floor for (A) | if it is not small against the +1 d error, the whole table is reported as a floor measurement and nothing else |
| **B1** | label evaluability | reported, never silently dropped (§3.3) | — |
| **B2** | floor printed | §3.2 computed and printed per spacecraft before any recall cell | no recall may be quoted |
| **B3** | detector untouched | `git diff --stat` over `tools/proximity_plane.py`, `tools/trigger_alarm.py`, `tools/alarm_lane_leo.py` is empty at measurement time and the hash is recorded | the measurement is void |
| **B4** | false-flag count present | §3.6(1) and (2) both computed | recall may not be quoted alone |

**A4 is the one that can void measurement (A)**: if propagating an element set
to its own epoch does not reproduce the truth to well inside the +1 d error,
the pipeline is measuring itself.

---

## 5. What the results may and may not say

- May: "over 2023, for Sentinel-1A / 3A / 3B, the median along-track error of
  an archive element set propagated h days reached X km", with n, quantiles,
  and the manoeuvre treatment named.
- May: "of N labelled manoeuvres on eleven geodetic and altimetry spacecraft,
  the detector at its shipped settings flagged k — recall k/N, Wilson 95%
  [·,·] — beside F flags inside labelled-quiet windows", with the floor and
  the tier split printed.
- **May not**: any statement about the catalogue at large, about
  constellations, about Starlink, about "the detector's recall" without the
  qualifier *on this labelled set, one window, these eleven spacecraft*; any
  claim that an unmatched flag is a false alarm; any extrapolated horizon; any
  use of the recall number to revise a published precision figure (a different
  denominator: precision and recall here are measured on different
  populations).
- Every threshold named in this document — 5σ, the 50 m and 0.01° floors,
  Γ = 5°, the 20 m screen, the burn-size bins — is a **chosen screen**, not a
  physical law, and must be described as one wherever it appears.

---

## 6. Deviations

Any departure from this document is written into the results document under a
heading "Deviations from the registration", with the reason, before the
affected number is read. Nothing in this file is edited after it is committed.

---

## 7. Files and reproduction

```
tools/truthset_fetch.py     products + labels + EOP -> private dir, manifest with SHA-256
tools/truthset_truth.py     EOF / SP3 / EOP parsers -> per-spacecraft state arrays
tools/truthset_sgp4.mjs     the programme's own SGP4 (satellite.js), batch bridge
tools/truthset_growth.py    measurement (A)
tools/truthset_recall.py    measurement (B)
tests/test_truthset.py      parser, frame, floor, association and interval tests
docs/t16b-truthset-results-<date>.md    the results, with the deviations section
docs/t16b-truthset-growth-<date>.json   (A) table, machine-readable
docs/t16b-truthset-recall-<date>.json   (B) table, machine-readable
```

Raw products and the licensed label tables live at `/home/sdegan/t16b-truth/`
on the analysis host and are not committed.

## 8. Sources of every number in this registration

```
docs/proximity-leo-results-20260922.md   sigma_n 6.2747e-5, sigma_theta 0.6994 deg,
                                          Gamma 5 deg / 0.2085 deg (25 km), theta_p 0.2 deg,
                                          D 30 d, 44.1%, 195.9 d, 0 / 18.79M control
docs/orbits-section-design-20260922.md   LEO ribbon 0.023 deg/day; "none measured for this site"
docs/kinematic-reach-design-20260922.md  M2; the +30 d GEO ribbon it is contrasted with
docs/alarm-lane-build-20260922.md        LEO arm 0.507%, 13,443 passive alerts, 0.797, 180 d chain
docs/research-program-runbook-20260921.md  the T16 row and its feasibility verdict
tools/proximity_plane.py                 BURN_SIGMA_K 5, BURN_BASELINE_SAMPLES 10,
                                          DA_FLOOR_KM 0.050, I_FLOOR_DEG 0.01,
                                          CAMPAIGN_MAX_GAP_DAYS 180
pipeline/orbit_history.py                the archive's quantisation scales
MAD-LEO docs/metadata.md                 1,134 events / 11 spacecraft, tiers A/B/C,
                                          30 h event window, 1,139 stable windows,
                                          the 20 m suspect screen, the Starlink claim boundary
IERS finals2000A.all                     UT1-UTC and polar motion
```
Derived in this document and labelled as such: the 0.1 m / 10 m / 26 m / 470 m
frame bounds (r·θ), the `|δa| = (2/3)(a/n)·thr_n` floor, `Δv = δa·n_ang/2`,
and the conversion `s = |r|·Γ·π/180`.
