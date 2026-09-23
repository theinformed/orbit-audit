# T3 secondary-channel results: S1 inclination, S2 eccentricity

Measured 2026-09-22 under `docs/cadence-preregistration-20260921.md` (`1a51afe`)
and its supplementary `docs/cadence-s1s2-preregistration-20260922.md`, committed
**alone at `ffe2242`, before any S1 or S2 periodogram existed** — the shard
summaries of the 2026-09-21 primary pass record `"channels": ["mean_motion"]`
and nothing else, so nothing below was chosen after a secondary-channel number
was visible. Two registered predictions failed and are reported as failures;
one was confirmed and is reported with the alternative explanation it does not
exclude.

Every number carries inline `<!-- src: -->` provenance. The artifacts are
`docs/cadence-s1-results-20260922.jsonl` / `.../-receipt.json` (inclination, one
row per object), the matching `cadence-s2-*` pair (eccentricity),
`docs/cadence-s{1,2}-lines-20260922.json` (the pooled descriptive line profile),
`docs/cadence-s{1,2}-geo-20260922.json` (the GEO-restricted profile, the D1
evaluation and the derivations recomputed in code), and the two shard summaries
under `/home/sdegan/t3-cadence/full/s1s2-shard{0,1}.npz.summary.json`.

**S1 and S2 are secondary channels. Prereg 3.2 forbids quoting a secondary
result as if it were a primary one, and the acceptance gates of prereg 10 are
evaluated on the primary channel only.** Nothing here changes any gate verdict,
any shipped threshold, or any object's status.

---

## 0. Verdict in one paragraph

**A north-south analogue of the primary channel's 14-day east-west line
exists, and the registered definition D1 is met.** In the inclination channel,
restricted to GEO, the payload peak distribution carries a sharp line at
**14.00 d at 15.85x its local background, against 1.02x in the same-regime GEO
passive control and 0.36x in the pooled passive control**, carried by **56
named geostationary communications satellites**
<!-- src: cadence-s1-geo-20260922.json d1Verdict, d1Best -->. It is separated
from the half sidereal month by 3.11 core half-widths and from the half synodic
month by 7.03, and the neighbouring quarter-days carry 3 to 19 peaks against the
line's 234 — it is a line, not a shoulder
<!-- src: cadence-s1-geo-20260922.json d1Best.geoPayload, derivations.fourteenDaySeparationInCoreHalfWidths -->.
**But the two north-south periods this registration predicted in advance — 43 d
and 86 d, the two standard latitude boxes — are not there** (1.38x and 0.12x)
<!-- src: cadence-s1-geo-20260922.json targets -->, so the line is the
registration's P2 outcome, not its P1: north-south burns on the *east-west
operational cycle*, not at the cadence the deadband alone requires. And the
registered S2 corroboration **failed**: the eccentricity channel, which the same
east-west burns must also move, shows **no 14-day line at all** (0.92x, 16
objects) <!-- src: cadence-s2-geo-20260922.json targets -->. The registered
per-object test is null in both channels and both classes, as it was in the
primary, and the window-level threshold again fails to transfer — 7.3x nominal
in S1 and 9.4x in S2 <!-- src: cadence-s{1,2}-results-20260922-receipt.json E3_rawWindowThreshold -->.

## 1. What ran, and what it cost

No extraction pass was needed: `inclination.bin` and `eccentricity.bin` were
written by the single streaming pass of 2026-09-21 and have not been touched
since. Two shards, both cards, through
`/home/sdegan/gpu-broker/gpu-run`, class `standard`, running **beside the two
resident 11,264 MiB SR training claims** on Sean's 2026-09-21 authorization.
`CUDA_VISIBLE_DEVICES` arrived as a GPU UUID and was never parsed as a number.

| | shard 0 | shard 1 |
|---|---|---|
| Broker request | `99eadfdf-667a-40f5-8208-4bb5cfff5d12` | `d86c031c-b8f7-4496-b584-ff5768ac4f52` |
| Card / UUID | 0 / `GPU-e7724e1e-…` | 1 / `GPU-4fc5964b-…` |
| Queue wait | 0.466 s | 0.474 s |
| `--estimate-mib` claimed | 1,800 | 1,800 |
| **Peak CuPy pool actually held** | **1,145.2 MiB** | **1,145.2 MiB** |
| Window-channels evaluated | 315,914 | 316,142 |
| Batches | 3,082 | 3,094 |
| Wall clock | **978.5 s** | **458.6 s** |

<!-- src: /home/sdegan/t3-cadence/full/s1s2-shard{0,1}.npz.summary.json; queue waits from gpu-broker/state/decisions.jsonl sequences 1403-1408 -->

The 1,800 MiB estimate was **evidence, not a guess**: it is the figure the
primary pass measured itself needing, and the measured peak pool came back at
exactly the same 1,145.2 MiB, because the batcher's element budget is fixed and
does not grow with the channel count. **632,056 window-periodograms** over the
registered 2,676-point grid — 1.691e9 sinusoid fits — in **1,437 s of summed
card time, 978.5 s elapsed** (the two shards ran concurrently), across two cards
that were simultaneously running someone else's training job.
The broker ledger is the usage record; T3 creates no recurring lane and owes no
`gpu-consumers.json` row (prereg 13).

Shard 0 again ran 2.1x slower than shard 1 for identical work, the same host-CPU
contention effect the primary pass measured and did not hide.

### 1.1 The analysed population

Identical to the primary pass, by construction: prereg 5.3's sample-count, gap
and span tests are evaluated on **mean motion**, so S1 and S2 are measured on
exactly the windows the primary was measured on (s1s2-prereg 7.1).

| | |
|---|---:|
| Windows admitted | 316,028 <!-- src: s1s2-shard{0,1} summaries windowsAdmitted, 157957+158071 --> |
| Windows rejected: too few samples / gap > 45 d / span | 47,777 / 13,625 / 6,205 <!-- src: s1s2-shard{0,1} summaries rejects --> |
| Windows rejected as **constant** in inclination or eccentricity | **0** <!-- src: s1s2-shard{0,1} summaries rejects has no constant:* key --> |
| Payload objects | 7,884 <!-- src: cadence-s1-results-20260922-receipt.json population.payloadObjects --> |
| Passive, calibration half | 5,627 <!-- src: same receipt population.passiveCalibrationObjects --> |
| Passive, **held-out audit half** | 5,485 <!-- src: same receipt population.passiveAuditObjects --> |
| GEO payload objects / windows | 1,248 / 23,018 <!-- src: cadence-s1-geo-20260922.json populations.geoPayload --> |
| GEO passive objects / windows | 331 / 5,579 <!-- src: cadence-s1-geo-20260922.json populations.geoPassive --> |

Not one window in either secondary channel was constant to within its archive
quantum, so prereg 5.3(4) removed nothing and the two channels were evaluated on
every admitted window.

## 2. The registered test — S1 and S2 in their own tables

### 2.1 Object-level, Benjamini-Hochberg, per channel (prereg 8.4)

| | S1 payload | S1 held-out passive | S2 payload | S2 held-out passive |
|---|---:|---:|---:|---:|
| Significant after BH at q = 0.05 | **0 / 7,884** | **0 / 5,485** | **0 / 7,884** | **0 / 5,485** |
| Jeffreys 95% on the fraction | [0, 0.000319] | [0, 0.000458] | [0, 0.000319] | [0, 0.000458] |

<!-- src: cadence-s1-results-20260922-receipt.json E3_bh; cadence-s2-results-20260922-receipt.json E3_bh -->

Zero in every cell, in both channels, in all four window-count bands
<!-- src: both receipts byWindowCountBand -->. Six S1 and nine S2 payload
p-values sat at the reference-set floor
<!-- src: both receipts pValueAtFloorPayloads -->, so the floor binds for a
handful of objects and is reported as prereg 8.3 requires.

### 2.2 Window-level, at the matched-cell 99th-percentile threshold — the audit number

**Reported honestly, and it fails transfer again.**

| | S1 payload | S1 held-out passive | S2 payload | S2 held-out passive |
|---|---:|---:|---:|---:|
| Objects with ≥1 window over its matched threshold | 413 / 7,884 = **5.238%** | 401 / 5,485 = **7.311%** | 644 / 7,884 = **8.168%** | 515 / 5,485 = **9.389%** |
| Jeffreys 95% | [0.04763, 0.05747] | [0.06644, 0.08022] | [0.07579, 0.08788] | [0.08639, 0.10183] |

<!-- src: cadence-s{1,2}-results-20260922-receipt.json E3_rawWindowThreshold -->

In both channels the control still fires **more** often than the treated class.
Bound to bound, `payload_lower / passive_upper` = 0.0476 / 0.0802 = **0.594**
for S1 and 0.0758 / 0.1018 = **0.744** for S2 — both under the Gate B
UNINFORMATIVE rung, and the sign again says the statistic anti-discriminates.
Two things are nevertheless different from the primary channel, and both are
reported because they are measurements and not opinions:

- the primary's payload/passive window-level rates were 3.36% against 9.32%, a
  ratio of 0.36. S1's 5.24% against 7.31% is a ratio of **0.72** and S2's is
  **0.87**. The anti-discrimination is real in all three channels and is
  **weakest in the secondaries**;
- the held-out passive exceedance rate at a nominal-1% threshold is **7.3x**
  nominal in S1 and **9.4x** in S2, against 9.3x in the primary. The
  window-level threshold does not transfer across an object-level split in any
  channel. The cause diagnosed in the primary report §2.2 — thresholds computed
  over windows treated as exchangeable, when a passive object contributes a
  median of 17 strongly correlated windows against a payload's 4
  <!-- src: derived from cadence-s1-results-20260922.jsonl, windows per object by class --> —
  applies unchanged here, and the registration did not register a clustered
  estimator for it in either channel.

**Prereg 6.4's required line, stated every time these numbers are:** of the
5-factor matching cells, 88 held the registered 200-window minimum, 64 at the
first fallback rung, 31 at the second, 8 at the third
<!-- src: both receipts thresholds.cellsAtOrAboveMinimum -->.
**24.96% of S1 payload objects and 27.63% of S2 payload objects were judged on a
fallback rung at or below "drop inclination"**
<!-- src: cadence-s{1,2}-results-20260922-receipt.json payloadExposureOnFallbackRungs -->.
The by-year null diagnostic against the unmatched solar-era confound is
uninformative for the same reason it was in the primary: the audit-half BH
fraction is 0.0 in every year, 2005–2023 in S1 and 2006–2023 in S2
<!-- src: both receipts nullByYear -->. The confound is **not** shown to be
absent; it is untested, because there were no detections to stratify.

### 2.3 The gates are not evaluated here

Prereg 3.2 says the acceptance criteria of prereg 10 are evaluated on the
primary channel. The receipts do carry gate-shaped fields, computed by the
shared code path — Gate A "CALIBRATED" vacuously (nothing was rejected in either
class), Gate B NOT EVALUABLE, Gate C nominally POWERED at 130 S1 and 327 S2
payload objects with ≥3 significant windows
<!-- src: cadence-s{1,2}-results-20260922-receipt.json gates -->. **These carry
no acceptance meaning and must not be quoted as verdicts.** Likewise the
`shifts` and `stops` fields present on every S1/S2 row are a by-product of the
shared analyser: prereg 7 computes change-points **on the primary channel only**,
and no S1/S2 change-point number is a result of this pass or is reported as one.

## 3. S1 — the north-south headline

### 3.1 D1 is met, at 14.00 days

The four clauses of s1s2-prereg 5.3, evaluated on the GEO populations:

| Clause | Registered bar | Measured at 14.00 d | |
|---|---|---:|---|
| 1 — GEO payload excess | ≥ 5.0 | **15.848** | PASS |
| 2 — same-regime GEO passive excess | ≤ 1.5 | **1.016** | PASS |
| 3 — clear of every derived natural line | > 1 core half-width | **3.114** (half sidereal month) | PASS |
| 4 — distinct GEO payload carriers | ≥ 20 | **56** | PASS |

<!-- src: cadence-s1-geo-20260922.json d1Best.d1 -->

**Verdict: `D1 MET`** <!-- src: cadence-s1-geo-20260922.json d1Verdict -->, and
it is the only period in the whole 3–200 d sweep that meets it
<!-- src: cadence-s1-geo-20260922.json d1PassingCandidates, length 1 -->.

It is a line and not a shoulder. The sweep's neighbourhood, in core peak counts
among GEO payload windows <!-- src: recomputed from s1s2-shard{0,1}.npz with tools/cadence_lines.local_excess on the GEO payload mask -->:

| Period | 13.50 | 13.75 | **14.00** | 14.25 | 14.50 | 14.75 |
|---|---:|---:|---:|---:|---:|---:|
| core peaks | 3 | 8 | **234** | 9 | 1 | 13 |
| local expectation | 32.8 | 16.7 | **14.8** | 15.5 | 36.8 | 36.9 |
| excess | 0.09 | 0.48 | **15.85** | 0.58 | 0.03 | 0.35 |

### 3.2 It is not a lunar term

At the half sidereal month (13.6609 d) the GEO payload excess is **0.18x** and
at the half synodic month (14.7653 d) it is **0.35x**
<!-- src: cadence-s1-geo-20260922.json targets -->. The line's core half-width is
±0.1089 d and it sits 3.11 and 7.03 core half-widths from those two
<!-- src: cadence-s1-geo-20260922.json derivations.fourteenDaySeparationInCoreHalfWidths -->.
The registration committed in advance to calling a line at 13.7 d a lunar term;
this one is not at 13.7 d, and the lunar half-months are where the payload
distribution is **emptiest**, not fullest.

### 3.3 The control, stated with its actual weight

- **Pooled passive control: 0.36x** — 7 core peaks against 19.25 expected
  <!-- src: cadence-s1-geo-20260922.json d1Best.pooledPassive -->. This is the
  statement with real weight behind it: the passive class does not carry 14 d.
- **Same-regime GEO passive control: 1.02x** — but only **1** core peak against
  **0.98** expected <!-- src: cadence-s1-geo-20260922.json d1Best.geoPassive -->.
  D1's clause 2 is met, and **it is met on an expected count below one window.**
  A same-regime control with that little weight cannot exclude a 1.5x excess, and
  saying it does would be exactly the error the primary report's §5.4 warned
  about from the other direction. The GEO passive population is 331 objects and
  5,579 windows, and almost all of its peaks pile at the band top (§3.6). **The
  same-regime control's silence at 14 d is consistent with the line being
  payload-only and is not on its own sufficient evidence of it.** The pooled
  control is what carries that claim here.

### 3.4 The registered P1 predictions failed

s1s2-prereg 3.4 predicted, before any S1 number existed, that a north-south
fingerprint would most likely sit at **38–49 d** (the ±0.05° latitude box) or
**77–97 d** (the ±0.10° box), because those are the boxes standard GEO practice
uses and neither interval contains a derived natural line. Measured:

| Registered target | Period | GEO payload excess | GEO passive | pooled passive |
|---|---:|---:|---:|---:|
| P1 tight box ±0.05° | 42.97 d | **1.38** | 1.52 | 0.53 |
| P1 loose box ±0.10° | 85.94 d | **0.12** | 0.03 | 0.13 |

<!-- src: cadence-s1-geo-20260922.json targets -->

As bands rather than lines (s1s2-prereg 3.4 P3, which registered in advance that
the ±0.10° box is a band and no narrow-line test can confirm it), the GEO
payload share of window peaks inside 38.4–48.7 d is 0.0120 against a
uniform-in-frequency 0.0111, and inside 76.9–97.4 d it is 0.0515 against 0.0055
<!-- src: cadence-s1-geo-20260922.json predictedBands -->. The second looks like
a 9x band excess, but the pooled passive share in the same band is 0.0611 —
**higher than the payload's** — so it is the low-frequency shoulder, not a
north-south signature.

**Neither registered deadband cadence is present. The prediction failed and is
reported as failed.**

### 3.5 What the line means, and the alternative it does not exclude

The registration wrote P2 down in advance: a 14.0-day north-south line, if it
appeared, would mean operators run north-south burns on the *east-west*
operational cycle rather than at the cadence the deadband alone requires,
because triaxiality and lunisolar torque have no physical reason to agree.
That is what happened.

**Derived, not asserted.** At the registered central drift rate of 0.85 deg/yr,
a 14.0-day cycle implies a latitude deadband of
`R = (di/dt) T / 2 = 0.01629°` <!-- src: cadence-s1-geo-20260922.json derivations.northSouthDeadbandDeg["14.0"] -->,
roughly a third of the standard ±0.05° box. The carriers' own median
inclinations say this is **not** a deadband measurement for most of them:
CHINASAT 9 at 0.015° and CHINASAT 12 at 0.018° would be consistent with a
±0.016° box, but BADR 6 at 0.063°, ARABSAT 4B at 0.054°, BADR 7 at 0.049° and
TURKSAT 2A at 0.050° hold inclinations three to four times that
<!-- src: cadence-s1-geo-20260922.json d1Best.topCarriers, targets["P2 east-west coincidence 14.0 d"].topCarriers -->.
An object inside a ±0.05° box that shows a 14-day inclination rhythm is being
touched more often than its box requires — an **operational schedule**, which is
what P2 said it would be.

One consistency check the drift derivation passes from the operational
direction: correcting 0.85 deg/yr of inclination costs
`Δv = 2 v sin((di/dt)/2) = 2 × 3074.7 × sin(0.425°) = 45.6 m/s/yr`, which is the
standard published north-south budget for a geostationary satellite. The
budget is set by the drift rate and not by the cycle, so this does not test the
cadence — it tests the 0.85 deg/yr the cadence was read against, and it passes.
At a 14-day cycle that is 1.75 m/s per burn; at the 43-day cycle the ±0.05° box
would imply, 5.4 m/s per burn.

**The alternative this pass does not exclude.** An east-west burn is tangential
and in-plane, so to first order it does not change inclination — but a manoeuvre
the TLE fitting process does not model is absorbed by *all* the fitted elements,
so a strong east-west rhythm could in principle bleed into fitted inclination.
The evidence against that reading is internal and is not decisive:

- **39 of the 56** S1 carriers also carry the 14-day line in mean motion, but
  **17 do not**; and **169** of the primary channel's 208 GEO carriers show no
  14-day inclination line at all
  <!-- src: derived from mm-shard{0,1}.npz and s1s2-shard{0,1}.npz, GEO payload carriers within 3 grid steps of 1/14 d -->.
  A pure fit-correlation artifact would put the inclination line on the
  *strongest* mean-motion carriers; instead the two carrier sets overlap by 70%
  in one direction and 19% in the other.
- If it were fit bleed-through from the east-west burns, the **eccentricity**
  channel — which those burns genuinely move, by `|Δe| = 2Δv/v ≈ 5.0e-5` per
  burn — should carry the line at least as strongly. **It does not** (§4.1).

Both observations are consistency arguments, not proofs, and the registration
does not license a synchrony or cross-channel statistic (s1s2-prereg 7.6). **The
14-day inclination line is reported as a descriptive consistency statement about
north-south operations, not as a significance claim and not as a proven separate
burn set.**

### 3.6 Named carriers, verified against known operators

s1s2-prereg 5.4 requires 3–5 named carriers and a statement of whether each is a
plausibly propelled satellite — the ETALON discipline, after the primary run's
strongest payload line turned out to be carried by two propulsion-free
laser-ranging spheres catalogued as PAYLOAD.

| NORAD | Name | Windows on line | Median inclination | Median perigee | Operator / role |
|---:|---|---:|---:|---:|---|
| 33051 | **CHINASAT 9** | 14 / 16 | 0.015° | 35,768.0 km | China Satcom — operational broadcast comsat |
| 33154 | **BADR 6** | 12 / 16 | 0.063° | 35,768.3 km | Arabsat — operational comsat |
| 29526 | **ARABSAT 4B (BADR-4)** | 11 / 17 | 0.054° | 35,767.6 km | Arabsat — operational comsat |
| 39017 | **CHINASAT 12** | 10 / 11 | 0.018° | 35,774.4 km | China Satcom — operational comsat |
| 29349 | **KOREASAT 5** | 10 / 17 | 0.019° | 35,780.1 km | KT SAT — operational civil/military comsat |

<!-- src: cadence-s1-geo-20260922.json d1Best.topCarriers -->

All five are operational geostationary communications satellites in commercial
or government fleets, at eccentricity 1.6e-4 to 4.4e-4 <!-- src: same -->, and
all five are objects that must be north-south kept to stay in a latitude box.
The full 56 are of the same kind — Arabsat/Badr, Koreasat, Intelsat, Turksat,
Thaicom, Syracuse, Yamal, Palapa, Apstar, Nimiq, Telstar, DirecTV, Anik,
Express, Hellas-Sat, EDRS-C — with **no ETALON-class object among them**: there
is no propulsion-free body in the carrier list. Five carriers sit at
inclinations above 0.2° (AMC-2 0.265°, ST 1 0.744°, ASTRA 2B 1.964°, INMARSAT
4-F1 2.786°, TURKSAT 1C 2.837°) and contribute one window each; those are
inclined-orbit or late-life objects and are the weakest carriers, not the line's
backbone. Operator attribution here is from the catalogue's own object names,
which is what `tools/cadence_analyze.operator_family` matches on; no external
registry was consulted and none of these names was audited against one.

### 3.7 The band-top shoulder is present in S1 too, and the control carries it harder

The strongest raw excess anywhere in the S1 GEO sweep is at 177–179 d, where the
GEO payload excess is 71.99x — and the **GEO passive control is 199.84x**, with
a core half-width of ±15 to ±18 d
<!-- src: cadence-s1-geo-20260922.json strongestGeoPayloadExcesses -->. A feature
thirty days wide that the control carries three times harder is the band's
shoulder, exactly as prereg §4(b) diagnosed for the primary and as s1s2-prereg
3.2 said the near-minimum inclination V-shape would produce. D1 clauses 2 and 3
reject it, which is what they are for. In the pooled S1 sweep the whole top of
the table is this shoulder: 189.00 d at 10.92x payload against 16.30x passive,
180.00 d at 9.49x against 16.89x, 171.25 d at 8.76x against 16.27x
<!-- src: cadence-s1-lines-20260922.json payloadOnlyLineSweep -->.

Note that the pooled sweep of `tools/cadence_lines.py` does **not** surface the
14-day line at all: its `localExpected >= 30` guard drops it, because pooled over
all payloads the local expectation at 14 d is only 19.6
<!-- src: cadence-s1-geo-20260922.json d1Best.pooledPayload.localExpected -->.
The GEO restriction registered in s1s2-prereg 5.2 is the reason the line is
visible, and that is a methodological finding in its own right.

## 4. S2 — eccentricity

### 4.1 The registered P4 corroboration failed

s1s2-prereg 4.3 registered, before the measurement, that the 14.00-day east-west
line the primary channel shows in 208 GEO payloads **should also appear in
eccentricity**, because the tangential burns that produce it change `e` by about
5.0e-5 each. Measured:

| | GEO payload | GEO passive | pooled passive | carriers |
|---|---:|---:|---:|---:|
| S2 at 14.00 d | **0.923** | 0.269 | 0.784 | 16 |

<!-- src: cadence-s2-geo-20260922.json targets["P2 east-west coincidence 14.0 d"] -->

21 core peaks against 22.75 expected — **there is no 14-day line in the
eccentricity channel.** Of the 1,248 GEO payload objects, **not one** has its
dominant period inside 13.89–14.11 d in S2, against 1.76% in S1
<!-- src: derived from cadence-s{1,2}-results-20260922.jsonl, GEO payload dominantPeriodDays -->.

**P4 failed.** As the registration required, this is reported as evidence
against, not explained away: the independent element that east-west
station-keeping must move does not show the east-west cadence. Three readings
are available and this pass does not choose between them — (i) the per-burn
`|Δe| ≈ 5e-5` is small against the annual SRP circle of 2.9e-4 that dominates a
GEO satellite's eccentricity and that the cubic cannot remove (§4.3), so the
line may simply be buried; (ii) operators actively manage the eccentricity
vector (sun-pointing perigee), which would suppress exactly this signature; or
(iii) the primary channel's east-west reading is wrong. **The registration
committed to reporting a P4 failure as evidence against reading (iii)'s
alternative being excluded, and it is reported that way.**

### 4.2 S2's own feature is at the synodic month, and D1's pass there is a boundary artifact

The strongest payload-only feature in the S2 GEO sweep is a broad plateau:

| Period | 28.75 | 29.00 | 29.25 | **29.50** | 29.75 | 30.00 | 30.25 |
|---|---:|---:|---:|---:|---:|---:|---:|
| GEO payload core peaks | 52 | 798 | 2,095 | **2,214** | 2,136 | 1,476 | 71 |
| GEO payload excess | 0.82 | 12.14 | 31.50 | **32.60** | 31.05 | 21.19 | 1.00 |
| GEO passive excess | 0.10 | 0.18 | 0.18 | **0.26** | 0.35 | 0.34 | 0.42 |

<!-- src: recomputed from s1s2-shard{0,1}.npz with tools/cadence_lines.local_excess on the GEO masks; the 29.50 and 29.00 rows also appear in cadence-s2-geo-20260922.json strongestGeoPayloadExcesses and d1Best -->

**The feature is centred at 29.50 d, which is 0.06 core half-widths from the
synodic month at 29.5306 d** — i.e. on it
<!-- src: cadence-s2-geo-20260922.json strongestGeoPayloadExcesses[0].separation -->.
D1 clause 3 therefore fails at the centre, correctly.

The computed D1 verdict for S2 nevertheless reads **`D1 MET` at 29.00 d**
(12.14x payload, 0.18x control, 321 carriers, separation 1.14 core half-widths)
<!-- src: cadence-s2-geo-20260922.json d1Verdict, d1Best -->. **The registration
is binding and that verdict is reported as computed — and the measurement in the
table above says plainly what it is: 29.00 d is the shoulder of the 29.50-day
plateau, and it passes clause 3 only because the clause tests the candidate's own
period rather than the parent feature's centroid.** That is a defect in D1 as
registered. It is named here, not patched, and **no north-south or operational
claim is made for S2 on this pass.** A future registration should evaluate the
separation test at the feature's centroid.

Two further reasons not to read 29.5 d as operational, both measured:

- the GEO **passive** control is 0.26x at 29.5 d but **15.60x and 17.37x at the
  anomalistic and sidereal months** (27.55 and 27.32 d)
  <!-- src: cadence-s2-geo-20260922.json targets -->, while the GEO payload is
  1.06x and 1.08x there. The two classes carry *different* lunar terms, which is
  a compositional statement about where each class's peaks sit, not evidence that
  one of the terms is propulsive;
- the GEO passive population's peaks pile at the band top (§4.3), so its local
  background near 29.5 d is thin — 10.9 expected peaks — and its silence there
  has correspondingly little weight, the same caveat as §3.3.

The primary report's §5.5 set the precedent and it is followed: **the 29.5-day
eccentricity feature is reported as unexplained rather than assigned a plausible
cause.**

### 4.3 The registered SRP shoulder is exactly where the registration put it

s1s2-prereg 4.1 predicted in advance that S2's band top would be
shoulder-dominated, because the solar-radiation-pressure eccentricity circle has
a period of 365.25 d — out of the searched band — but completes **2.96 cycles in
a 1080-day window**, which a cubic of `W/3 = 360 d` resolution cannot remove
<!-- src: cadence-s2-geo-20260922.json derivations.srpCyclesPerWindow, srpPeriodDays -->.
Measured: 196–198 d carries 25.37x in GEO payloads and **22.54x in the GEO
passive control**, with a core half-width above ±21 d
<!-- src: cadence-s2-geo-20260922.json strongestGeoPayloadExcesses -->; in the
pooled sweep, 199.75 d is 10.78x payload against 5.72x passive
<!-- src: cadence-s2-lines-20260922.json payloadOnlyLineSweep -->. **23.0% of the
S2 payload dominant periods and 15.5% of the passive ones land in the top bin
205–220 d**
<!-- src: cadence-s2-lines-20260922.json profile.{payload,passive}.periodHistogramShare -->.
The prediction was registered before the number and the number matched it.

## 5. E4 — descriptive distributions, significance not required

Because no object reached BH significance in either channel, the registered E4
table of *significant* cadences is empty in every regime and operator family
<!-- src: cadence-s{1,2}-results-20260922-receipt.json E4_byRegime, E4_byOperator -->.
What follows is the distribution of each object's dominant period regardless of
significance — descriptive, and labelled as such.

| | S1 payload | S1 passive | S2 payload | S2 passive |
|---|---:|---:|---:|---:|
| Dominant period p25 / p50 / p75 | 79.9 / 111.2 / 176.8 d | 130.0 / 176.8 / 189.2 d | 99.0 / 133.2 / 182.8 d | 124.0 / 136.6 / 189.2 d |
| Fraction with dominant period < 30 d | **0.77%** | 0.39% | **4.69%** | 1.84% |
| Max-over-window statistic p50 / p90 | 0.345 / 0.805 | 0.448 / 0.760 | 0.177 / 0.969 | 0.782 / 0.973 |

<!-- src: derived from cadence-s{1,2}-results-20260922.jsonl -->

Restricted to the GEO regime <!-- src: same, regime == "GEO" -->:

| | S1 GEO payload | S1 GEO passive | S2 GEO payload | S2 GEO passive |
|---|---:|---:|---:|---:|
| n | 1,248 | 331 | 1,248 | 331 |
| Dominant period p25 / p50 / p75 | 176.8 / 182.8 / 182.8 d | 176.8 / 182.8 / 182.8 d | 65.3 / 182.8 / 203.4 d | 140.1 / 189.2 / 203.4 d |
| Fraction < 30 d | **3.77%** | **0.00%** | **23.64%** | 7.25% |
| Fraction with dominant period in 13.89–14.11 d | **1.76%** | 0.00% | **0.00%** | 0.00% |

In S1 the GEO passive control has **no** object whose dominant period is under
30 days, against 3.77% of GEO payloads — the cleanest class separation anywhere
in this pass, and it is descriptive, carries no p-value, and is not a Gate B
substitute.

In S2, Inmarsat is the one operator family whose GEO median dominant period sits
in the lunar band at all (29.58 d, 61.1% under 30 d, n = 18)
<!-- src: derived from cadence-s2-results-20260922.jsonl, GEO payload rows by operator -->,
which is the 29.5-day feature of §4.2 and inherits its caveat entirely.

## 6. The registered resolution confound — measured, and it moved nothing

s1s2-prereg 6 registered in advance that a *controlled* GEO payload holds
inclination inside a deadband and so spans far fewer archive quanta per window
than the uncontrolled object it is compared with, and required both a
diagnostic and a sensitivity re-analysis.

**The asymmetry is real.** Median raw window range, in archive quanta
<!-- src: cadence-s1-results-20260922-receipt.json levelsByClass -->:

| S1 (1e-4 deg quanta) | p10 | p50 | p90 |
|---|---:|---:|---:|
| GEO **payload** | **629** | 11,778 | 20,820 |
| GEO **passive** | **8,339** | 16,852 | 26,074 |

At the tenth percentile the controlled class has **13x fewer** distinct
inclination values to work with than its control. That is the predicted,
directional, class-asymmetric effect, measured rather than assumed.

**It moved nothing.** No object in either class or any regime has a median
window range below 10 quanta — `fractionUnder10` is 0.0000 everywhere, in both
channels <!-- src: cadence-s{1,2}-results-20260922-receipt.json levelsByClass -->.
The pre-registered sensitivity re-analysis at `levels >= 10` returns the
identical population (316,028 windows, 7,884 payload objects, 5,485 audit
objects) and the identical numbers: BH 0/0, window-level payload 5.238% against
audit 7.311% in S1 and 8.168% against 9.389% in S2
<!-- src: cadence-s{1,2}-sensitivity-levels10-20260922-receipt.json, produced by tools/cadence_analyze.py --min-levels 10 -->.
The registered screen (prereg 5.3(4)) was not changed and rejected no window.

## 7. Blind spots — which are now measured, and which are not

The registered list of s1s2-prereg 7 and prereg 9, with what this pass can say.

1. **The window set is the primary channel's** — CONFIRMED and unquantified in
   cost. 47,777 + 13,625 + 6,205 windows were rejected on mean-motion
   admissibility and were never examined in inclination or eccentricity, even
   where those channels are well sampled. **How many of those the secondaries
   could have used is not known and was not measured.**
2. **float32 inclination storage** — PROVED HARMLESS, not merely argued: float32
   spacing at 180° is 1.53e-5 deg, below the archive's own 1e-4 deg quantum
   everywhere in the range <!-- src: tests/test_orbit_cadence_s1s2.py Float32Storage -->.
3. **The cubic is adequate for the secular lunisolar drift** — DERIVED AND
   TESTED, not assumed: least-squares bound 4.55e-6 deg, Taylor remainder
   2.04e-5 deg, both below the 1e-4 deg quantum
   <!-- src: cadence-s1-geo-20260922.json derivations.cubicDetrendAdequacy -->,
   with an end-to-end test that injects the Laplace-plane drift plus a ±0.05°
   north-south sawtooth and recovers the sawtooth period unchanged
   <!-- src: tests/test_orbit_cadence_s1s2.py CubicDetrendAdequacy -->.
4. **The same-regime GEO passive control is thin** — MEASURED: 331 objects,
   5,579 windows, and a local expectation below one window at 14 d (§3.3). This
   is the most important limitation of the D1 verdict and was **not** anticipated
   by the registration, which assumed a same-regime control would be strictly
   better than a pooled one. It is better in kind and much weaker in weight, and
   both were needed.
5. **D1 clause 3 tests the candidate's period, not the parent feature's
   centroid** — a registration defect, exposed by S2 (§4.2), named not patched.
6. **The fit-correlation alternative to the S1 line is not excluded** (§3.5).
   Only a manoeuvre-aware re-fit of the element history could settle it, and this
   track runs no detector (prereg 2).
7. **The window-level threshold does not transfer**, by 7.3x in S1 and 9.4x in
   S2 — the same clustered-estimator omission the primary measured, now measured
   in two more channels.
8. **The two classes occupy different eras** (prereg 6.4) — untested here, for
   the same reason as the primary: nothing was detected to stratify by year.
9. **Anything faster than 2 days, and continuous low thrust, remain invisible**
   by construction (prereg 9.1, 9.2). Unchanged.
10. **`object_type` is taken from the catalogue and is not audited.** The carrier
    list of §3.6 was checked by name against known operators, which is not the
    same as auditing the whole class label.

## 8. What prereg 9.3's blind spot now says

Prereg 9.3 recorded, before anything was measured, that "north-south GEO
station-keeping does not appear in the primary channel… a GEO satellite
returning `none` on the primary has not been shown to be un-kept." That blind
spot is now **partially closed**: the north-south channel does carry a rhythm,
it is visible, it is at 14.0 days, and it is carried by 56 named satellites that
the primary channel is silent about for 17 of them. The registered per-object
test still returns `none` for every one of them — a `none` in this track still
means "no periodicity above the passive-calibrated threshold on this channel",
never "does not station-keep".

## 9. Reproduction

```
gpu-run --estimate-mib 1800 --class standard --card N -- \
  .venv-gpu/bin/python tools/cadence_measure.py --artifacts ~/t3-cadence/full \
     --out ~/t3-cadence/full/s1s2-shardN.npz --shard N --shards 2 \
     --channels inclination,eccentricity
tools/cadence_analyze.py  --artifacts ~/t3-cadence/full --shards ... \
     --out docs/cadence-s1-results-20260922 --channel inclination
tools/cadence_analyze.py  ... --channel inclination --min-levels 10     # s1s2-prereg 6.3
tools/cadence_lines.py    ... --channel inclination --out docs/cadence-s1-lines-20260922.json
tools/cadence_s1s2_geo.py ... --channel inclination --out docs/cadence-s1-geo-20260922.json
```
(and the same four with `--channel eccentricity` into the `s2` stems.)

Offline tests: `tests/test_orbit_cadence_s1s2.py`, 41 tests, including the
derivations of s1s2-prereg 3 and 4 and the end-to-end multi-channel measurement
path on NumPy. The orbit suite runs **722 tests and is green**
<!-- src: .venv-gpu/bin/python -m unittest discover -s tests -p 'test_orbit*.py', 2026-09-22 -->,
against the 681-test baseline this pass inherited.

## Commit references

- `ffe2242` — the S1/S2 supplementary pre-registration, committed **alone,
  before any S1 or S2 number existed**. Its git history is the timestamp that
  makes this report's discipline checkable.
- `1a51afe` — the T3 pre-registration, committed alone before any T3 number
  existed; binding in every particular here.
- `1ac5050` — the T3 implementation, including the three-channel extractor and
  the per-channel quantum table this pass relies on.
- `da957ba` — the primary-channel results, whose §8 recorded S1 and S2 as
  **unexercised** in those words, and whose §5.3 and §5.4 set this pass's
  headline question and its same-regime-control requirement.
- `ec89303` — the research-programme runbook that assigns T3.
