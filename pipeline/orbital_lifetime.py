#!/usr/bin/env python3
"""How long an object stays up, measured from its own tracked orbit.

WHY THIS EXISTS. The catalogue carries about fifty objects that no published
source describes -- 2025-26 rideshare passengers, almost all of them, whose
operators publish nothing at all. Their cards had to say SOMETHING, and the
first attempt said the registry's own record back to the reader: orbit class,
altitude, period, launch date, launch group, country. Every one of those is
already in the Details grid two centimetres higher up the same card. Sean:
"that sounds absolutely tacky ... just having it lead into orbit is fucking
dumb", and "stop adding filler/fluff text to my site".

So the test for anything published here is whether it tells a reader something
the grid does NOT already show. Orbital lifetime does. It is the answer to the
question a Navy audience actually has about a dead 3U cubesat -- is this thing
going away, or is it traffic for the next thirty years -- and nothing else on
the card implies it.

WHAT IS MEASURED AND WHAT IS ASSUMED. This module does NOT assume a ballistic
coefficient. Area-to-mass is the term that ruins a textbook lifetime estimate
for exactly this population: nobody publishes the mass of BUZZZER-1, and a 1U
and a 12U at the same altitude differ by a factor of several. Instead the
object's OWN decay is measured, from the site's own element-set archive:
orbitHistory publishes a per-object series of fitted semi-major axes, and a
Theil-Sen slope through the last two years of it is a robust measurement of how
fast this specific object is coming down, in kilometres per year. That number
is a measurement. It is also, on its own, not a lifetime -- decay accelerates
as an object descends into thicker air.

So the measured rate fixes the constant of proportionality, and the SHAPE of
the atmosphere below carries it to the ground:

    rate(h) = rate_measured * rho(h)/rho(h0) * (a/a0)^2 * (revs(h)/revs(h0))

which is the standard first-order circular-orbit result -- the same one
pipeline.thermosphere.decay_rate_km_per_day states -- with the ballistic
coefficient divided out. The lifetime is the integral of dh/rate(h) from the
object's altitude down to 120 km. Because the model density appears as a
RATIO, its absolute scale cancels exactly; only how quickly density falls with
height enters, which is the part an empirical model gets right.

WHAT IS STILL UNCERTAIN, AND IT IS NOT SMALL. Solar activity. Neutral density
at 500 km differs by a factor of seventeen between F10.7 = 70 and F10.7 = 200,
and nobody can predict the next cycle. A lifetime quoted as one number would be
a certainty this cannot have, so estimate() returns three: the value on an
average cycle and the two bounding values, and the card names the assumption in
words. Where an object's tracked record is too short, or its orbit is being
maintained, estimate() returns None and the card says the class-level thing
with NO number rather than inventing one.

Two further errors are known and neither is corrected for. NRLMSIS is
documented to UNDER-RESPOND to geomagnetic forcing by 20-30% during storms, so
a decade containing severe storms decays faster than this says; and a
sun-synchronous object samples one local-time band rather than the global
average tabulated here. Both are second-order beside solar activity, and both
are reasons the published sentence says "roughly" and names the Sun rather than
quoting a figure to two places.

DENSITY TABLE. Globally averaged NRLMSIS-2.1 mass density, generated ONCE with
pymsis 0.12.0 and checked in here as a constant. It is not fetched, not
computed at build time, and has no network dependency -- the five-minute
publish cycle already has a 240-second budget and an incident behind it. The
generating parameters are recorded beside the table so it can be reproduced.
"""

from __future__ import annotations

import json
import math
import os
import statistics
import time
from pathlib import Path
from typing import Any, Iterable, Sequence

from pipeline.thermosphere import orbital_period_s

EARTH_EQUATORIAL_RADIUS_KM = 6378.137

#: Re-entry is taken at 120 km. Below that the first-order circular-orbit
#: result stops meaning anything and the remaining time is hours.
REENTRY_ALTITUDE_KM = 120.0

#: How the density table below was produced. Recorded here rather than in a
#: commit message so a reader who wants to reproduce it has the parameters.
DENSITY_TABLE_PROVENANCE = {
    "model": "NRLMSIS-2.1 via pymsis 0.12.0",
    "averaging": (
        "area-weighted over 12 latitudes and 24 longitudes, and over the four "
        "solstice/equinox days of one year, so local time and season are averaged out"
    ),
    "ap": 4.0,
    "levels": {"low": 70.0, "mean": 140.0, "high": 200.0},
    "note": (
        "F10.7 and F10.7A are set equal at each level. A sun-synchronous object "
        "samples a fixed local-time band rather than a global average, which is one of "
        "the reasons this is a teaching estimate and not an operational one."
    ),
}

#: (altitude km, rho at F10.7=70, rho at F10.7=140, rho at F10.7=200) in kg/m^3.
DENSITY_TABLE: tuple[tuple[int, float, float, float], ...] = (
    ( 110, 7.6395e-08, 7.8759e-08, 8.0758e-08),
    ( 120, 1.6285e-08, 1.6873e-08, 1.7380e-08),
    ( 130, 5.8159e-09, 5.9786e-09, 6.1287e-09),
    ( 140, 2.7279e-09, 2.8658e-09, 2.9987e-09),
    ( 150, 1.4723e-09, 1.6088e-09, 1.7338e-09),
    ( 160, 8.6367e-10, 9.9267e-10, 1.1052e-09),
    ( 170, 5.3538e-10, 6.5216e-10, 7.5101e-10),
    ( 180, 3.4526e-10, 4.4794e-10, 5.3359e-10),
    ( 190, 2.2943e-10, 3.1795e-10, 3.9165e-10),
    ( 200, 1.5614e-10, 2.3145e-10, 2.9462e-10),
    ( 210, 1.0838e-10, 1.7188e-10, 2.2592e-10),
    ( 220, 7.6506e-11, 1.2973e-10, 1.7591e-10),
    ( 230, 5.4806e-11, 9.9246e-11, 1.3872e-10),
    ( 240, 3.9775e-11, 7.6805e-11, 1.1055e-10),
    ( 250, 2.9204e-11, 6.0034e-11, 8.8902e-11),
    ( 260, 2.1667e-11, 4.7336e-11, 7.2056e-11),
    ( 270, 1.6227e-11, 3.7613e-11, 5.8807e-11),
    ( 280, 1.2255e-11, 3.0094e-11, 4.8288e-11),
    ( 290, 9.3263e-12, 2.4228e-11, 3.9869e-11),
    ( 300, 7.1461e-12, 1.9615e-11, 3.3081e-11),
    ( 310, 5.5095e-12, 1.5962e-11, 2.7572e-11),
    ( 320, 4.2715e-12, 1.3048e-11, 2.3074e-11),
    ( 330, 3.3284e-12, 1.0712e-11, 1.9382e-11),
    ( 340, 2.6056e-12, 8.8278e-12, 1.6337e-11),
    ( 350, 2.0484e-12, 7.3009e-12, 1.3814e-11),
    ( 360, 1.6166e-12, 6.0578e-12, 1.1714e-11),
    ( 370, 1.2805e-12, 5.0415e-12, 9.9611e-12),
    ( 380, 1.0178e-12, 4.2074e-12, 8.4916e-12),
    ( 390, 8.1162e-13, 3.5204e-12, 7.2559e-12),
    ( 400, 6.4926e-13, 2.9527e-12, 6.2136e-12),
    ( 410, 5.2098e-13, 2.4822e-12, 5.3320e-12),
    ( 420, 4.1932e-13, 2.0911e-12, 4.5844e-12),
    ( 430, 3.3853e-13, 1.7652e-12, 3.9487e-12),
    ( 440, 2.7415e-13, 1.4930e-12, 3.4071e-12),
    ( 450, 2.2272e-13, 1.2650e-12, 2.9446e-12),
    ( 460, 1.8154e-13, 1.0738e-12, 2.5488e-12),
    ( 470, 1.4847e-13, 9.1302e-13, 2.2096e-12),
    ( 480, 1.2187e-13, 7.7761e-13, 1.9182e-12),
    ( 490, 1.0041e-13, 6.6336e-13, 1.6675e-12),
    ( 500, 8.3058e-14, 5.6679e-13, 1.4515e-12),
    ( 510, 6.8997e-14, 4.8505e-13, 1.2651e-12),
    ( 520, 5.7574e-14, 4.1574e-13, 1.1040e-12),
    ( 530, 4.8269e-14, 3.5690e-13, 9.6453e-13),
    ( 540, 4.0671e-14, 3.0686e-13, 8.4371e-13),
    ( 550, 3.4448e-14, 2.6426e-13, 7.3887e-13),
    ( 560, 2.9336e-14, 2.2794e-13, 6.4781e-13),
    ( 570, 2.5125e-14, 1.9693e-13, 5.6860e-13),
    ( 580, 2.1644e-14, 1.7042e-13, 4.9964e-13),
    ( 590, 1.8757e-14, 1.4774e-13, 4.3952e-13),
    ( 600, 1.6353e-14, 1.2829e-13, 3.8707e-13),
    ( 610, 1.4344e-14, 1.1161e-13, 3.4126e-13),
    ( 620, 1.2658e-14, 9.7280e-14, 3.0120e-13),
    ( 630, 1.1236e-14, 8.4952e-14, 2.6613e-13),
    ( 640, 1.0032e-14, 7.4335e-14, 2.3542e-13),
    ( 650, 9.0080e-15, 6.5178e-14, 2.0849e-13),
    ( 660, 8.1320e-15, 5.7272e-14, 1.8485e-13),
    ( 670, 7.3790e-15, 5.0436e-14, 1.6408e-13),
    ( 680, 6.7282e-15, 4.4518e-14, 1.4582e-13),
    ( 690, 6.1628e-15, 3.9386e-14, 1.2974e-13),
    ( 700, 5.6689e-15, 3.4931e-14, 1.1559e-13),
    ( 710, 5.2350e-15, 3.1058e-14, 1.0310e-13),
    ( 720, 4.8517e-15, 2.7685e-14, 9.2088e-14),
    ( 730, 4.5115e-15, 2.4744e-14, 8.2358e-14),
    ( 740, 4.2077e-15, 2.2175e-14, 7.3756e-14),
    ( 750, 3.9353e-15, 1.9927e-14, 6.6144e-14),
    ( 760, 3.6896e-15, 1.7956e-14, 5.9402e-14),
    ( 770, 3.4671e-15, 1.6226e-14, 5.3425e-14),
    ( 780, 3.2647e-15, 1.4705e-14, 4.8121e-14),
    ( 790, 3.0799e-15, 1.3364e-14, 4.3410e-14),
    ( 800, 2.9103e-15, 1.2180e-14, 3.9222e-14),
    ( 810, 2.7543e-15, 1.1132e-14, 3.5495e-14),
    ( 820, 2.6102e-15, 1.0203e-14, 3.2174e-14),
    ( 830, 2.4768e-15, 9.3776e-15, 2.9214e-14),
    ( 840, 2.3529e-15, 8.6425e-15, 2.6570e-14),
    ( 850, 2.2375e-15, 7.9862e-15, 2.4209e-14),
    ( 860, 2.1298e-15, 7.3991e-15, 2.2095e-14),
    ( 870, 2.0291e-15, 6.8725e-15, 2.0203e-14),
    ( 880, 1.9347e-15, 6.3991e-15, 1.8506e-14),
    ( 890, 1.8461e-15, 5.9724e-15, 1.6983e-14),
    ( 900, 1.7627e-15, 5.5868e-15, 1.5614e-14),
    ( 910, 1.6843e-15, 5.2376e-15, 1.4382e-14),
    ( 920, 1.6103e-15, 4.9204e-15, 1.3272e-14),
    ( 930, 1.5405e-15, 4.6316e-15, 1.2270e-14),
    ( 940, 1.4745e-15, 4.3680e-15, 1.1366e-14),
    ( 950, 1.4121e-15, 4.1268e-15, 1.0547e-14),
    ( 960, 1.3531e-15, 3.9054e-15, 9.8058e-15),
    ( 970, 1.2971e-15, 3.7018e-15, 9.1332e-15),
    ( 980, 1.2440e-15, 3.5141e-15, 8.5222e-15),
    ( 990, 1.1937e-15, 3.3407e-15, 7.9662e-15),
    (1000, 1.1459e-15, 3.1800e-15, 7.4596e-15),
    (1010, 1.1005e-15, 3.0307e-15, 6.9973e-15),
    (1020, 1.0573e-15, 2.8919e-15, 6.5747e-15),
    (1030, 1.0162e-15, 2.7624e-15, 6.1878e-15),
    (1040, 9.7719e-16, 2.6414e-15, 5.8330e-15),
    (1050, 9.4001e-16, 2.5281e-15, 5.5072e-15),
    (1060, 9.0460e-16, 2.4218e-15, 5.2074e-15),
    (1070, 8.7087e-16, 2.3218e-15, 4.9312e-15),
    (1080, 8.3872e-16, 2.2278e-15, 4.6763e-15),
    (1090, 8.0807e-16, 2.1391e-15, 4.4406e-15),
    (1100, 7.7884e-16, 2.0553e-15, 4.2223e-15),
    (1110, 7.5095e-16, 1.9760e-15, 4.0198e-15),
    (1120, 7.2433e-16, 1.9010e-15, 3.8317e-15),
    (1130, 6.9891e-16, 1.8298e-15, 3.6566e-15),
    (1140, 6.7464e-16, 1.7621e-15, 3.4934e-15),
    (1150, 6.5146e-16, 1.6979e-15, 3.3410e-15),
    (1160, 6.2930e-16, 1.6367e-15, 3.1985e-15),
    (1170, 6.0812e-16, 1.5783e-15, 3.0650e-15),
    (1180, 5.8786e-16, 1.5227e-15, 2.9398e-15),
    (1190, 5.6849e-16, 1.4696e-15, 2.8222e-15),
    (1200, 5.4995e-16, 1.4189e-15, 2.7115e-15),
    (1210, 5.3221e-16, 1.3704e-15, 2.6072e-15),
    (1220, 5.1523e-16, 1.3240e-15, 2.5088e-15),
    (1230, 4.9897e-16, 1.2796e-15, 2.4159e-15),
    (1240, 4.8339e-16, 1.2370e-15, 2.3279e-15),
    (1250, 4.6847e-16, 1.1961e-15, 2.2446e-15),
    (1260, 4.5416e-16, 1.1570e-15, 2.1656e-15),
    (1270, 4.4045e-16, 1.1194e-15, 2.0906e-15),
    (1280, 4.2730e-16, 1.0832e-15, 2.0192e-15),
    (1290, 4.1469e-16, 1.0485e-15, 1.9513e-15),
    (1300, 4.0258e-16, 1.0152e-15, 1.8866e-15),)

DENSITY_LEVELS = ("low", "mean", "high")
_LEVEL_COLUMN = {"low": 1, "mean": 2, "high": 3}
_TABLE_STEP_KM = DENSITY_TABLE[1][0] - DENSITY_TABLE[0][0]


def density_kg_m3(level: str, altitude_km: float) -> float:
    """Globally averaged NRLMSIS density, log-interpolated between table rows.

    Log interpolation rather than linear because density falls by an order of
    magnitude every few table steps; a straight line between two rows of an
    exponential is wrong by tens of percent in the middle of the interval.
    """
    column = _LEVEL_COLUMN.get(level)
    if column is None:
        raise ValueError(f"unknown solar level {level!r}; expected one of {DENSITY_LEVELS}")
    first, last = DENSITY_TABLE[0], DENSITY_TABLE[-1]
    if altitude_km <= first[0]:
        return first[column]
    if altitude_km >= last[0]:
        return last[column]
    index = int((altitude_km - first[0]) // _TABLE_STEP_KM)
    low_row, high_row = DENSITY_TABLE[index], DENSITY_TABLE[index + 1]
    fraction = (altitude_km - low_row[0]) / _TABLE_STEP_KM
    return math.exp(
        math.log(low_row[column]) * (1.0 - fraction) + math.log(high_row[column]) * fraction
    )


def theil_sen_slope(
    times: Sequence[float], values: Sequence[float], sample_cap: int = 3000
) -> float | None:
    """Median of pairwise slopes: the robust fit, and robust is the requirement.

    An ordinary least-squares line through a satellite's semi-major axis is
    dragged by any manoeuvre in the window, and a spacecraft that raised its
    orbit once in two years would otherwise report a decay rate that is mostly
    that one burn. The median of the pairwise slopes ignores a minority of
    jumps entirely.

    sample_cap bounds the O(n^2) pair enumeration; the series run to a couple of
    thousand points, and a decimated subset of the pairs gives the same median
    to well inside the precision anything here is quoted at.
    """
    count = len(times)
    if count < 2:
        return None
    stride = max(1, (count * count) // (2 * max(1, sample_cap)))
    slopes: list[float] = []
    seen = 0
    for i in range(count):
        for j in range(i + 1, count):
            seen += 1
            if seen % stride:
                continue
            span = times[j] - times[i]
            if span > 0:
                slopes.append((values[j] - values[i]) / span)
    return statistics.median(slopes) if slopes else None


#: A record shorter than this measures the diurnal bulge and the current storm
#: rather than the trend, and a handful of element sets measures the fitter.
MIN_RECORD_DAYS = 180.0
MIN_ELEMENT_SETS = 40
#: Only the recent record is used. A 2019 rate is a measurement of the 2019
#: atmosphere, and the object may have manoeuvred since.
WINDOW_DAYS = 730.0


def measured_decay_km_per_day(samples: Sequence[dict[str, Any]]) -> float | None:
    """This object's own rate of altitude loss, or None if it cannot be measured.

    Returns None -- deliberately, and this is most of the value of the function
    -- when the object is not passively decaying. WORLDVIEW 1 has two years of
    history and a slope near zero because it is station-kept; LEGION 3 gained
    68 km because it raised its orbit. Publishing "199 years to re-entry" for a
    spacecraft holding its altitude with thrusters would be a confident number
    about the wrong physics, so a maintained orbit is refused rather than
    estimated. The test is that BOTH halves of the window decay: one negative
    overall slope can be produced by a single manoeuvre at one end.
    """
    if len(samples) < MIN_ELEMENT_SETS:
        return None
    latest = samples[-1]["t"]
    window = [row for row in samples if latest - row["t"] <= WINDOW_DAYS * 86_400_000]
    if len(window) < MIN_ELEMENT_SETS:
        return None
    start = window[0]["t"]
    times = [(row["t"] - start) / 86_400_000.0 for row in window]
    values = [float(row["semiMajorAxisKm"]) for row in window]
    if times[-1] < MIN_RECORD_DAYS:
        return None
    half = len(window) // 2
    overall = theil_sen_slope(times, values)
    first = theil_sen_slope(times[:half], values[:half])
    second = theil_sen_slope(times[half:], values[half:])
    if overall is None or first is None or second is None:
        return None
    if overall >= 0 or first >= 0 or second >= 0:
        return None
    return overall


def years_to_reentry(altitude_km: float, decay_km_per_day: float, level: str) -> float | None:
    """Integrate the measured decay down to 120 km under one solar assumption.

    None means "longer than this is worth quoting", which is the honest answer
    for anything above about 900 km: the integral there runs to tens of
    thousands of years, a figure with no meaning that a reader would still read
    as a prediction.
    """
    if decay_km_per_day >= 0 or altitude_km <= REENTRY_ALTITUDE_KM:
        return None
    reference_radius = EARTH_EQUATORIAL_RADIUS_KM + altitude_km
    # The measured rate is taken to correspond to the average solar level; the
    # band comes from re-evaluating the profile at the other two.
    reference_density = density_kg_m3("mean", altitude_km)
    reference_revs = 86400.0 / orbital_period_s(altitude_km)
    days = 0.0
    altitude = altitude_km
    while altitude > REENTRY_ALTITUDE_KM:
        step = min(1.0, altitude - REENTRY_ALTITUDE_KM)
        middle = altitude - step / 2.0
        radius = EARTH_EQUATORIAL_RADIUS_KM + middle
        scale = (
            (density_kg_m3(level, middle) / reference_density)
            * (radius * radius) / (reference_radius * reference_radius)
            * ((86400.0 / orbital_period_s(middle)) / reference_revs)
        )
        rate = abs(decay_km_per_day) * scale
        if rate <= 0:
            return None
        days += step / rate
        altitude -= step
        if days > 365.25 * 1000.0:
            return None
    return days / 365.25


def estimate(altitude_km: float, samples: Sequence[dict[str, Any]]) -> dict[str, Any] | None:
    """The published estimate: a measured rate and a three-point solar band."""
    decay = measured_decay_km_per_day(samples)
    if decay is None:
        return None
    middle = years_to_reentry(altitude_km, decay, "mean")
    return {
        "lossKmPerYear": -decay * 365.25,
        "yearsAverageCycle": middle,
        "yearsActiveSun": years_to_reentry(altitude_km, decay, "high"),
        "yearsQuietSun": years_to_reentry(altitude_km, decay, "low"),
    }


def _round_rate(value: float) -> str:
    if value >= 10:
        return str(round(value))
    if value >= 1:
        return f"{value:.1f}"
    return f"{value:.2f}"


def _round_years(value: float) -> str:
    """Round HARD. The band around this number spans a factor of five to twenty,
    so "2.2 years" claims a precision the estimate does not have and a reader
    would reasonably take at face value."""
    if value >= 100:
        return str(round(value / 50) * 50)
    if value >= 20:
        return str(round(value / 5) * 5)
    return str(max(1, round(value)))


def lifetime_sentence(measure: dict[str, Any] | None) -> str:
    """One sentence, or none at all.

    The measured rate leads because it is the part that is measured. The
    lifetime follows as a consequence of it, and the clause after the dash
    names the assumption that dominates the answer rather than burying it in a
    methods page nobody opens.
    """
    if not measure:
        return ""
    rate = _round_rate(measure["lossKmPerYear"])
    middle = measure.get("yearsAverageCycle")
    if middle is None:
        return (
            f"Its own tracked orbit is losing only about {rate} km a year, which at this "
            "height means drag will not bring it down within any horizon worth quoting."
        )
    if middle >= 60:
        return (
            f"Its own tracked orbit is losing about {rate} km a year, so on an average solar "
            f"cycle drag would need roughly {_round_years(middle)} years to bring it down "
            "— far beyond the twenty-five-year disposal guideline it would be judged against."
        )
    if middle < 1.5:
        return (
            f"Its own tracked orbit is losing about {rate} km a year, which puts re-entry "
            "inside about a year on an average solar cycle — sooner if the Sun stays "
            "active, later if it goes quiet."
        )
    return (
        f"Its own tracked orbit is losing about {rate} km a year, putting re-entry roughly "
        f"{_round_years(middle)} years out on an average solar cycle — sooner if the Sun "
        "stays active, later if it goes quiet."
    )


# ---------------------------------------------------------------------------
# Reading the archive
# ---------------------------------------------------------------------------

#: Shards are keyed norad % 256 (see pipeline/orbit_release.py), so the objects
#: that need an estimate select their own shards and nothing else is opened.
#: The whole set is 2.3 GB and 34 seconds; the fifty-odd objects that reach
#: this code are about 5 seconds, one shard resident at a time.
SHARD_COUNT = 256

#: Hard stop. Orbit history has already taken a five-minute publish cycle past
#: its 240-second timeout once (2026-08-08, 9.3 GB resident, four hours of
#: publishes lost). This lane is worth some seconds and worth zero outages.
DEFAULT_BUDGET_SECONDS = 25.0


def decay_samples(
    data_root: Path,
    catalog_ids: Iterable[int],
    budget_seconds: float = DEFAULT_BUDGET_SECONDS,
) -> dict[int, list[dict[str, Any]]]:
    """Per-object element-set series for the given objects, from the LAST publish.

    Reads the previously published orbitHistory shards, because the catalogue is
    built before this cycle's orbit history is written -- and because that lane
    is currently disabled, so what is on disk is what there is. Every failure
    here is silent and returns less data: an object with no series simply gets
    no lifetime clause, which is a card that says slightly less rather than a
    publish that fails.
    """
    if os.environ.get("SPACE_EXPLORER_DISABLE_LIFETIME") == "1":
        return {}
    wanted = {int(value) for value in catalog_ids}
    if not wanted:
        return {}
    manifest_path = data_root / "manifest.json"
    if not manifest_path.is_file():
        return {}
    try:
        record = json.loads(manifest_path.read_text()).get("orbitHistory") or {}
        shards = {int(entry["shard"]): str(entry["path"]) for entry in record.get("shards") or []}
    except (OSError, ValueError, KeyError, TypeError):
        return {}
    if not shards:
        return {}
    started = time.monotonic()
    series: dict[int, list[dict[str, Any]]] = {}
    for shard in sorted({value % SHARD_COUNT for value in wanted}):
        if time.monotonic() - started > budget_seconds:
            print(
                f"NOTE: orbital-lifetime archive read stopped at {budget_seconds:.0f}s; "
                f"{len(series)} of {len(wanted)} objects measured"
            )
            break
        path = data_root / shards.get(shard, "")
        if not path.is_file():
            continue
        try:
            objects = json.loads(path.read_text()).get("objects") or []
        except (OSError, ValueError):
            continue
        for entry in objects:
            catalog_id = entry.get("norad")
            if catalog_id in wanted and isinstance(entry.get("samples"), list):
                series[int(catalog_id)] = entry["samples"]
    return series
