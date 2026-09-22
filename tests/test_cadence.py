"""Proofs for the cadence control. No network, no real systemd, no clock.

This is the one thing on this surface that WRITES, and what it writes is a unit
file on a personal machine. So the assertions here are not about display —
they are about what cannot happen:

* **Nothing outside the allow-list can ever be applied.** Not by a request
  file, not by a filename with a slash in it, not by one with a newline, not by
  an empty one. The whole of the operator's input is which of a fixed set of
  names exists, and these tests enumerate the ways someone might try to make it
  more than that.
* **The request file's contents are never read.** A test parses the source to
  assert there is no code path that opens one, because a rule that lives only
  in a docstring is a rule until somebody is in a hurry.
* **The reconciler is idempotent**, so it is safe on a five-minute timer
  forever, and it reverts cleanly when the request is withdrawn.
* **The repository default and the live timer are compared**, so a silent
  divergence is visible rather than inferred.
"""

from __future__ import annotations

import json
import re
import tempfile
import unittest
from pathlib import Path

from ops import cadence as cad

NOW = 1786209000.0


def request_dir(room: str, *names: str, times: dict | None = None) -> Path:
    """A request directory holding exactly ``names`` and nothing else.

    Cleared each time, because the VPS-side directory is rsynced with
    ``--delete``: what arrives on bigmem is the whole request set, not an
    addition to it, and a helper that accumulated would test a state the real
    system cannot be in.
    """
    directory = Path(room) / "requests"
    directory.mkdir(parents=True, exist_ok=True)
    for stale in directory.iterdir():
        stale.unlink()
    for index, name in enumerate(names):
        path = directory / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("ignored entirely\n")
        stamp = (times or {}).get(name, NOW + index)
        import os  # noqa: PLC0415
        os.utime(path, (stamp, stamp))
    return directory


class TheAllowList(unittest.TestCase):
    """Everything outside the fixed set is refused. No exceptions, no coercion."""

    def test_every_shipped_option_is_allowed(self):
        for key in cad.CADENCES:
            self.assertTrue(cad.allowed(key))

    def test_the_repository_default_is_one_of_the_options(self):
        self.assertIn(cad.DEFAULT_KEY, cad.CADENCES)

    def test_hourly_is_offered_because_the_home_cap_is_going_away(self):
        self.assertIn("hourly", cad.CADENCES)

    def test_nothing_else_is_allowed(self):
        for value in ("", " ", "HOURLY", "hourly ", "daily\n", "every-3h", "every-2h ", "off",
                      "*-*-* *:00:00", "../../etc/systemd/system/x.timer",
                      "daily; rm -rf /", "daily && reboot", "$(whoami)", "`id`",
                      "hourly/../weekly", "%s", "{}", "0", "-1", "None"):
            self.assertFalse(cad.allowed(value), f"{value!r} passed the allow-list")

    def test_non_strings_are_not_allowed(self):
        for value in (None, 1, 1.0, True, ["hourly"], {"hourly": 1}, object()):
            self.assertFalse(cad.allowed(value))

    def test_a_request_naming_something_outside_the_list_is_skipped_and_counted(self):
        with tempfile.TemporaryDirectory() as room:
            directory = request_dir(room, "daily", "every-3h", "rm-rf-slash")
            request = cad.read_request(directory)
        self.assertEqual(request.key, "daily")
        self.assertEqual(sorted(request.rejected), ["every-3h", "rm-rf-slash"])

    def test_a_directory_of_only_bad_names_yields_no_request(self):
        with tempfile.TemporaryDirectory() as room:
            request = cad.read_request(request_dir(room, "hourly-ish", "please"))
        self.assertIsNone(request.key)
        self.assertFalse(request.present)

    def test_a_missing_directory_yields_no_request_rather_than_an_error(self):
        with tempfile.TemporaryDirectory() as room:
            self.assertIsNone(cad.read_request(Path(room) / "nope").key)

    def test_the_newest_valid_request_wins(self):
        with tempfile.TemporaryDirectory() as room:
            directory = request_dir(room, "weekly", "hourly", "daily",
                                    times={"weekly": NOW + 100, "hourly": NOW + 300,
                                           "daily": NOW + 200})
            self.assertEqual(cad.read_request(directory).key, "hourly")


class TheRequestBodyIsNeverRead(unittest.TestCase):
    """The operator's whole input is a filename, and this proves it stays that way."""

    def test_the_contents_of_a_request_file_do_not_reach_anything(self):
        with tempfile.TemporaryDirectory() as room:
            directory = Path(room) / "requests"
            directory.mkdir()
            (directory / "hourly").write_text(
                "[Timer]\nOnCalendar=*-*-* *:*:00\nExecStart=/bin/sh -c 'curl evil'\n")
            request = cad.read_request(directory)
            self.assertEqual(request.key, "hourly")
            written = cad.dropin_text(cad.CADENCES[request.key])
        self.assertNotIn("evil", written)
        self.assertNotIn("ExecStart", written)
        self.assertEqual(written, cad.dropin_text(cad.CADENCES["hourly"]))

    def test_no_code_path_opens_a_request_file(self):
        """A rule that lives only in a docstring is a rule until someone hurries."""
        source = Path(cad.__file__).read_text()
        body = source.split('"""', 2)[-1]          # skip the module docstring
        for reader in ("read_text(", "read_bytes(", ".open(", "json.load("):
            for line in body.splitlines():
                stripped = line.strip()
                if stripped.startswith("#") or reader not in stripped:
                    continue
                # The only readers allowed are of the repository unit file, the
                # drop-in this module itself wrote, and its own applied log.
                self.assertTrue(
                    any(marker in stripped for marker in
                        ("REPO_TIMER", "dropin", "log_path", "handle.write")),
                    f"a reader that is not one of the three permitted ones: {stripped}")


class TheDropInIsBuiltFromConstantsOnly(unittest.TestCase):

    def test_the_drop_in_contains_only_what_this_module_wrote(self):
        for key, option in cad.CADENCES.items():
            text = cad.dropin_text(option)
            self.assertIn(f"OnCalendar={option.on_calendar}", text)
            self.assertIn(f"RandomizedDelaySec={option.randomized_delay_sec}", text)
            self.assertIn(f"# cadence: {key}", text)

    def test_it_resets_the_inherited_schedule_before_setting_one(self):
        """Without the empty OnCalendar=, systemd ADDS to the unit's schedule."""
        text = cad.dropin_text(cad.CADENCES["hourly"])
        self.assertIn("OnCalendar=\n", text)
        self.assertLess(text.index("OnCalendar=\n"),
                        text.index(f"OnCalendar={cad.CADENCES['hourly'].on_calendar}"))

    def test_the_result_parses_back_to_exactly_one_schedule(self):
        for option in cad.CADENCES.values():
            self.assertEqual(cad.calendars_in(cad.dropin_text(option)),
                             [option.on_calendar])

    def test_no_option_carries_a_shell_metacharacter(self):
        for option in cad.CADENCES.values():
            self.assertIsNone(re.search(r"[;&|`$\n\\]", option.on_calendar),
                              f"{option.key} has a shell metacharacter in its schedule")


class ParsingUnitFiles(unittest.TestCase):

    def test_an_empty_on_calendar_clears_what_came_before_it(self):
        self.assertEqual(
            cad.calendars_in("[Timer]\nOnCalendar=*-*-* *:42:00\nOnCalendar=\n"
                             "OnCalendar=*-*-* 07:25:00 UTC\n"),
            ["*-*-* 07:25:00 UTC"])

    def test_two_schedules_without_a_reset_are_both_reported(self):
        self.assertEqual(
            cad.calendars_in("[Timer]\nOnCalendar=a\nOnCalendar=b\n"), ["a", "b"])

    def test_the_repository_file_is_one_of_the_options(self):
        key, lines = cad.repo_default()
        self.assertEqual(len(lines), 1)
        self.assertIsNotNone(key, f"deploy/systemd/orbit-release.timer says {lines}, "
                                  "which is not an option on the operations page")

    def test_the_repository_file_is_the_default_it_claims_to_be(self):
        # "daily" until 2026-08-18. The pass no longer completes in one firing:
        # a full sweep of the 181.3 M-row archive is about 6 h 40 m, so it works
        # to a budget, checkpoints and continues, and needs roughly eleven runs.
        # A daily timer would leave the artifacts permanently a sweep behind.
        self.assertEqual(cad.repo_default()[0], cad.DEFAULT_KEY)
        self.assertEqual(cad.DEFAULT_KEY, "every-2h")

    def test_systemd_timers_calendar_output_is_understood(self):
        facts = {"TimersCalendar":
                 "{ OnCalendar=*-*-* 07:25:00 ; next_elapse=Sun 2026-08-09 07:25:00 UTC }"}
        self.assertEqual(cad.live_calendars(facts), ["*-*-* 07:25:00"])

    def test_no_facts_means_no_live_schedule_rather_than_a_guess(self):
        self.assertEqual(cad.live_calendars(None), [])


class Reconciliation(unittest.TestCase):

    def apply(self, room, *names, **kwargs):
        return cad.reconcile(request_dir=request_dir(room, *names),
                             systemd_dir=Path(room) / "systemd",
                             log_path=Path(room) / "applied.jsonl",
                             now=NOW, reload=False, **kwargs)

    def dropin(self, room):
        return Path(room) / "systemd" / f"{cad.UNIT}.d" / cad.DROPIN_NAME

    def test_a_valid_request_writes_the_drop_in(self):
        with tempfile.TemporaryDirectory() as room:
            result = self.apply(room, "hourly")
            self.assertEqual(result["action"], "applied")
            self.assertEqual(cad.calendars_in(self.dropin(room).read_text()),
                             [cad.CADENCES["hourly"].on_calendar])

    def test_running_it_again_changes_nothing(self):
        """It is on a five-minute timer forever; it must be safe to repeat."""
        with tempfile.TemporaryDirectory() as room:
            self.apply(room, "hourly")
            before = self.dropin(room).read_text()
            second = self.apply(room, "hourly")
            self.assertEqual(second["action"], "none")
            self.assertEqual(self.dropin(room).read_text(), before)

    def test_withdrawing_the_request_restores_the_repository_default(self):
        with tempfile.TemporaryDirectory() as room:
            self.apply(room, "hourly")
            self.assertTrue(self.dropin(room).exists())
            result = self.apply(room)          # an empty request directory
            self.assertEqual(result["action"], "removed")
            self.assertFalse(self.dropin(room).exists())

    def test_removing_a_drop_in_that_is_not_there_is_a_no_op(self):
        with tempfile.TemporaryDirectory() as room:
            self.assertEqual(self.apply(room)["action"], "none")

    def test_a_request_outside_the_allow_list_changes_nothing(self):
        with tempfile.TemporaryDirectory() as room:
            result = self.apply(room, "every-3h", "daily; reboot")
            self.assertEqual(result["action"], "none")
            self.assertFalse(self.dropin(room).exists())
            self.assertEqual(sorted(result["rejected"]), ["daily; reboot", "every-3h"])

    def test_dry_run_writes_nothing(self):
        with tempfile.TemporaryDirectory() as room:
            result = self.apply(room, "weekly", dry_run=True)
            self.assertEqual(result["action"], "would-apply")
            self.assertFalse(self.dropin(room).exists())

    def test_switching_cadences_replaces_rather_than_appends(self):
        with tempfile.TemporaryDirectory() as room:
            self.apply(room, "hourly")
            directory = request_dir(room, "weekly", times={"weekly": NOW + 900})
            cad.reconcile(request_dir=directory, systemd_dir=Path(room) / "systemd",
                          log_path=Path(room) / "applied.jsonl", now=NOW, reload=False)
            self.assertEqual(cad.calendars_in(self.dropin(room).read_text()),
                             [cad.CADENCES["weekly"].on_calendar])

    def test_every_change_is_logged_with_what_and_when(self):
        with tempfile.TemporaryDirectory() as room:
            self.apply(room, "hourly")
            entries = cad.read_applied(Path(room) / "applied.jsonl")
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["cadence"], "hourly")
        self.assertEqual(entries[0]["at"], NOW)
        self.assertEqual(entries[0]["onCalendar"], cad.CADENCES["hourly"].on_calendar)

    def test_an_unchanged_run_is_not_logged(self):
        """A ledger that records non-events is a ledger nobody reads."""
        with tempfile.TemporaryDirectory() as room:
            self.apply(room, "hourly")
            self.apply(room, "hourly")
            self.assertEqual(len(cad.read_applied(Path(room) / "applied.jsonl")), 1)

    def test_it_only_ever_touches_the_one_unit(self):
        with tempfile.TemporaryDirectory() as room:
            self.apply(room, "hourly")
            written = [p for p in (Path(room) / "systemd").rglob("*") if p.is_file()]
        self.assertEqual([str(p.relative_to(Path(room) / "systemd")) for p in written],
                         [f"{cad.UNIT}.d/{cad.DROPIN_NAME}"])


class DivergenceIsVisible(unittest.TestCase):
    """The repository file is the default; the page must show when it is not live."""

    def facts(self, expression):
        return {"TimersCalendar": f"{{ OnCalendar={expression} ; next_elapse=x }}"}

    def test_live_matching_the_repository_default_is_not_divergence(self):
        with tempfile.TemporaryDirectory() as room:
            state = cad.status(request_dir=Path(room) / "none",
                               facts=self.facts(cad.CADENCES[cad.DEFAULT_KEY].on_calendar),
                               log_path=Path(room) / "applied.jsonl")
        # Follows the default rather than naming it. This test is about "live
        # agrees with the repository" being reported as agreement; hard-coding
        # the key made it fail the moment the default moved off daily, which is
        # a fact about this test and not about divergence.
        self.assertFalse(state["diverged"])
        self.assertEqual(state["liveKey"], cad.DEFAULT_KEY)

    def test_live_differing_from_the_repository_with_no_request_is_divergence(self):
        with tempfile.TemporaryDirectory() as room:
            state = cad.status(request_dir=Path(room) / "none",
                               facts=self.facts(cad.CADENCES["hourly"].on_calendar),
                               log_path=Path(room) / "applied.jsonl")
        self.assertTrue(state["diverged"])

    def test_a_request_explains_the_difference_and_it_is_not_divergence(self):
        with tempfile.TemporaryDirectory() as room:
            state = cad.status(request_dir=request_dir(room, "hourly"),
                               facts=self.facts(cad.CADENCES["hourly"].on_calendar),
                               log_path=Path(room) / "applied.jsonl")
        self.assertFalse(state["diverged"])
        self.assertEqual(state["requested"], "hourly")

    def test_a_hand_edited_timer_is_divergence_and_matches_no_option(self):
        with tempfile.TemporaryDirectory() as room:
            state = cad.status(request_dir=Path(room) / "none",
                               facts=self.facts("*-*-* *:07:00"),
                               log_path=Path(room) / "applied.jsonl")
        self.assertTrue(state["diverged"])
        self.assertIsNone(state["liveKey"])

    def test_systemd_not_answering_is_unmeasurable_not_divergence(self):
        """A check that could not run has not failed, and has not passed either."""
        with tempfile.TemporaryDirectory() as room:
            state = cad.status(request_dir=Path(room) / "none", facts=None,
                               log_path=Path(room) / "applied.jsonl")
        self.assertFalse(state["measurable"])
        self.assertFalse(state["diverged"])


class TheIngestCollisionIsStatedNotEnforced(unittest.TestCase):
    """Hourly is offered, and the page says what it costs in contention."""

    def test_hourly_is_marked_as_overlapping_the_ingest(self):
        self.assertFalse(cad.CADENCES["hourly"].clears_ingest)

    def test_every_option_that_starts_at_twenty_five_past_clears_it(self):
        for key, option in cad.CADENCES.items():
            if ":25:00" in option.on_calendar:
                self.assertTrue(option.clears_ingest, key)

    def test_every_option_explains_itself(self):
        for key, option in cad.CADENCES.items():
            self.assertTrue(option.note.strip(), f"{key} offers no reasoning")

    def test_runs_per_month_is_runs_per_day_over_thirty_days(self):
        for option in cad.CADENCES.values():
            self.assertAlmostEqual(option.runs_per_month, option.runs_per_day * 30)

    def test_the_options_are_ordered_from_most_frequent_to_least(self):
        rates = [option.runs_per_day for option in cad.CADENCES.values()]
        self.assertEqual(rates, sorted(rates, reverse=True))


class TheEndpointMatchesTheAllowList(unittest.TestCase):
    """The nginx config and ops/cadence.py must not drift apart.

    Two allow-lists that are supposed to be the same list are two allow-lists
    that will eventually disagree, and the way they disagree is that the
    endpoint accepts something bigmem refuses -- a click that reports success
    and changes nothing.
    """

    CONF = Path(cad.__file__).resolve().parents[1] / "deploy" / "nginx.conf"
    ENDPOINT = re.compile(r"^\s*location = /ops/cadence/([^\s{]+)", re.M)

    def endpoints(self) -> set[str]:
        return set(self.ENDPOINT.findall(self.CONF.read_text()))

    def block(self, key: str) -> str:
        """One location block's body.

        Split on the closing brace at the block's own indentation, not on the
        first ``}`` in the text -- ``limit_except PUT { deny all; }`` closes an
        inner brace on the very first line and would truncate every block to
        nothing, which reads on a green test run as "the assertion held".
        """
        text = self.CONF.read_text()
        opened = text.split(f"location = /ops/cadence/{key} {{", 1)[1]
        return opened.split("\n    }", 1)[0]

    def test_there_is_one_endpoint_per_cadence_and_no_others(self):
        self.assertEqual(self.endpoints(), set(cad.CADENCES))

    def test_each_endpoint_writes_to_a_file_named_after_its_cadence(self):
        for key in cad.CADENCES:
            self.assertIn(f"alias /var/lib/space-ops/{key};", self.block(key))

    def test_no_endpoint_maps_a_variable_or_a_capture_into_a_path(self):
        """A path built from the request is a path the caller controls."""
        for key in cad.CADENCES:
            self.assertNotIn("$", self.block(key), "the mapped path must be a literal")

    def test_every_endpoint_refuses_every_method_but_put(self):
        for key in cad.CADENCES:
            self.assertIn("limit_except PUT", self.block(key))

    def test_every_endpoint_caps_the_body(self):
        for key in cad.CADENCES:
            self.assertIn("client_max_body_size", self.block(key))

    def test_unknown_cadence_paths_have_a_catch_all_that_returns_not_found(self):
        self.assertIn("location /ops/cadence/", self.CONF.read_text())

    def test_the_compose_file_mounts_the_request_directory_the_pull_reads(self):
        compose = (self.CONF.parent / "compose.yaml").read_text()
        self.assertIn("./runtime/cadence-requests:/var/lib/space-ops:rw", compose)
        publish = (self.CONF.parent.parent / "pipeline" / "publish_vps.sh").read_text()
        self.assertIn("runtime/cadence-requests/", publish)


class AmbiguousRequests(unittest.TestCase):
    """WebDAV stamps to whole seconds, so two clicks can be genuinely tied."""

    def tie(self, room, *names):
        return request_dir(room, *names, times={name: NOW for name in names})

    def test_two_requests_in_the_same_second_are_ambiguous(self):
        with tempfile.TemporaryDirectory() as room:
            request = cad.read_request(self.tie(room, "hourly", "weekly"))
        self.assertIsNone(request.key)
        self.assertEqual(request.ambiguous, ("hourly", "weekly"))

    def test_an_ambiguous_request_changes_nothing_and_does_not_revert(self):
        """Absent means 'go back to the default'. Ambiguous must not mean that."""
        with tempfile.TemporaryDirectory() as room:
            systemd = Path(room) / "systemd"
            log = Path(room) / "applied.jsonl"
            cad.reconcile(request_dir=request_dir(room, "hourly"), systemd_dir=systemd,
                          log_path=log, now=NOW, reload=False)
            dropin = systemd / f"{cad.UNIT}.d" / cad.DROPIN_NAME
            before = dropin.read_text()
            result = cad.reconcile(request_dir=self.tie(room, "daily", "weekly"),
                                   systemd_dir=systemd, log_path=log, now=NOW,
                                   reload=False)
            self.assertEqual(result["action"], "refused")
            self.assertTrue(dropin.exists(), "an ambiguous request removed the drop-in")
            self.assertEqual(before, dropin.read_text())

    def test_a_single_request_at_the_newest_time_is_not_ambiguous(self):
        with tempfile.TemporaryDirectory() as room:
            directory = request_dir(room, "hourly", "weekly", "daily",
                                    times={"hourly": NOW, "weekly": NOW,
                                           "daily": NOW + 5})
            self.assertEqual(cad.read_request(directory).key, "daily")


class TheAppliedLog(unittest.TestCase):

    def test_a_corrupt_line_does_not_hide_the_rest(self):
        with tempfile.TemporaryDirectory() as room:
            path = Path(room) / "applied.jsonl"
            path.write_text(json.dumps({"at": NOW, "cadence": "daily"}) + "\nnot json\n")
            self.assertEqual(len(cad.read_applied(path)), 1)

    def test_a_missing_log_reads_as_no_history_rather_than_an_error(self):
        with tempfile.TemporaryDirectory() as room:
            self.assertEqual(cad.read_applied(Path(room) / "absent.jsonl"), [])


if __name__ == "__main__":
    unittest.main()
