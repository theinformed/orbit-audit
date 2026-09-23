"""Tests for the T16b truth-set instruments.

Offline: every fixture is written in the test. The two live checks -- the
spacecraft-to-NORAD map against the archive's own object table, and the
propagator bridge -- skip themselves when the archive or node is absent
rather than passing silently.
"""
from __future__ import annotations

import datetime as dt
import json
import math
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import vendor_names  # noqa: E402  the names, kept out of this file

import truthset_truth as tt                                     # noqa: E402
import truthset_growth as tg                                    # noqa: E402
import truthset_recall as tr                                    # noqa: E402

MU = 3.986004418e14


class TestSp3Parser(unittest.TestCase):
    """SP3-c: kilometres, decimetres per second, TAI tags, ITRF."""

    HEADER = (
        "#cV2023  1  8 21 56  0.00000000   13109 ORBIT ITRF  FIT CNES\n"
        "## 2244  78960.00000000    60.00000000 59952 0.9138888888889\n"
        "%c L  cc TAI ccc cccc cccc cccc cccc ccccc ccccc ccccc ccccc\n"
    )

    def _write(self, body: str) -> Path:
        path = Path(self.tmp.name) / "arc.sp3"
        path.write_text(self.HEADER + body)
        return path

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_units_and_time_system(self):
        body = ("*  2023  1  8 21 56  0.00000000\n"
                "PL74 -2650.9150549 -1055.6849831  6581.4662751999999.9999990\n"
                "VL74-70027.6215408  4629.4598382-27408.1513641999999.9999990\n")
        t, pos, vel = tt.parse_sp3(self._write(body))
        self.assertEqual(t.size, 1)
        # kilometres -> metres
        self.assertAlmostEqual(pos[0][0], -2650915.0549, places=3)
        # decimetres per second -> metres per second
        self.assertAlmostEqual(vel[0][0], -7002.76215408, places=6)
        # TAI tag 21:56:00 is UTC 21:55:23 in the 37 s era
        want = dt.datetime(2023, 1, 8, 21, 55, 23, tzinfo=dt.timezone.utc)
        self.assertEqual(int(t[0]), int(want.timestamp() * 1000))

    def test_a_non_itrf_header_is_refused(self):
        path = Path(self.tmp.name) / "bad.sp3"
        path.write_text("#cV2023  1  8 21 56  0.00000000   1 ORBIT WGS84 FIT X\n"
                        "*  2023  1  8 21 56  0.00000000\n"
                        "PL74     1.0000000     2.0000000     3.0000000\n"
                        "VL74     1.0000000     2.0000000     3.0000000\n")
        with self.assertRaises(ValueError):
            tt.parse_sp3(path)

    def test_a_position_without_a_velocity_is_not_emitted(self):
        body = ("*  2023  1  8 21 56  0.00000000\n"
                "PL74     1.0000000     2.0000000     3.0000000\n"
                "*  2023  1  8 21 57  0.00000000\n"
                "PL74     1.0000000     2.0000000     3.0000000\n"
                "VL74     1.0000000     2.0000000     3.0000000\n")
        t, _pos, _vel = tt.parse_sp3(self._write(body))
        self.assertEqual(t.size, 1)


class TestLeapSeconds(unittest.TestCase):
    def test_eras(self):
        self.assertEqual(tt.tai_minus_utc(dt.datetime(2023, 6, 1, tzinfo=dt.timezone.utc)), 37.0)
        self.assertEqual(tt.tai_minus_utc(dt.datetime(2016, 6, 1, tzinfo=dt.timezone.utc)), 36.0)
        self.assertEqual(tt.tai_minus_utc(dt.datetime(2013, 1, 1, tzinfo=dt.timezone.utc)), 35.0)

    def test_before_the_registered_eras_is_an_error_not_a_guess(self):
        with self.assertRaises(ValueError):
            tt.tai_minus_utc(dt.datetime(1990, 1, 1, tzinfo=dt.timezone.utc))


class TestEofParser(unittest.TestCase):
    XML = """<?xml version="1.0" ?>
<Earth_Explorer_File><Earth_Explorer_Header><Variable_Header>
<Ref_Frame>EARTH_FIXED</Ref_Frame><Time_Reference>UTC</Time_Reference>
</Variable_Header></Earth_Explorer_Header>
<Data_Block type="xml"><List_of_OSVs count="1"><OSV>
<TAI>TAI=2022-12-11T23:00:19.000000</TAI>
<UTC>UTC=2022-12-11T22:59:42.000000</UTC>
<UT1>UT1=2022-12-11T22:59:41.981875</UT1>
<Absolute_Orbit>+46290</Absolute_Orbit>
<X unit="m">-818257.346109</X>
<Y unit="m">5402798.403886</Y>
<Z unit="m">-4503240.869555</Z>
<VX unit="m/s">2462.292750</VX>
<VY unit="m/s">-4364.688307</VY>
<VZ unit="m/s">-5689.747049</VZ>
</OSV></List_of_OSVs></Data_Block></Earth_Explorer_File>
"""

    def test_reads_utc_and_metres(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "a.EOF"
            path.write_text(self.XML)
            t, pos, vel = tt.parse_eof(path)
        self.assertEqual(t.size, 1)
        want = dt.datetime(2022, 12, 11, 22, 59, 42, tzinfo=dt.timezone.utc)
        self.assertEqual(int(t[0]), int(want.timestamp() * 1000))
        self.assertAlmostEqual(pos[0][1], 5402798.403886, places=5)
        self.assertAlmostEqual(vel[0][2], -5689.747049, places=6)

    def test_the_utc_tag_is_used_and_not_the_tai_one(self):
        """The two tags differ by 37 s in the file; reading the wrong one puts
        every comparison 37 s -- about 280 km of along-track -- out."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "a.EOF"
            path.write_text(self.XML)
            t, _p, _v = tt.parse_eof(path)
        tai = dt.datetime(2022, 12, 11, 23, 0, 19, tzinfo=dt.timezone.utc)
        self.assertNotEqual(int(t[0]), int(tai.timestamp() * 1000))


class TestEarthOrientation(unittest.TestCase):
    ROW = ("73 1 2 41684.00 I  0.120733 0.009786  0.136966 0.015902  "
           "I 0.8084178 0.0002710  0.0000 0.1916  P    44.969     .500\n"
           "73 1 3 41685.00 I  0.118980 0.011039  0.135656 0.013616  "
           "I 0.8056163 0.0002710  3.5563 0.1916  P    45.005     .500\n")

    def test_columns(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "finals"
            path.write_text(self.ROW)
            mjd, xp, yp, dut1 = tt.parse_eop(path)
        self.assertEqual(list(mjd), [41684.0, 41685.0])
        self.assertAlmostEqual(xp[0], 0.120733)
        self.assertAlmostEqual(yp[0], 0.136966)
        self.assertAlmostEqual(dut1[0], 0.8084178)

    def test_interpolation_and_refusal_outside_the_series(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "finals"
            path.write_text(self.ROW)
            eop = tt.EarthOrientation(path)
            mid = (41684.5 - eop.MJD_UNIX_EPOCH) * 86400000.0
            xp, _yp, _d = eop.at_ms(np.asarray([mid]))
            self.assertAlmostEqual(float(xp[0]), (0.120733 + 0.118980) / 2, places=6)
            with self.assertRaises(ValueError):
                eop.at_ms(np.asarray([0.0]))


class TestFrames(unittest.TestCase):
    def test_polar_motion_matches_the_explicit_rotations(self):
        r = np.asarray([7000000.0, 100.0, -250.0])
        xp, yp = 0.25, -0.31
        got = tt.pef_to_itrf(r, xp, yp)
        x = xp * tt.ARCSEC
        y = yp * tt.ARCSEC
        r2 = np.asarray([[math.cos(-x), 0.0, -math.sin(-x)],
                         [0.0, 1.0, 0.0],
                         [math.sin(-x), 0.0, math.cos(-x)]])
        r1 = np.asarray([[1.0, 0.0, 0.0],
                         [0.0, math.cos(-y), math.sin(-y)],
                         [0.0, -math.sin(-y), math.cos(-y)]])
        want = r2 @ (r1 @ r)
        self.assertLess(float(np.linalg.norm(got - want)), 1e-3)

    def test_the_polar_motion_correction_is_the_size_the_design_derives(self):
        """0.3 arcsec at 7.2e6 m is about 10 m: the number the registration
        uses to justify applying it rather than neglecting it."""
        r = np.asarray([7200000.0, 0.0, 0.0])
        shifted = tt.pef_to_itrf(r, 0.0, 0.3)
        self.assertAlmostEqual(float(np.linalg.norm(shifted - r)), 0.0, places=6)
        r_z = np.asarray([0.0, 0.0, 7200000.0])
        shifted_z = tt.pef_to_itrf(r_z, 0.3, 0.0)
        self.assertAlmostEqual(float(np.linalg.norm(shifted_z - r_z)), 10.47, places=1)

    def test_rtn_basis_is_orthonormal_and_oriented(self):
        r = np.asarray([7000000.0, 0.0, 0.0])
        v = np.asarray([0.0, 7500.0, 0.0])
        radial, along, cross = tt.rtn_basis(r, v)
        for vec in (radial, along, cross):
            self.assertAlmostEqual(float(np.linalg.norm(vec)), 1.0, places=12)
        self.assertAlmostEqual(float(np.dot(radial, along)), 0.0, places=12)
        self.assertAlmostEqual(float(np.dot(radial, cross)), 0.0, places=12)
        self.assertGreater(float(np.dot(along, v)), 0.0)

    def test_semi_major_axis_of_a_circular_orbit_is_its_radius(self):
        radius = 7000000.0
        speed = math.sqrt(MU / radius)
        # an Earth-fixed velocity whose inertial value is the circular speed
        r = np.asarray([radius, 0.0, 0.0])
        v = np.asarray([0.0, speed - tt.OMEGA_EARTH * radius, 0.0])
        self.assertAlmostEqual(float(tt.semi_major_axis_m(r, v)) / radius, 1.0,
                               places=9)


class TestGrowthStatistics(unittest.TestCase):
    def test_crossing_is_interpolated_between_the_bracketing_horizons(self):
        horizons = [0, 1, 3, 7]
        medians = [None, 1.0, 2.0, 4.0]
        got = tg.crossing_horizon(medians, horizons, 3.0)
        self.assertTrue(got["crossed"])
        self.assertEqual(got["bracket"], [3, 7])
        # log-log interpolation of a power law through (3, 2) and (7, 4)
        want = 3.0 * (7.0 / 3.0) ** (math.log(1.5) / math.log(2.0))
        self.assertAlmostEqual(got["horizonDays"], want, places=9)

    def test_no_crossing_is_a_sentence_and_never_an_extrapolation(self):
        got = tg.crossing_horizon([None, 0.01, 0.02], [0, 1, 3], 5.0)
        self.assertFalse(got["crossed"])
        self.assertIn("no extrapolation", got["note"])
        self.assertNotIn("horizonDays", got)

    def test_already_above_at_the_first_horizon_is_labelled(self):
        got = tg.crossing_horizon([None, 9.0, 12.0], [0, 1, 3], 5.0)
        self.assertTrue(got["crossed"])
        self.assertTrue(got["beforeFirstHorizon"])

    def test_ids_manoeuvre_records_parse_to_their_reported_start(self):
        line = ("SEN3A 2016 053 09 30 2016 053 12 11     006 2 2016 053 09 30 "
                "26.812 03.16e+01 -1.02e-06 -1.79e-02 0 0 0 0 0 0 0\n")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "s3aman.txt"
            path.write_text(line + "SEN3B 2016 053 09 30 2016 053 12 11     006 1 x\n")
            got = tg.parse_ids_manoeuvres(path, "SEN3A")
        want = dt.datetime(2016, 2, 22, 9, 30, tzinfo=dt.timezone.utc)
        self.assertEqual(got, [int(want.timestamp() * 1000)])


class TestRecallStatistics(unittest.TestCase):
    def test_wilson_interval(self):
        lo, hi = tr.wilson(90, 1134)
        self.assertAlmostEqual(lo, 0.0650, places=3)
        self.assertAlmostEqual(hi, 0.0966, places=3)
        self.assertIsNone(tr.wilson(0, 0))
        lo, hi = tr.wilson(0, 30)
        self.assertEqual(lo, 0.0)
        self.assertGreater(hi, 0.0)

    def test_campaign_chaining_uses_the_shipped_gap(self):
        day = tr.DAY_MS
        flags = np.asarray([0, 10 * day, 20 * day,
                            20 * day + int(181 * day), 0 + int(400 * day)],
                           dtype=np.int64)
        starts = tr.campaign_starts(flags)
        self.assertEqual(starts.size, 3)
        self.assertEqual(int(starts[0]), 0)

    def test_burn_size_bins_are_closed_and_exhaustive(self):
        self.assertEqual(tr.bin_of(0.0, tr.DA_BINS), "0-20 m")
        self.assertEqual(tr.bin_of(19.99, tr.DA_BINS), "0-20 m")
        self.assertEqual(tr.bin_of(20.0, tr.DA_BINS), "20-50 m")
        self.assertEqual(tr.bin_of(4000.0, tr.DA_BINS), ">=500 m")
        self.assertEqual(tr.bin_of(None, tr.DA_BINS), "unknown")

    def test_detector_floor_reproduces_its_own_derivation(self):
        """|da|min = (2/3)(a/n) thr_n and dv = da n_ang / 2, computed here a
        second time from the elements rather than read back from the tool."""
        n = 14.3
        epochs = np.arange(0, 40) * int(tr.DAY_MS)
        el = {"epoch_ms": epochs.astype(np.int64),
              "n": np.full(40, n),
              "e": np.zeros(40),
              "inc": np.full(40, 98.6),
              "raan": np.zeros(40)}
        got = tr.detector_floor(el, tr.POOLED_SIGMA_N, tr.POOLED_SIGMA_THETA)
        a_km = float((MU / 1e9 / (2 * math.pi * n / 86400.0) ** 2) ** (1 / 3))
        thr = 5.0 * tr.POOLED_SIGMA_N
        want_da = (2.0 / 3.0) * (a_km / n) * thr * 1000.0
        self.assertAlmostEqual(got["minDetectableDaMetres"], want_da, places=6)
        n_ang = 2 * math.pi * n / 86400.0
        self.assertAlmostEqual(got["minDetectableDvMps"], want_da * n_ang / 2,
                               places=9)
        self.assertEqual(got["thresholdSetBy"], "fitNoise")

    def test_the_floor_falls_back_to_the_fifty_metre_term_when_noise_is_tiny(self):
        n = 14.3
        el = {"epoch_ms": (np.arange(0, 40) * int(tr.DAY_MS)).astype(np.int64),
              "n": np.full(40, n), "e": np.zeros(40),
              "inc": np.full(40, 98.6), "raan": np.zeros(40)}
        got = tr.detector_floor(el, 1e-9, 0.01)
        self.assertEqual(got["thresholdSetBy"], "floor")
        self.assertAlmostEqual(got["minDetectableDaMetres"], 50.0, places=6)

    def test_bracketed_delta_a_uses_the_sets_outside_the_window(self):
        day = int(tr.DAY_MS)
        el = {"epoch_ms": np.asarray([0, day, 2 * day, 3 * day], dtype=np.int64),
              "n": np.asarray([14.3, 14.3, 14.29, 14.29]),
              "e": np.zeros(4), "inc": np.full(4, 98.6), "raan": np.zeros(4)}
        got = tr.bracketed_da_metres(el, day + 1, 2 * day - 1)
        a0 = float((MU / 1e9 / (2 * math.pi * 14.3 / 86400.0) ** 2) ** (1 / 3))
        a1 = float((MU / 1e9 / (2 * math.pi * 14.29 / 86400.0) ** 2) ** (1 / 3))
        self.assertAlmostEqual(got, abs(a1 - a0) * 1000.0, places=3)
        self.assertIsNone(tr.bracketed_da_metres(el, -day, 4 * day))


class TestProseHygiene(unittest.TestCase):
    """No product or assistant names anywhere in the instruments or their
    outputs -- the repository's standing rule."""

    BANNED = vendor_names.BANNED

    def test_no_tool_names_in_the_truthset_sources(self):
        targets = sorted((REPO / "tools").glob("truthset_*"))
        targets += sorted((REPO / "docs").glob("t16b-truthset-*"))
        self.assertGreaterEqual(len(targets), 5)
        for path in targets:
            text = path.read_text(errors="replace").lower()
            for word in self.BANNED:
                # assertFalse, not assertNotIn: a failure should name the file
                # and the word, not print the whole source back
                self.assertFalse(word in text, f"{path.name} contains {word!r}")


class TestLiveMapping(unittest.TestCase):
    ARCHIVE = tr.ARCHIVE

    @unittest.skipUnless(ARCHIVE.exists(), "element archive not present")
    def test_every_spacecraft_id_maps_to_the_archive_object_it_names(self):
        db = sqlite3.connect(f"file:{self.ARCHIVE}?mode=ro", uri=True)
        expect = {
            "cryosat-2": "CRYOSAT", "hy-2a": "HAIYANG", "jason-1": "JASON",
            "jason-2": "JASON 2", "jason-3": "JASON 3", "saral": "SARAL",
            "sentinel-3a": "SENTINEL 3A", "sentinel-3b": "SENTINEL 3B",
            "sentinel-6a": "S6", "swot": "SWOT", "topex-poseidon": "TOPEX",
        }
        for sat, norad in tr.SAT_NORAD.items():
            row = db.execute("SELECT name FROM object WHERE norad=?",
                             (norad,)).fetchone()
            self.assertIsNotNone(row, f"{sat}: {norad} absent from the archive")
            self.assertIn(expect[sat], row[0].upper(),
                          f"{sat}: {norad} is named {row[0]!r}")
        db.close()


class TestPropagatorBridge(unittest.TestCase):
    NODE = tg.NODE

    @unittest.skipUnless(NODE.exists(), "node not present")
    def test_a_circular_orbit_comes_back_at_the_right_radius(self):
        """One element set, one instant: the bridge returns a position in the
        Earth-fixed frame whose radius is the orbit's own."""
        omm = {
            "NORAD_CAT_ID": 25544, "EPOCH": "2023-01-01T00:00:00.000",
            "MEAN_MOTION": 15.5, "ECCENTRICITY": 0.0001,
            "INCLINATION": 51.6, "RA_OF_ASC_NODE": 100.0,
            "ARG_OF_PERICENTER": 0.0, "MEAN_ANOMALY": 0.0,
            "BSTAR": 0.0001, "MEAN_MOTION_DOT": 0.0, "MEAN_MOTION_DDOT": 0.0,
        }
        t_ms = int(dt.datetime(2023, 1, 1, 1, 0, tzinfo=dt.timezone.utc).timestamp() * 1000)
        payload = json.dumps({"jobs": [{"id": 0, "omm": omm,
                                        "samples": [{"t": t_ms, "gmstMs": t_ms}]}]})
        proc = subprocess.run([str(self.NODE), str(tg.BRIDGE)],
                              input=payload.encode(), capture_output=True,
                              cwd=str(REPO))
        self.assertEqual(proc.returncode, 0, proc.stderr.decode()[:400])
        row = json.loads(proc.stdout.decode())["results"][0]
        self.assertTrue(row["ok"], row)
        radius = math.sqrt(sum(c * c for c in row["pef"]))
        expected = (MU / 1e9 / (2 * math.pi * 15.5 / 86400.0) ** 2) ** (1 / 3)
        self.assertLess(abs(radius - expected), 40.0)


if __name__ == "__main__":
    unittest.main()
