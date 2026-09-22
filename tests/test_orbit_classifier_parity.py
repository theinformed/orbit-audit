"""The Python half of the cross-language orbit-classifier parity check.

See tests/orbit-classifier-parity.test.ts for why this exists. In short: the
class a visitor reads on a card is stamped by `build_release.derive_orbit` at
build time, recomputed by `catalog_audit.regime_from_elements` during the audit,
and recomputed again by `classifyOrbit` in the browser. Three copies of one rule
drift silently -- nothing on the page shows a disagreement -- so all three read
the SAME case table and go red together.

The audit copy is not folded into the build copy on purpose. Its own docstring
says why: it mirrors the rule so that a disagreement means the *inputs* disagree,
not the definitions. An audit that imports what it audits audits nothing.
"""
import json
import math
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from pipeline import build_release, catalog_audit  # noqa: E402

CASES = json.loads(
    (pathlib.Path(__file__).parent / "fixtures" / "orbit-classifier-cases.json").read_text()
)["cases"]


class OrbitClassifierParity(unittest.TestCase):
    def test_build_release_matches_the_shared_case_table(self):
        for row in CASES:
            with self.subTest(row["why"]):
                got = build_release.derive_orbit(
                    row["meanMotion"], row["eccentricity"], row["inclinationDeg"]
                )["orbit"]
                self.assertEqual(got, row["expect"])

    def test_the_audit_copy_matches_the_same_table(self):
        """The audit is fed the build's own derived values, which is exactly how
        it runs in production -- it reads perigee, apogee and period off the
        registry rather than off a mean motion."""
        for row in CASES:
            with self.subTest(row["why"]):
                derived = build_release.derive_orbit(
                    row["meanMotion"], row["eccentricity"], row["inclinationDeg"]
                )
                got = catalog_audit.regime_from_elements(
                    derived["periodMinutes"], derived["apogeeKm"], derived["perigeeKm"],
                    row["inclinationDeg"], row["eccentricity"],
                )
                self.assertEqual(got, row["expect"])

    def test_the_table_covers_every_class_the_site_can_publish(self):
        covered = {row["expect"] for row in CASES}
        for regime in ("LEO", "MEO", "GEO", "IGSO", "HEO", "OTHER"):
            self.assertIn(regime, covered, f"no case expects {regime}")

    def test_every_published_class_has_a_plain_english_sentence(self):
        """`template_purpose` falls back to ORBIT_EVIDENCE["OTHER"] for any class
        it does not know, which would silently describe an IGSO as an orbit that
        is not one of the standard bands -- the exact sentence that was reported.
        """
        for regime in ("LEO", "MEO", "GEO", "IGSO", "HEO", "OTHER"):
            self.assertIn(regime, build_release.ORBIT_EVIDENCE)


if __name__ == "__main__":
    unittest.main()
