#!/usr/bin/env python3
"""The plasmasphere as a running physics simulation: DGCPM driven by measured Kp.

Why this file exists
--------------------
The site drew the plasmasphere from Carpenter & Anderson (1992) with an
O'Brien & Moldwin (2003) plasmapause. That is an *empirical* description: a
statistical density profile whose one boundary parameter is moved by a
statistical fit to Dst. It has no memory, no local time inside the
plasmasphere, and therefore no dusk bulge and no drainage plume - the two
structures that make a plasmasphere look like a thing the Sun is doing
something to. The site's owner asked for the coupling to be visible, and named
the right model: the **Dynamic Global Core Plasma Model** of

    D. M. Ober, J. L. Horwitz and D. L. Gallagher (1997), "Formation of density
    troughs embedded in the outer plasmasphere by subauroral ion drift events",
    J. Geophys. Res. 102(A7), 14595-14602, doi:10.1029/97JA01046.

DGCPM is a two-dimensional (L, MLT) continuity equation for the *content of a
flux tube*, drifting under E x B in an analytic convection + corotation
electric field, with a dayside ionospheric source and a nightside loss. It is
cheap enough to run inside a five-minute publish cycle and it produces erosion
and plumes from first principles rather than from a fitted boundary.

Where every equation and constant below came from
-------------------------------------------------
Not from memory. Two independent sources were read:

1. **The reference implementation.** DGCPM is a component of the Space Weather
   Modeling Framework and its source is public under Apache 2.0
   (https://github.com/SWMFsoftware/DGCPM). The files that matter are
   ``src/pbo.f`` (the solver: ``initmgridn``, ``filling``, ``upwind``,
   ``gradpot``, ``addcorotpot``, ``coro``, ``ecrossb``, ``getdipolevol``),
   ``src/ModFunctionsDGCPM.f90`` (``saturation``, ``trough``,
   ``dipoleFluxTubeVol``), ``src/dgcpm_setup.f90`` (``GETKPA``: the Kp to
   convection-strength law) and ``src/dgcpm_fields.f90`` (the Volland-Stern
   potential). Every numeric default here - 1.5 days to fill, 3 days to empty
   on the closed nightside, the L^-0.3 filling weight, the flux-tube volume
   expansion - is that code's own default, quoted with its file.
2. **A published statement of the electric field.** V. Pierrard, G. Khazanov,
   J. Cabrera and J. Lemaire (2008), "Influence of the convection electric
   field models on predicted plasmapause positions during magnetic storms",
   J. Geophys. Res. 113, A08212, doi:10.1029/2007JA012612 (open access via
   NASA NTRS 20090028672), section 2, writes the Volland-Stern model as
   ``Phi = A R^2 sin(theta)`` with

       A = 0.045 / (1 - 0.159 Kp + 0.0093 Kp^2)^3   kV / R_E^2

   "adapted by Maynard and Chen [1975]", and states the check this module's
   test uses: A = 45 V/R_E^2 at Kp = 0 and "over 800 V/R_E^2" at Kp = 6. The
   SWMF code's ``A = 7.05E-6/(1.-0.159*KP+0.0093*KP**2)**3`` is in V/m, and
   7.05e-6 V/m x 6.378e6 m = 44.96 V/R_E^2 - the same number, so the two
   sources agree to the printed precision.

Primary references for the pieces: Volland (1973) JGR 78, 171; Stern (1975)
JGR 80, 595; Maynard & Chen (1975) JGR 80, 1009 (the Kp law);
Carpenter & Anderson (1992) JGR 97(A2), 1097 (the saturated ceiling).

The model, in full
------------------
State variable: ``N(L, phi)``, the content of a dipole flux tube per unit
magnetic flux, in m^-3 x (m^3/Wb) = 1/Wb. Equatorial electron density is
``n = N / V(L)`` where V is the flux-tube volume per unit flux.

* **Flux-tube volume** (``dipoleFluxTubeVol``, ModFunctionsDGCPM.f90):

      V(L) = (4 pi / (mu0 M)) (32/35) L^4 sqrt(1 - 1/L)
             (1 + 1/(2L) + 3/(8L^2) + 5/(16L^3)) R_E^4      [m^3/Wb]

* **Electric potential**, in the inertial frame, phi measured from midnight
  and increasing eastward (toward dawn), which is the SWMF code's own
  convention (``getxydipole``: "phi is zero at 24 MLT, positive rotation
  towards dawn"):

      Phi(L, phi) = A R_E L^gamma sin(phi)  -  Phi_c / L                [V]
      A     = 7.05e-6 / (1 - 0.159 Kp + 0.0093 Kp^2)^3                [V/m]
      gamma = 2                       (the shielded Volland-Stern exponent)
      Phi_c = omega mu0 M / (4 pi R_E) = 9.179e4 V                (corotation)

  ``addcorotpot`` writes the corotation term as ``-omega mu0 M/(4 pi L R_E)``,
  which is the familiar -92 kV / L.

* **Drift**. This module differentiates the potential analytically rather than
  by the reference code's centred differences - the potential is a two-term
  closed form, so there is no reason to accept a truncation error:

      E_r   = -(1/R_E) dPhi/dL   = -( 2 A L sin(phi) + Phi_c / (R_E L^2) )
      E_phi = -(1/(L R_E)) dPhi/dphi = - A L cos(phi)
      B(L)  = mu0 M / (4 pi (L R_E)^3)                (equatorial dipole)
      v_r     = E_phi / B                                          [m/s]
      dphi/dt = - E_r / (B L R_E)                                [rad/s]

  which is exactly ``ecrossb``'s pair. Two checks that this is the real
  convection pattern and not its mirror image, both asserted in the tests: at
  midnight with no convection ``dphi/dt`` is positive and equals the corotation
  angular rate, and with convection on, ``v_r`` is inward at midnight and
  outward at noon - sunward flow through the inner magnetosphere.

* **Advection**: dimensionally split first-order upwind on N, radial then
  azimuthal, exactly ``upwind`` in pbo.f. N is a flux-tube content, so it is
  conserved *following a drift path* and the advective (non-conservative) form
  is the physically correct one. First-order upwind under its CFL condition
  cannot create a new maximum or minimum, which is the numerical guarantee the
  tests pin.

* **Sources and losses** (``filling`` in pbo.f), per time step:

  - Dayside (06-18 MLT), where the ionosphere below the tube is sunlit:

        f = ((n_sat(L) - n) / n_sat(L)) * f_max * (L/1)^-0.3 * max(0, -cos phi)
        f_max = V(L_0) n_sat(L_0) 2 L_0 / (FillDays * 86400)

    with L_0 the smallest L on the grid (the smallest flux-tube volume) and
    ``FillDays = 1.5``. Content above saturation is removed, so ``n_sat`` is a
    hard ceiling. ``max(0, -cos phi)`` is the code's ``sin(phi - 90 deg)``
    written for phi measured from midnight: 0 at dawn and dusk, 1 at noon.
  - Nightside (18-06 MLT): ``dN/dt = -N / (EmptyPeriodClosed * 86400)``,
    ``EmptyPeriodClosed = 3`` days.
  - **Outer boundary**: the outermost shell is held at the DGCPM trough
    content, ``n_trough(L) = 0.5 (10/L)^4 cm^-3`` (ModFunctionsDGCPM.f90). A
    flux tube convected in from beyond the model's outer edge therefore arrives
    carrying trough plasma, which is what makes the plasmapause: tubes on
    closed corotating paths refill and stay full, tubes on open paths are
    flushed with trough material and swept sunward.

* **What is deliberately NOT modelled.** The reference code can mask cells
  outside a Shue magnetopause and drain them on a 1-day time constant
  (``EmptyPeriodOpen``); that is off by default and off here, because this grid
  stops at L = 9 and the site already draws the magnetopause from a different,
  better source. There is no field-aligned structure (this is an equatorial
  model), no ring current (no coupling back from the hot population), no
  sub-auroral polarisation stream, no plasmaspheric wind, and no
  interchange/plasmaspheric-boundary-layer physics.

Drive data
----------
Kp, from NOAA SWPC's own products - the same host every other index on this
site comes from, so no new upstream relationship is created:

* ``products/noaa-planetary-k-index.json`` - the 3-hourly planetary Kp for the
  last seven days. This is the spin-up drive.
* ``json/planetary_k_index_1m.json`` - the 1-minute *estimated* Kp, which
  covers the last few hours that the 3-hourly product has not yet closed out.
  ``build_release`` already fetches this for the geomagnetic readout, so it is
  reused rather than refetched.

The two are joined, never averaged: 3-hourly values are used wherever they
exist and the estimated 1-minute values only after the last 3-hourly sample.
The join point is published in the artifact.
"""

from __future__ import annotations

import base64
import datetime as dt
import hashlib
import json
import math
from array import array
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

import numpy as np


# ---------------------------------------------------------------------------
# Published constants
# ---------------------------------------------------------------------------

EARTH_RADIUS_M = 6.378e6          # pbo.f uses this value, not 6371 or 6378137
VACUUM_PERMEABILITY = 4.0 * math.pi * 1.0e-7
DIPOLE_MOMENT_A_M2 = 8.05e22      # ModFunctionsDGCPM.f90 / addcorotpot
EARTH_ANGULAR_RATE_RAD_S = (2.0 * math.pi) / 86400.0

VOLLAND_STERN = {
    # A = a0 / (1 - c1 Kp + c2 Kp^2)^3, in volts per metre; see the module
    # docstring for the two sources this was read from.
    "amplitudeVPerM": 7.05e-6,
    "kpLinear": 0.159,
    "kpQuadratic": 0.0093,
    # The shielding exponent. Pierrard et al. (2008) print Phi = A R^2 sin,
    # i.e. gamma = 2, which is the shielded Volland-Stern form Maynard & Chen
    # fitted their Kp law against.
    "exponent": 2.0,
    "citation": "Volland (1973); Stern (1975); Kp law from Maynard & Chen (1975), JGR 80, 1009",
    "restatedBy": "Pierrard, Khazanov, Cabrera & Lemaire (2008), JGR 113, A08212",
    "doi": "10.1029/2007JA012612",
}

DGCPM_DEFAULTS = {
    # PARAM.XML defaults of the reference implementation.
    "fillDays": 1.5,
    "emptyPeriodClosedDays": 3.0,
    "fillLShellExponent": -0.3,
    "citation": "Ober, Horwitz & Gallagher (1997), JGR 102(A7), 14595-14602",
    "doi": "10.1029/97JA01046",
    "referenceImplementation": "SWMFsoftware/DGCPM (Apache-2.0), src/pbo.f and src/ModFunctionsDGCPM.f90",
}

# Carpenter & Anderson (1992) saturated reference profile, log10 ne = m L + b,
# ne in cm^-3. These two numbers must stay identical to
# `CARPENTER_ANDERSON_1992.saturatedSlopePerL` / `.saturatedIntercept` in
# src/inner-magnetosphere.ts; `tests/test_plasmasphere_dgcpm.py` reads that
# file and fails if they drift apart.
CARPENTER_ANDERSON_SATURATED_SLOPE = -0.3145
CARPENTER_ANDERSON_SATURATED_INTERCEPT = 3.9043

# DGCPM's own trough, ModFunctionsDGCPM.f90: 0.5 (10/L)^4 cm^-3. This is a
# simpler curve than Carpenter & Anderson's local-time-resolved trough (which
# the empirical layer still uses); it is the one the reference solver's outer
# boundary is built on, so it is the one used here.
DGCPM_TROUGH_COEFFICIENT = 0.5
DGCPM_TROUGH_REFERENCE_L = 10.0
DGCPM_TROUGH_EXPONENT = 4.0

# The simulation grid. L runs past the published range on purpose: the outer
# shells are where flux tubes are flushed with trough plasma and swept sunward,
# so they have to be simulated even though they are not drawn.
SIMULATION_L_MINIMUM = 1.5
SIMULATION_L_MAXIMUM = 9.0
SIMULATION_L_COUNT = 76           # 0.1 L spacing
SIMULATION_MLT_COUNT = 120        # 3 degrees, the reference implementation's

# The published grid, trimmed to the range the layer draws and thinned to keep
# the artifact small.
PUBLISHED_L_MINIMUM = 2.0
PUBLISHED_L_MAXIMUM = 8.0
PUBLISHED_L_COUNT = 61            # 0.1 L spacing
PUBLISHED_MLT_COUNT = 48          # half-hour MLT bins

# Same window and the same frame budget as the geospace sequence, so the two
# layers step together when the timeline is scrubbed.
PUBLISHED_HISTORY_HOURS = 48.0
MAX_PUBLISHED_FRAMES = 25
CADENCE_LADDER_MINUTES = (30, 60, 120)

# The longest spin-up this module will run before the published window, in
# hours. Refilling has a multi-day time constant, so more history is better;
# the seven days SWPC publishes is the practical ceiling and also the cap.
MAX_SPIN_UP_HOURS = 168.0
# Below this there is not enough drive to claim the outer plasmasphere has
# settled, and the module refuses rather than publishing a spun-up-looking
# field that is really an initial condition.
MIN_SPIN_UP_HOURS = 24.0

# Integration limits. dt is chosen from the CFL condition every step and then
# clamped into this range.
MAX_TIME_STEP_S = 120.0
MIN_TIME_STEP_S = 5.0
CFL_SAFETY = 0.4

DENSITY_ENCODING = {
    "quantity": "equatorial electron density",
    "scale": "log10",
    "minimum": -1.0,
    "maximum": 4.0,
    "units": "cm⁻³",
    "storage": "little-endian uint16 base64, L-major with MLT varying fastest",
}

# The plasmapause is reported as a stated contour, not as a fitted boundary.
# 50 cm^-3 is the level model/IMAGE-EUV comparisons conventionally use; the
# artifact says so, and the steepest-gradient location is published beside it
# so a reader can see the two agree.
PLASMAPAUSE_CONTOUR_CM3 = 50.0

SCHEMA_VERSION = "dgcpm-plasmasphere.v1"


class PlasmasphereDgcpmError(ValueError):
    """Raised when the drive data cannot support an honest simulation."""


# ---------------------------------------------------------------------------
# Closed-form pieces, each one separately testable
# ---------------------------------------------------------------------------


def convection_amplitude_v_per_m(kp: float) -> float:
    """Volland-Stern amplitude A at a given Kp, in volts per metre.

    ``A = 7.05e-6 / (1 - 0.159 Kp + 0.0093 Kp^2)^3``. The denominator has its
    minimum at Kp = 0.159/(2*0.0093) = 8.55 and never reaches zero over the
    Kp range that exists (0-9), so no guard is needed for the physical domain;
    a guard is present anyway because a corrupt index must not divide by zero.
    """
    if not math.isfinite(kp):
        raise PlasmasphereDgcpmError("Kp is not a finite number")
    kp = min(max(kp, 0.0), 9.0)
    denominator = (1.0 - VOLLAND_STERN["kpLinear"] * kp + VOLLAND_STERN["kpQuadratic"] * kp * kp) ** 3
    if denominator <= 0:
        raise PlasmasphereDgcpmError(f"degenerate Volland-Stern denominator at Kp={kp}")
    return VOLLAND_STERN["amplitudeVPerM"] / denominator


def convection_amplitude_v_per_re2(kp: float) -> float:
    """The same amplitude in the units the papers print it in, V/R_E^2."""
    return convection_amplitude_v_per_m(kp) * EARTH_RADIUS_M


def corotation_potential_scale_v() -> float:
    """Phi_c in ``Phi_corotation = -Phi_c / L``, in volts. About 91.8 kV."""
    return (
        EARTH_ANGULAR_RATE_RAD_S * VACUUM_PERMEABILITY * DIPOLE_MOMENT_A_M2
    ) / (4.0 * math.pi * EARTH_RADIUS_M)


def equatorial_dipole_field_t(l_shell: np.ndarray | float) -> np.ndarray | float:
    """Equatorial dipole field strength at L, in tesla."""
    return VACUUM_PERMEABILITY * DIPOLE_MOMENT_A_M2 / (
        4.0 * math.pi * (np.asarray(l_shell, dtype=float) * EARTH_RADIUS_M) ** 3
    )


def dipole_flux_tube_volume_m3_per_wb(l_shell: np.ndarray | float) -> np.ndarray | float:
    """Flux-tube volume per unit magnetic flux, m^3/Wb.

    ``dipoleFluxTubeVol`` of ModFunctionsDGCPM.f90, transcribed term for term.
    Valid for L > 1; the sqrt(1 - 1/L) factor is the ionospheric foot.
    """
    l_values = np.asarray(l_shell, dtype=float)
    return (
        (4.0 * math.pi) / (VACUUM_PERMEABILITY * DIPOLE_MOMENT_A_M2)
        * (32.0 / 35.0)
        * l_values ** 4
        * np.sqrt(1.0 - 1.0 / l_values)
        * (1.0 + 1.0 / (2.0 * l_values) + 3.0 / (8.0 * l_values ** 2) + 5.0 / (16.0 * l_values ** 3))
        * EARTH_RADIUS_M ** 4
    )


def saturation_density_cm3(l_shell: np.ndarray | float) -> np.ndarray | float:
    """Carpenter & Anderson's saturated plasmasphere density, cm^-3.

    The bare reference profile, which is what DGCPM uses as its ceiling. The
    paper's annual, semiannual and solar-cycle terms are NOT applied here: the
    reference implementation does not apply them, and the empirical layer that
    does apply them is still published beside this one.
    """
    l_values = np.asarray(l_shell, dtype=float)
    return 10.0 ** (
        CARPENTER_ANDERSON_SATURATED_SLOPE * l_values + CARPENTER_ANDERSON_SATURATED_INTERCEPT
    )


def trough_density_cm3(l_shell: np.ndarray | float) -> np.ndarray | float:
    """DGCPM's plasma-trough density, cm^-3: ``0.5 (10/L)^4``."""
    l_values = np.asarray(l_shell, dtype=float)
    return DGCPM_TROUGH_COEFFICIENT * (DGCPM_TROUGH_REFERENCE_L / l_values) ** DGCPM_TROUGH_EXPONENT


def total_potential_v(
    l_shell: np.ndarray | float,
    phi_rad: np.ndarray | float,
    amplitude_v_per_m: float,
) -> np.ndarray | float:
    """Volland-Stern convection plus corotation, in volts.

    ``phi`` is measured from midnight and increases eastward (toward dawn), so
    MLT = phi * 12/pi. Under the GSM mapping the rest of the site uses
    (x sunward, y duskward) this sign convention gives sunward convection;
    ``tests/test_plasmasphere_dgcpm.py`` asserts that rather than trusting it.
    """
    l_values = np.asarray(l_shell, dtype=float)
    return (
        amplitude_v_per_m * EARTH_RADIUS_M * l_values ** VOLLAND_STERN["exponent"] * np.sin(phi_rad)
        - corotation_potential_scale_v() / l_values
    )


def drift_velocity(
    l_shell: np.ndarray,
    phi_rad: np.ndarray,
    amplitude_v_per_m: float,
) -> tuple[np.ndarray, np.ndarray]:
    """E x B drift as (radial m/s, azimuthal rad/s) from the analytic potential."""
    corotation = corotation_potential_scale_v()
    field = equatorial_dipole_field_t(l_shell)
    e_radial = -(
        2.0 * amplitude_v_per_m * l_shell * np.sin(phi_rad)
        + corotation / (EARTH_RADIUS_M * l_shell ** 2)
    )
    e_azimuthal = -amplitude_v_per_m * l_shell * np.cos(phi_rad)
    radial_m_s = e_azimuthal / field
    azimuthal_rad_s = -e_radial / (field * l_shell * EARTH_RADIUS_M)
    return radial_m_s, azimuthal_rad_s


def stagnation_l(amplitude_v_per_m: float) -> float:
    """Where the dusk-meridian flow stops: L_s = (Phi_c / (2 A R_E))^(1/3).

    Setting the azimuthal drift to zero at phi = 270 deg (dusk, sin phi = -1)
    gives ``2 A L sin(phi) + Phi_c/(R_E L^2) = 0``. This is the nose of the
    classic teardrop and the reason the bulge is on the dusk side.
    """
    if amplitude_v_per_m <= 0:
        raise PlasmasphereDgcpmError("convection amplitude must be positive")
    return (corotation_potential_scale_v() / (2.0 * amplitude_v_per_m * EARTH_RADIUS_M)) ** (1.0 / 3.0)


def last_closed_boundary_l(
    l_values: np.ndarray,
    phi_values: np.ndarray,
    amplitude_v_per_m: float,
) -> np.ndarray:
    """Radius of the last closed equipotential at each MLT, for the spin-up start.

    The stagnation point sits on the dusk meridian at ``stagnation_l``; its
    potential is the value of the last closed equipotential. Walking outward
    from the Earth along each MLT, the boundary is the first crossing of that
    value - a radial-first connectivity rule, which is exact for a teardrop and
    avoids picking up the disconnected low-potential region that lies beyond
    the stagnation point on the dusk side. Where there is no crossing (the dusk
    meridian itself) the boundary is the stagnation radius.
    """
    stagnation = stagnation_l(amplitude_v_per_m)
    threshold = float(total_potential_v(stagnation, -math.pi / 2.0, amplitude_v_per_m))
    grid_l, grid_phi = np.meshgrid(l_values, phi_values, indexing="ij")
    potential = total_potential_v(grid_l, grid_phi, amplitude_v_per_m)
    outside = potential >= threshold
    boundary = np.full(phi_values.shape, stagnation, dtype=float)
    for index in range(phi_values.size):
        column = np.flatnonzero(outside[:, index])
        if column.size:
            boundary[index] = float(l_values[column[0]])
    return np.minimum(boundary, float(l_values[-1]))


# ---------------------------------------------------------------------------
# The Kp drive
# ---------------------------------------------------------------------------


def parse_utc(value: str) -> dt.datetime:
    text = value.strip().replace("Z", "+00:00")
    parsed = dt.datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def utc_iso(value: dt.datetime) -> str:
    return value.astimezone(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def parse_three_hour_kp(raw: Any) -> list[tuple[dt.datetime, float]]:
    """Parse SWPC ``products/noaa-planetary-k-index.json``.

    The product is a header row followed by data rows:
    ``["time_tag", "Kp", "a_running", "station_count"]``. Some deployments
    serve it as a list of objects instead; both shapes are accepted, and a row
    this function cannot read is skipped rather than guessed at.
    """
    samples: list[tuple[dt.datetime, float]] = []
    if isinstance(raw, list) and raw and isinstance(raw[0], list):
        header = [str(cell).strip().lower() for cell in raw[0]]
        try:
            time_index = header.index("time_tag")
            kp_index = header.index("kp")
        except ValueError as error:
            raise PlasmasphereDgcpmError("planetary Kp product has no time_tag/Kp columns") from error
        rows: Iterable[Any] = raw[1:]
        for row in rows:
            if not isinstance(row, list) or len(row) <= max(time_index, kp_index):
                continue
            sample = _kp_sample(row[time_index], row[kp_index])
            if sample is not None:
                samples.append(sample)
    elif isinstance(raw, list):
        for row in raw:
            if not isinstance(row, dict):
                continue
            sample = _kp_sample(row.get("time_tag"), row.get("Kp", row.get("kp")))
            if sample is not None:
                samples.append(sample)
    else:
        raise PlasmasphereDgcpmError("planetary Kp product is not a list")
    return sorted(set(samples))


def parse_estimated_kp(raw: Any) -> list[tuple[dt.datetime, float]]:
    """Parse SWPC ``json/planetary_k_index_1m.json`` (estimated Kp).

    The product carries two numbers per row. ``kp_index`` is rounded to a whole
    unit; ``estimated_kp`` is the continuous estimate the rounding came from,
    and it is the one used here - the convection amplitude is cubed in Kp, so
    a whole-unit staircase would put visible steps in the drift field that the
    index does not actually assert. ``kp_index`` is the fallback when the
    continuous column is absent.
    """
    samples: list[tuple[dt.datetime, float]] = []
    if not isinstance(raw, list):
        raise PlasmasphereDgcpmError("estimated Kp product is not a list")
    for row in raw:
        if not isinstance(row, dict):
            continue
        value = row.get("estimated_kp")
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            value = row.get("kp_index")
        sample = _kp_sample(row.get("time_tag"), value)
        if sample is not None:
            samples.append(sample)
    return sorted(set(samples))


def _kp_sample(time_value: Any, kp_value: Any) -> tuple[dt.datetime, float] | None:
    if not isinstance(time_value, str):
        return None
    if not isinstance(kp_value, (int, float)) or isinstance(kp_value, bool):
        return None
    kp = float(kp_value)
    if not math.isfinite(kp) or not 0.0 <= kp <= 9.0:
        return None
    try:
        return parse_utc(time_value), kp
    except ValueError:
        return None


def join_kp_series(
    three_hour: Sequence[tuple[dt.datetime, float]],
    estimated: Sequence[tuple[dt.datetime, float]],
    *,
    estimated_step_minutes: int = 30,
) -> tuple[list[tuple[dt.datetime, float]], dict[str, Any]]:
    """Join the definitive 3-hourly Kp with the estimated 1-minute tail.

    The two are never averaged and never overlap in the joined series: the
    3-hourly values are used wherever they exist, and the estimated series
    contributes only samples strictly after the last 3-hourly one, thinned to
    ``estimated_step_minutes`` so a few thousand 1-minute rows do not dominate
    a seven-day drive. The join instant is returned so the artifact can print
    which part of the drive is estimated.
    """
    if not three_hour:
        raise PlasmasphereDgcpmError("no 3-hourly planetary Kp samples")
    joined = list(three_hour)
    boundary = joined[-1][0]
    step = dt.timedelta(minutes=estimated_step_minutes)
    next_allowed = boundary + step
    estimated_used = 0
    for at, kp in estimated:
        if at <= boundary or at < next_allowed:
            continue
        joined.append((at, kp))
        estimated_used += 1
        next_allowed = at + step
    provenance = {
        "definitiveFrom": utc_iso(three_hour[0][0]),
        "definitiveTo": utc_iso(boundary),
        "definitiveCount": len(three_hour),
        "definitiveCadenceHours": 3,
        "estimatedFrom": utc_iso(joined[len(three_hour)][0]) if estimated_used else None,
        "estimatedTo": utc_iso(joined[-1][0]) if estimated_used else None,
        "estimatedCount": estimated_used,
        "estimatedStepMinutes": estimated_step_minutes,
        "joinRule": (
            "3-hourly planetary Kp wherever it exists; the 1-minute estimated Kp only after the "
            "last 3-hourly sample. The two series are never averaged together."
        ),
    }
    return joined, provenance


def kp_at(series: Sequence[tuple[dt.datetime, float]], at: dt.datetime) -> float:
    """Kp interpolated linearly in time, held flat outside the record.

    The reference implementation interpolates its Kp file the same way. Kp is
    really a 3-hour step index; interpolating avoids stepping the convection
    field discontinuously, and the difference is far inside the index's own
    one-third-unit resolution.
    """
    if not series:
        raise PlasmasphereDgcpmError("empty Kp series")
    if at <= series[0][0]:
        return series[0][1]
    if at >= series[-1][0]:
        return series[-1][1]
    low, high = 0, len(series) - 1
    while high - low > 1:
        middle = (low + high) // 2
        if series[middle][0] <= at:
            low = middle
        else:
            high = middle
    span = (series[high][0] - series[low][0]).total_seconds()
    if span <= 0:
        return series[low][1]
    weight = (at - series[low][0]).total_seconds() / span
    return series[low][1] + weight * (series[high][1] - series[low][1])


# ---------------------------------------------------------------------------
# The solver
# ---------------------------------------------------------------------------


class DgcpmGrid:
    """The (L, MLT) grid and everything on it that never changes."""

    def __init__(
        self,
        *,
        l_minimum: float = SIMULATION_L_MINIMUM,
        l_maximum: float = SIMULATION_L_MAXIMUM,
        l_count: int = SIMULATION_L_COUNT,
        mlt_count: int = SIMULATION_MLT_COUNT,
    ) -> None:
        if l_count < 4 or mlt_count < 8:
            raise PlasmasphereDgcpmError("DGCPM grid is too coarse to advect on")
        if not 1.0 < l_minimum < l_maximum:
            raise PlasmasphereDgcpmError("DGCPM grid needs 1 < Lmin < Lmax")
        self.l_values = np.linspace(l_minimum, l_maximum, l_count)
        self.delta_l = float(self.l_values[1] - self.l_values[0])
        self.phi_values = np.arange(mlt_count) * (2.0 * math.pi / mlt_count)
        self.delta_phi = 2.0 * math.pi / mlt_count
        self.grid_l, self.grid_phi = np.meshgrid(self.l_values, self.phi_values, indexing="ij")
        self.volume = np.asarray(dipole_flux_tube_volume_m3_per_wb(self.grid_l), dtype=float)
        # cm^-3 -> m^-3 for the content bookkeeping; the published density goes
        # back to cm^-3, which is the unit the legend and the papers use.
        self.saturation_m3 = np.asarray(saturation_density_cm3(self.grid_l), dtype=float) * 1.0e6
        self.trough_m3 = np.asarray(trough_density_cm3(self.grid_l), dtype=float) * 1.0e6
        self.saturated_content = self.saturation_m3 * self.volume
        self.trough_content = self.trough_m3 * self.volume
        # Dayside weight, `filling`'s sin(phi - 90 deg) written for phi from
        # midnight: zero at dawn and dusk, one at noon, zero all night.
        self.dayside_weight = np.maximum(0.0, -np.cos(self.grid_phi))
        self.fill_shape = self.grid_l ** DGCPM_DEFAULTS["fillLShellExponent"]
        smallest = float(self.l_values[0])
        self.fill_rate_ceiling = float(
            dipole_flux_tube_volume_m3_per_wb(smallest)
            * saturation_density_cm3(smallest) * 1.0e6
            * 2.0 * smallest
            / (DGCPM_DEFAULTS["fillDays"] * 86400.0)
        )

    @property
    def mlt_hours(self) -> np.ndarray:
        return self.phi_values * (12.0 / math.pi)


def initial_content(grid: DgcpmGrid, kp: float) -> np.ndarray:
    """The spin-up start: saturated inside the last closed equipotential, trough outside.

    This is ``initmgridn`` of pbo.f with the reference code's all-cells-closed
    mask replaced by the actual last closed equipotential for the first Kp,
    which is a better starting guess and is forgotten within a day or two of
    spin-up in any case.
    """
    boundary = last_closed_boundary_l(grid.l_values, grid.phi_values, convection_amplitude_v_per_m(kp))
    inside = grid.grid_l <= boundary[np.newaxis, :]
    return np.where(inside, grid.saturated_content, grid.trough_content)


def _upwind_step(
    content: np.ndarray,
    radial_m_s: np.ndarray,
    azimuthal_rad_s: np.ndarray,
    grid: DgcpmGrid,
    step_s: float,
) -> np.ndarray:
    """One dimensionally-split first-order upwind step, radial then azimuthal.

    Transcribed from ``upwind`` in pbo.f, including its boundary treatment: the
    innermost and outermost shells only advect when the flow is *into* the grid
    from a cell that exists, so nothing is drawn from outside the domain.
    """
    radial_courant = radial_m_s * step_s / (grid.delta_l * EARTH_RADIUS_M)
    forward = np.empty_like(content)
    forward[:-1] = content[1:]
    forward[-1] = content[-1]
    backward = np.empty_like(content)
    backward[1:] = content[:-1]
    backward[0] = content[0]
    half = np.where(
        radial_courant > 0.0,
        content - radial_courant * (content - backward),
        content - radial_courant * (forward - content),
    )

    azimuthal_courant = azimuthal_rad_s * step_s / grid.delta_phi
    ahead = np.roll(half, -1, axis=1)
    behind = np.roll(half, 1, axis=1)
    return np.where(
        azimuthal_courant > 0.0,
        half - azimuthal_courant * (half - behind),
        half - azimuthal_courant * (ahead - half),
    )


def _time_step_s(
    radial_m_s: np.ndarray,
    azimuthal_rad_s: np.ndarray,
    grid: DgcpmGrid,
    remaining_s: float,
) -> float:
    """The CFL-limited step, clamped and never overshooting the target time."""
    radial_speed = float(np.max(np.abs(radial_m_s)))
    azimuthal_speed = float(np.max(np.abs(azimuthal_rad_s)))
    limits = [MAX_TIME_STEP_S, remaining_s]
    if radial_speed > 0:
        limits.append(CFL_SAFETY * grid.delta_l * EARTH_RADIUS_M / radial_speed)
    if azimuthal_speed > 0:
        limits.append(CFL_SAFETY * grid.delta_phi / azimuthal_speed)
    return max(MIN_TIME_STEP_S, min(limits))


class DgcpmState:
    """Flux-tube content on the grid, plus the bookkeeping the tests check."""

    def __init__(self, grid: DgcpmGrid, content: np.ndarray) -> None:
        self.grid = grid
        self.content = np.array(content, dtype=float)
        self.filled_total = 0.0
        self.lost_total = 0.0
        self.steps = 0

    def density_cm3(self) -> np.ndarray:
        return self.content / self.grid.volume / 1.0e6

    def advance_to(
        self,
        start: dt.datetime,
        end: dt.datetime,
        kp_series: Sequence[tuple[dt.datetime, float]],
    ) -> None:
        """Integrate from ``start`` to ``end``, re-reading Kp at every step."""
        if end <= start:
            return
        grid = self.grid
        remaining = (end - start).total_seconds()
        now = start
        while remaining > 1e-6:
            kp = kp_at(kp_series, now)
            amplitude = convection_amplitude_v_per_m(kp)
            radial, azimuthal = drift_velocity(grid.grid_l, grid.grid_phi, amplitude)
            step = _time_step_s(radial, azimuthal, grid, remaining)
            self.content = _upwind_step(self.content, radial, azimuthal, grid, step)
            self._apply_sources(step)
            self.content[-1, :] = grid.trough_content[-1, :]
            remaining -= step
            now = now + dt.timedelta(seconds=step)
            self.steps += 1

    def _apply_sources(self, step_s: float) -> None:
        """`filling` of pbo.f: dayside source with a ceiling, nightside decay."""
        grid = self.grid
        deficit = np.clip(
            (grid.saturated_content - self.content) / grid.saturated_content, 0.0, 1.0
        )
        added = (
            deficit * grid.fill_rate_ceiling * grid.fill_shape * grid.dayside_weight * step_s
        )
        self.content = self.content + added
        self.filled_total += float(np.sum(added))
        # Content above the Carpenter & Anderson ceiling is removed, exactly as
        # the reference implementation does.
        excess = np.maximum(0.0, self.content - grid.saturated_content)
        self.content = self.content - excess
        self.lost_total += float(np.sum(excess))
        # Nightside closed-field-line loss.
        night = grid.dayside_weight <= 0.0
        decay = step_s / (DGCPM_DEFAULTS["emptyPeriodClosedDays"] * 86400.0)
        removed = np.where(night, self.content * decay, 0.0)
        self.content = self.content - removed
        self.lost_total += float(np.sum(removed))
        np.clip(self.content, 1.0e-30, None, out=self.content)


# ---------------------------------------------------------------------------
# Diagnostics: the numbers that decide whether the picture is true
# ---------------------------------------------------------------------------


def plasmapause_radius_by_mlt(
    density_cm3: np.ndarray,
    l_values: np.ndarray,
    *,
    contour_cm3: float = PLASMAPAUSE_CONTOUR_CM3,
) -> np.ndarray:
    """Outermost crossing of the stated density contour at each MLT, in L.

    Linear interpolation in log10(n) between the two bracketing shells. NaN
    where the profile never reaches the contour, which is a real state (a
    plasmasphere eroded inside the grid's inner edge would produce it) and is
    reported rather than filled in.
    """
    log_density = np.log10(np.maximum(density_cm3, 1e-30))
    target = math.log10(contour_cm3)
    above = log_density >= target
    result = np.full(density_cm3.shape[1], math.nan)
    for column in range(density_cm3.shape[1]):
        indices = np.flatnonzero(above[:, column])
        if indices.size == 0:
            continue
        outermost = int(indices[-1])
        if outermost >= density_cm3.shape[0] - 1:
            result[column] = float(l_values[outermost])
            continue
        low = log_density[outermost, column]
        high = log_density[outermost + 1, column]
        if low == high:
            result[column] = float(l_values[outermost])
            continue
        weight = (low - target) / (low - high)
        result[column] = float(
            l_values[outermost] + weight * (l_values[outermost + 1] - l_values[outermost])
        )
    return result


def steepest_gradient_l(density_cm3: np.ndarray, l_values: np.ndarray) -> np.ndarray:
    """Where |d log10 n / dL| is largest at each MLT, in L. The physical knee."""
    log_density = np.log10(np.maximum(density_cm3, 1e-30))
    gradient = np.abs(np.diff(log_density, axis=0)) / np.diff(l_values)[:, np.newaxis]
    centres = 0.5 * (l_values[:-1] + l_values[1:])
    return centres[np.argmax(gradient, axis=0)]


def plume_metrics(
    plasmapause_l: np.ndarray,
    mlt_hours: np.ndarray,
    *,
    minimum_extent_l: float = 0.5,
    dusk_sector: tuple[float, float] = (13.0, 22.0),
    night_sector: tuple[float, float] = (21.0, 3.0),
) -> dict[str, Any]:
    """Is there a dusk-side drainage plume, and how far out does it reach?

    A plume is a protrusion of plasmaspheric-density material beyond the
    corotating body of the plasmasphere, in the dusk-to-pre-midnight sector.
    Measured as: the largest plasmapause radius in the dusk sector, minus the
    median plasmapause radius across the night sector, which is the part of the
    boundary the convection field pushes inward hardest. The numbers are
    published per frame so the claim on screen can be checked against them.
    """
    finite = np.isfinite(plasmapause_l)
    if not finite.any():
        return {"present": False, "reason": "no plasmapause crossing at any MLT"}
    hours = np.asarray(mlt_hours, dtype=float)
    dusk = finite & (hours >= dusk_sector[0]) & (hours <= dusk_sector[1])
    night = finite & ((hours >= night_sector[0]) | (hours <= night_sector[1]))
    if not dusk.any() or not night.any():
        return {"present": False, "reason": "dusk or night sector has no plasmapause crossing"}
    dusk_index = int(np.argmax(np.where(dusk, plasmapause_l, -np.inf)))
    dusk_peak = float(plasmapause_l[dusk_index])
    night_median = float(np.median(plasmapause_l[night]))
    extent = dusk_peak - night_median
    return {
        "present": bool(extent >= minimum_extent_l),
        "peakMltHours": round(float(hours[dusk_index]), 2),
        "peakL": round(dusk_peak, 3),
        "nightMedianL": round(night_median, 3),
        "extentL": round(extent, 3),
        "thresholdL": minimum_extent_l,
    }


# ---------------------------------------------------------------------------
# Encoding and publishing
# ---------------------------------------------------------------------------


def _resample(density_cm3: np.ndarray, grid: DgcpmGrid) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Sample the simulated field onto the published (L, MLT) grid.

    Linear in L and in MLT, with MLT wrapping. Sampling only ever interpolates
    inside the simulated domain - the published L range is strictly inside it -
    so nothing here extrapolates.
    """
    l_out = np.linspace(PUBLISHED_L_MINIMUM, PUBLISHED_L_MAXIMUM, PUBLISHED_L_COUNT)
    mlt_out = np.arange(PUBLISHED_MLT_COUNT) * (24.0 / PUBLISHED_MLT_COUNT)
    phi_out = mlt_out * (math.pi / 12.0)
    # Interpolate in L first.
    radial = np.empty((l_out.size, density_cm3.shape[1]))
    for column in range(density_cm3.shape[1]):
        radial[:, column] = np.interp(l_out, grid.l_values, density_cm3[:, column])
    # Then in phi, with the periodic wrap made explicit.
    wrapped_phi = np.concatenate([grid.phi_values, [grid.phi_values[0] + 2.0 * math.pi]])
    out = np.empty((l_out.size, phi_out.size))
    for row in range(l_out.size):
        wrapped = np.concatenate([radial[row], [radial[row, 0]]])
        out[row] = np.interp(phi_out, wrapped_phi, wrapped)
    return out, l_out, mlt_out


def encode_density(density_cm3: np.ndarray) -> str:
    """Quantise log10(density) onto uint16 and base64 it, L-major."""
    minimum = float(DENSITY_ENCODING["minimum"])
    maximum = float(DENSITY_ENCODING["maximum"])
    span = maximum - minimum
    logarithmic = np.log10(np.maximum(density_cm3, 1e-30))
    normalised = np.clip((logarithmic - minimum) / span, 0.0, 1.0)
    values = array("H", np.rint(normalised * 65535).astype(np.uint16).ravel(order="C").tolist())
    if array("H", [1]).tobytes()[0] != 1:  # pragma: no cover - big-endian hosts
        values.byteswap()
    return base64.b64encode(values.tobytes()).decode("ascii")


def published_cadence_minutes(hours: float, budget: int = MAX_PUBLISHED_FRAMES) -> int:
    for cadence in CADENCE_LADDER_MINUTES:
        if (hours * 60.0) / cadence <= budget - 1:
            return cadence
    return CADENCE_LADDER_MINUTES[-1]


def frame_times(end: dt.datetime, hours: float, cadence_minutes: int) -> list[dt.datetime]:
    """Frame instants on a fixed UTC grid, so the artifact does not churn.

    Anchoring to a fixed grid rather than to "now" is what lets the simulation
    be cached between publish cycles: the frames a cycle asks for only change
    when the clock crosses a cadence boundary or when Kp is updated.
    """
    step = cadence_minutes * 60
    latest = int(end.timestamp()) // step * step
    earliest = latest - int(hours * 3600)
    return [
        dt.datetime.fromtimestamp(stamp, tz=dt.timezone.utc)
        for stamp in range(earliest, latest + 1, step)
    ]


def simulate(
    kp_series: Sequence[tuple[dt.datetime, float]],
    frames_at: Sequence[dt.datetime],
    *,
    grid: DgcpmGrid | None = None,
    spin_up_from: dt.datetime | None = None,
) -> dict[str, Any]:
    """Run the model and return one published frame per requested instant."""
    if not kp_series:
        raise PlasmasphereDgcpmError("no Kp drive")
    if not frames_at:
        raise PlasmasphereDgcpmError("no frame times requested")
    grid = grid or DgcpmGrid()
    ordered = sorted(frames_at)
    start = spin_up_from or kp_series[0][0]
    spin_up_hours = (ordered[0] - start).total_seconds() / 3600.0
    if spin_up_hours < MIN_SPIN_UP_HOURS:
        raise PlasmasphereDgcpmError(
            f"only {spin_up_hours:.1f} h of Kp before the first frame; "
            f"{MIN_SPIN_UP_HOURS:.0f} h is the minimum this module will spin up from"
        )
    if spin_up_hours > MAX_SPIN_UP_HOURS:
        start = ordered[0] - dt.timedelta(hours=MAX_SPIN_UP_HOURS)
        spin_up_hours = MAX_SPIN_UP_HOURS

    state = DgcpmState(grid, initial_content(grid, kp_at(kp_series, start)))
    frames: list[dict[str, Any]] = []
    cursor = start
    for at in ordered:
        state.advance_to(cursor, at, kp_series)
        cursor = at
        density = state.density_cm3()
        published, l_values, mlt_hours = _resample(density, grid)
        boundary = plasmapause_radius_by_mlt(published, l_values)
        kp = kp_at(kp_series, at)
        frames.append(
            {
                "validAt": utc_iso(at),
                "kp": round(kp, 3),
                "convectionAmplitudeVPerRe2": round(convection_amplitude_v_per_re2(kp), 2),
                "stagnationL": round(stagnation_l(convection_amplitude_v_per_m(kp)), 3),
                "densityU16": encode_density(published),
                "plasmapauseLByMlt": [
                    None if not math.isfinite(value) else round(float(value), 3) for value in boundary
                ],
                "steepestGradientLByMlt": [
                    round(float(value), 3) for value in steepest_gradient_l(published, l_values)
                ],
                "plume": plume_metrics(boundary, mlt_hours),
                "totalContentPerWb": float(np.sum(state.content)),
            }
        )
    return {
        "frames": frames,
        "spinUpHours": round(spin_up_hours, 2),
        "spinUpFrom": utc_iso(start),
        "integrationSteps": state.steps,
        "filledTotalPerWb": state.filled_total,
        "lostTotalPerWb": state.lost_total,
        "gridLValues": [round(float(value), 4) for value in np.linspace(
            PUBLISHED_L_MINIMUM, PUBLISHED_L_MAXIMUM, PUBLISHED_L_COUNT
        )],
        "gridMltHours": [round(float(value), 4) for value in
                         np.arange(PUBLISHED_MLT_COUNT) * (24.0 / PUBLISHED_MLT_COUNT)],
    }


def build_bundle(
    kp_series: Sequence[tuple[dt.datetime, float]],
    drive_provenance: dict[str, Any],
    *,
    now: dt.datetime | None = None,
    grid: DgcpmGrid | None = None,
) -> dict[str, Any]:
    """The published artifact: frames plus everything needed to read them."""
    now = (now or dt.datetime.now(dt.timezone.utc)).astimezone(dt.timezone.utc)
    cadence = published_cadence_minutes(PUBLISHED_HISTORY_HOURS)
    times = frame_times(now, PUBLISHED_HISTORY_HOURS, cadence)
    result = simulate(kp_series, times, grid=grid)
    frames = result["frames"]
    return {
        "schemaVersion": SCHEMA_VERSION,
        "status": "physics-simulation",
        "model": {
            "name": "Dynamic Global Core Plasma Model (DGCPM)",
            "citation": DGCPM_DEFAULTS["citation"],
            "doi": DGCPM_DEFAULTS["doi"],
            "referenceImplementation": DGCPM_DEFAULTS["referenceImplementation"],
            "electricField": {
                "name": "Volland-Stern with the Maynard & Chen Kp law, plus corotation",
                "citation": VOLLAND_STERN["citation"],
                "restatedBy": VOLLAND_STERN["restatedBy"],
                "doi": VOLLAND_STERN["doi"],
                "potential": "Phi(L,phi) = A R_E L^2 sin(phi) - 91.8 kV / L, phi from midnight increasing eastward",
                "amplitude": "A = 7.05e-6 / (1 - 0.159 Kp + 0.0093 Kp^2)^3 V/m = 45 V/Re^2 at Kp 0",
            },
            "saturationCeiling": (
                "Carpenter & Anderson (1992) saturated profile log10 ne = "
                f"{CARPENTER_ANDERSON_SATURATED_SLOPE} L + {CARPENTER_ANDERSON_SATURATED_INTERCEPT}, cm^-3"
            ),
            "troughBoundary": "DGCPM trough 0.5 (10/L)^4 cm^-3, held at the outer edge of the simulated grid",
            "fillDays": DGCPM_DEFAULTS["fillDays"],
            "emptyPeriodClosedDays": DGCPM_DEFAULTS["emptyPeriodClosedDays"],
            "advection": "dimensionally split first-order upwind on flux-tube content, CFL-limited",
            "simulatedGrid": {
                "lMinimum": SIMULATION_L_MINIMUM,
                "lMaximum": SIMULATION_L_MAXIMUM,
                "lCount": SIMULATION_L_COUNT,
                "mltCount": SIMULATION_MLT_COUNT,
            },
            "notModelled": [
                "any field-aligned density structure: this is an equatorial model, as Carpenter & Anderson is",
                "coupling back to the ring current; the ring current does not modify this field, and this field does not modify the ring current",
                "sub-auroral polarisation streams, plasmaspheric wind, and interchange/boundary-layer physics",
                "an open/closed magnetopause mask, so no loss to the magnetopause is applied",
                "the annual, semiannual and solar-cycle terms of Carpenter & Anderson, which the reference implementation also omits",
            ],
        },
        "drive": {
            "index": "planetary Kp",
            "sources": [
                "https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json",
                "https://services.swpc.noaa.gov/json/planetary_k_index_1m.json",
            ],
            **drive_provenance,
            "sampleCount": len(kp_series),
            "from": utc_iso(kp_series[0][0]),
            "to": utc_iso(kp_series[-1][0]),
            "interpolation": "linear in time between samples, held flat outside the record",
            "spinUpFrom": result["spinUpFrom"],
            "spinUpHours": result["spinUpHours"],
            "initialCondition": (
                "saturated inside the last closed equipotential of the first Kp, trough outside"
            ),
        },
        "grid": {
            "lValues": result["gridLValues"],
            "mltHours": result["gridMltHours"],
            "lCount": PUBLISHED_L_COUNT,
            "mltCount": PUBLISHED_MLT_COUNT,
            "order": "L-major; index = lIndex * mltCount + mltIndex",
            "mltConvention": "magnetic local time in hours, 0 at midnight, increasing eastward",
        },
        "fieldEncodings": {"electronDensity": dict(DENSITY_ENCODING)},
        "plasmapause": {
            "contourCm3": PLASMAPAUSE_CONTOUR_CM3,
            "method": (
                "outermost crossing of the stated contour, interpolated in log10 density between "
                "shells; the steepest log-gradient location is published beside it as a check"
            ),
        },
        "integration": {
            "steps": result["integrationSteps"],
            "maximumStepSeconds": MAX_TIME_STEP_S,
            "cflSafety": CFL_SAFETY,
            "filledTotalPerWb": result["filledTotalPerWb"],
            "lostTotalPerWb": result["lostTotalPerWb"],
        },
        "time": {
            "cadenceMinutes": cadence,
            "validFrom": frames[0]["validAt"],
            "validTo": frames[-1]["validAt"],
            "frameCount": len(frames),
        },
        "frames": frames,
    }


def drive_digest(kp_series: Sequence[tuple[dt.datetime, float]], frames_at: Sequence[dt.datetime]) -> str:
    """A cache key that changes when, and only when, the answer would change.

    Keyed on the Kp samples, the requested frame instants and the model
    parameters. Frame instants sit on a fixed UTC grid, so this is stable
    across the five-minute publish cycles between Kp updates - and it is not
    keyed on anything that moves every cycle, which is the failure mode that
    turns a cache into a permanent miss.
    """
    payload = json.dumps(
        {
            "schema": SCHEMA_VERSION,
            "kp": [[utc_iso(at), round(kp, 4)] for at, kp in kp_series],
            "frames": [utc_iso(at) for at in frames_at],
            "grid": [SIMULATION_L_MINIMUM, SIMULATION_L_MAXIMUM, SIMULATION_L_COUNT, SIMULATION_MLT_COUNT],
            "published": [PUBLISHED_L_MINIMUM, PUBLISHED_L_MAXIMUM, PUBLISHED_L_COUNT, PUBLISHED_MLT_COUNT],
            "model": [
                VOLLAND_STERN["amplitudeVPerM"],
                VOLLAND_STERN["exponent"],
                DGCPM_DEFAULTS["fillDays"],
                DGCPM_DEFAULTS["emptyPeriodClosedDays"],
                MAX_TIME_STEP_S,
                CFL_SAFETY,
            ],
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def publish(
    data_root: Path,
    write_artifact: Callable[[Path, str, Any], tuple[str, str]],
    three_hour_kp_raw: Any,
    estimated_kp_raw: Any,
    *,
    now: dt.datetime | None = None,
    cache_root: Path | None = None,
) -> dict[str, Any]:
    """Manifest fragment, in the shape ``build_release`` already merges.

    Cached on the drive digest: between Kp updates every publish cycle asks the
    same question, and the answer is a few seconds of integration.
    """
    three_hour = parse_three_hour_kp(three_hour_kp_raw)
    estimated = parse_estimated_kp(estimated_kp_raw) if estimated_kp_raw is not None else []
    kp_series, provenance = join_kp_series(three_hour, estimated)
    now = (now or dt.datetime.now(dt.timezone.utc)).astimezone(dt.timezone.utc)
    cadence = published_cadence_minutes(PUBLISHED_HISTORY_HOURS)
    times = frame_times(now, PUBLISHED_HISTORY_HOURS, cadence)
    digest = drive_digest(kp_series, times)

    bundle: dict[str, Any] | None = None
    cache_path: Path | None = None
    if cache_root is not None:
        cache_path = Path(cache_root) / f"dgcpm-{digest[:24]}.json"
        if cache_path.is_file():
            try:
                cached = json.loads(cache_path.read_text())
                if isinstance(cached, dict) and cached.get("schemaVersion") == SCHEMA_VERSION:
                    bundle = cached
            except (OSError, json.JSONDecodeError):
                bundle = None
    if bundle is None:
        bundle = build_bundle(kp_series, provenance, now=now)
        if cache_path is not None:
            try:
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                cache_path.write_text(json.dumps(bundle, separators=(",", ":"), sort_keys=True))
                _prune_cache(cache_path.parent, keep=6)
            except OSError:
                pass

    path, sha = write_artifact(data_root, "plasmasphere-dgcpm", bundle)
    plumes = sum(1 for frame in bundle["frames"] if frame["plume"].get("present"))
    return {
        "plasmasphere": {
            "path": path,
            "sha256": sha,
            "frameCount": bundle["time"]["frameCount"],
            "cadenceMinutes": bundle["time"]["cadenceMinutes"],
            "validFrom": bundle["time"]["validFrom"],
            "validTo": bundle["time"]["validTo"],
            "spinUpHours": bundle["drive"]["spinUpHours"],
            "framesWithPlume": plumes,
        }
    }


def _prune_cache(directory: Path, *, keep: int) -> None:
    entries = sorted(
        (path for path in directory.glob("dgcpm-*.json") if path.is_file()),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for stale in entries[keep:]:
        try:
            stale.unlink()
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Offline entry point, for verification runs. Never used by the publisher.
# ---------------------------------------------------------------------------


def main() -> int:
    import argparse
    import urllib.request

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kp-file", type=Path, help="a saved copy of the 3-hourly Kp product")
    parser.add_argument("--estimated-kp-file", type=Path)
    parser.add_argument("--out", type=Path, help="write the bundle here instead of stdout summary")
    args = parser.parse_args()

    if args.kp_file:
        three_hour_raw = json.loads(args.kp_file.read_text())
    else:
        request = urllib.request.Request(
            "https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json",
            headers={"User-Agent": "space-teaching-aid/1.0 (+https://sean.theinformed.org/space/)"},
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            if response.status != 200:
                raise SystemExit(f"upstream returned {response.status}; stopping")
            three_hour_raw = json.loads(response.read())
    estimated_raw = json.loads(args.estimated_kp_file.read_text()) if args.estimated_kp_file else None

    kp_series, provenance = join_kp_series(
        parse_three_hour_kp(three_hour_raw),
        parse_estimated_kp(estimated_raw) if estimated_raw is not None else [],
    )
    bundle = build_bundle(kp_series, provenance)
    if args.out:
        args.out.write_text(json.dumps(bundle, separators=(",", ":"), sort_keys=True))
    for frame in bundle["frames"]:
        plume = frame["plume"]
        print(
            f"{frame['validAt']}  Kp={frame['kp']:.2f}  "
            f"A={frame['convectionAmplitudeVPerRe2']:7.1f} V/Re^2  "
            f"Ls={frame['stagnationL']:.2f}  "
            f"plume={'YES' if plume.get('present') else 'no '} "
            f"extent={plume.get('extentL', float('nan'))} at MLT {plume.get('peakMltHours')}"
        )
    print(
        f"{bundle['time']['frameCount']} frames, cadence {bundle['time']['cadenceMinutes']} min, "
        f"spin-up {bundle['drive']['spinUpHours']} h, {bundle['integration']['steps']} steps"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
