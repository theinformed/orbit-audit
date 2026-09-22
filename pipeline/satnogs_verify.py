#!/usr/bin/env python3
"""Check this catalog's satellite cards against the SatNOGS DB, by catalog number.

WHY THIS EXISTS -- THE COSMIC CARD
----------------------------------
NORAD 66658 is named ``COSMIC``. It is a 3U South Korean rideshare CubeSat that
launched on Nuri/KSLV-II on 2025-11-26. The site showed it as a meteorological
spacecraft in the COSMIC constellation, because `classify_detailed` matches the
token ``COSMIC`` and that token belongs, in every other case in this catalog, to
the six Taiwanese/US FORMOSAT-7 / COSMIC-2 radio-occultation satellites launched
in 2019. Both matches are legitimate token matches. The boundary rule added on
2026-08-07 cannot separate them, and neither can any narrower spelling of the
pattern, because the two spacecraft genuinely share a name.

This is the THIRD recorded instance of that failure class in this file's
neighbourhood -- see `build_release.classify_detailed` for ``HUBBLE`` (the BLE
connectivity constellation read as the telescope) and for ``SES-``/``EUTE``.
A fourth is a matter of time. So this module does not add another name rule. It
adds a way to notice, from evidence outside our own naming, that a name-pattern
claim is about the wrong spacecraft.

WHAT SATNOGS IS, AND WHAT IT IS NOT
-----------------------------------
SatNOGS DB (<https://db.satnogs.org/>) is the Libre Space Foundation's
crowdsourced database of spacecraft and their radios. Their API documentation
states "API access is open to anyone" and "All API data are freely distributed
under the CC BY-SA license"
(<https://docs.satnogs.org/projects/satnogs-db/en/stable/api.html>). No rate
limit, quota or acceptable-use policy is published anywhere we could find; the
courtesy budget below is therefore ours, not theirs, and is deliberately far
under anything they would notice. `robots.txt` disallows only ``/admin/``.

They are volunteers. This project has already been firewalled once, by
CelesTrak, for retrying a dead endpoint on a timer. So: two bulk requests per
refresh, both cached to disk for a week; a hard one-per-1.2-second floor between
any two requests; a descriptive User-Agent with a contact address; and a STOP on
the first non-200 rather than a retry.

**SatNOGS IS NOT AN AUTHORITY ON OWNERSHIP, AND THIS MODULE MUST NEVER TREAT IT
AS ONE.** Measured against the live catalog on 2026-08-19: of 930 objects that
joined by catalog number, 673 agreed on country, 45 DISAGREED, 27 could not be
compared and 185 carried no country at all. The 45 are not 45 of our errors.
Reading them one by one, most are rideshare deployments where the community's
guess at which TLE belongs to which CubeSat differs from space-track's -- our
``KORSAT-1`` is their ``QPS-SAR-7``, our ``AIGLONSAT-1`` is their ``VEGAFLY-1``
-- and several more record the *manufacturer's* country rather than the
operator's (PROBA 1/2/V, ESA missions built in Belgium, are filed under BE).
44 more objects disagree on launch date, by up to a year.

That measurement is the whole design constraint. A pipeline that copied
SatNOGS's country over ours would have made 45 cards worse to fix none. So:

  * The catalog number is the key, and identity must be CORROBORATED before any
    comparison is believed at all (`identity_verdict` below).
  * Nothing here ever writes an owner, a country or a name.
  * The single automatic correction this module makes is a WITHDRAWAL -- it
    takes a name-pattern claim away and leaves "unknown" behind. It cannot
    assert anything. A wrong correction is worse than a known gap.
  * Everything else lands in the report for a human.

WHAT IT ACTUALLY CATCHES
------------------------
`cohort_outliers` needs no external source at all: it asks whether the members
of a name-derived constellation agree with each other about who owns them and
when they launched. COSMIC 66658 is the only owner-outlier in this catalog whose
constellation came from a name pattern, and SatNOGS then corroborates it three
ways -- same name, same launch date to the day, same country -- while placing
its two radios in ITU service ``Space Operation`` (a GomSpace NanoCom AX100/
AX2150 CubeSat bus radio) against the cohort's ``Earth Exploration``. Two
independent sources, one deterministic key, no model involved.

RUN IT
------
    python3 -m pipeline.satnogs_verify --report-only     # no writes but the report
    python3 -m pipeline.satnogs_verify                   # + data/satnogs_withdrawals.json
    python3 -m pipeline.satnogs_verify --refresh         # re-fetch even if cached

The token is read from ``SATNOGS_API_TOKEN`` or from the file named by
``SATNOGS_TOKEN_FILE`` (default ``~/.config/space-teaching-aid/satnogs.env``).
It is a personal token: it is never logged, never written to the report and
never committed. Absent, the module runs anonymously -- every endpoint this
module uses answers unauthenticated -- and says so, rather than carrying a
fallback key.
"""

from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "pipeline" / ".cache" / "satnogs"
STATE = ROOT / "state"
WITHDRAWALS = ROOT / "data" / "satnogs_withdrawals.json"
SERVICE_MISSIONS = ROOT / "data" / "satnogs_service_missions.json"

API = "https://db.satnogs.org/api"
SATELLITE_PAGE = "https://db.satnogs.org/satellite/{sat_id}"

#: Who is calling, and where to complain. An anonymous scraper is the thing a
#: volunteer sysadmin blocks first, and rightly.
USER_AGENT = (
    "space-teaching-aid-verify/1.0 "
    "(Space Environment Explorer, a Navy Space Cadre teaching site; "
    "contact sdegan@gmail.com)"
)

#: The floor between any two requests, in seconds. Two bulk calls per refresh
#: means this never actually bites on the normal path; it exists so that the
#: per-object description fetch (which is opt-in and capped) cannot turn into a
#: flood if somebody raises the cap.
MIN_REQUEST_INTERVAL_S = 1.2

#: How long a cached bulk dump is considered current. SatNOGS entries change on
#: the timescale of a volunteer noticing something, not minutes; a week is
#: generous to them and costs us nothing, since the catalog rebuild is the thing
#: that runs often, not this.
CACHE_MAX_AGE_S = 7 * 24 * 3600

#: SatNOGS mints a TEMPORARY five-digit identifier in the 90000+ range for an
#: object nobody has tied to a catalogue entry yet, and records the real one --
#: when a community member works it out -- in `norad_follow_id`. The Korean
#: COSMIC is `norad_cat_id` 98494 / `norad_follow_id` 66658, so an index built
#: on `norad_cat_id` alone MISSES THE ONE OBJECT THIS MODULE WAS WRITTEN FOR.
#: 629 of their 2,769 entries carry a placeholder and 343 carry a follow id.
PLACEHOLDER_NORAD_FLOOR = 90000

_LAST_REQUEST_AT = 0.0


class SatnogsUnavailable(RuntimeError):
    """SatNOGS said something other than 200, so we stop and report.

    Deliberately not a retry. The failure mode this project has already lived
    through is a timer knocking on a door that has stopped answering, and the
    correct response to a volunteer service returning 500 or 429 is to go away
    until a person looks at it.
    """


# ---------------------------------------------------------------------------
# Credentials
# ---------------------------------------------------------------------------

DEFAULT_TOKEN_FILE = Path.home() / ".config" / "space-teaching-aid" / "satnogs.env"


def api_token() -> str | None:
    """The operator's personal SatNOGS token, or None.

    Read from the environment or from an untracked file, never from the
    repository, and returned rather than logged. There is no embedded fallback
    on purpose: a missing token must be visible as "running anonymously", not
    silently papered over by a key checked into git.
    """
    direct = os.environ.get("SATNOGS_API_TOKEN", "").strip()
    if direct:
        return direct
    path = Path(os.environ.get("SATNOGS_TOKEN_FILE", str(DEFAULT_TOKEN_FILE)))
    if not path.is_file():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        key, _, value = line.partition("=")
        if key.strip() == "SATNOGS_API_TOKEN" and value.strip():
            return value.strip()
    return None


# ---------------------------------------------------------------------------
# Fetching, politely
# ---------------------------------------------------------------------------


def _throttle() -> None:
    global _LAST_REQUEST_AT
    wait = MIN_REQUEST_INTERVAL_S - (time.monotonic() - _LAST_REQUEST_AT)
    if wait > 0:
        time.sleep(wait)
    _LAST_REQUEST_AT = time.monotonic()


def fetch(url: str, token: str | None = None, timeout: int = 90) -> bytes:
    """One request. Throttled, identified, and fatal on anything but 200."""
    _throttle()
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    if token:
        # Their scheme, from the published OpenAPI document: `tokenAuth` is an
        # apiKey in the Authorization header with the required prefix "Token".
        request.add_header("Authorization", f"Token {token}")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            if response.status != 200:
                raise SatnogsUnavailable(f"{url} -> HTTP {response.status}")
            return response.read()
    except urllib.error.HTTPError as error:
        # The message never includes the Authorization header, so a token
        # cannot reach a log through this path.
        raise SatnogsUnavailable(f"{url} -> HTTP {error.code}") from None
    except (urllib.error.URLError, TimeoutError) as error:
        raise SatnogsUnavailable(f"{url} -> {error.__class__.__name__}") from None


def cached_json(
    name: str,
    url: str,
    *,
    token: str | None = None,
    refresh: bool = False,
    cache_dir: Path | None = None,
    max_age_s: float = CACHE_MAX_AGE_S,
) -> list[dict[str, Any]]:
    """A bulk endpoint, from disk when it is fresh enough.

    Cache first, network second, and a stale cache is preferred to a failed
    fetch: an old answer about who operates a spacecraft is very nearly as good
    as a new one, and far better than no report at all.
    """
    directory = cache_dir or CACHE
    path = directory / f"{name}.json"
    if path.is_file() and not refresh:
        age = time.time() - path.stat().st_mtime
        if age < max_age_s:
            return json.loads(path.read_text(encoding="utf-8"))
    try:
        payload = fetch(url, token=token)
    except SatnogsUnavailable:
        if path.is_file():
            print(f"NOTE: SatNOGS unreachable; using the cached {name} dump", flush=True)
            return json.loads(path.read_text(encoding="utf-8"))
        raise
    directory.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return json.loads(payload.decode("utf-8"))


def load_satellites(**kwargs: Any) -> list[dict[str, Any]]:
    """Every satellite SatNOGS knows, in ONE request.

    They publish the whole table unpaginated -- 2,769 rows, 1.3 MB. Using it is
    the single biggest courtesy available here: the per-object form
    (`?norad_cat_id=`) would be thousands of requests for the same bytes, and it
    would MISS the placeholder-id objects anyway, because that filter matches
    `norad_cat_id` only and the Korean COSMIC's is 98494.
    """
    return cached_json("satellites", f"{API}/satellites/?format=json", **kwargs)


def load_transmitters(**kwargs: Any) -> list[dict[str, Any]]:
    """Every transmitter, also in one request (5,007 rows, 3.5 MB).

    Worth the second request because `service` is an ITU radio service -- what a
    spacecraft is *licensed* to do, filed with a regulator by somebody who had
    to mean it. It is the only field in either database that is independent of
    the spacecraft's NAME, which is precisely the axis on which this project's
    classifier keeps failing.
    """
    return cached_json("transmitters", f"{API}/transmitters/?format=json", **kwargs)


# ---------------------------------------------------------------------------
# The deterministic key
# ---------------------------------------------------------------------------


def index_by_norad(entries: Iterable[dict[str, Any]]) -> dict[int, list[dict[str, Any]]]:
    """Catalog number -> SatNOGS entries. Placeholder ids are NOT catalog numbers.

    A row contributes its `norad_cat_id` only when that number is a real
    catalogue number, and always contributes its `norad_follow_id`. Collisions
    are kept as a list rather than resolved: two SatNOGS rows claiming one
    catalogue number is exactly the ambiguity a caller must be told about, not
    a thing for this function to pick a winner in.
    """
    index: dict[int, list[dict[str, Any]]] = collections.defaultdict(list)
    for entry in entries:
        keys: set[int] = set()
        primary = entry.get("norad_cat_id")
        if primary and int(primary) < PLACEHOLDER_NORAD_FLOOR:
            keys.add(int(primary))
        follow = entry.get("norad_follow_id")
        if follow:
            keys.add(int(follow))
        for key in keys:
            index[key].append(entry)
    return dict(index)


_NOISE = re.compile(r"[^A-Z0-9]+")


def normalized_name(name: str) -> str:
    """Upper case, letters and digits only.

    ``FORMOSAT7-3/COSMIC2-3`` and ``FORMOSAT 7-3`` are the same spacecraft
    spelled by two catalogues; ``COSMIC`` and ``COSMIC`` are two spacecraft
    spelled the same. Normalisation helps with the first and is powerless
    against the second, which is why it is never the key.
    """
    return _NOISE.sub("", (name or "").upper())


def names_agree(ours: str, theirs: str, alternates: str = "") -> bool:
    """Do the two catalogues plausibly spell the same object?

    Containment either way, because our names concatenate the programme
    designations that SatNOGS splits (``FORMOSAT7-3/COSMIC2-3`` contains
    ``FORMOSAT73``), and SatNOGS's `names` field carries the alternates that
    space-track sometimes uses as the primary.
    """
    a = normalized_name(ours)
    b = normalized_name(theirs)
    if not a or not b:
        return False
    if a == b or a in b or b in a:
        return True
    return any(
        normalized_name(alternate) and (
            normalized_name(alternate) == a
            or normalized_name(alternate) in a
            or a in normalized_name(alternate)
        )
        for alternate in (alternates or "").split(",")
    )


#: How far two launch dates may sit apart and still be the same launch. Two days
#: covers a UTC/local disagreement either way, which is what most of the
#: one-day gaps in their data are. Measured 2026-08-19: 44 of 930 joined objects
#: disagree on launch date, and the large gaps (a month, a year) are the ones
#: worth treating as evidence that the join is wrong.
LAUNCH_DATE_TOLERANCE_DAYS = 2


def launch_dates_agree(ours: str | None, theirs: str | None) -> bool | None:
    """True/False, or None when one side simply does not say."""
    if not ours or not theirs:
        return None
    try:
        a = dt.date.fromisoformat(ours[:10])
        b = dt.date.fromisoformat(theirs[:10])
    except ValueError:
        return None
    return abs((a - b).days) <= LAUNCH_DATE_TOLERANCE_DAYS


def identity_verdict(ours: dict[str, Any], theirs: dict[str, Any]) -> tuple[str, list[str]]:
    """Is their row about OUR spacecraft? -- and the reasons, always.

    A catalogue-number join is not identity on its own here. SatNOGS's
    `norad_follow_id` is frequently a community member's ATTRIBUTION of a TLE to
    a CubeSat deployed on a crowded rideshare, and when that attribution is
    wrong the join is wrong in a way that looks perfectly normal. So the number
    opens the door and two independent facts -- the name and the launch date --
    have to agree before anything is believed:

      ``confirmed``    the number plus at least one independent agreement, and
                       no independent DISagreement.
      ``id-only``      the number matched and nothing else could be checked.
      ``contradicted`` the number matched and an independent fact says no.

    Only ``confirmed`` is ever allowed to change a card.
    """
    reasons: list[str] = []
    name_ok = names_agree(ours.get("name", ""), theirs.get("name", ""), theirs.get("names", ""))
    launch_ok = launch_dates_agree(ours.get("launchDate"), theirs.get("launched"))
    if name_ok:
        reasons.append(f"name agrees ({ours.get('name')!r} vs {theirs.get('name')!r})")
    else:
        reasons.append(f"name differs ({ours.get('name')!r} vs {theirs.get('name')!r})")
    if launch_ok is True:
        reasons.append(f"launch date agrees ({ours.get('launchDate')} vs {str(theirs.get('launched'))[:10]})")
    elif launch_ok is False:
        reasons.append(f"launch date differs ({ours.get('launchDate')} vs {str(theirs.get('launched'))[:10]})")
    else:
        reasons.append("launch date not comparable")
    if not name_ok and launch_ok is False:
        return "contradicted", reasons
    if name_ok or launch_ok is True:
        return "confirmed", reasons
    return "id-only", reasons


# ---------------------------------------------------------------------------
# Comparing the two records
# ---------------------------------------------------------------------------

#: SatNOGS writes ISO 3166-1 alpha-2. space-track's SATCAT writes its own
#: abbreviations, and `build_release.OWNER_LABELS` is the list of the ones this
#: project has decided are unambiguous. This table maps between them for the ONE
#: purpose of asking "do the two sources say the same country?" -- it is a
#: comparison aid and nothing in this module writes an owner from it.
#:
#: A code absent here makes the comparison ``unmappable``, which is reported as
#: exactly that. Guessing that ``ZW`` is ``ZWE`` would be the same species of
#: cheap inference this whole module exists to stop.
ISO2_TO_SATCAT: dict[str, frozenset[str]] = {
    "US": frozenset({"US"}), "TW": frozenset({"TWN"}), "KR": frozenset({"SKOR"}),
    "JP": frozenset({"JPN"}), "CN": frozenset({"PRC"}), "RU": frozenset({"CIS"}),
    "IN": frozenset({"IND", "ISRO"}), "GB": frozenset({"UK"}), "FR": frozenset({"FR"}),
    "DE": frozenset({"GER"}), "CA": frozenset({"CA"}), "IT": frozenset({"IT"}),
    "ES": frozenset({"SPN"}), "NO": frozenset({"NOR"}), "BR": frozenset({"BRAZ"}),
    "AE": frozenset({"UAE"}), "SA": frozenset({"SAUD"}), "SG": frozenset({"SING"}),
    "BE": frozenset({"BEL"}), "AR": frozenset({"ARGN"}), "GR": frozenset({"GREC"}),
    "ID": frozenset({"INDO"}), "EG": frozenset({"EGYP"}), "PL": frozenset({"POL"}),
    "IL": frozenset({"ISRA"}), "TH": frozenset({"THAI"}), "CH": frozenset({"SWTZ"}),
    "BG": frozenset({"BGR"}), "RW": frozenset({"RWA"}), "LU": frozenset({"LUXE"}),
    "PT": frozenset({"POR"}), "IR": frozenset({"IRAN"}), "DZ": frozenset({"ALG"}),
    "KZ": frozenset({"KAZ"}), "PK": frozenset({"PAKI"}), "MX": frozenset({"MEX"}),
    "DK": frozenset({"DEN"}), "MY": frozenset({"MALA"}), "FI": frozenset({"FIN"}),
    "SE": frozenset({"SWED"}), "NL": frozenset({"NETH"}), "HU": frozenset({"HUN"}),
    "VN": frozenset({"VTNM"}), "NG": frozenset({"NIG"}), "AZ": frozenset({"AZER"}),
    "AO": frozenset({"AGO", "ANG"}), "CZ": frozenset({"CZCH"}), "AT": frozenset({"AUT"}),
    "NZ": frozenset({"NZ"}), "CL": frozenset({"CHLE"}), "PE": frozenset({"PERU"}),
    "QA": frozenset({"QAT"}), "LT": frozenset({"LTU"}), "LK": frozenset({"LKA"}),
    "BY": frozenset({"BELA"}), "UA": frozenset({"UKR"}), "PH": frozenset({"RP"}),
    "TR": frozenset({"TURK"}), "AU": frozenset({"AUS"}),
}


def country_verdict(owner_code: str, countries: str) -> tuple[str, str]:
    """agree / disagree / unmappable / absent, with a short reason."""
    text = (countries or "").strip()
    if not text:
        return "absent", "SatNOGS records no country"
    codes = [code.strip().upper() for code in text.split(",") if code.strip()]
    mapped: set[str] = set()
    for code in codes:
        known = ISO2_TO_SATCAT.get(code)
        if known is None:
            return "unmappable", f"no SATCAT equivalent for ISO {code!r}"
        mapped |= set(known)
    if owner_code in mapped:
        return "agree", f"{owner_code} matches SatNOGS {','.join(codes)}"
    return "disagree", f"we say {owner_code}, SatNOGS says {','.join(codes)}"


#: ITU radio services, and the missions in this site's taxonomy that each one is
#: CONSISTENT with. Deliberately generous in every row: the question being asked
#: is only "does the licensed service RULE THIS OUT", never "does it prove it".
#:
#: ``Space Operation`` is consistent with everything, and that is not laziness:
#: it is the allocation for a spacecraft's own telemetry-and-command link, which
#: every satellite of every kind has. It carries no information about the
#: mission and must never be allowed to look as if it does.
#:
#: ``Amateur`` includes ``communications``, because an amateur-radio satellite
#: IS a communications satellite -- a first draft that omitted it flagged 30
#: correctly-labelled OSCARs as contradictions.
SERVICE_CONSISTENT_MISSIONS: dict[str, frozenset[str]] = {
    "Meteorological": frozenset({"weather", "science", "earth-observation"}),
    "Earth Exploration": frozenset({"earth-observation", "weather", "science"}),
    "Space Research": frozenset({"science", "technology", "human-spaceflight", "earth-observation"}),
    "Amateur": frozenset({"communications", "technology", "science", "other"}),
    "Space Operation": frozenset({
        "weather", "communications", "missile-warning", "navigation",
        "earth-observation", "science", "human-spaceflight", "technology", "other",
    }),
    "Mobile": frozenset({"communications", "earth-observation"}),
    "Maritime": frozenset({"communications", "navigation"}),
    "Aeronautical": frozenset({"communications", "navigation"}),
    "Fixed": frozenset({"communications"}),
    "Broadcasting": frozenset({"communications"}),
    "Inter-satellite": frozenset({"communications", "weather", "earth-observation", "science"}),
    "Radionavigational": frozenset({"navigation"}),
    "Radiolocation": frozenset({"earth-observation", "navigation", "missile-warning", "science"}),
}

#: The service SatNOGS records when nobody has established one. It is not a
#: finding and must never be compared.
SERVICE_UNKNOWN = "Unknown"


def services_for(catalog_id: int, transmitters_by_norad: dict[int, list[dict[str, Any]]]) -> set[str]:
    """The ITU services this object's radios are filed under.

    Active transmitters when there are any, all of them otherwise: a decommissioned
    radio still says what the spacecraft was licensed to do, and for a dead or
    quiet object it is the only thing that does.
    """
    rows = transmitters_by_norad.get(catalog_id) or []
    if not rows:
        return set()
    active = {row.get("service") for row in rows if row.get("status") == "active"}
    services = active or {row.get("service") for row in rows}
    return {service for service in services if service and service != SERVICE_UNKNOWN}


# ---------------------------------------------------------------------------
# The COSMIC-class detector: does a constellation agree with itself?
# ---------------------------------------------------------------------------


#: A constellation must hold at least this many members before its internal
#: agreement means anything. Two spacecraft sharing an owner is a coincidence;
#: ten is a fleet. Measured across the live catalog the exact figure barely
#: matters -- 5 and 20 move the answer by fifteen objects out of six thousand --
#: so this is set where a reader would agree the word "fleet" starts.
COHORT_MIN_MEMBERS = 10

#: How much of a cohort has to agree before the cohort can vouch for anything.
#: A SUPERMAJORITY, not a plurality: Globalstar splits 12 GLOB / 6 US, Intelsat
#: 13 ITSO / 5 US / 1 AZER, O3b 7 O3B / 3 SES. Under a plurality rule each of
#: those fleets would "corroborate" its own larger faction while contradicting
#: the smaller one, which is a cohort that does not agree with itself being read
#: as agreement. At 0.9 all three are refused outright, which is the honest
#: answer and costs fifteen objects.
COHORT_AGREEMENT_SHARE = 0.9


def constellation_cohorts(
    satellites: Iterable[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """Group the catalog by the fleet each object was placed in.

    Shared by the negative detector below and by the positive verdict beside
    it, so the two can never disagree about what a cohort IS.
    """
    cohorts: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for satellite in satellites:
        if satellite.get("constellation"):
            cohorts[satellite["constellation"]].append(satellite)
    return cohorts


def constellation_cohort_verdicts(
    satellites: Iterable[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Does each fleet agree with itself well enough to vouch for its members?

    THE SAME QUESTION `cohort_outliers` ASKS, ASKED POSITIVELY. That function
    finds the object its own constellation contradicts; this one finds the
    constellations that contradict nobody. They share `constellation_cohorts`
    so there is one definition of a cohort in this file.

    WHAT THIS ESTABLISHES, AND WHAT IT DOES NOT. The 18th Space Defense Squadron
    assigns names to objects observed within a launch and corrects them later
    when users object; LitSat-1 and LituanicaSat-1 were transposed until Doppler
    measurements sorted them out, and Apstar 9A was reported retired when it had
    merely been renamed. So "this object is unit 11600 of the fleet" is a claim
    the catalog genuinely cannot support.

    But that failure mode is intra-batch. Transposing two names inside one
    Starlink launch leaves both objects Starlinks. So the MISSION CLASS survives
    exactly the error the identity does not, and it is the mission class the
    card's chip states. This function establishes the mission class and says
    nothing about which unit is which.

    A fleet vouches for its members when:

      * it has at least ``COHORT_MIN_MEMBERS`` of them here;
      * one owner code holds at least ``COHORT_AGREEMENT_SHARE`` of it;
      * one (mission, sector) pair holds at least that share too -- the clause
        that ties the test to the CLAIM. It costs nothing today and it is the
        reason a future name rule cannot drop a missile-warning label into the
        Starlink cohort and have four thousand siblings corroborate it;
      * at least one of its launch groups holds two of its members, so the fleet
        demonstrably launches in batches rather than being a name that several
        unrelated objects happen to share;
      * and NOTHING INDEPENDENT DISAGREES about any member -- no contested
        attribution, no name claim SatNOGS withdrew. `identity_verdict` already
        refuses to confirm anything an independent fact contradicts, and this is
        that rule at cohort scale. It is what keeps all 159 Yaogan hedged: the
        US Department of Defense and the operator do not agree about them, and a
        fleet with a disputed member cannot vouch for the rest.

    THE VERDICT IS THE COHORT'S, NOT THE MEMBER'S, and the caller applies it to
    every member. Every object in one fleet has to carry the same verdict, and
    that is not a cosmetic point.
    STARLINK-1892 and STARLINK-2001 are the only members of their launch batches
    the browser ceiling retained, and IRIDIUM 174 flew with spares; per object
    those three hedge while 4,919 visually identical siblings do not, and a
    reader cannot tell why. An inconsistent hedge teaches nothing. The claim is
    about the cohort, so the cohort is the unit that gets judged.

    Returns one row per constellation, passing or failing, each carrying the
    numbers it was judged on so the verdict can be audited from the artifact
    rather than taken on trust.
    """
    verdicts: dict[str, dict[str, Any]] = {}
    for label, members in sorted(constellation_cohorts(satellites).items()):
        owners = collections.Counter(m.get("ownerCode") for m in members)
        missions = collections.Counter((m.get("mission"), m.get("sector")) for m in members)
        top_owner, owner_count = owners.most_common(1)[0]
        (top_mission, top_sector), mission_count = missions.most_common(1)[0]
        launch_groups = collections.Counter(
            m.get("launchGroup") for m in members if m.get("launchGroup")
        )
        batched = sum(1 for count in launch_groups.values() if count >= 2)
        contested = sum(1 for m in members if m.get("contestedAttribution"))
        withdrawn = sum(
            1 for m in members if m.get("classificationBasis") == "withdrawn-name-collision"
        )
        owner_share = owner_count / len(members)
        mission_share = mission_count / len(members)
        if len(members) < COHORT_MIN_MEMBERS:
            why = f"only {len(members)} member(s) here; a fleet is judged from {COHORT_MIN_MEMBERS}"
        elif owner_share < COHORT_AGREEMENT_SHARE:
            why = (
                f"its members do not agree who owns them ({owner_share:.0%} share the "
                f"most common registration)"
            )
        elif mission_share < COHORT_AGREEMENT_SHARE:
            why = (
                f"its members do not agree what they are ({mission_share:.0%} share the "
                f"most common mission)"
            )
        elif not batched:
            why = "no two of its members went up on the same launch"
        elif contested:
            why = f"{contested} member(s) carry an attribution somebody disputes"
        elif withdrawn:
            why = "an independent source withdrew a member's name claim"
        else:
            why = ""
        verdicts[label] = {
            "consistent": not why,
            "why": why,
            "members": len(members),
            "ownerCode": top_owner,
            "ownerShare": round(owner_share, 4),
            "mission": top_mission,
            "sector": top_sector,
            "missionShare": round(mission_share, 4),
            "batchedLaunchGroups": batched,
            "contestedMembers": contested,
            "withdrawnMembers": withdrawn,
        }
    return verdicts




def cohort_outliers(satellites: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Objects whose own constellation contradicts them about owner and launch.

    A constellation is a fleet: its members share an operator and were put up in
    a small number of launches. When a name pattern drops one object into a
    cohort where NOBODY else shares its owner and NOBODY else shares its launch
    group, the name is doing the work and nothing else is.

    Both conditions are needed. Owner alone flags SES 3 (US-registered, in the
    SES fleet), METOP SG-A (ESA-registered, in EUMETSAT's) and AZERSPACE
    2/INTELSAT 38 (genuinely jointly owned) -- three correct cards. Requiring
    the launch group to be disjoint as well does not save those on its own
    either, which is why this function only NOMINATES; the decision to withdraw
    additionally demands independent evidence from SatNOGS, and none of those
    three is in SatNOGS at all.

    Measured against the live catalog 2026-08-19: 8 nominations, of which
    exactly one -- COSMIC 66658 -- has a name-pattern basis AND corroborating
    outside evidence.
    """
    cohorts = constellation_cohorts(satellites)
    found: list[dict[str, Any]] = []
    for label, members in sorted(cohorts.items()):
        if len(members) < 2:
            continue
        owners = collections.Counter(member.get("ownerCode") for member in members)
        for member in members:
            if owners[member.get("ownerCode")] != 1 or len(owners) < 2:
                continue
            others = {m.get("launchGroup") for m in members if m["id"] != member["id"]}
            if member.get("launchGroup") in others:
                continue
            found.append({
                "id": member["id"],
                "name": member.get("name"),
                "constellation": label,
                "basis": member.get("classificationBasis"),
                "ownerCode": member.get("ownerCode"),
                "cohortOwners": dict(owners.most_common()),
                "launchGroup": member.get("launchGroup"),
                "cohortLaunchGroups": sorted(g for g in others if g),
            })
    return found


def token_cohort_conflicts(
    satellites: Iterable[dict[str, Any]],
    tokens: Iterable[str] | None = None,
) -> list[dict[str, Any]]:
    """The COSMIC test again, applied to the name TOKEN instead of the constellation.

    `cohort_outliers` can only see objects the classifier put in a named fleet,
    and most of `classify_detailed`'s rules do not set one -- ``WEATHER``,
    ``TECH``, ``DEMO``, ``TEST``, ``PATHFINDER``, ``ASTRO`` and the rest attach a
    MISSION and nothing else. Those are exactly the loose, generic tokens where
    the next collision is most likely, so the same question has to be asked of
    the raw token: of every object in the catalog whose name contains this
    programme token, does this one stand alone on owner AND on launch?

    Run over the live catalog on 2026-08-19 this nominated 6 objects across 68
    tokens. It is a REVIEW list, not a correction list: nothing here is acted on
    without the same independent corroboration the withdrawal path demands.
    """
    from pipeline.build_release import NAME_PATTERN_MISSION_TOKENS, contains

    satellites = list(satellites)
    found: list[dict[str, Any]] = []
    for token in tokens if tokens is not None else NAME_PATTERN_MISSION_TOKENS:
        matches = [s for s in satellites if contains(s.get("name", ""), (token,))]
        if len(matches) < 2:
            # A token matching one object cannot be checked this way at all --
            # there is no cohort to disagree with it. Reported as coverage, not
            # as a clean bill of health, in the report's rule table.
            continue
        owners = collections.Counter(match.get("ownerCode") for match in matches)
        if len(owners) < 2:
            continue
        for match in matches:
            if owners[match.get("ownerCode")] != 1:
                continue
            others = {m.get("launchGroup") for m in matches if m["id"] != match["id"]}
            if match.get("launchGroup") in others:
                continue
            found.append({
                "id": match["id"],
                "name": match.get("name"),
                "token": token,
                "basis": match.get("classificationBasis"),
                "mission": match.get("mission"),
                "ownerCode": match.get("ownerCode"),
                "cohortOwners": dict(owners.most_common()),
            })
    return found


def name_rule_coverage(satellites: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Every name token, how many objects it claims, and how many owners it spans.

    A rule that silently captures hundreds of objects on a substring is where
    the next misclassification hides, so every rule is counted. A rule
    claiming 4,673 objects that all share one owner is not hiding anything; a
    rule claiming 7 objects across two owners is. A rule claiming ZERO is a
    different problem -- it is dead, and its absence has been silently doing
    nothing since somebody wrote it.
    """
    from pipeline.build_release import NAME_PATTERN_MISSION_TOKENS, contains

    satellites = list(satellites)
    rows: list[dict[str, Any]] = []
    for token in NAME_PATTERN_MISSION_TOKENS:
        matches = [s for s in satellites if contains(s.get("name", ""), (token,))]
        owners = collections.Counter(match.get("ownerCode") for match in matches)
        rows.append({
            "token": token,
            "claims": len(matches),
            "owners": len(owners),
            "topOwners": dict(owners.most_common(3)),
            "singletonOwners": sorted(
                owner for owner, count in owners.items() if count == 1 and len(owners) > 1
            ),
        })
    return sorted(rows, key=lambda row: (-row["claims"], row["token"]))


# ---------------------------------------------------------------------------
# The OTHER path a mission arrives by: CelesTrak's category groups
# ---------------------------------------------------------------------------
#
# `name_rule_coverage` above audits one of the two ways this site puts a mission
# on a card. This audits the other, and it is the one that turned out to be
# doing the bulk damage.
#
# The question is the same question, asked of a group instead of a token: does
# this group agree with itself? A group cannot be checked against its own
# members' labels, because it is what gave most of them their labels -- that is
# circular and would report every group as perfectly pure. So the check looks
# ONLY at members the site classified from INDEPENDENT evidence: a name rule, an
# exact-name rule, or a catalog-number rule. Those members' missions were
# decided without the group having a vote, so their agreement or disagreement is
# real information about what the group contains.
#
# THEMIS A was shown as CIVIL / OTHER SATCOM by exactly this route. A category
# that sweeps a science constellation into 'communications' is the kind of
# silent bulk error worth counting.

#: A basis that was NOT handed down by a category group, and can therefore serve
#: as an independent witness about what the group contains.
INDEPENDENT_BASES = frozenset({"name-pattern", "exact-name", "norad-id"})


def celestrak_group_coherence(satellites: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Every CelesTrak category group, and whether its own members agree with it.

    Returns one row per group in `CELESTRAK_MISSION_GROUPS`:

      ``members``       objects the published catalog puts in this group
      ``decided``       objects whose mission this group actually settled
      ``independent``   members classified from evidence the group did not give
      ``agree`` / ``disagree``  of those, how many match the group's mission
      ``disagreeAs``    what the dissenters actually are

    A group with many independent members and near-total disagreement is not
    noisy — it is ABOUT SOMETHING ELSE. Measured 2026-08-19: `sarsat` asserts
    communications and 70 of 70 independent members disagree (55 navigation, 15
    weather), because COSPAS-SARSAT is a distress-beacon transponder carried on
    other people's spacecraft. `tdrss` asserts communications and 11 of 14
    disagree, because the group lists a relay network's USERS. Against that,
    `weather` scores 46 of 48 and `resource` 68 of 70 — those groups really are
    about a kind of spacecraft.

    Reported, never applied. Which groups are withheld is a decision recorded in
    `build_release.PARTICIPATION_GROUPS` with its reasoning, because a threshold
    on this number would silently reclassify hundreds of objects the first time
    a group's membership shifted.
    """
    from pipeline.build_release import CELESTRAK_MISSION_GROUPS, PARTICIPATION_GROUPS

    satellites = list(satellites)
    members_of: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for satellite in satellites:
        for group in satellite.get("sourceGroups") or []:
            members_of[group].append(satellite)

    rows: list[dict[str, Any]] = []
    for group, mission, _sector, confidence in CELESTRAK_MISSION_GROUPS:
        members = members_of.get(group, [])
        independent = [s for s in members if s.get("classificationBasis") in INDEPENDENT_BASES]
        agree = [s for s in independent if mission is not None and s.get("mission") == mission]
        disagree = [s for s in independent if mission is not None and s.get("mission") != mission]
        rows.append({
            "group": group,
            "asserts": mission,
            "confidence": confidence,
            "members": len(members),
            "decided": sum(1 for s in members if s.get("classificationBasis") == "source-group"),
            "independent": len(independent),
            "agree": len(agree),
            "disagree": len(disagree),
            "disagreeAs": dict(collections.Counter(s.get("mission") for s in disagree).most_common(4)),
            "withheld": group in PARTICIPATION_GROUPS,
        })
    # Worst agreement first, and a group with no independent witnesses last: it
    # is unaudited rather than clean, and the report says so in those words.
    return sorted(
        rows,
        key=lambda row: (row["independent"] == 0, row["agree"] / row["independent"] if row["independent"] else 1.0),
    )


# ---------------------------------------------------------------------------
# Filling a gap, with a citation -- never with a guess
# ---------------------------------------------------------------------------

#: ITU radio services that map to ONE mission in this taxonomy and no other.
#:
#: This is the only place in this module that adds a claim rather than removing
#: one, so the bar is different and higher. An ITU service is not a mission
#: statement: it is the allocation an operator FILED WITH A REGULATOR, under
#: penalty, to be allowed to transmit at all. That makes it real evidence about
#: what a spacecraft does -- and still evidence of a different kind from an
#: operator's mission page, which is why the sentence it produces says which one
#: it is and links the entry.
#:
#: Services that map to more than one mission are ABSENT ON PURPOSE, not
#: resolved: `Mobile` is communications or a store-and-forward sensor, and
#: `Radiolocation` is radar imaging or missile tracking. Guessing between those
#: is the failure this whole module exists to prevent. `Space Operation` is
#: absent for the strongest reason of all -- every spacecraft has one.
SERVICE_IMPLIES_MISSION: dict[str, str] = {
    "Meteorological": "weather",
    "Earth Exploration": "earth-observation",
    "Space Research": "science",
    "Amateur": "communications",
    "Radionavigational": "navigation",
    "Broadcasting": "communications",
    "Fixed": "communications",
    "Maritime": "communications",
}

#: How to say it on the card. Written here rather than in `build_release` so the
#: claim and its wording live with the evidence that justifies them.
SERVICE_PURPOSE = (
    "The public catalog does not identify this spacecraft's payload. What is on record is its "
    "radio licence: its transmitters are filed under the ITU {service} service in the SatNOGS "
    "community database, which is what its operator told a regulator it would use the spectrum "
    "for. That is evidence about what it does, and it is not a mission statement from whoever "
    "flies it."
)


def service_missions(
    satellites: list[dict[str, Any]],
    satnogs_by_norad: dict[int, list[dict[str, Any]]],
    transmitters_by_norad: dict[int, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    """A cited mission for objects the site currently says nothing about.

    Fills a GAP ONLY. Every condition below exists to keep it from becoming a
    second opinion competing with a real one:

      1. our mission is ``other`` and our basis is ``unclassified`` -- so this
         can never contradict a name rule, a category group, a catalog-number
         rule or a human
      2. SatNOGS identity is ``confirmed``, on the catalog number plus the name
         or the launch date
      3. the object has ACTIVE transmitters, and after removing the universal
         ``Space Operation`` housekeeping allocation exactly ONE service remains
      4. that service maps to exactly one mission in ``SERVICE_IMPLIES_MISSION``

    Two services means two possible readings and produces nothing. Measured on
    the live catalog 2026-08-19: 1,969 objects have no mission at all, 626 of
    them are in SatNOGS, and this resolves the ones whose licence says so.
    """
    out: list[dict[str, Any]] = []
    for ours in satellites:
        # "The card says nothing" -- OR "the card says only what this lane put
        # there last time". The second half is not a convenience: this function
        # reads the PUBLISHED catalog, so once a licence-derived mission ships,
        # the object is no longer `unclassified` and a bar that demanded that
        # would find nothing on the next run, write an empty table, and revert
        # all 65 cards. Same trap as the withdrawal ledger, caught the same day.
        #
        # It is still re-derived from scratch every run rather than remembered,
        # which is the difference from the ledger: a licence can lapse and a
        # SatNOGS row can be corrected, and when that happens the sentence must
        # come off the card.
        eligible = (
            (ours.get("mission") == "other" and ours.get("classificationBasis") == "unclassified")
            or ours.get("classificationBasis") == "radio-licence"
        )
        if not eligible:
            continue
        entries = satnogs_by_norad.get(ours["id"]) or []
        if len(entries) != 1:
            continue
        theirs = entries[0]
        verdict, reasons = identity_verdict(ours, theirs)
        if verdict != "confirmed":
            continue
        services = services_for(ours["id"], transmitters_by_norad) - {"Space Operation"}
        if len(services) != 1:
            continue
        service = next(iter(services))
        mission = SERVICE_IMPLIES_MISSION.get(service)
        if mission is None:
            continue
        out.append({
            "id": ours["id"],
            "name": ours["name"],
            "mission": mission,
            "service": service,
            "purpose": SERVICE_PURPOSE.format(service=service),
            "evidence": reasons + [f"all active transmitters filed under ITU service {service!r}"],
            "source": SATELLITE_PAGE.format(sat_id=theirs.get("sat_id")),
            "checkedAt": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        })
    return out


def load_service_missions(path: Path | None = None) -> dict[int, dict[str, Any]]:
    """The cited-mission table `build_release` applies to otherwise-blank cards."""
    target = path or SERVICE_MISSIONS
    if not target.is_file():
        return {}
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return {int(entry["id"]): entry for entry in payload.get("missions", []) if entry.get("id")}


# ---------------------------------------------------------------------------
# The one automatic correction
# ---------------------------------------------------------------------------

#: The bases this module is allowed to overrule. A name pattern is the weakest
#: evidence `build_release` produces and the only one whose failure mode is
#: "a different spacecraft with the same name". `exact-name`, `norad-id`,
#: `source-group` and anything curated are all off limits -- a human or a
#: catalogue-number join stands, always. (Brief, 2026-08-19: never auto-overwrite
#: a curated entry.)
OVERRULABLE_BASES = frozenset({"name-pattern"})


def withdrawal_candidates(
    satellites: list[dict[str, Any]],
    satnogs_by_norad: dict[int, list[dict[str, Any]]],
    transmitters_by_norad: dict[int, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    """Name-pattern claims that two independent sources say are about somebody else.

    Every condition must hold, and each one is here because dropping it lets a
    correct card through:

      1. the claim's basis is a name pattern       (nothing stronger is touched)
      2. the object is a cohort outlier            (its own fleet disowns it)
      3. SatNOGS knows the object at all           (else there is no second source)
      4. SatNOGS identity is ``confirmed``         (a catalogue number is not identity)
      5. SatNOGS's radios put it in a different ITU service family from the
         cohort's, or SatNOGS's country contradicts the cohort's majority

    The output is a WITHDRAWAL, never a replacement: constellation, mission and
    sector go back to unknown and the card says so. This module cannot assert
    that COSMIC is a technology demonstrator -- that took a human reading a
    description, and it lives in `data/satellite_overrides.json` where human
    judgements belong.
    """
    by_id = {satellite["id"]: satellite for satellite in satellites}
    cohort_members: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for satellite in satellites:
        if satellite.get("constellation"):
            cohort_members[satellite["constellation"]].append(satellite)

    out: list[dict[str, Any]] = []
    for nomination in cohort_outliers(satellites):
        if nomination["basis"] not in OVERRULABLE_BASES:
            continue
        ours = by_id[nomination["id"]]
        entries = satnogs_by_norad.get(ours["id"]) or []
        if len(entries) != 1:
            # No entry means no second source. More than one means SatNOGS
            # itself is unsure which object this catalogue number is, and an
            # ambiguous source is not evidence.
            continue
        theirs = entries[0]
        verdict, reasons = identity_verdict(ours, theirs)
        if verdict != "confirmed":
            continue

        evidence = list(reasons)
        ours_services = services_for(ours["id"], transmitters_by_norad)
        cohort_services: set[str] = set()
        for member in cohort_members[nomination["constellation"]]:
            if member["id"] != ours["id"]:
                cohort_services |= services_for(member["id"], transmitters_by_norad)
        # `Space Operation` is every spacecraft's own housekeeping link, so it
        # cannot separate two missions and is removed from BOTH sides before the
        # comparison. What remains is what the object is licensed to DO.
        mission_services = ours_services - {"Space Operation"}
        cohort_mission_services = cohort_services - {"Space Operation"}
        service_split = bool(
            cohort_mission_services
            and (not mission_services or not (mission_services & cohort_mission_services))
        )
        if service_split:
            evidence.append(
                "ITU radio service differs from the rest of the constellation: "
                f"this object {sorted(ours_services) or ['none filed']}, "
                f"the cohort {sorted(cohort_services)}"
            )

        country = country_verdict(ours.get("ownerCode", ""), theirs.get("countries", ""))
        cohort_owner = collections.Counter(
            member.get("ownerCode")
            for member in cohort_members[nomination["constellation"]]
            if member["id"] != ours["id"]
        ).most_common(1)
        country_split = bool(
            country[0] == "agree" and cohort_owner and cohort_owner[0][0] != ours.get("ownerCode")
        )
        if country_split:
            evidence.append(
                f"SatNOGS independently confirms the owner we hold ({country[1]}), "
                f"and it is not the constellation's ({cohort_owner[0][0]})"
            )
        if not (service_split or country_split):
            continue

        out.append({
            "id": ours["id"],
            "name": ours["name"],
            "withdraw": ["constellation", "mission", "sector"],
            "was": {
                "constellation": ours.get("constellation"),
                "mission": ours.get("mission"),
                "sector": ours.get("sector"),
            },
            "why": (
                f"The name token that put this object in the {nomination['constellation']} "
                "constellation belongs to a different spacecraft. Its own cohort disagrees "
                "with it about owner and launch, and SatNOGS -- matched on catalog number "
                "and corroborated on name and launch date -- describes a different kind of "
                "spacecraft."
            ),
            "evidence": evidence,
            "source": SATELLITE_PAGE.format(sat_id=theirs.get("sat_id")),
            "satnogsName": theirs.get("name"),
            "checkedAt": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        })
    return out


def merge_withdrawals(
    existing: list[dict[str, Any]], found: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Keep every withdrawal ever made, and add the new ones. NEVER drop one here.

    THE CORRECTION ERASES ITS OWN EVIDENCE, and a first version of this file
    silently reverted itself because of it. `withdrawal_candidates` reads the
    PUBLISHED catalog, which is the right thing to check -- and a withdrawn
    object no longer looks like a name-pattern outlier in that catalog, because
    the withdrawal already fixed it. So the second run finds nothing, writes an
    empty table, and the next build puts COSMIC back in the weather
    constellation with every test still green.

    The fix is that this table is a LEDGER, not a snapshot. Removing an entry is
    a human decision -- delete the line and say why in the commit -- for the same
    reason an entry is only ever added on evidence.
    """
    merged = {int(entry["id"]): entry for entry in existing}
    for entry in found:
        key = int(entry["id"])
        if key in merged:
            # Re-confirmed. Keep the original date so the ledger records when
            # the finding was made, not when it was last re-read.
            merged[key] = {**entry, "firstSeen": merged[key].get("firstSeen", entry["checkedAt"])}
        else:
            merged[key] = {**entry, "firstSeen": entry["checkedAt"]}
    return [merged[key] for key in sorted(merged)]


def load_withdrawals(path: Path | None = None) -> dict[int, dict[str, Any]]:
    """The withdrawal table `build_release` applies, keyed by catalog number.

    Missing file is a normal state and returns nothing: the site must build
    identically whether or not this lane has ever run.
    """
    target = path or WITHDRAWALS
    if not target.is_file():
        return {}
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return {int(entry["id"]): entry for entry in payload.get("withdrawals", []) if entry.get("id")}


# ---------------------------------------------------------------------------
# The report
# ---------------------------------------------------------------------------


def compare_all(
    satellites: list[dict[str, Any]],
    satnogs_by_norad: dict[int, list[dict[str, Any]]],
    transmitters_by_norad: dict[int, list[dict[str, Any]]],
) -> dict[str, Any]:
    """Every object, every comparison, with the reason attached to each one."""
    rows: list[dict[str, Any]] = []
    counts = collections.Counter()
    for ours in satellites:
        entries = satnogs_by_norad.get(ours["id"]) or []
        if not entries:
            counts["not-in-satnogs"] += 1
            continue
        counts["joined"] += 1
        if len(entries) > 1:
            counts["ambiguous-satnogs-row"] += 1
        theirs = entries[0]
        verdict, reasons = identity_verdict(ours, theirs)
        counts[f"identity:{verdict}"] += 1
        country, country_reason = country_verdict(ours.get("ownerCode", ""), theirs.get("countries", ""))
        counts[f"country:{country}"] += 1
        services = services_for(ours["id"], transmitters_by_norad)
        mission_services = services - {"Space Operation"}
        service_conflict = bool(
            mission_services
            and ours.get("mission") not in ("other",)
            and not any(
                ours.get("mission") in SERVICE_CONSISTENT_MISSIONS.get(service, frozenset())
                for service in mission_services
            )
        )
        if service_conflict:
            counts["service-conflicts-mission"] += 1
        if verdict == "contradicted" or country == "disagree" or service_conflict:
            rows.append({
                "id": ours["id"],
                "ourName": ours.get("name"),
                "theirName": theirs.get("name"),
                "identity": verdict,
                "identityReasons": reasons,
                "ourOwner": ours.get("ownerCode"),
                "theirCountries": theirs.get("countries"),
                "countryVerdict": country,
                "countryReason": country_reason,
                "ourMission": ours.get("mission"),
                "ourBasis": ours.get("classificationBasis"),
                "ourPurposeKind": ours.get("purposeKind"),
                "theirServices": sorted(services),
                "serviceConflictsMission": service_conflict,
                "source": SATELLITE_PAGE.format(sat_id=theirs.get("sat_id")),
            })
    return {"rows": rows, "counts": dict(counts)}


def render_report(
    summary: dict[str, Any],
    nominations: list[dict[str, Any]],
    applied: list[dict[str, Any]],
    total: int,
    satnogs_total: int,
    authenticated: bool,
    coverage: list[dict[str, Any]] | None = None,
    coherence: list[dict[str, Any]] | None = None,
    token_conflicts: list[dict[str, Any]] | None = None,
    filled: list[dict[str, Any]] | None = None,
) -> str:
    """The document a reviewer reads. Scale first, then what was and was not done.

    Written as prose with tables rather than a bare diff because the honest
    answer here is mostly "we cannot tell", and a diff format makes that look
    like an omission instead of the finding it is.
    """
    counts = summary["counts"]
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    joined = counts.get("joined", 0)
    lines: list[str] = []
    add = lines.append
    add("# SatNOGS cross-check: where we and the community database disagree")
    add("")
    add(f"Generated {stamp} by `pipeline/satnogs_verify.py`. "
        f"SatNOGS request identity: {'Sean’s API token' if authenticated else 'anonymous'}.")
    add("")
    add("## How much of the catalog this can even reach")
    add("")
    add("| | objects |")
    add("|---|---:|")
    add(f"| Objects on the site's catalog | {total} |")
    add(f"| Satellites SatNOGS holds, in total | {satnogs_total} |")
    add(f"| **Joined by catalog number** | **{joined}** |")
    add(f"| No SatNOGS entry at all | {counts.get('not-in-satnogs', 0)} |")
    add("")
    add(f"So SatNOGS can say something about **{joined} of {total} objects "
        f"({joined * 100 // max(total, 1)}%)**. It is a database of spacecraft that "
        "amateurs receive radio from, so it is dense on CubeSats and empty on "
        "geostationary television. For the other "
        f"{counts.get('not-in-satnogs', 0)} objects this check produces nothing at all, "
        "and no amount of running it again will change that.")
    add("")
    add("## Of the objects it can reach")
    add("")
    add("| check | result | count |")
    add("|---|---|---:|")
    for key in sorted(k for k in counts if k.startswith("identity:")):
        add(f"| identity | {key.split(':', 1)[1]} | {counts[key]} |")
    for key in sorted(k for k in counts if k.startswith("country:")):
        add(f"| country | {key.split(':', 1)[1]} | {counts[key]} |")
    add(f"| ITU radio service | contradicts our mission | {counts.get('service-conflicts-mission', 0)} |")
    add(f"| SatNOGS itself | two rows for one catalog number | {counts.get('ambiguous-satnogs-row', 0)} |")
    add("")
    add("**Read the country row carefully.** A disagreement is not our error by "
        "default. Reading them by hand on 2026-08-19, most are rideshare "
        "deployments where the community's guess at which TLE belongs to which "
        "CubeSat differs from space-track's, and several record the "
        "manufacturer's country instead of the operator's. Nothing in this lane "
        "writes an owner from SatNOGS, and nothing should.")
    add("")
    add("## Corrections applied automatically")
    add("")
    if not applied:
        add("None. Every automatic correction requires a name-pattern claim, a "
            "constellation that disowns the object, and independent SatNOGS "
            "evidence; nothing met all three this run.")
    else:
        for entry in applied:
            add(f"### {entry['name']} (NORAD {entry['id']})")
            add("")
            add(f"Withdrawn: {', '.join(entry['withdraw'])}. "
                f"Was {entry.get('was')}. First found {entry.get('firstSeen', entry.get('checkedAt'))}.")
            add("")
            add(entry.get("why", ""))
            add("")
            for reason in entry.get("evidence", []):
                add(f"- {reason}")
            add(f"- Source: {entry.get('source', '—')} (SatNOGS entry {entry.get('satnogsName')!r})")
            add("")
    add("## Nominated by the cohort check but NOT corrected")
    add("")
    add("These objects sit in a constellation whose other members disagree with "
        "them about both owner and launch. That is a real smell, and on its own "
        "it is not enough -- several are correct cards for jointly owned or "
        "newly launched spacecraft. Each needs a person.")
    add("")
    add("| NORAD | name | constellation | basis | our owner | cohort owners |")
    add("|---:|---|---|---|---|---|")
    applied_ids = {entry["id"] for entry in applied}
    for nomination in nominations:
        if nomination["id"] in applied_ids:
            continue
        add(f"| {nomination['id']} | {nomination['name']} | {nomination['constellation']} | "
            f"{nomination['basis']} | {nomination['ownerCode']} | {nomination['cohortOwners']} |")
    add("")
    add("## Filled from a radio licence, where the card said nothing at all")
    add("")
    add("These objects had no mission on the site. Their transmitters are filed "
        "under one ITU radio service and one only, which is what their operator "
        "told a regulator they would use the spectrum for. The card now says that, "
        "says it is a licence and not a mission statement, and links the entry.")
    add("")
    if not (filled or []):
        add("None this run.")
    else:
        add("| NORAD | name | ITU service | mission now shown | source |")
        add("|---:|---|---|---|---|")
        for entry in filled or []:
            add(f"| {entry['id']} | {entry['name']} | {entry['service']} | "
                f"{entry['mission']} | {entry['source']} |")
    add("")
    add("## Every name rule, and how much it claims")
    add("")
    add("Sean's question, and the right one. A rule claiming thousands of objects "
        "that all share one owner is not hiding anything. A rule claiming a "
        "handful across several owners is where the next COSMIC is. A rule "
        "claiming NOTHING is dead -- a mission this site believes it recognises "
        "and does not.")
    add("")
    dead = [row for row in (coverage or []) if row["claims"] == 0]
    mixed = [row for row in (coverage or []) if row["claims"] and row["owners"] > 1]
    add(f"Of {len(coverage or [])} name tokens: {len(dead)} match nothing at all, "
        f"{len(mixed)} span more than one owner.")
    add("")
    add("| token | objects claimed | owners | top owners | lone owners |")
    add("|---|---:|---:|---|---|")
    for row in coverage or []:
        add(f"| `{row['token']}` | {row['claims']} | {row['owners']} | "
            f"{row['topOwners'] or '—'} | {', '.join(row['singletonOwners']) or '—'} |")
    add("")
    add("## Every CelesTrak category group, and whether it agrees with itself")
    add("")
    add("The other way a mission reaches a card. A group cannot be judged by the "
        "members it labelled itself, so this counts only members classified from "
        "INDEPENDENT evidence — a name rule, an exact name, or a catalog number. "
        "Their agreement is real information about what the group contains.")
    add("")
    add("A group with many independent members and near-total disagreement is not "
        "noisy. It is about something else: participation in a system rather than "
        "a kind of spacecraft. Those are withheld from the mission inference in "
        "`build_release.PARTICIPATION_GROUPS`, which records why for each one.")
    add("")
    add("| group | asserts | conf | in group | it decided | independent | agree | disagree | the dissenters are | withheld |")
    add("|---|---|---|---:|---:|---:|---:|---:|---|:-:|")
    for row in coherence or []:
        witness = "—" if not row["independent"] else f"{row['agree']}"
        add(f"| `{row['group']}` | {row['asserts'] or '—'} | {row['confidence']} | "
            f"{row['members']} | {row['decided']} | {row['independent']} | {witness} | "
            f"{row['disagree'] if row['independent'] else '—'} | "
            f"{row['disagreeAs'] or '—'} | {'yes' if row['withheld'] else ''} |")
    add("")
    add("A group with no independent members at all is **unaudited**, not clean: "
        "nothing in the catalog can currently contradict it.")
    add("")
    add("### Objects that stand alone inside a name rule")
    add("")
    add("Same test as the constellation check, applied to the raw token, so it "
        "reaches the rules that set a mission without setting a fleet. Review "
        "list only.")
    add("")
    add("| NORAD | name | token | mission | basis | our owner | others matching that token |")
    add("|---:|---|---|---|---|---|---|")
    for row in token_conflicts or []:
        add(f"| {row['id']} | {row['name']} | `{row['token']}` | {row['mission']} | "
            f"{row['basis']} | {row['ownerCode']} | {row['cohortOwners']} |")
    add("")
    add("## Every disagreement, for a human")
    add("")
    add("`identity` is the column that matters. `contradicted` means the catalog "
        "number matched but the name and the launch date both say it is a "
        "different spacecraft -- that is a SatNOGS attribution problem, not ours, "
        "and the rest of the row should be ignored.")
    add("")
    add("| NORAD | ours | theirs | identity | our owner | their country | our mission | basis | their ITU service | source |")
    add("|---:|---|---|---|---|---|---|---|---|---|")
    for row in sorted(summary["rows"], key=lambda r: r["id"]):
        add(
            f"| {row['id']} | {row['ourName']} | {row['theirName']} | {row['identity']} | "
            f"{row['ourOwner']} | {row['theirCountries'] or '—'} | {row['ourMission']} | "
            f"{row['ourBasis']} | {', '.join(row['theirServices']) or '—'} | {row['source']} |"
        )
    add("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# The free text: what a person wrote about the spacecraft
# ---------------------------------------------------------------------------
#
# SatNOGS keeps a human-written Description on each satellite -- "Reimei ...
# serves aurora observations as well as demonstrating several new technologies"
# -- and it is NOT in the API. The satellites serializer publishes 18 fields and
# that is not one of them, so the only way to read it is the object's own page.
#
# That means one request per object, which is exactly the pattern this file
# spends its docstring arguing against. It is allowed here on three conditions,
# all enforced below: it runs ONLY for objects whose card currently says nothing
# (so the request buys something), it is capped per run, and the answer is
# cached to disk permanently -- a description is a paragraph a volunteer typed,
# not a measurement, and re-reading it weekly would be pure waste. 566 objects
# qualified on 2026-08-19; at the 1.2-second floor that is about eleven minutes
# ONCE.
#
# Nothing in this section decides anything. The text is handed to a local model
# on the operator's own GPU, which proposes a mission and one sentence; the
# proposal lands in a review file and a person promotes it into
# data/satellite_overrides.json. No field on any card is written from it.

DESCRIPTIONS = "descriptions"

#: The page renders "Description" then the text then the "SatNOGS Links"
#: heading. Crude on purpose: a parser clever enough to be wrong quietly is
#: worse here than one that returns nothing when the template changes, and a
#: missing description is a normal, harmless outcome.
_DESCRIPTION = re.compile(r"Description\s*(.{0,4000}?)\s*SatNOGS Links", re.S)
_TAGS = re.compile(r"<[^>]+>")
_SCRIPTS = re.compile(r"<(script|style).*?</\1>", re.S)

#: Below this, the text is a label rather than a description -- "From Japan",
#: "Zombie satellite" -- and there is nothing for a model to reason over. Sending
#: it anyway would spend GPU time to produce a confident sentence about nothing,
#: which is the failure mode a modest model is worst at resisting.
MIN_DESCRIPTION_CHARS = 60


def description_of(page_html: str) -> str:
    text = _TAGS.sub(" ", _SCRIPTS.sub("", page_html))
    match = _DESCRIPTION.search(re.sub(r"\s+", " ", text))
    return match.group(1).strip() if match else ""


def fetch_descriptions(
    wanted: list[tuple[int, str]],
    *,
    token: str | None = None,
    limit: int = 250,
    cache_dir: Path | None = None,
) -> dict[str, str]:
    """SatNOGS page descriptions for the given (catalog id, sat_id) pairs.

    Cached forever by `sat_id`; only pairs absent from the cache cost a request,
    and only `limit` of them per run. Stops on the first non-200 and returns what
    it has -- a partial answer is worth having and hammering a volunteer service
    after it starts refusing is not.
    """
    directory = cache_dir or CACHE
    path = directory / f"{DESCRIPTIONS}.json"
    cache: dict[str, str] = {}
    if path.is_file():
        try:
            cache = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            cache = {}
    todo = [(catalog_id, sat_id) for catalog_id, sat_id in wanted if sat_id not in cache][:limit]
    fetched = 0
    for _catalog_id, sat_id in todo:
        try:
            page = fetch(SATELLITE_PAGE.format(sat_id=sat_id) + "/", token=token)
        except SatnogsUnavailable as error:
            print(f"STOPPING description fetch after {fetched}: {error}", flush=True)
            break
        # An empty string is a RESULT and is cached as one. Without that the next
        # run re-asks for every object that simply has no description written.
        cache[sat_id] = description_of(page.decode("utf-8", "replace"))
        fetched += 1
    if fetched:
        directory.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(cache, indent=0, sort_keys=True), encoding="utf-8")
    print(f"descriptions: {fetched} fetched, {len(cache)} cached, {len(todo) - fetched} left", flush=True)
    return cache


def description_queue(
    satellites: list[dict[str, Any]],
    satnogs_by_norad: dict[int, list[dict[str, Any]]],
    descriptions: dict[str, str],
) -> list[dict[str, Any]]:
    """The rows the local model is shown -- and nothing else.

    One row per object whose card says nothing and whose SatNOGS entry carries
    real prose. Identity must be ``confirmed`` first: reading a description
    attached to the wrong spacecraft is how a plausible, sourced, completely
    wrong sentence gets written.
    """
    rows: list[dict[str, Any]] = []
    for ours in satellites:
        if ours.get("mission") != "other":
            continue
        entries = satnogs_by_norad.get(ours["id"]) or []
        if len(entries) != 1:
            continue
        theirs = entries[0]
        if identity_verdict(ours, theirs)[0] != "confirmed":
            continue
        text = (descriptions.get(theirs.get("sat_id", "")) or "").strip()
        if len(text) < MIN_DESCRIPTION_CHARS:
            continue
        rows.append({
            "id": ours["id"],
            "name": ours["name"],
            "satnogsName": theirs.get("name"),
            "owner": ours.get("ownerLabel"),
            "orbit": ours.get("orbit"),
            "description": text,
            "source": SATELLITE_PAGE.format(sat_id=theirs.get("sat_id")),
        })
    return rows


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def published_catalog(data_root: Path) -> dict[str, Any]:
    """The catalog artifact the site is currently serving.

    Read from the published manifest rather than rebuilt, so this lane checks
    WHAT A VISITOR SEES. A check that classified a fresh in-memory catalog would
    be checking a thing nobody is looking at.
    """
    manifest = json.loads((data_root / "manifest.json").read_text(encoding="utf-8"))
    reference = manifest["catalog"]
    path = data_root / "artifacts" / Path(str(reference.get("path") or reference)).name
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data-root", default=str(ROOT / "public" / "data"))
    parser.add_argument("--refresh", action="store_true", help="re-fetch even if the cache is fresh")
    parser.add_argument("--report-only", action="store_true", help="write the report, write no corrections")
    parser.add_argument("--report", default=str(STATE / "satnogs-disagreements.md"))
    parser.add_argument("--fetch-descriptions", type=int, default=0, metavar="N",
                        help="read up to N SatNOGS pages for their free-text descriptions "
                             "(one request each, cached forever; 0 uses only the cache)")
    args = parser.parse_args(argv)

    token = api_token()
    print(f"SatNOGS: {'authenticated' if token else 'anonymous (no token found)'}", flush=True)
    try:
        satnogs = load_satellites(token=token, refresh=args.refresh)
        transmitters = load_transmitters(token=token, refresh=args.refresh)
    except SatnogsUnavailable as error:
        print(f"STOPPING: {error}. Nothing was changed; try again when they are back.", flush=True)
        return 2

    catalog = published_catalog(Path(args.data_root))
    satellites = catalog["satellites"]
    satnogs_by_norad = index_by_norad(satnogs)
    transmitters_by_norad = index_by_norad(transmitters)

    summary = compare_all(satellites, satnogs_by_norad, transmitters_by_norad)
    nominations = cohort_outliers(satellites)
    # Merged against the ledger BEFORE the report is rendered, so the report
    # shows every correction standing on the site -- not just the ones this run
    # rediscovered, which after the first successful run is none of them.
    applied = merge_withdrawals(
        list(load_withdrawals().values()),
        withdrawal_candidates(satellites, satnogs_by_norad, transmitters_by_norad),
    )
    wanted = [
        (ours["id"], (satnogs_by_norad[ours["id"]][0] or {}).get("sat_id", ""))
        for ours in satellites
        if ours.get("mission") == "other" and len(satnogs_by_norad.get(ours["id"]) or []) == 1
    ]
    descriptions = fetch_descriptions(wanted, token=token, limit=args.fetch_descriptions)
    queue = description_queue(satellites, satnogs_by_norad, descriptions)
    queue_path = STATE / "satnogs-description-queue.jsonl"
    queue_path.parent.mkdir(parents=True, exist_ok=True)
    queue_path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in queue), encoding="utf-8"
    )
    print(f"description queue -> {queue_path} ({len(queue)} rows)", flush=True)

    coverage = name_rule_coverage(satellites)
    coherence = celestrak_group_coherence(satellites)
    token_conflicts = token_cohort_conflicts(satellites)
    filled = service_missions(satellites, satnogs_by_norad, transmitters_by_norad)

    report = render_report(
        summary, nominations, applied, len(satellites), len(satnogs), bool(token),
        coverage=coverage, coherence=coherence, token_conflicts=token_conflicts,
        filled=filled,
    )
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")
    print(f"report -> {report_path}", flush=True)

    if not args.report_only:
        WITHDRAWALS.parent.mkdir(parents=True, exist_ok=True)
        WITHDRAWALS.write_text(
            json.dumps(
                {
                    "note": (
                        "Generated by pipeline/satnogs_verify.py. Each entry TAKES AWAY a "
                        "name-pattern claim that two independent sources contradict; none of "
                        "them asserts anything. A curated entry in satellite_overrides.json "
                        "outranks everything here."
                    ),
                    "generatedAt": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "withdrawals": applied,
                },
                indent=2,
                sort_keys=True,
            ) + "\n",
            encoding="utf-8",
        )
        print(f"withdrawals -> {WITHDRAWALS} ({len(applied)})", flush=True)
        # Not a ledger: unlike a withdrawal, this claim is re-derivable from the
        # same two sources every run, and an object that stops meeting the bar
        # (its licence lapses, SatNOGS revises the row) must lose the sentence
        # rather than keep it because we once wrote it down.
        SERVICE_MISSIONS.write_text(
            json.dumps(
                {
                    "note": (
                        "Generated by pipeline/satnogs_verify.py. A mission for objects the "
                        "catalog says NOTHING about, derived from the single ITU radio service "
                        "their transmitters are filed under. Never applied over any other "
                        "evidence, and the sentence on the card says it is a licence."
                    ),
                    "generatedAt": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "missions": filled,
                },
                indent=2,
                sort_keys=True,
            ) + "\n",
            encoding="utf-8",
        )
        print(f"service missions -> {SERVICE_MISSIONS} ({len(filled)})", flush=True)

    counts = summary["counts"]
    print(
        f"checked {len(satellites)} objects; {counts.get('joined', 0)} joined to SatNOGS; "
        f"{len(summary['rows'])} disagreements; {len(applied)} corrected; "
        f"{len(nominations) - len(applied)} nominated for a human; "
        f"{len(filled)} blank cards filled from a radio licence; "
        f"{sum(1 for row in coverage if row['claims'] == 0)} of {len(coverage)} name rules match nothing; "
        f"{sum(1 for row in coherence if row['independent'] and row['disagree'] > row['agree'])} "
        f"of {len(coherence)} CelesTrak groups are contradicted by their own independent members",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
