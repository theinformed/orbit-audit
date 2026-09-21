# T3 pre-registration: station-keeping cadence fingerprints

Registered 2026-09-21, **before any T3 periodogram, threshold, count or
result exists**. This document is committed alone, ahead of everything T3
will ever produce, exactly the way `docs/phase3-preregistration-20260921.md`
was committed ahead of Phase 3 and `docs/paperb-preregistration-20260920.md`
ahead of Paper B (`f317a28`). The git history of this file is the timestamp.
Nothing below may be changed once a T3 number exists; an awkward outcome is
reported, not edited away.

T3 is the third track of `docs/research-program-runbook-20260921.md`, on
Sean's 2026-09-21 GO. This document registers what T3 estimates, on which
elements, over which frequencies, against which null, with which thresholds,
under which multiple-testing correction, and what would make the pilot
uninformative. It implements nothing.

Estate rule this document is written under, restated because it is the reason
several sections below are derivations rather than assertions: **physical
assumptions are not facts — derive or cite every physical claim; thresholds
are screens, not laws.**

---

## 0. What was measured BEFORE this registration, and why that is not a result

Two pre-scans were run before this document was written. Both are disclosed
here in full because concealing a pre-scan is how a registration quietly
becomes a post-hoc rationalisation.

Both scripts are committed with the implementation in §12 — not with this
registration, which is committed alone — as
`tools/cadence_sampling_geometry.py` and `tools/cadence_spectral_window.py`,
so every number in this section is reproducible.

**Both read `norad`, `object_type` and `epoch_ms` and nothing else. Neither
read a single element value.** They characterise the archive's *sampling
pattern* — when the catalogue was observed, never what it said — which is the
same class of information as "how many objects are there". The estimand in §2
is a property of element *values*; no value entered either scan, so neither
can have been used to shop for a favourable threshold.

They exist because the task this registration answers requires the alias
structure to be **derived from the actual epoch spacing distribution, not
guessed**, and that derivation is impossible without looking at the epochs.

### 0.1 Epoch spacing and baseline (`tools/cadence_sampling_geometry.py`, systematic sample `norad % 97 == 0`, 236 objects drawn, 236 usable)

| Quantity | Payload (107 objects) | Passive: DEBRIS + ROCKET BODY (129 objects) |
|---|---:|---:|
| Median within-object epoch spacing (median over objects) | **0.3989 d** | **0.8747 d** |
| Within-object spacing p25 / p75 (median over objects) | 0.2650 / 0.7192 d | 0.4945 / 1.0280 d |
| Within-object spacing p5 / p95 (median over objects) | 0.0665 / 1.0413 d | 0.1547 / 2.4998 d |
| Median spacing, p10–p90 across objects | 0.3539 – 0.8022 d | 0.5578 – 1.4897 d |
| Element sets per object, p10 / p50 / p90 | 1,284 / 2,785 / 17,777 | 1,305 / 4,865 / 18,195 |
| Archive baseline, p10 / p50 / p90 | 885 / 1,586 / 15,028 d | 1,659 / 6,878 / 18,358 d |
| Exact duplicate-epoch fraction (median) | 0.000000 | 0.000000 |

Screened population (`rows >= 200` and baseline `>= 2` years, from
`object_rollup`): **36,302 objects**, of which **11,002 PAYLOAD**, **9,850
DEBRIS**, **2,075 ROCKET BODY** (the rest are `object_type` NULL or UNKNOWN and
are excluded by §3).

**The single most consequential fact in this table is that the two classes are
not sampled alike.** Payloads are re-fitted roughly twice as often as passive
objects (0.40 d against 0.87 d) and are watched for roughly a quarter as long
(1,586 d against 6,878 d). A Lomb-Scargle power statistic depends strongly on
sample count, baseline and sampling pattern. **A pooled passive null is
therefore known in advance to be the wrong null**, and §6's matching is not a
refinement — it is load-bearing. §6.4 states how far the matching can actually
go and where it stops.

### 0.2 The spectral window, and therefore the alias structure (`tools/cadence_spectral_window.py`, systematic sample `norad % 397 == 0`, 50 objects, latest 3,000 epochs each)

The spectral window of an irregularly sampled series,

&nbsp;&nbsp;&nbsp;&nbsp;`W(f) = | sum_j exp(-2*pi*i*f*t_j) |^2 / N^2`,

is the exact object that decides aliasing: a true signal at `f0` can be
counterfeited at `f0 ± g` for every `g` at which `W` has a peak, with relative
strength `W(g)`. Mean `W` over the sample, top peaks (band 0.02–4 cycles/day,
resolution 5e-4 c/d):

| Rank | Payload carrier (c/d) | `W` | Passive carrier (c/d) | `W` |
|---:|---:|---:|---:|---:|
| 1 | 3.0535 | 0.0385 | **2.0000** | 0.0754 |
| 2 | **1.0000** | 0.0356 | **3.0000** | 0.0430 |
| 3 | **3.0000** | 0.0323 | **3.9995** | 0.0269 |
| 4 | 2.0305 | 0.0203 | **1.0000** | 0.0214 |
| 5 | **2.0000** | 0.0172 | 1.9590 | 0.0162 |
| 6 | 3.9565 | 0.0110 | 2.1975 | 0.0159 |
| median `W` in band | | 2.71e-4 | | 3.14e-4 |

**The derivation this buys.** The window's carriers sit at, or within a few
per cent of, **integer multiples of the solar day**: 1, 2, 3 and 4 cycles/day,
at 2–8% relative strength, against a 3e-4 background. The catalogue is re-fitted
on a daily rhythm and sub-sampled at 1/2, 1/3 and 1/4 of a day; that rhythm,
and nothing else of consequence, is the archive's alias comb.

Three consequences, all registered:

1. **The lowest alias carrier is at `g = 1.0` c/d.** A signal anywhere in the
   band this registration searches (§4: `f <= 0.5` c/d) has its nearest alias
   at `1 - f0 >= 0.5` c/d — **outside the searched band**. Within the
   registered band, aliasing against the sampling comb cannot manufacture a
   detection. This is why §4 caps `f_max` at 0.5 c/d and not at the naive
   pseudo-Nyquist `1/(2 * 0.3989 d) = 1.25` c/d: the cap is chosen to sit
   strictly below the first carrier, giving up a factor 2.5 in frequency reach
   to buy an alias-free band.
2. **Everything faster than 2 days is therefore a declared blind spot**, not a
   negative result (§9).
3. Spectral leakage from the carriers still deposits power at low `f` through
   the window's skirts. It is not modelled away; it is present identically in
   the passive control, which is measured through the same comb, and the
   empirical null of §6 absorbs it. That is the main reason the null is
   empirical rather than analytic.

---

## 1. What T3 is for (three declared uses, registered before the result)

Registered now so that no use can be invented afterwards to fit whatever the
numbers turn out to be. These are the runbook's three, stated concretely:

- **U1 — fuel-odometer tightening (Paper A / G3).** `tools/fuel_odometer.py`
  currently prices consumed propellant from detected manoeuvres. A measured
  *cadence* supplies the missing denominator: burns-per-year for objects whose
  individual burns are below detection, multiplied by a thrust-per-burn
  estimate, bounds the odometer from a second, independent direction. T3
  delivers the cadence; it does **not** compute an odometer, and no odometer
  number changes on this registration's evidence alone.
- **U2 — EOL cadence-change telltale (G1).** A satellite that stops keeping
  station has stopped doing the only thing that distinguishes it from debris.
  §7's change-points are the detector for that. T3 delivers candidate
  change-points and their passive-calibrated false-positive rate; it does
  **not** relabel any object's end-of-life status, and `docs/eol-*` is not
  edited by this track.
- **U3 — matched-filter pilot for the supercompute pitch (G5 / T5a).** The
  runbook's T5a asks for template-bank matched filtering across the whole
  catalogue. T3 is its single-GPU pilot: one gaming card, one element channel,
  one template family (a sinusoid). Its job is to make the scale argument
  concrete by measuring what one card recovers and what it provably misses —
  **so §9's blind spots are a deliverable of U3, not a caveat on it.**

## 2. Estimand

For each object in the population of §3, over each analysis window of §5:

> **E1 — dominant periodicity.** The frequency `f*` in the registered grid
> (§4) at which the generalised Lomb-Scargle periodogram of the detrended
> primary element channel (§3.2) attains its maximum normalised power
> `P_max`, together with `P_max` itself; and the binary verdict
> `significant` / `none`, decided by §6's passive-calibrated threshold.
> The per-object dominant periodicity is that of its highest-`P_max`
> usable window; an object with no usable window is **`insufficient`**,
> which is a third outcome and is never merged into `none`.

> **E2 — cadence change-points.** Over an object's ordered sequence of
> windows, the epochs (window indices) at which its rhythm **shifts**
> (§7.1) or **stops** (§7.2), under the registered definitions, together
> with the rate at which the identical procedure fires on the held-out
> passive control.

Two population-level quantities are derived from E1 and are the headline
numbers of the results report:

> **E3 — the audit number.** `frac_sig(payload)` versus
> `frac_sig(passive_audit)`, both at the *same* thresholds, where
> `passive_audit` is the held-out half of the passive class (§6.2) that was
> never used to set a threshold. Reported as a ratio of a Jeffreys lower
> bound to a Jeffreys upper bound, using `orbit_events._jeffreys_interval`
> and the existing `orbit_events.separation_verdict` bound-to-bound shape —
> not a point-estimate ratio.

> **E4 — the cadence distribution**, tabulated by orbit regime (§6.3's
> stratum factors) and, where the catalogue's `object.name` makes it
> unambiguous, by operator family.

**T3 estimates nothing about manoeuvre detection.** It does not run
`pipeline/orbit_campaigns.py`'s step detector, does not produce or consume a
manoeuvre flag, and changes no threshold in any shipped code. It reads element
values and writes a periodogram summary.

### 2.1 What "periodicity" means here, and what it does not mean

A station-kept orbit's semi-major axis is a **sawtooth**: drag removes energy
continuously, a burn restores it discontinuously. A sawtooth of period `T` has
Fourier power at `1/T` and at every harmonic `k/T`. The Lomb-Scargle maximum
therefore recovers the burn cadence at its fundamental **only when the
fundamental carries more power than any harmonic**, which is the generic case
for a sawtooth (fundamental amplitude falls as `1/k`) but is not guaranteed
once detrending, irregular sampling and noise are applied. Registered
consequence: a recovered `f*` whose value is within the §4 grid resolution of
`2*f_ref` or `3*f_ref` for some other strong peak `f_ref` is reported with a
`harmonic_ambiguous` flag, and the flag is reported in the results table
rather than resolved by judgement.

## 3. Population, channels, and exclusions

### 3.1 Population

From `object_rollup` joined to `object` in
`/home/sdegan/space-orbit-history/orbit-history.sqlite3` (the hot archive,
read-only, `PRAGMA query_only=1`):

- **Payload class**: `object_type = 'PAYLOAD'`.
- **Passive class (the null / negative control)**: `object_type IN ('DEBRIS',
  'ROCKET BODY')`, i.e. `pipeline.orbit_events.PASSIVE_TYPES`, borrowed rather
  than restated so the two cannot drift apart.
- **Excluded**: `object_type` NULL or `'UNKNOWN'` (37,000-odd objects). They
  are excluded because the whole design rests on the class label being right,
  and an absent label is not a payload and not a control. Their exclusion is
  reported, never silently applied.
- **Screen**: `rows >= 200` and archive baseline `>= 2 years`. Both are
  sampling-adequacy screens, applied identically to both classes, chosen in §0
  from epoch counts alone before any element value was read. They are screens,
  not laws: an object failing them is `insufficient` (§2), never `none`.

The passive class is a **free negative control** in the program's exact sense:
debris and spent stages carry no propulsion, so every periodicity their
element histories show is, by construction, not station-keeping. We pay
nothing for it and it is larger than the treated class (11,925 against
11,002 under the screen).

### 3.2 Channels — which elements, and why

**PRIMARY channel: mean motion `n`, in revolutions per day, exactly as
archived** (`mean_motion_q / 1e8`, `pipeline.orbit_history.SCALE_MEAN_MOTION`).

Justification, derived rather than assumed:

- The specific orbital energy of a two-body orbit is `eps = -mu/(2a)`, and
  Kepler's third law gives `a = (mu/n^2)^(1/3)`. Hence `a` is a strictly
  decreasing function of `n` and `eps` is a strictly increasing function of
  `a`. **`n` is the energy channel**, inverted in sign.
- Every propulsive event with a tangential component changes orbital energy
  and therefore `n`. Atmospheric drag can only *remove* energy, so it can only
  raise `n`; it cannot produce the periodic energy *restoration* a
  station-keeping burn produces. This is the physical asymmetry the whole
  track rests on, and it is the same one
  `pipeline/orbit_campaigns.py` already relies on for its sustained-thrust
  lane.
- **Why `n` and not `a`.** Converting a TLE mean motion to `a` by the Kepler
  relation is not exact: the TLE mean motion is the Brouwer-Lyddane/Kozai mean
  element that SGP4 consumes, and the Kepler inversion of it differs from the
  osculating semi-major axis by terms of order `J2 ~ 1.08e-3` that depend on
  `a`, `e` and `i`. Those terms are smooth, but they are **functions of `e` and
  `i`**, so any in-band oscillation in eccentricity or inclination would leak
  into a converted `a` and could be mistaken for an energy rhythm. Analysing
  `n` as archived introduces no conversion and therefore no leakage path.
  Because `a` is monotone in `n`, **every periodicity statement is identical
  in the two variables**; only the units differ. The results report will quote
  an equivalent `Δa` in metres for interpretation, computed with
  `mu = 398600.4418 km^3/s^2` and flagged as an interpretive conversion.

**SECONDARY channel S1: inclination `i` (degrees).** Registered as secondary,
and registered *at all*, for a specific physical reason: **north-south
station-keeping at GEO is invisible in the energy channel.** A north-south burn
is applied normal to the orbit plane to fight the lunisolar inclination drift;
to first order it changes `i` and leaves `a` (hence `n`) unchanged. At GEO
north-south keeping is also the dominant propellant consumer, several times
the east-west budget. A track that looked only at `n` would therefore report
"no rhythm" for the largest fuel expenditure in geostationary operations. S1
exists so that omission is measured rather than inherited.

**SECONDARY channel S2: eccentricity `e`.** Registered because GEO eccentricity
control against solar radiation pressure, and perigee-raising campaigns
generally, move `e` with little `n` signature.

Registered discipline on the secondaries: **S1 and S2 carry their own
independent threshold calibration and their own independent FDR correction
(§8), and their results are reported in a separate table from the primary.**
A significant S1 or S2 result is never quoted as if it were a primary result,
and the primary result is never re-run on a secondary's threshold. The primary
channel is the one the acceptance criteria of §10 are evaluated on.

### 3.3 Coverage and gaps

`pipeline/orbit_campaigns.MAXIMUM_JOINABLE_GAP_DAYS = 3.0` already encodes
this repository's position that a long hole is a hole in the *archive*, not a
hole in the object's activity — and the archive is documented to contain a
real hole between the end of the bulk back-fill and the start of live capture.
A periodogram computed across such a hole measures the hole. Registered
window admissibility (§5.3) therefore bounds the largest gap explicitly.

## 4. Frequency grid

Registered as a closed form, evaluated identically for every object and every
window, so that no object gets a grid tuned to it:

- **Band.** `f` from `f_min = 1/220 d^-1 = 4.5455e-3` c/d to `f_max = 0.5`
  c/d. Equivalently **periods 2 days to 220 days**, inclusive.
  - `f_max = 0.5` c/d is derived in §0.2: strictly below the first sampling
    alias carrier at 1.0 c/d.
  - `P_max_period = 220 d` is set by two constraints that meet there. (i) The
    detrending polynomial of §5.2 must not be able to absorb an in-band
    signal: over a window of `W = 1080 d` a cubic has an effective resolution
    of `W/3 = 360 d`, so the longest searched period must sit well below 360 d
    — 220 d gives a factor 1.64. (ii) The **thermospheric semiannual density
    oscillation at 182.6 d** must remain *inside* the band: it is one of the
    natural lines the passive null is supposed to carry (§6.5), and a band
    that excluded it would hide the single most important thing the control
    has to say. 220 d keeps it in with room for its width.
  - The **annual (365.25 d)** density term, the **~2.2-year geostationary
    triaxiality libration** derived in §6.5, and the **~11-year solar cycle**
    are all **out of band by registration**. They are not tested and not
    reported as absent.
- **Spacing.** Uniform in frequency, `df = 1 / (OVERSAMPLE * W)` with
  `OVERSAMPLE = 5` and `W = 1080 d` the window length (§5.1), giving
  `df = 1.85185e-4` c/d and **2,676 grid points**, identical for every window.
  Oversampling 5 is the standard Lomb-Scargle choice for resolving a peak
  rather than straddling it; it is fixed here and not tuned.
- **Cycle-count floor.** At `f_min`, a 1080-day window contains
  `1080/220 = 4.9` cycles. The registered floor is that **every searched
  frequency must complete at least 4 cycles in the window**; `f_min` satisfies
  it with margin, so the floor binds nothing and is recorded only so that a
  later reader can see it was imposed in advance rather than discovered.

**Why Lomb-Scargle and not an FFT.** The epochs are irregular by construction
— they are element-set fit epochs, which arrive when the tracking network
happens to produce a fit. §0.1 measures the irregularity directly: the
within-object spacing runs from a p5 of 0.067 d to a p95 of 1.04 d for
payloads, a factor 16. An FFT requires resampling onto a uniform grid;
resampling irregular data interpolates, and interpolation both invents power
at the interpolation scale and suppresses power near the Nyquist frequency of
the *imposed* grid. Lomb-Scargle fits sinusoids to the samples where they
actually are, by least squares, and needs no resampling. The **generalised**
form (Zechmeister & Kürster 2009, A&A 496, 577) is used rather than classical
Lomb-Scargle because it fits a floating mean along with the sinusoid; a
classical periodogram assumes the mean is known and is biased when a window's
mean is not exactly zero after detrending, which after a polynomial fit it
will not exactly be.

Normalisation: `P` is the standard fraction-of-variance form, `P in [0,1]`,
`P = (chi2_0 - chi2(f)) / chi2_0`, so that power is comparable across objects
with different variances. **The test statistic is `P_max`, the maximum of `P`
over the 2,676 grid points** — one number per window. Taking the maximum over
the grid means the within-object multiplicity over frequency is absorbed into
the statistic, and is calibrated by the null in §6 rather than corrected for
analytically; analytic false-alarm formulae for Lomb-Scargle assume Gaussian
white noise and independent frequencies, and this data satisfies neither.

## 5. Windows and detrending

### 5.1 Windows

Fixed length **`W = 1080 days`**, step **`S = 360 days`** (two-thirds overlap),
tiled forward from each object's first epoch. Rationale, all fixed in advance:

- A fixed window makes the null far more transferable than a per-object
  baseline would: `P_max`'s distribution depends on the window length, and
  fixing it removes one of the three ways §0.1's payload/passive sampling
  mismatch could bite.
- 1080 d is 3× the 360-day detrending resolution of §5.2 and 4.9× the longest
  searched period.
- The overlap gives change-point resolution of one step, 360 d, while keeping
  each window independently long enough to resolve `f_min`. Overlapping windows
  are **not independent**, and §7 and §8 both treat them as dependent: the
  object, not the window, is the unit of multiple testing.

### 5.2 Detrending

Within each window, subtract the **least-squares cubic polynomial in time**
fitted to the channel over that window. Degree 3 is fixed, not selected:
`W/degree = 360 d` sets the resolution at which the trend can follow the data,
and §4 places the whole searched band below it.

What the cubic is for: the dominant non-periodic structure in `n` is the
secular drag rise, which over 1080 days is monotone but not linear (it
accelerates as the orbit decays, and it is modulated by the solar cycle on a
timescale long compared to the window). A cubic removes that without reaching
into the band. What it is explicitly **not** for: it does not remove the
27-day, semiannual or lunisolar lines, which stay in the data and are supposed
to — they are what the passive control measures.

No other filtering, smoothing, outlier rejection or clipping is applied to
either class. In particular **no manoeuvre detector is run and no element set
is removed as an outlier**: removing the steps would remove the signal.

### 5.3 Window admissibility (identical for both classes)

A window is **usable** iff all four hold:

1. `N >= 300` element sets inside it.
2. Largest interior epoch gap `<= 45 days`. (Fifteen times
   `MAXIMUM_JOINABLE_GAP_DAYS`, chosen so a window is rejected for an archive
   hole rather than for an ordinary tracking lull, and small enough that a
   45-day hole cannot by itself create a 90-day apparent rhythm at the
   band's low end.)
3. Observed span `>= 0.90 * W` (972 d), so a window cannot pass on a dense
   clump at one end.
4. The channel is not constant to within the archive's quantisation
   (`1e-8` rev/day for `n`); a constant window has no periodogram.

An object with zero usable windows is `insufficient` (§2). The count of such
objects is reported for both classes, because a screen that removes the two
classes at different rates is itself a covariate imbalance and must be visible.

## 6. The null, and how thresholds are built from it

### 6.1 The null is empirical, and it is the passive class

No analytic false-alarm probability is used. The null distribution of `P_max`
is the **measured distribution of `P_max` over passive-class windows** — objects
that cannot station-keep, put through the identical pipeline: identical
channel, identical window geometry, identical cubic detrend, identical grid.
Whatever the archive, the tracking network, the fitting process and the natural
environment jointly deposit in a periodogram, the passive class carries it too.

### 6.2 The calibration / audit split — the reason the audit number is not circular

**A threshold set at the 99th percentile of the passive distribution gives a
passive false-positive rate of 1% by construction.** Quoting that as a measured
audit result would be a tautology dressed as evidence.

Registered split: **each passive object is assigned to `calibration` or
`audit` by `sha256(f"t3-20260921:{norad}")`, first 8 hex digits, even → 
`calibration`, odd → `audit`.** Seed string fixed here; the split is by
**object**, never by window, so no object contributes to both halves and the
overlap of §5.1 cannot leak across the split.

- **Thresholds are computed from the `calibration` half only.**
- **The audit number E3 is measured on the `audit` half only**, which never
  touched a threshold. It is a genuine held-out false-positive rate and can
  come out above the nominal 1%. If it does, that is the result.

### 6.3 Matched thresholds

Within each matching cell, the threshold is the **99th percentile of the
calibration-half passive `P_max` distribution over usable windows in that
cell**. The 99th percentile is fixed here and is the only percentile that will
be used as the primary; the 95th and 99.9th are computed and reported
alongside purely as a sensitivity display, and **the primary verdict is never
re-read off a different percentile.**

Matching cell = the registered four-factor stratum of
`tools/paperb_strata.stratum_key`, **imported, not restated**, so T3 cannot
drift from Paper B's and Phase 3's registered cut points:

- perigee band (`orbit_campaigns._perigee_band`: `<300`, `300-500`, `500-800`,
  `800-1200`, `1200-2000`, `>2000 km`),
- inclination band (8 bands, `0-1` … `120-180`),
- eccentricity class (`<0.001`, `0.001-0.01`, `0.01-0.1`, `>=0.1`),
- cadence class (`<0.25`, `0.25-1`, `1-2`, `>=2 d`),

evaluated per **window**, from the window's **median** `perigee_km`,
`inclination`, `eccentricity` and **median epoch spacing**. Note on the
cadence factor: Paper B's `CADENCE_EDGES` were registered against a per-interval
span; T3 applies the same edges to a window's median epoch spacing. The edges
are borrowed unchanged; the quantity they band is stated here explicitly
because it is not the identical quantity.

Plus **one T3-specific factor, registered because the statistic demands it**:

- **sample-count band** of the window: `N` in `[300,600)`, `[600,1200)`,
  `[1200,2400)`, `[2400,4800)`, `[4800,inf)` — octave bins. The null
  distribution of a Lomb-Scargle maximum depends directly on the number of
  samples; §0.1 measured the two classes differing by a factor ~2 in cadence
  and hence in `N` per window. Omitting this factor would be a known,
  measured, uncorrected confound.

Perigee is computed as `a*(1-e) - R_e` with `R_e = 6378.137 km` (WGS-84
equatorial radius) and `a` from the Kepler relation — the one place the
conversion of §3.2 is used, for banding only, never for the analysed signal.

### 6.4 The fallback ladder, and an honest statement of how far matching goes

Thin cells are inevitable; Phase 3 exists precisely because covariates
transfer imperfectly. Registered ladder, applied per window, with the rung
used **recorded on every single object's row** in the output artifact:

1. Full 5-factor cell, if it holds `>= 200` calibration-half passive windows.
2. Drop eccentricity class → 4-factor cell, if `>= 200`.
3. Drop inclination band → 3-factor cell (perigee × cadence × N), if `>= 200`.
4. Drop perigee band → 2-factor cell (cadence × N), if `>= 200`.
5. Pooled calibration-half passive distribution.

`200` is chosen so the 99th percentile is estimated from at least 2 exceedances
— a genuinely poor estimate of a tail, which is exactly why the rung is
recorded and why the fraction of payload exposure that lands on rungs 3–5 is a
**required line in the results report**, in the same spirit as Phase 3's
requirement to report unsupported payload exposure every time.

**How far this matching goes, stated honestly and in advance:** it matches on
orbit regime, on tracking cadence, and on sample count. It does **not** match
on radar cross-section, on the tracking network's per-object priority, on the
epoch *pattern* beyond its median spacing, or on the solar-activity epoch the
window sits in — and §0.1 shows payload and passive baselines differ so much
(median 1,586 d against 6,878 d) that the two classes' windows are not drawn
from the same years. **Passive windows are, on the whole, older.** Solar
activity differs between eras, and thermospheric drag variance with it. This
is a real, unmatched, known confound, and the direction of its bias is not
predicted here. It is disclosed now so that it cannot be presented later as a
discovery, and one registered diagnostic addresses it: the results report will
tabulate the audit-half passive `frac_sig` **by calendar year of window
midpoint**, so a reader can see whether the null moves with the solar cycle.

### 6.5 What the passive null is expected to contain — derived and cited, not assumed

The empirical null is taken as given; this section exists so that its *shape*
can be interpreted rather than marvelled at, and so that a passive line
appearing where physics says one should appear is recognised instead of being
called a false positive.

In-band (2–220 d) natural periodicities that a passive object's mean motion can
legitimately carry:

- **~27.3 d, solar rotation.** The synodic Carrington rotation period is
  27.2753 d. Solar EUV and the F10.7 proxy are modulated at this period;
  every standard thermospheric density model is driven by F10.7 and its
  81-day mean (NRLMSISE-00, Picone, Hedin, Drob & Aikin 2002, *JGR Space
  Physics* 107(A12), 1468; Jacchia 1971, SAO Special Report 332), so
  thermospheric density, drag, and hence `dn/dt`, carry a ~27-day line for any
  object with appreciable drag.
- **182.6 d, the thermospheric semiannual density oscillation**, with maxima
  near April and October. Documented since Paetzold & Zschörner (1961),
  *Space Research* II; quantified for modern density models by Bowman,
  Tobiska, Marcos & Valladares (2008), *JASTP* 70(5), 774–793, "The
  thermospheric semiannual density response to solar EUV heating".
- **Lunisolar gravitational terms.** The classical development of the
  luni-solar disturbing function for a close Earth satellite (Kaula 1962,
  *Astron. J.* 67, 300; Cook 1962, *Geophys. J. R. astr. Soc.* 6, 271) yields
  long-period terms at the Moon's months and their halves: sidereal 27.32 d
  and 13.66 d, anomalistic 27.55 d and 13.78 d, synodic 29.53 d and 14.77 d;
  and solar terms at 365.25 d (out of band) and 182.6 d.
- **A regime-dependent beta-angle / local-time line, derived here.** A
  non-sun-synchronous orbit's plane regresses relative to the Sun, so the
  object's local solar time — and therefore the density it flies through, since
  the thermosphere has a strong diurnal bulge — cycles. The J2 nodal
  regression rate is

  &nbsp;&nbsp;&nbsp;&nbsp;`dOmega/dt = -(3/2) * J2 * (R_e/p)^2 * n * cos(i)`.

  For a circular orbit at 500 km altitude (`a = 6878.137 km`, `p = a`) with
  `i = 53°`, `J2 = 1.08263e-3`, `mu = 398600.4418 km^3/s^2`:
  `n = sqrt(mu/a^3) = 1.10678e-3 rad/s`; `(R_e/a)^2 = 0.85994`;
  `cos 53° = 0.60182`; giving `dOmega/dt = -9.3019e-7 rad/s = -4.6045 deg/day`.
  The mean Sun advances at `+0.9856 deg/day`, so the plane-to-Sun geometry
  closes at `4.6045 + 0.9856 = 5.5901 deg/day`, a **beta cycle of
  `360/5.5901 = 64.40 days`**. The same computation at `i = 98°` (sun-synchronous)
  gives `dOmega/dt = +0.9856 deg/day` by construction and **no beta cycle at
  all**. This line therefore moves with altitude and inclination across the
  whole band — which is, concretely, why §6.3 matches on perigee and
  inclination and why a single pooled threshold would be wrong.
- **Not in band, derived so it can be excluded rather than assumed absent:**
  an *uncontrolled* geostationary object librates in longitude about a stable
  equilibrium under Earth's triaxiality. With `J22 = 1.8154e-6`,
  `a = 42164.2 km`, `n = 7.2921e-5 rad/s`, the longitudinal acceleration is
  `d2λ/dt2 = -18 n^2 J22 (R_e/a)^2 sin(2(λ-λ22))`, whose amplitude is
  `3.976e-15 rad/s^2` (`= 1.70e-3 deg/day^2`, consistent with the standard
  figure). Linearising about the stable point gives
  `ω = sqrt(2 * 3.976e-15) = 8.918e-8 rad/s`, a libration period of
  `2π/ω = 7.05e7 s = 815 days ≈ 2.23 years` — far outside the 2–220 d band.
  **Uncontrolled GEO debris therefore contributes no in-band triaxiality
  line**, which is a genuine strengthening of the GEO null and is derived here
  rather than hoped for.

One thing this section deliberately does **not** do: subtract these lines, or
exclude frequencies near them, from the payload periodograms. Doing so would
require asserting that the model list is complete, which it is not (fitting
artefacts correlated with tracking geometry are in neither the list nor any
textbook). The empirical passive null carries all of it, listed and unlisted,
and that is the whole reason the control is worth more than the model.

## 7. Change-points

Computed only on the primary channel, only for objects with at least **4**
usable windows, and only in the registered forms below. Both forms are run
identically on the held-out passive audit half, and **both are reported with
that passive rate beside them**; a change-point count without its control rate
is not a result this registration permits.

### 7.1 Rhythm shift

A shift is declared at the boundary between window `k` and `k+1` iff:

- windows `k-1`, `k` and windows `k+1`, `k+2` all exist, are usable, and all
  four are **significant** under §6;
- `|P_before - P_after| / min(P_before, P_after) > 0.35`, where `P_before` and
  `P_after` are the median dominant **periods** of the two pairs.

The `0.35` is **`pipeline.orbit_campaigns.REPEAT_RELATIVE_TOLERANCE`**,
imported rather than restated. It is this repository's existing, load-bearing
answer to "how different do two station-keeping quantities have to be before
they are not the same thing", and reusing it is deliberate: inventing a fresh
tolerance for T3 would be exactly the free parameter a registration is
supposed to remove. It is a screen, not a law.

Requiring two significant windows on each side, rather than one, is what
prevents a single noisy window from producing a shift; it costs change-point
resolution (a shift is localised to within one 360-day step, and needs 4
windows ≈ 2160 days of context) and that cost is stated in §9.

### 7.2 Rhythm stop

A stop is declared at the boundary between `k` and `k+1` iff windows `k-1` and
`k` are usable and significant, and windows `k+1` and `k+2` are **usable**
(admissible under §5.3 — so the object is still being tracked, and this is not
an archive hole) and **not significant**. The usability requirement on the
"after" side is the entire content of the definition: without it, "stopped
station-keeping" and "left the archive" are the same event, and U2 would be
measuring the catalogue rather than the satellite.

### 7.3 Calibration

The passive audit half yields `stops_per_passive_object` and
`shifts_per_passive_object` by the identical procedure. Those are the
false-positive rates for E2 and are reported with every E2 number.

## 8. Multiple testing

Three multiplicities exist and each is handled by a named, pre-registered
mechanism:

1. **Across frequency, within a window (2,676 grid points).** Absorbed into
   the statistic: `P_max` is already a maximum over the grid, and its null is
   measured empirically over passive windows with the same grid (§6). No
   analytic correction is applied, because analytic Lomb-Scargle false-alarm
   probabilities assume independent Gaussian white-noise frequencies and this
   data is neither independent nor white.
2. **Across windows, within an object.** The per-object statistic is the
   maximum `P_max` over the object's usable windows, and it is compared
   against a null built the same way: for each calibration-half passive
   object, its own maximum-over-windows `P_max`. **Object-level statistic
   against object-level null** — so an object with 17 windows is not advantaged
   over one with 2 by having had more chances. Windows overlap and are
   therefore dependent; the empirical object-level null carries that dependence
   exactly, where any analytic per-window correction would not.
   - Per-object threshold: the window-count is itself matched, by comparing
     each payload object only against calibration-half passive objects whose
     usable-window count falls in the same band `{2-3, 4-7, 8-15, >=16}`,
     with the same fallback-to-pooled rule and the same recording requirement
     as §6.4.
3. **Across objects (≈11,002 payloads).** **Benjamini-Hochberg FDR at
   `q = 0.05`**, applied to the per-object empirical p-values
   `p_i = (1 + #{calibration passive objects with statistic >= object i's}) /
   (1 + #{calibration passive objects in the matched cell})`. BH rather than
   Bonferroni because the question is "what fraction of payloads have a
   rhythm", a fraction-of-discoveries question, and BH controls exactly that.
   The `+1` in numerator and denominator is the standard conservative
   correction for a finite permutation/reference set; p-values are therefore
   floored at `1/(1+n_cell)` and the floor is reported where it binds.
   - **The identical BH procedure, at the identical `q`, is run on the
     held-out passive audit objects**, so E3's audit number is measured at
     matched multiplicity, not at a raw threshold.
4. **Across channels.** Primary, S1, S2 each carry independent thresholds and
   independent BH runs, and are reported in separate tables (§3.2). No
   "significant in at least one channel" statistic is computed or reported,
   because that is precisely the union that would need a fourth correction.

Both the **raw threshold count** (objects over the §6.3 99th-percentile
threshold) and the **BH-surviving count** are reported; the headline E3 number
is the BH one.

## 9. Blind spots, declared in advance

These are deliverables of U3, not apologies. Each is stated with its cause and,
where possible, its size.

1. **Continuous low-thrust is invisible, by construction.** Electric
   propulsion spread over days changes `a` by metres per revolution and
   produces a *ramp*, not a rhythm. §5.2's cubic detrend removes exactly that
   ramp. `pipeline/orbit_campaigns.py` already records the measured instance:
   STARLINK-3005 offers 789 usable intervals to the step detector and produces
   zero events. T3's periodogram will do no better and will say so: an
   electrically-propelled satellite under continuous thrust is expected to
   return `none`, and **`none` for such an object is not evidence it is not
   manoeuvring.**
2. **Anything faster than 2 days is unreachable.** Derived in §0.2: the
   sampling comb's first carrier is at 1.0 c/d and the band stops at 0.5 c/d
   to stay clear of it. Payload median spacing is 0.3989 d, so a genuine
   3-day or 5-day cadence is comfortably resolved, a 2-day cadence sits on the
   band edge, and a daily or sub-daily cadence is not measurable with this
   archive at all.
3. **North-south GEO station-keeping does not appear in the primary channel**
   (§3.2). It is why S1 exists; a GEO satellite returning `none` on the
   primary has not been shown to be un-kept.
4. **Aliasing is bounded, not absent.** Within the band, the comb cannot
   manufacture a detection (§0.2). Leakage from the carriers' skirts into low
   `f` is real, is not modelled, and is absorbed into the empirical null —
   which means it is *calibrated* on the passive class, whose sampling comb
   §0.2 measured to be similar but **not identical** (passive window power at
   2.0 c/d is 0.075 against the payload's 0.017). The residual after §6.3's
   cadence-band matching is unquantified and is named here as such.
5. **The two classes occupy different eras** (§6.4). Unmatched; diagnosed by
   the by-year table, not corrected.
6. **Change-points need ~6 years of context** (§7.1), so the change-point half
   of T3 speaks only about long-lived objects, and its population is a
   subset of E1's — reported as its own denominator, never as a fraction of
   all payloads.
7. **A rhythm that was never there is not distinguishable from a rhythm too
   weak to see.** Every `none` in this track means "no periodicity above the
   passive-calibrated threshold in the 2–220 d band on this channel", and the
   results report writes it that way, not as "does not station-keep".
8. **`object_type` is taken from the catalogue and is not audited here.** A
   mislabelled payload in the passive class raises the measured passive
   false-positive rate; the direction is conservative for E3's ratio, and the
   count is not known.

## 10. Acceptance criteria — when the pilot is informative

Registered before any number exists, as a ladder with no discretionary rung.

**Gate A — is the null calibrated at all?** Measure `frac_sig(passive_audit)`
at the §6.3 thresholds, BH-corrected per §8.
- `<= 0.02` (twice the nominal 1%): the null **transfers**; proceed.
- `> 0.02`: the pilot is reported **UNCALIBRATED**. The thresholds are not
  re-tuned, the percentile is not moved, and no payload fraction is quoted as
  a detection rate. The result is the measured miscalibration and its
  by-year/by-stratum breakdown, which is itself a finding for T5a — it says
  the covariate matching available from TLE-derived quantities alone is
  insufficient, which is the same lesson Phase 3 is teaching in its own lane.

**Gate B — separation.** Only evaluated if Gate A passes. Compute the
bound-to-bound ratio `payload_frac_lower / passive_audit_frac_upper` using
`orbit_events._jeffreys_interval` at the same coverage
`orbit_events._control_rates` uses, and the existing
`orbit_events.separation_verdict` shape:
- `>= 10.0` (`pipeline.orbit_events.MIN_SEPARATION_BOUND_RATIO`, this estate's
  existing bar, imported not restated): **INFORMATIVE**.
- `3.0 <= ratio < 10.0`: **WEAK** — reported as a pilot that separates but does
  not meet the estate's shipped-gate bar, and every downstream use (U1, U2)
  must carry that word.
- `< 3.0`: **UNINFORMATIVE**.

**Gate C — is the change-point half powered?** At least **20** payload objects
with `>= 3` significant windows. Below that, E2 is reported as
**UNDERPOWERED** with its actual count, and no EOL telltale claim (U2) is made
on this pass.

The three gates are reported independently and all three verdicts appear in
the results report regardless of how they come out. **There is no combined
"overall pass".** A WEAK Gate B with a passing Gate A and an UNDERPOWERED
Gate C is a perfectly possible and perfectly reportable outcome.

## 11. Stop rules and no-shopping

- **Seed 20260921** fixes the calibration/audit split hash string (§6.2) and
  every random draw T3 makes. It is not changed after a number is seen.
- **One measurement pass.** If the pass completes, its numbers are the
  registered result. A pass that fails technically (crash, GPU fault,
  integrity error) may be re-run; a pass that completes and produces an
  unwelcome number may not.
- **The 99th percentile is the primary and the only primary** (§6.3). The 95th
  and 99.9th are displayed for shape and are never promoted.
- **No threshold in shipped code changes on this registration's evidence.**
  T3 writes documentation and one dated JSONL artifact. Any change to
  `pipeline/orbit_events.py`, `pipeline/orbit_campaigns.py`,
  `tools/fuel_odometer.py` or any EOL lane requires its own separate,
  reviewed commit citing both this registration and the measured result — never
  the same commit as the measurement.
- **T3 does not touch T1's or T2's files.** `tools/phase3_*.py`,
  `docs/phase3-*`, `docs/repricing-*` and `docs/paper-a-*` are out of scope by
  registration, and `tools/paperb_strata.py` and `pipeline/*` are **imported,
  never edited**, by this track.
- **The detector boundary question of `docs/phase3-preregistration-20260921.md`
  §4 (`INCLINATION_CORROBORATION_MIN_DEG`) is untouched by T3.** T3 runs no
  detector, so it cannot resolve it as a side effect, and it does not.
- **If T4 (§12) is later implemented, it re-enters at its own registration.**
  Nothing in this document licenses a synchrony claim.

## 12. Deliverables

1. This pre-registration, committed **alone**, ahead of every T3 artifact.
2. A batched GPU generalised-Lomb-Scargle implementation, with offline tests,
   reading the archive read-only, added to the orbit test suite and leaving it
   green.
3. `docs/cadence-results-20260921.jsonl` — one row per object, carrying at
   minimum: `norad`, `name`, `objectType`, class, split half, per-window
   `P_max` and `f*`, the matching rung used (§6.4), the window-count band
   (§8.2), the empirical p-value, BH verdict, `harmonic_ambiguous` flag, and
   every change-point found.
4. `docs/cadence-results-20260921.md` — E1–E4, the three gate verdicts, the
   fallback-rung exposure line, the by-year null diagnostic, and every number
   carrying inline `<!-- src: -->` provenance.
5. `docs/synchrony-design-20260921.md` — T4, design and draft registration
   skeleton only, clearly labelled DRAFT.

## 13. Resource bounds

Read-only archive access via `orbit_campaigns.open_archive_for_reading()`,
`PRAGMA query_only=1`, `nice 19`, idle I/O class, a single streaming extraction
pass. The T1 Phase 3 measurement is running concurrently on the same archive;
T3 takes one pass and yields to it. GPU work goes through
`/home/sdegan/gpu-broker/gpu-run` with an honest `--estimate-mib`, class
`standard`, running **beside** the resident SR training claims on Sean's
explicit 2026-09-21 authorization, and may split across both cards with
`--card`-pinned claims. `CUDA_VISIBLE_DEVICES` arrives as a GPU **UUID** and is
never parsed as an integer. No device-wide VRAM gate is taken. T3 creates **no
recurring lane**, so it owes no `gpu-consumers.json` row; its runs are ledgered
by the broker.

## Commit references

- `ec89303` — `docs/research-program-runbook-20260921.md`, the seven-track
  roster that assigns T3 and T4, committed before this registration.
- `docs/phase3-preregistration-20260921.md` — the sibling registration whose
  structure and discipline this document follows.
- `f317a28` — Paper B pre-registration, committed ahead of every Paper B
  result; the origin of the strata, bands and Jeffreys machinery §6 imports.
- `7626c55` — Paper B results: the finding that a pooled passive floor does
  **not** transfer to the payload covariate mix. That finding is why §6.3
  matches and §6.4 discloses, and why §10's Gate A exists as a way for this
  pilot to fail honestly.
