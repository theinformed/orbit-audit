#!/usr/bin/env python3
"""The regime-matched GEO passive null (amendment 2 A2.1, amendment 3 A3.2).

The registered all-regime passive null of registration 3.4 is 842 of 1,000 LEO,
while the routine-keeper population is 41 of 41 GEO. Regime and routine
operation are confounded in the ratio those two produce, and the floor results
said so and owed a matched control. This selects it: the SAME passive class,
the SAME partition, the SAME admissibility rule, the SAME seeded-hash order and
the SAME 1,000-object cap, restricted to GEO. Nothing else differs, and the
threshold the ratio is read at does not move.

Operationalisation, registered in amendment 3 A3.2 before any number: an object
enters the pool if `t18_data.regime_of` applied to its FIRST element set returns
GEO. Computing the median over every candidate's whole history would be a second
full pass over the archive, and the separation between GEO and LEO is four
thousand kilometres of perigee. The extractor then records its own median-based
regime for every object it takes, and the DISAGREEMENT COUNT is published with
the control rather than filtered away afterwards.

Usage:
  t18_geo_passive.py --out <file>          # comma-separated NORADs
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
TOOLS = Path(__file__).resolve().parent
for extra in (str(REPO), str(TOOLS)):
    if extra not in sys.path:
        sys.path.insert(0, extra)

import t18_data as td                                          # noqa: E402

PASSIVE_TYPES = ("DEBRIS", "ROCKET BODY")
CAP = td.PASSIVE_OBJECT_CAP


def select(split: dict, db, cap: int = CAP, say=print) -> list[int]:
    candidates = td.partition_objects(split, "test", None,
                                      object_types=PASSIVE_TYPES)
    say(f"passive test candidates, admissible, in seeded-hash order: "
        f"{len(candidates)}")
    picked = []
    for norad in candidates:
        got = db.execute(
            "SELECT mean_motion_q, eccentricity_q FROM element_set "
            "WHERE norad=? ORDER BY epoch_ms LIMIT 1", (int(norad),)).fetchone()
        if not got:
            continue
        el = {"n_rev_day": np.asarray([got[0] / td.SCALE_MEAN_MOTION]),
              "ecc": np.asarray([got[1] / td.SCALE_ECCENTRICITY])}
        if td.regime_of(el) == "GEO":
            picked.append(int(norad))
        if len(picked) >= cap:
            break
    say(f"GEO passive pool: {len(picked)}")
    if len(picked) < 20:
        say("BELOW GATE G7's BAR OF 20 SUPPORTING OBJECTS: the matched control "
            "is UNDERPOWERED and lends its name to nothing. It is never "
            "reported as zero.")
    return picked


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--split", type=Path,
                    default=REPO / "docs" / "t18-split-20260922.json")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--cap", type=int, default=CAP)
    args = ap.parse_args(argv)

    split = json.loads(args.split.read_text())
    picked = select(split, td.open_archive(), args.cap)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(",".join(str(n) for n in picked) + "\n")
    print(f"-> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
