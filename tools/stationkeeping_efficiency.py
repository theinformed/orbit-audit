#!/usr/bin/env python3
"""T10b/T10c: north-south burn-timing efficiency, and east-west deadband economics.

Binding registration: `docs/stationkeeping-efficiency-preregistration-20260922.md`,
committed alone at `f0f2b41` before any number this tool produces existed. Read it
first. Every screen, seed, constant and acceptance rule below is fixed there; this
file implements them and is not permitted to add one.

What this measures, in two sentences:

* **T10b** -- for each detected north-south manoeuvre, how much of the plane
  rotation the satellite bought went into changing its INCLINATION rather than
  swinging its NODE, which is exactly the `cos u` penalty for burning away from
  a node crossing. Reported as `eta = DV_ideal / DV_spent` with the node burn
  `2 v sin(|di|/2)` as the ideal, and as the effective burn location `u_eff`.
* **T10c** -- the relationship between an object's measured east-west deadband
  and its annualised east-west station-keeping delta-v, against the derived
  relation `DV_year = a A T_year / 3`, in which the deadband CANCELS.

What neither measures, stated here as well as in the registration §0 because a
docstring is where the next reader looks: gravity loss and in-burn steering loss
are structurally invisible to any instrument built on two-line element sets.
Nothing in this file may be described as either.

Two lessons of T10a (`docs/transfer-loss-results-20260922.md`) are built in:

1. **Natural dynamics are never charged to an operator.** The lunisolar pole
   precession about the Laplace pole and the production J2 nodal regression are
   propagated as a single rigid rotation and subtracted as a VECTOR before any
   element change is attributed to a burn. The uncorrected companion travels
   beside every corrected number.
2. **Every delta-v names which price it is.** T10b's primary denominator is the
   exact minimum impulse; the shipped detector price is a registered secondary
   and both are published per event. T10a measured the shipped price at a median
   0.942 of the exact minimum with a maximum of 93.40, so the two are never
   silently interchanged.

Nothing here detects anything. The event set is T2's, reused and hash-pinned.
Read-only against the archive; CPU only; no government or military object is
read, priced or named.
"""

from __future__ import annotations

import argparse
import datetime as dt
import gzip
import hashlib
import json
import math
import os
import random
import resource
import sqlite3
import statistics
import sys
import time
from bisect import insort
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.orbit_history import (  # noqa: E402
    MU_WGS72,
    RE_WGS72,
    noise_floor_for,
    semi_major_axis_km,
)
# The plane geometry and the nodal regression are the production detector's own,
# imported rather than re-implemented -- registration §2.3(b), §2.4, and the
# direct instruction of T10a's lesson (a).
from pipeline.orbit_events import (  # noqa: E402
    GEO_BAND_KM,
    GEO_SEMI_MAJOR_AXIS_KM,
    j2_secular_rates_deg_per_day,
    plane_rotation_deg,
)
# Mean longitude, GMST, the drift-informed unwrap and the triaxiality constants
# are T8a's, registered in docs/proximity-preregistration-20260922.md §2 and
# imported rather than restated (registration §1.3, §4.1, §4.5).
from tools.proximity_geo import (  # noqa: E402
    A_GEO_KM,
    DAY_MS,
    EARTH_RADIUS_KM,
    ECC_MAX,
    INC_MAX_DEG,
    J22,
    LAMBDA_DDOT_MAX,
    MM_MAX_REV_DAY,
    MM_MIN_REV_DAY,
    MU_KM3_S2,
    OMEGA_E_DEG_PER_DAY,
    STABLE_LONGITUDES_DEG,
    STATION_HALF_WIDTH_DEG,
    STATION_MIN_DAYS,
    V_GEO_KM_S,
    drift_rate_deg_per_day,
    gmst_deg,
    mean_longitude_deg,
    unwrap_longitude,
    wrap180,
)

import numpy as np  # noqa: E402

# ---------------------------------------------------------------------------
# Registered constants. Every one is fixed by the registration; a change to any
# of them is a change to the registered study.
# ---------------------------------------------------------------------------

REGISTRATION = "docs/stationkeeping-efficiency-preregistration-20260922.md"
REGISTRATION_COMMIT = "f0f2b41"

MU = MU_WGS72                        # km^3/s^2, the value the archive is fitted against
G0 = 9.80665                         # m/s^2

# -- T10b, registration §2.3(a): the Laplace-plane precession model -----------
LAPLACE_TILT_DEG = 7.4               # Laplace pole offset from the equatorial pole at GEO
LAPLACE_PRECESSION_PERIOD_YR = 53.0  # full circuit about the Laplace pole
# The SENSE of that circuit, which registration eq. (9) did not state and whose
# unstated default (+1) is wrong. The drift-direction control of registration
# §3.3 fired on it, and the direct calibration of `laplace_calibration()` below
# measures it on eleven retired commercial-civil GEO satellites: the circuit is
# RETROGRADE about the Laplace pole. A prograde circuit would carry an
# initially equatorial GEO orbit's pole toward RAAN 270 deg; every uncontrolled
# object in this archive goes the other way, toward RAAN ~90 deg, and arrives at
# 14.3 deg of inclination with its node near 0-40 deg.
LAPLACE_SENSE = -1.0
REGISTERED_SENSE = 1.0               # the registered-as-written model, kept as a companion
DAYS_PER_YEAR = 365.25
DRIFT_INTERVAL_DEG_PER_YR = (0.75, 0.95)   # the cited Soop interval, a screen not a law

# -- T10b, registration §2.6: the screens ------------------------------------
NS_SIGNATURES = frozenset({"geo-north-south-keeping", "inclination-change"})
RAISING_WINDOW_DAYS = 548            # the odometer's 18 months
SINGLE_EVENT_CEILING_MPS = 2500.0    # the odometer's frozen rule 7
SPAN_PRIMARY_DAYS = 7.0              # N5 primary
SPAN_SENSITIVITIES_DAYS = (3.0, 21.0)
NOISE_SIGMAS_THETA = 5.0             # N6
NOISE_SIGMAS_INC = 10.0              # N6, for u_eff only

# -- T10c, registration §4.5: the segment rules ------------------------------
SEGMENT_GAP_BREAK_DAYS = 10.0
DEADBAND_PRIMARY_PCT = (2.5, 97.5)
DEADBAND_SENSITIVITY_PCT = (1.0, 99.0)
DRIFT_AMPLITUDE_PCT = 97.5
FREE_DRIFT_MIN_SAMPLES = 5
FREE_DRIFT_MIN_SPAN_DAYS = 3.0

# -- statistics ---------------------------------------------------------------
BOOTSTRAP_DRAWS = 10000              # registration §2.7
MONTE_CARLO_DRAWS = 200              # registration §3.2 R4
SEED = 20260922

# -- acceptance ---------------------------------------------------------------
B1_MIN_EVENTS = 30
B1_MIN_OBJECTS = 10
B3_NOISE_MULTIPLE = 5.0
B3_MC_MAX_SHIFT = 0.25
B4_MAX_NATURAL_FRACTION = 0.25
C1_MIN_SEGMENTS = 20
C1_MIN_OBJECTS = 15
C4_RECALL_LIMITED_BELOW = 0.25
R1_MAX_RELATIVE_SHIFT = 0.25
DRIFT_DIRECTION_TOLERANCE_DEG = 20.0
PREDICTED_DRIFT_RAAN_DEG = 270.0

EXPECTED_HASHES = {
    "events": "6804c147596fdf2c78c1c6671a97f8037bcd33202dac785db85aac943d49e66f",
    "archive": "ffc4c4e521ca0c4eb78d5ec48039e8c9032e2f05183e5b3f09fe703bc5b734c3",
    "catalogue": "7f7a50bc4dff644705f52ec28fb2c52a7f8589c7be45433a7f4c23dcc72711a9",
}

DEFAULT_EVENTS = Path("/tmp/t2-repricing-20260921/events.jsonl.gz")
DEFAULT_ARCHIVE = Path("/tmp/eol-study-20260920/archive.sqlite3")
DEFAULT_CATALOGUE = ROOT / "data" / "propulsion-catalog-v1.json"

SECONDS_PER_YEAR = DAYS_PER_YEAR * 86400.0


# ===========================================================================
# Registration §2.2 -- the geometry of a plane change, exact
# ===========================================================================

def dv_rotation_mps(v_km_s: float, theta_deg: float) -> float:
    """Registration eq. (1): the exact impulse for a pure plane rotation.

    `2 v sin(theta/2)` is the chord of the velocity rotation. Exact -- it is
    not a small-angle expansion, and no first-order relation appears anywhere
    in this file, after T2's screen measured the first-order tangential
    relation overstating the cost by up to 127% on real events.
    """
    return 2000.0 * v_km_s * math.sin(math.radians(theta_deg) / 2.0)


def inclination_after(inc_deg: float, theta_deg: float, u_deg: float) -> float:
    """Registration eq. (3), exact, for any i, theta and u.

        cos i' = cos(theta) cos(i) - sin(theta) sin(i) cos(u)

    Derived from `h' = cos(theta) h - sin(theta) t` -- the rotation of the
    orbit pole about the radius vector at argument of latitude `u` -- dotted
    with `z`, using `t . z = sin(i) cos(u)`.
    """
    i = math.radians(inc_deg)
    th = math.radians(theta_deg)
    u = math.radians(u_deg)
    c = math.cos(th) * math.cos(i) - math.sin(th) * math.sin(i) * math.cos(u)
    return math.degrees(math.acos(max(-1.0, min(1.0, c))))


def rotation_for(inc_deg: float, delta_inc_deg: float, u_deg: float) -> float:
    """Registration eq. (6): the plane rotation a burn at `u` must spend to
    achieve the inclination change `delta_inc_deg`.

    Solves eq. (3) for theta by writing its right-hand side as
    `R cos(theta + phi)` with `R cos(phi) = cos i` and `R sin(phi) = sin i cos u`.

    `cos(theta + phi) = cos(i') / R` has TWO roots, `theta = ±acos(...) - phi`,
    which are the two rotations that land on the same inclination -- the short
    way round and the long way round. The smaller non-negative one is the
    cheapest rotation that achieves the change, and that is the one an ideal
    costs. Taking the principal `acos` branch alone would return `i + i'`
    instead of `i - i'` for a burn at the far node, i.e. it would price a
    routine north-south correction at several times its cost.
    """
    i = math.radians(inc_deg)
    u = math.radians(u_deg)
    r = math.hypot(math.cos(i), math.sin(i) * math.cos(u))
    if r <= 0.0:
        return float("nan")
    phi = math.atan2(math.sin(i) * math.cos(u), math.cos(i))
    base = math.acos(max(-1.0, min(1.0, math.cos(i + math.radians(delta_inc_deg)) / r)))
    roots = [t for t in (base - phi, -base - phi) if t >= -1e-12]
    if not roots:
        return float("nan")
    return math.degrees(max(0.0, min(roots)))


def radius_unit_vector(inc_deg: float, raan_deg: float, u_deg: float
                       ) -> tuple[float, float, float]:
    """The radius unit vector at argument of latitude `u`, i.e. the axis the
    burn rotates the orbit plane about.

    Its `z` component is `sin(i) sin(u)`, and the transverse direction 90 deg
    ahead has `z` component `sin(i) cos(u)` -- the fact eq. (3) is derived from.
    """
    i = math.radians(inc_deg)
    o = math.radians(raan_deg)
    u = math.radians(u_deg)
    return (math.cos(o) * math.cos(u) - math.sin(o) * math.sin(u) * math.cos(i),
            math.sin(o) * math.cos(u) + math.cos(o) * math.sin(u) * math.cos(i),
            math.sin(u) * math.sin(i))


def penalty_factor(inc_deg: float, delta_inc_deg: float, u_deg: float) -> float:
    """Registration eq. (7): the exact penalty for burning `u` from the node.

    `sin(theta/2) / sin(|di|/2)`, whose small-angle limit is `sec(u)`. The
    limit is quoted; the exact form is what is used.
    """
    theta = rotation_for(inc_deg, delta_inc_deg, u_deg)
    denom = math.sin(math.radians(abs(delta_inc_deg)) / 2.0)
    if denom <= 0.0:
        return float("nan")
    return math.sin(math.radians(theta) / 2.0) / denom


def argument_of_latitude(inc_deg: float, inc_after_deg: float, theta_deg: float) -> float | None:
    """Registration eq. (8): invert eq. (3) for the effective burn location.

        cos u = (cos(theta) cos(i) - cos(i')) / (sin(theta) sin(i))

    Returns None where the inversion is degenerate -- a satellite at zero
    inclination has no node, and screen N6 keeps that case out of the
    population rather than letting it return a number.
    """
    i = math.radians(inc_deg)
    th = math.radians(theta_deg)
    denom = math.sin(th) * math.sin(i)
    if denom <= 0.0:
        return None
    c = (math.cos(th) * math.cos(i) - math.cos(math.radians(inc_after_deg))) / denom
    if not (-1.0000001 <= c <= 1.0000001):
        return None
    return math.degrees(math.acos(max(-1.0, min(1.0, c))))


def node_offset_deg(u_deg: float) -> float:
    """Angular distance from the NEAREST node, in [0, 90].

    Both `u = 0` and `u = 180` are node crossings: one raises inclination and
    one lowers it, and both spend the whole rotation on inclination. The
    penalty depends on `|cos u|`, so the reportable placement figure is the
    distance to whichever node is nearer.
    """
    return 90.0 - abs(90.0 - u_deg)


def dv_min_combined_mps(v_before_km_s: float, v_after_km_s: float, theta_deg: float) -> float:
    """Registration eq. (13): the exact minimum single impulse.

        dv^2 = v-^2 + v+^2 - 2 v- v+ cos(theta)

    the law of cosines on the velocity triangle, which is T10a's eq. (4). Its
    identity form, used by the tests and by the ideal below:

        dv^2 = (v+ - v-)^2 + 4 v- v+ sin^2(theta/2)

    so the pure-rotation part of the cost is `2 sqrt(v- v+) sin(theta/2)`.
    """
    th = math.radians(theta_deg)
    speed_term = (v_after_km_s - v_before_km_s) ** 2
    rot_term = 4.0 * v_before_km_s * v_after_km_s * math.sin(th / 2.0) ** 2
    return 1000.0 * math.sqrt(max(0.0, speed_term + rot_term))


def dv_ideal_node_mps(v_before_km_s: float, v_after_km_s: float, delta_inc_deg: float) -> float:
    """The ideal of registration §2.2(a) at the same two speeds.

    `2 sqrt(v- v+) sin(|di|/2)`. The geometric mean is not a convenience: it
    is what makes registration §2.2(e)'s identity exact, i.e. a pure node burn
    with no semi-major-axis change scores eta = 1 to floating point.
    """
    v = math.sqrt(v_before_km_s * v_after_km_s)
    return 2000.0 * v * math.sin(math.radians(abs(delta_inc_deg)) / 2.0)


# ===========================================================================
# Registration §2.3/§2.4 -- the natural pole motion, and its subtraction
# ===========================================================================

def pole_vector(inc_deg: float, raan_deg: float) -> tuple[float, float, float]:
    """The orbit's angular-momentum unit vector in the equatorial frame."""
    i = math.radians(inc_deg)
    r = math.radians(raan_deg)
    return (math.sin(i) * math.sin(r), -math.sin(i) * math.cos(r), math.cos(i))


def pole_to_elements(p: tuple[float, float, float]) -> tuple[float, float]:
    """(inclination deg, RAAN deg) from a pole unit vector."""
    x, y, z = p
    inc = math.degrees(math.atan2(math.hypot(x, y), z))
    raan = math.degrees(math.atan2(x, -y)) % 360.0
    return inc, raan


def laplace_pole(tilt_deg: float = LAPLACE_TILT_DEG) -> tuple[float, float, float]:
    """The GEO Laplace pole: `RAAN = 0`, inclination `L`, i.e. `(0, -sin L, cos L)`.

    Its direction is fixed by the ecliptic and lunar mean poles lying at right
    ascension 270 deg. The consequence -- that an equatorial GEO orbit drifts
    toward `RAAN = 270 deg` -- is a falsifiable prediction, and the
    drift-direction control of registration §3.3 tests it on this archive.
    """
    t = math.radians(tilt_deg)
    return (0.0, -math.sin(t), math.cos(t))


def natural_rate_vector(a_km: float, ecc: float, inc_deg: float,
                        precession_period_yr: float = LAPLACE_PRECESSION_PERIOD_YR,
                        include_j2: bool = False,
                        sense: float = LAPLACE_SENSE) -> tuple[float, float, float]:
    """The secular angular velocity of the orbit pole, deg/day.

    Registration eq. (9) is the lunisolar precession about the Laplace pole.
    Registration eq. (10) adds the production J2 nodal regression about `z`.

    **THE REGISTERED SUM DOUBLE-COUNTS THE OBLATENESS, and the primary path
    here therefore applies eq. (9) alone.** This is a registration defect found
    by the test suite before any data was read, and it is reported as one
    rather than silently kept or silently dropped. The reason is in the source
    the registration itself cites: the Laplace pole sits at `L = 7.4 deg`
    precisely because J2's `-4.8995 deg/yr` nodal regression competes with the
    lunisolar torque -- "which is what tilts the GEO Laplace plane to roughly
    7.4 deg instead of 23.4 and reduces the drift"
    <!-- src: docs/cadence-s1s2-preregistration-20260922.md §3.1 -->. A
    Laplace-plane rotation is therefore ALREADY the combined secular motion:
    an orbit sitting exactly on the Laplace plane does not precess, and adding
    eq. (10) would make it precess at `4.8995 sin(7.4 deg) = 0.63 deg/yr`,
    which is a statement the Laplace plane's own definition forbids.

    `include_j2=True` reproduces the registered sum exactly, and every event
    carries its value so the size of the defect is published rather than
    asserted. At the inclinations this population lives at it is small -- the
    extra pole speed is `|RAAN_dot| sin(i)`, i.e. 0.0043 deg/yr at
    `i = 0.05 deg` -- but it is not small at 5 deg and it is not nothing.

    The two terms act SIMULTANEOUSLY, so where both are used their angular
    velocities add and the motion over an interval is one rigid rotation about
    the combined axis -- which is what makes the propagator's half-steps
    compose exactly (§6.1 test 6).
    """
    omega_l = sense * 360.0 / (precession_period_yr * DAYS_PER_YEAR)
    px, py, pz = laplace_pole()
    raan_dot = 0.0
    if include_j2:
        rates = j2_secular_rates_deg_per_day(a_km, ecc, inc_deg)
        raan_dot = rates[0] if rates else 0.0
    return (omega_l * px, omega_l * py, omega_l * pz + raan_dot)


def rotate_about(p: tuple[float, float, float], axis: tuple[float, float, float],
                 angle_deg: float) -> tuple[float, float, float]:
    """Rodrigues rotation of a unit vector about a unit axis."""
    n = math.sqrt(sum(c * c for c in axis))
    if n == 0.0 or angle_deg == 0.0:
        return p
    kx, ky, kz = (c / n for c in axis)
    a = math.radians(angle_deg)
    ca, sa = math.cos(a), math.sin(a)
    px, py, pz = p
    cross = (ky * pz - kz * py, kz * px - kx * pz, kx * py - ky * px)
    dot = kx * px + ky * py + kz * pz
    return tuple(p_i * ca + c_i * sa + k_i * dot * (1.0 - ca)
                 for p_i, c_i, k_i in zip(p, cross, (kx, ky, kz)))


def propagate_natural(inc_deg: float, raan_deg: float, a_km: float, ecc: float,
                      days: float, precession_period_yr: float = LAPLACE_PRECESSION_PERIOD_YR,
                      include_j2: bool = False, sense: float = LAPLACE_SENSE
                      ) -> tuple[float, float, tuple[float, float, float]]:
    """Carry the pole forward by the natural motion alone. Registration §2.4 step 2."""
    p = pole_vector(inc_deg, raan_deg)
    w = natural_rate_vector(a_km, ecc, inc_deg, precession_period_yr, include_j2, sense)
    mag = math.sqrt(sum(c * c for c in w))
    if mag == 0.0 or days == 0.0:
        return inc_deg, raan_deg, p
    moved = rotate_about(p, w, mag * days)
    norm = math.sqrt(sum(c * c for c in moved))
    moved = tuple(c / norm for c in moved)
    inc_pred, raan_pred = pole_to_elements(moved)
    return inc_pred, raan_pred, moved


def period_for_drift_rate(deg_per_year: float, tilt_deg: float = LAPLACE_TILT_DEG) -> float:
    """The Laplace-circuit period that produces a given pole speed at i = 0.

    `omega sin(L) = rate`, so `T = 360 sin(L) / rate` years. Registration §2.3
    registers 0.75-0.95 deg/yr as the interval and this is how R1 applies it.
    """
    return 360.0 * math.sin(math.radians(tilt_deg)) / deg_per_year


def pole_angle_deg(p: tuple[float, float, float], q: tuple[float, float, float]) -> float:
    """Angle between two pole unit vectors, by the half-angle form.

    The chord is computed first and the angle from `2 asin(chord/2)`, for the
    same reason `plane_rotation_deg` uses a half-angle: `acos` of two identical
    poles returns rounding noise, and this returns exactly zero.
    """
    chord = math.sqrt(sum((a - b) ** 2 for a, b in zip(p, q)))
    return 2.0 * math.degrees(math.asin(min(1.0, chord / 2.0)))


# ===========================================================================
# Registration §4.1/§4.2 -- the triaxial acceleration and the deadband cycle
# ===========================================================================

def triaxial_acceleration_max_deg_day2_t3() -> float:
    """T3's form: `A = 18 n^2 J22 (RE/a)^2`, in deg/day^2.

    <!-- src: tools/cadence_lines.py, geo_longitude_acceleration_deg_day2 -->
    """
    n = 2.0 * math.pi / 86164.0905
    a = 42164.2
    amp = 18.0 * n * n * 1.8154e-6 * (6378.137 / a) ** 2     # rad/s^2
    return math.degrees(amp) * 86400.0 * 86400.0


def triaxial_acceleration_max_deg_day2_t8a() -> float:
    """T8a's form: `A = 3 omega_E a_T,max / v_GEO`, in deg/day^2.

    <!-- src: tools/proximity_geo.py, LAMBDA_DDOT_MAX -->  Imported rather than
    recomputed, so the two forms above and here cannot drift apart silently.
    """
    return LAMBDA_DDOT_MAX


A_MAX_DEG_DAY2 = triaxial_acceleration_max_deg_day2_t8a()
A_MAX_RAD_S2 = math.radians(A_MAX_DEG_DAY2) / (86400.0 ** 2)


def triaxial_acceleration_deg_day2(longitude_deg: float) -> float:
    """`A(lambda) = A_max |sin(2(lambda - 75.1))|`, the magnitude at a slot.

    Zero at the two stable longitudes and at the two unstable ones 90 deg away;
    maximal midway. Registration §4.1.
    """
    return A_MAX_DEG_DAY2 * abs(math.sin(2.0 * math.radians(longitude_deg - STABLE_LONGITUDES_DEG[0])))


def triaxial_acceleration_signed_deg_day2(longitude_deg: float) -> float:
    """The signed acceleration of registration eq. (14), restoring toward 75.1."""
    return -A_MAX_DEG_DAY2 * math.sin(2.0 * math.radians(longitude_deg - STABLE_LONGITUDES_DEG[0]))


def cycle_period_days(half_width_deg: float, accel_deg_day2: float) -> float:
    """Registration eq. (16): `T = 4 sqrt(R / A)`."""
    if accel_deg_day2 <= 0.0 or half_width_deg <= 0.0:
        return float("nan")
    return 4.0 * math.sqrt(half_width_deg / accel_deg_day2)


def dv_per_cycle_mps(half_width_deg: float, accel_deg_day2: float,
                     a_km: float = A_GEO_KM) -> float:
    """Registration eq. (18): `DV_cycle = (4a/3) sqrt(A R)`.

    From `d(lambda_dot) = -3 dv / a` (eq. 17) and `lambda_dot_0 = 2 sqrt(A R)`
    (eq. 15). The deg/day rate is converted to rad/s before it meets a km.
    """
    if accel_deg_day2 <= 0.0 or half_width_deg <= 0.0:
        return 0.0
    rate_deg_day = 4.0 * math.sqrt(accel_deg_day2 * half_width_deg)
    rate_rad_s = math.radians(rate_deg_day) / 86400.0
    return (a_km * 1000.0 / 3.0) * rate_rad_s


def dv_per_year_mps(accel_deg_day2: float, a_km: float = A_GEO_KM) -> float:
    """Registration eq. (19): `DV_year = a A T_year / 3` -- the deadband CANCELS.

    This function deliberately takes no deadband argument. That is the result:
    the annual east-west station-keeping budget is set by the slot's triaxial
    acceleration alone, and a tighter box buys the same bill in more, smaller
    burns.
    """
    accel_rad_s2 = math.radians(accel_deg_day2) / (86400.0 ** 2)
    return (a_km * 1000.0 / 3.0) * accel_rad_s2 * SECONDS_PER_YEAR


def manoeuvres_per_year(half_width_deg: float, accel_deg_day2: float) -> float:
    """`365.25 / T`, proportional to `R^-1/2` -- what a tighter box actually costs."""
    t = cycle_period_days(half_width_deg, accel_deg_day2)
    return DAYS_PER_YEAR / t if t == t and t > 0 else float("nan")


def deadband_from_drift_amplitude(rate_amp_deg_day: float, accel_deg_day2: float) -> float:
    """Registration §4.5's independent estimator: `R = lambda_dot^2 / (4 A)`,
    the inverse of eq. (15). Reads the deadband off the MEAN MOTION channel
    rather than the longitude channel, so the two are independent measurements
    of the same box."""
    if accel_deg_day2 <= 0.0:
        return float("nan")
    return rate_amp_deg_day * rate_amp_deg_day / (4.0 * accel_deg_day2)


def north_south_budget_mps_per_year(drift_deg_per_year: float = 0.85,
                                    v_km_s: float = V_GEO_KM_S) -> float:
    """Registration §4.4: `2 v sin(drift/2)` per year -- 45.6 m/s/yr at 0.85 deg/yr."""
    return dv_rotation_mps(v_km_s, drift_deg_per_year)


# ===========================================================================
# Inputs
# ===========================================================================

@dataclass(frozen=True)
class State:
    """One archived element set, in the units the physics wants."""
    epoch_ms: int
    a_km: float
    e: float
    inc_deg: float
    raan_deg: float
    argp_deg: float
    ma_deg: float

    @property
    def v_km_s(self) -> float:
        return math.sqrt(MU / self.a_km)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def load_catalogue(path: Path) -> dict[int, dict]:
    """Registration §1.2. The policy check is a stop rule, not a formality."""
    data = json.loads(path.read_text())
    if data.get("policy") != "commercial-civil-only":
        raise SystemExit("catalogue policy is not commercial-civil-only; refusing to run")
    return {o["norad"]: o for o in data["objects"] if o.get("norad")}


def open_archive_readonly(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        conn.execute("CREATE TABLE _t10bc_write_probe (x INTEGER)")
    except sqlite3.OperationalError:
        conn.execute("PRAGMA query_only=1")
        return conn
    raise SystemExit("archive opened writable; refusing to run")


def element_states(conn: sqlite3.Connection, norad: int) -> list[State]:
    rows = conn.execute(
        "SELECT epoch_ms, mean_motion_q, eccentricity_q, inclination_q, raan_q, "
        "arg_perigee_q, mean_anomaly_q FROM element_set WHERE norad=? ORDER BY epoch_ms",
        (norad,)).fetchall()
    out: list[State] = []
    for epoch_ms, mm_q, ec_q, in_q, ra_q, ap_q, ma_q in rows:
        mm = mm_q / 1e8
        if mm <= 0:
            continue
        out.append(State(epoch_ms, semi_major_axis_km(mm), ec_q / 1e8, in_q / 1e4,
                         ra_q / 1e4, ap_q / 1e4, ma_q / 1e4))
    return out


def load_events(path: Path) -> dict[int, dict]:
    out: dict[int, dict] = {}
    with gzip.open(path, "rt") as fh:
        for line in fh:
            rec = json.loads(line)
            out[rec["norad"]] = rec
    return out


def parse_iso_ms(text: str) -> int:
    return int(dt.datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp() * 1000)


def state_at(states: list[State], epochs: list[int], target_ms: int,
             tolerance_ms: int = 1500) -> State | None:
    """The element set the detector used as an interval boundary.

    Event timestamps are second-truncated and the archive holds milliseconds,
    so the nearest row inside the tolerance is the detector's own boundary row
    -- the same rule and the same tolerance T10a used.
    """
    from bisect import bisect_left
    k = bisect_left(epochs, target_ms)
    best, gap = None, None
    for j in (k - 1, k, k + 1):
        if 0 <= j < len(states):
            d = abs(states[j].epoch_ms - target_ms)
            if gap is None or d < gap:
                best, gap = states[j], d
    if best is None or gap > tolerance_ms:
        return None
    return best


def is_geo(s: State) -> bool:
    """Screen N1 -- the production detector's own GEO test, reused verbatim."""
    return abs(s.a_km - GEO_SEMI_MAJOR_AXIS_KM) <= GEO_BAND_KM and s.e < 0.01


def bus_family(bus: str | None) -> str | None:
    """T10a's implemented normalisation: upper-case, truncate after the first
    run of digits (`BSS-702SP -> BSS-702`, `SSL-1300 -> SSL-1300`). Adopted
    explicitly here so there is nothing to discover later."""
    if not bus:
        return None
    text = bus.upper().strip()
    seen_digit = False
    out = []
    for ch in text:
        if ch.isdigit():
            seen_digit = True
            out.append(ch)
        elif seen_digit:
            break
        else:
            out.append(ch)
    return "".join(out).strip() or text


# ===========================================================================
# Statistics
# ===========================================================================

def quantiles(values: list[float]) -> dict:
    if not values:
        return {}
    s = sorted(values)

    def q(p: float) -> float:
        if len(s) == 1:
            return s[0]
        idx = p * (len(s) - 1)
        lo = int(math.floor(idx))
        hi = min(lo + 1, len(s) - 1)
        return s[lo] + (s[hi] - s[lo]) * (idx - lo)

    return {"n": len(s), "min": s[0], "p25": q(0.25), "median": q(0.5),
            "p75": q(0.75), "p90": q(0.9), "max": s[-1],
            "mean": sum(s) / len(s)}


def percentile(values: list[float], p: float) -> float:
    if not values:
        return float("nan")
    s = sorted(values)
    if len(s) == 1:
        return s[0]
    idx = (p / 100.0) * (len(s) - 1)
    lo = int(math.floor(idx))
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (idx - lo)


def mad_sigma(values: list[float]) -> float:
    """Robust 1-sigma. MAD rather than a standard deviation for the reason
    `pipeline/orbit_history._mad_sigma` gives: one manoeuvre in the sample
    would inflate a standard deviation enough to hide itself."""
    if len(values) < 3:
        return float("nan")
    centre = statistics.median(values)
    return 1.4826 * statistics.median([abs(v - centre) for v in values])


def bootstrap_median_by_group(values_by_group: dict, seed: int = SEED,
                              draws: int = BOOTSTRAP_DRAWS) -> dict:
    """Median with a 95% percentile interval, resampling GROUPS (objects) with
    replacement -- registration §2.7, because events on one satellite are not
    independent draws."""
    groups = [v for v in values_by_group.values() if v]
    flat = [x for v in groups for x in v]
    if not flat:
        return {}
    rng = random.Random(seed)
    meds = []
    n = len(groups)
    for _ in range(draws):
        sample = []
        for _ in range(n):
            sample.extend(groups[rng.randrange(n)])
        if sample:
            meds.append(statistics.median(sample))
    meds.sort()
    return {"median": statistics.median(flat),
            "ci95": [meds[int(0.025 * (len(meds) - 1))],
                     meds[int(0.975 * (len(meds) - 1))]],
            "nGroups": n, "nValues": len(flat)}


def theil_sen(xs: list[float], ys: list[float]) -> float:
    slopes = []
    for i in range(len(xs)):
        for j in range(i + 1, len(xs)):
            dx = xs[j] - xs[i]
            if dx != 0.0:
                slopes.append((ys[j] - ys[i]) / dx)
    if not slopes:
        return float("nan")
    return statistics.median(slopes)


def theil_sen_bootstrap(xs: list[float], ys: list[float], groups: list,
                        seed: int = SEED, draws: int = 2000) -> dict:
    """Theil-Sen slope with a group-resampled 95% interval."""
    if len(xs) < 3:
        return {"slope": float("nan"), "ci95": [float("nan"), float("nan")], "n": len(xs)}
    base = theil_sen(xs, ys)
    by_group: dict = {}
    for x, y, g in zip(xs, ys, groups):
        by_group.setdefault(g, []).append((x, y))
    keys = list(by_group)
    rng = random.Random(seed)
    out = []
    for _ in range(draws):
        sx, sy = [], []
        for _ in range(len(keys)):
            for x, y in by_group[keys[rng.randrange(len(keys))]]:
                sx.append(x)
                sy.append(y)
        s = theil_sen(sx, sy)
        if s == s:
            out.append(s)
    out.sort()
    if not out:
        return {"slope": base, "ci95": [float("nan"), float("nan")], "n": len(xs)}
    return {"slope": base,
            "ci95": [out[int(0.025 * (len(out) - 1))], out[int(0.975 * (len(out) - 1))]],
            "n": len(xs), "nGroups": len(keys)}


# ===========================================================================
# T10b -- the measurement
# ===========================================================================

@dataclass
class NsEvent:
    norad: int
    name: str
    bus: str | None
    family: str | None
    start_ms: int
    end_ms: int
    signature: str
    span_days: float
    inc_before: float
    inc_after: float
    raan_before: float
    raan_after: float
    a_before: float
    a_after: float
    e_before: float
    e_after: float
    inc_pred: float = 0.0
    raan_pred: float = 0.0
    di_net: float = 0.0
    theta_net: float = 0.0
    di_raw: float = 0.0
    theta_raw: float = 0.0
    natural_pole_deg: float = 0.0
    observed_pole_deg: float = 0.0
    natural_fraction: float = 0.0
    dv_ideal: float = 0.0
    dv_min: float = 0.0
    dv_shipped: float = 0.0
    radial_bound_mps: float = 0.0
    eta: float = float("nan")
    eta_shipped: float = float("nan")
    eta_raw: float = float("nan")
    u_eff: float | None = None
    u_node: float | None = None
    sigma_eta: float = float("nan")
    inc_pred_j2: float = 0.0
    di_net_j2: float = 0.0
    theta_net_j2: float = 0.0
    eta_j2: float = float("nan")
    flags: list = field(default_factory=list)
    flags_ex_span: list = field(default_factory=list)

    @property
    def informative(self) -> bool:
        return not self.flags


def measure_ns_event(ev: dict, before: State, after: State, cat: dict,
                     precession_period_yr: float = LAPLACE_PRECESSION_PERIOD_YR) -> NsEvent:
    """One north-south event, measured. Registration §2.4, §2.5."""
    span_days = (after.epoch_ms - before.epoch_ms) / DAY_MS
    inc_pred, raan_pred, p_pred = propagate_natural(
        before.inc_deg, before.raan_deg, before.a_km, before.e, span_days,
        precession_period_yr)
    p_before = pole_vector(before.inc_deg, before.raan_deg)
    p_after = pole_vector(after.inc_deg, after.raan_deg)

    theta_net = plane_rotation_deg(inc_pred, after.inc_deg, after.raan_deg - raan_pred)
    theta_raw = plane_rotation_deg(before.inc_deg, after.inc_deg,
                                   after.raan_deg - before.raan_deg)
    di_net = after.inc_deg - inc_pred
    di_raw = after.inc_deg - before.inc_deg

    # The registration AS WRITTEN -- eq. (9) in its unstated prograde sense plus
    # eq. (10) -- kept as a published companion so the size of both defects is
    # measured rather than argued.
    inc_j2, raan_j2, _ = propagate_natural(
        before.inc_deg, before.raan_deg, before.a_km, before.e, span_days,
        precession_period_yr, include_j2=True, sense=REGISTERED_SENSE)
    theta_j2 = plane_rotation_deg(inc_j2, after.inc_deg, after.raan_deg - raan_j2)
    di_j2 = after.inc_deg - inc_j2

    dv_ideal = dv_ideal_node_mps(before.v_km_s, after.v_km_s, di_net)
    dv_min = dv_min_combined_mps(before.v_km_s, after.v_km_s, theta_net)
    dv_min_raw = dv_min_combined_mps(before.v_km_s, after.v_km_s, theta_raw)
    dv_ideal_raw = dv_ideal_node_mps(before.v_km_s, after.v_km_s, di_raw)
    shipped = float(ev["deltaV"]["totalMetresPerSecond"])

    u = argument_of_latitude(inc_pred, after.inc_deg, theta_net)
    bus = cat.get("bus")
    out = NsEvent(
        norad=cat["norad"], name=cat.get("name") or "", bus=bus, family=bus_family(bus),
        start_ms=parse_iso_ms(ev["startAt"]), end_ms=parse_iso_ms(ev["endAt"]),
        signature=ev["signature"], span_days=span_days,
        inc_before=before.inc_deg, inc_after=after.inc_deg,
        raan_before=before.raan_deg, raan_after=after.raan_deg,
        a_before=before.a_km, a_after=after.a_km, e_before=before.e, e_after=after.e,
        inc_pred=inc_pred, raan_pred=raan_pred,
        di_net=di_net, theta_net=theta_net, di_raw=di_raw, theta_raw=theta_raw,
        natural_pole_deg=pole_angle_deg(p_before, p_pred),
        observed_pole_deg=pole_angle_deg(p_before, p_after),
        dv_ideal=dv_ideal, dv_min=dv_min, dv_shipped=shipped,
        radial_bound_mps=1000.0 * max(before.e, after.e) * before.v_km_s,
        u_eff=u, u_node=node_offset_deg(u) if u is not None else None,
        inc_pred_j2=inc_j2, di_net_j2=di_j2, theta_net_j2=theta_j2,
    )
    out.natural_fraction = (out.natural_pole_deg / out.observed_pole_deg
                            if out.observed_pole_deg > 0 else float("nan"))
    out.eta = dv_ideal / dv_min if dv_min > 0 else float("nan")
    out.eta_shipped = dv_ideal / shipped if shipped > 0 else float("nan")
    out.eta_raw = dv_ideal_raw / dv_min_raw if dv_min_raw > 0 else float("nan")
    dv_min_j2 = dv_min_combined_mps(before.v_km_s, after.v_km_s, theta_j2)
    out.eta_j2 = (dv_ideal_node_mps(before.v_km_s, after.v_km_s, di_j2) / dv_min_j2
                  if dv_min_j2 > 0 else float("nan"))
    return out


def measure_sigma_pole(states: list[State], busy_ms: list[tuple[int, int]],
                       max_span_days: float = SPAN_PRIMARY_DAYS) -> list[tuple]:
    """Registration §3.1: the quiet arcs that MEASURE the pole floor.

    For every consecutive GEO element-set pair of this object that lies wholly
    outside every detected interval and is separated by at most `max_span_days`,
    returns

        (residual deg, span days, observed displacement, predicted displacement,
         residual displacement)

    The RESIDUAL magnitude is the pole-noise floor of §3.1. The OBSERVED
    displacement is what the drift-direction control of §3.3 tests, because §3.3
    asks where the observed pole motion is heading -- not where what is left of
    it after the model has been removed is heading.
    """
    out = []
    busy = sorted(busy_ms)
    for a, b in zip(states, states[1:]):
        if not (is_geo(a) and is_geo(b)):
            continue
        span = (b.epoch_ms - a.epoch_ms) / DAY_MS
        if not (0.0 < span <= max_span_days):
            continue
        if any(not (b.epoch_ms <= lo or a.epoch_ms >= hi) for lo, hi in busy):
            continue
        _, _, p_pred = propagate_natural(a.inc_deg, a.raan_deg, a.a_km, a.e, span)
        p_before = pole_vector(a.inc_deg, a.raan_deg)
        p_after = pole_vector(b.inc_deg, b.raan_deg)
        observed = tuple(x - y for x, y in zip(p_after, p_before))
        predicted = tuple(x - y for x, y in zip(p_pred, p_before))
        residual = tuple(x - y for x, y in zip(p_after, p_pred))
        out.append((pole_angle_deg(p_pred, p_after), span, observed, predicted,
                    residual, a.inc_deg))
    return out


def _heading_raan(vec) -> float:
    """The RAAN a pole displacement `(dx, dy)` is heading toward.

    From `p = sin(i) (sin RAAN, -cos RAAN, .)`, a purely radial displacement is
    proportional to `(sin RAAN, -cos RAAN)`, so the heading is `atan2(dx, -dy)`.
    """
    return math.degrees(math.atan2(vec[0], -vec[1])) % 360.0


def drift_direction(arcs: list[tuple]) -> dict:
    """Registration §3.3: where the OBSERVED quiet-arc pole motion is heading.

    The model predicts 270 deg (`P_L x z` points along `-x`), and a measurement
    more than 20 deg away fails the control and withdraws the T10b population
    claim.

    Two unregistered diagnostics travel with it, labelled as unregistered: the
    heading of the RESIDUAL after the model is removed -- which says which way
    the model errs -- and the projected magnitude ratio
    `(observed . predicted) / |predicted|^2`, whose pooled value is 1 if the
    modelled rate is right.
    """
    if not arcs:
        return {}
    obs = [a[2] for a in arcs]
    pred = [a[3] for a in arcs]
    res = [a[4] for a in arcs]

    def pooled(vs) -> dict:
        sx = sum(v[0] for v in vs)
        sy = sum(v[1] for v in vs)
        heading = math.degrees(math.atan2(sx, -sy)) % 360.0
        per = [_heading_raan(v) for v in vs if math.hypot(v[0], v[1]) > 0]
        if per:
            cx = sum(math.cos(math.radians(t)) for t in per) / len(per)
            cy = sum(math.sin(math.radians(t)) for t in per) / len(per)
            conc = math.hypot(cx, cy)
        else:
            conc = float("nan")
        return {"pooledHeadingRaanDeg": heading, "concentration": conc}

    def ratio(o_list, p_list) -> float:
        num = sum(sum(a * b for a, b in zip(v, w)) for v, w in zip(o_list, p_list))
        den = sum(sum(b * b for b in w) for w in p_list)
        return (num / den) if den > 0 else float("nan")

    o = pooled(obs)
    sep = abs((o["pooledHeadingRaanDeg"] - PREDICTED_DRIFT_RAAN_DEG + 180.0) % 360.0 - 180.0)

    # UNREGISTERED variant, added after the registered control failed: restrict
    # to arcs on objects that are NOT being north-south kept at the time. The
    # registered control was posed on a population every member of which is
    # actively cancelling the drift it is trying to see, so its arcs contain the
    # corrections as well as the drift. Above ~0.5 deg of inclination an object
    # has stopped north-south keeping (inclined-orbit operation, or retirement)
    # and its pole moves freely. This is reported as unregistered and changes no
    # verdict; fixing a registered check after seeing what it returns is exactly
    # what registration exists to prevent.
    unkept = {}
    for floor in (0.5, 1.0, 2.0):
        sel = [a for a in arcs if a[5] >= floor]
        if len(sel) < 100:
            continue
        po = pooled([a[2] for a in sel])
        s2 = abs((po["pooledHeadingRaanDeg"] - PREDICTED_DRIFT_RAAN_DEG + 180.0) % 360.0 - 180.0)
        unkept[f"inclinationAtLeast{floor:g}deg"] = {
            "n": len(sel), "pooledHeadingRaanDeg": po["pooledHeadingRaanDeg"],
            "separationDeg": s2, "concentration": po["concentration"],
            "projectedRateRatio": ratio([a[2] for a in sel], [a[3] for a in sel]),
            "wouldPass": s2 <= DRIFT_DIRECTION_TOLERANCE_DEG}

    return {"meanRaanDeg": o["pooledHeadingRaanDeg"],
            "predictedRaanDeg": PREDICTED_DRIFT_RAAN_DEG,
            "separationDeg": sep, "concentration": o["concentration"],
            "n": len(arcs),
            "pass": sep <= DRIFT_DIRECTION_TOLERANCE_DEG,
            "unregisteredResidualHeading": pooled(res),
            "unregisteredProjectedRateRatio": ratio(obs, pred),
            "unregisteredUnkeptSubsets": unkept}


# ===========================================================================
# T10c -- the measurement
# ===========================================================================

@dataclass
class Segment:
    norad: int
    name: str
    bus: str | None
    start_ms: int
    end_ms: int
    n_samples: int
    observed_years: float
    slot_deg: float
    accel_deg_day2: float
    accel_signed_deg_day2: float
    deadband_deg: float
    deadband_p1p99_deg: float
    deadband_minmax_deg: float
    deadband_from_drift_deg: float
    drift_amp_deg_day: float
    events: int
    detected_dv_mps: float
    detected_dv_per_year: float
    theory_dv_per_year: float
    theory_dv_per_cycle: float
    theory_cycle_days: float
    theory_manoeuvres_per_year: float
    recall_ratio: float
    measured_accel_deg_day2: float
    measured_accel_samples: int
    short_window_accel_deg_day2: float = float("nan")
    short_window_samples: int = 0
    pair_accel_deg_day2: float = float("nan")
    pair_samples: int = 0
    quiet_arc_days_median: float = float("nan")
    shipped_over_min: list = field(default_factory=list)
    flags: list = field(default_factory=list)


def station_segments_on_epochs(epochs: list[int], lam: list[float]) -> list[tuple[int, int]]:
    """Maximal stretches holding one slot: `|lambda - median| <= 0.3 deg`
    throughout, span `>= 30 d`, a gap over 10 d breaking the run.

    The registered T8a rule (`STATION_HALF_WIDTH_DEG`, `STATION_MIN_DAYS`),
    evaluated on the object's own element epochs rather than on a daily grid,
    and grown one sample at a time against a sorted window so the median
    condition is checked exactly at every step rather than by trimming a
    too-long candidate -- the same construction `proximity_geo.station_segments`
    uses.
    """
    segs: list[tuple[int, int]] = []
    n = len(lam)
    i = 0
    while i < n:
        window = [lam[i]]
        j = i
        while j + 1 < n:
            if (epochs[j + 1] - epochs[j]) / DAY_MS > SEGMENT_GAP_BREAK_DAYS:
                break
            v = lam[j + 1]
            insort(window, v)
            m = len(window)
            med = window[m // 2] if m % 2 else 0.5 * (window[m // 2 - 1] + window[m // 2])
            if window[-1] - med > STATION_HALF_WIDTH_DEG or med - window[0] > STATION_HALF_WIDTH_DEG:
                window.remove(v)
                break
            j += 1
        if (epochs[j] - epochs[i]) / DAY_MS >= STATION_MIN_DAYS:
            segs.append((i, j))
            i = j + 1
        else:
            i += 1
    return segs


def free_drift_acceleration(epochs: list[int], rates: list[float],
                            busy: list[tuple[int, int]]) -> list[float]:
    """Registration §4.6: `d(lambda_dot)/dt` on quiet arcs, by least squares.

    This is a DIRECT measurement of the triaxial acceleration from this archive,
    independent of any manoeuvre pricing, and it is the control that can fail
    T10c outright: if the free drift between burns does not accelerate the way
    eq. (14) says it does, nothing built on eq. (19) may be claimed.
    """
    from bisect import bisect_left, bisect_right
    out: list[float] = []
    merged: list[list[int]] = []
    for lo, hi in sorted(busy):
        if merged and lo <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], hi)
        else:
            merged.append([lo, hi])
    bounds = [epochs[0]] + [t for lo, hi in merged for t in (lo, hi)] + [epochs[-1]]
    for k in range(0, len(bounds) - 1, 2):
        lo, hi = bounds[k], bounds[k + 1]
        i0 = bisect_left(epochs, lo)
        i1 = bisect_right(epochs, hi)
        if i1 - i0 < FREE_DRIFT_MIN_SAMPLES:
            continue
        if (epochs[i1 - 1] - epochs[i0]) / DAY_MS < FREE_DRIFT_MIN_SPAN_DAYS:
            continue
        t = np.array([(e - epochs[i0]) / DAY_MS for e in epochs[i0:i1]])
        y = np.array(rates[i0:i1])
        out.append(float(np.polyfit(t, y, 1)[0]))
    return out


UNREGISTERED_SHORT_WINDOW_DAYS = 10.0


def free_drift_acceleration_short_windows(epochs: list[int], rates: list[float],
                                          busy: list[tuple[int, int]],
                                          window_days: float = UNREGISTERED_SHORT_WINDOW_DAYS
                                          ) -> list[float]:
    """UNREGISTERED diagnostic, added after the registered control of §4.6 failed.

    The registered control fits one straight line to the drift rate across the
    whole arc between consecutive DETECTED east-west events. With a detected
    event rate of a few per year and a theoretical cycle of a few weeks, such an
    arc contains many undetected sawtooth cycles, and a single line through them
    averages the triaxial acceleration to zero. That is not evidence the
    acceleration is absent; it is evidence the arc is longer than the cycle.

    This diagnostic fits the same slope on SLIDING WINDOWS no longer than
    `window_days`, which is shorter than the shortest theoretical cycle in this
    population, and returns the per-window signed slopes. It is reported beside
    the registered control, is labelled unregistered everywhere it appears, and
    changes no verdict.
    """
    from bisect import bisect_left, bisect_right
    out: list[float] = []
    merged: list[list[int]] = []
    for lo, hi in sorted(busy):
        if merged and lo <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], hi)
        else:
            merged.append([lo, hi])
    bounds = [epochs[0]] + [t for lo, hi in merged for t in (lo, hi)] + [epochs[-1]]
    span_ms = window_days * DAY_MS
    for k in range(0, len(bounds) - 1, 2):
        lo, hi = bounds[k], bounds[k + 1]
        i0 = bisect_left(epochs, lo)
        i1 = bisect_right(epochs, hi)
        start = i0
        while start < i1:
            stop = min(i1, bisect_right(epochs, epochs[start] + span_ms))
            if stop - start >= FREE_DRIFT_MIN_SAMPLES and \
                    (epochs[stop - 1] - epochs[start]) / DAY_MS >= FREE_DRIFT_MIN_SPAN_DAYS:
                t = np.array([(e - epochs[start]) / DAY_MS for e in epochs[start:stop]])
                y = np.array(rates[start:stop])
                out.append(float(np.polyfit(t, y, 1)[0]))
            if stop <= start:
                break
            start = stop
    return out


CALIBRATION_MIN_INC_DEG = 3.0
CALIBRATION_MIN_YEARS = 3.0


def laplace_calibration(states: list[State]) -> dict | None:
    """Measure the Laplace circuit directly on ONE object that is no longer kept.

    An object that has stopped north-south keeping moves along a small circle
    about the Laplace pole. Three quantities fall straight out of its own
    element history and none of them is fitted:

    * the **tilt** of the Laplace pole, as the angular distance from it to the
      object's pole, which the model puts at 7.4 deg;
    * the **signed circuit rate** about it, whose SIGN is the thing registration
      eq. (9) left unstated and got wrong, and whose magnitude is
      `360 / T_prec`;
    * the **pole speed** the two imply at zero inclination,
      `|rate| sin(tilt)`, which is the 0.75-0.95 deg/yr figure the registration
      carries from Soop.

    Objects are admitted only above `CALIBRATION_MIN_INC_DEG`, where a GEO
    satellite is demonstrably not being north-south kept, and only with at
    least `CALIBRATION_MIN_YEARS` of such history. This is an UNREGISTERED
    measurement, added after the registered §3.3 control fired.
    """
    rows = [s for s in states
            if abs(s.a_km - GEO_SEMI_MAJOR_AXIS_KM) < 600.0 and s.e < 0.02
            and s.inc_deg > CALIBRATION_MIN_INC_DEG]
    if len(rows) < 50:
        return None
    a, b = rows[0], rows[-1]
    years = (b.epoch_ms - a.epoch_ms) / DAY_MS / DAYS_PER_YEAR
    if years < CALIBRATION_MIN_YEARS:
        return None
    lap = laplace_pole()

    def about(p):
        d = sum(x * y for x, y in zip(p, lap))
        v = tuple(x - d * y for x, y in zip(p, lap))
        n = math.sqrt(sum(x * x for x in v))
        if n == 0.0:
            return None, None
        return tuple(x / n for x in v), math.degrees(math.acos(max(-1.0, min(1.0, d))))

    # Accumulate the signed circuit angle over consecutive samples rather than
    # taking it between the two endpoints: a history longer than half a circuit
    # would otherwise wrap through atan2 and return the wrong sign. Subsampled
    # because consecutive element sets are hours apart and the circuit is
    # decades long.
    step = max(1, len(rows) // 400)
    sampled = rows[::step] + [b]
    phi = 0.0
    tilts = []
    prev_u = None
    for row in sampled:
        u, d = about(pole_vector(row.inc_deg, row.raan_deg))
        if u is None:
            continue
        tilts.append(d)
        if prev_u is not None:
            cross = (prev_u[1] * u[2] - prev_u[2] * u[1],
                     prev_u[2] * u[0] - prev_u[0] * u[2],
                     prev_u[0] * u[1] - prev_u[1] * u[0])
            phi += math.degrees(math.atan2(sum(c * l for c, l in zip(cross, lap)),
                                           sum(x * y for x, y in zip(prev_u, u))))
        prev_u = u
    if not tilts:
        return None
    rate = phi / years
    tilt = statistics.median(tilts)
    return {"years": years, "incStartDeg": a.inc_deg, "incEndDeg": b.inc_deg,
            "circuitDeg": phi, "tiltDeg": tilt, "circuitRateDegPerYear": rate,
            "periodYears": (360.0 / abs(rate)) if rate else float("nan"),
            "poleSpeedDegPerYear": abs(rate) * math.sin(math.radians(tilt)),
            "samples": len(rows)}


PAIR_MIN_DAYS = 0.05
PAIR_MAX_DAYS = 2.0


def free_drift_acceleration_pair_median(epochs: list[int], rates: list[float],
                                        busy: list[tuple[int, int]]) -> list[float]:
    """UNREGISTERED diagnostic: the adjacent-pair slope `d(lambda_dot)/dt`.

    A station-kept object's drift rate is a SAWTOOTH: it climbs at the triaxial
    acceleration and is stepped back by each burn. Almost every burn in this
    population is below the detector's threshold, so a straight line fitted
    across any arc longer than a cycle averages the ramp against the steps and
    returns nothing -- which is what the registered control of §4.6 measures.

    The slope between ADJACENT element sets, by contrast, lies inside one ramp
    unless the pair happens to straddle a step, so the MEDIAN of those slopes
    rejects the steps as outliers and measures the ramp. That is the whole
    difference between this estimator and the registered one, and it is a
    difference in robustness, not in physics.

    Pairs separated by less than `PAIR_MIN_DAYS` are dropped because the element
    noise divided by a tiny interval is unbounded; pairs over `PAIR_MAX_DAYS`
    are dropped because they begin to straddle steps.
    """
    merged: list[list[int]] = []
    for lo, hi in sorted(busy):
        if merged and lo <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], hi)
        else:
            merged.append([lo, hi])
    out: list[float] = []
    for k in range(len(epochs) - 1):
        a, b = epochs[k], epochs[k + 1]
        if any(not (b <= lo or a >= hi) for lo, hi in merged):
            continue
        dt = (b - a) / DAY_MS
        if not (PAIR_MIN_DAYS <= dt <= PAIR_MAX_DAYS):
            continue
        out.append((rates[k + 1] - rates[k]) / dt)
    return out


# ===========================================================================
# The run
# ===========================================================================

def runtime_proofs() -> dict:
    """Registration §6.3 D3: the closed forms are reproduced BEFORE data is read.

    Not a substitute for the test suite -- a duplicate of the four that decide
    whether the arithmetic in this process is the arithmetic that was
    registered.
    """
    proofs = {}

    # Test 1 -- eq. (3) at u = 0 is i' = i + theta
    worst = 0.0
    for inc in (0.0, 0.03, 0.5, 5.0, 28.5):
        for th in (0.001, 0.05, 1.0, 10.0):
            worst = max(worst, abs(inclination_after(inc, th, 0.0) - (inc + th)))
    proofs["eq3NodeIdentityWorstDeg"] = worst
    assert worst < 1e-9, worst

    # Test 3 -- the law of cosines against T10a's published GTO->GEO apogee kick
    a_gto = (6378.135 + 185.0 + 6378.135 + 35786.0) / 2.0
    r_apo = 6378.135 + 35786.0
    v_gto_apo = math.sqrt(MU * (2.0 / r_apo - 1.0 / a_gto))
    v_geo = math.sqrt(MU / r_apo)
    kick = dv_min_combined_mps(v_gto_apo, v_geo, 28.5)
    proofs["t10aApogeeKickMps"] = kick
    proofs["t10aApogeeKickPublished"] = 1837.4396175374018
    assert abs(kick - 1837.4396175374018) / 1837.4396175374018 < 1e-9, kick

    # Test 7 -- the natural drift rate and its direction
    inc1, raan1, _ = propagate_natural(0.0, 0.0, A_GEO_KM, 0.0, DAYS_PER_YEAR)
    proofs["naturalDriftDegPerYearAtZeroInc"] = inc1
    assert abs(inc1 - 0.8748) < 5e-4, inc1
    _, raan_d, _ = propagate_natural(0.0, 0.0, A_GEO_KM, 0.0, 1.0)
    proofs["naturalDriftRaanDegOverOneDay"] = raan_d
    proofs["naturalDriftSense"] = "retrograde about the Laplace pole (measured)"
    assert abs((raan_d - 90.0 + 180.0) % 360.0 - 180.0) < 0.1, raan_d
    _, raan_reg, _ = propagate_natural(0.0, 0.0, A_GEO_KM, 0.0, 1.0,
                                       sense=REGISTERED_SENSE)
    proofs["registeredAsWrittenDriftRaanDegOverOneDay"] = raan_reg
    proofs["naturalDriftRaanDegOverOneYear"] = raan1
    # the registered eq. (9)+(10) sum, kept as a measured companion
    inc_j2, _, _ = propagate_natural(0.0, 0.0, A_GEO_KM, 0.0, DAYS_PER_YEAR, include_j2=True)
    proofs["registeredWithJ2DriftDegPerYearAtZeroInc"] = inc_j2
    proofs["j2DoubleCountNote"] = (
        "Registration eq. (10) double-counts the oblateness that eq. (9)'s 7.4 deg "
        "Laplace tilt already encodes; the primary path uses eq. (9) alone and every "
        "event publishes the registered sum beside it.")

    # Test 12 -- the T10c derivation chain, and the deadband cancellation
    proofs["aMaxDegPerDay2T3"] = triaxial_acceleration_max_deg_day2_t3()
    proofs["aMaxDegPerDay2T8a"] = A_MAX_DEG_DAY2
    assert abs(proofs["aMaxDegPerDay2T3"] - A_MAX_DEG_DAY2) / A_MAX_DEG_DAY2 < 1e-3
    proofs["cycleDaysAt0p0208Deg"] = cycle_period_days(0.0208, A_MAX_DEG_DAY2)
    proofs["dvPerCycleMpsAt0p0208Deg"] = dv_per_cycle_mps(0.0208, A_MAX_DEG_DAY2)
    proofs["dvPerYearMpsAtAMax"] = dv_per_year_mps(A_MAX_DEG_DAY2)
    proofs["manoeuvresPerYearAt0p0208Deg"] = manoeuvres_per_year(0.0208, A_MAX_DEG_DAY2)
    # The cancellation itself, composed from (18) and (16) across four decades
    # of deadband: DV_cycle x manoeuvres-per-year must be constant.
    composed = [dv_per_cycle_mps(r, A_MAX_DEG_DAY2) * manoeuvres_per_year(r, A_MAX_DEG_DAY2)
                for r in (1e-4, 1e-3, 1e-2, 1e-1, 1.0)]
    direct = dv_per_year_mps(A_MAX_DEG_DAY2)
    residual = max(abs(c - direct) / direct for c in composed)
    proofs["deadbandCancellationRelativeResidual"] = residual
    proofs["deadbandCancellationProbedHalfWidthsDeg"] = [1e-4, 1e-3, 1e-2, 1e-1, 1.0]
    assert residual < 1e-12, residual
    proofs["northSouthBudgetMpsPerYear"] = north_south_budget_mps_per_year()
    assert abs(proofs["cycleDaysAt0p0208Deg"] - 14.0) < 0.02
    assert abs(proofs["dvPerYearMpsAtAMax"] - 1.764) < 0.01
    return proofs


def mean_motion_rev_day(a_km: float) -> float:
    return 86400.0 / (2.0 * math.pi * math.sqrt(a_km ** 3 / MU))


def run(args) -> int:
    t_wall = time.time()
    t_cpu = resource.getrusage(resource.RUSAGE_SELF).ru_utime

    proofs = runtime_proofs()

    hashes = {"catalogue": sha256_file(args.catalogue),
              "events": sha256_file(args.events)}
    if not args.skip_archive_hash:
        hashes["archive"] = sha256_file(args.archive)
    for key, want in EXPECTED_HASHES.items():
        got = hashes.get(key)
        if got is not None and got != want:
            raise SystemExit(
                f"input hash mismatch for {key}: {got} != {want} (registration §6.3 S1)")

    catalogue = load_catalogue(args.catalogue)
    events = load_events(args.events)
    conn = open_archive_readonly(args.archive)

    census = {"catalogueObjects": len(catalogue), "catalogueObjectsWithEvents": 0,
              "objectsWithArchiveHistory": 0, "nsEventsSeen": 0, "ewEventsSeen": 0,
              "geoObjectsForSegments": 0}
    ns_events: list[NsEvent] = []
    ns_inputs: list[tuple] = []
    dropped: list[dict] = []
    quiet_residuals: list[float] = []
    quiet_vectors: list[tuple] = []
    quiet_spans: list[float] = []
    segments: list[Segment] = []
    calibrations: list[dict] = []

    for norad, cat in sorted(catalogue.items()):
        rec = events.get(norad)
        if rec is None:
            continue
        census["catalogueObjectsWithEvents"] += 1
        states = element_states(conn, norad)
        if len(states) < 3:
            continue
        census["objectsWithArchiveHistory"] += 1
        epochs = [s.epoch_ms for s in states]
        busy = [(parse_iso_ms(e["startAt"]), parse_iso_ms(e["endAt"])) for e in rec["events"]]
        launch = cat.get("launch_date")
        launch_ms = parse_iso_ms(launch + "T00:00:00Z") if launch else None

        # ---------------- T10b ----------------------------------------
        for ev in rec["events"]:
            if ev["signature"] not in NS_SIGNATURES:
                continue
            census["nsEventsSeen"] += 1
            start_ms = parse_iso_ms(ev["startAt"])
            end_ms = parse_iso_ms(ev["endAt"])
            flags: list[str] = []
            if launch_ms is None:
                flags.append("N3-no-launch-date")
            elif start_ms < launch_ms:
                flags.append("N4-starts-before-launch")
            elif (start_ms - launch_ms) / DAY_MS <= RAISING_WINDOW_DAYS:
                flags.append("N3-inside-raising-window")
            if float(ev["deltaV"]["totalMetresPerSecond"]) > SINGLE_EVENT_CEILING_MPS:
                flags.append("N4-above-odometer-ceiling")
            before = state_at(states, epochs, start_ms)
            after = state_at(states, epochs, end_ms)
            if before is None or after is None:
                dropped.append({"norad": norad, "name": cat.get("name") or "",
                                "startAt": ev["startAt"], "endAt": ev["endAt"],
                                "signature": ev["signature"],
                                "flags": flags + ["N7-endpoint-missing"],
                                "informative": False})
                continue
            if not (is_geo(before) and is_geo(after)):
                flags.append("N1-not-geo")
            span = (after.epoch_ms - before.epoch_ms) / DAY_MS
            m = measure_ns_event(ev, before, after, cat)
            m.flags_ex_span = list(flags)
            if not (0.0 < span <= SPAN_PRIMARY_DAYS):
                flags.append("N5-span")
            if not (m.theta_net > 0 and abs(m.di_net) > 0 and m.dv_min > 0
                    and m.dv_ideal == m.dv_ideal and m.eta == m.eta):
                flags.append("N7-degenerate")
                m.flags_ex_span.append("N7-degenerate")
            m.flags = flags
            ns_events.append(m)
            ns_inputs.append((ev, before, after, cat))

        cal = laplace_calibration(states)
        if cal is not None:
            cal["norad"] = norad
            cal["name"] = cat.get("name") or ""
            calibrations.append(cal)

        # ------------- quiet arcs: the MEASURED pole floor --------------
        for arc in measure_sigma_pole(states, busy):
            quiet_residuals.append(arc[0])
            quiet_spans.append(arc[1])
            quiet_vectors.append(arc)

        # ---------------- T10c ----------------------------------------
        geo_idx = [k for k, s in enumerate(states)
                   if MM_MIN_REV_DAY <= mean_motion_rev_day(s.a_km) <= MM_MAX_REV_DAY
                   and s.e < ECC_MAX and s.inc_deg < INC_MAX_DEG]
        if len(geo_idx) < 30:
            continue
        census["geoObjectsForSegments"] += 1
        geo_states = [states[k] for k in geo_idx]
        g_epochs = [s.epoch_ms for s in geo_states]
        mm = np.array([mean_motion_rev_day(s.a_km) for s in geo_states])
        lam_wrapped = mean_longitude_deg(
            np.array([s.raan_deg for s in geo_states]),
            np.array([s.argp_deg for s in geo_states]),
            np.array([s.ma_deg for s in geo_states]),
            np.array(g_epochs, dtype=np.float64))
        rates = drift_rate_deg_per_day(mm)
        lam = [float(x) for x in unwrap_longitude(
            lam_wrapped, np.array(g_epochs, dtype=np.float64), rates)]
        rate_list = [float(x) for x in rates]
        ew_events = [e for e in rec["events"] if e["signature"] == "geo-east-west-keeping"]
        census["ewEventsSeen"] += len(ew_events)
        ew_ms = [(parse_iso_ms(e["startAt"]), parse_iso_ms(e["endAt"]), e) for e in ew_events]
        for i0, i1 in station_segments_on_epochs(g_epochs, lam):
            seg = build_segment(norad, cat, geo_states, g_epochs, lam, rate_list,
                                i0, i1, ew_ms)
            if seg is not None:
                segments.append(seg)

    conn.close()

    # ---- the measured pole-noise floor (registration §3.1) ---------------
    calibration = summarise_calibration(calibrations)
    sigma_pole = mad_sigma(quiet_residuals)
    sigma_pole_short = mad_sigma([r for r, s in zip(quiet_residuals, quiet_spans) if s <= 1.5])
    direction = drift_direction(quiet_vectors)

    # ---- N6, applied with the MEASURED floor -----------------------------
    screen_counts: dict = {}
    for row in dropped:
        for f in row["flags"]:
            screen_counts[f] = screen_counts.get(f, 0) + 1
    for m in ns_events:
        if not (m.theta_net >= NOISE_SIGMAS_THETA * sigma_pole):
            m.flags.append("N6-below-pole-noise")
            m.flags_ex_span.append("N6-below-pole-noise")
        if m.u_eff is not None and not (m.inc_pred >= NOISE_SIGMAS_INC * sigma_pole):
            m.u_eff = None
            m.u_node = None
        for f in m.flags:
            screen_counts[f] = screen_counts.get(f, 0) + 1

    primary = [m for m in ns_events if m.informative]

    # ---- R1: the drift-rate sensitivity, both edges of 0.75-0.95 deg/yr ---
    variants = [("low0.75", DRIFT_INTERVAL_DEG_PER_YR[0]),
                ("high0.95", DRIFT_INTERVAL_DEG_PER_YR[1])]
    measured_speed = (calibration.get("poleSpeedDegPerYear") or {}).get("median")
    if measured_speed:
        variants.append(("measuredUnregistered", measured_speed))
    r1 = {}
    for label, rate in variants:
        period = period_for_drift_rate(rate)
        etas = []
        for (ev, before, after, cat), base in zip(ns_inputs, ns_events):
            if not base.informative:
                continue
            alt = measure_ns_event(ev, before, after, cat, precession_period_yr=period)
            if alt.eta == alt.eta:
                etas.append(alt.eta)
        r1[label] = {"driftDegPerYear": rate, "precessionPeriodYr": period,
                     "medianEta": statistics.median(etas) if etas else None,
                     "n": len(etas)}

    # ---- R5: the span sensitivities --------------------------------------
    r5 = {}
    for days in SPAN_SENSITIVITIES_DAYS:
        subset = [m for m in ns_events
                  if not m.flags_ex_span and 0.0 < m.span_days <= days]
        r5[f"span{days:g}d"] = {
            "n": len(subset),
            "medianEta": statistics.median([m.eta for m in subset]) if subset else None,
            "medianNodeOffsetDeg": statistics.median(
                [m.u_node for m in subset if m.u_node is not None])
            if any(m.u_node is not None for m in subset) else None}

    ns_result = summarise_ns(primary, sigma_pole)
    ns_result["R1_driftRateSensitivity"] = r1
    if ns_result.get("etaBootstrap", {}).get("median"):
        base_med = ns_result["etaBootstrap"]["median"]
        shifts = [abs(v["medianEta"] - base_med) / base_med
                  for k, v in r1.items() if v["medianEta"] and k != "measuredUnregistered"]
        ns_result["R1_maxRelativeShift"] = max(shifts) if shifts else None
        ns_result["R1_driftModelSensitive"] = (
            bool(shifts) and max(shifts) > R1_MAX_RELATIVE_SHIFT)
    ns_result["R5_spanSensitivity"] = r5
    ns_result["driftDirectionControl"] = direction
    if not direction.get("pass", False):
        ns_result["acceptance"]["verdict"] = "NO POPULATION CLAIM (drift-direction control failed)"

    ew_result = summarise_ew(segments)

    receipt = {
        "schema": 1,
        "track": "T10b/T10c",
        "registration": REGISTRATION,
        "registrationCommit": REGISTRATION_COMMIT,
        "measuredAt": dt.datetime.now(dt.timezone.utc).isoformat(),
        "host": os.uname().nodename,
        "executionMode": "cpu",
        "gpuBrokerRequest": None,
        "gpuNote": "No GPU arm was built; the CPU figures below are the entire cost "
                   "of both studies and nothing is left to prove later.",
        "seeds": {"bootstrap": SEED, "monteCarlo": SEED,
                  "bootstrapDraws": BOOTSTRAP_DRAWS, "monteCarloDraws": MONTE_CARLO_DRAWS},
        "inputs": {"sha256": hashes,
                   "archiveHashVerified": not args.skip_archive_hash,
                   "events": str(args.events), "archive": str(args.archive),
                   "catalogue": str(args.catalogue)},
        "sourceSha256": sha256_file(Path(__file__).resolve()),
        "runtimeProofs": proofs,
        "census": census,
        "screenCounts": screen_counts,
        "poleNoiseFloor": {
            "sigmaPoleDeg": sigma_pole,
            "sigmaPoleDegShortArcsUnder1p5d": sigma_pole_short,
            "quietArcs": len(quiet_residuals),
            "medianResidualDeg": statistics.median(quiet_residuals) if quiet_residuals else None,
            "medianSpanDays": statistics.median(quiet_spans) if quiet_spans else None,
            "note": "MEASURED on quiet arcs. An upper bound on pole noise, not a sigma: "
                    "it contains fit noise, the unmodelled periodic lunisolar terms and "
                    "any sub-threshold burn (registration section 3.1).",
        },
        "driftDirectionControl": direction,
        "laplaceCalibrationUnregistered": calibration,
        "t10b": ns_result,
        "t10c": ew_result,
    }

    stem = args.out_prefix
    write_ns_jsonl(f"{stem}-ns.jsonl" if not stem.endswith("-20260922")
                   else stem.replace("-efficiency-20260922", "-ns-20260922") + ".jsonl",
                   ns_events, dropped, receipt)
    write_ew_jsonl(f"{stem}-ew.jsonl" if not stem.endswith("-20260922")
                   else stem.replace("-efficiency-20260922", "-ew-20260922") + ".jsonl",
                   segments, receipt)

    receipt["wallSeconds"] = time.time() - t_wall
    receipt["cpuSeconds"] = resource.getrusage(resource.RUSAGE_SELF).ru_utime - t_cpu
    receipt["maxRssKb"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    Path(f"{stem}-receipt.json").write_text(json.dumps(receipt, indent=1, default=float))
    print(json.dumps({"nsSeen": census["nsEventsSeen"], "nsPrimary": len(primary),
                      "segments": len(segments), "sigmaPoleDeg": sigma_pole,
                      "t10bVerdict": ns_result.get("acceptance", {}).get("verdict"),
                      "t10cVerdict": ew_result.get("acceptance", {}).get("verdict"),
                      "wallSeconds": receipt["wallSeconds"],
                      "cpuSeconds": receipt["cpuSeconds"]}, indent=1, default=float))
    return 0


def summarise_calibration(rows: list[dict]) -> dict:
    """Pool the per-object Laplace-circuit measurements of `laplace_calibration`."""
    if not rows:
        return {"n": 0}
    return {
        "n": len(rows),
        "tiltDeg": quantiles([r["tiltDeg"] for r in rows]),
        "circuitRateDegPerYear": quantiles([r["circuitRateDegPerYear"] for r in rows]),
        "periodYears": quantiles([r["periodYears"] for r in rows]),
        "poleSpeedDegPerYear": quantiles([r["poleSpeedDegPerYear"] for r in rows]),
        "modelTiltDeg": LAPLACE_TILT_DEG,
        "modelCircuitRateDegPerYear": LAPLACE_SENSE * 360.0 / LAPLACE_PRECESSION_PERIOD_YR,
        "modelPoleSpeedDegPerYear": (360.0 / LAPLACE_PRECESSION_PERIOD_YR)
        * math.sin(math.radians(LAPLACE_TILT_DEG)),
        "registeredIntervalDegPerYear": list(DRIFT_INTERVAL_DEG_PER_YR),
        "allRetrograde": all(r["circuitRateDegPerYear"] < 0 for r in rows),
        "perObject": sorted(rows, key=lambda r: r["norad"]),
        "note": "UNREGISTERED measurement on catalogue objects that have stopped "
                "north-south keeping. It is what fixed the sense of registration "
                "eq. (9) and it is the only direct calibration of the natural-motion "
                "model this programme has.",
    }


def build_segment(norad, cat, geo_states, g_epochs, lam, rates, i0, i1, ew_ms):
    """One station segment, measured. Registration §4.5, §4.6."""
    window = lam[i0:i1 + 1]
    epochs = g_epochs[i0:i1 + 1]
    seg_rates = rates[i0:i1 + 1]
    seg_states = geo_states[i0:i1 + 1]
    med = statistics.median(window)
    centred = [x - med for x in window]
    deadband = 0.5 * (percentile(centred, DEADBAND_PRIMARY_PCT[1])
                      - percentile(centred, DEADBAND_PRIMARY_PCT[0]))
    deadband_p1 = 0.5 * (percentile(centred, DEADBAND_SENSITIVITY_PCT[1])
                         - percentile(centred, DEADBAND_SENSITIVITY_PCT[0]))
    deadband_mm = 0.5 * (max(centred) - min(centred))
    rate_med = statistics.median(seg_rates)
    rate_amp = percentile([abs(r - rate_med) for r in seg_rates], DRIFT_AMPLITUDE_PCT)

    slot = float(wrap180(np.array([med]))[0])
    accel = triaxial_acceleration_deg_day2(slot)
    accel_signed = triaxial_acceleration_signed_deg_day2(slot)
    a_mean = statistics.median([s.a_km for s in seg_states])

    lo, hi = epochs[0], epochs[-1]
    inside = [(a, b, e) for a, b, e in ew_ms if lo <= a <= hi]
    detected = sum(float(e["deltaV"]["totalMetresPerSecond"]) for _, _, e in inside)

    observed_days = sum(min((b - a) / DAY_MS, SEGMENT_GAP_BREAK_DAYS)
                        for a, b in zip(epochs, epochs[1:]))
    observed_years = observed_days / DAYS_PER_YEAR
    if observed_years <= 0:
        return None

    busy = [(a, b) for a, b, _ in inside]
    measured_accels = free_drift_acceleration(epochs, seg_rates, busy)
    measured_accel = statistics.median(measured_accels) if measured_accels else float("nan")
    short = free_drift_acceleration_short_windows(epochs, seg_rates, busy)
    short_accel = statistics.median(short) if short else float("nan")
    pairs = free_drift_acceleration_pair_median(epochs, seg_rates, busy)
    pair_accel = statistics.median(pairs) if len(pairs) >= FREE_DRIFT_MIN_SAMPLES else float("nan")
    arc_days = quiet_arc_lengths(epochs, busy)

    ratios = []
    for a, b, e in inside:
        sa = state_at(seg_states, epochs, a)
        sb = state_at(seg_states, epochs, b)
        if sa is None or sb is None:
            continue
        # eq. (13) already carries the tangential term as (v+ - v-)^2, so the
        # same function prices an east-west burn and a plane change alike.
        theta = plane_rotation_deg(sa.inc_deg, sb.inc_deg, sb.raan_deg - sa.raan_deg)
        exact = dv_min_combined_mps(sa.v_km_s, sb.v_km_s, theta)
        if exact > 0:
            ratios.append(float(e["deltaV"]["totalMetresPerSecond"]) / exact)

    theory_year = dv_per_year_mps(accel, a_mean)
    return Segment(
        norad=norad, name=cat.get("name") or "", bus=cat.get("bus"),
        start_ms=lo, end_ms=hi, n_samples=len(window), observed_years=observed_years,
        slot_deg=slot, accel_deg_day2=accel, accel_signed_deg_day2=accel_signed,
        deadband_deg=deadband, deadband_p1p99_deg=deadband_p1, deadband_minmax_deg=deadband_mm,
        deadband_from_drift_deg=deadband_from_drift_amplitude(rate_amp, accel),
        drift_amp_deg_day=rate_amp,
        events=len(inside), detected_dv_mps=detected,
        detected_dv_per_year=detected / observed_years,
        theory_dv_per_year=theory_year,
        theory_dv_per_cycle=dv_per_cycle_mps(deadband, accel, a_mean),
        theory_cycle_days=cycle_period_days(deadband, accel),
        theory_manoeuvres_per_year=manoeuvres_per_year(deadband, accel),
        recall_ratio=(detected / observed_years / theory_year) if theory_year > 0 else float("nan"),
        measured_accel_deg_day2=measured_accel,
        measured_accel_samples=len(measured_accels),
        short_window_accel_deg_day2=short_accel,
        short_window_samples=len(short),
        pair_accel_deg_day2=pair_accel,
        pair_samples=len(pairs),
        quiet_arc_days_median=statistics.median(arc_days) if arc_days else float("nan"),
        shipped_over_min=ratios,
    )


def quiet_arc_lengths(epochs: list[int], busy: list[tuple[int, int]]) -> list[float]:
    """Arc lengths, in days, of the gaps between detected east-west events --
    the number that explains why the registered §4.6 control behaves as it does."""
    merged: list[list[int]] = []
    for lo, hi in sorted(busy):
        if merged and lo <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], hi)
        else:
            merged.append([lo, hi])
    bounds = [epochs[0]] + [t for lo, hi in merged for t in (lo, hi)] + [epochs[-1]]
    return [(bounds[k + 1] - bounds[k]) / DAY_MS for k in range(0, len(bounds) - 1, 2)
            if bounds[k + 1] > bounds[k]]


def summarise_ns(primary, sigma_pole) -> dict:
    """The registered T10b headline numbers and the acceptance verdict."""
    if not primary:
        return {"n": 0, "acceptance": {"verdict": "UNDERPOWERED"},
                "note": "no event survived the registered screens"}
    by_obj: dict = {}
    for m in primary:
        by_obj.setdefault(m.norad, []).append(m.eta)
    boot = bootstrap_median_by_group(by_obj)

    u_by_obj: dict = {}
    for m in primary:
        if m.u_node is not None:
            u_by_obj.setdefault(m.norad, []).append(m.u_node)
    u_boot = bootstrap_median_by_group(u_by_obj, seed=SEED + 1)

    # R4 -- the element-noise Monte Carlo, on the MEASURED pole floor
    rng = random.Random(SEED)
    sigma_i = noise_floor_for(35786.0)[2]
    mc_medians = []
    for _ in range(MONTE_CARLO_DRAWS):
        draw = []
        for m in primary:
            if m.inc_pred <= 0:
                continue
            d_inc = rng.gauss(0.0, sigma_i)
            d_raan = rng.gauss(0.0, sigma_pole / max(math.sin(math.radians(m.inc_pred)), 1e-9))
            theta = plane_rotation_deg(m.inc_pred, m.inc_after + d_inc,
                                       m.raan_after + d_raan - m.raan_pred)
            di = m.inc_after + d_inc - m.inc_pred
            v1 = math.sqrt(MU / m.a_before)
            v2 = math.sqrt(MU / m.a_after)
            dvm = dv_min_combined_mps(v1, v2, theta)
            if dvm > 0:
                draw.append(dv_ideal_node_mps(v1, v2, di) / dvm)
        if draw:
            mc_medians.append(statistics.median(draw))
    mc_median = statistics.median(mc_medians) if mc_medians else float("nan")
    mc_shift = (abs(mc_median - boot["median"]) / boot["median"]
                if boot.get("median") else float("nan"))

    natural_fracs = [m.natural_fraction for m in primary
                     if m.natural_fraction == m.natural_fraction]
    thetas = [m.theta_net for m in primary]

    families: dict = {}
    operators: dict = {}
    for m in primary:
        if m.family:
            families.setdefault(m.family, []).append(m)
        operators.setdefault(operator_family(m.name), []).append(m)

    def group_table(groups: dict, min_objects: int = 5) -> dict:
        out = {}
        for key, rows in sorted(groups.items()):
            objs = {r.norad for r in rows}
            entry = {"events": len(rows), "objects": len(objs)}
            if len(objs) >= min_objects:
                entry["medianEta"] = statistics.median([r.eta for r in rows])
                un = [r.u_node for r in rows if r.u_node is not None]
                entry["medianNodeOffsetDeg"] = statistics.median(un) if un else None
                entry["etaQuantiles"] = quantiles([r.eta for r in rows])
                entry["medianPenaltyMpsPerYear"] = (
                    (1.0 / entry["medianEta"] - 1.0) * north_south_budget_mps_per_year())
            out[key] = entry
        return out

    a1 = len(primary) >= B1_MIN_EVENTS and len(by_obj) >= B1_MIN_OBJECTS
    ci = boot.get("ci95", [float("nan"), float("nan")])
    a2 = not (ci[0] <= 1.0 <= ci[1])
    a3 = (statistics.median(thetas) >= B3_NOISE_MULTIPLE * sigma_pole
          and mc_shift == mc_shift and mc_shift < B3_MC_MAX_SHIFT)
    a4 = (statistics.median(natural_fracs) < B4_MAX_NATURAL_FRACTION) if natural_fracs else False
    verdict = ("INFORMATIVE" if (a1 and a2 and a3 and a4)
               else ("UNDERPOWERED" if not a1
                     else ("NOISE-DOMINATED" if not a3 else "MEASURED NULL")))

    raised = [m for m in primary if m.di_net > 0]
    lowered = [m for m in primary if m.di_net < 0]

    return {
        "n": len(primary), "objects": len(by_obj),
        "etaBootstrap": boot,
        "etaQuantiles": quantiles([m.eta for m in primary]),
        "R3_etaShippedDenominatorQuantiles": quantiles(
            [m.eta_shipped for m in primary if m.eta_shipped == m.eta_shipped]),
        "R2_etaNoNaturalSubtractionQuantiles": quantiles(
            [m.eta_raw for m in primary if m.eta_raw == m.eta_raw]),
        "nodeOffsetBootstrap": u_boot,
        "nodeOffsetQuantiles": quantiles([m.u_node for m in primary if m.u_node is not None]),
        "uEffectiveQuantiles": quantiles([m.u_eff for m in primary if m.u_eff is not None]),
        "thetaNetQuantiles": quantiles(thetas),
        "diNetQuantiles": quantiles([abs(m.di_net) for m in primary]),
        "spanDaysQuantiles": quantiles([m.span_days for m in primary]),
        "naturalFractionQuantiles": quantiles(natural_fracs),
        "naturalPoleMotionDegQuantiles": quantiles([m.natural_pole_deg for m in primary]),
        "shippedOverExactMinimum": quantiles(
            [m.dv_shipped / m.dv_min for m in primary if m.dv_min > 0]),
        "radialTermBoundMpsQuantiles": quantiles([m.radial_bound_mps for m in primary]),
        "signSplit": {
            "inclinationLowered": len(lowered), "inclinationRaised": len(raised),
            "medianEtaLowered": statistics.median([m.eta for m in lowered]) if lowered else None,
            "medianEtaRaised": statistics.median([m.eta for m in raised]) if raised else None,
        },
        "registrationDefects_naturalModel": {
            "medianEtaPrimaryLaplaceOnly": statistics.median([m.eta for m in primary]),
            "medianEtaRegisteredAsWritten": statistics.median(
                [m.eta_j2 for m in primary if m.eta_j2 == m.eta_j2]),
            "medianThetaNetPrimaryDeg": statistics.median([m.theta_net for m in primary]),
            "medianThetaNetRegisteredAsWrittenDeg": statistics.median(
                [m.theta_net_j2 for m in primary]),
            "medianAbsoluteThetaDifferenceDeg": statistics.median(
                [abs(m.theta_net - m.theta_net_j2) for m in primary]),
            "maxAbsoluteThetaDifferenceDeg": max(
                abs(m.theta_net - m.theta_net_j2) for m in primary),
            "note": "TWO defects in the registered natural-motion model. (1) eq. (10) "
                    "double-counts the oblateness that eq. (9)'s 7.4 deg Laplace tilt "
                    "already encodes -- found by the test suite before any data was read. "
                    "(2) eq. (9) did not state the SENSE of the circuit and its unstated "
                    "default is prograde, which is backwards -- found by the registered "
                    "drift-direction control of §3.3 and confirmed by the direct "
                    "calibration on eleven retired satellites. The primary applies eq. (9) "
                    "alone, retrograde; the registration as written travels beside every "
                    "event as etaRegisteredAsWritten.",
        },
        "R4_monteCarlo": {"medianEta": mc_median, "relativeShift": mc_shift,
                          "draws": MONTE_CARLO_DRAWS, "sigmaIncDeg": sigma_i},
        "busFamilies": group_table(families),
        "operatorFamilies": group_table(operators),
        "acceptance": {"B1_power": a1, "B2_excludesUnity": a2,
                       "B3_aboveNoiseFloor": a3, "B4_notDriftDominated": a4,
                       "verdict": verdict},
        "annualPenalty": {
            "northSouthBudgetMpsPerYear": north_south_budget_mps_per_year(),
            "budgetBandMpsPerYear": [north_south_budget_mps_per_year(DRIFT_INTERVAL_DEG_PER_YR[0]),
                                     north_south_budget_mps_per_year(DRIFT_INTERVAL_DEG_PER_YR[1])],
            "medianPenaltyMpsPerYear": ((1.0 / boot["median"] - 1.0)
                                        * north_south_budget_mps_per_year())
            if boot.get("median") else None,
            "p90PenaltyMpsPerYear": (
                (1.0 / percentile([m.eta for m in primary], 10.0) - 1.0)
                * north_south_budget_mps_per_year()),
        },
    }


def operator_family(name: str) -> str:
    """Coarse operator family from the catalogue's own object name.

    Matched on the name the catalogue carries and nothing else; no external
    registry is consulted, exactly as T3's §3.6 disclosed for its carrier list.
    """
    up = (name or "").upper()
    for key in ("INTELSAT", "EUTELSAT", "ASTRA", "SES", "INMARSAT", "ARABSAT", "BADR",
                "JCSAT", "BSAT", "DIRECTV", "GALAXY", "ANIK", "AMC", "HOT BIRD", "HOTBIRD",
                "THURAYA", "TELSTAR", "XM-", "SXM", "GOES", "ASIASAT", "KOREASAT", "NIMIQ",
                "YAMAL", "THAICOM", "OPTUS", "TURKSAT", "TÜRKSAT", "VIASAT", "ECHOSTAR",
                "SPACEWAY", "AMAZONAS", "HISPASAT", "NBN", "APSTAR", "PALAPA", "MEASAT",
                "YAHSAT", "ABS-", "O3B", "STAR ONE", "SGDC", "HELLAS", "BANGABANDHU",
                "RASCOM", "NILESAT", "AMOS", "HORIZONS", "SENTINEL", "LANDSAT", "TERRA",
                "AQUA", "AURA", "JASON", "GRACE", "NOAA", "SUOMI"):
        if key in up:
            return key.strip("-")
    return "other"


def summarise_ew(segments) -> dict:
    """The registered T10c headline numbers and the acceptance verdict."""
    usable = [s for s in segments if s.events > 0 and s.deadband_deg > 0
              and s.theory_dv_per_year > 0]
    if not usable:
        return {"segments": len(segments), "usableSegments": 0,
                "acceptance": {"verdict": "UNDERPOWERED"}}
    objs = {s.norad for s in usable}

    m1 = theil_sen_bootstrap([s.deadband_deg for s in usable],
                             [s.detected_dv_per_year for s in usable],
                             [s.norad for s in usable], seed=SEED)
    m2 = theil_sen_bootstrap([s.accel_deg_day2 / A_MAX_DEG_DAY2 for s in usable],
                             [s.detected_dv_per_year for s in usable],
                             [s.norad for s in usable], seed=SEED + 2)
    m1_count = theil_sen_bootstrap([s.deadband_deg for s in usable],
                                   [s.events / s.observed_years for s in usable],
                                   [s.norad for s in usable], seed=SEED + 3)

    ctrl = [s for s in segments if s.measured_accel_samples > 0
            and s.measured_accel_deg_day2 == s.measured_accel_deg_day2]
    m4 = theil_sen_bootstrap([s.accel_signed_deg_day2 for s in ctrl],
                             [s.measured_accel_deg_day2 for s in ctrl],
                             [s.norad for s in ctrl], seed=SEED + 4)
    short = [s for s in segments if s.short_window_samples > 0
             and s.short_window_accel_deg_day2 == s.short_window_accel_deg_day2]
    m4b = theil_sen_bootstrap([s.accel_signed_deg_day2 for s in short],
                              [s.short_window_accel_deg_day2 for s in short],
                              [s.norad for s in short], seed=SEED + 5)
    pairs = [s for s in segments if s.pair_samples >= 50
             and s.pair_accel_deg_day2 == s.pair_accel_deg_day2]
    m4c = theil_sen_bootstrap([s.accel_signed_deg_day2 for s in pairs],
                              [s.pair_accel_deg_day2 for s in pairs],
                              [s.norad for s in pairs], seed=SEED + 6)
    named = sorted(pairs, key=lambda s: -s.pair_samples)[:8]

    recall = [s.recall_ratio for s in usable if s.recall_ratio == s.recall_ratio]
    recall_q = quantiles(recall)
    ratios = [r for s in segments for r in s.shipped_over_min]

    # C2: is the deadband-independence test decidable? Compare the interval
    # width with the slope a DV_year ~ sqrt(R) alternative would produce at the
    # population's own medians: d(DV)/dR = DV/(2R).
    med_dv = statistics.median([s.detected_dv_per_year for s in usable])
    med_r = statistics.median([s.deadband_deg for s in usable])
    alt_slope = med_dv / (2.0 * med_r) if med_r > 0 else float("nan")
    ci = m1.get("ci95", [float("nan"), float("nan")])
    width = ci[1] - ci[0] if ci[0] == ci[0] and ci[1] == ci[1] else float("nan")
    c2 = width == width and alt_slope == alt_slope and width < 2.0 * abs(alt_slope)

    c1 = len(usable) >= C1_MIN_SEGMENTS and len(objs) >= C1_MIN_OBJECTS
    m4ci = m4.get("ci95", [float("nan"), float("nan")])
    c3 = (m4ci[0] <= 1.0 <= m4ci[1]) if (m4ci[0] == m4ci[0] and m4ci[1] == m4ci[1]) else False
    recall_limited = recall_q.get("median", float("nan")) < C4_RECALL_LIMITED_BELOW

    if not c3:
        verdict = "INPUT NOT VERIFIED"
    elif recall_limited:
        verdict = "RECALL-LIMITED"
    elif ci[0] <= 0.0 <= ci[1]:
        verdict = "CONFIRMATION"
    else:
        verdict = "DISAGREEMENT"

    return {
        "segments": len(segments), "usableSegments": len(usable), "objects": len(objs),
        "observedYearsQuantiles": quantiles([s.observed_years for s in usable]),
        "slotDegQuantiles": quantiles([s.slot_deg for s in usable]),
        "deadbandDegQuantiles": quantiles([s.deadband_deg for s in usable]),
        "deadbandP1P99Quantiles": quantiles([s.deadband_p1p99_deg for s in usable]),
        "deadbandMinMaxQuantiles": quantiles([s.deadband_minmax_deg for s in usable]),
        "deadbandFromDriftQuantiles": quantiles(
            [s.deadband_from_drift_deg for s in usable
             if s.deadband_from_drift_deg == s.deadband_from_drift_deg]),
        "deadbandEstimatorRatio": quantiles(
            [s.deadband_from_drift_deg / s.deadband_deg for s in usable
             if s.deadband_deg > 0 and s.deadband_from_drift_deg == s.deadband_from_drift_deg]),
        "detectedDvPerYearQuantiles": quantiles([s.detected_dv_per_year for s in usable]),
        "theoryDvPerYearQuantiles": quantiles([s.theory_dv_per_year for s in usable]),
        "theoryCycleDaysQuantiles": quantiles(
            [s.theory_cycle_days for s in usable if s.theory_cycle_days == s.theory_cycle_days]),
        "theoryManoeuvresPerYearQuantiles": quantiles(
            [s.theory_manoeuvres_per_year for s in usable
             if s.theory_manoeuvres_per_year == s.theory_manoeuvres_per_year]),
        "detectedEventsPerYearQuantiles": quantiles(
            [s.events / s.observed_years for s in usable]),
        "M1_slopeDvOnDeadband": m1,
        "M1_sqrtAlternativeSlope": alt_slope,
        "M1b_slopeEventRateOnDeadband": m1_count,
        "M2_slopeDvOnAcceleration": m2,
        "M2_theoreticalSlope": dv_per_year_mps(A_MAX_DEG_DAY2),
        "M3_recallRatio": recall_q,
        "M4_freeDriftControl": m4,
        "M4b_freeDriftShortWindowUnregistered": m4b,
        "M4c_freeDriftAdjacentPairUnregistered": m4c,
        "M4c_pairAccelQuantiles": quantiles([s.pair_accel_deg_day2 for s in pairs]),
        "M4c_predictedAccelQuantiles": quantiles([s.accel_signed_deg_day2 for s in pairs]),
        "M4c_ratioQuantiles": quantiles(
            [s.pair_accel_deg_day2 / s.accel_signed_deg_day2 for s in pairs
             if abs(s.accel_signed_deg_day2) > 0.1 * A_MAX_DEG_DAY2]),
        "M4c_segments": len(pairs),
        "M4c_namedExamples": [
            {"norad": s.norad, "name": s.name, "slotDeg": s.slot_deg,
             "derivedAccelDegPerDay2": s.accel_signed_deg_day2,
             "measuredAccelDegPerDay2": s.pair_accel_deg_day2,
             "pairs": s.pair_samples, "observedYears": s.observed_years}
            for s in named],
        "M4b_shortWindowAccelQuantiles": quantiles(
            [s.short_window_accel_deg_day2 for s in short]),
        "M4b_windowDays": UNREGISTERED_SHORT_WINDOW_DAYS,
        "quietArcDaysQuantiles": quantiles(
            [s.quiet_arc_days_median for s in segments
             if s.quiet_arc_days_median == s.quiet_arc_days_median]),
        "M4_measuredAccelQuantiles": quantiles([s.measured_accel_deg_day2 for s in ctrl]),
        "M4_predictedAccelQuantiles": quantiles([s.accel_signed_deg_day2 for s in ctrl]),
        "freeDriftSegments": len(ctrl),
        "shippedOverExactMinimum": quantiles(ratios),
        "acceptance": {"C1_power": c1, "C2_decidable": c2,
                       "C3_freeDriftControlPasses": c3,
                       "C4_recallLimited": recall_limited, "verdict": verdict},
    }


def _provenance(receipt: dict) -> dict:
    return {"_provenance": {
        "registration": REGISTRATION, "registrationCommit": REGISTRATION_COMMIT,
        "measuredAt": receipt["measuredAt"], "inputs": receipt["inputs"]["sha256"],
        "sourceSha256": receipt["sourceSha256"], "seeds": receipt["seeds"],
        "executionMode": receipt["executionMode"],
        "note": "Analysis artifact. Every delta-v is a LOWER BOUND. Population is "
                "data/propulsion-catalog-v1.json, policy commercial-civil-only; no "
                "government or military object is read, priced or named."}}


def _iso(ms: int) -> str:
    return dt.datetime.fromtimestamp(ms / 1000, dt.timezone.utc).isoformat().replace("+00:00", "Z")


def write_ns_jsonl(path_str: str, rows, dropped, receipt) -> None:
    with open(path_str, "w") as fh:
        fh.write(json.dumps(_provenance(receipt)) + "\n")
        for m in sorted(rows, key=lambda r: (r.norad, r.start_ms)):
            fh.write(json.dumps({
                "norad": m.norad, "name": m.name, "bus": m.bus, "busFamily": m.family,
                "startAt": _iso(m.start_ms), "endAt": _iso(m.end_ms),
                "signature": m.signature, "spanDays": m.span_days,
                "incBeforeDeg": m.inc_before, "incPredictedDeg": m.inc_pred,
                "incAfterDeg": m.inc_after,
                "raanBeforeDeg": m.raan_before, "raanPredictedDeg": m.raan_pred,
                "raanAfterDeg": m.raan_after,
                "aBeforeKm": m.a_before, "aAfterKm": m.a_after,
                "eBefore": m.e_before, "eAfter": m.e_after,
                "deltaIncNetDeg": m.di_net, "planeRotationNetDeg": m.theta_net,
                "deltaIncRawDeg": m.di_raw, "planeRotationRawDeg": m.theta_raw,
                "incPredictedRegisteredAsWrittenDeg": m.inc_pred_j2,
                "deltaIncNetRegisteredAsWrittenDeg": m.di_net_j2,
                "planeRotationNetRegisteredAsWrittenDeg": m.theta_net_j2,
                "etaRegisteredAsWritten": m.eta_j2,
                "naturalPoleMotionDeg": m.natural_pole_deg,
                "observedPoleMotionDeg": m.observed_pole_deg,
                "naturalFraction": m.natural_fraction,
                "dvIdealNodeBurnMps": m.dv_ideal, "dvExactMinimumMps": m.dv_min,
                "dvShippedMps": m.dv_shipped, "radialTermBoundMps": m.radial_bound_mps,
                "eta": m.eta, "etaShippedDenominator": m.eta_shipped,
                "etaNoNaturalSubtraction": m.eta_raw,
                "uEffectiveDeg": m.u_eff, "nodeOffsetDeg": m.u_node,
                "flags": m.flags, "informative": m.informative,
            }, default=float) + "\n")
        for row in dropped:
            fh.write(json.dumps(row, default=float) + "\n")


def write_ew_jsonl(path_str: str, rows, receipt) -> None:
    with open(path_str, "w") as fh:
        fh.write(json.dumps(_provenance(receipt)) + "\n")
        for s in sorted(rows, key=lambda r: (r.norad, r.start_ms)):
            fh.write(json.dumps({
                "norad": s.norad, "name": s.name, "bus": s.bus,
                "startAt": _iso(s.start_ms), "endAt": _iso(s.end_ms),
                "samples": s.n_samples, "observedYears": s.observed_years,
                "slotDeg": s.slot_deg,
                "triaxialAccelDegPerDay2": s.accel_deg_day2,
                "triaxialAccelSignedDegPerDay2": s.accel_signed_deg_day2,
                "measuredAccelDegPerDay2": s.measured_accel_deg_day2,
                "measuredAccelSamples": s.measured_accel_samples,
                "measuredAccelShortWindowDegPerDay2Unregistered": s.short_window_accel_deg_day2,
                "shortWindowSamples": s.short_window_samples,
                "measuredAccelAdjacentPairDegPerDay2Unregistered": s.pair_accel_deg_day2,
                "adjacentPairSamples": s.pair_samples,
                "medianQuietArcDays": s.quiet_arc_days_median,
                "deadbandHalfWidthDeg": s.deadband_deg,
                "deadbandP1P99Deg": s.deadband_p1p99_deg,
                "deadbandMinMaxDeg": s.deadband_minmax_deg,
                "deadbandFromDriftDeg": s.deadband_from_drift_deg,
                "driftAmplitudeDegPerDay": s.drift_amp_deg_day,
                "detectedEvents": s.events, "detectedDvMps": s.detected_dv_mps,
                "detectedDvPerYearMps": s.detected_dv_per_year,
                "theoryDvPerYearMps": s.theory_dv_per_year,
                "theoryDvPerCycleMps": s.theory_dv_per_cycle,
                "theoryCycleDays": s.theory_cycle_days,
                "theoryManoeuvresPerYear": s.theory_manoeuvres_per_year,
                "recallRatio": s.recall_ratio,
                "shippedOverExactMinimum": s.shipped_over_min,
                "flags": s.flags,
            }, default=float) + "\n")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="T10b/T10c station-keeping efficiency")
    ap.add_argument("--events", type=Path, default=DEFAULT_EVENTS)
    ap.add_argument("--archive", type=Path, default=DEFAULT_ARCHIVE)
    ap.add_argument("--catalogue", type=Path, default=DEFAULT_CATALOGUE)
    ap.add_argument("--out-prefix", default="docs/stationkeeping-efficiency-20260922")
    ap.add_argument("--skip-archive-hash", action="store_true",
                    help="development only; the receipt records that it was skipped")
    return run(ap.parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
