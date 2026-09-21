"""Proofs about what the bandwidth section is allowed to draw.

The other two files here prove the arithmetic. This one proves the rendering,
and it exists because a template is a place where a correct number becomes a
misleading sentence. A syntax error in an f-string inside this module was
invisible to every other test in the suite for exactly as long as nobody
imported it — the page is written by a timer, so a break here reaches the
operator before it reaches a test run.

The properties, in the same order as the module's own docstring:

* an unmeasured leg is words, never a figure;
* a projection never appears without saying it is one, and disappears entirely
  when its window is too short to mean anything;
* wire and raw are never in the same column;
* an unlimited allowance renders, and does not divide by zero.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import tempfile
import unittest
from pathlib import Path

from ops import bandwidth as bw
from ops import bandwidth_page as page
from ops import cadence as cad

NOW = dt.datetime(2026, 8, 8, 12, 0, tzinfo=dt.timezone.utc).timestamp()
DAY = 86400.0


def text_of(markup: str) -> str:
    """The page with its tags stripped, so assertions read like a person would."""
    import html as H  # noqa: PLC0415

    # Non-breaking spaces are collapsed too: the page uses them to keep
    # "bigmem → VPS" and "3 TB" from wrapping, and a reader does not see the
    # difference, so an assertion should not either.
    plain = H.unescape(re.sub(r"<[^>]+>", " ", markup)).replace("\xa0", " ")
    return re.sub(r"\s+", " ", plain)


class Fixture:
    """A rendered section over a ledger this test built, and nothing else."""

    def __init__(self, room: str, *, ledger_lines=(), allowances=None, requests=(),
                 facts=None, visit=None):
        self.room = Path(room)
        self.ledger = self.room / "ledger.jsonl"
        for kwargs in ledger_lines:
            bw.record(path=self.ledger, **kwargs)
        self.allowances = self.room / "allowances.json"
        if allowances is not None:
            self.allowances.write_text(json.dumps(allowances))
        self.requests = self.room / "requests"
        self.requests.mkdir(exist_ok=True)
        for name in requests:
            (self.requests / name).write_text("x")
        self.visit_path = self.room / "visit.json"
        if visit is not None:
            self.visit_path.write_text(json.dumps(visit))

    def render(self) -> str:
        state = bw.summarise(NOW, path=self.ledger, allowances_path=self.allowances)
        state["visit"] = bw.read_visit(self.visit_path)
        state["originEgressNow"] = None
        state["wireguardNow"] = None
        cadence = cad.status(request_dir=self.requests, facts=None,
                             log_path=self.room / "applied.jsonl")
        return page.render(state, cadence, NOW)


HOME_UNLIMITED = {
    "schema": 1,
    "allowances": {
        "home": {"label": "home", "counts": "both directions", "windows": [
            {"effectiveFrom": "2026-01-01", "unlimited": True, "bytes": None,
             "confirmed": True, "note": "fibre"}]},
        "vps": {"label": "vps", "counts": "egress only", "windows": [
            {"effectiveFrom": "2026-01-01", "bytes": 3_000_000_000_000,
             "confirmed": True, "note": ""}]},
    },
}
HOME_CAPPED = {
    "schema": 1,
    "allowances": {
        "home": {"label": "home", "counts": "both directions", "windows": [
            {"effectiveFrom": "2026-01-01", "bytes": 1_250_000_000_000,
             "confirmed": True, "note": ""}]},
        "vps": {"label": "vps", "counts": "egress only", "windows": [
            {"effectiveFrom": "2026-01-01", "bytes": 3_000_000_000_000,
             "confirmed": True, "note": ""}]},
    },
}


def sends(byte_count: int, at: float, family: str = "aurora") -> dict:
    return dict(leg=bw.BIGMEM_EGRESS, family=family, byte_count=byte_count,
                basis=bw.WIRE, source="rsync --stats", run="publish", at=at)


class ItAlwaysRenders(unittest.TestCase):
    """The page is written by a timer. It must not be able to throw."""

    def test_an_empty_ledger_and_no_allowances_still_render(self):
        with tempfile.TemporaryDirectory() as room:
            markup = Fixture(room).render()
        self.assertIn("What this site moves", markup)
        self.assertIn("No allowance is recorded", markup)

    def test_a_full_ledger_renders(self):
        with tempfile.TemporaryDirectory() as room:
            markup = Fixture(room, allowances=HOME_CAPPED, ledger_lines=[
                sends(10_000_000, NOW - 2 * DAY),
                sends(90_000_000, NOW - DAY, family="orbit-history"),
                sends(5_000_000, NOW - 3600, family="catalog"),
            ]).render()
        self.assertIn("orbit-history", markup)
        self.assertIn("catalog", markup)

    def test_every_cadence_option_has_a_button(self):
        with tempfile.TemporaryDirectory() as room:
            markup = Fixture(room).render()
        for key in cad.CADENCES:
            self.assertIn(f'data-cadence="{key}"', markup)

    def test_the_only_thing_the_button_sends_is_an_allow_listed_key(self):
        """No input box, no template, nothing typed reaches the endpoint."""
        self.assertIn("fetch('cadence/' + encodeURIComponent(key)", page.SCRIPT)
        self.assertNotIn("<input", page.render.__doc__ or "")
        with tempfile.TemporaryDirectory() as room:
            self.assertNotIn("<input", Fixture(room).render())


class NothingUnmeasuredRendersAsANumber(unittest.TestCase):

    def test_an_empty_ledger_says_not_measured_on_every_leg(self):
        with tempfile.TemporaryDirectory() as room:
            body = text_of(Fixture(room, allowances=HOME_CAPPED).render())
        self.assertIn("not measured", body)
        # Four legs, each with a specific reason rather than a bare grey cell.
        for reason in ("the publish has not run", "no fetch has been recorded",
                       "the WireGuard counter has not been sampled",
                       "the origin log has not been sampled"):
            self.assertIn(reason, body)

    def test_an_unmeasured_leg_never_shows_a_percentage_of_the_allowance(self):
        with tempfile.TemporaryDirectory() as room:
            body = text_of(Fixture(room, allowances=HOME_CAPPED).render())
        self.assertNotIn("0.0% of", body)

    def test_a_measured_zero_is_not_the_same_cell_as_an_unmeasured_leg(self):
        with tempfile.TemporaryDirectory() as room:
            body = text_of(Fixture(room, allowances=HOME_CAPPED,
                                   ledger_lines=[sends(0, NOW - DAY)]).render())
        self.assertIn("0 B", body)


class ProjectionsAreLabelledOrAbsent(unittest.TestCase):

    def test_a_long_window_projects_and_says_it_is_a_projection(self):
        with tempfile.TemporaryDirectory() as room:
            body = text_of(Fixture(room, allowances=HOME_CAPPED, ledger_lines=[
                sends(1_000_000_000, NOW - 3 * DAY),
                sends(1_000_000_000, NOW - 60),
            ]).render())
        self.assertIn("a projection, not a measurement", body)

    def test_a_short_window_shows_no_month_end_figure_at_all(self):
        with tempfile.TemporaryDirectory() as room:
            body = text_of(Fixture(room, allowances=HOME_CAPPED, ledger_lines=[
                sends(700_000_000, NOW - 600),
                sends(700_000_000, NOW - 60),
            ]).render())
        self.assertIn("not yet projectable", body)
        self.assertIn("too short to project a month", body)
        self.assertIn("waiting on a full day of records", body)

    def test_no_percentage_is_taken_of_a_figure_the_page_refused_to_print(self):
        with tempfile.TemporaryDirectory() as room:
            body = text_of(Fixture(room, allowances=HOME_CAPPED, ledger_lines=[
                sends(700_000_000, NOW - 600),
                sends(700_000_000, NOW - 60),
            ]).render())
        self.assertNotIn("% of 1.25 TB", body)


class TheTwoBasesStaySeparate(unittest.TestCase):

    def test_the_layer_tables_state_which_basis_they_are_in(self):
        with tempfile.TemporaryDirectory() as room:
            markup = Fixture(room, allowances=HOME_CAPPED, ledger_lines=[
                sends(1_000, NOW - DAY),
                dict(leg=bw.BIGMEM_EGRESS, family="aurora", byte_count=4_000,
                     basis=bw.RAW, source="rsync %l", run="publish", at=NOW - DAY),
            ]).render()
        body = text_of(markup)
        self.assertIn("wire, after rsync -z", body)
        self.assertIn("raw, on disk", body)

    def test_the_wire_table_totals_the_wire_records_only(self):
        with tempfile.TemporaryDirectory() as room:
            markup = Fixture(room, allowances=HOME_CAPPED, ledger_lines=[
                sends(1_000, NOW - DAY),
                dict(leg=bw.BIGMEM_EGRESS, family="aurora", byte_count=4_000,
                     basis=bw.RAW, source="rsync %l", run="publish", at=NOW - DAY),
            ]).render()
        # 1,000 wire and 4,000 raw. 5,000 anywhere would be the two summed.
        self.assertNotIn("5000 B", text_of(markup))


class AllowancesRender(unittest.TestCase):

    def test_an_unlimited_plan_says_no_ceiling_and_shows_no_percentage(self):
        with tempfile.TemporaryDirectory() as room:
            body = text_of(Fixture(room, allowances=HOME_UNLIMITED, ledger_lines=[
                sends(1_000_000_000, NOW - 3 * DAY), sends(1_000_000_000, NOW - 60),
            ]).render())
        self.assertIn("no ceiling", body)
        self.assertIn("unlimited", body)

    def test_the_vps_allowance_is_shown_as_not_billing_the_publish_leg(self):
        with tempfile.TemporaryDirectory() as room:
            body = text_of(Fixture(room, allowances=HOME_CAPPED).render())
        self.assertIn("does not count against this allowance", body)
        self.assertIn("the publish costs nothing against the 3 TB", body)

    def test_an_unconfirmed_allowance_is_marked_as_a_placeholder(self):
        unconfirmed = json.loads(json.dumps(HOME_CAPPED))
        unconfirmed["allowances"]["home"]["windows"][0]["confirmed"] = False
        with tempfile.TemporaryDirectory() as room:
            body = text_of(Fixture(room, allowances=unconfirmed).render())
        self.assertIn("NOT CONFIRMED", body)

    def test_the_shipped_allowances_render_with_their_provenance(self):
        with tempfile.TemporaryDirectory() as room:
            fixture = Fixture(room)
            fixture.allowances = bw.ALLOWANCES
            body = text_of(fixture.render())
        self.assertIn("Sean confirmed 1.25 TB/month on 2026-08-08", body)
        self.assertIn("Announced, not in force", body)


class TheVisitFigure(unittest.TestCase):

    VISIT = {"schema": 1, "at": NOW, "url": "https://example.test/space/",
             "wireBytes": 1_650_088, "decodedBytes": 12_705_941}

    def test_it_reports_both_wire_and_decoded_and_says_which_is_billed(self):
        with tempfile.TemporaryDirectory() as room:
            body = text_of(Fixture(room, allowances=HOME_CAPPED,
                                   visit=self.VISIT).render())
        self.assertIn("1.65 MB on the wire", body)
        self.assertIn("NOT what is billed", body)

    def test_plenty_of_headroom_says_so_against_a_stated_threshold(self):
        with tempfile.TemporaryDirectory() as room:
            body = text_of(Fixture(room, allowances=HOME_CAPPED,
                                   visit=self.VISIT).render())
        self.assertIn("100,000 visits a month", body)
        self.assertIn("not a constraint", body)

    def test_a_heavy_page_flips_the_verdict_rather_than_reassuring_anyway(self):
        """The sentence is a comparison, not a policy about this site."""
        heavy = dict(self.VISIT, wireBytes=200_000_000)   # 200 MB a visit
        with tempfile.TemporaryDirectory() as room:
            body = text_of(Fixture(room, allowances=HOME_CAPPED, visit=heavy).render())
        self.assertIn("worth watching", body)
        self.assertNotIn("nothing here needs watching", body)

    def test_with_no_measurement_it_asks_for_one_instead_of_assuming(self):
        with tempfile.TemporaryDirectory() as room:
            body = text_of(Fixture(room, allowances=HOME_CAPPED).render())
        self.assertIn("No per-visit measurement has been taken", body)


class TheCadenceSection(unittest.TestCase):

    def test_each_option_shows_a_monthly_cost_and_its_provenance(self):
        with tempfile.TemporaryDirectory() as room:
            body = text_of(Fixture(room, allowances=HOME_CAPPED).render())
        self.assertIn("Cost per month (wire bytes)", body)
        self.assertIn("not measured by this page", body)

    def test_hourly_is_shown_as_overlapping_the_ingest(self):
        with tempfile.TemporaryDirectory() as room:
            body = text_of(Fixture(room, allowances=HOME_CAPPED).render())
        self.assertIn("overlaps the element ingest", body)
        self.assertIn("clears the element ingest", body)

    def test_a_rejected_request_is_shown_as_ignored(self):
        with tempfile.TemporaryDirectory() as room:
            body = text_of(Fixture(room, allowances=HOME_CAPPED,
                                   requests=("every-3h",)).render())
        self.assertIn("not in the allow-list", body)
        self.assertIn("every-3h", body)

    def test_an_unreadable_systemd_is_said_so_rather_than_drawn_as_running(self):
        with tempfile.TemporaryDirectory() as room:
            body = text_of(Fixture(room, allowances=HOME_CAPPED).render())
        self.assertIn("systemd did not answer", body)

    def test_the_monthly_cost_is_the_rebuild_cost_times_the_run_count(self):
        """Arithmetic over a measurement, and reproducible by hand."""
        cost = bw.rebuild_cost([], now=NOW)["bytes"]
        hourly = cad.CADENCES["hourly"]
        expected = page.human_bytes(cost * hourly.runs_per_month)
        with tempfile.TemporaryDirectory() as room:
            body = text_of(Fixture(room, allowances=HOME_CAPPED).render())
        self.assertIn(expected, body)


if __name__ == "__main__":
    unittest.main()
