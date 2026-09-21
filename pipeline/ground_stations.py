"""Published ground stations, and the published links between them and spacecraft.

What this module is allowed to do
---------------------------------
It reads a hand-authored, cited table (``data/ground_stations.json``), validates
it far harder than it validates anything else, joins the link rows to the
published satellite catalog **by NORAD catalog ID only**, and emits an artifact.

What this module must never do, and cannot
------------------------------------------
It must never decide that a station and a spacecraft are related. That decision
belongs to whoever published the statement, and the citation is the whole
product. ``docs/mission-speculation-design.md`` §1.6 excluded object-to-object
association because the owner of this site is a serving US information warfare
officer and correlating identities is an intelligence product; associating a
spacecraft with the antenna that commands it is the same act pointed at the
ground, so it gets the same treatment.

The exclusion is structural, exactly as §1.6 requires, not a comment:

1. **No function here takes an orbit.** There is no OMM, no propagation, no
   latitude, no pass geometry and no timing on any code path in this file. A
   capability with no function to call cannot be reached by a later refactor.
2. **A link is a row that a human typed with a URL beside it.** ``resolve_links``
   only matches ``noradId`` to a catalog entry that already exists. It can drop
   a row. It can never create one.
3. **Every link carries ``evidence``** — the published sentence, in the
   publisher's words. A row nobody can check does not build.
4. **Distances are never computed.** Station coordinates and satellite elements
   never meet in this module. The browser computes passes for a pair the reader
   has selected, from a link that was already published; it does not search for
   pairs.

No network access. Everything here is a pure function of the checked-in table
plus the catalog the release already built.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Callable, Iterable

ROOT = Path(__file__).resolve().parents[1]
STATION_TABLE = ROOT / "data" / "ground_stations.json"

SCHEMA_VERSION = 1

#: Closed set. A station type outside this list is a hard error, not a
#: pass-through, so a new category has to be added deliberately in a diff a
#: reviewer sees.
STATION_ROLES = frozenset({
    "deep-space-tracking",
    "command-and-control",
    "data-downlink",
    "tracking-telemetry-command",
    "launch-range-tracking",
    "amateur-reception",
})

#: Who runs the site. This drives the military policy gate below.
OPERATOR_KINDS = frozenset({
    "civil-agency",
    "scientific",
    "commercial",
    "academic",
    "amateur",
    "military",
})

#: How well the coordinate is known, so the interface can say so rather than
#: implying survey precision it does not have. ``privacy-reduced`` means the
#: publisher deliberately degraded it — SatNOGS rounds volunteer stations so a
#: home address cannot be read off the map — and the site must not "improve" it.
COORDINATE_PRECISIONS = frozenset({
    "published-survey",
    "published-approximate",
    "privacy-reduced",
})

BANDS = frozenset({"UHF", "VHF", "L", "S", "C", "X", "Ku", "Ka", "optical"})

#: Closed set of published relationship kinds. Note what is absent: there is no
#: "assessed", "likely", "co-located" or "observed-tracking" value. A row is a
#: published statement about a role, or it is not a row.
RELATIONSHIPS = frozenset({
    "command-and-control",
    "data-downlink",
    "tracking-telemetry-command",
    "deep-space-tracking",
})

RELATIONSHIP_LABELS = {
    "command-and-control": "commands this spacecraft",
    "data-downlink": "receives this spacecraft's mission data",
    "tracking-telemetry-command": "provides telemetry, tracking and command",
    "deep-space-tracking": "tracks this spacecraft as part of a deep-space network",
}

#: Policy values for military ground sites. The default is ``excluded`` and the
#: validator refuses a military row while it holds, so turning this on is a
#: single reviewable line rather than something that happens by drift. This is
#: Sean's call to make, not the pipeline's: see docs/ground-stations-design.md.
MILITARY_POLICIES = frozenset({"excluded", "included"})

_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

#: Fields that would turn a volunteer's station entry into a home address or a
#: person. Present in the table at all is an error, whatever their value.
FORBIDDEN_STATION_FIELDS = frozenset({
    "address",
    "contact",
    "email",
    "phone",
    "ownerName",
    "personName",
    "callsign",
})


class StationTableError(ValueError):
    """A ground-station table that cannot be published as it stands."""


def _require_url(value: Any, where: str) -> str:
    text = str(value or "").strip()
    if not text.startswith("https://") and not text.startswith("http://"):
        raise StationTableError(f"{where}: a citation must be a URL, got {value!r}")
    return text


def _require_text(value: Any, where: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise StationTableError(f"{where}: required and must not be empty")
    return text


def _require_closed(values: Any, allowed: Iterable[str], where: str) -> list[str]:
    if not isinstance(values, list) or not values:
        raise StationTableError(f"{where}: expected a non-empty list")
    allowed = frozenset(allowed)
    unknown = [value for value in values if value not in allowed]
    if unknown:
        raise StationTableError(f"{where}: unknown value(s) {unknown!r}; allowed {sorted(allowed)}")
    if len(set(values)) != len(values):
        raise StationTableError(f"{where}: repeats a value")
    return list(values)


def validate_station_table(table: dict[str, Any]) -> None:
    """Refuse a table that could put an uncited claim or an address on the map.

    Deliberately raises rather than warning, for the same reason
    ``validate_overrides`` does. A station pin asserts that a named
    organisation operates an antenna at a named place; a link row asserts that
    a named antenna talks to a named spacecraft. Both are claims about real
    installations on a site published under a serving officer's name, and
    neither ships without somewhere a reader can go to check it.
    """
    if table.get("schema") != SCHEMA_VERSION:
        raise StationTableError(f"unsupported ground-station table schema {table.get('schema')!r}")

    policy = table.get("policy")
    if not isinstance(policy, dict):
        raise StationTableError("the table must carry a 'policy' object")
    military = policy.get("militarySites")
    if military not in MILITARY_POLICIES:
        raise StationTableError(
            f"policy.militarySites must be one of {sorted(MILITARY_POLICIES)}, got {military!r}"
        )
    _require_text(policy.get("militarySitesRationale"), "policy.militarySitesRationale")

    stations = table.get("stations")
    if not isinstance(stations, list) or not stations:
        raise StationTableError("the table must carry a non-empty 'stations' list")

    seen: dict[str, dict[str, Any]] = {}
    for station in stations:
        if not isinstance(station, dict):
            raise StationTableError("every station must be an object")
        station_id = _require_text(station.get("id"), "station.id")
        where = f"station {station_id!r}"
        if not _ID.match(station_id):
            raise StationTableError(f"{where}: id must be lower-case kebab-case")
        if station_id in seen:
            raise StationTableError(f"{where}: duplicate id")

        leaked = sorted(FORBIDDEN_STATION_FIELDS.intersection(station))
        if leaked:
            raise StationTableError(
                f"{where}: carries personal or contact field(s) {leaked}. "
                "A ground-station pin is a place, never a person; drop the field."
            )

        _require_text(station.get("name"), f"{where}.name")
        _require_text(station.get("network"), f"{where}.network")
        _require_text(station.get("operator"), f"{where}.operator")
        _require_text(station.get("country"), f"{where}.country")

        operator_kind = station.get("operatorKind")
        if operator_kind not in OPERATOR_KINDS:
            raise StationTableError(
                f"{where}.operatorKind must be one of {sorted(OPERATOR_KINDS)}, got {operator_kind!r}"
            )
        if operator_kind == "military" and military == "excluded":
            raise StationTableError(
                f"{where}: operatorKind 'military' while policy.militarySites is 'excluded'. "
                "Including military ground sites is the site owner's decision, not the "
                "pipeline's; see docs/ground-stations-design.md before changing the policy."
            )

        latitude = station.get("latitudeDeg")
        longitude = station.get("longitudeDeg")
        if not isinstance(latitude, (int, float)) or not -90 <= float(latitude) <= 90:
            raise StationTableError(f"{where}.latitudeDeg must be a number in [-90, 90], got {latitude!r}")
        if not isinstance(longitude, (int, float)) or not -180 <= float(longitude) <= 180:
            raise StationTableError(f"{where}.longitudeDeg must be a number in [-180, 180], got {longitude!r}")

        precision = station.get("coordinatePrecision")
        if precision not in COORDINATE_PRECISIONS:
            raise StationTableError(
                f"{where}.coordinatePrecision must be one of {sorted(COORDINATE_PRECISIONS)}, got {precision!r}"
            )
        if operator_kind == "amateur" and precision != "privacy-reduced":
            raise StationTableError(
                f"{where}: an amateur station must be published at 'privacy-reduced' precision. "
                "These are volunteers' homes."
            )

        _require_closed(station.get("roles"), STATION_ROLES, f"{where}.roles")
        bands = station.get("bands")
        if bands is not None:
            _require_closed(bands, BANDS, f"{where}.bands")

        mask = station.get("minimumElevationDeg")
        if mask is not None and (not isinstance(mask, (int, float)) or not 0 <= float(mask) < 90):
            raise StationTableError(f"{where}.minimumElevationDeg must be in [0, 90), got {mask!r}")

        _require_url(station.get("source"), f"{where}.source")
        _require_text(station.get("sourceName"), f"{where}.sourceName")
        _require_text(station.get("sourceRetrieved"), f"{where}.sourceRetrieved")
        _require_text(station.get("licence"), f"{where}.licence")
        seen[station_id] = station

    links = table.get("links")
    if not isinstance(links, list):
        raise StationTableError("the table must carry a 'links' list, even when empty")
    pairs: set[tuple[str, int, str]] = set()
    for index, link in enumerate(links):
        if not isinstance(link, dict):
            raise StationTableError("every link must be an object")
        where = f"link[{index}]"
        station_id = _require_text(link.get("stationId"), f"{where}.stationId")
        if station_id not in seen:
            raise StationTableError(f"{where}: stationId {station_id!r} is not a station in this table")
        norad = link.get("noradId")
        if not isinstance(norad, int) or isinstance(norad, bool) or norad <= 0:
            raise StationTableError(f"{where}.noradId must be a positive integer, got {norad!r}")
        _require_text(link.get("satelliteName"), f"{where}.satelliteName")
        relationship = link.get("relationship")
        if relationship not in RELATIONSHIPS:
            raise StationTableError(
                f"{where}.relationship must be one of {sorted(RELATIONSHIPS)}, got {relationship!r}"
            )
        key = (station_id, norad, relationship)
        if key in pairs:
            raise StationTableError(f"{where}: duplicates an earlier link for the same station, object and role")
        pairs.add(key)

        _require_url(link.get("source"), f"{where}.source")
        _require_text(link.get("sourceName"), f"{where}.sourceName")
        _require_text(link.get("sourceRetrieved"), f"{where}.sourceRetrieved")
        # The published sentence, in the publisher's words. This is the field
        # that makes the difference between "someone published this" and "an
        # agent decided it looked right", and it is why there is no code path
        # here that can manufacture a link: nothing can write this string.
        evidence = _require_text(link.get("evidence"), f"{where}.evidence")
        if len(evidence) < 24:
            raise StationTableError(
                f"{where}.evidence is too short to be a published statement: {evidence!r}"
            )


def load_station_table(path: Path = STATION_TABLE) -> dict[str, Any]:
    table = json.loads(path.read_text())
    validate_station_table(table)
    return table


def resolve_links(
    table: dict[str, Any],
    catalog_ids: Iterable[int],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Split the published links into those whose object is in this release and those not.

    The catalog is capped and rebuilt every five minutes, so a perfectly good
    published link can point at an object that is not in today's 8,000. That is
    an ordinary, honest outcome and it is reported rather than hidden: the
    reader sees the citation with a note that the spacecraft is not in the
    displayed catalog, instead of the relationship silently disappearing.

    This is the only join in the module, and it is on an identifier. It reads
    no orbit and computes no geometry.
    """
    present = set(catalog_ids)
    resolved: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    for link in table["links"]:
        record = {
            "stationId": link["stationId"],
            "noradId": link["noradId"],
            "satelliteName": link["satelliteName"],
            "relationship": link["relationship"],
            "relationshipLabel": RELATIONSHIP_LABELS[link["relationship"]],
            "evidence": link["evidence"],
            "source": link["source"],
            "sourceName": link["sourceName"],
            "sourceRetrieved": link["sourceRetrieved"],
        }
        if link.get("note"):
            record["note"] = str(link["note"])
        (resolved if link["noradId"] in present else unresolved).append(record)
    return resolved, unresolved


def build_ground_station_bundle(
    table: dict[str, Any],
    catalog_ids: Iterable[int],
) -> dict[str, Any]:
    """The published artifact: stations, published links, and what is missing."""
    resolved, unresolved = resolve_links(table, catalog_ids)
    stations = []
    for station in table["stations"]:
        record = {
            "id": station["id"],
            "name": station["name"],
            "network": station["network"],
            "operator": station["operator"],
            "operatorKind": station["operatorKind"],
            "country": station["country"],
            "latitudeDeg": float(station["latitudeDeg"]),
            "longitudeDeg": float(station["longitudeDeg"]),
            "coordinatePrecision": station["coordinatePrecision"],
            "roles": list(station["roles"]),
            "source": station["source"],
            "sourceName": station["sourceName"],
            "sourceRetrieved": station["sourceRetrieved"],
            "licence": station["licence"],
        }
        for optional in ("altitudeM", "bands", "antennaDiameterM", "minimumElevationDeg", "note"):
            if station.get(optional) is not None:
                record[optional] = station[optional]
        stations.append(record)

    return {
        "schema": SCHEMA_VERSION,
        "status": "published-record",
        "policy": dict(table["policy"]),
        "attribution": table.get(
            "attribution",
            "Station locations and satellite relationships are published by the operators cited on each record.",
        ),
        "limitation": (
            "Every station and every station-to-spacecraft relationship on this map is a statement "
            "its operator published, shown with the citation. Nothing here is inferred from orbits, "
            "pass timing or geometry, and a relationship that has not been published is simply absent "
            "rather than guessed at. The map is not a complete census of ground stations: it shows "
            "the ones whose location an operator chose to publish."
        ),
        "stationCount": len(stations),
        "linkCount": len(resolved),
        "stations": stations,
        "links": resolved,
        "linksOutsideCatalog": unresolved,
        "relationshipLabels": dict(RELATIONSHIP_LABELS),
    }


def publish(
    data_root: Path,
    write_artifact: Callable[[Path, str, Any], tuple[str, str]],
    catalog_ids: Iterable[int],
    table_path: Path = STATION_TABLE,
) -> dict[str, Any]:
    """Manifest fragment, in the shape ``build_release`` already merges."""
    bundle = build_ground_station_bundle(load_station_table(table_path), catalog_ids)
    path, digest = write_artifact(data_root, "ground-stations", bundle)
    return {
        "groundStations": {
            "path": path,
            "sha256": digest,
            "stationCount": bundle["stationCount"],
            "linkCount": bundle["linkCount"],
        }
    }
