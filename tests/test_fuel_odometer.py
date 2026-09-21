"""Offline fixtures for the fuel odometer: a lower bound must stay a lower bound."""
import math
import unittest

from tools import fuel_odometer as o

DAY = o.DAY_MS
LAUNCH = '2010-01-01'
START = o.epoch(LAUNCH)


def event(day, signature='geo-north-south-keeping', dv=10.0, perigee=35786.0, apogee=35800.0,
          inclination=0.05):
    t = START + int(day*DAY)
    return dict(startAt=o.iso(t), endAt=o.iso(t+DAY//2), signature=signature,
                inclinationDeg=inclination, regime='GEO', confidence='candidate',
                perigeeAltitudeKm=perigee, apogeeAltitudeKm=apogee,
                deltaV={'totalMetresPerSecond': dv})


def record(events, days=3650, hole=None, regimes=None):
    intervals = [[START+d*DAY, START+(d+1)*DAY] for d in range(days)]
    if hole:
        a, b = hole
        intervals = [i for i in intervals if not (START+a*DAY <= i[0] < START+b*DAY)]
    return dict(norad=1, name='FIXTURE', objectType='PAYLOAD',
                facts={'launchDate': LAUNCH}, rows=days, rowsSha256='fixture',
                intervals=intervals, firstEpoch=intervals[0][0], lastEpoch=intervals[-1][1],
                regimes=regimes or {'GEO': days}, events=sorted(events, key=lambda e: e['startAt']))


def entry(**over):
    base = dict(name='FIXTURE', norad=1, cospar='2010-001A', bus='TEST', launch_date=LAUNCH,
                launch_mass_kg=1000.0, dry_mass_kg=None, confidence='datasheet',
                sk_propulsion={'type': 'MMH/NTO biprop', 'isp_range_s': [300, 320]},
                raising_propulsion={'type': 'apogee motor', 'isp_range_s': [310, 315]},
                sources=[])
    base.update(over)
    return base


class OdometerTests(unittest.TestCase):
    def test_low_isp_is_the_high_burn_edge(self):
        x = o.analyse_object(entry(), record([event(800, dv=100.0)]))
        low, high = x['burnedKgIspBand']
        self.assertLess(low, high)
        self.assertAlmostEqual(low, 1000*(1-math.exp(-100/(320*o.G0))), places=6)
        self.assertAlmostEqual(high, 1000*(1-math.exp(-100/(300*o.G0))), places=6)
        self.assertEqual(x['burnedKgLowerBound'], low)
        self.assertTrue(x['cumulativeIsAtLeast'])

    def test_raising_isp_only_for_raising_signatures_in_the_window(self):
        events = [event(10, 'inclination-change', dv=1400.0, perigee=250.0, apogee=35700.0),
                  event(20, 'geo-north-south-keeping', dv=10.0),
                  event(900, 'inclination-change', dv=50.0)]
        x = o.analyse_object(entry(), record(events))
        self.assertEqual(x['legCounts'], {'raising': 1, 'stationKeeping': 2})
        self.assertAlmostEqual(x['legDeltaVMps']['raising'], 1400.0)
        self.assertAlmostEqual(x['legDeltaVMps']['stationKeeping'], 60.0)

    def test_no_raising_leg_prices_everything_on_station_keeping(self):
        events = [event(10, 'inclination-change', dv=100.0)]
        x = o.analyse_object(entry(raising_propulsion=None), record(events))
        self.assertEqual(x['legCounts'], {'stationKeeping': 1})

    def test_pre_launch_and_over_ceiling_events_are_excluded_but_published(self):
        events = [event(-30, 'inclination-change', dv=500.0),
                  event(5, 'inclination-change', dv=9000.0),
                  event(900, dv=20.0)]
        x = o.analyse_object(entry(), record(events))
        reasons = {e['reason'] for e in x['eventsExcludedAsNotOwnPropulsion']}
        self.assertEqual(reasons, {'starts-before-catalogued-launch-date',
                                   'single-event-delta-v-above-ceiling'})
        self.assertEqual(x['eventsPriced'], 1)
        self.assertAlmostEqual(x['totalDeltaVMpsLowerBound'], 20.0)
        self.assertAlmostEqual(x['deltaVMpsExcludedAsNotOwnPropulsion'], 9500.0)
        # The unfiltered integration stays visible, so the rule cannot hide anything.
        self.assertAlmostEqual(x['withoutCeiling']['totalDeltaVMpsLowerBound'], 9520.0)
        self.assertGreater(x['withoutCeiling']['burnedFractionOfLaunchMass'][0],
                           x['burnedFractionOfLaunchMass'][0])

    def test_non_propulsive_signatures_never_burn_fuel(self):
        events = [event(800, 'drag-decay', dv=500.0), event(900, 'unclassified-change', dv=500.0)]
        x = o.analyse_object(entry(), record(events))
        self.assertEqual(x['eventsPropulsive'], 0)
        self.assertEqual(x['burnedKgLowerBound'], 0.0)
        sensitivity = o.analyse_object(entry(), record(events), sensitivity=True)
        self.assertEqual(sensitivity['eventsPropulsive'], 1)
        self.assertGreater(sensitivity['burnedKgLowerBound'], 0.0)

    def test_remaining_is_an_upper_bound_and_absent_without_dry_mass(self):
        events = [event(800, dv=100.0)]
        x = o.analyse_object(entry(), record(events))
        self.assertIsNone(x['propellantRemainingUpperBoundKg'])
        self.assertNotIn('propellantCapacityKg', x)
        y = o.analyse_object(entry(dry_mass_kg=600.0), record(events))
        self.assertEqual(y['propellantCapacityKg'], 400.0)
        # Upper bound uses the LOW-burn edge, so it is the largest remaining consistent with data.
        self.assertAlmostEqual(y['propellantRemainingUpperBoundKg'],
                               400.0-y['burnedKgIspBand'][0], places=6)
        self.assertFalse(y['remainingExceedsCapacity'])

    def test_coverage_hole_is_counted_and_never_interpolated(self):
        r = record([event(800, dv=10.0)], hole=(1000, 1400))
        x = o.analyse_object(entry(), r)
        self.assertEqual(x['coverage']['holeCount'], 1)
        self.assertAlmostEqual(x['coverage']['holeDays'], 400, delta=2)
        self.assertLess(x['coverage']['observedDays'], x['coverage']['calendarSpanDays'])
        self.assertTrue(x['crossPrediction']['atLeastBecauseOfCoverageHoles'])
        # Gap-aware station years never count the hole.
        self.assertLess(x['sanity']['observedStationYears'], x['sanity']['calendarStationYears'])

    def test_folklore_anchor_is_gap_aware_and_flags_the_gap(self):
        # Ten years of 50 m/s/yr would be 500 m/s; two detected 10 m/s burns is 4%.
        x = o.analyse_object(entry(), record([event(800, dv=10.0), event(1200, dv=10.0)]))
        self.assertTrue(x['sanity']['isGeo'])
        self.assertAlmostEqual(x['sanity']['stationKeepingDeltaVMpsLowerBound'], 20.0)
        self.assertLess(x['sanity']['explainedFractionOfFolkloreBudget'], 0.1)
        self.assertEqual(x['sanity']['flag'], 'far-below-folklore-detection-gap')

    def test_electric_station_keeping_is_flagged_as_structurally_blind(self):
        x = o.analyse_object(entry(sk_propulsion={'type': 'electric ion (xenon, gridded)',
                                                  'isp_range_s': [3400, 3500]}),
                             record([event(800, dv=10.0)]))
        self.assertTrue(x['electricStationKeeping'])
        self.assertTrue(x['stepDetectorBlindToContinuousBurns'])
        self.assertEqual(x['sanity']['flag'], 'electric-station-keeping-step-detector-blind')

    def test_unresolved_isp_band_is_flagged_not_averaged(self):
        x = o.analyse_object(entry(sk_propulsion={'type': 'UNRESOLVED: A2100',
                                                  'isp_range_s': [210, 615]}),
                             record([event(800, dv=100.0)]))
        self.assertTrue(x['ispUnresolved'])
        self.assertEqual(x['ispBandSeconds'], [210.0, 615.0])
        self.assertGreater(x['massBandWidthKg'], 0)
        low, high = x['burnedKgIspBand']
        self.assertAlmostEqual(low, 1000*(1-math.exp(-100/(615*o.G0))), places=6)
        self.assertAlmostEqual(high, 1000*(1-math.exp(-100/(210*o.G0))), places=6)

    def test_plausibility_is_flagged_never_corrected(self):
        x = o.analyse_object(entry(), record([event(800, dv=2000.0), event(900, dv=2000.0)]),
                             plausibility_ceiling=0.6)
        self.assertTrue(x['burnedFractionExceedsCataloguePlausibility'])
        self.assertGreater(x['burnedKgLowerBound'], 600.0)  # flagged, not clipped
        self.assertEqual(x['plausibilityCeilingFraction'], 0.6)
        below = o.analyse_object(entry(), record([event(800, dv=2000.0)]),
                                 plausibility_ceiling=0.6)
        self.assertFalse(below['burnedFractionExceedsCataloguePlausibility'])

    def test_missing_inputs_exclude_rather_than_guess(self):
        self.assertEqual(o.analyse_object(entry(launch_mass_kg=None),
                                          record([event(800)]))['excluded'], 'no-launch-mass')
        self.assertEqual(o.analyse_object(entry(sk_propulsion={'type': 'unknown'}),
                                          record([event(800)]))['excluded'], 'no-catalogued-isp')
        self.assertEqual(o.analyse_object(entry(), None)['excluded'], 'no-archive-record')

    def test_rounding_does_not_change_structure(self):
        self.assertEqual(o.round_floats({'a': [1.123456789, 2], 'b': {'c': 3.000000001}}),
                         {'a': [1.123457, 2], 'b': {'c': 3.0}})

    def test_non_geo_object_is_not_measured_against_a_geo_rule(self):
        x = o.analyse_object(entry(), record([event(800, 'along-track-raise', dv=5.0)],
                                             regimes={'LEO': 3650}))
        self.assertFalse(x['sanity']['isGeo'])
        self.assertEqual(x['sanity']['flag'], 'not-geo-folklore-does-not-apply')


if __name__ == '__main__':
    unittest.main()
