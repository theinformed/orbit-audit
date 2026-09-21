#!/usr/bin/env python3
"""Render the offline EOL results and retained label contradictions."""
from pathlib import Path
import argparse
import json
from collections import Counter
root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--prefix',type=Path,default=root/'docs/eol-three-arm-20260920')
prefix=parser.parse_args().prefix
s=json.loads(Path(str(prefix)+'-receipt.json').read_text())
rows=[json.loads(x) for x in Path(str(prefix)+'.jsonl').read_text().splitlines()]
flow=s['raiseFlow']; a=s['arms']; ext=s['external']['firstUncontaminatedPayloadObjects']; counts=s['archiveDirectCount']
def f(x):
 if x is None:return '—'
 if isinstance(x,(float,int)):return f'{x:,.3f}'.rstrip('0').rstrip('.') if isinstance(x,float) else f'{x:,}'
 return str(x)
def ci(x):return '—' if x is None else '['+', '.join(f(y) for y in x)+']'
def pct(x):return '—' if x is None else f'{100*x:.1f}%'
lines=[]
def out(t=''):lines.append(t)
def table(headers,data):
 out('| '+' | '.join(headers)+' |');out('| '+' | '.join('---' for _ in headers)+' |')
 for row in data:out('| '+' | '.join(map(str,row))+' |')
 out()
out('# EOL policy relaxation: full-archive census and three-arm study')
out()
out('Measured 2026-09-20. This extends [arm 1’s published-artifact probe](eol-policy-relaxation-20260920.md). It is an analysis of detected orbital changes, not a fuel estimator. The extraction is complete; candidate labels, coverage failures, and external contradictions remain visible in the evidence.')
out()
out('## Verdict, stated first')
out()
published=22
grew=a['arm1']['candidateCount']/published if published else None
out(f"Full-archive extraction did what it was supposed to do: distinct payload endpoints rose from **{published}** in the published artifact to **{f(a['arm1']['candidateCount'])}**, a **{grew:.1f}x** increase, and **{f(flow['payloadObjects'])}** distinct payloads carry a raise flag. The cadence measurement still fails. Only **{f(a['arm1']['usable'])}** arm-1 and **{f(a['arm2']['usable'])}** arm-2 trajectories clear the registered baseline-and-final-year cadence gate, against a pre-registered feasibility floor of **15 complete matched pairs**. Neither arm produced a complete pair with both outcome ratios estimable, so **no effect size, hypothesis test, TOST equivalence result or confidence interval is reported for either arm**. This is an underpowered verdict, not a null result: the hypothesis that station-keeping relaxes before retirement is neither supported nor refuted here.")
out()
out(f"What the run does deliver is a census and two measured-but-tiny lead distributions. The binding constraint is not the number of retirements in the archive — it is **detected north-south keeping cadence**: {a['arm1']['eligibilityFailures'].get('baseline-cadence-not-estimable',0)} of {f(a['arm1']['candidateCount'])} arm-1 candidates cannot even have a baseline cadence estimated, and {a['arm1']['eligibilityFailures'].get('final-year-cadence-not-estimable',0)} cannot have a final-year one. Three NSK detections and two same-segment spacings per window is a modest requirement; the detector does not supply it for most GEO payloads in this archive. Any future attempt at this study needs detection recall, not more objects.")
out()
out(f"Arm 3 is the part that survives. Post-NS-cessation outcomes separate into {'; '.join(k+' '+str(v) for k,v in sorted(s['cessationClasses'].items()) if k!='no-eligible-ns-cessation')} (and {f(s['cessationClasses'].get('no-eligible-ns-cessation',0))} payloads with no eligible NS cessation at all). Inclined operation is therefore a real, separately observable outcome of NS cessation in this archive, and treating NS cessation as a retirement proxy would have mislabelled those objects. External audit of the object-level endpoints agrees at **{pct(ext['agreementAssessable'])}** among assessable cases, Wilson 95% **{ci(ext['agreementCI95'])}**, with **{ext['counts'].get('contradiction',0)}** contradictions retained and examined below.")
out()
out('## Arm 0: uncapped extraction')
out()
table(['Census stage','Count'],[
 ['Frozen archive rows / objects',f(counts['rows'])+' / '+f(counts['objects'])],
 ['Full-row conservative mean-motion screen: selected objects',f(s['censusReceipt']['prefilterObjects'])],
 ['Objects with GEO/near-GEO intervals / payloads',f(s['geoObjects'])+' / '+f(s['payloadObjects'])],
 ['All retained raise flags / payload flags',f(flow['allFlags'])+' / '+f(flow['payloadFlags'])],
 ['Distinct payloads carrying a raise',f(flow['payloadObjects'])],
 ['Payload flags excluded by <=18-month launch rule',f(flow['contaminatedFlags'])],
 ['Payload flags with unknown launch date',f(flow['unknownLaunchFlags'])],
 ['Remaining payload flags / distinct candidate endpoints',f(flow['retainedFlags'])+' / '+f(a['arm1']['candidateCount'])]])
out('The earlier probe inspected **all 256 detail shards**, not just the 1,500 headline events. The loss occurred at the publication catalogue filter. This run scans every archive row and re-detects every selected object’s full history without that filter, an event cap, or a current-catalogue requirement. The positive mean-motion <=2 rev/day screen is conservative: the detector’s GEO/near-GEO branch requires a much larger semi-major axis than a 2 rev/day orbit. Passive and unknown-type candidates are retained too.')
out()
out('The source is a consistent SQLite backup made from a connection opened by `open_archive_for_reading`; the snapshot is also read through that opener with `query_only=1`. Detection and exposure therefore use the same frozen rows. The archive rollups were stale; the authoritative totals above are a direct full-table count, not the smaller rollup figures preserved in the raw GPU receipt. The archive contains a small future-epoch tail through 2026-09-24; these are catalogue fit epochs, not future observations.')
out()
out('## The three-arm result')
out()
table(['Arm','Candidate objects','Usable NSK trajectories','Complete matched pairs','Verdict'],[
 ['1 — first uncontaminated raise',f(a['arm1']['candidateCount']),f(a['arm1']['usable']),f(a['arm1']['effects']['R_interval']['n']),a['arm1']['effects']['R_interval']['status']],
 ['2 — total keeping ceases, no later raise/restart',f(a['arm2']['candidateCount']),f(a['arm2']['usable']),f(a['arm2']['effects']['R_interval']['n']),a['arm2']['effects']['R_interval']['status']],
 ['3 — NS cessation outcomes','See split below','Separate NS and total signals','Not a two-group cadence test','Retrospective classification only']])
out('A usable trajectory requires three years of gap-qualified pre-endpoint exposure and NSK depth, plus at least three NSK events and two same-segment spacings in each baseline/final-year window. Missing cadence is null, never zero or an infinite interval. Ratios for excluded trajectories are descriptive diagnostics and do not count as usable observations.')
out()
table(['Primary/secondary comparison','Complete pairs','Geometric ratio of ratios','95% bootstrap CI','TOST equivalence'],[
 [arm+' '+metric,f(a[arm]['effects'][metric]['n']),f(a[arm]['effects'][metric]['effect']),ci(a[arm]['effects'][metric]['ci95']),str(a[arm]['effects'][metric]['tost']) if a[arm]['effects'][metric]['tost'] else 'Not tested']
 for arm in ('arm1','arm2') for metric in ('R_interval','R_dv')])
out('The [registration](eol-three-arm-preregistration-20260920.md) fixed the TOST margin at **[0.8, 1.25]**, or +/-log(1.25), before any new outcomes were computed. Both one-sided tests must reject at alpha .05 to claim equivalence. Fewer than 15 complete pairs triggers the confirmatory stop. No non-significant p-value is accepted as evidence of no difference. The 25% margin is an explicit engineering choice, not an empirically validated fuel threshold; 15 pairs is a feasibility floor, not a power calculation.')
out()
for arm in ('arm1','arm2'):
 out(f"{arm} eligibility failures (overlapping): "+'; '.join(k+'='+str(v) for k,v in a[arm]['eligibilityFailures'].items())+'.')
 out()
out('### Arm 2: survivorship check')
out()
out(f"There are **{a['arm2']['candidateCount']}** objects meeting the registered detected-total-cessation rule. **{a['arm2']['currentOperationalContradictions']}** still appear operational in the frozen CelesTrak catalogue. Those contradictions are retained, so this cohort is called abandonment-compatible, never independently confirmed dead. An absence of detectable steps cannot establish that small, continuous, or geometrically different corrections stopped.")
out()
out('Cessation needs a preceding two-year cadence and no detections for at least max(180 days, three preceding median spacings). Non-raise classification additionally needs 24 calendar months of unbroken observation coverage and no detected later restart. Gaps are not filled. These choices avoid declaring every sparsely observed historical payload abandoned, but necessarily leave many real failures unresolved.')
out()
out('### Arm 3: inclined-operation disambiguation')
out()
table(['Post-NS class','Payload objects'],[(k,f(v)) for k,v in sorted(s['cessationClasses'].items())])
out('EW-only continuation requires at least three subsequent EW detections, continued keeping at or beyond 24 months on the same observed segment, an EW detection in the last 180 days of that window, and a monthly-median inclination slope of 0.5–1.2 deg/year. This is an inclined-operation-compatible signature, not proof of revenue service. A later raise beyond 24 months stays explicitly unresolved rather than being forced into the abandonment group.')
out()
out('The operator’s [2 August 2017 EchoStar III release](https://ir.echostar.com/news-releases/news-release-details/echostar-iii-satellite-experiences-anomaly-during-move) confirms more than three years of inclined operation before a relocation anomaly. Its [Q3 2017 filing](https://www.sec.gov/Archives/edgar/data/1415404/000141540417000050/sats09301710qdocument.htm) reports recovery of control and retirement in August. This independently illustrates why NS cessation cannot be equated with immediate retirement, and why an anomaly need not mean unrecovered abandonment.')
out()
out('## Two lead-time distributions')
out()
table(['Signal → first uncontaminated raise','Objects','Median days','IQR days','Range days','Median 95% bootstrap CI'],[
 [key,f(v['n']),f(v['median']),ci(v['iqr']),ci(v['range']),ci(v['medianCI95'])] for key,v in s['leads'].items()])
out('These are last-detected-correction **end** to raise-flag **start**, not independently measured physical cessation times. A supported preceding cadence and uninterrupted coverage are mandatory; post-raise keeping restarts invalidate a terminal-cessation lead. Each object contributes once per signal. Null distributions are not zero-day leads. The JSONL preserves last-event time and retrospective confirmation time separately; any prospective warning would have to subtract the confirmation delay and avoid the detector’s future-looking baseline/persistence information.')
out()
table(['External status stratum','NS lead n / median days','Total lead n / median days'],[
 [k,f(v['nsToRaise']['n'])+' / '+f(v['nsToRaise']['median']),f(v['totalToRaise']['n'])+' / '+f(v['totalToRaise']['median'])] for k,v in s['leadsByExternal'].items()])
out('## External agreement and what it establishes')
out()
out(f"All **{flow['allFlags']}** raise flags receive an external lookup, including non-payloads and launch contamination. The primary agreement unit is one first uncontaminated raise per payload: **{ext['counts'].get('support',0)} supporting, {ext['counts'].get('contradiction',0)} contradicting, and {ext['counts'].get('unknown',0)} unknown**, out of **{ext['n']}**. Among assessable cases, agreement is **{pct(ext['agreementAssessable'])}**, Wilson 95% CI **{ci(ext['agreementCI95'])}** (fractions); support across all candidates is **{pct(ext['supportAll'])}**, CI **{ci(ext['supportAllCI95'])}**. Unknowns remain in the all-candidate denominator. Repeated-flag rates are descriptive only; they do not get falsely independent binomial intervals.")
out()
table(['Audit population','Support','Contradiction','Unknown','Total'],[
 [k,f(v['counts'].get('support',0)),f(v['counts'].get('contradiction',0)),f(v['counts'].get('unknown',0)),f(v['n'])] for k,v in s['external'].items()])
out('The local CelesTrak SATCAT is operational-only: its absence is unknown. Space-Track supplies launch/decay and catalogue geometry but no equivalent operational curation. The supplemental [ESA 2019 classification](https://astronomer.ru/data/0128/Classification_of_Geosynchronous_Objects_I21R0.pdf) supplies historical controlled/drifting states, with all 1,363 TLE/NORAD identities independently checked against SATCAT international designators. Vimpel identifiers are excluded from NORAD joins. Current operational contradictions take precedence over an older elevated drifting state; restoration of service remains a possible explanation.')
out()
out(f"**{ext['disposalYearsConfirmed']}** first-candidate disposal years match ESA’s explicitly named 2018 list. **{ext['documentaryWindowsAgree']}** match supplemental operator retirement windows, including **{ext['historicalDatesConfirmed']}** at day resolution. These convenience audits are not a random validation sample. [NOAA dates GOES-10’s decommissioning](https://www.ncei.noaa.gov/products/goes-1-15/space-weather-instruments) to 1 December 2009; that agrees with the detected flag’s calendar day, not necessarily its firing timestamp. All other elevated-orbit support is state consistency, not independent confirmation of a historical disposal date. Thus the agreement rate is **not retirement-label positive predictive value**.")
out()
out('The [supplemental audit protocol](eol-external-audit-protocol-20260920.md) and [documentary evidence](eol-external-documentary-evidence-20260920.json) preserve the provenance and date resolution. No CelesTrak network request, forbidden GP group, halt marker, provider schedule or cache was touched.')
out()
out('### Every external contradiction, retained for examination')
out()
data=[]
for r in rows:
 for q in r['raiseEvents']:
  if q['external']['assessment']!='contradiction':continue
  e=q['event'];ex=q['external'];status=ex['opsStatus'] or (ex.get('esa') or {}).get('classification') or ex['reason']
  data.append([r['norad'],r['name'],e['startAt'][:10],'launch' if q['launchContaminated'] else 'later',status,sum(q['postRaiseKeepingCounts'].values()),(q['lastPostRaiseKeepingAt'] or '—')[:10]])
table(['NORAD','Name','Raise','Age screen','External control','Later keeping flags','Last later keeping'],data)
out('Each contradiction above was examined against age at launch, external control classification and all retained post-raise keeping. Early flags are consistent with station acquisition under the frozen exclusion; later flags with continuing control or later corrections do not establish terminal retirement. A threshold excursion, relocation, restoration, or misclassification remains possible. No alternative retirement date was substituted to improve a trajectory. The full JSONL includes catalogue fields, ESA page/epoch, repeated flags and supporting as well as conflicting evidence.')
out()
out('## ESA totals: compatible definitions, not a fitted target')
out()
out('The often quoted **37 abandoned / 117 retirements** is for **1997–2004**, from [Jehn, Agapov and Hernandez (2005)](https://conference.sdo.esoc.esa.int/proceedings/sdc4/paper/71/SDC4-paper71.pdf): the other outcomes were 39 compliant and 41 insufficient reorbits. It is not a current archive-wide rate. The [2026 ESA Environment Report](https://www.sdo.esoc.esa.int/environment_report/Space_Environment_Report_I10R1_20260908.pdf), figure 6.35, counts **357 NS+EW-controlled and 191 EW-only-controlled** payloads near GEO during 2025. Its disposal classes distinguish successful, insufficient and no attempt. Our fixed 235-km **semi-major-axis** crossing is not ESA’s perigee/eccentricity/long-term-clearance criterion. Neither historical total supplies the number of detectable transitions with adequate exposure in this archive.')
out()
out('## What a reviewer still attacks')
out()
for t in [
 'Detection completeness remains unmeasured. The sparse, thresholded NSK event process can miss real corrections; zero detected cadence is not zero actual cadence. Requiring estimable final-year cadence also excludes the most extreme apparent relaxation.',
 'The three arms address the design confounds but do not automatically identify fuel state. Propulsion mode, mission policy, relocation, satellite reuse, failures, fit noise and natural inclination evolution can produce similar patterns.',
 'External status curation reduces circular interpretation, but ESA and Space-Track often share TLE inputs. Most cases lack operator-dated retirement evidence. Orbit-state agreement cannot validate the epoch or cause of retirement.',
 'The inclination-slope band is a prespecified operational filter, not a universal law. Genuine inclined operations can fall outside it, and EW-like element changes need not prove longitude control or working communications payloads.',
 'Continuous-observation requirements reduce gap bias while selecting the best-covered survivors. The resulting cohorts cannot be treated as an unbiased census of all GEO retirements or abandonments. Future-epoch fits and current-vs-historical status differences further limit temporal interpretation.',
 'Lead times are retrospective and interval-censored by fitted element epochs. Future-looking detector baselines and confirmation delays prevent a prospective prediction claim. No held-out calibration, base-rate-adjusted precision, or useful EOL watch score has been demonstrated.',
 'The matching calipers and TOST margin were fixed beforehand, but operator, propulsion, bus and mission covariates remain incompletely controlled. Small-sample bootstrap intervals, where available, are exploratory. A failed significance test never establishes equivalence.'
]:out('- '+t)
out()
out('## Reproduction and evidence')
out()
out('### Two corrections made while finishing this run')
out()
out('This study was designed and largely built in one session and finished in another. Two defects were found and fixed before the numbers above were produced, and both are recorded here rather than silently absorbed.')
out()
out('**A bare date was being read in the host\u2019s local zone.** `epoch()` parsed `"2009-12-29"` into a naive datetime and took its POSIX timestamp, which this machine resolves as EDT \u2014 four hours off UTC. Event timestamps carry `Z` and were never affected, so the published arm-1 probe, which only ever parses event strings, is untouched. The three-arm study does parse bare dates: launch dates, calendar-year boundaries, ESA reference dates, catalogue decay dates and documentary windows. It is fixed, it is covered by a test, and the study was re-run from the same frozen census afterwards. **Every figure in this report is identical before and after the fix** \u2014 the affected boundaries are hours wide and no event fell inside one \u2014 but a launch-day manoeuvre a few hours after midnight UTC was being classified as pre-launch in the companion fuel-odometer run, which is how it was caught.')
out()
out(f"**The extended JSONL was compacted, without changing a measured value.** Hole lists longer than {s['jsonlCompaction']['internalGapCap']} entries keep an exact count and total days and truncate the enumeration; full observation-segment lists are retained for cohort objects (payloads carrying a raise or an eligible cessation) and reduced to first and last for the rest; keeping events keep their total Delta-v and drop the component breakdown; calendar years with no observed exposure are omitted and counted; floats are rounded to six decimal places. The artifact went from 64 MB to {Path(str(prefix)+'.jsonl').stat().st_size/1e6:.1f} MB. Both rules are declared in the receipt under `jsonlCompaction`.")
out()
out('New analysis files only. Existing probe outputs are preserved. Source UI, narration, production ingestion, GPU placement and timers were not edited. GPU arithmetic uses the existing detector implementation through the broker’s standard lane; unavailable GPU execution raises rather than falling back to CPU. All compute ran nice 19 / idle I/O. The focused offline suite covers archive holes, launch boundaries, missing launch dates, restarts, distinct lead times, inclined operations, external source namespaces and TOST logic.')
out()
r=s['censusReceipt'];g=r['gpu'];out(f"GPU census cost: **{f(r['wallSeconds'])} s wall / {f(r['cpuSeconds'])} s main-process CPU**, **{f(r['selectedRows'])}** selected full-history rows. GPU outcome `{g['outcome']}`, **{g['gpuObjects']}** objects, **{g['fallbackObjects']}** fallbacks. CPU in the GPU arithmetic thread is recorded separately in the receipt, so the main-process CPU figure must not be added to it as an independent total.")
out()
out('Artifacts: [extended JSONL](eol-three-arm-20260920.jsonl), [machine-readable receipt](eol-three-arm-20260920-receipt.json), [census runner](../tools/eol_archive_census.py), [arm analysis](../tools/eol_three_arm_study.py), [ESA parser](../tools/eol_esa_audit.py), and [optional analysis dependencies](../tools/eol-analysis-requirements.txt). The JSONL contains every GEO-capable object, every raise, compact NSK/EW histories, yearly observed exposure, both cessation signals, censoring, cohort exclusions and external audits. **Every `watchEligible` is false.**')
out()
out('The full frozen SQLite copy and uncapped compressed extraction are in `/tmp/eol-study-20260920/`; the latter retains exact observation intervals for reproducibility. They are analysis working files, not production artifacts or an archival retention commitment. The snapshot SHA-256 is `'+s['archiveSnapshotSha256']+'`. The receipt records source hashes, registration hash, external file hashes and extraction hash. Preserve or intentionally relocate those working inputs before cleaning `/tmp` if exact replay is needed.')
out()
out('Canonical commands (after creating the frozen archive and selected-ID file as described above):')
out()
out('```bash\nnice -n 19 ionice -c 3 /home/sdegan/gpu-broker/gpu-run \\\n  --estimate-mib 320 --class standard --wait-seconds 3600 -- \\\n  .venv-gpu/bin/python tools/eol_archive_census.py \\\n  --archive /tmp/eol-study-20260920/archive.sqlite3 \\\n  --selected /tmp/eol-study-20260920/selected.json \\\n  --output /tmp/eol-study-20260920/census.jsonl.gz \\\n  --registration docs/eol-three-arm-preregistration-20260920.md\n\nPYTHONPATH=/tmp/eol-study-20260920/stats-deps nice -n 19 ionice -c 3 \\\n  .venv-gpu/bin/python tools/eol_three_arm_study.py \\\n  --census /tmp/eol-study-20260920/census.jsonl.gz \\\n  --celestrak /tmp/eol-study-20260920/celestrak-satcat.json \\\n  --spacetrack /tmp/eol-study-20260920/spacetrack-satcat.json \\\n  --esa /tmp/eol-study-20260920/esa-geo-2019-v2.json \\\n  --documentary docs/eol-external-documentary-evidence-20260920.json \\\n  --output-prefix docs/eol-three-arm-20260920\n```')
out()
out('Outputs use exclusive creation; a reproduction must select fresh output paths. No detector outputs were spliced from the older published artifact into this census.')
out()
out('## First uncontaminated payload endpoint census')
out()
data=[]
for r in rows:
 if r['arm1'] is None:continue
 q=next(q for q in r['raiseEvents'] if not q['launchContaminated'] and not q['launchUnknown']);x=r['arm1']
 data.append([r['norad'],r['name'],r['firstUncontaminatedRaiseAt'][:10],len(r['raiseEvents']),f(q['priorNskEvents']),f(q['nskDepthYears']),str(x['baseline']['nskEvents'])+'/'+str(x['finalYear']['nskEvents']),'yes' if x['usable'] else 'no',q['external']['assessment']])
table(['NORAD','Name','First retained raise','All raise flags','Prior NSK','NSK depth yr','NSK baseline/final','Usable','External'],data)
Path(str(prefix)+'.md').write_text('\n'.join(lines)+'\n')
print('Report written',str(prefix)+'.md')
