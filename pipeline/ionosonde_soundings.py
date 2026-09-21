"""Measured ionosonde soundings: the only layer parameters on this site that an
instrument actually observed.

Why this lane exists
--------------------
The site draws its ionosphere from NOAA's operational WAM-IPE field, and that
field genuinely does not contain a resolvable E or F1 layer. This was measured
on the live artifact, not assumed:

* the E ledge's median prominence above the E-F valley is **0.02 dex** on a
  5.6-decade scale - one uint8 code - and clears 0.3 dex in only ~20% of
  columns;
* on the dayside, where a Chapman E layer must be strongest, the median
  prominence is **-0.088 dex**: negative, meaning there is no local E maximum
  at all and density climbs monotonically from E into F;
* the published F1 criterion resolved F1 over **0%** of columns.

So D and F2 can be drawn from the model and E and F1 cannot. The layer
parameters that WAM-IPE lacks are exactly the ones an ionosonde measures
directly, by sweeping a radio frequency upward and timing the echo, and
scaling the resulting ionogram. That is a measurement, so it enters the site
in the ``observed`` evidence class and never mixes with the model field.

Source, and why it is this one rather than GIRO directly
--------------------------------------------------------
The authority is the Lowell GIRO Data Center (LGDC) at UMass Lowell, which
operates DIDBase. It is NOT the practical machine interface for this site, and
that was established by probing it rather than assumed:

* the documented ``https://lgdc.uml.edu/common/DIDBGetValues`` servlet returns
  a Tomcat path-level **404** ("The requested resource is not available") on
  both ``lgdc.uml.edu`` and ``giro.uml.edu``, over http and https. Its sibling
  servlets on the same host (``DIDBFastStationList``, ``DIDBYearListForStation``)
  answer 200, so the host is up and that one entry point is retired or moved;
* ``DIDBGetValues`` requires ``ursiCode``, i.e. one request per station. A
  nearest-station feature needs the whole network, which is ~100 requests per
  refresh;
* LGDC returned **429 Too Many Requests** after about eight requests spread
  over a few minutes during that probe. ~100 requests per refresh is flatly
  incompatible with that rate limiter;
* the LGDC Rules of the Road require a registered account for data access and
  its (SA) clause says data "are to be shared only with users who have an
  up-to-date LGDC account", which is in tension with republishing values on a
  public teaching site. Their own summary simultaneously calls the collection
  an open dataset that may be "freely used, re-used, and redistributed" under
  CC BY-NC-SA 4.0. That contradiction is unresolved and is a reason not to
  build a bulk redistribution lane against a credentialed account.

``prop.kc2g.com`` is a public propagation service, funded by WWROF, that
already aggregates the same GIRO soundings and republishes them; it returns
the entire network in **one** request. It is an aggregator, not the authority,
and this module says so wherever the data is shown. Attribution therefore
carries the whole chain - the observatory operators, GIRO/INGV as distributor,
and kc2g as the aggregator this site actually called.

Terms: kc2g publishes **no** terms of use, **no** licence, **no** rate limit
and serves **no** robots.txt (404), and its source repository has no README or
licence file. That is an ABSENCE of a published policy, not permission. This
lane therefore self-limits: one request per release build at most, a
descriptive User-Agent naming the project and a contact, no retry, and a hard
stop on any non-200 (``fetch_json_once`` breaks on 403/429 and does not retry
any status).

What the feed actually is - characterised, not assumed
------------------------------------------------------
``/api/stations.json`` is a **last-known-value roster, not a live feed.** On
2026-08-19T19:15Z it carried 101 stations of which only **27** had sounded
within three hours. 70% were older than a day and the oldest was
**11 years** stale (LO168, 2015-06-10). A naive nearest-station search over
the raw list will therefore hand a reader an 11-year-old sounding and call it
current. ``FRESH_LIMIT_MINUTES`` exists to stop exactly that, and
``stale_station_count`` is published so the site can say how many were dropped.

Nullity in this feed is mostly PHYSICS, not missing data, and the two must
never be conflated in the UI:

* ``fof1`` was present in **0%** of records taken above 80 deg solar zenith
  angle and in 40-80% below it. The largest solar zenith angle at which any
  record carried an F1 layer was **72.5 deg**. F1 is a daytime-only layer; a
  null at night is the correct answer, not a gap.
* ``foe`` was present in 60-71% of records taken below 80 deg and in 7% above
  100 deg, for the same reason: the E layer is solar-produced and largely
  recombines after sunset.

Two traps in the field set, both found by inspection:

1. ``foes`` is **sporadic E**, not the regular E layer. The regular E critical
   frequency is ``foe``. Reading ``foes`` as "the E layer" would report a thin
   irregular patch as the main layer.
2. ``hme`` is exactly ``110.0`` in 23 of 101 records while every other value
   appears once - it is the autoscaler's nominal height, not a measurement,
   and 18 of those 23 have no ``foe`` at all. This module therefore refuses an
   E layer that has no ``foe``, and flags a nominal ``hme``.
"""

from __future__ import annotations

import datetime as dt
import math
from typing import Any, Callable

SCHEMA_VERSION = 1

STATIONS_URL = "https://prop.kc2g.com/api/stations.json"

#: The upstream is a roster of last-known values with no expiry, so freshness
#: is this module's job. Three hours is chosen from the measured cadence: the
#: stations that are actually reporting re-sound every 5-15 minutes (13 of 101
#: records changed timestamp in a 4-minute window), so a station silent for
#: three hours has missed at least a dozen soundings and is not "current" by
#: any reading. It is not a round number for its own sake - shortening it to
#: one hour on the measured frame would have cost 0 of the 27 fresh stations,
#: and lengthening it to 24 hours would have admitted 3 more that had each
#: missed a hundred soundings.
FRESH_LIMIT_MINUTES = 180

#: Fetch cadence. The publisher timer runs every 5 minutes and the fastest
#: station cadence observed upstream was 5 minutes, so a shorter age cannot
#: produce new information and would only add load to an aggregator that
#: publishes no rate limit.
MAX_AGE_SECONDS = 300

ATTRIBUTION = (
    "Ionosonde soundings measured by observatory operators worldwide, distributed "
    "through the Lowell GIRO Data Center (GIRO) and INGV, and retrieved from the "
    "prop.kc2g.com aggregator. GIRO data are released under CC BY-NC-SA 4.0; this "
    "site is non-commercial and educational. Reinisch, B. W., and I. A. Galkin, "
    "Global Ionospheric Radio Observatory (GIRO), Earth, Planets and Space, 63, "
    "377-381, doi:10.5047/eps.2011.03.001, 2011. "
    "http://spase.info/SMWG/Observatory/GIRO"
)

SOURCE_NOTE = (
    "prop.kc2g.com is an aggregator, not the authority. The authority is the Lowell "
    "GIRO Data Center. Its own DIDBGetValues endpoint returned 404 and its host "
    "rate-limited at 429 after about eight requests, and a nearest-station feature "
    "needs the whole network in one call, so this site reads the aggregator and "
    "credits the full chain."
)

#: ``hme`` takes this exact value in 23 of 101 records while every other value
#: occurs once. It is the ARTIST autoscaler's nominal E height, not a scaled
#: one, so it is reported as nominal rather than as a measured peak height.
NOMINAL_E_HEIGHT_KM = 110.0


def _number(value: Any) -> float | None:
    """Coerce an upstream field to a finite float, or to None.

    The upstream mixes types: ``latitude`` and ``longitude`` arrive as strings,
    ``md`` arrives as a string of a number, and most layer parameters arrive as
    floats or null. A field that cannot be read is None, never 0.0 - a zero
    critical frequency is a real and different claim from an unscaled one.
    """
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def normalize_longitude(longitude_deg: float) -> float:
    """Upstream publishes 0..360; the rest of this site uses -180..180.

    Measured on the live feed: station longitudes ran 0.5 to 359.4, so the
    convention is unambiguous and a station at 262.3 is Austin, Texas at
    -97.7 rather than a point in the Indian Ocean.
    """
    return (longitude_deg + 180.0) % 360.0 - 180.0


def parse_sounding_time(value: Any) -> dt.datetime | None:
    """Upstream timestamps are naive ISO strings and are UTC.

    They carry no offset, so ``fromisoformat`` yields a naive datetime. Stamping
    UTC here rather than at the comparison site keeps a naive/aware mix from
    reaching the age arithmetic, where it would raise rather than mislead - but
    only after a release had already been built.
    """
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = dt.datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed.replace(tzinfo=dt.timezone.utc) if parsed.tzinfo is None else parsed


def normalize_station(record: Any, observed_at: dt.datetime) -> dict[str, Any] | None:
    """One upstream record to one sounding, or None if it cannot be trusted.

    A record is dropped only when it has no identity, no position or no usable
    time. A record with a valid position and time but no scaled parameters is
    KEPT: a station that sounded and could scale nothing is a real observation
    of a disturbed or blanketed ionosphere, and dropping it would silently
    improve the network's apparent coverage.
    """
    if not isinstance(record, dict):
        return None
    station = record.get("station")
    if not isinstance(station, dict):
        return None
    code = station.get("code")
    if not isinstance(code, str) or not code.strip():
        return None
    latitude = _number(station.get("latitude"))
    longitude = _number(station.get("longitude"))
    if latitude is None or longitude is None:
        return None
    if not -90.0 <= latitude <= 90.0:
        return None
    sounded_at = parse_sounding_time(record.get("time"))
    if sounded_at is None:
        return None

    age_minutes = (observed_at - sounded_at).total_seconds() / 60.0

    fo_e = _number(record.get("foe"))
    hm_e = _number(record.get("hme"))
    # The E layer is admitted only on a scaled foE. hmE alone is not evidence of
    # an E layer: 18 of the 23 records carrying the nominal 110.0 km height had
    # no foE at all, so an hmE-only E layer would draw a layer nobody measured.
    if fo_e is None:
        hm_e = None
    e_height_is_nominal = hm_e is not None and hm_e == NOMINAL_E_HEIGHT_KM

    fo_f1 = _number(record.get("fof1"))
    hm_f1 = _number(record.get("hmf1"))
    if fo_f1 is None:
        hm_f1 = None

    return {
        "code": code.strip(),
        "name": (station.get("name") or code).strip(),
        "latitudeDeg": latitude,
        "longitudeDeg": normalize_longitude(longitude),
        "soundedAt": sounded_at.replace(tzinfo=None).isoformat() + "Z",
        "ageMinutes": round(age_minutes, 1),
        "foF2Mhz": _number(record.get("fof2")),
        "hmF2Km": _number(record.get("hmf2")),
        "foF1Mhz": fo_f1,
        "hmF1Km": hm_f1,
        "foEMhz": fo_e,
        "hmEKm": hm_e,
        "eHeightIsNominal": e_height_is_nominal,
        # Sporadic E, kept under its own name so it can never be read as the
        # regular E layer. It is a thin irregular patch, not a layer of the
        # daily ionosphere, and it is reported separately or not at all.
        "foEsMhz": _number(record.get("foes")),
        # ARTIST autoscaling confidence, 0-100; -1 means the upstream published
        # no score. 100 is a manually validated scaling.
        "confidence": _number(record.get("cs")),
        "upstreamSource": record.get("source") if isinstance(record.get("source"), str) else None,
    }


def build_ionosonde_bundle(
    fetch_json: Callable[[str, int], Any],
    *,
    observed_at: dt.datetime | None = None,
) -> dict[str, Any]:
    """Fetch the network and return the fresh soundings plus what was dropped.

    ``fetch_json`` is injected rather than imported so the caller owns the
    caching, the User-Agent and the non-200 policy, and so the tests can
    exercise every branch of this module without touching the network.
    """
    observed_at = observed_at or dt.datetime.now(dt.timezone.utc)
    payload = fetch_json(STATIONS_URL, MAX_AGE_SECONDS)
    if not isinstance(payload, list):
        raise RuntimeError(
            f"{STATIONS_URL} returned {type(payload).__name__}, not the expected list of stations"
        )

    normalized = [normalize_station(record, observed_at) for record in payload]
    usable = [record for record in normalized if record is not None]
    fresh = sorted(
        (record for record in usable if record["ageMinutes"] <= FRESH_LIMIT_MINUTES),
        key=lambda record: record["code"],
    )

    return {
        "schemaVersion": SCHEMA_VERSION,
        "observedAt": observed_at.replace(tzinfo=None).isoformat(timespec="seconds") + "Z",
        "evidence": "observed",
        "freshLimitMinutes": FRESH_LIMIT_MINUTES,
        "stations": fresh,
        # Published so the site can state the network's real condition rather
        # than implying that the stations it draws are the network.
        "upstreamStationCount": len(payload),
        "staleStationCount": len(usable) - len(fresh),
        "unreadableRecordCount": len(normalized) - len(usable),
        "withFoF2": sum(1 for record in fresh if record["foF2Mhz"] is not None),
        "withFoE": sum(1 for record in fresh if record["foEMhz"] is not None),
        "withFoF1": sum(1 for record in fresh if record["foF1Mhz"] is not None),
        "attribution": ATTRIBUTION,
        "sourceNote": SOURCE_NOTE,
        "sourceUrl": STATIONS_URL,
    }
