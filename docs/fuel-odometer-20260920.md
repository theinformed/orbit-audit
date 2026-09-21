# The fuel odometer: what the manoeuvre ledger says each satellite has burned

Measured 2026-09-20 UTC. Catalogue × detected-manoeuvre ledger, integrated through the rocket equation. Every number below is a **lower bound** or an explicit band; nothing here is a fuel gauge.

## The verdict, stated first

For the **54** chemically-station-kept GEO satellites where the comparison is meaningful, the detected station-keeping Delta-v accounts for a median of **1.81%** of the ~50 m/s/yr north-south-keeping rule of thumb — **46 of 54** fall below 10%, and **none** exceed twice it. This is a statement about our detection recall, not about how much fuel these satellites burn. Routine station-keeping corrections are mostly below the detector's threshold, so the station-keeping odometer reads **far too low, by construction**.

The transfer phase is the opposite story. Where a satellite raised itself out of a transfer orbit, the detector catches the apogee burns cleanly: the largest genuine single burns in this cohort cluster at 1,430–1,502 m/s, exactly the textbook apogee kick out of a standard transfer orbit. **12** satellites both show a detected transfer burn and carry a catalogued dry mass. For **9** of them the integrated transfer burn recovers **50.0% to 107.5%** of the catalogued launch-to-dry mass drop; the remaining **3** recover only 1.4%–12.9%, which is what a transfer that the archive only partly watched looks like — their coverage and event lists are in the JSONL. The odometer works where the burns are large and fails where they are small, and that is the single most useful thing this run establishes.

Across the whole cohort the integrated burn is **at least 130,740.9 kg** of propellant over 151 satellites, median **5.98%** of launch mass. Every one of those sums crosses at least one archive coverage hole, so every one of them is an "at least".

## Directionality, because it changes what every number means

| Quantity | Direction | Why |
| --- | --- | --- |
| Detected Delta-v per event | Lower bound | The detector prices the cheapest manoeuvre consistent with the element change |
| Events detected | Lower bound | Sub-threshold, continuous and geometrically ambiguous burns are never counted |
| Propellant burned | Lower bound at BOTH ends of the Isp band | A lower-bound Delta-v cannot produce an upper-bound mass; the band is Isp uncertainty only |
| Propellant remaining (21 objects with dry mass) | Upper bound | Capacity minus a lower-bound burn; quote only the high-Isp edge |
| Remaining fraction for the other 130 | Not computed | No dry mass, so no capacity, so no remaining-fraction claim is made |

An Isp band is **not** an error bar on the fuel. A satellite whose catalogue entry is unresolved between a 210 s monopropellant and a 615 s arcjet gets both integrations and a flag; the midpoint of that band is not knowledge and is never reported as one.

## Cohort and detection

| Stage | Count |
| --- | --- |
| Catalogue objects (`data/propulsion-catalog-v1.json`) | 159 |
| Objects carrying a NORAD id — the detection cohort | 151 |
| Archive rows re-detected for that cohort | 1,257,404 |
| Objects with no archive rows at all | 0 |
| Events detected (all signatures) | 5,341 |
| Propulsive events priced | 4,888 |
| Events excluded as not the satellite’s own propulsion | 4 |
| Objects with at least one coverage hole | 151 |
| Objects with no propulsive event at all | 5 |

Detection re-ran the current post-56eef64 detector over the whole history of each catalogued NORAD, cohort-only, on the frozen read-only archive snapshot the EOL study also used. No published artifact was read: the published event list caps at 1,500 events catalogue-wide. Detection ran on CPU at nice 19 — 151 objects cost 118.4 s wall and 103.3 s CPU, so no GPU slot was taken.

| Signature | Events |
| --- | --- |
| geo-east-west-keeping | 2,556 |
| along-track-raise | 953 |
| geo-north-south-keeping | 792 |
| unclassified-change | 449 |
| inclination-change | 315 |
| along-track-lower | 250 |
| geo-graveyard-raise | 22 |
| deorbit-lowering | 4 |


### The four events that are not this satellite’s fuel

| NORAD | Name | Launch | Event | Signature | Δv m/s | Perigee km | Apogee km | Incl ° | Excluded because |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 39008 | EchoStar 16 | 2012-11-20 | 2012-11-21T09:58:29 | inclination-change | 6,350.3 | 265.6 | 4,991.8 | 50.32 | single-event-delta-v-above-ceiling |
| 28628 | Inmarsat-4 F1 | 2005-03-11 | 2005-03-29T00:08:00 | geo-north-south-keeping | 2,621.6 | 35,574.6 | 36,003.0 | 3.00 | single-event-delta-v-above-ceiling |
| 38098 | Intelsat 22 | 2012-03-25 | 2012-03-25T19:40:50 | inclination-change | 5,403.0 | 363.9 | 14,407.8 | 50.77 | single-event-delta-v-above-ceiling |
| 43611 | Telstar 18V | 2018-09-10 | 2018-09-07T10:20:56 | inclination-change | 9,700.9 | 839.4 | 857.9 | 98.81 | starts-before-catalogued-launch-date |

These are visible in the data, not inferred: a 9,700 m/s "manoeuvre" three days before launch between an 840 km sun-synchronous orbit and a transfer orbit is a mis-associated element set; a 5,400 m/s step out of a 364 × 14,408 km 50.8° orbit on launch day is a Briz-M burn sequence. The cohort’s largest genuine satellite burn is 1,502 m/s, so the 2,500 m/s ceiling sits in a clean gap. Without this rule **4** objects would integrate to more propellant than any satellite in this catalogue carries (the catalogue’s own maximum propellant fraction is **60.8%** of launch mass, from its 21 dry-mass rows). With it, **0** exceed that ceiling. Every object’s unfiltered integration is still published in the JSONL as `withoutCeiling`.

## Sanity anchor 1 — station-keeping against the 50 m/s/yr rule of thumb

| Statistic | Value |
| --- | --- |
| Objects anchored (GEO, chemical station-keeping, observed exposure) | 54 |
| Median fraction of the folklore budget explained | 1.81% |
| Quartiles | 0.76–7.11 % |
| Range | 0.00–68.98 % |
| Below 10% of the folklore budget | 46 |
| Above twice the folklore budget | 0 |

Observed years are **gap-aware**: they sum observed interval days from the end of the 18-month station-acquisition window, never the calendar span across a hole. The 84 electrically station-kept satellites are excluded from this anchor entirely — a continuous low-thrust burn produces no step for a step detector to find, so their station-keeping odometer is not merely low, it is structurally blind. Cross-reference the drift lane.

The eight objects that come closest to the rule of thumb:

| NORAD | Name | SK Δv m/s (≥) | Observed station yr | Δv/yr m/s (≥) | Folklore budget explained |
| --- | --- | --- | --- | --- | --- |
| 37775 | Astra 1N | 414.1 | 12.01 | 34.49 | 69.0% |
| 41029 | Arabsat 6B (Badr-7) | 89.9 | 8.56 | 10.50 | 21.0% |
| 41310 | Eutelsat 9B | 74.1 | 8.31 | 8.92 | 17.8% |
| 39617 | Astra 5B | 68.6 | 10.20 | 6.73 | 13.5% |
| 41729 | JCSAT-16 | 48.7 | 7.44 | 6.55 | 13.1% |
| 20523 | Intelsat 603 | 140.7 | 21.57 | 6.52 | 13.0% |
| 40364 | Astra 2G | 50.7 | 9.47 | 5.35 | 10.7% |
| 38778 | Astra 2F | 61.1 | 11.49 | 5.32 | 10.6% |


## Sanity anchor 2 — the transfer burn against catalogued mass

A catalogued "dry mass" for a GEO communications satellite is very often the beginning-of-life mass **in GEO**, after the apogee burn, rather than a true structural dry mass. Where that is what the number means, the launch-to-dry difference is the transfer propellant, and the ratio below should approach 1. This is the only direct, per-object check the odometer has.

| NORAD | Name | Launch kg | Dry kg | Capacity kg | Detected transfer burn kg | Ratio to capacity | Catalogue confidence |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 36131 | DirecTV-12 (AT&T T-12) | 6,060 | 3,556 | 2,504 | 2,690.9–2,729.1 | 107.5–109.0 % | datasheet |
| 28378 | Anik F2 | 5,950 | 3,805 | 2,145 | 1,927.2–2,002.7 | 89.8–93.4 % | datasheet |
| 32019 | BSAT-3a | 1,967 | 927 | 1,040 | 728.1–755.6 | 70.0–72.6 % | class-prior |
| 33056 | Türksat 3A | 3,110 | 1,272 | 1,838 | 1,167.4–1,176.0 | 63.5–64.0 % | class-prior |
| 37238 | Intelsat 17 | 5,540 | 2,393 | 3,147 | 1,991.7–2,022.3 | 63.3–64.3 % | class-prior |
| 32018 | Spaceway-3 | 6,075 | 3,832 | 2,243 | 1,375.1–1,401.2 | 61.3–62.5 % | datasheet |
| 41866 | GOES-16 | 5,192 | 2,857 | 2,335 | 1,360.5–1,360.5 | 58.3–58.3 % | class-prior |
| 28446 | AMC-15 | 4,021 | 2,050 | 1,971 | 1,049.5–1,049.5 | 53.2–53.2 % | class-prior |
| 43226 | GOES-17 | 5,192 | 2,857 | 2,335 | 1,168.4–1,168.4 | 50.0–50.0 % | class-prior |
| 51850 | GOES-18 | 5,192 | 2,857 | 2,335 | 302.2–302.2 | 12.9–12.9 % | class-prior |
| 20523 | Intelsat 603 | 4,215 | 1,910 | 2,305 | 127.3–133.4 | 5.5–5.8 % | class-prior |
| 44186 | Arabsat-6A | 6,465 | 3,520 | 2,945 | 39.9–41.8 | 1.4–1.4 % | class-prior |

The remaining 9 dry-mass objects show a zero transfer burn: their archive history begins after the transfer was over, or they never had one (the two LEO objects). A zero here is missing observation, not a satellite that reached orbit for free.

**One object integrates past its catalogued capacity.** DirecTV-12 (AT&T T-12) (NORAD 36131) burns at least 2,692.1 kg against a catalogued capacity of 2,504 kg, 107.5% of it. That is a single-digit percentage overshoot on a quantity built from a lower-bound Delta-v and a catalogued mass whose semantics are not guaranteed, which reads as close agreement rather than as a contradiction — but it is reported as an overshoot, not quietly clipped, and its `propellantRemainingUpperBoundKg` is therefore negative in the JSONL.

## Sanity anchor 3 — the sourced graveyard retirees

**16** catalogue objects carry a sourced graveyard-disposal record. Their burned fraction of launch mass has a median of **0.85%** and a maximum of **37.7%** at the high-burn edge of the Isp band — comfortably below any published propellant fraction, as it must be for a lower-bound odometer. This anchor can only ever falsify, never confirm: a retiree that integrated to more than its tank would have proved the method wrong, and none does.

| NORAD | Name | Retired | Launch kg | Burned kg (≥) | Of launch mass | Graveyard raises detected | Holes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 25491 | Eutelsat W2 | 2010 | 2,965 | 1,109.0–1,118.8 | 37.40–37.73 % | 0 | 423 |
| 20523 | Intelsat 603 | 2015 | 4,215 | 322.8–342.1 | 7.66–8.12 % | 0 | 595 |
| 25495 | Hot Bird 5 | — | 3,000 | 177.4–189.6 | 5.91–6.32 % | 0 | 371 |
| 20315 | Intelsat 602 | 2012 | 4,215 | 77.3–82.8 | 1.83–1.96 % | 0 | 625 |
| 23842 | Astra 1F | 2020 | 3,010 | 41.3–44.2 | 1.37–1.47 % | 0 | 317 |
| 23686 | Astra 1E | 2015 | 3,014 | 40.1–43.0 | 1.33–1.43 % | 1 | 305 |
| 27499 | Hot Bird 6 | 2016 | 3,905 | 39.7–42.5 | 1.02–1.09 % | 1 | 243 |
| 25237 | Hot Bird 4 | 2015 | 2,900 | 25.4–27.3 | 0.88–0.94 % | 0 | 307 |
| 23331 | Astra 1D | 2021 | 2,790 | 22.8–24.4 | 0.82–0.88 % | 0 | 405 |
| 21653 | Intelsat 605 | 2009 | 4,296 | 25.9–27.7 | 0.60–0.65 % | 0 | 621 |
| 22653 | Astra 1C | 2015 | 2,790 | 14.3–15.3 | 0.51–0.55 % | 1 | 420 |
| 22087 | Optus B1 | 2008 | 2,858 | 11.2–12.0 | 0.39–0.42 % | 0 | 563 |
| 28218 | Superbird A2 | — | 3,100 | 10.5–11.2 | 0.34–0.36 % | 0 | 279 |
| 21765 | Intelsat 601 | 2011 | 4,330 | 12.0–12.9 | 0.28–0.30 % | 0 | 633 |
| 23314 | Thaicom 2 | 2010 | 1,080 | 2.2–2.5 | 0.20–0.23 % | 0 | 427 |
| 21139 | Astra 1B | 2006 | 2,580 | 0.0–0.0 | 0.00–0.00 % | 0 | 438 |


## Isp unresolved: the bands the catalogue refuses to collapse

| NORAD | Name | Bus | Isp band | Burned kg (≥) | Band width kg | Events priced |
| --- | --- | --- | --- | --- | --- | --- |
| 37207 | BSAT-3b | A2100A | 210–615 s | 733.5–780.6 | 47.1 | 77 |
| 37776 | BSAT-3c | A2100A | 210–615 s | 58.9–96.4 | 37.5 | 117 |
| 38331 | JCSAT-13 | A2100AXS | 210–615 s | 1,248.0–1,356.9 | 108.9 | 41 |
| 41866 | GOES-16 | A2100A | 210–615 s | 1,372.0–1,393.9 | 21.9 | 13 |
| 43226 | GOES-17 | A2100A | 210–615 s | 1,311.5–1,573.3 | 261.8 | 31 |
| 44186 | Arabsat-6A | LM 2100 | 210–615 s | 87.7–180.8 | 93.1 | 137 |
| 51850 | GOES-18 | A2100A | 210–615 s | 310.7–326.9 | 16.2 | 11 |

The A2100 bus documents both hydrazine monopropellant motors and electric thrusters for orbit maintenance, and the catalogue deliberately refuses to guess which flew on a given unit. The band is wide because the knowledge is absent, and the width is the honest report of that absence. Which way it hurts depends on the Delta-v: a burn large enough to empty most of a tank empties it at either Isp, so the ABSOLUTE band narrows as Delta-v grows, while the RELATIVE band is worst where Delta-v is small. Arabsat-6A's burned mass is uncertain by a factor of 2.06; GOES-16's by 1.6%. A midpoint would hide both.

## Cross-prediction for the other two fuel routes

Every object carries a `crossPrediction` block for the quantum-drift (Route 2) and A/m-trend (Route 3) comparisons: predicted **fractional mass loss per year**, as a band, plus Δv per observed year and kg per year. All three are lower bounds, and each carries `atLeastBecauseOfCoverageHoles` — which is true for every object in this cohort.

| Statistic | Value |
| --- | --- |
| Objects with a fractional-mass-loss prediction | 151 |
| Median fractional mass loss per year (lower edge) | 0.7265% |
| Maximum | 17.320%  (SXM-7) |
| Minimum | 0.0000%  (Turksat 5A) |

A route that predicts a *larger* annual mass loss than this odometer is not contradicting it: this odometer misses burns. A route that predicts a *smaller* one is in genuine tension and should be examined.

## Limitations a reviewer will go for first

- Detection recall is the dominant error and it is one-sided. Station-keeping corrections at GEO are a few m/s; the detector needs a step that stands out against a fitted baseline. The 1.8% median folklore fraction is the size of that miss, measured.
- Electric propulsion is invisible to a step detector by construction. 84 of 151 catalogued satellites station-keep electrically. For those, only the transfer phase is measurable at all, and even that is only measurable when it was chemical.
- Coverage holes are universal here: every object crosses at least one, median 52 holes, median coverage fraction 0.87. Sums are "at least" sums and observed years are gap-aware, but a hole that swallowed a burn is invisible either way.
- Launch mass, dry mass and Isp are catalogue values, 90 of 151 in the detection cohort at class-prior confidence. The rocket equation propagates a wrong Isp linearly into mass; it propagates a wrong launch mass proportionally. The confidence field travels with every row for exactly this reason.
- "Dry mass" is semantically unstable across sources — structural dry mass for some objects, beginning-of-life mass in GEO for others. Sanity anchor 2 depends on which one a given row means, and the catalogue does not always say.
- The 2,500 m/s single-event ceiling and the 18-month raising window are declared rules, not measured constants. Both are published with the unfiltered alternative alongside, but a reviewer is entitled to ask what a 2,000 m/s or 3,000 m/s ceiling would do — for this cohort, nothing, because the gap between 1,502 and 2,622 m/s is empty.
- A per-event mass decrement assumes each detected interval is one burn. A detected interval that contains several burns, or one burn split across two intervals, still sums correctly in Delta-v but the sequential exponential is only first-order in that case.
- Nothing here is validated against an operator-published propellant figure. The anchors are internal consistency checks against catalogue mass and a rule of thumb, which is weaker than ground truth and should not be described as calibration.

## Per-object results

Burned mass is the lower bound at the high-Isp edge; the band is the Isp range. "Holes" is the number of archive coverage gaps inside the object’s observed span — any non-zero value makes that row’s cumulative burn an "at least". Years covered is gap-aware observed exposure.

| NORAD | Name | Catalogue confidence | Launch kg | Burned kg (≥) | Of launch mass | Band width kg | Years covered | Events priced | Holes | Remaining kg (≤) | Sanity flag |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 43611 | Telstar 18V | datasheet | 7,060 | 4,083.3 | 57.84–59.56 % | 122.0 | 7.0 | 11 | 28 | — | electric-station-keeping-step-detector-blind |
| 43562 | Telstar 19V | datasheet | 7,075 | 3,670.8 | 51.88–53.56 % | 118.5 | 6.9 | 7 | 46 | — | electric-station-keeping-step-detector-blind |
| 47240 | SXM-7 | datasheet | 7,000 | 3,421.5 | 48.88–49.62 % | 51.9 | 4.3 | 16 | 49 | — | electric-station-keeping-step-detector-blind |
| 39360 | Sirius FM-6 | datasheet | 6,003 | 3,021.0 | 50.32–51.00 % | 40.6 | 11.6 | 9 | 54 | — | electric-station-keeping-step-detector-blind |
| 39285 | Astra 2E | class-prior | 6,020 | 3,017.3 | 50.12–51.78 % | 99.9 | 12.1 | 83 | 21 | — | far-below-folklore-detection-gap |
| 33278 | Inmarsat-4 F3 | class-prior | 5,960 | 2,819.5 | 47.31–48.92 % | 96.4 | 16.0 | 14 | 130 | — | far-below-folklore-detection-gap |
| 36131 | DirecTV-12 (AT&T T-12) | datasheet | 6,060 | 2,692.1 | 44.42–45.06 % | 38.2 | 15.2 | 9 | 67 | -188.1 | electric-station-keeping-step-detector-blind |
| 43228 | Hispasat 30W-6 | datasheet | 6,092 | 2,661.7 | 43.69–45.24 % | 94.1 | 7.5 | 16 | 40 | — | electric-station-keeping-step-detector-blind |
| 39008 | EchoStar 16 | datasheet | 6,258 | 2,468.4 | 39.44–40.90 % | 91.0 | 12.6 | 5 | 45 | — | electric-station-keeping-step-detector-blind |
| 44479 | AMOS-17 | class-prior | 6,500 | 2,451.3 | 37.71–39.13 % | 91.9 | 6.2 | 22 | 21 | — | far-below-folklore-detection-gap |
| 39215 | Alphasat (Inmarsat-4A F4) | datasheet | 6,649 | 2,419.8 | 36.39–37.77 % | 91.7 | 12.0 | 9 | 39 | — | electric-station-keeping-step-detector-blind |
| 41382 | Eutelsat 65 West A | class-prior | 6,564 | 2,395.3 | 36.49–38.03 % | 101.1 | 9.7 | 52 | 11 | — | far-below-folklore-detection-gap |
| 44476 | Intelsat 39 | datasheet | 6,600 | 2,319.2 | 35.14–35.68 % | 36.0 | 6.1 | 9 | 33 | — | electric-station-keeping-step-detector-blind |
| 37775 | Astra 1N | class-prior | 5,350 | 2,316.4 | 43.30–45.02 % | 92.0 | 12.8 | 76 | 93 | — | within-order-of-folklore |
| 41904 | Star One D1 | class-prior | 6,433 | 2,306.9 | 35.86–37.33 % | 94.6 | 8.8 | 46 | 17 | — | far-below-folklore-detection-gap |
| 40364 | Astra 2G | class-prior | 6,020 | 2,254.7 | 37.45–38.89 % | 86.4 | 10.8 | 81 | 23 | — | within-order-of-folklore |
| 41794 | NBN Co 1B (Sky Muster 2) | datasheet | 6,440 | 2,247.8 | 34.90–36.24 % | 86.2 | 9.0 | 6 | 21 | — | electric-station-keeping-step-detector-blind |
| 40940 | NBN Co 1A (Sky Muster 1) | datasheet | 6,440 | 2,242.4 | 34.82–36.16 % | 86.0 | 10.1 | 4 | 16 | — | electric-station-keeping-step-detector-blind |
| 42942 | AsiaSat 9 | datasheet | 6,141 | 2,227.8 | 36.28–37.66 % | 84.7 | 6.9 | 13 | 113 | — | electric-station-keeping-step-detector-blind |
| 40333 | DirecTV 14 | datasheet | 6,300 | 2,183.3 | 34.66–35.99 % | 84.1 | 10.9 | 9 | 17 | — | electric-station-keeping-step-detector-blind |
| 41308 | Intelsat 29e | datasheet | 6,552 | 2,148.6 | 32.79–32.90 % | 7.1 | 9.8 | 10 | 18 | — | far-below-folklore-detection-gap |
| 28899 | Inmarsat-4 F2 | class-prior | 5,958 | 2,128.2 | 35.72–37.09 % | 81.3 | 16.7 | 8 | 269 | — | far-below-folklore-detection-gap |
| 40271 | Intelsat 30 | datasheet | 6,320 | 2,125.7 | 33.63–34.20 % | 35.5 | 10.0 | 12 | 107 | — | electric-station-keeping-step-detector-blind |
| 38749 | Intelsat 21 | datasheet | 5,984 | 2,104.0 | 35.16–35.20 % | 2.2 | 12.0 | 41 | 114 | — | far-below-folklore-detection-gap |
| 42692 | SGDC-1 | class-prior | 5,735 | 2,081.7 | 36.30–36.58 % | 15.9 | 8.7 | 7 | 4 | — | electric-station-keeping-step-detector-blind |
| 38740 | Intelsat 20 | datasheet | 6,094 | 2,081.1 | 34.15–34.70 % | 33.7 | 12.6 | 8 | 74 | — | electric-station-keeping-step-detector-blind |
| 41191 | Eutelsat 36C | class-prior | 5,700 | 2,020.2 | 35.44–36.80 % | 77.4 | 9.7 | 49 | 34 | — | far-below-folklore-detection-gap |
| 37238 | Intelsat 17 | class-prior | 5,540 | 2,013.9 | 36.35–36.95 % | 33.0 | 13.3 | 20 | 143 | 1,133.1 | far-below-folklore-detection-gap |
| 35942 | Amazonas 2 | class-prior | 5,465 | 1,966.6 | 35.98–37.38 % | 76.2 | 14.4 | 82 | 118 | — | far-below-folklore-detection-gap |
| 27445 | Galaxy 3C | datasheet | 4,810 | 1,939.1 | 40.31–40.91 % | 28.6 | 17.4 | 7 | 342 | — | electric-station-keeping-step-detector-blind |
| 28378 | Anik F2 | datasheet | 5,950 | 1,929.8 | 32.43–33.70 % | 75.5 | 16.2 | 8 | 234 | 215.2 | electric-station-keeping-step-detector-blind |
| 38992 | Eutelsat 21B | class-prior | 5,012 | 1,885.2 | 37.61–37.91 % | 14.7 | 12.3 | 42 | 76 | — | electric-station-keeping-step-detector-blind |
| 32729 | DirecTV-11 (AT&T T-11) | datasheet | 5,923 | 1,849.7 | 31.23–31.73 % | 29.5 | 15.9 | 8 | 135 | — | electric-station-keeping-step-detector-blind |
| 35696 | AsiaSat 5 | class-prior | 3,760 | 1,819.3 | 48.39–50.23 % | 69.2 | 15.6 | 117 | 73 | — | far-below-folklore-detection-gap |
| 27825 | Thuraya 2 | class-prior | 5,177 | 1,723.0 | 33.28–34.65 % | 70.8 | 19.9 | 31 | 220 | — | far-below-folklore-detection-gap |
| 42934 | Amazonas 5 | class-prior | 5,900 | 1,693.3 | 28.70–29.90 % | 70.8 | 7.4 | 7 | 53 | — | far-below-folklore-detection-gap |
| 26624 | Anik F1 | datasheet | 4,711 | 1,541.9 | 32.73–34.01 % | 60.1 | 18.2 | 19 | 340 | — | electric-station-keeping-step-detector-blind |
| 26761 | XM-1 (Roll) | datasheet | 4,682 | 1,528.4 | 32.64–33.92 % | 59.7 | 19.7 | 15 | 283 | — | electric-station-keeping-step-detector-blind |
| 28626 | XM-3 (Rhythm) | datasheet | 4,703 | 1,503.6 | 31.97–32.48 % | 23.9 | 16.7 | 9 | 248 | — | electric-station-keeping-step-detector-blind |
| 45245 | JCSAT-17 | class-prior | 5,857 | 1,487.8 | 25.40–26.55 % | 67.3 | 5.8 | 11 | 13 | — | electric-station-keeping-step-detector-blind |
| 41903 | JCSAT-15 | class-prior | 3,407 | 1,483.9 | 43.55–45.16 % | 54.8 | 8.8 | 4 | 25 | — | far-below-folklore-detection-gap |
| 26038 | Galaxy 11 | datasheet | 4,477 | 1,481.4 | 33.09–34.38 % | 57.6 | 19.3 | 57 | 392 | — | electric-station-keeping-step-detector-blind |
| 42740 | ViaSat-2 | class-prior | 6,418 | 1,465.7 | 22.84–23.80 % | 61.7 | 8.1 | 2 | 43 | — | electric-station-keeping-step-detector-blind |
| 41729 | JCSAT-16 | class-prior | 4,600 | 1,456.7 | 31.67–33.03 % | 62.7 | 8.9 | 43 | 46 | — | within-order-of-folklore |
| 32018 | Spaceway-3 | datasheet | 6,075 | 1,377.8 | 22.68–23.11 % | 26.2 | 16.1 | 33 | 167 | 865.1 | electric-station-keeping-step-detector-blind |
| 41866 | GOES-16 | class-prior | 5,192 | 1,372.0 | 26.42–26.85 % | 21.9 | 9.0 | 13 | 15 | 963.0 | electric-station-keeping-step-detector-blind |
| 42691 | Koreasat 7 | class-prior | 3,680 | 1,353.8 | 36.79–37.10 % | 11.5 | 8.5 | 96 | 14 | — | far-below-folklore-detection-gap |
| 43226 | GOES-17 | class-prior | 5,192 | 1,311.5 | 25.26–30.30 % | 261.8 | 7.7 | 31 | 11 | 1,023.5 | electric-station-keeping-step-detector-blind |
| 42951 | BSAT-4a | class-prior | 3,520 | 1,293.9 | 36.76–38.27 % | 53.4 | 7.8 | 52 | 26 | — | far-below-folklore-detection-gap |
| 48838 | SXM-8 | datasheet | 7,000 | 1,291.0 | 18.44–18.81 % | 25.9 | 3.8 | 7 | 57 | — | electric-station-keeping-step-detector-blind |
| 46112 | BSAT-4b | class-prior | 3,530 | 1,263.9 | 35.80–37.28 % | 52.0 | 5.1 | 30 | 28 | — | far-below-folklore-detection-gap |
| 33056 | Türksat 3A | class-prior | 3,110 | 1,254.7 | 40.34–40.80 % | 14.3 | 14.8 | 131 | 146 | 583.3 | electric-station-keeping-step-detector-blind |
| 26608 | Intelsat 1R (PAS-1R) | datasheet | 4,792 | 1,252.6 | 26.14–26.57 % | 20.8 | 15.9 | 21 | 413 | — | electric-station-keeping-step-detector-blind |
| 38331 | JCSAT-13 | class-prior | 4,528 | 1,248.0 | 27.56–29.97 % | 108.9 | 12.2 | 41 | 112 | — | electric-station-keeping-step-detector-blind |
| 43633 | Horizons-3e | class-prior | 6,441 | 1,185.0 | 18.40–19.22 % | 52.9 | 7.0 | 4 | 29 | — | far-below-folklore-detection-gap |
| 39617 | Astra 5B | class-prior | 5,724 | 1,145.4 | 20.01–20.91 % | 51.7 | 11.5 | 105 | 29 | — | within-order-of-folklore |
| 40874 | Intelsat 34 | datasheet | 3,300 | 1,134.6 | 34.38–34.93 % | 18.2 | 10.1 | 9 | 28 | — | electric-station-keeping-step-detector-blind |
| 26487 | Eutelsat W1 | class-prior | 3,250 | 1,126.9 | 34.67–36.02 % | 43.8 | 18.7 | 15 | 349 | — | electric-station-keeping-step-detector-blind |
| 25491 | Eutelsat W2 | datasheet | 2,965 | 1,109.0 | 37.40–37.73 % | 9.8 | 17.7 | 4 | 423 | — | electric-station-keeping-step-detector-blind |
| 28446 | AMC-15 | class-prior | 4,021 | 1,074.9 | 26.73–26.77 % | 1.3 | 18.2 | 41 | 196 | 896.1 | electric-station-keeping-step-detector-blind |
| 38342 | Nimiq 6 | class-prior | 4,500 | 1,071.9 | 23.82–24.93 % | 50.0 | 13.0 | 20 | 42 | — | far-below-folklore-detection-gap |
| 22930 | DirecTV 1 | datasheet | 2,860 | 1,068.5 | 37.36–37.99 % | 18.0 | 23.2 | 16 | 503 | — | far-below-folklore-detection-gap |
| 40107 | AsiaSat 8 | class-prior | 4,535 | 971.9 | 21.43–22.47 % | 47.0 | 11.3 | 31 | 18 | — | far-below-folklore-detection-gap |
| 28628 | Inmarsat-4 F1 | class-prior | 5,959 | 850.5 | 14.27–14.93 % | 39.4 | 18.2 | 15 | 194 | — | far-below-folklore-detection-gap |
| 28472 | AMC-16 | class-prior | 4,065 | 810.2 | 19.93–19.97 % | 1.8 | 18.1 | 28 | 201 | — | electric-station-keeping-step-detector-blind |
| 32019 | BSAT-3a | class-prior | 1,967 | 772.7 | 39.28–40.89 % | 31.5 | 14.7 | 38 | 196 | 267.3 | electric-station-keeping-step-detector-blind |
| 37207 | BSAT-3b | class-prior | 2,060 | 733.5 | 35.61–37.89 % | 47.1 | 14.1 | 77 | 69 | — | electric-station-keeping-step-detector-blind |
| 40141 | AsiaSat 6 | class-prior | 3,700 | 728.2 | 19.68–20.65 % | 35.7 | 10.9 | 44 | 37 | — | far-below-folklore-detection-gap |
| 29644 | AMC-18 | class-prior | 2,081 | 680.2 | 32.69–32.73 % | 1.0 | 17.0 | 46 | 147 | — | electric-station-keeping-step-detector-blind |
| 38778 | Astra 2F | class-prior | 5,968 | 621.6 | 10.42–10.94 % | 31.1 | 12.3 | 79 | 52 | — | within-order-of-folklore |
| 21222 | Anik E2 | class-prior | 2,977 | 607.9 | 20.42–21.35 % | 27.6 | 24.1 | 22 | 636 | — | electric-station-keeping-step-detector-blind |
| 42984 | Koreasat 5A | class-prior | 3,500 | 603.2 | 17.23–17.41 % | 6.1 | 8.1 | 64 | 8 | — | far-below-folklore-detection-gap |
| 41036 | Telstar 12 Vantage | class-prior | 4,900 | 550.0 | 11.23–11.74 % | 25.1 | 9.4 | 5 | 52 | — | far-below-folklore-detection-gap |
| 44307 | Yamal 601 | datasheet | 5,700 | 508.7 | 8.92–9.05 % | 7.0 | 5.9 | 12 | 54 | — | electric-station-keeping-step-detector-blind |
| 38098 | Intelsat 22 | datasheet | 6,199 | 366.3 | 5.91–5.95 % | 2.4 | 12.5 | 13 | 105 | — | far-below-folklore-detection-gap |
| 42818 | Intelsat 35e | datasheet | 6,761 | 335.1 | 4.96–5.09 % | 9.0 | 8.3 | 18 | 23 | — | far-below-folklore-detection-gap |
| 20523 | Intelsat 603 | class-prior | 4,215 | 322.8 | 7.66–8.12 % | 19.4 | 22.8 | 19 | 595 | 1,982.2 | within-order-of-folklore |
| 51850 | GOES-18 | class-prior | 5,192 | 310.7 | 5.98–6.30 % | 16.2 | 3.4 | 11 | 37 | 2,024.3 | electric-station-keeping-step-detector-blind |
| 41029 | Arabsat 6B (Badr-7) | class-prior | 5,798 | 194.5 | 3.35–3.59 % | 13.6 | 10.0 | 92 | 21 | — | within-order-of-folklore |
| 25495 | Hot Bird 5 | datasheet | 3,000 | 177.4 | 5.91–6.32 % | 12.3 | 19.1 | 8 | 371 | — | electric-station-keeping-step-detector-blind |
| 41310 | Eutelsat 9B | class-prior | 5,175 | 144.9 | 2.80–3.00 % | 10.2 | 9.8 | 65 | 17 | — | within-order-of-folklore |
| 36581 | Astra 3B | class-prior | 5,472 | 98.9 | 1.81–1.94 % | 7.0 | 13.1 | 114 | 121 | — | far-below-folklore-detection-gap |
| 40147 | Measat-3b | class-prior | 5,897 | 88.9 | 1.51–1.61 % | 6.3 | 11.1 | 49 | 24 | — | far-below-folklore-detection-gap |
| 44186 | Arabsat-6A | class-prior | 6,465 | 87.7 | 1.36–2.80 % | 93.1 | 6.4 | 137 | 31 | 2,857.3 | electric-station-keeping-step-detector-blind |
| 25994 | Terra | class-prior | 5,190 | 85.1 | 1.64–1.83 % | 10.0 | 25.6 | 122 | 7 | — | not-geo-folklore-does-not-apply |
| 28638 | Apstar-6 | class-prior | 4,680 | 79.7 | 1.70–1.82 % | 5.6 | 19.9 | 34 | 75 | — | electric-station-keeping-step-detector-blind |
| 20315 | Intelsat 602 | class-prior | 4,215 | 77.3 | 1.83–1.96 % | 5.5 | 20.3 | 8 | 625 | 2,227.7 | far-below-folklore-detection-gap |
| 29270 | Hotbird 13B | class-prior | 4,875 | 74.9 | 1.54–1.65 % | 5.3 | 15.4 | 80 | 178 | — | far-below-folklore-detection-gap |
| 28358 | Intelsat 10-02 | datasheet | 5,575 | 62.2 | 1.12–1.19 % | 4.1 | 17.0 | 2 | 281 | — | electric-station-keeping-step-detector-blind |
| 39084 | Landsat 8 | class-prior | 2,780 | 60.9 | 2.19–2.33 % | 3.9 | 12.5 | 110 | 11 | 1,207.1 | not-geo-folklore-does-not-apply |
| 41456 | Sentinel-1B | class-prior | 2,164 | 60.2 | 2.78–3.06 % | 6.0 | 9.5 | 131 | 14 | — | not-geo-folklore-does-not-apply |
| 37776 | BSAT-3c | class-prior | 2,910 | 58.9 | 2.02–3.31 % | 37.5 | 13.4 | 117 | 83 | — | electric-station-keeping-step-detector-blind |
| 36831 | Rascom-QAF 1R | class-prior | 3,050 | 55.4 | 1.81–1.94 % | 3.9 | 14.1 | 41 | 94 | — | electric-station-keeping-step-detector-blind |
| 36830 | Nilesat 201 | class-prior | 3,200 | 52.9 | 1.65–1.77 % | 3.7 | 14.1 | 29 | 64 | — | electric-station-keeping-step-detector-blind |
| 27424 | Aqua | class-prior | 2,934 | 52.1 | 1.78–1.98 % | 6.1 | 23.2 | 182 | 21 | — | not-geo-folklore-does-not-apply |
| 28376 | Aura | class-prior | 3,000 | 47.4 | 1.58–1.77 % | 5.6 | 21.3 | 217 | 15 | — | not-geo-folklore-does-not-apply |
| 35812 | Palapa-D | class-prior | 4,100 | 44.6 | 1.09–1.16 % | 3.2 | 14.2 | 15 | 166 | — | electric-station-keeping-step-detector-blind |
| 32404 | Thuraya 3 | class-prior | 5,177 | 44.1 | 0.85–0.91 % | 3.1 | 15.7 | 27 | 175 | — | far-below-folklore-detection-gap |
| 36745 | Arabsat 5A | class-prior | 4,939 | 43.7 | 0.88–0.95 % | 3.1 | 13.7 | 88 | 156 | — | far-below-folklore-detection-gap |
| 23842 | Astra 1F | datasheet | 3,010 | 41.3 | 1.37–1.47 % | 2.9 | 16.1 | 40 | 317 | — | electric-station-keeping-step-detector-blind |
| 23686 | Astra 1E | datasheet | 3,014 | 40.1 | 1.33–1.43 % | 2.8 | 15.9 | 15 | 305 | — | electric-station-keeping-step-detector-blind |
| 27499 | Hot Bird 6 | datasheet | 3,905 | 39.7 | 1.02–1.09 % | 2.8 | 15.3 | 15 | 243 | — | electric-station-keeping-step-detector-blind |
| 39773 | Eutelsat 3B (W7 heritage slot) | class-prior | 5,967 | 37.2 | 0.62–0.67 % | 2.7 | 11.5 | 20 | 16 | — | far-below-folklore-detection-gap |
| 37849 | Suomi NPP | class-prior | 2,200 | 35.6 | 1.62–1.81 % | 4.2 | 13.6 | 54 | 19 | 764.4 | not-geo-folklore-does-not-apply |
| 43175 | SES-14 | datasheet | 4,423 | 30.6 | 0.69–0.99 % | 13.4 | 7.4 | 6 | 47 | — | electric-station-keeping-step-detector-blind |
| 39163 | Eutelsat 7B | class-prior | 5,470 | 30.4 | 0.56–0.60 % | 2.2 | 12.4 | 22 | 28 | — | electric-station-keeping-step-detector-blind |
| 43488 | SES-12 | datasheet | 5,300 | 27.6 | 0.52–0.75 % | 12.1 | 7.2 | 7 | 39 | — | electric-station-keeping-step-detector-blind |
| 23754 | EchoStar 1 | datasheet | 3,287 | 27.0 | 0.82–0.88 % | 1.9 | 21.1 | 12 | 480 | — | far-below-folklore-detection-gap |
| 38356 | Intelsat 19 | class-prior | 5,600 | 26.6 | 0.47–0.49 % | 1.1 | 12.7 | 8 | 72 | — | far-below-folklore-detection-gap |
| 43437 | Sentinel-3B | class-prior | 1,150 | 26.5 | 2.30–2.54 % | 2.7 | 7.7 | 104 | 9 | — | not-geo-folklore-does-not-apply |
| 41335 | Sentinel-3A | class-prior | 1,150 | 26.4 | 2.30–2.53 % | 2.7 | 9.4 | 103 | 4 | — | not-geo-folklore-does-not-apply |
| 21653 | Intelsat 605 | class-prior | 4,296 | 25.9 | 0.60–0.65 % | 1.8 | 20.9 | 5 | 621 | 2,360.1 | far-below-folklore-detection-gap |
| 25237 | Hot Bird 4 | datasheet | 2,900 | 25.4 | 0.88–0.94 % | 1.8 | 16.3 | 6 | 307 | — | electric-station-keeping-step-detector-blind |
| 23331 | Astra 1D | datasheet | 2,790 | 22.8 | 0.82–0.88 % | 1.6 | 19.3 | 38 | 405 | — | electric-station-keeping-step-detector-blind |
| 43013 | NOAA-20 (JPSS-1) | class-prior | 2,540 | 22.4 | 0.88–0.94 % | 1.4 | 7.8 | 38 | 4 | — | not-geo-folklore-does-not-apply |
| 23305 | Intelsat 703 / NSS-703 | class-prior | 3,695 | 19.0 | 0.51–0.55 % | 1.4 | 19.9 | 9 | 500 | 2,226.0 | far-below-folklore-detection-gap |
| 22871 | Intelsat 701 | class-prior | 3,642 | 15.4 | 0.42–0.45 % | 1.1 | 21.7 | 6 | 540 | 2,176.6 | far-below-folklore-detection-gap |
| 22653 | Astra 1C | datasheet | 2,790 | 14.3 | 0.51–0.55 % | 1.0 | 16.9 | 5 | 420 | — | electric-station-keeping-step-detector-blind |
| 21765 | Intelsat 601 | class-prior | 4,330 | 12.0 | 0.28–0.30 % | 0.9 | 20.4 | 5 | 633 | 2,408.0 | far-below-folklore-detection-gap |
| 56370 | ViaSat-3 Americas (ViaSat-3 F1) | class-prior | 6,418 | 11.4 | 0.18–0.25 % | 4.5 | 2.3 | 19 | 38 | — | electric-station-keeping-step-detector-blind |
| 22087 | Optus B1 | datasheet | 2,858 | 11.2 | 0.39–0.42 % | 0.8 | 23.4 | 6 | 563 | — | far-below-folklore-detection-gap |
| 28218 | Superbird A2 | class-prior | 3,100 | 10.5 | 0.34–0.36 % | 0.7 | 17.6 | 7 | 279 | 1,612.5 | far-below-folklore-detection-gap |
| 42063 | Sentinel-2B | class-prior | 1,200 | 8.9 | 0.74–0.82 % | 0.9 | 8.7 | 41 | 9 | — | not-geo-folklore-does-not-apply |
| 41240 | Jason-3 | class-prior | 553 | 7.8 | 1.41–1.58 % | 0.9 | 9.8 | 59 | 8 | — | not-geo-folklore-does-not-apply |
| 37810 | Arabsat 5C | class-prior | 4,630 | 7.6 | 0.16–0.18 % | 0.5 | 12.7 | 40 | 118 | — | far-below-folklore-detection-gap |
| 40697 | Sentinel-2A | class-prior | 1,200 | 7.5 | 0.62–0.68 % | 0.8 | 10.4 | 43 | 6 | — | not-geo-folklore-does-not-apply |
| 41581 | Intelsat 31 | datasheet | 6,450 | 5.2 | 0.08–0.09 % | 0.3 | 8.4 | 2 | 88 | — | electric-station-keeping-step-detector-blind |
| 34710 | Eutelsat 10A | datasheet | 5,900 | 5.1 | 0.09–0.09 % | 0.3 | 14.8 | 38 | 131 | — | electric-station-keeping-step-detector-blind |
| 37258 | KA-SAT (Eutelsat KA-SAT 9A) | class-prior | 6,150 | 5.0 | 0.08–0.09 % | 0.4 | 14.2 | 1 | 57 | — | far-below-folklore-detection-gap |
| 41380 | SES-9 | datasheet | 5,330 | 4.4 | 0.08–0.08 % | 0.1 | 9.6 | 13 | 22 | — | electric-station-keeping-step-detector-blind |
| 53961 | SES-21 | datasheet | 1,700 | 4.3 | 0.25–0.26 % | 0.1 | 2.9 | 9 | 36 | — | electric-station-keeping-step-detector-blind |
| 53960 | SES-20 | datasheet | 1,500 | 3.5 | 0.23–0.24 % | 0.1 | 2.9 | 12 | 33 | — | electric-station-keeping-step-detector-blind |
| 37393 | Yahsat 1A (Al Yah 1) | datasheet | 5,965 | 3.1 | 0.05–0.06 % | 0.2 | 14.1 | 5 | 52 | — | electric-station-keeping-step-detector-blind |
| 43476 | GRACE-FO 1 | class-prior | 580 | 2.9 | 0.51–0.62 % | 0.7 | 7.6 | 11 | 7 | — | not-geo-folklore-does-not-apply |
| 39634 | Sentinel-1A | class-prior | 2,157 | 2.9 | 0.13–0.15 % | 0.3 | 11.6 | 20 | 10 | — | not-geo-folklore-does-not-apply |
| 43463 | Bangabandhu-1 | class-prior | 3,700 | 2.8 | 0.08–0.08 % | 0.2 | 7.5 | 44 | 13 | — | electric-station-keeping-step-detector-blind |
| 23314 | Thaicom 2 | class-prior | 1,080 | 2.2 | 0.20–0.23 % | 0.3 | 21.2 | 4 | 427 | — | far-below-folklore-detection-gap |
| 42741 | Eutelsat 172B | datasheet | 3,551 | 1.9 | 0.05–0.08 % | 0.8 | 8.2 | 5 | 25 | — | electric-station-keeping-step-detector-blind |
| 39022 | Yamal 402 | datasheet | 5,250 | 1.7 | 0.03–0.04 % | 0.1 | 12.2 | 5 | 71 | — | electric-station-keeping-step-detector-blind |
| 29520 | XM-4 (Blues) | datasheet | 5,193 | 1.6 | 0.03–0.03 % | 0.0 | 15.3 | 3 | 225 | — | electric-station-keeping-step-detector-blind |
| 37843 | ViaSat-1 | datasheet | 6,740 | 1.1 | 0.02–0.02 % | 0.1 | 13.1 | 1 | 73 | — | electric-station-keeping-step-detector-blind |
| 42709 | SES-15 | datasheet | 2,302 | 1.0 | 0.04–0.04 % | 0.0 | 8.1 | 4 | 48 | — | electric-station-keeping-step-detector-blind |
| 54755 | O3b mPOWER (F1, representative of 13-satellite constellation) | class-prior | 1,700 | 0.8 | 0.05–0.07 % | 0.3 | 2.8 | 2 | 28 | — | not-geo-folklore-does-not-apply |
| 38245 | Yahsat 1B (Al Yah 2) | datasheet | 6,100 | 0.5 | 0.01–0.01 % | 0.0 | 13.2 | 1 | 48 | — | electric-station-keeping-step-detector-blind |
| 40424 | ABS-3A | datasheet | 1,954 | 0.1 | 0.00–0.00 % | 0.0 | 10.1 | 1 | 43 | — | electric-station-keeping-step-detector-blind |
| 41588 | ABS-2A (MongolSat 1) | datasheet | 2,000 | 0.1 | 0.00–0.00 % | 0.0 | 8.9 | 1 | 42 | — | electric-station-keeping-step-detector-blind |
| 21139 | Astra 1B | class-prior | 2,580 | 0.0 | 0.00–0.00 % | 0.0 | 18.6 | 0 | 438 | — | electric-station-keeping-step-detector-blind |
| 40425 | Eutelsat 115 West B | datasheet | 2,205 | 0.0 | 0.00–0.00 % | 0.0 | 10.2 | 0 | 37 | — | electric-station-keeping-step-detector-blind |
| 41589 | Eutelsat 117 West B (Satmex 9) | datasheet | 1,963 | 0.0 | 0.00–0.00 % | 0.0 | 9.0 | 0 | 40 | — | electric-station-keeping-step-detector-blind |
| 44034 | Hellas-Sat 4 | class-prior | 6,495 | 0.0 | 0.00–0.00 % | 0.0 | 6.6 | 0 | 35 | 2,545.0 | electric-station-keeping-step-detector-blind |
| 47306 | Turksat 5A | class-prior | 3,500 | 0.0 | 0.00–0.00 % | 0.0 | 4.5 | 0 | 51 | — | electric-station-keeping-step-detector-blind |

## Reproduction and provenance

Analysis only: new files, a read-only archive snapshot opened through `orbit_campaigns.open_archive_for_reading`, no production artifact, no timer, no network, no deploy. The pre-registered rules are frozen in the module docstring and reproduced verbatim in the receipt’s `preRegisteredRules` field.

| Input | SHA-256 |
| --- | --- |
| Frozen archive snapshot | ffc4c4e521ca0c4eb78d5ec48039e8c9032e2f05183e5b3f09fe703bc5b734c3 |
| Propulsion catalogue | 7f7a50bc4dff644705f52ec28fb2c52a7f8589c7be45433a7f4c23dcc72711a9 |
| Cohort extraction | 9e75b035a64b27d24bb5a9636876e62348f46e10344c4347fd792b09653637d4 |
| Odometer module at detection | bd73945e93b7a9d5a18bce33c922cf70825a39ad30b9e68867a119e04a827e61 |
| Odometer module at integration | bd73945e93b7a9d5a18bce33c922cf70825a39ad30b9e68867a119e04a827e61 |
| Reused EOL probe helpers | f858bc2919d764de15b3d93dbde7c27e8115f6e8fc3555ce261a1d4e1ed96b47 |
| Reused EOL three-arm helpers | 4bb50a7108486bb56ea8ff9eb129d1338fd960e8d63e46e0b555fd8c3ddcd572 |
| Manoeuvre expectations | 3b09c73c6ef7eb8a1516391cb6727c0dd6985b82474561cc8365a715f2c15abb |
| Detector source `pipeline/orbit_campaigns.py` | 1037ac43f14144cd519ef296005723369d0c3a26412b5608dd654e3800bb507b |
| Detector source `pipeline/orbit_events.py` | 56bc4fa3a4aa23a743eb368b5537e8e99f2e77867630f8f81b5d86b8885330de |
| Detector source `pipeline/orbit_history.py` | f9beae5c4adc7d69ae1e573721972d57cb98dba13be2e452093b752f75c6d9e8 |

```bash
nice -n 19 ionice -c 3 .venv-gpu/bin/python tools/fuel_odometer.py detect \
  --archive /tmp/eol-study-20260920/archive.sqlite3 \
  --output /tmp/odometer-20260920/cohort-events.jsonl.gz

nice -n 19 .venv-gpu/bin/python tools/fuel_odometer.py integrate \
  --events /tmp/odometer-20260920/cohort-events.jsonl.gz \
  --output-prefix docs/fuel-odometer-20260920

.venv-gpu/bin/python tools/fuel_odometer_report.py
```

Artifacts: [per-object JSONL](fuel-odometer-20260920.jsonl), [receipt](fuel-odometer-20260920-receipt.json), [module](../tools/fuel_odometer.py), [report renderer](../tools/fuel_odometer_report.py), [tests](../tests/test_fuel_odometer.py). The JSONL carries, per object: the full mass curve sample (one point per priced event, with the mass band), the annual Δv trajectory, the coverage segments and holes, the excluded events with their reasons, the unfiltered integration, the per-leg split, and the cross-prediction block — enough for a site page to be precomputed without re-reading the archive.
