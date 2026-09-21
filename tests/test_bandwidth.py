"""Proofs for the bandwidth ledger. No network, no systemd, no clock.

Every assertion here is an arithmetic identity over a list of records, in the
same style as ``tests/test_watchdog.py`` and for the same reason: a model once
wrote an all-clear over 105 real warnings on this stack, so nothing on this
surface is allowed to be a judgement call.

The three properties worth defending, and all three have a history:

* **A byte total can never be reported from a source that did not report.**
  ``None`` and ``0`` are different answers and the second one is comfortable.
  Everything that renders a leg has to be able to tell them apart.
* **A projection always carries the window it was extrapolated from.** The
  figure that started this work — 538 GB/month — was an extrapolation from one
  hour, and it was right, but only by luck.
* **Wire bytes and raw bytes are never summed.** Totalling decoded response
  bodies once reported a cold visit as 13.97 MB when 1.71 MB left the machine,
  a fourfold overstatement of what hosting the site costs.
"""

from __future__ import annotations

import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path

from ops import bandwidth as bw

HOUR = 3600.0
DAY = 86400.0
#: A fixed instant, so nothing here depends on when it is run. Eight days into
#: a 31-day month, which is deliberately the awkward case: the tracker was
#: installed mid-month and a naive month-to-date reads as a quiet month.
NOW = dt.datetime(2026, 8, 8, 12, 0, tzinfo=dt.timezone.utc).timestamp()
MONTH_START = dt.datetime(2026, 8, 1, 0, 0, tzinfo=dt.timezone.utc).timestamp()


def entry(**kwargs) -> dict:
    base = {"schema": 1, "at": NOW, "leg": bw.BIGMEM_EGRESS, "family": "aurora",
            "bytes": 1000, "basis": bw.WIRE, "source": "test", "run": "test"}
    base.update(kwargs)
    return base


class UnmeasuredIsNotZero(unittest.TestCase):
    """The single most important property on this page."""

    def test_no_records_gives_none_not_zero(self):
        total = bw.totals([], leg=bw.BIGMEM_EGRESS, basis=bw.WIRE)
        self.assertIsNone(total.bytes)
        self.assertNotEqual(total.bytes, 0)
        self.assertFalse(total.measured)

    def test_a_measured_zero_is_zero_and_says_so(self):
        """rsync reporting that nothing moved is a measurement, not a blind spot."""
        total = bw.totals([entry(bytes=0)], leg=bw.BIGMEM_EGRESS, basis=bw.WIRE)
        self.assertEqual(total.bytes, 0)
        self.assertTrue(total.measured)

    def test_an_unmeasured_leg_has_no_projection(self):
        coverage = bw.Coverage(period_start=MONTH_START, period_end=MONTH_START + 31 * DAY,
                               now=NOW, first_record_at=None)
        self.assertIsNone(bw.project(bw.totals([], leg=bw.VPS_EGRESS, basis=bw.WIRE),
                                     coverage))

    def test_an_unmeasured_leg_has_no_share_of_allowance(self):
        window = bw.AllowanceWindow(bytes=1_250_000_000_000, unlimited=False,
                                    effective_from="2026-01-01", confirmed=True, note="")
        self.assertIsNone(bw.share_of_allowance(None, window))

    def test_summarise_leaves_unmeasured_legs_as_none(self):
        with tempfile.TemporaryDirectory() as room:
            ledger = Path(room) / "ledger.jsonl"
            bw.record(leg=bw.BIGMEM_EGRESS, family="aurora", byte_count=5, basis=bw.WIRE,
                      source="test", run="test", at=NOW, path=ledger)
            state = bw.summarise(NOW, path=ledger, allowances_path=Path(room) / "none.json")
        self.assertEqual(state["legs"][f"{bw.BIGMEM_EGRESS}/{bw.WIRE}"].bytes, 5)
        for leg in (bw.VPS_EGRESS, bw.VPS_INGRESS, bw.BIGMEM_INGRESS):
            self.assertIsNone(state["legs"][f"{leg}/{bw.WIRE}"].bytes,
                              f"{leg} reported a number nobody measured")


class WireAndRawNeverMix(unittest.TestCase):
    """The 13.97-MB-versus-1.71-MB trap, made structurally impossible."""

    RECORDS = [entry(bytes=100, basis=bw.WIRE), entry(bytes=400, basis=bw.RAW)]

    def test_a_wire_total_excludes_raw_records(self):
        self.assertEqual(bw.totals(self.RECORDS, leg=bw.BIGMEM_EGRESS, basis=bw.WIRE).bytes,
                         100)

    def test_a_raw_total_excludes_wire_records(self):
        self.assertEqual(bw.totals(self.RECORDS, leg=bw.BIGMEM_EGRESS, basis=bw.RAW).bytes,
                         400)

    def test_the_two_totals_do_not_sum_to_the_ledger(self):
        """If they did, one column would be double-counting the other."""
        wire = bw.totals(self.RECORDS, leg=bw.BIGMEM_EGRESS, basis=bw.WIRE).bytes
        raw = bw.totals(self.RECORDS, leg=bw.BIGMEM_EGRESS, basis=bw.RAW).bytes
        self.assertNotEqual(wire + raw, wire)
        self.assertNotEqual(wire + raw, raw)

    def test_an_unknown_basis_is_refused(self):
        with self.assertRaises(ValueError):
            bw.totals(self.RECORDS, leg=bw.BIGMEM_EGRESS, basis="bytes-ish")

    def test_a_record_with_an_unknown_basis_cannot_be_written(self):
        with tempfile.TemporaryDirectory() as room:
            with self.assertRaises(ValueError):
                bw.record(leg=bw.BIGMEM_EGRESS, family="aurora", byte_count=1,
                          basis="onthewire", source="test", run="test",
                          path=Path(room) / "l.jsonl")


class ProjectionIsAlwaysLabelled(unittest.TestCase):

    def coverage(self, first_record_at):
        return bw.Coverage(period_start=MONTH_START, period_end=MONTH_START + 31 * DAY,
                           now=NOW, first_record_at=first_record_at)

    def test_a_projection_carries_its_window_and_its_word(self):
        total = bw.totals([entry(bytes=2_000_000_000)], leg=bw.BIGMEM_EGRESS, basis=bw.WIRE)
        projection = bw.project(total, self.coverage(NOW - DAY))
        self.assertEqual(projection.label, "projection")
        self.assertIn("projection", projection.sentence())
        self.assertIn("days of measurement", projection.sentence())

    def test_the_rate_comes_from_the_measured_window_not_the_whole_period(self):
        """Installing the tracker on the 8th must not read as a quiet month.

        Two gigabytes measured over one day is 2 GB/day. Dividing the same two
        gigabytes by the seven and a half days that have elapsed would report
        0.27 GB/day -- a rate no instrument ever saw.
        """
        total = bw.totals([entry(bytes=2_000_000_000)], leg=bw.BIGMEM_EGRESS, basis=bw.WIRE)
        projection = bw.project(total, self.coverage(NOW - DAY))
        self.assertAlmostEqual(projection.per_day, 2_000_000_000, delta=1)
        self.assertAlmostEqual(projection.window_seconds, DAY, delta=1)

    def test_month_end_is_measured_plus_the_rate_over_what_is_left(self):
        coverage = self.coverage(NOW - DAY)
        total = bw.totals([entry(bytes=1_000_000_000)], leg=bw.BIGMEM_EGRESS, basis=bw.WIRE)
        projection = bw.project(total, coverage)
        expected = 1_000_000_000 + projection.per_day * (coverage.remaining_seconds / DAY)
        self.assertAlmostEqual(projection.period_total, expected, delta=1)

    def test_a_window_shorter_than_a_day_is_not_projectable(self):
        """Twelve minutes once projected one leg at 92% of the home allowance.

        A month-end figure needs a window that can contain the daily
        orbit-history rebuild, which is the largest single thing this site
        ships. Anything shorter is dominated by whatever happened to be
        transferring, and it renders identically to a trustworthy figure.
        """
        total = bw.totals([entry(bytes=700_000_000)], leg=bw.BIGMEM_EGRESS, basis=bw.WIRE)
        short = bw.project(total, self.coverage(NOW - 12 * 60))
        self.assertFalse(short.reliable)
        self.assertIn("too short to project", short.sentence())

    def test_a_full_day_is_projectable(self):
        total = bw.totals([entry(bytes=700_000_000)], leg=bw.BIGMEM_EGRESS, basis=bw.WIRE)
        self.assertTrue(bw.project(total, self.coverage(NOW - DAY)).reliable)

    def test_an_unreliable_projection_still_reports_the_rate_it_measured(self):
        """Refusing the month-end figure must not throw away the measurement."""
        total = bw.totals([entry(bytes=600_000_000)], leg=bw.BIGMEM_EGRESS, basis=bw.WIRE)
        short = bw.project(total, self.coverage(NOW - HOUR))
        self.assertAlmostEqual(short.per_day, 600_000_000 * 24, delta=1)
        self.assertIn("GB/day", short.rate_sentence())

    def test_a_projection_never_undercuts_what_has_already_been_measured(self):
        coverage = self.coverage(NOW - DAY)
        total = bw.totals([entry(bytes=9_000_000_000)], leg=bw.BIGMEM_EGRESS, basis=bw.WIRE)
        self.assertGreaterEqual(bw.project(total, coverage).period_total, 9_000_000_000)


class CoverageIsHonestAboutPartialMonths(unittest.TestCase):

    def test_a_ledger_that_starts_today_covers_only_today(self):
        coverage = bw.Coverage(period_start=MONTH_START, period_end=MONTH_START + 31 * DAY,
                               now=NOW, first_record_at=NOW - DAY)
        self.assertAlmostEqual(coverage.measured_seconds, DAY, delta=1)
        self.assertAlmostEqual(coverage.elapsed_seconds, 7.5 * DAY, delta=1)
        self.assertFalse(coverage.complete)

    def test_a_ledger_older_than_the_period_covers_all_of_it(self):
        coverage = bw.Coverage(period_start=MONTH_START, period_end=MONTH_START + 31 * DAY,
                               now=NOW, first_record_at=MONTH_START - 5 * DAY)
        self.assertAlmostEqual(coverage.fraction, 1.0, places=6)
        self.assertTrue(coverage.complete)

    def test_no_records_is_no_coverage_and_not_full_coverage(self):
        coverage = bw.Coverage(period_start=MONTH_START, period_end=MONTH_START + 31 * DAY,
                               now=NOW, first_record_at=None)
        self.assertEqual(coverage.measured_seconds, 0.0)
        self.assertFalse(coverage.complete)

    def test_days_remaining_plus_days_elapsed_is_the_period(self):
        coverage = bw.Coverage(period_start=MONTH_START, period_end=MONTH_START + 31 * DAY,
                               now=NOW, first_record_at=NOW)
        self.assertAlmostEqual(coverage.elapsed_seconds + coverage.remaining_seconds,
                               31 * DAY, delta=1)


class BillingPeriod(unittest.TestCase):

    def test_the_calendar_month_contains_now(self):
        start, end = bw.billing_period(NOW)
        self.assertLessEqual(start, NOW)
        self.assertGreater(end, NOW)

    def test_a_reset_day_after_today_belongs_to_the_previous_month(self):
        start, _ = bw.billing_period(NOW, start_day=20)
        self.assertEqual(dt.datetime.fromtimestamp(start, dt.timezone.utc).month, 7)

    def test_a_reset_day_before_today_belongs_to_this_month(self):
        start, _ = bw.billing_period(NOW, start_day=3)
        self.assertEqual(dt.datetime.fromtimestamp(start, dt.timezone.utc).day, 3)
        self.assertEqual(dt.datetime.fromtimestamp(start, dt.timezone.utc).month, 8)

    def test_no_reset_day_can_produce_an_empty_or_reversed_period(self):
        """A day-29 reset in February is the case that would break this."""
        for day in range(1, 32):
            for month in range(1, 13):
                moment = dt.datetime(2026, month, 15, tzinfo=dt.timezone.utc).timestamp()
                start, end = bw.billing_period(moment, start_day=day)
                self.assertLess(start, end, f"day={day} month={month}")
                self.assertLessEqual(start, moment)
                self.assertGreater(end, moment)


class FamilyAttribution(unittest.TestCase):
    """The breakdown that made the orbit-history problem findable."""

    def test_a_shard_is_attributed_to_the_layer_not_to_the_shard(self):
        self.assertEqual(bw.family_of("orbit-history-000-9fa48e9c34ba5330.json"),
                         "orbit-history")
        self.assertEqual(bw.family_of("orbit-history-255-864a7103f1a06c48.json.gz"),
                         "orbit-history")

    def test_every_known_family_round_trips(self):
        for family in bw.ARTIFACT_FAMILIES:
            if family == "orbit-history":
                continue
            self.assertEqual(bw.family_of(f"{family}-0123456789abcdef.json"), family)

    def test_an_unknown_prefix_is_named_other_rather_than_guessed(self):
        self.assertEqual(bw.family_of("brand-new-layer-0123456789abcdef.json"), "other")

    def test_the_family_column_sums_to_the_leg_total(self):
        records = [entry(family="aurora", bytes=10), entry(family="catalog", bytes=20),
                   entry(family="orbit-history", bytes=70)]
        rows = bw.by_family(records, leg=bw.BIGMEM_EGRESS, basis=bw.WIRE)
        self.assertEqual(sum(count for _, count, _ in rows),
                         bw.totals(records, leg=bw.BIGMEM_EGRESS, basis=bw.WIRE).bytes)

    def test_the_breakdown_is_ordered_largest_first(self):
        records = [entry(family="aurora", bytes=10), entry(family="orbit-history", bytes=70)]
        self.assertEqual(bw.by_family(records, leg=bw.BIGMEM_EGRESS, basis=bw.WIRE)[0][0],
                         "orbit-history")

    def test_a_record_naming_a_family_outside_the_vocabulary_is_refused(self):
        with tempfile.TemporaryDirectory() as room:
            with self.assertRaises(ValueError):
                bw.record(leg=bw.BIGMEM_EGRESS, family="whatever", byte_count=1,
                          basis=bw.WIRE, source="t", run="t", path=Path(room) / "l.jsonl")


class UpstreamAttribution(unittest.TestCase):

    def test_each_upstream_is_recognised(self):
        cases = {
            "https://services.swpc.noaa.gov/json/goes/primary/xrays-1-day.json": "noaa-swpc",
            "https://nomads.ncep.noaa.gov/pub/data/nccf/com/swmf/prod/x.out": "noaa-nomads-swmf",
            "https://nomads.ncep.noaa.gov/pub/data/nccf/com/wfs/prod/y.nc": "noaa-nomads-wam-ipe",
            "https://www.space-track.org/basicspacedata/query": "space-track",
            "https://celestrak.org/NORAD/elements/gp.php": "celestrak-mirror-pull",
        }
        for url, family in cases.items():
            self.assertEqual(bw.upstream_family(url), family, url)

    def test_an_unrecognised_host_is_named_rather_than_folded_in(self):
        self.assertEqual(bw.upstream_family("https://example.invalid/data.json"),
                         "other-upstream")


class RsyncParsing(unittest.TestCase):
    """The instrument on the leg Sean is actually watching."""

    OUTPUT = """XFER|193200|510|aurora-0123456789abcdef.json
XFER|193200|72|orbit-history-000-0123456789abcdef.json
XFER|193200|69|orbit-history-001-0123456789abcdef.json

Number of files: 7 (reg: 6, dir: 1)
Total file size: 1,159,200 bytes
Total bytes sent: 1,053
Total bytes received: 130
"""

    def test_the_wire_total_is_read_from_the_stats_block(self):
        self.assertEqual(bw.parse_rsync(self.OUTPUT)["totalSent"], 1053)

    def test_thousands_separators_do_not_break_the_parse(self):
        """A comma in 'fetched 6,824,528 bytes' has already broken one regex here."""
        self.assertEqual(bw.parse_rsync(self.OUTPUT)["totalReceived"], 130)

    def test_per_file_bytes_are_the_compressed_ones_not_the_file_length(self):
        parsed = bw.parse_rsync(self.OUTPUT)
        self.assertEqual(parsed["perFileWire"], 510 + 72 + 69)
        self.assertEqual(parsed["perFileRaw"], 193200 * 3)
        self.assertLess(parsed["perFileWire"], parsed["perFileRaw"])

    def test_the_overhead_residual_closes_the_gap_exactly(self):
        parsed = bw.parse_rsync(self.OUTPUT)
        self.assertEqual(parsed["perFileWire"] + parsed["overhead"], parsed["totalSent"])

    def test_output_with_no_stats_block_reports_nothing_rather_than_zero(self):
        parsed = bw.parse_rsync("XFER|1|1|aurora-0123456789abcdef.json\n")
        self.assertIsNone(parsed["totalSent"])
        self.assertIsNone(parsed["overhead"])

    def test_a_run_that_never_printed_stats_records_nothing(self):
        """An rsync that died has not transferred a known number of bytes."""
        with tempfile.TemporaryDirectory() as room:
            ledger = Path(room) / "l.jsonl"
            result = bw.record_rsync_push("rsync: connection unexpectedly closed",
                                          run="test", path=ledger)
            self.assertEqual(result["recorded"], 0)
            self.assertFalse(ledger.exists())

    def test_a_recorded_push_sums_to_the_measured_total(self):
        with tempfile.TemporaryDirectory() as room:
            ledger = Path(room) / "l.jsonl"
            bw.record_rsync_push(self.OUTPUT, run="test", path=ledger, at=NOW)
            records = bw.read(ledger)
            total = bw.totals(records, leg=bw.BIGMEM_EGRESS, basis=bw.WIRE)
            self.assertEqual(total.bytes, 1053)

    def test_the_layer_split_of_a_recorded_push_is_measured_not_apportioned(self):
        with tempfile.TemporaryDirectory() as room:
            ledger = Path(room) / "l.jsonl"
            bw.record_rsync_push(self.OUTPUT, run="test", path=ledger, at=NOW)
            rows = dict((name, count) for name, count, _ in
                        bw.by_family(bw.read(ledger), leg=bw.BIGMEM_EGRESS, basis=bw.WIRE))
        self.assertEqual(rows["aurora"], 510)
        self.assertEqual(rows["orbit-history"], 72 + 69)
        self.assertEqual(rows[bw.PROTOCOL_FAMILY], 1053 - (510 + 72 + 69))

    def test_a_pull_is_ingress_and_never_egress(self):
        """Counting the mirror pull as egress would inflate the number Sean watches."""
        with tempfile.TemporaryDirectory() as room:
            ledger = Path(room) / "l.jsonl"
            bw.record_rsync_pull(self.OUTPUT, run="test", path=ledger, at=NOW)
            records = bw.read(ledger)
        self.assertIsNone(bw.totals(records, leg=bw.BIGMEM_EGRESS, basis=bw.WIRE).bytes)
        self.assertEqual(bw.totals(records, leg=bw.BIGMEM_INGRESS, basis=bw.WIRE).bytes, 130)

    def test_forcing_a_family_keeps_ops_pages_out_of_other(self):
        with tempfile.TemporaryDirectory() as room:
            ledger = Path(room) / "l.jsonl"
            bw.record_rsync_push("XFER|10|4|watchdog.html\nTotal bytes sent: 4\n",
                                 run="test", path=ledger, at=NOW,
                                 force_family=bw.OPS_PAGES_FAMILY)
            rows = dict((name, count) for name, count, _ in
                        bw.by_family(bw.read(ledger), leg=bw.BIGMEM_EGRESS, basis=bw.WIRE))
        self.assertEqual(rows.get(bw.OPS_PAGES_FAMILY), 4)
        self.assertNotIn(bw.OTHER_FAMILY, rows)


class CounterDeltas(unittest.TestCase):
    """WireGuard and nginx are counters, not totals. This is where that goes wrong."""

    def sample(self, room, value, at):
        return bw.record_wireguard(value, peer="peer-a", run="test",
                                   cursor=Path(room) / "cursor.json",
                                   path=Path(room) / "l.jsonl", at=at)

    def test_the_first_sample_records_nothing(self):
        """A lifetime counter read once is not one interval's traffic."""
        with tempfile.TemporaryDirectory() as room:
            self.assertEqual(self.sample(room, 8_000_000_000, NOW)["recorded"], 0)
            self.assertEqual(bw.read(Path(room) / "l.jsonl"), [])

    def test_the_second_sample_records_the_difference_only(self):
        with tempfile.TemporaryDirectory() as room:
            self.sample(room, 8_000_000_000, NOW)
            self.sample(room, 8_000_001_500, NOW + 300)
            total = bw.totals(bw.read(Path(room) / "l.jsonl"),
                              leg=bw.VPS_INGRESS, basis=bw.WIRE)
            self.assertEqual(total.bytes, 1500)

    def test_a_counter_reset_records_nothing_rather_than_a_negative_or_a_total(self):
        with tempfile.TemporaryDirectory() as room:
            self.sample(room, 8_000_000_000, NOW)
            outcome = self.sample(room, 12_000, NOW + 300)
            self.assertEqual(outcome["recorded"], 0)
            self.assertIn("reset", outcome["reason"])
            self.assertEqual(bw.read(Path(room) / "l.jsonl"), [])

    def test_it_re_bases_after_a_reset_and_keeps_counting(self):
        with tempfile.TemporaryDirectory() as room:
            self.sample(room, 8_000_000_000, NOW)
            self.sample(room, 12_000, NOW + 300)
            self.sample(room, 13_000, NOW + 600)
            total = bw.totals(bw.read(Path(room) / "l.jsonl"),
                              leg=bw.VPS_INGRESS, basis=bw.WIRE)
            self.assertEqual(total.bytes, 1000)

    def test_a_probe_that_did_not_answer_records_nothing(self):
        with tempfile.TemporaryDirectory() as room:
            self.assertEqual(self.sample(room, None, NOW)["recorded"], 0)

    def test_the_origin_upper_bound_is_recorded_as_raw_never_as_wire(self):
        """It is uncompressed at the origin; a wire column must not contain it."""
        with tempfile.TemporaryDirectory() as room:
            cursor, ledger = Path(room) / "c.json", Path(room) / "l.jsonl"
            bw.record_origin_egress(1000, 5, run="t", cursor=cursor, path=ledger, at=NOW)
            bw.record_origin_egress(3000, 9, run="t", cursor=cursor, path=ledger,
                                    at=NOW + 300)
            records = bw.read(ledger)
        self.assertIsNone(bw.totals(records, leg=bw.VPS_EGRESS, basis=bw.WIRE).bytes)
        self.assertEqual(bw.totals(records, leg=bw.VPS_EGRESS, basis=bw.RAW).bytes, 2000)


class CrossCheckIsShownNotReconciled(unittest.TestCase):

    def test_two_close_numbers_agree(self):
        gap = bw.Disagreement("rsync", 1_000_000, "wireguard", 1_050_000)
        self.assertTrue(gap.agrees)
        self.assertIn("agree", gap.sentence())

    def test_a_large_gap_is_reported_as_a_disagreement(self):
        gap = bw.Disagreement("rsync", 1_000_000, "wireguard", 4_000_000)
        self.assertFalse(gap.agrees)
        self.assertIn("DISAGREE", gap.sentence())

    def test_neither_side_is_silently_preferred(self):
        gap = bw.Disagreement("rsync", 1_000_000, "wireguard", 4_000_000)
        self.assertIn("1,000,000", gap.sentence())
        self.assertIn("4,000,000", gap.sentence())

    def test_one_missing_side_is_not_an_agreement(self):
        gap = bw.Disagreement("rsync", 1_000_000, "wireguard", None)
        self.assertIsNone(gap.agrees)
        self.assertIn("no measurement", gap.sentence())

    def test_the_delta_is_the_far_end_minus_the_near_one(self):
        self.assertEqual(bw.Disagreement("a", 100, "b", 130).delta, 30)

    def test_one_wireguard_sample_is_not_a_comparison_and_not_a_disagreement(self):
        """The instruments wake up at different times; that is not a finding."""
        records = [entry(bytes=93_000_000),
                   entry(leg=bw.VPS_INGRESS, family="site-total", bytes=33_000_000)]
        gap = bw.cross_check(records)
        self.assertIsNone(gap.agrees)
        self.assertIn("not a disagreement", gap.sentence())

    def test_the_comparison_uses_only_the_window_both_instruments_covered(self):
        """A month-to-date against a month-to-date compares different windows."""
        records = [
            # Before the WireGuard counter had been sampled twice. Real
            # traffic, but nothing at the far end measured that interval.
            entry(bytes=500_000, at=NOW),
            entry(leg=bw.VPS_INGRESS, family="site-total", bytes=0, at=NOW + 60),
            # Inside the comparable window.
            entry(bytes=1_000_000, at=NOW + 120),
            entry(leg=bw.VPS_INGRESS, family="site-total", bytes=1_050_000, at=NOW + 180),
        ]
        gap = bw.cross_check(records)
        self.assertEqual(gap.left, 1_000_000)
        self.assertEqual(gap.right, 1_050_000)
        self.assertTrue(gap.agrees)

    def test_a_real_gap_inside_the_common_window_is_still_reported(self):
        records = [
            entry(leg=bw.VPS_INGRESS, family="site-total", bytes=0, at=NOW),
            entry(bytes=1_000_000, at=NOW + 60),
            entry(leg=bw.VPS_INGRESS, family="site-total", bytes=9_000_000, at=NOW + 120),
        ]
        self.assertFalse(bw.cross_check(records).agrees)


class Allowances(unittest.TestCase):

    def window(self, **kwargs):
        base = dict(bytes=1_250_000_000_000, unlimited=False,
                    effective_from="2026-01-01", confirmed=True, note="")
        base.update(kwargs)
        return bw.AllowanceWindow(**base)

    def test_an_unlimited_plan_never_divides_by_zero(self):
        window = self.window(bytes=None, unlimited=True)
        self.assertIsNone(bw.share_of_allowance(999_000_000_000, window))

    def test_an_announced_change_with_no_date_is_not_in_force(self):
        """'later this week' is not a date, and must not silently take effect."""
        allowance = bw.Allowance(
            key="home", label="home", counts="both", billing_start_day=1,
            billing_day_confirmed=False,
            windows=(self.window(),),
            announced=(self.window(bytes=None, unlimited=True, effective_from=None),),
        )
        in_force = allowance.at(NOW)
        self.assertFalse(in_force.unlimited)
        self.assertEqual(in_force.bytes, 1_250_000_000_000)

    def test_a_dated_change_takes_effect_on_its_date_and_not_before(self):
        later = self.window(bytes=None, unlimited=True, effective_from="2026-08-15")
        allowance = bw.Allowance(key="home", label="home", counts="both",
                                 billing_start_day=1, billing_day_confirmed=False,
                                 windows=(self.window(), later))
        before = dt.datetime(2026, 8, 14, tzinfo=dt.timezone.utc).timestamp()
        after = dt.datetime(2026, 8, 16, tzinfo=dt.timezone.utc).timestamp()
        self.assertFalse(allowance.at(before).unlimited)
        self.assertTrue(allowance.at(after).unlimited)

    def test_the_shipped_file_parses_and_names_who_confirmed_each_number(self):
        allowances = bw.load_allowances(bw.ALLOWANCES)
        self.assertIn("home", allowances)
        self.assertIn("vps", allowances)
        self.assertEqual(allowances["vps"].counts, "egress only")
        for key, allowance in allowances.items():
            self.assertTrue(allowance.source_note,
                            f"{key} states a number with no provenance")

    def test_a_missing_file_yields_nothing_rather_than_a_default(self):
        """An invented allowance would look exactly like a confirmed one."""
        with tempfile.TemporaryDirectory() as room:
            self.assertEqual(bw.load_allowances(Path(room) / "absent.json"), {})

    def test_no_allowance_constant_is_hard_coded_in_the_module(self):
        source = Path(bw.__file__).read_text()
        for forbidden in ("1_250_000_000_000", "3_000_000_000_000", "1.25e12", "3e12"):
            self.assertNotIn(forbidden, source,
                             "an allowance belongs in ops/allowances.json, not in code")


class RebuildCost(unittest.TestCase):
    """What one orbit-history rebuild costs, which is what makes cadence a choice."""

    def push(self, ledger, at, byte_count):
        bw.record(leg=bw.BIGMEM_EGRESS, family="orbit-history", byte_count=byte_count,
                  basis=bw.WIRE, source="test", run="publish", at=at, path=ledger)

    def test_bursts_separated_by_an_hour_are_separate_rebuilds(self):
        with tempfile.TemporaryDirectory() as room:
            ledger = Path(room) / "l.jsonl"
            self.push(ledger, NOW, 100)
            self.push(ledger, NOW + 300, 200)          # same rebuild
            self.push(ledger, NOW + 4 * HOUR, 500)     # the next one
            episodes = bw.bursts(bw.read(ledger), leg=bw.BIGMEM_EGRESS,
                                 basis=bw.WIRE, family="orbit-history")
        self.assertEqual([e["bytes"] for e in episodes], [300, 500])

    def test_an_episode_still_shipping_is_not_counted(self):
        """A half-sent rebuild averaged in understates every cadence's cost."""
        with tempfile.TemporaryDirectory() as room:
            ledger = Path(room) / "l.jsonl"
            self.push(ledger, NOW, 7)
            cost = bw.rebuild_cost(bw.read(ledger), now=NOW + 60)
        self.assertFalse(cost["measured"])

    def test_one_finished_episode_is_enough(self):
        """At a daily cadence, 'wait for the second' means a day of not knowing."""
        with tempfile.TemporaryDirectory() as room:
            ledger = Path(room) / "l.jsonl"
            self.push(ledger, NOW, 1000)
            cost = bw.rebuild_cost(bw.read(ledger), now=NOW + 2 * HOUR)
        self.assertTrue(cost["measured"])
        self.assertEqual(cost["bytes"], 1000)

    def test_a_finished_and_an_unfinished_episode_average_only_the_finished_one(self):
        with tempfile.TemporaryDirectory() as room:
            ledger = Path(room) / "l.jsonl"
            self.push(ledger, NOW, 1000)
            self.push(ledger, NOW + 4 * HOUR, 7)
            cost = bw.rebuild_cost(bw.read(ledger), now=NOW + 4 * HOUR + 60)
        self.assertEqual(cost["bytes"], 1000)
        self.assertEqual(cost["episodes"], 1)

    def test_with_nothing_observed_it_falls_back_and_says_so(self):
        cost = bw.rebuild_cost([], now=NOW)
        self.assertFalse(cost["measured"])
        self.assertIn("not measured by this page", cost["note"])


class LedgerIntegrity(unittest.TestCase):

    def test_a_record_missing_its_instrument_is_refused(self):
        with tempfile.TemporaryDirectory() as room:
            with self.assertRaises(ValueError):
                bw.record(leg=bw.BIGMEM_EGRESS, family="aurora", byte_count=1,
                          basis=bw.WIRE, source="", run="t", path=Path(room) / "l.jsonl")

    def test_negative_bytes_are_refused(self):
        with tempfile.TemporaryDirectory() as room:
            with self.assertRaises(ValueError):
                bw.record(leg=bw.BIGMEM_EGRESS, family="aurora", byte_count=-1,
                          basis=bw.WIRE, source="t", run="t", path=Path(room) / "l.jsonl")

    def test_an_unknown_leg_is_refused(self):
        with tempfile.TemporaryDirectory() as room:
            with self.assertRaises(ValueError):
                bw.record(leg="somewhere-else", family="aurora", byte_count=1,
                          basis=bw.WIRE, source="t", run="t", path=Path(room) / "l.jsonl")

    def test_a_corrupt_line_is_skipped_and_the_rest_still_counts(self):
        with tempfile.TemporaryDirectory() as room:
            ledger = Path(room) / "l.jsonl"
            bw.record(leg=bw.BIGMEM_EGRESS, family="aurora", byte_count=7, basis=bw.WIRE,
                      source="t", run="t", at=NOW, path=ledger)
            with ledger.open("a") as handle:
                handle.write("{not json at all\n")
            self.assertEqual(bw.totals(bw.read(ledger), leg=bw.BIGMEM_EGRESS,
                                       basis=bw.WIRE).bytes, 7)

    def test_the_window_filter_excludes_records_outside_the_period(self):
        with tempfile.TemporaryDirectory() as room:
            ledger = Path(room) / "l.jsonl"
            bw.record(leg=bw.BIGMEM_EGRESS, family="aurora", byte_count=5, basis=bw.WIRE,
                      source="t", run="t", at=MONTH_START - DAY, path=ledger)
            bw.record(leg=bw.BIGMEM_EGRESS, family="aurora", byte_count=6, basis=bw.WIRE,
                      source="t", run="t", at=NOW, path=ledger)
            inside = bw.read(ledger, since=MONTH_START)
        self.assertEqual(bw.totals(inside, leg=bw.BIGMEM_EGRESS, basis=bw.WIRE).bytes, 6)

    def test_trimming_keeps_the_newest_records(self):
        with tempfile.TemporaryDirectory() as room:
            ledger = Path(room) / "l.jsonl"
            for index in range(40):
                bw.record(leg=bw.BIGMEM_EGRESS, family="aurora", byte_count=index,
                          basis=bw.WIRE, source="t", run="t", at=NOW + index, path=ledger)
            bw.trim(ledger, limit=20)
            records = bw.read(ledger)
        self.assertEqual(len(records), 10)
        self.assertEqual(records[-1]["bytes"], 39)


class VisitPayload(unittest.TestCase):

    def test_visits_supported_is_the_allowance_over_one_visit(self):
        window = bw.AllowanceWindow(bytes=3_000_000_000_000, unlimited=False,
                                    effective_from="2026-01-01", confirmed=True, note="")
        self.assertAlmostEqual(bw.visits_supported(window, {"wireBytes": 1_650_000}),
                               3_000_000_000_000 / 1_650_000, places=3)

    def test_an_unlimited_allowance_supports_no_finite_count(self):
        window = bw.AllowanceWindow(bytes=None, unlimited=True, effective_from="2026-01-01",
                                    confirmed=False, note="")
        self.assertIsNone(bw.visits_supported(window, {"wireBytes": 1_650_000}))

    def test_with_no_measurement_there_is_no_visit_count(self):
        window = bw.AllowanceWindow(bytes=3_000_000_000_000, unlimited=False,
                                    effective_from="2026-01-01", confirmed=True, note="")
        self.assertIsNone(bw.visits_supported(window, None))

    def test_a_malformed_visit_file_reads_as_no_measurement(self):
        with tempfile.TemporaryDirectory() as room:
            path = Path(room) / "visit.json"
            path.write_text(json.dumps({"wireBytes": "quite a lot"}))
            self.assertIsNone(bw.read_visit(path))


if __name__ == "__main__":
    unittest.main()
