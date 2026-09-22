#!/usr/bin/env python3
"""The GROUP=active GP bulk file must be UNREQUESTABLE, not merely unrequested.

Offline. Nothing here opens a socket; every "request" is a mock, and a test that
lets a real one through is itself the failure.

WHY THIS FILE EXISTS
--------------------
On 2026-08-26 ``ingest/celestrak_mirror.py`` carried a docstring saying
CelesTrak's ``GROUP=active`` GP file "is never requested" while the code beneath
it downloaded that same 6.9 MB file every two hours. CelesTrak answered the
fifth identical download of the day with HTTP 403.

The test that existed then, ``test_active_gp_bulk_url_is_absent``, grepped the
module source for the literal ``gp.php?GROUP=active``. That check passes for the
most likely way the mistake comes back -- putting ``"active"`` into ``GROUPS``,
which the surviving f-string then expands -- so it proved absence, not
impossibility.

Every test below is NEGATIVE-CONTROLLED: it also runs the same scenario with the
guard disabled and asserts the forbidden request WOULD have gone out. Without
that control a guard test can pass because the code path was never reached, and
this project has been bitten by exactly that shape before.
"""

from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

if str(Path(__file__).resolve().parents[1]) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ingest import celestrak_groups as guard  # noqa: E402
from ingest import celestrak_mirror as mirror  # noqa: E402

FORBIDDEN_GP_URL = "https://celestrak.org/NORAD/elements/gp.php?GROUP=active&FORMAT=json"
ALLOWED_SATCAT_URL = "https://celestrak.org/satcat/records.php?GROUP=active&FORMAT=json"


class Response:
    def __init__(self, body: bytes, status: int = 200) -> None:
        self.body = io.BytesIO(body)
        self.status = status

    def read(self, size: int = -1) -> bytes:
        return self.body.read(size)

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class ConstructionTests(unittest.TestCase):
    """gp_url() is the only supported builder, and it says no."""

    def test_active_cannot_be_built(self):
        with self.assertRaises(guard.ForbiddenCelestrakGroup) as raised:
            guard.gp_url("active", where="test")
        self.assertIn("403", str(raised.exception))

    def test_negative_control_the_same_call_succeeds_without_the_guard(self):
        # If this control ever fails, the test above has stopped measuring the
        # guard and started measuring something else.
        with mock.patch.object(guard, "FORBIDDEN_GP_GROUPS", {}):
            self.assertEqual(guard.gp_url("active", where="test"), FORBIDDEN_GP_URL)

    def test_case_and_whitespace_do_not_smuggle_a_name_through(self):
        for name in ("Active", "ACTIVE", "  active  ", "iridium-NEXT", "Starlink"):
            with self.subTest(group=name):
                with self.assertRaises(guard.ForbiddenCelestrakGroup):
                    guard.gp_url(name, where="test")

    def test_every_forbidden_name_is_refused(self):
        for name in guard.FORBIDDEN_GP_GROUPS:
            with self.subTest(group=name):
                with self.assertRaises(guard.ForbiddenCelestrakGroup):
                    guard.gp_url(name, where="test")

    def test_a_real_mission_category_is_still_built(self):
        self.assertEqual(
            guard.gp_url("science", where="test"),
            "https://celestrak.org/NORAD/elements/gp.php?GROUP=science&FORMAT=json",
        )

    def test_the_shipped_group_list_carries_no_forbidden_name(self):
        self.assertEqual(guard.forbidden_gp_groups(mirror.GROUPS), [])
        self.assertEqual(mirror.GROUP_LIST_PROBLEMS, [])

    def test_the_mirror_no_longer_hand_builds_a_gp_url(self):
        # The construction site is gone, so nothing can expand a group name into
        # a URL behind gp_url()'s back. Matched on "gp.php?" -- the start of a
        # URL query -- rather than "gp.php", because the module deliberately
        # NAMES the endpoint in prose to say it is forbidden, and a test that
        # banned the prose would push the explanation out of the file.
        source = Path(mirror.__file__).read_text()
        self.assertNotIn("gp.php?", source)
        self.assertNotIn("elements/gp.php\"", source)
        self.assertNotIn("elements/gp.php'", source)


class SocketGateTests(unittest.TestCase):
    """The backstop: no forbidden GP request reaches a socket, however built."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        for name, value in (
            ("CACHE", root / "cache"),
            ("STATE", root / "state"),
            ("HALT_MARKER", root / "state" / "HALTED.json"),
            ("SATCAT_APPLIED", root / "state" / "satcat-applied-signature.json"),
            ("LAST_ATTEMPT", root / "state" / "last-request-at.json"),
            # Required by the conditional-request path. Without it this
            # offline test wrote the REAL ingest/state/http-validators.json --
            # caught on the first run, by a 36-byte file appearing in live state
            # while the mirror was supposed to be halted. A sandbox that misses
            # one path is not a sandbox.
            ("VALIDATORS", root / "state" / "http-validators.json"),
            ("LOG", root / "mirror.log"),
            ("POLITE_GAP", 0),
        ):
            patch = mock.patch.object(mirror, name, value)
            patch.start()
            self.addCleanup(patch.stop)
        alert = mock.patch.object(mirror, "alert_human")
        alert.start()
        self.addCleanup(alert.stop)
        mirror.CACHE.mkdir(parents=True, exist_ok=True)
        mirror.STATE.mkdir(parents=True, exist_ok=True)

    def _fresh_satcat(self):
        """Make the SATCAT branch not due, so a run reaches the group branch."""
        directory = json.dumps([{
            "FILE_NAME": "satcat.csv", "FILE_SIZE": "1200000", "FILE_MTIME": "2026-08-26 00:00:00",
        }]).encode()
        (mirror.CACHE / "satcat-dir.json").write_bytes(directory)
        mirror._mark_satcat_applied(mirror.satcat_signature(directory), reason="test fixture")

    def test_validate_url_refuses_a_hand_rolled_active_gp_url(self):
        with self.assertRaises(guard.ForbiddenCelestrakGroup):
            mirror._validate_url(FORBIDDEN_GP_URL)

    def test_the_refusal_happens_before_a_request_slot_is_spent(self):
        budget = mirror.RequestBudget()
        with mock.patch.object(mirror.DIRECT_OPENER, "open") as opened:
            with self.assertRaises(guard.ForbiddenCelestrakGroup):
                mirror.fetch(
                    FORBIDDEN_GP_URL,
                    mirror.CACHE / "gp-active.json",
                    budget=budget,
                    dataset="gp-active",
                    group="active",
                )
        opened.assert_not_called()
        self.assertEqual(budget.used, 0)
        self.assertFalse((mirror.CACHE / "gp-active.json").exists())

    def test_active_in_the_group_list_opens_no_socket_at_all(self):
        self._fresh_satcat()
        poisoned = list(mirror.GROUPS) + ["active"]
        problems = guard.malformed_group_names(poisoned) + guard.forbidden_gp_groups(poisoned)
        self.assertTrue(problems, "a poisoned list must be reported as a configuration error")
        with mock.patch.object(mirror, "GROUPS", poisoned), \
             mock.patch.object(mirror, "GROUP_LIST_PROBLEMS", problems), \
             mock.patch.object(mirror.DIRECT_OPENER, "open") as opened:
            self.assertEqual(mirror.run(), 4)
        opened.assert_not_called()

    def test_negative_control_without_the_guard_that_list_does_reach_the_wire(self):
        # The whole point. With FORBIDDEN_GP_GROUPS emptied, the identical
        # configuration sends GROUP=active to gp.php -- which is what happened
        # for real on 2026-08-26. If this control stops reproducing the bad
        # request, the test above is no longer proving anything.
        self._fresh_satcat()
        calls: list[str] = []

        def open_request(request, timeout=0):
            del timeout
            calls.append(request.full_url)
            return Response(b'[{"NORAD_CAT_ID": 25544}]')

        with mock.patch.object(guard, "FORBIDDEN_GP_GROUPS", {}), \
             mock.patch.object(mirror, "GROUPS", ["active"]), \
             mock.patch.object(mirror, "GROUP_LIST_PROBLEMS", []), \
             mock.patch.object(mirror.DIRECT_OPENER, "open", side_effect=open_request):
            self.assertEqual(mirror.run(), 0)
        self.assertEqual(calls, [FORBIDDEN_GP_URL])

    def test_the_satcat_endpoint_with_group_active_is_still_allowed(self):
        # The guard must be about the GP bulk endpoint, not about the word
        # "active". satcat/records.php?GROUP=active is the operational curation
        # that keeps ~2,600 long-dead spacecraft off the site, and banning it
        # would be a different, quieter outage.
        mirror._validate_url(ALLOWED_SATCAT_URL)
        mirror._validate_url(mirror.SATCAT_ACTIVE)
        mirror._validate_url(mirror.SATCAT_DIR)
        self.assertEqual(guard.forbidden_gp_reason(guard.group_from_url(ALLOWED_SATCAT_URL)), guard.FORBIDDEN_GP_GROUPS["active"])


class DeployedHaltPathTests(unittest.TestCase):
    """The live halt marker must keep the DEPLOYED module socket-free.

    The real service has run this path ten times since 2026-08-26T14:36Z and
    written no ``last-request-at.json`` -- the tripwire the code stamps BEFORE a
    socket opens. This test re-proves it in-process against the patched module,
    because a guard added today must not have disturbed the short-circuit that
    is currently holding the line.
    """

    LIVE_HALT = Path("/root/space-teaching-aid/ingest/state/HALTED.json")

    def setUp(self):
        # Gate on the HOST, not on the file. Path.exists() raises PermissionError
        # rather than returning False when the caller cannot traverse /root, so on
        # bigmem this class errored on all three tests instead of skipping -- it
        # had been red there since it shipped on 2026-08-26 and nobody saw it
        # because the file is only ever run on the VPS by hand.
        import socket as _socket  # noqa: PLC0415
        if _socket.gethostname() != mirror.CELESTRAK_HOST:
            self.skipTest(f"the deployed lane lives on {mirror.CELESTRAK_HOST}; this is not it")

    def test_the_real_halt_marker_short_circuits_before_any_socket(self):
        if not self.LIVE_HALT.exists():
            self.skipTest("no live halt marker on this host")
        with mock.patch.object(mirror.DIRECT_OPENER, "open") as opened:
            self.assertEqual(mirror.run(), 0)
        opened.assert_not_called()

    def test_the_live_halt_marker_is_intact_and_records_the_403(self):
        if not self.LIVE_HALT.exists():
            self.skipTest("no live halt marker on this host")
        marker = json.loads(self.LIVE_HALT.read_text())
        self.assertEqual(marker["status"], 403)
        self.assertEqual(marker["url"], FORBIDDEN_GP_URL)

    def test_the_pre_socket_tripwire_was_never_stamped_while_halted(self):
        if not self.LIVE_HALT.exists():
            self.skipTest("no live halt marker on this host")
        self.assertFalse(
            Path("/root/space-teaching-aid/ingest/state/last-request-at.json").exists(),
            "a request attempt was stamped while the mirror was supposed to be halted",
        )


class LedgerCompatibilityTests(unittest.TestCase):
    """A quarantine that reads as empty is a quarantine that is not running."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.state = Path(self.temp.name)

    def test_the_pre_schema_flat_ledger_still_quarantines(self):
        # The shape actually on the VPS at ingest/state/invalid-groups.json,
        # written 2026-08-08, before the {"schema", "groups"} wrapper existed.
        (self.state / "invalid-groups.json").write_text(json.dumps({
            "swarm": {"at": "2026-08-08T06:04:32+00:00", "said": "Invalid query"},
            "gorizont": {"at": "2026-08-08T06:47:27+00:00", "said": "Invalid query"},
        }))
        self.assertEqual(guard.quarantined_groups(self.state), {"swarm", "gorizont"})

    def test_the_current_schema_still_reads(self):
        (self.state / "invalid-groups.json").write_text(json.dumps({
            "schema": 1, "groups": {"swarm": {"group": "swarm"}},
        }))
        self.assertEqual(guard.quarantined_groups(self.state), {"swarm"})

    def test_junk_reads_as_empty_rather_than_fatal(self):
        (self.state / "invalid-groups.json").write_text("not json")
        self.assertEqual(guard.quarantined_groups(self.state), set())


if __name__ == "__main__":
    unittest.main(verbosity=2)
