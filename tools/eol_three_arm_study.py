#!/usr/bin/env python3
"""Offline, gap-aware three-arm EOL analysis of the uncapped GPU census."""
from __future__ import annotations
import argparse
import calendar
from collections import Counter
from datetime import datetime, timezone
import gzip
import json
import math
from pathlib import Path
import statistics
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.eol_policy_probe import (DAY_MS, RAISE, NSK, epoch, iso, years_before,
                                    digest, window_evidence, ratios, oc)

EW = 'geo-east-west-keeping'
KEEP = {NSK, EW}
ACTIVE = {'+', 'P', 'B', 'S', 'X'}
MARGIN = math.log(1.25)


def months_after(t, months):
    d = datetime.fromtimestamp(t/1000,timezone.utc)
    y,m = divmod(d.year*12+d.month-1+months,12)
    return int(d.replace(year=y,month=m+1,day=min(d.day,calendar.monthrange(y,m+1)[1])).timestamp()*1000)


def interval_objects(record):
    return [SimpleNamespace(start_ms=a,end_ms=b,span_days=(b-a)/DAY_MS) for a,b in record['intervals']]


def for_signal(events, signatures):
    return [dict(e,signature=NSK) for e in events if e['signature'] in signatures]


def continuous(iv, start, end):
    return any(a <= start <= end <= b for a,b in oc._segments(iv))


def cessation(record, iv, signatures, endpoint, *, followup_months=0):
    events = [e for e in record['events'] if e['signature'] in signatures and epoch(e['endAt']) < endpoint]
    if not events:
        return dict(eligible=False,reason='no-prior-detections',lastAt=None)
    last = max(events,key=lambda e:epoch(e['endAt']))
    t = epoch(last['endAt'])
    # Include the trigger in the preceding cadence, while outcome windows later
    # remain strictly pre-trigger. No cadence is estimated through the absence.
    pre = window_evidence(for_signal(events,signatures),iv,years_before(t,2),t+1,measure=True)
    med = pre['medianIntervalDays']
    minimum = max(180,3*med) if med is not None else None
    to = (max(months_after(t,followup_months),t+(minimum or 0)*DAY_MS)
          if followup_months else endpoint)
    segment_end = next((b for a,b in oc._segments(iv)
                        if a<=epoch(last['startAt'])<=t<=b),t)
    observed_end = min(endpoint,segment_end)
    reasons = []
    if med is None: reasons.append('insufficient-prior-cadence')
    if minimum is not None and (endpoint-t)/DAY_MS < minimum: reasons.append('absence-too-short')
    if to > endpoint: reasons.append('right-censored-before-followup')
    if not continuous(iv,epoch(last['startAt']),to): reasons.append('coverage-hole-or-missing-edge')
    return dict(eligible=not reasons,reason=','.join(reasons) or 'qualified-detected-cessation',
                lastAt=iso(t),lastStartAt=last['startAt'],endpointAt=iso(endpoint),
                observedAbsenceDays=max(0,(observed_end-t)/DAY_MS),
                calendarSinceLastDetectionDays=(endpoint-t)/DAY_MS,
                uninterruptedObservedThrough=iso(observed_end),minimumAbsenceDays=minimum,
                confirmedAt=iso(max(t+minimum*DAY_MS,to)) if not reasons else None,
                priorTwoYear=pre,followupMonths=followup_months)


def trajectory(record,iv,t,signatures={NSK}):
    events=for_signal(record['events'],signatures)
    split=years_before(t,1)
    b=window_evidence(events,iv,min(record['firstEpoch'],split),split,measure=True)
    f=window_evidence(events,iv,split,t,measure=True)
    prior=[epoch(e['startAt']) for e in events if epoch(e['endAt'])<t]
    depth=(t-min(prior))/DAY_MS/365.25 if prior else None
    obs=(b['observedDays']+f['observedDays'])/365.25
    result=dict(baseline=b,finalYear=f,nskCalendarDepthYears=depth,preObservedYears=obs,
                threeYearDepth=bool(prior and min(prior)<=years_before(t,3)),**ratios(b,f))
    result['usable']=result['threeYearDepth'] and obs>=3 and result['R_interval'] is not None
    result['eligibilityFailures']=[reason for condition,reason in (
        (not result['threeYearDepth'],'nsk-depth-below-three-years'),
        (obs<3,'observed-exposure-below-three-years'),
        (b['medianIntervalDays'] is None,'baseline-cadence-not-estimable'),
        (f['medianIntervalDays'] is None,'final-year-cadence-not-estimable')) if condition]
    return result


def external_audit(norad,t,ct,st,esa=None,documentary=None):
    c,s=ct.get(norad),st.get(norad)
    status=c.get('OPS_STATUS_CODE') if c else None
    result='unknown'
    reason='no-independent-operational-status'
    if status in ACTIVE:
        result,reason='contradiction','current-operational-status-contradicts-terminal-retirement'
    elif status=='-':
        try: high=float(c['PERIGEE']) >= oe_geo_altitude()+235
        except (TypeError,ValueError,KeyError): high=False
        if high: result,reason='support','inactive-and-current-perigee-above-graveyard-floor'
        else: reason='inactive-but-no-supporting-disposal-geometry'
    decay=(c or {}).get('DECAY_DATE') or (s or {}).get('DECAY')
    if decay:
        try:
            if epoch(decay)<t:
                result,reason='contradiction','catalogue-decay-predates-detected-raise'
        except ValueError: pass
    primary=result
    esa_row=(esa or {}).get(norad)
    esa_result='unknown'
    year_confirmed=False
    if esa_row and t<epoch(esa_row['referenceDate']):
        if esa_row['classification'] in ('C1','C2','C4'):
            esa_result='contradiction'
        elif esa_row['classification']=='D' and esa_row['perigeeAboveGeoKm']>=235:
            esa_result='support'
        year_confirmed=bool(esa_row['listed2018Disposal'] and epoch('2018-01-01')<=t<epoch('2019-01-01'))
        if year_confirmed:esa_result='support'
    if result!='contradiction' and esa_result!='unknown':
        result=esa_result
        reason=('ESA-2018-disposal-year-corroborated' if year_confirmed else
                'ESA-2019-controlled-after-raise' if result=='contradiction' else
                'ESA-2019-drifting-elevated-orbit-supports-disposal-state-not-date')
    doc=(documentary or {}).get(norad)
    doc_match=bool(doc and epoch(doc['from'])<=t<epoch(doc['toExclusive']))
    return dict(assessment=result,reason=reason,opsStatus=status,satcatAssessment=primary,
                esaAssessment=esa_result,esa=esa_row,disposalYearConfirmed=year_confirmed,
                celestrakPresent=c is not None,spacetrackPresent=s is not None,
                decay=decay,celestrak=c,spacetrack=s,
                documentary=doc,documentaryWindowAgrees=doc_match,
                historicalDateConfirmed=bool(doc_match and doc['precision']=='day'))


def oe_geo_altitude():
    from pipeline.orbit_events import GEO_SEMI_MAJOR_AXIS_KM, RE_WGS72
    return GEO_SEMI_MAJOR_AXIS_KM-RE_WGS72


def slope(record,start,end):
    pairs=[(epoch(m+'-15'),v) for m,v in record['monthlyInclination'].items()
           if start<=epoch(m+'-15')<=end]
    if len(pairs)<12: return dict(n=len(pairs),degreesPerYear=None,ci95=None)
    from scipy.stats import linregress
    fit=linregress([(t-start)/DAY_MS/365.25 for t,v in pairs],[v for t,v in pairs])
    from scipy.stats import t as student
    width=student.ppf(.975,len(pairs)-2)*fit.stderr
    return dict(n=len(pairs),degreesPerYear=fit.slope,ci95=[fit.slope-width,fit.slope+width],
                ciCaveat='OLS residual interval; serial dependence not corrected')


def wilson(k,n):
    if not n:return None
    z=1.959963984540054;p=k/n;d=1+z*z/n
    mid=(p+z*z/(2*n))/d;w=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
    return [mid-w,mid+w]


def distribution(values):
    import numpy as np
    a=np.asarray(values,dtype=float)
    if not len(a):return dict(n=0,median=None,iqr=None,range=None,medianCI95=None)
    ci=None
    if len(a)>=2:
        rng=np.random.default_rng(20260920)
        boots=np.median(rng.choice(a,(10000,len(a)),replace=True),axis=1)
        ci=np.quantile(boots,[.025,.975]).tolist()
    return dict(n=len(a),median=float(np.median(a)),iqr=np.quantile(a,[.25,.75]).tolist(),
                range=[float(a.min()),float(a.max())],medianCI95=ci)


def paired_effect(differences):
    import numpy as np
    from scipy.stats import t as student
    n=len(differences)
    if n<2:return dict(n=n,effect=None,ci95=None,tost=None,superiorityP=None,status='underpowered')
    a=np.asarray(differences);m=float(a.mean());rng=np.random.default_rng(20260920)
    boots=rng.choice(a,(10000,n),replace=True).mean(axis=1)
    result=dict(n=n,effect=math.exp(m),ci95=np.exp(np.quantile(boots,[.025,.975])).tolist(),
                tost=None,superiorityP=None,status='underpowered' if n<15 else 'tested')
    if n>=15:
        se=float(a.std(ddof=1)/math.sqrt(n))
        if se==0:
            ps=[float(m<=-MARGIN),float(m>=MARGIN)];ci=[m,m]
        else:
            ps=[float(student.sf((m+MARGIN)/se,n-1)),float(student.cdf((m-MARGIN)/se,n-1))]
            w=student.ppf(.95,n-1)*se;ci=[m-w,m+w]
        result['tost']=dict(margin=[.8,1.25],pLower=ps[0],pUpper=ps[1],
                            equivalent=max(ps)<.05,ci90=[math.exp(x) for x in ci])
        perm=(rng.choice([-1,1],(10000,n))*a).mean(axis=1)
        result['superiorityP']=(1+int((perm>=m).sum()))/10001
    return result


def analyse_record(r,ct,st,esa=None,documentary=None):
    iv=interval_objects(r)
    events=r['events']
    n=r['norad'];c=ct.get(n,{});s=st.get(n,{})
    launch=c.get('LAUNCH_DATE') or s.get('LAUNCH') or r['facts'].get('launchDate')
    try: launch_t=epoch(launch) if launch else None
    except ValueError:launch_t=None
    raises=[]
    for e in events:
        if e['signature']!=RAISE:continue
        t=epoch(e['startAt']);contam=launch_t is not None and t<=months_after(launch_t,18)
        prior=[x for x in events if x['signature']==NSK and epoch(x['endAt'])<t]
        depth=(t-min(epoch(x['startAt']) for x in prior))/DAY_MS/365.25 if prior else None
        after=[x for x in events if x['signature'] in KEEP and epoch(x['startAt'])>t]
        raises.append(dict(event=e,launchContaminated=contam,launchUnknown=launch_t is None,
                           priorNskEvents=len(prior),nskDepthYears=depth,
                           postRaiseKeepingCounts=dict(Counter(x['signature'] for x in after)),
                           lastPostRaiseKeepingAt=max((x['endAt'] for x in after),default=None),
                           external=external_audit(n,t,ct,st,esa,documentary)))
    valid=[e for e in raises if not e['launchContaminated'] and not e['launchUnknown']]
    chosen=valid[0] if valid else None
    out=dict(schema=2,role='geo-census-object',norad=n,name=r['name'],objectType=r['objectType'],
             launchDate=launch,launchSource='celestrak' if c.get('LAUNCH_DATE') else 'spacetrack-or-archive',
             currentOperationalStatus=c.get('OPS_STATUS_CODE'),
             currentOperationalCataloguePresent=bool(c),
             esa2019Classification=(esa or {}).get(n,{}).get('classification'),
             firstEpoch=iso(r['firstEpoch']),lastEpoch=iso(r['lastEpoch']),archiveRows=r['rows'],
             followupCensoredAt=iso(r['lastEpoch']),
             archiveRowsSha256=r['rowsSha256'],raiseEvents=raises,
             firstUncontaminatedRaiseAt=chosen['event']['startAt'] if chosen else None,
             keepingCounts=dict(Counter(e['signature'] for e in events if e['signature'] in KEEP)),
             keepingEvents=[{k:e[k] for k in ('startAt','endAt','signature','deltaV','inclinationDeg')}
                            for e in events if e['signature'] in KEEP],
             observationSegments=[[iso(a),iso(b)] for a,b in oc._segments(iv)],
             watchEligible=False,watchReason='unvalidated-retrospective-detection-proxies',
             manoeuvreLabelPermitted=False,
             groundTruthDatePermitted=bool(chosen and chosen['external']['historicalDateConfirmed']
                                          and chosen['external']['assessment']!='contradiction'),
             labelScope='detected-behaviour-candidate; external-state-audit-does-not-date-retirement',
             arm1=None,arm2=None,nsCessation=None,totalCessation=None,
             postNsClass='no-eligible-ns-cessation',leadDays={'nsToRaise':None,'totalToRaise':None})
    # Annual exposure and counts include zeros only when exposure is positive.
    years=range(datetime.fromtimestamp(r['firstEpoch']/1000,timezone.utc).year,
                datetime.fromtimestamp(r['lastEpoch']/1000,timezone.utc).year+1)
    annual=[]
    for y in years:
        a,b=epoch(f'{y}-01-01'),epoch(f'{y+1}-01-01')
        exposure=sum(max(0,min(b,i.end_ms)-max(a,i.start_ms)) for i in iv)/DAY_MS
        counts=Counter(e['signature'] for e in events if a<=epoch(e['startAt'])<b and e['signature'] in KEEP)
        annual.append(dict(year=y,observedDays=exposure,nsk=counts[NSK] if exposure else None,
                           ew=counts[EW] if exposure else None))
    out['annualTrajectory']=annual
    if r['objectType']!='PAYLOAD':return out
    if chosen:
        t=epoch(chosen['event']['startAt'])
        out['arm1']=trajectory(r,iv,t)
        out['arm1']['totalKeeping']=trajectory(r,iv,t,KEEP)
        for key,sigs,lead in [('nsCessation',{NSK},'nsToRaise'),('totalCessation',KEEP,'totalToRaise')]:
            sig=cessation(r,iv,sigs,t)
            # Continuing keeping after the raise contradicts terminal cessation.
            sig['postRaiseRestart']=any(e['signature'] in sigs and epoch(e['startAt'])>t for e in events)
            if sig['postRaiseRestart']:
                sig['eligible']=False;sig['reason']+=';post-raise-restart'
            out[key]=sig
            if sig['eligible']:out['leadDays'][lead]=sig['observedAbsenceDays']
        if out['nsCessation']['eligible']:
            ns=epoch(out['nsCessation']['lastAt'])
            out['postNsClass']='raise-within-24mo' if t<=months_after(ns,24) else 'raise-after-24mo-unresolved'
    # Independent terminal-cessation census: use all detections, not just retirees.
    endpoint=r['lastEpoch']
    total=cessation(r,iv,KEEP,endpoint+1,followup_months=24)
    ns=cessation(r,iv,{NSK},endpoint+1,followup_months=24)
    out['terminalNsCessation']=ns
    out['terminalTotalCessation']=total
    def old_enough(sig):
        return sig['lastAt'] is not None and launch_t is not None and epoch(sig['lastAt'])>months_after(launch_t,18)
    if total['lastAt'] and not any(epoch(e['event']['startAt'])>epoch(total['lastAt']) for e in raises):
        if total['eligible'] and old_enough(total):
            t=epoch(total['lastAt'])
            out['arm2']=trajectory(r,iv,t)
            out['arm2']['totalKeeping']=trajectory(r,iv,t,KEEP)
            out['arm2']['cessation']=total
            out['arm2']['externalCurrentStatus']=c.get('OPS_STATUS_CODE')
            out['arm2']['externalContradiction']=c.get('OPS_STATUS_CODE') in ACTIVE
    if ns['eligible'] and old_enough(ns) and out['postNsClass']=='no-eligible-ns-cessation':
        a=epoch(ns['lastAt']);b=months_after(a,24)
        later=[e for e in raises if epoch(e['event']['startAt'])>a]
        ew=[e for e in events if e['signature']==EW and epoch(e['startAt'])>a]
        fit=slope(r,a,b)
        out['inclinationAfterNs']=fit
        if later:
            out['postNsClass']='raise-after-24mo-unresolved'
        elif (len(ew)>=3 and max(epoch(e['endAt']) for e in ew)>=b
              and any(b-180*DAY_MS<=epoch(e['startAt'])<=b for e in ew)
              and any(epoch(e['endAt'])>=b and continuous(iv,a,epoch(e['endAt'])) for e in ew)
              and fit['degreesPerYear'] is not None and .5<=fit['degreesPerYear']<=1.2):
            out['postNsClass']='inclined-operations-compatible'
        elif out['arm2'] is not None:
            out['postNsClass']='abandonment-compatible'
        else:out['postNsClass']='unresolved'
    return out


GAP_CAP = 10


def trim_gaps(node):
    """Evidence stays, byte count does not: long hole lists become count+days.

    Nothing measured is changed. Every window already carries its own
    observedDays and spacingsExcludedAcrossGaps; this only stops a 1,929-object
    artifact from carrying a quarter of a million individually enumerated holes.
    """
    if isinstance(node,dict):
        gaps=node.get('internalGaps')
        if isinstance(gaps,list):
            node['internalGapCount']=len(gaps)
            node['internalGapDays']=sum(g['days'] for g in gaps)
            node['internalGapsTruncated']=len(gaps)>GAP_CAP
            if len(gaps)>GAP_CAP:node['internalGaps']=gaps[:GAP_CAP]
        for value in list(node.values()):trim_gaps(value)
    elif isinstance(node,list):
        for value in node:trim_gaps(value)


def round_floats(node,places=6):
    """Seventeen significant digits on a bootstrap quantile is not evidence."""
    if isinstance(node,dict):return {k:round_floats(v,places) for k,v in node.items()}
    if isinstance(node,list):return [round_floats(v,places) for v in node]
    if isinstance(node,float):return round(node,places)
    return node


def compact_record(r):
    """Full segment lists only for objects an EOL watch page would actually draw."""
    trim_gaps(r)
    for e in r.get('keepingEvents',()):
        if isinstance(e.get('deltaV'),dict):
            e['deltaVMps']=e['deltaV']['totalMetresPerSecond']
            del e['deltaV']
    annual=r.get('annualTrajectory')
    if annual is not None:
        kept=[y for y in annual if y['observedDays']>0]
        r['annualTrajectoryYearsOmittedNoExposure']=len(annual)-len(kept)
        r['annualTrajectory']=kept
    segments=r['observationSegments']
    r['observationSegmentCount']=len(segments)
    r['observedSegmentDays']=sum((epoch(b)-epoch(a))/DAY_MS for a,b in segments)
    cohort=(r['objectType']=='PAYLOAD' and (bool(r['raiseEvents']) or r['arm1'] or r['arm2']
            or r['terminalNsCessation']['eligible'] or r['terminalTotalCessation']['eligible']))
    r['observationSegmentsRetained']='all' if cohort else 'first-and-last-only'
    if not cohort:
        r['observationSegments']=[segments[0],segments[-1]] if segments else []
    return r


def match_arm(arm,records,raw):
    used=set();pairs=[]
    candidates=sorted((r for r in records if r[arm] and r[arm]['usable']),
                       key=lambda r:(r[arm]['finalYear']['toExclusive'],r['norad']))
    for r in candidates:
        t=epoch(r[arm]['finalYear']['toExclusive']);split=years_before(t,1)
        a=r[arm]['baseline']; source=raw[r['norad']]
        inc=[v for m,v in source['monthlyInclination'].items() if epoch(m+'-15')<split]
        if not inc:continue
        ai=statistics.median(inc);ac=a['observedDays']/a['calendarDays']
        choices=[]
        for c in records:
            n=c['norad']
            if n==r['norad'] or n in used or c['objectType']!='PAYLOAD':continue
            rr=raw[n]
            if any(e['signature']==RAISE and epoch(e['startAt'])<=t for e in rr['events']):continue
            if not any(e['signature'] in KEEP and epoch(e['startAt'])>t for e in rr['events']):continue
            civ=interval_objects(rr)
            # Baseline exactly matches case calendar window, including start.
            cb=window_evidence(rr['events'],civ,epoch(a['from']),split,measure=True)
            ci=[v for m,v in rr['monthlyInclination'].items() if epoch(a['from'])<=epoch(m+'-15')<split]
            if not ci or cb['medianIntervalDays'] is None:continue
            di=statistics.median(ci)-ai;dc=cb['observedDays']/cb['calendarDays']-ac
            dl=math.log(cb['medianIntervalDays']/a['medianIntervalDays'])
            if abs(di)>5 or abs(dc)>.15 or abs(dl)>math.log(2):continue
            distance=(di/5)**2+(dc/.15)**2+(dl/math.log(2))**2
            choices.append((distance,n,cb))
        if not choices:
            r[arm]['controlMatch']=None;continue
        distance,n,cb=min(choices,key=lambda x:(x[0],x[1]));used.add(n)
        rr=raw[n];cf=window_evidence(rr['events'],interval_objects(rr),split,t,measure=True)
        cr=ratios(cb,cf)
        pair=dict(caseNorad=r['norad'],controlNorad=n,distance=distance,baseline=cb,finalYear=cf,**cr)
        r[arm]['controlMatch']=pair;pairs.append((r,pair))
    results={}
    for metric in ('R_interval','R_dv'):
        diffs=[math.log(r[arm][metric]/p[metric]) for r,p in pairs
               if r[arm][metric] is not None and r[arm][metric]>0 and p[metric] is not None and p[metric]>0]
        results[metric]=paired_effect(diffs)
    return dict(eligibleCaseCount=len(candidates),matched=len(pairs),effects=results)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--census',type=Path,required=True)
    p.add_argument('--celestrak',type=Path,required=True)
    p.add_argument('--spacetrack',type=Path,required=True)
    p.add_argument('--esa',type=Path)
    p.add_argument('--documentary',type=Path)
    p.add_argument('--output-prefix',type=Path,required=True)
    args=p.parse_args()
    receipt=json.loads(Path(str(args.census)+'.receipt.json').read_text())
    assert receipt['complete'] and digest(args.census)==receipt['extractionSha256']
    ct={int(r['NORAD_CAT_ID']):r for r in json.loads(args.celestrak.read_text())}
    st={int(r['NORAD_CAT_ID']):r for r in json.loads(args.spacetrack.read_text())}
    esa_document=json.loads(args.esa.read_text()) if args.esa else None
    esa={int(k):v for k,v in esa_document['objects'].items()} if esa_document else {}
    doc_document=json.loads(args.documentary.read_text()) if args.documentary else None
    documentary={int(k):v for k,v in doc_document['objects'].items()} if doc_document else {}
    records=[];raw={}
    with gzip.open(args.census,'rt') as f:
        for line in f:
            r=json.loads(line)
            if not r['geoCapable']:continue
            records.append(analyse_record(r,ct,st,esa,documentary));raw[r['norad']]=r
    summary=dict(schema=2,censusReceipt=receipt,geoObjects=len(records),
                 payloadObjects=sum(r['objectType']=='PAYLOAD' for r in records),
                 sourceHashes={'celestrak':digest(args.celestrak),'spacetrack':digest(args.spacetrack),
                               'analysis':digest(Path(__file__)),
                               'reusedProbe':digest(ROOT/'tools/eol_policy_probe.py'),
                               'expectations':digest(ROOT/'data/orbit_manoeuvre_expectations.json')},
                 cessationClasses=dict(Counter(r['postNsClass'] for r in records if r['objectType']=='PAYLOAD')),
                 arms={},leads={})
    counts_path=args.census.parent/'archive-counts.json'
    if counts_path.exists():
        summary['archiveDirectCount']=json.loads(counts_path.read_text())
        summary['archiveCountCaveat']='Census receipt archiveRows/archiveObjects are stale rollup metadata; use archiveDirectCount.'
    provenance_path=args.census.parent/'satcat-provenance.json'
    if provenance_path.exists():summary['satcatProvenance']=json.loads(provenance_path.read_text())
    for filename,key in [('protocol-receipt.json','protocolProvenance'),
                         ('storage-audit.json','archiveStorageAudit')]:
        path=args.census.parent/filename
        if path.exists():summary[key]=json.loads(path.read_text())
    snapshot_hash_path=args.census.parent/'archive.sha256'
    if snapshot_hash_path.exists():summary['archiveSnapshotSha256']=snapshot_hash_path.read_text().split()[0]
    if esa_document:
        summary['esaProvenance']={k:v for k,v in esa_document.items() if k!='objects'}
        summary['esaProvenance']['parsedObjects']=len(esa)
    if doc_document:summary['documentaryProvenance']=dict(path=str(args.documentary),sha256=digest(args.documentary),selection=doc_document['selection'])
    for arm in ('arm1','arm2'):
        summary['arms'][arm]=dict(candidates=sum(r[arm] is not None for r in records),
                                  usable=sum(bool(r[arm] and r[arm]['usable']) for r in records),
                                  **match_arm(arm,records,raw))
        summary['arms'][arm]['candidateCount']=sum(r[arm] is not None for r in records)
        summary['arms'][arm]['eligibilityFailures']=dict(Counter(reason for r in records if r[arm]
                                                    for reason in r[arm]['eligibilityFailures']))
        if arm=='arm2':summary['arms'][arm]['currentOperationalContradictions']=sum(
            bool(r[arm] and r[arm]['externalContradiction']) for r in records)
    # Holm correction across primary arm superiority tests only.
    tests=sorted((a['effects']['R_interval']['superiorityP'],name) for name,a in summary['arms'].items()
                 if a['effects']['R_interval']['superiorityP'] is not None)
    previous=0
    for rank,(pv,name) in enumerate(tests):
        previous=max(previous,min(1,pv*(len(tests)-rank)))
        summary['arms'][name]['effects']['R_interval']['holmP']=previous
    for signal in ('nsToRaise','totalToRaise'):
        summary['leads'][signal]=distribution([r['leadDays'][signal] for r in records if r['leadDays'][signal] is not None])
    payload_raises=[x for r in records if r['objectType']=='PAYLOAD' for x in r['raiseEvents']]
    uncontaminated=[x for x in payload_raises if not x['launchContaminated'] and not x['launchUnknown']]
    summary['raiseFlow']=dict(allFlags=sum(len(r['raiseEvents']) for r in records),payloadFlags=len(payload_raises),
       payloadObjects=sum(bool(r['raiseEvents']) and r['objectType']=='PAYLOAD' for r in records),
       contaminatedFlags=sum(x['launchContaminated'] for x in payload_raises),
       unknownLaunchFlags=sum(x['launchUnknown'] for x in payload_raises),retainedFlags=len(uncontaminated))
    summary['external']={}
    first_per_object=[]
    for r in records:
        valid=[x for x in r['raiseEvents'] if not x['launchContaminated'] and not x['launchUnknown']]
        if r['objectType']=='PAYLOAD' and valid:first_per_object.append(valid[0])
    for label,pop in [('allPayloadRaises',payload_raises),('uncontaminatedPayloadRaises',uncontaminated),
                      ('firstUncontaminatedPayloadObjects',first_per_object)]:
        counts=Counter(x['external']['assessment'] for x in pop);n=counts['support']+counts['contradiction']
        independent=label=='firstUncontaminatedPayloadObjects'
        summary['external'][label]=dict(counts=counts,n=len(pop),assessable=n,
            agreementAssessable=counts['support']/n if n else None,
            agreementCI95=wilson(counts['support'],n) if independent else None,
            supportAll=counts['support']/len(pop) if pop else None,
            supportAllCI95=wilson(counts['support'],len(pop)) if independent else None,
            intervalUnit='distinct-object-first-raise' if independent else 'repeat-flags-descriptive-only',
            historicalDatesConfirmed=sum(x['external']['historicalDateConfirmed'] for x in pop),
            documentaryWindowsAgree=sum(x['external']['documentaryWindowAgrees'] for x in pop))
        satcat_counts=Counter(x['external']['satcatAssessment'] for x in pop)
        summary['external'][label]['satcatOnlyCounts']=dict(satcat_counts)
        summary['external'][label]['disposalYearsConfirmed']=sum(x['external']['disposalYearConfirmed'] for x in pop)
    summary['leadsByExternal']={}
    for label in ('support','contradiction','unknown'):
        group=[]
        for r in records:
            valid=[e for e in r['raiseEvents'] if not e['launchContaminated'] and not e['launchUnknown']]
            if valid and valid[0]['external']['assessment']==label:group.append(r)
        summary['leadsByExternal'][label]={signal:distribution([r['leadDays'][signal] for r in group
                                        if r['leadDays'][signal] is not None]) for signal in ('nsToRaise','totalToRaise')}
    summary['jsonlCompaction']=dict(
        internalGapCap=GAP_CAP,
        note=('Hole lists longer than the cap are truncated to the cap with an exact count and '
              'total days retained; full observation-segment lists are kept for cohort objects '
              '(payloads carrying a raise or an eligible cessation) and reduced to first and last '
              'for the rest. Keeping events keep their total Delta-v and drop the component '
              'breakdown; calendar years with no observed exposure are omitted and counted. '
              'Floats are rounded to six decimal places. No measured quantity is affected.'))
    with Path(str(args.output_prefix)+'.jsonl').open('x') as f:
        for r in records:f.write(json.dumps(round_floats(compact_record(r)),allow_nan=False,separators=(',',':'))+'\n')
    with Path(str(args.output_prefix)+'-receipt.json').open('x') as f:json.dump(summary,f,indent=2,allow_nan=False)
    print(json.dumps({k:v for k,v in summary.items() if k!='censusReceipt'},indent=2))


if __name__=='__main__':main()
