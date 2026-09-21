"""Reduce NOAA's operational WAM-IPE plasma forecast for the browser.

NCEP NOMADS publishes two complementary operational IPE products: exact HmF2
and NmF2 fields every five minutes, and a full 3-D ion-density grid every ten
minutes.  bigmem-PC preserves the five-minute peak motion, samples the much
larger 3-D profiles, derives electron density by quasi-neutrality, and extracts
only profile-supported E/F1 peaks.  Nothing in this reducer invents fixed
ionospheric layers; the full-field lower boundary is 90 km, so most of the
D region is explicitly outside the WAM-IPE artifact.
"""

from __future__ import annotations

import base64
import datetime as dt
import html
import os
import re
import tempfile
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Iterable

try:
    import numpy as np
    from netCDF4 import Dataset
except ImportError as error:  # pragma: no cover - exercised on an unprovisioned host
    np = None  # type: ignore[assignment]
    Dataset = None  # type: ignore[assignment,misc]
    NETCDF_IMPORT_ERROR: ImportError | None = error
else:
    NETCDF_IMPORT_ERROR = None


def _require_netcdf() -> None:
    if NETCDF_IMPORT_ERROR is None:
        return
    raise RuntimeError(
        "WAM-IPE reduction requires python3-netcdf4 and python3-numpy "
        "(sudo apt-get install python3-netcdf4)"
    ) from NETCDF_IMPORT_ERROR


NOMADS_WFS_ROOT = "https://nomads.ncep.noaa.gov/pub/data/nccf/com/wfs/prod"
USER_AGENT = "SpaceEnvironmentExplorer/0.3 educational-project contact=sean.theinformed.org"
DEFAULT_CACHE = Path("/mnt/d/space-explorer/wam-ipe-cache")
FALLBACK_CACHE = Path(__file__).resolve().parent / ".cache" / "wam-ipe"

SOURCE_CADENCE_MINUTES = 10
PEAK_SOURCE_CADENCE_MINUTES = 5
PUBLISHED_CADENCE_MINUTES = 240
PEAK_PUBLISHED_CADENCE_MINUTES = 5
REQUESTED_HISTORY_HOURS = 48
WAM_CACHE_RETENTION_HOURS = REQUESTED_HISTORY_HOURS + 12
LONGITUDE_STRIDE = 2
LATITUDE_STRIDE = 2
# Retain fine vertical sampling through the F region, then every other source
# level through the operational file's 2,655 km top.  These are indices, not
# invented layer boundaries.
ALTITUDE_INDICES = tuple(range(0, 40, 2)) + tuple(range(40, 58, 2)) + (57,)
ION_DENSITY_VARIABLES = (
    "O_plus_density",
    "H_plus_density",
    "He_plus_density",
    "N_plus_density",
    "NO_plus_density",
    "O2_plus_density",
    "N2_plus_density",
)
DENSITY_ENCODING = {
    "quantity": "electron number density derived by quasi-neutral sum of published positive-ion densities",
    "units": "m⁻³",
    "scale": "log10",
    "minimum": 7.0,
    "maximum": 12.6,
    "storage": "uint8",
}
ION_COMPOSITION_ENCODING = {
    "species": [name.removesuffix("_density").replace("_plus", "+") for name in ION_DENSITY_VARIABLES],
    "quantity": "positive-ion fraction of the quasi-neutral electron-density sum",
    "units": "fraction",
    "storage": "packed-uint4",
    "maximumCode": 15,
    "packing": "species pairs in low then high nibble; final high nibble unused",
}

WFS_DAY = re.compile(r"wfs\.(\d{8})/?")
CYCLE = re.compile(r"(00|06|12|18)/?")
IPE10_FILE = re.compile(r"wfs\.t(\d{2})z\.ipe10\.(\d{8}_\d{6})\.nc")
IPE05_FILE = re.compile(r"wfs\.t(\d{2})z\.ipe05\.(\d{8}_\d{6})\.nc")

REGION_SURFACE_DEFINITIONS = {
    "e": {
        "label": "E-region profile peak",
        "searchAltitudeKm": [90, 170],
        "criterion": "largest interior local maximum with at least 0.02 dex two-sided prominence",
    },
    "f1": {
        "label": "distinct F1 profile peak where supported",
        "searchAltitudeKm": [160, 230],
        "criterion": (
            "largest interior local maximum below and distinct from the same profile's F-region maximum, with at least "
            "0.02 dex two-sided prominence; absent otherwise"
        ),
    },
}
SURFACE_ALTITUDE_ENCODING = {
    "quantity": "geometric altitude of the selected column peak",
    "units": "km",
    "scaleKm": 0.1,
    "storage": "uint16-le",
}


def _utc(value: dt.datetime) -> dt.datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=dt.timezone.utc)
    return value.astimezone(dt.timezone.utc)


def _iso(value: dt.datetime) -> str:
    return _utc(value).isoformat(timespec="seconds").replace("+00:00", "Z")


def _parse_compact_time(value: str) -> dt.datetime:
    return dt.datetime.strptime(value, "%Y%m%d_%H%M%S").replace(tzinfo=dt.timezone.utc)


def _cache_root() -> Path:
    configured = os.environ.get("SPACE_EXPLORER_WAM_IPE_CACHE")
    if configured:
        return Path(configured)
    return DEFAULT_CACHE if DEFAULT_CACHE.parent.is_dir() else FALLBACK_CACHE


def _request_bytes(url: str, timeout: int = 120) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read()
    # The largest single downloads on this stack -- model files of 20 MB and up,
    # several per cycle. Counted at the socket, not at _cached_file, which
    # returns bytes that never crossed the network.
    try:
        from ops import bandwidth  # noqa: PLC0415 - optional, never load-bearing

        bandwidth.record_fetch(len(body), family="noaa-nomads-wam-ipe",
                               source="urllib response.read() length (decoded)",
                               run="wam-ipe")
    except Exception:  # noqa: BLE001 - measurement must never break a fetch
        pass
    if not body:
        raise RuntimeError(f"empty NOAA WAM-IPE response: {url}")
    return body


def _listing(url: str) -> list[str]:
    page = _request_bytes(url, timeout=60).decode("utf-8", errors="replace")
    return [html.unescape(item) for item in re.findall(r'href="([^"?#]+)', page)]


def _cache_destination(url: str) -> Path:
    parsed = urllib.parse.urlsplit(url)
    parts = [part for part in parsed.path.split("/") if part]
    day = next((part for part in parts if WFS_DAY.fullmatch(part)), "wfs.unknown")
    cycle_index = parts.index(day) + 1 if day in parts else -1
    cycle = parts[cycle_index] if 0 <= cycle_index < len(parts) and CYCLE.fullmatch(parts[cycle_index]) else "unknown"
    return _cache_root() / day / cycle / Path(parsed.path).name


def _cached_file(url: str, minimum_size: int = 20_000_000) -> Path:
    destination = _cache_destination(url)
    if destination.is_file() and destination.stat().st_size >= minimum_size:
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    body = _request_bytes(url)
    if len(body) < minimum_size:
        raise RuntimeError(f"implausibly small NOAA WAM-IPE file ({len(body)} bytes): {url}")
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
    return destination


def _candidate_cycles() -> Iterable[tuple[dt.datetime, str]]:
    days: list[tuple[str, str]] = []
    for item in _listing(f"{NOMADS_WFS_ROOT}/"):
        match = WFS_DAY.fullmatch(item)
        if match:
            days.append((match.group(1), urllib.parse.urljoin(f"{NOMADS_WFS_ROOT}/", item)))
    for day_text, day_url in sorted(days, reverse=True)[:3]:
        for item in sorted(_listing(day_url), reverse=True):
            match = CYCLE.fullmatch(item)
            if not match:
                continue
            run = dt.datetime.strptime(day_text + match.group(1), "%Y%m%d%H").replace(tzinfo=dt.timezone.utc)
            yield run, urllib.parse.urljoin(day_url, item)


def _cached_cycles() -> Iterable[tuple[dt.datetime, str]]:
    """Expose retained raw frames through their canonical NOMADS URLs.

    `_cached_file` resolves those URLs back to these paths without a transfer.
    This lets scheduled builds keep a true rolling history after NOMADS removes
    an older cycle from its short public directory listing.
    """

    root = _cache_root()
    if not root.is_dir():
        return
    for directory in root.glob("wfs.????????/??"):
        day_match = WFS_DAY.fullmatch(directory.parent.name)
        cycle_match = CYCLE.fullmatch(directory.name)
        if not day_match or not cycle_match:
            continue
        run_at = dt.datetime.strptime(day_match.group(1) + cycle_match.group(1), "%Y%m%d%H").replace(
            tzinfo=dt.timezone.utc
        )
        cycle_url = f"{NOMADS_WFS_ROOT}/{directory.parent.name}/{directory.name}/"
        yield run_at, cycle_url


def _cycle_files(
    cycle_url: str,
    *,
    pattern: re.Pattern[str] = IPE10_FILE,
    minimum_size: int = 20_000_000,
    allow_listing_failure: bool = False,
) -> dict[dt.datetime, str]:
    files: dict[dt.datetime, str] = {}
    try:
        listing = _listing(cycle_url)
    except Exception:
        if not allow_listing_failure:
            raise
        listing = []
    for item in listing:
        match = pattern.fullmatch(item)
        if not match:
            continue
        valid = _parse_compact_time(match.group(2))
        files[valid] = urllib.parse.urljoin(cycle_url, item)
    parsed = urllib.parse.urlsplit(cycle_url)
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) >= 2 and WFS_DAY.fullmatch(parts[-2]) and CYCLE.fullmatch(parts[-1]):
        cached_directory = _cache_root() / parts[-2] / parts[-1]
        for path in cached_directory.glob("*.nc") if cached_directory.is_dir() else ():
            match = pattern.fullmatch(path.name)
            if match and path.stat().st_size >= minimum_size:
                files[_parse_compact_time(match.group(2))] = urllib.parse.urljoin(cycle_url, path.name)
    return files


def _nearest_cycle_frame(
    wanted: dt.datetime,
    cycles: list[tuple[dt.datetime, dict[dt.datetime, str]]],
    *,
    prefer_latest_run: bool,
    source_cadence_minutes: int = SOURCE_CADENCE_MINUTES,
) -> tuple[dt.datetime, dt.datetime, str] | None:
    tolerance = dt.timedelta(minutes=source_cadence_minutes)
    candidates: list[tuple[dt.datetime, dt.datetime, str]] = []
    for run_at, files in cycles:
        if not files:
            continue
        valid_at = min(files, key=lambda item: abs((item - wanted).total_seconds()))
        if abs(valid_at - wanted) <= tolerance:
            candidates.append((valid_at, run_at, files[valid_at]))
    if not candidates:
        return None
    if prefer_latest_run:
        return max(candidates, key=lambda item: (item[1], -abs((item[0] - wanted).total_seconds())))
    nonnegative_leads = [item for item in candidates if item[1] <= item[0]]
    eligible = nonnegative_leads or candidates
    return max(eligible, key=lambda item: (item[1], -abs((item[0] - wanted).total_seconds())))


def _select_frame_urls(
    now: dt.datetime,
    cycles: list[tuple[dt.datetime, dict[dt.datetime, str]]],
    *,
    source_cadence_minutes: int = SOURCE_CADENCE_MINUTES,
    published_cadence_minutes: int = PUBLISHED_CADENCE_MINUTES,
    product_label: str = "ipe10 full-field",
) -> tuple[list[tuple[dt.datetime, dt.datetime, str]], dict[str, Any]]:
    cycles = [(run_at, files) for run_at, files in cycles if files]
    if not cycles:
        raise RuntimeError(f"NOAA WAM-IPE has no available {product_label} cycles")
    now = _utc(now)
    anchor = now.replace(
        minute=(now.minute // source_cadence_minutes) * source_cadence_minutes,
        second=0,
        microsecond=0,
    )
    latest_run_at, latest_files = max(cycles, key=lambda item: item[0])
    official_forecast_end = max(latest_files)
    cadence = dt.timedelta(minutes=published_cadence_minutes)
    # ANCHOR THE TARGET GRID ABSOLUTELY, NOT ON `now`.
    #
    # This used to start the grid at `anchor - REQUESTED_HISTORY_HOURS`, and
    # `anchor` follows the clock. The publish job runs every five minutes, so
    # the whole grid slid forward on each run, every target resolved to a
    # DIFFERENT nearest source frame, and `_cached_file` never got a hit it
    # could keep. The union over a day was every frame the source publishes.
    #
    # Measured on the live cache, 2026-09-08, before this change: 1,052 ipe10
    # frames held, 22.34 GB, and 995 of 1,048 consecutive pairs were exactly
    # SOURCE_CADENCE_MINUTES apart -- i.e. we were downloading all of it and
    # shipping one frame in twenty-four. A 24x overfetch, and it was the largest
    # single writer to the spinning disk on this machine.
    #
    # Snapping to a fixed grid (multiples of the published cadence since the
    # epoch) makes successive runs ask for the SAME instants, so the second run
    # is a cache hit instead of a fresh 21.7 MB download per frame.
    epoch = dt.datetime(1970, 1, 1, tzinfo=dt.timezone.utc)
    raw_start = anchor - dt.timedelta(hours=REQUESTED_HISTORY_HOURS)
    steps = int((raw_start - epoch).total_seconds() // cadence.total_seconds())
    requested_start = epoch + steps * cadence
    targets: list[dt.datetime] = []
    target = requested_start
    while target <= official_forecast_end:
        targets.append(target)
        target += cadence
    if not targets or targets[-1] != official_forecast_end:
        targets.append(official_forecast_end)

    selected: list[tuple[dt.datetime, dt.datetime, str]] = []
    for wanted in targets:
        item = _nearest_cycle_frame(
            wanted,
            cycles,
            prefer_latest_run=wanted >= anchor,
            source_cadence_minutes=source_cadence_minutes,
        )
        if item is not None and (not selected or item[0] != selected[-1][0]):
            selected.append(item)
    if not selected:
        raise RuntimeError("NOAA WAM-IPE cycles do not cover the requested model sequence")
    history_boundary_candidates = [
        (valid_at, run_at, url)
        for run_at, cycle_files in cycles
        for valid_at, url in cycle_files.items()
        if valid_at <= anchor
    ]
    if history_boundary_candidates:
        boundary = min(
            history_boundary_candidates,
            key=lambda item: (abs((item[0] - requested_start).total_seconds()), -item[1].timestamp()),
        )
        if boundary[0] < selected[0][0]:
            selected.append(boundary)
    if not any(item[0] == official_forecast_end for item in selected):
        selected.append((official_forecast_end, latest_run_at, latest_files[official_forecast_end]))
    selected = sorted({item[0]: item for item in selected}.values(), key=lambda item: item[0])
    actual_history_hours = max(0.0, (anchor - selected[0][0]).total_seconds() / 3600)
    forecast_hours = max(0.0, (selected[-1][0] - anchor).total_seconds() / 3600)
    if forecast_hours < 24:
        raise RuntimeError(f"NOAA WAM-IPE forecast sequence is incomplete: only {forecast_hours:.1f} hours")
    return selected, {
        "requestedHistoryHours": REQUESTED_HISTORY_HOURS,
        "actualHistoryHours": round(actual_history_hours, 3),
        "forecastHours": round(forecast_hours, 3),
        "validFrom": _iso(selected[0][0]),
        "validTo": _iso(selected[-1][0]),
        "latestRunAt": _iso(latest_run_at),
        "sourceCadenceMinutes": source_cadence_minutes,
        "publishedCadenceMinutes": published_cadence_minutes,
        "sourceRetentionLimited": actual_history_hours + (source_cadence_minutes / 60) < REQUESTED_HISTORY_HOURS,
    }


def _discover_wam_ipe_products(
    now: dt.datetime,
) -> tuple[
    dt.datetime,
    list[tuple[dt.datetime, dt.datetime, str]],
    dict[str, Any],
    list[tuple[dt.datetime, dt.datetime, str]],
    dict[str, Any],
]:
    now = _utc(now)
    errors: list[str] = []
    cycle_urls: dict[dt.datetime, tuple[str, bool]] = {
        run_at: (url, True) for run_at, url in _cached_cycles() if run_at <= now + dt.timedelta(hours=1)
    }
    try:
        for run_at, cycle_url in _candidate_cycles():
            if run_at <= now + dt.timedelta(hours=1):
                cycle_urls[run_at] = (cycle_url, False)
    except Exception as error:
        errors.append(f"cycle listing: {error}")
    full_cycles: list[tuple[dt.datetime, dict[dt.datetime, str]]] = []
    peak_cycles: list[tuple[dt.datetime, dict[dt.datetime, str]]] = []
    for run_at, (cycle_url, cached_only) in sorted(cycle_urls.items()):
        try:
            full_files = _cycle_files(cycle_url, allow_listing_failure=cached_only)
            peak_files = _cycle_files(
                cycle_url,
                pattern=IPE05_FILE,
                minimum_size=50_000,
                allow_listing_failure=cached_only,
            )
        except Exception as error:
            errors.append(f"{_iso(run_at)}: {error}")
            continue
        if full_files:
            full_cycles.append((run_at, full_files))
        if peak_files:
            peak_cycles.append((run_at, peak_files))
    if full_cycles and peak_cycles:
        try:
            full_selected, full_coverage = _select_frame_urls(now, full_cycles)
            peak_selected, peak_coverage = _select_frame_urls(
                now,
                peak_cycles,
                source_cadence_minutes=PEAK_SOURCE_CADENCE_MINUTES,
                published_cadence_minutes=PEAK_PUBLISHED_CADENCE_MINUTES,
                product_label="ipe05 HmF2/NmF2",
            )
            # The two products can appear a few minutes apart at cycle start.
            # The compatibility runAt belongs to the 3-D sequence; the peak
            # reducer validates its own selected ipe05 run independently.
            latest_run_at = max(full_cycles, key=lambda item: item[0])[0]
            return latest_run_at, full_selected, full_coverage, peak_selected, peak_coverage
        except Exception as error:
            errors.append(str(error))
    detail = "; ".join(errors[-4:]) or "no forecast cycles were listed"
    raise RuntimeError(f"no paired NOAA WAM-IPE profile and peak sequence covers history and forecast: {detail}")


def discover_wam_ipe_sequence(
    now: dt.datetime,
) -> tuple[dt.datetime, list[tuple[dt.datetime, dt.datetime, str]], dict[str, Any]]:
    """Compatibility wrapper exposing the reduced 3-D sequence."""

    latest_run_at, selected, coverage, _peak_selected, _peak_coverage = _discover_wam_ipe_products(now)
    return latest_run_at, selected, coverage


def _coordinates(dataset: Dataset) -> tuple[np.ndarray[Any, Any], np.ndarray[Any, Any], np.ndarray[Any, Any]]:
    required_dimensions = {"x01": 90, "x02": 91, "x03": 58}
    actual_dimensions = {name: len(dataset.dimensions[name]) for name in required_dimensions if name in dataset.dimensions}
    if actual_dimensions != required_dimensions:
        raise RuntimeError(f"unexpected NOAA WAM-IPE dimensions: {actual_dimensions}")
    longitude = np.asarray(dataset.variables["lon"][:], dtype=np.float64)
    latitude = np.asarray(dataset.variables["lat"][:], dtype=np.float64)
    altitude = np.asarray(dataset.variables["alt"][:], dtype=np.float64)
    if not (
        longitude.shape == (90,)
        and latitude.shape == (91,)
        and altitude.shape == (58,)
        and np.all(np.diff(longitude) > 0)
        and np.all(np.diff(latitude) > 0)
        and np.all(np.diff(altitude) > 0)
        and abs(float(longitude[0])) < 0.01
        and abs(float(longitude[-1]) - 356) < 0.01
        and abs(float(latitude[0]) + 90) < 0.01
        and abs(float(latitude[-1]) - 90) < 0.01
        and abs(float(altitude[0]) - 90) < 0.01
    ):
        raise RuntimeError("unexpected NOAA WAM-IPE coordinate grid")
    return longitude, latitude, altitude


def _plasma_fields(
    dataset: Dataset,
) -> tuple[np.ndarray[Any, Any], np.ndarray[Any, Any], np.ndarray[Any, Any]]:
    density = np.zeros((58, 91, 90), dtype=np.float64)
    valid = np.ones(density.shape, dtype=np.bool_)
    ion_density = np.zeros((len(ION_DENSITY_VARIABLES), *density.shape), dtype=np.float32)
    for species_index, name in enumerate(ION_DENSITY_VARIABLES):
        variable = dataset.variables.get(name)
        if variable is None or variable.dimensions != ("x03", "x02", "x01"):
            raise RuntimeError(f"missing or malformed NOAA WAM-IPE ion field: {name}")
        raw = variable[:]
        values = np.asarray(np.ma.filled(raw, np.nan), dtype=np.float64)
        field_valid = ~np.ma.getmaskarray(raw) & np.isfinite(values) & (values >= 0)
        if values.shape != density.shape:
            raise RuntimeError(f"invalid NOAA WAM-IPE ion density shape: {name}")
        valid &= field_valid
        density += np.where(field_valid, values, 0)
        ion_density[species_index] = np.where(field_valid, values, 0).astype(np.float32)
    finite_density = density[valid]
    valid_fraction = float(np.count_nonzero(valid) / valid.size)
    if finite_density.size == 0 or valid_fraction < 0.5:
        raise RuntimeError(f"insufficient valid NOAA WAM-IPE electron-density coverage: {valid_fraction:.3f}")
    maximum_density = float(np.max(finite_density))
    if maximum_density < 1e10 or maximum_density > 1e14:
        raise RuntimeError(f"implausible NOAA WAM-IPE electron-density range: {maximum_density}")
    return density, valid, ion_density


def _encoded_density(density: np.ndarray[Any, Any], valid: np.ndarray[Any, Any]) -> tuple[str, str]:
    sampled = density[np.ix_(ALTITUDE_INDICES, range(0, 91, LATITUDE_STRIDE), range(0, 90, LONGITUDE_STRIDE))]
    sampled_valid = valid[np.ix_(ALTITUDE_INDICES, range(0, 91, LATITUDE_STRIDE), range(0, 90, LONGITUDE_STRIDE))]
    minimum = float(DENSITY_ENCODING["minimum"])
    maximum = float(DENSITY_ENCODING["maximum"])
    logarithmic = np.log10(np.maximum(sampled, 10**minimum))
    normalized = np.clip((logarithmic - minimum) / (maximum - minimum), 0, 1)
    encoded = np.rint(normalized * 255).astype(np.uint8)
    encoded[~sampled_valid] = 0
    validity = np.packbits(sampled_valid.reshape(-1), bitorder="little")
    return (
        base64.b64encode(encoded.tobytes(order="C")).decode("ascii"),
        base64.b64encode(validity.tobytes()).decode("ascii"),
    )


def _encoded_composition(
    ion_density: np.ndarray[Any, Any],
    electron_density: np.ndarray[Any, Any],
    valid: np.ndarray[Any, Any],
) -> str:
    selection = np.ix_(ALTITUDE_INDICES, range(0, 91, LATITUDE_STRIDE), range(0, 90, LONGITUDE_STRIDE))
    total = electron_density[selection]
    sampled_valid = valid[selection]
    codes = np.zeros((len(ION_DENSITY_VARIABLES), *total.shape), dtype=np.uint8)
    for species_index in range(len(ION_DENSITY_VARIABLES)):
        sampled = ion_density[species_index][selection]
        fraction = np.divide(sampled, total, out=np.zeros_like(sampled, dtype=np.float64), where=total > 0)
        codes[species_index] = np.rint(np.clip(fraction, 0, 1) * 15).astype(np.uint8)
    packed = np.zeros((*total.shape, (len(ION_DENSITY_VARIABLES) + 1) // 2), dtype=np.uint8)
    for species_index in range(len(ION_DENSITY_VARIABLES)):
        byte_index = species_index // 2
        shift = 4 * (species_index % 2)
        packed[..., byte_index] |= codes[species_index] << shift
    packed[~sampled_valid] = 0
    return base64.b64encode(packed.tobytes(order="C")).decode("ascii")


def _density_codes(values: np.ndarray[Any, Any], valid: np.ndarray[Any, Any]) -> np.ndarray[Any, Any]:
    minimum = float(DENSITY_ENCODING["minimum"])
    maximum = float(DENSITY_ENCODING["maximum"])
    logarithmic = np.log10(np.maximum(values, 10**minimum))
    encoded = np.rint(np.clip((logarithmic - minimum) / (maximum - minimum), 0, 1) * 255).astype(np.uint8)
    encoded[~valid] = 0
    return encoded


def _encode_surface(
    altitude_km: np.ndarray[Any, Any],
    density_m3: np.ndarray[Any, Any],
    valid: np.ndarray[Any, Any],
) -> dict[str, Any]:
    selection = np.ix_(range(0, 91, LATITUDE_STRIDE), range(0, 90, LONGITUDE_STRIDE))
    sampled_altitude = altitude_km[selection]
    sampled_density = density_m3[selection]
    sampled_valid = valid[selection]
    altitude_code = np.rint(np.maximum(sampled_altitude, 0) / SURFACE_ALTITUDE_ENCODING["scaleKm"]).astype("<u2")
    altitude_code[~sampled_valid] = 0
    density_code = _density_codes(sampled_density, sampled_valid)
    validity = np.packbits(sampled_valid.reshape(-1), bitorder="little")
    return {
        "altitudeU16": base64.b64encode(altitude_code.tobytes(order="C")).decode("ascii"),
        "densityU8": base64.b64encode(density_code.tobytes(order="C")).decode("ascii"),
        "validityBits": base64.b64encode(validity.tobytes()).decode("ascii"),
        "validColumnCount": int(np.count_nonzero(sampled_valid)),
    }


def _local_profile_peak(
    profile: np.ndarray[Any, Any],
    altitude: np.ndarray[Any, Any],
    candidate_indices: np.ndarray[Any, Any],
    *,
    minimum_log_prominence: float,
    maximum_altitude_km: float | None = None,
) -> int | None:
    candidates: list[tuple[float, int]] = []
    logarithmic = np.log10(np.maximum(profile, 1))
    for position in range(1, len(candidate_indices) - 1):
        index = int(candidate_indices[position])
        if maximum_altitude_km is not None and float(altitude[index]) >= maximum_altitude_km:
            continue
        previous_index = int(candidate_indices[position - 1])
        next_index = int(candidate_indices[position + 1])
        value = float(logarithmic[index])
        if value < float(logarithmic[previous_index]) or value < float(logarithmic[next_index]):
            continue
        if value == float(logarithmic[previous_index]) == float(logarithmic[next_index]):
            continue
        left_minimum = float(np.min(logarithmic[candidate_indices[:position]]))
        right_minimum = float(np.min(logarithmic[candidate_indices[position + 1 :]]))
        prominence = value - max(left_minimum, right_minimum)
        if prominence >= minimum_log_prominence:
            candidates.append((float(profile[index]), index))
    return max(candidates)[1] if candidates else None


def _profile_region_surfaces(
    density: np.ndarray[Any, Any],
    valid: np.ndarray[Any, Any],
    altitude: np.ndarray[Any, Any],
) -> dict[str, dict[str, Any]]:
    """Extract conservative E/F1 column peaks from the actual 3-D profiles.

    A region is absent in a column unless the profile has a distinct interior
    maximum.  This intentionally leaves holes at night or wherever WAM-IPE
    does not support a separate layer; selecting a fixed nominal altitude
    would fabricate structure.
    """

    e_indices = np.flatnonzero((altitude >= 90) & (altitude <= 170))
    f1_indices = np.flatnonzero((altitude >= 160) & (altitude <= 230))
    f_indices = np.flatnonzero((altitude >= 160) & (altitude <= 1000))
    outputs = {
        name: {
            "altitude": np.zeros((91, 90), dtype=np.float64),
            "density": np.zeros((91, 90), dtype=np.float64),
            "valid": np.zeros((91, 90), dtype=np.bool_),
        }
        for name in ("e", "f1")
    }

    for latitude_index in range(91):
        for longitude_index in range(90):
            profile = density[:, latitude_index, longitude_index]
            column_valid = valid[:, latitude_index, longitude_index]
            if np.all(column_valid[e_indices]):
                peak = _local_profile_peak(
                    profile,
                    altitude,
                    e_indices,
                    minimum_log_prominence=0.02,
                )
                if peak is not None:
                    outputs["e"]["altitude"][latitude_index, longitude_index] = altitude[peak]
                    outputs["e"]["density"][latitude_index, longitude_index] = profile[peak]
                    outputs["e"]["valid"][latitude_index, longitude_index] = True

            if not (np.all(column_valid[f_indices]) and np.all(column_valid[f1_indices])):
                continue
            f_peak_position = int(np.argmax(profile[f_indices]))
            if f_peak_position in (0, len(f_indices) - 1):
                continue
            f2_index = int(f_indices[f_peak_position])
            f1_peak = _local_profile_peak(
                profile,
                altitude,
                f1_indices,
                minimum_log_prominence=0.02,
                maximum_altitude_km=float(altitude[f2_index]) - 10,
            )
            if f1_peak is not None and profile[f1_peak] < profile[f2_index]:
                outputs["f1"]["altitude"][latitude_index, longitude_index] = altitude[f1_peak]
                outputs["f1"]["density"][latitude_index, longitude_index] = profile[f1_peak]
                outputs["f1"]["valid"][latitude_index, longitude_index] = True

    return {
        name: _encode_surface(output["altitude"], output["density"], output["valid"])
        for name, output in outputs.items()
    }


def _reduce_peak_file(
    listed_valid_at: dt.datetime,
    listed_run_at: dt.datetime,
    path: Path,
) -> dict[str, Any]:
    with Dataset(path, "r") as dataset:
        if str(getattr(dataset, "run_type", "")) != "wfs" or str(getattr(dataset, "model", "")) != "ipe":
            raise RuntimeError(f"not an operational WFS/IPE file: {path}")
        try:
            file_run_at = _parse_compact_time(str(dataset.init_date))
            file_valid_at = _parse_compact_time(str(dataset.fcst_date))
        except (AttributeError, ValueError) as error:
            raise RuntimeError(f"missing NOAA WAM-IPE peak metadata: {path}") from error
        if file_valid_at != _utc(listed_valid_at) or file_run_at != _utc(listed_run_at):
            raise RuntimeError(f"NOAA WAM-IPE ipe05 filename/directory metadata mismatch: {path}")
        required_dimensions = {"x01": 90, "x02": 91}
        actual_dimensions = {name: len(dataset.dimensions[name]) for name in required_dimensions if name in dataset.dimensions}
        if actual_dimensions != required_dimensions:
            raise RuntimeError(f"unexpected NOAA WAM-IPE ipe05 dimensions: {actual_dimensions}")
        longitude = np.asarray(dataset.variables["lon"][:], dtype=np.float64)
        latitude = np.asarray(dataset.variables["lat"][:], dtype=np.float64)
        hm_raw = dataset.variables.get("HmF2")
        nm_raw = dataset.variables.get("NmF2")
        if hm_raw is None or nm_raw is None or hm_raw.dimensions != ("x02", "x01") or nm_raw.dimensions != ("x02", "x01"):
            raise RuntimeError(f"missing or malformed NOAA WAM-IPE HmF2/NmF2 fields: {path}")
        hm = np.asarray(np.ma.filled(hm_raw[:], np.nan), dtype=np.float64)
        nm = np.asarray(np.ma.filled(nm_raw[:], np.nan), dtype=np.float64)
        valid = (
            ~np.ma.getmaskarray(hm_raw[:])
            & ~np.ma.getmaskarray(nm_raw[:])
            & np.isfinite(hm)
            & np.isfinite(nm)
            & (hm >= 100)
            & (hm <= 1000)
            & (nm >= 1e8)
            & (nm <= 1e14)
        )
        if longitude.shape != (90,) or latitude.shape != (91,) or np.count_nonzero(valid) < valid.size * 0.5:
            raise RuntimeError(f"invalid NOAA WAM-IPE HmF2/NmF2 coverage: {path}")
        encoded = _encode_surface(hm, nm, valid)
        return {
            "validAt": _iso(file_valid_at),
            "runAt": _iso(file_run_at),
            "leadMinutes": round((file_valid_at - file_run_at).total_seconds() / 60),
            **encoded,
        }


def reduce_wam_ipe_files(
    files: list[tuple[dt.datetime, dt.datetime, Path]],
    *,
    generated_at: dt.datetime,
    expected_latest_run_at: dt.datetime | None = None,
    coverage: dict[str, Any] | None = None,
    source_url: str = NOMADS_WFS_ROOT,
) -> dict[str, Any]:
    _require_netcdf()
    if not files:
        raise RuntimeError("no NOAA WAM-IPE files selected")
    generated_at = _utc(generated_at)
    frames: list[dict[str, Any]] = []
    reference_coordinates: tuple[np.ndarray[Any, Any], np.ndarray[Any, Any], np.ndarray[Any, Any]] | None = None
    run_times: set[dt.datetime] = set()

    for listed_valid_at, listed_run_at, path in sorted(files):
        with Dataset(path, "r") as dataset:
            if str(getattr(dataset, "run_type", "")) != "wfs" or str(getattr(dataset, "model", "")) != "ipe":
                raise RuntimeError(f"not an operational WFS/IPE file: {path}")
            try:
                file_run_at = _parse_compact_time(str(dataset.init_date))
                file_valid_at = _parse_compact_time(str(dataset.fcst_date))
            except (AttributeError, ValueError) as error:
                raise RuntimeError(f"missing NOAA WAM-IPE forecast metadata: {path}") from error
            if file_valid_at != _utc(listed_valid_at):
                raise RuntimeError(f"NOAA WAM-IPE filename/metadata valid-time mismatch: {path}")
            if file_run_at != _utc(listed_run_at):
                raise RuntimeError(f"NOAA WAM-IPE directory/file run-time mismatch: {path}")
            run_times.add(file_run_at)
            coordinates = _coordinates(dataset)
            if reference_coordinates is None:
                reference_coordinates = tuple(item.copy() for item in coordinates)
            elif any(not np.array_equal(current, reference) for current, reference in zip(coordinates, reference_coordinates)):
                raise RuntimeError("NOAA WAM-IPE grid changed within the selected sequence")
            electron_density, valid, ion_density = _plasma_fields(dataset)
            density_u8, validity_bits = _encoded_density(electron_density, valid)
            composition_u4 = _encoded_composition(ion_density, electron_density, valid)
            region_surfaces = _profile_region_surfaces(electron_density, valid, coordinates[2])
            frames.append(
                {
                    "validAt": _iso(file_valid_at),
                    "runAt": _iso(file_run_at),
                    "leadMinutes": round((file_valid_at - file_run_at).total_seconds() / 60),
                    "phase": "history" if file_valid_at < generated_at else "forecast",
                    "densityU8": density_u8,
                    "validityBits": validity_bits,
                    "compositionU4": composition_u4,
                    "regionSurfaces": region_surfaces,
                }
            )

    assert run_times and reference_coordinates is not None
    latest_run_at = max(run_times)
    if expected_latest_run_at is not None and latest_run_at != _utc(expected_latest_run_at):
        raise RuntimeError(
            f"NOAA WAM-IPE latest run-time mismatch: {_iso(expected_latest_run_at)} vs {_iso(latest_run_at)}"
        )
    longitude, latitude, altitude = reference_coordinates
    longitudes = longitude[::LONGITUDE_STRIDE]
    latitudes = latitude[::LATITUDE_STRIDE]
    altitudes = altitude[list(ALTITUDE_INDICES)]
    point_count = len(longitudes) * len(latitudes) * len(altitudes)
    expected_bytes = point_count
    for frame in frames:
        if len(base64.b64decode(frame["densityU8"], validate=True)) != expected_bytes:
            raise RuntimeError("NOAA WAM-IPE encoded frame length mismatch")
        if len(base64.b64decode(frame["validityBits"], validate=True)) != (expected_bytes + 7) // 8:
            raise RuntimeError("NOAA WAM-IPE validity-mask length mismatch")
        if len(base64.b64decode(frame["compositionU4"], validate=True)) != expected_bytes * 4:
            raise RuntimeError("NOAA WAM-IPE composition frame length mismatch")
        surface_point_count = len(longitudes) * len(latitudes)
        for surface in frame["regionSurfaces"].values():
            if len(base64.b64decode(surface["altitudeU16"], validate=True)) != surface_point_count * 2:
                raise RuntimeError("NOAA WAM-IPE region-surface altitude length mismatch")
            if len(base64.b64decode(surface["densityU8"], validate=True)) != surface_point_count:
                raise RuntimeError("NOAA WAM-IPE region-surface density length mismatch")
            if len(base64.b64decode(surface["validityBits"], validate=True)) != (surface_point_count + 7) // 8:
                raise RuntimeError("NOAA WAM-IPE region-surface validity length mismatch")

    sequence_coverage = coverage or {
        "requestedHistoryHours": REQUESTED_HISTORY_HOURS,
        "actualHistoryHours": round(max(0, (generated_at - _utc(files[0][0])).total_seconds() / 3600), 3),
        "forecastHours": round(max(0, (_utc(files[-1][0]) - generated_at).total_seconds() / 3600), 3),
        "validFrom": frames[0]["validAt"],
        "validTo": frames[-1]["validAt"],
        "latestRunAt": _iso(latest_run_at),
        "sourceRetentionLimited": False,
    }

    return {
        "schema": 1,
        "generatedAt": _iso(generated_at),
        "status": "forecast",
        "model": "NOAA operational WAM-IPE Forecast System (WFS)",
        "runAt": _iso(latest_run_at),
        "coverage": sequence_coverage,
        "source": {
            "name": "NOAA/NCEP NOMADS operational WAM-IPE full-field IPE output",
            "url": source_url,
            "sourceCadenceMinutes": SOURCE_CADENCE_MINUTES,
            "publishedCadenceMinutes": PUBLISHED_CADENCE_MINUTES,
        },
        "grid": {
            "coordinateSystem": "geographic longitude, latitude, and geometric altitude",
            "ordering": "altitude-latitude-longitude",
            "longitudesDeg": [round(float(value), 3) for value in longitudes],
            "latitudesDeg": [round(float(value), 3) for value in latitudes],
            "altitudesKm": [round(float(value), 3) for value in altitudes],
            "pointCount": point_count,
            "sourceShape": [58, 91, 90],
            "sampling": {
                "longitudeStride": LONGITUDE_STRIDE,
                "latitudeStride": LATITUDE_STRIDE,
                "altitudeSourceIndices": list(ALTITUDE_INDICES),
            },
        },
        "electronDensity": DENSITY_ENCODING,
        "ionComposition": ION_COMPOSITION_ENCODING,
        "representation": {
            "recommendedDefault": "smooth",
            "native": "Native reduced horizontal mesh of data-derived peak surfaces; no vertical pillars.",
            "smooth": (
                "Continuous horizontal peak-surface geometry. HmF2 controls F2 radius, NmF2 controls color, "
                "and a missing contributing source corner leaves a hole rather than filling the layer."
            ),
        },
        "profileRegionSurfaces": {
            "source": "derived independently in each actual ipe10 3-D electron-density column",
            "definitions": REGION_SURFACE_DEFINITIONS,
            "altitudeEncoding": SURFACE_ALTITUDE_ENCODING,
            "densityEncoding": DENSITY_ENCODING,
            "missingRule": "no supported interior profile peak means no surface vertex",
            "dRegion": {
                "available": False,
                "reason": "The operational ipe10 full-field grid begins at 90 km; most of the D region is not present.",
            },
        },
        "frames": frames,
        "caveat": (
            "Operational physics-model forecast, not an electron-density observation or assimilation. "
            "Electron density is derived by quasi-neutral summation of the seven published singly charged "
            "positive-ion densities; packed composition values are quantized fractions of that same sum. "
            "The published full-field grid begins at 90 km, so it omits most of the "
            "D region and provides no negative-ion field, and it ends at 2,655 km despite IPE's higher "
            "internal model domain. Horizontal and vertical samples are reduced on bigmem-PC; globe altitude "
            "is visually compressed while reported kilometers and density values retain source units."
        ),
    }


def reduce_wam_ipe_peak_files(
    files: list[tuple[dt.datetime, dt.datetime, Path]],
    *,
    generated_at: dt.datetime,
    expected_latest_run_at: dt.datetime | None = None,
    coverage: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Reduce exact five-minute NOAA HmF2/NmF2 files to moving surface frames."""

    _require_netcdf()
    if not files:
        raise RuntimeError("no NOAA WAM-IPE ipe05 peak files selected")
    generated_at = _utc(generated_at)
    frames = []
    for valid_at, run_at, path in sorted(files):
        frame = _reduce_peak_file(valid_at, run_at, path)
        frame["phase"] = "history" if _utc(valid_at) < generated_at else "forecast"
        frames.append(frame)
    latest_run_at = max(_utc(run_at) for _valid_at, run_at, _path in files)
    if expected_latest_run_at is not None and latest_run_at != _utc(expected_latest_run_at):
        raise RuntimeError(
            f"NOAA WAM-IPE peak latest run-time mismatch: {_iso(expected_latest_run_at)} vs {_iso(latest_run_at)}"
        )
    point_count = (91 // LATITUDE_STRIDE + 1) * (90 // LONGITUDE_STRIDE)
    for frame in frames:
        if len(base64.b64decode(frame["altitudeU16"], validate=True)) != point_count * 2:
            raise RuntimeError("NOAA WAM-IPE HmF2 encoded length mismatch")
        if len(base64.b64decode(frame["densityU8"], validate=True)) != point_count:
            raise RuntimeError("NOAA WAM-IPE NmF2 encoded length mismatch")
        if len(base64.b64decode(frame["validityBits"], validate=True)) != (point_count + 7) // 8:
            raise RuntimeError("NOAA WAM-IPE peak validity length mismatch")
    return {
        "sourceProduct": "NOAA/NCEP WFS ipe05",
        "sourceVariables": ["HmF2", "NmF2"],
        "sourceCadenceMinutes": PEAK_SOURCE_CADENCE_MINUTES,
        "publishedCadenceMinutes": PEAK_PUBLISHED_CADENCE_MINUTES,
        "coverage": coverage,
        "pointCount": point_count,
        "gridOrdering": "latitude-longitude",
        "altitudeEncoding": SURFACE_ALTITUDE_ENCODING,
        "densityEncoding": DENSITY_ENCODING,
        "temporalDisplay": "linear interpolation between adjacent five-minute model fields",
        "frames": frames,
    }


def _prune_cache(
    keep: set[Path],
    retention_hours: int = WAM_CACHE_RETENTION_HOURS,
    *,
    dry_run: bool = False,
    now: float | None = None,
) -> dict[str, int]:
    """Bound the disposable WAM-IPE source cache.

    The exact files selected for the current browser bundle are protected
    regardless of age.  Unselected files get a twelve-hour margin beyond the
    48-hour history contract so one failed/upstream-stale cycle can reuse a
    nearby frame without retaining four days of five-minute selection churn.
    """
    root = _cache_root()
    if not root.is_dir():
        return {"removedFiles": 0, "removedBytes": 0, "removedDirectories": 0}
    root = root.resolve()
    if (
        root.name != "wam-ipe-cache"
        or root.parent.name != "space-explorer"
        or root.is_symlink()
        or retention_hours < REQUESTED_HISTORY_HOURS
    ):
        raise RuntimeError(f"refusing unsafe WAM-IPE cache root or retention: {root}")

    protected = {path.resolve() for path in keep}
    cutoff = (time.time() if now is None else now) - retention_hours * 3600
    removed_files = 0
    removed_bytes = 0
    for path in root.glob("wfs.????????/??/*.nc"):
        resolved = path.resolve()
        if path.is_symlink() or resolved in protected:
            continue
        stat = path.stat()
        if stat.st_mtime >= cutoff:
            continue
        removed_files += 1
        removed_bytes += stat.st_size
        if not dry_run:
            path.unlink()

    removed_directories = 0
    if not dry_run:
        for directory in sorted(root.glob("wfs.????????/??"), reverse=True):
            if directory.is_dir() and not directory.is_symlink() and not any(directory.iterdir()):
                directory.rmdir()
                removed_directories += 1
        for directory in sorted(root.glob("wfs.????????"), reverse=True):
            if directory.is_dir() and not directory.is_symlink() and not any(directory.iterdir()):
                directory.rmdir()
                removed_directories += 1
    return {
        "removedFiles": removed_files,
        "removedBytes": removed_bytes,
        "removedDirectories": removed_directories,
    }


def build_wam_ipe_bundle(now: dt.datetime | None = None) -> dict[str, Any]:
    now = _utc(now or dt.datetime.now(dt.timezone.utc))
    latest_run_at, selected, coverage, peak_selected, peak_coverage = _discover_wam_ipe_products(now)
    paths: list[Path] = []
    peak_paths: list[Path] = []
    try:
        # Four concurrent transfers keep the first build well inside the scheduled
        # job timeout without requesting more than a small fraction of one cycle.
        with ThreadPoolExecutor(max_workers=4) as pool:
            paths = list(pool.map(lambda item: _cached_file(item[2]), selected))
        with ThreadPoolExecutor(max_workers=8) as pool:
            peak_paths = list(pool.map(lambda item: _cached_file(item[2], minimum_size=50_000), peak_selected))
        selected_files = [(valid_at, run_at, path) for (valid_at, run_at, _), path in zip(selected, paths)]
        bundle = reduce_wam_ipe_files(
            selected_files,
            generated_at=now,
            expected_latest_run_at=latest_run_at,
            coverage=coverage,
            source_url=f"{NOMADS_WFS_ROOT}/",
        )
        peak_files = [
            (valid_at, run_at, path)
            for (valid_at, run_at, _url), path in zip(peak_selected, peak_paths)
        ]
        bundle["peakSurface"] = reduce_wam_ipe_peak_files(
            peak_files,
            generated_at=now,
            expected_latest_run_at=max(run_at for _valid_at, run_at, _path in peak_files),
            coverage=peak_coverage,
        )
        return bundle
    finally:
        # A decode/reduction failure must not disable the cache lifecycle. Files
        # downloaded far enough to reach this point are still protected when
        # they belong to the attempted selection.
        _prune_cache(set(paths) | set(peak_paths))
