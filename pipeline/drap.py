#!/usr/bin/env python3
"""Ingest and reduce NOAA SWPC D-RAP highest-affected-frequency fields.

The operational source is a small ASCII grid.  This module snapshots that
source on bigmem and emits a browser artifact; it never infers absorption where
NOAA did not publish a value.  NCEI daily archives can be reduced separately
for historical lessons without making a visitor download the source PNGs.
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
import struct
import tarfile
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, BinaryIO, Iterable


CURRENT_TEXT_URL = "https://services.swpc.noaa.gov/text/drap_global_frequencies.txt"
PRODUCT_URL = "https://www.spaceweather.gov/products/d-region-absorption-predictions-d-rap"
DOCUMENTATION_URL = "https://www.spaceweather.gov/content/global-d-region-absorption-prediction-documentation"
ARCHIVE_LANDING_URL = "https://www.ncei.noaa.gov/products/space-weather/ionospheric-program/d-region-absorption-prediction"
ARCHIVE_FILES_API = "https://www.ncei.noaa.gov/cloud-access/space-weather-portal/api/v1/files"
ARCHIVE_FILE_PREFIX = "https://archive.data.noaa.gov/satellite-spaceweather/SWPC/Models/DRAP/SWX_DRAP20/"
USER_AGENT = "SpaceEnvironmentExplorer/0.1 educational-project contact=sean.theinformed.org"
MISSING_U16 = 65535
QUANTIZATION_MHZ = 0.1


class DrapFormatError(ValueError):
    """Raised when a purported NOAA D-RAP grid is structurally unsafe."""


def utc_iso(value: dt.datetime) -> str:
    return value.astimezone(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def parse_utc(value: str) -> dt.datetime:
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(dt.timezone.utc)


def parse_drap_global_frequencies(text: str) -> dict[str, Any]:
    """Parse NOAA's current/archive GLOBAL.txt product into one compact frame."""
    valid_match = re.search(r"^#\s*Product Valid At\s*:\s*(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2})\s+UTC\s*$", text, re.MULTILINE)
    if not valid_match:
        raise DrapFormatError("D-RAP valid time is missing")
    valid_at = dt.datetime.fromisoformat(f"{valid_match.group(1)}T{valid_match.group(2)}:00+00:00")

    longitude_line = next((line for line in text.splitlines() if re.match(r"^\s+-?\d+(?:\s+-?\d+){20,}\s*$", line)), None)
    if longitude_line is None:
        raise DrapFormatError("D-RAP longitude header is missing")
    longitudes = [int(value) for value in longitude_line.split()]
    if len(longitudes) < 20 or any(b <= a for a, b in zip(longitudes, longitudes[1:])):
        raise DrapFormatError("D-RAP longitude coordinates are not a plausible increasing grid")

    rows: list[tuple[int, list[float | None]]] = []
    row_pattern = re.compile(r"^\s*(-?\d+)\s*\|\s*(.*?)\s*$")
    for line in text.splitlines():
        match = row_pattern.match(line)
        if not match:
            continue
        latitude = int(match.group(1))
        values: list[float | None] = []
        for token in match.group(2).split():
            if token in {"--", "NA", "N/A"}:
                values.append(None)
                continue
            try:
                value = float(token)
            except ValueError as error:
                raise DrapFormatError(f"invalid D-RAP value {token!r}") from error
            if not math.isfinite(value) or value < 0 or value > 200:
                raise DrapFormatError(f"implausible D-RAP HAF value {value}")
            values.append(value)
        if len(values) != len(longitudes):
            raise DrapFormatError(
                f"D-RAP latitude {latitude} has {len(values)} values; expected {len(longitudes)}"
            )
        rows.append((latitude, values))

    if len(rows) < 20:
        raise DrapFormatError(f"implausible D-RAP latitude count: {len(rows)}")
    latitudes = [row[0] for row in rows]
    if any(b >= a for a, b in zip(latitudes, latitudes[1:])):
        raise DrapFormatError("D-RAP latitude coordinates are not a decreasing grid")
    longitude_step = _constant_step(longitudes, "longitude")
    latitude_step = _constant_step(latitudes, "latitude")

    quantized: list[int] = []
    finite_values: list[float] = []
    for _, values in rows:
        for value in values:
            if value is None:
                quantized.append(MISSING_U16)
            else:
                finite_values.append(value)
                encoded = round(value / QUANTIZATION_MHZ)
                if encoded >= MISSING_U16:
                    raise DrapFormatError(f"D-RAP value {value} exceeds uint16 encoding")
                quantized.append(encoded)
    if not finite_values:
        raise DrapFormatError("D-RAP grid contains no finite values")

    frame = {
        "validAt": utc_iso(valid_at),
        "valuesU16": base64.b64encode(struct.pack(f"<{len(quantized)}H", *quantized)).decode("ascii"),
        "maximumHafMhz": round(max(finite_values), 1),
        "affectedCellPercent": {
            f"{frequency}MHz": round(100 * sum(value >= frequency for value in finite_values) / len(finite_values), 2)
            for frequency in (3, 10, 30)
        },
    }
    return {
        "grid": {
            "longitudeStartDeg": longitudes[0],
            "longitudeStepDeg": longitude_step,
            "longitudeCount": len(longitudes),
            "latitudeStartDeg": latitudes[0],
            "latitudeStepDeg": latitude_step,
            "latitudeCount": len(latitudes),
            "order": "latitude-major, north-to-south, west-to-east",
        },
        "frame": frame,
        "messages": {
            "estimatedRecovery": _header_value(text, "Estimated Recovery Time"),
            "xray": _header_value(text, "X-RAY Message"),
            "xrayWarning": _header_value(text, "X-RAY Warning"),
            "proton": _header_value(text, "Proton Message"),
            "protonWarning": _header_value(text, "Proton Warning"),
        },
    }


def build_drap_bundle(
    current_text: str,
    *,
    retrieved_at: dt.datetime,
    historical_frames: Iterable[dict[str, Any]] = (),
) -> dict[str, Any]:
    parsed = parse_drap_global_frequencies(current_text)
    current_frame = parsed["frame"]
    expected_bytes = parsed["grid"]["longitudeCount"] * parsed["grid"]["latitudeCount"] * 2
    frames_by_time: dict[str, dict[str, Any]] = {}
    for frame in [*historical_frames, current_frame]:
        if not isinstance(frame, dict) or not isinstance(frame.get("validAt"), str):
            continue
        try:
            payload = base64.b64decode(frame.get("valuesU16", ""), validate=True)
            parse_utc(frame["validAt"])
        except (ValueError, TypeError):
            continue
        if len(payload) != expected_bytes:
            continue
        frames_by_time[frame["validAt"]] = frame
    frames = [frames_by_time[key] for key in sorted(frames_by_time, key=parse_utc)]
    start = frames[0]["validAt"]
    end = frames[-1]["validAt"]
    return {
        "schemaVersion": "noaa-drap.v1",
        "product": "NOAA SWPC D-Region Absorption Predictions (D-RAP 2)",
        "status": "model",
        "temporalKind": "empirical-nowcast",
        "retrievedAt": utc_iso(retrieved_at),
        "source": {
            "currentData": CURRENT_TEXT_URL,
            "productPage": PRODUCT_URL,
            "documentation": DOCUMENTATION_URL,
            "historicalArchive": ARCHIVE_LANDING_URL,
            "historicalFilesApi": ARCHIVE_FILES_API,
            "inputs": "GOES 0.1–0.8 nm X-ray flux and GOES energetic-proton flux",
            "sourceCadence": "X-ray component 1 minute; proton component 5 minutes",
        },
        "grid": parsed["grid"],
        "encoding": {
            "type": "uint16-le-base64",
            "scaleMhz": QUANTIZATION_MHZ,
            "missingValue": MISSING_U16,
        },
        "quantity": {
            "name": "Highest Affected Frequency",
            "shortName": "1 dB HAF",
            "units": "MHz",
            "definition": "Highest frequency expected to lose at least 1 dB on a vertical ground–ionosphere–ground path; lower frequencies lose more.",
            "pathGeometry": "vertical two-pass",
        },
        "time": {
            "validFrom": start,
            "validTo": end,
            "frameCount": len(frames),
            "selection": "hold latest frame at or before requested UTC; do not interpolate",
            "staleAfterMinutes": 12,
            "futureAvailable": False,
        },
        "legend": {
            "title": "D-region HF absorption",
            "subtitle": "1 dB HAF · MHz",
            "minimumDisplayedMhz": 3,
            "maximumDisplayedMhz": 30,
            "ticksMhz": [3, 5, 10, 15, 20, 25, 30],
            "belowMinimumLabel": "<3 MHz · below HF band",
            "aboveMaximumLabel": "≥30 MHz",
        },
        "messages": parsed["messages"],
        "frames": frames,
        "limitations": [
            "Empirical model guidance driven by near-real-time GOES inputs; it is not a direct absorption observation or an outage report.",
            "The global HAF field combines X-ray and solar-proton effects but does not include auroral-electron absorption, which can be important at high and middle latitudes.",
            "The displayed threshold is for a vertical two-pass path. Oblique paths, antenna performance, link margin, mode structure, noise, and F-region support are not evaluated.",
            "NOAA validation found large event- and location-dependent errors; use the field as a qualitative indicator of highly disturbed conditions, not a deterministic communications decision aid.",
        ],
        "operationalDisplay": {
            "defaultVisible": False,
            "menu": "advanced-layers",
            "singleCompactLegend": True,
            "assumptionDriven": False,
        },
    }


def snapshot_current_frame(snapshot_root: Path, bundle: dict[str, Any]) -> Path:
    """Persist one official frame on bigmem for the rolling site history."""
    frames = bundle.get("frames") or []
    if not frames:
        raise DrapFormatError("D-RAP bundle contains no frame to snapshot")
    frame = frames[-1]
    label = re.sub(r"[^0-9]", "", frame["validAt"])
    path = snapshot_root / f"drap-{label}.json"
    document = {"schema": 1, "grid": bundle["grid"], "encoding": bundle["encoding"], "frame": frame}
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
    if not snapshot_root.exists():
        return []
    for path in snapshot_root.glob("drap-*.json"):
        try:
            document = json.loads(path.read_text())
            frame = document["frame"]
            valid_at = parse_utc(frame["validAt"])
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
            continue
        if document.get("grid") != grid or valid_at < start or valid_at > end:
            continue
        frames[frame["validAt"]] = frame
    return [frames[key] for key in sorted(frames, key=parse_utc)]


def ncei_archive_query_url(start: dt.datetime, end: dt.datetime, *, limit: int = 100) -> str:
    query = urllib.parse.urlencode({
        "start_time": utc_iso(start),
        "end_time": utc_iso(end),
        "sat": "SWPC-Models",
        "inst": "DRAP",
        "prod": "SWX_DRAP20",
        "limit": limit,
        "order": "asc",
    })
    return f"{ARCHIVE_FILES_API}?{query}"


def parse_ncei_archive_index(payload: Any) -> list[dict[str, Any]]:
    status = payload.get("status") if isinstance(payload, dict) else None
    if not isinstance(status, dict) or status.get("code") != 200:
        raise DrapFormatError("NCEI archive API did not return status 200")
    files: list[dict[str, Any]] = []
    for item in payload.get("data", []):
        if not isinstance(item, dict) or item.get("product") != "SWX_DRAP20":
            continue
        link = item.get("file_link")
        if not isinstance(link, str) or not link.startswith(ARCHIVE_FILE_PREFIX) or not link.endswith(".tar.gz"):
            continue
        files.append({
            "url": link,
            "sizeBytes": int(item.get("size_bytes") or 0),
            "validFrom": str(item.get("time_coverage_start") or ""),
            "validTo": str(item.get("time_coverage_end") or ""),
        })
    return files


def reduce_ncei_archive(
    fileobj: BinaryIO,
    *,
    cadence_minutes: int = 15,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Stream a NOAA daily archive and keep one official numeric frame/bucket."""
    if cadence_minutes < 1:
        raise ValueError("cadence_minutes must be positive")
    buckets: dict[int, dict[str, Any]] = {}
    grid: dict[str, Any] | None = None
    with tarfile.open(fileobj=fileobj, mode="r|gz") as archive:
        for member in archive:
            if not member.isfile() or not member.name.endswith("_GLOBAL.txt"):
                continue
            extracted = archive.extractfile(member)
            if extracted is None:
                continue
            try:
                parsed = parse_drap_global_frequencies(extracted.read().decode("utf-8", errors="replace"))
            except DrapFormatError:
                continue
            if grid is None:
                grid = parsed["grid"]
            elif parsed["grid"] != grid:
                continue
            frame = parsed["frame"]
            bucket = int(parse_utc(frame["validAt"]).timestamp() // (cadence_minutes * 60))
            prior = buckets.get(bucket)
            if prior is None or parse_utc(frame["validAt"]) > parse_utc(prior["validAt"]):
                buckets[bucket] = frame
    if grid is None or not buckets:
        raise DrapFormatError("NCEI archive contains no valid D-RAP GLOBAL.txt frames")
    return grid, [buckets[key] for key in sorted(buckets)]


def fetch_text(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/plain"})
    with urllib.request.urlopen(request, timeout=60) as response:
        body = response.read()
    if not body:
        raise RuntimeError(f"empty response from {url}")
    return body.decode("utf-8", errors="replace")


def fetch_json(url: str) -> Any:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def _constant_step(values: list[int], label: str) -> int:
    steps = {b - a for a, b in zip(values, values[1:])}
    if len(steps) != 1 or 0 in steps:
        raise DrapFormatError(f"D-RAP {label} spacing is not constant")
    return steps.pop()


def _header_value(text: str, label: str) -> str | None:
    match = re.search(
        rf"^#[ \t]*{re.escape(label)}[ \t]*:[ \t]*([^\r\n]*)[ \t]*$",
        text,
        re.MULTILINE | re.IGNORECASE,
    )
    if not match:
        return None
    value = match.group(1).strip()
    return value or None


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


def _parse_cli_time(value: str) -> dt.datetime:
    if not re.search(r"(?:Z|[+-]\d{2}:\d{2})$", value):
        raise argparse.ArgumentTypeError("time must include an explicit UTC offset")
    parsed = parse_utc(value)
    return parsed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    current = subparsers.add_parser("current", help="fetch current NOAA grid and update a rolling bigmem snapshot")
    current.add_argument("--output", type=Path, required=True)
    current.add_argument("--snapshot-root", type=Path)
    current.add_argument("--history-hours", type=float, default=48)
    archive = subparsers.add_parser("archive-index", help="list official NCEI daily D-RAP archives")
    archive.add_argument("--start", type=_parse_cli_time, required=True)
    archive.add_argument("--end", type=_parse_cli_time, required=True)
    args = parser.parse_args()

    if args.command == "archive-index":
        result = parse_ncei_archive_index(fetch_json(ncei_archive_query_url(args.start, args.end)))
        print(json.dumps(result, indent=2))
        return 0

    retrieved_at = dt.datetime.now(dt.timezone.utc)
    current_text = fetch_text(CURRENT_TEXT_URL)
    first = build_drap_bundle(current_text, retrieved_at=retrieved_at)
    history: list[dict[str, Any]] = []
    if args.snapshot_root:
        history = load_snapshot_frames(
            args.snapshot_root,
            start=retrieved_at - dt.timedelta(hours=args.history_hours),
            end=retrieved_at,
            grid=first["grid"],
        )
    bundle = build_drap_bundle(current_text, retrieved_at=retrieved_at, historical_frames=history)
    if args.snapshot_root:
        snapshot_current_frame(args.snapshot_root, bundle)
    _atomic_write(args.output, json.dumps(bundle, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    print(f"wrote {args.output} with {len(bundle['frames'])} D-RAP frame(s), valid through {bundle['time']['validTo']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
