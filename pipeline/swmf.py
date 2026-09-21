"""Reduce NOAA's operational SWMF outputs into compact browser-ready model frames.

NOAA NOMADS publishes the actual one-minute BATS-R-US y=0/z=0 IDL plot files and
the coupled Radiation Belt Environment (RBE) electron solution.  The browser must
not download those multi-megabyte scientific files directly, so bigmem-PC selects
a two-hour sequence, validates it, and quantizes only the fields used by the site.
"""

from __future__ import annotations

import base64
import datetime as dt
import html
import math
import os
import re
import statistics
import struct
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from array import array
from pathlib import Path
from typing import Any, Iterable


NOMADS_ROOT = "https://nomads.ncep.noaa.gov/pub/data/nccf/com/swmf/prod"
USER_AGENT = "SpaceEnvironmentExplorer/0.2 educational-project contact=sean.theinformed.org"
DEFAULT_CACHE = Path("/mnt/d/space-explorer/swmf-cache")
FALLBACK_CACHE = Path(__file__).resolve().parent / ".cache" / "swmf"
FRAME_OFFSETS_MINUTES = (-60, -40, -20, 0, 20, 40)
PLANE_BOUNDS_RE = (-55.0, 25.0, -35.0, 35.0)
STRUCTURE_ANGLES_DEGREES = tuple(range(-70, 71, 5))
STRUCTURE_RADIUS_SCALE = 100
STRUCTURE_MISSING_U16 = 65535
STREAMLINE_COORDINATE_SCALE = 100
STREAMLINE_SPEED_SCALE = 10
FIELD_MASK_MISSING = 1
FIELD_MASK_CLIPPED_LOW = 2
FIELD_MASK_CLIPPED_HIGH = 4

FIELD_ENCODINGS = {
    "density": {"scale": "log10", "minimum": -2.0, "maximum": 1.7, "units": "amu cm⁻³"},
    "speed": {"scale": "linear", "minimum": 0.0, "maximum": 1000.0, "units": "km s⁻¹"},
    "pressure": {"scale": "log10", "minimum": -3.0, "maximum": 1.3, "units": "nPa"},
    "magneticField": {"scale": "log10", "minimum": 0.0, "maximum": 3.0, "units": "nT"},
}
RADIATION_ENCODING = {
    "scale": "log10",
    "minimum": -2.0,
    "maximum": 9.0,
    "quantity": "near-90° pitch-angle differential electron flux",
    "units": "model-native differential flux",
}

# ---------------------------------------------------------------------------
# Ground magnetic perturbation (mag_grid)
#
# The same NOAA run that publishes the y=0/z=0 cut planes also publishes, every
# minute, the ground magnetic perturbation its ionosphere/magnetosphere solution
# would produce on a 5-degree GEOGRAPHIC grid, decomposed by the current system
# responsible for it. That is what a geomagnetic storm is at the ground: the
# quantity a magnetometer records and the quantity that drives geomagnetically
# induced currents.
#
# Two things about this file differ from everything else in this module and are
# easy to get wrong:
#
#   * its coordinates are GEO (Earth-fixed latitude/longitude), not GSM. It is
#     drawn on the globe next to coastlines, not in the Sun-fixed group; and
#   * the four per-source columns are the MODEL'S OWN attribution of its own
#     ground signature, not four measurements. Nothing observed separates them.
#
# The decomposition is also coarser than the textbook current-system diagram.
# ``Fac`` is the Birkeland (field-aligned) current sheets and ``Hal``/``Ped``
# are their ionospheric closure -- Hall being the auroral electrojets. But
# ``Mhd`` is a single lump containing the ring current, the cross-tail current
# sheet and the magnetopause (Chapman-Ferraro) currents together. Labelling it
# "ring current" would be wrong, and this file never does.
# ---------------------------------------------------------------------------

MAG_GRID_HEADER = "Magnetometer grid (GEO) [deg] dB (North-East-Down) [nT]"
MAG_GRID_COLUMNS = (
    "Lon", "Lat",
    "dBn", "dBe", "dBd",
    "dBnMhd", "dBeMhd", "dBdMhd",
    "dBnFac", "dBeFac", "dBdFac",
    "dBnHal", "dBeHal", "dBdHal",
    "dBnPed", "dBePed", "dBdPed",
)
#: Public key -> the suffix NOAA uses on its per-source columns.
GROUND_CURRENT_SYSTEMS = (
    ("total", ""),
    ("magnetospheric", "Mhd"),
    ("fieldAligned", "Fac"),
    ("hall", "Hal"),
    ("pedersen", "Ped"),
)
#: Public key -> the NOAA column stem. North-East-Down, as the header states.
GROUND_COMPONENTS = (("north", "dBn"), ("east", "dBe"), ("down", "dBd"))
#: Wide enough that clipping is a real-storm event rather than a routine one.
#: The Carrington-class literature figure is a few thousand nT; the strongest
#: cell in the file this was written against was 910 nT. 10,000 nT across a
#: uint16 resolves 0.153 nT, which is finer than a magnetometer's noise floor.
GROUND_FIELD_ENCODING = {
    "scale": "linear",
    "minimum": -5000.0,
    "maximum": 5000.0,
    "units": "nT",
    "quantity": "ground magnetic perturbation component",
}
#: The grid the operational run has published for as long as we have watched it.
#: Checked, never assumed: a changed grid fails the frame rather than reshaping
#: a browser array that the renderer would then index off the end of.
MAG_GRID_EXPECTED_SHAPE = (72, 35)
MAG_GRID_MINIMUM_BYTES = 400_000


def _utc(value: dt.datetime) -> dt.datetime:
    return value.astimezone(dt.timezone.utc)


def _iso(value: dt.datetime) -> str:
    return _utc(value).isoformat(timespec="seconds").replace("+00:00", "Z")


def _cache_root() -> Path:
    configured = os.environ.get("SPACE_EXPLORER_SWMF_CACHE")
    if configured:
        return Path(configured)
    return DEFAULT_CACHE if DEFAULT_CACHE.parent.is_dir() else FALLBACK_CACHE


def _request_bytes(url: str, timeout: int = 90) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read()
    # Counted here rather than in _cached_file, because that returns cached
    # bytes that never crossed the network. See pipeline/build_release._count_ingress
    # for why this is recorded on the "raw" basis and why it swallows everything.
    try:
        from ops import bandwidth  # noqa: PLC0415 - optional, never load-bearing

        bandwidth.record_fetch(len(body), family="noaa-nomads-swmf",
                               source="urllib response.read() length (decoded)",
                               run="swmf")
    except Exception:  # noqa: BLE001 - measurement must never break a fetch
        pass
    if not body:
        raise RuntimeError(f"empty NOAA SWMF response: {url}")
    return body


def _listing(url: str) -> list[str]:
    page = _request_bytes(url).decode("utf-8", errors="replace")
    return [html.unescape(item) for item in re.findall(r'href="([^"?#]+)', page)]


def _cached_file(url: str, minimum_size: int) -> bytes:
    parsed = urllib.parse.urlsplit(url)
    day = next((part.removeprefix("swmf.") for part in parsed.path.split("/") if part.startswith("swmf.")), "unknown")
    destination = _cache_root() / day / Path(parsed.path).name
    if destination.is_file() and destination.stat().st_size >= minimum_size:
        return destination.read_bytes()
    destination.parent.mkdir(parents=True, exist_ok=True)
    body = _request_bytes(url)
    if len(body) < minimum_size:
        raise RuntimeError(f"implausibly small NOAA SWMF file ({len(body)} bytes): {url}")
    descriptor, temporary = tempfile.mkstemp(prefix=f".{destination.name}.", dir=destination.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(body)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
    return body


def _parse_timestamp(value: str) -> dt.datetime:
    normalized = value.replace("_", "T")
    return dt.datetime.strptime(normalized, "%Y%m%dT%H%M%S").replace(tzinfo=dt.timezone.utc)


def _discover_files(now: dt.datetime) -> tuple[dict[dt.datetime, dict[str, tuple[str, str]]], dict[dt.datetime, str]]:
    gm: dict[dt.datetime, dict[str, tuple[str, str]]] = {}
    radiation: dict[dt.datetime, str] = {}
    anchor = _utc(now).replace(second=0, microsecond=0)
    days = {anchor.date(), (anchor - dt.timedelta(minutes=70)).date()}
    for day in sorted(days):
        stamp = day.strftime("%Y%m%d")
        day_root = f"{NOMADS_ROOT}/swmf.{stamp}"
        gm_root = f"{day_root}/GM/IO2/"
        rb_root = f"{day_root}/RB/plots/"
        for name in _listing(gm_root):
            # mag_grid rides the SAME directory listing the cut planes already
            # cost us, so discovering the ground field adds no listing bytes at
            # all -- only the frames actually published are ever downloaded.
            match = re.fullmatch(r"(y0|z0)_(\d{8}T\d{4})_(\d{8}T\d{6})", name) or re.fullmatch(
                r"(mag_grid)_(\d{8}T\d{4})_(\d{8}T\d{6})\.txt", name
            )
            if not match:
                continue
            plane, cycle, valid_text = match.groups()
            valid = _parse_timestamp(valid_text)
            prior = gm.setdefault(valid, {}).get(plane)
            if prior is None or cycle > prior[0]:
                gm[valid][plane] = (cycle, urllib.parse.urljoin(gm_root, name))
        for name in _listing(rb_root):
            match = re.fullmatch(r"(\d{8}_\d{6})_e\.fls", name)
            if match:
                radiation[_parse_timestamp(match.group(1))] = urllib.parse.urljoin(rb_root, name)
    return gm, radiation


def _select_times(now: dt.datetime, gm: dict[dt.datetime, dict[str, tuple[str, str]]], radiation: dict[dt.datetime, str]) -> list[dt.datetime]:
    common = sorted(time for time, planes in gm.items() if {"y0", "z0"}.issubset(planes) and time in radiation)
    if not common:
        raise RuntimeError("NOAA SWMF listings have no common GM/RBE valid time")
    now = _utc(now)
    anchor_minute = (now.minute // 20) * 20
    anchor = now.replace(minute=anchor_minute, second=0, microsecond=0)
    selected: list[dt.datetime] = []
    for offset in FRAME_OFFSETS_MINUTES:
        wanted = anchor + dt.timedelta(minutes=offset)
        nearest = min(common, key=lambda item: abs((item - wanted).total_seconds()))
        if abs((nearest - wanted).total_seconds()) <= 6 * 60 and nearest not in selected:
            selected.append(nearest)
    selected.sort()
    if len(selected) < 4:
        raise RuntimeError(f"NOAA SWMF sequence is incomplete: only {len(selected)} usable frames")
    return selected


def _fortran_records(body: bytes) -> list[memoryview]:
    records: list[memoryview] = []
    view = memoryview(body)
    offset = 0
    while offset < len(view):
        if offset + 8 > len(view):
            raise RuntimeError("truncated SWMF Fortran record marker")
        length = struct.unpack_from("<i", view, offset)[0]
        offset += 4
        if length <= 0 or offset + length + 4 > len(view):
            raise RuntimeError(f"invalid SWMF Fortran record length: {length}")
        records.append(view[offset : offset + length])
        offset += length
        closing = struct.unpack_from("<i", view, offset)[0]
        offset += 4
        if closing != length:
            raise RuntimeError("mismatched SWMF Fortran record markers")
    return records


def _float_array(payload: memoryview) -> array[float]:
    values: array[float] = array("f")
    values.frombytes(payload.tobytes())
    if sys.byteorder != "little":
        values.byteswap()
    return values


def _parse_plane(body: bytes) -> dict[str, Any]:
    records = _fortran_records(body)
    if len(records) < 17:
        raise RuntimeError(f"unexpected SWMF plane record count: {len(records)}")
    _, _, dimensions, _, variable_count = struct.unpack("<ifiii", records[1])
    point_count, secondary = struct.unpack("<ii", records[2])
    if dimensions != -2 or secondary != 1 or variable_count != 11 or point_count < 10_000:
        raise RuntimeError(f"unexpected SWMF plane metadata: dim={dimensions}, points={point_count}, vars={variable_count}")
    names = records[4].tobytes().decode("ascii", errors="replace").strip().split()
    expected_fields = ["Rho", "Ux", "Uy", "Uz", "Bx", "By", "Bz", "P", "jx", "jy", "jz"]
    if names[0] != "x" or names[1] not in {"y", "z"} or names[2:13] != expected_fields:
        raise RuntimeError(f"unexpected SWMF plane variables: {names[:13]}")
    coordinates = _float_array(records[5])
    if len(coordinates) != point_count * 2:
        raise RuntimeError("SWMF plane coordinate count mismatch")
    variables = [_float_array(record) for record in records[6:17]]
    if any(len(values) != point_count for values in variables):
        raise RuntimeError("SWMF plane field count mismatch")
    return {
        "x": coordinates[:point_count],
        "cross": coordinates[point_count:],
        "rho": variables[0],
        "ux": variables[1],
        "uy": variables[2],
        "uz": variables[3],
        "bx": variables[4],
        "by": variables[5],
        "bz": variables[6],
        "pressure": variables[7],
        "jx": variables[8],
        "jy": variables[9],
        "jz": variables[10],
    }


def _little_endian_base64(values: array[Any]) -> str:
    if sys.byteorder != "little":
        values.byteswap()
    return base64.b64encode(values.tobytes()).decode("ascii")


def _encode_coordinates(x: Iterable[float], cross: Iterable[float], indices: list[int]) -> str:
    encoded: array[int] = array("h")
    for index in indices:
        encoded.append(round(x[index] * 100))
        encoded.append(round(cross[index] * 100))
    return _little_endian_base64(encoded)


def _quantized_with_mask(
    values: Iterable[float],
    indices: list[int],
    encoding: dict[str, Any],
) -> tuple[str, str]:
    minimum = float(encoding["minimum"])
    maximum = float(encoding["maximum"])
    logarithmic = encoding["scale"] == "log10"
    output: array[int] = array("H")
    masks: array[int] = array("B")
    span = maximum - minimum
    for index in indices:
        value = values[index]
        if not math.isfinite(value):
            normalized = 0.0
            mask = FIELD_MASK_MISSING
        else:
            transformed = math.log10(value) if logarithmic and value > 0 else value
            if logarithmic and value <= 0:
                transformed = minimum
                mask = FIELD_MASK_CLIPPED_LOW
            elif transformed < minimum:
                mask = FIELD_MASK_CLIPPED_LOW
            elif transformed > maximum:
                mask = FIELD_MASK_CLIPPED_HIGH
            else:
                mask = 0
            normalized = max(0.0, min(1.0, (transformed - minimum) / span))
        output.append(round(normalized * 65535))
        masks.append(mask)
    return _little_endian_base64(output), _little_endian_base64(masks)


def _quantized(values: Iterable[float], indices: list[int], encoding: dict[str, Any]) -> str:
    encoded, _ = _quantized_with_mask(values, indices, encoding)
    return encoded


def _encode_plane(parsed: dict[str, Any], indices: list[int]) -> dict[str, dict[str, str]]:
    speed = array("f", (
        math.sqrt(parsed["ux"][index] ** 2 + parsed["uy"][index] ** 2 + parsed["uz"][index] ** 2)
        for index in range(len(parsed["ux"]))
    ))
    magnetic = array("f", (
        math.sqrt(parsed["bx"][index] ** 2 + parsed["by"][index] ** 2 + parsed["bz"][index] ** 2)
        for index in range(len(parsed["bx"]))
    ))
    source_fields = {
        "density": parsed["rho"],
        "speed": speed,
        "pressure": parsed["pressure"],
        "magneticField": magnetic,
    }
    fields: dict[str, str] = {}
    masks: dict[str, str] = {}
    for name, values in source_fields.items():
        fields[name], masks[name] = _quantized_with_mask(values, indices, FIELD_ENCODINGS[name])
    return {"fieldsU16": fields, "fieldMasksU8": masks}


def _plane_indices(parsed: dict[str, Any]) -> list[int]:
    xmin, xmax, cross_min, cross_max = PLANE_BOUNDS_RE
    return [
        index
        for index, (x, cross) in enumerate(zip(parsed["x"], parsed["cross"]))
        if xmin <= x <= xmax and cross_min <= cross <= cross_max and math.hypot(x, cross) >= 2.55
    ]


class _PlaneSampler:
    """Small dependency-free interpolator for the adaptive 2-D model cuts."""

    field_names = ("rho", "ux", "uy", "uz", "bx", "by", "bz", "pressure", "jx", "jy", "jz")

    def __init__(self, parsed: dict[str, Any], cell_size_re: float = 1.0):
        self.x = parsed["x"]
        self.cross = parsed["cross"]
        self.fields = tuple(parsed[name] for name in self.field_names)
        self.cell_size_re = cell_size_re
        self.bins: dict[tuple[int, int], list[int]] = {}
        for index, (x_value, cross_value) in enumerate(zip(self.x, self.cross)):
            key = (math.floor(x_value / cell_size_re), math.floor(cross_value / cell_size_re))
            self.bins.setdefault(key, []).append(index)

    def sample(self, x_value: float, cross_value: float) -> tuple[float, ...] | None:
        x_bin = math.floor(x_value / self.cell_size_re)
        cross_bin = math.floor(cross_value / self.cell_size_re)
        candidates: list[int] = []
        for radius in range(3):
            candidates = [
                index
                for x_offset in range(-radius, radius + 1)
                for cross_offset in range(-radius, radius + 1)
                for index in self.bins.get((x_bin + x_offset, cross_bin + cross_offset), ())
            ]
            if len(candidates) >= 6:
                break
        nearest = sorted(
            candidates,
            key=lambda index: (self.x[index] - x_value) ** 2 + (self.cross[index] - cross_value) ** 2,
        )[:6]
        if not nearest:
            return None
        distances = [math.hypot(self.x[index] - x_value, self.cross[index] - cross_value) for index in nearest]
        # The dayside model is more finely resolved than this cutoff. Refuse to
        # bridge a larger adaptive-grid gap rather than inventing a structure.
        if distances[0] > 0.8:
            return None
        if distances[0] < 1e-7:
            return tuple(float(field[nearest[0]]) for field in self.fields)
        weights = [1.0 / max(distance * distance, 1e-5) for distance in distances]
        weight_sum = sum(weights)
        return tuple(
            sum(float(field[index]) * weight for index, weight in zip(nearest, weights)) / weight_sum
            for field in self.fields
        )


def _plasma_diagnostics(sample: tuple[float, ...]) -> dict[str, float]:
    rho, ux, uy, uz, bx, by, bz, pressure, jx, jy, jz = sample
    return {
        "density": max(rho, 1e-8),
        "speed": math.sqrt(ux * ux + uy * uy + uz * uz),
        "magneticField": math.sqrt(bx * bx + by * by + bz * bz),
        "pressure": max(pressure, 1e-8),
        "currentDensity": math.sqrt(jx * jx + jy * jy + jz * jz),
    }


def _ray_samples(sampler: _PlaneSampler, angle_degrees: float) -> list[dict[str, float]]:
    angle = math.radians(angle_degrees)
    cosine = math.cos(angle)
    sine = math.sin(angle)
    # Stay inside the same crop that is published for the scalar planes.
    radial_limits = [40.0]
    if cosine > 1e-6:
        radial_limits.append(PLANE_BOUNDS_RE[1] / cosine)
    if abs(sine) > 1e-6:
        radial_limits.append(PLANE_BOUNDS_RE[3] / abs(sine))
    maximum_radius = max(8.0, min(radial_limits) - 0.5)
    samples: list[dict[str, float]] = []
    steps = max(0, math.floor((maximum_radius - 5.0) / 0.25))
    for step in range(steps, -1, -1):
        radius = 5.0 + step * 0.25
        raw = sampler.sample(radius * cosine, radius * sine)
        if raw is None:
            continue
        samples.append({"radius": radius, **_plasma_diagnostics(raw)})
    return samples


def _ray_boundaries(samples: list[dict[str, float]]) -> tuple[float | None, float | None]:
    """Find conservative raywise bow-shock and magnetopause proxy radii.

    The bow-shock proxy is the strongest local transition within 3 RE of the
    outermost point where density and thermal pressure rise while flow slows
    relative to the undisturbed outer samples. The inner proxy is a modeled
    current-density ridge supported by an inward density drop. Neither result is
    promoted to a directly resolved 3-D discontinuity.
    """

    if len(samples) < 20:
        return None, None
    upstream = samples[: min(16, len(samples))]
    upstream_density = statistics.median(item["density"] for item in upstream)
    upstream_pressure = statistics.median(item["pressure"] for item in upstream)
    upstream_speed = statistics.median(item["speed"] for item in upstream)
    if upstream_speed <= 0 or upstream_pressure <= 0 or upstream_density <= 0:
        return None, None

    shock_candidates: list[tuple[float, float]] = []
    for index in range(2, len(samples) - 2):
        point = samples[index]
        if not (
            point["density"] >= 1.3 * upstream_density
            and point["pressure"] >= 5.0 * upstream_pressure
            and point["speed"] <= 0.96 * upstream_speed
        ):
            continue
        outer = samples[index - 2]
        inner = samples[index + 2]
        strength = (
            math.log(max(inner["density"] / outer["density"], 1e-8))
            + math.log(max(inner["pressure"] / outer["pressure"], 1e-8))
            + math.log(max(outer["speed"] / max(inner["speed"], 1e-8), 1e-8))
        )
        shock_candidates.append((strength, point["radius"]))
    if not shock_candidates:
        return None, None
    outermost_candidate = max(radius for _, radius in shock_candidates)
    supported_shock = [item for item in shock_candidates if item[1] >= outermost_candidate - 3.0]
    _, shock_radius = max(supported_shock)

    inner_limit = max(5.5, 0.5 * shock_radius)
    outer_limit = shock_radius - 2.0
    current_samples = [
        item for item in samples if inner_limit <= item["radius"] <= outer_limit
    ]
    if len(current_samples) < 5:
        return shock_radius, None
    median_current = max(statistics.median(item["currentDensity"] for item in current_samples), 1e-8)
    magnetopause_candidates: list[tuple[float, float, float]] = []
    for index in range(2, len(samples) - 2):
        point = samples[index]
        if not inner_limit <= point["radius"] <= outer_limit:
            continue
        outer = samples[index - 2]
        inner = samples[index + 2]
        density_drop = max(0.0, math.log(max(outer["density"] / inner["density"], 1e-8)))
        magnetic_rise = max(
            0.0,
            math.log(max(inner["magneticField"] / max(outer["magneticField"], 1e-8), 1e-8)),
        )
        score = (
            point["currentDensity"]
            / median_current
            * (0.25 + density_drop)
            * (1.0 + 0.5 * magnetic_rise)
        )
        magnetopause_candidates.append((score, point["radius"], density_drop))
    if not magnetopause_candidates:
        return shock_radius, None
    score, magnetopause_radius, density_drop = max(magnetopause_candidates)
    if score < 1.0 or density_drop < 0.25:
        return shock_radius, None
    return shock_radius, magnetopause_radius


def _encode_profile(values: Iterable[float | None]) -> str:
    encoded: array[int] = array("H")
    for value in values:
        if value is None or not math.isfinite(value) or value < 0:
            encoded.append(STRUCTURE_MISSING_U16)
        else:
            encoded.append(min(STRUCTURE_MISSING_U16 - 1, round(value * STRUCTURE_RADIUS_SCALE)))
    return _little_endian_base64(encoded)


def _inside_structure_bounds(point: tuple[float, float]) -> bool:
    x_value, cross_value = point
    xmin, xmax, cross_min, cross_max = PLANE_BOUNDS_RE
    return (
        xmin <= x_value <= xmax
        and cross_min <= cross_value <= cross_max
        and math.hypot(x_value, cross_value) >= 2.7
    )


def _projected_direction(
    sampler: _PlaneSampler,
    point: tuple[float, float],
    plane: str,
    field: str,
) -> tuple[float, float] | None:
    sample = sampler.sample(*point)
    if sample is None:
        return None
    _, ux, uy, uz, bx, by, bz, *_ = sample
    if field == "flow":
        x_component, cross_component = ux, uy if plane == "equatorial" else uz
        total = math.sqrt(ux * ux + uy * uy + uz * uz)
    else:
        x_component, cross_component = bx, by if plane == "equatorial" else bz
        total = math.sqrt(bx * bx + by * by + bz * bz)
    projected = math.hypot(x_component, cross_component)
    # A tiny in-plane projection cannot support a meaningful projected line.
    if projected < 1e-9 or total < 1e-9 or projected / total < 0.15:
        return None
    return x_component / projected, cross_component / projected


def _trace_direction(
    sampler: _PlaneSampler,
    seed: tuple[float, float],
    plane: str,
    field: str,
    sign: float,
    *,
    step_re: float = 0.3,
    maximum_steps: int = 260,
) -> list[tuple[float, float]]:
    points = [seed]
    visited: set[tuple[int, int]] = set()
    for _ in range(maximum_steps):
        current = points[-1]
        direction = _projected_direction(sampler, current, plane, field)
        if direction is None:
            break
        midpoint = (
            current[0] + sign * direction[0] * step_re * 0.5,
            current[1] + sign * direction[1] * step_re * 0.5,
        )
        midpoint_direction = _projected_direction(sampler, midpoint, plane, field)
        if midpoint_direction is None:
            break
        candidate = (
            current[0] + sign * midpoint_direction[0] * step_re,
            current[1] + sign * midpoint_direction[1] * step_re,
        )
        if not _inside_structure_bounds(candidate):
            break
        cell = (round(candidate[0] / step_re), round(candidate[1] / step_re))
        if cell in visited and len(points) > 8:
            break
        visited.add(cell)
        points.append(candidate)
    return points


def _trace_projected_line(
    sampler: _PlaneSampler,
    seed: tuple[float, float],
    plane: str,
    field: str,
) -> list[tuple[float, float]]:
    if field == "flow":
        return _trace_direction(sampler, seed, plane, field, 1.0)
    backward = _trace_direction(sampler, seed, plane, field, -1.0)
    forward = _trace_direction(sampler, seed, plane, field, 1.0)
    return list(reversed(backward[1:])) + forward


def _streamline_seeds(plane: str, field: str) -> list[tuple[float, float]]:
    if field == "flow":
        return [(24.0, cross) for cross in (-20.0, -16.0, -12.0, -8.0, -4.0, 0.0, 4.0, 8.0, 12.0, 16.0, 20.0)]
    circle = [
        (3.2 * math.cos(math.radians(angle)), 3.2 * math.sin(math.radians(angle)))
        for angle in range(0, 360, 30)
    ]
    tail = [(-8.0, cross) for cross in (-6.0, -3.0, 3.0, 6.0)]
    if plane == "meridional":
        tail.extend([(-16.0, -5.0), (-16.0, 5.0)])
    return circle + tail


def _encode_streamlines(
    lines: Iterable[list[tuple[float, float]]],
    sampler: _PlaneSampler | None = None,
) -> dict[str, Any]:
    retained = [line for line in lines if len(line) >= 5]
    coordinates: array[int] = array("h")
    offsets: array[int] = array("H", [0])
    speeds: array[int] = array("H")
    point_count = 0
    for line in retained:
        if point_count + len(line) >= 65535:
            break
        for x_value, cross_value in line:
            coordinates.append(round(x_value * STREAMLINE_COORDINATE_SCALE))
            coordinates.append(round(cross_value * STREAMLINE_COORDINATE_SCALE))
            if sampler is not None:
                sample = sampler.sample(x_value, cross_value)
                if sample is None:
                    speed = 0.0
                else:
                    _, ux, uy, uz, *_ = sample
                    speed = math.sqrt(ux * ux + uy * uy + uz * uz)
                speeds.append(min(65535, max(0, round(speed * STREAMLINE_SPEED_SCALE))))
        point_count += len(line)
        offsets.append(point_count)
    encoded = {
        "lineCount": max(0, len(offsets) - 1),
        "pointCount": point_count,
        "coordinatesI16": _little_endian_base64(coordinates),
        "offsetsU16": _little_endian_base64(offsets),
    }
    if sampler is not None:
        encoded["speedU16"] = _little_endian_base64(speeds)
    return encoded


def _derive_plane_structures(parsed: dict[str, Any], plane: str) -> dict[str, Any]:
    sampler = _PlaneSampler(parsed)
    bow_shock: list[float | None] = []
    magnetopause: list[float | None] = []
    for angle in STRUCTURE_ANGLES_DEGREES:
        shock_radius, magnetopause_radius = _ray_boundaries(_ray_samples(sampler, angle))
        bow_shock.append(shock_radius)
        magnetopause.append(magnetopause_radius)

    magnetic_lines = [
        _trace_projected_line(sampler, seed, plane, "magnetic")
        for seed in _streamline_seeds(plane, "magnetic")
    ]
    flow_lines = [
        _trace_projected_line(sampler, seed, plane, "flow")
        for seed in _streamline_seeds(plane, "flow")
    ]
    return {
        "bowShockRadiusU16": _encode_profile(bow_shock),
        "magnetopauseProxyRadiusU16": _encode_profile(magnetopause),
        "projectedMagneticStreamlines": _encode_streamlines(magnetic_lines),
        "projectedFlowStreamlines": _encode_streamlines(flow_lines, sampler),
    }


NUMBER = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[Ee][-+]?\d+)?")


def _line_numbers(line: str) -> list[float]:
    return [float(item) for item in NUMBER.findall(line.split("!", 1)[0])]


def _consume_values(lines: list[str], line_index: int, count: int) -> tuple[list[float], int]:
    values: list[float] = []
    while len(values) < count:
        if line_index >= len(lines):
            raise RuntimeError("truncated NOAA RBE header")
        values.extend(_line_numbers(lines[line_index]))
        line_index += 1
    if len(values) != count:
        raise RuntimeError("unexpected NOAA RBE header wrapping")
    return values, line_index


# Beyond this the mapped crossing is not a stretched tail any more, it is wrong.
RBE_RADIUS_OUTLIER_MAX = 40.0
# If more than this fraction of cells fall outside the band, the frame itself is
# suspect and the publish should fail rather than serve a hollowed-out belt.
RBE_MAX_OUTLIER_FRACTION = 0.02


def _rbe_equatorial_coordinate(metadata: list[float]) -> tuple[float, float] | None:
    """Return mapped equatorial radius/MLT, not the uniform source-grid MLT."""

    if len(metadata) != 7:
        raise RuntimeError("unexpected NOAA RBE block metadata")
    equatorial_radius = metadata[2]
    equatorial_mlt = metadata[3] % 24
    # The band used to be a hard <= 15 R_E and a single point outside it raised,
    # which threw away the entire geospace bundle -- belts, cut planes and all --
    # for one cell. NOAA's mapped equatorial radius genuinely exceeds 15 R_E on a
    # stretched tail: observed 16.15 on 2026-08-07 and 17.05 on 2026-08-08, in
    # contiguous blocks that were otherwise clean. That is a physical signature,
    # not corruption, so a lone outlier must not be able to blank the layer.
    #
    # Outliers are now dropped and COUNTED, never silently kept. The caller
    # fails the frame if too many are bad, so systemic corruption still stops the
    # publish while a stretched tail does not. Nothing is interpolated to replace
    # a dropped cell.
    #
    # CORRECTION, 2026-08-08: an earlier version of this comment said a dropped
    # cell "is simply absent, which the renderer already handles". It does not.
    # src/radiation-belt.ts validateGridShape() throws RangeError unless the
    # published gridShape multiplies out to the published point count, so an
    # absent cell is a client-side crash, not a gap. This function therefore only
    # REPORTS that a cell is out of band; _parse_radiation() decides what to drop,
    # and it drops whole radial shells so the grid stays rectangular.
    if not (0 <= metadata[3] <= 24.5 and 0.9 <= equatorial_radius <= RBE_RADIUS_OUTLIER_MAX):
        return None
    return equatorial_radius, equatorial_mlt


def _parse_radiation(body: bytes) -> dict[str, Any]:
    lines = body.decode("ascii", errors="strict").splitlines()
    header = _line_numbers(lines[0])
    if len(header) != 6:
        raise RuntimeError(f"unexpected NOAA RBE header: {header}")
    _, radial_count_f, mlt_count_f, energy_count_f, pitch_count_f, _ = header
    radial_count, mlt_count = int(radial_count_f), int(mlt_count_f)
    energy_count, pitch_count = int(energy_count_f), int(pitch_count_f)
    if (radial_count, mlt_count, energy_count, pitch_count) != (51, 48, 12, 12):
        raise RuntimeError(f"unexpected NOAA RBE grid: {(radial_count, mlt_count, energy_count, pitch_count)}")
    line_index = 1
    energies, line_index = _consume_values(lines, line_index, energy_count)
    pitch_grid, line_index = _consume_values(lines, line_index, pitch_count)
    radial_grid, line_index = _consume_values(lines, line_index, radial_count)
    run_parameters = _line_numbers(lines[line_index])[:11]
    line_index += 1
    if len(run_parameters) != 11:
        raise RuntimeError("unexpected NOAA RBE run parameter count")

    chosen_indices = [4, 7, 9, 10]
    values_per_block = energy_count * pitch_count
    total_blocks = radial_count * mlt_count

    # ---- pass 1: read every block, judge it, drop NOTHING yet ---------------
    #
    # The drop cannot be decided per cell here, because the published product is
    # a RECTANGULAR grid: the artifact carries gridShape, and src/radiation-belt.ts
    # validateGridShape() THROWS RangeError unless radialCount * mltCount equals
    # the published point count exactly. Removing single cells from a flat
    # radial-major list leaves a punctured grid that no rectangle describes, so
    # the browser would have thrown the moment the outlier path first fired --
    # trading a server-side layer loss for a client-side crash of the same layer,
    # in a branch that nothing exercises while the data happens to be in band.
    # Verified against a synthetic frame: one dropped cell gives 2447 points
    # under a 51x48=2448 gridShape.
    #
    # So a shell -- one radial index, all mlt_count of its cells -- is the
    # smallest unit that can be removed while leaving a grid that is still a
    # rectangle and a gridShape that is still true. Anything smaller cannot be
    # published, and publishing a shape that does not describe the data is the
    # one thing this file must never do.
    block_metadata: list[list[float]] = []
    block_distributions: list[list[float]] = []
    out_of_band: list[tuple[float, float]] = []       # (mlt, radius), for the report
    bad_shells: set[int] = set()
    misordered_shells: set[int] = set()
    for block_index in range(total_blocks):
        metadata, line_index = _consume_values(lines, line_index, 7)
        distribution, line_index = _consume_values(lines, line_index, values_per_block)
        block_metadata.append(metadata)
        block_distributions.append(distribution)
        radial_index, mlt_index = divmod(block_index, mlt_count)
        source_grid_mlt = mlt_index * 24 / mlt_count
        # This ordering tolerance used to raise, which made it the same
        # one-bad-block-kills-the-bundle shape as the plausibility band four
        # lines below it -- it is a float comparison on ONE block's values, not
        # a check on the file's structure. It now condemns that block's shell
        # and is subject to the same aggregate backstop.
        if (abs(metadata[0] - radial_grid[radial_index]) > 0.02
                or abs(metadata[1] - source_grid_mlt) > 0.02):
            misordered_shells.add(radial_index)
            bad_shells.add(radial_index)
            continue
        # Columns 3 and 4 are the field-line-mapped equatorial crossing radius
        # and MLT. Column 2 is the uniform source-grid MLT; using it here would
        # incorrectly force the distorted model solution into circular rings.
        if _rbe_equatorial_coordinate(metadata) is None:
            out_of_band.append((metadata[3], metadata[2]))
            bad_shells.add(radial_index)

    # ---- the aggregate backstop, over the cells that were genuinely bad -----
    #
    # Measured on the cells that actually failed a check, NOT on the cells that
    # shell-quantisation then removes alongside them. Sean's threshold means
    # "how much of this frame is wrong", and amplifying it by a factor of
    # mlt_count would silently turn a 2% tolerance into a 0.04% one.
    bad_cells = len(out_of_band) + sum(
        1 for index in range(total_blocks) if divmod(index, mlt_count)[0] in misordered_shells
    )
    if total_blocks and bad_cells / total_blocks > RBE_MAX_OUTLIER_FRACTION:
        worst = max((radius for _, radius in out_of_band), default=float("nan"))
        raise RuntimeError(
            f"RBE_MAX_OUTLIER_FRACTION exceeded: {bad_cells} of {total_blocks} cells failed a "
            f"plausibility or ordering check, worst radius {worst:.2f} R_E"
        )

    kept_shells = [index for index in range(radial_count) if index not in bad_shells]
    if not kept_shells:
        raise RuntimeError("every NOAA RBE radial shell failed a plausibility or ordering check")
    if bad_shells:
        reasons = []
        if out_of_band:
            worst = max(radius for _, radius in out_of_band)
            reasons.append(f"{len(out_of_band)} cells outside the plausibility band, "
                           f"worst {worst:.2f} R_E")
        if misordered_shells:
            reasons.append(f"{len(misordered_shells)} shells misordered")
        print(
            f"NOTE: dropped {len(bad_shells)} of {radial_count} RBE radial shells "
            f"({'; '.join(reasons)}); publishing the remaining {len(kept_shells)} shells "
            f"as a {len(kept_shells)}x{mlt_count} grid",
            flush=True,
        )

    # ---- pass 2: emit the kept shells, in radial-major / MLT-minor order ----
    native_channel_values: dict[int, list[float]] = {index: [] for index in chosen_indices}
    pitch_resolved_values: dict[int, list[float]] = {index: [] for index in chosen_indices}
    equatorial_radii: list[float] = []
    equatorial_magnetic_local_times: list[float] = []
    for radial_index in kept_shells:
        for mlt_index in range(mlt_count):
            block_index = radial_index * mlt_count + mlt_index
            metadata = block_metadata[block_index]
            distribution = block_distributions[block_index]
            coordinate = _rbe_equatorial_coordinate(metadata)
            if coordinate is None:  # pragma: no cover - kept shells are all in band
                raise RuntimeError("internal error: a kept RBE shell holds an out-of-band cell")
            equatorial_radius, equatorial_mlt = coordinate
            equatorial_magnetic_local_times.append(equatorial_mlt)
            equatorial_radii.append(equatorial_radius)
            for energy_index in chosen_indices:
                pitch_values = distribution[energy_index * pitch_count : (energy_index + 1) * pitch_count]
                if len(pitch_values) != pitch_count:
                    raise RuntimeError("NOAA RBE pitch-angle channel is truncated")
                pitch_resolved_values[energy_index].extend(pitch_values)
                native_channel_values[energy_index].append(pitch_values[-1])

    coordinate_values: array[int] = array("H")
    for equatorial_radius, magnetic_local_time in zip(equatorial_radii, equatorial_magnetic_local_times):
        coordinate_values.append(round(equatorial_radius * 1000))
        coordinate_values.append(round(magnetic_local_time * 1000))
    published_radial_count = len(kept_shells)
    # The invariant the renderer enforces, enforced here too, so a frame that
    # would throw in someone's browser can never leave this machine.
    if published_radial_count * mlt_count != len(equatorial_radii):
        raise RuntimeError(
            f"internal error: RBE gridShape {published_radial_count}x{mlt_count} does not "
            f"describe {len(equatorial_radii)} published points"
        )
    point_indices = list(range(len(equatorial_radii)))
    pitch_value_indices = list(range(len(equatorial_radii) * pitch_count))
    return {
        "coordinatesU16": _little_endian_base64(coordinate_values),
        "electronFlux": {
            str(round(energies[index], 3)): _quantized(native_channel_values[index], point_indices, RADIATION_ENCODING)
            for index in chosen_indices
        },
        "pitchResolvedElectronFlux": {
            str(round(energies[index], 3)): _quantized(
                pitch_resolved_values[index], pitch_value_indices, RADIATION_ENCODING
            )
            for index in chosen_indices
        },
        "energiesKev": [round(energies[index], 3) for index in chosen_indices],
        "pitchCoordinatesSin": [round(value, 5) for value in pitch_grid],
        "pitchAnglesDegrees": [round(math.degrees(math.asin(value)), 3) for value in pitch_grid],
        "pitchCoordinate": round(pitch_grid[-1], 5),
        "nativePitchIndex": pitch_count - 1,
        "innerBoundaryRe": round(header[0], 5),
        "count": len(equatorial_radii),
        # The shape of what was PUBLISHED, not the shape declared in the NOAA
        # header. Those differ whenever a shell was dropped, and publishing the
        # header's shape over a shorter point list is what would throw in the
        # browser.
        "gridShape": {"radialCount": published_radial_count,
                      "magneticLocalTimeCount": mlt_count},
    }


def _uniform_axis(values: list[float], count: int, label: str) -> tuple[float, float]:
    """Start and step of an axis that is actually uniform, or a refusal.

    Returned rather than assumed. A grid whose spacing is not what the file's
    own header implies cannot be drawn as an equirectangular texture at all --
    every cell would land at the wrong longitude, which is precisely the class
    of error that once shipped the whole globe a quarter-turn out.
    """
    if len(values) != count or count < 2:
        raise RuntimeError(f"NOAA mag_grid {label} axis has {len(values)} values, not {count}")
    step = values[1] - values[0]
    if not step > 0:
        raise RuntimeError(f"NOAA mag_grid {label} axis does not increase")
    for index, value in enumerate(values):
        if abs(value - (values[0] + index * step)) > 1e-6:
            raise RuntimeError(f"NOAA mag_grid {label} axis is not uniformly spaced at index {index}")
    return values[0], step


def _parse_mag_grid(body: bytes) -> dict[str, Any]:
    """Parse one NOAA ``mag_grid`` file into axes and 15 named columns.

    Everything the renderer will later rely on is checked here, on this machine,
    where a failure is a skipped frame rather than a wrong picture: the header
    sentence, the column names in order, the declared cell count against the
    rows actually present, and every row's own longitude/latitude against the
    position the ordering claims it occupies.
    """
    text = body.decode("ascii", errors="replace")
    lines = [line for line in text.splitlines() if line.strip()]
    if len(lines) < 5:
        raise RuntimeError(f"truncated NOAA mag_grid file: {len(lines)} lines")
    if lines[0].strip() != MAG_GRID_HEADER:
        raise RuntimeError(f"unexpected NOAA mag_grid header: {lines[0].strip()!r}")
    shape = [int(value) for value in lines[2].split()]
    if len(shape) != 2:
        raise RuntimeError(f"unexpected NOAA mag_grid shape line: {lines[2].strip()!r}")
    longitude_count, latitude_count = shape
    if (longitude_count, latitude_count) != MAG_GRID_EXPECTED_SHAPE:
        raise RuntimeError(
            f"NOAA mag_grid shape changed: {longitude_count}x{latitude_count} "
            f"is not {MAG_GRID_EXPECTED_SHAPE[0]}x{MAG_GRID_EXPECTED_SHAPE[1]}"
        )
    names = tuple(lines[3].split())
    if names != MAG_GRID_COLUMNS:
        raise RuntimeError(f"unexpected NOAA mag_grid columns: {names}")

    cell_count = longitude_count * latitude_count
    rows = lines[4:]
    if len(rows) != cell_count:
        raise RuntimeError(
            f"NOAA mag_grid declares {longitude_count}x{latitude_count} = {cell_count} cells "
            f"but carries {len(rows)} data rows"
        )
    columns: dict[str, array[float]] = {name: array("f") for name in MAG_GRID_COLUMNS[2:]}
    longitudes: list[float] = []
    latitudes: list[float] = []
    for index, row in enumerate(rows):
        values = [float(item) for item in row.split()]
        if len(values) != len(MAG_GRID_COLUMNS):
            raise RuntimeError(f"NOAA mag_grid row {index} has {len(values)} values, not {len(MAG_GRID_COLUMNS)}")
        if index < longitude_count:
            longitudes.append(values[0])
        if index % longitude_count == 0:
            latitudes.append(values[1])
        # Longitude cycles fastest, latitude south to north. Assumed nowhere;
        # every row is checked against the position the ordering gives it.
        if abs(values[0] - longitudes[index % longitude_count]) > 1e-6:
            raise RuntimeError(f"NOAA mag_grid row {index} longitude leaves the declared ordering")
        if abs(values[1] - latitudes[index // longitude_count]) > 1e-6:
            raise RuntimeError(f"NOAA mag_grid row {index} latitude leaves the declared ordering")
        for name, value in zip(MAG_GRID_COLUMNS[2:], values[2:]):
            columns[name].append(value)

    longitude_start, longitude_step = _uniform_axis(longitudes, longitude_count, "longitude")
    latitude_start, latitude_step = _uniform_axis(latitudes, latitude_count, "latitude")
    if abs(longitude_count * longitude_step - 360.0) > 1e-6:
        raise RuntimeError("NOAA mag_grid longitude axis does not close the globe exactly once")
    return {
        "longitudeCount": longitude_count,
        "latitudeCount": latitude_count,
        "longitudeStartDeg": longitude_start,
        "longitudeStepDeg": longitude_step,
        "latitudeStartDeg": latitude_start,
        "latitudeStepDeg": latitude_step,
        "columns": columns,
    }


def _ground_column(parsed: dict[str, Any], suffix: str, stem: str) -> array[float]:
    return parsed["columns"][f"{stem}{suffix}"]


def _encode_ground_frame(parsed: dict[str, Any]) -> dict[str, Any]:
    """Quantize every current system and component, and measure the frame.

    The extrema are computed from the SOURCE floats before quantization, so the
    number the legend prints is the model's own value and not a decode of a
    rounded one.
    """
    indices = list(range(parsed["longitudeCount"] * parsed["latitudeCount"]))
    fields: dict[str, dict[str, str]] = {}
    masks: dict[str, dict[str, str]] = {}
    for system, suffix in GROUND_CURRENT_SYSTEMS:
        fields[system] = {}
        masks[system] = {}
        for component, stem in GROUND_COMPONENTS:
            values = _ground_column(parsed, suffix, stem)
            encoded, mask = _quantized_with_mask(values, indices, GROUND_FIELD_ENCODING)
            fields[system][component] = encoded
            masks[system][component] = mask

    north = _ground_column(parsed, "", "dBn")
    east = _ground_column(parsed, "", "dBe")
    down = _ground_column(parsed, "", "dBd")
    strongest_index = -1
    strongest_horizontal = -1.0
    unusable = 0
    for index in indices:
        if not (math.isfinite(north[index]) and math.isfinite(east[index]) and math.isfinite(down[index])):
            unusable += 1
            continue
        horizontal = math.hypot(north[index], east[index])
        if horizontal > strongest_horizontal:
            strongest_horizontal = horizontal
            strongest_index = index
    if strongest_index < 0:
        raise RuntimeError("NOAA mag_grid frame carries no finite total perturbation")
    longitude_count = parsed["longitudeCount"]
    return {
        "fieldsU16": fields,
        "fieldMasksU8": masks,
        "extrema": {
            "maximumHorizontalNt": round(strongest_horizontal, 3),
            "maximumHorizontalLatitudeDeg": round(
                parsed["latitudeStartDeg"] + (strongest_index // longitude_count) * parsed["latitudeStepDeg"], 3
            ),
            "maximumHorizontalLongitudeDeg": round(
                parsed["longitudeStartDeg"] + (strongest_index % longitude_count) * parsed["longitudeStepDeg"], 3
            ),
            "maximumVerticalNt": round(max(abs(value) for value in down if math.isfinite(value)), 3),
            "unusableCellCount": unusable,
        },
    }


def reduce_local_frame(
    *,
    valid_at: dt.datetime,
    run_at: dt.datetime,
    plane_bodies: dict[str, bytes],
    radiation_body: bytes,
) -> dict[str, Any]:
    """Reduce already-downloaded NOAA files into one complete geospace frame.

    This is the same reduction `build_geospace_bundle` performs, exposed for
    callers that already hold the source bytes - notably the offline backfill in
    `pipeline/geospace_history.py`, which replays the disposable NOMADS download
    cache on bigmem. It performs no network access whatsoever.
    """
    planes: dict[str, Any] = {}
    frame_planes: dict[str, Any] = {}
    frame_structures: dict[str, Any] = {}
    for public_name, body in plane_bodies.items():
        parsed = _parse_plane(body)
        indices = _plane_indices(parsed)
        planes[public_name] = {
            "count": len(indices),
            "coordinatesI16": _encode_coordinates(parsed["x"], parsed["cross"], indices),
            "boundsRe": list(PLANE_BOUNDS_RE),
        }
        frame_planes[public_name] = _encode_plane(parsed, indices)
        frame_structures[public_name] = _derive_plane_structures(parsed, public_name)
    radiation = _parse_radiation(radiation_body)
    frame = {
        "validAt": _iso(valid_at),
        "leadMinutes": round((_utc(valid_at) - _utc(run_at)).total_seconds() / 60),
        "runAt": _iso(run_at),
        "planes": frame_planes,
        "structures": frame_structures,
        "radiationBelt": {
            "coordinatesU16": radiation["coordinatesU16"],
            "electronFluxU16": radiation["electronFlux"],
            "pitchResolvedElectronFluxU16": radiation["pitchResolvedElectronFlux"],
        },
    }
    return {"frame": frame, "planes": planes, "radiation": radiation}


def build_geospace_bundle(now: dt.datetime | None = None) -> dict[str, Any]:
    """The coupled geospace bundle alone, for callers that want only it."""
    return build_geospace_and_ground_bundles(now)[0]


def build_geospace_and_ground_bundles(
    now: dt.datetime | None = None,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Build the geospace bundle and the ground-perturbation bundle together.

    They are built in one pass because they come from one directory listing and
    one selected sequence of valid times. Discovering the ground field
    separately would re-download NOAA's ~790 KB index of a day's 6,247 files on
    every publish cycle for nothing.

    The ground bundle is the second return value and may be ``None``. It is
    never allowed to take the geospace bundle down with it: a mag_grid file that
    is missing, short or malformed costs its own frame and is recorded as a gap,
    and if that leaves no frames at all the ground layer is simply absent from
    the release. The cut planes, the belts and the structures are untouched.
    """
    now = _utc(now or dt.datetime.now(dt.timezone.utc))
    gm_files, radiation_files = _discover_files(now)
    selected_times = _select_times(now, gm_files, radiation_files)
    plane_coordinates: dict[str, dict[str, Any]] = {}
    coordinate_fingerprints: dict[str, bytes] = {}
    frames: list[dict[str, Any]] = []
    first_radiation: dict[str, Any] | None = None
    ground_frames: list[dict[str, Any]] = []
    ground_gaps: list[dict[str, Any]] = []
    ground_grid: dict[str, Any] | None = None

    for valid_time in selected_times:
        frame_planes: dict[str, Any] = {}
        frame_structures: dict[str, Any] = {}
        cycles: list[str] = []
        for upstream_name, public_name in (("z0", "equatorial"), ("y0", "meridional")):
            cycle, url = gm_files[valid_time][upstream_name]
            cycles.append(cycle)
            parsed = _parse_plane(_cached_file(url, 1_000_000))
            indices = _plane_indices(parsed)
            coordinate_bytes = bytes(array("f", parsed["x"])) + bytes(array("f", parsed["cross"]))
            if public_name not in coordinate_fingerprints:
                coordinate_fingerprints[public_name] = coordinate_bytes
                plane_coordinates[public_name] = {
                    "count": len(indices),
                    "coordinatesI16": _encode_coordinates(parsed["x"], parsed["cross"], indices),
                    "boundsRe": list(PLANE_BOUNDS_RE),
                }
            elif coordinate_fingerprints[public_name] != coordinate_bytes:
                raise RuntimeError("NOAA SWMF adaptive grid changed within the selected sequence")
            frame_planes[public_name] = _encode_plane(parsed, indices)
            frame_structures[public_name] = _derive_plane_structures(parsed, public_name)

        radiation = _parse_radiation(_cached_file(radiation_files[valid_time], 3_000_000))
        # The bundle publishes ONE radiationBelt.count and ONE gridShape, taken
        # from the first frame, while every frame carries its own coordinate and
        # flux arrays. Those must therefore all be the same length. They always
        # were when the grid was fixed at the NOAA header's 51x48; now that a
        # frame can drop a bad radial shell, two frames in one sequence could
        # disagree, and the browser would validate the shorter arrays against the
        # first frame's shape and throw. This is the same invariant the plane grid
        # already enforces twenty lines above, and it is enforced the same way.
        if first_radiation is None:
            first_radiation = radiation
        elif (radiation["gridShape"] != first_radiation["gridShape"]
              or radiation["count"] != first_radiation["count"]):
            raise RuntimeError(
                "NOAA SWMF RBE grid changed within the selected sequence: "
                f"{radiation['gridShape']} with {radiation['count']} points against "
                f"{first_radiation['gridShape']} with {first_radiation['count']}"
            )
        run_time = _parse_timestamp(max(cycles) + "00")

        ground_source = gm_files[valid_time].get("mag_grid")
        if ground_source is None:
            ground_gaps.append({"validAt": _iso(valid_time), "reason": "no-mag-grid-file-published"})
        else:
            try:
                ground_parsed = _parse_mag_grid(_cached_file(ground_source[1], MAG_GRID_MINIMUM_BYTES))
                grid = {key: value for key, value in ground_parsed.items() if key != "columns"}
                if ground_grid is None:
                    ground_grid = grid
                elif ground_grid != grid:
                    raise RuntimeError("NOAA mag_grid geometry changed within the selected sequence")
                encoded_ground = _encode_ground_frame(ground_parsed)
            except (RuntimeError, ValueError, OSError, urllib.error.URLError) as error:
                # One unusable ground frame is a hole in one layer, printed and
                # published as a hole. It is not a reason to withhold the cut
                # planes, the belts or the other ground frames.
                print(f"WARNING: NOAA mag_grid frame {_iso(valid_time)} is unusable: {error}")
                ground_gaps.append({"validAt": _iso(valid_time), "reason": f"unusable-source-file: {error}"})
            else:
                ground_frames.append(
                    {
                        "validAt": _iso(valid_time),
                        "runAt": _iso(_parse_timestamp(ground_source[0] + "00")),
                        "leadMinutes": round(
                            (valid_time - _parse_timestamp(ground_source[0] + "00")).total_seconds() / 60
                        ),
                        **encoded_ground,
                    }
                )

        frames.append(
            {
                "validAt": _iso(valid_time),
                "leadMinutes": round((valid_time - run_time).total_seconds() / 60),
                "runAt": _iso(run_time),
                "planes": frame_planes,
                "structures": frame_structures,
                "radiationBelt": {
                    "coordinatesU16": radiation["coordinatesU16"],
                    "electronFluxU16": radiation["electronFlux"],
                    "pitchResolvedElectronFluxU16": radiation["pitchResolvedElectronFlux"],
                },
            }
        )

    # Reused from the loop above rather than parsed a second time. Re-parsing the
    # first frame here cost a full RBE parse on every publish and, once the
    # reducer started reporting dropped shells, printed that report twice.
    if first_radiation is None:
        raise RuntimeError("NOAA SWMF sequence produced no radiation frames")
    ground_bundle = _ground_field_bundle(
        now=now,
        selected_times=selected_times,
        grid=ground_grid,
        frames=ground_frames,
        gaps=ground_gaps,
    )
    geospace_bundle = {
        "schema": 1,
        "generatedAt": _iso(now),
        "status": "model",
        "model": "NOAA operational Geospace SWMF: BATS-R-US + RIM + RCM + RBE",
        "coordinateSystem": "GSM for MHD planes; magnetic local time/L shell for RBE",
        "source": {
            "name": "NOAA/NCEP NOMADS operational SWMF output",
            "url": f"{NOMADS_ROOT}/",
            "cadence": "one-minute upstream output reduced to a 20-minute browser sequence",
        },
        "planes": plane_coordinates,
        "fieldEncodings": FIELD_ENCODINGS,
        "fieldMaskEncoding": {
            "storage": "uint8 base64, one bit field per adaptive-grid value",
            "flags": {
                "missing": FIELD_MASK_MISSING,
                "clippedLow": FIELD_MASK_CLIPPED_LOW,
                "clippedHigh": FIELD_MASK_CLIPPED_HIGH,
            },
            "meaning": "Missing and range-clipped source values remain distinguishable from valid encoded endpoints.",
        },
        "displayModes": {
            "default": "smooth",
            "smooth": "gap-aware local interpolation clamped to contributing source values; cannot introduce new extrema",
            "native": "unresampled NOAA adaptive-grid samples",
        },
        "structures": {
            "status": "model-derived-proxies",
            "coordinateSystem": "GSM",
            "anglesDegrees": list(STRUCTURE_ANGLES_DEGREES),
            "radiusEncoding": {
                "storage": "little-endian uint16 base64",
                "scaleRe": 1 / STRUCTURE_RADIUS_SCALE,
                "missingValue": STRUCTURE_MISSING_U16,
            },
            "streamlineEncoding": {
                "storage": "little-endian int16 coordinate pairs plus uint16 offsets, base64",
                "scaleRe": 1 / STREAMLINE_COORDINATE_SCALE,
                "flowSpeedStorage": "little-endian uint16 base64 aligned one-to-one with projected flow points",
                "flowSpeedScaleKps": 1 / STREAMLINE_SPEED_SCALE,
            },
            "bowShock": {
                "representation": "raywise transition profiles on y=0 and z=0 cuts; browser loft is constrained to those two sections",
                "sourceVariables": ["Rho", "Ux", "Uy", "Uz", "P"],
                "derivation": "outermost simultaneous density >=1.3x and thermal pressure >=5x upstream with speed <=0.96x upstream; strongest local log-change within the outer transition",
                "meaning": "model-derived bow-shock proxy, not a directly published discontinuity or full 3-D isosurface",
            },
            "magnetopause": {
                "representation": "raywise current-layer profiles on y=0 and z=0 cuts; browser loft may contain unsupported gaps",
                "sourceVariables": ["Rho", "Bx", "By", "Bz", "jx", "jy", "jz"],
                "derivation": "strongest current-density ridge between 0.5 bow-shock radius and 2 RE inside the shock, retained only with an inward density drop",
                "meaning": "model-derived magnetopause current-layer proxy; the region between it and the bow-shock proxy is a magnetosheath cue",
            },
            "projectedMagneticStreamlines": {
                "sourceVariables": ["Bx", "By", "Bz"],
                "meaning": "instantaneous in-plane magnetic-vector projections, not traced 3-D field lines or magnetic connectivity",
            },
            "projectedFlowStreamlines": {
                "sourceVariables": ["Ux", "Uy", "Uz"],
                "meaning": "instantaneous in-plane bulk-flow projections with source-vector speed at every point; model-time advection follows slowing and deflection but is not a Lagrangian time integration",
            },
            "notExtracted": {
                "cusps": "The meridional current-layer proxy may show an indentation, but two cuts cannot establish a 3-D cusp surface or reconnection topology, so no cusp is classified.",
                "ringCurrent": "The published cuts contain bulk MHD variables, and the RBE file contains energetic electrons on L/MLT coordinates; neither is a species-resolved ring-current distribution.",
                "volumetricTopology": "Two orthogonal adaptive-grid cuts cannot recover dawn-dusk structure away from those planes or true 3-D field-line connectivity.",
            },
        },
        "radiationBelt": {
            "count": first_radiation["count"],
            "gridShape": first_radiation["gridShape"],
            "energiesKev": first_radiation["energiesKev"],
            "pitchCoordinate": first_radiation["pitchCoordinate"],
            "pitchCoordinatesSin": first_radiation["pitchCoordinatesSin"],
            "pitchAnglesDegrees": first_radiation["pitchAnglesDegrees"],
            "pitchResolvedOrdering": "equatorial-point-major, pitch-index-minor",
            "innerBoundaryRe": first_radiation["innerBoundaryRe"],
            "coordinates": {
                "storage": "little-endian uint16 radius/MLT pairs, base64",
                "radiusScaleRe": 0.001,
                "magneticLocalTimeScaleHours": 0.001,
                "meaning": "field-line-mapped equatorial crossing radius and magnetic local time from RBE block columns 3 and 4",
                "orientation": "MLT 0 midnight, 6 dawn, 12 noon (+X GSM), and 18 dusk (+Y GSM)",
            },
            "views": {
                "nativeEquatorial": {
                    "status": "model",
                    "label": "MODEL-NATIVE EQUATORIAL FLUX",
                    "pitchIndex": first_radiation["nativePitchIndex"],
                    "meaning": "RBE equatorial differential electron flux at the highest published equatorial pitch channel",
                },
                "dipoleMapped3d": {
                    "status": "model-derived-mapping",
                    "label": "DIPOLE-MAPPED MODEL VISUALIZATION",
                    "fieldLine": "r = L cos^2(lambda)",
                    "mirrorCondition": "sin^2(alpha_local) / B_local = sin^2(alpha_equatorial) / B_equatorial",
                    "meaning": "browser mapping of RBE equatorial pitch-resolved samples along ideal dipole lines, not native 3-D RBE or BATS-R-US output",
                },
            },
            "encoding": RADIATION_ENCODING,
        },
        "frames": frames,
        "caveat": "Physics-model output, not a direct volumetric measurement. Boundary lofts and streamlines are explicitly model-derived two-cut proxies, not recovered 3-D fields. RBE is model-native only at its equatorial coordinates; any off-equator belt is explicitly ideal-dipole mapped. Plane distance is compressed in the globe; colors are consistently quantized across time.",
    }
    return geospace_bundle, ground_bundle


def _ground_field_bundle(
    *,
    now: dt.datetime,
    selected_times: list[dt.datetime],
    grid: dict[str, Any] | None,
    frames: list[dict[str, Any]],
    gaps: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Assemble the published ground-perturbation bundle, or nothing at all.

    Deliberately carries no ``generatedAt``. The artifact is content-addressed by
    ``pipeline/build_release.write_artifact``, so a wall-clock stamp inside the
    body would mint a new file on every five-minute publish cycle and rsync a
    fresh half-megabyte to the VPS for a bundle whose frames had not changed.
    The time this was built belongs in the manifest record, which is small and
    changes every cycle anyway.
    """
    if grid is None or not frames:
        return None
    return {
        "schema": 1,
        "product": "swmf-ground-magnetic-perturbation",
        "status": "model",
        # Site evidence vocabulary, docs/SCIENTIFIC-LAYERS.md. Every frame here
        # is valid AFTER the run that produced it, so it is guidance, not a
        # nowcast, and each frame carries its own leadMinutes to prove it.
        "evidence": "Model (physics simulation), published as forecast guidance",
        "model": "NOAA operational Geospace SWMF: BATS-R-US + RIM ground magnetometer grid",
        "coordinateSystem": "geographic (GEO) latitude/longitude, Earth-fixed",
        "quantity": {
            "name": "ground magnetic perturbation",
            "units": "nT",
            "components": "north, east, down (the header's North-East-Down convention)",
            "meaning": "the deviation from the background field that the model's current systems would produce at the Earth's surface -- the quantity a ground magnetometer records, and the quantity whose rate of change drives geomagnetically induced currents",
        },
        "grid": {
            **grid,
            "cellCount": grid["longitudeCount"] * grid["latitudeCount"],
            "ordering": "longitude cycles fastest; latitude runs south to north",
            "polarCaps": "The source grid stops at the last row it publishes. Beyond it there is no value, and none is extrapolated -- the caps are drawn as absent, not as quiet.",
        },
        "currentSystems": [
            {
                "key": "total",
                "label": "Total",
                "meaning": "The full modeled ground perturbation. It is the exact sum of the four attributions below.",
            },
            {
                "key": "magnetospheric",
                "sourceColumn": "Mhd",
                "label": "Magnetospheric currents (lumped)",
                "meaning": "Everything the MHD magnetosphere carries: the ring current, the cross-tail current sheet and the magnetopause (Chapman-Ferraro) currents TOGETHER. The model does not separate them here, so this is not a ring-current signature and must not be read as one.",
            },
            {
                "key": "fieldAligned",
                "sourceColumn": "Fac",
                "label": "Field-aligned (Birkeland) currents",
                "meaning": "The current sheets running along field lines between the magnetosphere and the ionosphere.",
            },
            {
                "key": "hall",
                "sourceColumn": "Hal",
                "label": "Hall currents (auroral electrojets)",
                "meaning": "The ionospheric Hall closure of the Birkeland currents. At auroral latitudes this is the electrojet.",
            },
            {
                "key": "pedersen",
                "sourceColumn": "Ped",
                "label": "Pedersen currents",
                "meaning": "The ionospheric Pedersen closure of the Birkeland currents, flowing along the electric field.",
            },
        ],
        "attribution": "The four per-source fields are the MODEL'S OWN attribution of its own ground signature. No instrument separates a measured perturbation into current systems; nothing here is an observation of which current did what.",
        "fieldEncoding": GROUND_FIELD_ENCODING,
        "fieldMaskEncoding": {
            "storage": "uint8 base64, one byte per grid cell per component",
            "flags": {
                "missing": FIELD_MASK_MISSING,
                "clippedLow": FIELD_MASK_CLIPPED_LOW,
                "clippedHigh": FIELD_MASK_CLIPPED_HIGH,
            },
            "meaning": "A cell that is missing or outside the encoded range stays distinguishable from a cell that is genuinely near zero.",
        },
        "source": {
            "name": "NOAA/NCEP NOMADS operational SWMF output, GM/IO2 mag_grid",
            "url": f"{NOMADS_ROOT}/",
            "cadence": "one-minute upstream output; only the frames this bundle publishes are ever downloaded",
        },
        "time": {
            "requestedFrom": _iso(min(selected_times)),
            "requestedTo": _iso(max(selected_times)),
            "coverageComplete": not gaps,
            "noDataIntervals": gaps,
            "selectedFrameCount": len(selected_times),
        },
        "history": {
            "archived": False,
            "meaning": "Only the live NOAA window is published. There is no bigmem archive of this field yet, so a selected UTC outside the window reads NO DATA rather than being served a held frame.",
        },
        "displayModes": {
            "default": "smooth",
            "smooth": "bilinear display of the published cells; cannot introduce a new extremum",
            "native": "the unresampled 5-degree source cells",
        },
        "frames": frames,
        "caveat": "Physics-simulation output on a geographic grid, not a magnetometer measurement and not an assimilation of one. Frames are valid after the run that produced them. The per-current-system split is the model's own attribution; 'magnetospheric' lumps the ring current, cross-tail sheet and magnetopause currents together and is not any one of them. A frame the run did not publish is shown as a gap and never as a quiet zero.",
    }
