# EOL policy relaxation: full-archive census and three-arm study

Measured 2026-09-20. This extends [arm 1’s published-artifact probe](eol-policy-relaxation-20260920.md). It is an analysis of detected orbital changes, not a fuel estimator. The extraction is complete; candidate labels, coverage failures, and external contradictions remain visible in the evidence.

## Verdict, stated first

Full-archive extraction did what it was supposed to do: distinct payload endpoints rose from **22** in the published artifact to **113**, a **5.1x** increase, and **133** distinct payloads carry a raise flag. The cadence measurement still fails. Only **2** arm-1 and **1** arm-2 trajectories clear the registered baseline-and-final-year cadence gate, against a pre-registered feasibility floor of **15 complete matched pairs**. Neither arm produced a complete pair with both outcome ratios estimable, so **no effect size, hypothesis test, TOST equivalence result or confidence interval is reported for either arm**. This is an underpowered verdict, not a null result: the hypothesis that station-keeping relaxes before retirement is neither supported nor refuted here.

What the run does deliver is a census and two measured-but-tiny lead distributions. The binding constraint is not the number of retirements in the archive — it is **detected north-south keeping cadence**: 97 of 113 arm-1 candidates cannot even have a baseline cadence estimated, and 108 cannot have a final-year one. Three NSK detections and two same-segment spacings per window is a modest requirement; the detector does not supply it for most GEO payloads in this archive. Any future attempt at this study needs detection recall, not more objects.

Arm 3 is the part that survives. Post-NS-cessation outcomes separate into abandonment-compatible 1; inclined-operations-compatible 3; raise-after-24mo-unresolved 2; raise-within-24mo 2; unresolved 8 (and 1,363 payloads with no eligible NS cessation at all). Inclined operation is therefore a real, separately observable outcome of NS cessation in this archive, and treating NS cessation as a retirement proxy would have mislabelled those objects. External audit of the object-level endpoints agrees at **79.7%** among assessable cases, Wilson 95% **[0.688, 0.875]**, with **14** contradictions retained and examined below.

## Arm 0: uncapped extraction

| Census stage | Count |
| --- | --- |
| Frozen archive rows / objects | 216,937,797 / 68,711 |
| Full-row conservative mean-motion screen: selected objects | 3,475 |
| Objects with GEO/near-GEO intervals / payloads | 1,929 / 1,379 |
| All retained raise flags / payload flags | 156 / 152 |
| Distinct payloads carrying a raise | 133 |
| Payload flags excluded by <=18-month launch rule | 30 |
| Payload flags with unknown launch date | 0 |
| Remaining payload flags / distinct candidate endpoints | 122 / 113 |

The earlier probe inspected **all 256 detail shards**, not just the 1,500 headline events. The loss occurred at the publication catalogue filter. This run scans every archive row and re-detects every selected object’s full history without that filter, an event cap, or a current-catalogue requirement. The positive mean-motion <=2 rev/day screen is conservative: the detector’s GEO/near-GEO branch requires a much larger semi-major axis than a 2 rev/day orbit. Passive and unknown-type candidates are retained too.

The source is a consistent SQLite backup made from a connection opened by `open_archive_for_reading`; the snapshot is also read through that opener with `query_only=1`. Detection and exposure therefore use the same frozen rows. The archive rollups were stale; the authoritative totals above are a direct full-table count, not the smaller rollup figures preserved in the raw GPU receipt. The archive contains a small future-epoch tail through 2026-09-24; these are catalogue fit epochs, not future observations.

## The three-arm result

| Arm | Candidate objects | Usable NSK trajectories | Complete matched pairs | Verdict |
| --- | --- | --- | --- | --- |
| 1 — first uncontaminated raise | 113 | 2 | 0 | underpowered |
| 2 — total keeping ceases, no later raise/restart | 20 | 1 | 0 | underpowered |
| 3 — NS cessation outcomes | See split below | Separate NS and total signals | Not a two-group cadence test | Retrospective classification only |

A usable trajectory requires three years of gap-qualified pre-endpoint exposure and NSK depth, plus at least three NSK events and two same-segment spacings in each baseline/final-year window. Missing cadence is null, never zero or an infinite interval. Ratios for excluded trajectories are descriptive diagnostics and do not count as usable observations.

| Primary/secondary comparison | Complete pairs | Geometric ratio of ratios | 95% bootstrap CI | TOST equivalence |
| --- | --- | --- | --- | --- |
| arm1 R_interval | 0 | — | — | Not tested |
| arm1 R_dv | 1 | — | — | Not tested |
| arm2 R_interval | 0 | — | — | Not tested |
| arm2 R_dv | 1 | — | — | Not tested |

The [registration](eol-three-arm-preregistration-20260920.md) fixed the TOST margin at **[0.8, 1.25]**, or +/-log(1.25), before any new outcomes were computed. Both one-sided tests must reject at alpha .05 to claim equivalence. Fewer than 15 complete pairs triggers the confirmatory stop. No non-significant p-value is accepted as evidence of no difference. The 25% margin is an explicit engineering choice, not an empirically validated fuel threshold; 15 pairs is a feasibility floor, not a power calculation.

arm1 eligibility failures (overlapping): nsk-depth-below-three-years=44; observed-exposure-below-three-years=20; baseline-cadence-not-estimable=97; final-year-cadence-not-estimable=108.

arm2 eligibility failures (overlapping): baseline-cadence-not-estimable=17; final-year-cadence-not-estimable=19; nsk-depth-below-three-years=5.

### Arm 2: survivorship check

There are **20** objects meeting the registered detected-total-cessation rule. **2** still appear operational in the frozen CelesTrak catalogue. Those contradictions are retained, so this cohort is called abandonment-compatible, never independently confirmed dead. An absence of detectable steps cannot establish that small, continuous, or geometrically different corrections stopped.

Cessation needs a preceding two-year cadence and no detections for at least max(180 days, three preceding median spacings). Non-raise classification additionally needs 24 calendar months of unbroken observation coverage and no detected later restart. Gaps are not filled. These choices avoid declaring every sparsely observed historical payload abandoned, but necessarily leave many real failures unresolved.

### Arm 3: inclined-operation disambiguation

| Post-NS class | Payload objects |
| --- | --- |
| abandonment-compatible | 1 |
| inclined-operations-compatible | 3 |
| no-eligible-ns-cessation | 1,363 |
| raise-after-24mo-unresolved | 2 |
| raise-within-24mo | 2 |
| unresolved | 8 |

EW-only continuation requires at least three subsequent EW detections, continued keeping at or beyond 24 months on the same observed segment, an EW detection in the last 180 days of that window, and a monthly-median inclination slope of 0.5–1.2 deg/year. This is an inclined-operation-compatible signature, not proof of revenue service. A later raise beyond 24 months stays explicitly unresolved rather than being forced into the abandonment group.

The operator’s [2 August 2017 EchoStar III release](https://ir.echostar.com/news-releases/news-release-details/echostar-iii-satellite-experiences-anomaly-during-move) confirms more than three years of inclined operation before a relocation anomaly. Its [Q3 2017 filing](https://www.sec.gov/Archives/edgar/data/1415404/000141540417000050/sats09301710qdocument.htm) reports recovery of control and retirement in August. This independently illustrates why NS cessation cannot be equated with immediate retirement, and why an anomaly need not mean unrecovered abandonment.

## Two lead-time distributions

| Signal → first uncontaminated raise | Objects | Median days | IQR days | Range days | Median 95% bootstrap CI |
| --- | --- | --- | --- | --- | --- |
| nsToRaise | 2 | 530.37 | [526.984, 533.756] | [523.598, 537.143] | [523.598, 537.143] |
| totalToRaise | 0 | — | — | — | — |

These are last-detected-correction **end** to raise-flag **start**, not independently measured physical cessation times. A supported preceding cadence and uninterrupted coverage are mandatory; post-raise keeping restarts invalidate a terminal-cessation lead. Each object contributes once per signal. Null distributions are not zero-day leads. The JSONL preserves last-event time and retrospective confirmation time separately; any prospective warning would have to subtract the confirmation delay and avoid the detector’s future-looking baseline/persistence information.

| External status stratum | NS lead n / median days | Total lead n / median days |
| --- | --- | --- |
| support | 1 / 537.143 | 0 / — |
| contradiction | 0 / — | 0 / — |
| unknown | 1 / 523.598 | 0 / — |

## External agreement and what it establishes

All **156** raise flags receive an external lookup, including non-payloads and launch contamination. The primary agreement unit is one first uncontaminated raise per payload: **55 supporting, 14 contradicting, and 44 unknown**, out of **113**. Among assessable cases, agreement is **79.7%**, Wilson 95% CI **[0.688, 0.875]** (fractions); support across all candidates is **48.7%**, CI **[0.397, 0.578]**. Unknowns remain in the all-candidate denominator. Repeated-flag rates are descriptive only; they do not get falsely independent binomial intervals.

| Audit population | Support | Contradiction | Unknown | Total |
| --- | --- | --- | --- | --- |
| allPayloadRaises | 62 | 35 | 55 | 152 |
| uncontaminatedPayloadRaises | 58 | 16 | 48 | 122 |
| firstUncontaminatedPayloadObjects | 55 | 14 | 44 | 113 |

The local CelesTrak SATCAT is operational-only: its absence is unknown. Space-Track supplies launch/decay and catalogue geometry but no equivalent operational curation. The supplemental [ESA 2019 classification](https://astronomer.ru/data/0128/Classification_of_Geosynchronous_Objects_I21R0.pdf) supplies historical controlled/drifting states, with all 1,363 TLE/NORAD identities independently checked against SATCAT international designators. Vimpel identifiers are excluded from NORAD joins. Current operational contradictions take precedence over an older elevated drifting state; restoration of service remains a possible explanation.

**5** first-candidate disposal years match ESA’s explicitly named 2018 list. **2** match supplemental operator retirement windows, including **1** at day resolution. These convenience audits are not a random validation sample. [NOAA dates GOES-10’s decommissioning](https://www.ncei.noaa.gov/products/goes-1-15/space-weather-instruments) to 1 December 2009; that agrees with the detected flag’s calendar day, not necessarily its firing timestamp. All other elevated-orbit support is state consistency, not independent confirmation of a historical disposal date. Thus the agreement rate is **not retirement-label positive predictive value**.

The [supplemental audit protocol](eol-external-audit-protocol-20260920.md) and [documentary evidence](eol-external-documentary-evidence-20260920.json) preserve the provenance and date resolution. No CelesTrak network request, forbidden GP group, halt marker, provider schedule or cache was touched.

### Every external contradiction, retained for examination

| NORAD | Name | Raise | Age screen | External control | Later keeping flags | Last later keeping |
| --- | --- | --- | --- | --- | --- | --- |
| 23613 | TDRS 7 | 2009-06-09 | later | + | 49 | 2025-02-05 |
| 24307 | INMARSAT 3-F2 | 1996-09-25 | launch | B | 5 | 2019-02-06 |
| 24957 | NSS 5 (INTELSAT 803) | 2002-10-24 | later | C2 | 33 | 2021-12-04 |
| 26590 | INTELSAT 12 (PAS 12) | 2000-11-02 | launch | C2 | 24 | 2021-10-27 |
| 27400 | ASTRA 3A | 2013-10-17 | later | C2 | 18 | 2022-11-22 |
| 27632 | NIMIQ 2 | 2019-04-26 | later | + | 53 | 2023-12-29 |
| 27632 | NIMIQ 2 | 2020-04-27 | later | + | 27 | 2023-12-29 |
| 28158 | USA 176 | 2026-09-14 | later | P | 0 | — |
| 28659 | DIRECTV 8 | 2005-09-07 | launch | + | 15 | 2023-06-19 |
| 29644 | AMC-18 | 2007-01-23 | launch | C1 | 42 | 2023-11-09 |
| 29644 | AMC-18 | 2018-02-26 | later | C1 | 36 | 2023-11-09 |
| 32019 | BSAT-3A | 2013-07-26 | later | C1 | 34 | 2025-02-13 |
| 33278 | INMARSAT 4-F3 | 2008-09-16 | launch | + | 6 | 2008-10-23 |
| 35812 | PALAPA D | 2009-10-13 | launch | C1 | 11 | 2021-04-21 |
| 36108 | WGS F3 (USA 211) | 2021-04-29 | later | + | 27 | 2026-08-18 |
| 36108 | WGS F3 (USA 211) | 2022-11-21 | later | + | 13 | 2026-08-18 |
| 36131 | DIRECTV 12 | 2010-05-04 | launch | + | 1 | 2010-05-11 |
| 36828 | BEIDOU 5 | 2021-08-03 | later | + | 4 | 2023-10-08 |
| 37207 | BSAT-3B | 2013-01-23 | later | + | 64 | 2026-08-10 |
| 41586 | BD-2-G7 | 2018-09-17 | later | + | 73 | 2026-08-20 |
| 41838 | SJ-17 | 2018-02-10 | launch | P | 133 | 2025-11-23 |
| 41838 | SJ-17 | 2018-07-17 | later | P | 111 | 2025-11-23 |
| 42907 | COSMOS 2520 | 2021-01-25 | later | + | 1 | 2022-08-11 |
| 42965 | QZS-4 | 2017-10-14 | launch | + | 7 | 2023-07-13 |
| 44071 | WGS 10 (USA 291) | 2019-09-23 | launch | + | 22 | 2020-10-23 |
| 44071 | WGS 10 (USA 291) | 2020-01-23 | launch | + | 9 | 2020-10-23 |
| 44625 | MEV-1 | 2020-02-01 | launch | + | 3 | 2025-05-13 |
| 44625 | MEV-1 | 2020-02-01 | launch | + | 3 | 2025-05-13 |
| 44903 | ELEKTRO-L 3 | 2020-05-31 | launch | + | 18 | 2026-09-11 |
| 53355 | SBIRS GEO 6 (USA 336) | 2023-10-11 | launch | + | 3 | 2023-11-09 |
| 53765 | EUTE KONNECT VHTS | 2023-01-29 | launch | + | 0 | — |
| 54219 | LDPE-2 | 2025-05-21 | later | + | 20 | 2026-09-01 |
| 55131 | SJ-23 | 2023-01-22 | launch | + | 45 | 2026-08-08 |
| 55131 | SJ-23 | 2023-02-08 | launch | + | 40 | 2026-08-08 |
| 55841 | LUCH (OLYMP) 2 | 2023-05-05 | launch | + | 59 | 2025-03-07 |

Each contradiction above was examined against age at launch, external control classification and all retained post-raise keeping. Early flags are consistent with station acquisition under the frozen exclusion; later flags with continuing control or later corrections do not establish terminal retirement. A threshold excursion, relocation, restoration, or misclassification remains possible. No alternative retirement date was substituted to improve a trajectory. The full JSONL includes catalogue fields, ESA page/epoch, repeated flags and supporting as well as conflicting evidence.

## ESA totals: compatible definitions, not a fitted target

The often quoted **37 abandoned / 117 retirements** is for **1997–2004**, from [Jehn, Agapov and Hernandez (2005)](https://conference.sdo.esoc.esa.int/proceedings/sdc4/paper/71/SDC4-paper71.pdf): the other outcomes were 39 compliant and 41 insufficient reorbits. It is not a current archive-wide rate. The [2026 ESA Environment Report](https://www.sdo.esoc.esa.int/environment_report/Space_Environment_Report_I10R1_20260908.pdf), figure 6.35, counts **357 NS+EW-controlled and 191 EW-only-controlled** payloads near GEO during 2025. Its disposal classes distinguish successful, insufficient and no attempt. Our fixed 235-km **semi-major-axis** crossing is not ESA’s perigee/eccentricity/long-term-clearance criterion. Neither historical total supplies the number of detectable transitions with adequate exposure in this archive.

## What a reviewer still attacks

- Detection completeness remains unmeasured. The sparse, thresholded NSK event process can miss real corrections; zero detected cadence is not zero actual cadence. Requiring estimable final-year cadence also excludes the most extreme apparent relaxation.
- The three arms address the design confounds but do not automatically identify fuel state. Propulsion mode, mission policy, relocation, satellite reuse, failures, fit noise and natural inclination evolution can produce similar patterns.
- External status curation reduces circular interpretation, but ESA and Space-Track often share TLE inputs. Most cases lack operator-dated retirement evidence. Orbit-state agreement cannot validate the epoch or cause of retirement.
- The inclination-slope band is a prespecified operational filter, not a universal law. Genuine inclined operations can fall outside it, and EW-like element changes need not prove longitude control or working communications payloads.
- Continuous-observation requirements reduce gap bias while selecting the best-covered survivors. The resulting cohorts cannot be treated as an unbiased census of all GEO retirements or abandonments. Future-epoch fits and current-vs-historical status differences further limit temporal interpretation.
- Lead times are retrospective and interval-censored by fitted element epochs. Future-looking detector baselines and confirmation delays prevent a prospective prediction claim. No held-out calibration, base-rate-adjusted precision, or useful EOL watch score has been demonstrated.
- The matching calipers and TOST margin were fixed beforehand, but operator, propulsion, bus and mission covariates remain incompletely controlled. Small-sample bootstrap intervals, where available, are exploratory. A failed significance test never establishes equivalence.

## Reproduction and evidence

### Two corrections made while finishing this run

This study was designed and largely built in one session and finished in another. Two defects were found and fixed before the numbers above were produced, and both are recorded here rather than silently absorbed.

**A bare date was being read in the host’s local zone.** `epoch()` parsed `"2009-12-29"` into a naive datetime and took its POSIX timestamp, which this machine resolves as EDT — four hours off UTC. Event timestamps carry `Z` and were never affected, so the published arm-1 probe, which only ever parses event strings, is untouched. The three-arm study does parse bare dates: launch dates, calendar-year boundaries, ESA reference dates, catalogue decay dates and documentary windows. It is fixed, it is covered by a test, and the study was re-run from the same frozen census afterwards. **Every figure in this report is identical before and after the fix** — the affected boundaries are hours wide and no event fell inside one — but a launch-day manoeuvre a few hours after midnight UTC was being classified as pre-launch in the companion fuel-odometer run, which is how it was caught.

**The extended JSONL was compacted, without changing a measured value.** Hole lists longer than 10 entries keep an exact count and total days and truncate the enumeration; full observation-segment lists are retained for cohort objects (payloads carrying a raise or an eligible cessation) and reduced to first and last for the rest; keeping events keep their total Delta-v and drop the component breakdown; calendar years with no observed exposure are omitted and counted; floats are rounded to six decimal places. The artifact went from 64 MB to 15.8 MB. Both rules are declared in the receipt under `jsonlCompaction`.

New analysis files only. Existing probe outputs are preserved. Source UI, narration, production ingestion, GPU placement and timers were not edited. GPU arithmetic uses the existing detector implementation through the broker’s standard lane; unavailable GPU execution raises rather than falling back to CPU. All compute ran nice 19 / idle I/O. The focused offline suite covers archive holes, launch boundaries, missing launch dates, restarts, distinct lead times, inclined operations, external source namespaces and TOST logic.

GPU census cost: **2,236.399 s wall / 816.804 s main-process CPU**, **18,922,604** selected full-history rows. GPU outcome `gpu`, **1917** objects, **0** fallbacks. CPU in the GPU arithmetic thread is recorded separately in the receipt, so the main-process CPU figure must not be added to it as an independent total.

Artifacts: [extended JSONL](eol-three-arm-20260920.jsonl), [machine-readable receipt](eol-three-arm-20260920-receipt.json), [census runner](../tools/eol_archive_census.py), [arm analysis](../tools/eol_three_arm_study.py), [ESA parser](../tools/eol_esa_audit.py), and [optional analysis dependencies](../tools/eol-analysis-requirements.txt). The JSONL contains every GEO-capable object, every raise, compact NSK/EW histories, yearly observed exposure, both cessation signals, censoring, cohort exclusions and external audits. **Every `watchEligible` is false.**

The full frozen SQLite copy and uncapped compressed extraction are in `/tmp/eol-study-20260920/`; the latter retains exact observation intervals for reproducibility. They are analysis working files, not production artifacts or an archival retention commitment. The snapshot SHA-256 is `ffc4c4e521ca0c4eb78d5ec48039e8c9032e2f05183e5b3f09fe703bc5b734c3`. The receipt records source hashes, registration hash, external file hashes and extraction hash. Preserve or intentionally relocate those working inputs before cleaning `/tmp` if exact replay is needed.

Canonical commands (after creating the frozen archive and selected-ID file as described above):

```bash
nice -n 19 ionice -c 3 /home/sdegan/gpu-broker/gpu-run \
  --estimate-mib 320 --class standard --wait-seconds 3600 -- \
  .venv-gpu/bin/python tools/eol_archive_census.py \
  --archive /tmp/eol-study-20260920/archive.sqlite3 \
  --selected /tmp/eol-study-20260920/selected.json \
  --output /tmp/eol-study-20260920/census.jsonl.gz \
  --registration docs/eol-three-arm-preregistration-20260920.md

PYTHONPATH=/tmp/eol-study-20260920/stats-deps nice -n 19 ionice -c 3 \
  .venv-gpu/bin/python tools/eol_three_arm_study.py \
  --census /tmp/eol-study-20260920/census.jsonl.gz \
  --celestrak /tmp/eol-study-20260920/celestrak-satcat.json \
  --spacetrack /tmp/eol-study-20260920/spacetrack-satcat.json \
  --esa /tmp/eol-study-20260920/esa-geo-2019-v2.json \
  --documentary docs/eol-external-documentary-evidence-20260920.json \
  --output-prefix docs/eol-three-arm-20260920
```

Outputs use exclusive creation; a reproduction must select fresh output paths. No detector outputs were spliced from the older published artifact into this census.

## First uncontaminated payload endpoint census

| NORAD | Name | First retained raise | All raise flags | Prior NSK | NSK depth yr | NSK baseline/final | Usable | External |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 10024 | INTELSAT 4A-F4 | 1997-04-26 | 2 | 0 | — | 0/0 | no | unknown |
| 12474 | INTELSAT 501 | 1997-02-04 | 1 | 0 | — | 0/0 | no | support |
| 13669 | RADUGA 11 | 1989-01-13 | 2 | 1 | 3.799 | 1/0 | no | support |
| 14821 | EKRAN 12 | 1988-05-08 | 1 | 0 | — | 0/0 | no | support |
| 15236 | LEASAT 2 | 1996-10-01 | 1 | 0 | — | 0/0 | no | support |
| 18328 | EKRAN 16 | 1989-10-03 | 1 | 2 | 2.084 | 2/0 | no | support |
| 18350 | OPTUS A3 (AUSSAT 3) | 2008-04-03 | 1 | 0 | — | 0/0 | no | support |
| 19121 | NSS 513 (INTELSAT 513) | 1995-07-10 | 2 | 0 | — | 0/0 | no | support |
| 19217 | PAS 1 | 2001-07-12 | 1 | 0 | — | 0/0 | no | unknown |
| 19688 | ASTRA 1A | 2004-12-01 | 1 | 1 | 3.015 | 1/0 | no | support |
| 20263 | GORIZONT 19 | 1996-10-30 | 1 | 1 | 0.42 | 0/1 | no | unknown |
| 20558 | ASIASAT 1 | 2003-02-21 | 2 | 1 | 6.749 | 1/0 | no | support |
| 20667 | INTELSAT 604 | 2006-04-05 | 1 | 0 | — | 0/0 | no | support |
| 20762 | THOR 1 (MARCOPOLO 2) | 2003-01-07 | 1 | 1 | 1.914 | 1/0 | no | support |
| 20872 | SBS 6 | 2009-02-18 | 1 | 3 | 13.181 | 3/0 | no | support |
| 21222 | ANIK E2 | 2005-11-21 | 1 | 3 | 10.775 | 3/0 | no | support |
| 21814 | INMARSAT 2-F3 | 2006-04-28 | 1 | 1 | 1.898 | 1/0 | no | support |
| 21893 | SUPERBIRD B1 | 2001-07-29 | 1 | 2 | 2.423 | 1/1 | no | support |
| 21906 | GALAXY 5 | 2005-01-26 | 1 | 0 | — | 0/0 | no | unknown |
| 22096 | SATCOM C4 | 2007-02-23 | 1 | 0 | — | 0/0 | no | support |
| 22116 | HISPASAT 1A | 2003-07-17 | 1 | 1 | 0.02 | 0/1 | no | unknown |
| 22653 | ASTRA 1C | 2014-07-21 | 1 | 0 | — | 0/0 | no | support |
| 22694 | HGS 4 (GALAXY 4) | 2000-03-14 | 1 | 0 | — | 0/0 | no | unknown |
| 22871 | INTELSAT 701 | 2017-05-24 | 1 | 1 | 12.975 | 1/0 | no | support |
| 22930 | DIRECTV 1 (DBS 1) | 2009-02-17 | 1 | 0 | — | 0/0 | no | support |
| 23124 | INTELSAT 702 | 2016-09-27 | 1 | 0 | — | 0/0 | no | support |
| 23175 | INTELSAT 2 (PAS 2) | 2011-01-24 | 1 | 0 | — | 0/0 | no | support |
| 23192 | DIRECTV 2 (DBS 2) | 2007-05-08 | 1 | 1 | 4.099 | 1/0 | no | support |
| 23199 | BRAZILSAT B1 | 2010-12-01 | 1 | 0 | — | 0/0 | no | support |
| 23305 | NSS 703 (INTELSAT 703) | 2014-10-11 | 1 | 3 | 3.957 | 2/1 | no | unknown |
| 23313 | SOLIDARIDAD 2 | 2013-12-10 | 1 | 1 | 17.02 | 1/0 | no | support |
| 23461 | INTELSAT 704 | 2009-05-31 | 1 | 1 | 3.805 | 1/0 | no | support |
| 23528 | INTELSAT 705 | 2011-01-26 | 1 | 0 | — | 0/0 | no | support |
| 23537 | HOT BIRD 1 | 2007-02-17 | 1 | 0 | — | 0/0 | no | support |
| 23581 | GOES 9 | 2007-06-14 | 1 | 2 | 5.566 | 2/0 | no | support |
| 23598 | DIRECTV 3 (DBS/NIMIQ 3) | 2009-06-03 | 1 | 2 | 4.874 | 2/0 | no | support |
| 23613 | TDRS 7 | 2009-06-09 | 1 | 0 | — | 0/0 | no | contradiction |
| 23686 | ASTRA 1E | 2015-06-05 | 1 | 3 | 6.901 | 3/0 | no | support |
| 23696 | UFO 6 (USA 114) | 2017-05-28 | 1 | 0 | — | 0/0 | no | unknown |
| 23723 | AMOS 5I (ASIASAT 2) | 2012-07-17 | 1 | 4 | 7.811 | 3/1 | no | unknown |
| 23754 | ECHOSTAR 1 | 2018-01-05 | 1 | 1 | 8.54 | 1/0 | no | support |
| 23816 | INTELSAT 707 | 2013-01-11 | 1 | 0 | — | 0/0 | no | unknown |
| 23915 | INTELSAT 709 | 2013-01-31 | 1 | 3 | 6.9 | 3/0 | no | support |
| 24209 | TELECOM 2D | 2012-11-09 | 1 | 1 | 7.618 | 1/0 | no | support |
| 24714 | NAHUEL 1A | 2010-07-13 | 1 | 1 | 13.436 | 1/0 | no | unknown |
| 24748 | DIRECTV 6 (TEMPO 2) | 2006-08-13 | 1 | 1 | 5.301 | 1/0 | no | unknown |
| 24786 | GOES 10 | 2009-12-01 | 1 | 2 | 12.471 | 2/0 | no | unknown |
| 24957 | NSS 5 (INTELSAT 803) | 2002-10-24 | 1 | 3 | 5.069 | 2/1 | no | contradiction |
| 25004 | ECHOSTAR 3 | 2017-08-20 | 1 | 3 | 19.847 | 3/0 | no | support |
| 25010 | APSTAR 2R (TELSTAR 10) | 2012-11-03 | 1 | 19 | 12.789 | 17/2 | no | unknown |
| 25354 | CHINASAT 5A (CHINASTAR1) | 2018-06-14 | 1 | 8 | 17.918 | 8/0 | no | support |
| 25404 | CHINASAT 5B (SINOSAT 1) | 2013-07-05 | 1 | 7 | 14.071 | 7/0 | no | support |
| 25462 | ASTRA 2A | 2025-04-20 | 1 | 15 | 26.619 | 15/0 | no | unknown |
| 25515 | AFRISTAR | 2018-01-04 | 1 | 0 | — | 0/0 | no | support |
| 25516 | AMC-5 (GE-5) | 2014-05-13 | 1 | 2 | 9.903 | 2/0 | no | support |
| 25558 | EUTE 115 WEST A(SATMEX 5 | 2016-04-15 | 1 | 1 | 3.318 | 1/0 | no | support |
| 25585 | INTELSAT 6B (PAS 6B) | 2008-03-19 | 1 | 1 | 9.212 | 1/0 | no | support |
| 25626 | GALAXY 26 (TELSTAR 6) | 2014-06-02 | 1 | 6 | 15.279 | 3/3 | no | support |
| 25785 | ASTRA 1H | 2019-10-12 | 1 | 0 | — | 0/0 | no | unknown |
| 25913 | ECHOSTAR 5 | 2009-08-05 | 1 | 1 | 8.725 | 1/0 | no | support |
| 25922 | GALAXY 27 (TELSTAR 7) | 2016-05-06 | 1 | 1 | 6.091 | 1/0 | no | support |
| 25937 | DIRECTV 1R | 2014-05-02 | 1 | 2 | 14.446 | 2/0 | no | support |
| 26095 | SUPERBIRD 4 | 2018-06-05 | 1 | 6 | 18.268 | 6/0 | no | support |
| 26098 | EXPRESS 2A | 2015-11-03 | 1 | 4 | 15.368 | 4/0 | no | support |
| 26487 | EUROBIRD 4A(EUTELSAT W1) | 2012-02-16 | 1 | 0 | — | 0/0 | no | support |
| 26495 | AMC-7 (GE-7) | 2020-01-25 | 1 | 2 | 5.834 | 2/0 | no | unknown |
| 26608 | INTELSAT 1R (PAS 1R) | 2024-07-26 | 1 | 3 | 8.541 | 3/0 | no | unknown |
| 26824 | INTELSAT 901 | 2025-03-31 | 1 | 3 | 23.792 | 3/0 | no | unknown |
| 26985 | DIRECTV 4S | 2019-11-07 | 1 | 5 | 13.252 | 5/0 | no | unknown |
| 27298 | INSAT 3C | 2017-07-26 | 1 | 15 | 14.89 | 14/1 | no | support |
| 27400 | ASTRA 3A | 2013-10-17 | 1 | 3 | 2.507 | 2/1 | no | contradiction |
| 27403 | INTELSAT 903 | 2020-04-21 | 1 | 3 | 16.134 | 3/0 | no | unknown |
| 27499 | EUTE 8 WEST C (HB 6) | 2016-08-07 | 1 | 1 | 4.723 | 1/0 | no | support |
| 27508 | EUTE 12 WEST A (AB 1) | 2018-10-30 | 2 | 3 | 14.565 | 3/0 | no | support |
| 27516 | DRTS | 2017-08-03 | 1 | 2 | 8.127 | 2/0 | no | unknown |
| 27632 | NIMIQ 2 | 2019-04-26 | 2 | 1 | 16.175 | 1/0 | no | contradiction |
| 27715 | GALAXY 12 | 2023-09-12 | 1 | 10 | 16.553 | 10/0 | no | unknown |
| 28132 | AMOS 2 | 2017-04-05 | 1 | 3 | 13.172 | 3/0 | no | support |
| 28154 | AMC-10 (GE-10) | 2019-02-15 | 1 | 8 | 7.459 | 8/0 | no | unknown |
| 28158 | USA 176 | 2026-09-14 | 1 | 0 | — | 0/0 | no | contradiction |
| 28463 | EXPRESS AM-1 | 2013-08-17 | 1 | 1 | 5.734 | 1/0 | no | support |
| 28472 | AMC-16 | 2021-08-04 | 1 | 11 | 16.238 | 10/1 | no | unknown |
| 28629 | EXPRESS AM-2 | 2016-12-11 | 1 | 4 | 8.844 | 4/0 | no | support |
| 28638 | APSTAR 6 | 2020-12-03 | 1 | 8 | 12.857 | 5/3 | no | unknown |
| 28707 | EXPRESS AM-3 | 2022-03-10 | 1 | 3 | 14.152 | 3/0 | no | unknown |
| 28790 | GALAXY 14 | 2024-10-27 | 1 | 14 | 10.435 | 14/0 | no | unknown |
| 28903 | SPACEWAY 2 | 2024-11-21 | 1 | 3 | 10.071 | 3/0 | no | unknown |
| 28911 | INSAT 4A | 2019-10-22 | 1 | 15 | 10.919 | 10/5 | yes | unknown |
| 28937 | HIMAWARI 7 | 2020-05-16 | 1 | 16 | 11.355 | 9/7 | yes | unknown |
| 28946 | EUTELSAT HOTBIRD 13E | 2024-11-26 | 2 | 19 | 9.894 | 19/0 | no | unknown |
| 29155 | EWS-G1 | 2023-11-09 | 1 | 3 | 17.443 | 3/0 | no | unknown |
| 29163 | THAICOM 5 | 2020-02-25 | 1 | 17 | 9.079 | 17/0 | no | unknown |
| 29230 | KAZSAT 1 | 2009-08-11 | 1 | 1 | 2.185 | 1/0 | no | support |
| 29644 | AMC-18 | 2018-02-26 | 3 | 5 | 8.999 | 3/2 | no | contradiction |
| 30323 | BEIDOU 1D | 2009-02-18 | 1 | 0 | — | 0/0 | no | unknown |
| 32018 | SPACEWAY 3 | 2024-01-22 | 1 | 0 | — | 0/0 | no | unknown |
| 32019 | BSAT-3A | 2013-07-26 | 1 | 1 | 2.224 | 1/0 | no | contradiction |
| 32252 | OPTUS D2 | 2025-08-17 | 1 | 8 | 7.021 | 8/0 | no | unknown |
| 32373 | RADUGA 1M-1 | 2013-07-08 | 1 | 3 | 5.437 | 3/0 | no | unknown |
| 33154 | BADR 6 | 2024-11-17 | 1 | 24 | 11.804 | 24/0 | no | unknown |
| 33453 | CIEL-2 | 2024-01-28 | 1 | 17 | 10.549 | 17/0 | no | unknown |
| 33596 | EXPRESS MD1 | 2013-08-23 | 1 | 3 | 2.553 | 2/1 | no | support |
| 35812 | PALAPA D | 2021-04-15 | 2 | 5 | 8.681 | 5/0 | no | unknown |
| 36108 | WGS F3 (USA 211) | 2021-04-29 | 2 | 0 | — | 0/0 | no | contradiction |
| 36828 | BEIDOU 5 | 2021-08-03 | 1 | 0 | — | 0/0 | no | contradiction |
| 37207 | BSAT-3B | 2013-01-23 | 1 | 1 | 0.758 | 0/1 | no | contradiction |
| 40258 | LUCH (OLYMP) | 2025-10-15 | 1 | 1 | 3.217 | 1/0 | no | unknown |
| 41586 | BD-2-G7 | 2018-09-17 | 1 | 0 | — | 0/0 | no | contradiction |
| 41838 | SJ-17 | 2018-07-17 | 2 | 9 | 1.699 | 5/4 | no | contradiction |
| 42907 | COSMOS 2520 | 2021-01-25 | 1 | 2 | 3.391 | 2/0 | no | contradiction |
| 49818 | LDPE-1 | 2025-01-09 | 2 | 3 | 3.068 | 2/1 | no | unknown |
| 54219 | LDPE-2 | 2025-05-21 | 1 | 3 | 1.297 | 1/2 | no | contradiction |
| 55264 | LDPE-3A | 2025-04-01 | 3 | 4 | 0.806 | 0/4 | no | unknown |

