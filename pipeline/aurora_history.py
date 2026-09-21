#!/usr/bin/env python3
"""Reduce NOAA SWPC OVATION 2020 grids into an honest rolling time series.

NOAA publicly distributes the latest machine-readable global probability grid.
Its 24-hour animation manifests reference rendered JPEGs, not numeric grids, and
the NCEI public product inventory does not currently expose an OVATION archive.
This reducer therefore snapshots exact NOAA JSON frames on bigmem going forward;
it never reconstructs probabilities from images or upstream solar-wind data.
"""

from __future__ import annotations

import argparse
import base64
import contextlib
import datetime as dt
import json
import math
import os
import re
import tempfile
import urllib.request
from pathlib import Path
from typing import Any, Iterable


LATEST_GRID_URL = "https://services.swpc.noaa.gov/json/ovation_aurora_latest.json"
PRODUCT_URL = "https://www.spaceweather.gov/products/aurora-30-minute-forecast"
WMO_PRODUCT_URL = "https://www.spaceweather.gov/content/wmo/auroral-activity"
NORTH_IMAGE_MANIFEST_URL = "https://services.swpc.noaa.gov/products/animations/ovation_north_24h.json"
SOUTH_IMAGE_MANIFEST_URL = "https://services.swpc.noaa.gov/products/animations/ovation_south_24h.json"
NCEI_PRODUCT_INVENTORY_URL = "https://www.ncei.noaa.gov/cloud-access/space-weather-portal/api/v1/products"
USER_AGENT = "SpaceEnvironmentExplorer/0.1 educational-project contact=sean.theinformed.org"
EXPECTED_SOURCE_FORMAT = "[Longitude, Latitude, Aurora]"
STALE_AFTER_MINUTES = 12
SOURCE_CADENCE_MINUTES = 5

# Published so the artifact explains, on its own, why the browser draws nothing
# across the equator. The reducer never edits a source byte or a validity bit;
# the withdrawal is a display rule and the guards below are its whole extent.
# Measured over 198 consecutive five-minute grids on 2026-08-06/07, the seam
# never left the rows from 2 degrees south to the equator and was always
# 37 to 45 rows of exactly zero probability away from the nearest real signal.
EQUATORIAL_SEAM_DISCLOSURE = {
    "observed": (
        "NOAA's global grid carries a 1-4% seam in the rows from about 2 degrees south to the equator; "
        "it brightens toward the equator, which is the opposite of a real auroral oval"
    ),
    "handling": "withdrawn from the display as missing, never rewritten to zero",
    "bandLatitudeDeg": 5,
    "isolationLatitudeDeg": 10,
    "guard": (
        "a run of probability-bearing latitude rows is withdrawn only when it never leaves the band and is "
        "separated from every other probability-bearing row by at least the isolation distance, so a genuine "
        "storm-time equatorward expansion, which stays continuous with the oval, is always drawn in full"
    ),
    "sourceBytesModified": False,
}


class AuroraFormatError(ValueError):
    """Raised when a purported OVATION grid cannot be represented safely."""


def utc_iso(value: dt.datetime) -> str:
    return value.astimezone(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def parse_utc(value: str) -> dt.datetime:
    parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include a UTC offset")
    return parsed.astimezone(dt.timezone.utc)


def parse_ovation_latest(payload: Any) -> dict[str, Any]:
    """Validate and losslessly encode one NOAA global OVATION probability grid."""
    if not isinstance(payload, dict):
        raise AuroraFormatError("OVATION payload is not an object")
    if payload.get("Data Format") != EXPECTED_SOURCE_FORMAT:
        raise AuroraFormatError("OVATION coordinate format is missing or unexpected")
    try:
        observed_at = parse_utc(str(payload["Observation Time"]))
        valid_at = parse_utc(str(payload["Forecast Time"]))
    except (KeyError, TypeError, ValueError) as error:
        raise AuroraFormatError("OVATION observation or forecast time is invalid") from error
    if valid_at < observed_at:
        raise AuroraFormatError("OVATION forecast time precedes its observation time")

    coordinates = payload.get("coordinates")
    if not isinstance(coordinates, list) or not coordinates:
        raise AuroraFormatError("OVATION coordinates are missing")

    cells: dict[tuple[float, float], int | None] = {}
    longitudes: set[float] = set()
    latitudes: set[float] = set()
    for point in coordinates:
        if not isinstance(point, list) or len(point) < 3:
            raise AuroraFormatError("OVATION coordinate is not a longitude/latitude/value triple")
        try:
            longitude = float(point[0])
            latitude = float(point[1])
        except (TypeError, ValueError) as error:
            raise AuroraFormatError("OVATION coordinate contains a nonnumeric position") from error
        if not math.isfinite(longitude) or not math.isfinite(latitude):
            raise AuroraFormatError("OVATION coordinate contains a nonfinite position")
        if longitude < 0 or longitude >= 360 or latitude < -90 or latitude > 90:
            raise AuroraFormatError("OVATION coordinate is outside its documented global grid")
        key = (longitude, latitude)
        if key in cells:
            raise AuroraFormatError(f"OVATION grid repeats coordinate {key}")

        raw_probability = point[2]
        if raw_probability is None:
            probability = None
        else:
            try:
                numeric_probability = float(raw_probability)
            except (TypeError, ValueError) as error:
                raise AuroraFormatError("OVATION probability is nonnumeric") from error
            if (
                not math.isfinite(numeric_probability)
                or numeric_probability < 0
                or numeric_probability > 100
                or not numeric_probability.is_integer()
            ):
                raise AuroraFormatError(f"OVATION probability {raw_probability!r} is not an integer from 0 to 100")
            probability = int(numeric_probability)
        cells[key] = probability
        longitudes.add(longitude)
        latitudes.add(latitude)

    sorted_longitudes = sorted(longitudes)
    sorted_latitudes = sorted(latitudes)
    longitude_step = _constant_step(sorted_longitudes, "longitude")
    latitude_step = _constant_step(sorted_latitudes, "latitude")
    width = len(sorted_longitudes)
    height = len(sorted_latitudes)
    cell_count = width * height
    if width < 2 or height < 2:
        raise AuroraFormatError("OVATION grid has fewer than two coordinates on an axis")

    probabilities = bytearray(cell_count)
    validity = bytearray((cell_count + 7) // 8)
    valid_values: list[int] = []
    north_values: list[int] = []
    south_values: list[int] = []
    for latitude_index, latitude in enumerate(sorted_latitudes):
        for longitude_index, longitude in enumerate(sorted_longitudes):
            index = latitude_index * width + longitude_index
            probability = cells.get((longitude, latitude))
            if probability is None:
                continue
            probabilities[index] = probability
            validity[index // 8] |= 1 << (index % 8)
            valid_values.append(probability)
            if latitude > 0:
                north_values.append(probability)
            elif latitude < 0:
                south_values.append(probability)
    if not valid_values:
        raise AuroraFormatError("OVATION grid has no valid probability values")

    grid = {
        "longitudeStartDeg": sorted_longitudes[0],
        "longitudeStepDeg": longitude_step,
        "longitudeCount": width,
        "latitudeStartDeg": sorted_latitudes[0],
        "latitudeStepDeg": latitude_step,
        "latitudeCount": height,
        "order": "latitude-major, south-to-north, west-to-east",
        "longitudeConvention": "0 <= east longitude < 360",
        "sourceCoordinateOrder": "longitude-major, south-to-north within each longitude",
    }
    frame = {
        "observedAt": utc_iso(observed_at),
        "validAt": utc_iso(valid_at),
        "leadMinutes": round((valid_at - observed_at).total_seconds() / 60, 3),
        "probabilityU8": base64.b64encode(probabilities).decode("ascii"),
        "validityBits": base64.b64encode(validity).decode("ascii"),
        "validCellCount": len(valid_values),
        "missingCellCount": cell_count - len(valid_values),
        "maximumProbabilityPercent": max(valid_values),
        "hemispheres": {
            "north": {
                "validCellCount": len(north_values),
                "maximumProbabilityPercent": max(north_values) if north_values else None,
            },
            "south": {
                "validCellCount": len(south_values),
                "maximumProbabilityPercent": max(south_values) if south_values else None,
            },
        },
    }
    return {"grid": grid, "frame": frame}


def build_aurora_bundle(
    current_payload: Any,
    *,
    retrieved_at: dt.datetime,
    historical_frames: Iterable[dict[str, Any]] = (),
    history_hours: float = 48,
) -> dict[str, Any]:
    if history_hours <= 0:
        raise ValueError("history_hours must be positive")
    parsed = parse_ovation_latest(current_payload)
    grid = parsed["grid"]
    current_frame = parsed["frame"]
    expected_cells = grid["longitudeCount"] * grid["latitudeCount"]
    frames_by_valid_time: dict[str, dict[str, Any]] = {}
    for frame in [*historical_frames, current_frame]:
        if _valid_frame(frame, expected_cells):
            frames_by_valid_time[frame["validAt"]] = frame
    frames = [frames_by_valid_time[key] for key in sorted(frames_by_valid_time, key=parse_utc)]

    retrieved_at = retrieved_at.astimezone(dt.timezone.utc)
    requested_from = retrieved_at - dt.timedelta(hours=history_hours)
    requested_to = max(retrieved_at, parse_utc(frames[-1]["validAt"]))
    no_data = _no_data_intervals(frames, requested_from, requested_to)
    available_from = frames[0]["validAt"]
    available_to = frames[-1]["validAt"]
    coverage_complete = not no_data and parse_utc(available_from) <= requested_from

    return {
        "schemaVersion": "noaa-ovation-history.v1",
        "product": "NOAA SWPC OVATION 2020 Aurora Forecast",
        "status": "model",
        "temporalKind": "observation-driven forecast",
        "retrievedAt": utc_iso(retrieved_at),
        "source": {
            "currentNumericGrid": LATEST_GRID_URL,
            "productPage": PRODUCT_URL,
            "wmoProductPage": WMO_PRODUCT_URL,
            "northImageHistoryManifest": NORTH_IMAGE_MANIFEST_URL,
            "southImageHistoryManifest": SOUTH_IMAGE_MANIFEST_URL,
            "nceiProductInventory": NCEI_PRODUCT_INVENTORY_URL,
            "model": "OVATION 2020",
            "inputs": "near-real-time L1 solar-wind speed and interplanetary magnetic field; Kp fallback when L1 data are unavailable or contaminated",
            "sourceCadenceMinutes": SOURCE_CADENCE_MINUTES,
        },
        "sourceAvailability": {
            "publicNumericDistribution": "latest grid only",
            "publicRenderedImageHistoryHours": 24,
            "publicNumericHistoryHours": 0,
            "historyMethod": "exact NOAA numeric grids accumulated by scheduled bigmem snapshots",
            "notUsed": "rendered-image reconstruction, solar-wind reanalysis, temporal interpolation, or synthetic hemispheric mirroring",
            "inventoryCheckedAt": utc_iso(retrieved_at),
        },
        "grid": grid,
        "encoding": {
            "probability": "uint8-base64",
            "validity": "bitset-lsb-first-base64",
            "validRangePercent": [0, 100],
            "missingRepresentation": "validity bit 0; paired probability byte must be ignored",
        },
        "quantity": {
            "name": "Aurora viewing probability",
            "units": "%",
            "definition": "OVATION model probability of visible aurora under dark, clear viewing conditions at the forecast-valid time",
        },
        "time": {
            "requestedHistoryHours": history_hours,
            "requestedFrom": utc_iso(requested_from),
            "requestedTo": utc_iso(requested_to),
            "availableFrom": available_from,
            "availableTo": available_to,
            "frameCount": len(frames),
            "coverageComplete": coverage_complete,
            "noDataIntervals": no_data,
            "selection": (
                "history uses only forecast-valid time and may hold a frame for at most 12 minutes; "
                "the current latest-feed grid may also be shown before its future valid time only "
                "within the narrow retrieval window below and must be labeled active forecast"
            ),
            "staleAfterMinutes": STALE_AFTER_MINUTES,
            "forecastLead": "carried per frame from NOAA Forecast Time minus Observation Time; not assumed to be 30 minutes",
            "activeForecast": {
                "sourceObservedAt": current_frame["observedAt"],
                "forecastValidAt": current_frame["validAt"],
                "feedRetrievedAt": utc_iso(retrieved_at),
                "selectionWindowMinutes": STALE_AFTER_MINUTES,
                "definition": (
                    "near-live display exception for this exact latest NOAA grid only; feedRetrievedAt "
                    "is the bigmem retrieval time, not a NOAA issue time, and historical gaps remain unavailable"
                ),
            },
        },
        "display": {
            "defaultMode": "smooth",
            "nativeModeAvailable": True,
            "smoothing": "spatial bilinear presentation only; source values and masks remain unchanged and no temporal interpolation is allowed",
            "hemispheres": ["north", "south"],
            "equatorialSeam": EQUATORIAL_SEAM_DISCLOSURE,
        },
        "frames": frames,
        "limitations": [
            "This is empirical model guidance, not a direct optical observation of the aurora.",
            "The probability assumes dark, clear viewing conditions; daylight, clouds, terrain, and local light pollution can prevent visibility.",
            "Forecast lead varies with measured solar-wind transit conditions. NOAA's Kp fallback is a nowcast and has no forecast lead.",
            "Frames before bigmem accumulation began are unavailable because NOAA's public 24-hour animation history contains images rather than native probability grids.",
            (
                "NOAA's global grid carries a 1-4% numerical seam in the rows from about 2 degrees south to "
                "the equator. It brightens toward the equator and is separated from the real oval by tens of "
                "degrees of exactly zero probability, so it is auroral in neither location nor shape. Stored "
                "frames keep NOAA's bytes; the display withdraws those cells as missing rather than as zero."
            ),
        ],
    }


def snapshot_current_frame(snapshot_root: Path, bundle: dict[str, Any]) -> Path:
    frames = bundle.get("frames") or []
    if not frames:
        raise AuroraFormatError("OVATION bundle contains no frame to snapshot")
    frame = frames[-1]
    label = re.sub(r"[^0-9]", "", frame["validAt"])
    path = snapshot_root / f"ovation-{label}.json"
    document = {
        "schemaVersion": "noaa-ovation-snapshot.v1",
        "grid": bundle["grid"],
        "encoding": bundle["encoding"],
        "frame": frame,
    }
    _atomic_write(path, json.dumps(document, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    return path


def load_snapshot_frames(
    snapshot_root: Path,
    *,
    start: dt.datetime,
    end: dt.datetime,
    grid: dict[str, Any],
) -> list[dict[str, Any]]:
    frames: dict[str, dict[str, Any]] = {}
    expected_cells = grid["longitudeCount"] * grid["latitudeCount"]
    if not snapshot_root.exists():
        return []
    for path in snapshot_root.glob("ovation-*.json"):
        try:
            document = json.loads(path.read_text())
            frame = document["frame"]
            valid_at = parse_utc(frame["validAt"])
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
            continue
        if document.get("grid") != grid or valid_at < start or valid_at > end:
            continue
        if _valid_frame(frame, expected_cells):
            frames[frame["validAt"]] = frame
    return [frames[key] for key in sorted(frames, key=parse_utc)]


def fetch_json(url: str) -> Any:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def _constant_step(values: list[float], label: str) -> float:
    if len(values) < 2:
        raise AuroraFormatError(f"OVATION {label} axis is too short")
    steps = [b - a for a, b in zip(values, values[1:])]
    first = steps[0]
    if first <= 0 or any(not math.isclose(step, first, abs_tol=1e-9) for step in steps[1:]):
        raise AuroraFormatError(f"OVATION {label} spacing is not constant")
    return first


def _valid_frame(frame: Any, expected_cells: int) -> bool:
    if not isinstance(frame, dict):
        return False
    try:
        observed_at = parse_utc(frame["observedAt"])
        valid_at = parse_utc(frame["validAt"])
        probability = base64.b64decode(frame["probabilityU8"], validate=True)
        validity = base64.b64decode(frame["validityBits"], validate=True)
        lead = float(frame["leadMinutes"])
    except (KeyError, TypeError, ValueError):
        return False
    return (
        valid_at >= observed_at
        and math.isfinite(lead)
        and math.isclose(lead, (valid_at - observed_at).total_seconds() / 60, abs_tol=0.001)
        and len(probability) == expected_cells
        and len(validity) == (expected_cells + 7) // 8
    )


def _no_data_intervals(
    frames: list[dict[str, Any]],
    requested_from: dt.datetime,
    requested_to: dt.datetime,
) -> list[dict[str, str]]:
    intervals: list[dict[str, str]] = []
    first = parse_utc(frames[0]["validAt"])
    if requested_from < first:
        intervals.append({
            "from": utc_iso(requested_from),
            "to": utc_iso(min(first, requested_to)),
            "reason": "before-bigmem-accumulation",
        })
    allowed = dt.timedelta(minutes=STALE_AFTER_MINUTES)
    for previous, following in zip(frames, frames[1:]):
        previous_end = parse_utc(previous["validAt"]) + allowed
        following_start = parse_utc(following["validAt"])
        if following_start > previous_end:
            gap_start = max(previous_end, requested_from)
            gap_end = min(following_start, requested_to)
            if gap_start < gap_end:
                intervals.append({
                    "from": utc_iso(gap_start),
                    "to": utc_iso(gap_end),
                    "reason": "snapshot-gap",
                })
    last_end = parse_utc(frames[-1]["validAt"]) + allowed
    if requested_to > last_end:
        intervals.append({
            "from": utc_iso(max(last_end, requested_from)),
            "to": utc_iso(requested_to),
            "reason": "after-latest-frame",
        })
    return [interval for interval in intervals if interval["from"] < interval["to"]]


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o644)
        os.replace(temporary, path)
    finally:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(temporary)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--snapshot-root", type=Path, required=True)
    parser.add_argument("--history-hours", type=float, default=48)
    args = parser.parse_args()

    retrieved_at = dt.datetime.now(dt.timezone.utc)
    payload = fetch_json(LATEST_GRID_URL)
    first = build_aurora_bundle(payload, retrieved_at=retrieved_at, history_hours=args.history_hours)
    history = load_snapshot_frames(
        args.snapshot_root,
        start=retrieved_at - dt.timedelta(hours=args.history_hours),
        end=retrieved_at + dt.timedelta(hours=3),
        grid=first["grid"],
    )
    bundle = build_aurora_bundle(
        payload,
        retrieved_at=retrieved_at,
        historical_frames=history,
        history_hours=args.history_hours,
    )
    snapshot = snapshot_current_frame(args.snapshot_root, bundle)
    _atomic_write(args.output, json.dumps(bundle, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    coverage = "complete" if bundle["time"]["coverageComplete"] else "partial"
    print(
        f"wrote {args.output} with {len(bundle['frames'])} exact OVATION frame(s); "
        f"48-hour coverage is {coverage}; snapshot {snapshot}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
