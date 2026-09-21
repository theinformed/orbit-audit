"""What the Satellite Background section is allowed to contain, pinned.

Two lanes fill this section and they have opposite risks. `narration/shaped-purposes.json`
is a MODEL shortening cited text that already exists, so its risk is containment and it is
gated in two places already. `data/constellation_overrides.json` is HAND-WRITTEN prose
about a fleet, printed on up to 4,648 cards at once, with no source text to check it
against -- so what CAN be checked mechanically is checked here, every build.
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pipeline.build_release as build  # noqa: E402
from pipeline.build_release import (  # noqa: E402
    BACKGROUND_SECTION_MAX_CHARS,
    _purpose_key,
    attach_background_shape,
)

# Loaded by path rather than as a package: `narration/` is a directory of authoring
# scripts, not an importable package, and adding an __init__.py to it to satisfy one
# test would change what that directory is.
_spec = importlib.util.spec_from_file_location(
    "build_shaped_purposes", ROOT / "narration" / "build_shaped_purposes.py")
shaper = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(shaper)

FLEETS = json.loads((ROOT / "data" / "constellation_overrides.json").read_text())


class BackgroundShape(unittest.TestCase):


    def test_the_publish_ceiling_is_the_one_the_shaper_derived(self):
        """Two copies of Sean's format, and a drift between them un-shapes cards silently."""
        assert BACKGROUND_SECTION_MAX_CHARS == shaper.SECTION_MAX


    def test_the_description_key_is_the_same_function_on_both_sides(self):
        """A drift here matches nothing and every card quietly goes back to its full wall."""
        for text in ("", "  a description  ", "unicode — dash", "A" * 3000):
            assert _purpose_key(text) == shaper.text_key(text)


    def test_no_fleet_paragraph_contains_a_digit(self):
        """A member count is the one fact about a fleet that moves, so it is never written.

        build_release.py injects it from the retained catalogue at publish time. This is the
        constellation-of-the-day lane's proven trap, and it is cheap to make impossible.
        """
        for name, entry in FLEETS["constellations"].items():
            assert not re.search(r"\d", entry["fleetNote"]), name


    def test_every_fleet_paragraph_carries_its_own_source_and_the_quotes_behind_it(self):
        for name, entry in FLEETS["constellations"].items():
            assert entry["fleetNoteSource"].startswith("https://"), name
            assert entry.get("sourceTitle"), name
            assert len(entry.get("verifiedQuotes") or []) >= 2, name


    def test_no_fleet_paragraph_runs_past_the_format(self):
        """The paragraph plus its members' own sentence must fit Sean's section ceiling."""
        for name, entry in FLEETS["constellations"].items():
            total = entry["ownSentenceChars"] + len(entry["fleetNote"])
            assert total <= BACKGROUND_SECTION_MAX_CHARS, f"{name}: {total}"
            assert entry["fleetNote"].count(".") <= 5, name


    def test_the_corpus_stays_small_enough_to_read_in_one_sitting(self):
        """Ten paragraphs Sean can read in full is the whole safety argument for this file."""
        assert len(FLEETS["constellations"]) <= 10


    def test_a_card_never_gets_three_paragraphs(self):
        """The shortening lane and the fleet lane must stay disjoint, and it is checked here
        rather than assumed: they are keyed off opposite ends of the same length distribution
        today, and a future researched paragraph could put one object in both."""
        satellites = [
            {"id": 1, "constellation": "Starlink",
             "purpose": "A low-Earth-orbit spacecraft in SpaceX's Starlink constellation."},
            {"id": 2, "constellation": None, "purpose": "x" * 900},
        ]
        with contextlib.redirect_stdout(io.StringIO()):
            attach_background_shape(satellites)
        for record in satellites:
            paragraphs = list(record.get("purposeShaped") or [record["purpose"]])
            if record.get("fleetNote"):
                paragraphs.append(record["fleetNote"])
            assert len(paragraphs) <= 2, record["id"]


    def test_a_fleet_paragraph_with_a_digit_is_refused_at_publish_time(self):
        """The test above pins the file; this pins the PIPELINE, so a paragraph that arrives
        with a digit some other way still never reaches a card."""
        original = build._read_optional_json
        build._read_optional_json = lambda path: (
            {"constellations": {"Starlink": {"fleetNote": "Four thousand and 648 of them.",
                                             "fleetNoteSource": "https://example.org/"}}}
            if path == build.CONSTELLATION_OVERRIDES else {}
        )
        printed = io.StringIO()
        try:
            satellites = [{"id": 1, "constellation": "Starlink", "purpose": "short"}]
            with contextlib.redirect_stdout(printed):
                attach_background_shape(satellites)
        finally:
            build._read_optional_json = original
        self.assertNotIn("fleetNote", satellites[0])
        self.assertIn("contains a digit", printed.getvalue())


    def test_a_missing_shaping_file_leaves_every_card_exactly_as_it_was(self):
        """THE MODEL DECORATES, IT NEVER GATES. bigmem down, the lane never run, the file
        deleted -- the card prints the full researched description, which is what it does
        today."""
        original = build._read_optional_json
        build._read_optional_json = lambda path: {}
        try:
            satellites = [{"id": 1, "constellation": "Starlink", "purpose": "the whole thing"}]
            with contextlib.redirect_stdout(io.StringIO()):
                attach_background_shape(satellites)
        finally:
            build._read_optional_json = original
        assert satellites[0] == {"id": 1, "constellation": "Starlink", "purpose": "the whole thing"}


    def test_the_shaper_refuses_the_failures_it_was_built_to_refuse(self):
        """One case per gate, because a gate that never fires is not evidence of anything.

        Every one of these is a shape the local model actually produced on 2026-08-27.
        """
        row = {
            "key": "k", "example": "ASBM-1", "members": 2, "printedOn": 2,
            "doNotName": ["ASBM-1", "ASBM-2"], "spacecraft": None,
            "text": ("An Arctic Satellite Broadband Mission spacecraft. Space Norway put ASBM-1 "
                     "and ASBM-2 into a highly elliptical orbit, 8,100 km at perigee, so one of "
                     "the pair always dwells over the north. They carry payloads for the "
                     "Norwegian Armed Forces and the U.S. Space Force, and the arrangement is "
                     "what makes broadband above the Arctic Circle possible at all for anyone."),
        }
        fine = {"first": ("An Arctic Satellite Broadband Mission spacecraft on a highly elliptical "
                          "orbit that always keeps one of the pair dwelling over the north."),
                "second": "It carries payloads for the Norwegian Armed Forces and the U.S. Space Force."}
        assert shaper.check(fine, row) is None

        # Every case keeps `fine`'s second paragraph unless it is testing length, so a
        # case aimed at the name gate is not quietly refused by the minimum-length one
        # instead. A test that passes for the wrong reason proves nothing about the gate
        # it names.
        def refused(first, second=fine["second"]):
            return shaper.check({"first": first, "second": second}, row) or ""

        assert "2019" in refused(fine["first"] + " It launched in 2019 from Cape Canaveral there.")
        assert "Eutelsat" in refused(fine["first"].replace("Arctic Satellite", "Eutelsat Arctic"))
        assert "ASBM-1" in refused("ASBM-1 is an Arctic Satellite Broadband Mission spacecraft on "
                                   "an elliptical orbit that dwells over the north for its owners.")
        assert "hedges" in refused("An Arctic Satellite Broadband Mission spacecraft that "
                                  "apparently dwells over the north on a highly elliptical orbit "
                                  "for the Norwegian Armed Forces and their partners.")
        assert "characters" in refused(row["text"][:360], row["text"][:360])
        assert "deletion" in refused("An Arctic spacecraft.", "")


    def test_a_qualifier_in_the_description_must_survive_into_the_short_version(self):
        """The fabrication this lane exists to prevent: "reportedly manoeuvred" -> "manoeuvred".
        Every word shorter, and an attributed report promoted to an established fact."""
        row = {
            "key": "k", "example": "COSMOS 9", "members": 1, "printedOn": 1,
            "doNotName": None, "spacecraft": "COSMOS 9",
            "text": ("A Russian spacecraft that reportedly manoeuvred back towards its own spent "
                     "upper stage, according to analysts watching it from the ground, and whose "
                     "purpose Russia has never stated in public for anybody at all to read."),
        }
        dropped = {"first": ("A Russian spacecraft that manoeuvred back towards its own spent "
                             "upper stage, and whose purpose Russia has never stated in public "
                             "to anyone at all, then or since."),
                   "second": ""}
        assert "attributes or qualifies" in shaper.check(dropped, row)
        kept = {"first": ("A Russian spacecraft that reportedly manoeuvred back towards its own "
                          "spent upper stage, and whose purpose Russia has never stated in "
                          "public to anyone at all, then or since."),
                "second": ""}
        assert shaper.check(kept, row) is None


if __name__ == "__main__":
    unittest.main()
