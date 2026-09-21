#!/usr/bin/env python3
"""Reduce operational NOAA WAM neutral-atmosphere fields into a thermosphere layer.

The thermosphere is the *neutral* atmosphere between roughly 90 km and the
exobase.  It is defined by its temperature profile -- temperature rises steeply
above the mesopause and then becomes isothermal at the exospheric temperature --
and it is the neutral mass density of that same air, not the ionospheric
electron density, that produces satellite drag.  The ionosphere is the ionised
minority of the identical gas: at 300 km a typical daytime F2 electron density
of 1e12 m^-3 sits inside a neutral gas of roughly 7e14 m^-3, about one particle
in seven hundred.  This module publishes the neutral variable so the site can
show both without conflating them.

Primary source, and the reason this module is small: NOAA already publishes the
neutral field.  The same WAM-IPE Forecast System that supplies `ipe05`/`ipe10`
to `pipeline/wam_ipe.py` also produces `wam05` and `wam10`, and NOAA's Open Data
archive republishes a `wam_fixed_height` product carrying neutral mass density
on a regular 100-1000 km altitude grid.  That is an operational model field from
a US Government source on the same 90 x 91 horizontal grid as the ionosphere
layer, which is what makes the "same air, two variables" comparison honest
rather than rhetorical.

Two models are published, and the visitor chooses between them
(`THERMOSPHERE_MODELS`, `resolve_thermosphere_model`).  NOAA WAM is the default
because it is far better at storms, which is the lesson this layer exists to
teach.  NRLMSIS 2.1 is the alternative and the automatic fallback, because WAM's
archive only reaches back to 2023-03-21 while NRLMSIS evaluates any date from
F10.7 and Ap alone.  The label, evidence class and description are read from the
same record as the data, in one operation, so the UI cannot show one model's
numbers under another model's name.

`pymsis` is imported lazily and every function that does not mention MSIS in its
name works without it.

`CURATED_DENSITY_EVENTS` turns the disagreement between the two models into the
teaching object: for a handful of famous storms it carries the *published
observation* alongside what each model says, with citations.

Nothing in this module fetches during import, and the parsers accept an already
opened dataset so the test suite runs with no network.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import re
from typing import Any, Iterable, Mapping, Sequence


# NOAA Open Data Dissemination bucket for the WAM-IPE Forecast System.  Public,
# anonymous, not requester-pays.  Retains `wam_fixed_height` only.
AWS_ARCHIVE_ROOT = "https://noaa-nws-wam-ipe-pds.s3.amazonaws.com"
AWS_ARCHIVE_VERSION = "v1.2"
# The live NOMADS tree that `pipeline/wam_ipe.py` already lists.  It carries the
# native-grid `wam05`/`wam10` products but *not* `wam_fixed_height`.
NOMADS_WFS_ROOT = "https://nomads.ncep.noaa.gov/pub/data/nccf/com/wfs/prod"
PRODUCT_URL = "https://www.spaceweather.gov/products/wam-ipe"
REGISTRY_URL = "https://registry.opendata.aws/noaa-nws-wam-ipe/"
USER_AGENT = "SpaceEnvironmentExplorer/0.1 educational-project contact=sean.theinformed.org"

FIXED_HEIGHT_FILE = re.compile(
    r"wam_fixed_height\.wfs\.t(\d{2})z\.wam10\.(\d{8}_\d{6})\.nc$"
)

# Avogadro's number and the molar masses WAM carries, in kg/mol.  Used only by
# `mass_density_from_species`, for the native `wam10` route.
AVOGADRO = 6.02214076e23
MOLAR_MASS_KG = {"O": 16.0e-3, "O2": 32.0e-3, "N2": 28.0e-3}

# Encoding domain for log10(rho / (kg m^-3)).
#
# Measured, not guessed.  Across the real frames inspected -- 2024-05-08 quiet,
# 2024-05-11 (Gannon, Kp 9) and 2026-08-07 -- WAM spans -15.21 to -6.04, and
# NRLMSIS at deep solar minimum on the night side of 1000 km reaches -15.22
# while an extreme storm at 100 km reaches -6.20.  A domain fitted to the
# observed range would therefore clip on the very frames the site exists to
# show: the first attempt at -15.0 was rejected by `encode_log_density` on the
# Gannon frame.  These bounds keep roughly 1.8 dex of headroom below and 0.5
# above, and the encoder raises rather than clamps if anything ever exceeds them.
LOG_DENSITY_FLOOR = -17.0
LOG_DENSITY_CEILING = -5.5

# Physical constants for the drag derivation.
EARTH_GRAVITATIONAL_PARAMETER = 3.986004418e14  # m^3 s^-2
EARTH_EQUATORIAL_RADIUS_M = 6378137.0

# NOAA fills the two pole rows of the WAM grid.  They are a coordinate
# singularity, not a measurement gap, and they are the only invalid cells seen
# in the inspected frames -- but the mask is derived from the data, never
# assumed, because assuming it is how a fill value becomes a published number.
POLE_LATITUDE_TOLERANCE_DEG = 0.05


class ThermosphereFormatError(ValueError):
    """Raised when a purported NOAA WAM neutral field is structurally unsafe."""


def utc_iso(value: dt.datetime) -> str:
    return value.astimezone(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def parse_utc(value: str) -> dt.datetime:
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(dt.timezone.utc)


def parse_compact_time(value: str) -> dt.datetime:
    return dt.datetime.strptime(value, "%Y%m%d_%H%M%S").replace(tzinfo=dt.timezone.utc)


# ---------------------------------------------------------------------------
# Upstream addressing
# ---------------------------------------------------------------------------


def archive_cycle_prefix(cycle_start: dt.datetime) -> str:
    """S3 key prefix for one 6-hourly WFS cycle in the NOAA Open Data archive."""
    cycle_start = cycle_start.astimezone(dt.timezone.utc)
    if cycle_start.hour % 6 or cycle_start.minute or cycle_start.second:
        raise ThermosphereFormatError(
            f"WFS cycles start at 00/06/12/18Z exactly; got {utc_iso(cycle_start)}"
        )
    return (
        f"{AWS_ARCHIVE_VERSION}/wfs.{cycle_start:%Y%m%d}/{cycle_start:%H}/"
    )


def archive_listing_url(cycle_start: dt.datetime, max_keys: int = 1000) -> str:
    """List-objects URL for one cycle.  Anonymous S3 REST, no credentials."""
    prefix = archive_cycle_prefix(cycle_start)
    return f"{AWS_ARCHIVE_ROOT}/?list-type=2&prefix={prefix}&max-keys={int(max_keys)}"


def archive_frame_url(cycle_start: dt.datetime, valid_at: dt.datetime) -> str:
    """Direct object URL for one 10-minute neutral-density frame."""
    cycle_start = cycle_start.astimezone(dt.timezone.utc)
    valid_at = valid_at.astimezone(dt.timezone.utc)
    if valid_at.minute % 10 or valid_at.second:
        raise ThermosphereFormatError(
            f"wam_fixed_height frames are published every 10 minutes; got {utc_iso(valid_at)}"
        )
    name = (
        f"wam_fixed_height.wfs.t{cycle_start:%H}z.wam10.{valid_at:%Y%m%d_%H%M%S}.nc"
    )
    return f"{AWS_ARCHIVE_ROOT}/{archive_cycle_prefix(cycle_start)}{name}"


def parse_frame_key(key: str) -> tuple[int, dt.datetime]:
    """Recover (cycle hour, valid time) from an archive object key."""
    match = FIXED_HEIGHT_FILE.search(key)
    if not match:
        raise ThermosphereFormatError(f"not a wam_fixed_height frame key: {key!r}")
    return int(match.group(1)), parse_compact_time(match.group(2))


# ---------------------------------------------------------------------------
# Parsing and validation
# ---------------------------------------------------------------------------


def _coordinate(values: Sequence[float], name: str, low: float, high: float) -> list[float]:
    coords = [float(v) for v in values]
    if len(coords) < 8:
        raise ThermosphereFormatError(f"WAM {name} axis has only {len(coords)} points")
    if any(not math.isfinite(v) for v in coords):
        raise ThermosphereFormatError(f"WAM {name} axis contains a non-finite coordinate")
    if any(b <= a for a, b in zip(coords, coords[1:])):
        raise ThermosphereFormatError(f"WAM {name} axis is not strictly increasing")
    if coords[0] < low or coords[-1] > high:
        raise ThermosphereFormatError(
            f"WAM {name} axis spans {coords[0]}..{coords[-1]}, outside {low}..{high}"
        )
    return coords


def parse_wam_fixed_height(dataset: Any) -> dict[str, Any]:
    """Validate one opened `wam_fixed_height` dataset into a plain frame dict.

    `dataset` is anything exposing netCDF4's `.variables` mapping; the caller
    owns opening and closing it, which is what keeps this function testable
    without a network.

    Returns physical SI values and an explicit boolean validity mask.  A zero
    or non-finite density is a fill value, never a density: NOAA writes zeros
    into the two pole rows, and a zero silently taken as a real number would
    become -inf the moment anything takes its logarithm.
    """
    import numpy as np

    required = {"lon", "lat", "hlevs", "time", "den"}
    missing = required - set(dataset.variables)
    if missing:
        raise ThermosphereFormatError(
            f"WAM fixed-height frame is missing {sorted(missing)}"
        )

    lon = _coordinate(np.asarray(dataset.variables["lon"][:]).ravel(), "longitude", -180.0, 360.0)
    lat = _coordinate(np.asarray(dataset.variables["lat"][:]).ravel(), "latitude", -90.0, 90.0)
    alt = _coordinate(np.asarray(dataset.variables["hlevs"][:]).ravel(), "altitude", 50.0, 5000.0)

    raw_time = np.asarray(dataset.variables["time"][:]).ravel()
    if raw_time.size != 1:
        raise ThermosphereFormatError(
            f"expected exactly one time in a WAM fixed-height frame, got {raw_time.size}"
        )
    valid_at = dt.datetime(1970, 1, 1, tzinfo=dt.timezone.utc) + dt.timedelta(days=float(raw_time[0]))

    # netCDF4 returns a masked array when the variable declares a fill value,
    # and `np.asarray` on a masked array silently hands back the *raw* buffer
    # with the sentinel still in it.  The WAM products do not even agree on the
    # sentinel: `wam_fixed_height` writes 0, while `wam05` writes -99999 into
    # `den400` and `ON2`.  Resolving the mask to NaN first makes the validity
    # test below independent of whichever sentinel a given product chose.
    density = np.ma.filled(
        np.ma.masked_invalid(np.ma.asarray(dataset.variables["den"][:], dtype=float)),
        np.nan,
    )
    density = density.reshape(density.shape[-3:]) if density.ndim == 4 else density
    expected = (len(alt), len(lat), len(lon))
    if density.shape != expected:
        raise ThermosphereFormatError(
            f"WAM density has shape {density.shape}; coordinates imply {expected}"
        )

    valid = np.isfinite(density) & (density > 0.0)
    if not valid.any():
        raise ThermosphereFormatError("WAM density frame has no valid samples")
    coverage = float(valid.sum()) / valid.size
    if coverage < 0.75:
        raise ThermosphereFormatError(
            f"WAM density frame is only {100 * coverage:.1f}% valid; refusing to publish"
        )

    finite = density[valid]
    if finite.max() > 1e-3 or finite.min() < 1e-20:
        raise ThermosphereFormatError(
            f"WAM density spans {finite.min():.3e}..{finite.max():.3e} kg m^-3, "
            "which is not a thermospheric range"
        )

    # Density must fall with altitude in the mean.  A frame that does not is
    # either a corrupted transfer or a product change, and either way must not
    # reach the browser.
    column_means = [float(finite_mean(density[k], valid[k])) for k in range(len(alt))]
    if column_means[0] <= column_means[-1]:
        raise ThermosphereFormatError(
            "WAM density does not decrease with altitude; the vertical axis may be inverted"
        )

    return {
        "validAt": utc_iso(valid_at),
        "longitudeDeg": lon,
        "latitudeDeg": lat,
        "altitudeKm": alt,
        "densityKgM3": density,
        "valid": valid,
        "validFraction": coverage,
        "levelMeanDensityKgM3": column_means,
    }


def finite_mean(values: Any, mask: Any) -> float:
    import numpy as np

    selected = np.asarray(values)[np.asarray(mask)]
    return float(selected.mean()) if selected.size else float("nan")


def mass_density_from_species(
    o_density_m3: Any, o2_density_m3: Any, n2_density_m3: Any
) -> Any:
    """Neutral mass density from the native `wam10` species number densities.

    WAM's native product carries O, O2 and N2 number densities on model pressure
    surfaces rather than a mass density.  Reconstructing rho from them reproduces
    NOAA's own published `den400` field to within 0.5% (median ratio 0.9947 over
    the 8,190 columns of the 2026-08-07 00Z frame), which is the check that
    licenses using this route when the fixed-height product is unavailable.

    Helium and atomic hydrogen are absent from the WAM output and are therefore
    absent here.  They are negligible for mass density below roughly 600 km and
    become significant above it, so this reconstruction must not be extended to
    the top of the fixed-height grid without saying so.
    """
    import numpy as np

    o = np.asarray(o_density_m3, dtype=float)
    o2 = np.asarray(o2_density_m3, dtype=float)
    n2 = np.asarray(n2_density_m3, dtype=float)
    if not (o.shape == o2.shape == n2.shape):
        raise ThermosphereFormatError("WAM species fields have mismatched shapes")
    total = (
        MOLAR_MASS_KG["O"] * o + MOLAR_MASS_KG["O2"] * o2 + MOLAR_MASS_KG["N2"] * n2
    ) / AVOGADRO
    return total


# ---------------------------------------------------------------------------
# Browser reduction
# ---------------------------------------------------------------------------


def _nearest_level_indices(altitudes: Sequence[float], wanted: Sequence[float]) -> list[int]:
    chosen: list[int] = []
    for target in wanted:
        index = min(range(len(altitudes)), key=lambda i: abs(altitudes[i] - target))
        if chosen and index <= chosen[-1]:
            continue
        chosen.append(index)
    return chosen


def encode_log_density(
    density: Any,
    valid: Any,
    *,
    bits: int = 16,
    floor: float = LOG_DENSITY_FLOOR,
    ceiling: float = LOG_DENSITY_CEILING,
) -> dict[str, Any]:
    """Quantise log10(rho) into uint8 or uint16 with a separate validity mask.

    Code 0 is reserved for "no value" in both widths, so a decoder that ignores
    the mask still cannot mistake a hole for the lowest density on the scale.

    Width matters here in a way it does not for a purely visual field.  At 8
    bits the quantum over this domain is 0.0374 dex, about 9% in density, and
    drag force is linear in density -- so a quoted drag or decay number carries
    that 9% as an artifact of the encoding rather than of the science.  16 bits
    reduces it to 0.000145 dex (0.03%) for twice the bytes, and the field
    compresses well, so 16 is the default.
    """
    import numpy as np

    if bits not in (8, 16):
        raise ThermosphereFormatError(f"unsupported encoding width {bits}")
    if ceiling <= floor:
        raise ThermosphereFormatError("encoding ceiling must exceed the floor")

    density = np.asarray(density, dtype=float)
    valid = np.asarray(valid, dtype=bool)
    if density.shape != valid.shape:
        raise ThermosphereFormatError("density and validity mask have different shapes")

    codes = (1 << bits) - 1
    dtype = np.uint8 if bits == 8 else np.uint16
    out = np.zeros(density.shape, dtype=dtype)

    if valid.any():
        logs = np.log10(density[valid])
        if float(logs.min()) < floor or float(logs.max()) > ceiling:
            raise ThermosphereFormatError(
                f"log10 density spans {logs.min():.3f}..{logs.max():.3f}, "
                f"outside the encoding domain {floor}..{ceiling}"
            )
        scaled = (logs - floor) / (ceiling - floor) * (codes - 1)
        out[valid] = np.clip(np.rint(scaled) + 1, 1, codes).astype(dtype)

    return {
        "bits": bits,
        "codes": out,
        "logFloor": floor,
        "logCeiling": ceiling,
        "quantumDex": (ceiling - floor) / (codes - 1),
        "zeroMeans": "no value",
    }


def decode_log_density(encoded: dict[str, Any]) -> Any:
    """Inverse of :func:`encode_log_density`; holes decode to NaN, never to zero."""
    import numpy as np

    codes = np.asarray(encoded["codes"])
    span = (1 << int(encoded["bits"])) - 1
    floor = float(encoded["logFloor"])
    ceiling = float(encoded["logCeiling"])
    out = np.full(codes.shape, np.nan, dtype=float)
    filled = codes > 0
    logs = floor + (codes[filled].astype(float) - 1) / (span - 1) * (ceiling - floor)
    out[filled] = np.power(10.0, logs)
    return out


def pack_validity_mask(valid: Any) -> bytes:
    """Pack the validity mask LSB-first, matching the ionosphere artifact."""
    import numpy as np

    return np.packbits(np.asarray(valid, dtype=bool).ravel(), bitorder="little").tobytes()


def reduce_thermosphere_frame(
    frame: dict[str, Any],
    *,
    longitude_stride: int = 2,
    latitude_stride: int = 2,
    altitudes_km: Sequence[float] | None = None,
    bits: int = 16,
) -> dict[str, Any]:
    """Decimate one validated frame into a browser payload.

    Decimation is coordinate-preserving: it selects source samples rather than
    averaging neighbours, so every published value is a value NOAA published.
    The validity mask is decimated with the same stride and never dilated, so a
    filled pole row cannot leak into a retained sample.
    """
    import numpy as np

    if longitude_stride < 1 or latitude_stride < 1:
        raise ThermosphereFormatError("strides must be at least 1")

    lon = frame["longitudeDeg"]
    lat = frame["latitudeDeg"]
    alt = frame["altitudeKm"]
    density = np.asarray(frame["densityKgM3"], dtype=float)
    valid = np.asarray(frame["valid"], dtype=bool)

    level_index = (
        list(range(len(alt)))
        if altitudes_km is None
        else _nearest_level_indices(alt, altitudes_km)
    )
    lat_index = list(range(0, len(lat), latitude_stride))
    lon_index = list(range(0, len(lon), longitude_stride))

    picked = np.ix_(level_index, lat_index, lon_index)
    sub_density = density[picked]
    sub_valid = valid[picked]
    encoded = encode_log_density(sub_density, sub_valid, bits=bits)

    return {
        "validAt": frame["validAt"],
        "grid": {
            "altitudeKm": [alt[i] for i in level_index],
            "latitudeDeg": [lat[i] for i in lat_index],
            "longitudeDeg": [lon[i] for i in lon_index],
        },
        "quantity": "neutral mass density",
        "units": "kg m-3",
        "encoding": {
            "bits": encoded["bits"],
            "logFloor": encoded["logFloor"],
            "logCeiling": encoded["logCeiling"],
            "quantumDex": encoded["quantumDex"],
            "zeroMeans": encoded["zeroMeans"],
        },
        "codes": encoded["codes"],
        "validMask": pack_validity_mask(sub_valid),
        "validFraction": float(sub_valid.sum()) / sub_valid.size,
        "sourceValidFraction": frame["validFraction"],
    }


def source_metadata(frames: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Provenance block; the layer is a MODEL field, and says so."""
    times = sorted(f["validAt"] for f in frames)
    return {
        "product": "NOAA/NCEP WAM-IPE Forecast System, WAM neutral mass density (wam_fixed_height)",
        "status": "model",
        "quantity": "neutral (not ionised) mass density of the thermosphere",
        "productUrl": PRODUCT_URL,
        "archiveUrl": REGISTRY_URL,
        "frameCount": len(frames),
        "validFrom": times[0] if times else None,
        "validTo": times[-1] if times else None,
        "notes": [
            "Neutral mass density is the quantity that produces satellite drag.",
            "The ionosphere layer describes the ionised minority of this same gas.",
            "Pole rows are filled by the source and are published as holes, not zeros.",
        ],
    }


# ---------------------------------------------------------------------------
# Teaching derivations
# ---------------------------------------------------------------------------


def circular_orbital_speed_m_s(altitude_km: float) -> float:
    radius = EARTH_EQUATORIAL_RADIUS_M + altitude_km * 1000.0
    return math.sqrt(EARTH_GRAVITATIONAL_PARAMETER / radius)


def orbital_period_s(altitude_km: float) -> float:
    radius = EARTH_EQUATORIAL_RADIUS_M + altitude_km * 1000.0
    return 2.0 * math.pi * math.sqrt(radius**3 / EARTH_GRAVITATIONAL_PARAMETER)


def drag_deceleration_m_s2(
    density_kg_m3: float, altitude_km: float, ballistic_coefficient_kg_m2: float
) -> float:
    """a_drag = rho * v^2 / (2 * BC), with BC = m / (Cd * A).

    Linear in density.  That linearity is the whole teaching point: a factor of
    two in neutral density is a factor of two in drag, immediately, with no
    threshold and no delay.
    """
    if ballistic_coefficient_kg_m2 <= 0:
        raise ThermosphereFormatError("ballistic coefficient must be positive")
    if density_kg_m3 < 0:
        raise ThermosphereFormatError("density must be non-negative")
    speed = circular_orbital_speed_m_s(altitude_km)
    return density_kg_m3 * speed * speed / (2.0 * ballistic_coefficient_kg_m2)


def decay_rate_km_per_day(
    density_kg_m3: float, altitude_km: float, ballistic_coefficient_kg_m2: float
) -> float:
    """Semi-major-axis decay of a circular orbit, in km/day (negative = decaying).

    Per revolution, da = -2 pi rho a^2 / BC.  This is the standard first-order
    result for a circular orbit in a locally uniform atmosphere.  It ignores
    eccentricity, atmospheric rotation, lift, and the fact that a real satellite
    is manoeuvring, so it is an order-of-magnitude teaching figure and must be
    labelled as one -- but the *ratio* between two space-weather conditions at
    the same altitude and attitude is much more robust than either absolute
    value, because every neglected term cancels.
    """
    radius = EARTH_EQUATORIAL_RADIUS_M + altitude_km * 1000.0
    per_revolution_m = -2.0 * math.pi * density_kg_m3 * radius**2 / ballistic_coefficient_kg_m2
    revolutions_per_day = 86400.0 / orbital_period_s(altitude_km)
    return per_revolution_m * revolutions_per_day / 1000.0


def pressure_scale_height_km(temperature_k: float, mean_molar_mass_kg_mol: float,
                             altitude_km: float) -> float:
    """H = kT/(mg), expressed with molar mass; g is evaluated at altitude."""
    if temperature_k <= 0 or mean_molar_mass_kg_mol <= 0:
        raise ThermosphereFormatError("temperature and molar mass must be positive")
    radius = EARTH_EQUATORIAL_RADIUS_M + altitude_km * 1000.0
    gravity = EARTH_GRAVITATIONAL_PARAMETER / radius**2
    gas_constant = 8.314462618
    return gas_constant * temperature_k / (mean_molar_mass_kg_mol * gravity) / 1000.0


def ionised_fraction(electron_density_m3: float, neutral_number_density_m3: float) -> float:
    """The single number that separates the thermosphere from the ionosphere."""
    if neutral_number_density_m3 <= 0:
        raise ThermosphereFormatError("neutral number density must be positive")
    return electron_density_m3 / neutral_number_density_m3


# ---------------------------------------------------------------------------
# Optional NRLMSIS cross-check
# ---------------------------------------------------------------------------


def msis_available() -> bool:
    try:
        import pymsis  # noqa: F401
    except Exception:
        return False
    return True


def msis_profile(
    when: dt.datetime,
    longitude_deg: float,
    latitude_deg: float,
    altitudes_km: Iterable[float],
    f107: float,
    f107a: float,
    ap: float | Sequence[float],
    *,
    version: str = "2.1",
    storm_mode: bool = False,
) -> list[dict[str, float]]:
    """Empirical NRLMSIS neutral profile, for cross-checking the WAM layer.

    `f107`, `f107a` and `ap` are always passed explicitly.  pymsis will silently
    download and cache historical indices if they are omitted, which would give
    this module a hidden network dependency and break the offline test rule.

    `ap` is either a single daily Ap, or MSIS's full seven-element history:
    (daily Ap, ap now, ap -3 h, ap -6 h, ap -9 h, mean ap 12-33 h ago, mean ap
    36-57 h ago).  Only the first element is used unless `storm_mode=True`, so
    passing a scalar with `storm_mode=True` asserts a flat storm history, which
    is rarely what the data says.  A real event should pass all seven.

    `storm_mode=True` selects MSIS's 3-hourly-ap formulation.  Even in storm mode
    NRLMSIS under-responds to geomagnetic forcing; see `CURATED_DENSITY_EVENTS`
    and the design document before quoting a storm number from it.
    """
    import numpy as np
    from pymsis import Variable, calculate

    altitudes = [float(a) for a in altitudes_km]
    if not altitudes:
        raise ThermosphereFormatError("msis_profile needs at least one altitude")
    if when.tzinfo is not None:
        when = when.astimezone(dt.timezone.utc).replace(tzinfo=None)

    if isinstance(ap, (int, float)):
        ap_history = [float(ap)] * 7
    else:
        ap_history = [float(value) for value in ap]
        if len(ap_history) != 7:
            raise ThermosphereFormatError(
                f"MSIS needs a 7-element ap history or a single value; got {len(ap_history)}"
            )
    if any(value < 0 or not math.isfinite(value) for value in ap_history):
        raise ThermosphereFormatError("ap values must be finite and non-negative")

    result = calculate(
        when,
        float(longitude_deg),
        float(latitude_deg),
        altitudes,
        float(f107),
        float(f107a),
        [ap_history],
        version=version,
        geomagnetic_activity=(-1 if storm_mode else 1),
    ).reshape(-1, 11)

    rows: list[dict[str, float]] = []
    for index, altitude in enumerate(altitudes):
        row = result[index]
        neutral_number = float(
            np.nansum(
                [
                    row[Variable.N2],
                    row[Variable.O2],
                    row[Variable.O],
                    row[Variable.HE],
                    row[Variable.H],
                    row[Variable.AR],
                    row[Variable.N],
                ]
            )
        )
        rows.append(
            {
                "altitudeKm": altitude,
                "massDensityKgM3": float(row[Variable.MASS_DENSITY]),
                "temperatureK": float(row[Variable.TEMPERATURE]),
                "neutralNumberDensityM3": neutral_number,
                "oNumberDensityM3": float(row[Variable.O]),
                "n2NumberDensityM3": float(row[Variable.N2]),
            }
        )
    return rows


def compare_to_msis(
    frame: dict[str, Any],
    f107: float,
    f107a: float,
    ap: float,
    *,
    altitudes_km: Sequence[float] = (200.0, 300.0, 400.0, 500.0),
) -> list[dict[str, float]]:
    """Global-mean WAM density against NRLMSIS at the same times and altitudes.

    Two different models will not agree, and the point is not that they should.
    The point is that an unannounced factor of ten is a broken pipeline, and
    this is the cheapest check that catches one.
    """
    import numpy as np

    density = np.asarray(frame["densityKgM3"], dtype=float)
    valid = np.asarray(frame["valid"], dtype=bool)
    altitudes = list(frame["altitudeKm"])
    when = parse_utc(frame["validAt"])

    rows: list[dict[str, float]] = []
    for target in altitudes_km:
        level = min(range(len(altitudes)), key=lambda i: abs(altitudes[i] - target))
        wam_mean = finite_mean(density[level], valid[level])
        msis_rows = msis_profile(when, 0.0, 0.0, [altitudes[level]], f107, f107a, ap)
        msis_value = msis_rows[0]["massDensityKgM3"]
        rows.append(
            {
                "altitudeKm": altitudes[level],
                "wamGlobalMeanKgM3": wam_mean,
                "msisEquatorNoonKgM3": msis_value,
                "ratio": wam_mean / msis_value if msis_value else float("nan"),
            }
        )
    return rows


# ---------------------------------------------------------------------------
# Model selection
# ---------------------------------------------------------------------------

# Shape and spirit copied deliberately from `RADIATION_BELT_VIEWS` in
# `src/radiation-belt.ts`, which backs the existing "RBE presentation" segmented
# control.  Reusing the idiom means the thermosphere selector reads as part of
# the same product rather than a second way of doing the same thing, and it
# inherits the property that matters: label, evidence class and description are
# fields of the *same record* the renderer selects, so they cannot drift apart
# from the data being shown.
THERMOSPHERE_MODELS = {
    "wamNeutral": {
        "label": "NOAA WAM OPERATIONAL NEUTRAL DENSITY",
        "status": "model",
        "shortName": "NOAA WAM-IPE",
        "description": (
            "Neutral mass density from the operational NOAA/NCEP WAM-IPE Forecast System, "
            "the same forecast system that supplies this site's ionospheric layer. "
            "A physics-based whole-atmosphere model, not a measurement and not assimilated "
            "in the thermosphere."
        ),
        "strength": "Storm response. Resolves the auroral heating that drives storm-time drag.",
        "limitation": (
            "Only exists where NOAA published it: the archive begins 2023-03-21 and runs to "
            "the current cycle's forecast endpoint."
        ),
    },
    "nrlmsis21": {
        "label": "NRLMSIS 2.1 EMPIRICAL NEUTRAL DENSITY",
        "status": "empirical",
        "shortName": "NRLMSIS 2.1",
        "description": (
            "The US Naval Research Laboratory's empirical model, a published fit to decades "
            "of observations, evaluated from F10.7 and Ap alone. Not a measurement and not a "
            "physics simulation: a statistical description of how the atmosphere usually behaves."
        ),
        "strength": "Reach. Evaluates any date instantly, including events long before WAM existed.",
        "limitation": (
            "Systematically under-responds to geomagnetic storms. See CURATED_DENSITY_EVENTS "
            "for the size of the discrepancy against published measurements."
        ),
    },
}

DEFAULT_THERMOSPHERE_MODEL = "wamNeutral"

# NOAA's Open Data archive for the WAM-IPE Forecast System.  v1.1 output begins
# 2023-03-21; v1.2 begins 2023-07-01.  Nothing before that exists at any cadence,
# which is the entire reason the layer needs a second model.
WAM_ARCHIVE_START = dt.datetime(2023, 3, 21, tzinfo=dt.timezone.utc)


class ThermosphereModelSelection(dict):
    """A resolved model choice.  A dict so it serialises into the artifact as-is."""


def resolve_thermosphere_model(
    requested: str | None,
    when: dt.datetime,
    *,
    wam_valid_from: dt.datetime | None = None,
    wam_valid_to: dt.datetime | None = None,
) -> ThermosphereModelSelection:
    """Resolve the model actually used at `when`, and say why.

    Rules, in order:

    1. An explicit request is honoured whenever that model can serve `when`.
    2. WAM is the default, because storm response is the lesson.
    3. Outside WAM's published coverage the layer falls back to NRLMSIS rather
       than showing nothing -- but `fallbackApplied` is set and the label
       changes, so the fallback is never silent.  A viewer scrubbing back to
       February 2022 must see the model name change under their hand.

    NRLMSIS has no coverage limit, so there is no case in which the layer has
    nothing to draw.
    """
    if requested is not None and requested not in THERMOSPHERE_MODELS:
        raise ThermosphereFormatError(
            f"unknown thermosphere model {requested!r}; "
            f"expected one of {sorted(THERMOSPHERE_MODELS)}"
        )

    when = when.astimezone(dt.timezone.utc)
    lower = wam_valid_from or WAM_ARCHIVE_START
    wam_covers = when >= lower and (wam_valid_to is None or when <= wam_valid_to)

    chosen = requested or DEFAULT_THERMOSPHERE_MODEL
    fallback = False
    if chosen == "wamNeutral" and not wam_covers:
        chosen = "nrlmsis21"
        fallback = True

    record = THERMOSPHERE_MODELS[chosen]
    if fallback:
        reason = (
            f"NOAA WAM has no published field at {utc_iso(when)}; "
            f"its archive begins {utc_iso(lower)}. Showing NRLMSIS 2.1 instead."
        )
    elif requested is None:
        reason = "Default model."
    else:
        reason = "Selected by the viewer."

    return ThermosphereModelSelection(
        model=chosen,
        modelLabel=record["label"],
        modelStatus=record["status"],
        modelShortName=record["shortName"],
        representation=record["description"],
        requested=requested,
        fallbackApplied=fallback,
        reason=reason,
        wamCoverage={
            "validFrom": utc_iso(lower),
            "validTo": utc_iso(wam_valid_to) if wam_valid_to else None,
        },
    )


# ---------------------------------------------------------------------------
# Curated events: model against model against measurement
# ---------------------------------------------------------------------------

# Every `observedRatio` here is a published measurement with a citation, not a
# model result.  `msisDrivers` are the F10.7 and ap histories used to evaluate
# NRLMSIS for the same event; `wamRatio`, where present, was measured by this
# project directly from NOAA's published frames and is labelled accordingly.
#
# Comparison method, and it matters: neutral density has a large diurnal cycle,
# so evaluating "quiet" in the afternoon and "storm" at night produces a ratio
# dominated by local time rather than by the storm.  The first draft of this
# table did exactly that and made NRLMSIS look worse than it is.  Every model
# ratio below is therefore a cosine-latitude-weighted mean over all longitudes
# and latitudes, which averages the diurnal cycle out.  Published observations
# from a single satellite track use their own baselines, stated per event.
CURATED_DENSITY_EVENTS = {
    "halloween-2003": {
        "name": "Halloween storms",
        "date": "2003-10-30",
        "altitudeKm": 400.0,
        "summary": (
            "Two X-class-flare-driven superstorms in three days, the largest of the "
            "modern satellite era."
        ),
        "observedRatio": (4.0, 6.0),
        "observedBy": "CHAMP accelerometer at ~400 km",
        "observedBaseline": "quiet-time values, noon and midnight sectors",
        "citation": {
            "authors": "Liu, H., & Lühr, H.",
            "year": 2005,
            "title": (
                "Strong disturbance of the upper thermospheric density due to magnetic "
                "storms: CHAMP observations"
            ),
            "journal": "Journal of Geophysical Research 110, A09S29",
            "doi": "10.1029/2004JA010908",
            "quotedFinding": (
                "Density enhancements peaked around 400% and 500% of quiet-time values "
                "for the 29-30 and 30-31 October 2003 storms."
            ),
        },
        "msisDrivers": {
            "f107": 275.0,
            "f107a": 200.0,
            "quiet": {"when": "2003-10-27T12:00:00Z", "ap": [7.0] * 7},
            "storm": {
                "when": "2003-10-30T00:00:00Z",
                "ap": [400.0, 400.0, 400.0, 400.0, 300.0, 200.0, 100.0],
            },
        },
        "wamRatio": None,
        "wamNote": "Predates the NOAA WAM archive by two decades.",
    },
    "starlink-2022": {
        "name": "Starlink Group 4-7 loss",
        "date": "2022-02-03",
        "altitudeKm": 440.0,
        "summary": (
            "A minor storm, Kp 5-6, during the deployment of 49 Starlink satellites into a "
            "210 km insertion orbit. 38 of them re-entered."
        ),
        "observedRatio": (2.1, 2.2),
        "observedBy": "Swarm-A and GRACE-FO accelerometers",
        "observedBaseline": "pre-storm quiet conditions",
        "citation": {
            "authors": "He, J., et al.",
            "year": 2023,
            "title": (
                "Comparison of Empirical and Theoretical Models of the Thermospheric "
                "Density Enhancement During the 3-4 February 2022 Geomagnetic Storm"
            ),
            "journal": "Space Weather 21",
            "doi": "10.1029/2023SW003521",
            "quotedFinding": (
                "NRLMSIS 2.0 gave a ~25% density increase, while Swarm-A and GRACE-FO "
                "observed 110% and 120%."
            ),
        },
        "supportingCitation": {
            "authors": "Fang, T.-W., et al.",
            "year": 2022,
            "title": (
                "Space Weather Environment During the SpaceX Starlink Satellite Loss in "
                "February 2022"
            ),
            "journal": "Space Weather 20, e2022SW003193",
            "doi": "10.1029/2022SW003193",
            "quotedFinding": (
                "WAM-IPE gave peak density increases at 210 km of 50-100% relative to a "
                "10-day pre-storm average, depending on location."
            ),
        },
        "msisDrivers": {
            "f107": 110.0,
            "f107a": 100.0,
            "quiet": {"when": "2022-02-01T12:00:00Z", "ap": [5.0] * 7},
            "storm": {
                "when": "2022-02-03T18:00:00Z",
                "ap": [40.0, 56.0, 56.0, 48.0, 39.0, 32.0, 12.0],
            },
        },
        "wamRatio": None,
        "wamNote": (
            "Predates the NOAA WAM archive, which begins 2023-03-21. The WAM-IPE figure "
            "above is from Fang et al.'s retrospective run, not from an archived frame."
        ),
    },
    "gannon-2024": {
        "name": "Gannon storm",
        "date": "2024-05-11",
        "altitudeKm": 400.0,
        "summary": "G5, the most severe geomagnetic storm since October 2003.",
        "observedRatio": (6.0, 6.0),
        "observedBy": "orbit-derived, whole NORAD LEO catalog",
        "observedBaseline": "12 hours prior (2024-05-10 14:00 UTC vs 2024-05-11 02:00 UTC)",
        "citation": {
            "authors": "Parker, W. E., & Linares, R.",
            "year": 2024,
            "title": "Satellite Drag Analysis During the May 2024 Gannon Geomagnetic Storm",
            "journal": "Journal of Spacecraft and Rockets (also arXiv:2406.08617)",
            "doi": "10.2514/1.A36164",
            "quotedFinding": (
                "Joule heating and particle precipitation create large density enhancements "
                "of up to 6x the baseline value 12 hours prior. KANOPUS-V 3's decay rate "
                "rose from about 38 m/day to 180 m/day, a factor of 4.7."
            ),
        },
        "msisDrivers": {
            "f107": 220.0,
            "f107a": 190.0,
            "quiet": {"when": "2024-05-10T14:00:00Z", "ap": [22.0] * 7},
            "storm": {
                "when": "2024-05-11T02:00:00Z",
                "ap": [400.0, 400.0, 400.0, 300.0, 200.0, 120.0, 40.0],
            },
        },
        # Measured by this project from NOAA's own published wam_fixed_height
        # frames for 2024-05-08 12:00Z and 2024-05-11 00:00Z, global mean over
        # valid cells.  Not a published figure; labelled as such in the UI.
        "wamRatio": 2.27,
        "wamNote": (
            "Measured from NOAA's published frames by this project: global-mean ratio at "
            "400 km, quiet 2024-05-08 12:00Z against storm 2024-05-11 00:00Z. Peak local "
            "enhancement in the same frame reached 4.69x."
        ),
    },
}

# One clean citable statement that the pattern below is general and not three
# cherry-picked events.
MODEL_ASSESSMENT_CITATION = {
    "authors": "Wang, J. C., et al.",
    "year": 2026,
    "title": (
        "Comprehensive and Open Assessment of Thermospheric Models During Geomagnetic "
        "Storm Times Within CCMC Framework"
    ),
    "journal": "Space Weather 24, e2025SW004782",
    "doi": "10.1029/2025SW004782",
    "quotedFinding": (
        "Assessing five satellite missions across 151 geomagnetic storms over more than "
        "20 years, the study recommends DTM2020 and JB2008 rather than MSIS as the "
        "benchmark empirical models for satellite drag during geomagnetically active periods."
    ),
}


def global_mean_msis_density(
    when: dt.datetime,
    altitude_km: float,
    f107: float,
    f107a: float,
    ap: Sequence[float],
    *,
    latitude_step_deg: float = 10.0,
    longitude_step_deg: float = 30.0,
) -> float:
    """Cosine-latitude-weighted global mean NRLMSIS density at one altitude.

    Averaging over longitude is what removes the diurnal cycle, so that a
    quiet/storm ratio measures the storm rather than the local time at which the
    two samples happened to be taken.
    """
    import numpy as np

    values: list[float] = []
    weights: list[float] = []
    latitude = -90.0 + latitude_step_deg / 2.0
    while latitude < 90.0:
        for index in range(int(round(360.0 / longitude_step_deg))):
            longitude = index * longitude_step_deg
            row = msis_profile(
                when, longitude, latitude, [altitude_km], f107, f107a, ap, storm_mode=True
            )[0]
            values.append(row["massDensityKgM3"])
            weights.append(math.cos(math.radians(latitude)))
        latitude += latitude_step_deg
    return float(np.average(values, weights=weights))


def compare_models_for_event(event_id: str) -> dict[str, Any]:
    """Published observation against NRLMSIS, for one curated event.

    Returns the ratios side by side so the UI can show all three -- observation,
    empirical model, physics model -- rather than one confident curve.
    """
    if event_id not in CURATED_DENSITY_EVENTS:
        raise ThermosphereFormatError(
            f"unknown event {event_id!r}; expected one of {sorted(CURATED_DENSITY_EVENTS)}"
        )
    event = CURATED_DENSITY_EVENTS[event_id]
    drivers = event["msisDrivers"]
    altitude = event["altitudeKm"]

    quiet = global_mean_msis_density(
        parse_utc(drivers["quiet"]["when"]),
        altitude,
        drivers["f107"],
        drivers["f107a"],
        drivers["quiet"]["ap"],
    )
    storm = global_mean_msis_density(
        parse_utc(drivers["storm"]["when"]),
        altitude,
        drivers["f107"],
        drivers["f107a"],
        drivers["storm"]["ap"],
    )
    msis_ratio = storm / quiet

    low, high = event["observedRatio"]
    return {
        "event": event_id,
        "name": event["name"],
        "date": event["date"],
        "altitudeKm": altitude,
        "observed": {
            "ratioLow": low,
            "ratioHigh": high,
            "instrument": event["observedBy"],
            "baseline": event["observedBaseline"],
            "citation": event["citation"],
        },
        "nrlmsis21": {
            "quietKgM3": quiet,
            "stormKgM3": storm,
            "ratio": msis_ratio,
            "shortfall": low / msis_ratio,
            "method": "cosine-latitude-weighted global mean, diurnal cycle averaged out",
        },
        "wam": {"ratio": event["wamRatio"], "note": event["wamNote"]},
        "assessment": MODEL_ASSESSMENT_CITATION,
    }


# ---------------------------------------------------------------------------
# Release bundle
# ---------------------------------------------------------------------------

# The vertical levels this site publishes, out of NOAA's 91.
#
# The layer exists to show the altitude of a drag-relevant density level rising
# during a storm, so the grid has to be fine enough that interpolating that
# altitude between two levels is honest. Log density is close to linear in
# altitude across a pressure scale height, which is roughly 50 km through the
# LEO band at these temperatures, so 30 km steps keep the interpolation error
# far below the storm signal the layer is drawing. Above 600 km nothing this
# site shows is drag-limited and the spacing opens out; 1000 km is kept only so
# the profile has a top that is not a cliff.
PUBLISHED_ALTITUDES_KM = (
    120.0, 150.0, 180.0, 210.0, 240.0, 270.0, 300.0, 330.0, 360.0, 390.0,
    420.0, 450.0, 480.0, 510.0, 550.0, 600.0, 700.0, 800.0, 1000.0,
)

# WFS runs four cycles a day and each publishes frames every ten minutes. An
# hour is plenty for a field whose storm response takes hours to develop, and
# it keeps one release near a megabyte instead of near thirty.
PUBLISH_CADENCE_MINUTES = 60
PUBLISH_HOURS_BACK = 3
PUBLISH_HOURS_AHEAD = 9


def json_safe_frame(frame: dict[str, Any]) -> dict[str, Any]:
    """Base64 the two binary members, matching the ionosphere and aurora artifacts.

    Shape is not stored alongside the bytes because it is already implied by
    `grid`: the codes are C-order (altitude, latitude, longitude), so a decoder
    that reads the grid lengths cannot disagree with the array it is decoding.
    """
    import base64  # noqa: PLC0415
    import numpy as np  # noqa: PLC0415

    codes = np.asarray(frame["codes"])
    if codes.dtype not in (np.uint8, np.uint16):
        raise ThermosphereFormatError(f"unexpected code width {codes.dtype}")
    out = dict(frame)
    out["codes"] = base64.b64encode(codes.tobytes(order="C")).decode("ascii")
    out["codesDtype"] = str(codes.dtype)
    out["codesOrder"] = "altitude,latitude,longitude"
    out["validMask"] = base64.b64encode(bytes(frame["validMask"])).decode("ascii")
    return out


def select_publish_times(
    available: Sequence[dt.datetime],
    now: dt.datetime,
    *,
    hours_back: int = PUBLISH_HOURS_BACK,
    hours_ahead: int = PUBLISH_HOURS_AHEAD,
    cadence_minutes: int = PUBLISH_CADENCE_MINUTES,
) -> list[dt.datetime]:
    """Choose which published frames to carry, without inventing any.

    Pure so it can be tested without the network. Every returned time is a time
    NOAA actually published: the cadence selects from `available`, it never
    rounds to a grid of its own and never interpolates between frames. A gap in
    the archive therefore stays a gap in the release, which is the same rule the
    ionosphere and aurora layers follow.
    """
    if cadence_minutes < 1:
        raise ThermosphereFormatError("cadence must be at least one minute")
    now = now.astimezone(dt.timezone.utc)
    low = now - dt.timedelta(hours=hours_back)
    high = now + dt.timedelta(hours=hours_ahead)

    inside = sorted(t for t in available if low <= t.astimezone(dt.timezone.utc) <= high)
    chosen: list[dt.datetime] = []
    step = dt.timedelta(minutes=cadence_minutes)
    for moment in inside:
        if not chosen or moment - chosen[-1] >= step:
            chosen.append(moment)
    # The newest frame is the forecast endpoint and says how far ahead NOAA has
    # committed; losing it to the cadence would understate the coverage.
    if inside and chosen and chosen[-1] != inside[-1]:
        chosen.append(inside[-1])
    return chosen


def _archive_bytes(url: str, timeout: int = 120) -> bytes:
    """One anonymous GET against NOAA's public bucket, measured."""
    import urllib.request  # noqa: PLC0415

    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read()
    try:
        from ops import bandwidth  # noqa: PLC0415 - optional, never load-bearing

        bandwidth.record_fetch(
            len(body),
            family="noaa-wam-ipe-pds",
            source="urllib response.read() length",
            run="thermosphere",
        )
    except Exception:  # noqa: BLE001 - measurement must never break a fetch
        pass
    if not body:
        raise ThermosphereFormatError(f"empty response from the WAM archive: {url}")
    return body


def list_archive_frames(
    cycle_start: dt.datetime,
    *,
    fetch: Any = None,
) -> list[dt.datetime]:
    """Valid times of every neutral-density frame NOAA published for one cycle."""
    import re as _re  # noqa: PLC0415

    fetch = fetch or (lambda url: _archive_bytes(url, timeout=60))
    body = fetch(archive_listing_url(cycle_start)).decode("utf-8", errors="replace")
    times: list[dt.datetime] = []
    for key in _re.findall(r"<Key>([^<]+)</Key>", body):
        try:
            _cycle_hour, valid_at = parse_frame_key(key)
        except ThermosphereFormatError:
            continue  # the cycle carries other products; ignore them quietly
        times.append(valid_at)
    return sorted(set(times))


def discover_latest_cycle(
    now: dt.datetime,
    *,
    cycles_back: int = 4,
    fetch: Any = None,
) -> tuple[dt.datetime, list[dt.datetime]]:
    """The newest cycle that actually has frames, and those frames.

    Walks backwards rather than assuming the current cycle has published: a
    cycle appears in the bucket before it is complete, and a run can be late.
    Raises rather than returning an empty cycle, because a layer with no frames
    must fail the build loudly instead of publishing an empty field.
    """
    now = now.astimezone(dt.timezone.utc)
    cycle = now.replace(hour=(now.hour // 6) * 6, minute=0, second=0, microsecond=0)
    problems: list[str] = []
    best: tuple[dt.datetime, list[dt.datetime]] | None = None
    for step in range(cycles_back):
        candidate = cycle - dt.timedelta(hours=6 * step)
        if candidate < WAM_ARCHIVE_START:
            break
        try:
            frames = list_archive_frames(candidate, fetch=fetch)
        except Exception as error:  # noqa: BLE001 - one bad cycle is not fatal
            problems.append(f"{utc_iso(candidate)}: {error}")
            continue
        if not frames:
            problems.append(f"{utc_iso(candidate)}: no neutral-density frames")
            continue
        # Newest FIRST, but only if it actually reaches the present.
        #
        # NOAA publishes a cycle's frames as the run produces them, so the most
        # recent cycle is routinely the one LEAST able to cover now: measured
        # 2026-08-18 at 21:26Z, the 18Z cycle had published only as far as
        # 20:10Z, and taking it left the layer with three frames that all ended
        # in the past and a legend reading "no data at this time". An older,
        # completed cycle covers the present perfectly well.
        if frames[-1] >= now:
            return candidate, frames
        if best is None or frames[-1] > best[1][-1]:
            best = (candidate, frames)
        problems.append(
            f"{utc_iso(candidate)}: published only to {utc_iso(frames[-1])}, before now"
        )
    if best is not None:
        # Nothing reaches the present. Publish the furthest-forward cycle we
        # found rather than nothing: a short series that ends in the past is
        # still honest — the layer says "no data at this time" and offers the
        # jump — where an empty release says the field does not exist.
        return best
    raise ThermosphereFormatError(
        "no WAM neutral-density cycle carried frames; tried "
        + "; ".join(problems or ["nothing"])
    )


def build_thermosphere_bundle(
    now: dt.datetime | None = None,
    *,
    altitudes_km: Sequence[float] = PUBLISHED_ALTITUDES_KM,
    longitude_stride: int = 2,
    latitude_stride: int = 2,
    bits: int = 16,
    cadence_minutes: int = PUBLISH_CADENCE_MINUTES,
    fetch: Any = None,
    open_dataset: Any = None,
) -> dict[str, Any]:
    """Fetch, validate and reduce one release worth of neutral density.

    `fetch` and `open_dataset` are injectable so the whole path can be tested
    against recorded bytes with no network and no netCDF4.
    """
    now = (now or dt.datetime.now(dt.timezone.utc)).astimezone(dt.timezone.utc)
    cycle_start, available = discover_latest_cycle(now, fetch=fetch)
    wanted = select_publish_times(available, now, cadence_minutes=cadence_minutes)
    if not wanted:
        raise ThermosphereFormatError(
            f"cycle {utc_iso(cycle_start)} published {len(available)} frames but none "
            f"inside the release window around {utc_iso(now)}"
        )

    if open_dataset is None:
        def open_dataset(payload: bytes, valid_at: dt.datetime) -> Any:  # noqa: ARG001
            import netCDF4  # noqa: PLC0415

            return netCDF4.Dataset("inmemory.nc", mode="r", memory=payload)

    getter = fetch or _archive_bytes
    frames: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    for valid_at in wanted:
        url = archive_frame_url(cycle_start, valid_at)
        try:
            payload = getter(url)
            dataset = open_dataset(payload, valid_at)
            try:
                parsed = parse_wam_fixed_height(dataset)
            finally:
                closer = getattr(dataset, "close", None)
                if callable(closer):
                    closer()
            frames.append(
                json_safe_frame(
                    reduce_thermosphere_frame(
                        parsed,
                        longitude_stride=longitude_stride,
                        latitude_stride=latitude_stride,
                        altitudes_km=altitudes_km,
                        bits=bits,
                    )
                )
            )
        except Exception as error:  # noqa: BLE001
            # One unreadable frame is a gap, not a failed build — but it is
            # recorded, because a silently shorter series is exactly how a
            # coverage hole turns into an apparently quiet atmosphere.
            skipped.append({"validAt": utc_iso(valid_at), "reason": str(error)})

    if not frames:
        raise ThermosphereFormatError(
            f"every frame in cycle {utc_iso(cycle_start)} failed to reduce: "
            + "; ".join(item["reason"] for item in skipped[:3])
        )

    times = sorted(frame["validAt"] for frame in frames)
    selection = resolve_thermosphere_model(
        None,
        now,
        wam_valid_from=WAM_ARCHIVE_START,
        wam_valid_to=parse_utc(times[-1]),
    )
    return {
        "generatedAt": utc_iso(now),
        "cycleStart": utc_iso(cycle_start),
        "validFrom": times[0],
        "validTo": times[-1],
        "cadenceMinutes": cadence_minutes,
        "model": dict(selection),
        "source": source_metadata(frames),
        "frames": frames,
        "skipped": skipped,
        "publishedAltitudesKm": [float(value) for value in altitudes_km],
    }




# ---------------------------------------------------------------------------
# The empirical field that covers the rest of the timeline
# ---------------------------------------------------------------------------
#
# WHY THIS EXISTS, measured. The site's clock spans 48 hours back to 72 hours
# ahead -- 120 hours. One NOAA WAM release covers about twelve of them: on
# 2026-08-20 the published bundle ran 2026-08-19T23:40Z to 2026-08-20T11:30Z,
# 11.8 hours, 9.8% of the slider. Until e4502f8 the other 90% showed the last
# frame the layer happened to have chosen, still badged MODEL, which is why
# every report of this layer for a month was "the thermosphere is static": it
# WAS static, because it was one frozen hour of WAM standing in for five days.
#
# NRLMSIS is defined at every instant, because it is an empirical model driven
# by three published indices rather than a forecast integrated from an initial
# condition. It is also what operational drag and conjunction work actually
# uses, so it is not a consolation prize -- and because ap is one of its
# drivers, it RESPONDS TO STORMS, which is the lesson this layer was built for.
#
# Three rules, and they are the whole design:
#
#   1. MSIS never replaces WAM. It is published across the entire window, WAM
#      is published where NOAA has it, and the reader's clock chooses: a WAM
#      frame within half a cadence wins, otherwise MSIS. Nothing blends.
#   2. The badge changes when the model changes. WAM is MODEL, MSIS is
#      EMPIRICAL, and the card, the chip and the timeline all say so at the same
#      instant. A visible seam at the boundary is honest and is left visible.
#   3. Frames sit on WHOLE UTC HOURS, not on offsets from `now`. Two builds five
#      minutes apart therefore produce byte-identical shards for every hour
#      whose drivers have not changed, so the content-addressed artifacts are
#      not rewritten and not re-transferred. Anchoring to `now` would rewrite
#      fourteen megabytes every five minutes to say the same thing.

# One shard is six hours. Measured on this grid: a frame is 109 kB of JSON and
# 71 kB gzipped, so a shard is ~420 kB gzipped and a reader who opens the site
# at `now` downloads exactly one of them. Sharding is not an optimisation here,
# it is the difference between 420 kB and 8.3 MB to draw one hour.
MSIS_SHARD_HOURS = 6
MSIS_CADENCE_MINUTES = 60
# The site's own slider, and it must match: an MSIS window shorter than the
# slider re-creates the hole this module exists to fill, and a longer one is
# payload nobody can reach.
MSIS_HOURS_BACK = 48
MSIS_HOURS_AHEAD = 72
# The same horizontal grid the WAM layer publishes, deliberately. MSIS is a
# low-order harmonic fit and carries no structure that needs 4 degrees of
# latitude, so a coarser grid would lose nothing of the model -- but it would
# make the two fields look different at the boundary for a reason that has
# nothing to do with the models, and the whole point of the boundary is that
# what changes across it is the EVIDENCE.
MSIS_LATITUDE_STEP_DEG = 4.0
MSIS_LONGITUDE_STEP_DEG = 8.0
MSIS_VERSION = "2.1"


def msis_grid(
    *,
    latitude_step_deg: float = MSIS_LATITUDE_STEP_DEG,
    longitude_step_deg: float = MSIS_LONGITUDE_STEP_DEG,
) -> tuple[list[float], list[float]]:
    """The published horizontal grid: ascending, pole to pole, seam not repeated.

    Longitude stops one step short of 360 because 0 and 360 are the same
    meridian; publishing both would put a duplicated column in every frame and
    make the browser's wrap-around interpolation cross a zero-width cell.
    """
    if latitude_step_deg <= 0 or longitude_step_deg <= 0:
        raise ThermosphereFormatError("grid steps must be positive")
    latitude_count = int(round(180.0 / latitude_step_deg)) + 1
    longitude_count = int(round(360.0 / longitude_step_deg))
    latitudes = [-90.0 + latitude_step_deg * i for i in range(latitude_count)]
    longitudes = [longitude_step_deg * i for i in range(longitude_count)]
    return latitudes, longitudes


def msis_field(
    when: dt.datetime,
    latitudes: Sequence[float],
    longitudes: Sequence[float],
    altitudes_km: Sequence[float],
    f107: float,
    f107a: float,
    ap_history: Sequence[float],
    *,
    version: str = MSIS_VERSION,
) -> Any:
    """One NRLMSIS mass-density field, C-order (altitude, latitude, longitude).

    `ap_history` is MSIS's seven-element array and `geomagnetic_activity=-1`
    selects the storm-time formulation that reads all seven. Passing a scalar
    would silently select the daily-Ap formulation, which cannot show a storm
    arriving -- and a layer that cannot show a storm arriving is the layer this
    one replaced.
    """
    import numpy as np  # noqa: PLC0415
    from pymsis import Variable, calculate  # noqa: PLC0415

    if len(ap_history) != 7:
        raise ThermosphereFormatError(
            f"MSIS needs a seven-element ap history; got {len(ap_history)}"
        )
    naive = when.astimezone(dt.timezone.utc).replace(tzinfo=None)
    result = calculate(
        naive,
        [float(value) for value in longitudes],
        [float(value) for value in latitudes],
        [float(value) for value in altitudes_km],
        float(f107),
        float(f107a),
        [[float(value) for value in ap_history]],
        version=version,
        geomagnetic_activity=-1,
    )
    # pymsis returns (time, longitude, latitude, altitude, variable) and this
    # site's wire format is (altitude, latitude, longitude). The transpose is
    # written out rather than reshaped because a reshape of the wrong axes
    # produces a field that is the right size, the right range and completely
    # scrambled -- it would look like weather.
    density = np.asarray(result)[0, ..., Variable.MASS_DENSITY]
    return np.ascontiguousarray(np.transpose(density, (2, 1, 0)))


def build_msis_frame(
    when: dt.datetime,
    ap_series: Any,
    flux: Any,
    *,
    now: dt.datetime,
    latitudes: Sequence[float],
    longitudes: Sequence[float],
    altitudes_km: Sequence[float] = PUBLISHED_ALTITUDES_KM,
    bits: int = 16,
) -> dict[str, Any]:
    """One published MSIS frame, in the same shape a WAM frame is published in.

    The drivers used are carried ON the frame. A reader who asks why the air
    thickened at 09Z gets the ap that did it, from the same record as the
    numbers, and a future maintainer cannot re-derive them differently.
    """
    import numpy as np  # noqa: PLC0415

    when = when.astimezone(dt.timezone.utc)
    day = when.date()
    f107 = flux.f107_for(day)
    ap_history = ap_series.msis_history(when)
    density = msis_field(
        when, latitudes, longitudes, altitudes_km, f107, flux.f107a, ap_history
    )
    valid = np.isfinite(density) & (density > 0)
    if not valid.all():
        # MSIS is defined everywhere in this altitude range, so a hole means the
        # call was driven with something it could not use. Publishing it as a
        # gap would hide that behind a picture with a bite out of it.
        raise ThermosphereFormatError(
            f"NRLMSIS returned {int((~valid).sum())} non-finite samples at {utc_iso(when)}"
        )
    encoded = encode_log_density(density, valid, bits=bits)
    # WHETHER THIS HOUR IS A FORECAST, and the two ways of getting it wrong.
    #
    # The 3-hour Kp interval and the F10.7 day disagree about the word at the
    # edges, so the frame is only OBSERVED when BOTH drivers were observed. That
    # is the conservative direction: it can call a frame predicted that was
    # nearly observed, and it can never call a frame observed that was driven
    # off a forecast.
    #
    # And an hour AHEAD OF THE BUILD is a forecast whatever NOAA's label says.
    # NOAA marks the entire current UT day `estimated` in its Kp product:
    # measured 2026-08-20T03:53Z, seven of the eight intervals carrying that
    # word had not happened yet. Trusting the label alone would badge tonight's
    # thermosphere EMPIRICAL rather than EMPIRICAL - FORECAST, which is a
    # forecast presented as a reconstruction -- the exact substitution this
    # layer exists to stop making.
    ap_status = ap_series.status_at(when)
    flux_status = flux.status_for(day)
    ahead_of_build = when >= now.astimezone(dt.timezone.utc)
    observed = (
        not ahead_of_build
        and ap_status in {"observed", "estimated"}
        and flux_status == "observed"
    )
    return json_safe_frame({
        "validAt": utc_iso(when),
        "grid": {
            "altitudeKm": [float(value) for value in altitudes_km],
            "latitudeDeg": [float(value) for value in latitudes],
            "longitudeDeg": [float(value) for value in longitudes],
        },
        "quantity": "neutral mass density",
        "units": "kg m-3",
        "encoding": {
            "bits": encoded["bits"],
            "logFloor": encoded["logFloor"],
            "logCeiling": encoded["logCeiling"],
            "quantumDex": encoded["quantumDex"],
            "zeroMeans": encoded["zeroMeans"],
        },
        "codes": encoded["codes"],
        "validMask": pack_validity_mask(valid),
        "validFraction": 1.0,
        "sourceValidFraction": 1.0,
        "drivers": {
            "f107": round(float(f107), 1),
            "f107a": round(float(flux.f107a), 1),
            "kp": ap_series.kp_at(when),
            "ap": ap_series.ap_at(when),
            "apHistory": [round(float(value), 3) for value in ap_history],
            "apStatus": ap_status,
            "f107Status": flux_status,
            # Kept beside the two labels rather than re-derived downstream: the
            # browser has its own clock, and an hour's status must not change
            # depending on how long a reader left the tab open.
            "aheadOfBuild": ahead_of_build,
        },
        "driverStatus": "observed" if observed else "predicted",
    })


def msis_publish_hours(
    now: dt.datetime,
    *,
    hours_back: int = MSIS_HOURS_BACK,
    hours_ahead: int = MSIS_HOURS_AHEAD,
    shard_hours: int = MSIS_SHARD_HOURS,
) -> list[dt.datetime]:
    """Whole UTC hours covering the slider, extended out to shard boundaries.

    Anchored to the clock, not to `now`. Two builds five minutes apart return
    the same list except at the two ends, which is what keeps the shards
    byte-identical and off the wire.
    """
    if shard_hours < 1 or 24 % shard_hours:
        raise ThermosphereFormatError("shard length must divide the day")
    now = now.astimezone(dt.timezone.utc).replace(minute=0, second=0, microsecond=0)
    first = now - dt.timedelta(hours=hours_back)
    last = now + dt.timedelta(hours=hours_ahead)
    first -= dt.timedelta(hours=first.hour % shard_hours)
    trailing = last.hour % shard_hours
    if trailing:
        last += dt.timedelta(hours=shard_hours - trailing)
    steps = int((last - first).total_seconds() // 3600)
    return [first + dt.timedelta(hours=step) for step in range(steps + 1)]


def build_msis_bundle(
    now: dt.datetime | None = None,
    *,
    kp_rows: Sequence[Mapping[str, Any]],
    flux: Any = None,
    altitudes_km: Sequence[float] = PUBLISHED_ALTITUDES_KM,
    latitude_step_deg: float = MSIS_LATITUDE_STEP_DEG,
    longitude_step_deg: float = MSIS_LONGITUDE_STEP_DEG,
    shard_hours: int = MSIS_SHARD_HOURS,
    hours_back: int = MSIS_HOURS_BACK,
    hours_ahead: int = MSIS_HOURS_AHEAD,
    bits: int = 16,
) -> dict[str, Any]:
    """The empirical thermosphere across the whole slider, in six-hour shards.

    `kp_rows` are the rows this release already publishes for its Kp chart --
    observed record and NOAA forecast in one series -- so the ap that drives
    this model is the same geomagnetic history the rest of the site is drawing.
    Fetching Kp separately here would let the two disagree, and a thermosphere
    responding to a storm the Kp chart does not show is worse than no
    thermosphere at all.

    An hour the drivers cannot reach is NOT published. There is no default
    ap, no held-over F10.7 and no extrapolation: the series simply stops, the
    client finds no frame, and the card says so.
    """
    from pipeline.msis_drivers import ApSeries, driver_provenance, fetch_f107_series  # noqa: PLC0415

    now = (now or dt.datetime.now(dt.timezone.utc)).astimezone(dt.timezone.utc)
    ap_series = ApSeries(kp_rows)
    flux = flux if flux is not None else fetch_f107_series()

    latitudes, longitudes = msis_grid(
        latitude_step_deg=latitude_step_deg, longitude_step_deg=longitude_step_deg
    )
    wanted = msis_publish_hours(
        now, hours_back=hours_back, hours_ahead=hours_ahead, shard_hours=shard_hours
    )

    frames: list[dict[str, Any]] = []
    outside: list[dict[str, str]] = []
    for when in wanted:
        if not ap_series.covers(when) or when < ap_series.earliest_drivable():
            outside.append({"validAt": utc_iso(when), "reason": "no ap history from the published Kp series"})
            continue
        if not flux.covers(when.date()):
            outside.append({"validAt": utc_iso(when), "reason": "no F10.7 published for this day"})
            continue
        frames.append(
            build_msis_frame(
                when, ap_series, flux, now=now,
                latitudes=latitudes, longitudes=longitudes,
                altitudes_km=altitudes_km, bits=bits,
            )
        )

    if not frames:
        raise ThermosphereFormatError(
            "no hour in the release window had both drivers; "
            + "; ".join(item["reason"] for item in outside[:2])
        )

    shards: list[dict[str, Any]] = []
    step = dt.timedelta(hours=shard_hours)
    for frame in frames:
        when = parse_utc(frame["validAt"])
        start = when.replace(minute=0, second=0, microsecond=0) - dt.timedelta(
            hours=when.hour % shard_hours
        )
        if not shards or shards[-1]["validFrom"] != utc_iso(start):
            shards.append({
                "validFrom": utc_iso(start),
                "validTo": utc_iso(start + step),
                "cadenceMinutes": MSIS_CADENCE_MINUTES,
                "frames": [],
            })
        shards[-1]["frames"].append(frame)
    for shard in shards:
        statuses = {frame["driverStatus"] for frame in shard["frames"]}
        shard["frameCount"] = len(shard["frames"])
        shard["driverStatus"] = statuses.pop() if len(statuses) == 1 else "mixed"

    record = THERMOSPHERE_MODELS["nrlmsis21"]
    times = [frame["validAt"] for frame in frames]
    return {
        "generatedAt": utc_iso(now),
        "validFrom": times[0],
        "validTo": times[-1],
        "cadenceMinutes": MSIS_CADENCE_MINUTES,
        "shardHours": shard_hours,
        "publishedAltitudesKm": [float(value) for value in altitudes_km],
        "model": {
            "model": "nrlmsis21",
            "modelLabel": record["label"],
            "modelStatus": record["status"],
            "modelShortName": record["shortName"],
            "representation": record["description"],
            "strength": record["strength"],
            "limitation": record["limitation"],
            "version": MSIS_VERSION,
        },
        "source": {
            "product": f"NRLMSIS {MSIS_VERSION}, evaluated from NOAA SWPC F10.7 and Kp-derived ap",
            "status": "empirical",
            "quantity": "neutral (not ionised) mass density of the thermosphere",
            "productUrl": "https://map.nrl.navy.mil/map/pub/nrl/NRLMSIS/NRLMSIS2.1/",
            "implementation": "pymsis (US Government work, public domain)",
            "frameCount": len(frames),
            "validFrom": times[0],
            "validTo": times[-1],
            "notes": [
                "An empirical model: a published fit to decades of observation, not a measurement and not a physics simulation.",
                "Evaluated at every published hour from its own drivers. Nothing here is interpolated between frames and nothing is held over.",
                "Forward of the last observed Kp interval the drivers are NOAA's forecast, and the frames say so.",
            ],
        },
        "drivers": driver_provenance(ap_series, flux, now),
        # The hours the drivers could not reach, named. A shorter series than
        # the slider is a fact about the drivers and has to be visible, or it
        # reads as an atmosphere that stopped existing.
        "outsideDrivers": outside,
        "shards": shards,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--file", help="local wam_fixed_height NetCDF frame to reduce")
    parser.add_argument("--longitude-stride", type=int, default=2)
    parser.add_argument("--latitude-stride", type=int, default=2)
    parser.add_argument("--bits", type=int, default=16, choices=(8, 16))
    parser.add_argument("--f107", type=float, help="cross-check against NRLMSIS with this F10.7")
    parser.add_argument("--f107a", type=float)
    parser.add_argument("--ap", type=float, default=4.0)
    parser.add_argument(
        "--events",
        action="store_true",
        help="print the curated observation-vs-model comparison and exit",
    )
    args = parser.parse_args(argv)

    if args.events:
        if not msis_available():
            print("pymsis is not installed; the model comparison needs it")
            return 1
        rows = [compare_models_for_event(key) for key in CURATED_DENSITY_EVENTS]
        print(json.dumps({"curatedEvents": rows}, indent=2))
        return 0

    if not args.file:
        parser.error("--file is required; this module never fetches implicitly")

    import netCDF4  # noqa: PLC0415

    with netCDF4.Dataset(args.file) as dataset:
        frame = parse_wam_fixed_height(dataset)

    reduced = reduce_thermosphere_frame(
        frame,
        longitude_stride=args.longitude_stride,
        latitude_stride=args.latitude_stride,
        bits=args.bits,
    )
    summary = {
        "validAt": reduced["validAt"],
        "shape": [len(reduced["grid"][k]) for k in ("altitudeKm", "latitudeDeg", "longitudeDeg")],
        "encoding": reduced["encoding"],
        "codeBytes": reduced["codes"].nbytes,
        "maskBytes": len(reduced["validMask"]),
        "validFraction": round(reduced["validFraction"], 5),
        "source": source_metadata([frame]),
    }
    print(json.dumps(summary, indent=2))

    if args.f107 is not None:
        if not msis_available():
            print("pymsis is not installed; skipping the NRLMSIS cross-check")
        else:
            rows = compare_to_msis(frame, args.f107, args.f107a or args.f107, args.ap)
            print(json.dumps({"msisCrossCheck": rows}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
