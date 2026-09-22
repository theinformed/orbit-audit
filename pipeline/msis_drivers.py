#!/usr/bin/env python3
"""The solar and geomagnetic indices that drive NRLMSIS, and nothing else.

NRLMSIS is an empirical model: it is a published fit to decades of observation,
evaluated from three numbers.  Those three numbers are the whole reason the
model can be evaluated at any instant, past or future, which is what lets this
site draw a thermosphere across a 120-hour timeline that NOAA's WAM covers about
a tenth of.

    F10.7   the 10.7 cm solar radio flux for the day, a proxy for solar EUV
    F10.7A  a long-run average of the same, the "how active is this solar
            cycle" term
    ap      the 3-hourly linear geomagnetic index, and the term that makes the
            model respond to a storm

`ap` is not fetched.  It is DERIVED from the Kp series this site already
publishes, through the standard Kp -> ap conversion table (`KP_TO_AP`), which is
a definition rather than a model: Kp is a quasi-logarithmic index reported in
thirds of a unit and each of its 28 values has exactly one ap.  That matters
here for a reason beyond tidiness -- the published Kp series carries NOAA's
FORECAST as well as the observed record, so the ap history that drives MSIS
forward of now is a forecast, and a layer built on it may say FORECAST and mean
it.

Nothing in this module is evaluated at import and every fetch is injectable, so
the tests run with no network.
"""

from __future__ import annotations

import datetime as dt
import json
import math
import re
from typing import Any, Mapping, Sequence

USER_AGENT = (
    "SpaceEnvironmentExplorer/0.1 educational-project contact=sean.theinformed.org"
)

# NOAA SWPC, unrestricted.  The first carries the observed 10.7 cm flux three
# times a day for about the last six weeks and, on the noon record, NOAA's own
# published running mean.  The second is NOAA's 27-day outlook, which is where
# the flux forward of now comes from.
F107_OBSERVED_URL = "https://services.swpc.noaa.gov/json/f107_cm_flux.json"
F107_OUTLOOK_URL = "https://services.swpc.noaa.gov/text/27-day-outlook.txt"


class DriverError(ValueError):
    """Raised when a purported index series cannot be used to drive a model."""


def utc_iso(value: dt.datetime) -> str:
    return value.astimezone(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def parse_utc(value: str) -> dt.datetime:
    text = value.strip().replace("Z", "+00:00")
    parsed = dt.datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


# ---------------------------------------------------------------------------
# Kp -> ap
# ---------------------------------------------------------------------------

# The standard conversion, Bartels' table, as published by GFZ Potsdam and used
# unchanged by every empirical thermosphere model that takes an ap.  Index is Kp
# in thirds of a unit: 0 -> Kp 0, 1 -> Kp 0+, 2 -> Kp 1-, ... 27 -> Kp 9.
#
# It is a LOOKUP, not a formula.  ap is not proportional to Kp and is not a
# smooth function of it: Kp 9- is 300 and Kp 9 is 400, a 33% step for one third
# of a Kp unit, because Kp is quasi-logarithmic in the underlying range of
# geomagnetic variation.  Fitting a curve through this table -- which is the
# obvious shortcut -- gets storm-time ap badly wrong, and storm-time ap is the
# only part of it this layer exists to show.
KP_TO_AP: tuple[int, ...] = (
    0, 2, 3, 4, 5, 6, 7, 9, 12, 15, 18, 22, 27, 32,
    39, 48, 56, 67, 80, 94, 111, 132, 154, 179, 207, 236, 300, 400,
)

KP_TO_AP_SOURCE = (
    "Bartels' standard Kp-to-ap conversion table (GFZ Potsdam); 28 values, one "
    "per third of a Kp unit, looked up rather than fitted."
)


def kp_to_ap(kp: float) -> int:
    """The ap equivalent of one Kp value.

    Kp is reported in thirds -- 2.33 is 2+, 2.67 is 3- -- so the table index is
    `round(kp * 3)`.  A value that is not a third of a unit is rounded to the
    nearest one and that is stated rather than hidden, because a Kp of 2.4 did
    not come from a magnetometer network and the caller should know its number
    was adjusted.
    """
    if kp is None or not math.isfinite(float(kp)):
        raise DriverError(f"Kp must be a finite number; got {kp!r}")
    kp = float(kp)
    if kp < 0 or kp > 9:
        raise DriverError(f"Kp is defined on 0..9; got {kp}")
    return KP_TO_AP[int(round(kp * 3))]


# ---------------------------------------------------------------------------
# The ap series, and MSIS's seven-element history
# ---------------------------------------------------------------------------

# Kp intervals are three hours long and begin at 00, 03, ... UT.  Nothing here
# interpolates between them: an instant falls inside exactly one interval and
# takes that interval's ap.
KP_INTERVAL = dt.timedelta(hours=3)


class ApSeries:
    """A 3-hourly ap record built from a published Kp series.

    Holds the interval start times, the ap for each, and -- kept beside the
    number rather than derived later -- whether NOAA had OBSERVED that interval
    or was PREDICTING it.  The distinction survives all the way to the badge on
    the card, so it cannot be a detail that gets lost in a helper.
    """

    def __init__(self, rows: Sequence[Mapping[str, Any]]):
        entries: dict[dt.datetime, tuple[int, str, float]] = {}
        rejected: list[str] = []
        for index, row in enumerate(rows):
            time_text = row.get("time")
            kp = row.get("kp")
            if not isinstance(time_text, str) or kp is None:
                rejected.append(f"row {index}: no time or no Kp")
                continue
            try:
                when = parse_utc(time_text)
                ap = kp_to_ap(float(kp))
            except (ValueError, DriverError) as error:
                rejected.append(f"row {index}: {error}")
                continue
            # Kp intervals start on a three-hour boundary. A row that does not
            # is a different quantity wearing the same field names.
            if when.minute or when.second or when.hour % 3:
                rejected.append(f"row {index}: {time_text} is not a Kp interval start")
                continue
            status = row.get("status") or row.get("sourceStatus") or "unknown"
            entries[when] = (ap, str(status).lower(), float(kp))
        if not entries:
            raise DriverError(
                "no usable Kp rows; cannot derive an ap history "
                + ("(" + "; ".join(rejected[:3]) + ")" if rejected else "")
            )
        self.times = sorted(entries)
        self.entries = entries
        self.rejected = rejected

    @property
    def first(self) -> dt.datetime:
        return self.times[0]

    @property
    def last(self) -> dt.datetime:
        """START of the last interval; it is valid for three hours after this."""
        return self.times[-1]

    def covers(self, when: dt.datetime) -> bool:
        when = when.astimezone(dt.timezone.utc)
        return self.first <= when < self.last + KP_INTERVAL

    def interval_start(self, when: dt.datetime) -> dt.datetime:
        when = when.astimezone(dt.timezone.utc)
        floored = when.replace(minute=0, second=0, microsecond=0)
        return floored - dt.timedelta(hours=floored.hour % 3)

    def ap_at(self, when: dt.datetime) -> int:
        start = self.interval_start(when)
        found = self.entries.get(start)
        if found is None:
            raise DriverError(f"no Kp interval published for {utc_iso(start)}")
        return found[0]

    def status_at(self, when: dt.datetime) -> str:
        start = self.interval_start(when)
        found = self.entries.get(start)
        if found is None:
            raise DriverError(f"no Kp interval published for {utc_iso(start)}")
        return found[1]

    def kp_at(self, when: dt.datetime) -> float:
        start = self.interval_start(when)
        found = self.entries.get(start)
        if found is None:
            raise DriverError(f"no Kp interval published for {utc_iso(start)}")
        return found[2]

    def daily_ap(self, when: dt.datetime) -> float:
        """Ap for the UT day containing `when`: the mean of its eight ap values.

        That is the definition of Ap, and it is computed here rather than taken
        from NOAA's daily product because the daily product is issued once a day
        and would disagree with the 3-hourly series the same card is showing.
        """
        day = when.astimezone(dt.timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        values = [
            self.entries[day + dt.timedelta(hours=3 * step)][0]
            for step in range(8)
            if day + dt.timedelta(hours=3 * step) in self.entries
        ]
        if not values:
            raise DriverError(f"no Kp intervals published for the UT day {day.date()}")
        return sum(values) / len(values)

    def msis_history(self, when: dt.datetime) -> list[float]:
        """MSIS's seven-element ap array for one instant, in MSIS's order.

        NRLMSIS's storm-time formulation wants, exactly:

            0  daily Ap
            1  ap for the 3-hour interval containing `when`
            2  ap 3 hours earlier
            3  ap 6 hours earlier
            4  ap 9 hours earlier
            5  mean of the eight ap values 12 to 33 hours earlier
            6  mean of the eight ap values 36 to 57 hours earlier

        Getting this order wrong does not raise; it produces a plausible field
        driven by the wrong storm, which is why the layout is written out here
        and asserted in the tests rather than trusted to a comment upstream.
        """
        start = self.interval_start(when)
        history = [
            float(self.daily_ap(when)),
            float(self.ap_at(start)),
            float(self.ap_at(start - dt.timedelta(hours=3))),
            float(self.ap_at(start - dt.timedelta(hours=6))),
            float(self.ap_at(start - dt.timedelta(hours=9))),
        ]
        for offset in (12, 36):
            block = [
                float(self.ap_at(start - dt.timedelta(hours=offset + 3 * step)))
                for step in range(8)
            ]
            history.append(sum(block) / len(block))
        return history

    def earliest_drivable(self) -> dt.datetime:
        """First instant with a complete 57-hour ap history behind it."""
        return self.first + dt.timedelta(hours=57)

    def latest_drivable(self) -> dt.datetime:
        """Last instant inside the last published interval."""
        return self.last + KP_INTERVAL - dt.timedelta(seconds=1)


# ---------------------------------------------------------------------------
# F10.7
# ---------------------------------------------------------------------------


def _fetch_text(url: str, timeout: int = 45) -> str:
    import urllib.request  # noqa: PLC0415

    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read()
    try:
        from ops import bandwidth  # noqa: PLC0415 - optional, never load-bearing

        bandwidth.record_fetch(
            len(body), family="noaa-swpc-f107", source="urllib response.read() length",
            run="thermosphere-msis",
        )
    except Exception:  # noqa: BLE001 - measurement must never break a fetch
        pass
    if not body:
        raise DriverError(f"empty response from {url}")
    return body.decode("utf-8", errors="replace")


def parse_f107_observed(payload: Any) -> dict[str, Any]:
    """NOAA's observed 10.7 cm flux, one value per UT day, plus its running mean.

    NOAA reports the flux three times a day.  The value everyone means by
    "F10.7" is the LOCAL NOON one from Penticton, which NOAA tags 20:00 UT and
    labels `reporting_schedule: "Noon"`; the morning and afternoon values are
    the same instrument at a different solar elevation and are not the index.
    Taking whichever record happened to be last would silently mix three
    different quantities into one series.
    """
    if isinstance(payload, str):
        payload = json.loads(payload)
    if not isinstance(payload, list):
        raise DriverError("the F10.7 product must be a list of records")
    daily: dict[dt.date, float] = {}
    mean_value: float | None = None
    mean_at: dt.date | None = None
    mean_days: int | None = None
    mean_from: str | None = None
    for record in payload:
        if not isinstance(record, Mapping):
            continue
        if str(record.get("reporting_schedule") or "").strip().lower() != "noon":
            continue
        try:
            when = parse_utc(str(record["time_tag"]))
            flux = float(record["flux"])
        except (KeyError, ValueError, TypeError):
            continue
        if not math.isfinite(flux) or flux <= 0:
            continue
        daily[when.date()] = flux
        running = record.get("ninety_day_mean")
        if running is not None and (mean_at is None or when.date() > mean_at):
            try:
                mean_value = float(running)
                mean_at = when.date()
                mean_days = int(record.get("rec_count") or 0) or None
                mean_from = str(record.get("avg_begin_date") or "") or None
            except (ValueError, TypeError):
                pass
    if not daily:
        raise DriverError("no noon F10.7 records in the product")
    return {
        "daily": daily,
        "runningMean": mean_value,
        "runningMeanAt": mean_at,
        "runningMeanDays": mean_days,
        "runningMeanFrom": mean_from,
    }


_OUTLOOK_ROW = re.compile(
    r"^(\d{4})\s+([A-Z][a-z]{2})\s+(\d{1,2})\s+(\d+)\s+(\d+)\s+(\d+)\s*$"
)
_MONTHS = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
    "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
}


def parse_f107_outlook(text: str) -> dict[dt.date, float]:
    """NOAA's 27-day outlook, radio-flux column only.

    The same table carries a predicted A index and a largest-Kp, and this
    deliberately does not read them: ap here comes from the 3-hourly Kp series
    the site already publishes, and taking a daily A from one product while
    taking 3-hourly ap from another would give the model two different storms.
    """
    rows: dict[dt.date, float] = {}
    for line in text.splitlines():
        match = _OUTLOOK_ROW.match(line.strip())
        if not match:
            continue
        year, month_text, day, flux, _a_index, _kp = match.groups()
        month = _MONTHS.get(month_text)
        if month is None:
            continue
        rows[dt.date(int(year), month, int(day))] = float(flux)
    if not rows:
        raise DriverError("no dated rows in the 27-day outlook table")
    return rows


class F107Series:
    """Daily F10.7 across the whole timeline, observed behind and forecast ahead.

    `f107a` is the long-run average term.  NRLMSIS defines it as the 81-day mean
    CENTRED on the day, and that number does not exist for today: it needs forty
    days of the future.  Rather than compute a centred mean out of a forecast and
    present it as one, this carries NOAA's own published running mean of the same
    flux and says which it is.  The difference matters only through a slow
    solar-cycle term, and stating it is cheaper than pretending.
    """

    def __init__(
        self,
        observed: Mapping[dt.date, float],
        predicted: Mapping[dt.date, float] | None = None,
        *,
        running_mean: float | None = None,
        running_mean_days: int | None = None,
        running_mean_at: dt.date | None = None,
    ):
        if not observed:
            raise DriverError("F10.7 needs at least one observed day")
        self.observed = dict(observed)
        self.predicted = dict(predicted or {})
        self.last_observed = max(self.observed)
        if running_mean is not None and math.isfinite(running_mean) and running_mean > 0:
            self.f107a = float(running_mean)
            self.f107a_days = running_mean_days
            self.f107a_at = running_mean_at
            self.f107a_basis = (
                f"NOAA's published {running_mean_days or 90}-day running mean of the same "
                "10.7 cm flux. NRLMSIS defines F10.7A as the 81-day mean centred on the day, "
                "which cannot be computed for today because it needs forty days of the future."
            )
        else:
            values = list(self.observed.values())
            self.f107a = sum(values) / len(values)
            self.f107a_days = len(values)
            self.f107a_at = self.last_observed
            self.f107a_basis = (
                f"Mean of the {len(values)} observed days this release holds. NOAA published no "
                "running mean in the product, and NRLMSIS's 81-day centred mean cannot be "
                "computed for today because it needs forty days of the future."
            )

    def covers(self, day: dt.date) -> bool:
        return day in self.observed or day in self.predicted

    def f107_for(self, day: dt.date) -> float:
        if day in self.observed:
            return self.observed[day]
        if day in self.predicted:
            return self.predicted[day]
        raise DriverError(f"no F10.7 published for {day.isoformat()}")

    def status_for(self, day: dt.date) -> str:
        if day in self.observed:
            return "observed"
        if day in self.predicted:
            return "predicted"
        raise DriverError(f"no F10.7 published for {day.isoformat()}")

    @property
    def first_day(self) -> dt.date:
        return min([*self.observed, *self.predicted])

    @property
    def last_day(self) -> dt.date:
        return max([*self.observed, *self.predicted])


def fetch_f107_series(*, fetch: Any = None) -> F107Series:
    """Both halves of the daily F10.7 record, from NOAA SWPC."""
    getter = fetch or _fetch_text
    observed = parse_f107_observed(getter(F107_OBSERVED_URL))
    try:
        predicted = parse_f107_outlook(getter(F107_OUTLOOK_URL))
    except Exception:  # noqa: BLE001 - the observed half is what the model needs
        predicted = {}
    # NOAA's 27-day outlook is issued weekly and its first rows are days that
    # have since been observed. Observation wins wherever both exist.
    predicted = {day: flux for day, flux in predicted.items() if day not in observed["daily"]}
    return F107Series(
        observed["daily"],
        predicted,
        running_mean=observed["runningMean"],
        running_mean_days=observed["runningMeanDays"],
        running_mean_at=observed["runningMeanAt"],
    )


def driver_provenance(
    ap: ApSeries, flux: F107Series, now: dt.datetime | None = None
) -> dict[str, Any]:
    """Everything a reader needs to check the model was driven honestly.

    `now` caps `observedThrough`, and it is not optional in spirit. NOAA labels
    the WHOLE current UT day `estimated` in its Kp product -- measured
    2026-08-20T03:53Z, seven of the eight intervals so labelled had not happened
    yet -- so taking NOAA's word for it would advertise an observed record
    running twenty-one hours into the future.
    """
    return {
        "ap": {
            "quantity": "3-hourly linear geomagnetic index",
            "derivedFrom": "the planetary Kp series published in this release",
            "conversion": KP_TO_AP_SOURCE,
            "intervalCount": len(ap.times),
            "validFrom": utc_iso(ap.first),
            "validTo": utc_iso(ap.last + KP_INTERVAL),
            "observedThrough": utc_iso(min(
                max(
                    (t for t in ap.times if ap.entries[t][1] in {"observed", "estimated"}),
                    default=ap.first,
                ) + KP_INTERVAL,
                (now or dt.datetime.now(dt.timezone.utc)).astimezone(dt.timezone.utc),
            )),
            "rejectedRows": ap.rejected,
        },
        "f107": {
            "quantity": "10.7 cm solar radio flux, daily noon value",
            "source": F107_OBSERVED_URL,
            "forecastSource": F107_OUTLOOK_URL,
            "observedDays": len(flux.observed),
            "predictedDays": len(flux.predicted),
            "observedThrough": flux.last_observed.isoformat(),
            "validFrom": flux.first_day.isoformat(),
            "validTo": flux.last_day.isoformat(),
        },
        "f107a": {
            "value": round(flux.f107a, 1),
            "basis": flux.f107a_basis,
            "dayCount": flux.f107a_days,
            "asOf": flux.f107a_at.isoformat() if flux.f107a_at else None,
        },
    }
