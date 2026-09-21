# Perigee-speed re-pricing of the tangential delta-v channel — measured

Measured 2026-09-21 UTC on bigmem's GPU through the broker. Track T2 of
`docs/research-program-runbook-20260921.md`. Registered **before any number
below existed** in `docs/repricing-preregistration-20260921.md`, committed
alone at `62f98d3`; this document is the result the registration binds.

Analysis re-run, **not a production change**. No production pricing, published
artifact, site number or label gate was touched.

## The verdict, stated first

Re-pricing the tangential channel at perigee speed — the cheapest burn point,
derived in the registration §1 from vis-viva and cross-checked against the
Gauss variational equation — lowers the cohort's summed detected delta-v by
**5.62%** and its integrated propellant by **3.23%** <!-- src: docs/repricing-20260921-receipt.json, perEvent.totalCircularMps 126046.89865679 vs totalPerigeeMps 118962.50305945; arms.circular.totalBurnedKgLowerBound 130740.9399196 vs arms.perigee.totalBurnedKgLowerBound 126517.80084019 -->.

It does **not** produce anything like the 2.53x reduction the limitations
table of `docs/paper-a-draft-20260921.md` implies for transfer-orbit
eccentricity, and the reason is a measurement this track did not anticipate:
**on exactly the eccentric intervals where the factor is large, the tangential
channel stops being the binding in-plane term.** The pipeline charges the
largest of the three in-plane channels, and on an apogee kick the eccentricity
channel — which is not re-priced, and which already charges *less* than its
own infimum — is almost the same size as the tangential one. Drop the
tangential channel by a factor of 2.5 and the eccentricity channel simply takes
over. **115 of the 170 events at eccentricity above 0.5 are re-priced to
exactly the same total** <!-- src: computed from /tmp/t2-repricing-20260921/events.jsonl.gz: 170 events with repricing.eccentricity > 0.5, 115 with totalPerigeeMps == totalCircularMps -->.

The station-keeping anchor that carries Paper A §4.1 moves by **−0.033%
relative** — 1.809394% of the folklore budget to 1.808803% <!-- src: docs/repricing-20260921-receipt.json, arms.circular.folkloreExplainedFraction.median 0.01809394 vs arms.perigee 0.01808803 -->, well inside the
registration's "less than 0.1% relative" prediction, and both round to the
1.81% already published.

Every registered directional prediction held: no object's cumulative delta-v
rose, no anchor rose, and every per-event ratio is in (0, 1] <!-- src: docs/repricing-20260921.jsonl, max perigeeOverCircularDeltaV = 1.0 to 1e-12; docs/repricing-20260921-receipt.json, perEvent.perEventRatio.max 1.0 -->.

## The control arm, which had to pass before any of the above could be read

Registration §4 fixed the 2026-09-20 odometer's headline figures in advance and
required this re-run's circular arm to reproduce them. It does, on all eight
registered checks <!-- src: `tools/perigee_repricing.py compare --receipt docs/repricing-20260921-receipt.json`, "reproduced": true -->:

| Check | 2026-09-20 published | This re-run, circular arm |
| --- | ---: | ---: |
| Events detected | 5,341 | 5,341 |
| Events priced | 4,888 | 4,888 |
| Events excluded as not own propulsion | 4 | 4 |
| Folklore-anchored objects | 54 | 54 |
| Median folklore fraction | 1.81% | 1.809394% |
| Below 10% of the budget | 46 | 46 |
| Total integrated propellant | 130,740.9 kg | 130,740.9399 kg |
| Median burned fraction of launch mass | 5.98% | 5.983446% |

<!-- src: docs/fuel-odometer-20260920.md, "The verdict, stated first" and "Sanity anchor 1", against docs/repricing-20260921-receipt.json arms.circular -->

The per-signature event counts are identical too, to the flag <!-- src: docs/repricing-20260921-receipt.json, detectionReceipt.eventCounts vs docs/fuel-odometer-20260920-receipt.json detectionReceipt.eventCounts: geo-east-west-keeping 2556, along-track-raise 953, geo-north-south-keeping 792, unclassified-change 449, inclination-change 315, along-track-lower 250, geo-graveyard-raise 22, deorbit-lowering 4 -->. The detector's source hashes have moved since
2026-09-20 (`aee7ed8`, `c6a7761`, `066b205`, `061539e`), and none of those
changes moved a number, which is what the comment-and-diagnostics description
of them predicted.

## What was re-priced, and what the arithmetic is

From vis-viva, for an impulse at radius *r* (registration eq. 2):

    dv = mu * da / (2 a^2 v)

so the cost of a given semi-major-axis change is inversely proportional to the
speed at the burn point. At *r* = *a* this is the shipped `dv = n da / 2`; at
perigee, where `v_p = v_c sqrt((1+e)/(1-e))`, it is smaller by
`sqrt((1-e)/(1+e))`; at apogee it is larger by the reciprocal. Perigee and
apogee therefore **bracket** the cost of any single tangential impulse that
produced the observed `da`. All three arms re-form the event total with the
pipeline's own unchanged rule, `hypot(max(|tangential|, eccentricity,
apsidal), plane_change)`.

Not re-priced, per registration §2.4: the plane-change channel (already at
apogee, already the minimum over burn points), the eccentricity channel
(already below its own apsidal-tangential infimum), the apse-line channel
(already exact), the combination rule, and every detection decision.

## Per-event: where the re-pricing bites and where it does not

| Quantity over all 5,341 detected events | Circular | Perigee | Apogee |
| --- | ---: | ---: | ---: |
| Summed delta-v, m/s | 126,046.90 | 118,962.50 | 184,982.01 |
| Ratio to circular | 1 | 0.94380 | 1.46757 |

<!-- src: docs/repricing-20260921-receipt.json, perEvent.totalCircularMps / totalPerigeeMps / totalApogeeMps -->

The distribution is extremely lopsided <!-- src: docs/repricing-20260921-receipt.json, perEvent.perEventRatio and perEvent.eccentricity -->:

| Per-event perigee/circular ratio | Value |
| --- | ---: |
| Minimum | 0.293893 |
| 25th percentile | 0.999691 |
| Median | 0.999861 |
| 75th percentile | 1.000000 |
| Events changed by more than 1% | 91 of 5,341 |
| Events unchanged to the last bit | 1,527 of 5,341 |

<!-- src: docs/repricing-20260921-receipt.json, perEvent.perEventRatio, perEvent.eventsWhereRepricingChangesTotalAboveOnePercent 91; unchanged count computed from /tmp/t2-repricing-20260921/events.jsonl.gz -->

Interval eccentricity has median 0.000275 and maximum 0.840988 over the
detected set, so most of the cohort's events sit where the factor is 0.9997
<!-- src: docs/repricing-20260921-receipt.json, perEvent.eccentricity.median 0.0002753, .max 0.840988 -->. Split at *e* = 0.01:

| Subset | Events | Summed circular m/s | Summed perigee m/s | Ratio |
| --- | ---: | ---: | ---: | ---: |
| *e* ≤ 0.01 (near-circular, the GEO ring) | 4,978 | 16,615.8 | 16,611.7 | 0.999754 |
| *e* > 0.01 | 363 | 109,431.1 | 102,350.8 | 0.9353 |
| *e* > 0.5 | 170 | 70,497.5 | 65,060.6 | 0.9229 |

<!-- src: computed from /tmp/t2-repricing-20260921/events.jsonl.gz repricing blocks, partitioned on repricing.eccentricity -->

### The finding the registration did not predict

The tangential channel is the binding in-plane term for 4,546 of 5,341 events,
and re-pricing removes it from that role for 30 of them <!-- src: docs/repricing-20260921-receipt.json, perEvent.eventsWhereTangentialBindsInPlane 4546, perEvent.eventsWhereTangentialStopsBindingAfterRepricing 30 -->. On the transfer
burns the two in-plane channels are nearly equal before re-pricing, so the
re-priced total barely moves:

| Object | Date | *e* | Tangential | Eccentricity ch. | Plane | Total circ. | Total perigee |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| TURKSAT 3A | 2008-06-23 | 0.7270 | 1,480.4 | 1,467.6 | 55.3 | 1,481.4 | 1,468.6 |
| BSAT-3A | 2007-08-16 | 0.7271 | 1,472.5 | 1,469.4 | 53.1 | 1,473.5 | 1,470.4 |
| EUTELSAT 21B | 2012-11-16 | 0.7277 | 1,464.4 | 1,465.6 | 55.1 | 1,466.6 | 1,466.6 |
| EUTELSAT W2 | 1998-10-07 | 0.7293 | 1,380.1 | 1,417.7 | 192.0 | 1,430.7 | 1,430.7 |
| INTELSAT 17 | 2010-11-29 | 0.7293 | 1,311.4 | 1,375.2 | 53.5 | 1,376.3 | 1,376.3 |
| ASIASAT 5 | 2009-08-11 | 0.7232 | 727.6 | 921.2 | 1,187.0 | 1,502.5 | 1,502.5 |

<!-- src: /tmp/t2-repricing-20260921/events.jsonl.gz, per-event `repricing` blocks; m/s, largest circular totals in the cohort excluding the four events the odometer excludes as not own propulsion -->

That is the substantive correction this track makes to Paper A §4.1's
limitations paragraph: the 2.53x factor is the factor on **the tangential
channel**, not on the **event total**, and on the events where *e* is large
enough for it to matter the event total is usually being set by a different
channel.

### The largest movers

| Object | Date | *e* | Circular m/s | Perigee m/s | Change |
| --- | --- | ---: | ---: | ---: | ---: |
| INTELSAT 22 | 2012-03-25 | 0.5102 | 5,403.0 | 3,226.8 | −2,176.2 (x0.597) |
| ECHOSTAR 16 | 2012-11-21 | 0.2624 | 6,350.3 | 4,996.9 | −1,353.4 (x0.787) |
| TELSTAR 19V | 2018-07-26 | 0.6647 | 497.5 | 223.3 | −274.2 (x0.449) |
| TELSTAR 18V | 2018-09-12 | 0.6307 | 504.8 | 240.2 | −264.6 (x0.476) |
| VIASAT 2 | 2017-06-07 | 0.7626 | 384.0 | 141.0 | −243.1 (x0.367) |
| SPACEWAY 3 | 2007-08-22 | 0.7274 | 744.3 | 542.0 | −202.2 (x0.728) |

<!-- src: /tmp/t2-repricing-20260921/events.jsonl.gz, per-event `repricing` blocks, sorted by totalPerigeeMps - totalCircularMps -->

The first two are the odometer's own excluded events — an Intelsat 22 Briz-M
burn sequence and an EchoStar 16 element-set artefact — so they carry no fuel
<!-- src: docs/fuel-odometer-20260920.md, "The four events that are not this satellite's fuel" -->. They still change the picture for any use of the raw event
stream, which is why they are listed.

Worst-case **object** by cumulative delta-v: **SES-14**, 122.5 m/s to 75.8 m/s,
a ratio of 0.619; then ViaSat-2 at 0.706 and Spaceway-3 at 0.723 <!-- src: docs/repricing-20260921.jsonl, perigeeOverCircularDeltaV ascending: 43175 SES-14 0.61886, 42740 ViaSat-2 0.70579, 32018 Spaceway-3 0.72328 -->. 51 of
151 objects move by more than 0.1%; 5 do not move at all <!-- src: docs/repricing-20260921.jsonl, 51 rows with perigeeOverCircularDeltaV < 0.999 and 5 rows within 1e-9 of 1 -->.

## Per-object and the three Paper A anchors

| Arm | Total integrated propellant | Median burned fraction | Folklore median | Below 10% | Retiree median | Retiree max |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Circular (as published) | 130,740.94 kg | 5.9834% | 1.809394% | 46 of 54 | 0.8473% | 37.734% |
| **Perigee (primary)** | **126,517.80 kg** | **5.9790%** | **1.808803%** | **47 of 54** | **0.8468%** | **37.731%** |
| Apogee (bracket edge) | 161,420.20 kg | 3.3550% | 1.809987% | 46 of 54 | 0.8477% | 13.387% |

<!-- src: docs/repricing-20260921-receipt.json, arms.{circular,perigee,apogee}: totalBurnedKgLowerBound, medianBurnedFractionLowerBound, folkloreExplainedFraction.median, folkloreExplainedFraction.belowTenPercent, retireeBurnedFractionOfLaunchMass.median and .maxHighIspEdge -->

One object crosses the 10%-of-budget line: **Intelsat 603**, 13.04% to 9.23%
<!-- src: docs/repricing-20260921.jsonl, norad 20523, circular.explainedFractionOfFolkloreBudget 0.130412 vs perigee 0.092296 -->. Quartiles move in the sixth decimal: 0.761414%–7.112581% to
0.761386%–7.112472% <!-- src: docs/repricing-20260921-receipt.json, arms.circular.folkloreExplainedFraction.quartiles vs arms.perigee -->.

The apogee row's median burned fraction **falls** to 3.36% rather than rising,
and its retiree maximum falls from 37.7% to 13.4%. That is not a physical
result: at apogee pricing nine events cross the odometer's registered 2,500 m/s
own-propulsion ceiling instead of three, so rule 7 removes those objects'
transfer burns entirely <!-- src: docs/repricing-20260921-receipt.json, arms.apogee.eventsExcludedAsNotOwnPropulsion 10 with excludedEventReasons single-event-delta-v-above-ceiling 9, against arms.circular 4 and 3 -->. It is the registered rule-7
exclusion delta doing exactly what it was registered to expose, and it is the
reason the apogee bracket edge cannot be used unmodified as a comparison
denominator (see §"The bracket does not survive rule 7" below). The perigee arm
excludes the same four events as the circular arm, so the primary comparison is
like-for-like <!-- src: docs/repricing-20260921-receipt.json, arms.perigee.eventsExcludedAsNotOwnPropulsion 4, same reasons as arms.circular -->.

### Paper A §4.2's transfer anchor, re-priced

Twelve satellites carry both a detected transfer burn and a catalogued dry
mass. The recovered fraction of the catalogued launch-to-dry mass drop, under
both pricings:

| NORAD | Name | Circular | Perigee | Factor |
| --- | --- | ---: | ---: | ---: |
| 36131 | DirecTV-12 (AT&T T-12) | 107.5–109.0% | 105.5–107.0% | x0.9816 |
| 28378 | Anik F2 | 89.8–93.4% | 89.1–92.6% | x0.9917 |
| 32019 | BSAT-3a | 70.0–72.6% | 69.9–72.5% | x0.9983 |
| 33056 | Türksat 3A | 63.5–64.0% | 63.1–63.6% | x0.9932 |
| 37238 | Intelsat 17 | 63.3–64.3% | 63.3–64.3% | x1.0000 |
| 32018 | Spaceway-3 | 61.3–62.5% | 45.5–46.4% | x0.7420 |
| 41866 | GOES-16 | 58.3% | 57.5% | x0.9865 |
| 28446 | AMC-15 | 53.2% | 53.2% | x1.0000 |
| 43226 | GOES-17 | 50.0% | 49.7% | x0.9923 |
| 51850 | GOES-18 | 12.9% | 12.9% | x0.9993 |
| 20523 | Intelsat 603 | 5.5–5.8% | 5.5–5.7% | x0.9929 |
| 44186 | Arabsat-6A | 1.4% | 1.4% | x0.9984 |

<!-- src: docs/repricing-20260921.jsonl, per-object circular.raisingBurnVsCapacityRatioBand vs perigee.raisingBurnVsCapacityRatioBand -->

So the band §4.2 quotes as "50.0% to 107.5%" for nine objects becomes
**45.5% to 105.5%**, with one object (GOES-17, 49.7%) now just below 50 and
one (Spaceway-3) moving materially <!-- src: same table; the nine are the rows above 50% of capacity in the circular arm, and the low-edge figures are the band's low-Isp-independent lower edges -->. DirecTV-12 remains an overshoot at
105.5%, so the over-pricing of the tangential channel does **not** explain it
away <!-- src: docs/repricing-20260921.jsonl, norad 36131 -->.

## Registered secondaries

### The implausibility screen admits nothing new

5,388 intervals were priced. Two were rejected by the 2x-perigee-speed screen
on their circular price, and **neither would pass under perigee pricing**
<!-- src: docs/repricing-20260921-receipt.json, detectionReceipt.implausibilityScreen: intervalsPriced 5388, rejectedByCircularPrice 2, wouldPassUnderPerigeePrice 0 -->. The event set is therefore identical whichever price the screen is
evaluated on, for this cohort, and no detector question is entangled with this
pricing question here. That is a cohort-specific result and not a general one.

### The bracket does not survive rule 7

Registration §7 proposed comparing §4.2's transfer check against the apogee
bracket edge, on the physical ground that a geostationary transfer orbit is
circularised **at apogee**. That proposal does not survive contact with the
odometer's own rules: at apogee pricing the transfer burns of BSAT-3a, Türksat
3A and Intelsat 17 exceed 2,500 m/s and rule 7 removes them, so their apogee
"recovered fraction" is 0.0% rather than a larger number <!-- src: docs/repricing-20260921.jsonl, norads 32019, 33056, 37238: apogee.raisingBurnVsCapacityRatioBand [0.0, 0.0] -->. The bracket is
reported in the arms table and in the JSONL for every object, and it is **not**
used as a comparison denominator anywhere. Making it usable would mean
re-deriving rule 7's ceiling under the new pricing, which is a change this
registration did not authorise and this track does not make.

### The first-order screen found something larger than the burn point

Registration §1.4 registered an exact finite-impulse check, eq. (7), as a
screen to be reported and not acted on. Over the 4,146 events with a non-zero
tangential channel, the shipped first-order relation agrees with the exact
finite-impulse cost to a median of 5.4e-5 relative — and to a **maximum of
1.269**, i.e. it overstates the tangential cost by 127% on the largest
transfer events <!-- src: docs/repricing-20260921-receipt.json, perEvent.firstOrderRelativeErrorAtCircular: n 4146, median 5.413e-05, p75 0.00020573, max 1.26891595 -->:

| Object | Date | *e* | Tangential, first order | Exact at *r* = *a* | Exact at perigee |
| --- | --- | ---: | ---: | ---: | ---: |
| TURKSAT 3A | 2008-06-23 | 0.7270 | 1,480.4 | 779.7 | 334.4 |
| BSAT-3A | 2007-08-16 | 0.7271 | 1,472.5 | 777.3 | 333.2 |
| EUTELSAT 21B | 2012-11-16 | 0.7277 | 1,464.4 | 775.1 | 331.8 |
| INTELSAT 17 | 2010-11-29 | 0.7293 | 1,311.4 | 729.5 | 310.0 |
| ASIASAT 5 | 2009-08-11 | 0.7232 | 727.6 | 503.3 | 212.1 |

<!-- src: /tmp/t2-repricing-20260921/events.jsonl.gz, per-event repricing.tangentialCircularMps, .exactTangentialAtCircularMps, .exactTangentialAtPerigeeMps; m/s -->

This is a statement about the **order of the expansion**, not about the burn
point, and it is a larger effect than the burn point on exactly the events
Paper A §4.2 uses. It is reported here as the screen it was registered as. No
number in this document is computed from eq. (7), and this track makes no
change on the strength of it; it is named in Paper A §4.3 as the next
registered pricing item.

## The caveat, which has not changed

The pipeline sees two element sets and prices the cheapest impulse consistent
with the difference. It does not know where the burn happened.

* The **perigee** price is a lower-cost bound: no single tangential impulse
  producing that `da` could have cost less.
* The **circular** price is an upper-side convention, not a bound: it is what
  the burn would have cost at *r* = *a*, a radius the spacecraft actually
  passes through twice per orbit on any eccentric orbit.
* The truth is mixed and in between, per event, and unknowable from this data.

And, as registered: for the transfer intervals the burn point is known on
physical grounds to be **apogee**, where the same `da` costs `sqrt((1+e)/(1-e))`
times the circular price — 2.53x *more*, not less. Perigee pricing moves those
events away from their physically expected burn point. It is still the right
primary figure, because an infimum over burn points is what "cheapest impulse
consistent with the element change" has to mean, but §4.2's recovered fractions
fall for that reason and **not** because the measurement improved. The re-priced
odometer is a **valid but weaker** lower bound than the circular one.

## Reproduction and evidence

Registered at `62f98d3`, before any of the above existed. Analysis code:
`tools/perigee_repricing.py` (sha256 recorded in the receipt). It re-uses
`tools/fuel_odometer.py`'s pre-registered rules 1-8 **unmodified**, calling
`analyse_object` and `summarise` once per pricing arm over the same event set.

Frozen read-only archive snapshot
`/tmp/eol-study-20260920/archive.sqlite3`, sha256
`ffc4c4e521ca0c4eb78d5ec48039e8c9032e2f05183e5b3f09fe703bc5b734c3` — the same
snapshot the EOL study and the 2026-09-20 odometer used <!-- src: docs/repricing-20260921-receipt.json, detectionReceipt.archiveSnapshotSha256 -->. 1,257,404 rows re-detected
over 151 objects, kappa 32, self-history control basis.

```bash
nice -n 19 ionice -c 3 /home/sdegan/gpu-broker/gpu-run \
  --estimate-mib 320 --class standard --wait-seconds 3600 -- \
  .venv-gpu/bin/python tools/perigee_repricing.py detect \
  --archive /tmp/eol-study-20260920/archive.sqlite3 \
  --output /tmp/t2-repricing-20260921/events.jsonl.gz --gpu

.venv-gpu/bin/python tools/perigee_repricing.py integrate \
  --events /tmp/t2-repricing-20260921/events.jsonl.gz \
  --output-prefix docs/repricing-20260921

.venv-gpu/bin/python tools/perigee_repricing.py compare \
  --receipt docs/repricing-20260921-receipt.json
```

**Cost.** Broker grant `bafbebdf-4e36-48c1-a6cd-2803ccaaa618`, card 0, admitted
after 0.735 s, `CUDA_VISIBLE_DEVICES=GPU-e7724e1e-bdd0-0671-dd83-00b1177c7c0e`
(a UUID, never an index). **67.014 s wall / 50.099 s main-process CPU**, of
which the GPU arithmetic thread was 23.658 s wall / 16.773 s CPU over
1,081,715 intervals. Outcome `gpu`, **151 objects on the device, 0 fallbacks**.
Device pool peak 13,494,272 bytes, charged 281,929,728 bytes against a
335,544,320-byte ceiling <!-- src: docs/repricing-20260921-receipt.json, detectionReceipt.gpu and detectionReceipt.wallSeconds/cpuSeconds -->. One-off run; the broker ledger is its usage
record and no recurring lane was created, so `gpu-consumers.json` gains no row.

**A first invocation of the same command under the system `python3` was
admitted by the broker and then fell back to CPU** — `No module named 'cupy'`,
GPU outcome `cpu-fallback`, 0 of 151 objects on the device — and its output was
deleted rather than reported. The figures above are from the `.venv-gpu`
re-run. Recording it because a silent CPU fallback under a held GPU grant is
exactly the failure an execution-mode field exists to catch, and because
`executionMode: "gpu"` in the receipt records the **flag**, while
`gpu.outcome` records what actually happened; only the second is evidence.

Artifacts: [per-object JSONL](repricing-20260921.jsonl),
[receipt](repricing-20260921-receipt.json),
[pre-registration](repricing-preregistration-20260921.md),
[analysis code](../tools/perigee_repricing.py). The full per-event extraction
with every `repricing` block is `/tmp/t2-repricing-20260921/events.jsonl.gz`
(sha256 `6804c147596fdf2c78c1c6671a97f8037bcd33202dac785db85aac943d49e66f`), an
analysis working file rather than a retention commitment; preserve it before
cleaning `/tmp` if exact replay is needed.

**Registered predictions, all four held** <!-- src: registration §5 against docs/repricing-20260921.jsonl and docs/repricing-20260921-receipt.json -->:

1. Every re-priced event total ≤ its circular total — held, maximum per-event
   ratio 1.0.
2. The GEO station-keeping anchor moves by less than 0.1% relative — held, it
   moved 0.033%.
3. Transfer anchor falls by a factor between 1 and 2.53 — held, the largest
   per-object transfer fall is x0.742 (Spaceway-3), a factor of 1.35.
4. No anchor rises — held.

Nothing else in the repository was changed by this run. The production sweep,
the published site numbers and the label gate were not touched.
