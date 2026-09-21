"""Offline research fixtures: missing coverage must not turn into retirement."""
import math
import importlib.util
import unittest

from tools import eol_three_arm_study as s

HAS_SCIPY=importlib.util.find_spec('scipy') is not None


def event(day,signature=s.NSK):
    t=s.epoch('2010-01-01')+day*s.DAY_MS
    return dict(startAt=s.iso(t),endAt=s.iso(t+s.DAY_MS/2),signature=signature,
                deltaV={'totalMetresPerSecond':1.0},inclinationDeg=.1)


def record(events,end=2200):
    a=s.epoch('2010-01-01')
    return dict(norad=123,name='FIXTURE',objectType='PAYLOAD',facts={'launchDate':'2000-01-01'},
                rows=end+1,rowsSha256='fixture',firstEpoch=a,lastEpoch=a+end*s.DAY_MS,
                intervals=[[a+d*s.DAY_MS,a+(d+1)*s.DAY_MS] for d in range(end)],
                monthlyInclination={},events=sorted(events,key=lambda e:e['startAt']))


class EolStudyTests(unittest.TestCase):
    def test_esa_identifiers_do_not_cross_source_namespaces(self):
        from tools.eol_esa_audit import parse
        fixture='''D.1 1981-050A Intelsat V F-1 PL
TLEs EGO (-) 2018-12-30 10:00:00 -10 400 360 440
12474 TEME 42566.967 0.0007042 14.6657 346.6551 276.5527 318.4466
D.2 1984-129A USA 7 PL
vimpel EGO (-) 2018-12-25 00:00:00 -10 400 380 420
145600 J2000 42567.500 0.0004940 15.4580 345.1960 301.0520 247.1319
'''
        x=parse(fixture,minimum=1)
        self.assertEqual(set(x),{12474})
        self.assertEqual(x[12474]['cospar'],'1981-050A')
        self.assertGreater(x[12474]['perigeeAboveGeoKm'],235)
        tight=fixture.replace('1981-050A Intelsat','1968-081AJTranstage')
        self.assertEqual(parse(tight,minimum=1)[12474]['cospar'],'1968-081AJ')

    def test_esa_disposal_year_is_not_day_confirmation(self):
        esa={123:dict(referenceDate='2019-01-01',classification='D',perigeeAboveGeoKm=300,
                      listed2018Disposal=True)}
        x=s.external_audit(123,s.epoch('2018-05-01'),{}, {},esa)
        self.assertTrue(x['disposalYearConfirmed'])
        self.assertFalse(x['historicalDateConfirmed'])
        self.assertEqual(x['assessment'],'support')
        x=s.external_audit(123,s.epoch('2010-05-01'),{}, {},esa)
        self.assertFalse(x['disposalYearConfirmed'])

    def test_current_control_contradicts_old_elevated_state(self):
        esa={123:dict(referenceDate='2019-01-01',classification='D',perigeeAboveGeoKm=300,
                      listed2018Disposal=False)}
        x=s.external_audit(123,s.epoch('2010-05-01'),{123:{'OPS_STATUS_CODE':'+'}}, {},esa)
        self.assertEqual(x['assessment'],'contradiction')
        self.assertEqual(x['esaAssessment'],'support')

    def test_calendar_launch_margin(self):
        self.assertEqual(s.iso(s.months_after(s.epoch('2020-08-31'),18))[:10],'2022-02-28')
        r=record([event(0,s.RAISE)])
        launch=s.months_after(s.epoch('2010-01-01'),-18)
        r['facts']['launchDate']=s.iso(launch)
        x=s.analyse_record(r,{}, {})
        self.assertTrue(x['raiseEvents'][0]['launchContaminated'])
        self.assertIsNone(x['arm1'])

    def test_unknown_launch_is_not_accepted(self):
        r=record([event(1500,s.RAISE)])
        r['facts']['launchDate']=None
        x=s.analyse_record(r,{}, {})
        self.assertTrue(x['raiseEvents'][0]['launchUnknown'])
        self.assertIsNone(x['arm1'])

    def test_long_spacing_with_coverage_and_hole(self):
        r=record([event(100),event(300),event(500)])
        iv=s.interval_objects(r)
        a=s.epoch('2010-01-01');b=a+600*s.DAY_MS
        w=s.window_evidence(r['events'],iv,a,b,measure=True)
        self.assertEqual(w['medianIntervalDays'],200)
        r['intervals']=[x for x in r['intervals'] if not a+350*s.DAY_MS<=x[0]<a+360*s.DAY_MS]
        w=s.window_evidence(r['events'],s.interval_objects(r),a,b,measure=True)
        self.assertEqual(w['spacingsExcludedAcrossGaps'],1)
        self.assertIsNone(w['medianIntervalDays'])

    def test_cessation_cannot_cross_hole(self):
        r=record([event(300),event(350),event(400)])
        x=s.cessation(r,s.interval_objects(r),{s.NSK},r['lastEpoch'],followup_months=24)
        self.assertTrue(x['eligible'])
        a=s.epoch('2010-01-01')
        r['intervals']=[x for x in r['intervals'] if not a+600*s.DAY_MS<=x[0]<a+610*s.DAY_MS]
        x=s.cessation(r,s.interval_objects(r),{s.NSK},r['lastEpoch'],followup_months=24)
        self.assertFalse(x['eligible'])
        self.assertIn('coverage-hole',x['reason'])

    def test_sparse_detection_is_not_a_cessation(self):
        r=record([event(300),event(400)])
        x=s.cessation(r,s.interval_objects(r),{s.NSK},r['lastEpoch'],followup_months=24)
        self.assertFalse(x['eligible'])
        self.assertIn('insufficient-prior-cadence',x['reason'])

    def test_late_hole_does_not_extend_observed_absence(self):
        r=record([event(300),event(350),event(400)])
        a=s.epoch('2010-01-01')
        r['intervals']=[iv for iv in r['intervals'] if not a+1400*s.DAY_MS<=iv[0]<a+1410*s.DAY_MS]
        x=s.cessation(r,s.interval_objects(r),{s.NSK},r['lastEpoch'],followup_months=24)
        self.assertTrue(x['eligible'])
        self.assertAlmostEqual(x['observedAbsenceDays'],999.5)
        self.assertGreater(x['calendarSinceLastDetectionDays'],x['observedAbsenceDays'])

    def test_late_restart_invalidates_terminal_cessation(self):
        r=record([event(300),event(350),event(400),event(2190)])
        x=s.analyse_record(r,{}, {})
        self.assertIsNone(x['arm2'])

    def test_no_raise_abandonment_is_separate_arm(self):
        r=record([event(300),event(350),event(400)])
        x=s.analyse_record(r,{}, {})
        self.assertIsNotNone(x['arm2'])
        self.assertEqual(x['postNsClass'],'abandonment-compatible')
        self.assertFalse(x['watchEligible'])

    def test_two_signals_have_different_leads(self):
        r=record([event(300),event(350),event(400),event(600,s.EW),
                  event(650,s.EW),event(700,s.EW),event(1100,s.RAISE)])
        x=s.analyse_record(r,{}, {})
        self.assertGreater(x['leadDays']['nsToRaise'],x['leadDays']['totalToRaise'])
        self.assertAlmostEqual(x['leadDays']['nsToRaise'],699.5)
        self.assertAlmostEqual(x['leadDays']['totalToRaise'],399.5)
        self.assertIsNone(x['arm2'])

    def test_raise_followed_by_keeping_is_retained_but_not_terminal(self):
        r=record([event(300),event(350),event(400),event(1100,s.RAISE),event(1200)])
        x=s.analyse_record(r,{}, {})
        self.assertEqual(len(x['raiseEvents']),1)
        self.assertTrue(x['nsCessation']['postRaiseRestart'])
        self.assertIsNone(x['leadDays']['nsToRaise'])

    def test_external_absence_is_unknown(self):
        x=s.external_audit(123,s.epoch('2010-01-01'),{}, {123:{'PERIGEE':36050}})
        self.assertEqual(x['assessment'],'unknown')
        self.assertFalse(x['historicalDateConfirmed'])

    def test_external_operational_contradiction_not_silently_removed(self):
        r=record([event(1100,s.RAISE)])
        x=s.analyse_record(r,{123:{'OPS_STATUS_CODE':'+','LAUNCH_DATE':'2000-01-01'}},{})
        self.assertIsNotNone(x['arm1'])
        self.assertEqual(x['raiseEvents'][0]['external']['assessment'],'contradiction')

    @unittest.skipUnless(HAS_SCIPY,'optional EOL analysis dependencies required')
    def test_inclined_ops_is_not_abandonment(self):
        events=[event(300),event(350),event(400)]
        events += [event(d,s.EW) for d in range(430,2190,60)]
        r=record(events)
        a=s.epoch('2010-01-01')
        r['monthlyInclination']={f'{y}-{m:02d}':.85*(s.epoch(f'{y}-{m:02d}-15')-a)/s.DAY_MS/365.25
                                 for y in range(2010,2017) for m in range(1,13)}
        x=s.analyse_record(r,{}, {})
        self.assertEqual(x['postNsClass'],'inclined-operations-compatible')
        self.assertIsNone(x['arm2'])

    @unittest.skipUnless(HAS_SCIPY,'optional EOL analysis dependencies required')
    def test_equivalence_requires_both_sides(self):
        x=s.paired_effect([-.01,.01]*20)
        self.assertTrue(x['tost']['equivalent'])
        x=s.paired_effect([-4,4]*10)
        self.assertGreater(x['superiorityP'],.05)
        self.assertFalse(x['tost']['equivalent'])

    @unittest.skipUnless(HAS_SCIPY,'optional EOL analysis dependencies required')
    def test_small_sample_is_not_tested(self):
        x=s.paired_effect([0,.1])
        self.assertIsNotNone(x['ci95'])
        self.assertIsNone(x['tost'])
        self.assertEqual(x['status'],'underpowered')
        self.assertIsNone(s.distribution([])['median'])
        self.assertIsNone(s.distribution([1])['medianCI95'])


    def test_compaction_keeps_the_evidence_it_truncates(self):
        node={'internalGaps':[{'from':'a','to':'b','days':d} for d in range(1,31)],
              'nested':{'internalGaps':[{'from':'a','to':'b','days':2.0}]}}
        s.trim_gaps(node)
        self.assertEqual(node['internalGapCount'],30)
        self.assertEqual(node['internalGapDays'],sum(range(1,31)))
        self.assertTrue(node['internalGapsTruncated'])
        self.assertEqual(len(node['internalGaps']),s.GAP_CAP)
        self.assertEqual(node['nested']['internalGapCount'],1)
        self.assertFalse(node['nested']['internalGapsTruncated'])

    def test_compaction_retains_segments_for_cohort_objects_only(self):
        base=dict(objectType='PAYLOAD',raiseEvents=[],arm1=None,arm2=None,
                  terminalNsCessation=dict(eligible=False),terminalTotalCessation=dict(eligible=False),
                  observationSegments=[['2010-01-01T00:00:00+00:00','2010-02-01T00:00:00+00:00'],
                                       ['2011-01-01T00:00:00+00:00','2011-02-01T00:00:00+00:00'],
                                       ['2012-01-01T00:00:00+00:00','2012-02-01T00:00:00+00:00']])
        quiet=s.compact_record(dict(base))
        self.assertEqual(quiet['observationSegmentsRetained'],'first-and-last-only')
        self.assertEqual(quiet['observationSegmentCount'],3)
        self.assertEqual(len(quiet['observationSegments']),2)
        self.assertAlmostEqual(quiet['observedSegmentDays'],31+31+31)
        cohort=s.compact_record(dict(base,arm1={'usable':False}))
        self.assertEqual(cohort['observationSegmentsRetained'],'all')
        self.assertEqual(len(cohort['observationSegments']),3)


    def test_bare_dates_are_utc_not_host_local(self):
        self.assertEqual(s.epoch('2009-12-29'),s.epoch('2009-12-29T00:00:00Z'))
        self.assertEqual(s.iso(s.epoch('2009-12-29'))[:19],'2009-12-29T00:00:00')
        # A launch-day burn a few hours after midnight UTC is not "before launch".
        self.assertGreater(s.epoch('2009-12-29T03:58:40Z'),s.epoch('2009-12-29'))


if __name__=='__main__':unittest.main()
