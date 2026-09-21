"""Normalize NOAA SWPC outlook products into one fail-soft JSON-ready bundle.

This module deliberately performs no network I/O.  Callers fetch the five source
products, pass the decoded JSON/text payloads to :func:`normalize_swpc_outlook`,
and may then serialize the returned dictionary directly.

Public API::

    normalize_swpc_outlook(
        noaa_scales=<dict>,
        three_day_forecast=<str>,
        three_day_geomag=<str>,
        kp_forecast=<list[dict]>,
        alerts=<list[dict]>,
        retrieved_at=<datetime or ISO string>,
    ) -> dict

The component normalizers are public as well.  They return stable shapes with
``None`` for unavailable scalar values and a ``parseWarnings`` list.  The bundle
normalizer moves those component warnings into its top-level ``parseWarnings``.
Malformed fields never turn a valid NOAA zero into missing data, and one broken
product does not prevent the other products from being normalized.
"""

from __future__ import annotations

import datetime as dt
import math
import re
from collections.abc import Mapping, Sequence
from typing import Any


NOAA_SCALES_URL = "https://services.swpc.noaa.gov/products/noaa-scales.json"
NOAA_THREE_DAY_URL = "https://services.swpc.noaa.gov/text/3-day-forecast.txt"
NOAA_THREE_DAY_GEOMAG_URL = "https://services.swpc.noaa.gov/text/3-day-geomag-forecast.txt"
NOAA_KP_FORECAST_URL = "https://services.swpc.noaa.gov/products/noaa-planetary-k-index-forecast.json"
NOAA_ALERTS_URL = "https://services.swpc.noaa.gov/products/alerts.json"

SCHEMA_VERSION = "swpc-outlook.v1"

_ISSUED_RE = re.compile(
    r"^:Issued:\s*(\d{4})\s+([A-Za-z]{3})\s+(\d{1,2})\s+(\d{4})(?:\s+(?:UTC|UT|Z))?\s*$",
    re.IGNORECASE | re.MULTILINE,
)
_MONTHS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}
_PHASES = {"observed", "estimated", "predicted"}


def _text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


def _compact_prose(value: str | None) -> str | None:
    return re.sub(r"\s+", " ", value).strip() if value else None


def _iso_datetime(value: Any) -> str | None:
    """Interpret NOAA's zone-less service timestamps as UTC."""

    if isinstance(value, dt.datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        normalized = value.strip()
        if normalized.endswith("Z"):
            normalized = normalized[:-1] + "+00:00"
        try:
            parsed = dt.datetime.fromisoformat(normalized)
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    else:
        parsed = parsed.astimezone(dt.timezone.utc)
    timespec = "milliseconds" if parsed.microsecond else "seconds"
    return parsed.isoformat(timespec=timespec).replace("+00:00", "Z")


def _iso_date(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        return dt.date.fromisoformat(value.strip()).isoformat()
    except ValueError:
        return None


def _record_timestamp(record: Mapping[str, Any]) -> str | None:
    date_stamp = _text(record.get("DateStamp"))
    time_stamp = _text(record.get("TimeStamp"))
    if date_stamp is None or time_stamp is None:
        return None
    return _iso_datetime(f"{date_stamp}T{time_stamp}")


def _issued_at(source: Any) -> str | None:
    if not isinstance(source, str):
        return None
    match = _ISSUED_RE.search(source)
    if not match:
        return None
    year_text, month_text, day_text, time_text = match.groups()
    month = _MONTHS.get(month_text.lower())
    if month is None:
        return None
    try:
        parsed = dt.datetime(
            int(year_text),
            month,
            int(day_text),
            int(time_text[:2]),
            int(time_text[2:]),
            tzinfo=dt.timezone.utc,
        )
    except (ValueError, TypeError):
        return None
    return _iso_datetime(parsed)


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _integer(value: Any) -> int | None:
    number = _number(value)
    if number is None or not number.is_integer():
        return None
    return int(number)


def _scale_level(value: Any, warnings: list[str], path: str) -> int | None:
    if value is None:
        return None
    parsed = _integer(value)
    if parsed is None or not 0 <= parsed <= 5:
        warnings.append(f"{path} is not a NOAA scale level from 0 through 5")
        return None
    return parsed


def _percent(value: Any, warnings: list[str], path: str) -> int | float | None:
    if value is None:
        return None
    parsed = _number(value)
    if parsed is None or not 0 <= parsed <= 100:
        warnings.append(f"{path} is not a percentage from 0 through 100")
        return None
    return int(parsed) if parsed.is_integer() else parsed


def _scale_record(
    record: Mapping[str, Any],
    key: str,
    warnings: list[str],
    path: str,
) -> dict[str, Any]:
    raw = record.get(key)
    value = raw if isinstance(raw, Mapping) else {}
    if raw is not None and not isinstance(raw, Mapping):
        warnings.append(f"{path} is not an object")
    return {
        "level": _scale_level(value.get("Scale"), warnings, f"{path}.Scale"),
        "label": _text(value.get("Text")),
    }


def _normalized_scales_record(
    record: Mapping[str, Any],
    warnings: list[str],
    path: str,
) -> dict[str, Any]:
    radio = _scale_record(record, "R", warnings, f"{path}.R")
    radiation = _scale_record(record, "S", warnings, f"{path}.S")
    geomagnetic = _scale_record(record, "G", warnings, f"{path}.G")

    raw_radio = record.get("R") if isinstance(record.get("R"), Mapping) else {}
    raw_radiation = record.get("S") if isinstance(record.get("S"), Mapping) else {}
    radio.update(
        {
            "r1R2ProbabilityPercent": _percent(
                raw_radio.get("MinorProb"), warnings, f"{path}.R.MinorProb"
            ),
            "r3R5ProbabilityPercent": _percent(
                raw_radio.get("MajorProb"), warnings, f"{path}.R.MajorProb"
            ),
        }
    )
    radiation["s1OrGreaterProbabilityPercent"] = _percent(
        raw_radiation.get("Prob"), warnings, f"{path}.S.Prob"
    )
    return {
        "radioBlackout": radio,
        "solarRadiation": radiation,
        "geomagnetic": geomagnetic,
    }


def normalize_noaa_scales(raw: Any) -> dict[str, Any]:
    """Normalize current, rolling-maximum, and three forecast NOAA-scale records."""

    warnings: list[str] = []
    root: Mapping[str, Any]
    if isinstance(raw, Mapping):
        root = raw
    else:
        root = {}
        warnings.append("root is not an object")

    def record(key: str) -> Mapping[str, Any]:
        value = root.get(key, root.get(int(key)) if key.lstrip("-").isdigit() else None)
        if isinstance(value, Mapping):
            return value
        if value is not None:
            warnings.append(f"record {key} is not an object")
        return {}

    rolling_record = record("-1")
    current_record = record("0")
    rolling = _normalized_scales_record(rolling_record, warnings, "-1")
    rolling.update(
        {
            # NOAA labels record -1 as the prior 24-hour maximum; its stamp is
            # the start of that rolling window, not a second current-as-of time.
            "windowStart": _record_timestamp(rolling_record),
            "windowEnd": _record_timestamp(current_record),
        }
    )
    latest = _normalized_scales_record(current_record, warnings, "0")
    latest["asOf"] = _record_timestamp(current_record)

    forecast_days: list[dict[str, Any]] = []
    for day_index in range(1, 4):
        day_record = record(str(day_index))
        normalized = _normalized_scales_record(day_record, warnings, str(day_index))
        normalized.update(
            {
                "dayIndex": day_index,
                "date": _iso_date(day_record.get("DateStamp")),
                "sourceTimestamp": _record_timestamp(day_record),
            }
        )
        forecast_days.append(normalized)

    return {
        "source": NOAA_SCALES_URL,
        "latestObserved": latest,
        "rolling24HourMaximum": rolling,
        "forecastDays": forecast_days,
        "parseWarnings": warnings,
    }


def _forecast_sections(source: str) -> dict[str, str]:
    markers = list(
        re.finditer(
            r"^[ABC]\.\s+NOAA\s+(.+?)\s+Activity (?:Observation )?and Forecast\s*$",
            source,
            flags=re.IGNORECASE | re.MULTILINE,
        )
    )
    sections: dict[str, str] = {}
    for index, marker in enumerate(markers):
        end = markers[index + 1].start() if index + 1 < len(markers) else len(source)
        heading = marker.group(1).strip().lower()
        sections[heading] = source[marker.end() : end]
    return sections


def _rationale(section: str | None) -> str | None:
    if not section:
        return None
    match = re.search(r"^Rationale:\s*(.*)\Z", section, flags=re.IGNORECASE | re.MULTILINE | re.DOTALL)
    return _compact_prose(match.group(1)) if match else None


def parse_three_day_forecast(source: Any) -> dict[str, Any]:
    """Extract the product issue time and the three forecaster rationales."""

    warnings: list[str] = []
    text = source if isinstance(source, str) else ""
    if not isinstance(source, str):
        warnings.append("source is not text")
    issued_at = _issued_at(text)
    if issued_at is None:
        warnings.append("issued time is missing or invalid")

    sections = _forecast_sections(text)
    rationales = {
        "geomagnetic": _rationale(sections.get("geomagnetic")),
        "solarRadiation": _rationale(sections.get("solar radiation")),
        "radioBlackout": _rationale(sections.get("radio blackout")),
    }
    for name, rationale in rationales.items():
        if rationale is None:
            warnings.append(f"{name} rationale is missing")

    return {
        "source": NOAA_THREE_DAY_URL,
        "issuedAt": issued_at,
        "rationales": rationales,
        "parseWarnings": warnings,
    }


def _anchor_date(issued_at: str | None) -> dt.date | None:
    if issued_at is None:
        return None
    normalized = issued_at[:-1] + "+00:00" if issued_at.endswith("Z") else issued_at
    try:
        return dt.datetime.fromisoformat(normalized).date()
    except ValueError:
        return None


def _partial_date(day_text: str, month_text: str, anchor: dt.date | None) -> dt.date | None:
    month = _MONTHS.get(month_text.lower())
    if month is None or anchor is None:
        return None
    candidates: list[dt.date] = []
    for year in (anchor.year - 1, anchor.year, anchor.year + 1):
        try:
            candidates.append(dt.date(year, month, int(day_text)))
        except ValueError:
            continue
    return min(candidates, key=lambda value: abs((value - anchor).days)) if candidates else None


def _date_range(
    start_day: str,
    start_month: str,
    end_day: str,
    end_month: str,
    anchor: dt.date | None,
) -> list[str | None]:
    start = _partial_date(start_day, start_month, anchor)
    if start is None:
        return []
    end_month_number = _MONTHS.get(end_month.lower())
    if end_month_number is None:
        return []
    try:
        end = dt.date(start.year, end_month_number, int(end_day))
        if end < start:
            end = dt.date(start.year + 1, end_month_number, int(end_day))
    except ValueError:
        return []
    span = (end - start).days
    if not 0 <= span <= 10:
        return []
    return [(start + dt.timedelta(days=offset)).isoformat() for offset in range(span + 1)]


def _ap_single(text: str, label: str, anchor: dt.date | None) -> dict[str, Any]:
    match = re.search(
        rf"^{re.escape(label)}\s+Ap\s+(\d{{1,2}})\s+([A-Za-z]{{3}})\s+(\d+)\s*$",
        text,
        flags=re.IGNORECASE | re.MULTILINE,
    )
    if not match:
        return {"date": None, "value": None}
    day, month, value = match.groups()
    parsed_date = _partial_date(day, month, anchor)
    return {"date": parsed_date.isoformat() if parsed_date else None, "value": _integer(value)}


def _predicted_ap(text: str, anchor: dt.date | None) -> list[dict[str, Any]]:
    match = re.search(
        r"^Predicted\s+Ap\s+(\d{1,2})\s+([A-Za-z]{3})\s*-\s*"
        r"(\d{1,2})\s+([A-Za-z]{3})\s+([0-9]+(?:-[0-9]+)*)\s*$",
        text,
        flags=re.IGNORECASE | re.MULTILINE,
    )
    if not match:
        return []
    start_day, start_month, end_day, end_month, values_text = match.groups()
    dates = _date_range(start_day, start_month, end_day, end_month, anchor)
    values = [_integer(value) for value in values_text.split("-")]
    count = max(len(dates), len(values))
    return [
        {
            "date": dates[index] if index < len(dates) else None,
            "value": values[index] if index < len(values) else None,
        }
        for index in range(count)
    ]


def _probability_dates(text: str, anchor: dt.date | None) -> list[str | None]:
    match = re.search(
        r"^NOAA Geomagnetic Activity Probabilities\s+"
        r"(\d{1,2})\s+([A-Za-z]{3})\s*-\s*(\d{1,2})\s+([A-Za-z]{3})\s*$",
        text,
        flags=re.IGNORECASE | re.MULTILINE,
    )
    return _date_range(*match.groups(), anchor) if match else []


def _probability_values(text: str, label_pattern: str) -> list[int | float | None]:
    match = re.search(
        rf"^{label_pattern}\s+([0-9.]+(?:\s*/\s*[0-9.]+)*)\s*$",
        text,
        flags=re.IGNORECASE | re.MULTILINE,
    )
    if not match:
        return []
    values: list[int | float | None] = []
    for raw in re.split(r"\s*/\s*", match.group(1)):
        parsed = _number(raw)
        if parsed is None or not 0 <= parsed <= 100:
            values.append(None)
        else:
            values.append(int(parsed) if parsed.is_integer() else parsed)
    return values


def parse_three_day_geomag(source: Any) -> dict[str, Any]:
    """Extract Ap values and daily activity probabilities from geomag text."""

    warnings: list[str] = []
    text = source if isinstance(source, str) else ""
    if not isinstance(source, str):
        warnings.append("source is not text")
    issued_at = _issued_at(text)
    if issued_at is None:
        warnings.append("issued time is missing or invalid")
    anchor = _anchor_date(issued_at)

    observed = _ap_single(text, "Observed", anchor)
    estimated = _ap_single(text, "Estimated", anchor)
    predicted = _predicted_ap(text, anchor)
    if observed["value"] is None:
        warnings.append("observed Ap is missing or invalid")
    if estimated["value"] is None:
        warnings.append("estimated Ap is missing or invalid")
    if not predicted:
        warnings.append("predicted Ap values are missing or invalid")

    probability_dates = _probability_dates(text, anchor)
    category_values = {
        "activePercent": _probability_values(text, r"Active"),
        "minorStormPercent": _probability_values(text, r"Minor\s+storm"),
        "moderateStormPercent": _probability_values(text, r"Moderate\s+storm"),
        "strongToExtremeStormPercent": _probability_values(text, r"Strong\s*-\s*Extreme\s+storm"),
    }
    count = max(
        [len(probability_dates), len(predicted), *(len(values) for values in category_values.values())]
    )
    if count == 0:
        warnings.append("daily geomagnetic activity probabilities are missing or invalid")
    if not probability_dates and predicted:
        probability_dates = [entry["date"] for entry in predicted]

    probabilities: list[dict[str, Any]] = []
    for index in range(count):
        row: dict[str, Any] = {
            "date": probability_dates[index] if index < len(probability_dates) else None,
        }
        for key, values in category_values.items():
            row[key] = values[index] if index < len(values) else None
        probabilities.append(row)

    return {
        "source": NOAA_THREE_DAY_GEOMAG_URL,
        "issuedAt": issued_at,
        "ap": {
            "observed": observed,
            "estimated": estimated,
            "predicted": predicted,
        },
        "activityProbabilities": probabilities,
        "parseWarnings": warnings,
    }


def normalize_kp_forecast(raw: Any) -> dict[str, Any]:
    """Preserve NOAA Kp row phases and scale labels without inventing issuance."""

    warnings: list[str] = []
    if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes, bytearray)):
        source_rows = raw
    else:
        source_rows = []
        warnings.append("root is not an array")

    rows: list[dict[str, Any]] = []
    for index, item in enumerate(source_rows):
        if not isinstance(item, Mapping):
            warnings.append(f"row {index} is not an object")
            continue
        source_time = item.get("time_tag")
        normalized_time = _iso_datetime(source_time)
        if source_time is not None and normalized_time is None:
            warnings.append(f"row {index} has an invalid time_tag")

        kp = _number(item.get("kp"))
        if item.get("kp") is not None and (kp is None or not 0 <= kp <= 9):
            warnings.append(f"row {index} has an invalid Kp value")
            kp = None

        source_status = _text(item.get("observed"))
        status = source_status.lower() if source_status and source_status.lower() in _PHASES else None
        if source_status is not None and status is None:
            warnings.append(f"row {index} has an unknown observed/estimated/predicted status")

        rows.append(
            {
                "time": normalized_time,
                "sourceTimeTag": source_time if isinstance(source_time, str) else None,
                "kp": kp,
                "status": status,
                "sourceStatus": source_status,
                "noaaScale": _text(item.get("noaa_scale")),
            }
        )

    return {
        "source": NOAA_KP_FORECAST_URL,
        "issuedAt": None,
        "rows": rows,
        "parseWarnings": warnings,
    }


def normalize_recent_alerts(raw: Any) -> dict[str, Any]:
    """Normalize the recent-message feed without claiming any message is active."""

    warnings: list[str] = []
    if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes, bytearray)):
        source_items = raw
    else:
        source_items = []
        warnings.append("root is not an array")

    items: list[dict[str, Any]] = []
    for index, item in enumerate(source_items):
        if not isinstance(item, Mapping):
            warnings.append(f"item {index} is not an object")
            continue
        source_issue = item.get("issue_datetime")
        issued_at = _iso_datetime(source_issue)
        if source_issue is not None and issued_at is None:
            warnings.append(f"item {index} has an invalid issue_datetime")
        raw_message = item.get("message") if isinstance(item.get("message"), str) else None
        if item.get("message") is not None and raw_message is None:
            warnings.append(f"item {index} message is not text")
        items.append(
            {
                "productId": _text(item.get("product_id")),
                "issuedAt": issued_at,
                "sourceIssueDatetime": source_issue if isinstance(source_issue, str) else None,
                "state": "recent-not-necessarily-active",
                # Do not strip or fold this text. It contains NOAA's warning
                # lifecycle, serial numbers, valid windows, and cancellations.
                "rawMessage": raw_message,
            }
        )

    return {
        "source": NOAA_ALERTS_URL,
        "label": "Recent NOAA messages — not necessarily active",
        "recentNotNecessarilyActive": True,
        "items": items,
        "parseWarnings": warnings,
    }


def normalize_swpc_outlook(
    *,
    noaa_scales: Any = None,
    three_day_forecast: Any = None,
    three_day_geomag: Any = None,
    kp_forecast: Any = None,
    alerts: Any = None,
    retrieved_at: dt.datetime | str | None = None,
) -> dict[str, Any]:
    """Return the complete, stable, JSON-ready SWPC outlook contract."""

    components = {
        "noaaScales": normalize_noaa_scales(noaa_scales),
        "threeDayForecast": parse_three_day_forecast(three_day_forecast),
        "geomagneticForecast": parse_three_day_geomag(three_day_geomag),
        "kpForecast": normalize_kp_forecast(kp_forecast),
        "alerts": normalize_recent_alerts(alerts),
    }
    warnings: list[str] = []
    for component_name, component in components.items():
        for warning in component.pop("parseWarnings"):
            warnings.append(f"{component_name}: {warning}")

    normalized_retrieved_at = _iso_datetime(retrieved_at)
    if retrieved_at is not None and normalized_retrieved_at is None:
        warnings.append("retrievedAt is invalid")

    return {
        "schemaVersion": SCHEMA_VERSION,
        "retrievedAt": normalized_retrieved_at,
        **components,
        "parseWarnings": warnings,
    }


__all__ = [
    "NOAA_ALERTS_URL",
    "NOAA_KP_FORECAST_URL",
    "NOAA_SCALES_URL",
    "NOAA_THREE_DAY_GEOMAG_URL",
    "NOAA_THREE_DAY_URL",
    "SCHEMA_VERSION",
    "normalize_kp_forecast",
    "normalize_noaa_scales",
    "normalize_recent_alerts",
    "normalize_swpc_outlook",
    "parse_three_day_forecast",
    "parse_three_day_geomag",
]
