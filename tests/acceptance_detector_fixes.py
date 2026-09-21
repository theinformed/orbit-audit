"""Intentionally RED until separate full-sweep bundles supply passive evidence.

Run: python3 -m unittest discover -s tests -p 'acceptance_detector_fixes.py' -v
Set DETECTOR_ACCEPTANCE_DIR to a directory containing f3.json, f4.json and
f1.json (complete orbit-events bundles, not headline samples or checkpoints).
These tests only read those JSON files. They never start a sweep or open the DB.
F3 is compared to the authoritative design baseline. F4 and F1 each differ
from F3 by exactly their own flag; a two-flag experiment is not evidence.
"""
import json
import os
from pathlib import Path
import unittest


# Predeclared table from DETECTOR-DESIGN.md (all fifteen, including failures):
#             < 500 | 500–800 | 800–1,500 | 1,500–30,000 | GEO+
# pre-2013      *       *          *            *           *
# 2013–2020     *       *          *            *           *
# 2021+         *       *          *            *           *
# Minimum passive intervals per stratum: 200,000.
ERAS = ("pre-2013", "2013-2020", "2021+")
BANDS = ("<500", "500-800", "800-1500", "1500-30000", "GEO+")
FLAGS_F3 = {"INCLINATION_FLOOR_TAIL_AWARE": True,
            "MATCHED_CONTROL_STRATA_ENABLED": False,
            "DECLINE_AFTER_TRACKING_GAP": False}


class DetectorAcceptance(unittest.TestCase):
    def measurement(self, name, flags):
        root = os.environ.get("DETECTOR_ACCEPTANCE_DIR")
        self.assertIsNotNone(root, f"not measured: {name} requires a separate full-archive "
                             "passive-control bundle; flags ship disabled; set DETECTOR_ACCEPTANCE_DIR")
        path = Path(root) / f"{name}.json"
        self.assertTrue(path.is_file(), f"not measured: missing full-sweep evidence {path}")
        bundle = json.loads(path.read_text())
        control = bundle["controls"]["selfHistory"]
        self.assertEqual(control["detectorFlags"], flags, "wrong detector or more than one flag changed")
        self.assertEqual(control["kappa"], 32, "acceptance must not tune kappa")
        self.assertGreaterEqual(control["passive"]["intervals"], 89_179_650,
                                "the design requires whole-archive evidence, not its sample")
        return bundle, control

    def test_f3_tail_floor_whole_archive_acceptance(self):
        bundle, control = self.measurement("f3", FLAGS_F3)
        self.assertLess(control["passive"]["jeffreys95"][1], 0.00025)
        # The design's printed 175,600 rounds down its own 92% rule.
        # Enforce the stricter inequality (integer minimum 175,607).
        self.assertGreaterEqual(control["payload"]["flags"], 0.92 * 190_877)
        self.assertGreaterEqual(control["rateSeparation"]["boundRatio"], 12)
        self.assertLessEqual(abs(control["catalogueGeoNorthSouthKeepingEvents"] - 2826), 0.02 * 2826)
        self.assertEqual(bundle["groundTruth"]["scorable"], 27)
        self.assertGreaterEqual(bundle["groundTruth"]["detected"], 18)

    def test_f4_gap_declines_are_published_and_payload_cost_is_bounded(self):
        _, control = self.measurement("f4", {**FLAGS_F3, "DECLINE_AFTER_TRACKING_GAP": True})
        _, baseline = self.measurement("f3", FLAGS_F3)
        drops = control["trackingGapDroppedIntervals"]
        self.assertIs(type(drops), int, "a disabled/unmeasured gate must publish a gap string")
        self.assertGreater(drops, 0, "the gate must actually decline measured intervals")
        self.assertGreaterEqual(control["payload"]["flags"], .985 * baseline["payload"]["flags"])

    def test_f1_all_predeclared_strata_and_each_permitted_margin(self):
        bundle, control = self.measurement("f1", {**FLAGS_F3, "MATCHED_CONTROL_STRATA_ENABLED": True})
        self.measurement("f3", FLAGS_F3)
        self.assertEqual(set(control["strata"]), set(ERAS))
        policies = bundle["labelPolicy"]["byBasis"]["byStratum"]
        permissions = []
        for era in ERAS:
            self.assertEqual(set(control["strata"][era]), set(BANDS))
            for band in BANDS:
                block = control["strata"][era][band]
                self.assertIs(type(block["passive"]["intervals"]), int)
                self.assertIs(type(block["payload"]["intervals"]), int)
                self.assertIs(type(block["passive"]["flags"]), int)
                self.assertIs(type(block["payload"]["flags"]), int)
                permitted = policies[era][band]["manoeuvreLabelPermitted"]
                self.assertEqual(permitted, block["sufficientToLabel"])
                permissions.append(permitted)
                if permitted:
                    self.assertGreaterEqual(block["passive"]["intervals"], 200_000)
                    self.assertLess(block["passive"]["jeffreys95"][1], 0.001)
                    self.assertGreaterEqual(block["rateSeparation"]["boundRatio"], 12)
                else:
                    self.assertIsInstance(block["blockingReason"], str)
        self.assertTrue(any(permissions), "detecting nothing cannot earn acceptance")
        self.assertEqual(bundle["labelPolicy"]["manoeuvreLabelPermitted"],
                         all(permissions) and bundle["labelPolicy"]["byBasis"]["cohort"])
        for event in bundle["events"]:
            if event["controlBasis"] == "self-history":
                key = event["controlStratum"]
                if not policies[key["era"]][key["band"]]["manoeuvreLabelPermitted"]:
                    self.assertFalse(event["manoeuvreLabelPermitted"])


if __name__ == "__main__":
    unittest.main()
