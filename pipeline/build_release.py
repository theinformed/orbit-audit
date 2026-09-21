#!/usr/bin/env python3
"""Build a compact, immutable browser bundle on bigmem-PC.

This job is intentionally the only component that talks to upstream catalog and
space-weather feeds. The VPS receives content-addressed artifacts and an atomic
manifest; it never performs this processing itself.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import fcntl
import gzip
import hashlib
import functools
import json
import math
import os
import re
import statistics
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable, Iterable

from pipeline import catalog_factcheck, satnogs_verify
from pipeline.aurora_history import (
    LATEST_GRID_URL as NOAA_OVATION_LATEST,
    build_aurora_bundle,
    load_snapshot_frames as load_aurora_snapshot_frames,
    snapshot_current_frame as snapshot_current_aurora_frame,
)
from pipeline.storm_indices import (
    KYOTO_DST as NOAA_KYOTO_DST,
    NOAA_MODEL_DST,
    USGS_DST,
    build_storm_indices,
    derive_driver_terms,
    fetch_storm_sources,
    storm_source_records,
)
from pipeline.drap import (
    CURRENT_TEXT_URL as NOAA_DRAP_CURRENT,
    build_drap_bundle,
    load_snapshot_frames as load_drap_snapshot_frames,
    snapshot_current_frame as snapshot_current_drap_frame,
)
from pipeline.geospace_history import (
    PUBLISHED_HISTORY_HOURS as GEOSPACE_HISTORY_HOURS,
    SNAPSHOT_RETENTION_HOURS as GEOSPACE_SNAPSHOT_RETENTION_HOURS,
    history_metadata as geospace_history_metadata,
    load_snapshot_frames as load_geospace_snapshot_frames,
    merge_frames as merge_geospace_frames,
    prune_snapshots as prune_geospace_snapshots,
    published_cadence_minutes as geospace_published_cadence_minutes,
    radiation_fingerprint as geospace_radiation_fingerprint,
    snapshot_frames as snapshot_geospace_frames,
    snapshot_times as geospace_snapshot_times,
)
from pipeline.storm_indices import (
    KYOTO_DST as NOAA_KYOTO_DST,
    NOAA_MODEL_DST,
    USGS_DST,
    build_storm_indices,
    derive_driver_terms,
    fetch_storm_sources,
    storm_source_records,
)
from pipeline.programme_participation import (
    load_participation,
    participation_disclosure,
    participation_index,
    programme_catalog,
    validate_participation,
)
from ingest.celestrak_groups import (
    InvalidCelestrakGroup,
    assert_group_list_is_sane,
    record_invalid_group,
    validate_group_body,
)
from pipeline.solar_wind_guard import assess_rtsw
from pipeline.swpc_outlook import normalize_swpc_outlook
from pipeline.swmf import NOMADS_ROOT, build_geospace_and_ground_bundles
from pipeline.thermosphere import build_msis_bundle, build_thermosphere_bundle
from pipeline.wam_ipe import NOMADS_WFS_ROOT, build_wam_ipe_bundle


ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "pipeline" / ".cache"
USER_AGENT = "SpaceEnvironmentExplorer/0.1 educational-project contact=sean.theinformed.org"
ENVIRONMENT_HISTORY_HOURS = 48
DEFAULT_ENVIRONMENT_HISTORY_ROOT = Path("/mnt/d/space-explorer/environment-history")
STARLINK_RECENT_COHORT_DAYS = 45

CELESTRAK_FLEET_GROUPS = {
    "tdrss": "TDRSS",
    "sarsat": "COSPAS-SARSAT",
    "dmc": "Disaster Monitoring Constellation",
    "argos": "ARGOS",
    "planet": "Flock / PlanetScope",
    "spire": "Spire",
    "intelsat": "Intelsat",
    "ses": "SES",
    "eutelsat": "Eutelsat",
    "telesat": "Telesat",
    "starlink": "Starlink",
    "oneweb": "OneWeb",
    "qianfan": "Qianfan",
    "hulianwang": "Guowang / SatNet",
    "kuiper": "Project Kuiper",
    "iridium-NEXT": "Iridium NEXT",
    "orbcomm": "Orbcomm",
    "globalstar": "Globalstar",
    "gps-ops": "GPS",
    "glo-ops": "GLONASS",
    "galileo": "Galileo",
    "beidou": "BeiDou",
    "sbas": "SBAS",
}

# Additional CelesTrak category groups fetched only to supply mission evidence
# (never a constellation label). CELESTRAK_FLEET_GROUPS above already covers a
# few of these (sarsat, dmc, tdrss, argos, planet, spire, starlink, oneweb);
# this tuple lists the rest so fetch_celestrak_fleet_memberships() can join
# both into one per-satellite group-membership set. See CELESTRAK_MISSION_GROUPS
# for how membership resolves a mission and docs/satellite-catalog-classification.md
# for the verification method and precedence rationale.
# `noaa`, `swarm`, `gorizont`, `raduga` and `molniya` were removed on
# 2026-08-16: CelesTrak does not publish groups by those names. Asked for them
# it answers **HTTP 200** with a plain-text `Invalid query: ... not found`, so a
# status-code check sees success and only the JSON validator catches it — the
# same "200 is not success" shape this project has been bitten by before.
# Verified one request each from the VPS, the only host allowed to reach
# celestrak.org. NOAA and GOES spacecraft are covered by the `weather` group,
# which is mirrored and does work.
CELESTRAK_MISSION_CATEGORY_GROUPS = (
    "weather", "goes", "gnss", "nnss", "science", "geodetic",
    "amateur", "resource", "stations", "military", "other-comm",
    "musson", "engineering", "education", "radar", "cubesat",
)

# Ordered CelesTrak group -> (mission, sector, confidence) repair table, applied
# in build_catalog() ONLY when classify()'s exact-named and name-pattern rules
# left an object as mission == "other". Because it is gated on "other", it can
# never override a name-pattern classification; it can only resolve objects the
# name rules did not recognize. Entries are evaluated top to bottom and the
# first group present in a satellite's sourceGroups wins, so relative order
# matters. The first seven rows (through the "oneweb" row) reproduce the prior
# hard-coded fallback exactly, in its original order, so every previously
# resolved "other" repair keeps its previous result. All new rows are appended
# after them, so they can only affect objects that were still "other" before
# this change. A `None` mission (the "military" row) means CelesTrak confirms
# the sector without identifying a specific mission bucket; mission is left
# unchanged (it stays "other") and only sector/confidence are set, matching the
# prior behavior.
# Offline shape check on every list above. It makes no request: it can only
# catch a malformed name or one of the five names measured absent from the VPS
# (noaa, swarm, molniya, raduga, gorizont). Whether a plausible new name exists
# is learned only by the VPS mirror's first naturally due request, then
# remembered in its quarantine ledger. Nothing validates names by probing the
# live service on a schedule.
assert_group_list_is_sane(tuple(CELESTRAK_FLEET_GROUPS), where="CELESTRAK_FLEET_GROUPS")
assert_group_list_is_sane(CELESTRAK_MISSION_CATEGORY_GROUPS, where="CELESTRAK_MISSION_CATEGORY_GROUPS")

CELESTRAK_MISSION_GROUPS: tuple[tuple[str, str | None, str, str], ...] = (
    ("weather", "weather", "civil", "high"),
    ("gnss", "navigation", "mixed", "high"),
    ("science", "science", "civil", "high"),
    ("resource", "earth-observation", "civil", "medium"),
    ("stations", "human-spaceflight", "civil", "medium"),
    ("military", None, "military", "high"),
    ("starlink", "communications", "commercial", "high"),
    ("oneweb", "communications", "commercial", "high"),
    # New category-group evidence added 2026-08-07 to resolve the remaining
    # low-confidence "other" backlog. Mapped into the site's existing mission
    # values only (no new facet); see docs/satellite-catalog-classification.md
    # for the source and honesty rationale behind each mapping.
    ("goes", "weather", "civil", "high"),
    ("nnss", "navigation", "civil", "high"),
    ("geodetic", "science", "civil", "high"),
    ("amateur", "communications", "civil", "high"),
    ("tdrss", "communications", "civil", "high"),
    ("sarsat", "communications", "civil", "high"),
    ("dmc", "earth-observation", "civil", "high"),
    ("planet", "earth-observation", "commercial", "high"),
    ("argos", "earth-observation", "civil", "medium"),
    ("spire", "weather", "commercial", "medium"),
    ("musson", "communications", "mixed", "medium"),
    ("other-comm", "communications", "civil", "medium"),
    ("engineering", "technology", "civil", "medium"),
    ("education", "technology", "academic", "medium"),
    ("cubesat", "technology", "academic", "medium"),
    ("radar", "technology", "civil", "medium"),
)

NOAA_WIND = "https://services.swpc.noaa.gov/json/rtsw/rtsw_wind_1m.json"
NOAA_MAG = "https://services.swpc.noaa.gov/json/rtsw/rtsw_mag_1m.json"
NOAA_KP = "https://services.swpc.noaa.gov/json/planetary_k_index_1m.json"
# The 3-hourly planetary Kp for the last seven days. Same host, same publisher,
# and the only record long enough to spin a plasmasphere simulation up: see
# pipeline/plasmasphere_dgcpm.py. Its cadence is three hours, so it is fetched
# with a long max-age and, like every other feed here, never retried.
NOAA_KP_3HOUR = "https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json"
NOAA_XRAY = "https://services.swpc.noaa.gov/json/goes/primary/xrays-7-day.json"
NOAA_PROTONS = "https://services.swpc.noaa.gov/json/goes/primary/integral-protons-6-hour.json"
NOAA_ELECTRONS = "https://services.swpc.noaa.gov/json/goes/primary/integral-electrons-6-hour.json"
NOAA_GLOTEC_INDEX = "https://services.swpc.noaa.gov/products/glotec/geojson_2d_urt.json"
NOAA_AURORA = "https://services.swpc.noaa.gov/json/ovation_aurora_latest.json"
NOAA_SCALES = "https://services.swpc.noaa.gov/products/noaa-scales.json"
NOAA_ALERTS = "https://services.swpc.noaa.gov/products/alerts.json"
NOAA_KP_FORECAST = "https://services.swpc.noaa.gov/products/noaa-planetary-k-index-forecast.json"
NOAA_THREE_DAY = "https://services.swpc.noaa.gov/text/3-day-forecast.txt"
NOAA_THREE_DAY_GEOMAG = "https://services.swpc.noaa.gov/text/3-day-geomag-forecast.txt"
NOAA_PROPAGATED_WIND = "https://services.swpc.noaa.gov/products/geospace/propagated-solar-wind.json"
NOAA_BASE = "https://services.swpc.noaa.gov"
LAND_URL = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_110m_admin_0_countries.geojson"

EARTH_RADIUS_KM = 6378.137
EARTH_MU_KM3_S2 = 398600.4418

OWNER_LABELS = {
    "US": "United States",
    "PRC": "People's Republic of China",
    "CIS": "Commonwealth of Independent States",
    "ESA": "European Space Agency",
    "EUME": "EUMETSAT",
    "JPN": "Japan",
    "IND": "India",
    "ISRO": "Indian Space Research Organisation",
    "UK": "United Kingdom",
    "FR": "France",
    "GER": "Germany",
    "CA": "Canada",
    "IT": "Italy",
    "SPN": "Spain",
    "SKOR": "Republic of Korea",
    "ISS": "International Space Station",
    "NATO": "NATO",
    "ITSO": "Intelsat",
    "EUTE": "Eutelsat",
    "SES": "SES",
    "IRID": "Iridium",
    "O3B": "O3b / SES",
    "GLOB": "Globalstar",
    "IM": "Inmarsat",
    # Added 2026-08-07. Without these the card printed the registry's raw
    # abbreviation -- "SAUD", "ISRA", "AB" -- in a field labelled OWNER /
    # OPERATOR, which reads as a name the site knows rather than a code it
    # failed to expand. Only codes whose expansion is unambiguous are listed;
    # anything uncertain is deliberately left as the raw code rather than
    # guessed at, and shows up in the audit's owner review queue instead.
    "TURK": "Türkiye",
    "AUS": "Australia",
    "TWN": "Taiwan",
    "NOR": "Norway",
    "BRAZ": "Brazil",
    "UAE": "United Arab Emirates",
    "SAUD": "Saudi Arabia",
    "SING": "Singapore",
    "BEL": "Belgium",
    "ARGN": "Argentina",
    "GREC": "Greece",
    "INDO": "Indonesia",
    "EGYP": "Egypt",
    "POL": "Poland",
    "ISRA": "Israel",
    "THAI": "Thailand",
    "SWTZ": "Switzerland",
    "BGR": "Bulgaria",
    "RWA": "Rwanda",
    "LUXE": "Luxembourg",
    "POR": "Portugal",
    "IRAN": "Iran",
    "ALG": "Algeria",
    "KAZ": "Kazakhstan",
    "PAKI": "Pakistan",
    "MEX": "Mexico",
    "DEN": "Denmark",
    "MALA": "Malaysia",
    "FIN": "Finland",
    "SWED": "Sweden",
    "NETH": "Netherlands",
    "HUN": "Hungary",
    "VTNM": "Viet Nam",
    "NIG": "Nigeria",
    "AZER": "Azerbaijan",
    "AGO": "Angola",
    "ANG": "Angola",
    "CZCH": "Czechia",
    "AUT": "Austria",
    "NZ": "New Zealand",
    "CHLE": "Chile",
    "PERU": "Peru",
    "QAT": "Qatar",
    "LTU": "Lithuania",
    "LKA": "Sri Lanka",
    "BELA": "Belarus",
    "UKR": "Ukraine",
    "RP": "Philippines",
    "AB": "Arab Satellite Communications Organization",
    "ABS": "Asia Broadcast Satellite",
    "AC": "Asia Satellite Telecommunications Company",
    "TBD": "Not yet attributed in the registry",
}

CONSTELLATION_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("PWSA Transport Layer", ("PRAETORIAN SDA_",)),
    ("GPS", ("GPS ", "NAVSTAR")),
    ("BeiDou", ("BEIDOU",)),
    ("Galileo", ("GALILEO",)),
    ("GLONASS", ("GLONASS",)),
    ("QZSS", ("QZSS", "QZS-")),
    ("NavIC", ("NAVIC", "IRNSS")),
    ("Starlink", ("STARLINK",)),
    ("OneWeb", ("ONEWEB",)),
    ("Project Kuiper", ("KUIPER",)),
    ("Qianfan", ("QIANFAN",)),
    ("Guowang", ("GUOWANG",)),
    ("Iridium", ("IRIDIUM",)),
    ("Globalstar", ("GLOBALSTAR",)),
    ("Orbcomm", ("ORBCOMM",)),
    ("O3b / mPOWER", ("O3B", "MPOWER")),
    ("Inmarsat", ("INMARSAT",)),
    # "GALAXY" is Intelsat's own fleet name (<https://www.intelsat.com/fleet/>);
    # "EUTE" is space-track's SATCAT abbreviation for Eutelsat, which is how
    # those spacecraft are actually named in the mirror this build reads.
    ("Intelsat", ("INTELSAT", "GALAXY")),
    ("Eutelsat", ("EUTELSAT", "EUTE")),
    ("SES", ("SES-",)),
    ("Flock / PlanetScope", ("FLOCK", "DOVE ")),
    ("Spire", ("LEMUR",)),
    ("SpaceBEE", ("SPACEBEE",)),
    ("ICEYE", ("ICEYE",)),
    ("Capella", ("CAPELLA",)),
    ("Umbra", ("UMBRA",)),
    ("BlackSky", ("GLOBAL-", "BLACKSKY")),
    ("Satellogic", ("NUSAT",)),
    ("SkySat", ("SKYSAT",)),
    ("Sentinel", ("SENTINEL",)),
    ("Swarm", ("SWARM",)),
    ("CYGNSS", ("CYGNSS",)),
    ("COSMIC", ("COSMIC",)),
    ("Yaogan", ("YAOGAN",)),
    ("GOES", ("GOES ", "GOES-")),
    ("JPSS", ("JPSS", "SUOMI NPP")),
    ("DMSP", ("DMSP",)),
    ("Metop", ("METOP",)),
    ("Meteosat", ("METEOSAT",)),
    ("Fengyun", ("FENGYUN", "FY-")),
    ("Himawari", ("HIMAWARI",)),
    ("WGS", ("WGS ",)),
    ("MUOS", ("MUOS",)),
    ("AEHF", ("AEHF",)),
    ("SBIRS", ("SBIRS",)),
)

# Publicly identified York-built Tranche 1 Transport Layer spacecraft.  The
# first and third planes use PRAETORIAN names in the public catalog; the second
# plane currently uses this contiguous SDA number block.  SDA identifies all
# three 21-spacecraft planes as LEO data-transport / tactical-communications
# vehicles, so they belong under MILSATCOM rather than "Other / unverified".
PWSA_TRANSPORT_NAMES = re.compile(r"^(?:PRAETORIAN SDA_\d+|SDA_(?:16(?:6[4-9]|7\d|8[0-4])))$")
UHF_FOLLOW_ON_NAMES = re.compile(r"^UFO (?:2|4|10|11)(?: \(USA \d+\))?$")
TACSAT_4_NAME = re.compile(r"^TACSAT[- ]4$")
ASBM_NAMES = re.compile(r"^ASBM-[12]$")
# The three operator families in CelesTrak's `gnss` group that carry an
# augmentation transponder but are NOT navigation spacecraft, and whose names no
# other rule recognises. Without these, 7 objects read mission "unknown" while
# still showing a navigation secondary -- a card that says a satellite does
# navigation augmentation and nothing else, which is backwards about what the
# spacecraft is for.
#
# The optional suffix is CelesTrak's own annotation, e.g. "GSAT-8 (GAGAN/PRN
# 127)". Matching it here rather than stripping it upstream keeps the rule
# readable against the name as the group file actually writes it.
#
# The separator is [- ] because the two upstreams disagree and the catalog is
# built from the one that does NOT hyphenate: CelesTrak writes "GSAT-8", while
# space-track's SATCAT -- the name the published record carries -- writes
# "GSAT 8". A hyphen-only rule matched the group file and missed every object on
# the site, which is the same failure already recorded for "SES-" and "EUTE"
# above. Verified 2026-08-18 against the published catalog, not against the
# group file.
AUGMENTATION_SUFFIX = r"(?: \([A-Z]+/PRN \d+\))?"
ASTRA_5B_NAME = re.compile(r"^ASTRA 5B" + AUGMENTATION_SUFFIX + r"$")
GSAT_HOSTED_NAMES = re.compile(r"^GSAT[- ](?:8|10|15)" + AUGMENTATION_SUFFIX + r"$")
LUCH_RELAY_NAMES = re.compile(r"^LUCH 5[ABV]" + AUGMENTATION_SUFFIX + r"$")
LAUNCH_GROUP = re.compile(r"^(\d{4}-\d{3})")


def identify_constellation(name: str) -> str | None:
    upper = name.upper()
    return next((label for label, patterns in CONSTELLATION_PATTERNS if contains(upper, patterns)), None)


def identify_launch_group(object_id: str) -> str | None:
    match = LAUNCH_GROUP.match(object_id.strip())
    return match.group(1) if match else None


def normalize_launch_date(value: Any) -> str | None:
    candidate = str(value or "").strip()[:10]
    try:
        return dt.date.fromisoformat(candidate).isoformat()
    except ValueError:
        return None


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def iso_z(value: dt.datetime) -> str:
    return value.astimezone(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def atomic_write(path: Path, data: bytes) -> None:
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


def cache_path(url: str) -> Path:
    label = re.sub(r"[^a-zA-Z0-9]+", "-", urllib.parse.urlsplit(url).path).strip("-")[-70:]
    return CACHE / f"{label}-{sha256(url.encode())[:10]}.json"


def _count_ingress(url: str, byte_count: int) -> None:
    """Tell the bandwidth ledger how much this fetch brought in.

    Called at the point the socket read returns, NOT where fetch_bytes returns:
    a cache hit returns bytes that never crossed the network, and counting
    those would report traffic that did not happen.

    ``len(body)`` is the DECODED length -- urllib has already inflated a
    gzipped response by this point -- so ops/bandwidth records it on the "raw"
    basis, where it can never be summed into a wire total. Wrapped in
    suppress-everything on purpose: a byte counter that can break the data
    pipeline is a worse problem than an hour the page has to report as
    unmeasured, and reporting an unmeasured hour is a thing it knows how to do.
    """
    try:
        from ops import bandwidth  # noqa: PLC0415 - optional, and never load-bearing

        bandwidth.record_fetch(
            byte_count, family=bandwidth.upstream_family(url),
            source="urllib response.read() length (decoded, not on-the-wire)",
            run="build_release",
        )
    except Exception:  # noqa: BLE001 - measurement must never break a fetch
        pass



def fetch_bytes(
    url: str,
    max_age_seconds: int,
    *,
    retries: int = 2,
    timeout_seconds: int = 60,
    validator: Callable[[bytes], Any] | None = None,
) -> bytes:
    CACHE.mkdir(parents=True, exist_ok=True)
    cached = cache_path(url)
    if cached.exists() and time.time() - cached.stat().st_mtime < max_age_seconds:
        cached_body = cached.read_bytes()
        try:
            if validator is not None:
                validator(cached_body)
            return cached_body
        except InvalidCelestrakGroup:
            # A cached "Invalid query" body is the silent failure itself, sitting
            # on disk. Refetching it would just ask again for a name CelesTrak
            # has already said does not exist, so this raises instead.
            raise
        except Exception as error:
            # A prior interrupted/malformed upstream response must not pin the
            # refresh loop to a fresh but unusable cache entry.
            print(f"WARNING: cached response is invalid; refetching {url}: {error}")

    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                body = response.read()
            _count_ingress(url, len(body))
            if not body:
                raise RuntimeError(f"empty response from {url}")
            if validator is not None:
                try:
                    validator(body)
                except InvalidCelestrakGroup:
                    # The server answered instantly and correctly: this group
                    # does not exist. Asking again is precisely the impoliteness
                    # that got this installation firewalled on 2026-08-07, so
                    # this skips the retry loop and the stale-cache fallback
                    # both.
                    raise
                except Exception as error:
                    raise RuntimeError(f"invalid response from {url}: {error}") from error
            atomic_write(cached, body)
            return body
        except InvalidCelestrakGroup:
            raise
        except urllib.error.HTTPError as error:
            last_error = error
            # CelesTrak intentionally returns 403 when a caller asks for the same
            # large catalog more than once per upstream update. Retrying would be
            # abusive and can trigger its firewall.
            if error.code in {403, 429}:
                break
            if attempt < retries:
                time.sleep(2**attempt)
        except (urllib.error.URLError, TimeoutError, RuntimeError) as error:
            last_error = error
            if attempt < retries:
                time.sleep(2**attempt)
    if cached.exists():
        cached_body = cached.read_bytes()
        try:
            if validator is not None:
                validator(cached_body)
        except InvalidCelestrakGroup:
            raise
        except Exception as error:
            raise RuntimeError(
                f"upstream fetch failed and cached response is invalid for {url}: {error}"
            ) from error
        # Treat a validated last-known-good response as a short negative-cache
        # hit. Otherwise an unreachable provider is retried for every URL on
        # every five-minute timer run, keeping the publisher continuously busy.
        # Scientific/source timestamps live inside the artifacts and are not
        # changed by this local retry timestamp.
        os.utime(cached, None)
        print(f"WARNING: upstream fetch failed; using stale cache for {url}: {last_error}")
        return cached_body
    raise RuntimeError(f"fetch failed for {url}: {last_error}")


def fetch_json(url: str, max_age_seconds: int) -> Any:
    body = fetch_bytes(url, max_age_seconds, validator=json.loads)
    return json.loads(body)


def fetch_json_once(url: str, max_age_seconds: int) -> Any:
    """Fetch JSON with no retry at all.

    The project rule for any upstream is: respect the published cadence and
    stop on a non-200 rather than retrying. `fetch_bytes` already breaks
    immediately on 403/429 for CelesTrak; `retries=0` extends that to every
    status and to connection failures, which is the right posture for the
    NOAA and USGS index feeds - they publish on a fixed cadence, so a second
    attempt inside the same publish cycle can only ever be noise.
    """
    body = fetch_bytes(url, max_age_seconds, retries=0, validator=json.loads)
    return json.loads(body)


def fetch_text(url: str, max_age_seconds: int) -> str:
    return fetch_bytes(url, max_age_seconds).decode("utf-8", errors="replace")


def fetch_celestrak(url: str, max_age_seconds: int, **kwargs: Any) -> Any:
    """Structurally forbid direct CelesTrak access from the publisher.

    CelesTrak belongs to the VPS mirror under the LLC identity.  The publisher
    runs on bigmem under Sean's personal identity and must only read the mirror
    pulled over WireGuard.  This unconditional guard replaces the former
    environment-variable kill switch and its network fallbacks: forgetting an
    environment variable can no longer cross the identity boundary.
    """
    del max_age_seconds, kwargs
    raise RuntimeError(
        "direct CelesTrak network access is forbidden in pipeline/build_release.py; "
        f"read the VPS mirror instead: {url}"
    )


def celestrak_ledger_dir() -> Path:
    """Where bigmem writes down a group CelesTrak rejected.

    Beside the fetch cache, because that is the directory this process owns on
    every host it runs on, including a test's temporary one.
    """
    return CACHE


def note_invalid_group(error: InvalidCelestrakGroup, *, where: str) -> None:
    """Record and shout. Never raises; the caller decides what to do next."""
    row = record_invalid_group(celestrak_ledger_dir(), error, seen_by=where)
    print(
        f"INVALID CELESTRAK GROUP {error.group!r} ({where}): {error.detail}. "
        f"Body began: {error.excerpt[:120]!r}. Seen {row.get('count')} time(s); "
        "quarantined, so nothing will request it again. Remove the name from the "
        "configured list in pipeline/build_release.py."
    )


def environment_history_root() -> Path:
    """Return bigmem's durable exact-frame store, with a local bigmem fallback.

    The environment override is useful for tests and operators relocating the
    cold store.  Both defaults are on bigmem; nothing here asks the VPS to
    fetch or reduce NOAA fields.
    """
    configured = os.environ.get("SPACE_EXPLORER_ENVIRONMENT_HISTORY_ROOT")
    if configured:
        return Path(configured)
    try:
        DEFAULT_ENVIRONMENT_HISTORY_ROOT.mkdir(parents=True, exist_ok=True)
        return DEFAULT_ENVIRONMENT_HISTORY_ROOT
    except OSError as error:
        fallback = CACHE / "environment-history"
        fallback.mkdir(parents=True, exist_ok=True)
        print(f"WARNING: /mnt/d environment history is unavailable; using bigmem WSL storage: {error}")
        return fallback


def exact_frame_coverage(
    frames: Iterable[dict[str, Any]],
    *,
    requested_from: dt.datetime,
    requested_to: dt.datetime,
    stale_after_minutes: float,
) -> dict[str, Any]:
    """Describe exact-frame coverage without filling or temporally interpolating gaps."""
    requested_from = requested_from.astimezone(dt.timezone.utc)
    requested_to = requested_to.astimezone(dt.timezone.utc)
    if requested_to < requested_from:
        raise ValueError("requested coverage end precedes its start")
    if stale_after_minutes <= 0:
        raise ValueError("stale_after_minutes must be positive")

    valid_times: list[dt.datetime] = []
    for frame in frames:
        value = frame.get("validAt") if isinstance(frame, dict) else None
        if not isinstance(value, str):
            continue
        with contextlib.suppress(ValueError):
            valid_times.append(parse_time(value))
    valid_times = sorted(set(valid_times))
    if not valid_times:
        return {
            "availableFrom": None,
            "availableTo": None,
            "frameCount": 0,
            "coverageComplete": False,
            "actualCoverageHours": 0.0,
            "noDataIntervals": [{
                "from": iso_z(requested_from),
                "to": iso_z(requested_to),
                "reason": "no-exact-frames",
            }] if requested_from < requested_to else [],
        }

    allowed = dt.timedelta(minutes=stale_after_minutes)
    intervals: list[dict[str, str]] = []
    first = valid_times[0]
    if requested_from < first:
        gap_to = min(first, requested_to)
        if requested_from < gap_to:
            intervals.append({"from": iso_z(requested_from), "to": iso_z(gap_to), "reason": "before-bigmem-accumulation"})
    for previous, following in zip(valid_times, valid_times[1:]):
        gap_from = max(previous + allowed, requested_from)
        gap_to = min(following, requested_to)
        if gap_from < gap_to:
            intervals.append({"from": iso_z(gap_from), "to": iso_z(gap_to), "reason": "snapshot-gap"})
    last_end = valid_times[-1] + allowed
    if requested_to > last_end:
        gap_from = max(last_end, requested_from)
        if gap_from < requested_to:
            intervals.append({"from": iso_z(gap_from), "to": iso_z(requested_to), "reason": "after-latest-frame"})

    requested_seconds = max(0.0, (requested_to - requested_from).total_seconds())
    missing_seconds = sum((parse_time(item["to"]) - parse_time(item["from"])).total_seconds() for item in intervals)
    return {
        "availableFrom": iso_z(valid_times[0]),
        "availableTo": iso_z(valid_times[-1]),
        "frameCount": len(valid_times),
        "coverageComplete": not intervals,
        "actualCoverageHours": round(max(0.0, requested_seconds - missing_seconds) / 3600, 3),
        "noDataIntervals": intervals,
    }


def build_drap_release_bundle(
    snapshot_root: Path,
    *,
    retrieved_at: dt.datetime | None = None,
    history_hours: float = ENVIRONMENT_HISTORY_HOURS,
) -> dict[str, Any]:
    """Fetch one official D-RAP grid and merge only exact local/official frames."""
    retrieved_at = (retrieved_at or utcnow()).astimezone(dt.timezone.utc)
    current_text = fetch_text(NOAA_DRAP_CURRENT, 4 * 60)
    current_only = build_drap_bundle(current_text, retrieved_at=retrieved_at)
    requested_from = retrieved_at - dt.timedelta(hours=history_hours)
    history = load_drap_snapshot_frames(
        snapshot_root,
        start=requested_from,
        end=retrieved_at + dt.timedelta(minutes=15),
        grid=current_only["grid"],
    )
    bundle = build_drap_bundle(current_text, retrieved_at=retrieved_at, historical_frames=history)
    coverage = exact_frame_coverage(
        bundle["frames"],
        requested_from=requested_from,
        requested_to=retrieved_at,
        stale_after_minutes=float(bundle["time"]["staleAfterMinutes"]),
    )
    bundle["time"].update({
        "requestedHistoryHours": history_hours,
        "requestedFrom": iso_z(requested_from),
        "requestedTo": iso_z(retrieved_at),
        **coverage,
        "historyMethod": "exact NOAA numeric archive frames and scheduled bigmem snapshots only",
        "sourceRetentionLimited": False,
    })
    snapshot_current_drap_frame(snapshot_root, bundle)
    return bundle


def build_aurora_release_bundle(
    snapshot_root: Path,
    *,
    retrieved_at: dt.datetime | None = None,
    history_hours: float = ENVIRONMENT_HISTORY_HOURS,
) -> dict[str, Any]:
    """Fetch OVATION's latest numeric grid and merge exact bigmem snapshots."""
    retrieved_at = (retrieved_at or utcnow()).astimezone(dt.timezone.utc)
    current_payload = fetch_json(NOAA_OVATION_LATEST, 4 * 60)
    current_only = build_aurora_bundle(
        current_payload,
        retrieved_at=retrieved_at,
        history_hours=history_hours,
    )
    history = load_aurora_snapshot_frames(
        snapshot_root,
        start=retrieved_at - dt.timedelta(hours=history_hours),
        end=retrieved_at + dt.timedelta(hours=3),
        grid=current_only["grid"],
    )
    bundle = build_aurora_bundle(
        current_payload,
        retrieved_at=retrieved_at,
        historical_frames=history,
        history_hours=history_hours,
    )
    requested_seconds = max(
        0.0,
        (parse_time(bundle["time"]["requestedTo"]) - parse_time(bundle["time"]["requestedFrom"])).total_seconds(),
    )
    missing_seconds = sum(
        (parse_time(item["to"]) - parse_time(item["from"])).total_seconds()
        for item in bundle["time"]["noDataIntervals"]
    )
    bundle["time"].update({
        "actualCoverageHours": round(max(0.0, requested_seconds - missing_seconds) / 3600, 3),
        # NOAA's public machine-readable distribution is latest-only even
        # after our rolling exact-frame cache becomes complete.
        "sourceRetentionLimited": True,
    })
    snapshot_current_aurora_frame(snapshot_root, bundle)
    return bundle


def build_geospace_release_bundle(
    snapshot_root: Path,
    *,
    retrieved_at: dt.datetime | None = None,
    history_hours: float = GEOSPACE_HISTORY_HOURS,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Reduce NOAA's current SWMF/RBE window, then republish it with bigmem history.

    The live reduction is untouched: `build_geospace_bundle` still returns the
    six-frame, roughly 100-minute operational window with complete cut planes.
    Everything added here comes from frames this pipeline already reduced on an
    earlier cycle and wrote to bigmem, so no additional upstream request is made.

    The second return value is the ground magnetic perturbation bundle from the
    same run's mag_grid files, or ``None`` when that field could not be reduced.
    It is published as its OWN artifact rather than being folded into this one,
    for two reasons: nobody who has not switched the ground layer on downloads a
    byte of it, and the geospace bundle's own frames stay byte-identical, so the
    magnetosphere and radiation-belt work is not disturbed by this change.
    """
    retrieved_at = (retrieved_at or utcnow()).astimezone(dt.timezone.utc)
    bundle, ground = build_geospace_and_ground_bundles(retrieved_at)
    live_frames = list(bundle["frames"])
    radiation = geospace_radiation_fingerprint(bundle)

    requested_from = retrieved_at - dt.timedelta(hours=history_hours)
    live_from = parse_time(live_frames[0]["validAt"])
    live_to = parse_time(live_frames[-1]["validAt"])
    # The archive lives on /mnt/d, which can be full, slow, or on a machine this
    # is not running on. None of that may cost the site a geospace layer whose
    # live reduction already succeeded, so archiving degrades to the previous
    # behaviour - the live window alone, honestly labelled - rather than raising.
    stored: list[dt.datetime] = []
    archived_frames: list[dict[str, Any]] = []
    cadence = 20
    try:
        snapshot_geospace_frames(snapshot_root, bundle)
        prune_geospace_snapshots(
            snapshot_root,
            older_than=retrieved_at - dt.timedelta(hours=GEOSPACE_SNAPSHOT_RETENTION_HOURS),
        )
        archive_end = min(live_from, retrieved_at)
        stored = geospace_snapshot_times(snapshot_root)
        cadence = geospace_published_cadence_minutes(stored, start=requested_from, end=archive_end)
        archived_frames = load_geospace_snapshot_frames(
            snapshot_root,
            start=requested_from,
            end=archive_end,
            cadence_minutes=cadence,
            radiation=radiation,
        )
    except Exception as error:  # noqa: BLE001
        print(f"WARNING: geospace history unavailable; publishing the live NOAA window only: {error}")
    bundle["frames"] = merge_geospace_frames(archived_frames, live_frames)

    coverage = exact_frame_coverage(
        bundle["frames"],
        requested_from=requested_from,
        requested_to=max(retrieved_at, live_to),
        # A published frame accounts for its own cadence slot and no more. A
        # missing slot therefore reports as no data rather than being papered
        # over by the frame beside it.
        stale_after_minutes=float(cadence),
    )
    bundle["time"] = {
        "requestedHistoryHours": history_hours,
        "requestedFrom": iso_z(requested_from),
        "requestedTo": iso_z(max(retrieved_at, live_to)),
        **coverage,
        "selection": (
            "snap to the nearer published frame; the radiation belts never interpolate through "
            "time, and a missing slot on the published grid is reported as no data"
        ),
        "staleAfterMinutes": float(cadence),
        "snapRadiusMinutes": cadence / 2,
        "noDataIntervalBasis": (
            "computed by holding each published frame forward for one cadence. The browser "
            "instead snaps to the nearer frame, so an interval's width is exact but its "
            f"placement can differ by up to {cadence / 2:g} minutes."
        ),
        # NOAA NOMADS publishes only the current operational run's output, so
        # exact numeric geospace history begins with bigmem accumulation.
        "sourceRetentionLimited": True,
    }
    bundle["history"] = geospace_history_metadata(
        cadence_minutes=cadence,
        archived_count=len(archived_frames),
        live_count=len(live_frames),
        retained_snapshots=len(stored),
    )
    return bundle, ground


def derive_orbit(mean_motion: float, eccentricity: float, inclination: float) -> dict[str, Any]:
    period_seconds = 86400.0 / mean_motion
    semimajor = ((EARTH_MU_KM3_S2 * period_seconds**2) / (4 * math.pi**2)) ** (1 / 3)
    perigee = semimajor * (1 - eccentricity) - EARTH_RADIUS_KM
    apogee = semimajor * (1 + eccentricity) - EARTH_RADIUS_KM
    period_minutes = period_seconds / 60
    near_geo = 1380 <= period_minutes <= 1500
    if near_geo and eccentricity < 0.15 and inclination < 20:
        regime = "GEO"
    # INCLINED GEOSYNCHRONOUS. The exact complement of the GEO test above,
    # inside the same period/eccentricity box, so the two classes cannot drift
    # apart -- 20 deg is not a fresh threshold, it is the GEO rule's own `< 20`
    # read the other way. This branch and `classifyOrbit` in src/orbit.ts are
    # one rule written twice, and tests/test_orbit_classifier_parity.py runs
    # both over the published catalog and fails on any disagreement, because a
    # split between the artifact's `orbit` field and the client's classifier
    # would be invisible on the page.
    elif near_geo and eccentricity < 0.15 and inclination >= 20:
        regime = "IGSO"
    elif eccentricity >= 0.25 or (apogee > 40000 and perigee < 30000):
        regime = "HEO"
    elif apogee < 2000:
        regime = "LEO"
    elif perigee >= 2000 and apogee < 35000:
        regime = "MEO"
    else:
        regime = "OTHER"
    return {
        "periodMinutes": round(period_minutes, 3),
        "perigeeKm": round(perigee, 1),
        "apogeeKm": round(apogee, 1),
        "orbit": regime,
    }


# Substring containment is not name matching.
#
# This function used to be `any(pattern in name for pattern in patterns)`, and
# on 2026-08-07 that shipped a 1971 solid aluminium radar-calibration sphere,
# RIGIDSPHERE 2 (LCS 4), to the public site as "a Defense Support Program
# spacecraft using infrared sensors for strategic missile-launch warning",
# operated by the U.S. Space Force, at "high" confidence -- because "DSP" is
# inside "RIGI(DSP)HERE". The same defect made SKYTERRA 1, a geostationary
# L-band Ligado spacecraft, a NASA Earth-observing mission ("TERRA" inside
# "SKY(TERRA)"), made SWISSCUBE and AISSAT 4 human spaceflight ("ISS"), made
# ANGOSAT 2 and NIGCOMSAT 1R JAXA missions ("GOSAT", "GCOM"), and made the
# ASTROCAST IoT communications constellation a science programme ("ASTRO").
#
# A programme name is a *token*. It may start at the beginning of the name or
# after punctuation, and it may be followed by its flight number -- COSMIC2,
# FORMOSAT7 -- because upstream sometimes omits the separator. It may not be
# preceded by other letters or digits, and it may not be followed by more
# letters, because at that point it is a different word belonging to somebody
# else's programme.
_BOUNDARY_PATTERNS: dict[str, re.Pattern[str]] = {}


def name_pattern(fragment: str) -> re.Pattern[str]:
    """Compile (and cache) the token-boundary matcher for one rule fragment."""
    cached = _BOUNDARY_PATTERNS.get(fragment)
    if cached is None:
        # Rule fragments were written with fake boundaries baked in -- "GPS ",
        # "SES-", "GOES-". Those trailing characters were a workaround for the
        # missing boundary rule and they caused their own bug: CelesTrak names
        # SES spacecraft "SES 1", with a space, so "SES-" never matched any of
        # them. Strip the decoration and enforce the boundary properly.
        core = fragment.upper().strip().strip("-_/ ")
        cached = re.compile(rf"(?<![A-Z0-9]){re.escape(core)}(?![A-Z])")
        _BOUNDARY_PATTERNS[fragment] = cached
    return cached


def contains(name: str, patterns: Iterable[str]) -> bool:
    """True when any fragment appears in `name` as a whole token."""
    upper = name.upper()
    return any(name_pattern(pattern).search(upper) for pattern in patterns)


# The name tokens `classify_detailed` matches on, lifted out of the function so
# they can be COUNTED.
#
# Sean, 2026-08-19: "a rule that silently captures hundreds of objects on a
# substring is where the next COSMIC is hiding. Report the count per rule."
# That audit is impossible while the tokens are literals inside an if-chain, and
# it turned out to be worth having for a second reason: run over the live
# catalog, 27 of these 95 tokens match NOTHING AT ALL. "GPS " has never matched
# an object, because space-track names those spacecraft NAVSTAR; CHANDRA, TESS,
# FERMI, JPSS, MILSTAR and twenty more are the same. A dead rule is not
# harmless -- it is a mission this site believes it recognises and does not.
#
# `pipeline/satnogs_verify.name_rule_coverage` prints the table. These are the
# same objects the tuples always were; nothing about matching has changed.
MISSILE_WARNING_TOKENS = ("SBIRS", "DSP", "MISSILE WARNING", "OPIR")
WEATHER_TOKENS = ("GOES", "NOAA", "METOP", "METEOSAT", "HIMAWARI", "FENGYUN", "DMSP", "JPSS", "SUOMI NPP", "WEATHER", "METEOR-M", "COSMIC", "CYGNSS")
GPS_TOKENS = ("GPS ", "NAVSTAR")
NAVIGATION_TOKENS = ("GPS ", "NAVSTAR", "GALILEO", "BEIDOU", "GLONASS", "QZS", "IRNSS", "NAVIC")
MILSATCOM_TOKENS = ("AEHF", "MUOS", "WGS ", "DSCS", "MILSTAR", "UHF F/O", "SKYNET", "SICRAL", "SYRACUSE")
COMMERCIAL_COMMS_TOKENS = ("STARLINK", "ONEWEB", "IRIDIUM", "GLOBALSTAR", "INTELSAT", "GALAXY", "EUTELSAT", "EUTE", "INMARSAT", "O3B", "SES-", "VIASAT", "TELSTAR", "JCSAT", "TURKSAT", "ARABSAT", "ECHOSTAR")
CIVIL_COMMS_TOKENS = ("TDRS", "RELAY", "COMSAT", "SATCOM")
EARTH_OBSERVATION_TOKENS = ("SENTINEL", "LANDSAT", "TERRA", "AQUA", "ALOS", "GCOM", "GOSAT", "PLEIADES", "WORLDVIEW", "CARTOSAT", "RADARSAT", "GAOFEN", "YAOGAN", "KOMPSAT", "EARTHCARE", "SMAP")
HUMAN_SPACEFLIGHT_TOKENS = ("ISS", "TIANHE", "SHENZHOU", "SOYUZ-MS", "PROGRESS-MS", "CREW DRAGON")
SCIENCE_TOKENS = ("HST", "CHANDRA", "TESS", "FERMI", "NUSTAR", "SWIFT", "SWARM", "GRACE", "ICESAT", "CALIPSO", "CLOUDSAT", "ASTRO", "XRISM")
TECHNOLOGY_TOKENS = ("CUBESAT", "TECH", "DEMO", "TEST", "PATHFINDER")

#: Every one of them, in rule order, for the coverage audit.
NAME_PATTERN_MISSION_TOKENS: tuple[str, ...] = (
    MISSILE_WARNING_TOKENS + WEATHER_TOKENS + NAVIGATION_TOKENS + MILSATCOM_TOKENS
    + COMMERCIAL_COMMS_TOKENS + CIVIL_COMMS_TOKENS + EARTH_OBSERVATION_TOKENS
    + HUMAN_SPACEFLIGHT_TOKENS + SCIENCE_TOKENS + TECHNOLOGY_TOKENS
)


def classify(name: str, owner_code: str) -> tuple[str, str, str | None, str, str]:
    """Backwards-compatible five-field view of :func:`classify_detailed`."""
    return classify_detailed(name, owner_code)[:5]


def classify_detailed(name: str, owner_code: str) -> tuple[str, str, str | None, str, str, str]:
    """As `classify`, plus the *basis* on which the claim was made.

    The sixth field is the evidence class -- ``"exact-name"`` for a rule that
    matched the whole spacecraft name, ``"name-pattern"`` for a token-boundary
    programme-name match, ``"unclassified"`` when nothing fired. It is published
    so a visitor (and this project's own audit) can tell a certainty from an
    inference, which the single `classificationConfidence` string could not: a
    pattern-derived guess and a genuine unknown both used to read as text with
    no provenance attached.
    """
    upper = name.upper()
    constellation = identify_constellation(upper)

    if PWSA_TRANSPORT_NAMES.fullmatch(upper):
        return "communications", "military", "PWSA Transport Layer", "Space Development Agency", "high", "exact-name"
    if UHF_FOLLOW_ON_NAMES.fullmatch(upper):
        return "communications", "military", "UHF Follow-On (UFO)", "U.S. Navy", "high", "exact-name"
    if TACSAT_4_NAME.fullmatch(upper):
        return "communications", "military", "TacSat", "U.S. Navy / Naval Research Laboratory", "high", "exact-name"
    if upper == "ATHENA-FIDUS":
        return "communications", "military", None, "France / Italy", "high", "exact-name"
    if ASBM_NAMES.fullmatch(upper):
        return "communications", "mixed", "Arctic Satellite Broadband Mission", "Space Norway", "high", "exact-name"
    # Sources checked 2026-08-18; each states the primary mission AND the hosted
    # navigation payload, which is the same primary/secondary shape the record
    # publishes:
    #   ASTRA 5B  "Communication (Direct Broadcasting)", hosted L-band for EGNOS
    #             <https://space.skyrocket.de/doc_sdat/astra-5b.htm>
    #   GSAT-8    "Type of Satellite: Communication ... GAGAN Navigation Payload"
    #             <https://www.isro.gov.in/GSAT_8.html> (also GSAT_10, GSAT_15)
    #   LUCH 5A/B/V  "Russian follow-on relay satellites"
    #             <https://space.skyrocket.de/doc_sdat/luch-5a.htm>
    if ASTRA_5B_NAME.fullmatch(upper):
        return "communications", "commercial", None, "SES", "high", "exact-name"
    if GSAT_HOSTED_NAMES.fullmatch(upper):
        return "communications", "civil", None, "ISRO", "high", "exact-name"
    if LUCH_RELAY_NAMES.fullmatch(upper):
        return "communications", "civil", None, "Roscosmos", "high", "exact-name"
    # Everything below is a *programme name* match, now anchored on token
    # boundaries by `contains`. It is real evidence, but it is weaker than an
    # exact-name rule, so it no longer claims "high" confidence: a name pattern
    # tells you which programme the name belongs to, not that the label on the
    # card was checked against a source for this individual spacecraft.
    registry = owner_organization(upper, owner_code)
    if contains(upper, MISSILE_WARNING_TOKENS):
        return "missile-warning", "military", constellation, "U.S. Space Force", "medium", "name-pattern"
    if contains(upper, WEATHER_TOKENS):
        return "weather", "military" if "DMSP" in upper else "civil", constellation, registry, "medium", "name-pattern"
    if contains(upper, NAVIGATION_TOKENS):
        return "navigation", "military" if contains(upper, GPS_TOKENS) else "mixed", constellation, registry, "medium", "name-pattern"
    if contains(upper, MILSATCOM_TOKENS):
        return "communications", "military", constellation, registry, "medium", "name-pattern"
    # "EUTE" and "GALAXY" added 2026-08-07. space-track's own SATCAT abbreviates
    # Eutelsat spacecraft as "EUTE 172A", which no "EUTELSAT" rule can ever see
    # (23 objects); Intelsat operates the Galaxy fleet under its own name
    # (<https://www.intelsat.com/fleet/>) (15 objects). "SES-" also silently
    # never matched, because the registry writes "SES 1" with a space -- that
    # one is fixed for free by the token-boundary rule (21 objects).
    if contains(upper, COMMERCIAL_COMMS_TOKENS):
        return "communications", "commercial", constellation, registry, "medium", "name-pattern"
    if contains(upper, CIVIL_COMMS_TOKENS):
        return "communications", "civil", constellation, registry, "low", "name-pattern"
    if contains(upper, EARTH_OBSERVATION_TOKENS):
        sector = "military" if "YAOGAN" in upper else "civil"
        return "earth-observation", sector, constellation, registry, "medium", "name-pattern"
    if contains(upper, HUMAN_SPACEFLIGHT_TOKENS):
        return "human-spaceflight", "civil", constellation, registry, "medium", "name-pattern"
    # "HUBBLE" removed 2026-08-07. The Hubble *Network* is a BLE connectivity
    # constellation flying on Spire buses -- HUBBLE 6, HUBBLE 7,
    # LEMUR 2 HUBBLE-4/-5 -- and the rule called all four of them astronomy.
    # Both matches are legitimate token matches, so the boundary rule cannot
    # catch this class; only a narrower rule can. The telescope itself is
    # attached by NORAD ID 20580 and is unaffected.
    if contains(upper, SCIENCE_TOKENS):
        return "science", "civil", constellation, registry, "medium", "name-pattern"
    if contains(upper, TECHNOLOGY_TOKENS):
        return "technology", "academic" if owner_code not in {"US", "PRC", "CIS"} else "civil", constellation, registry, "low", "name-pattern"
    return "other", "unknown", constellation, registry, "low", "unclassified"


# Satellite-based augmentation systems, and the reason this list exists.
#
# CelesTrak's `gnss` group holds 170 objects. 157 are core constellation members
# — GPS, BeiDou, GLONASS (catalogued as COSMOS), Galileo — and for those, group
# membership is exactly the evidence needed: nothing in "COSMOS 2559" says
# navigation, and 28 GLONASS satellites depend on the group for their label.
#
# The other 13 are communications satellites that merely CARRY an augmentation
# transponder. GALAXY 30 is a television broadcast satellite; ASTRA 5B and the
# Eutelsats are commercial comms; the GSATs are Indian INSAT comms; the LUCHs are
# Russian relays. Calling their mission "navigation" would be wrong about what
# the spacecraft is for, and when this rule was written 7 of the 13 were
# unrecognised by name, so nothing else would have stopped it. Those 7 now have
# cited exact-name rules in `classify_detailed`, but the withholding stays: it
# is what keeps the group from overriding a primary mission, and the next hosted
# payload CelesTrak adds will again arrive with no rule of its own.
#
# CelesTrak names the hosted system inside the object name for every one of the
# 13 and for none of the 157 — "GALAXY 30 (WAAS/PRN 135)" against "GPS BIIR-5
# (PRN 22)". That annotation is the evidence, and it comes from the same file as
# the membership, so the claim and its basis travel together. Verified against
# the live group 2026-08-18.
SBAS_SYSTEMS = ("EGNOS", "WAAS", "GAGAN", "SDCM", "SOUTHPAN", "MSAS", "KASS", "BDSBAS")


def hosted_augmentation_system(object_name: str) -> str | None:
    """The augmentation system a satellite hosts, from CelesTrak's own naming."""
    upper = (object_name or "").upper()
    for system in SBAS_SYSTEMS:
        if system in upper:
            return system
    return None


@functools.lru_cache(maxsize=1)
def celestrak_hosted_augmentations() -> dict[int, str]:
    """NORAD id -> hosted augmentation system, read from the gnss group file.

    Read separately from the membership join rather than threaded through it:
    this is one extra fact about one group, and the membership plumbing has
    three read paths that would each have to carry it.
    """
    records = mirror_records("group-gnss.json")
    hosted: dict[int, str] = {}
    for record in records or []:
        if not isinstance(record, dict):
            continue
        system = hosted_augmentation_system(record.get("OBJECT_NAME", ""))
        catalog_id = record.get("NORAD_CAT_ID")
        if system and catalog_id is not None:
            hosted[int(catalog_id)] = system
    return hosted


# PARTICIPATION IS NOT IDENTITY.
#
# Some of CelesTrak's category groups answer "what system does this spacecraft
# take part in", not "what kind of spacecraft is this". Reading one as the other
# is a bulk error: it relabels every participant at once, at high confidence,
# with a card that reads perfectly.
#
# This project already knew that in two places and had not generalised it. The
# `gnss` group is withheld from spacecraft that merely HOST an augmentation
# transponder -- see `SBAS_SYSTEMS`, whose comment says withholding "is what
# stops 'GALAXY 30, mission: navigation'". And on 2026-08-19 the `stations`
# group was found putting six ISS-DEPLOYED CubeSats on the site as crewed
# spaceflight. Sean then found THEMIS A -- one of NASA's five magnetospheric
# physics spacecraft, studying substorm onset in the magnetotail -- displayed
# as CIVIL / OTHER SATCOM, because it is in CelesTrak's `tdrss` group.
#
# So the groups were MEASURED rather than argued about. For each one, take the
# members the site classified from OTHER evidence (a name rule, an exact name, a
# catalog-number rule) and ask whether they agree with what the group asserts:
#
#     group     asserts               independently classified   agree   disagree
#     sarsat    communications high            70                  0        70
#     tdrss     communications high            14                  3        11
#     argos     earth-observation med           2                  0         2
#     amateur   communications high             3                  0         3
#     ------------------------------------------------------------------------
#     science   science        high            17                 15         2
#     weather   weather        high            48                 46         2
#     resource  earth-observation med          70                 68         2
#
# The top three are not noisy, they are ABOUT SOMETHING ELSE. COSPAS-SARSAT is a
# distress-beacon relay carried on GNSS and weather satellites, so 55 of its
# members are navigation spacecraft and 15 are meteorological ones. TDRSS is
# NASA's relay network, and its group lists the network's USERS -- Hubble, the
# ISS, Terra, Aqua, Fermi, the four MMS spacecraft, THEMIS -- beside the eight
# TDRS relays themselves. ARGOS is a data-collection payload; its group is now
# dominated by the 25 Kinéis IoT nanosatellites, which relay beacon messages and
# observe nothing. `amateur` stays: an amateur-radio satellite really is a
# communications satellite, and its three disagreements are CubeSats that happen
# to carry a ham payload.
#
# The remedy is the one already used for `gnss`: withhold the group from the
# mission inference AND from the fleet fallback, and keep it in the published
# `sourceGroups`, because "this spacecraft uses TDRSS" is true, interesting, and
# simply not a mission. Withdrawing leaves "unknown", which is honest; asserting
# a different mission from the same weak signal would be the same mistake again.
#
# `stations` is the one that needs a companion rule, because a station module
# genuinely IS the thing the group names. The allowlist below is what a station
# or a station-visiting vehicle is actually called, and anything else declines
# rather than asserting. That direction matters: a name rule that ASSERTS is how
# RIGIDSPHERE 2, a 1971 aluminium radar calibration sphere, shipped as a
# missile-warning satellite; one that only declines can at worst leave a card
# saying "unknown", which is true. Verified against the live `stations` group
# 2026-08-19: 23 objects, of which 17 match and 6 do not.
PARTICIPATION_GROUPS: dict[str, str] = {
    "tdrss": (
        "NASA's Tracking and Data Relay Satellite System. The group lists the network's USERS "
        "alongside the TDRS relays; 11 of the 14 members classified from other evidence are "
        "science, Earth-observation, weather or crewed spacecraft. The relays themselves are "
        "named TDRS and are matched by name."
    ),
    "sarsat": (
        "COSPAS-SARSAT, the international distress-beacon relay. It is a hosted transponder, not "
        "a spacecraft type: 55 of its members are GNSS navigation satellites and 15 are "
        "meteorological ones, and none of the 70 agrees that it is a communications mission."
    ),
    "argos": (
        "The ARGOS data-collection system. Its members carry an ARGOS payload rather than being "
        "Earth-observation spacecraft, and the group is now dominated by the 25 Kinéis IoT "
        "nanosatellites, which relay beacon messages and observe nothing."
    ),
    "stations": (
        "Objects AT a space station, not objects that are one. It listed six CubeSats deployed "
        "from the ISS as crewed spaceflight. Station modules and visiting vehicles are recognised "
        "by name below; everything else declines to claim."
    ),
}
STATION_OR_VISITING_VEHICLE = re.compile(
    r"^(?:"
    r"ISS\b|CSS\b|"                                    # the two stations, by module
    r"ZARYA|ZVEZDA|UNITY|DESTINY|POISK|NAUKA|RASSVET|PIRS|PRICHAL|"
    r"TIANHE|WENTIAN|MENGTIAN|"
    r"PROGRESS|SOYUZ|SHENZHOU|SZ-|TIANZHOU|"             # crew and cargo ferries
    r"DRAGON|CREW DRAGON|CARGO DRAGON|CYGNUS|STARLINER|HTV|KOUNOTORI"
    r")"
)


def station_group_is_about_this_object(name: str) -> bool:
    """Is this object a station or a vehicle visiting one, rather than cargo?

    Read `False` as "we are not going to guess", not as "this is a CubeSat".
    """
    return bool(STATION_OR_VISITING_VEHICLE.match((name or "").upper().strip()))


def repair_mission_from_groups(
    mission: str, sector: str, confidence: str, source_groups: list[str]
) -> tuple[str, str, str]:
    """Resolve a still-unclassified object using CelesTrak's own category groups.

    Only called when `classify()`'s exact-named and name-pattern rules left
    mission == "other"; a name-pattern match is never overridden. Walks
    CELESTRAK_MISSION_GROUPS in order and applies the first matching group's
    (mission, sector, confidence), or leaves the input unchanged if none of the
    object's source groups appear in the table.
    """
    if mission != "other":
        return mission, sector, confidence
    for group, group_mission, group_sector, group_confidence in CELESTRAK_MISSION_GROUPS:
        if group in source_groups:
            return (group_mission if group_mission is not None else mission), group_sector, group_confidence
    return mission, sector, confidence


# Operator families, and the sector each one actually operates in.
#
# Measured 2026-08-07: six of the eight errors found by hand-verifying a random
# sample were commercial imaging operators displayed as `civil`. The cause is
# structural -- `classify()`'s earth-observation branch reads
# `"military" if YAOGAN else "civil"`, which has no way to express "a company
# sells this imagery". SKYSAT is Planet Labs, JILIN-01 is Chang Guang, HAWK is
# HawkEye 360; none of them is a civil government programme.
#
# One citation per operator family, stored beside the claim. Granularity is the
# operator, not the spacecraft, because that is the unit the fact belongs to.
# Families whose operator link could not be established are deliberately absent
# rather than guessed at -- see docs/catalog-accuracy-audit.md for the list and
# the object counts they would have covered.
#
# Each entry sets sector and operator only. It never sets a mission: a company
# being commercial says nothing about what its spacecraft does, and inventing a
# mission facet here would be the same class of error this table exists to fix.
OPERATOR_SECTORS: tuple[tuple[str, str, str, str], ...] = (
    # (name prefix, sector, operator, source)
    ("SKYSAT", "commercial", "Planet Labs", "https://www.planet.com/our-constellations/"),
    ("FLOCK", "commercial", "Planet Labs", "https://www.planet.com/our-constellations/"),
    ("DOVE", "commercial", "Planet Labs", "https://www.planet.com/our-constellations/"),
    ("JILIN", "commercial", "Chang Guang Satellite Technology", "https://www.charmingglobe.com/"),
    ("WORLDVIEW", "commercial", "Maxar", "https://www.maxar.com/products/satellite-imagery"),
    ("GEOEYE", "commercial", "Maxar", "https://www.maxar.com/products/satellite-imagery"),
    ("LEGION", "commercial", "Maxar", "https://www.maxar.com/products/satellite-imagery"),
    ("ICEYE", "commercial", "ICEYE", "https://www.iceye.com/satellite-data"),
    ("CAPELLA", "commercial", "Capella Space", "https://www.capellaspace.com/"),
    ("NUSAT", "commercial", "Satellogic", "https://satellogic.com/"),
    ("NEWSAT", "commercial", "Satellogic", "https://satellogic.com/"),
    ("BLACKSKY", "commercial", "BlackSky", "https://www.blacksky.com/"),
    ("GLOBAL", "commercial", "BlackSky", "https://www.blacksky.com/"),
    ("LEMUR", "commercial", "Spire Global", "https://spire.com/"),
    ("HAWK", "commercial", "HawkEye 360", "https://www.he360.com/"),
    ("UMBRA", "commercial", "Umbra", "https://umbra.space/"),
    ("STRIX", "commercial", "Synspective", "https://synspective.com/"),
    ("GHGSAT", "commercial", "GHGSat", "https://www.ghgsat.com/"),
    ("FIREFLY", "commercial", "Pixxel", "https://www.pixxel.space/"),
    # Not commercial: GOES-15 and GOES-14 were transferred from NOAA to the
    # U.S. Space Force and renamed. The site showed them as civil weather
    # spacecraft, which is what they used to be.
    ("EWS-G", "military", "U.S. Space Force",
     "https://www.spaceforce.mil/About-Us/Fact-Sheets/Fact-Sheet-Display/Article/3298455/eoir-weather-system-geostationary-ews-g1/"),
)


# Orbit regime vs mission.
#
# Orbits are not decorative. A spacecraft's regime constrains, hard, what it can
# be doing: you cannot resolve land cover from 35,786 km with the optics anyone
# flies, and the Earth observation that does happen from geostationary orbit is
# nearly all meteorological, which this taxonomy files under a separate mission.
#
# The site does not resolve these conflicts. It shows them.
#
# The first design withdrew the claim: a name-pattern mission contradicted by
# the object's own orbit fell back to "unclassified". Sean overruled that, and
# he was right -- it silently discards the most interesting thing in the record.
# A student learns more from "here is a claim, here is evidence that does not
# fit it, here is us declining to pretend we know" than from a card that quietly
# says nothing, and the disagreement demonstrates the very method this site
# exists to teach: that an orbit constrains what a spacecraft can be for.
#
# `annotate` is the threshold column, and it is deliberately narrow. A card
# covered in hedges teaches nothing, so an annotation appears only where the
# orbit rules the claimed mission out on physical or operational grounds -- not
# merely where the combination is unusual. The three `False` rules below are
# real audit signals but have real counter-examples in flight (Transit-heritage
# LEO navigation, LEO missile-tracking layers, GEO technology demonstrators), so
# they stay in the review queue and off the card.
#
# `strength` ranks them: 3 = no example of this exists; 2 = essentially absent
# from this regime; 1 = documented exceptions exist and are not rare.
REGIME_MISSION_RULES: tuple[tuple[str, str, str, bool, int, str], ...] = (
    (
        "GEO", "earth-observation", "review", True, 1,
        "Earth-imaging spacecraft overwhelmingly fly low, high-inclination or sun-synchronous "
        "orbits. The Earth observation that does happen from geostationary orbit is nearly all "
        "meteorological, which this taxonomy files under the separate 'weather' mission.",
    ),
    (
        "MEO", "earth-observation", "review", True, 2,
        "Imaging missions overwhelmingly use low, high-inclination or sun-synchronous orbits. "
        "Medium Earth orbit is where navigation constellations fly; it is not an imaging orbit.",
    ),
    (
        "GEO", "human-spaceflight", "contradiction", True, 3,
        "No crewed vehicle or inhabited facility operates in geostationary orbit.",
    ),
    (
        "MEO", "human-spaceflight", "contradiction", True, 3,
        "No crewed vehicle operates in medium Earth orbit; the Van Allen belts are there.",
    ),
    (
        "HEO", "human-spaceflight", "contradiction", True, 3,
        "No crewed vehicle currently operates in a highly elliptical Earth orbit.",
    ),
    (
        "GEO", "technology", "review", False, 1,
        "Technology demonstrations are usually LEO rideshares; a GEO demo claim needs a source.",
    ),
    (
        "LEO", "navigation", "review", False, 1,
        "GNSS is MEO/GEO/IGSO. LEO navigation exists (Transit/NNSS heritage, LEO-PNT "
        "demonstrators) but is unusual enough to want a source.",
    ),
    (
        "LEO", "missile-warning", "review", False, 1,
        "Legacy missile warning is GEO/HEO; LEO tracking layers are new and should be "
        "attributed to a named programme rather than inferred.",
    ),
)

# A curated `norad`/`exact` entry is exempt: a human chose that spacecraft
# deliberately and signed a source URL against the exception, which is exactly
# how GEO-KOMPSAT-2A and 2B keep their genuinely geostationary Earth-observation
# labels without a hedge. Everything weaker gets annotated.
REGIME_RULE_EXEMPT_BASES = frozenset({"norad-id", "exact-name"})

MISSION_LABELS = {
    "weather": "meteorological or environmental observation",
    "communications": "communications or data relay",
    "missile-warning": "space-based infrared missile warning",
    "navigation": "positioning, navigation, or timing",
    "earth-observation": "Earth observation",
    "science": "scientific research",
    "human-spaceflight": "crewed flight or an inhabited orbital facility",
    "technology": "technology demonstration",
    "other": "no established purpose",
}


def attribution_note(kind: str, claim: dict[str, Any], counter: dict[str, Any], position: str) -> dict[str, Any]:
    """One unresolved disagreement about what this object is.

    The same shape serves two very different sources of doubt, because they are
    the same idea: a claim, a competing signal, both attributed, no forced
    resolution. `kind` says which -- ``"contested-source"`` when two
    institutions disagree, ``"orbit-inconsistent"`` when the object's own orbit
    does not support the label its name implies.
    """
    return {"kind": kind, "claim": claim, "counter": counter, "position": position}


def regime_conflict_note(
    name: str, mission: str, basis: str, orbit_data: dict[str, Any], inclination: float
) -> dict[str, Any] | None:
    """An annotation when this object's orbit does not support its mission label."""
    if basis in REGIME_RULE_EXEMPT_BASES or mission == "other":
        return None
    for rule_orbit, rule_mission, _severity, annotate, strength, why in REGIME_MISSION_RULES:
        if not (annotate and rule_orbit == orbit_data["orbit"] and rule_mission == mission):
            continue
        regime_words = {
            "LEO": "low Earth orbit", "MEO": "medium Earth orbit",
            "GEO": "geostationary orbit", "IGSO": "an inclined geosynchronous orbit",
            "HEO": "a highly elliptical orbit",
        }.get(orbit_data["orbit"], "this orbit")
        return attribution_note(
            kind="orbit-inconsistent",
            claim={
                "value": MISSION_LABELS.get(mission, mission),
                "attributedTo": "this spacecraft's programme name",
                "source": None,
            },
            counter={
                "value": (
                    f"a {orbit_data['periodMinutes']:.0f}-minute period at "
                    f"{inclination:.0f}° inclination, {orbit_data['perigeeKm']:,.0f}-"
                    f"{orbit_data['apogeeKm']:,.0f} km, in {regime_words}. {why}"
                ),
                "attributedTo": "this object's own orbital elements",
                "source": "https://www.space-track.org/",
            },
            position=(
                "The site records the programme attribution and notes the inconsistency "
                "rather than resolving it."
            ),
            ) | {"strength": strength}
    return None


def operator_sector(name: str) -> tuple[str, str, str] | None:
    """(sector, operator, source) when a cited operator family owns this name.

    Prefix-anchored on a token boundary, the same contract as an override in
    `prefix` mode: the operator's programme name must START the spacecraft
    name. "GLOBAL" claiming BlackSky is safe for "GLOBAL-4" and cannot reach
    "GLOBALSTAR", which ends in more letters.
    """
    upper = name.upper()
    for prefix, sector, operator, source in OPERATOR_SECTORS:
        if re.match(rf"{re.escape(prefix)}(?![A-Z])", upper):
            return sector, operator, source
    return None


def owner_organization(name: str, owner_code: str) -> str:
    """The registry's own attribution. Nothing else.

    This function used to guess an operating agency from the spacecraft name.
    Audited on 2026-08-07 against the live catalog, the NASA branch alone was
    attached to nine objects and was **wrong on six of them**: TERRA SAR X is a
    German DLR/Airbus X-band radar satellite, ANGOSAT 2 is an Angolan
    geostationary comsat, and four Hubble Network CubeSats built by Spire are
    not NASA spacecraft at all. The JAXA branch caught NIGCOMSAT 1R. A rule
    that is wrong two thirds of the time does not pay for itself, and it was
    the only mechanism putting an operator name on the card that the registry
    could not back.

    Operator attribution now comes from exactly two places, both of which can
    be pointed at a source: an exact named-programme rule in `classify()`, or a
    curated entry in `data/satellite_overrides.json`. Everything else shows the
    registry owner, which is a fact rather than an inference. Where a spacecraft
    genuinely has a well-known operating agency and no curated entry, the honest
    outcome is that the site says the registry's answer and stops.
    """
    return OWNER_LABELS.get(owner_code, owner_code or "Unknown")


# What an orbit alone actually tells a visitor. These are statements about the
# orbit, which the registry does establish, not about the payload, which it does
# not. They are the honest floor: a card can always say this much.
ORBIT_EVIDENCE = {
    "LEO": "a low Earth orbit, the band used by imaging, weather, science and large broadband constellations",
    "MEO": "a medium Earth orbit, the band used by navigation constellations and some data relay",
    "GEO": "a geostationary orbit, which holds a fixed point over the equator and is what broadcast, relay and wide-area communications use",
    "IGSO": "an inclined geosynchronous orbit, at the same height as the geostationary belt and taking the same sidereal day to go round, but tilted off the equator so it traces a figure-of-eight over one region rather than holding a fixed point -- the orbit BeiDou, NavIC and QZSS use to put a navigation satellite high in the sky over Asia",
    "HEO": "a highly elliptical orbit, which dwells over high latitudes and is used for communications and space science",
    "OTHER": "an orbit that does not fall into the standard low, medium, geostationary, inclined geosynchronous or highly elliptical bands -- a stranded, transfer or above-the-belt disposal orbit, or one sitting on the boundary between two bands",
}


#: What each classification basis is, in words a reader can weigh. The template
#: description below used to say "comes from a programme-name pattern" for every
#: object alike, and on 2026-08-19 that was WRONG ON 356 OF THE 568 CARDS THAT
#: CARRIED IT: their label came from the category CelesTrak files the object
#: under, which is a different and considerably better piece of evidence than a
#: name match. A card that misstates its own evidence is the same defect class as
#: a card that misstates its mission -- the site's whole claim is that it shows
#: you what it knows and how it knows it -- and it is worse than the underlying
#: uncertainty, because a reader who checks will find the sentence untrue.
BASIS_EVIDENCE = {
    "name-pattern": (
        "comes from a programme-name pattern, not from a source checked against this spacecraft"
    ),
    "source-group": (
        "comes from the category CelesTrak files this object under, not from a source checked "
        "against this spacecraft"
    ),
    "norad-id": (
        "comes from a rule written for this catalog number, but no description of the spacecraft "
        "has been checked and cited here"
    ),
    "exact-name": (
        "comes from a rule written for this exact name, but no description of the spacecraft has "
        "been checked and cited here"
    ),
    "unclassified": (
        "has not been established from any source"
    ),
    "web-corroborated": (
        "comes from independent published sources that agree this catalog number is this "
        "spacecraft, each quoted and linked beside this record"
    ),
    # ASSESSED IS NOT DOCUMENTED, AND THE SITE MAY NOT SAY IT IS.
    #
    # Added 2026-08-20. The site's owner filtered the catalog by MILSATCOM and
    # got 101 objects, 93 of them American, and asked whether we know of no PLA
    # military communications satellites. We do. What we do not have for them is
    # the same KIND of evidence: SKYNET has a gov.uk page, Syracuse has a CNES
    # page, WGS has a Space Force fact sheet -- the operator says, in public,
    # what the spacecraft is for. Nobody publishes a fact sheet for Shentong-2,
    # for Blagovest or for Garpun. What exists is the consistent reading of
    # several independent analysts, and for Garpun a SpaceNews sentence that
    # says so in as many words: "Russian officials did not disclose the
    # satellite's mission, but outside observers believe ...".
    #
    # Flattening those two into one label would be the site claiming a certainty
    # it does not have, about exactly the objects a reader is least able to
    # check. So an assessment is published as its own basis, it is deliberately
    # NOT in the interface's `CORROBORATED_BASES`, and the card draws the same
    # dashed, dimmed, question-marked chip it draws for a bare name match --
    # while the curated sentence beside it names who is doing the assessing.
    "assessed": (
        "is an assessment by independent analysts, named and linked beside this record; no "
        "operator or government has published what this spacecraft is for"
    ),
}


# REMOVED 2026-08-20: `registry_owner_clause` and `registry_facts_clause`.
#
# Together they formatted the sentence "This object's registry record: about
# 976 km up on a 104.6-minute period, launched 1964-10-06 in launch group
# 1964-063, registered to the United States.", which an override flag appended
# to 1,205 published descriptions -- 553 of them researched, curated prose that
# it padded from behind. Every fact in it is already a row in the Satellite
# Details grid on the same screen, so the sentence restated the grid.
#
# Sean: "that sounds absolutely tacky ... just having it lead into orbit is
# fucking dumb", and the standing rule, "stop adding filler/fluff text to my
# site". This was the THIRD appearance of the defect: removed from the
# generated description, it came back through a dormant opt-in flag. The
# functions are DELETED rather than left unused for that reason -- there is now
# nothing in the pipeline that can render the grid back into prose.
#
# The underlying values are legitimate data and are untouched: perigeeKm,
# apogeeKm, periodMinutes, launchDate, launchGroup and ownerLabel still ship on
# every catalog record and the card still draws them in the Details grid.


def constellation_shell_note(
    override: dict[str, Any], inclination: float | None, registry: dict[str, Any] | None
) -> str:
    """Where in its own constellation this particular spacecraft flies.

    Sean, on the objects carrying no description: "I can google search any
    satellite I click and get details." The family paragraph is most of that
    answer, but a family paragraph repeated across 186 Guowang cards is still
    186 identical cards, and identical is what "no details" feels like.

    A shell is the cheapest per-object fact that is not already a row in the
    Details grid, and it is DERIVED, never asserted: the entry declares the shells the
    operator published, each with an inclination band and/or an altitude band,
    and this picks the one the object's own measured orbit falls inside. An
    object matching no declared shell gets no sentence, which is the honest
    outcome for a spacecraft still raising its orbit or flying somewhere the
    published architecture does not describe.

    Deliberately not a name rule. Guowang's two shells are 86.5 degrees at
    1,175 km and 50.0 degrees at 1,156 km, and NOTHING in the catalogue name
    HULIANWANG DIGUI-05 says which. The elements say it, so the elements decide.
    """
    shells = override.get("shells") or ()
    if not shells:
        return ""
    altitude = None
    if registry:
        perigee, apogee = registry.get("perigeeKm"), registry.get("apogeeKm")
        if isinstance(perigee, (int, float)) and isinstance(apogee, (int, float)):
            altitude = (perigee + apogee) / 2
    for shell in shells:
        band = shell.get("inclinationDeg")
        if band is not None:
            if inclination is None or not band[0] <= inclination <= band[1]:
                continue
        band = shell.get("altitudeKm")
        if band is not None:
            if altitude is None or not band[0] <= altitude <= band[1]:
                continue
        return str(shell.get("note") or "")
    return ""


#: A launch this size is a rideshare, and saying so is the single most useful
#: thing a card can tell a reader about an object nobody has written about.
#: Ten is deliberately low: it is under every Transporter and Bandwagon flight
#: and over every dedicated launch of a primary payload plus a few secondaries,
#: so a spacecraft only gets called a rideshare passenger when it plainly is one.
RIDESHARE_COHORT_PAYLOADS = 10


def launch_cohort_payloads(satcat_rows: Iterable[dict[str, Any]]) -> dict[str, int]:
    """How many payloads the registry still lists from each launch.

    Counted over PAYLOAD rows only, so a Falcon upper stage and eighty pieces
    of debris do not inflate the number a card quotes. It is a count of what is
    still catalogued rather than what was launched -- the registry drops decayed
    objects -- which is the honest reading of "one of 110 payloads the registry
    lists from a single launch" and is also the number that matters for traffic.
    """
    counts: dict[str, int] = {}
    for row in satcat_rows:
        if str(row.get("OBJECT_TYPE") or "").upper() != "PAYLOAD":
            continue
        group = identify_launch_group(str(row.get("OBJECT_ID") or ""))
        if group:
            counts[group] = counts.get(group, 0) + 1
    return counts


#: What every object in this class has in common, and the reason the site's
#: owner asked for this text at all: "for the ones that we don't have data on,
#: put something that makes sense ... potentially you could say what picosats
#: are in general". A small satellite almost never carries propulsion. It
#: therefore cannot be the one that moves, which is a fact about how LEO
#: traffic is actually managed and is not derivable from anything in the
#: Details grid. Sean, on this clause: "yes the operational hook you mentioned
#: is awesome."
CANNOT_MANOEUVRE = (
    "Objects this size almost never carry propulsion, so in a close approach they cannot be "
    "the one that moves."
)


def template_purpose(
    name: str,
    mission: str,
    sector: str,
    orbit: str,
    basis: str = "name-pattern",
    registry: dict[str, Any] | None = None,
    cohort_payloads: int | None = None,
) -> str:
    """The description shown when nothing authoritative names this spacecraft.

    REWRITTEN 2026-08-20, twice in one night, and the second rewrite is the one
    that matters. The first replaced an apology-led sentence with a fact-led
    one -- the gap in seven words, then the registry's own record. Measured on a
    finished card, that record turned out to be six facts (orbit class,
    altitude, period, launch date, launch group, registering state) EVERY ONE OF
    WHICH was already in the Details grid on the same screen. Sean: "that sounds
    absolutely tacky. Saying 'we don't have it in the catalog but we do have...'
    and just having it lead into orbit is fucking dumb", and, standing:
    "stop adding filler/fluff text to my site."

    So the test here is not "is this true" -- the registry clause was perfectly
    true -- but "does this tell the reader something the grid does not already
    show". What the grid cannot express is WHAT KIND OF THING THIS IS, and for
    the fifty-odd objects that reach this function that is a genuinely
    interesting answer that most readers do not know:

      - a modern rideshare carries a hundred-plus spacecraft at once, and the
        registry says how many;
      - most of the small ones are university, start-up or company payloads
        whose operators publish nothing, so the absence of a description is a
        fact about the catalogue rather than a hole in this site;
      - the catalogue NAME is frequently a dispenser slot or a builder's serial
        rather than a mission name, which is why searching for it finds nothing;
      - and almost none of them can manoeuvre.

    The admission is kept and kept FIRST -- "no public source names this
    spacecraft's payload" -- because it is true and because burying it would be
    the same failure in the other direction. It simply stops being the whole
    paragraph.

    Nothing here asserts a mission, an operator or an instrument, which is the
    property test_no_template_description_names_an_agency_or_an_instrument pins.
    `mission`, `sector` and `basis` are still taken because every caller has
    them; the hedge they used to carry lives on the card's category chip, which
    draws dashed and dimmed for exactly these objects.

    The lifetime clause is NOT added here. It is appended in `build_catalog`
    from the object's own tracked orbit, because it needs the element-set
    archive and because it is absent for anything too new or too heavily
    station-kept to measure -- see pipeline/orbital_lifetime.py.
    """
    if orbit != "LEO":
        # Nothing in the catalogue reaches this today. A small satellite that is
        # not in low Earth orbit is a different animal from a rideshare
        # passenger and must not inherit its paragraph, so it gets the honest
        # floor: what the orbit itself establishes, and nothing else.
        hint = ORBIT_EVIDENCE.get(orbit, ORBIT_EVIDENCE["OTHER"])
        return (
            "No public source names this spacecraft's payload, so this site does not claim one. "
            f"What is established is its orbit: {hint}."
        )
    if cohort_payloads and cohort_payloads >= RIDESHARE_COHORT_PAYLOADS:
        return (
            "No public source names this spacecraft's payload, which is ordinary for its class: "
            f"it is one of {cohort_payloads} payloads the registry lists from a single launch, and "
            "small rideshare passengers are mostly university, start-up or company projects whose "
            "operators publish nothing \u2014 the catalogue name is often a dispenser slot or a "
            f"builder's serial rather than a mission name. {CANNOT_MANOEUVRE}"
        )
    return (
        "No public source names this spacecraft's payload. Small satellites in this band are flown "
        "in quantity by universities, start-ups and national agencies for technology demonstration, "
        "store-and-forward messaging and amateur radio, and most such operators publish nothing "
        "beyond a launch announcement \u2014 the catalogue name is frequently a builder's serial "
        f"rather than a mission name. {CANNOT_MANOEUVRE}"
    )


# How an override is allowed to attach itself to a spacecraft.
#
# "norad"  - an explicit list of NORAD catalog IDs. The only mechanism that
#            cannot be wrong, and the only one permitted to state instruments,
#            operators or objectives for an individual spacecraft.
# "exact"  - the whole spacecraft name, exactly. TERRA is one satellite; without
#            this mode the TERRA entry also claimed TERRA SAR X and SKYTERRA 1.
# "prefix" - the programme name at the START of the name, on a token boundary.
#            For genuine families (STARLINK-37189, GOES 16, BEIDOU 3M4) where
#            every member shares the description. Never for an individual.
# "token"  - the programme name anywhere in the name, on a token boundary.
#            Needed because the registry names Russian navigation spacecraft
#            "COSMOS 2501 (GLONASS)": the programme name is real, it is simply
#            not at the front. Weakest family mode; never for an individual.
OVERRIDE_MATCH_MODES = ("norad", "exact", "prefix", "token")
#
# Confidence deliberately does NOT read (high, medium, low, low) straight down
# this list. `classificationBasis` is published alongside it and already carries
# the mechanism losslessly, which frees `classificationConfidence` to mean what a
# visitor reads it as: how much to trust the label. An anchored token-boundary
# match on an unambiguous programme name -- STARLINK-37189, GOES 16 -- is not a
# guess, and grading it "low" would put it level with RIGIDSPHERE 2, about which
# the site knows nothing at all. That would make the weakest signal on the card
# the least informative one. Raise these to match the mechanism exactly if that
# tradeoff is ever decided the other way; it is a one-line change.
OVERRIDE_MATCH_CONFIDENCE = {"norad": "high", "exact": "high", "prefix": "medium", "token": "medium"}


def override_classification(
    override: dict[str, Any],
    match_kind: str,
    basis: str,
    confidence: str,
) -> tuple[str, str]:
    """What an override match is allowed to say about the MISSION LABEL.

    `classificationBasis` and `classificationConfidence` describe how the
    mission label was arrived at, and the card turns them into a chip: solid
    means corroborated, dashed and dimmed with a question mark means claimed.

    An override that supplies a mission or a description has established that
    label, so the chip may report the mechanism that matched -- a catalogue
    number is exact and deserves to say so. An override that supplies ONLY an
    operator attribution has established no such thing: the mission label still
    came from wherever it came from before, usually a name pattern. Promoting
    the basis on the strength of an operator line puts a solid, confident chip
    above a description that says no public source names the payload, which is
    the Tianmu-1 11 contradiction wearing a different hat.

    It was live. SMAP carried an operator-only entry keyed on catalogue number
    40376 and shipped `norad-id` at `high` beside "No public source names this
    spacecraft's payload, ...". Returned unchanged, the pair says the honest
    thing: the object was matched, the mission was not established.
    """
    if not (override.get("purpose") or override.get("mission")):
        return basis, confidence
    return (
        {"norad": "norad-id", "exact": "exact-name"}.get(match_kind, "name-pattern"),
        OVERRIDE_MATCH_CONFIDENCE[match_kind],
    )

#: Where curated override tables live. The base file, plus one file per
#: partition of the catalog.
OVERRIDES_DIR = ROOT / "data"
OVERRIDES_BASE = OVERRIDES_DIR / "satellite_overrides.json"
OVERRIDES_GLOB = "satellite_overrides_*.json"


def load_overrides(directory: Path | None = None) -> dict[str, Any]:
    """The curated override table: the base file plus every partition file.

    Writing descriptions for eight thousand objects is work that gets split up,
    and when four people write into one JSON file at once every entry is a
    merge conflict. So a partition lands as its own
    ``data/satellite_overrides_<partition>.json`` and this globs them together.
    Nothing needs re-wiring when the next partition appears, which is the point:
    the alternative is four edits to this line, three of which conflict.

    The base file wins a key collision, and says so on the way past. Refusing
    outright would wedge the five-minute publish timer on a duplicate key --
    turning a safety gate into an outage, which is how safety gates get deleted.
    The duplicate is caught in CI instead, by
    ``test_no_override_key_is_defined_in_two_files``.
    """
    directory = directory or OVERRIDES_DIR
    base = directory / OVERRIDES_BASE.name
    merged: dict[str, Any] = json.loads(base.read_text()) if base.is_file() else {}
    origin: dict[str, str] = dict.fromkeys(merged, base.name)
    for path in sorted(directory.glob(OVERRIDES_GLOB)):
        for key, entry in json.loads(path.read_text()).items():
            if key in merged:
                print(
                    f"NOTE: override {key!r} in {path.name} is ignored; "
                    f"{origin[key]} already defines it"
                )
                continue
            merged[key] = entry
            origin[key] = path.name
    return merged


def validate_overrides(overrides: dict[str, Any]) -> None:
    """Refuse an override table that can attach a specific claim by accident.

    Deliberately raises rather than warning. A description naming an agency and
    its instruments is the single highest-consequence string this pipeline
    emits, and the failure it guards against -- an `individual: true` entry
    spreading across a family by substring -- is exactly what put a NASA
    Earth-science paragraph on SKYTERRA 1.
    """
    for key, entry in overrides.items():
        mode = entry.get("match", "prefix")
        if mode not in OVERRIDE_MATCH_MODES:
            raise ValueError(f"override {key!r}: unknown match mode {mode!r}")
        if mode == "norad" and not entry.get("norad"):
            raise ValueError(f"override {key!r}: match=norad requires a non-empty 'norad' list")
        if entry.get("individual") and mode in {"prefix", "token"}:
            raise ValueError(
                f"override {key!r}: an individual spacecraft description may not attach by {mode}; "
                "use match=norad (preferred) or match=exact"
            )
        # A paragraph asserting an operator, an instrument or an objective is
        # the highest-consequence string this pipeline emits. It does not ship
        # without somewhere a reader can go to check it.
        if entry.get("purpose") and not str(entry.get("source") or "").startswith("http"):
            raise ValueError(
                f"override {key!r}: a curated description must carry a 'source' URL"
            )
        # An assessment must say WHOSE it is. The whole point of the class is
        # that the reader can weigh who is doing the assessing, so an entry that
        # claims the weaker evidence class without naming its analyst is refused
        # rather than published as an anonymous hedge.
        evidence = entry.get("evidence")
        if evidence is not None and evidence != "assessed":
            raise ValueError(
                f"override {key!r}: unknown evidence class {evidence!r}; only 'assessed' exists"
            )
        if evidence == "assessed":
            graded = entry.get("assessedConfidence")
            if graded is not None and graded not in {"medium", "low"}:
                raise ValueError(
                    f"override {key!r}: assessedConfidence must be 'medium' or 'low'; "
                    f"got {graded!r}. An assessed claim cannot promote itself to 'high'."
                )
            if not str(entry.get("assessedBy") or "").strip():
                raise ValueError(
                    f"override {key!r}: an assessed entry must name who assesses it in 'assessedBy'"
                )
            if not str(entry.get("source") or "").startswith("http"):
                raise ValueError(
                    f"override {key!r}: an assessed entry must carry a 'source' URL"
                )
        # A declared shell is published prose selected by the object's own
        # measured orbit. A malformed band would either select nothing (a
        # silent gap) or everything (the wrong sentence on the wrong card), so
        # the shape is checked here rather than discovered on a card.
        for shell in entry.get("shells") or ():
            if not isinstance(shell, dict) or not str(shell.get("note") or "").strip():
                raise ValueError(f"override {key!r}: every shell needs a 'note'")
            bands = [
                band
                for band in (shell.get("inclinationDeg"), shell.get("altitudeKm"))
                if band is not None
            ]
            if not bands:
                raise ValueError(
                    f"override {key!r}: a shell must be selected by 'inclinationDeg' or "
                    "'altitudeKm'; a shell that matches everything is not a shell"
                )
            for band in bands:
                if (
                    not isinstance(band, list)
                    or len(band) != 2
                    or not all(isinstance(edge, (int, float)) for edge in band)
                    or band[0] >= band[1]
                ):
                    raise ValueError(f"override {key!r}: shell band {band!r} must be [low, high]")
        # Both fields EXTEND a description. Silently doing nothing when there is
        # nothing to extend is how a card ends up missing the per-object clause
        # that was the whole point of the entry.
        if entry.get("shells") and not entry.get("purpose"):
            raise ValueError(
                f"override {key!r}: 'shells' extends a description; there is none to extend"
            )
        # RETIRED 2026-08-20, and refused rather than ignored. A dormant
        # opt-in flag is exactly how this sentence came back the first time:
        # it was removed from the generated description, then reappeared
        # through this override on ten times as many cards. An entry still
        # carrying it fails the build with the reason, so the next person to
        # copy an old entry finds out here instead of on 1,205 cards.
        if "appendRegistryFacts" in entry:
            raise ValueError(
                f"override {key!r}: 'appendRegistryFacts' is retired. It appended "
                "the object's altitude, period, launch date, launch-group and "
                "registering state to the description -- every one of which is "
                "already a row in the Satellite Details grid on the same screen. "
                "Delete the flag; the facts stay in the data and on the grid."
            )
        contested = entry.get("contestedAttribution")
        if contested is None:
            continue
        if not isinstance(contested, dict):
            raise ValueError(f"override {key!r}: contestedAttribution must be an object")
        for side in ("recorded", "alternate"):
            claim = contested.get(side)
            if not isinstance(claim, dict):
                raise ValueError(f"override {key!r}: contestedAttribution.{side} is missing")
            for field in ("value", "attributedTo", "source"):
                if not str(claim.get(field) or "").strip():
                    raise ValueError(
                        f"override {key!r}: contestedAttribution.{side}.{field} is required"
                    )
            if not str(claim["source"]).startswith("http"):
                raise ValueError(
                    f"override {key!r}: contestedAttribution.{side}.source must be a URL"
                )


def contested_caveat(notes: list[dict[str, Any]]) -> str:
    """The visible caveat prose, generated from the structured notes.

    Generated rather than hand-written for two reasons. The prose and the
    machine-readable field can then never drift apart, and the next contested
    object inherits the wording instead of needing new copy.

    It is also deliberate belt-and-braces: `contestedAttribution` is published
    for the interface to render properly, but until it does, this prose is the
    only thing the reader sees. A caveat that exists only in a field nothing
    renders is not a caveat.
    """
    parts: list[str] = []
    for note in notes:
        claim, counter = note["claim"], note["counter"]
        if note["kind"] == "contested-source":
            parts.append(
                f" This attribution is contested: {counter['attributedTo']} characterises it as "
                f"{counter['value']}, while {claim['attributedTo']} assesses it as "
                f"{claim['value']}. {note['position']}"
            )
        else:
            parts.append(
                f" One note on the evidence: the programme name is associated with "
                f"{claim['value']}, but this object flies {counter['value']} "
                f"{note['position']}"
            )
    return "".join(parts)


def matching_override(
    name: str, overrides: dict[str, Any], norad_id: int | None = None
) -> tuple[dict[str, Any], str] | None:
    """Find the override for this spacecraft, and how strongly it matched.

    Was ``if fragment.upper() in upper``. That is how ``"TERRA"`` claimed
    ``"SKYTERRA 1"``. Matching is now explicit about the strength of the claim,
    and the strength is published as the record's confidence rather than being
    hard-coded to "high" for every override alike.
    """
    upper = name.upper()
    matches: list[tuple[int, dict[str, Any], str]] = []
    for fragment, override in overrides.items():
        mode = override.get("match", "prefix")
        if mode == "norad":
            if norad_id is not None and norad_id in set(override.get("norad", ())):
                matches.append((0, override, "norad"))
            continue
        if mode == "exact":
            names = {str(value).upper() for value in override.get("names", (fragment,))}
            if upper in names:
                matches.append((1, override, "exact"))
            continue
        # prefix: the programme name must START the spacecraft name, on a token
        # boundary. Anchoring at the start is a second, independent guard: even
        # if the boundary rule were later loosened, SKYTERRA 1 still cannot
        # match TERRA, because it does not begin with it.
        core = fragment.upper().strip().strip("-_/ ")
        if mode == "prefix":
            if re.match(rf"{re.escape(core)}(?![A-Z])", upper):
                matches.append((2, override, "prefix"))
            continue
        if name_pattern(core).search(upper):
            matches.append((3, override, "token"))
    if not matches:
        return None
    matches.sort(key=lambda item: item[0])
    return matches[0][1], matches[0][2]


# Where the VPS-side polite mirror drops its files after rsync.  This is the
# publisher's ONLY CelesTrak input.  There is no environment-controlled network
# fallback: bigmem must remain incapable of contacting CelesTrak even when the
# mirror is missing, incomplete, or stale.
CELESTRAK_MIRROR = Path(
    os.environ.get("SPACE_EXPLORER_CELESTRAK_MIRROR", str(ROOT / "runtime" / "celestrak-mirror"))
)


# ---------------------------------------------------------------------------
# space-track.org, mirrored by ingest/spacetrack_ingest.py on bigmem ONLY.
#
# USSPACECOM grants express blanket approval to redistribute basic SSA data -
# TLEs/OMMs, SATCAT, and decay data - "conditioned on appropriate citation", so
# the published artifact must always carry the citation below.
# ---------------------------------------------------------------------------
SPACETRACK_MIRROR = Path(
    os.environ.get("SPACE_EXPLORER_SPACETRACK_MIRROR", str(ROOT / "runtime" / "spacetrack-mirror"))
)

# space-track returns every value as a string; CelesTrak returns numbers. The
# published artifact must not change shape depending on which upstream fed it,
# so the numeric OMM fields are coerced back to numbers here.
_OMM_NUMERIC = (
    "MEAN_MOTION", "ECCENTRICITY", "INCLINATION", "RA_OF_ASC_NODE",
    "ARG_OF_PERICENTER", "MEAN_ANOMALY", "BSTAR", "MEAN_MOTION_DOT",
    "MEAN_MOTION_DDOT", "EPHEMERIS_TYPE", "NORAD_CAT_ID", "ELEMENT_SET_NO",
    "REV_AT_EPOCH",
)

# space-track's SATCAT uses different names for two fields we actually read.
# Missing this mapping silently blanks every owner and launch date.
_SATCAT_ALIASES = {"COUNTRY": "OWNER", "LAUNCH": "LAUNCH_DATE"}


def _coerce_number(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    try:
        return int(value) if value.lstrip("-").isdigit() else float(value)
    except ValueError:
        return value


def normalise_gp_record(record: dict[str, Any]) -> dict[str, Any]:
    normalised = dict(record)
    for key in _OMM_NUMERIC:
        if key in normalised:
            normalised[key] = _coerce_number(normalised[key])
    return normalised


def normalise_satcat_record(record: dict[str, Any]) -> dict[str, Any]:
    normalised = dict(record)
    for source, target in _SATCAT_ALIASES.items():
        if target not in normalised and source in normalised:
            normalised[target] = normalised[source]
    return normalised


def spacetrack_records(name: str) -> list[dict[str, Any]] | None:
    path = SPACETRACK_MIRROR / name
    if not path.exists():
        return None
    try:
        records = json.loads(path.read_bytes())
    except (OSError, json.JSONDecodeError) as error:
        print(f"WARNING: mirrored space-track file {name} is unreadable: {error}")
        return None
    return records if isinstance(records, list) else None


# ---------------------------------------------------------------------------
# Jonathan McDowell's GCAT, mirrored by ingest/gcat_mirror.py.
#
# ONE fact is read from it: the country the spacecraft's OPERATOR belongs to.
#
# The catalog's existing country comes from space-track's SATCAT `COUNTRY`
# column, renamed to `OWNER` by `_SATCAT_ALIASES` above. That column is the
# state the object is ATTRIBUTED to in the registry, which for a rideshare
# smallsat is routinely whoever filed the paperwork -- very often the
# integrator, not the operator. It tracks the BUILDER, mechanically:
# IdeiaSpace -> BRAZ, ISISPACE -> NETH, OHB Sweden -> SWED, ZfT -> GER,
# U-Space -> FR, EnduroSat -> BGR. Live on 2026-08-20: SARI-1 and SARI-2
# (Saudi) read Brazil, LEONAV-1 (UAE) read France, CLOUDCT-PRECURSOR
# (Israeli) read Germany, GARAI-B (Spanish) read Sweden.
#
# That value is not WRONG as a registry fact and it is not overwritten here.
# It is simply not the operator's country, and the site had no second field to
# put the operator's country in, so a reader filtering the catalog by country
# found a Saudi spacecraft under Brazil. GCAT keeps `Owner`, `State` and
# `Manufacturer` as three separate columns, which is exactly the distinction
# being lost.
# ---------------------------------------------------------------------------
GCAT_MIRROR = Path(os.environ.get("SPACE_EXPLORER_GCAT_MIRROR", str(ROOT / "runtime" / "gcat-mirror")))

#: GCAT's state codes, in this site's own country vocabulary so that the owner
#: facet does not split one country across two spellings. Same doctrine as
#: OWNER_LABELS: a code whose expansion is not unambiguous is NOT guessed at --
#: it is left out, the object publishes no operator country, and the card says
#: the registry's answer and stops.
#:
#: ESIB (Islas Baleares) is GCAT's sub-national code for a Spanish autonomous
#: community and maps to Spain: the entry exists because GCAT records where the
#: operating university sits, not because the Balearics register spacecraft.
GCAT_STATE_LABELS = {
    "US": "United States",
    "CN": "People's Republic of China",
    "RU": "Russian Federation",
    "SU": "Soviet Union",
    "UK": "United Kingdom",
    "J": "Japan",
    "F": "France",
    "I": "Italy",
    "IN": "India",
    "D": "Germany",
    "CA": "Canada",
    "KR": "Republic of Korea",
    "KP": "Democratic People's Republic of Korea",
    "E": "Spain",
    "ESIB": "Spain",
    "TR": "Türkiye",
    "AU": "Australia",
    "NZ": "New Zealand",
    "TW": "Taiwan",
    "L": "Luxembourg",
    "BR": "Brazil",
    "N": "Norway",
    "S": "Sweden",
    "DK": "Denmark",
    "FI": "Finland",
    "SA": "Saudi Arabia",
    "UAE": "United Arab Emirates",
    "QA": "Qatar",
    "KW": "Kuwait",
    "BH": "Bahrain",
    "JO": "Jordan",
    "IL": "Israel",
    "IR": "Iran",
    "EG": "Egypt",
    "MA": "Morocco",
    "DZ": "Algeria",
    "NG": "Nigeria",
    "ZA": "South Africa",
    "RW": "Rwanda",
    "AO": "Angola",
    "BW": "Botswana",
    "DJ": "Djibouti",
    "MU": "Mauritius",
    "GR": "Greece",
    "CH": "Switzerland",
    "AT": "Austria",
    "B": "Belgium",
    "NL": "Netherlands",
    "PL": "Poland",
    "CZ": "Czechia",
    "SK": "Slovakia",
    "SI": "Slovenia",
    "HR": "Croatia",
    "HU": "Hungary",
    "RO": "Romania",
    "BGN": "Bulgaria",
    "UA": "Ukraine",
    "BY": "Belarus",
    "LT": "Lithuania",
    "P": "Portugal",
    "IE": "Ireland",
    "MC": "Monaco",
    "HK": "Hong Kong",
    "SG": "Singapore",
    "ID": "Indonesia",
    "MY": "Malaysia",
    "T": "Thailand",
    "VN": "Viet Nam",
    "PH": "Philippines",
    "BD": "Bangladesh",
    "PK": "Pakistan",
    "LA": "Laos",
    "KZ": "Kazakhstan",
    "AZ": "Azerbaijan",
    "MX": "Mexico",
    "AR": "Argentina",
    "CL": "Chile",
    "PE": "Peru",
    "EC": "Ecuador",
    "BO": "Bolivia",
    "UY": "Uruguay",
    "VE": "Venezuela",
    "PG": "Papua New Guinea",
    "SB": "Solomon Islands",
    "BM": "Bermuda",
    "I-EU": "European Union",
    "I-ESA": "European Space Agency",
    "I-EUM": "EUMETSAT",
    "I-INM": "Inmarsat",
    "I-ARAB": "Arab Satellite Communications Organization",
    "I-RASC": "RascomStar-QAF",
    # States GCAT records elsewhere in its 70,000 rows. Listed so that a future
    # launch does not silently lose its operator country -- and so this table's
    # "unknown code" NOTE stays a signal instead of printing on every cycle.
    "AM": "Armenia",
    "BT": "Bhutan",
    "CO": "Colombia",
    "CR": "Costa Rica",
    "CSFR": "Czechoslovakia",
    "CSSR": "Czechoslovakia",
    "CYM": "Cayman Islands",
    "EE": "Estonia",
    "ET": "Ethiopia",
    "GH": "Ghana",
    "GT": "Guatemala",
    "HKUK": "Hong Kong",
    "KE": "Kenya",
    "LK": "Sri Lanka",
    "LV": "Latvia",
    "MD": "Moldova",
    "ME": "Montenegro",
    "MN": "Mongolia",
    "MYM": "Myanmar",
    "NP": "Nepal",
    "PR": "Puerto Rico",
    "PY": "Paraguay",
    "SD": "Sudan",
    "SN": "Senegal",
    "TN": "Tunisia",
    "UG": "Uganda",
    "ZW": "Zimbabwe",
    "I-ESRO": "European Space Research Organisation",
    "I-EUT": "Eutelsat",
    "I-INT": "Intelsat",
    "I-NATO": "NATO",
}


#: When the registry's code and GCAT's state code name the SAME attribution.
#:
#: Both catalogues use their own abbreviations, and most of the time they are
#: saying the same thing in different letters -- the registry writes BRAZ and
#: GCAT writes BR. Without this table every one of those would look like a
#: disagreement and the card would carry two rows saying "Brazil" and "Brazil",
#: which implies two sources corroborating each other when there is only one
#: fact. So an operator country is published ONLY where it falls outside the
#: set here.
#:
#: Two entries are judgements rather than translations, and are written down as
#: such:
#:
#: CIS  covers RU and SU. The registry's CIS is a bloc, and Russia is what it
#:      means in practice; a CIS-coded object whose operator GCAT places in
#:      UKRAINE, BELARUS or KAZAKHSTAN is a real difference and still shows.
#: ESA  covers both I-ESA and I-EU. The site's one "European Space Agency"
#:      label is read by both, and the Galileo and Copernicus spacecraft that
#:      the EU owns and ESA procures already say so in their curated operator.
#:
#: A registry code that is NOT here and NOT in REGISTRY_CODES_NOT_A_COUNTRY is
#: a code nobody has decided about, which `test_every_registry_code_is_decided`
#: refuses. That is deliberate: falling through to a default is how a new
#: country code would quietly start publishing a second row that says nothing.
REGISTRY_COUNTRY_EQUIVALENTS = {
    "US": frozenset({"United States"}),
    "PRC": frozenset({"People's Republic of China"}),
    "CHBZ": frozenset({"People's Republic of China", "Brazil"}),
    "UK": frozenset({"United Kingdom"}),
    "CIS": frozenset({"Russian Federation", "Soviet Union"}),
    "JPN": frozenset({"Japan"}),
    "IT": frozenset({"Italy"}),
    "FR": frozenset({"France"}),
    "FRIT": frozenset({"France", "Italy"}),
    "IND": frozenset({"India"}),
    "ISRO": frozenset({"India"}),
    "GER": frozenset({"Germany"}),
    "ESA": frozenset({"European Space Agency", "European Union"}),
    "CA": frozenset({"Canada"}),
    "SPN": frozenset({"Spain"}),
    "SKOR": frozenset({"Republic of Korea"}),
    "NKOR": frozenset({"Democratic People's Republic of Korea"}),
    "TURK": frozenset({"Türkiye"}),
    "AUS": frozenset({"Australia"}),
    "TWN": frozenset({"Taiwan"}),
    "NOR": frozenset({"Norway"}),
    "BRAZ": frozenset({"Brazil"}),
    "UAE": frozenset({"United Arab Emirates"}),
    "SAUD": frozenset({"Saudi Arabia"}),
    "SING": frozenset({"Singapore"}),
    "STCT": frozenset({"Singapore"}),
    "BEL": frozenset({"Belgium"}),
    "ARGN": frozenset({"Argentina"}),
    "GREC": frozenset({"Greece"}),
    "GRSA": frozenset({"Greece"}),
    "INDO": frozenset({"Indonesia"}),
    "EGYP": frozenset({"Egypt"}),
    "POL": frozenset({"Poland"}),
    "ISRA": frozenset({"Israel"}),
    "THAI": frozenset({"Thailand"}),
    "SWTZ": frozenset({"Switzerland"}),
    "BGR": frozenset({"Bulgaria"}),
    "BUL": frozenset({"Bulgaria"}),
    "RWA": frozenset({"Rwanda"}),
    "LUXE": frozenset({"Luxembourg"}),
    "POR": frozenset({"Portugal"}),
    "IRAN": frozenset({"Iran"}),
    # GCAT has no Iraqi state code at all: the one IRAQ-registered object in
    # this catalog is TIGRISAT, which GCAT places in ITALY after the Politecnico
    # di Torino group that built and flies it. Empty rather than {"Iraq"},
    # because an equivalence naming a country GCAT can never write is a rule
    # that cannot fire -- and `test_every_equivalence_names_a_country_the_state
    # _table_can_produce` caught exactly that when this line said {"Iraq"}.
    "IRAQ": frozenset(),
    "ALG": frozenset({"Algeria"}),
    "KAZ": frozenset({"Kazakhstan"}),
    "PAKI": frozenset({"Pakistan"}),
    "MEX": frozenset({"Mexico"}),
    "DEN": frozenset({"Denmark"}),
    "MALA": frozenset({"Malaysia"}),
    "MA": frozenset({"Morocco"}),
    "FIN": frozenset({"Finland"}),
    "SWED": frozenset({"Sweden"}),
    "NETH": frozenset({"Netherlands"}),
    "HUN": frozenset({"Hungary"}),
    "VTNM": frozenset({"Viet Nam"}),
    "NIG": frozenset({"Nigeria"}),
    "AZER": frozenset({"Azerbaijan"}),
    "LTU": frozenset({"Lithuania"}),
    "CHLE": frozenset({"Chile"}),
    "VENZ": frozenset({"Venezuela"}),
    "ASRA": frozenset({"Austria"}),
    "AUT": frozenset({"Austria"}),
    "ECU": frozenset({"Ecuador"}),
    "QAT": frozenset({"Qatar"}),
    "SAFR": frozenset({"South Africa"}),
    "CZE": frozenset({"Czechia"}),
    "CZCH": frozenset({"Czechia"}),
    "BOL": frozenset({"Bolivia"}),
    "UKR": frozenset({"Ukraine"}),
    "TMMC": frozenset({"Monaco"}),
    "LAOS": frozenset({"Laos"}),
    "BELA": frozenset({"Belarus"}),
    "PER": frozenset({"Peru"}),
    "PERU": frozenset({"Peru"}),
    "BGD": frozenset({"Bangladesh"}),
    "RP": frozenset({"Philippines"}),
    "JOR": frozenset({"Jordan"}),
    "SVN": frozenset({"Slovenia"}),
    "AGO": frozenset({"Angola"}),
    "ANG": frozenset({"Angola"}),
    "KWT": frozenset({"Kuwait"}),
    "HRV": frozenset({"Croatia"}),
    "DJI": frozenset({"Djibouti"}),
    "BWA": frozenset({"Botswana"}),
    "BHR": frozenset({"Bahrain"}),
    "SLB": frozenset({"Solomon Islands"}),
    "NZ": frozenset({"New Zealand"}),
    "ROM": frozenset({"Romania"}),
    "SVK": frozenset({"Slovakia"}),
    "LKA": frozenset({"Sri Lanka"}),
    "SEN": frozenset({"Senegal"}),
    "KEN": frozenset({"Kenya"}),
    "TUN": frozenset({"Tunisia"}),
    "EST": frozenset({"Estonia"}),
    "LVA": frozenset({"Latvia"}),
    "COL": frozenset({"Colombia"}),
    "CRI": frozenset({"Costa Rica"}),
    "URY": frozenset({"Uruguay"}),
    "PRY": frozenset({"Paraguay"}),
    "ETH": frozenset({"Ethiopia"}),
    "GHA": frozenset({"Ghana"}),
    "MNG": frozenset({"Mongolia"}),
    "NPL": frozenset({"Nepal"}),
    "BTN": frozenset({"Bhutan"}),
    "ZWE": frozenset({"Zimbabwe"}),
    "UGA": frozenset({"Uganda"}),
    "SUDN": frozenset({"Sudan"}),
    "ARM": frozenset({"Armenia"}),
    "MDA": frozenset({"Moldova"}),
    "MNE": frozenset({"Montenegro"}),
}

#: Registry codes that name an ORGANISATION, not a country. For these the site
#: has never had a country at all -- the "Country / registry" row said "SES",
#: "Intelsat", "O3b / SES" -- so an operator country is new information rather
#: than a contradiction, and it is published whenever GCAT has one.
REGISTRY_CODES_NOT_A_COUNTRY = frozenset({
    "SES", "ITSO", "EUTE", "GLOB", "IM", "O3B", "AC", "ABS", "AB", "EUME",
    "RASC", "IRID", "NATO", "ISS", "NICO", "TBD", "UNK",
})



def operator_state_agrees(owner_code: str, registry_label: str, operator_state: str) -> bool:
    """Do the registry and the operator catalogue name the same attribution?

    Two rows saying "Brazil" and "Brazil" is not a second source agreeing, it is
    one fact printed twice, so an operator country that agrees is not published
    at all. Agreement is decided from the registry CODE rather than from the
    label, because the labels are two different vocabularies -- and where the
    registry code names an organisation rather than a country there is no
    country to agree with, so anything GCAT supplies is new.
    """
    if operator_state == registry_label:
        return True
    if owner_code in REGISTRY_CODES_NOT_A_COUNTRY:
        return False
    return operator_state in REGISTRY_COUNTRY_EQUIVALENTS.get(owner_code, frozenset())

def _read_gcat_table(name: str) -> list[dict[str, str]] | None:
    """One GCAT TSV as dictionaries, or None when the mirror has no copy."""
    path = GCAT_MIRROR / name
    if not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as error:
        print(f"WARNING: mirrored GCAT file {name} is unreadable: {error}")
        return None
    header: list[str] | None = None
    rows: list[dict[str, str]] = []
    for line in text.splitlines():
        if header is None and line.startswith("#"):
            header = line.lstrip("#").split("\t")
            continue
        if header is None or line.startswith("#") or not line.strip():
            continue
        fields = line.split("\t")
        if len(fields) < len(header):
            fields += [""] * (len(header) - len(fields))
        rows.append(dict(zip(header, fields)))
    return rows


def catalog_name_forms(name: str) -> frozenset[str]:
    """Every form of a catalogue name a second catalogue might have used.

    Space-track writes ``OSCAR 11 (UOSAT 2)`` and ``EUTE 7B (EUTE 3D)``: the
    parenthesis carries a second, often more widely used name for the same
    spacecraft, so all of them count as this object's names.
    """
    forms = {name, re.sub(r"\s*\(.*?\)", "", name)}
    forms.update(re.findall(r"\((.*?)\)", name))
    return frozenset(
        squashed for squashed in (re.sub(r"[^A-Z0-9]", "", form.upper()) for form in forms)
        if squashed
    )


def gcat_identity_agrees(catalog_name: str, entry: dict[str, Any] | None) -> bool:
    """Do the registry and GCAT agree WHICH spacecraft this number is?

    They do not always, and it is not a rounding error. GCAT records catalog
    number 55045 as NuSat-34, a 41.5 kg Satellogic imager flown from Montevideo;
    the register lists the same number as CONTINUUM-1, an Australian object, and
    CelesTrak -- checked directly from the VPS on 2026-08-20 -- agrees with the
    register. 22826 is ITAMSAT to the registry and Healthsat 2 to GCAT. Both
    catalogues accept the same COSPAR piece in both cases, so the piece cannot
    separate them; they simply disagree about which passenger of a crowded
    launch this number belongs to.

    A number the two catalogues do not agree about is not a number this site can
    read an operator's country off. Publishing one anyway would put ANOTHER
    spacecraft's operator on the card -- the same shape of error as the defect
    this cross-check exists to repair, arrived at from the other side.

    The comparison is deliberately dumb: normalise away punctuation and case,
    accept a parenthesised alias on the registry's side, accept GCAT's ``Name``
    or its payload name ``PLName``, and accept a containment either way (GCAT's
    ``Femto-1`` payload name is the only thing that shows ``FEMTO-1`` and
    ``ARQSAT-1`` are one spacecraft). Anything cleverer would be a heuristic
    tuned to the disagreements that happen to exist today, which is a rule
    fitted to its own sample.
    """
    if not entry:
        return False
    ours = catalog_name_forms(catalog_name)
    theirs = entry.get("names") or frozenset()

    def same(mine: str, yours: str) -> bool:
        if mine == yours:
            return True
        # Containment is how "ANISCSAT" recognises "ANISCSAT-1" and how GCAT's
        # "Suomi NPP" recognises "NPP". Two characters inside a longer word is
        # not recognition, though -- "CALSPHERE 4(A)" offers the alias "A" --
        # so a containment has to rest on at least three characters.
        shorter, longer = sorted((mine, yours), key=len)
        return len(shorter) >= 3 and shorter in longer

    return any(same(mine, yours) for mine in ours for yours in theirs)


def published_operator_state(
    catalog_name: str, owner_code: str, registry_label: str, entry: dict[str, Any] | None
) -> str | None:
    """The operator country this object publishes, or None -- ONE rule, one place.

    Called by the build and by ``tests/test_operator_country.py`` alike. A test
    that restates the rule it is checking passes the moment the two copies drift
    the same way, which is how this project has shipped green tests over dead
    rules before.

    Nothing is published when GCAT has no row for the number, when the two
    catalogues disagree about which spacecraft the number is, or when GCAT's
    answer is the registry's answer in different letters.
    """
    if not entry:
        return None
    if not gcat_identity_agrees(catalog_name, entry):
        return None
    state = entry.get("state")
    if not state or operator_state_agrees(owner_code, registry_label, state):
        return None
    return str(state)


def gcat_operator_records() -> dict[int, dict[str, Any]]:
    """NORAD catalog number -> the operator's country and GCAT's names for it.

    Every step here refuses rather than guesses:

    * A row whose ``Satcat`` number is claimed by ANOTHER row is a data-entry
      error, and GCAT has three of them today. ``S68468`` (DB-BECON-2-VU) carries
      ``Satcat`` 68488, which belongs to Vindler 2.0.1; ``S69898`` (GRUS-3E)
      carries 66898, which belongs to Starlink 36065; ``S69903`` (Balkan-3)
      carries 66903, Starlink 36077. In all three the row's own JCAT identifier
      disagrees with the catalog number it claims, so the row whose JCAT number
      AGREES keeps the number and the other is dropped. A bulk import that did
      not do this would publish a Bulgarian operator for a Starlink.
    * A state code with no entry in ``GCAT_STATE_LABELS`` publishes nothing.
    * A missing mirror publishes nothing at all, and the caller says so in the
      artifact rather than letting "no operator country" read as "the operator
      is from the registering state".
    """
    rows = _read_gcat_table("satcat.tsv")
    if rows is None:
        return {}
    claims: dict[int, list[dict[str, str]]] = {}
    for row in rows:
        number = row.get("Satcat", "").strip()
        if not number.isdigit():
            continue
        claims.setdefault(int(number), []).append(row)
    records: dict[int, dict[str, Any]] = {}
    unknown: set[str] = set()
    dropped = 0
    for catalog_id, candidates in claims.items():
        if len(candidates) > 1:
            # The row whose own identifier agrees with the number it claims.
            agreeing = [
                row for row in candidates
                if re.sub(r"^[A-Za-z]+", "", row.get("JCAT", "").strip()) == str(catalog_id)
            ]
            if len(agreeing) != 1:
                dropped += len(candidates)
                continue
            dropped += len(candidates) - 1
            candidates = agreeing
        code = candidates[0].get("State", "").strip()
        label = GCAT_STATE_LABELS.get(code)
        if label is None:
            if code:
                unknown.add(code)
            continue
        records[catalog_id] = {
            "state": label,
            # BOTH names GCAT holds. ``Name`` is the object as GCAT lists it and
            # ``PLName`` is the payload it carries, and either can be the name
            # the registry chose: GCAT calls 68419 ARQSAT-1 with payload name
            # Femto-1, and the payload name is the only thing that shows it is
            # the registry's FEMTO-1 rather than another passenger on the same
            # rideshare.
            "names": frozenset(
                squashed
                for squashed in (
                    re.sub(r"[^A-Z0-9]", "", str(candidates[0].get(field) or "").upper())
                    for field in ("Name", "PLName")
                )
                if squashed
            ),
        }
    if dropped:
        print(f"NOTE: dropped {dropped} GCAT row(s) whose catalog number is claimed twice")
    if unknown:
        print(
            "NOTE: GCAT state codes with no label in GCAT_STATE_LABELS, so no "
            f"operator country is published for them: {', '.join(sorted(unknown))}"
        )
    return records


def mirror_records(name: str) -> list[dict[str, Any]] | None:
    """Read one mirrored CelesTrak dataset, or None when it is not mirrored."""
    path = CELESTRAK_MIRROR / name
    if not path.exists():
        return None
    try:
        raw = path.read_bytes()
    except OSError as error:
        print(f"WARNING: mirrored CelesTrak file {name} is unreadable: {error}")
        return None
    group = name[len("group-"):-len(".json")] if name.startswith("group-") else None
    try:
        records = validate_group_body(raw, url=f"mirror:{name}", group=group)
    except InvalidCelestrakGroup as error:
        # A mirror file that holds CelesTrak's plain-text refusal instead of
        # records is the silent failure this guard exists for, arriving by
        # rsync instead of by socket. Treat it as no data at all, loudly.
        note_invalid_group(error, where=f"VPS mirror file {name}")
        return None
    return records if isinstance(records, list) else None


def mirror_age_hours(name: str) -> float | None:
    path = CELESTRAK_MIRROR / name
    if not path.exists():
        return None
    return (time.time() - path.stat().st_mtime) / 3600.0


def fetch_celestrak_fleet_memberships() -> dict[int, set[str]]:
    """Join category evidence from the on-disk VPS mirror, never the network."""
    memberships: dict[int, set[str]] = {}
    groups = sorted(set(CELESTRAK_FLEET_GROUPS) | set(CELESTRAK_MISSION_CATEGORY_GROUPS))
    for group in groups:
        mirrored = mirror_records(f"group-{group}.json")
        if mirrored is None:
            continue
        for record in mirrored:
            catalog_id = record.get("NORAD_CAT_ID")
            if catalog_id is not None:
                memberships.setdefault(int(catalog_id), set()).add(group)
    return memberships


def fetch_celestrak_catalog() -> tuple[list[dict[str, Any]], list[dict[str, Any]], str, dict[int, set[str]]]:
    """Build from Space-Track plus CelesTrak's on-disk curation mirror.

    Space-Track is the sole orbital-element source.  CelesTrak contributes only
    the operational SATCAT curation and weekly mission-category memberships that
    Space-Track does not publish.  There is deliberately no CelesTrak GP-active
    fallback and no network bootstrap path: duplicate bulk elements were the
    request that hit CelesTrak's one-download-per-update 403 enforcement.
    """
    st_gp = spacetrack_records("gp-active.json")
    st_satcat = spacetrack_records("satcat-active.json")
    if st_gp is None or st_satcat is None:
        raise RuntimeError(
            "the Space-Track mirror is incomplete (gp-active.json and satcat-active.json "
            "are required). Direct CelesTrak fallback is forbidden; keep serving the "
            "last published release and inspect spacetrack-ingest.timer."
        )

    satcat = [normalise_satcat_record(record) for record in st_satcat]
    payloads = {
        int(record["NORAD_CAT_ID"])
        for record in satcat
        if record.get("OBJECT_TYPE") == "PAYLOAD" and record.get("NORAD_CAT_ID") is not None
    }

    # Space-Track's PAYLOAD includes dead spacecraft.  CelesTrak's SATCAT is
    # retained because its operational curation has no Space-Track equivalent.
    operational = mirror_records("satcat-active.json")
    if operational:
        live = {
            int(record["NORAD_CAT_ID"])
            for record in operational
            if record.get("NORAD_CAT_ID") is not None
        }
        before = len(payloads)
        payloads &= live
        print(
            f"CelesTrak operational curation applied: {before:,} payloads -> "
            f"{len(payloads):,} still operational"
        )
    else:
        print(
            "WARNING: no CelesTrak SATCAT mirror; keeping every Space-Track payload, "
            "which includes spacecraft that stopped working decades ago"
        )

    gp = [
        normalise_gp_record(record)
        for record in st_gp
        if record.get("NORAD_CAT_ID") is not None
        and int(record["NORAD_CAT_ID"]) in payloads
    ]
    age = (time.time() - (SPACETRACK_MIRROR / "gp-active.json").stat().st_mtime) / 3600
    print(
        f"using the Space-Track mirror: {len(gp):,} payload GP records "
        f"(from {len(st_gp):,} on-orbit objects), {len(satcat):,} SATCAT, "
        f"elements {age:.1f} h old"
    )
    if age > 24:
        print(
            f"WARNING: mirrored Space-Track elements are {age:.1f} h old; "
            "check spacetrack-ingest.timer and its halt marker on bigmem"
        )
    return gp, satcat, "space-track.org (18 SDS)", fetch_celestrak_fleet_memberships()


def catalog_priority(record: dict[str, Any]) -> tuple[int, int, str, int]:
    if record["purposeKind"] == "curated":
        rank = 0
    elif record["mission"] in {"weather", "missile-warning", "navigation", "human-spaceflight", "science", "earth-observation"}:
        rank = 1
    elif record["sector"] in {"military", "mixed"}:
        rank = 2
    elif record["constellation"] is None:
        rank = 3
    elif record["mission"] == "communications":
        rank = 4
    else:
        rank = 5
    stable_sample = int(hashlib.sha256(str(record["id"]).encode()).hexdigest()[:8], 16)
    return rank, stable_sample, record["name"], record["id"]


#: The two files that shape the Satellite Background section. Both are optional and
#: both fail SILENT AND UNCHANGED: absent, empty or malformed, every card renders the
#: full researched description exactly as it did before either existed.
SHAPED_PURPOSES = ROOT / "narration" / "shaped-purposes.json"
CONSTELLATION_OVERRIDES = ROOT / "data" / "constellation_overrides.json"

#: Sean, 2026-08-27: "on the site, I want max 2 paragraphs, and max just a few lines per
#: paragraph. It is fine if some only have 1 paragraph and it can be longer if so, with a
#: max of maybe 6-8 lines." Eight lines at the MEASURED 46 characters per line of the
#: card's description column -- 280.5 px at a 1440 px viewport, 11.6 px Inter on an
#: 18.56 px line box. The one place this number is derived is
#: narration/build_shaped_purposes.py; this is the publish-time copy of it, and the two
#: are pinned equal by tests/test_build_release.py.
BACKGROUND_SECTION_MAX_CHARS = 368


def attach_background_shape(satellites: list[dict[str, Any]]) -> None:
    """Two paragraphs, at most, on the cards that need them. Nothing researched is lost.

    ONE: the LONG tail. 835 objects carry 800 to 2,425 characters of researched, cited
    prose as a single block with no paragraph break in it -- fifty-three lines on the
    card at worst. `purposeShaped` is a shortened opening for those, produced by the
    `space-purpose-shape` authoring lane and checked into narration/shaped-purposes.json.
    `purpose` IS LEFT EXACTLY AS IT WAS; the interface prints the short version and keeps
    the full text one disclosure below it, so nothing anybody researched is deleted and a
    card with no shortened version simply renders as it always has.

    TWO: the THIN tail. 5,075 objects are in fleets whose own sentence is a single
    clause -- one sentence covers all 4,648 Starlinks -- and it answers "what is this
    one" without ever answering "what is the fleet". `fleetNote` is a hand-written,
    separately cited paragraph per fleet from data/constellation_overrides.json,
    published as its OWN field so the interface can give it its OWN Source link.
    IT IS NEVER CONCATENATED ONTO `purpose`: two paragraphs from two different sources
    sharing one citation is how a card starts vouching for something nobody checked.

    THE COUNT IS COMPUTED HERE, NEVER WRITTEN IN THE PROSE. A member count is the one
    fact about a fleet that moves, and prose is where a stale number goes to hide -- the
    constellation-of-the-day lane proved that. It is counted over the RETAINED records,
    like every other count this file publishes, so a reader holding the artifact can
    recompute it.

    THE FORMAT IS ENFORCED HERE TOO, not just asked for. A fleet paragraph whose members'
    own sentence leaves no room inside the section ceiling is DROPPED with a note, and a
    fleet paragraph containing a digit is dropped with a louder one.
    """
    shaped = _read_optional_json(SHAPED_PURPOSES).get("entries") or {}
    if shaped:
        for record in satellites:
            entry = shaped.get(_purpose_key(record.get("purpose")))
            paragraphs = (entry or {}).get("paragraphs") or []
            if paragraphs:
                record["purposeShaped"] = paragraphs
        print(f"NOTE: shortened opening on {sum(1 for r in satellites if r.get('purposeShaped'))} "
              f"of {len(satellites)} objects, from {len(shaped)} distinct descriptions")

    fleets = _read_optional_json(CONSTELLATION_OVERRIDES).get("constellations") or {}
    if not fleets:
        return
    counts: dict[str, int] = {}
    for record in satellites:
        name = record.get("constellation")
        if name:
            counts[name] = counts.get(name, 0) + 1
    attached = 0
    for name, entry in sorted(fleets.items()):
        note = str(entry.get("fleetNote") or "").strip()
        source = str(entry.get("fleetNoteSource") or "")
        members = [r for r in satellites if r.get("constellation") == name]
        if not note or not source.startswith("http"):
            print(f"NOTE: fleet paragraph for {name!r} has no text or no source URL; skipped")
            continue
        if any(character.isdigit() for character in note):
            print(f"NOTE: fleet paragraph for {name!r} contains a digit and was NOT published. "
                  "Counts are injected by code; they are never written into the prose.")
            continue
        if not members:
            print(f"NOTE: no object in this release is in the {name!r} fleet; paragraph skipped")
            continue
        longest = max(len((r.get("purpose") or "").strip()) for r in members)
        if longest + len(note) > BACKGROUND_SECTION_MAX_CHARS:
            print(f"NOTE: fleet paragraph for {name!r} would put a member card at "
                  f"{longest + len(note)} characters, past the {BACKGROUND_SECTION_MAX_CHARS} "
                  "the format allows; NOT published")
            continue
        for record in members:
            record["fleetNote"] = note
            record["fleetNoteSource"] = source
            record["fleetLabel"] = name
            record["fleetMemberCount"] = counts[name]
        attached += len(members)
    print(f"NOTE: fleet paragraph on {attached} of {len(satellites)} objects, "
          f"from {len(fleets)} researched fleets")


def _read_optional_json(path: Path) -> dict[str, Any]:
    """The file, or {}. A missing or broken file leaves the site as it was, never empty."""
    try:
        value = json.loads(path.read_text())
    except (OSError, ValueError) as error:
        print(f"NOTE: {path.name} not read ({error}); the cards keep their full descriptions")
        return {}
    return value if isinstance(value, dict) else {}


def _purpose_key(purpose: str | None) -> str:
    """The identity of a description, so 4,648 identical sentences are one entry.

    Kept byte-identical to `text_key` in narration/build_shaped_purposes.py; the pair is
    pinned by tests/test_build_release.py, because a drift here would silently un-shape
    every card rather than fail.
    """
    return hashlib.sha256((purpose or "").strip().encode("utf-8")).hexdigest()[:16]


def select_catalog_satellites(satellites: list[dict[str, Any]], max_satellites: int) -> list[dict[str, Any]]:
    if max_satellites <= 0 or len(satellites) <= max_satellites:
        return list(satellites)

    launch_dates = [
        dt.date.fromisoformat(record["launchDate"])
        for record in satellites
        if record.get("launchDate")
    ]
    recent_starlink_groups: set[str] = set()
    if launch_dates:
        cutoff = max(launch_dates) - dt.timedelta(days=STARLINK_RECENT_COHORT_DAYS)
        recent_starlink_groups = {
            record["launchGroup"]
            for record in satellites
            if record.get("constellation") == "Starlink"
            and record.get("launchGroup")
            and record.get("launchDate")
            and dt.date.fromisoformat(record["launchDate"]) >= cutoff
        }

    # Reserve whole recent launch cohorts, including a member whose SATCAT row
    # happens to omit LAUNCH_DATE. Splitting a fresh cohort would defeat the
    # launch-train teaching view this reservation exists to support.
    reserved = [
        record
        for record in satellites
        if record.get("constellation") == "Starlink"
        and record.get("launchGroup") in recent_starlink_groups
    ]
    if len(reserved) > max_satellites:
        raise RuntimeError(
            f"browser ceiling {max_satellites} is smaller than the {len(reserved)} "
            f"Starlink spacecraft in complete recent launch cohorts"
        )

    reserved_ids = {record["id"] for record in reserved}
    remainder = sorted(
        (record for record in satellites if record["id"] not in reserved_ids),
        key=catalog_priority,
    )
    return reserved + remainder[: max_satellites - len(reserved)]


# How long a fleet membership carried forward from an already-published catalog
# may still be used. Category membership changes on the order of months, so days
# of carry-forward costs nothing; carrying it forever would let a stale label
# outlive the fact behind it with no way to notice.
SOURCE_GROUP_CARRY_FORWARD_DAYS = 14

# Bumped whenever the meaning of a published classification field changes. It is
# also the acknowledgement the drift gate below accepts, so a deliberate
# taxonomy change publishes and an accidental one does not.
# 2026-08-19: the SatNOGS cross-check wave. `classificationBasis` gains
# "withdrawn-name-collision" (a name-pattern claim two independent sources
# contradict) and "radio-licence" (a mission for an otherwise-blank card, from
# the single ITU service its transmitters are filed under). The template
# description now names the evidence it actually rests on instead of saying
# "programme-name pattern" for every object alike, which was wrong on 356 of the
# 568 cards carrying it. And CelesTrak's `stations` group no longer implies
# crewed spaceflight for payloads merely deployed FROM a station.
# .2 (same day): CelesTrak's participation groups -- `tdrss`, `sarsat`, `argos`
# and `stations` -- no longer set a mission or a fleet. They say what a
# spacecraft takes part in, not what it is.
# .3 (2026-08-19): the web fact-check lane. `classificationBasis` gains
# "web-corroborated" -- a programme identity for an object the catalogue lists
# only by a registry designation, established from independent published sources
# that each name this CATALOG NUMBER, quoted and linked. It exists because US
# military spacecraft are registered as "USA nnn": the site had a DSCS rule
# matching a string that appears nowhere in the catalogue, so DSCS III B-6 sat as
# an unnamed GEO object with no mission at all. See pipeline/catalog_factcheck.py.
# 2026-08-20.1: non-US military communications. Filtering the catalogue by
# MILSATCOM returned 101 objects, 93 of them American and none of them Chinese or
# Russian, and the cause was again that the rules were written in English against
# American naming: the PLA's Shentong-2 satellites are catalogued as "CHINASAT
# 2A", Russia's Blagovest and Garpun as "COSMOS 25nn". `classificationBasis`
# gains "assessed" so those can be published WITHOUT being dressed as documented:
# nobody prints a fact sheet for Shentong-2, and a card that reads the same as
# SKYNET's -- which has a gov.uk page behind it -- would be claiming a certainty
# this site does not have. The five allied programmes it already knew (SKYNET,
# SYRACUSE, AEHF, WGS, MUOS) moved from a name prefix onto catalog numbers so the
# contrast is visible rather than asserted.
# 2026-08-20.8: the registry read-out comes off the cards. An override flag
# `appendRegistryFacts` appended "This object's registry record: about 976 km up
# on a 104.6-minute period, launched 1964-10-06 in launch-group 1964-063,
# registered to the United States." to 1,205 published descriptions, 553 of them
# researched prose it padded from behind. Every value in it is already a row in
# the Satellite Details grid on the same screen. Sean: "that sounds absolutely
# tacky", and the standing rule, "stop adding filler/fluff text to my site".
# The flag, the clause helpers that formatted it and the 627 override entries
# that set it are all deleted; `validate_overrides` now REFUSES the flag, since
# leaving it dormant is how it came back the second time. `purpose` changes on
# 1,205 retained objects, which is what this bump acknowledges.
# 2026-08-27: cohort corroboration. Sean, looking at STARLINK-11600: "I don't
# like that ?", and "it looks ridiculous on the display". He was right, and the
# measurement agreed: 6,288 of 8,000 cards rested on `name-pattern` and drew the
# dashed, dimmed, question-marked chip, so the mark that exists to warn about
# Tianmu-1 11 was firing on four thousand Starlinks and had stopped meaning
# anything. The 18th Space Defense Squadron's naming really is provisional
# within a launch -- LitSat-1 and LituanicaSat-1 were transposed until Doppler
# sorted them out -- so the scepticism was right about IDENTITY. It was wrong
# about the MISSION CLASS, which is what the chip actually states and which
# survives a transposition: swap two names inside a Starlink batch and both
# objects are still commercial SATCOM. A new published field
# `missionCorroboration` records that a spacecraft's own fleet agrees with it on
# owner, on mission and on launching in batches, with nothing independent
# disputing any member. `classificationBasis` is UNCHANGED on every object.
TAXONOMY_VERSION = "2026-08-27.1"


def prior_published_catalog(data_root: Path) -> dict[str, Any] | None:
    """The catalog artifact from the previous release, if it is still on disk."""
    record = prior_artifact_record(data_root, "catalog")
    if record is None:
        return None
    try:
        return json.loads((data_root / str(record["path"])).read_text())
    except (OSError, json.JSONDecodeError, KeyError):
        return None


# Wall-clock ceiling on searching retained releases for recoverable evidence.
# Same discipline as the CelesTrak group budget above: useful, bounded, and
# incapable of eating the publish job's 240 s.
SOURCE_GROUP_RECOVERY_BUDGET_SECONDS = 20.0
SOURCE_GROUP_RECOVERY_GOOD_COVERAGE = 0.5


def _release_time(stamp: Any) -> dt.datetime | None:
    try:
        return dt.datetime.strptime(str(stamp), "%Y%m%dT%H%M%SZ").replace(tzinfo=dt.timezone.utc)
    except (TypeError, ValueError):
        return None


def recoverable_source_groups(
    data_root: Path, now: dt.datetime | None = None
) -> tuple[dict[int, list[str]], str | None]:
    """Search retained releases for the richest recent fleet evidence we hold.

    The most recent release is not necessarily the best source: when the group
    mirror empties, every subsequent release inherits the emptiness. On
    2026-08-07 the newest published catalog carried fleet membership for 380 of
    8,000 objects while a release retained three hours earlier carried all
    8,000. Both are ours, both are already on disk, and neither costs an
    upstream request.

    Newest first, so a fresher answer wins ties, with an early exit once
    coverage is good and a hard time budget so a degraded state cannot turn
    this into an unbounded scan of every retained manifest.
    """
    reference = now or utcnow()
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=dt.timezone.utc)
    horizon = reference - dt.timedelta(days=SOURCE_GROUP_CARRY_FORWARD_DAYS)

    candidates: list[tuple[dt.datetime, Path]] = []
    seen_paths: set[Path] = set()
    manifests = [data_root / "manifest.json", *sorted(data_root.glob("manifests/manifest-*.json"), reverse=True)]
    for manifest_path in manifests:
        try:
            manifest = json.loads(manifest_path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        released = _release_time(manifest.get("release"))
        catalog_entry = manifest.get("catalog")
        if released is None or released < horizon or not isinstance(catalog_entry, dict):
            continue
        artifact = data_root / str(catalog_entry.get("path", ""))
        if not artifact.is_file() or artifact in seen_paths:
            continue
        seen_paths.add(artifact)
        candidates.append((released, artifact))
    candidates.sort(key=lambda item: item[0], reverse=True)

    deadline = time.monotonic() + SOURCE_GROUP_RECOVERY_BUDGET_SECONDS
    best: tuple[int, dict[int, list[str]], str] | None = None
    for released, artifact in candidates:
        if time.monotonic() > deadline:
            break
        try:
            catalog = json.loads(artifact.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        recovered = {
            int(record["id"]): list(record["sourceGroups"])
            for record in catalog.get("satellites", [])
            if isinstance(record, dict) and record.get("id") is not None and record.get("sourceGroups")
        }
        total = len(catalog.get("satellites", [])) or 1
        if best is None or len(recovered) > best[0]:
            best = (len(recovered), recovered, iso_z(released))
        if len(recovered) / total >= SOURCE_GROUP_RECOVERY_GOOD_COVERAGE:
            break
    if best is None or not best[0]:
        return {}, None
    return best[1], best[2]


def carried_forward_source_groups(
    prior: dict[str, Any] | None, now: dt.datetime | None = None
) -> tuple[dict[int, list[str]], str | None]:
    """Fleet membership recovered from our own last published catalog.

    On 2026-08-07 CelesTrak fetching moved to the VPS and the bigmem-side rsync
    replaced the older, fuller group cache with the VPS's near-empty one. Fleet
    labels for 4,802 objects vanished between two builds two hours apart -- not
    because anything changed in orbit, but because the evidence was no longer on
    disk. The evidence was, however, still sitting in the artifact we had just
    published, which is derived data we already hold: recovering it needs no
    upstream request at all.

    Two guards. The result carries the *source* release's timestamp, so nothing
    downstream can claim this membership is fresher than it is; and it expires,
    so a permanently missing mirror degrades to honest silence instead of a
    label frozen in place forever.
    """
    if not isinstance(prior, dict):
        return {}, None
    as_of = prior.get("upstreamAsOf")
    if not isinstance(as_of, str) or not as_of:
        return {}, None
    try:
        stamped = dt.datetime.fromisoformat(as_of.replace("Z", "+00:00"))
    except ValueError:
        return {}, None
    if stamped.tzinfo is None:
        stamped = stamped.replace(tzinfo=dt.timezone.utc)
    reference = now or utcnow()
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=dt.timezone.utc)
    if (reference - stamped) > dt.timedelta(days=SOURCE_GROUP_CARRY_FORWARD_DAYS):
        return {}, None
    recovered = {
        int(record["id"]): list(record["sourceGroups"])
        for record in prior.get("satellites", [])
        if isinstance(record, dict) and record.get("id") is not None and record.get("sourceGroups")
    }
    return recovered, as_of


# Fraction of *retained* objects whose displayed mission, fleet or description
# may change between two consecutive releases without a human being told. The
# publish cycle runs every five minutes; a student who bookmarks a satellite
# card and comes back to a different mission has been misinformed by the
# pipeline, not by the sky. Measured on 2026-08-07: two builds two hours apart
# silently moved 89 fleet labels, 75 missions and 138 description paragraphs.
CATALOG_DRIFT_FRACTION = 0.01
CATALOG_DRIFT_ALLOWED = os.environ.get("SPACE_EXPLORER_ALLOW_CATALOG_DRIFT") == "1"
# `operatorState` joined this list on 2026-08-20 with the field itself. It is a
# row on the card -- "Operator's country" -- and a claim the site makes, so a
# build that silently blanked all 146 of them would otherwise publish clean and
# green. Every field watched here is one a reader can see.
_DRIFT_FIELDS = ("mission", "sector", "constellation", "organization", "purpose", "operatorState")


def catalog_drift(prior: dict[str, Any] | None, satellites: list[dict[str, Any]]) -> dict[str, Any]:
    """Which displayed claims changed for objects present in both releases."""
    if not isinstance(prior, dict):
        return {"comparable": 0, "changed": {}, "examples": []}
    previous = {record["id"]: record for record in prior.get("satellites", []) if isinstance(record, dict)}
    changed: dict[str, int] = {field: 0 for field in _DRIFT_FIELDS}
    examples: list[str] = []
    comparable = 0
    for record in satellites:
        before = previous.get(record["id"])
        if before is None:
            continue
        comparable += 1
        for field in _DRIFT_FIELDS:
            if before.get(field) != record.get(field):
                changed[field] += 1
                if len(examples) < 20:
                    examples.append(
                        f"{record['id']} {record['name']}: {field} {before.get(field)!r} -> {record.get(field)!r}"
                    )
    return {"comparable": comparable, "changed": changed, "examples": examples}


def report_catalog_drift(
    prior: dict[str, Any] | None,
    satellites: list[dict[str, Any]],
    taxonomy_version: str | None = None,
) -> dict[str, Any]:
    """Print the drift, and refuse the build when it is larger than expected.

    The pipeline already refuses an implausible GP row count rather than
    publishing it. The same discipline applies here: a taxonomy change that
    rewrites hundreds of cards is a decision, and decisions get acknowledged.

    A bumped ``taxonomyVersion`` *is* that acknowledgement, and is accepted in
    place of the environment override. Without this, landing a taxonomy fix
    would wedge the five-minute publish timer until someone noticed and set an
    environment variable -- turning a safety gate into an outage, which is how
    safety gates get deleted. Drift under an *unchanged* taxonomy version is the
    dangerous case, and that is still refused.
    """
    drift = catalog_drift(prior, satellites)
    taxonomy_changed = (
        isinstance(prior, dict)
        and taxonomy_version is not None
        and prior.get("taxonomyVersion") not in (None, taxonomy_version)
    )
    worst = max(drift["changed"].values(), default=0)
    if not drift["comparable"] or not worst:
        return drift
    print(
        f"catalog drift vs previous release: "
        + ", ".join(f"{field}={count}" for field, count in drift["changed"].items() if count)
        + f" of {drift['comparable']} retained objects"
    )
    for example in drift["examples"]:
        print(f"  {example}")
    if taxonomy_changed:
        print(
            f"  accepted: taxonomyVersion moved {prior.get('taxonomyVersion')!r} -> "
            f"{taxonomy_version!r}, which is the acknowledgement this gate asks for"
        )
        return drift
    limit = max(1, int(drift["comparable"] * CATALOG_DRIFT_FRACTION))
    if worst > limit and not CATALOG_DRIFT_ALLOWED:
        raise RuntimeError(
            f"catalog drift {worst} exceeds the {limit}-object threshold "
            f"({CATALOG_DRIFT_FRACTION:.0%} of {drift['comparable']} retained objects). "
            "Review the diff above; set SPACE_EXPLORER_ALLOW_CATALOG_DRIFT=1 to publish it."
        )
    return drift


def attach_orbital_lifetime(satellites: list[dict[str, Any]], data_root: Path | None) -> None:
    """Add one measured sentence to the cards that have nothing else to say.

    ONLY to those cards. The estimate is genuinely interesting for a dead 3U
    cubesat and pure noise on a geostationary comsat, and the site's owner had
    just had every card cut by 20-60%: "I just don't want useless filler or
    redundant bullshit." So it is appended where the alternative is a card that
    teaches a class and nothing about this object, and nowhere else.

    Everything here degrades to silence. The archive lives on /mnt/d, may be
    absent, may be mid-roll, and its publishing lane is currently switched off;
    none of that may take down a publish cycle, so a failure costs a clause.
    """
    if not satellites:
        return
    wanted = {
        record["id"]: record
        for record in satellites
        if record.get("purposeKind") == "class" and record.get("orbit") == "LEO"
    }
    if not wanted or data_root is None:
        return
    try:
        from pipeline import orbital_lifetime

        series = orbital_lifetime.decay_samples(data_root, wanted)
        measured = 0
        for catalog_id, record in wanted.items():
            samples = series.get(catalog_id)
            if not samples:
                continue
            # Mean altitude, not perigee: every object that reaches here is
            # near-circular (the widest is 16 km of eccentricity), and the
            # first-order result this integrates is a circular-orbit result.
            altitude = (float(record["perigeeKm"]) + float(record["apogeeKm"])) / 2.0
            sentence = orbital_lifetime.lifetime_sentence(
                orbital_lifetime.estimate(altitude, samples)
            )
            if sentence:
                record["purpose"] = f"{record['purpose'].rstrip()} {sentence}"
                measured += 1
        print(f"NOTE: orbital lifetime measured for {measured} of {len(wanted)} class-described objects")
    except Exception as error:  # noqa: BLE001
        print(f"WARNING: orbital lifetime unavailable; cards keep the class description alone: {error}")


def build_catalog(max_satellites: int, data_root: Path | None = None) -> dict[str, Any]:
    gp_records, satcat_records, catalog_scope, group_memberships = fetch_celestrak_catalog()
    if not isinstance(gp_records, list) or len(gp_records) < 1000:
        raise RuntimeError(f"implausible CelesTrak active GP row count: {len(gp_records) if isinstance(gp_records, list) else 'not-list'}")
    satcat_by_id = {int(row["NORAD_CAT_ID"]): row for row in satcat_records if row.get("NORAD_CAT_ID") is not None}
    # The operator's country, from a catalogue that keeps it apart from the
    # registering state. Empty when the mirror is absent, which the artifact
    # reports rather than hiding.
    operator_records = gcat_operator_records()
    # How crowded each launch was, from the registry itself. Read once here
    # rather than per object: the SATCAT is thirty-five thousand rows and the
    # answer is the same for every passenger on the same flight.
    cohort_payloads = launch_cohort_payloads(satcat_records)
    overrides = load_overrides()
    validate_overrides(overrides)
    # Name-pattern claims withdrawn after a SatNOGS cross-check. Keyed on catalog
    # number only, like `participation`, so it cannot mis-attach by name -- which
    # would be a striking way to fix a name-collision bug.
    satnogs_withdrawals = satnogs_verify.load_withdrawals()
    # A mission for objects this catalog says NOTHING about, derived from the one
    # ITU radio service their transmitters are filed under. Gap-filling only --
    # see the guard at the point of use.
    satnogs_service_missions = satnogs_verify.load_service_missions()
    # A programme name for objects the catalogue lists only by a registry
    # designation -- USA 170 is DSCS III B-6 -- corroborated across independent
    # published sources and cited. Keyed on catalog ID only, like every other
    # table here, so a lane that exists to fix name-based misattribution cannot
    # itself attach by name. See pipeline/catalog_factcheck.py.
    web_findings = catalog_factcheck.load_findings()
    # Publicly documented, source-cited programme participation: one spacecraft
    # carrying or serving somebody else's mission. Keyed on catalog ID only, so
    # it cannot mis-attach by name. See pipeline/programme_participation.py.
    participation = load_participation()
    validate_participation(participation)
    participation_by_id = participation_index(participation)
    satellites: list[dict[str, Any]] = []
    # Whether this build had any fleet evidence to check at all. When the group
    # mirror is empty, "no named fleet identified" is a claim the build never
    # tested, and the site must not present an untested negative as a finding.
    fleet_evidence_available = bool(group_memberships)

    prior_catalog = prior_published_catalog(data_root) if data_root is not None else None
    carried_groups, carried_as_of = (
        recoverable_source_groups(data_root) if data_root is not None else ({}, None)
    )
    carried_used = 0
    for catalog_id, groups in carried_groups.items():
        if not group_memberships.get(catalog_id):
            group_memberships[catalog_id] = set(groups)
            carried_used += 1
    if carried_used:
        fleet_evidence_available = True
        print(
            f"NOTE: fleet membership for {carried_used} objects carried forward from the "
            f"already-published catalog of {carried_as_of}; the live group mirror covered "
            f"{len(group_memberships) - carried_used}"
        )

    for omm in gp_records:
        catalog_id = int(omm["NORAD_CAT_ID"])
        satcat = satcat_by_id.get(catalog_id, {})
        name = str(omm.get("OBJECT_NAME") or satcat.get("OBJECT_NAME") or f"NORAD {catalog_id}").strip()
        owner_code = str(satcat.get("OWNER") or "UNK")
        orbit_data = derive_orbit(float(omm["MEAN_MOTION"]), float(omm["ECCENTRICITY"]), float(omm["INCLINATION"]))
        # Hoisted above the description block, which now states them. They used
        # to be computed just before the record was assembled, forty lines below
        # the only place that needed them.
        launch_date = normalize_launch_date(satcat.get("LAUNCH_DATE"))
        launch_group = identify_launch_group(str(omm.get("OBJECT_ID") or ""))
        mission, sector, constellation, organization, confidence, basis = classify_detailed(name, owner_code)
        registry_label = OWNER_LABELS.get(owner_code, owner_code or "Unknown")
        organization_source = "registry" if organization == registry_label else "named-program"
        source_groups = sorted(group_memberships.get(catalog_id, set()))
        # A satellite that only HOSTS an augmentation payload keeps whatever
        # primary mission it already had — communications, usually — and records
        # the augmentation as a secondary role below. Withholding the group here
        # is what stops "GALAXY 30, mission: navigation".
        hosted_system = celestrak_hosted_augmentations().get(catalog_id)
        if hosted_system:
            source_groups = [group for group in source_groups if group != "gnss"]
        if constellation is None:
            # Same reason, and it was doing visible damage: 58 objects were shown
            # in a "fleet" they merely USE. Hubble was in the TDRSS constellation,
            # INSAT 3D in COSPAS-SARSAT, SARAL in ARGOS. A fleet is a set of
            # spacecraft flown together by one operator; a relay network's
            # customer list is not one, and the card's FLEET row is read as the
            # former.
            constellation = next(
                (
                    CELESTRAK_FLEET_GROUPS[group]
                    for group in source_groups
                    if group in CELESTRAK_FLEET_GROUPS and group not in PARTICIPATION_GROUPS
                ),
                None,
            )
        # A participation group says what system this object takes part in, not
        # what it is. Withheld from the mission inference, and deliberately NOT
        # removed from `source_groups`: "uses TDRSS", "carries a COSPAS-SARSAT
        # transponder", "was deployed from the ISS" are all true and interesting
        # facts, they are simply not missions. `stations` is the one that can
        # still be about the object itself, so it keeps its name check.
        mission_groups = [
            group for group in source_groups
            if group not in PARTICIPATION_GROUPS
            or (group == "stations" and station_group_is_about_this_object(name))
        ]
        repaired = repair_mission_from_groups(mission, sector, confidence, mission_groups)
        if repaired != (mission, sector, confidence):
            basis = "source-group"
        mission, sector, confidence = repaired

        # A name-pattern claim that two independent sources say is about a
        # different spacecraft. Applied HERE -- after the group repair, before
        # the override table -- so that stronger evidence still wins in both
        # directions: a CelesTrak category group can re-establish a mission the
        # name got wrong, and a curated entry below overrides this entirely,
        # which is the rule that a human-checked value outranks an automated one.
        # See pipeline/satnogs_verify.py for how an entry gets into that file;
        # nothing there can ASSERT a mission, only take a wrong one away.
        withdrawal = satnogs_withdrawals.get(catalog_id)
        if withdrawal and basis in {"name-pattern"}:
            if "constellation" in withdrawal.get("withdraw", []):
                constellation = None
            if "mission" in withdrawal.get("withdraw", []):
                mission = "other"
            if "sector" in withdrawal.get("withdraw", []):
                sector = "unknown"
            confidence = "low"
            basis = "withdrawn-name-collision"
        purpose_source: str | None = None
        notes: list[dict[str, Any]] = []
        # What the registry holds for this object, for the description to state
        # when nothing names its payload. Published for 100% of the catalog.
        registry_facts = {
            "perigeeKm": orbit_data["perigeeKm"],
            "apogeeKm": orbit_data["apogeeKm"],
            "periodMinutes": orbit_data["periodMinutes"],
            "launchDate": launch_date,
            "launchGroup": launch_group,
            "ownerLabel": registry_label,
        }

        # A card that currently says nothing, given what its operator told a
        # regulator. This is the ONLY place in the SatNOGS lane that adds a claim
        # instead of removing one, so it is fenced in hard: it runs only when the
        # site has no mission at all and no evidence of any kind, so it can never
        # compete with a name rule, a CelesTrak group, a catalog-number rule or a
        # human -- and the curated override table below still overrides it.
        #
        # `basis` becomes "radio-licence" rather than borrowing an existing value,
        # because a licence is a genuinely different kind of evidence from every
        # other basis here and the card says which one it is reading.
        service_mission = satnogs_service_missions.get(catalog_id)
        if service_mission and mission == "other" and basis == "unclassified":
            mission = service_mission["mission"]
            confidence = "medium"
            basis = "radio-licence"

        # The same gap-fill bar as the radio-licence rule above, and for the same
        # reason: this may only speak where the site has nothing to say. It runs
        # AFTER the licence rule so a licence -- which an operator filed with a
        # regulator, under penalty -- is never displaced by a web citation, and
        # BEFORE the override table so a person still outranks it.
        #
        # `basis` becomes "web-corroborated" rather than borrowing an existing
        # value. A reader is owed the difference between "the name told us" and
        # "two independent published sources, quoted and linked, agree that this
        # catalogue number is that spacecraft".
        web_finding = web_findings.get(catalog_id)
        if web_finding and mission == "other" and basis == "unclassified":
            mission = web_finding["mission"]
            sector = web_finding["sector"]
            organization = web_finding["organization"]
            organization_source = "web-corroborated"
            confidence = "medium"
            basis = "web-corroborated"

        matched = matching_override(name, overrides, catalog_id)
        if matched:
            override, match_kind = matched
            mission = override.get("mission", mission)
            sector = override.get("sector", sector)
            organization = override.get("organization", organization)
            # An entry may carry only an operator attribution. Attaching an
            # operator the registry can be pointed at is cheap and safe;
            # writing a paragraph about a spacecraft is neither, so an entry
            # without a purpose keeps the honest orbit-derived description.
            purpose = override.get("purpose") or template_purpose(
                name, mission, sector, orbit_data["orbit"], basis, registry_facts,
                cohort_payloads.get(launch_group or ""),
            )
            if override.get("purpose"):
                # A family paragraph is TRUE of this object but not ABOUT it.
                # The shell clause is what makes the card specific, and it is
                # read off this object's own measured elements rather than
                # asserted: which published shell it is flying in.
                #
                # There used to be a second clause here, appended under an
                # override flag `appendRegistryFacts`: "This object's registry
                # record: about 976 km up on a 104.6-minute period, launched
                # ...". It was removed on 2026-08-20 and MUST NOT come back.
                # Every fact in it -- altitude, period, launch date, launch
                # group, registering state -- is already a row in the Satellite
                # Details grid on the same screen, so it restated the grid in
                # prose and padded 1,205 cards, 553 of them researched. Sean:
                # "that sounds absolutely tacky ... just having it lead into
                # orbit is fucking dumb", and "stop adding filler/fluff text to
                # my site". This was its THIRD appearance; `validate_overrides`
                # now refuses the flag outright rather than ignoring it, and
                # `test_the_description_never_restates_the_details_grid`
                # guards the override path as well as the generated one.
                shell = constellation_shell_note(
                    override, float(omm["INCLINATION"]), registry_facts
                )
                if shell:
                    purpose = f"{purpose.rstrip()} {shell.strip()}"
            # THREE kinds, not two. "class" means the sentence above is this
            # site's own class-level description and names no source, and the
            # card has to be able to tell that apart from a family paragraph
            # that IS about the spacecraft -- the 65 SatNOGS radio-licence
            # entries are `purposeKind: "template"` and are real, cited prose.
            # Matching on the prose's opening words worked until the prose
            # changed; a published flag cannot rot the same way.
            if override.get("purpose"):
                purpose_kind = "curated" if override.get("individual") else "template"
            else:
                purpose_kind = "class"
            # Was hard-coded "high" for every override alike, which is how a
            # family template inherited an individual spacecraft's certainty.
            # Confidence now reports how the entry actually matched.
            #
            # ...and only where the entry says something about the mission.
            # The rule is a named function so it can be tested against cases the
            # catalog does not currently contain -- an invariant checked only
            # against shipped data goes silently vacuous the moment the last
            # offending object is fixed, which is how this project has shipped
            # green tests over dead rules before.
            basis, confidence = override_classification(override, match_kind, basis, confidence)
            # An entry may be curated and still not be DOCUMENTED. `evidence:
            # "assessed"` says a person checked sources and what the sources
            # contain is an assessment, so the mechanism that matched the object
            # (a catalog number, which is exact) must not be read as evidence
            # about the mission (which nobody has published). Applied after the
            # match-kind grading above precisely so it can take that certainty
            # back off again.
            if override.get("evidence") == "assessed":
                basis = "assessed"
                # An assessment is not one strength. Gunter Krebs writing
                # "Kosmos 2570 (Lotos-S1 #7)" flat, and Gunter Krebs writing
                # "Kosmos 2615 (OO-MKA #7 ?)" with a question mark, are not the
                # same claim, and the card should not draw them the same. An
                # entry may therefore grade its own assessment down to "low";
                # it may never grade itself up, which is why "high" is refused
                # by `validate_overrides` rather than merely ignored here.
                confidence = override.get("assessedConfidence", "medium")
            if override.get("organization"):
                organization_source = "curated"
            # An entry carrying only an operator attribution supplies a source
            # for the OPERATOR, and hanging that link under a sentence saying no
            # source names the payload reads as a contradiction the reader is
            # right to distrust: SMAP shipped a "Source" link to smap.jpl.nasa.gov
            # directly beneath "no public source names this spacecraft's payload".
            purpose_source = override.get("source") if purpose_kind != "class" else None
            declared = override.get("contestedAttribution")
            if declared:
                notes.append(attribution_note(
                    kind="contested-source",
                    claim=declared["recorded"],
                    counter=declared["alternate"],
                    position=(
                        "This site records the assessment by "
                        f"{declared['recorded']['attributedTo']} and shows both readings."
                    ),
                ) | {"strength": 3})
        else:
            if constellation == "PWSA Transport Layer":
                purpose = (
                    "This Space Development Agency Tranche 1 Transport Layer spacecraft is part of a "
                    "proliferated LEO mesh network providing resilient, low-latency military data transport "
                    "and tactical communications, including optical inter-satellite links and tactical data links."
                )
                purpose_kind = "curated"
                basis = "exact-name"
                purpose_source = "https://www.sda.mil/transport/"
            elif basis == "web-corroborated" and web_finding:
                # The sentence lives with the evidence, in catalog_factcheck's
                # hand-written programme table, and ships with that programme's
                # own source. The retrieved citations that established WHICH
                # programme this object belongs to are in
                # data/catalog_factcheck.json beside their quoted spans.
                purpose = web_finding["purpose"]
                purpose_kind = "curated"
                purpose_source = web_finding["programmeSource"]
            elif basis == "radio-licence" and service_mission:
                # The sentence lives beside the evidence, in satnogs_verify, and
                # it carries its own citation: a claim about what a spacecraft
                # does does not ship here without somewhere a reader can check it.
                purpose = service_mission["purpose"]
                purpose_kind = "template"
                purpose_source = service_mission["source"]
            else:
                purpose = template_purpose(
                    name, mission, sector, orbit_data["orbit"], basis, registry_facts,
                    cohort_payloads.get(launch_group or ""),
                )
                purpose_kind = "class"
                purpose_source = None

        # An orbit that does not support the label the name implies is surfaced,
        # not silently resolved: YAOGAN-41 is geostationary and YAOGAN 45/46 sit
        # in MEO at 20 degrees, and none of those is an imaging orbit.
        regime_note = regime_conflict_note(
            name, mission, basis, orbit_data, float(omm["INCLINATION"])
        )
        if regime_note is not None:
            notes.append(regime_note)
        if notes:
            # The caveat travels with the sentence, not in a methods page the
            # reader has to go looking for.
            purpose = purpose.rstrip() + contested_caveat(notes)

        # Operator families last, so a cited operator wins over a name-pattern
        # default but never over a curated per-spacecraft entry.
        operator = operator_sector(name)
        if operator is not None:
            sector_value, operator_name, operator_source = operator
            sector = sector_value
            if organization_source != "curated":
                organization = operator_name
                organization_source = "named-program"
                if purpose_source is None:
                    purpose_source = operator_source
        # WHOSE COUNTRY. The registry's answer and the operator's answer are two
        # different facts, and this is where they stop being confused.
        #
        # `operator_state` is published only when the two DISAGREE -- when they
        # agree there is nothing extra to say, and a second row repeating the
        # first would imply corroboration between two sources the site did not
        # get. Where they disagree, BOTH ship: overwriting the registry's
        # attribution would destroy a citable fact, and international
        # registration genuinely can name a state other than the operator's
        # (an ISS-cohort cubesat inheriting the 1998-067 series, an SES
        # spacecraft flown from Luxembourg through a UK licensee). The card
        # shows the two, labelled, and lets the reader see the difference.
        #
        # The ONE thing that is overwritten is the case where the site was
        # passing the registering state off AS the operator: `organization`
        # starts life as the registry's country label, and for an object with
        # no curated entry, no named-programme rule, no radio licence and no
        # web finding it stays that way -- so SARI-1's "Owner / operator" row
        # said "Brazil" and the owner filter listed a Saudi spacecraft under
        # Brazil. Only that case is replaced, and only by a country that an
        # operator-focused catalogue names, never over a human's entry.
        #
        # And NOTHING is read off a number the two catalogues do not agree
        # about. GCAT records 55045 as the Satellogic imager NuSat-34 with a
        # Uruguayan operator; the registry and CelesTrak both record it as
        # CONTINUUM-1, Australian. Publishing "Uruguay" there would put another
        # spacecraft's operator on the card, which is this defect again from the
        # other side. `published_operator_state` refuses those, and the release
        # counts them so the silence is a labelled gap.
        gcat_entry = operator_records.get(catalog_id)
        operator_state = published_operator_state(name, owner_code, registry_label, gcat_entry)
        if operator_state and organization_source == "registry":
            organization = operator_state
            organization_source = "gcat-state"

        # Last, because the disclosure sentence names the operator and the
        # operator-family table above is what settles that. Purely additive: a
        # programme claim never changes mission, sector or operator, because
        # hosting somebody else's payload does not change whose spacecraft it
        # is -- which is exactly the fact the field exists to make visible.
        programmes = participation_by_id.get(catalog_id)
        if programmes:
            purpose = purpose.rstrip() + participation_disclosure(programmes, organization)
        normalized_omm = {
            "OBJECT_NAME": name,
            "OBJECT_ID": str(omm.get("OBJECT_ID") or ""),
            "EPOCH": str(omm["EPOCH"]),
            "MEAN_MOTION": float(omm["MEAN_MOTION"]),
            "ECCENTRICITY": float(omm["ECCENTRICITY"]),
            "INCLINATION": float(omm["INCLINATION"]),
            "RA_OF_ASC_NODE": float(omm["RA_OF_ASC_NODE"]),
            "ARG_OF_PERICENTER": float(omm["ARG_OF_PERICENTER"]),
            "MEAN_ANOMALY": float(omm["MEAN_ANOMALY"]),
            "EPHEMERIS_TYPE": int(omm.get("EPHEMERIS_TYPE") or 0),
            "CLASSIFICATION_TYPE": str(omm.get("CLASSIFICATION_TYPE") or "U"),
            "NORAD_CAT_ID": catalog_id,
            "ELEMENT_SET_NO": int(omm.get("ELEMENT_SET_NO") or 0),
            "REV_AT_EPOCH": int(omm.get("REV_AT_EPOCH") or 0),
            "BSTAR": float(omm.get("BSTAR") or 0),
            "MEAN_MOTION_DOT": float(omm.get("MEAN_MOTION_DOT") or 0),
            "MEAN_MOTION_DDOT": float(omm.get("MEAN_MOTION_DDOT") or 0),
        }
        satellites.append(
            {
                "id": catalog_id,
                "name": name,
                "cosparId": normalized_omm["OBJECT_ID"],
                "ownerCode": owner_code,
                "ownerLabel": OWNER_LABELS.get(owner_code, owner_code or "Unknown"),
                "organization": organization,
                # The operator's country, present ONLY when it differs from the
                # registering state above. Absent means either "they agree" or
                # "GCAT has no row for this object"; `operatorStateEvidence` on
                # the release says how many of each, so absence never has to be
                # read as a finding.
                "operatorState": operator_state,
                "launchDate": launch_date,
                "launchGroup": launch_group,
                "mission": mission,
                # What else this spacecraft does. A hosted payload is a real
                # capability and increasingly the norm, but it is not what the
                # satellite is FOR, so it is carried beside the primary mission
                # rather than replacing it. Each entry states its own evidence.
                "secondaryMissions": (
                    [{
                        "mission": "navigation",
                        "role": "augmentation",
                        "system": hosted_system,
                        "basis": "celestrak-group:gnss",
                        "why": (
                            f"Hosts a {hosted_system} satellite-based augmentation payload, "
                            "which broadcasts corrections that improve GNSS accuracy. "
                            "CelesTrak lists it under gnss and names the system in the object name."
                        ),
                    }]
                    if hosted_system else []
                ),
                "sector": sector,
                "constellation": constellation,
                # A null constellation means two very different things: "the
                # fleet lists were checked and this object is in none of them",
                # and "there were no fleet lists to check". Only the first is a
                # finding. The UI must not render the second as one.
                "fleetEvidence": "checked" if fleet_evidence_available else "unavailable",
                "sourceGroups": source_groups,
                **orbit_data,
                "purpose": purpose,
                "purposeKind": purpose_kind,
                "classificationConfidence": confidence,
                # How the claim above was arrived at: "norad-id", "exact-name",
                # "name-pattern", "source-group" or "unclassified".
                "classificationBasis": basis,
                # Set after this loop, in the cohort pass at the end of
                # build_catalog: it needs the whole retained catalog to see a
                # fleet. Present only where a fleet vouched for this object's
                # MISSION CLASS; absent is the ordinary case and is not a
                # finding. It never replaces `classificationBasis` above.
                # Where the OWNER / OPERATOR value came from. "registry" means
                # it is the same fact as COUNTRY / REGISTRY in different words,
                # and the card should not print it twice: two fields agreeing
                # implies corroboration that does not exist. "gcat-state" means
                # the site knows no operator BY NAME but an operator-focused
                # catalogue puts the operator in a different country from the
                # one the registry attributes the object to, so the value is a
                # country and the card must not label it as an operator.
                "organizationSource": organization_source,
                # The public page behind a curated claim, so a reader can check
                # it and a reviewer can audit it.
                "purposeSource": purpose_source,
                # Set after this loop by attach_background_shape(): a shortened, at most
                # two-paragraph opening for a description too long for the card, and the
                # researched paragraph about this object's FLEET with its own separate
                # citation. Both are absent for most objects and absent is the ordinary
                # case: the card then prints `purpose` whole, exactly as it always has.
                # Both characterisations of a disputed attribution, each with
                # its own citation, so the interface can show the reader that
                # the claim is contested at the point the claim is made.
                "contestedAttribution": notes or None,
                # Publicly documented participation in a programme that is not
                # this spacecraft's own: a hosted payload, leased capacity, a
                # shared bus, a guest instrument, or a partner's stake in the
                # system. Every element carries the citation that states it.
                # Absent (null) where the public record says nothing -- never
                # inferred from orbit, name, owner or company.
                "programmes": programmes or None,
                "omm": normalized_omm,
            }
        )

    total_available = len(satellites)
    satellites = select_catalog_satellites(satellites, max_satellites)
    satellites.sort(key=lambda record: record["id"])
    attach_orbital_lifetime(satellites, data_root)
    # DOES EACH FLEET AGREE WITH ITSELF? -- and if it does, every one of its
    # members carries that finding.
    #
    # Judged over the RETAINED records rather than the full catalog, so every
    # count published below can be recomputed by anyone holding the artifact.
    # The alternative reads a larger, truer cohort and publishes a denominator
    # nobody can check, and this file already has a comment about why that is
    # not evidence of anything.
    #
    # `classificationBasis` IS NOT TOUCHED. A Starlink stays `name-pattern`,
    # because that is still exactly how its mission label was arrived at and
    # destroying that record to change a chip would be losing data to win an
    # argument. This is an ADDITIONAL fact recorded beside it, which is what
    # lets the interface's rendering rule be re-tuned later -- Sean intends to
    # revisit the doctrine -- without re-deriving or rebuilding anything.
    cohort_verdicts = satnogs_verify.constellation_cohort_verdicts(satellites)
    for record in satellites:
        verdict = cohort_verdicts.get(record.get("constellation") or "")
        if verdict and verdict["consistent"]:
            # A string rather than a flag, so a second kind of mission
            # corroboration can arrive later without a schema change.
            record["missionCorroboration"] = "cohort-consistent"
    # The Satellite Background section's shape: the shortened opening for the long
    # descriptions, and the researched fleet paragraph for the thin ones. Runs over the
    # RETAINED records so the member count it publishes is one a reader can recompute
    # from the artifact.
    attach_background_shape(satellites)
    report_catalog_drift(prior_catalog, satellites, TAXONOMY_VERSION)
    upstream_as_of = max(record["omm"]["EPOCH"] for record in satellites)
    return {
        "schema": 1,
        "upstreamAsOf": upstream_as_of,
        # USSPACECOM's blanket approval to redistribute basic SSA data - OMMs,
        # SATCAT, decay data - is "conditioned on appropriate citation", so the
        # citation travels with the data and names whichever upstream fed it.
        "source": source_citation(catalog_scope),
        "taxonomyVersion": TAXONOMY_VERSION,
        # One row per programme in data/programme_participation.json, with the
        # count of retained objects attached to it, so the browser can offer a
        # "programme" facet beside constellation and owner without scanning the
        # catalog to discover which programmes exist.
        "programmeCatalog": programme_catalog(
            participation,
            {
                record["id"]: record["programmes"]
                for record in satellites
                if record.get("programmes")
            },
        ),
        # Whether the operator's country was CHECKED, and what checking found.
        # The same distinction `fleetEvidence` draws, for the same reason: a
        # missing GCAT mirror and an object whose operator sits in the state
        # that registered it both publish no `operatorState`, and only one of
        # them is a finding.
        "operatorStateEvidence": {
            "available": bool(operator_records),
            "source": "Jonathan McDowell's General Catalog of Artificial Space Objects (GCAT)",
            "url": "https://planet4589.org/space/gcat/",
            "checkedObjects": sum(1 for record in satellites if record["id"] in operator_records),
            "differingObjects": sum(1 for record in satellites if record.get("operatorState")),
            # Objects where GCAT has a row, holds a DIFFERENT country, and names
            # a different spacecraft than the register does -- so nothing was
            # read off it. A labelled gap: the cross-check ran and declined,
            # which is not the same as the cross-check finding agreement. Counted
            # over the objects that SHIP, like its two neighbours; a loop counter
            # over every candidate the builder walked read 64 for a catalog
            # carrying 34, and a number nobody can reproduce from the artifact is
            # not evidence of anything.
            "identityDisputedObjects": sum(
                1 for record in satellites
                if record["id"] in operator_records
                and not gcat_identity_agrees(record["name"], operator_records[record["id"]])
                and not operator_state_agrees(
                    record["ownerCode"], record["ownerLabel"], operator_records[record["id"]]["state"]
                )
            ),
        },
        "fleetEvidence": {
            "available": fleet_evidence_available,
            "carriedForwardObjects": carried_used,
            "carriedForwardAsOf": carried_as_of,
        },
        # Every fleet in this release and whether it agrees with itself, with
        # the numbers each verdict was reached on. Published in full -- the
        # REFUSALS included, each with the sentence saying why -- because a
        # cohort that could not vouch for its members is the interesting half:
        # it is why 159 Yaogan cards keep their question mark.
        "cohortEvidence": {
            "rule": (
                "A fleet vouches for its members' MISSION CLASS when it has at least "
                f"{satnogs_verify.COHORT_MIN_MEMBERS} members here, at least "
                f"{satnogs_verify.COHORT_AGREEMENT_SHARE:.0%} of them share one registration and "
                "one mission, two of them went up on the same launch, and nothing "
                "independent disputes any of them. It establishes what these spacecraft "
                "are, never which unit of the fleet any one of them is."
            ),
            "minMembers": satnogs_verify.COHORT_MIN_MEMBERS,
            "agreementShare": satnogs_verify.COHORT_AGREEMENT_SHARE,
            "corroboratedObjects": sum(
                1 for record in satellites if record.get("missionCorroboration")
            ),
            "constellations": cohort_verdicts,
        },
        "totalAvailable": total_available,
        "selectionNote": f"Teaching catalog includes {len(satellites):,} objects from the {catalog_scope} ({total_available:,} available before the browser ceiling); complete Starlink launch cohorts from the latest {STARLINK_RECENT_COHORT_DAYS} days are retained, then older large-constellation members are deterministically hash-sampled for mobile performance.",
        "satellites": satellites,
    }


def source_citation(catalog_scope: str) -> dict[str, Any]:
    """Cite the upstream that actually supplied this release's elements.

    USSPACECOM grants express blanket approval for redistributing basic SSA data
    "conditioned on appropriate citation", so this is a condition of use, not a
    courtesy. Category membership is Dr. Kelso's own curation and is credited
    separately whenever it contributed.
    """
    if catalog_scope.startswith("space-track"):
        return {
            "name": "Space-Track.org GP and SATCAT",
            "url": "https://www.space-track.org/",
            "attribution": (
                "Orbital element sets (OMM) and satellite catalog data courtesy of "
                "United States Space Command (USSPACECOM) / 18th Space Defense Squadron, "
                "obtained via Space-Track.org. Satellite mission categories courtesy of "
                "CelesTrak (Dr. T.S. Kelso)."
            ),
        }
    return {
        "name": "CelesTrak GP and SATCAT",
        "url": "https://celestrak.org/",
        "attribution": (
            "Orbital element sets and public catalog facts courtesy of CelesTrak "
            "(Dr. T.S. Kelso), derived from United States Space Command / "
            "18th Space Defense Squadron data."
        ),
    }


def parse_time(value: str) -> dt.datetime:
    """Parse an upstream time tag as UTC, including the naive ones.

    NOAA publishes time_tag both ways. goes/.../xrays-*.json carries a
    Z; json/planetary_k_index_1m.json, products/solar-wind/plasma-*
    and products/solar-wind/mag-* do not, and every SWPC feed is UTC
    whether or not it says so.

    fromisoformat returns a NAIVE datetime for those, and .astimezone
    on a naive datetime assumes the HOST's local zone. On a builder running in
    US Eastern that silently added four hours to every sample of every
    unsuffixed feed. Measured on release 684cf0ca: the geomagnetic Kp series
    ran to 2026-08-20T01:33Z beside its own observedAt of 21:33, and the
    solar-wind and IMF series to 01:31Z beside 21:31 — three of the five
    driver sparklines on the awareness page drew half their points into the
    future while carrying an OBSERVED badge. The X-ray tile was correct, and
    only because its feed happens to print the Z.

    Nothing on this site may imply a measurement it does not have, and a
    timestamp is part of the measurement. A tag with no zone is UTC.
    """

    parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def newest(records: list[dict[str, Any]], predicate=lambda _: True) -> dict[str, Any]:
    choices = [row for row in records if row.get("time_tag") and predicate(row)]
    if not choices:
        return {}
    return max(choices, key=lambda row: parse_time(str(row["time_tag"])))


def shue_boundary(dynamic_pressure_npa: float | None, bz_gsm_nt: float | None) -> tuple[float | None, float | None]:
    if dynamic_pressure_npa is None or bz_gsm_nt is None or dynamic_pressure_npa <= 0:
        return None, None
    r0 = (10.22 + 1.29 * math.tanh(0.184 * (bz_gsm_nt + 8.14))) * dynamic_pressure_npa ** (-1 / 6.6)
    flaring_alpha = (0.58 - 0.007 * bz_gsm_nt) * (1 + 0.024 * math.log(dynamic_pressure_npa))
    return r0, flaring_alpha


def propagated_driver_series(raw: Any, history_hours: int = 48, cadence_minutes: int = 5) -> list[dict[str, Any]]:
    if not isinstance(raw, list) or len(raw) < 2 or not isinstance(raw[0], list):
        return []
    headers = [str(value) for value in raw[0]]
    rows: dict[int, dict[str, Any]] = {}
    cutoff = utcnow() - dt.timedelta(hours=history_hours, minutes=15)
    for values in raw[1:]:
        if not isinstance(values, list):
            continue
        record = dict(zip(headers, values))
        valid_text = record.get("propagated_time_tag")
        observed_text = record.get("time_tag")
        if not valid_text or not observed_text:
            continue
        try:
            valid_at = parse_time(str(valid_text))
            observed_at = parse_time(str(observed_text))
            speed = float(record["speed"])
            density = float(record["density"])
            bz = float(record["bz"])
        except (KeyError, TypeError, ValueError):
            continue
        if valid_at < cutoff or speed <= 0 or density < 0:
            continue
        bucket = int(valid_at.timestamp() // (cadence_minutes * 60))
        pressure = 1.6726e-6 * density * speed**2
        r0, alpha = shue_boundary(pressure, bz)
        # NOAA's propagated product carries the full IMF and velocity vectors
        # (`bx, by, bz, bt, vx, vy, vz`) and this function used to keep three
        # columns and discard the rest. IMF By is what makes the clock angle
        # computable, and the clock angle is the switch that governs dayside
        # reconnection -- so the discarded columns were the difference between
        # a solar-wind readout and a storm narrative. `derive_driver_terms`
        # owns every formula; nothing is duplicated here.
        terms = derive_driver_terms(record)
        bx = terms_value(record, "bx")
        by = terms_value(record, "by")
        bt = terms_value(record, "bt")
        rows[bucket] = {
            "validAt": iso_z(valid_at),
            "observedAt": iso_z(observed_at),
            "speedKps": round(speed, 2),
            "densityCm3": round(density, 3),
            "bzGsmNt": round(bz, 3),
            "bxNt": round(bx, 3) if bx is not None else None,
            "byNt": round(by, 3) if by is not None else None,
            "btNt": round(bt, 3) if bt is not None else None,
            "dynamicPressureNpa": round(pressure, 4),
            "magneticPressureNpa": (
                round(terms["magneticPressureNpa"], 5)
                if terms["magneticPressureNpa"] is not None else None
            ),
            "clockAngleDeg": (
                round(terms["clockAngleDeg"], 1) if terms["clockAngleDeg"] is not None else None
            ),
            "newellCoupling": (
                round(terms["newellCoupling"], 1) if terms["newellCoupling"] is not None else None
            ),
            "subsolarStandoffRe": round(r0, 3) if r0 is not None else None,
            "flaringAlpha": round(alpha, 5) if alpha is not None else None,
        }
    return [rows[bucket] for bucket in sorted(rows)]


def newest_propagated_record(raw: Any, valid_at: str | None) -> dict[str, Any] | None:
    """The raw NOAA propagated row whose Earth-arrival time is `valid_at`.

    The published driver series is bucketed and renamed; the storm block needs
    NOAA's own column names to derive coupling. Recovering the raw row by its
    propagated time tag keeps the two in step, and in particular keeps the
    solar-wind guard's decision authoritative: if the guard truncated the
    series, `valid_at` is the last surviving sample and this returns that one.
    """
    if not valid_at or not isinstance(raw, list) or len(raw) < 2 or not isinstance(raw[0], list):
        return None
    headers = [str(value) for value in raw[0]]
    for values in reversed(raw[1:]):
        if not isinstance(values, list):
            continue
        record = dict(zip(headers, values))
        try:
            arrival = iso_z(parse_time(str(record["propagated_time_tag"])))
        except (KeyError, TypeError, ValueError):
            continue
        if arrival == valid_at:
            return record
    return None


def terms_value(record: dict[str, Any], key: str) -> float | None:
    """One numeric column of a propagated solar-wind record, or None.

    NOAA leaves a column null rather than omitting it when a spacecraft channel
    is out, so a missing value must degrade that one field and nothing else.
    """
    try:
        value = float(record[key])
    except (KeyError, TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def downsample(
    records: list[dict[str, Any]],
    field: str,
    *,
    predicate=lambda _: True,
    minutes: int = 10,
    hours: int = 6,
) -> list[dict[str, Any]]:
    cutoff = utcnow() - dt.timedelta(hours=hours)
    buckets: dict[int, tuple[dt.datetime, float]] = {}
    for row in records:
        if not predicate(row) or row.get(field) is None or not row.get("time_tag"):
            continue
        observed = parse_time(str(row["time_tag"]))
        if observed < cutoff:
            continue
        bucket = int(observed.timestamp() // (minutes * 60))
        value = float(row[field])
        previous = buckets.get(bucket)
        if previous is None or observed > previous[0]:
            buckets[bucket] = (observed, value)
    # Significant figures, not decimal places. `round(x, 5)` is fine for Dst in
    # nanotesla and speed in km/s, and it silently annihilates GOES X-ray flux,
    # which is of order 1e-7 W/m^2: every one of the 576 published history
    # values came out as exactly 0.0. The site then drew a flat line at zero
    # while the headline reading said B2.2 — a picture of the rounding rule
    # rather than of the Sun.
    #
    # Six significant figures keeps every series this function is used for well
    # inside float precision and costs a few bytes per point.
    def trimmed(value: float) -> float:
        if value == 0 or not math.isfinite(value):
            return value
        return round(value, 5 - int(math.floor(math.log10(abs(value)))))

    return [{"time": iso_z(item[0]), "value": trimmed(item[1])} for _, item in sorted(buckets.items())]


def xray_class(flux: float | None) -> str:
    if not flux or flux <= 0:
        return "—"
    families = ((1e-4, "X"), (1e-5, "M"), (1e-6, "C"), (1e-7, "B"), (1e-8, "A"))
    for threshold, label in families:
        if flux >= threshold:
            return f"{label}{flux / threshold:.1f}"
    return f"A{flux / 1e-8:.1f}"


def deterministic_weather_brief(speed: float | None, bz: float | None, kp: float | None, flare_class: str) -> dict[str, str]:
    if speed is None:
        wind_phrase = "The upstream solar-wind speed is unavailable"
    elif speed >= 600:
        wind_phrase = "The upstream solar wind is fast"
    elif speed >= 450:
        wind_phrase = "The upstream solar wind is moderate"
    else:
        wind_phrase = "The upstream solar wind is relatively slow"

    if bz is None:
        coupling_phrase = "IMF Bz is unavailable, so magnetic coupling cannot be characterized from this snapshot"
    elif bz <= -5:
        coupling_phrase = "IMF Bz is southward enough to favor stronger dayside magnetic coupling if it persists"
    elif bz >= 5:
        coupling_phrase = "IMF Bz is northward, which is generally less favorable for sustained dayside reconnection"
    else:
        coupling_phrase = "IMF Bz is near neutral in this snapshot"

    if kp is None:
        kp_phrase = "Planetary Kp is unavailable"
    elif kp >= 5:
        kp_phrase = "Planetary Kp is in NOAA geomagnetic-storm range"
    elif kp >= 4:
        kp_phrase = "Planetary Kp is active but below NOAA storm threshold"
    else:
        kp_phrase = "Planetary Kp is below NOAA geomagnetic-storm threshold"

    flare_phrase = f"The current GOES long-channel X-ray level is {flare_class}." if flare_class != "—" else "The current GOES X-ray class is unavailable."
    return {
        "kind": "deterministic",
        "text": f"{wind_phrase}; {coupling_phrase}. {kp_phrase}. {flare_phrase}",
        "caveat": "A fact-bounded snapshot, not a forecast or a local spacecraft-effects assessment.",
    }


def brief_fact_packet(weather: dict[str, Any]) -> dict[str, Any]:
    return {
        "solarWind": {key: weather["solarWind"].get(key) for key in ("observedAt", "sourceSpacecraft", "speedKps", "densityCm3", "dynamicPressureNpa")},
        "imf": {key: weather["imf"].get(key) for key in ("observedAt", "sourceSpacecraft", "btNt", "bzGsmNt")},
        "geomagnetic": {key: weather["geomagnetic"].get(key) for key in ("observedAt", "kp")},
        "xray": {key: weather["xray"].get(key) for key in ("observedAt", "class")},
        "ionosphere": {key: weather["ionosphere"].get(key) for key in ("observedAt", "status", "tecRange", "medianHmF2Km")},
        "magnetopause": {key: weather["magnetopause"].get(key) for key in ("status", "model", "subsolarStandoffRe", "flaringAlpha", "caveat")},
    }


def validated_qwen_brief(facts: dict[str, Any]) -> dict[str, str] | None:
    """Publish the model-written brief only if it still describes these conditions.

    Every rule lives in pipeline/teaching_brief.py; read that module before
    changing the prompt. Rejection is deliberately silent: the caller falls back
    to the deterministic sentence, which is honest, just less interesting.

    The previous contract compared a hash of the whole fact packet, including
    every observedAt timestamp. Those change on each five-minute publication, so
    a brief was invalid within one cycle of being written and this function
    could never return anything.
    """
    from pipeline.teaching_brief import load_candidate, validate_candidate

    candidate = load_candidate(CACHE / "qwen-teaching-brief.json")
    return validate_candidate(candidate, facts, sha256, canonical_json)


#: Below this a non-empty OVATION grid is a fault rather than a quiet aurora.
#: Same number and same reasoning as the GloTEC floor in build_space_weather().
OVATION_MINIMUM_POINTS = 1000


def ovation_points(aurora: dict[str, Any]) -> list[dict[str, Any]]:
    """The poleward, non-zero OVATION cells, with bad triples skipped and counted.

    Lifted out of build_space_weather() so it can actually be tested. It used to
    be a list comprehension buried 150 lines inside a function that fetches from
    six upstreams, which meant the failure path below had no test over it and no
    way to acquire one -- the "green tests that never execute the production
    path" shape this codebase has already produced four times.

    build_space_weather() is called with NO try/except around it, so anything
    raised here takes the catalog, geospace, D-RAP and the manifest down with it.
    Two faults were possible and both are now contained:

      1. A single malformed coordinate triple. float() inside the old
         comprehension raised ValueError straight out of build_space_weather, so
         one bad element out of ~185,000 stopped the entire site's data.
      2. An absent or empty OVATION response, which is the legitimate "OVATION is
         not there this cycle" case. It is now tolerated exactly as GloTEC's is:
         the aurora layer reports no data and everything else still publishes.
         src/globe.ts already guards an empty point list.

    A non-empty but implausibly short grid still raises, unchanged and
    deliberately not widened, because that is a fault rather than an absence.
    """
    points: list[dict[str, Any]] = []
    unusable = 0
    for point in aurora.get("coordinates", []):
        try:
            if len(point) < 3:
                continue
            longitude, latitude, probability = float(point[0]), float(point[1]), float(point[2])
        except (TypeError, ValueError):
            unusable += 1
            continue
        if probability <= 0 or abs(latitude) < 30:
            continue
        points.append({
            "lon": int((longitude + 180) % 360 - 180),
            "lat": int(latitude),
            "probability": int(probability),
        })
    if unusable:
        print(f"NOTE: skipped {unusable} unusable NOAA OVATION coordinate triples; "
              f"the remaining {len(points)} points are published", flush=True)
    if len(points) < OVATION_MINIMUM_POINTS:
        if points:
            raise RuntimeError(f"implausible NOAA OVATION point count: {len(points)}")
        print("WARNING: no NOAA OVATION points this cycle; the aurora layer will report no "
              "data rather than failing the whole cycle", flush=True)
    return points


def build_space_weather() -> dict[str, Any]:
    wind = fetch_json(NOAA_WIND, 4 * 60)
    mag = fetch_json(NOAA_MAG, 4 * 60)
    kp = fetch_json(NOAA_KP, 4 * 60)
    xray = fetch_json(NOAA_XRAY, 4 * 60)
    protons = fetch_json(NOAA_PROTONS, 4 * 60)
    electrons = fetch_json(NOAA_ELECTRONS, 4 * 60)
    glotec_index = fetch_json(NOAA_GLOTEC_INDEX, 4 * 60)
    aurora = fetch_json(NOAA_AURORA, 4 * 60)
    noaa_scales = fetch_json(NOAA_SCALES, 4 * 60)
    alerts = fetch_json(NOAA_ALERTS, 4 * 60)
    kp_forecast = fetch_json(NOAA_KP_FORECAST, 4 * 60)
    three_day_forecast = fetch_text(NOAA_THREE_DAY, 10 * 60)
    three_day_geomag = fetch_text(NOAA_THREE_DAY_GEOMAG, 10 * 60)
    propagated_wind = fetch_json(NOAA_PROPAGATED_WIND, 4 * 60)
    driver_series = propagated_driver_series(propagated_wind)
    # Three Dst series, three evidence classes, one fetch each per cycle and no
    # retry. See pipeline/storm_indices.py for why they must stay separate.
    storm_sources = fetch_storm_sources(fetch_json_once, max_age_seconds=4 * 60)
    outlook = normalize_swpc_outlook(
        noaa_scales=noaa_scales,
        three_day_forecast=three_day_forecast,
        three_day_geomag=three_day_geomag,
        kp_forecast=kp_forecast,
        alerts=alerts[:12] if isinstance(alerts, list) else alerts,
        retrieved_at=utcnow(),
    )
    # GloTEC used to abort the entire build when NOAA served an empty index,
    # which threw away perfectly good satellite, geospace, aurora and D-RAP data
    # for one missing layer. It happened again on 2026-08-08 and cost hours of
    # publishes. Its siblings (WAM-IPE, SWMF) already degrade by preserving the
    # prior artifact; GloTEC was the odd one out. It now behaves like them: the
    # TEC layer goes absent and says so, and everything else still publishes.
    # Recorded as decision 1.3 in docs/OPEN-WORK.md.
    glotec: dict[str, Any] = {}
    glotec_entry: dict[str, Any] = {}
    glotec_url = ""
    if not isinstance(glotec_index, list) or not glotec_index:
        print("WARNING: NOAA GloTEC manifest is empty; publishing without the TEC layer "
              "rather than failing the whole cycle")
    else:
        glotec_entry = max(glotec_index, key=lambda item: parse_time(str(item["time_tag"])))
        glotec_url = urllib.parse.urljoin(NOAA_BASE, str(glotec_entry["url"]))
        try:
            glotec = fetch_json(glotec_url, 30 * 24 * 60 * 60)
        except Exception as error:  # noqa: BLE001
            print(f"WARNING: NOAA GloTEC frame unavailable ({error}); publishing without "
                  "the TEC layer rather than failing the whole cycle")
            glotec = {}

    # The selection rule used to be `active and overall_quality == 0`, i.e. one
    # spacecraft's opinion of itself. During the May 2024 Gannon storm DSCOVR
    # reported `overall_quality = 0` for 549 minutes while its plasma speed was
    # wrong by a factor of two, which would have made this site draw an expanded
    # magnetosphere during the worst compression event in twenty years.
    # pipeline/solar_wind_guard.py corroborates against the other L1 monitors in
    # these same two files, against physical bounds, and against the magnetic
    # field's behaviour across any sharp plasma step, and returns predicates that
    # select nothing when the sample must not be published.
    wind_quality = assess_rtsw(wind, mag, utcnow())
    active = wind_quality.wind_row_predicate()
    active_mag = wind_quality.imf_row_predicate()
    current_wind = newest(wind, active)
    current_mag = newest(mag, active_mag)
    # NOAA derives the propagated series from whichever L1 monitor is active, so
    # a faulty plasma instrument poisons it too -- and the browser prefers this
    # series over the headline sample when it draws the Shue boundary.
    driver_series = wind_quality.truncate_driver_series(driver_series)

    # The storm block's coupling numbers must be derived from the same sample
    # the guard let through, not from whatever NOAA published most recently.
    # When the guard withholds everything, `storm_driver` is None and the
    # coupling panel disappears rather than freezing on a stale value.
    storm_driver = newest_propagated_record(
        propagated_wind, driver_series[-1]["validAt"] if driver_series else None
    )
    storm = build_storm_indices(
        model_dst_raw=storm_sources.get("model"),
        usgs_dst_raw=storm_sources.get("usgs"),
        kyoto_dst_raw=storm_sources.get("kyoto"),
        driver=storm_driver,
        now=utcnow(),
    )
    current_kp = newest(kp)
    long_xray = lambda row: row.get("energy") == "0.1-0.8nm"
    current_xray = newest(xray, long_xray)
    proton_channel = lambda row: str(row.get("energy", "")).replace(" ", "") in {">=10MeV", ">10MeV"}
    electron_channel = lambda row: ">=2" in str(row.get("energy", "")).replace(" ", "") or ">2" in str(row.get("energy", "")).replace(" ", "")
    current_proton = newest(protons, proton_channel) or newest(protons)
    current_electron = newest(electrons, electron_channel) or newest(electrons)

    speed = float(current_wind["proton_speed"]) if current_wind.get("proton_speed") is not None else None
    density = float(current_wind["proton_density"]) if current_wind.get("proton_density") is not None else None
    pressure = 1.6726e-6 * density * speed**2 if speed is not None and density is not None else None
    bz = float(current_mag["bz_gsm"]) if current_mag.get("bz_gsm") is not None else None
    kp_value = float(current_kp["kp_index"]) if current_kp.get("kp_index") is not None else None
    current_xray_class = xray_class(float(current_xray["flux"])) if current_xray.get("flux") is not None else "—"
    r0, flaring_alpha = shue_boundary(pressure, bz)

    tec_points: list[dict[str, Any]] = []
    hmf2_values: list[float] = []
    tec_values: list[float] = []
    lon_values: set[float] = set()
    lat_values: set[float] = set()
    glotec_unusable = 0
    for feature in glotec.get("features", []):
        coordinate = feature.get("geometry", {}).get("coordinates", [])
        properties = feature.get("properties", {})
        if len(coordinate) < 2:
            continue
        # Same reasoning as the OVATION loop below: build_space_weather() has no
        # try/except around it, so an unparseable coordinate in ONE feature used
        # to raise ValueError out of here and abort the whole publish -- catalog,
        # geospace, D-RAP and all. The feature is skipped and counted instead.
        try:
            longitude, latitude = float(coordinate[0]), float(coordinate[1])
        except (TypeError, ValueError):
            glotec_unusable += 1
            continue
        tec = properties.get("tec")
        anomaly = properties.get("anomaly")
        hmf2 = properties.get("hmF2")
        quality = properties.get("quality_flag")
        if isinstance(tec, (int, float)):
            tec_values.append(float(tec))
        if isinstance(hmf2, (int, float)) and 100 < float(hmf2) < 1000:
            hmf2_values.append(float(hmf2))
        lon_values.add(longitude)
        lat_values.add(latitude)
        tec_points.append(
            {
                "lon": round(longitude, 2),
                "lat": round(latitude, 2),
                "tec": round(float(tec), 2) if isinstance(tec, (int, float)) else None,
                "anomaly": round(float(anomaly), 2) if isinstance(anomaly, (int, float)) else None,
                "hmF2": round(float(hmf2), 1) if isinstance(hmf2, (int, float)) else None,
                "quality": int(quality) if isinstance(quality, (int, float)) else None,
            }
        )
    if glotec_unusable:
        print(f"NOTE: skipped {glotec_unusable} unusable GloTEC features; the remaining "
              f"{len(tec_points)} points are published", flush=True)
    if len(tec_points) < 1000:
        # Zero points is the legitimate "GloTEC is absent this cycle" case, which
        # the fetch above now tolerates. Only a non-empty but implausible grid is
        # a real fault worth failing on.
        if tec_points:
            raise RuntimeError(f"implausible GloTEC point count: {len(tec_points)}")
        print("WARNING: no GloTEC points this cycle; the TEC layer will report no data")
    # See ovation_points(): an absent OVATION no longer aborts the whole publish.
    aurora_points = ovation_points(aurora)
    sorted_lons = sorted(lon_values)
    sorted_lats = sorted(lat_values)
    lon_step = statistics.median(b - a for a, b in zip(sorted_lons, sorted_lons[1:])) if len(sorted_lons) > 1 else 5
    lat_step = statistics.median(b - a for a, b in zip(sorted_lats, sorted_lats[1:])) if len(sorted_lats) > 1 else 2.5

    sources = [
        {"product": "Real-time solar wind plasma", "url": NOAA_WIND, "status": "observed", "observedAt": wind_quality.observed_at(current_wind, wind_quality.wind), "corroboration": wind_quality.wind.verdict, "corroborationNote": wind_quality.wind.notice},
        {"product": "Real-time interplanetary magnetic field", "url": NOAA_MAG, "status": "observed", "observedAt": wind_quality.observed_at(current_mag, wind_quality.imf), "corroboration": wind_quality.imf.verdict, "corroborationNote": wind_quality.imf.notice},
        {"product": "Planetary K index", "url": NOAA_KP, "status": "observed", "observedAt": str(current_kp.get("time_tag") or "")},
        {"product": "GOES X-ray flux", "url": NOAA_XRAY, "status": "observed", "observedAt": str(current_xray.get("time_tag") or "")},
        *([{"product": "GloTEC", "url": glotec_url, "status": "assimilated", "observedAt": str(glotec_entry["time_tag"])}] if glotec_entry else []),
        {"product": "OVATION aurora forecast", "url": NOAA_AURORA, "status": "forecast", "observedAt": str(aurora.get("Forecast Time") or "")},
        {"product": "NOAA Space Weather Scales", "url": NOAA_SCALES, "status": "observed", "observedAt": str(outlook["noaaScales"]["latestObserved"].get("asOf") or "")},
        {"product": "NOAA 3-Day Forecast", "url": NOAA_THREE_DAY, "status": "forecast", "observedAt": str(outlook["threeDayForecast"].get("issuedAt") or "")},
        {"product": "NOAA 3-Day Geomagnetic Forecast", "url": NOAA_THREE_DAY_GEOMAG, "status": "forecast", "observedAt": str(outlook["geomagneticForecast"].get("issuedAt") or "")},
        *storm_source_records(storm),
    ]
    weather = {
        "schema": 1,
        "sources": sources,
        "solarWind": {
            # Never the empty string: the browser calls new Date(...).toISOString()
            # on this and would throw while rendering. See PublishDecision.observed_at.
            "observedAt": wind_quality.observed_at(current_wind, wind_quality.wind),
            "sourceSpacecraft": wind_quality.wind_label,
            "speedKps": round(speed, 1) if speed is not None else None,
            "densityCm3": round(density, 2) if density is not None else None,
            "temperatureK": round(float(current_wind["proton_temperature"])) if current_wind.get("proton_temperature") is not None else None,
            "dynamicPressureNpa": round(pressure, 3) if pressure is not None else None,
            "series": downsample(wind, "proton_speed", predicate=wind_quality.wind_series_predicate()),
        },
        "imf": {
            "observedAt": wind_quality.observed_at(current_mag, wind_quality.imf),
            "sourceSpacecraft": wind_quality.imf_label,
            "btNt": round(float(current_mag["bt"]), 2) if current_mag.get("bt") is not None else None,
            "bzGsmNt": round(bz, 2) if bz is not None else None,
            "series": downsample(mag, "bz_gsm", predicate=wind_quality.imf_series_predicate()),
        },
        "geomagnetic": {
            "observedAt": str(current_kp.get("time_tag") or ""),
            "kp": round(kp_value, 2) if kp_value is not None else None,
            "series": downsample(kp, "kp_index", hours=24, minutes=15),
        },
        "xray": {
            "observedAt": str(current_xray.get("time_tag") or ""),
            "fluxWm2": float(current_xray["flux"]) if current_xray.get("flux") is not None else None,
            "class": current_xray_class,
            "series": downsample(xray, "flux", predicate=long_xray, minutes=5, hours=48),
        },
        "particles": {
            "protonObservedAt": str(current_proton.get("time_tag") or ""),
            "protonFlux": float(current_proton["flux"]) if current_proton.get("flux") is not None else None,
            "protonEnergy": str(current_proton.get("energy") or "channel unavailable"),
            "electronObservedAt": str(current_electron.get("time_tag") or ""),
            "electronFlux": float(current_electron["flux"]) if current_electron.get("flux") is not None else None,
            "electronEnergy": str(current_electron.get("energy") or "channel unavailable"),
        },
        "ionosphere": {
            "observedAt": str(glotec_entry["time_tag"]) if glotec_entry else "",
            "status": "assimilated",
            "gridDegrees": {"lon": round(lon_step, 2), "lat": round(lat_step, 2)},
            "tecRange": [round(min(tec_values), 1), round(max(tec_values), 1)] if tec_values else [0, 1],
            "medianHmF2Km": round(statistics.median(hmf2_values), 1) if hmf2_values else None,
            "points": tec_points,
        },
        "aurora": {
            "observedAt": str(aurora.get("Observation Time") or ""),
            "forecastAt": str(aurora.get("Forecast Time") or ""),
            "status": "forecast",
            "model": "NOAA OVATION 2020",
            # max() of an empty sequence raises, which would have re-armed the
            # whole-publish abort three lines after it was just disarmed above.
            # null means "no aurora data this cycle", the same thing an empty
            # points list means. Not 0: an absent OVATION and an OVATION that
            # reports no aurora anywhere are different claims, and only the
            # second of them has a maximum of zero.
            #
            # src/types.ts declares this field `number`, not `number | null`, but
            # nothing in src/ reads it -- only the declaration exists -- so the
            # null is inert today. Flagged for Sean rather than changed here,
            # because src/ belongs to another agent this session.
            "maximumProbability": (max(point["probability"] for point in aurora_points)
                                   if aurora_points else None),
            "points": aurora_points,
            "caveat": "Model-derived aurora viewing probability; daylight, cloud, terrain, and local viewing conditions are not represented on the globe.",
        },
        "magnetopause": {
            "status": "model",
            "model": "Shue et al. (1998) empirical magnetopause boundary",
            "subsolarStandoffRe": round(r0, 2) if r0 is not None else None,
            "flaringAlpha": round(flaring_alpha, 4) if flaring_alpha is not None else None,
            "driverSeries": driver_series,
            "driverSource": "NOAA Geospace propagated solar wind; validAt is the propagated Earth-arrival time",
            "caveat": (
                "An axisymmetric empirical boundary driven by upstream pressure and IMF Bz; it is not a measured surface or a physics-based MHD simulation."
                + (f" {wind_quality.notice()}" if wind_quality.degraded else "")
            ),
            "cuspedBoundaries": {
                "status": "empirical",
                "note": (
                    "The Shue surface has no cusps by construction: r(theta) depends on solar "
                    "zenith angle only, with no azimuthal and no dipole-tilt term. Two published "
                    "crossing-fitted models that do have them are evaluated in the browser from "
                    "these same drivers: Nguyen et al. (2022) Model 3 for the magnetopause "
                    "current sheet and Lin et al. (2010) for the cusp inner boundary."
                ),
                "models": [
                    {
                        "id": "nguyen2022",
                        "label": "Nguyen et al. (2022) Model 3",
                        "surface": "magnetopause current sheet",
                        "doi": "10.1029/2021JA029776",
                        "fittedTo": "17,230 magnetopause crossings (THEMIS, Cluster, Double Star, MMS, ARTEMIS)",
                        "drivers": ["dynamicPressureNpa", "magneticPressureNpa", "clockAngleDeg", "bzGsmNt", "dipoleTiltDeg"],
                    },
                    {
                        "id": "lin2010",
                        "label": "Lin et al. (2010)",
                        "surface": "cusp inner boundary (the funnel wall)",
                        "doi": "10.1029/2009JA014235",
                        "fittedTo": "1,482 magnetopause crossings",
                        "drivers": ["dynamicPressureNpa", "magneticPressureNpa", "bzGsmNt", "dipoleTiltDeg"],
                    },
                ],
                "exteriorCusp": (
                    "Drawn together, the gap between them is the exterior cusp: Lin traces its "
                    "inner wall and Nguyen traces the current sheet outside it. Both are "
                    "empirical fits driven by live solar wind. Neither is an observation and "
                    "neither is an MHD simulation."
                ),
            },
        },
        "storm": storm,
        "dataQuality": wind_quality.as_dict(),
        "outlook": outlook,
    }
    facts = brief_fact_packet(weather)
    brief = validated_qwen_brief(facts) or deterministic_weather_brief(speed, bz, kp_value, current_xray_class)
    if wind_quality.degraded:
        # A model-written sentence must never be the thing that decides whether a
        # visitor hears about withheld data. When the guard fires, the
        # deterministic sentence is used and the guard's own words go first.
        # This project has a recorded incident where a generated health report
        # claimed all-clear over 105 real warnings; nothing here may repeat it.
        brief = deterministic_weather_brief(speed, bz, kp_value, current_xray_class)
        brief = {**brief, "text": f"{wind_quality.notice()} {brief['text']}"}
    weather["teachingBrief"] = brief
    return weather


def write_artifact(data_root: Path, prefix: str, value: Any) -> tuple[str, str]:
    encoded = canonical_json(value)
    digest = sha256(encoded)
    relative = f"artifacts/{prefix}-{digest[:16]}.json"
    destination = data_root / relative
    if not destination.exists():
        atomic_write(destination, encoded)
    else:
        destination.chmod(0o644)
    compressed = destination.with_suffix(destination.suffix + ".gz")
    if not compressed.exists():
        atomic_write(compressed, gzip.compress(encoded, compresslevel=9, mtime=0))
    else:
        compressed.chmod(0o644)
    if prefix.startswith("orbit-history-") and isinstance(value, dict) and "objects" in value:
        from pipeline.plot_views import publish_shard
        try:
            publish_shard(data_root, value, relative, digest, write_artifact)
        except Exception as error:  # The original archive remains publishable.
            print(f"WARNING: small plot views unavailable for {prefix}: {error}")
    return relative, digest


def prior_artifact_record(data_root: Path, key: str) -> dict[str, Any] | None:
    """Return a last-known-good manifest record only when its artifact exists."""
    manifest_path = data_root / "manifest.json"
    if not manifest_path.is_file():
        return None
    try:
        candidate = json.loads(manifest_path.read_text()).get(key)
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(candidate, dict):
        return None
    relative_path = candidate.get("path")
    digest = candidate.get("sha256")
    if not isinstance(relative_path, str) or not isinstance(digest, str):
        return None
    if not (data_root / relative_path).is_file():
        return None
    return candidate


def timed_environment_record(path: str, digest: str, bundle: dict[str, Any]) -> dict[str, Any]:
    """Build the common manifest contract from a validated temporal artifact."""
    time_record = bundle.get("time")
    frames = bundle.get("frames")
    if not isinstance(time_record, dict) or not isinstance(frames, list) or not frames:
        raise ValueError("environment artifact has no temporal frames")
    valid_from = time_record.get("availableFrom") or time_record.get("validFrom")
    valid_to = time_record.get("availableTo") or time_record.get("validTo")
    if not isinstance(valid_from, str) or not isinstance(valid_to, str):
        raise ValueError("environment artifact does not report an available time range")
    requested_from = time_record.get("requestedFrom", valid_from)
    requested_to = time_record.get("requestedTo", valid_to)
    no_data = time_record.get("noDataIntervals", [])
    if not isinstance(requested_from, str) or not isinstance(requested_to, str) or not isinstance(no_data, list):
        raise ValueError("environment artifact coverage metadata is malformed")
    # Validate ordering before the manifest makes these timestamps discoverable.
    if parse_time(valid_to) < parse_time(valid_from) or parse_time(requested_to) < parse_time(requested_from):
        raise ValueError("environment artifact time range is reversed")
    return {
        "path": path,
        "sha256": digest,
        "frameCount": len(frames),
        "validFrom": valid_from,
        "validTo": valid_to,
        "requestedFrom": requested_from,
        "requestedTo": requested_to,
        "coverageComplete": bool(time_record.get("coverageComplete", not no_data)),
        "actualCoverageHours": float(time_record.get("actualCoverageHours", 0)),
        "noDataIntervalCount": len(no_data),
        "sourceRetentionLimited": bool(time_record.get("sourceRetentionLimited", False)),
    }


# ---------------------------------------------------------------------------
# TEMPORARY: replays held back from the published artifact
# ---------------------------------------------------------------------------
#
# ADDED 2026-08-21. REMOVE BY SETTING THIS DICT TO {} — nothing else.
#
# WHY THIS EXISTS. `data/events.json` publishes on the five-minute
# `space-explorer-data.timer`. The frontend does not: it is baked into a Docker
# image and reaches visitors only on a deploy. So an event carrying a NEW
# `replay.kind` goes live BEFORE the code that can draw it, and
# `mountEventReplay` returns null for a kind it does not know. The page then
# renders `eventReplayBody` — the milestone prose with an EMPTY RECTANGLE where
# the chart belongs. It does not throw and it logs nothing.
#
# That is exactly what happened to `stpatricks-2015` on 2026-08-21. It is the
# first event to use `southward-turning`; the deployed bundle was built at
# 00:51 UTC and has no case for it, and the live page was verified serving a
# silent blank. Holding the `replay` block back makes the SAME deployed code
# take its other branch — `eventSchematicBody`, which prints the honest "no
# measured replay is published for this event yet" line. The card, the
# milestones and the sources all render correctly either way and are untouched.
#
# WHAT MUST BE TRUE TO REMOVE IT: a frontend is deployed whose
# `mountEventReplay` has a `case "southward-turning":`. Check with
#
#     curl -s https://sean.theinformed.org/space/ | grep -o 'assets/index-[^."]*\.js' | head -1
#     # then: curl -s https://sean.theinformed.org/space/assets/index-XXXX.js | grep -c southward-turning
#
# A non-zero count means the deployed bundle can draw it and this dict should
# go back to {} on the same day.
#
# WHAT THIS DOES NOT DO: it does not touch `data/events.json`. The replay is
# built, committed and complete in the source bundle, and every test and every
# local build still sees it. Only the PUBLISHED copy is thinned, and the
# manifest says so out loud.
REPLAY_WITHHOLDS: dict[str, str] = {}


def withhold_undeployable_replays(bundle: dict) -> tuple[dict, list[dict]]:
    """Strip the `replay` block from any event named in `REPLAY_WITHHOLDS`.

    Returns the bundle to publish and a record of what was held back. The
    record goes into the manifest so the withhold is visible from the live site
    and cannot quietly become permanent, and every build prints it, so a
    publish that is thinning the artifact says so every five minutes rather
    than once.

    A withhold naming an event that is not in the bundle is an ERROR, not a
    no-op: it means the id was renamed or the event was removed, and a stale
    entry here would sit silently doing nothing until somebody trusted it.
    """
    if not REPLAY_WITHHOLDS:
        return bundle, []
    known = {event["id"] for event in bundle["events"]}
    unknown = sorted(set(REPLAY_WITHHOLDS) - known)
    if unknown:
        raise SystemExit(
            f"REPLAY_WITHHOLDS names events that are not in data/events.json: {unknown}. "
            "Remove the stale entry or fix the id; a withhold that matches nothing is a "
            "withhold nobody can see.")

    published = dict(bundle)
    published["events"] = []
    record: list[dict] = []
    for event in bundle["events"]:
        reason = REPLAY_WITHHOLDS.get(event["id"])
        if reason is None or "replay" not in event:
            published["events"].append(event)
            continue
        thinned = {key: value for key, value in event.items() if key != "replay"}
        published["events"].append(thinned)
        record.append({
            "id": event["id"],
            "kind": event["replay"].get("kind"),
            "reason": reason,
            "withheldSince": "2026-08-21",
            "restoreBy": "set REPLAY_WITHHOLDS = {} in pipeline/build_release.py",
        })

    for held in record:
        print(f"!! WITHHELD from the published artifact: {held['id']} replay "
              f"(kind={held['kind']}). {held['reason']}", flush=True)
    print("!! The replay is intact in data/events.json. To restore it, set "
          "REPLAY_WITHHOLDS = {} in pipeline/build_release.py.", flush=True)
    return published, record


def publish_timed_environment_artifact(
    data_root: Path,
    *,
    key: str,
    prefix: str,
    builder: Callable[[], dict[str, Any]],
) -> dict[str, Any] | None:
    """Publish one exact time series, preserving the previous artifact on error."""
    previous = prior_artifact_record(data_root, key)
    try:
        bundle = builder()
        path, digest = write_artifact(data_root, prefix, bundle)
        return timed_environment_record(path, digest, bundle)
    except Exception as error:
        disposition = "preserving the prior artifact" if previous is not None else "omitting the unavailable artifact"
        print(f"WARNING: {key} reduction failed; {disposition}: {error}")
        return previous


def build_release(data_root: Path, max_satellites: int) -> dict[str, Any]:
    generated_at = iso_z(utcnow())
    catalog = build_catalog(max_satellites, data_root)
    weather = build_space_weather()
    ionosphere_model: dict[str, Any] | None = None
    prior_ionosphere_model: dict[str, Any] | None = None
    try:
        ionosphere_model = build_wam_ipe_bundle()
    except Exception as error:
        print(f"WARNING: NOAA WAM-IPE reduction failed; preserving the prior model artifact when available: {error}")
        prior_manifest_path = data_root / "manifest.json"
        if prior_manifest_path.is_file():
            with contextlib.suppress(OSError, json.JSONDecodeError):
                candidate = json.loads(prior_manifest_path.read_text()).get("ionosphereModel")
                if isinstance(candidate, dict) and (data_root / str(candidate.get("path", ""))).is_file():
                    prior_ionosphere_model = candidate
    # The neutral atmosphere, from the same forecast system as the ionosphere
    # above. It is a separate artifact rather than another field on that one
    # because it answers a different question — how much air is a satellite
    # flying through, and how much did the storm add — and because it falls back
    # to a different model on its own terms outside NOAA's WAM archive.
    thermosphere: dict[str, Any] | None = None
    prior_thermosphere: dict[str, Any] | None = None
    try:
        thermosphere = build_thermosphere_bundle()
    except Exception as error:
        print(f"WARNING: NOAA WAM neutral-density reduction failed; preserving the prior model artifact when available: {error}")
        prior_manifest_path = data_root / "manifest.json"
        if prior_manifest_path.is_file():
            with contextlib.suppress(OSError, json.JSONDecodeError):
                candidate = json.loads(prior_manifest_path.read_text()).get("thermosphere")
                if isinstance(candidate, dict) and (data_root / str(candidate.get("path", ""))).is_file():
                    prior_thermosphere = candidate

    # The empirical field that covers the REST of the timeline.
    #
    # NOAA WAM covers about a tenth of this site's clock -- 11.8 hours of a
    # 120-hour slider on 2026-08-20 -- and until this shipped the other nine
    # tenths showed one frozen WAM hour still badged MODEL. NRLMSIS is defined
    # at every instant because it is driven by indices rather than integrated
    # from an initial condition, and it is driven HERE by the same Kp series
    # this release publishes for its own chart, so the thermosphere and the
    # geomagnetic history on the page cannot disagree about whether there was a
    # storm. It is published across the whole window; the browser prefers WAM
    # wherever WAM has a frame and says which one it is drawing.
    thermosphere_msis: dict[str, Any] | None = None
    prior_thermosphere_msis: dict[str, Any] | None = None
    try:
        kp_rows = ((weather.get("outlook") or {}).get("kpForecast") or {}).get("rows") or []
        thermosphere_msis = build_msis_bundle(kp_rows=kp_rows)
    except Exception as error:
        print(f"WARNING: NRLMSIS empirical thermosphere failed; preserving the prior shard set when available: {error}")
        prior_manifest_path = data_root / "manifest.json"
        if prior_manifest_path.is_file():
            with contextlib.suppress(OSError, json.JSONDecodeError):
                candidate = json.loads(prior_manifest_path.read_text()).get("thermosphereEmpirical")
                # A sharded record is only usable if EVERY shard is still on
                # disk. Keeping a record whose shards the pruner has taken
                # publishes a manifest that 404s, which reaches the reader as a
                # layer that silently stopped working.
                if isinstance(candidate, dict) and isinstance(candidate.get("shards"), list) and candidate["shards"] and all(
                    isinstance(shard, dict) and (data_root / str(shard.get("path", ""))).is_file()
                    for shard in candidate["shards"]
                ):
                    prior_thermosphere_msis = candidate

    history_root = environment_history_root()
    geospace: dict[str, Any] | None = None
    ground_field: dict[str, Any] | None = None
    prior_geospace: dict[str, Any] | None = None
    prior_ground_field: dict[str, Any] | None = None
    try:
        geospace, ground_field = build_geospace_release_bundle(history_root / "geospace")
    except Exception as error:
        print(f"WARNING: NOAA SWMF reduction failed; preserving the prior model artifact when available: {error}")
        prior_manifest_path = data_root / "manifest.json"
        if prior_manifest_path.is_file():
            with contextlib.suppress(OSError, json.JSONDecodeError):
                candidate = json.loads(prior_manifest_path.read_text()).get("geospace")
                if isinstance(candidate, dict) and (data_root / str(candidate.get("path", ""))).is_file():
                    prior_geospace = candidate
    if ground_field is None:
        # The ground field is absent whenever the run published no usable
        # mag_grid for any selected time. Hold the last good artifact rather
        # than dropping the layer out of the manifest, exactly as the geospace
        # bundle does -- the browser's own coverage check then decides whether
        # the held window still contains the selected UTC.
        prior_manifest_path = data_root / "manifest.json"
        if prior_manifest_path.is_file():
            with contextlib.suppress(OSError, json.JSONDecodeError):
                candidate = json.loads(prior_manifest_path.read_text()).get("groundField")
                if isinstance(candidate, dict) and (data_root / str(candidate.get("path", ""))).is_file():
                    prior_ground_field = candidate
    drap_record = publish_timed_environment_artifact(
        data_root,
        key="drap",
        prefix="drap",
        builder=lambda: build_drap_release_bundle(history_root / "drap"),
    )
    aurora_record = publish_timed_environment_artifact(
        data_root,
        key="aurora",
        prefix="aurora",
        builder=lambda: build_aurora_release_bundle(history_root / "aurora"),
    )
    events_source = json.loads((ROOT / "data" / "events.json").read_text())
    events, withheld_replays = withhold_undeployable_replays(events_source)
    land = json.loads(fetch_bytes(LAND_URL, 30 * 24 * 60 * 60))
    provenance = {
        "schema": 1,
        "labels": {
            "observed": "Direct instrument or index observation at the displayed source and time.",
            "assimilated": "Observations combined with a numerical or empirical background model.",
            "model": "Calculated model output or empirical boundary estimate, not a direct measurement.",
            "forecast": "A prediction valid for a future time.",
            "schematic": "A teaching representation that preserves the concept but not literal scale or local conditions.",
        },
        "catalog": {
            "source": "Space-Track GP/SATCAT with CelesTrak operational and category curation",
            "urls": ["https://www.space-track.org/", "https://celestrak.org/satcat/search.php"],
            "method": "Space-Track OMM mean elements and SATCAT facts are joined by NORAD catalog ID. A VPS-only, rate-limited CelesTrak mirror contributes operational status and weekly category membership; it never supplies duplicate bulk elements. Mission taxonomy uses deterministic, versioned rules plus curated summaries.",
            "limitations": "Public GP elements are propagated predictions near their epoch, not telemetry or collision-quality ephemerides. Mission classifications without curated sources are best-effort teaching labels.",
        },
        "spaceWeather": {
            "source": "NOAA Space Weather Prediction Center",
            "urls": [NOAA_WIND, NOAA_MAG, NOAA_KP, NOAA_XRAY, NOAA_PROTONS, NOAA_ELECTRONS, NOAA_GLOTEC_INDEX, NOAA_AURORA, NOAA_DRAP_CURRENT, NOAA_SCALES, NOAA_ALERTS, NOAA_KP_FORECAST, NOAA_THREE_DAY, NOAA_THREE_DAY_GEOMAG, NOAA_MODEL_DST, USGS_DST, NOAA_KYOTO_DST, f"{NOMADS_ROOT}/", f"{NOMADS_WFS_ROOT}/"],
            "method": "Latest quality-controlled observations are reduced on bigmem-PC. Exact NOAA D-RAP and OVATION numeric grids are accumulated there and published with explicit cache gaps; unavailable times are never reconstructed from rendered images or interpolated between model frames. GloTEC is data-assimilative. The operational WAM-IPE full-field forecast is reduced at source grid points and electron density is derived by quasi-neutral summation of its seven published positive-ion densities. NOAA operational SWMF BATS-R-US cut planes and coupled RBE electron fields are reduced into separate consistent time sequences; the Shue surface remains a separate empirical context layer. Geomagnetic storm indices are published as three separate Dst traces that are never merged: NOAA Geospace SWMF modelled Dst (model, runs ahead of real time), USGS Dst3 (observed, ~4 minute latency), and the WDC Kyoto hourly quicklook index (observed, cited with doi:10.17593/14515-74000). IMF clock angle, the Newell coupling function, Akasofu epsilon, the Boyle cross-polar-cap potential and the Dessler-Parker-Sckopke ring-current energy are deterministic functions of NOAA's own propagated solar-wind columns.",
            "limitations": "GloTEC TEC is column-integrated. NOAA publicly distributes only the latest native OVATION probability grid, so exact numeric history begins with bigmem accumulation and gaps remain gaps. WAM-IPE supplies vertical model structure, not observed electron density: its published grid begins at 90 km, omits most of the D region and a negative-ion field, and ends at 2,655 km. GOES particle flux is local to a geostationary sensor. SWMF fields are physics-model output rather than measurements. Model distances are displayed on compressed spatial coordinates. Modelled Dst is an estimate, not a measurement; the Kyoto quicklook index is for monitoring only and its final values are routinely revised by 20-30 nT; the ring-current energy from the Dessler-Parker-Sckopke relation is good to about a factor of two. The cusped magnetopause models are empirical fits to spacecraft crossings driven by live solar wind, not observations of a surface and not MHD.",
        },
        "land": {
            "source": "Natural Earth 1:110m Admin 0 Countries",
            "url": LAND_URL,
            "license": "Public domain",
        },
        "groundStations": {
            "source": "Operator and agency publications, cited per station",
            "url": "https://sean.theinformed.org/space/",
            "license": "Station coordinates are published geographic facts; each row carries its own source and terms.",
            "method": "Hand-authored cited table; links are published operator statements joined to the catalog by NORAD ID.",
            "limitations": "Not a census. Nothing is inferred from orbits, pass timing or observation logs.",
        },
        "disclaimer": "Educational only. Not for satellite operations, conjunction assessment, navigation, communications planning, or official space-weather warning decisions.",
    }

    catalog_path, catalog_hash = write_artifact(data_root, "catalog", catalog)
    weather_path, weather_hash = write_artifact(data_root, "space-weather", weather)
    ionosphere_model_record = prior_ionosphere_model
    if ionosphere_model is not None:
        ionosphere_model_path, ionosphere_model_hash = write_artifact(data_root, "ionosphere-model", ionosphere_model)
        ionosphere_model_record = {
            "path": ionosphere_model_path,
            "sha256": ionosphere_model_hash,
            "frameCount": len(ionosphere_model["frames"]),
            "validFrom": ionosphere_model["frames"][0]["validAt"],
            "validTo": ionosphere_model["frames"][-1]["validAt"],
            "runAt": ionosphere_model["runAt"],
            "requestedHistoryHours": ionosphere_model["coverage"]["requestedHistoryHours"],
            "actualHistoryHours": ionosphere_model["coverage"]["actualHistoryHours"],
            "forecastHours": ionosphere_model["coverage"]["forecastHours"],
            "sourceRetentionLimited": ionosphere_model["coverage"]["sourceRetentionLimited"],
        }
    thermosphere_record = prior_thermosphere
    if thermosphere is not None:
        thermosphere_path, thermosphere_hash = write_artifact(data_root, "thermosphere", thermosphere)
        thermosphere_record = {
            "path": thermosphere_path,
            "sha256": thermosphere_hash,
            "frameCount": len(thermosphere["frames"]),
            "validFrom": thermosphere["validFrom"],
            "validTo": thermosphere["validTo"],
            "cycleStart": thermosphere["cycleStart"],
            "cadenceMinutes": thermosphere["cadenceMinutes"],
            "publishedAltitudesKm": thermosphere["publishedAltitudesKm"],
            # Which model produced these numbers, carried beside them rather than
            # inferred later: outside NOAA's WAM archive this layer is NRLMSIS,
            # and a reader scrubbing back to 2022 must see the name change.
            "model": thermosphere["model"]["model"],
            "modelLabel": thermosphere["model"]["modelLabel"],
            "modelStatus": thermosphere["model"]["modelStatus"],
            "fallbackApplied": thermosphere["model"]["fallbackApplied"],
            # A frame NOAA published that we could not read is a hole in the
            # series. Counted here so a short series is visible rather than
            # looking like a calm atmosphere.
            "skippedCount": len(thermosphere["skipped"]),
        }
    thermosphere_empirical_record = prior_thermosphere_msis
    if thermosphere_msis is not None:
        # One artifact per six-hour shard. The frames are anchored to whole UTC
        # hours, so a shard whose drivers have not changed hashes to the same
        # name it had five minutes ago and is neither rewritten nor re-sent:
        # the whole set is 13.2 MB of JSON, and anchoring it to `now` instead
        # would push all of that over the wire every cycle to say the same
        # thing. The reader downloads the ONE shard their clock is inside.
        shard_records: list[dict[str, Any]] = []
        for shard in thermosphere_msis["shards"]:
            shard_path, shard_hash = write_artifact(
                data_root, f"thermosphere-msis-{shard['validFrom'][:13].replace('-', '').replace('T', '')}", shard
            )
            shard_records.append({
                "path": shard_path,
                "sha256": shard_hash,
                "validFrom": shard["validFrom"],
                "validTo": shard["validTo"],
                "frameCount": shard["frameCount"],
                # Whether the hours in this shard were driven by the OBSERVED
                # Kp record or by NOAA's forecast of it. The badge on the card
                # reads this, so it is carried per shard rather than inferred
                # from a comparison with the clock in the browser.
                "driverStatus": shard["driverStatus"],
            })
        observed = [
            frame["validAt"]
            for shard in thermosphere_msis["shards"]
            for frame in shard["frames"]
            if frame["driverStatus"] == "observed"
        ]
        thermosphere_empirical_record = {
            "model": thermosphere_msis["model"]["model"],
            "modelLabel": thermosphere_msis["model"]["modelLabel"],
            "modelStatus": thermosphere_msis["model"]["modelStatus"],
            "modelShortName": thermosphere_msis["model"]["modelShortName"],
            "representation": thermosphere_msis["model"]["representation"],
            "limitation": thermosphere_msis["model"]["limitation"],
            "product": thermosphere_msis["source"]["product"],
            "productUrl": thermosphere_msis["source"]["productUrl"],
            "cadenceMinutes": thermosphere_msis["cadenceMinutes"],
            "shardHours": thermosphere_msis["shardHours"],
            "validFrom": thermosphere_msis["validFrom"],
            "validTo": thermosphere_msis["validTo"],
            "frameCount": sum(shard["frameCount"] for shard in thermosphere_msis["shards"]),
            "publishedAltitudesKm": thermosphere_msis["publishedAltitudesKm"],
            # The last hour whose drivers were the observed Kp record. After
            # this the field is driven by NOAA's forecast, and the card says
            # FORECAST rather than leaving the reader to guess.
            "observedThrough": max(observed) if observed else None,
            "drivers": thermosphere_msis["drivers"],
            "outsideDriversCount": len(thermosphere_msis["outsideDrivers"]),
            "shards": shard_records,
        }
    geospace_record = prior_geospace
    if geospace is not None:
        geospace_path, geospace_hash = write_artifact(data_root, "geospace-model", geospace)
        geospace_record = {
            "path": geospace_path,
            "sha256": geospace_hash,
            "frameCount": len(geospace["frames"]),
            "validFrom": geospace["frames"][0]["validAt"],
            "validTo": geospace["frames"][-1]["validAt"],
            # Additive coverage facts, so "why is the belt hidden at this UTC?"
            # is answerable from the manifest alone, as it already is for the
            # D-RAP and aurora layers.
            "requestedFrom": geospace["time"]["requestedFrom"],
            "requestedTo": geospace["time"]["requestedTo"],
            "coverageComplete": geospace["time"]["coverageComplete"],
            "actualCoverageHours": geospace["time"]["actualCoverageHours"],
            "noDataIntervalCount": len(geospace["time"]["noDataIntervals"]),
            "sourceRetentionLimited": geospace["time"]["sourceRetentionLimited"],
            "publishedCadenceMinutes": geospace["history"]["publishedCadenceMinutes"],
            "archivedFrameCount": geospace["history"]["archivedFrameCount"],
            "liveFrameCount": geospace["history"]["liveFrameCount"],
        }
    ground_field_record = prior_ground_field
    if ground_field is not None:
        ground_field_path, ground_field_hash = write_artifact(data_root, "ground-field", ground_field)
        ground_field_record = {
            "path": ground_field_path,
            "sha256": ground_field_hash,
            "frameCount": len(ground_field["frames"]),
            "validFrom": ground_field["frames"][0]["validAt"],
            "validTo": ground_field["frames"][-1]["validAt"],
            "requestedFrom": ground_field["time"]["requestedFrom"],
            "requestedTo": ground_field["time"]["requestedTo"],
            "coverageComplete": ground_field["time"]["coverageComplete"],
            "noDataIntervalCount": len(ground_field["time"]["noDataIntervals"]),
            # The bundle body carries no wall clock, so its content hash is
            # stable while the frames are. This is where "when was this built"
            # lives instead.
            "reducedAt": generated_at,
        }
    events_path, events_hash = write_artifact(data_root, "events", events)
    land_path, land_hash = write_artifact(data_root, "land-110m", land)
    provenance_path, provenance_hash = write_artifact(data_root, "provenance", provenance)
    release = generated_at.replace("-", "").replace(":", "")
    manifest = {
        "schema": 1,
        "release": release,
        "generatedAt": generated_at,
        "catalog": {"path": catalog_path, "sha256": catalog_hash, "count": len(catalog["satellites"]), "upstreamAsOf": catalog["upstreamAsOf"]},
        "spaceWeather": {"path": weather_path, "sha256": weather_hash, "observedAt": weather["solarWind"]["observedAt"]},
        # `withheldReplays` is deliberately in the MANIFEST, which is a small
        # file anyone can fetch from the live site. A withhold that can only be
        # seen by reading this source file is a withhold that becomes permanent
        # by being forgotten.
        "events": {"path": events_path, "sha256": events_hash, "count": len(events["events"]),
                   **({"withheldReplays": withheld_replays} if withheld_replays else {})},
        "land": {"path": land_path, "sha256": land_hash},
        "provenance": {"path": provenance_path, "sha256": provenance_hash},
    }
    if geospace_record is not None:
        manifest["geospace"] = geospace_record
    if ground_field_record is not None:
        manifest["groundField"] = ground_field_record
    if ionosphere_model_record is not None:
        manifest["ionosphereModel"] = ionosphere_model_record
    if thermosphere_record is not None:
        manifest["thermosphere"] = thermosphere_record
    if thermosphere_empirical_record is not None:
        manifest["thermosphereEmpirical"] = thermosphere_empirical_record
    if drap_record is not None:
        manifest["drap"] = drap_record
    if aurora_record is not None:
        manifest["aurora"] = aurora_record
    # Ground stations. Additive and optional in exactly the way orbit history
    # is: a malformed or missing station table must not take down a publish
    # cycle that is otherwise fine. Imported here rather than at module scope
    # so a missing module cannot stop the build from starting either.
    #
    # Unlike the orbit archive this reads one 135 KB checked-in table and joins
    # it to the catalog already in memory, so it is cheap enough to belong in
    # the five-minute cycle rather than on its own timer.
    try:
        from pipeline.ground_stations import publish as publish_ground_stations

        manifest.update(publish_ground_stations(
            data_root,
            write_artifact,
            [satellite["id"] for satellite in catalog["satellites"]],
        ))
    except Exception as error:  # noqa: BLE001
        print(f"WARNING: ground-station artifact unavailable; preserving whatever was published before: {error}")
        previous = prior_artifact_record(data_root, "groundStations")
        if previous is not None:
            manifest["groundStations"] = previous
    # Measured ionosonde soundings.
    #
    # The only layer parameters on this site that an instrument actually
    # observed. WAM-IPE resolves D and F2 and genuinely does not resolve E or
    # F1 (the E ledge clears 0.3 dex in ~20% of columns, and its DAYSIDE median
    # prominence is negative), so the E and F1 layers can only come from
    # soundings. See pipeline/ionosonde_soundings.py for the source diligence,
    # the terms, and what the feed actually is.
    #
    # Additive and optional in the same way ground stations are: one 42 KB
    # request against an aggregator that publishes no rate limit, and a failure
    # must leave the previously published soundings in place rather than taking
    # the E and F1 layers off the site. `fetch_json_once` does not retry and
    # stops on any non-200, which is the required posture for an upstream whose
    # terms are unpublished.
    try:
        from pipeline.ionosonde_soundings import build_ionosonde_bundle

        ionosonde_bundle = build_ionosonde_bundle(fetch_json_once)
        ionosonde_path, ionosonde_digest = write_artifact(data_root, "ionosonde", ionosonde_bundle)
        manifest["ionosondeSoundings"] = {
            "path": ionosonde_path,
            "sha256": ionosonde_digest,
            "observedAt": ionosonde_bundle["observedAt"],
            "stationCount": len(ionosonde_bundle["stations"]),
            "staleStationCount": ionosonde_bundle["staleStationCount"],
            "upstreamStationCount": ionosonde_bundle["upstreamStationCount"],
            "withFoE": ionosonde_bundle["withFoE"],
            "withFoF1": ionosonde_bundle["withFoF1"],
        }
        print(
            "ionosonde soundings: {} fresh of {} upstream ({} stale dropped), foE {}, foF1 {}".format(
                len(ionosonde_bundle["stations"]),
                ionosonde_bundle["upstreamStationCount"],
                ionosonde_bundle["staleStationCount"],
                ionosonde_bundle["withFoE"],
                ionosonde_bundle["withFoF1"],
            )
        )
    except Exception as error:  # noqa: BLE001
        print(f"WARNING: ionosonde soundings unavailable; preserving whatever was published before: {error}")
        previous = prior_artifact_record(data_root, "ionosondeSoundings")
        if previous is not None:
            manifest["ionosondeSoundings"] = previous
    # Plasmasphere. A DGCPM simulation driven by the published Kp record, run
    # here rather than downloaded because nobody publishes a plasmasphere
    # nowcast in a machine-readable form (see docs/SCIENTIFIC-LAYERS.md).
    #
    # Additive and optional in exactly the way ground stations and orbit history
    # are: a bad Kp response or a numerical failure must not take down a publish
    # cycle that is otherwise fine, and the previously published frames stay on
    # the site until a good run replaces them. Imported inside the try so a
    # missing numpy cannot stop the build from starting either.
    #
    # Cost: about six seconds of integration, and only when the Kp drive or the
    # frame grid has actually moved - the result is cached on a digest of both.
    # Both fetches read `fetch_json_once`'s cache when a fresh copy is already
    # there, so the 1-minute product costs no request at all: the space-weather
    # block fetched it seconds ago.
    try:
        if os.environ.get("SPACE_EXPLORER_DISABLE_PLASMASPHERE") == "1":
            # Kill switch, same shape as the orbit-history one. The simulation
            # costs about eight seconds of CPU whenever the Kp drive moves,
            # which is twice an hour; that is well inside this service's budget,
            # but a timer that gets SIGKILLed on timeout cannot be rescued by
            # the handler below, so there is a way to switch it off without a
            # deploy. The handler preserves the previously published frames.
            raise RuntimeError("plasmasphere disabled by SPACE_EXPLORER_DISABLE_PLASMASPHERE=1")
        from pipeline.plasmasphere_dgcpm import publish as publish_plasmasphere

        manifest.update(publish_plasmasphere(
            data_root,
            write_artifact,
            fetch_json_once(NOAA_KP_3HOUR, max_age_seconds=45 * 60),
            fetch_json_once(NOAA_KP, max_age_seconds=4 * 60),
            cache_root=CACHE / "plasmasphere-dgcpm",
        ))
    except Exception as error:  # noqa: BLE001
        print(f"WARNING: plasmasphere simulation unavailable; preserving whatever was published before: {error}")
        previous = prior_artifact_record(data_root, "plasmasphere")
        if previous is not None:
            manifest["plasmasphere"] = previous
    # Orbit history. Additive and fully optional: the archive lives on /mnt/d and
    # may be absent, mid-roll, or on a machine that is not this one, and none of
    # those may take down a publish cycle that is otherwise fine. Imported here
    # rather than at module scope so a missing orbit module cannot stop the
    # build from starting either.
    try:
        if os.environ.get("SPACE_EXPLORER_DISABLE_ORBIT_HISTORY") == "1":
            # Kill switch added 2026-08-08. This step took a five-minute publish
            # cycle past its 240 s timeout while holding 9.3 GB resident, which
            # killed four hours of publishes and left the site serving stale data.
            # The existing handler below preserves the previously published
            # artifacts, so disabling this loses nothing already on the site.
            # Remove once the heavy work runs on its own timer and streams the
            # archive instead of loading it.
            raise RuntimeError("orbit history disabled by SPACE_EXPLORER_DISABLE_ORBIT_HISTORY=1")
        from pipeline.orbit_release import publish as publish_orbit_history

        manifest.update(publish_orbit_history(data_root, write_artifact=write_artifact))
    except Exception as error:  # noqa: BLE001
        print(f"WARNING: orbit history artifacts unavailable; preserving whatever was published before: {error}")
        for key in ("orbitHistory", "orbitEvents", "orbitDrag"):
            previous = prior_artifact_record(data_root, key) if key != "orbitHistory" else None
            if previous is not None:
                manifest[key] = previous
    # These are bounded derivative indexes produced by the offline archive job.
    # The frequent publisher must never reopen the large history shards.
    from pipeline.plot_views import manifest_views
    manifest["orbitPlotViews"] = manifest_views(data_root, manifest.get("orbitHistory", {}))
    from pipeline.static_figures import publish as publish_static_figures
    try:
        manifest["staticFigures"] = publish_static_figures(data_root, catalog, land, manifest["generatedAt"])
    except Exception as error:
        # Do not disguise an old image as this release. The reader says unavailable.
        print(f"WARNING: static figures unavailable: {error}")
    manifest_bytes = canonical_json(manifest)
    atomic_write(data_root / "manifest.json", manifest_bytes)
    atomic_write(data_root / "manifests" / f"manifest-{release}.json", manifest_bytes)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=ROOT / "public" / "data")
    parser.add_argument("--max-satellites", type=int, default=8000, help="0 includes the full active public catalog")
    # The manifest used to be dumped to stdout unconditionally. Nothing reads it
    # there -- it is written to data_root/manifest.json and to the dated copy in
    # manifests/, and publish_data.py reads it off disk -- but this runs from
    # space-explorer-data.service every five minutes, and systemd sends the
    # service's stdout to the journal, which forwards it to /var/log/syslog.
    # Pretty-printed that manifest is ~22,500 lines a cycle: 6.5 M lines and
    # about 1 GB a DAY, which was 99.0% of every line in /var/log/syslog
    # (4.7 GB for one week) and pushed the root disk to 89%. It also held the
    # 2 GB journal to roughly two days of history, so the chatter was crowding
    # out the one message an operator would need.
    #
    # The dump is kept, behind a flag, because it is genuinely useful by hand;
    # the default is now a one-line receipt that says where the manifest is.
    parser.add_argument(
        "--print-manifest",
        action="store_true",
        help="dump the whole manifest as JSON on stdout (default: one summary line)",
    )
    args = parser.parse_args()
    args.data_root.mkdir(parents=True, exist_ok=True)
    lock_path = CACHE / "build-release.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("Another Space Environment Explorer bundle build is already running.")
            return 0
        manifest = build_release(args.data_root, args.max_satellites)
    if args.print_manifest:
        print(json.dumps(manifest, indent=2))
    else:
        manifest_path = args.data_root / "manifest.json"
        try:
            size = f"{manifest_path.stat().st_size:,} bytes"
        except OSError:
            size = "size unavailable"
        print(
            f"manifest: {len(manifest)} top-level records, generatedAt "
            f"{manifest.get('generatedAt', 'unknown')}, written to {manifest_path} "
            f"({size}); pass --print-manifest to dump it"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
