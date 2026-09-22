#!/usr/bin/env python3
"""Deterministic classification of *what kind* of orbit change happened, and what it cost.

`pipeline/orbit_history.py` answers "did something change?" against one object's
own scatter. This module answers the two questions a visitor actually asks —
**what kind of change was it** and **what did it cost the operator** — and it
answers them in code, because a language model must never be the thing that
decides whether a manoeuvre is ordinary.

Three ideas carry the whole file.

**1. Drag is predicted, not assumed away.**
Semi-major axis falls for two unrelated reasons: the atmosphere takes energy
out, and the operator puts energy in or takes it out on purpose. Separating
them is the entire job. Atmospheric decay obeys

    adot_drag = -(C_D A / m) rho sqrt(mu a)

and the fitted B* term is directly proportional to `C_D A / m`. So
**adot/B\\* is very nearly a property of the atmosphere alone** at a given
altitude, shared by every object flying through it, whatever it is made of.
Measured on the live archive, normalising by B* tightens the relative spread of
the passive population within a 50 km shell from 1.27 to 0.14 at 750-800 km,
0.89 to 0.19 at 700-750 km, and 0.94 to 0.35 at 550-600 km. That is a three- to
nine-fold tightening of the null distribution, and it comes from physics rather
than from a tuned constant.

The consequence: for every interval we can state how much of the observed change
in `a` drag alone accounts for, and treat only the **residual** as propulsive.
"This object lost 3,898 m of altitude, of which drag on a body of this ballistic
coefficient accounts for 5 m" is a far stronger statement than "a changed".

**2. Discrimination comes from the population, not from a threshold.**
`docs/orbit-history-design.md` §2.1 measures the fitted-element residual
distribution and finds no usable tail decay: at kappa=8 the observed exceedance
is 23.6% where a Gaussian predicts 1e-15. **No threshold can be made clean by
tuning it.** So every test here is against a *cohort* — objects at the same
perigee altitude and inclination over the same interval — and the cohort is the
thing that separates weather from operator action. A storm bends a whole shell
at once; an operator bends one object.

This also makes the feature work on the day the archive is switched on. A
per-object detector needs weeks of that object's history before it can estimate
that object's scatter. A cohort detector needs *one* interval per object and
many objects, which is exactly what an hours-old archive holds.

**3. What counts as ordinary is decided by object class, in code.**
A Starlink in an operational shell manoeuvring every day is ordinary. A spent
rocket body manoeuvring at all is impossible. A GEO communications satellite
spending 2 m/s a year east-west is ordinary; spending 50 m/s in a week is not.
`data/orbit_manoeuvre_expectations.json` holds those priors as hand-authored,
cited, versioned data, and `score_against_expectation()` compares an event to
them. The model is never asked whether something is normal.

Boundaries this module is built to respect
------------------------------------------
* **No object-to-object association.** `docs/mission-speculation-design.md` §1.6
  is a decision by the site owner, who is a serving US information warfare
  officer, and it is structural rather than editorial. The cohort here is an
  anonymous *statistical population* binned by orbit regime: it returns counts,
  medians and scales, and there is no function anywhere in this module that
  returns cohort membership, names a neighbour, or compares two named objects.
  The node and the argument of perigee ARE read, as of the change that added
  the node and apsidal channels, but only as one object's own residual against
  its own predicted J2 drift. They are never a cohort key, never compared
  between two named objects, and there is still no function here that can
  return a neighbour. The distinction is the one the design turns on: reading
  RAAN to ask "did this object's plane rotate more than the shell's did" is
  orbital mechanics; reading RAAN to ask "whose plane is this object's plane
  near" is association, and that function does not exist.
* **No mission language for opaque objects.** `opacity_denied()` implements the
  §1.3 gate. A denied object still gets every physical number — Delta-v, element
  deltas, drag share, cohort context — because that is orbital mechanics. It
  gets no purpose language, and its absence is silent (§1.5): there is no
  "withheld" marker, because a redaction badge is itself an assessment.
* **No network.** Everything is read from the archive on `/mnt/d` and from
  files in the repository.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import datetime as dt
import json
import math
import multiprocessing
import sys
import re
import sqlite3
import statistics
from bisect import bisect_left, bisect_right
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

from pipeline.orbit_history import (
    CATALOGUE_NOISE_FLOOR,
    MU_WGS72,
    RE_WGS72,
    ElementSet,
    archive_root,
    archive_stats,
    epoch_ms_to_datetime,
    noise_floor_for,
    open_archive,
    paged_element_sets,
    rates,
    series,
)
# Imported rather than re-implemented: a second fold of an angle difference
# into (-180, 180] is a second chance to get a sign convention wrong, and the
# two would be compared against each other by nothing.
from pipeline.orbit_history import _wrap_deg as wrap_degrees

ROOT = Path(__file__).resolve().parents[1]
EXPECTATIONS_PATH = ROOT / "data" / "orbit_manoeuvre_expectations.json"
GROUND_TRUTH_PATH = ROOT / "data" / "orbit_manoeuvre_truth.json"

SCHEMA_VERSION = 1

# The projection every whole-archive scan in this pipeline now reads.
# `orbit_history.SCAN_COLUMNS` is the six-column form the two scans shared
# before the node and apse-line channels existed; both scans read this
# eight-column form instead, and they must keep reading the SAME one, for the
# reason recorded against `SCAN_COLUMNS` itself: the agreement of the cohort
# detector and the self-history detector is the release's only cross-check, and
# two scans projecting different columns would be comparing different
# measurements. The first two columns are the paging cursor and cannot move.
SCAN_COLUMNS_WITH_ANGLES = (
    "norad, epoch_ms, mean_motion_q, eccentricity_q, inclination_q, bstar_q, "
    "raan_q, arg_perigee_q"
)

# ---------------------------------------------------------------------------
# Cohort geometry
# ---------------------------------------------------------------------------
# Perigee altitude, because drag does its work at perigee; inclination, because
# it fixes the latitude band the object samples and therefore the atmosphere it
# actually flies through. Both tolerances come from
# `docs/orbit-history-design.md` §3.8.
COHORT_PERIGEE_TOLERANCE_KM = 25.0
COHORT_INCLINATION_TOLERANCE_DEG = 2.0
# Time is part of the index, not a filter left until after the altitude slice.
# A seven-day cohort holds enough same-altitude intervals that scanning the
# whole altitude band for every query is near-quadratic. Intervals are assigned
# once, by start time, to a six-hour bucket and a bounded duration class.
# A query then looks back only as far as each class can overlap it.
COHORT_TIME_BUCKET_HOURS = 6
COHORT_DURATION_CLASS_HOURS = (6, 12, 24, 36, 48, 60, 72)
# Forking a tiny population costs more than it saves. The production seven-day
# window is orders of magnitude above this line; fixtures and callers that do
# not ask for workers stay in the simple one-process path.
COHORT_PARALLEL_MINIMUM_INTERVALS = 64
# Several ordered chunks keep one worker from sitting idle when one side of the
# NORAD-ordered interval list contains much longer histories. Pool.map still
# returns chunk results in input order, so flattening them preserves the serial
# detector's order exactly.
COHORT_PARALLEL_CHUNKS_PER_WORKER = 4

# Two cohort sizes, on purpose. Below `COHORT_MINIMUM` there is no usable
# population statistic at all and the interval is reported unscreened. Between
# the two, the screen runs but `cohortScreened` stays false, because a median
# over a handful of members has a scale estimate that a single outlier can set.
# Measured on the live archive: at a threshold of 20 the passive control shrinks
# to four intervals, which cannot measure anything; at 8 it holds 68. So 8 is
# the operating point today and the count travels with every event so a reader
# can see how thin it is.
COHORT_MINIMUM = 8
COHORT_PREFERRED = 20

# Robust-sigma multiple. Not a Gaussian confidence: with the measured tails
# (design doc §2.1) kappa=8 is roughly an empirical 99.5th percentile, and the
# honest false-alarm number is measured against the passive control, never
# derived from this constant.
DEFAULT_KAPPA = 8.0

# Intervals shorter than this are dropped. Two element sets an hour apart differ
# mostly by fit noise, and dividing that noise by a very small span produces an
# enormous apparent rate. That is not merely a weak measurement: mixed into a
# cohort it inflates the population's scale estimate by orders of magnitude and
# quietly disables the screen for everyone in the shell. Measured on the live
# archive, a handful of sub-hour pairs pushed the geostationary cohort's robust
# scale to ~144 km/day, against which a real 2.7 km/day station-keeping burn
# scored z = 0.02 and was discarded. 2.4 hours is a little over one and a half
# low Earth orbit revolutions and comfortably longer than the fit's own
# correlation time.
MINIMUM_SPAN_DAYS = 0.1

# B* below this is not a usable ballistic coefficient: the drag term was either
# not fitted or has collapsed to the fit's floor, and dividing by it invents a
# number. Objects below it get no drag prediction and are labelled as such
# rather than being handed a prediction of zero.
MINIMUM_USABLE_BSTAR = 1e-7

# Above this altitude drag is not the story and B* is routinely fitted to
# garbage or to a negative value. The drag model is simply not applied.
DRAG_MODEL_CEILING_KM = 1400.0

# Below this perigee an object is in terminal decay. Drag removes tens of
# kilometres of semi-major axis per day, the fits degrade badly because the
# atmosphere is changing faster than the arc, and no propulsive claim can be
# separated from it. **No manoeuvre signature is ever asserted below this
# altitude.** This is not conservatism for its own sake: the first run of this
# detector labelled a rocket body at 126 km perigee, losing 57 km in a day on
# its way into the atmosphere, as a 30 m/s "disposal lowering". It was
# re-entering. A real deorbit burn down here would be missed, and that is the
# right trade -- the alternative is calling every re-entry a manoeuvre.
TERMINAL_DECAY_PERIGEE_KM = 200.0

# Luni-solar precession of the inclination vector, for orbits high enough that
# it is the dominant plane perturbation. Solar and lunar gravity make the
# inclination vector of a high orbit precess about a pole roughly 7.4 deg from
# the equator with a period near 53 years; a satellite left alone at zero
# inclination therefore gains about 0.85 deg/year, which is the whole reason
# north-south station-keeping exists and consumes most of a geostationary
# satellite's propellant.
#
# **This is a bound, deliberately, and not a model.** The precession rate of
# the inclination vector is exactly `omega * |h - p|`, where `h` is the
# object's inclination vector and `p` the pole's; the DIRECTION of that motion
# depends on the object's node, so two objects at the same inclination can drift
# opposite ways. Rather than model the direction — which would mean getting a
# sign convention right with no way to check it, and getting it wrong makes the
# correction worse than none — the code bounds the magnitude:
#
#     |di/dt| <= omega * (i + i_pole)
#
# by the triangle inequality, with no reference to the node at all. Anything
# under the bound cannot be distinguished from natural drift and is never
# claimed. Anything over it cannot be natural.
#
# Why this matters: the first run of this detector reported "north-south
# station-keeping" on INTELSAT 4-F1, launched 1971 and long dead, and on the
# apogee kick motor of METEOSAT 2. Both were drifting exactly as physics says
# an abandoned geostationary object must.
LUNISOLAR_POLE_INCLINATION_DEG = 7.44
LUNISOLAR_PRECESSION_PERIOD_YEARS = 53.0
LUNISOLAR_REGIME_MINIMUM_SEMI_MAJOR_AXIS_KM = 20000.0

GEO_SEMI_MAJOR_AXIS_KM = 42164.0
GEO_BAND_KM = 300.0

# The geostationary equivalent of the luni-solar bound above, and the same trap
# in a different element.
#
# The Earth's equatorial ellipticity — the J22 term — gives the geostationary
# ring two stable longitudes near 75.1E and 104.9W and two unstable ones near
# 11.5W and 161.9E. An object anywhere else feels a longitudinal acceleration
# of up to about 0.0018 deg/day^2, largest roughly 45 degrees from a stable
# point. An *uncontrolled* object therefore oscillates about the nearest stable
# longitude with a period of a couple of years, and that libration is a change
# in semi-major axis with nobody burning anything.
#
# The size of it, derived rather than quoted: the drift rate in longitude
# relates to the semi-major axis offset by dD/da = -(3/2)(n/a) in the right
# units, which is -0.01284 deg/day per km at a = 42164 km. So a longitudinal
# acceleration of 0.0018 deg/day^2 is a semi-major-axis rate of
# 0.0018 / 0.01284 = 0.140 km/day, or **140 metres per day**.
#
# That number is why this constant exists. Against a measured geostationary
# fit scatter of 12.44 m, 140 m/day of perfectly natural libration is an
# 11-sigma "manoeuvre" every single day, on every uncontrolled object in the
# ring. The detector duly reported east-west station-keeping on the apogee kick
# motor of METEOSAT 2, abandoned in 1981, at 149 m — and on five active
# spacecraft at 141 to 180 m, which are just as likely to have been drifting.
# A real east-west correction is a few centimetres per second, which is one to
# three KILOMETRES of semi-major axis, comfortably above this bound; the
# detector loses nothing real by refusing everything below it.
GEO_TRIAXIALITY_DRIFT_METRES_PER_DAY = 140.0
# The IADC-recommended disposal region begins ~235 km above the geostationary
# ring plus a term in solar-radiation-pressure area-to-mass; 235 km is the floor
# and is what a raise is measured against.
GEO_GRAVEYARD_MINIMUM_RAISE_KM = 235.0


# ---------------------------------------------------------------------------
# The node and the apse line: the two elements the archive stored and nobody
# watched
# ---------------------------------------------------------------------------
# A node-change manoeuvre rotates the orbit plane about the Earth's axis and
# can leave a, e and i very nearly untouched; an apsidal manoeuvre rotates the
# ellipse inside its own plane and leaves a, e and i untouched by definition.
# The detector was blind to both, and a Molniya-type orbit -- which the site's
# own ellipse figure teaches -- spends its life on the second.
#
# BOTH ELEMENTS DRIFT ENORMOUSLY WITHOUT ANYONE BURNING ANYTHING, which is the
# whole reason they were not simply switched on. The Earth's oblateness makes
# the node regress and the apse line rotate at rates of order a degree a day in
# low Earth orbit -- a thousand times the catalogue's own scatter in those
# angles. So neither channel ever sees the raw element difference. Each sees
# the RESIDUAL after the predicted J2 secular drift has been subtracted,
# exactly as the semi-major-axis channel sees the residual after drag.
#
# `J2_SECULAR_MODEL_RELATIVE_ERROR` is what is left over after that
# subtraction, expressed as a fraction of the drift it removed. The terms this
# model keeps are first order in J2; the ones it drops -- second-order J2
# products, and the J4 and J2-squared secular terms -- are smaller than the
# retained ones by a further factor of order J2 itself. So the model's own
# error is bounded by J2 times the drift it predicted, and that bound is added
# to the natural floor of both angle channels. It is a derivation, not a tuned
# constant: for a sun-synchronous orbit regressing 0.99 deg/day over a six-hour
# interval it admits 2.7e-4 deg of model error, against a catalogue scatter in
# the angle itself of 1.4e-4 deg.
J2_SECULAR_MODEL_RELATIVE_ERROR = 1.082616e-3

# The catalogue quantises every published angle to 1e-4 degrees
# (`orbit_history.SCALE_ANGLE`). No angular floor is ever finer than that,
# whatever the geometry says.
ANGLE_QUANTISATION_DEG = 1.0e-4

# THE NODE IS NOT DEFINED FOR AN EQUATORIAL ORBIT, and it is badly determined
# near one. The orbit plane's orientation is fixed by the direction of its
# angular-momentum vector, and a small rotation of that vector by an angle eps
# shows up as `di = eps` in one direction and `dRAAN sin i = eps` in the other.
# So the well-conditioned coordinate pair is (i, RAAN sin i), and an
# uncertainty of sigma in plane orientation is an uncertainty of sigma / sin i
# in the node. At one degree of inclination that is already a 57-fold
# inflation, and at the geostationary ring, where the inclination is a few
# hundredths of a degree, the published node is very nearly a fitted random
# number. The floor below carries the 1/sin i factor, and the channel is not
# opened at all below this inclination.
NODE_MINIMUM_INCLINATION_DEG = 1.0

# THE ARGUMENT OF PERIGEE IS NOT DEFINED FOR A CIRCLE, for the same kind of
# reason. What the fit actually determines is the eccentricity VECTOR, whose
# components are of size e; the argument of perigee is that vector's direction,
# so a scatter of sigma_e in the vector is a scatter of sigma_e / e radians in
# the angle. The catalogue's measured sigma_e is 4.5e-7 to 1.3e-6, so at
# e = 1e-3 the published argument of perigee is good to about 0.07 deg and at
# e = 1e-5 it is good to nothing at all -- it wanders through hundreds of
# degrees while the orbit does nothing.
#
# The 1/e factor is in the floor, which would in principle be enough. The hard
# cut-off is here as well because below it the problem is no longer the size of
# the error bar but the meaning of the number: the mean element being
# differenced is the direction of a vector shorter than the perturbations that
# move it, and a residual computed from two such directions is not a
# measurement of anything an operator did. 1e-3 is the value: at it the fit
# noise alone is 0.07 deg, and a J2 apsidal rate of a degree a day means the
# residual is dominated by the model rather than by the fit, which is the
# regime the channel is designed for.
ARGP_MINIMUM_ECCENTRICITY = 1.0e-3


# ---------------------------------------------------------------------------
# The opacity gate (mission-speculation-design.md Sections 1.3 to 1.5)
# ---------------------------------------------------------------------------
# Anchored, case-insensitive, and deliberately symmetric with respect to
# nationality: an opaque US object is denied on exactly the same terms as an
# opaque Russian or Chinese one. A rule that stopped only at foreign objects
# would be a rule about sensitivity; this is a rule about evidence, which is
# both defensible in public and simply true.
OPAQUE_NAME_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"^USA[\s-]?\d+",
        r"^TJS[\s-]?\d+",
        r"^COSMOS[\s-]?\d+$",
        r"^SHIYAN\b",
        r"^SY-\d+",
        r"^YAOGAN\b",
        r"^NROL\b",
        r"^OBJECT\s+[A-Z]{1,3}$",
        r"^UNKNOWN\b",
        r"^LUCH\b",
        r"^OLYMP\b",
    )
)


def opacity_denied(name: str | None, sector: str | None, mission: str | None,
                   classification_confidence: str | None) -> bool:
    """True when this object may carry no purpose language of any kind.

    Physics is unaffected: a denied object still gets Delta-v, element deltas,
    the drag share and the cohort context, because those are measurements of an
    orbit rather than claims about a payload. What it never gets is a sentence
    whose grammatical subject is the spacecraft and whose predicate is a
    mission.

    The absence must be indistinguishable from ordinary absence (Section 1.5).
    Callers must not render a badge, a greyed box or a "withheld" label: a
    visible redaction marker is an assessment by implication, and aggregated
    across a catalog it is itself a targeting aid.
    """
    label = (name or "").strip()
    if any(pattern.match(label) for pattern in OPAQUE_NAME_PATTERNS):
        return True
    if sector == "military" and (mission in (None, "", "other")):
        return True
    if sector in (None, "", "unknown") and classification_confidence == "low":
        return True
    return False


# ---------------------------------------------------------------------------
# One interval, with everything needed to judge it
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Interval:
    """One consecutive pair of element sets for one object.

    This is the unit of everything downstream. It is deliberately flat and
    self-contained so the cohort pass can be a single ordered sweep rather than
    one query per object: measured on the live archive, per-object queries cost
    1.54 ms each in v9fs round trips, which is 12 s at catalog scale before the
    archive has any depth at all.
    """

    norad: int
    name: str
    object_type: str
    start_ms: int
    end_ms: int
    span_days: float
    a_start_km: float
    a_end_km: float
    delta_a_km: float
    delta_e: float
    delta_i_deg: float
    eccentricity: float
    inclination_deg: float
    perigee_altitude_km: float
    apogee_altitude_km: float
    bstar: float | None
    mean_motion_rev_per_day: float
    # The node and the apse line. **Optional, and None means "not measured"
    # rather than "did not move".** An Interval built from a row set that
    # predates the angle columns, or by a test that does not care about them,
    # must not be judged on them: `detect_events` opens the two angle channels
    # only when these are present. Wrapped into (-180, 180] at construction,
    # because a node that crosses 360 degrees has not moved 359 degrees.
    raan_deg: float | None = None
    arg_perigee_deg: float | None = None
    delta_raan_deg: float | None = None
    delta_arg_perigee_deg: float | None = None

    @property
    def mid_ms(self) -> int:
        return (self.start_ms + self.end_ms) // 2

    @property
    def regime(self) -> str:
        return orbit_regime(self.a_start_km, self.eccentricity, self.inclination_deg)

    @property
    def angles_measured(self) -> bool:
        return self.delta_raan_deg is not None and self.delta_arg_perigee_deg is not None

    @property
    def j2_drift_deg(self) -> tuple[float, float] | None:
        """Node and apse-line motion this orbit gets for free over this interval."""
        rates_j2 = j2_secular_rates_deg_per_day(
            self.a_start_km, self.eccentricity, self.inclination_deg
        )
        if rates_j2 is None:
            return None
        return rates_j2[0] * self.span_days, rates_j2[1] * self.span_days

    @property
    def raan_residual_deg(self) -> float | None:
        """Node motion left over after the predicted J2 regression is removed.

        THE ONLY QUANTITY THE NODE CHANNEL EVER SEES. A channel fed the raw
        difference would report ordinary nodal regression -- about a degree a
        day in low Earth orbit, against a catalogue scatter of 1e-4 degrees --
        as a ten-thousand-sigma manoeuvre on every object every day, which is
        very much worse than having no channel at all.
        """
        drift = self.j2_drift_deg
        if self.delta_raan_deg is None or drift is None:
            return None
        return self.delta_raan_deg - drift[0]

    @property
    def arg_perigee_residual_deg(self) -> float | None:
        """Apse-line motion left over after the predicted J2 precession is removed."""
        drift = self.j2_drift_deg
        if self.delta_arg_perigee_deg is None or drift is None:
            return None
        return self.delta_arg_perigee_deg - drift[1]


def interval_from_pair(
    norad: int,
    name: str,
    object_type: str,
    first: Sequence[Any],
    second: Sequence[Any],
    *,
    minimum_span_days: float = MINIMUM_SPAN_DAYS,
    max_gap_days: float = 3.0,
) -> Interval | None:
    """Build one Interval from two element-set rows, or None if the pair is unusable.

    ONE construction site, called by both scans. `load_intervals` here and
    `orbit_campaigns.intervals_from_rows` used to hold two hand-copied bodies
    that had to stay field-for-field identical, because the agreement of the
    two detectors is the release's only cross-check and a divergence between
    them would look like a disagreement about the sky rather than a typo. The
    angle columns would have been the third thing to copy; instead there is now
    nothing to copy.

    A row is `(epoch_ms, mean_motion, eccentricity, inclination_deg, bstar)`,
    optionally followed by `(raan_deg, arg_perigee_deg)`. A five-element row is
    an element set read before the angle columns were projected, and produces an
    Interval whose angle channels are simply not opened.
    """
    t0, n0, e0, i0, b0 = first[0], first[1], first[2], first[3], first[4]
    t1, n1 = second[0], second[1]
    span = (t1 - t0) / 86_400_000.0
    if span < minimum_span_days or span > max_gap_days:
        return None
    if n0 <= 0 or n1 <= 0:
        return None
    e1, i1 = second[2], second[3]
    a0 = (MU_WGS72 / (n0 * 2.0 * math.pi / 86400.0) ** 2) ** (1.0 / 3.0)
    a1 = (MU_WGS72 / (n1 * 2.0 * math.pi / 86400.0) ** 2) ** (1.0 / 3.0)
    raan0 = first[5] if len(first) > 6 else None
    argp0 = first[6] if len(first) > 6 else None
    raan1 = second[5] if len(second) > 6 else None
    argp1 = second[6] if len(second) > 6 else None
    delta_raan = None if raan0 is None or raan1 is None else wrap_degrees(raan1 - raan0)
    delta_argp = None if argp0 is None or argp1 is None else wrap_degrees(argp1 - argp0)
    return Interval(
        norad=norad,
        name=name,
        object_type=object_type,
        start_ms=t0,
        end_ms=t1,
        span_days=span,
        a_start_km=a0,
        a_end_km=a1,
        delta_a_km=a1 - a0,
        delta_e=e1 - e0,
        delta_i_deg=i1 - i0,
        eccentricity=e0,
        inclination_deg=i0,
        perigee_altitude_km=a0 * (1.0 - e0) - RE_WGS72,
        apogee_altitude_km=a0 * (1.0 + e0) - RE_WGS72,
        # B* is taken from the FIRST element set of the pair, so the ballistic
        # coefficient used to predict the interval was fitted before it, never
        # after. A manoeuvre that shifts the fitted B* must not be allowed to
        # explain itself away.
        bstar=b0,
        mean_motion_rev_per_day=n0,
        raan_deg=raan0,
        arg_perigee_deg=argp0,
        delta_raan_deg=delta_raan,
        delta_arg_perigee_deg=delta_argp,
    )


def geo_libration_bound_metres(a_km: float, eccentricity: float, span_days: float) -> float:
    """Largest change in semi-major axis triaxial libration alone can produce.

    A property of one orbit — its own semi-major axis and the elapsed time. It
    deliberately does not read the object's longitude, for the same reason
    `lunisolar_inclination_bound_deg` does not read its node: a bound cannot be
    got backwards, and a model can.

    Returns 0 outside the geostationary band, where the resonance does not act.
    """
    if abs(a_km - GEO_SEMI_MAJOR_AXIS_KM) > GEO_BAND_KM or eccentricity >= 0.01:
        return 0.0
    return GEO_TRIAXIALITY_DRIFT_METRES_PER_DAY * max(span_days, 0.0)


def lunisolar_inclination_bound_deg(a_km: float, inclination_deg: float, span_days: float) -> float:
    """Largest inclination change luni-solar gravity alone can produce here.

    A property of one orbit: its own semi-major axis, its own inclination, and
    the elapsed time. Reads nothing about any other object, and deliberately
    reads no node — see the constants above for why the bound is preferred to a
    model.

    Returns 0 below the regime floor, where J2 and drag dominate the plane and
    luni-solar precession is not the story.
    """
    if a_km < LUNISOLAR_REGIME_MINIMUM_SEMI_MAJOR_AXIS_KM or span_days <= 0:
        return 0.0
    omega_per_year = 2.0 * math.pi / LUNISOLAR_PRECESSION_PERIOD_YEARS
    separation_deg = abs(inclination_deg) + LUNISOLAR_POLE_INCLINATION_DEG
    return omega_per_year * separation_deg * (span_days / 365.25)


def orbit_regime(a_km: float, eccentricity: float, inclination_deg: float) -> str:
    """Coarse orbit class, from the elements only.

    Used to pick the right expectation and the right vocabulary, never to say
    anything about a payload.

    NOT A FOURTH COPY OF THE PUBLISHED CLASSIFIER, and deliberately so. The rule
    a visitor reads on a card is `build_release.derive_orbit`, mirrored by
    `catalog_audit.regime_from_elements` and by `classifyOrbit` in src/orbit.ts,
    and those three are pinned together by tests/test_orbit_classifier_parity.py.
    This one answers a different question with a different vocabulary -- it emits
    `near-GEO` and `transfer`, which the site never publishes -- because what it
    is choosing is how to TALK about an event: whether to discuss longitude
    drift and station-keeping, or perigee decay.

    So it takes no IGSO branch, and adding one here would be a regression. Its
    geosynchronous test is inclination-agnostic on purpose, so a BeiDou IGSO,
    NavIC or QZSS craft already answers "GEO" to it -- which is the right answer
    to the question being asked, because an inclined geosynchronous spacecraft
    does keep station in longitude and its events are geosynchronous events.
    """
    perigee = a_km * (1.0 - eccentricity) - RE_WGS72
    apogee = a_km * (1.0 + eccentricity) - RE_WGS72
    if abs(a_km - GEO_SEMI_MAJOR_AXIS_KM) <= GEO_BAND_KM and eccentricity < 0.01:
        return "GEO"
    if eccentricity >= 0.1 and apogee > 25000.0:
        return "HEO"
    if perigee > 25000.0:
        return "near-GEO"
    if apogee <= 2000.0:
        return "LEO"
    if perigee >= 2000.0:
        return "MEO"
    return "transfer"


def j2_secular_rates_deg_per_day(
    a_km: float, eccentricity: float, inclination_deg: float
) -> tuple[float, float] | None:
    """Nodal regression and apsidal precession from J2, in deg/day. None if degenerate.

    The first-order secular rates, which is what the published mean elements
    are fitted to carry:

        dRAAN/dt = -(3/2) n J2 (Re/p)^2 cos i
        dARGP/dt =  (3/4) n J2 (Re/p)^2 (5 cos^2 i - 1)

    with `p = a (1 - e^2)` the semi-latus rectum and `n` the mean motion. Both
    are properties of ONE orbit and read nothing about any other object.

    This is the same physics `orbit_history.j2_secular_rates` applies to an
    `ElementSet`; that function needs a whole element set and this path has
    only the three elements the interval carries, so the rates are expressed
    once here in terms of those three and the two are pinned together by
    `tests/test_orbit_events.py`. `sun_synchronous` was the third copy of the
    nodal half and is now a caller.
    """
    if a_km <= 0 or not (0.0 <= eccentricity < 1.0):
        return None
    p = a_km * (1.0 - eccentricity * eccentricity)
    if p <= 0:
        return None
    from pipeline.orbit_history import J2_WGS72

    n_deg_day = 360.0 * 86400.0 / (2.0 * math.pi) * math.sqrt(MU_WGS72 / a_km**3)
    factor = J2_WGS72 * (RE_WGS72 / p) ** 2
    cos_i = math.cos(math.radians(inclination_deg))
    raan_dot = -1.5 * n_deg_day * factor * cos_i
    argp_dot = 0.75 * n_deg_day * factor * (5.0 * cos_i * cos_i - 1.0)
    return raan_dot, argp_dot


def sun_synchronous(a_km: float, eccentricity: float, inclination_deg: float,
                    tolerance_deg_per_day: float = 0.05) -> bool:
    """Does this orbit's J2 nodal regression track the mean sun?

    A property of a single orbit — it compares the object's own nodal rate
    against a fixed astronomical rate, and reads no other object. The
    sun-synchronous rate is 360 deg / 365.2422 d = +0.9856 deg/day.
    """
    rates_j2 = j2_secular_rates_deg_per_day(a_km, eccentricity, inclination_deg)
    if rates_j2 is None:
        return False
    return abs(rates_j2[0] - 0.9856473) <= tolerance_deg_per_day


def load_intervals(
    connection: sqlite3.Connection,
    *,
    since_ms: int | None = None,
    until_ms: int | None = None,
    minimum_span_days: float = MINIMUM_SPAN_DAYS,
    max_gap_days: float = 3.0,
) -> list[Interval]:
    """Every usable consecutive pair in the archive, in one ordered sweep.

    One query for the objects and one ordered scan of the element sets. Rebuilt
    per object in memory rather than with a query per object, for the v9fs
    reason in `Interval`'s docstring.

    The scan is paged by `orbit_history.paged_element_sets`, so it releases the
    archive between pages rather than holding a SHARED lock for its whole
    length; the reason is the capture starvation documented under CONTENTION in
    `pipeline/orbit_history.py`. `build_bundles` calls this in the same run as
    `orbit_campaigns.scan_archive`, so leaving it as one statement would have
    left a second multi-minute lock behind after fixing the first.

    `since_ms` and `until_ms` moved out of SQL and into Python with that change,
    and the result is identical. There is no index on `epoch_ms`, so the clause
    never chose the access path - it was always the same full ordered walk with
    a filter on top. It cannot stay in SQL under paging, because `LIMIT` counts
    rows that survive the filter: a 45-day window over a 22-year archive would
    make one "page" scan most of the table to find its quota, which is the very
    thing the paging exists to prevent.
    """
    facts = {
        row[0]: (row[1] or f"OBJECT {row[0]}", row[2] or "UNKNOWN")
        for row in connection.execute("SELECT norad, name, object_type FROM object")
    }

    out: list[Interval] = []
    current: int | None = None
    buffer: list[tuple] = []

    def flush() -> None:
        if current is None or len(buffer) < 2:
            return
        name, object_type = facts.get(current, (f"OBJECT {current}", "UNKNOWN"))
        for first, second in zip(buffer, buffer[1:]):
            built = interval_from_pair(
                current,
                name,
                object_type,
                first,
                second,
                minimum_span_days=minimum_span_days,
                max_gap_days=max_gap_days,
            )
            if built is not None:
                out.append(built)

    for row in paged_element_sets(connection, columns=SCAN_COLUMNS_WITH_ANGLES):
        norad, epoch_ms, mm_q, ecc_q, inc_q, bstar_q, raan_q, argp_q = row
        if norad != current:
            flush()
            current, buffer = norad, []
        if since_ms is not None and epoch_ms < since_ms:
            continue
        if until_ms is not None and epoch_ms > until_ms:
            continue
        buffer.append(
            (
                epoch_ms,
                mm_q / 1e8,
                ecc_q / 1e8,
                inc_q / 1e4,
                None if bstar_q is None else bstar_q / 1e12,
                raan_q / 1e4,
                argp_q / 1e4,
            )
        )
    flush()
    out.sort(key=lambda interval: (interval.norad, interval.start_ms))
    return out


# ---------------------------------------------------------------------------
# The cohort: an anonymous statistical population, never a set of neighbours
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class CohortStatistic:
    """A population summary. Deliberately carries no identity of any member.

    There is no `members` field and no accessor that could grow one. This is
    the structural half of the object-to-object exclusion in
    `docs/mission-speculation-design.md` Section 1.6: a capability that has no
    function to call cannot be invoked by a later refactor.
    """

    count: int
    median: float
    scale: float
    screened: bool


class CohortIndex:
    """Time-and-perigee index supporting the +/-25 km, +/-2 deg cohort query.

    The first index was sorted only by perigee. It bisected the altitude range,
    then checked time overlap one candidate at a time. That looked O(N log N)
    on the few-hour cohort it was written against, but widening the intended
    window to seven real days exposed the inner scan: every interval walked all
    seven days in its altitude band. Time buckets make overlap a lookup
    dimension while the exact overlap predicate below preserves membership.
    """

    def __init__(self, intervals: Sequence[Interval]) -> None:
        self._intervals = sorted(intervals, key=lambda i: i.perigee_altitude_km)
        self._perigees = [i.perigee_altitude_km for i in self._intervals]
        # A candidate participates in many neighbouring intervals' cohorts.
        # Its natural-floor-normalised element changes are properties of that
        # candidate alone, so calculate each once rather than repeating the J2
        # and noise-floor arithmetic for every neighbour that asks for it.
        self._normalised: dict[str, dict[int, float | None]] = {}
        self._bucket_ms = COHORT_TIME_BUCKET_HOURS * 3_600_000
        grouped: list[dict[int, list[Interval]]] = [
            {} for _ in range(len(COHORT_DURATION_CLASS_HOURS) + 1)
        ]
        self._duration_class_max_ms = [
            hours * 3_600_000 for hours in COHORT_DURATION_CLASS_HOURS
        ] + [0]
        for interval in intervals:
            duration_ms = interval.end_ms - interval.start_ms
            duration_class = next(
                (
                    index
                    for index, hours in enumerate(COHORT_DURATION_CLASS_HOURS)
                    if duration_ms <= hours * 3_600_000
                ),
                len(COHORT_DURATION_CLASS_HOURS),
            )
            self._duration_class_max_ms[duration_class] = max(
                self._duration_class_max_ms[duration_class], duration_ms
            )
            bucket = interval.start_ms // self._bucket_ms
            grouped[duration_class].setdefault(bucket, []).append(interval)
        self._time_buckets: list[
            dict[int, tuple[list[Interval], list[float]]]
        ] = []
        for duration_group in grouped:
            built: dict[int, tuple[list[Interval], list[float]]] = {}
            for bucket, members in duration_group.items():
                ordered = sorted(members, key=lambda i: i.perigee_altitude_km)
                built[bucket] = (
                    ordered,
                    [i.perigee_altitude_km for i in ordered],
                )
            self._time_buckets.append(built)

    def normalised_deviation(self, interval: Interval, element: str) -> float | None:
        cache = self._normalised.setdefault(element, {})
        identity = id(interval)
        if identity not in cache:
            cache[identity] = normalised_deviation(interval, element)
        return cache[identity]

    def prime_normalised(self, elements: Iterable[str]) -> None:
        """Fill immutable candidate values before a fork can share their pages."""
        for element in elements:
            if len(self._normalised.get(element, {})) == len(self._intervals):
                continue
            self._normalised[element] = {
                id(interval): normalised_deviation(interval, element)
                for interval in self._intervals
            }

    def _window(
        self,
        interval: Interval,
        ignore_inclination: bool = False,
        overlap_only: bool = True,
    ) -> Iterable[Interval]:
        def timed_sources() -> Iterable[tuple[list[Interval], list[float]]]:
            for buckets, maximum_duration_ms in zip(
                self._time_buckets, self._duration_class_max_ms
            ):
                first = (interval.start_ms - maximum_duration_ms) // self._bucket_ms
                last = (interval.end_ms - 1) // self._bucket_ms
                for bucket in range(first, last + 1):
                    source = buckets.get(bucket)
                    if source is not None:
                        yield source

        sources = (
            timed_sources()
            if overlap_only
            else iter(((self._intervals, self._perigees),))
        )
        for members, perigees in sources:
            low = bisect_left(
                perigees,
                interval.perigee_altitude_km - COHORT_PERIGEE_TOLERANCE_KM,
            )
            high = bisect_right(
                perigees,
                interval.perigee_altitude_km + COHORT_PERIGEE_TOLERANCE_KM,
            )
            for candidate in members[low:high]:
                if candidate.norad == interval.norad:
                    continue
                if not ignore_inclination and (
                    abs(candidate.inclination_deg - interval.inclination_deg)
                    > COHORT_INCLINATION_TOLERANCE_DEG
                ):
                    continue
                yield candidate

    def statistic(
        self,
        interval: Interval,
        value: Any,
        *,
        floor: float = 0.0,
        overlap_only: bool = True,
        ignore_inclination: bool = False,
    ) -> CohortStatistic | None:
        """Median and robust scale of `value` across the cohort, or None.

        `value` is a callable taking an Interval. `overlap_only` requires the
        cohort member's interval to overlap this one in time, which is what
        makes the screen a control for *this moment* — a storm, a catalog
        re-fit or a tracking outage all act on a window, and a cohort drawn
        from a different window would not see them.
        """
        return self.statistics(
            interval,
            {"value": (value, floor, ignore_inclination)},
            overlap_only=overlap_only,
        ).get("value")

    def statistics(
        self,
        interval: Interval,
        specifications: dict[str, tuple[Any, float, bool]],
        *,
        overlap_only: bool = True,
    ) -> dict[str, CohortStatistic | None]:
        """Several cohort statistics from one exact population walk.

        Each specification is ``(value, scale_floor, ignore_inclination)``.
        Drag deliberately uses the whole altitude shell while element channels
        use the inclination band, but their time/perigee candidates are the
        same. Walking that set once keeps the real seven-day release window
        affordable without changing a single cohort member or statistic.
        """
        samples: dict[str, list[float]] = {name: [] for name in specifications}
        for candidate in self._window(
            interval, ignore_inclination=True, overlap_only=overlap_only
        ):
            if overlap_only and not (
                candidate.start_ms < interval.end_ms and candidate.end_ms > interval.start_ms
            ):
                continue
            inclination_close = (
                abs(candidate.inclination_deg - interval.inclination_deg)
                <= COHORT_INCLINATION_TOLERANCE_DEG
            )
            for name, (value, _floor, ignore_inclination) in specifications.items():
                if not ignore_inclination and not inclination_close:
                    continue
                sample = value(candidate)
                if sample is None or sample != sample:
                    continue
                samples[name].append(sample)

        result: dict[str, CohortStatistic | None] = {}
        for name, (_value, floor, _ignore_inclination) in specifications.items():
            values = samples[name]
            if len(values) < COHORT_MINIMUM:
                result[name] = None
                continue
            median = statistics.median(values)
            mad = statistics.median([abs(sample - median) for sample in values]) * 1.4826
            result[name] = CohortStatistic(
                count=len(values),
                median=median,
                scale=max(mad, floor) if mad == mad else floor,
                screened=len(values) >= COHORT_PREFERRED,
            )
        return result


# ---------------------------------------------------------------------------
# Drag, predicted from the population and the object's own ballistic coefficient
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class DragPrediction:
    """How much of the observed change in `a` the atmosphere accounts for."""

    applicable: bool
    reason: str
    predicted_delta_a_metres: float
    # Uncertainty in that prediction, in metres: the cohort's own robust spread
    # in specific decay rate, carried through this object's B* and this span.
    # A prediction without it is a prediction claimed to arbitrary precision,
    # and the difference between the two is the difference between "drag
    # accounts for this" and "here is a false manoeuvre".
    sigma_metres: float
    specific_rate_km_per_day: float | None   # cohort median of adot / B*
    cohort_count: int
    bstar: float | None


def _specific_decay_rate(candidate: Interval) -> float | None:
    if candidate.bstar is None or candidate.bstar < MINIMUM_USABLE_BSTAR:
        return None
    return (candidate.delta_a_km / candidate.span_days) / candidate.bstar


def predict_drag(
    interval: Interval,
    index: CohortIndex,
    *,
    cohort_statistics: dict[str, CohortStatistic | None] | None = None,
) -> DragPrediction:
    """Predicted drag-only change in `a` over this interval, in metres.

    The physics: `adot_drag = -(C_D A / m) rho sqrt(mu a)` and B* is
    proportional to `C_D A / m`, so `adot / B*` depends on the atmosphere and
    the altitude but not on what the object is made of. Take the **cohort
    median** of that specific rate — the atmosphere the shell actually flew
    through, measured rather than modelled — and multiply it back by this
    object's own B*.

    The cohort median is used rather than the mean because a shell containing a
    manoeuvring payload would otherwise have its atmosphere estimated partly
    from a burn.
    """
    if interval.perigee_altitude_km > DRAG_MODEL_CEILING_KM:
        return DragPrediction(False, "above-drag-regime", 0.0, 0.0, None, 0, interval.bstar)
    if interval.bstar is None:
        return DragPrediction(False, "no-fitted-bstar", 0.0, 0.0, None, 0, None)
    if interval.bstar < MINIMUM_USABLE_BSTAR:
        # Includes the negative B* the fit sometimes produces for an object
        # whose recent arc was dominated by a burn. Reporting a prediction from
        # it would be reporting the manoeuvre as the atmosphere.
        return DragPrediction(False, "bstar-not-usable", 0.0, 0.0, None, 0, interval.bstar)

    # The drag cohort deliberately ignores inclination. Neutral density is
    # overwhelmingly a function of altitude and of the state of the
    # thermosphere; the latitude band an orbit samples is a second-order
    # correction to it, worth perhaps tens of percent. The manoeuvre screen
    # keeps the inclination constraint because there it separates operational
    # populations; the drag model drops it because it buys cohort members at
    # altitudes where they are scarce, and members are what the estimate needs.
    statistic = (
        index.statistic(
            interval, _specific_decay_rate, overlap_only=True, ignore_inclination=True
        )
        if cohort_statistics is None
        else cohort_statistics.get("drag")
    )
    if statistic is None:
        return DragPrediction(False, "cohort-too-small", 0.0, 0.0, None, 0, interval.bstar)
    predicted_km = statistic.median * interval.bstar * interval.span_days
    sigma_km = abs(statistic.scale * interval.bstar * interval.span_days)
    return DragPrediction(
        applicable=True,
        reason="cohort-specific-decay",
        predicted_delta_a_metres=predicted_km * 1000.0,
        sigma_metres=sigma_km * 1000.0,
        specific_rate_km_per_day=statistic.median,
        cohort_count=statistic.count,
        bstar=interval.bstar,
    )


# ---------------------------------------------------------------------------
# Delta-v
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class DeltaV:
    """The cost of the change, decomposed. Every figure is a LOWER bound.

    Lower bounds because each is the cheapest manoeuvre that could produce the
    observed element change: a real burn in any other direction, at any other
    point in the orbit, or spread over a finite arc costs more. Saying so is
    the honest framing and it is also the useful one — "at least 12 m/s" is a
    floor on what the operator spent.
    """

    tangential: float          # m/s, from the drag-corrected change in a
    # m/s, from the rotation of the orbit PLANE -- inclination and node
    # together, because they are two coordinates of one rotation and charging
    # for them separately would bill an operator twice for one burn.
    plane_change: float
    eccentricity: float        # m/s, from the change in e
    total: float               # m/s, in-plane and out-of-plane combined
    drag_removed_metres: float
    propulsive_delta_a_metres: float
    # None when the cost is physically possible; otherwise why it is not, in
    # words a reader can check. See physical_ceiling() below.
    implausible: str | None = None
    # None when the cost is one a spacecraft plausibly spends; otherwise why it
    # is not. A JUDGEMENT, not a law -- it flags and never drops.
    beyond_routine: str | None = None
    # m/s, from the rotation of the apse line inside the orbit plane. Appended
    # rather than inserted: the constructor is called positionally in the tests
    # that pin the arithmetic, and moving a field would silently re-map them.
    apsidal: float = 0.0
    # The plane rotation `plane_change` was charged for, in degrees. Published
    # because a reader given only a cost in m/s cannot tell a large rotation of
    # a slow orbit from a small rotation of a fast one.
    plane_rotation_deg: float = 0.0


# The largest burn a spacecraft routinely performs, in m/s. Named rather than
# inlined because it is a judgement someone may want to revisit, and a bare
# 2000.0 inside an if-statement hides that it is one.
ROUTINE_MANOEUVRE_CEILING_MS = 2000.0


def plane_rotation_deg(
    inclination_from_deg: float, inclination_to_deg: float, delta_raan_deg: float
) -> float:
    """The angle the orbit plane turned through, from the two elements that fix it.

    Spherical trigonometry on the angular-momentum unit vectors, derived in
    `delta_v`'s docstring:

        cos theta = cos i1 cos i2 + sin i1 sin i2 cos dRAAN.

    **Evaluated as a half-angle, not as an arccosine.** Rearranged with
    `1 - cos x = 2 sin^2(x/2)` twice, that identity becomes

        sin^2(theta/2) = sin^2(di/2) + sin i1 sin i2 sin^2(dRAAN/2)

    which is the same angle and a different computation. It matters: the
    arccosine form asks for `acos` of a number that is 1 minus a rounding
    error when nothing rotated, and returns about a microdegree of rotation
    out of thin air -- which then bills an operator 4.6e-05 m/s for a plane
    change that did not happen, on every event whose plane channels did not
    trip. The half-angle form returns exactly zero for exactly zero, and
    exactly `|di|` when the node did not move.

    Kept separate from the cost so it can be tested against its two closed-form
    limits directly, and so a caller that wants the geometry without the
    propulsion can have it.
    """
    i1 = math.radians(inclination_from_deg)
    i2 = math.radians(inclination_to_deg)
    half_inclination = math.sin(math.radians(inclination_to_deg - inclination_from_deg) / 2.0)
    half_node = math.sin(math.radians(delta_raan_deg) / 2.0)
    sin_half_theta_squared = (
        half_inclination * half_inclination
        + math.sin(i1) * math.sin(i2) * half_node * half_node
    )
    sin_half_theta = math.sqrt(max(sin_half_theta_squared, 0.0))
    return 2.0 * math.degrees(math.asin(min(sin_half_theta, 1.0)))


def delta_v(interval: Interval, drag: DragPrediction, tests: Sequence[ChannelTest]) -> DeltaV:
    """Decompose the interval into what a propulsion system would have to spend.

    * **Tangential.** For a near-circular orbit a tangential burn changes `a`
      by `da = 2 dv / n`, so `dv = n da / 2` with `n` in rad/s and `da` in
      metres. `da` here is the observed change *minus* the drag prediction,
      which is the whole point of `predict_drag`.
    * **Plane change.** Rotating the orbit plane through an angle `theta`
      costs `dv = 2 V sin(theta/2)`, because the cheapest way to change a
      velocity vector's direction by `theta` without changing its magnitude is
      an impulse forming the third side of an isosceles triangle. It is
      evaluated at **apogee**, where `V` is smallest and the rotation is
      cheapest, so the figure is a true lower bound. For a circular orbit
      apogee speed is the circular speed and the two coincide.

      `theta` is derived, not assumed, and it is the rotation of the whole
      plane rather than the change in inclination alone. The orbit plane's
      orientation is the direction of its angular-momentum unit vector

          h(i, RAAN) = (sin i sin RAAN, -sin i cos RAAN, cos i)

      so for two orbits differing in both elements

          cos theta = h1 . h2 = cos i1 cos i2 + sin i1 sin i2 cos dRAAN.

      Two limits check it. With `dRAAN = 0` this collapses to
      `cos theta = cos(i2 - i1)`, so `theta = |di|` and the cost is exactly
      what this function charged before the node channel existed -- the
      inclination-only arithmetic is unchanged to the last decimal. With
      `di = 0` it gives `cos theta = 1 - 2 sin^2 i sin^2(dRAAN/2)`, hence

          sin(theta/2) = |sin i| |sin(dRAAN/2)|   and   dv = 2 V sin i sin(dRAAN/2),

      which for small angles is the familiar `dv = V dRAAN sin i`: a node
      change is free at the poles, where the planes already coincide, and
      costs a full plane change at the equator. **This is a lower bound twice
      over**: the burn is charged at apogee, and the two planes intersect on a
      line that is in general nowhere near apogee, so a real single-impulse
      node change costs more than this and a real one spread over an arc costs
      more again.
    * **Eccentricity.** A tangential burn at an apsis changes `e` by
      `de = 2 dv / V`, so `dv = V de / 2`.
    * **Apse line.** Rotating the ellipse inside its own plane through `dw`,
      holding `a` and `e` fixed. Two such ellipses cross where their radii
      agree; with true anomalies `nu1` and `nu2 = nu1 - dw` measured from their
      own perigees, `r` depends on `cos nu`, so they cross at `nu1 = dw/2` and
      `nu2 = -dw/2`. There the transverse velocity `sqrt(mu/p)(1 + e cos nu)`
      is identical on both orbits -- `cos nu` is even -- while the radial
      velocity `sqrt(mu/p) e sin nu` is equal and opposite. The impulse is
      therefore purely radial and

          dv = 2 e sqrt(mu / p) |sin(dw/2)|,      p = a (1 - e^2).

      It vanishes as `e -> 0`, which is right: a circle has no apse line to
      rotate. It is expensive on an eccentric orbit -- a single degree on a
      Molniya ellipse is about 74 m/s -- which is exactly why a Molniya orbit
      is flown at the critical inclination and lets J2 leave its apse line
      alone rather than paying to hold it.

    The total combines the in-plane and out-of-plane parts in quadrature,
    because they are orthogonal, and takes the **largest** of the three
    in-plane figures rather than their sum, because one burn changes several
    elements at once — adding them would charge one burn several times.
    """
    # **Only channels that cleared the bar contribute to the cost.** An
    # inclination residual that failed its own significance test is not
    # evidence of a plane change, and letting it into the Delta-v total means
    # publishing a cost for something the detector just declined to claim. This
    # was not hypothetical: an apogee kick motor abandoned at geostationary
    # altitude was reported at 0.11 m/s, of which 0.1115 came from an
    # inclination residual that never tripped, while the tangential part it was
    # actually flagged on was 0.005 m/s.
    residuals = {test.element: test.delta for test in tests if test.tripped}
    a_km = interval.a_start_km
    n_rad_s = math.sqrt(MU_WGS72 / a_km**3)
    drag_metres = drag.predicted_delta_a_metres if drag.applicable else 0.0
    # Every figure below is built from the RESIDUAL after the natural
    # perturbation has been subtracted, never from the raw element difference.
    # Charging an operator for the luni-solar drift of a satellite that has
    # been dead since the 1970s is the specific mistake this indirection
    # prevents.
    propulsive_metres = residuals.get("semiMajorAxis", 0.0)
    residual_inclination_deg = residuals.get("inclination", 0.0)
    residual_eccentricity = residuals.get("eccentricity", 0.0)
    residual_raan_deg = residuals.get("raan", 0.0)
    residual_arg_perigee_deg = residuals.get("argPerigee", 0.0)
    # The observed-minus-drag figure is still reported, because it is the
    # measurement, and a reader wants it whether or not it cleared a threshold.
    observed_minus_drag = interval.delta_a_km * 1000.0 - drag_metres

    tangential = 0.5 * n_rad_s * propulsive_metres

    apogee_km = a_km * (1.0 + interval.eccentricity)
    speed_at_apogee = math.sqrt(max(MU_WGS72 * (2.0 / apogee_km - 1.0 / a_km), 0.0)) * 1000.0
    rotation_deg = plane_rotation_deg(
        interval.inclination_deg,
        interval.inclination_deg + residual_inclination_deg,
        residual_raan_deg,
    )
    plane = 2.0 * speed_at_apogee * math.sin(math.radians(rotation_deg) / 2.0)

    circular_speed = math.sqrt(MU_WGS72 / a_km) * 1000.0
    ecc = 0.5 * circular_speed * abs(residual_eccentricity)

    semi_latus_rectum_km = a_km * (1.0 - interval.eccentricity * interval.eccentricity)
    transverse_speed = (
        math.sqrt(MU_WGS72 / semi_latus_rectum_km) * 1000.0
        if semi_latus_rectum_km > 0
        else 0.0
    )
    apsidal = (
        2.0
        * interval.eccentricity
        * transverse_speed
        * abs(math.sin(math.radians(residual_arg_perigee_deg) / 2.0))
    )

    in_plane = max(abs(tangential), ecc, apsidal)
    total = math.hypot(in_plane, plane)

    # THE PHYSICAL SCREEN, AND WHAT IT IS NOT. Reversing the velocity vector
    # outright costs 2V, but that is NOT the most an impulse can do to a bound
    # orbit: what has to stay below escape is the FINAL speed, not the impulse,
    # so the true single-impulse supremum at radius r is v(r) + v_esc(r) =
    # (1 + sqrt 2) * v(r) ~= 2.414 * v(r), reached by reversing the velocity and
    # then adding up to escape speed the other way. At r = 7,000 km that is
    # 18.22 km/s against this screen's 15.09 km/s.
    #
    # So 2 x the perigee speed is a SCREEN set about 21 per cent inside the true
    # bound, not the bound itself. It is kept there because no real spacecraft
    # manoeuvre approaches even twice orbital speed, so a priced total above it
    # is an element pair that does not describe one orbit rather than an
    # expensive burn. Two further reasons it is a heuristic and not a bound:
    # the total below is a hypot of components priced at three different points
    # in the orbit (tangential and eccentricity at circular speed, plane change
    # at apogee) while the ceiling is evaluated at perigee, and each component
    # is itself a cheapest-case figure. Corrected 2026-09-21 after an
    # adversarial physics review; the constant is unchanged.
    perigee_km = a_km * (1.0 - interval.eccentricity)
    speed_at_perigee = math.sqrt(max(MU_WGS72 * (2.0 / perigee_km - 1.0 / a_km), 0.0)) * 1000.0
    ceiling = 2.0 * speed_at_perigee
    implausible = None
    if ceiling > 0.0 and total > ceiling:
        implausible = (
            f"{total:,.0f} m/s exceeds {ceiling:,.0f} m/s, twice the speed at perigee -- a "
            "screen set inside the true single-impulse ceiling of about 2.414x that speed. "
            "The element pair does not describe one orbit."
        )

    # A GTO-to-GEO apogee kick, the largest burn a communications satellite
    # routinely performs, is about 1,500-1,800 m/s. Above 2,000 m/s in a single
    # interval is therefore outside routine operations -- which is a claim about
    # spacecraft, not about physics, so it is reported rather than enforced.
    beyond_routine = None
    if implausible is None and total > ROUTINE_MANOEUVRE_CEILING_MS:
        beyond_routine = (
            f"{total:,.0f} m/s is larger than any routine manoeuvre. A GTO-to-GEO apogee "
            "kick, the largest burn a communications satellite normally performs, is about "
            "1,800 m/s. Real transfer burns do reach this range; so do element pairs that "
            "should not have been compared."
        )

    return DeltaV(
        tangential=tangential,
        plane_change=plane,
        eccentricity=ecc,
        total=total,
        drag_removed_metres=drag_metres,
        propulsive_delta_a_metres=observed_minus_drag,
        implausible=implausible,
        beyond_routine=beyond_routine,
        apsidal=apsidal,
        plane_rotation_deg=rotation_deg,
    )


# ---------------------------------------------------------------------------
# Significance, against the cohort and against the catalogue floor
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ChannelTest:
    # "semiMajorAxis" | "inclination" | "eccentricity" | "raan" | "argPerigee"
    element: str
    # metres for a, degrees for i, raan and argPerigee, dimensionless for e.
    # For the two angles this is the residual AFTER the predicted J2 secular
    # drift, never the raw element difference.
    delta: float
    floor_sigma: float    # the measured catalogue scatter, same units
    floor_z: float
    cohort_z: float | None
    cohort_count: int
    cohort_screened: bool
    tripped: bool
    # What the expectation was measured against. "cohort" means other objects
    # at the same altitude and inclination over the same hours; "self-history"
    # means this object's own recent intervals, which is what
    # `pipeline/orbit_campaigns.py` uses once an object has enough history.
    # It travels with the test rather than being inferred by the reader,
    # because the two answer materially different questions and a card that
    # said only "z = 47" would leave a visitor unable to tell which.
    basis: str = "cohort"
    reason: str | None = None


def node_natural_floor_deg(interval: Interval) -> float:
    """The largest node residual that needs no propulsion at all, in degrees.

    Two terms, whichever dominates.

    **The fit.** What the catalogue determines is the direction of the orbit's
    angular-momentum vector. Resolve a small rotation of that vector into the
    two orthogonal directions it can go and one of them is `di` while the other
    is `dRAAN sin i`, so an uncertainty `sigma` in plane orientation is an
    uncertainty `sigma / sin i` in the node. The measured plane-orientation
    scatter is the inclination floor in `CATALOGUE_NOISE_FLOOR`; sqrt(2)
    because an interval differences two independent element sets.

    **The model.** The residual this channel tests is what is left after the
    predicted J2 nodal regression is removed, so the error in that prediction
    is part of the floor. It is bounded by `J2_SECULAR_MODEL_RELATIVE_ERROR`
    times the drift that was removed -- the neglected terms are smaller than
    the retained ones by a further factor of order J2 -- and it grows with the
    drift, which is exactly where the model is least trustworthy.

    **The Moon and the Sun.** Above `LUNISOLAR_REGIME_MINIMUM_SEMI_MAJOR_AXIS_KM`
    the J2 model is not the whole story of the plane, and a residual against it
    would be a measurement of third-body gravity. `lunisolar_inclination_bound_deg`
    already bounds how far third bodies can tip the plane over this span, by
    the triangle inequality and with no reference to the node; the same
    geometry that puts `1/sin i` in the fit term converts that plane-orientation
    bound into a node bound. Below the regime floor it returns zero and this
    term does nothing.
    """
    _, _, floor_i = noise_floor_for(interval.perigee_altitude_km)
    sin_i = abs(math.sin(math.radians(interval.inclination_deg)))
    sin_i = max(sin_i, math.sin(math.radians(NODE_MINIMUM_INCLINATION_DEG)))
    fit = max(floor_i, ANGLE_QUANTISATION_DEG) / sin_i * math.sqrt(2.0)
    drift = interval.j2_drift_deg
    model = 0.0 if drift is None else J2_SECULAR_MODEL_RELATIVE_ERROR * abs(drift[0])
    third_body = lunisolar_inclination_bound_deg(
        interval.a_start_km, interval.inclination_deg, interval.span_days
    ) / sin_i
    return max(fit, model, third_body)


def apsis_natural_floor_deg(interval: Interval) -> float:
    """The largest apse-line residual that needs no propulsion at all, in degrees.

    The same two terms. The fit term is `sigma_e / e` radians rather than
    `sigma_i / sin i`, because what the catalogue determines is the
    eccentricity VECTOR and the argument of perigee is its direction: a scatter
    of `sigma_e` in a vector of length `e` is a scatter of `sigma_e / e` in its
    heading. That is why the floor grows without bound as the orbit becomes
    circular, and why `ARGP_MINIMUM_ECCENTRICITY` closes the channel entirely
    below a point where even the floor stops meaning anything.

    The third term is the Moon and the Sun, and it is the one place in this
    function where a bound is BORROWED rather than derived. Above the
    luni-solar regime floor the third-body quadrupole rotates the eccentricity
    vector as well as the plane, and it does so at a rate of the same order --
    the two coefficients differ by factors of order one, not by orders of
    magnitude, and near the critical inclination, where J2 leaves the apse line
    almost alone, third-body gravity is what actually moves it. So
    `lunisolar_inclination_bound_deg` is applied to the apse line as well. It
    is a generous bound rather than an exact one, deliberately: a channel that
    is going to be wrong about a high orbit must be wrong in the direction of
    refusing to claim.
    """
    _, floor_e, _ = noise_floor_for(interval.perigee_altitude_km)
    eccentricity = max(interval.eccentricity, ARGP_MINIMUM_ECCENTRICITY)
    fit = max(math.degrees(floor_e / eccentricity), ANGLE_QUANTISATION_DEG) * math.sqrt(2.0)
    drift = interval.j2_drift_deg
    model = 0.0 if drift is None else J2_SECULAR_MODEL_RELATIVE_ERROR * abs(drift[1])
    third_body = lunisolar_inclination_bound_deg(
        interval.a_start_km, interval.inclination_deg, interval.span_days
    )
    return max(fit, model, third_body)


def natural_floor(interval: Interval, element: str) -> float:
    """The largest change in this element that needs no propulsion at all.

    Sources, whichever dominates: the catalogue's own measured fit scatter, the
    luni-solar precession of the plane, the triaxial libration of the
    geostationary ring, and -- for the two angle channels, whose input is
    already a residual -- the error in the J2 model that produced that
    residual. All of them are bounds rather than models, all of them are
    properties of this one orbit, and each is derived where it is defined
    above.
    """
    floor_a, floor_e, floor_i = noise_floor_for(interval.perigee_altitude_km)
    if element == "semiMajorAxis":
        return max(
            floor_a * 1000.0 * math.sqrt(2.0),
            geo_libration_bound_metres(
                interval.a_start_km, interval.eccentricity, interval.span_days
            ),
        )
    if element == "inclination":
        return max(
            floor_i * math.sqrt(2.0),
            lunisolar_inclination_bound_deg(
                interval.a_start_km, interval.inclination_deg, interval.span_days
            ),
        )
    if element == "raan":
        return node_natural_floor_deg(interval)
    if element == "argPerigee":
        return apsis_natural_floor_deg(interval)
    return floor_e * math.sqrt(2.0)


def _raw_delta(interval: Interval, element: str) -> float | None:
    if element == "semiMajorAxis":
        return interval.delta_a_km * 1000.0
    if element == "inclination":
        return interval.delta_i_deg
    # The two angle channels are fed the J2 residual and never the raw
    # difference, at every point they are read -- including here, which is what
    # the cohort statistic is built from. A cohort of raw nodal differences
    # would be a cohort of nodal regressions, and its median would be a
    # regression rate rather than a shared model error.
    if element == "raan":
        return interval.raan_residual_deg
    if element == "argPerigee":
        return interval.arg_perigee_residual_deg
    return interval.delta_e


def normalised_deviation(interval: Interval, element: str) -> float | None:
    """How far this object moved, in units of what it could have moved for free.

    Dimensionless, and therefore comparable across objects whose element sets
    are spaced differently — which is the whole reason it exists. The first
    version of the cohort screen compared raw per-day RATES, and an interval
    spanning twenty minutes turns a metre of fit noise into kilometres per day.
    A handful of those in a shell set the population's robust scale and the
    screen silently stopped working for every object in it.
    """
    floor = natural_floor(interval, element)
    if floor <= 0:
        return None
    delta = _raw_delta(interval, element)
    if delta is None:
        return None
    return delta / floor


def _channel(
    interval: Interval,
    index: CohortIndex,
    *,
    element: str,
    observed: float,
    kappa: float,
    physical_expectation: float | None = None,
    expectation_sigma: float = 0.0,
    cohort_statistics: dict[str, CohortStatistic | None] | None = None,
) -> ChannelTest:
    """One element's test: against the measured floor and against the cohort.

    **Nothing is ever tested against zero.** That is the single most important
    line in this function, and it is the same lesson `detect_manoeuvres` learned
    in `orbit_history.py`: every element of a real orbit drifts secularly under
    perturbations nobody commanded, and a test against zero reports the
    perturbation as a burn on every interval.

    Concretely, and this was caught by running the first version of this module
    against the live archive: luni-solar gravity tips a geostationary orbit's
    plane by roughly 0.85 deg/year, which is 0.0023 deg/day. Tested against
    zero, that natural drift is a 17-sigma inclination "event" on every
    geostationary object every day — and the first run duly reported
    north-south station-keeping on INTELSAT 4-F1, launched in 1971 and dead for
    decades, and on an apogee kick motor. The expectation therefore comes from
    the **cohort median**: objects at the same altitude and inclination feel the
    same luni-solar torque, so the population's own median rate is the natural
    drift, measured rather than modelled, and what is left over is what this one
    object did that its neighbours did not.

    For semi-major axis there is a better expectation than the cohort median —
    the drag prediction, which uses this object's own ballistic coefficient —
    and `physical_expectation` carries it when it exists.

    `expectation_sigma` is the uncertainty **in the expectation itself**, in the
    same absolute units. It matters: a prediction of 104 m of decay from a
    cohort whose specific rates scatter by 40% is not a prediction good to a
    millimetre, and treating it as one turns the drag model's own scatter into
    manoeuvres. The first run did exactly that on a FENGYUN 1C fragment.
    """
    floor_sigma = natural_floor(interval, element)

    # The cohort is compared in units of each member's OWN natural floor, so a
    # member with a longer or shorter gap between element sets contributes on
    # equal terms. Scale floored at 1, because a population that all sat inside
    # its own noise has a robust scale of zero and would make every deviation
    # infinite.
    statistic = (
        index.statistic(
            interval,
            lambda candidate: index.normalised_deviation(candidate, element),
            floor=1.0,
            overlap_only=True,
        )
        if cohort_statistics is None
        else cohort_statistics.get(element)
    )
    cohort_z: float | None = None
    count = 0
    screened = False
    cohort_expectation = 0.0
    own = normalised_deviation(interval, element)
    if statistic is not None and statistic.scale > 0 and own is not None:
        count = statistic.count
        screened = statistic.screened
        cohort_z = (own - statistic.median) / statistic.scale
        cohort_expectation = statistic.median * natural_floor(interval, element)

    expected = (
        physical_expectation if physical_expectation is not None else cohort_expectation
    )
    residual = observed - expected
    sigma = math.hypot(floor_sigma, expectation_sigma)
    floor_z = residual / sigma if sigma > 0 else 0.0

    tripped = abs(floor_z) > kappa and (cohort_z is None or abs(cohort_z) > kappa)
    return ChannelTest(
        element=element,
        delta=residual,
        floor_sigma=sigma,
        floor_z=floor_z,
        cohort_z=cohort_z,
        cohort_count=count,
        cohort_screened=screened,
        tripped=tripped,
    )


# ---------------------------------------------------------------------------
# What kind of change was it
# ---------------------------------------------------------------------------
SIGNATURES = (
    "re-entry-decay",
    "drag-and-thrust-not-separable",
    "drag-decay",
    "drag-make-up",
    "along-track-raise",
    "along-track-lower",
    "inclination-change",
    "node-change",
    "apsidal-change",
    "thrust-excess",
    "geo-east-west-keeping",
    "geo-north-south-keeping",
    "geo-graveyard-raise",
    "orbit-raising",
    "orbit-lowering",
    "deorbit-lowering",
    "unclassified-change",
)

SIGNATURE_PROSE = {
    "re-entry-decay": (
        "re-entry decay",
        "Perigee is below two hundred kilometres. Down here the atmosphere removes tens of "
        "kilometres of semi-major axis a day, the orbit is changing faster than the element set "
        "that describes it can be fitted, and nothing an operator could do is separable from what "
        "the atmosphere is doing. This site makes no propulsive claim in this regime.",
    ),
    "drag-and-thrust-not-separable": (
        "not separable",
        "The orbit lost energy, which is what both atmospheric drag and a retrograde burn do. "
        "Splitting them needs a drag prediction, and that needs a population of comparable objects "
        "at the same altitude over the same hours. There were not enough. The measurement stands; "
        "the attribution does not.",
    ),
    "drag-decay": (
        "orbital decay",
        "The semi-major axis fell by about the amount the atmosphere alone accounts for "
        "at this altitude for a body of this ballistic coefficient. No propulsion is needed "
        "to explain it.",
    ),
    "drag-make-up": (
        "drag make-up",
        "A small raise in semi-major axis, of the size and sign that offsets the decay this "
        "object accumulates. This is routine station-keeping against the atmosphere, and its "
        "cadence is set by how fast the object falls.",
    ),
    "along-track-raise": (
        "in-plane raise",
        "The semi-major axis rose by more than atmospheric drag can explain, with the orbit "
        "plane essentially unchanged. A prograde tangential burn raises the orbit and slows "
        "the ground track's eastward drift.",
    ),
    "along-track-lower": (
        "in-plane lowering",
        "The semi-major axis fell by more than atmospheric drag accounts for, with the orbit "
        "plane essentially unchanged. A retrograde tangential burn lowers the orbit.",
    ),
    "inclination-change": (
        "plane change",
        "The inclination moved, and rotating an orbit plane is dramatically more expensive per "
        "degree than any in-plane change: the cost is set by the orbital speed itself rather "
        "than by the small difference between two orbits. An operator does not spend this on "
        "maintenance.",
    ),
    "node-change": (
        "plane rotation",
        "The orbit plane turned about the Earth's axis by more than the Earth's own "
        "oblateness accounts for. Nodal regression is ordinary and predictable — every orbit "
        "gets it for free — so what is measured here is the part left over after it, and "
        "rotating a plane is the most expensive thing an operator can do per unit of change.",
    ),
    "apsidal-change": (
        "apse-line rotation",
        "The ellipse turned inside its own plane: the same size and shape of orbit, with "
        "perigee somewhere else. The Earth's oblateness rotates the apse line on its own, "
        "and what is measured here is the part left over after that. An orbit that must hold "
        "perigee over one hemisphere — a Molniya-type orbit is the classic case — either pays "
        "for this or is flown at the critical inclination where the natural rotation stops.",
    ),
    "thrust-excess": (
        "above its own baseline",
        "This object is under sustained thrust: its semi-major axis has been climbing for "
        "days at a rate the atmosphere cannot produce. Over this interval it climbed faster "
        "than its own recent baseline. That is an excess over a fitted baseline and not a "
        "measured burn — nobody publishes what the thruster did — but a low-thrust system "
        "spread over many revolutions has no step for a step detector to find, and this is "
        "what a change in it looks like.",
    ),
    "geo-east-west-keeping": (
        "east-west station-keeping",
        "At geostationary altitude a small change in semi-major axis is the signature of "
        "longitude control. The Earth's equatorial ellipticity pulls a satellite towards one of "
        "two stable longitudes, and the operator answers with small tangential burns every few "
        "weeks. It is the cheap half of geostationary station-keeping.",
    ),
    "geo-north-south-keeping": (
        "north-south station-keeping",
        "Luni-solar gravity tips a geostationary orbit's plane by roughly three quarters of a "
        "degree a year. Holding inclination near zero is the expensive half of geostationary "
        "station-keeping, and it is a plane change, so it costs far more per unit of correction "
        "than east-west control does.",
    ),
    "geo-graveyard-raise": (
        "disposal raise",
        "A raise out of the geostationary ring. The IADC disposal guideline asks operators to "
        "leave the protected region at end of life rather than drift through it, and the "
        "resulting orbit is called a graveyard or super-synchronous orbit.",
    ),
    "orbit-raising": (
        "orbit raising",
        "Part of a sustained climb rather than a single correction. New spacecraft raise from "
        "an injection orbit to an operational one over days to months, especially with electric "
        "propulsion, whose low thrust spreads the manoeuvre across many revolutions.",
    ),
    "orbit-lowering": (
        "orbit lowering",
        "Part of a sustained descent under propulsion rather than a single correction.",
    ),
    "deorbit-lowering": (
        "disposal lowering",
        "A lowering far larger than drag accounts for, at an altitude where the remaining "
        "lifetime is already short. Lowering perigee deliberately shortens it further.",
    ),
    "unclassified-change": (
        "unclassified change",
        "Something moved by more than the catalogue's own fit noise, but the pattern does not "
        "match a signature this site is willing to name.",
    ),
}


# Signatures that assert nothing propulsive. They are still events worth
# drawing -- "the atmosphere did this" is a real answer, and the honest
# "we cannot tell" is a more useful thing to show a visitor than a blank -- but
# they never count towards a Delta-v total, never count as a detection against
# the ground truth, and never count as a false alarm against the passive
# control, because none of them is a claim that anything burned.
NON_PROPULSIVE_SIGNATURES = frozenset(
    {"drag-decay", "re-entry-decay", "drag-and-thrust-not-separable", "unclassified-change"}
)


def classify_change(
    interval: Interval,
    drag: DragPrediction,
    cost: DeltaV,
    tests: Sequence[ChannelTest],
) -> str:
    """Name the kind of change, from the elements and the drag model alone.

    Order matters: the plane change is tested first because it is by far the
    most expensive thing an operator can do and the least likely to be an
    artefact, and the geostationary cases are separated because east-west and
    north-south keeping have different physics, different costs and different
    cadences — telling them apart is most of what makes a geostationary
    satellite's history readable.
    """
    tripped = {test.element for test in tests if test.tripped}
    regime = interval.regime
    propulsive = cost.propulsive_delta_a_metres

    # Terminal decay first, before anything else can claim the interval. An
    # object below this perigee is on its way into the atmosphere and every
    # element it has is being dragged around; asserting anything propulsive
    # about it is asserting that we can see through the re-entry, and we cannot.
    if interval.perigee_altitude_km < TERMINAL_DECAY_PERIGEE_KM:
        return "re-entry-decay"

    if regime in ("GEO", "near-GEO"):
        if "inclination" in tripped:
            return "geo-north-south-keeping"
        if (interval.a_start_km - GEO_SEMI_MAJOR_AXIS_KM) < GEO_GRAVEYARD_MINIMUM_RAISE_KM <= (
            interval.a_end_km - GEO_SEMI_MAJOR_AXIS_KM
        ):
            return "geo-graveyard-raise"
        if "semiMajorAxis" in tripped:
            return "geo-east-west-keeping"
        return "unclassified-change"

    if "inclination" in tripped:
        return "inclination-change"

    # The node before the apse line, and both before anything in-plane, on the
    # same reasoning that puts inclination first: rotating a plane costs
    # hundreds of times more per unit than moving inside one, so when a plane
    # rotation is on the table it is the thing that happened and the rest is
    # incidental to it.
    if "raan" in tripped:
        return "node-change"
    if "argPerigee" in tripped:
        return "apsidal-change"

    if "semiMajorAxis" not in tripped:
        # Nothing cleared the bar. If drag explains the whole interval, say so
        # positively rather than saying nothing: "the atmosphere did this" is a
        # real answer and it is the answer most of the time.
        if drag.applicable and interval.delta_a_km < 0:
            return "drag-decay"
        return "unclassified-change"

    # The asymmetry that makes an uncorrected interval readable at all:
    # **atmospheric drag can only remove energy.** A semi-major axis that ROSE
    # by more than the catalogue's own fit noise cannot be the atmosphere, so a
    # raise is propulsive whether or not a drag prediction was available. A
    # semi-major axis that FELL is exactly what drag does, so without a drag
    # prediction there is nothing to attribute it to and the honest label says
    # so. (The one perturbation that can raise an orbit without propulsion is
    # solar radiation pressure, and at these magnitudes and altitudes it is
    # orders of magnitude too small; at GEO it matters and the GEO branch above
    # has already claimed those intervals.)
    if propulsive > 0:
        if drag.applicable and abs(propulsive + drag.predicted_delta_a_metres) < abs(
            drag.predicted_delta_a_metres
        ):
            # The burn did not fully cancel the decay: net still downwards.
            return "drag-make-up"
        return "along-track-raise"

    if not drag.applicable:
        return "drag-and-thrust-not-separable"

    if interval.perigee_altitude_km < 400.0 and abs(propulsive) > 500.0:
        return "deorbit-lowering"
    return "along-track-lower"


# ---------------------------------------------------------------------------
# Expectations: what is ordinary for this class of object
# ---------------------------------------------------------------------------
@dataclass
class Expectations:
    version: str
    generated_note: str
    classes: list[dict[str, Any]]
    budgets: list[dict[str, Any]]

    @classmethod
    def load(cls, path: Path = EXPECTATIONS_PATH) -> "Expectations":
        payload = json.loads(path.read_text())
        return cls(
            version=str(payload.get("version", "0")),
            generated_note=str(payload.get("note", "")),
            classes=list(payload.get("classes", [])),
            budgets=list(payload.get("deltaVBudgets", [])),
        )

    def match(self, interval: Interval, catalog: dict[str, Any] | None) -> dict[str, Any] | None:
        """The most specific expectation whose conditions this object meets.

        Conditions are read from data, evaluated here, and are all properties
        of ONE object: its own type, its own name pattern, its own altitude,
        its own inclination, its own sun-synchronicity. Nothing in this
        matcher can read a second object.
        """
        best: dict[str, Any] | None = None
        best_rank = -1
        for entry in self.classes:
            rank = int(entry.get("specificity", 0))
            if rank <= best_rank:
                continue
            if not self._matches(entry, interval, catalog):
                continue
            best, best_rank = entry, rank
        return best

    @staticmethod
    def _matches(entry: dict[str, Any], interval: Interval, catalog: dict[str, Any] | None) -> bool:
        match = entry.get("match", {})
        types = match.get("objectType")
        if types and interval.object_type not in types:
            return False
        pattern = match.get("namePattern")
        if pattern and not re.match(pattern, interval.name, re.IGNORECASE):
            return False
        regime = match.get("regime")
        if regime and interval.regime not in regime:
            return False
        band = match.get("perigeeAltitudeKm")
        if band and not (band[0] <= interval.perigee_altitude_km <= band[1]):
            return False
        inclination = match.get("inclinationDeg")
        if inclination and not (inclination[0] <= interval.inclination_deg <= inclination[1]):
            return False
        if match.get("sunSynchronous") is True and not sun_synchronous(
            interval.a_start_km, interval.eccentricity, interval.inclination_deg
        ):
            return False
        mission = match.get("mission")
        if mission and (catalog or {}).get("mission") not in mission:
            return False
        constellation = match.get("constellation")
        if constellation and (catalog or {}).get("constellation") not in constellation:
            return False
        return True


def score_against_expectation(
    interval: Interval,
    signature: str,
    cost: DeltaV,
    expectation: dict[str, Any] | None,
) -> dict[str, Any]:
    """Compare this event to what its class of object ordinarily does.

    Some satellites would be retasked and others would not, and that difference
    belongs in the calculus. A Starlink in an operational shell raising its
    orbit is unremarkable; a
    spent rocket body doing anything at all is impossible; a geostationary
    communications satellite spending fifty metres per second in a week is out
    of family. The verdict is computed here and handed to the interface and to
    the model as a finished fact. **A model is never asked whether something is
    normal.**
    """
    if expectation is None:
        return {
            "verdict": "no-expectation",
            "class": None,
            "reason": "No expectation is published for this class of object.",
            "citations": [],
        }
    label = expectation.get("label", "")
    citations = expectation.get("citations", [])
    if expectation.get("cannotManoeuvre"):
        return {
            "verdict": "impossible-for-class",
            "class": label,
            "reason": (
                # The class cannot manoeuvre; the evidence that this OBJECT is in
                # the class is a catalogue field, which can be wrong or stale. The
                # verdict is unchanged and the control population is unchanged --
                # a real late disposal burn inflates the measured false-alarm rate
                # rather than hiding it, so the error runs in the safe direction --
                # but the sentence no longer claims more than it can show.
                "Objects of this class carry no propulsion, so a propulsive signature "
                "on one is a false alarm unless the catalogue has this object in the "
                "wrong class. That is exactly why the class is used as the control "
                "population."
            ),
            "citations": citations,
        }
    ordinary = set(expectation.get("ordinarySignatures", []))
    ceiling = expectation.get("perEventDeltaVCeilingMetresPerSecond")
    if signature not in ordinary:
        return {
            "verdict": "unusual-for-class",
            "class": label,
            "reason": (
                f"{SIGNATURE_PROSE.get(signature, (signature, ''))[0]} is not among the "
                f"manoeuvres this class ordinarily performs "
                f"({', '.join(sorted(ordinary)) or 'none published'})."
            ),
            "citations": citations,
        }
    if ceiling is not None and cost.total > float(ceiling):
        return {
            "verdict": "larger-than-typical",
            "class": label,
            "reason": (
                "The manoeuvre type is ordinary for this class, but the cost is above the "
                "published per-event figure for it."
            ),
            "citations": citations,
        }
    return {
        "verdict": "expected-for-class",
        "class": label,
        "reason": "Both the manoeuvre type and its cost are in family for this class of object.",
        "citations": citations,
    }


# ---------------------------------------------------------------------------
# The event
# ---------------------------------------------------------------------------
@dataclass
class OrbitEvent:
    norad: int
    name: str
    object_type: str
    start_ms: int
    end_ms: int
    signature: str
    confidence: str
    delta_v: DeltaV
    drag: DragPrediction
    tests: list[ChannelTest]
    expectation: dict[str, Any]
    regime: str
    perigee_altitude_km: float
    apogee_altitude_km: float
    inclination_deg: float
    kp_max: float | None = None
    density_ratio: float | None = None
    ground_truth: dict[str, Any] | None = None
    opaque: bool = False
    catalog: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "norad": self.norad,
            "name": self.name,
            "objectType": self.object_type,
            "startAt": _iso(self.start_ms),
            "endAt": _iso(self.end_ms),
            "spanDays": round((self.end_ms - self.start_ms) / 86_400_000.0, 4),
            "signature": self.signature,
            "signatureLabel": SIGNATURE_PROSE.get(self.signature, (self.signature, ""))[0],
            "signatureExplanation": SIGNATURE_PROSE.get(self.signature, ("", ""))[1],
            "confidence": self.confidence,
            "regime": self.regime,
            "perigeeAltitudeKm": round(self.perigee_altitude_km, 1),
            "apogeeAltitudeKm": round(self.apogee_altitude_km, 1),
            "inclinationDeg": round(self.inclination_deg, 4),
            "deltaV": {
                "totalMetresPerSecond": round(self.delta_v.total, 4),
                "tangentialMetresPerSecond": round(self.delta_v.tangential, 4),
                "planeChangeMetresPerSecond": round(self.delta_v.plane_change, 4),
                "planeRotationDeg": round(self.delta_v.plane_rotation_deg, 6),
                "apsidalMetresPerSecond": round(self.delta_v.apsidal, 4),
                "eccentricityMetresPerSecond": round(self.delta_v.eccentricity, 4),
                "note": "Lower bound: the cheapest manoeuvre consistent with the element change.",
                # Null on every ordinary event. Present only where the cost is
                # larger than routine operations, and worded so the reader knows
                # a large TRANSFER burn is a legitimate way to land here.
                "beyondRoutine": self.delta_v.beyond_routine,
            },
            "drag": {
                "applicable": self.drag.applicable,
                "reason": self.drag.reason,
                "predictedDeltaAMetres": round(self.drag.predicted_delta_a_metres, 2),
                "predictedSigmaMetres": round(self.drag.sigma_metres, 2),
                "propulsiveDeltaAMetres": round(self.delta_v.propulsive_delta_a_metres, 2),
                "cohortCount": self.drag.cohort_count,
                "bstar": self.drag.bstar,
            },
            "tests": [
                {
                    "element": test.element,
                    "delta": test.delta,
                    "floorSigma": test.floor_sigma,
                    "floorZ": round(test.floor_z, 2),
                    "cohortZ": None if test.cohort_z is None else round(test.cohort_z, 2),
                    "cohortCount": test.cohort_count,
                    "cohortScreened": test.cohort_screened,
                    "tripped": test.tripped,
                    "basis": test.basis,
                }
                for test in self.tests
            ],
            "expectation": self.expectation,
            "spaceWeather": {"kpMax": self.kp_max, "densityRatio": self.density_ratio},
            "groundTruth": self.ground_truth,
            "purposeLanguagePermitted": not self.opaque,
        }


def _iso(epoch_ms: int) -> str:
    return epoch_ms_to_datetime(epoch_ms).isoformat(timespec="seconds").replace("+00:00", "Z")


# ---------------------------------------------------------------------------
# The two angle channels, opened only where the angle means something
# ---------------------------------------------------------------------------
# ONE OF THESE TWO IS ON AND THE OTHER IS OFF, AND THE MEASUREMENT DECIDED IT.
#
# The false-alarm rate is the currency of this whole module: the published
# control stands at 34 flags in 1,941 intervals of objects that physically
# cannot manoeuvre, against a design target of one in a thousand, and
# `manoeuvreLabelPermitted` is false because of it. A new channel that spends
# that currency buys nothing, so each was measured on the passive control
# before being switched on.
#
# **The node channel is on.** Measured over one seven-day release window of
# the live archive (15,363 intervals, 3,205 of them on debris and spent
# stages), the passive control was 49 flags with the channel off and 49 with it
# on -- unchanged, to the flag -- while 41 payload node tests cleared the bar
# and 11 of them became published node-change events, the rest being intervals
# a more expensive signature had already claimed. It reached that only with the
# three gates below it: the inclination floor, the requirement that a cohort
# exist, and a kappa a half again stricter than the other channels', which is
# where the control's own node tests go to zero.
#
# **The apse-line channel is off.** Same window, same run: the passive control
# went from 49 flags to 62, a thirteen-flag increase on objects with no
# propulsion, and the excess did not come from anything a threshold could fix.
# Every tripped test was on debris, at eccentricities from 0.0016 to 0.19, and
# their COHORT z-scores ran from 8.5 to 147 -- so the population screen, which
# is what saves the node channel, does not save this one. Three physical
# causes, none of them modelled here:
#
#   * atmospheric drag rotates the apse line of an eccentric orbit, by an
#     amount that depends on the object's area-to-mass ratio, and this module
#     has no model for it (the worst offenders had B* of 0.16 and 0.19);
#   * the catalogue's measured eccentricity scatter is taken from well-tracked
#     payloads, and a tumbling fragment's eccentricity vector is fitted far
#     more loosely, so `sigma_e / e` understates the floor by two orders of
#     magnitude on exactly the objects that trip it;
#   * the residual distribution has heavier tails than the population MAD
#     describes, which `docs/orbit-history-design.md` Section 2.1 records for
#     the elements already in use and which no threshold can be tuned around.
#
# So the channel ships written, tested and OFF. Turning it on is a deliberate
# act that must be preceded by a fresh measurement on the passive control, and
# the three causes above are the work that would have to be done first. This is
# the intended outcome of a measurement that came out negative, not a gap.
NODE_CHANNEL_ENABLED = True
APSIDAL_CHANNEL_ENABLED = False

# Neither angle channel may trip without a cohort behind it. See the long note
# in `angle_channels` for the measurement that put this here.
ANGLE_CHANNELS_REQUIRE_COHORT = True

# PERSISTENCE IS ENFORCED IN THE SELF-HISTORY LANE, not borrowed from it here.
# `orbit_campaigns.step_persistence` follows each channel for two full observed
# days and declines a fitted excursion that returns to trend. That lane owns an
# object's full ordered history, which makes the test physical and exact.
#
# The cohort lane answers a different question: how one interval compares with
# the population flying through the same altitude over the same hours. Its
# seven-day release window is now correctly anchored on the capture ledger,
# rather than a future fitted epoch, but the right edge remains deliberately
# censored: the newest two days cannot prove persistence yet. Adding a partial
# persistence rule here would therefore make the cohort detector's acceptance
# depend on where an interval happened to fall inside the release window.
# Keep the independent cohort control honest and let the full-history lane own
# persistence. `orbit_release` publishes the two controls and label permissions
# separately, so neither detector lends certainty to the other.

# The node channel is held to a stricter kappa than its three neighbours, and
# the multiple came from the control rather than from a distribution.
#
# Measured over one seven-day release window (13,574 node tests that had a
# cohort behind them; 2,553 of them on debris and spent stages):
#
#     kappa   passive tests tripped   payload tests tripped
#       8              3                       77
#      10              0                       54
#      12              0                       41
#      15              0                       23
#      20              0                       16
#      50              0                        0
#
# The largest z the channel produced on ANY object with no propulsion was 9.6,
# and the passive tail below it is smooth -- 9.6, 9.1, 8.6, 7.8, 7.5 -- while
# the payload tail runs 47.8, 45.3, 44.4, 42.3, 40.9. The two populations
# separate, and 12 sits a quarter above the largest passive value with 41
# payload detections still standing. It is expressed as a MULTIPLE of whatever
# kappa the run is using, not as a bare 12, so a run at a different operating
# point moves both together and `control_rates` keeps reporting a single kappa
# that means something.
#
# What this is not: a threshold tuned until the answer looked good.
# `docs/orbit-history-design.md` Section 2.1 measures the residual
# distribution's tails and concludes no threshold can be made clean by tuning,
# and that remains true -- which is why the number below is read off a measured
# control curve with a stated margin, and why the curve is written down here so
# the next measurement can contradict it.
NODE_CHANNEL_KAPPA_MULTIPLIER = 1.5


def angle_channels(
    interval: Interval,
    index: CohortIndex,
    *,
    kappa: float,
    cohort_statistics: dict[str, CohortStatistic | None] | None = None,
) -> list[ChannelTest]:
    """The node and apse-line tests, where the geometry allows them to exist.

    Three gates, and each of them is a refusal to measure rather than a
    threshold on a measurement:

    * **The angles were not read.** An Interval built from a row set without
      them is judged on the three elements it has.
    * **The orbit is too nearly equatorial for a node.** Below
      `NODE_MINIMUM_INCLINATION_DEG` the ascending node is the direction in
      which the orbit plane crosses a plane it is nearly coincident with, and
      the published number is very nearly a fitted random walk. This is what
      keeps the channel off the whole geostationary ring, where the inclination
      is hundredths of a degree.
    * **The orbit is too nearly circular for an apse line.** Below
      `ARGP_MINIMUM_ECCENTRICITY` the argument of perigee is the heading of a
      vector shorter than the perturbations that move it.

    A gated channel is omitted rather than emitted untripped, so a reader
    counting the tests on an event sees the ones that were actually run.
    """
    if not interval.angles_measured:
        return []
    # THE NODE HAS TO EXIST FOR EITHER CHANNEL, and that is not a coincidence:
    # the argument of perigee is the angle FROM the ascending node to perigee,
    # so an orbit whose node is a fitted random number has an argument of
    # perigee that is the same random number with a real angle added to it.
    # Measured on the passive control, this was the single largest source of
    # false alarms in the whole exercise: geostationary transfer stages at
    # inclinations of a tenth of a degree produced apse-line residuals of a
    # third of a degree per interval and z-scores near a thousand, on objects
    # that have been inert for twenty years. (The quantity that IS determined
    # for such an orbit is the longitude of perigee, RAAN + ARGP; this module
    # does not watch it, and a future channel that did would be watching a
    # different element with a different floor.)
    node_defined = (
        abs(interval.inclination_deg) >= NODE_MINIMUM_INCLINATION_DEG
        and abs(interval.inclination_deg - 180.0) >= NODE_MINIMUM_INCLINATION_DEG
    )
    out: list[ChannelTest] = []
    residual_node = interval.raan_residual_deg
    if NODE_CHANNEL_ENABLED and residual_node is not None and node_defined:
        out.append(
            _channel(
                interval,
                index,
                element="raan",
                observed=residual_node,
                kappa=kappa * NODE_CHANNEL_KAPPA_MULTIPLIER,
                cohort_statistics=cohort_statistics,
            )
        )
    residual_apse = interval.arg_perigee_residual_deg
    if (
        APSIDAL_CHANNEL_ENABLED
        and residual_apse is not None
        and node_defined
        and interval.eccentricity >= ARGP_MINIMUM_ECCENTRICITY
    ):
        out.append(
            _channel(
                interval,
                index,
                element="argPerigee",
                observed=residual_apse,
                kappa=kappa,
                cohort_statistics=cohort_statistics,
            )
        )
    if ANGLE_CHANNELS_REQUIRE_COHORT:
        # **No cohort, no claim.** The floors these two channels are tested
        # against are bounds on SOME of the ways an angle moves for free: the
        # fit's own scatter, the J2 model's error, third-body precession. They
        # are not bounds on all of them. Atmospheric drag rotates the apse line
        # of an eccentric orbit and this module has no model for it; a fragment
        # with a poor radar cross-section is fitted far more loosely than the
        # catalogue-wide table assumes, and that table was measured on
        # well-tracked payloads. The cohort sees every one of those at once,
        # because it is other objects in the same orbit over the same hours,
        # which is exactly why the design leans on it everywhere else.
        #
        # Measured on the passive control: six of the eight node false alarms
        # had no cohort at all, and the channel was therefore running on its
        # floor alone. A test is still emitted, untripped, so a reader can see
        # that the channel ran and declined rather than that it was absent.
        out = [
            test if test.cohort_z is not None else replace(test, tripped=False)
            for test in out
        ]
    return out


# ---------------------------------------------------------------------------
# The detection pass
# ---------------------------------------------------------------------------
_DETECT_WORKER_STATE: tuple[
    Sequence[Interval], CohortIndex, float, Expectations, dict[int, dict[str, Any]], bool
] | None = None


def _detect_one(
    interval: Interval,
    index: CohortIndex,
    *,
    kappa: float,
    expectations: Expectations,
    catalog: dict[int, dict[str, Any]],
    include_drag_only: bool,
) -> tuple[OrbitEvent | None, bool]:
    """Judge one interval; the boolean says its implied cost was impossible."""
    specifications: dict[str, tuple[Any, float, bool]] = {
        element: (
            lambda candidate, element=element: index.normalised_deviation(
                candidate, element
            ),
            1.0,
            False,
        )
        for element in ("semiMajorAxis", "inclination", "eccentricity")
    }
    if (
        interval.perigee_altitude_km <= DRAG_MODEL_CEILING_KM
        and interval.bstar is not None
        and interval.bstar >= MINIMUM_USABLE_BSTAR
    ):
        specifications["drag"] = (_specific_decay_rate, 0.0, True)
    node_defined = (
        interval.angles_measured
        and abs(interval.inclination_deg) >= NODE_MINIMUM_INCLINATION_DEG
        and abs(interval.inclination_deg - 180.0) >= NODE_MINIMUM_INCLINATION_DEG
    )
    if NODE_CHANNEL_ENABLED and node_defined:
        specifications["raan"] = (
            lambda candidate: index.normalised_deviation(candidate, "raan"),
            1.0,
            False,
        )
    if (
        APSIDAL_CHANNEL_ENABLED
        and node_defined
        and interval.eccentricity >= ARGP_MINIMUM_ECCENTRICITY
    ):
        specifications["argPerigee"] = (
            lambda candidate: index.normalised_deviation(candidate, "argPerigee"),
            1.0,
            False,
        )
    cohort_statistics = index.statistics(interval, specifications)
    drag = predict_drag(interval, index, cohort_statistics=cohort_statistics)

    tests = [
        _channel(
            interval,
            index,
            element="semiMajorAxis",
            observed=interval.delta_a_km * 1000.0,
            physical_expectation=(
                drag.predicted_delta_a_metres if drag.applicable else None
            ),
            expectation_sigma=drag.sigma_metres,
            kappa=kappa,
            cohort_statistics=cohort_statistics,
        ),
        _channel(
            interval,
            index,
            element="inclination",
            observed=interval.delta_i_deg,
            kappa=kappa,
            cohort_statistics=cohort_statistics,
        ),
        _channel(
            interval,
            index,
            element="eccentricity",
            observed=interval.delta_e,
            kappa=kappa,
            cohort_statistics=cohort_statistics,
        ),
    ]
    tests.extend(
        angle_channels(
            interval,
            index,
            kappa=kappa,
            cohort_statistics=cohort_statistics,
        )
    )
    cost = delta_v(interval, drag, tests)
    if cost.implausible is not None:
        return None, True
    signature = classify_change(interval, drag, cost, tests)
    if not any(test.tripped for test in tests) and signature != "drag-decay":
        return None, False
    if signature in ("drag-decay", "re-entry-decay") and not include_drag_only:
        return None, False

    record = catalog.get(interval.norad, {})
    expectation = expectations.match(interval, record)
    screened = any(test.tripped and test.cohort_screened for test in tests)
    thin = any(test.tripped and test.cohort_z is None for test in tests)
    confidence = (
        "candidate" if screened else "candidate-unscreened" if thin else "candidate-thin-cohort"
    )
    return OrbitEvent(
        norad=interval.norad,
        name=interval.name,
        object_type=interval.object_type,
        start_ms=interval.start_ms,
        end_ms=interval.end_ms,
        signature=signature,
        confidence=confidence,
        delta_v=cost,
        drag=drag,
        tests=tests,
        expectation=score_against_expectation(interval, signature, cost, expectation),
        regime=interval.regime,
        perigee_altitude_km=interval.perigee_altitude_km,
        apogee_altitude_km=interval.apogee_altitude_km,
        inclination_deg=interval.inclination_deg,
        opaque=opacity_denied(
            interval.name,
            record.get("sector"),
            record.get("mission"),
            record.get("classificationConfidence"),
        ),
        catalog=record,
    ), False


def _detect_range(bounds: tuple[int, int]) -> tuple[list[OrbitEvent], int]:
    """Fork worker: preserve interval order within one contiguous range."""
    if _DETECT_WORKER_STATE is None:
        raise RuntimeError("cohort detector worker started without inherited state")
    intervals, index, kappa, expectations, catalog, include_drag_only = _DETECT_WORKER_STATE
    events: list[OrbitEvent] = []
    implausible_costs = 0
    for position in range(*bounds):
        event, implausible = _detect_one(
            intervals[position],
            index,
            kappa=kappa,
            expectations=expectations,
            catalog=catalog,
            include_drag_only=include_drag_only,
        )
        implausible_costs += int(implausible)
        if event is not None:
            events.append(event)
    return events, implausible_costs


@contextmanager
def _cohort_pool(worker_count):
    pool = multiprocessing.get_context("fork").Pool(worker_count)
    try:
        yield pool
    finally:
        # Fork inherits the tail's cooperative TERM handler. Pool.__exit__
        # uses terminate(), which can then hang forever joining an idle worker
        # that handled TERM without exiting. Completed/budgeted map batches
        # must shut down by queue sentinel, not by signal.
        pool.close()
        pool.join()


def detect_events(
    intervals: Sequence[Interval],
    *,
    kappa: float = DEFAULT_KAPPA,
    expectations: Expectations | None = None,
    catalog: dict[int, dict[str, Any]] | None = None,
    include_drag_only: bool = False,
    workers: int = 1,
    checkpoint: Callable | None = None,
) -> list[OrbitEvent]:
    """Classify every interval, and keep the ones that cleared a bar.

    The cohort index is built once over the whole population and queried per
    interval. A caller may ask for a small, explicit worker count: on Linux the
    workers inherit that read-mostly index with copy-on-write, judge contiguous
    ranges, and return them in input order. Nothing about cohort membership or
    arithmetic changes; this only gives the release tail enough wall-clock
    room to write its shards after the real seven-day window was restored.

    `confidence` is hard-wired to `"candidate"` or weaker, always, and there is
    no code path that produces anything stronger. Per
    `docs/orbit-history-design.md` Section 3.7 the label has to be *earned* by a
    measured false-alarm rate, and the measurement is a separate function whose
    output the interface publishes next to the event.
    """
    if checkpoint is not None:
        expectations = checkpoint("cohort-expectations", lambda: expectations or Expectations.load())
    else:
        expectations = expectations or Expectations.load()
    catalog = catalog or {}
    index = CohortIndex(intervals)
    worker_count = max(1, min(int(workers), len(intervals) or 1))
    parallel = (
        worker_count > 1
        and len(intervals) >= COHORT_PARALLEL_MINIMUM_INTERVALS
        and "fork" in multiprocessing.get_all_start_methods()
    )
    if parallel:
        # Each half of the target intervals still draws candidates from the
        # whole population. Prime once in the parent so both fork workers read
        # the same copy-on-write pages instead of calculating and allocating
        # an almost identical cache independently.
        index.prime_normalised(
            ("semiMajorAxis", "inclination", "eccentricity", "raan")
        )
        chunk_count = min(
            len(intervals), worker_count * COHORT_PARALLEL_CHUNKS_PER_WORKER
        )
        step = math.ceil(len(intervals) / chunk_count)
        ranges = [
            (first, min(first + step, len(intervals)))
            for first in range(0, len(intervals), step)
        ]
        global _DETECT_WORKER_STATE
        _DETECT_WORKER_STATE = (
            intervals, index, kappa, expectations, catalog, include_drag_only
        )
        try:
            with _cohort_pool(worker_count) as pool:
                if checkpoint is None:
                    parts = pool.map(_detect_range, ranges)
                else:
                    # Save bounded, ordered batches. Each target still uses
                    # the FULL index; slicing the reference population would
                    # silently change the detector and its controls.
                    parts = []
                    for first in range(0, len(intervals), 2048):
                        end = min(first + 2048, len(intervals))
                        width = math.ceil((end - first) / worker_count)
                        batch = [(i, min(i + width, end)) for i in range(first, end, width)]
                        parts.extend(checkpoint(f"cohort-range:{first}",
                                                lambda: pool.map(_detect_range, batch)))
        finally:
            _DETECT_WORKER_STATE = None
        events = [event for part, _dropped in parts for event in part]
        implausible_costs = sum(dropped for _part, dropped in parts)
    elif checkpoint is not None:
        parts = []
        for first in range(0, len(intervals), 2048):
            parts.extend(checkpoint(f"cohort-range:{first}", lambda: [_detect_range_sequential(
                intervals[first:first + 2048], index, kappa=kappa,
                expectations=expectations, catalog=catalog, include_drag_only=include_drag_only)]))
        events = [event for part, _dropped in parts for event in part]
        implausible_costs = sum(dropped for _part, dropped in parts)
    else:
        events, implausible_costs = _detect_range_sequential(
            intervals,
            index,
            kappa=kappa,
            expectations=expectations,
            catalog=catalog,
            include_drag_only=include_drag_only,
        )
    if implausible_costs:
        print(
            f"orbit_events: dropped {implausible_costs:,} interval(s) whose implied Delta-v "
            "exceeded twice the perigee speed -- element pairs that do not describe one orbit",
            file=sys.stderr,
        )
    return events


def _detect_range_sequential(
    intervals: Sequence[Interval],
    index: CohortIndex,
    *,
    kappa: float,
    expectations: Expectations,
    catalog: dict[int, dict[str, Any]],
    include_drag_only: bool,
) -> tuple[list[OrbitEvent], int]:
    """The ordinary path, kept explicit so parallel and serial share one judge."""
    events: list[OrbitEvent] = []
    implausible_costs = 0
    for interval in intervals:
        event, implausible = _detect_one(
            interval,
            index,
            kappa=kappa,
            expectations=expectations,
            catalog=catalog,
            include_drag_only=include_drag_only,
        )
        implausible_costs += int(implausible)
        if event is not None:
            events.append(event)
    return events, implausible_costs


# ---------------------------------------------------------------------------
# Controls: the negative one is free, the positive one is hand-curated
# ---------------------------------------------------------------------------
PASSIVE_TYPES = ("DEBRIS", "ROCKET BODY")


# The SEPARATION half of the manoeuvre-label gate, and the reason it is not a
# p-value.
#
# The gate's first half is a bound on the false-alarm rate: the Jeffreys upper
# bound on the passive rate must be strictly below the design target of 1 per
# 1,000 intervals. On its own that half is buyable. A detector tightened until
# it flags almost nothing has a passive rate of almost nothing and clears it --
# while flagging almost nothing on payloads either, which is a calibration that
# has been achieved by detecting nothing.
#
# Asking additionally that the payload excess be statistically significant does
# not close that. Significance is a statement about the size of the archive,
# not about the size of the difference: the self-history control holds 89
# million passive intervals and 62 million payload intervals, at which the
# smallest rate ratio a two-proportion test resolves at alpha = 0.05 is about
# 1.006 at the payload rate, 1.008 pooled and 1.015 at the passive rate (and
# 1.008 / 1.011 / 1.020 at this gate's own p < 0.01). An earlier version of
# this comment said 1.001, which is wrong by an order of magnitude -- the
# archive would have to be about 67 times larger for 1.001 to reach p < 0.05 --
# and quoted a pooled z of 459 that reproduces from no bundle now published
# (the live artifact gives 411.8, the paired original 413.6). Corrected
# 2026-09-21. The argument is unchanged and the numbers now support it: an
# effect of six parts in a thousand is not a reason to print the word
# "manoeuvre", so a separation requirement has to be an EFFECT SIZE.
#
# So the second half compares the two Jeffreys intervals, and compares BOUNDS
# rather than point estimates for exactly the reason the first half uses the
# upper bound: the lower bound on the payload rate must be at least this many
# times the upper bound on the passive rate.
#
# The factor is TEN, and the reasoning is a share of flags rather than a fit to
# the data. If the process that produces flags on objects without propulsion
# also acts on payloads, the share of payload flags attributable to it is at
# most passive_rate / payload_rate. A factor of ten bounds that share below one
# in ten. The word "manoeuvre" on an event card is a claim about THAT event, so
# the reader is entitled to more than a coin flip -- and a coin flip, a factor
# of two, is roughly what a threshold reverse-engineered from the current
# archive would have been.
#
# STATE OF THE GATE, 2026-09-21. When this comment was first written both
# halves were shut: the self-history bounds gave a ratio of 2.2 against this
# 10x test and a false-alarm rate of 6.2 per 1,000 against a target of 1. They
# are not shut now. The 2026-09-20 inclination-corroboration rule took the
# full-population passive rate to 0.1589 per 1,000 (95% upper 0.161539) and the
# bound separation to 18.191x, so both halves of the published gate are open on
# the RAW pooled floor. That is not the whole story and the code should not
# pretend it is: the registered covariate-transfer analysis of the same week
# measured the payload-covariate-reweighted floor at 2.0591x the raw one, and
# 18.191 / 2.0591 = 8.83x, which is BELOW this requirement. The pooled gate
# that ships is computed on the raw floor; docs/phase3-preregistration-20260921.md
# registers the covariate-aware gate that would be computed on the reweighted
# one, and control_rates_by_object already discloses the transfer finding in
# its covariateTransfer block. Numbers here from
# docs/orbit-phase2b-corroboration-20260920.md and docs/paperb-results-20260920.md.
#
# The share argument assumes the two classes are fitted alike, and they are
# not: payloads are tracked and fitted differently from fragments, so the share
# is an estimate rather than a true bound. That is a further argument for a
# generous factor rather than one set at the edge of what the data allows.
MIN_SEPARATION_BOUND_RATIO = 10.0


def separation_verdict(
    passive_upper: float | None, payload_lower: float | None
) -> dict[str, Any]:
    """How far the payload flag rate stands clear of the false-alarm floor.

    Returns the ratio of bounds actually achieved, the ratio required, whether
    it is met, and -- when it is not -- a labelled `gap` in this codebase's
    usual shape, so that a caller publishes a stated reason rather than a bare
    false. Used by both detectors' controls, so there is one definition of what
    "separated" means rather than one per lane.
    """
    if not isinstance(passive_upper, (int, float)) or not isinstance(
        payload_lower, (int, float)
    ):
        return {
            "boundRatio": None,
            "requiredBoundRatio": MIN_SEPARATION_BOUND_RATIO,
            "meets": False,
            "gap": (
                "One of the two rates has not been measured, so the separation between "
                "them cannot be stated and the manoeuvre label stays shut."
            ),
        }
    if passive_upper <= 0:
        # A Jeffreys upper bound is strictly positive for any non-empty
        # control, so this is a control that was never measured rather than one
        # that measured zero.
        return {
            "boundRatio": None,
            "requiredBoundRatio": MIN_SEPARATION_BOUND_RATIO,
            "meets": False,
            "gap": (
                "The passive control has no measured upper bound, so the separation "
                "between the two rates cannot be stated."
            ),
        }
    ratio = payload_lower / passive_upper
    meets = ratio >= MIN_SEPARATION_BOUND_RATIO
    return {
        "boundRatio": round(ratio, 3),
        "requiredBoundRatio": MIN_SEPARATION_BOUND_RATIO,
        "meets": meets,
        "gap": (
            None
            if meets
            else (
                f"The payload flag rate is only {ratio:.1f} times the false-alarm floor "
                f"once both are read at their 95 per cent bounds, against the {MIN_SEPARATION_BOUND_RATIO:.0f} "
                "times this site requires before an individual event may be called a "
                "manoeuvre. Up to one flag in "
                f"{max(1, int(round(ratio)))} on a payload could be the same noise."
            )
        ),
        "note": (
            "Lower bound on the payload rate against upper bound on the passive rate. "
            "Bounds rather than point estimates, and an effect size rather than a "
            "p-value: with tens of millions of intervals a two-proportion test is "
            "significant for a ratio of 1.001, which would say the archive is large "
            "rather than that the detector separates the two populations."
        ),
    }


def control_rates(
    intervals: Sequence[Interval],
    events: Sequence[OrbitEvent],
    *,
    kappa: float = DEFAULT_KAPPA,
) -> dict[str, Any]:
    """The false-alarm rate, measured on objects that physically cannot manoeuvre.

    Debris and spent stages are the free negative control: they see the same
    fits, the same tracking outages, the same space weather and the same epoch
    spacing as the payloads being judged, and any propulsive signature on one of
    them is wrong by construction.

    Reported with a **Jeffreys interval**, not a bare ratio. With a control
    population only tens of intervals deep, a point estimate is close to
    meaningless and quoting one alone would be the dishonest half of an honest
    measurement.
    """
    passive_intervals = [i for i in intervals if i.object_type in PASSIVE_TYPES]
    active_intervals = [i for i in intervals if i.object_type == "PAYLOAD"]
    claims = [e for e in events if e.signature not in NON_PROPULSIVE_SIGNATURES]
    passive_flags = [e for e in claims if e.object_type in PASSIVE_TYPES]
    active_flags = [e for e in claims if e.object_type == "PAYLOAD"]

    def interval_estimate(flags: int, total: int) -> dict[str, Any]:
        if total == 0:
            return {"flags": flags, "intervals": 0, "rate": None, "interval95": None}
        rate = flags / total
        low, high = _jeffreys_interval(flags, total)
        return {
            "flags": flags,
            "intervals": total,
            "rate": round(rate, 5),
            "interval95": [round(low, 5), round(high, 5)],
        }

    passive = interval_estimate(len(passive_flags), len(passive_intervals))
    active = interval_estimate(len(active_flags), len(active_intervals))
    passive_upper = _jeffreys_interval(
        len(passive_flags), len(passive_intervals)
    )[1] if passive_intervals else None
    excess = _two_proportion_z(
        len(active_flags), len(active_intervals), len(passive_flags), len(passive_intervals)
    )
    p_value = excess.get("approximatePValue")
    z_value = excess.get("z")
    payload_excess_significant = (
        z_value is not None
        and z_value > 0
        and p_value is not None
        and p_value < 0.01
    )
    payload_lower = _jeffreys_interval(
        len(active_flags), len(active_intervals)
    )[0] if active_intervals else None
    # Significance AND effect size. Either alone can be cleared by a detector
    # that has stopped detecting; see MIN_SEPARATION_BOUND_RATIO.
    separation = separation_verdict(passive_upper, payload_lower)
    usable = (
        passive["intervals"] >= 200
        and passive_upper is not None
        and passive_upper < 0.001
        and payload_excess_significant
        and separation["meets"]
    )
    blocking: str | None = None
    if not usable:
        if passive["intervals"] < 200:
            blocking = "The passive control holds too few intervals to bound a rate."
        elif passive_upper is not None and passive_upper >= 0.001:
            blocking = (
                f"The upper bound on the cohort false-alarm rate is "
                f"{passive_upper * 1000:.1f} per 1,000 intervals, not below the design target "
                "of 1 per 1,000."
            )
        elif not payload_excess_significant:
            blocking = (
                "Payloads are not yet flagged significantly more often than objects that "
                "cannot manoeuvre."
            )
        else:
            blocking = separation["gap"]
    return {
        "kappa": kappa,
        "passiveControl": passive,
        "payloadPopulation": active,
        "excessSignificance": excess,
        "excessRate": (
            None
            if passive["rate"] is None or active["rate"] is None
            else round(active["rate"] - passive["rate"], 5)
        ),
        "sufficientToLabel": usable,
        "excessSignificant": payload_excess_significant,
        "separation": separation,
        "designTarget": 0.001,
        "note": (
            "Debris and spent rocket stages cannot manoeuvre, so every flag on one is a "
            "false alarm. The payload rate is not a detection rate: most payload intervals "
            "contain no manoeuvre either. What the two together bound is how much of the "
            "payload flag rate could be noise."
        ),
        "blockingReason": blocking,
    }


def _two_proportion_z(
    flags_a: int, trials_a: int, flags_b: int, trials_b: int
) -> dict[str, Any]:
    """Is the payload flag rate actually higher than the control's?

    The number that matters is not the ratio of the two rates but whether the
    difference survives the counts behind it. A payload rate three times the
    control rate sounds decisive and, on a control of a hundred and fifty
    intervals, is not. Publishing the ratio without this is the exact shape of
    dishonesty this whole module exists to avoid.

    Normal approximation to the difference of two binomial proportions, pooled
    under the null. Approximate at these counts, and labelled as approximate.
    """
    if trials_a <= 0 or trials_b <= 0:
        return {"z": None, "approximatePValue": None, "method": "insufficient-data"}
    rate_a, rate_b = flags_a / trials_a, flags_b / trials_b
    pooled = (flags_a + flags_b) / (trials_a + trials_b)
    variance = pooled * (1.0 - pooled) * (1.0 / trials_a + 1.0 / trials_b)
    if variance <= 0:
        return {"z": None, "approximatePValue": None, "method": "degenerate"}
    z = (rate_a - rate_b) / math.sqrt(variance)
    p_value = math.erfc(abs(z) / math.sqrt(2.0))
    return {
        "z": round(z, 3),
        "approximatePValue": round(p_value, 4),
        "method": "pooled two-proportion normal approximation, two-sided",
        "caution": (
            "The normal approximation is poor when either count is below about ten. "
            "Treat this as an order-of-magnitude statement about significance, not a "
            "precise p-value."
        ),
    }


def _jeffreys_interval(successes: int, trials: int, level: float = 0.95) -> tuple[float, float]:
    """Equal-tailed Jeffreys credible interval for a binomial rate.

    Jeffreys rather than Wald: at zero observed flags Wald returns the interval
    [0, 0], which would claim a false-alarm rate of exactly zero from a control
    of four intervals. That is the single most misleading number this module
    could publish, so the estimator that cannot produce it is the one used.
    Implemented by bisection on the regularised incomplete beta function so it
    needs no SciPy — this pipeline runs on system python3 with no virtualenv.
    """
    if trials <= 0:
        return (0.0, 1.0)
    alpha = (1.0 - level) / 2.0
    a = successes + 0.5
    b = trials - successes + 0.5

    def cdf(x: float) -> float:
        return _regularised_incomplete_beta(a, b, x)

    def invert(target: float) -> float:
        low, high = 0.0, 1.0
        for _ in range(200):
            mid = (low + high) / 2.0
            if cdf(mid) < target:
                low = mid
            else:
                high = mid
        return (low + high) / 2.0

    lower = 0.0 if successes == 0 else invert(alpha)
    upper = 1.0 if successes == trials else invert(1.0 - alpha)
    return lower, upper


def _regularised_incomplete_beta(a: float, b: float, x: float) -> float:
    """I_x(a, b) by the standard continued fraction, with the symmetry flip."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    log_front = (
        math.lgamma(a + b)
        - math.lgamma(a)
        - math.lgamma(b)
        + a * math.log(x)
        + b * math.log(1.0 - x)
    )
    front = math.exp(log_front)
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _beta_continued_fraction(a, b, x) / a
    return 1.0 - front * _beta_continued_fraction(b, a, 1.0 - x) / b


def _beta_continued_fraction(a: float, b: float, x: float, iterations: int = 300) -> float:
    """Lentz's algorithm for the beta continued fraction.

    Each iteration applies **two** partial numerators — the even one and the
    odd one — and a version that applies only one per iteration silently
    returns the wrong answer rather than failing. The first draft here did
    exactly that and gave I(2,3,0.5) = 1.22, where a cumulative distribution
    function cannot exceed 1. `tests/test_orbit_events.py` pins it against
    closed-form values for integer parameters, which is the only reason the
    error was visible.
    """
    tiny = 1e-30
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < tiny:
        d = tiny
    d = 1.0 / d
    result = d
    for m in range(1, iterations + 1):
        m2 = 2 * m
        numerator = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + numerator * d
        if abs(d) < tiny:
            d = tiny
        c = 1.0 + numerator / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        result *= d * c
        numerator = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + numerator * d
        if abs(d) < tiny:
            d = tiny
        c = 1.0 + numerator / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        delta = d * c
        result *= delta
        if abs(delta - 1.0) < 1e-13:
            break
    return result


# ---------------------------------------------------------------------------
# The positive control: operator-published manoeuvres
# ---------------------------------------------------------------------------
@dataclass
class GroundTruth:
    version: str
    entries: list[dict[str, Any]]

    @classmethod
    def load(cls, path: Path = GROUND_TRUTH_PATH) -> "GroundTruth":
        try:
            payload = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            return cls(version="missing", entries=[])
        return cls(version=str(payload.get("version", "0")), entries=list(payload.get("events", [])))


def score_against_ground_truth(
    events: Sequence[OrbitEvent],
    truth: GroundTruth,
    *,
    archive_start_ms: int | None,
    archive_end_ms: int | None,
    match_window_hours: float = 36.0,
) -> dict[str, Any]:
    """Detection rate against manoeuvres the operator published.

    The negative control says how often the detector fires on something that
    cannot burn. This says how often it fires on something that definitely did.
    Both are needed: a detector with a zero false-alarm rate and a zero
    detection rate is just a detector that never fires.

    **An event outside the archive's window is `pending`, never a miss.** The
    archive begins 2026-08-07 and most published manoeuvres predate it by
    years. Scoring those as failures would be scoring the calendar, and the
    number would get better on its own without the detector improving at all.
    """
    matched: list[dict[str, Any]] = []
    missed: list[dict[str, Any]] = []
    pending: list[dict[str, Any]] = []
    window_ms = int(match_window_hours * 3_600_000)

    by_norad: dict[int, list[OrbitEvent]] = {}
    for event in events:
        by_norad.setdefault(event.norad, []).append(event)

    for entry in truth.entries:
        occurred = _parse_iso_ms(entry.get("occurredAt"))
        norad = entry.get("norad")
        summary = {
            "object": entry.get("object"),
            "norad": norad,
            "occurredAt": entry.get("occurredAt"),
            "type": entry.get("type"),
            "publishedDeltaVMetresPerSecond": entry.get("deltaVMetresPerSecond"),
            "source": entry.get("source"),
        }
        if occurred is None or archive_start_ms is None or archive_end_ms is None:
            pending.append({**summary, "reason": "no-archive-window"})
            continue
        if occurred < archive_start_ms or occurred > archive_end_ms:
            pending.append({**summary, "reason": "outside-archive-window"})
            continue
        if norad is None:
            pending.append({**summary, "reason": "no-catalog-number-published"})
            continue
        hit = next(
            (
                event
                for event in by_norad.get(int(norad), [])
                if event.signature not in NON_PROPULSIVE_SIGNATURES
                if event.start_ms - window_ms <= occurred <= event.end_ms + window_ms
            ),
            None,
        )
        if hit is None:
            missed.append(summary)
            continue
        matched.append(
            {
                **summary,
                "detectedSignature": hit.signature,
                "detectedDeltaVMetresPerSecond": round(hit.delta_v.total, 4),
                "detectedStartAt": _iso(hit.start_ms),
                "detectedEndAt": _iso(hit.end_ms),
            }
        )

    scored = len(matched) + len(missed)
    return {
        "tableVersion": truth.version,
        "publishedEvents": len(truth.entries),
        "inArchiveWindow": scored,
        "detected": len(matched),
        "notDetected": len(missed),
        "pending": len(pending),
        "detectionRate": (len(matched) / scored) if scored else None,
        "matches": matched,
        "misses": missed,
        "pendingEvents": pending[:200],
        "note": (
            "Events published by an operator but occurring outside the archive's window are "
            "pending, not missed: the archive cannot contain them. The detection rate is "
            "computed only over events the archive could see."
        ),
    }


def _parse_iso_ms(value: Any) -> int | None:
    if not isinstance(value, str) or not value:
        return None
    text = value.replace("Z", "+00:00")
    for parser in (dt.datetime.fromisoformat,):
        try:
            parsed = parser(text)
        except ValueError:
            continue
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt.timezone.utc)
        return int(parsed.timestamp() * 1000)
    return None


# ---------------------------------------------------------------------------
# Per-object summaries: the columns the browser sorts on
# ---------------------------------------------------------------------------
def summarise_objects(
    intervals: Sequence[Interval],
    events: Sequence[OrbitEvent],
    *,
    catalog: dict[int, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """One row per object: how often it corrects, what it spends, where it is going.

    These are the operational questions the surface exists to answer: how often
    a satellite needs correction, who is spending the most Delta-v, what is
    deorbiting, what makes the same correction repeatedly, and what is behaving
    unusually for its class. Each is computed, none is inferred.

    Every rate carries the observation span it was computed over, because a
    "manoeuvres per day" figure from a six-hour archive is not a cadence and
    must not be displayed as one. The interface uses `observedDays` to decide
    whether a rate is publishable at all.
    """
    catalog = catalog or {}
    by_object: dict[int, list[Interval]] = {}
    for interval in intervals:
        by_object.setdefault(interval.norad, []).append(interval)
    events_by_object: dict[int, list[OrbitEvent]] = {}
    for event in events:
        events_by_object.setdefault(event.norad, []).append(event)

    rows: list[dict[str, Any]] = []
    for norad, own in by_object.items():
        own.sort(key=lambda i: i.start_ms)
        own_events = events_by_object.get(norad, [])
        observed_days = (own[-1].end_ms - own[0].start_ms) / 86_400_000.0
        propulsive = [e for e in own_events if e.signature not in NON_PROPULSIVE_SIGNATURES]
        spend = sum(e.delta_v.total for e in propulsive)
        record = catalog.get(norad, {})
        first = own[0]
        decay_metres_per_day = statistics.median(
            [i.delta_a_km * 1000.0 / i.span_days for i in own]
        )
        signatures = [e.signature for e in propulsive]
        repeated = None
        if signatures:
            counts = {s: signatures.count(s) for s in set(signatures)}
            top = max(counts.items(), key=lambda kv: kv[1])
            repeated = {"signature": top[0], "count": top[1]} if top[1] >= 2 else None
        rows.append(
            {
                "norad": norad,
                "name": first.name,
                "objectType": first.object_type,
                "regime": first.regime,
                "perigeeAltitudeKm": round(first.perigee_altitude_km, 1),
                "apogeeAltitudeKm": round(first.apogee_altitude_km, 1),
                "inclinationDeg": round(first.inclination_deg, 3),
                "sunSynchronous": sun_synchronous(
                    first.a_start_km, first.eccentricity, first.inclination_deg
                ),
                "mission": record.get("mission"),
                "sector": record.get("sector"),
                "constellation": record.get("constellation"),
                "intervals": len(own),
                "observedDays": round(observed_days, 4),
                "events": len(propulsive),
                "deltaVMetresPerSecond": round(spend, 4),
                "medianDeltaAMetresPerDay": round(decay_metres_per_day, 2),
                "repeatedSignature": repeated,
                "outOfFamily": any(
                    e.expectation.get("verdict") in ("unusual-for-class", "impossible-for-class",
                                                     "larger-than-typical")
                    for e in propulsive
                ),
                "decaying": decay_metres_per_day < 0 and first.perigee_altitude_km < 1400,
                "purposeLanguagePermitted": not opacity_denied(
                    first.name,
                    record.get("sector"),
                    record.get("mission"),
                    record.get("classificationConfidence"),
                ),
            }
        )
    rows.sort(key=lambda row: -row["deltaVMetresPerSecond"])
    return rows


# ---------------------------------------------------------------------------
# Space weather context
# ---------------------------------------------------------------------------
def kp_context(connection: sqlite3.Connection, start_ms: int, end_ms: int) -> float | None:
    """Highest archived Kp overlapping this interval, or None.

    Kp is the only geomagnetic index this archive holds. Dst and F10.7 are not
    ingested (`docs/orbit-history-design.md` Section 5.7); what they would add
    is stated in `space_weather_gaps()` rather than being silently missing.
    """
    row = connection.execute(
        "SELECT MAX(value) FROM geomagnetic WHERE index_name='kp' AND observed_ms BETWEEN ? AND ?",
        (start_ms, end_ms),
    ).fetchone()
    return None if row is None or row[0] is None else float(row[0])


def space_weather_gaps() -> list[dict[str, str]]:
    """What is not ingested, and what each would add. Published, not hidden."""
    return [
        {
            "index": "F10.7",
            "status": "not-ingested",
            "adds": (
                "The solar EUV proxy. It is the other driver of thermospheric density besides "
                "geomagnetic activity, and it sets the slowly varying baseline that a storm "
                "enhancement sits on top of. Without it, a quiet-time drag baseline drifts with "
                "the solar cycle and has to be re-derived by hand each year."
            ),
        },
        {
            "index": "Dst",
            "status": "not-ingested",
            "adds": (
                "Ring-current energy, which tracks storm main phase far better than Kp. Kp is a "
                "quasi-logarithmic range index capped at 9 and saturates during the largest "
                "storms, exactly when the density enhancement is largest."
            ),
        },
        {
            "index": "Ap (observed)",
            "status": "forecast-only",
            "adds": (
                "A linear equivalent of Kp, which is what empirical thermosphere models actually "
                "take as input. Only the three-day forecast is currently held."
            ),
        },
    ]


# ---------------------------------------------------------------------------
# Archive maturity: what the browser can honestly show today
# ---------------------------------------------------------------------------
def observation_span_days(connection: sqlite3.Connection) -> float:
    """How long this archive has actually been watching, from the capture ledger.

    **Not** the span of the epochs it holds, which is a different and much
    larger number for a reason that will mislead anyone who uses it: a single
    snapshot of the catalogue contains element sets whose epochs are days old
    and, occasionally, epochs stamped in the future. Measured on the live
    archive after one hour of capture, the epoch span read as seventeen days.
    Every maturity decision keyed on it would have been wrong, and one of them
    was: the storm density estimator saw "seventeen days" and ran a
    twelve-thousand-object comparison of an archive against itself, which cost
    thirty-six seconds of a two-hundred-and-forty-second publish budget to
    produce a ratio of one.
    """
    row = connection.execute(
        "SELECT MIN(captured_ms), MAX(captured_ms) FROM capture"
    ).fetchone()
    if not row or row[0] is None or row[1] is None:
        return 0.0
    return (row[1] - row[0]) / 86_400_000.0


def archive_maturity(connection: sqlite3.Connection, intervals: Sequence[Interval]) -> dict[str, Any]:
    """What this archive can and cannot support yet, as a publishable record.

    The interface uses this to choose between showing a feature, showing the
    honest empty state for it, and hiding it. "Not enough history yet" has to
    look deliberate, and it can only look deliberate if the interface knows
    exactly which day it becomes available.
    """
    stats = archive_stats(connection)
    span_days = observation_span_days(connection)
    epoch_span_days = 0.0
    if stats["earliestEpoch"] and stats["latestEpoch"]:
        epoch_span_days = (
            _parse_iso_ms(stats["latestEpoch"]) - _parse_iso_ms(stats["earliestEpoch"])
        ) / 86_400_000.0
    per_object = {}
    for interval in intervals:
        per_object[interval.norad] = per_object.get(interval.norad, 0) + 1
    with_eight = sum(1 for count in per_object.values() if count >= 8)

    capabilities = [
        {
            "id": "population-cohort-screen",
            "available": len(intervals) >= 100,
            "needs": "about a hundred overlapping intervals across the population",
            "why": (
                "The cohort control compares an object against others at the same altitude and "
                "inclination over the same hours. It needs many objects at one moment, not one "
                "object over many months, so it works on the day the archive starts."
            ),
        },
        {
            "id": "per-object-cadence",
            "available": with_eight > 0,
            "objectsReady": with_eight,
            "needs": "eight or more element-set intervals for a single object, typically 3-5 days",
            "why": (
                "How often an object corrects, and whether the corrections are regular, is a "
                "property of one object's own time series. It cannot be borrowed from the "
                "population."
            ),
        },
        {
            "id": "station-keeping-cadence",
            "available": with_eight > 0 and span_days >= 21.0,
            "needs": "about three weeks, because geostationary east-west cycles run one to four weeks",
            "why": (
                "A cadence needs several complete cycles before its regularity means anything. "
                "Four corrections at irregular spacing are not a cadence."
            ),
        },
        {
            "id": "storm-density-enhancement",
            "available": span_days >= 7.0,
            "needs": "a geomagnetically quiet baseline window and a storm window in the same archive",
            "why": (
                "The density ratio is each object's storm-time decay against its OWN quiet-time "
                "decay, so the archive has to contain both."
            ),
        },
        {
            "id": "measured-false-alarm-rate",
            "available": False,
            "needs": "a passive control of at least a few hundred intervals, roughly a month",
            "why": (
                "Until the false-alarm rate is bounded, no event may carry a manoeuvre label. "
                "The plots ship; the labels do not."
            ),
        },
    ]
    return {
        "archive": stats,
        "observationSpanDays": round(span_days, 4),
        "epochSpanDays": round(epoch_span_days, 4),
        "epochSpanNote": (
            "The epoch span is larger than the observation span and is not a measure of how long "
            "this archive has been running: one snapshot of the catalogue already contains element "
            "sets days old. Maturity is decided on the capture ledger."
        ),
        "intervals": len(intervals),
        "objectsWithIntervals": len(per_object),
        "objectsWithEightIntervals": with_eight,
        "capabilities": capabilities,
        "coverageNote": (
            "The archive begins with the first capture on 2026-08-07. Before that there is "
            "nothing, and nothing can back-fill it: the historical bulk element classes are a "
            "separate, more tightly rate-limited product this installation does not use."
        ),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def load_catalog(data_root: Path) -> dict[int, dict[str, Any]]:
    """Object facts from the published catalog artifact, keyed by NORAD id.

    Read from the manifest rather than globbed, because the artifacts are
    content-addressed and their filenames change on every publish. Returns an
    empty mapping rather than raising: a missing catalog degrades the
    expectation match to "no-expectation", which is honest, while an exception
    would take down a publish cycle over a nicety.
    """
    manifest_path = data_root / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text())
        catalog = json.loads((data_root / manifest["catalog"]["path"]).read_text())
    except (OSError, KeyError, json.JSONDecodeError):
        return {}
    out: dict[int, dict[str, Any]] = {}
    for record in catalog.get("satellites", []):
        norad = record.get("id")
        if isinstance(norad, int):
            out[norad] = {
                "mission": record.get("mission"),
                "sector": record.get("sector"),
                "constellation": record.get("constellation"),
                "classificationConfidence": record.get("classificationConfidence"),
                "orbit": record.get("orbit"),
                "name": record.get("name"),
            }
    return out


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, default=None)
    parser.add_argument("--data-root", type=Path, default=ROOT / "public" / "data")
    parser.add_argument("--kappa", type=float, default=DEFAULT_KAPPA)
    parser.add_argument("--limit", type=int, default=25)
    parser.add_argument("--controls", action="store_true", help="print the control measurements only")
    parser.add_argument("--maturity", action="store_true", help="print what the archive can support")
    args = parser.parse_args(argv)

    connection = open_archive(args.archive)
    intervals = load_intervals(connection)
    catalog = load_catalog(args.data_root)

    if args.maturity:
        print(json.dumps(archive_maturity(connection, intervals), indent=2))
        return 0

    events = detect_events(intervals, kappa=args.kappa, catalog=catalog)
    if args.controls:
        stats = archive_stats(connection)
        print(json.dumps({
            "controls": control_rates(intervals, events, kappa=args.kappa),
            "groundTruth": score_against_ground_truth(
                events,
                GroundTruth.load(),
                archive_start_ms=_parse_iso_ms(stats["earliestEpoch"]),
                archive_end_ms=_parse_iso_ms(stats["latestEpoch"]),
            ),
        }, indent=2))
        return 0

    events.sort(key=lambda e: -abs(e.delta_v.total))
    print(json.dumps([e.as_dict() for e in events[: args.limit]], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
