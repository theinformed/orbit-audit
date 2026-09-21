"""Pre-registered high-inclination corroboration and checkpoint continuity."""
from dataclasses import asdict, replace
import contextlib
import io
import math
import os
import pickle
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np
from pipeline import orbit_campaigns as oc
from pipeline import orbit_sweep_gpu as gpu
from test_orbit_campaigns import BASE_MS, DAY_MS, series, intervals
from test_orbit_sweep_gpu import oracle


def inclination_rows(inclination=51.6, energy=None, geo=False):
    rows = series(inclination_deg=inclination,
                  a_km=42164 if geo else oc.RE_WGS72 + 700,
                  decay_metres_per_day=0,
                  steps={30: 3000} if energy == 'a' else {},
                  spikes={30: 3000} if energy == 'spike' else {})
    return [(t, mm, e + (0.01 if energy == 'e' and t >= BASE_MS + 30 * DAY_MS else 0),
             i + (0.2 if t >= BASE_MS + 30 * DAY_MS else 0), b) for t, mm, e, i, b in rows]


def detect(data, **kw):
    with contextlib.redirect_stderr(io.StringIO()):
        return oc.detect_object_events(data, kappa=32, **kw)


class CorroborationTests(unittest.TestCase):
    def test_boundary_and_both_energy_channels(self):
        for inc in (0.0, 0.5, math.nextafter(30.0, 0), 30.0, 60.0, 98.0, 180.0):
            for energy in (None, 'a', 'e', 'spike'):
                with self.subTest(inclination=inc, energy=energy):
                    data = intervals(inclination_rows(inc, energy))
                    before = detect(data, _inclination_corroboration=False)
                    self.assertTrue(before)
                    diagnostics = {}
                    after = detect(data, diagnostics=diagnostics)
                    decline = inc >= 30 and energy in (None, 'spike')
                    self.assertEqual(diagnostics['inclinationUncorroborated'], int(decline))
                    if decline:
                        self.assertFalse(after)
                    else:
                        self.assertEqual(before, after)

    def test_geo_north_south_keeping_unchanged(self):
        data = intervals(inclination_rows(0.3, geo=True))
        before = detect(data, _inclination_corroboration=False)
        self.assertEqual([e.signature for e in before], ['geo-north-south-keeping'])
        self.assertEqual(before, detect(data))

    def test_node_is_not_an_energy_corroborator(self):
        data = intervals(inclination_rows())
        result = oracle(data, 32)
        pos = np.flatnonzero(result.inclination_uncorroborated)[0]
        tests = result.channel_tests(pos, result.baseline_rows()[pos])
        tests.append(replace(next(t for t in tests if t.element == 'inclination'), element='raan'))
        self.assertTrue(oc._inclination_uncorroborated(data[pos], tests))

    def test_injected_gpu_corroboration_flip_aborts(self):
        data = intervals(inclination_rows())
        result = oracle(data, 32)
        pos = np.flatnonzero(result.inclination_uncorroborated)[0]
        result.inclination_uncorroborated[pos] = False
        with mock.patch.object(gpu.Backend, 'start'), \
                mock.patch.object(gpu.Backend, 'analyze', return_value=result), gpu.Verification() as v:
            with self.assertRaisesRegex(gpu.AgreementError, 'corroboration flag'):
                detect(data, gpu_verifier=v)
            self.assertEqual(v.fallback_objects, 0)

    def test_execution_consumes_gpu_corroboration_without_cpu_policy(self):
        data = intervals(inclination_rows())
        result = oracle(data, 32)
        with mock.patch.object(gpu.Backend, 'start'), \
                mock.patch.object(gpu.Backend, 'analyze', return_value=result), \
                mock.patch.object(oc, '_inclination_uncorroborated', side_effect=AssertionError('CPU policy')), \
                gpu.Execution() as executor:
            self.assertFalse(detect(data, gpu_executor=executor))

    def _archive(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        db = sqlite3.connect(Path(directory.name) / 'fixture.sqlite3')
        self.addCleanup(db.close)
        db.executescript('''PRAGMA journal_mode=WAL;
            CREATE TABLE object(norad INTEGER PRIMARY KEY,name TEXT,object_type TEXT);
            CREATE TABLE element_set(norad INTEGER,epoch_ms INTEGER,mean_motion_q INTEGER,
                eccentricity_q INTEGER,inclination_q INTEGER,bstar_q INTEGER,
                raan_q INTEGER,arg_perigee_q INTEGER,PRIMARY KEY(norad,epoch_ms)) WITHOUT ROWID;''')
        for n, kind in ((1, 'DEBRIS'), (2, 'PAYLOAD')):
            db.execute('INSERT INTO object VALUES(?,?,?)', (n, str(n), kind))
            db.executemany('INSERT INTO element_set VALUES(?,?,?,?,?,?,0,0)',
                           [(n,t,round(mm*1e8),round(e*1e8),round(i*1e4),round(b*1e12))
                            for t,mm,e,i,b in inclination_rows()])
        db.commit()
        return db

    def test_serial_parallel_abstention_counts_reconcile(self):
        db = self._archive()
        with contextlib.redirect_stderr(io.StringIO()):
            serial = oc.sweep_archive(db, workers=1, columnar_root=False).passed
            parallel = oc.sweep_archive(db, workers=2, columnar_root=False).passed
        self.assertEqual(asdict(serial), asdict(parallel))
        self.assertEqual(serial.inclination_uncorroborated, 2)
        for breakdown in (serial.passive_breakdown, serial.payload_breakdown):
            self.assertEqual(breakdown['abstention']['inclinationUncorroborated'], 1)
        control = oc.control_rates_by_object(serial, kappa=32)['inclinationUncorroborated']
        self.assertEqual(control['intervals'], 2)
        self.assertIn('unconfirmed', control['reason'])
        self.assertIsNone(control['gap'])

    def test_old_checkpoint_finishes_original_policy_and_fresh_sweep_changes(self):
        db = self._archive()
        old = oc.ArchivePass(objects_scanned=68000, passive_intervals=12345, passive_flags=67)
        del old.inclination_corroboration
        del old.inclination_uncorroborated
        old = pickle.loads(pickle.dumps(old))
        self.assertFalse(old.inclination_corroboration)
        for workers in (1, 2):
            with contextlib.redirect_stderr(io.StringIO()):
                resumed = oc.sweep_archive(db, workers=workers, into=pickle.loads(pickle.dumps(old)),
                                          columnar_root=False).passed
            self.assertEqual(resumed.objects_scanned, 68002)
            self.assertEqual(resumed.passive_flags, 68)
            self.assertEqual(resumed.payload_flags, 1)
            self.assertEqual(resumed.inclination_uncorroborated, 0)
            control = oc.control_rates_by_object(resumed, kappa=32)['inclinationUncorroborated']
            self.assertFalse(control['enabled'])
            self.assertIsNone(control['intervals'])
            self.assertIn('legacy checkpoint', control['gap'])
        with self.assertRaisesRegex(ValueError, 'different inclination'):
            old.merge(oc.ArchivePass(objects_scanned=1))


    def test_legacy_checkpoint_policy_survives_columnar_dispatch(self):
        db = self._archive()
        root = Path(tempfile.mkdtemp())
        import shutil
        self.addCleanup(shutil.rmtree, root)
        for workers in (1, 2):
            old = oc.ArchivePass(inclination_corroboration=False,
                                 objects_scanned=68000, passive_flags=67,
                                 passive_intervals=12345)
            with contextlib.redirect_stderr(io.StringIO()):
                resumed = oc.sweep_archive(db, workers=workers, into=old,
                                          columnar_root=root).passed
            self.assertFalse(resumed.inclination_corroboration)
            self.assertEqual(resumed.passive_flags, 68)
            self.assertEqual(resumed.payload_flags, 1)
            self.assertTrue(all(not s.inclination_corroboration
                                for s in resumed.strata.values()))

    def test_legacy_checkpoint_keeps_raw_gpu_trips(self):
        db = self._archive()
        old = oc.ArchivePass(inclination_corroboration=False)
        with mock.patch.object(gpu.Backend, 'start'), \
                mock.patch.object(gpu.Backend, 'analyze', side_effect=oracle), \
                contextlib.redirect_stderr(io.StringIO()):
            resumed = oc.sweep_archive(db, into=old, gpu_devices=(0,),
                                      columnar_root=False).passed
        self.assertEqual(resumed.passive_flags, 1)
        self.assertEqual(resumed.payload_flags, 1)
        self.assertEqual(resumed.inclination_uncorroborated, 0)

@unittest.skipUnless(os.environ.get('ORBIT_SWEEP_GPU_TEST') == '1', 'opt-in CUDA sweep fixtures')
class RealCorroborationTests(unittest.TestCase):
    def test_real_gpu_boundary_persistence_and_geo(self):
        device = int(os.environ.get('ORBIT_SWEEP_GPU_DEVICE', '0'))
        with gpu.Verification((device,), 320) as verifier, gpu.Execution((device,), 320) as executor:
            for inc, energy, geo in ((29.9999,None,False), (30,None,False),
                                    (98,'a',False), (98,'e',False), (98,'spike',False),
                                    (0.3,None,True)):
                data = intervals(inclination_rows(inc, energy, geo))
                expected = detect(data)
                self.assertEqual(expected, detect(data, gpu_verifier=verifier))
                actual = detect(data, gpu_executor=executor)
                self.assertEqual([e.start_ms for e in expected], [e.start_ms for e in actual])
                self.assertEqual([e.signature for e in expected], [e.signature for e in actual])
            self.assertEqual(verifier.report()['outcome'], 'agreement')
            self.assertEqual(executor.report()['outcome'], 'gpu')
            self.assertEqual(verifier.inclination_abstentions, 2)
