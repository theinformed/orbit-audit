#!/usr/bin/env python3
"""Regenerate DENSITY_TABLE in pipeline/orbital_lifetime.py. Run by hand, rarely.

The table is a CLIMATOLOGY, not a forecast, and that is deliberate. The site's
published thermosphere covers a 120-hour slider; an orbital lifetime integrates
over years to centuries, so what it needs is the average shape of the
atmosphere at a named level of solar activity, which is exactly what NRLMSIS
evaluated at a fixed F10.7 gives.

Everything goes through pipeline.thermosphere.msis_profile, which passes f107,
f107a and ap EXPLICITLY. That is not a style preference: pymsis silently
downloads and caches historical indices when they are omitted, which would make
this script's output depend on the day it was run and on a network fetch nobody
asked for.

    python3 tools/regenerate-lifetime-density-table.py > /tmp/rows.txt

then paste the rows between the DENSITY_TABLE parentheses. Verify with
tests/test_orbital_lifetime.py, which pins several rows against published
NRLMSIS values.
"""

from __future__ import annotations

import datetime as dt
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.thermosphere import msis_profile  # noqa: E402

ALTITUDES_KM = list(range(110, 1301, 10))
LATITUDES_DEG = [-87.5 + 15.0 * index for index in range(12)]
LONGITUDES_DEG = [15.0 * index for index in range(24)]
# One equinox pair and one solstice pair, so the annual cycle averages out.
DATES = [dt.datetime(2018, month, 21) for month in (3, 6, 9, 12)]
LEVELS = {"low": 70.0, "mean": 140.0, "high": 200.0}
AP = 4.0


def main() -> int:
    weights = [math.cos(math.radians(value)) for value in LATITUDES_DEG]
    total_weight = sum(weights)
    columns: dict[str, list[float]] = {}
    for label, f107 in LEVELS.items():
        accumulated = [0.0] * len(ALTITUDES_KM)
        samples = 0
        for when in DATES:
            for longitude in LONGITUDES_DEG:
                for latitude, weight in zip(LATITUDES_DEG, weights):
                    rows = msis_profile(
                        when, longitude, latitude, ALTITUDES_KM, f107, f107, AP
                    )
                    for index, row in enumerate(rows):
                        accumulated[index] += row["massDensityKgM3"] * weight / total_weight
                samples += 1
        columns[label] = [value / samples for value in accumulated]
    for index, altitude in enumerate(ALTITUDES_KM):
        print(
            "    (%4d, %.4e, %.4e, %.4e),"
            % (altitude, columns["low"][index], columns["mean"][index], columns["high"][index])
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
