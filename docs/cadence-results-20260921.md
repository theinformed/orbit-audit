# T3 results: station-keeping cadence fingerprints

Measured 2026-09-21 under `docs/cadence-preregistration-20260921.md`, committed
**alone at `1a51afe`, before this measurement's code existed** (the
implementation followed at `1ac5050`). Every rule applied below was fixed in
that registration; nothing here was chosen after a number was visible, and the
registered outcome is reported whichever way it came out.

Every number carries inline `<!-- src: -->` provenance naming the artifact and
field it came from. The artifacts are
`docs/cadence-results-20260921.jsonl` (one row per object),
`docs/cadence-results-20260921-receipt.json` (the population quantities),
`docs/cadence-results-20260921-lines.json` (the descriptive diagnostic of §5),
and the two per-shard summaries under `/home/sdegan/t3-cadence/full/`.

---

## 0. Verdict in one paragraph

**The registered per-object test found nothing, in either class.** Zero of
7,884 payloads and zero of 5,485 held-out passive controls survive
Benjamini-Hochberg at q = 0.05
<!-- src: cadence-results-20260921-receipt.json E3_bh.payload.hits, E3_bh.passiveAudit.hits -->.
Gate A passes but **vacuously**, because the procedure rejected nothing
anywhere; Gate B is NOT EVALUABLE; Gate C is POWERED
<!-- src: cadence-results-20260921-receipt.json gates -->. At the registered
window-level threshold the instrument is worse than uninformative: payloads
exceed it **less** often than the passive control does
(3.36% against 9.32%)
<!-- src: cadence-results-20260921-receipt.json E3_rawWindowThreshold -->, and
the held-out passive exceedance rate at a 99th-percentile threshold is **9.3
times its nominal value**, a measured failure of the window-level threshold to
transfer across an object-level split. §4 diagnoses why, and the diagnosis is
the useful part: **the registered statistic — the maximum normalised
Lomb-Scargle power over the band — is dominated by residual drag trend, not by
rhythm.**

And yet the free negative control earns its keep. Against a local background,
the pooled peak-frequency distribution carries a **narrow line at 14.00 ± 0.11
days that is 10.16x its local background in payloads and 0.94x — i.e. absent —
in the passive class**, carried by 208 geostationary payloads out of 214
<!-- src: cadence-results-20260921-lines.json payloadOnlyLineSweep[periodDays=14.0] -->.
That is the east-west station-keeping cycle, and §5.3 derives the deadband it
implies. The same analysis shows that the *strongest* payload line, at 27.5
days, is **not** station-keeping — it is carried by ETALON 1 and ETALON 2,
catalogued as PAYLOAD and in fact passive laser-ranging spheres with no
propulsion (§5.4). Both conclusions are available only because the control was
run through the identical pipeline.

## 1. What ran, and what it cost

### 1.1 Extraction

One read-only streaming pass over `/home/sdegan/space-orbit-history/orbit-history.sqlite3`
(`PRAGMA query_only=1`, `nice 19`, idle I/O), taken while the T1 Phase 3
measurement held six concurrent readers on the same file.

| | |
|---|---:|
| Objects passing the registered screen in `object_rollup` | 36,302 <!-- src: full/index.json census.object_rollup_rows --> |
| Excluded: `object_type` NULL or UNKNOWN (prereg 3.1) | 13,375 <!-- src: full/index.json census.excluded_unlabelled --> |
| Excluded: baseline too short for even one 1080-day window | 2,589 <!-- src: full/index.json census.excluded_short_baseline_for_one_window --> |
| **Objects extracted** | **20,338** <!-- src: full/index.json census.kept --> |
| — payload | 8,841 <!-- src: full/index.json census.by_class.payload --> |
| — passive (DEBRIS + ROCKET BODY) | 11,497 <!-- src: full/index.json census.by_class.passive --> |
| Element sets read | 161,234,467 <!-- src: full/index.json census.element_sets --> |
| Wall clock | 283.2 s <!-- src: full/index.json census.seconds --> |

### 1.2 The GPU pass, and what it actually held

Two shards, split across both cards, each admitted by
`/home/sdegan/gpu-broker/gpu-run`, running **beside** the two resident SR
training claims (11,264 MiB each) on Sean's 2026-09-21 authorization.
`CUDA_VISIBLE_DEVICES` arrived as a GPU UUID and was never parsed as a number.

| | shard 0 | shard 1 |
|---|---:|---:|
| Broker request | `2a6e42fc-c585-47b4-b525-a1f94b9d5300` | `13b46bf5-f3f6-4f5e-b4f9-6f9910cdc782` |
| Card / UUID | 0 / `GPU-e7724e1e-…` | 1 / `GPU-4fc5964b-…` |
| `--estimate-mib` claimed | 2,500 | 1,800 |
| **Peak CuPy pool actually held** | **1,145.2 MiB** | **1,145.2 MiB** |
| Objects | 10,169 | 10,169 |
| Windows considered / admitted | 191,707 / 157,957 | 191,928 / 158,071 |
| Batches | 1,544 | 1,551 |
| Wall clock | 1,056.7 s | 225.5 s |

<!-- src: /home/sdegan/t3-cadence/full/mm-shard0.npz.summary.json and mm-shard1.npz.summary.json -->

**316,028 window-periodograms**, each over the registered 2,676-point frequency
grid — 8.457e8 sinusoid fits — in **1,057 s of wall clock across two consumer
cards that were simultaneously running someone else's training job.** Shard 1,
which ran when the host CPU was less contended, did its 158,071 windows in
225.5 s; at that rate **a single RTX 4080 would do the whole catalogue in about
7.5 minutes.**

Two things in that table are reported rather than tidied. The 2,500 MiB
estimate on shard 0 was an a-priori guess made before anything had been
measured; when card 1's admissible headroom turned out to be 2,402 MiB the
claim was **lowered to the measured figure (1,800 MiB against a measured
1,145 MiB peak pool plus CUDA context), not forced through**. And the two
shards differ 4.7x in wall clock for identical work; the cause was host CPU
contention (load average 16.6 against the six Phase 3 readers), not the GPU —
card 0 was at 64% utilisation while shard 0 ran. That is a real cost of
sharing the host and it is not hidden here.

Window rejections, applied identically to both classes
<!-- src: mm-shard{0,1}.npz.summary.json rejects -->: 47,777 for too few
samples, 13,625 for an interior gap over 45 days, 6,205 for insufficient span.
**957 payload objects and 385 passive objects produced no usable window at
all** and are `insufficient`, never `none` (prereg 2)
<!-- src: derived from index.json census.by_class minus receipt population -->.

### 1.3 Analysed population

| | |
|---|---:|
| Payload objects | 7,884 <!-- src: receipt population.payloadObjects --> |
| Passive, calibration half | 5,627 <!-- src: receipt population.passiveCalibrationObjects --> |
| Passive, **held-out audit half** | 5,485 <!-- src: receipt population.passiveAuditObjects --> |
| Windows analysed | 316,028 <!-- src: receipt population.totalWindowsAnalysed --> |

## 2. E3 — the audit number, as registered

### 2.1 Object-level, Benjamini-Hochberg (the registered headline)

| | payloads | held-out passive |
|---|---:|---:|
| Significant after BH at q = 0.05 | **0 / 7,884** | **0 / 5,485** |
| Jeffreys 95% interval on the fraction | [0, 0.000319] | [0, 0.000458] |

<!-- src: receipt E3_bh -->

Zero in both classes. None of the four window-count bands produced a single
detection in either class
<!-- src: receipt byWindowCountBand -->. No payload p-value sat at the
reference-set floor <!-- src: receipt pValueAtFloorPayloads -->, so this is not
a resolution artefact of the finite null.

### 2.2 Window-level, at the matched-cell threshold (also registered, prereg 8)

| | payloads | held-out passive |
|---|---:|---:|
| Objects with ≥1 window over its matched 99th-percentile threshold | 265 / 7,884 = **3.361%** | 511 / 5,485 = **9.316%** |
| Jeffreys 95% | [0.02980, 0.03776] | [0.08569, 0.10107] |

<!-- src: receipt E3_rawWindowThreshold -->

**The control fires three times as often as the treated class.** Bound to
bound, `payload_lower / passive_upper = 0.0298 / 0.1011 = 0.295` — under the
registered Gate B ladder that reads UNINFORMATIVE, and the *sign* says the
statistic anti-discriminates.

Separately, 9.316% is **9.3x the 1% a 99th-percentile threshold nominally
buys.** The thresholds were computed over calibration-half *windows*, treating
windows as exchangeable; they are not — a passive object contributes up to 50
strongly correlated windows, and passive objects carry a median of 17 of them
against payloads' 4
<!-- src: derived from cadence-results-20260921.jsonl, windows per object -->.
This registration did **not** register a clustered estimator for the
window-level threshold, and that omission is now measured rather than
suspected. It is the same lesson `docs/paperb-results-20260920.md` (`7626c55`)
taught about the pooled passive floor, arriving in a second lane.

### 2.3 The three gates, as registered

| Gate | Registered rule | Measured | Verdict |
|---|---|---|---|
| **A** — is the null calibrated | held-out passive BH fraction ≤ 0.02 | 0.0 | **CALIBRATED — but vacuously** |
| **B** — separation | `payload_lower / passive_upper` ≥ 10 informative, ≥ 3 weak | payload lower bound is 0 | **NOT EVALUABLE** |
| **C** — change-point power | ≥ 20 payloads with ≥ 3 significant windows | 107 | **POWERED** |

<!-- src: receipt gates -->

Gate A's pass is reported as vacuous and must not be quoted without that word:
the BH procedure rejected nothing in *either* class, so "the passive
false-positive rate is 0" carries no information about whether the null would
have transferred had anything been detected. §2.2's 9.3x is the honest
statement about calibration at this pilot's scale.

### 2.4 Covariate matching, and how far it actually reached

Of the five-factor matching cells, 88 held the registered 200-window minimum
from the calibration half; 64 at the first fallback rung, 31 at the second, 8
at the third <!-- src: receipt thresholds.cellsAtOrAboveMinimum -->. Payload
best-windows landed on the rungs as: full cell 2,465; drop eccentricity 3,186;
drop inclination 917; drop perigee 33; pooled 1,283
<!-- src: receipt matchRungs -->. **28.32% of payload objects were judged on a
fallback rung at or below "drop inclination"**
<!-- src: receipt payloadExposureOnFallbackRungs -->, which the registration
requires be stated every time these numbers are.

The by-year null diagnostic registered in prereg §6.4 against the unmatched
solar-era confound is uninformative here for the same reason Gate A is: the
audit-half fraction is 0.0 in every year from 1994 to 2023
<!-- src: receipt nullByYear -->. The confound is **not** shown to be absent;
it is untested, because there were no detections to stratify.

## 3. E2 — change-points

| | payloads | held-out passive |
|---|---:|---:|
| Objects with ≥ 4 usable windows | 4,172 | 4,820 |
| Rhythm **shifts** (episodes) | 0 | 0 |
| Rhythm **stops** (episodes) | 140 | 176 |
| Stops per eligible object | **0.03356** | **0.03651** |

<!-- src: receipt E2_changepoints -->

**The stop detector fires slightly more often on objects that physically cannot
station-keep than on payloads.** As registered, E2 therefore carries no
end-of-life information from this pass, and no object's EOL status is or may be
changed on this evidence (U2 is not discharged).

Inspection of the payload "stops" shows why, and it is blind spot §9.8 of the
registration in action: they are EXPLORER 7 (1959), ELEKTRON 1 and 3 (1964),
SECOR 5 (1965), COSMOS 86–90 (1965)
<!-- src: cadence-results-20260921.jsonl, payload rows with non-empty stops -->
— objects catalogued as PAYLOAD that have been functionally debris for sixty
years. A "stop" found on them is a correct detection of nothing happening.

Zero shifts in either class is a power statement, not a finding: a shift
requires four consecutive *significant* windows straddling the boundary, and
§2 shows significance was essentially never awarded.

## 4. Why the registered statistic failed — diagnosed, not excused

The registered per-object statistic is `max P_max` over an object's windows,
where `P_max` is the maximum normalised generalised-Lomb-Scargle power over the
2–220 day band. Three measurements together explain the null.

**(a) The peaks are not where rhythms are.** 63.93% of payload window peaks and
**87.64% of passive window peaks** land at periods above 100 days; only 18.45%
and 6.73% respectively land below 30 days
<!-- src: derived from mm-shard{0,1}.npz, peak period distribution by class -->.
The calibration-half pooled 99th percentile of `P_max` is **0.9641**
<!-- src: receipt thresholds.pooledCalibrationP99 --> — that is, one window in
a hundred is fit to 96% of its variance by a single sinusoid. Nothing about a
manoeuvre rhythm does that. A smooth residual does.

**(b) The cause is residual trend, and the registration under-provisioned
against it.** Prereg §5.2 removes a cubic per 1080-day window and §4 justified
a 220-day band top by "W/3 = 360 d resolution, a factor 1.64 of margin". The
measurement says 1.64 was not enough: the unfitted curvature of drag decay
survives the cubic as a slow, smooth residual, and the longest sinusoids in the
band fit it nearly perfectly. The pile-up is visible as a broad hump — at
period 180.75 d the "excess over local background" is 20.4x in payloads and
**38.4x in the passive control**, with a core half-width of ±18.2 days
<!-- src: cadence-results-20260921-lines.json payloadOnlyLineSweep -->. A
feature 37 days wide is not a line; it is the band's shoulder.

**(c) `max` over windows is the wrong aggregator when the tail saturates.**
Passive objects carry a median of 17 usable windows against payloads' 4, and
their max-over-windows statistic is correspondingly *higher*: median 0.374
against payloads' 0.161
<!-- src: derived from cadence-results-20260921.jsonl statistic field by class -->.
The registration matched on window-count band (prereg §8.2) precisely against
this, and the band-matched result is still zero in every band — because within
a band the passive objects' longer, smoother, undisturbed histories still
produce the higher maxima. A payload's history is *broken up* by the very
manoeuvres we are looking for, which lowers its best single-sinusoid fit.

**The registration is binding and none of the above was changed.** It is
recorded here because it is the pilot's most useful output for T5a: the
bottleneck is not data volume and not GPU time — one gaming card did the whole
catalogue in under 18 minutes on two cards — it is that **a sinusoid is the wrong template for a
sawtooth, and a max-power statistic is the wrong detector for a trend-dominated
channel.** That is precisely the matched-filter argument T5a exists to make.

## 5. The descriptive line profile — what the control makes readable

> **Not a registered test.** The registration registers per-object significance
> and the E4 distribution; it does not register a line search. Nothing in this
> section carries a p-value, nothing here feeds a gate, and no inferential claim
> rests on it. It is reported because a null without a diagnosis is worth
> nothing, and because the structure it shows is what a registered T3.1 should
> be built to test. Reproducible via `tools/cadence_lines.py`.

Excesses below are against a **local** background annulus in frequency, and each
carries its core half-width **in days**, because the grid is uniform in
frequency and three grid steps spans ±0.11 d at 14 days but ±18.5 d at 182.

| Period | core half-width | payload excess | **passive excess** | payload objects | dominant regime |
|---:|---:|---:|---:|---:|---|
| **14.00 d** | ±0.109 d | **10.16x** | **0.94x** | 214 | GEO (208) |
| **12.50 d** | ±0.087 d | 3.67x | 0.54x | 300 | LEO (288) |
| **21.00 d** | ±0.245 d | 2.27x | 0.51x | 61 | GEO (44) |
| **75.25 d** | ±3.146 d | 3.61x | 0.18x | 572 | LEO (479) |
| 27.50 d | ±0.420 d | 22.78x | **8.17x** | 787 | GEO (470), MEO (255) |
| 163–200 d | ±15 to ±22 d | 5.6–33.4x | 9.2–38.4x | thousands | all — this is §4(b)'s shoulder, not a line |

<!-- src: cadence-results-20260921-lines.json payloadOnlyLineSweep -->

### 5.1 The lunar half-months are absent, which matters

At 13.661 d (half sidereal month) the payload excess is **0.72x** and at
14.765 d (half synodic month) **0.44x**
<!-- src: cadence-results-20260921-lines.json profile.payload.targets -->. The
14.00 d line is separated from both by far more than its ±0.11 d core, so it is
**not** a lunar term. Neither is it a harmonic of the 27.5 d line, whose half
is 13.75 d.

### 5.2 The 27.5-day line is natural, and ETALON proves it

The largest payload excess in the band (22.78x) sits at 27.5 d, within a grid
step of the anomalistic month (27.5546 d), the sidereal month (27.3217 d) and
the synodic Carrington rotation (27.2753 d) — the registration's §6.5 predicted
all three and this grid cannot separate them. It is present in the **passive
control at 8.17x**, so it is partly natural on that evidence alone.

The decisive evidence is internal. The two objects sitting most completely on
the line are **COSMOS 1989 (ETALON 1)**, 35 of 35 windows, and **COSMOS 2024
(ETALON 2)**, 30 of 35
<!-- src: cadence-results-20260921-lines.json payloadOnlyLineSweep[periodDays=27.5].topCarriers -->.
ETALON 1 and 2 are **passive laser-ranging geodetic spheres**: catalogued as
PAYLOAD, carrying no propulsion of any kind. Whatever puts them on a 27.5-day
line is not station-keeping. At their altitude (perigee 19,087 km, so
a ≈ 25,500 km, i ≈ 64.9°) atmospheric drag is negligible, so the solar-rotation route via
density is unavailable and the lunisolar gravitational terms of Kaula (1962)
and Cook (1962) are the available mechanism. Their measured dominant periods
are 27.47 d and 27.62 d, and neither has a single significant window
<!-- src: cadence-results-20260921.jsonl norad 19751, 20026 -->.

**Without the control this line would have been the headline finding, and it
would have been wrong.**

### 5.3 The 14.0-day and 21.0-day GEO lines, and the deadbands they imply

The 14.00-day line is carried by 208 GEO payloads of 214, named comsats at
perigee ≈ 35,770 km and eccentricity ≈ 0.0004: OPS 9437 (DSCS 2-7) on 23 of 23
windows, GORIZONT 13 on 21 of 28, GSAT 1 on 21 of 23, ASIASTAR on 16 of 24,
SYRACUSE 3A on 16 of 18, AFRISTAR, EUTELSAT 28A, CHINASAT 6B
<!-- src: cadence-results-20260921-lines.json payloadOnlyLineSweep[periodDays=14.0] -->.
Its passive excess is **0.94x — the control does not carry it at all.**

The 21.00-day line is Inmarsat-shaped: INMARSAT 3-F5 on 21 of 26 windows,
3-F3 on 14 of 27, 3-F1 on 13 of 27, with THAICOM 1 and BRAZILSAT B2
<!-- src: cadence-results-20260921-lines.json payloadOnlyLineSweep[periodDays=21.0] -->.

Derived rather than asserted. Earth's triaxiality drives longitude with
`d²λ/dt² = −18 n² J22 (R_e/a)² sin(2(λ − λ22))`; with `J22 = 1.8154e-6`,
`a = 42164.2 km`, `n = 2π/86164.0905 s⁻¹`, the amplitude is
`3.976e-15 rad s⁻² = 1.7006e-3 deg/day²`
<!-- src: cadence-results-20260921-lines.json derivations.geoLongitudeAccelerationDegPerDay2 -->.
A one-sided parabolic drift cycle across a deadband of half-width `Δλ` takes
`T = 4·sqrt(Δλ/A)`, so `Δλ = A·T²/16`:

| Cycle | at the max-acceleration longitude | at half that acceleration |
|---:|---:|---:|
| 14.0 d | ±0.0208° | ±0.0104° |
| 21.0 d | ±0.0469° | ±0.0234° |

<!-- src: cadence-results-20260921-lines.json derivations.eastWestDeadbandDeg -->

Both sit inside the ±0.05° longitude slot that is standard GEO practice, with
14 days the tight box and 21 days the loose one. **The observed periods are
consistent with east-west station-keeping under the derived triaxial
acceleration, at deadbands operators plausibly use.** That is the strongest
positive statement this pass supports, and it is a *consistency* statement, not
a significance claim.

### 5.4 The 75.25-day line is natural too — derived, and it nearly fooled us

572 objects, 479 of them LEO, 406 named COSMOS, clustered at perigee
1,368–1,463 km and inclination 74.0°
<!-- src: cadence-results-20260921-lines.json payloadOnlyLineSweep[periodDays=75.25] -->.
Passive excess **0.18x** — the control does not carry it. On the pattern of
§5.3 that reads as an operational cadence.

It is not. For that shell, the J2 nodal regression
`dΩ/dt = −(3/2) J2 (R_e/p)² n cos i` gives a plane-against-Sun (beta) period of
**151.5 to 155.3 days** over the altitude range, whose **half is 75.7 to 77.6
days**
<!-- src: cadence-results-20260921-lines.json derivations.cosmosShellBetaPeriodDays -->,
against a measured 75.25 d. The factor of two is physical, not fitted: the
thermosphere has a strong diurnal density bulge, and the orbit plane sweeps
past it **twice** per cycle against the Sun, so the drag — and therefore
`dn/dt` — is modulated at twice the nodal-relative frequency. The line is
absent from the pooled passive control only because passive objects are spread
over many altitudes and inclinations, so their half-beta periods scatter across
the band instead of piling at one value; this Cosmos family is a tight shell
and piles up.

**The control's silence is not sufficient evidence of an operational origin.**
A same-shell control, not a pooled one, is what this line needed — which is
exactly the design move T4 is built around
(`docs/synchrony-design-20260921.md` §3.1), arrived at here from the other
direction.

### 5.5 The 12.5-day line is unexplained

Same Cosmos 74° / ~1,450 km shell as §5.4 (285 of 300 objects named COSMOS),
payload excess 3.67x, passive 0.54x, core ±0.087 d. It is not a submultiple of
that shell's 76-day half-beta period and no derivation offered here accounts
for it. **It is reported as unexplained rather than assigned a plausible
cause.**

## 6. E4 — cadence distribution by regime and operator

Because no object reached BH significance, the registered E4 table of
*significant* cadences is empty in every regime and every operator family
<!-- src: receipt E4_byRegime, E4_byOperator -->. What follows is the
distribution of each object's **dominant period regardless of significance** —
descriptive, and labelled as such.

| | payload objects | passive objects |
|---|---:|---:|
| Dominant period p25 / p50 / p75 | 102.8 / 189.2 / 203.4 d | 165.9 / 182.8 / 196.0 d |
| Fraction with a dominant period < 30 d | **12.08%** | **6.23%** |
| Max-over-window statistic p50 / p90 | 0.161 / 0.674 | 0.374 / 0.732 |

<!-- src: derived from cadence-results-20260921.jsonl -->

Payloads are about twice as likely as the control to peak below 30 days, and
their statistic is systematically *lower* — §4(c).

Named families, dominant period (all objects, significance not required)
<!-- src: derived from cadence-results-20260921.jsonl by operator -->:

| Family | n | median P | p25 / p75 | fraction < 30 d |
|---|---:|---:|---:|---:|
| Starlink (SpaceX) | 2,809 | 203.4 d | 196.0 / 211.4 | **0.04%** |
| OneWeb | 618 | 203.4 d | 203.4 / 220.0 | **0.00%** |
| Intelsat | 96 | 42.8 d | 24.9 / 125.1 | 36.5% |
| Iridium | 101 | 43.0 d | 35.6 / 126.9 | 8.9% |
| GPS (NAVSTAR) | 69 | 27.8 d | 27.6 / 211.4 | 52.2% |
| Galileo | 27 | 27.6 d | 27.5 / 189.2 | 70.4% |
| BeiDou | 49 | 28.2 d | 27.5 / 171.2 | 53.1% |
| Cosmos (Russian) | 1,116 | 98.1 d | 77.6 / 189.2 | 17.1% |

The GNSS families cluster at 27.5–28.2 d. §5.2 has already shown that line to
be the lunisolar/solar-rotation term, demonstrated by ETALON in the same MEO
shell. **These are not GNSS station-keeping cadences and must not be quoted as
such.**

### 6.1 The registered continuous-low-thrust blind spot, measured

Prereg §9.1 predicted, in advance, that electrically propelled satellites under
continuous thrust would return `none`, and that `none` would not be evidence
they are not manoeuvring. Measured:

- **Starlink: 0 of 2,809 objects** have a single window over its matched
  threshold; median dominant period 203.4 d; 0.04% below 30 days.
- **OneWeb: 0 of 618 objects**; median 203.4 d; **0.00%** below 30 days.

<!-- src: derived from cadence-results-20260921.jsonl, operator rows, fields anyWindowOverThreshold and dominantPeriodDays -->

These are the two largest actively-manoeuvring constellations in orbit and the
instrument sees nothing in either. The registration said it would. This is a
confirmed prediction about a blind spot, not a measurement of their behaviour.

## 7. The three declared uses, discharged or not

- **U1 — fuel-odometer tightening.** **NOT DISCHARGED.** No cadence reached
  significance, so no burns-per-year figure is supplied and no odometer number
  changes. The GEO consistency of §5.3 is not a measured cadence.
- **U2 — EOL cadence-change telltale.** **NOT DISCHARGED, and measured to be
  uninformative at this design**: stops fire at 0.0336 per payload against
  0.0365 per passive control object (§3). No EOL status is changed.
- **U3 — matched-filter pilot for the supercompute slate.** **DISCHARGED, and
  the most valuable output of the pass.** Two consumer cards evaluated 316,028
  windows over a 2,676-point grid in 17.6 minutes of wall clock, beside someone
  else's training job, and the faster shard's rate implies one card could do it
  in 7.5. Compute is not the binding constraint. The binding constraints, now
  measured rather than assumed, are (i) template mismatch — a sinusoid against
  a sawtooth, §4; (ii) trend leakage into the low-frequency end of any band a
  fixed-window detrend can support, §4(b); (iii) an object-level threshold that
  does not transfer across an object-level split by a factor of 9.3, §2.2. Each
  is a concrete, quantified thing that dense template banks, covariance-aware
  sequence modelling and TLE re-fit ensembles (T5a, T5c) would attack directly.

## 8. Secondary channels

**Not run.** Prereg §3.2 registers inclination (S1) and eccentricity (S2) as
secondary channels with independent calibration and independent correction, to
be reported in separate tables. This pass measured the **primary channel only**
(`mean_motion`). S1 and S2 are **unexercised** — in those words — and nothing
in this report speaks to north-south GEO station-keeping, which §3.2 says is
invisible in the energy channel by construction.

## 9. What would be registered next, if T3 continues

Stated as candidates for a *separate* future registration, never as changes to
this one:

1. **A sawtooth template bank** instead of a single sinusoid — the direct
   consequence of §4, and the T5a pilot's own recommendation for itself.
2. **A clustered, object-level threshold estimator** for the window-level test,
   the way `docs/paperb-preregistration-20260920.md` §4 already does it for
   rates. §2.2 is the measurement that says this is needed.
3. **A same-shell rather than pooled control**, per §5.4's near-miss and
   T4's §3.1.
4. **A statistic other than the maximum** — §4(c) shows `max` rewards smooth
   passive histories over broken payload ones.
5. **Recording the fitted phase**, which `gls_power` computes and discards, and
   which `docs/synchrony-design-20260921.md` §3.5 names as T4's first
   implementation task.

## 10. Reproduction

```
tools/cadence_sampling_geometry.py 97      # prereg section 0.1, epochs only
tools/cadence_spectral_window.py 397       # prereg section 0.2, epochs only
tools/cadence_extract.py   --out <dir>
gpu-run --estimate-mib 1800 --class standard --card N -- \
  tools/cadence_measure.py --artifacts <dir> --out <dir>/mm-shardN.npz \
                           --shard N --shards 2 --channels mean_motion
tools/cadence_analyze.py   --artifacts <dir> --shards ... --out docs/cadence-results-20260921
tools/cadence_lines.py     --artifacts <dir> --shards ... --results ... --out ...-lines.json
```

Offline tests: `tests/test_orbit_cadence.py`, 51 tests. The orbit suite runs
681 tests and is green <!-- src: python3 -m unittest discover -s tests -p 'test_orbit*.py', 2026-09-21 -->.

## Commit references

- `1a51afe` — T3 pre-registration, committed **alone, before any T3 code or
  number existed**. The git history of that file is the timestamp that makes
  this report's discipline checkable.
- `1ac5050` — the implementation and its 51 offline tests, committed after the
  registration and before this report.
- `ec89303` — the research-programme runbook that assigns T3 and T4.
- `f317a28`, `7626c55` — Paper B's registration and its finding that a pooled
  passive floor does not transfer; the direct ancestor of §2.2's result.
