"""Tests for the bulk-TLE backfill.

No network access anywhere in here. Two tests enforce that positively rather
than by convention: `test_import_makes_no_network_calls` and
`test_cross_check_makes_no_network_calls` replace `urllib.request.urlopen` with
something that raises, and then run the real import and the real cross-check
through it.

This project has a documented defect class of *green tests over code paths that
never execute*. Several tests below exist specifically to close it: the bundle
fixtures are written in the exact wire format the real bundles use - trailing
backslash on every line 1, no name lines, records out of catalogue order - and
they are driven through `import_bundle` end to end rather than through the field
parsers alone. `test_bundle_format_would_fail_a_naive_parser` asserts that the
fixture really does exercise the backslash path, so the day someone "simplifies"
`normalise_line` away, a test fails instead of the backfill silently rejecting
one hundred percent of every file.

    python3 -m unittest discover -s tests -p 'test_*.py'
"""

from __future__ import annotations

import ast
import datetime as dt
import json
import sqlite3
import tempfile
import unittest
import unittest.mock
import urllib.request
import zipfile
from pathlib import Path
from unittest import mock

from pipeline import orbit_history as oh
from pipeline import orbit_history_backfill as bf


# ---------------------------------------------------------------------------
# Fixtures - real element sets, taken from the live space-track GP mirror on
# 2026-08-07, with their published GP values alongside. Real records are used
# rather than invented ones so the checksums, the exponent fields and the
# column offsets are all genuine.
# ---------------------------------------------------------------------------
VANGUARD_1 = (
    "1 00005U 58002B   26219.05386967  .00000247  00000-0  33237-3 0  9998",
    "2 00005  34.2423 157.3493 1836071   7.8517 354.7118 10.86027427448812",
)
VANGUARD_1_GP = {
    "EPOCH": "2026-08-07T01:17:34.339488",
    "MEAN_MOTION": 10.86027427,
    "ECCENTRICITY": 0.18360709,
    "INCLINATION": 34.2423,
    "RA_OF_ASC_NODE": 157.3493,
    "ARG_OF_PERICENTER": 7.8517,
    "MEAN_ANOMALY": 354.7118,
    "REV_AT_EPOCH": 44881,
}

# Negative B* and negative n-dot: both signs must survive the exponent decode.
NEGATIVE_BSTAR = (
    "1 00167U 61017D   26219.25689622 -.00000181  00000-0 -11783-4 0  9995",
    "2 00167  47.8441 183.2306 0090805 320.9026  38.5320 14.24190720371957",
)

# Non-zero n-ddot, which is almost always zero and therefore almost never tested.
NONZERO_NDDOT = (
    "1 05192U 71015AP  26217.22158103  .12840828  72144-5  26647-2 0  9994",
    "2 05192  65.4779 265.2955 0014998 304.7197  55.2577 16.30315337779357",
)

# Alpha-5. The catalogue passed 99999 during the window the bundles cover, so
# a five-digit assumption silently drops the newest objects in the file.
ALPHA5 = (
    "1 A0000U 26067CY  26219.20115975  .00004079  00000-0  18801-3 0  9992",
    "2 A0000  97.4609 177.1574 0007759 173.5467 186.5870 15.20812648 19451",
)


def as_bundle_lines(pairs, *, trailing_backslash: bool = True) -> list[str]:
    """Render pairs the way space-track's yearly bundles actually render them.

    Line 1 carries a trailing backslash and no name line is emitted. Getting
    this wrong is not a cosmetic difference: it is the whole file.
    """
    out: list[str] = []
    for first, second in pairs:
        out.append(first + ("\\" if trailing_backslash else ""))
        out.append(second)
    return out


def write_bundle(path: Path, pairs, *, member: str = "tle.txt", **kwargs) -> Path:
    lines = as_bundle_lines(pairs, **kwargs)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(member, "\n".join(lines) + "\n")
    return path


def retime(pair, *, epoch: str) -> tuple[str, str]:
    """Move a real TLE to a different epoch, fixing the checksum.

    `epoch` is the whole 14-column `YYDDD.DDDDDDDD` field. Passing a shorter
    string shifts every field to its right, which is a silent way to build a
    fixture that tests something other than what it claims to.
    """
    assert len(epoch) == 14, "the TLE epoch field is columns 19-32, 14 wide"
    return bf.fix_checksum(pair[0][:18] + epoch + pair[0][32:]), pair[1]


def at_day(day: int, *, year: str = "24", pair=None) -> tuple[str, str]:
    """A VANGUARD 1 element set moved to day `day` of `year`."""
    return retime(pair or VANGUARD_1, epoch=f"{year}{day:03d}.05386967")


# ---------------------------------------------------------------------------
# The boundary
# ---------------------------------------------------------------------------
class EntityBoundaryTest(unittest.TestCase):
    def test_refuses_any_host_but_bigmem(self):
        for host in ("theinformed-vps", "localhost", "bigmem-pc", ""):
            with self.assertRaises(SystemExit) as caught:
                bf.enforce_entity_boundary(host)
            self.assertIn("REFUSING TO RUN", str(caught.exception))

    def test_allows_bigmem(self):
        bf.enforce_entity_boundary("bigmem-PC")

    def test_guard_matches_the_ingest_script(self):
        # Two guards that disagree about the host name are worse than one.
        source = (
            Path(__file__).resolve().parents[1] / "ingest" / "spacetrack_ingest.py"
        ).read_text()
        self.assertIn(f'SPACETRACK_HOST = "{bf.SPACETRACK_HOST}"', source)

    def test_no_url_in_the_module_points_at_a_rate_limited_upstream(self):
        """Every URL literal in the module, checked - not every mention.

        The docstring quotes space-track's own guidance and names the
        `gp_history` class it tells callers not to use, so a plain substring
        search over the file would fail on the documentation. What must never
        exist is a *URL* aimed at their API, or at CelesTrak, which this entity
        is not permitted to query at all.
        """
        tree = ast.parse(Path(bf.__file__).read_text())
        urls = [
            node.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and node.value.startswith(("http://", "https://"))
        ]
        self.assertTrue(urls, "expected at least the bulk share URL")
        for url in urls:
            for forbidden in ("space-track.org", "celestrak.org", "celestrak.com"):
                self.assertNotIn(forbidden, url, f"{url} targets a forbidden upstream")

    def test_the_only_upstream_is_the_sanctioned_bulk_share(self):
        self.assertTrue(bf.BULK_SHARE_URL.startswith("https://ln5.sync.com/dl/"))


# ---------------------------------------------------------------------------
# Field decoding
# ---------------------------------------------------------------------------
class ChecksumTest(unittest.TestCase):
    def test_real_lines_validate(self):
        for pair in (VANGUARD_1, NEGATIVE_BSTAR, NONZERO_NDDOT, ALPHA5):
            for line in pair:
                self.assertEqual(
                    bf.tle_checksum(line), int(line[68]), f"checksum failed on {line}"
                )

    def test_minus_signs_count_as_one(self):
        # The only part of the rule anyone gets wrong.
        self.assertEqual(bf.tle_checksum("-" + "0" * 67), 1)
        self.assertEqual(bf.tle_checksum("1" * 68), 68 % 10)

    def test_letters_and_spaces_count_as_zero(self):
        self.assertEqual(bf.tle_checksum("U" * 68), 0)
        self.assertEqual(bf.tle_checksum(" " * 68), 0)

    def test_a_corrupted_digit_is_caught(self):
        line = VANGUARD_1[0]
        broken = line[:20] + ("9" if line[20] != "9" else "8") + line[21:]
        self.assertNotEqual(bf.tle_checksum(broken), int(broken[68]))


class NormaliseLineTest(unittest.TestCase):
    def test_strips_the_bundle_trailing_backslash(self):
        raw = VANGUARD_1[0] + "\\\n"
        self.assertEqual(bf.normalise_line(raw), VANGUARD_1[0])
        self.assertEqual(len(bf.normalise_line(raw)), 69)

    def test_strips_crlf(self):
        self.assertEqual(bf.normalise_line(VANGUARD_1[1] + "\r\n"), VANGUARD_1[1])

    def test_leaves_a_clean_line_alone(self):
        self.assertEqual(bf.normalise_line(VANGUARD_1[1]), VANGUARD_1[1])


class SatnumTest(unittest.TestCase):
    def test_plain_five_digit(self):
        self.assertEqual(bf.decode_satnum("00005"), 5)
        self.assertEqual(bf.decode_satnum("99999"), 99999)

    def test_alpha5(self):
        self.assertEqual(bf.decode_satnum("A0000"), 100000)
        self.assertEqual(bf.decode_satnum("B1234"), 111234)
        # I and O are skipped because they read as 1 and 0.
        self.assertEqual(bf.decode_satnum("H0000"), 170000)
        self.assertEqual(bf.decode_satnum("J0000"), 180000)
        self.assertEqual(bf.decode_satnum("Z9999"), 339999)

    def test_rejects_the_excluded_letters(self):
        self.assertIsNone(bf.decode_satnum("I0001"))
        self.assertIsNone(bf.decode_satnum("O0001"))

    def test_space_padded_numbers(self):
        """The bundles space-pad as well as zero-pad, and VANGUARD 1 is one.

        Found in the real 2024 bundle: `1     5U 58002B ...`. A parser that
        assumes five digits drops the object this project pins its
        semi-major-axis test against, and drops it silently.
        """
        self.assertEqual(bf.decode_satnum("    5"), 5)
        self.assertEqual(bf.decode_satnum("  167"), 167)
        self.assertEqual(bf.decode_satnum(" 5192"), 5192)

    def test_the_real_space_padded_line_parses(self):
        line1 = "1     5U 58002B   24002.87243220  .00000271  00000-0  37474-3 0  6676"
        line2 = "2     5  34.2504 218.5271 1841204 335.3400  16.5900 10.85862325437441"
        element = bf.parse_tle_pair(line1, bf.fix_checksum(line2))
        self.assertIsNotNone(element)
        self.assertEqual(element.norad, 5)

    def test_rejects_junk(self):
        self.assertIsNone(bf.decode_satnum(""))
        self.assertIsNone(bf.decode_satnum("     "))
        self.assertIsNone(bf.decode_satnum("A00X0"))
        self.assertIsNone(bf.decode_satnum("*0000"))
        self.assertIsNone(bf.decode_satnum("A123"))      # too short after the letter
        self.assertIsNone(bf.decode_satnum("A12345"))    # too long after the letter


class AnalystObjectTest(unittest.TestCase):
    """Analyst records: 68 columns, no checksum, recycled catalogue numbers.

    All three properties are taken from the real 2024 bundle, where 6,715 of
    the first 3,000,000 line-1 records are analyst records and every one of the
    68-column lines in that sample is one.
    """

    ANALYST = (
        "1 81134U          24001.37508183 +.00000151 +00000+0 +53062-3 0    1",
        "2 81134  90.2545 347.7738 0026102  90.2541 270.1568 12.9260949137069",
    )

    def test_the_fixture_is_the_unchecksummed_68_column_form(self):
        # Guards the fixture itself: if it ever becomes an ordinary 69-column
        # line, this class stops testing what it says it tests.
        for line in self.ANALYST:
            self.assertEqual(len(line), 68)

    def test_excluded_by_default_with_a_named_reason(self):
        log = bf.RejectionLog()
        self.assertIsNone(bf.parse_tle_pair(*self.ANALYST, log=log))
        self.assertEqual(log.counts.get(bf.Rejection.ANALYST), 1)
        # Specifically NOT filed as a short line, which is what an
        # order-of-checks mistake would produce.
        self.assertNotIn(bf.Rejection.SHORT_LINE, log.counts)

    def test_they_do_parse_when_the_exclusion_is_lifted(self):
        # Proves the exclusion is a decision about identity, not a parse failure.
        element = bf.parse_tle_pair(*self.ANALYST, exclude_analyst=False)
        self.assertIsNotNone(element)
        self.assertEqual(element.norad, 81134)
        self.assertAlmostEqual(element.inclination, 90.2545, 4)
        self.assertAlmostEqual(element.mean_motion, 12.92609491, 8)

    def test_the_band_is_the_test_not_the_line_length(self):
        # 28 analyst records in that same 3M sample DO carry a checksum, so
        # filtering on length alone would let those through.
        checksummed = (bf.fix_checksum(self.ANALYST[0]), bf.fix_checksum(self.ANALYST[1]))
        log = bf.RejectionLog()
        self.assertIsNone(bf.parse_tle_pair(*checksummed, log=log))
        self.assertEqual(log.counts.get(bf.Rejection.ANALYST), 1)

    def test_the_band_boundaries(self):
        self.assertFalse(bf.is_analyst(79999))
        self.assertTrue(bf.is_analyst(80000))
        self.assertTrue(bf.is_analyst(89999))
        self.assertFalse(bf.is_analyst(90000))

    def test_a_non_analyst_record_missing_its_checksum_is_still_refused(self):
        log = bf.RejectionLog()
        self.assertIsNone(bf.parse_tle_pair(VANGUARD_1[0][:68], VANGUARD_1[1], log=log))
        self.assertEqual(log.counts.get(bf.Rejection.SHORT_LINE), 1)


class UnchecksummedEarlyBundleTest(unittest.TestCase):
    """The deep history publishes whole records with no checksum column.

    Both fixtures are verbatim from `tle2004_1of8.txt.zip`, from the region
    that begins about 7% into the file and runs to the end - 1,723,295 of that
    bundle's 1,816,163 records, 95% of it. They are ordinary catalogued
    objects, not analyst records, and every element in them is correct.

    The parser used to refuse all of them, filed under `short-line`. That would
    have thrown away 2004 and 2005 - roughly 56 million records, a quarter of
    the whole archive - while reporting the years as imported.
    """

    ISS_2001 = (
        "1 25544U 98067A   01211.86127679 +.00013801 +00000-0 +18788-3 0 0279",
        "2 25544 051.6384 228.0530 0011394 318.8013 105.3045 15.5779942415390",
    )
    SL_2001 = (
        "1 26121U 99057H   01237.83117426 +.00002889 +00000-0 +45565-3 0 0244",
        "2 26121 098.6992 353.6713 0090184 222.9968 136.4173 14.7060791807774",
    )

    def test_the_fixtures_really_do_lack_the_checksum_column(self):
        # If space-track ever reissues these bundles in the 69-column form,
        # this class stops testing what it says it tests - so it fails loudly
        # rather than passing vacuously.
        for pair in (self.ISS_2001, self.SL_2001):
            for line in pair:
                self.assertEqual(len(line), 68)
                self.assertFalse(bf.is_analyst(bf.decode_satnum(line[2:7])))

    def test_the_iss_at_a_2001_epoch_parses_to_its_real_orbit(self):
        element = bf.parse_tle_pair(*self.ISS_2001)
        self.assertIsNotNone(element)
        self.assertEqual(element.norad, 25544)
        # Correct column alignment is what these numbers prove: a shifted
        # field would not land on the ISS's actual inclination.
        self.assertAlmostEqual(element.inclination, 51.6384, 4)
        self.assertAlmostEqual(element.raan, 228.0530, 4)
        self.assertAlmostEqual(element.eccentricity, 0.0011394, 7)
        self.assertAlmostEqual(element.mean_motion, 15.57799424, 8)
        self.assertAlmostEqual(element.ndot, 0.00013801, 8)
        self.assertAlmostEqual(element.bstar, 0.00018788, 8)
        self.assertEqual(element.rev_at_epoch, 15390)
        self.assertEqual(
            bf.oh.epoch_ms_to_datetime(element.epoch_ms).year, 2001
        )

    def test_it_is_counted_as_accepted_with_a_note_never_as_a_rejection(self):
        log = bf.RejectionLog()
        self.assertIsNotNone(bf.parse_tle_pair(*self.SL_2001, log=log))
        self.assertEqual(log.total, 0)
        self.assertEqual(log.notes.get(bf.Rejection.NO_CHECKSUM_COLUMN), 1)
        payload = log.as_dict()
        self.assertEqual(payload["total"], 0)
        self.assertEqual(payload["byReason"], {})
        self.assertEqual(
            payload["acceptedWithNote"], {bf.Rejection.NO_CHECKSUM_COLUMN: 1}
        )

    def test_a_truncated_line_is_still_a_truncated_line(self):
        """The rule is uniformity, not length.

        68 columns on both lines is a format. 68 on one and 69 on the other is
        a line that lost its last character, and accepting that would archive
        something nothing has verified.
        """
        for broken in (
            (self.ISS_2001[0], bf.fix_checksum(self.ISS_2001[1])),
            (bf.fix_checksum(self.ISS_2001[0]), self.ISS_2001[1]),
        ):
            log = bf.RejectionLog()
            self.assertIsNone(bf.parse_tle_pair(*broken, log=log))
            self.assertEqual(log.counts.get(bf.Rejection.SHORT_LINE), 1)

    def test_a_checksum_that_is_present_is_still_enforced(self):
        # Relaxing the absent case must not relax the present one.
        good = (bf.fix_checksum(self.ISS_2001[0]), bf.fix_checksum(self.ISS_2001[1]))
        self.assertIsNotNone(bf.parse_tle_pair(*good))
        bad = (good[0][:68] + ("0" if good[0][68] != "0" else "1"), good[1])
        log = bf.RejectionLog()
        self.assertIsNone(bf.parse_tle_pair(*bad, log=log))
        self.assertEqual(log.counts.get(bf.Rejection.CHECKSUM_1), 1)

    def test_an_analyst_record_is_still_excluded_by_its_band(self):
        # Both are 68 columns; only one of them is an identity question.
        log = bf.RejectionLog()
        self.assertIsNone(
            bf.parse_tle_pair(*AnalystObjectTest.ANALYST, log=log)
        )
        self.assertEqual(log.counts.get(bf.Rejection.ANALYST), 1)
        self.assertEqual(log.notes, {})

    def test_the_whole_record_survives_an_import(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            connection = oh.open_archive(root / "a.sqlite3")
            try:
                path = root / "b.zip"
                with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
                    archive.writestr(
                        "tle.txt",
                        "\n".join(
                            line + "\\" for pair in (self.ISS_2001, self.SL_2001)
                            for line in pair
                        ) + "\n",
                    )
                result = bf.import_bundle(connection, path)
                self.assertEqual(result.elements_new, 2)
                self.assertEqual(result.rejections.total, 0)
                self.assertEqual(
                    result.rejections.notes[bf.Rejection.NO_CHECKSUM_COLUMN], 2
                )
                stored = oh.series(connection, 25544)
                self.assertAlmostEqual(stored[0].inclination, 51.6384, 4)
            finally:
                connection.close()


class ImpliedDecimalTest(unittest.TestCase):
    def test_positive_and_negative(self):
        self.assertAlmostEqual(bf.decode_implied_decimal(" 17439-2"), 0.17439e-2, 15)
        self.assertAlmostEqual(bf.decode_implied_decimal("-21183-6"), -0.21183e-6, 20)
        self.assertAlmostEqual(bf.decode_implied_decimal("-11783-4"), -0.11783e-4, 18)

    def test_zero(self):
        self.assertEqual(bf.decode_implied_decimal(" 00000-0"), 0.0)
        self.assertEqual(bf.decode_implied_decimal(" 00000+0"), 0.0)

    def test_positive_exponent(self):
        self.assertAlmostEqual(bf.decode_implied_decimal(" 12345+3"), 123.45, 9)

    def test_blank_is_missing_not_zero(self):
        # A missing B* and a B* of zero are different physical statements, and
        # `orbit_history` keeps them different all the way into the schema.
        self.assertIsNone(bf.decode_implied_decimal("        "))
        self.assertIsNone(bf.decode_implied_decimal(""))

    def test_rejects_junk(self):
        self.assertIsNone(bf.decode_implied_decimal(" 1x345-2"))
        self.assertIsNone(bf.decode_implied_decimal("+"))


class EpochTest(unittest.TestCase):
    def test_matches_space_tracks_own_epoch_string_exactly(self):
        got = bf.decode_epoch_ms("26", "219.05386967")
        want = oh.parse_epoch_ms(VANGUARD_1_GP["EPOCH"])
        self.assertEqual(got, want)

    def test_two_digit_year_pivot(self):
        # 57-99 is 19xx, 00-56 is 20xx. Sputnik launched in 1957.
        self.assertEqual(
            oh.epoch_ms_to_datetime(bf.decode_epoch_ms("57", "001.00000000")).year, 1957
        )
        self.assertEqual(
            oh.epoch_ms_to_datetime(bf.decode_epoch_ms("56", "001.00000000")).year, 2056
        )
        self.assertEqual(
            oh.epoch_ms_to_datetime(bf.decode_epoch_ms("99", "001.00000000")).year, 1999
        )
        self.assertEqual(
            oh.epoch_ms_to_datetime(bf.decode_epoch_ms("00", "001.00000000")).year, 2000
        )

    def test_day_one_is_january_first(self):
        stamp = oh.epoch_ms_to_datetime(bf.decode_epoch_ms("24", "001.00000000"))
        self.assertEqual((stamp.year, stamp.month, stamp.day), (2024, 1, 1))

    def test_leap_day_366_is_accepted_in_a_leap_year(self):
        stamp = oh.epoch_ms_to_datetime(bf.decode_epoch_ms("24", "366.50000000"))
        self.assertEqual((stamp.year, stamp.month, stamp.day), (2024, 12, 31))

    def test_day_366_is_refused_in_a_common_year(self):
        self.assertIsNone(bf.decode_epoch_ms("23", "366.50000000"))

    def test_out_of_range_days(self):
        self.assertIsNone(bf.decode_epoch_ms("24", "000.50000000"))
        self.assertIsNone(bf.decode_epoch_ms("24", "367.50000000"))
        self.assertIsNone(bf.decode_epoch_ms("24", "abc"))

    def test_millisecond_resolution(self):
        # The TLE epoch's last digit is 0.86 ms; two epochs one unit apart must
        # not collapse onto the same stored millisecond in a way that loses one.
        a = bf.decode_epoch_ms("24", "100.00000001")
        b = bf.decode_epoch_ms("24", "100.00000002")
        self.assertLessEqual(abs(a - b), 2)


# ---------------------------------------------------------------------------
# Pair parsing
# ---------------------------------------------------------------------------
class ParsePairTest(unittest.TestCase):
    def test_reproduces_the_published_gp_elements(self):
        element = bf.parse_tle_pair(*VANGUARD_1)
        self.assertIsNotNone(element)
        self.assertEqual(element.norad, 5)
        self.assertEqual(element.epoch_ms, oh.parse_epoch_ms(VANGUARD_1_GP["EPOCH"]))
        self.assertAlmostEqual(element.mean_motion, VANGUARD_1_GP["MEAN_MOTION"], 8)
        self.assertAlmostEqual(element.inclination, VANGUARD_1_GP["INCLINATION"], 4)
        self.assertAlmostEqual(element.raan, VANGUARD_1_GP["RA_OF_ASC_NODE"], 4)
        self.assertAlmostEqual(element.arg_perigee, VANGUARD_1_GP["ARG_OF_PERICENTER"], 4)
        self.assertAlmostEqual(element.mean_anomaly, VANGUARD_1_GP["MEAN_ANOMALY"], 4)
        self.assertEqual(element.rev_at_epoch, VANGUARD_1_GP["REV_AT_EPOCH"])
        # Eccentricity is the one field the TLE renders more coarsely than GP.
        self.assertAlmostEqual(element.eccentricity, VANGUARD_1_GP["ECCENTRICITY"], 7)

    def test_semi_major_axis_matches_space_tracks_own(self):
        # space-track publishes SEMIMAJOR_AXIS 8613.401 km for this element set.
        element = bf.parse_tle_pair(*VANGUARD_1)
        self.assertAlmostEqual(element.semi_major_axis_km, 8613.401, 2)

    def test_signs_survive(self):
        element = bf.parse_tle_pair(*NEGATIVE_BSTAR)
        self.assertLess(element.bstar, 0)
        self.assertLess(element.ndot, 0)
        self.assertAlmostEqual(element.bstar, -0.11783e-4, 18)
        self.assertAlmostEqual(element.ndot, -0.00000181, 12)

    def test_nonzero_nddot(self):
        element = bf.parse_tle_pair(*NONZERO_NDDOT)
        self.assertAlmostEqual(element.nddot, 0.72144e-5, 15)

    def test_alpha5_pair(self):
        element = bf.parse_tle_pair(*ALPHA5)
        self.assertEqual(element.norad, 100000)

    def test_bad_checksum_is_rejected_and_counted(self):
        log = bf.RejectionLog()
        first = VANGUARD_1[0][:68] + ("0" if VANGUARD_1[0][68] != "0" else "1")
        self.assertIsNone(bf.parse_tle_pair(first, VANGUARD_1[1], log=log))
        self.assertEqual(log.counts.get(bf.Rejection.CHECKSUM_1), 1)
        self.assertEqual(log.total, 1)

    def test_satnum_mismatch_is_rejected(self):
        log = bf.RejectionLog()
        self.assertIsNone(bf.parse_tle_pair(VANGUARD_1[0], NEGATIVE_BSTAR[1], log=log))
        self.assertEqual(log.counts.get(bf.Rejection.SATNUM_MISMATCH), 1)

    def test_short_line_is_rejected(self):
        log = bf.RejectionLog()
        self.assertIsNone(bf.parse_tle_pair("1 00005U", VANGUARD_1[1], log=log))
        self.assertEqual(log.counts.get(bf.Rejection.SHORT_LINE), 1)

    def test_out_of_range_mean_motion_is_rejected(self):
        # 20 rev/day is below the Earth's surface; the same guard the live GP
        # path applies, so the two sources cannot disagree about what is legal.
        second = VANGUARD_1[1][:52] + "99.86027427" + VANGUARD_1[1][63:]
        second = second[:68] + str(bf.tle_checksum(second))
        log = bf.RejectionLog()
        self.assertIsNone(bf.parse_tle_pair(VANGUARD_1[0], second, log=log))
        self.assertEqual(log.counts.get(bf.Rejection.OUT_OF_RANGE), 1)

    def test_absurd_drag_exponent_is_rejected_not_stored(self):
        # The 2005 bulk bundle carries records whose second derivative decodes
        # to about 1e8 rev/day^3. Quantised at 1e13 that is past the signed
        # 64-bit range SQLite stores integers in, and it used to reach
        # `executemany` and raise OverflowError mid-batch.
        first = bf.fix_checksum(VANGUARD_1[0][:44] + " 12345+9" + VANGUARD_1[0][52:])
        log = bf.RejectionLog()
        self.assertIsNone(bf.parse_tle_pair(first, VANGUARD_1[1], log=log))
        self.assertEqual(log.counts.get(bf.Rejection.OUT_OF_RANGE), 1)

    def test_swapped_lines_are_rejected(self):
        log = bf.RejectionLog()
        self.assertIsNone(bf.parse_tle_pair(VANGUARD_1[1], VANGUARD_1[0], log=log))
        self.assertEqual(log.counts.get(bf.Rejection.BAD_PREFIX), 1)

    def test_rejection_log_keeps_one_example_per_reason(self):
        log = bf.RejectionLog()
        log.add("x", "first")
        log.add("x", "second")
        self.assertEqual(log.counts["x"], 2)
        self.assertEqual(log.examples["x"], "first")


class PairingTest(unittest.TestCase):
    def test_name_lines_are_skipped(self):
        lines = ["0 VANGUARD 1", VANGUARD_1[0], VANGUARD_1[1]]
        self.assertEqual(list(bf.iter_tle_pairs(lines)), [VANGUARD_1])

    def test_blank_lines_are_skipped(self):
        lines = ["", VANGUARD_1[0], "", VANGUARD_1[1], ""]
        self.assertEqual(list(bf.iter_tle_pairs(lines)), [VANGUARD_1])

    def test_an_orphan_line_two_is_surfaced_not_swallowed(self):
        pairs = list(bf.iter_tle_pairs([VANGUARD_1[1]]))
        self.assertEqual(pairs, [("", VANGUARD_1[1])])

    def test_two_line_ones_in_a_row_keeps_the_second(self):
        pairs = list(bf.iter_tle_pairs([VANGUARD_1[0], ALPHA5[0], ALPHA5[1]]))
        self.assertEqual(pairs, [ALPHA5])

    def test_bundle_backslashes_are_handled_by_the_iterator(self):
        lines = as_bundle_lines([VANGUARD_1, ALPHA5])
        self.assertEqual(list(bf.iter_tle_pairs(lines)), [VANGUARD_1, ALPHA5])


# ---------------------------------------------------------------------------
# The trap this project keeps producing: a green test over a path that never runs
# ---------------------------------------------------------------------------
class BundleFormatTest(unittest.TestCase):
    def test_bundle_format_would_fail_a_naive_parser(self):
        """The fixture must genuinely exercise the backslash path.

        If `as_bundle_lines` ever stops emitting the trailing backslash, or
        `normalise_line` stops removing it, this fails - rather than the import
        quietly rejecting every record in every real bundle while every other
        test stays green.
        """
        raw = as_bundle_lines([VANGUARD_1])[0]
        self.assertEqual(len(raw), 70)
        self.assertTrue(raw.endswith("\\"))
        # A parser that reads the checksum from the last character of the raw
        # line - the obvious implementation - gets a backslash, not a digit.
        self.assertFalse(raw[-1].isdigit())
        # And the module's own path recovers it.
        self.assertIsNotNone(bf.parse_tle_pair(raw, VANGUARD_1[1]))


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------
class ImportTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.connection = oh.open_archive(self.root / "archive.sqlite3")

    def tearDown(self):
        self.connection.close()
        self.tmp.cleanup()

    def bundle(self, pairs, name="tle2024.txt.zip", **kwargs) -> Path:
        return write_bundle(self.root / name, pairs, **kwargs)

    def test_imports_real_bundle_format_end_to_end(self):
        path = self.bundle([VANGUARD_1, NEGATIVE_BSTAR, ALPHA5])
        result = bf.import_bundle(self.connection, path)
        self.assertEqual(result.records_read, 3)
        self.assertEqual(result.elements_new, 3)
        self.assertEqual(result.rejections.total, 0)
        self.assertEqual(result.objects_seen, 3)
        stored = oh.series(self.connection, 100000)
        self.assertEqual(len(stored), 1)
        self.assertAlmostEqual(stored[0].inclination, 97.4609, 4)

    def test_one_overflowing_record_costs_only_that_record(self):
        # What matters is not the rejection, it is that a single garbled drag
        # exponent in a 20-year archive costs that record and nothing else.
        # Before the guard it raised OverflowError inside `executemany`, which
        # took down the whole batch, the bundle, and every year still queued
        # behind it.
        first = bf.fix_checksum(VANGUARD_1[0][:44] + " 12345+9" + VANGUARD_1[0][52:])
        good = at_day(200, year="05")
        path = self.root / "overflow.zip"
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(
                "tle.txt", "\n".join([first, VANGUARD_1[1], good[0], good[1]]) + "\n"
            )
        result = bf.import_bundle(self.connection, path)
        self.assertEqual(result.records_read, 1)
        self.assertEqual(result.elements_new, 1)
        self.assertEqual(result.rejections.counts.get(bf.Rejection.OUT_OF_RANGE), 1)

    def test_reimport_is_idempotent(self):
        path = self.bundle([VANGUARD_1, ALPHA5])
        first = bf.import_bundle(self.connection, path)
        second = bf.import_bundle(self.connection, path)
        self.assertEqual(first.elements_new, 2)
        self.assertEqual(second.elements_new, 0)
        self.assertEqual(second.duplicates, 2)
        self.assertEqual(
            self.connection.execute("SELECT COUNT(*) FROM element_set").fetchone()[0], 2
        )

    def test_duplicate_epochs_inside_one_bundle_collapse(self):
        path = self.bundle([VANGUARD_1, VANGUARD_1, VANGUARD_1])
        result = bf.import_bundle(self.connection, path)
        self.assertEqual(result.records_read, 3)
        self.assertEqual(result.elements_new, 1)
        self.assertEqual(result.duplicates, 2)

    def test_distinct_epochs_of_one_object_all_survive(self):
        pairs = [at_day(d, year="26") for d in (100, 101, 102)]
        result = bf.import_bundle(self.connection, self.bundle(pairs))
        self.assertEqual(result.elements_new, 3)
        self.assertEqual(len(oh.series(self.connection, 5)), 3)

    def test_rejections_are_counted_with_reasons(self):
        broken = VANGUARD_1[0][:68] + ("0" if VANGUARD_1[0][68] != "0" else "1")
        path = self.bundle([VANGUARD_1, (broken, VANGUARD_1[1]), ALPHA5])
        result = bf.import_bundle(self.connection, path)
        self.assertEqual(result.records_read, 2)
        self.assertEqual(result.rejections.counts.get(bf.Rejection.CHECKSUM_1), 1)
        self.assertEqual(result.rejections.total, 1)
        self.assertIn(bf.Rejection.CHECKSUM_1, result.rejections.as_dict()["byReason"])

    def test_records_a_capture_ledger_row(self):
        path = self.bundle([VANGUARD_1])
        bf.import_bundle(self.connection, path)
        row = self.connection.execute(
            "SELECT source, records_read, elements_new FROM capture"
        ).fetchone()
        self.assertEqual(row[0], "spacetrack:bulk:tle2024.txt.zip")
        self.assertEqual((row[1], row[2]), (1, 1))

    def test_does_not_clobber_object_identity_from_the_live_capture(self):
        # The bundles carry catalogue numbers only. Overwriting a live `object`
        # row would erase the name the browser shows.
        oh.ingest_records(
            self.connection,
            [
                {
                    "NORAD_CAT_ID": "5",
                    "OBJECT_NAME": "VANGUARD 1",
                    "OBJECT_TYPE": "PAYLOAD",
                    "COUNTRY_CODE": "US",
                    "EPOCH": "2026-08-07T00:00:00",
                    "MEAN_MOTION": "10.86",
                    "ECCENTRICITY": "0.1836",
                    "INCLINATION": "34.24",
                    "RA_OF_ASC_NODE": "157.3",
                    "ARG_OF_PERICENTER": "7.85",
                    "MEAN_ANOMALY": "354.7",
                }
            ],
        )
        bf.import_bundle(self.connection, self.bundle([VANGUARD_1]))
        name, object_type = self.connection.execute(
            "SELECT name, object_type FROM object WHERE norad = 5"
        ).fetchone()
        self.assertEqual(name, "VANGUARD 1")
        self.assertEqual(object_type, "PAYLOAD")

    def test_first_seen_is_widened_backwards_by_the_backfill(self):
        oh.ingest_records(
            self.connection,
            [
                {
                    "NORAD_CAT_ID": "5",
                    "OBJECT_NAME": "VANGUARD 1",
                    "EPOCH": "2026-08-07T00:00:00",
                    "MEAN_MOTION": "10.86",
                    "ECCENTRICITY": "0.1836",
                    "INCLINATION": "34.24",
                    "RA_OF_ASC_NODE": "157.3",
                    "ARG_OF_PERICENTER": "7.85",
                    "MEAN_ANOMALY": "354.7",
                }
            ],
        )
        before = self.connection.execute(
            "SELECT first_seen_ms FROM object WHERE norad = 5"
        ).fetchone()[0]
        bf.import_bundle(self.connection, self.bundle([at_day(10, year="05")]))
        after = self.connection.execute(
            "SELECT first_seen_ms FROM object WHERE norad = 5"
        ).fetchone()[0]
        self.assertLess(after, before)

    def test_batching_does_not_change_the_result(self):
        pairs = [at_day(d, year="26") for d in range(100, 140)]
        path = self.bundle(pairs)
        # yield_seconds=0: this is about batching, and nothing else is holding
        # a temporary database, so there is no writer to stand back for.
        small = bf.import_bundle(self.connection, path, batch_rows=3, yield_seconds=0)
        self.assertEqual(small.elements_new, 40)
        other = oh.open_archive(self.root / "other.sqlite3")
        try:
            big = bf.import_bundle(other, path, batch_rows=10_000, yield_seconds=0)
            self.assertEqual(big.elements_new, 40)
        finally:
            other.close()

    def test_an_empty_zip_is_an_error_not_a_silent_success(self):
        path = self.root / "empty.zip"
        with zipfile.ZipFile(path, "w"):
            pass
        with self.assertRaises(bf.BackfillError):
            bf.import_bundle(self.connection, path)

    def test_a_bundle_of_only_garbage_imports_nothing_and_says_why(self):
        path = self.root / "junk.zip"
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("tle.txt", "not a tle\nnor is this\n")
        result = bf.import_bundle(self.connection, path)
        self.assertEqual(result.records_read, 0)
        self.assertEqual(result.elements_new, 0)

    def test_dedupe_verification_reports_the_key_holds(self):
        pairs = [at_day(d, year="26") for d in range(100, 130)]
        bf.import_bundle(self.connection, self.bundle(pairs))
        report = bf.verify_dedupe_at_scale(self.connection)
        self.assertTrue(report["holds"])
        self.assertEqual(report["duplicateKeys"], 0)
        self.assertEqual(report["rows"], 30)

    def test_quantisation_is_the_archives_own(self):
        bf.import_bundle(self.connection, self.bundle([VANGUARD_1]))
        row = self.connection.execute(
            "SELECT mean_motion_q, inclination_q FROM element_set WHERE norad = 5"
        ).fetchone()
        self.assertEqual(row[0], oh.quantise(10.86027427, oh.SCALE_MEAN_MOTION))
        self.assertEqual(row[1], oh.quantise(34.2423, oh.SCALE_ANGLE))

    def test_import_makes_no_network_calls(self):
        path = self.bundle([VANGUARD_1, ALPHA5])
        with mock.patch.object(
            urllib.request, "urlopen", side_effect=AssertionError("network!")
        ):
            result = bf.import_bundle(self.connection, path)
        self.assertEqual(result.elements_new, 2)


# ---------------------------------------------------------------------------
# The cross-check
# ---------------------------------------------------------------------------
def mirror_record(pair, gp: dict, norad: str) -> dict:
    return {
        "NORAD_CAT_ID": norad,
        "EPOCH": gp["EPOCH"],
        "MEAN_MOTION": str(gp["MEAN_MOTION"]),
        "ECCENTRICITY": str(gp["ECCENTRICITY"]),
        "INCLINATION": str(gp["INCLINATION"]),
        "RA_OF_ASC_NODE": str(gp["RA_OF_ASC_NODE"]),
        "ARG_OF_PERICENTER": str(gp["ARG_OF_PERICENTER"]),
        "MEAN_ANOMALY": str(gp["MEAN_ANOMALY"]),
        "BSTAR": "0.00033236870000",
        "MEAN_MOTION_DOT": "0.00000247",
        "MEAN_MOTION_DDOT": "0.0000000000000",
        "REV_AT_EPOCH": str(gp["REV_AT_EPOCH"]),
        "TLE_LINE1": pair[0],
        "TLE_LINE2": pair[1],
    }


class CrossCheckTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def write_mirror(self, records) -> Path:
        path = self.root / "gp-active.json"
        path.write_text(json.dumps(records))
        return path

    def test_matching_sources_produce_the_expected_residuals(self):
        path = self.write_mirror([mirror_record(VANGUARD_1, VANGUARD_1_GP, "5")])
        report = bf.cross_check_live_capture(path)
        self.assertEqual(report["recordsCompared"], 1)
        # Epoch must be exact: the two-digit year and the fractional day have to
        # reproduce space-track's own timestamp to the millisecond.
        self.assertEqual(report["epochResidualMs"]["max"], 0.0)
        self.assertEqual(report["elementResiduals"]["meanMotion"]["max"], 0.0)
        self.assertEqual(report["elementResiduals"]["inclination"]["max"], 0.0)
        # Eccentricity is rendered with one fewer decimal in the TLE, so its
        # residual is bounded by half that quantum and nothing else is.
        self.assertLessEqual(report["elementResiduals"]["eccentricity"]["max"], 5e-8)

    def test_a_wrong_conversion_is_actually_detected(self):
        # The negative test that makes the positive one mean something: if the
        # parser drifted, the cross-check has to fail rather than pass quietly.
        bad = mirror_record(VANGUARD_1, VANGUARD_1_GP, "5")
        bad["INCLINATION"] = "35.0000"
        report = bf.cross_check_live_capture(self.write_mirror([bad]))
        self.assertGreater(report["elementResiduals"]["inclination"]["max"], 0.7)

    def test_records_without_tle_lines_are_counted_not_skipped_silently(self):
        record = mirror_record(VANGUARD_1, VANGUARD_1_GP, "5")
        record.pop("TLE_LINE1")
        report = bf.cross_check_live_capture(self.write_mirror([record]))
        self.assertEqual(report["recordsCompared"], 0)
        self.assertEqual(report["recordsWithoutTleLines"], 1)

    def test_missing_mirror_raises(self):
        with self.assertRaises(bf.BackfillError):
            bf.cross_check_live_capture(self.root / "absent.json")

    def test_empty_mirror_raises_rather_than_reporting_a_clean_pass(self):
        with self.assertRaises(bf.BackfillError):
            bf.cross_check_live_capture(self.write_mirror([]))

    def test_cross_check_makes_no_network_calls(self):
        path = self.write_mirror([mirror_record(VANGUARD_1, VANGUARD_1_GP, "5")])
        with mock.patch.object(
            urllib.request, "urlopen", side_effect=AssertionError("network!")
        ):
            report = bf.cross_check_live_capture(path)
        self.assertEqual(report["recordsCompared"], 1)


class ArchiveOverlapTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.connection = oh.open_archive(self.root / "archive.sqlite3")

    def tearDown(self):
        self.connection.close()
        self.tmp.cleanup()

    def test_no_overlap_is_reported_as_no_overlap_not_as_agreement(self):
        path = write_bundle(self.root / "b.zip", [VANGUARD_1])
        report = bf.cross_check_archive_overlap(self.connection, path)
        self.assertEqual(report["epochsAlsoInArchive"], 0)
        self.assertIn("not a pass", report["note"])

    def test_an_overlapping_epoch_is_compared(self):
        path = write_bundle(self.root / "b.zip", [VANGUARD_1])
        bf.import_bundle(self.connection, path)
        report = bf.cross_check_archive_overlap(self.connection, path)
        self.assertEqual(report["epochsAlsoInArchive"], 1)
        self.assertEqual(report["disagreements"], [])
        self.assertEqual(report["note"], "")


# ---------------------------------------------------------------------------
# Manifest and resume
# ---------------------------------------------------------------------------
class ManifestTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_missing_manifest_is_an_empty_one(self):
        self.assertEqual(bf.load_manifest(self.root)["files"], {})

    def test_round_trip(self):
        bf.save_manifest(self.root, {"share": "x", "files": {"a": {"bytes": 1}}})
        self.assertEqual(bf.load_manifest(self.root)["files"]["a"]["bytes"], 1)

    def test_a_corrupt_manifest_refuses_rather_than_authorising_a_refetch(self):
        (self.root / bf.MANIFEST_NAME).write_text("{ this is not json")
        with self.assertRaises(bf.BackfillError):
            bf.load_manifest(self.root)

    def test_a_manifest_of_the_wrong_shape_is_refused(self):
        (self.root / bf.MANIFEST_NAME).write_text("[]")
        with self.assertRaises(bf.BackfillError):
            bf.load_manifest(self.root)

    def test_held_requires_the_file_the_size_and_a_digest(self):
        name = "tle2024.txt.zip"
        manifest = {"files": {name: {"bytes": 4, "sha256": "abc"}}}
        self.assertFalse(bf.file_is_held(self.root, manifest, name))
        (self.root / name).write_bytes(b"abcd")
        self.assertTrue(bf.file_is_held(self.root, manifest, name))
        # A truncated file is the failure that actually happens.
        (self.root / name).write_bytes(b"ab")
        self.assertFalse(bf.file_is_held(self.root, manifest, name))

    def test_held_is_false_without_a_digest(self):
        name = "tle2024.txt.zip"
        (self.root / name).write_bytes(b"abcd")
        self.assertFalse(bf.file_is_held(self.root, {"files": {name: {"bytes": 4}}}, name))

    def test_a_held_file_is_never_refetched(self):
        name = "tle2024.txt.zip"
        (self.root / name).write_bytes(b"abcd")
        bf.save_manifest(
            self.root, {"files": {name: {"bytes": 4, "sha256": bf.sha256_of(self.root / name)}}}
        )
        with mock.patch.object(bf, "mint_urls", side_effect=AssertionError("refetch!")):
            record = bf.download_file(name, directory=self.root)
        self.assertEqual(record["skipped"], "already held")

    def test_sha256_matches_hashlib(self):
        import hashlib

        path = self.root / "x"
        path.write_bytes(b"orbital elements")
        self.assertEqual(bf.sha256_of(path), hashlib.sha256(b"orbital elements").hexdigest())

    def test_bundle_names_for_a_year_include_every_part(self):
        listing = [
            {"name": "tle2004_1of8.txt.zip"},
            {"name": "tle2004_7of8.txt.zip"},
            {"name": "tle2024.txt.zip"},
            {"name": "tle2005.txt.zip"},
        ]
        self.assertEqual(
            bf.bundle_name_for_year(2004, listing),
            ["tle2004_1of8.txt.zip", "tle2004_7of8.txt.zip"],
        )
        self.assertEqual(bf.bundle_name_for_year(2024, listing), ["tle2024.txt.zip"])
        self.assertEqual(bf.bundle_name_for_year(1999, listing), [])


class ResumeTest(unittest.TestCase):
    """The resume path, driven without a network by faking the transport."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.payload = bytes(range(256)) * 40      # 10,240 bytes
        self.name = "tle2024.txt.zip"

    def tearDown(self):
        self.tmp.cleanup()

    def fake_open(self, *, truncate_at=None, honour_range=True):
        payload = self.payload

        class Response:
            def __init__(self, offset):
                self.status = 206 if (offset and honour_range) else 200
                start = offset if honour_range else 0
                self.body = payload[start:]
                if truncate_at is not None:
                    self.body = self.body[:truncate_at]
                self.headers = {
                    "Content-Range": f"bytes {start}-{len(payload) - 1}/{len(payload)}"
                }
                self._at = 0

            def read(self, size):
                block = self.body[self._at : self._at + size]
                self._at += len(block)
                return block

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

        def opener(url, offset, user_agent):
            return Response(offset)

        return opener

    def _mint(self):
        return {
            "userAgent": "test-agent",
            "listing": [{"name": self.name, "bytes": len(self.payload)}],
            "urls": {self.name: {"url": "https://example.invalid/x"}},
        }

    def test_a_clean_download_verifies_and_records(self):
        with mock.patch.object(bf, "mint_urls", return_value=self._mint()), mock.patch.object(
            bf, "_open_range", self.fake_open()
        ):
            record = bf.download_file(
                self.name, directory=self.root, expected_bytes=len(self.payload)
            )
        self.assertEqual(record["bytes"], len(self.payload))
        self.assertEqual((self.root / self.name).read_bytes(), self.payload)
        self.assertEqual(record["sha256"], bf.sha256_of(self.root / self.name))

    def test_an_interrupted_download_resumes_instead_of_restarting(self):
        # Leave a partial file behind, as a killed run would.
        (self.root / (self.name + ".part")).write_bytes(self.payload[:4096])
        seen = {}

        original = self.fake_open()

        def watching(url, offset, user_agent):
            seen["offset"] = offset
            return original(url, offset, user_agent)

        with mock.patch.object(bf, "mint_urls", return_value=self._mint()), mock.patch.object(
            bf, "_open_range", watching
        ):
            bf.download_file(
                self.name, directory=self.root, expected_bytes=len(self.payload)
            )
        self.assertEqual(seen["offset"], 4096)
        self.assertEqual((self.root / self.name).read_bytes(), self.payload)

    def test_a_server_that_ignores_range_does_not_produce_a_spliced_file(self):
        (self.root / (self.name + ".part")).write_bytes(self.payload[:4096])
        with mock.patch.object(bf, "mint_urls", return_value=self._mint()), mock.patch.object(
            bf, "_open_range", self.fake_open(honour_range=False)
        ), mock.patch.object(bf.time, "sleep", lambda _s: None):
            bf.download_file(
                self.name, directory=self.root, expected_bytes=len(self.payload)
            )
        # The partial was discarded and the file re-fetched whole, rather than
        # the full body being appended to the 4 KiB we already had.
        self.assertEqual((self.root / self.name).read_bytes(), self.payload)

    def test_a_short_transfer_is_refused_and_retried(self):
        with mock.patch.object(bf, "mint_urls", return_value=self._mint()), mock.patch.object(
            bf, "_open_range", self.fake_open(truncate_at=100)
        ), mock.patch.object(bf.time, "sleep", lambda _s: None):
            with self.assertRaises(bf.BackfillError):
                bf.download_file(
                    self.name, directory=self.root, expected_bytes=len(self.payload)
                )
        # Nothing was promoted to the final name, and nothing was recorded.
        self.assertFalse((self.root / self.name).exists())
        self.assertEqual(bf.load_manifest(self.root)["files"], {})


# ---------------------------------------------------------------------------
# Consolidation and storage
# ---------------------------------------------------------------------------
class ConsolidateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.connection = oh.open_archive(self.root / "archive.sqlite3")

    def tearDown(self):
        self.connection.close()
        self.tmp.cleanup()

    def _import_days(self, days):
        pairs = [at_day(d, year="24") for d in days]
        bf.import_bundle(self.connection, write_bundle(self.root / "b.zip", pairs))

    def test_decimates_and_exports_without_pruning(self):
        self._import_days([10, 11, 12, 40, 41])
        start_ms, _ = oh.month_bounds(2024, 1)
        _, end_ms = oh.month_bounds(2024, 12)
        report = bf.consolidate(
            self.connection, cold_directory=self.root / "cold",
            start_ms=start_ms, end_ms=end_ms,
        )
        self.assertEqual(report["days"], 5)
        self.assertEqual(report["decimated"], 5)
        self.assertFalse(report["pruned"])
        months = {row["month"] for row in report["exported"]}
        self.assertEqual(months, {"2024-01", "2024-02"})
        self.assertTrue(all(row.get("verified") for row in report["exported"]))
        # Nothing was deleted from tier 1.
        self.assertEqual(
            self.connection.execute("SELECT COUNT(*) FROM element_set").fetchone()[0], 5
        )
        # And tier 2 got one sample per day.
        self.assertEqual(
            self.connection.execute("SELECT COUNT(*) FROM element_set_daily").fetchone()[0],
            5,
        )

    def test_a_month_behind_the_prune_watermark_is_skipped_loudly(self):
        self._import_days([10, 40])
        # Simulate an operator having already pruned into this range.
        watermark, _ = oh.month_bounds(2024, 3)
        self.connection.execute(
            "INSERT OR REPLACE INTO meta VALUES('pruned_before_ms', ?)", (str(watermark),)
        )
        self.connection.commit()
        start_ms, _ = oh.month_bounds(2024, 1)
        _, end_ms = oh.month_bounds(2024, 12)
        report = bf.consolidate(
            self.connection, cold_directory=self.root / "cold",
            start_ms=start_ms, end_ms=end_ms,
        )
        skipped = [row for row in report["exported"] if row.get("skipped")]
        self.assertEqual(len(skipped), 2)
        self.assertIn("watermark", skipped[0]["skipped"])

    def test_the_cold_shard_round_trips(self):
        self._import_days([10, 11])
        start_ms, _ = oh.month_bounds(2024, 1)
        _, end_ms = oh.month_bounds(2024, 12)
        bf.consolidate(
            self.connection, cold_directory=self.root / "cold",
            start_ms=start_ms, end_ms=end_ms,
        )
        shard = self.root / "cold" / "orbit-history-2024-01.ohz"
        rows = oh.decode_shard(shard.read_bytes())
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0][0], 5)


class StorageProjectionTest(unittest.TestCase):
    def test_uses_the_measured_per_row_costs(self):
        report = bf.storage_projection({2024: 1_000_000})
        self.assertEqual(report["rowsImported"], 1_000_000)
        self.assertEqual(report["hotBytesIfNeverRolled"], int(1_000_000 * 62.9))
        self.assertEqual(report["coldBytesAfterRolling"], int(1_000_000 * 22.36))

    def test_years_older_than_the_retention_cutoff_cost_nothing_hot(self):
        # 2004 cannot survive a 400-day window under any circumstances.
        report = bf.storage_projection({2004: 5_000_000}, retain_days=400)
        self.assertEqual(report["hotRowsStillInsideWindowUpperBound"], 0)
        self.assertEqual(report["hotBytesAfterRollingUpperBound"], 0)
        self.assertEqual(report["coldBytesAfterRolling"], int(5_000_000 * 22.36))

    def test_matches_the_design_document(self):
        # If anyone re-measures, both numbers move together or the report lies.
        self.assertEqual(bf.BYTES_PER_HOT_ROW, 62.9)
        self.assertEqual(bf.BYTES_PER_COLD_ROW, 22.36)

    def test_empty_input_is_zero_not_an_error(self):
        self.assertEqual(bf.storage_projection({})["rowsImported"], 0)


class PriorityOrderTest(unittest.TestCase):
    def test_gannon_year_is_first(self):
        self.assertEqual(bf.PRIORITY_YEARS[0], 2024)

    def test_every_year_on_the_share_is_covered_exactly_once(self):
        years = list(bf.PRIORITY_YEARS)
        self.assertEqual(len(years), len(set(years)))
        self.assertEqual(set(years), set(range(2004, 2026)))

    def test_recent_years_come_before_the_deep_history(self):
        order = {year: index for index, year in enumerate(bf.PRIORITY_YEARS)}
        self.assertLess(order[2023], order[2010])
        self.assertLess(order[2019], order[2004])


class PruneWatermarkStallTest(unittest.TestCase):
    """A prune that deletes nothing must record nothing.

    This class used to document the opposite, because the opposite was true.
    `prune_hot()` advanced `meta.pruned_before_ms` unconditionally, including
    when its DELETE matched zero rows, and on the real archive that happened:
    created 2026-08-07 holding only 2026 epochs, a `--roll --retain-days 400`
    deleted nothing and set the watermark to 2025-07-03 anyway.

    Every month the backfill then imported began before that watermark, and
    `roll()` refused to export any month behind it - a guard that is right for
    its own case, a month partly pruned, and wrong here, where nothing was ever
    pruned at all. Nothing reached tier 3 for a day, and tier 1 grew without
    bound; the cold directory still held one 10 KB shard.

    Two things changed, and each is asserted below. The watermark now moves only
    when rows actually left, and the export guard asks `pruned_month` - which
    months lost rows - instead of asking a scalar instant that condemns every
    month before it.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.connection = oh.open_archive(self.root / "archive.sqlite3")

    def tearDown(self):
        self.connection.close()
        self.tmp.cleanup()

    def test_a_prune_that_deleted_nothing_leaves_the_watermark_alone(self):
        deleted = oh.prune_hot(self.connection, oh.month_bounds(2025, 7)[0])
        self.assertEqual(deleted, 0)
        self.assertEqual(oh.pruned_before_ms(self.connection), 0)

    def test_a_prune_that_deleted_rows_does_move_the_watermark(self):
        """The other half of the identity: the guard must still fire when it should."""
        bf.import_bundle(
            self.connection,
            write_bundle(self.root / "b.zip", [at_day(d, year="24") for d in (10, 11)]),
        )
        cutoff = oh.month_bounds(2025, 7)[0]
        deleted = oh.prune_hot(self.connection, cutoff, force=True)
        self.assertEqual(deleted, 2)
        self.assertEqual(oh.pruned_before_ms(self.connection), cutoff)
        self.assertEqual(
            [row[0] for row in self.connection.execute("SELECT month FROM pruned_month")],
            ["2024-01"],
        )

    def test_the_roll_now_exports_a_backfilled_month_behind_a_dead_watermark(self):
        oh.prune_hot(self.connection, oh.month_bounds(2025, 7)[0])
        bf.import_bundle(
            self.connection,
            write_bundle(self.root / "b.zip", [at_day(d, year="24") for d in (10, 11)]),
        )
        now_ms = int(
            dt.datetime(2026, 8, 8, tzinfo=dt.timezone.utc).timestamp() * 1000
        )
        report = oh.roll(
            self.connection,
            retain_days=400,
            cold_directory=self.root / "cold",
            now_ms=now_ms,
        )
        self.assertEqual(report["skipped"], [])
        self.assertEqual([row["month"] for row in report["exported"]], ["2024-01"])
        self.assertTrue((self.root / "cold" / "orbit-history-2024-01.ohz").exists())
        # And with a shard covering it, the prune now goes through.
        self.assertEqual(report["pruned"], 2)
        self.assertEqual(
            self.connection.execute("SELECT COUNT(*) FROM element_set").fetchone()[0], 0
        )

    def test_a_month_that_really_was_pruned_is_still_refused(self):
        """The guard being narrowed still has to catch the case it was built for."""
        bf.import_bundle(
            self.connection,
            write_bundle(self.root / "b.zip", [at_day(d, year="24") for d in (10, 11)]),
        )
        # Between the two element sets, so 2024-01 really does lose one row.
        cutoff = int(dt.datetime(2024, 1, 11, tzinfo=dt.timezone.utc).timestamp() * 1000)
        self.assertEqual(oh.prune_hot(self.connection, cutoff, force=True), 1)
        now_ms = int(
            dt.datetime(2026, 8, 8, tzinfo=dt.timezone.utc).timestamp() * 1000
        )
        report = oh.roll(
            self.connection,
            retain_days=400,
            cold_directory=self.root / "cold",
            now_ms=now_ms,
        )
        self.assertEqual([row["month"] for row in report["skipped"]], ["2024-01"])
        self.assertEqual(report["exported"], [])


class OfflineImportTest(unittest.TestCase):
    """The resumable half: import bytes already held, touching no network.

    The fetch happens once, because space-track asks callers to store the
    history rather than re-download it. Everything after that is local work
    that takes days on this hardware and will be interrupted, so it has to
    resume - and it must not be able to reach for the share to do so.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.connection = oh.open_archive(self.root / "archive.sqlite3")

    def tearDown(self):
        self.connection.close()
        self.tmp.cleanup()

    def _hold(self, name, pairs):
        path = write_bundle(self.root / name, pairs)
        manifest = bf.load_manifest(self.root)
        manifest["files"][name] = {
            "attempts": 1,
            "bytes": path.stat().st_size,
            "sha256": bf.sha256_of(path),
            "downloadedAt": bf._now_iso(),
        }
        bf.save_manifest(self.root, manifest)
        return path

    def _no_network(self):
        def refuse(*_args, **_kwargs):
            raise AssertionError("the offline import reached for the network")

        return unittest.mock.patch.multiple(
            bf, mint_urls=refuse, download_file=refuse, _open_range=refuse
        )

    def test_imports_held_bundles_without_touching_the_share(self):
        self._hold("tle2024.txt.zip", [VANGUARD_1, ALPHA5])
        with self._no_network():
            report = bf.import_held_years(
                years=[2024], directory=self.root,
                connection=self.connection, verbose=False,
            )
        self.assertEqual(report["rowsByYear"], {2024: 2})
        self.assertEqual(
            self.connection.execute("SELECT COUNT(*) FROM element_set").fetchone()[0], 2
        )

    def test_a_finished_bundle_is_skipped_on_the_next_run(self):
        self._hold("tle2024.txt.zip", [VANGUARD_1])
        with self._no_network():
            bf.import_held_years(
                years=[2024], directory=self.root,
                connection=self.connection, verbose=False,
            )
            again = bf.import_held_years(
                years=[2024], directory=self.root,
                connection=self.connection, verbose=False,
            )
        self.assertEqual(again["skipped"], ["tle2024.txt.zip"])
        self.assertEqual(again["imports"], [])

    def test_an_interrupted_bundle_is_re_read_rather_than_half_trusted(self):
        # No manifest `import` record means the previous run died part-way, as
        # the first real run of this backfill did at fifteen million rows. The
        # bundle is re-read, and the primary key makes that free of effect.
        path = self._hold("tle2024.txt.zip", [VANGUARD_1, ALPHA5])
        bf.import_bundle(self.connection, path)     # partial run, never marked
        with self._no_network():
            report = bf.import_held_years(
                years=[2024], directory=self.root,
                connection=self.connection, verbose=False,
            )
        self.assertEqual(report["imports"][0]["elementsNew"], 0)
        self.assertEqual(report["imports"][0]["duplicates"], 2)
        self.assertEqual(
            self.connection.execute("SELECT COUNT(*) FROM element_set").fetchone()[0], 2
        )

    def test_a_lock_pauses_the_bundle_instead_of_ending_the_run(self):
        """A multi-day job beside an hourly writer must survive being locked out.

        The real failure: `database is locked` from executemany, thirty-two
        minutes into a run, with a thirty-MINUTE busy timeout set and verified -
        so it was refused immediately rather than made to wait, which no busy
        handler can prevent. Re-reading a bundle costs time and nothing else,
        so a lock is a pause.
        """
        path = self._hold("tle2024.txt.zip", [VANGUARD_1, ALPHA5])
        calls = {"n": 0}
        real = bf.import_bundle

        def flaky(connection, target, **kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                raise sqlite3.OperationalError("database is locked")
            return real(connection, target, **kwargs)

        with unittest.mock.patch.object(bf, "import_bundle", flaky), \
                unittest.mock.patch.object(bf.time, "sleep"):
            result = bf._import_with_lock_retry(
                self.connection, path, verbose=False, pause_seconds=0
            )
        self.assertEqual(calls["n"], 2)
        self.assertEqual(result.elements_new, 2)

    def test_an_error_that_is_not_a_lock_is_raised_at_once(self):
        # Retrying a genuine fault just hides it for twelve attempts.
        path = self._hold("tle2024.txt.zip", [VANGUARD_1])
        with unittest.mock.patch.object(
            bf, "import_bundle",
            side_effect=sqlite3.OperationalError("no such table: element_set"),
        ):
            with self.assertRaises(sqlite3.OperationalError):
                bf._import_with_lock_retry(
                    self.connection, path, verbose=False, pause_seconds=0
                )

    def test_a_lock_that_never_clears_eventually_stops(self):
        path = self._hold("tle2024.txt.zip", [VANGUARD_1])
        with unittest.mock.patch.object(
            bf, "import_bundle",
            side_effect=sqlite3.OperationalError("database is locked"),
        ) as stub:
            with self.assertRaises(sqlite3.OperationalError):
                bf._import_with_lock_retry(
                    self.connection, path, verbose=False, attempts=3, pause_seconds=0
                )
        self.assertEqual(stub.call_count, 3)

    def test_a_year_whose_bytes_are_absent_is_reported_not_fetched(self):
        with self._no_network():
            report = bf.import_held_years(
                years=[2019], directory=self.root,
                connection=self.connection, verbose=False,
            )
        self.assertEqual(report["missing"], [2019])
        self.assertEqual(report["imports"], [])

    def test_a_truncated_bundle_is_not_treated_as_held(self):
        path = self._hold("tle2024.txt.zip", [VANGUARD_1])
        path.write_bytes(path.read_bytes()[:-10])
        manifest = bf.load_manifest(self.root)
        self.assertEqual(bf.held_bundles_for_year(self.root, manifest, 2024), [])

    def test_every_part_of_a_split_year_is_found(self):
        for part in (1, 2, 3):
            self._hold(f"tle2004_{part}of8.txt.zip", [VANGUARD_1])
        manifest = bf.load_manifest(self.root)
        self.assertEqual(
            bf.held_bundles_for_year(self.root, manifest, 2004),
            ["tle2004_1of8.txt.zip", "tle2004_2of8.txt.zip", "tle2004_3of8.txt.zip"],
        )

    def test_the_import_stands_back_after_every_commit(self):
        """The backfill must let go of the file between batches.

        On 2026-08-08 an 80-minute import of tle2024 made
        `spacetrack-ingest.service` fail twice with `database is locked` and
        lost two hourly captures of live GP elements, which nothing can
        back-fill. Small batches were not enough by themselves: back-to-back
        transactions never left a window inside the capture's 60-second busy
        timeout. The writer has to actually stop.
        """
        path = self._hold("tle2024.txt.zip", [VANGUARD_1, ALPHA5, NEGATIVE_BSTAR])
        slept: list[float] = []
        with unittest.mock.patch.object(bf.time, "sleep", slept.append):
            bf.import_bundle(self.connection, path, batch_rows=1)
        # Three rows, one batch each: the first takes the lock straight away,
        # and the two that follow wait first. Each wait long enough for a
        # capture that inserts 31,697 rows in 0.16 s.
        self.assertEqual(len(slept), 2)
        self.assertTrue(all(s >= 1.0 for s in slept), slept)
        self.assertGreaterEqual(bf.BATCH_YIELD_SECONDS, 1.0)

    def test_every_few_batches_it_stops_properly_not_briefly(self):
        """Four seconds is not a window, and the capture proved it.

        With the short yield already shipped, the 2026-08-09T05:00Z capture
        still died - and reported waiting nine seconds, not the nine hundred it
        was configured for, because a reader upgrading to a writer is refused
        immediately rather than made to wait. A job holding the file 95% of the
        time leaves an hourly job needing luck, so periodically it lets go for
        long enough that luck is not required.
        """
        pairs = [at_day(d, year="24") for d in range(100, 116)]
        path = self._hold("tle2024.txt.zip", pairs)
        slept: list[float] = []
        with unittest.mock.patch.object(bf.time, "sleep", slept.append):
            bf.import_bundle(
                self.connection, path, batch_rows=1,
                long_yield_every=6, long_yield_seconds=90.0,
            )
        long_waits = [s for s in slept if s >= 60.0]
        self.assertEqual(len(long_waits), 2, slept)   # after batches 6 and 12
        self.assertTrue(all(s == 90.0 for s in long_waits))
        # And the short yield still covers every other gap.
        self.assertEqual(len(slept), 15)

    def test_a_single_batch_import_does_not_wait_at_all(self):
        # Otherwise every caller, and every test, pays a needless pause per
        # bundle for a lock it is about to release anyway.
        path = self._hold("tle2024.txt.zip", [VANGUARD_1])
        with unittest.mock.patch.object(bf.time, "sleep") as sleep:
            result = bf.import_bundle(self.connection, path)
        sleep.assert_not_called()
        self.assertEqual(result.elements_new, 1)

    def test_the_yield_can_be_turned_off_for_a_private_archive(self):
        path = self._hold("tle2024.txt.zip", [VANGUARD_1, ALPHA5])
        with unittest.mock.patch.object(bf.time, "sleep") as sleep:
            bf.import_bundle(self.connection, path, batch_rows=1, yield_seconds=0)
        sleep.assert_not_called()

    def test_the_bulk_busy_timeout_is_far_longer_than_a_captures(self):
        # The first run died with "database is locked" after fifteen million
        # rows because it waited only as long as the hourly capture does.
        bf.tune_for_bulk(self.connection)
        held = self.connection.execute("PRAGMA busy_timeout").fetchone()[0]
        self.assertEqual(held, bf.BUSY_TIMEOUT_MS)
        self.assertGreaterEqual(bf.BUSY_TIMEOUT_MS, 10 * 60 * 1000)


if __name__ == "__main__":
    unittest.main()
