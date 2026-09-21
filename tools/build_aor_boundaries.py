#!/usr/bin/env python3
"""Build the vendored areas-of-responsibility overlay from published sources.

Why this is a generator rather than a hand-drawn file
-----------------------------------------------------
Combatant-command areas of responsibility are published as *lists of countries*.
The familiar Unified Command Plan map is a country-shaded map: it is not a survey
of lines, it is an assignment of states. So the honest way to draw one is to take
the published assignment and colour exactly those countries -- which means the
geometry comes from a public-domain basemap (Natural Earth) and the *authorship*
of the boundary stays with the command that published the list.

Numbered fleet areas are different. They are maritime and are published as prose,
some of which names real lines ("the International Date Line", "the India/
Pakistan border") and some of which does not ("the Kuril Islands in the North").
Those get drawn from the named lines, with every unnamed edge marked indefinite
so the map shows an open boundary instead of a confident invention.

Nothing here is traced from a picture and nothing is guessed. Each record carries
the sentence it came from and the URL that published it.

Usage
-----
    python3 tools/build_aor_boundaries.py --out src/data/aor-boundaries.ts
"""

from __future__ import annotations

import argparse
import json
import re
import urllib.request
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
NE_110M = (
    "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/"
    "geojson/ne_110m_admin_0_countries.geojson"
)

# --------------------------------------------------------------------------
# Areas published as a PROSE EXTENT rather than as a country list.
#
# Numbered fleets are all of this kind, and so is USINDOPACOM, whose published
# statement gives real limits ("the western border of India", "from Antarctica
# to the North Pole") rather than a roster of states.
#
# `edges` describes each side of the box. An edge is either a published line
# (kind "published", with the words that published it) or an unpublished one
# (kind "indefinite"), and the renderer draws the second kind as an open, faded
# boundary rather than a hard line. That distinction is the whole reason this is
# drawable at all.
# --------------------------------------------------------------------------
PROSE_EXTENTS: list[dict[str, Any]] = [
    {
        "id": "c7f",
        "name": "U.S. 7th Fleet",
        "statement": (
            "Seventh Fleet's area of operations spans more than 124-million square "
            "kilometers, stretching from the International Date Line to the India/Pakistan "
            "border; and from the Kuril Islands in the North to the Antarctic in the South."
        ),
        "source": "https://www.c7f.navy.mil/About-Us/Facts-Sheet/",
        "archiveSource": "https://web.archive.org/web/20260413082339/https://www.c7f.navy.mil/About-Us/Facts-Sheet/",
        "sourceName": "U.S. 7th Fleet",
        "year": 2026,
        "box": {"west": 68.0, "east": 180.0, "south": -78.0, "north": 50.5},
        "edges": {
            "east": {"kind": "published", "note": "The International Date Line, named in the fact sheet."},
            "west": {"kind": "published-numeric", "note": "The 68th meridian east. Seventh Fleet's 2013 fact sheet stated this numerically - 'from the International Date Line to the 68th meridian east, which runs down from the India-Pakistan border' - and it is the only numeric coordinate boundary the U.S. Navy has ever published for any fleet. The current fact sheet gives the same limit in words."},
            "north": {"kind": "indefinite", "note": "'The Kuril Islands in the North' names a landmark, not a line. Drawn at their latitude and shown open."},
            "south": {"kind": "indefinite", "note": "'The Antarctic in the South' names a region, not a line. Shown open."},
        },
        "labelAt": [150.0, 15.0],
    },
    {
        "id": "c5f",
        "name": "U.S. 5th Fleet",
        "statement": (
            "...encompasses about 2.5 million square miles of water area and includes the "
            "Arabian Gulf, Red Sea, Gulf of Oman and parts of the Indian Ocean. This expanse, "
            "comprised of 21 countries, includes three critical choke points at the Strait of "
            "Hormuz, the Suez Canal and the Strait of Bab el-Mandeb at the southern tip of Yemen."
        ),
        "source": "https://www.cusnc.navy.mil/About-Us/",
        "archiveSource": "https://web.archive.org/web/20260802000000/https://www.cusnc.navy.mil/About-Us/",
        "sourceName": "U.S. Naval Forces Central Command / U.S. 5th Fleet",
        "year": 2026,
        "box": {"west": 32.0, "east": 78.0, "south": 5.0, "north": 30.5},
        "edges": {
            "east": {"kind": "indefinite", "note": "'Parts of the Indian Ocean' names no seaward limit."},
            "west": {"kind": "published", "note": "The Red Sea and the Suez Canal, both named in the fact sheet."},
            "north": {"kind": "published", "note": "The Arabian Gulf and the Strait of Hormuz, both named in the fact sheet."},
            "south": {"kind": "published", "note": "The Strait of Bab el-Mandeb, named in the fact sheet."},
        },
        "labelAt": [58.0, 18.0],
    },
    {
        "id": "c6f",
        "name": "U.S. Naval Forces Europe-Africa / 6th Fleet",
        "statement": (
            "The Commander, U.S. Naval Forces Europe-Africa (NAVEUR-NAVAF) area of "
            "responsibility (AOR) covers approximately half of the Atlantic Ocean, from the "
            "Arctic Ocean to the coast of Antarctica, as well as the Adriatic, Baltic, "
            "Barents, Black, Caspian, Mediterranean, and North Seas."
        ),
        "source": "https://www.c6f.navy.mil/About-Us/",
        "archiveSource": "https://web.archive.org/web/20260629145143/https://www.c6f.navy.mil/About-Us/",
        "sourceName": "U.S. Naval Forces Europe-Africa / U.S. 6th Fleet",
        "year": 2026,
        "box": {"west": -45.0, "east": 55.0, "south": -78.0, "north": 84.0},
        "edges": {
            "east": {"kind": "indefinite", "note": "The Caspian Sea is named, but no eastern line is published."},
            "west": {"kind": "indefinite", "note": "'Approximately half of the Atlantic Ocean' is explicitly imprecise; drawn at the mid-Atlantic and shown open."},
            "north": {"kind": "published", "note": "'From the Arctic Ocean', named in the fact sheet."},
            "south": {"kind": "published", "note": "'To the coast of Antarctica', named in the fact sheet."},
        },
        "labelAt": [-10.0, 35.0],
    },
]

# --------------------------------------------------------------------------
# Commands that publish their own AOR geometry.
#
# This is the strongest source available, and it settles the method question:
# AFRICOM's file literally declares `"name": "ne_50m_admin_0_countries"`. The
# command built its own AOR map by taking public-domain Natural Earth outlines
# and selecting the assigned states -- exactly the construction this generator
# uses. So this is not a workaround for missing data; it is the same method the
# publisher used, and where the publisher hosts the result we take theirs.
#
# Both files are `var countryData = {...};` wrappers with hand-added `//`
# comments inside the coordinate arrays and trailing commas, so they need
# cleaning before json.loads.
# --------------------------------------------------------------------------
PUBLISHED_GEOJSON: list[dict[str, Any]] = [
    {
        "id": "usafricom",
        "name": "United States Africa Command",
        "url": "https://www.africom.mil/data/africajson.js",
        "statement": (
            "responsible for operations, exercises, and security cooperation on the African "
            "continent, its island nations, and surrounding waters. The area of responsibility "
            "consists of 53 African states"
        ),
        "source": "https://www.africom.mil/about-the-command",
        "archiveSource": None,
        "sourceName": "U.S. Africa Command",
        "year": 2026,
        "geometrySource": "https://www.africom.mil/data/africajson.js",
        "exclude": set(),
        "caveat": (
            "The command's own map data, published on its own host. The file declares its base "
            "layer as Natural Earth 1:50m admin-0 countries, so the outlines are public-domain "
            "basemap and the assignment - which is the actual boundary - is AFRICOM's. Western "
            "Sahara appears in neither the list nor the file, so that edge is genuinely "
            "unpublished. Egypt is excluded by AFRICOM's own footnote: it sits in U.S. Central "
            "Command's area."
        ),
        "labelAt": [20.0, 2.0],
    },
    {
        "id": "useucom",
        "name": "United States European Command",
        "url": "https://www.eucom.mil/data/europejson.js",
        "statement": (
            "The USEUCOM area of responsibility covers 50 countries and territories, including "
            "Europe, Russia, and parts of Asia and the Middle East."
        ),
        "source": "https://www.eucom.mil/about/the-region",
        "archiveSource": None,
        "sourceName": "U.S. European Command",
        "year": 2026,
        "geometrySource": "https://www.eucom.mil/data/europejson.js",
        # Israel's ASSIGNMENT moved to U.S. Central Command; DoD announced it
        # on 15 January 2021. The geometry file was not wrong and did not go
        # stale: it carries the lines, which did not move. See the caveat.
        "exclude": {"ISR"},
        "caveat": (
            "The command's own map data, with one deliberate subtraction. The file carries the "
            "GEOGRAPHY and the command's live country-list page carries the ASSIGNMENTS, and "
            "those change on different timescales: Israel's assignment moved to U.S. Central "
            "Command on 15 January 2021 without any line moving. So this overlay takes the "
            "geometry from the file and the assignment from the list, and the two are not in "
            "conflict - a stable geometry file alongside a current assignment list is exactly "
            "how a boundary set behaves when its lines hold for years while the states inside "
            "them occasionally change hands. The file also carries five European dependencies "
            "- Aland, the Faroe Islands, Guernsey, the Isle of Man and Jersey - which the "
            "50-country prose list does not enumerate."
        ),
        "labelAt": [15.0, 52.0],
    },
]

# Commands that publish a country LIST but no geometry. Filled from the list.
COMMANDS: list[dict[str, Any]] = []


def load_published_geojson(url: str) -> list[dict[str, Any]]:
    """Read a command's own `var countryData = {...};` AOR file.

    Both known files carry hand-added `//` comments inside the coordinate arrays
    and trailing commas, and AFRICOM's nests FeatureCollections one level deep in
    places -- so walk for Features rather than reading `.features` directly.
    """
    # A bare "Mozilla/5.0" gets a 403 from these hosts; a full browser
    # User-Agent does not. Verified against both files on 2026-08-08.
    request = urllib.request.Request(url, headers={
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/126.0 Safari/537.36"
        ),
    })
    with urllib.request.urlopen(request, timeout=180) as response:
        text = response.read().decode("utf-8-sig")
    text = text[text.index("{"):].rstrip().rstrip(";")
    text = re.sub(r"//[^\n]*", "", text)
    text = re.sub(r",\s*([}\]])", r"\1", text)
    document = json.loads(text)

    features: list[dict[str, Any]] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            if node.get("type") == "Feature":
                features.append(node)
                return
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(document)
    return features


def feature_code(feature: dict[str, Any]) -> str | None:
    """ADM0_A3, whatever case the publisher used. AFRICOM upper, EUCOM lower."""
    properties = feature.get("properties", {})
    for key in ("ADM0_A3", "adm0_a3", "ISO_A3", "iso_a3"):
        value = properties.get(key)
        if isinstance(value, str) and value not in ("", "-99"):
            return value.upper()
    return None


def load_countries(path: Path | None) -> dict[str, Any]:
    if path is not None:
        return json.loads(path.read_text())
    request = urllib.request.Request(NE_110M, headers={"User-Agent": "space-explorer-aor-builder"})
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.loads(response.read().decode("utf8"))


def rings_of(geometry: dict[str, Any]) -> Iterable[list[list[float]]]:
    kind = geometry["type"]
    coordinates = geometry["coordinates"]
    if kind == "Polygon":
        yield from coordinates
    elif kind == "MultiPolygon":
        for polygon in coordinates:
            yield from polygon


def round_ring(ring: list[list[float]], places: int = 1) -> list[list[float]]:
    """Round, drop consecutive duplicates, and discard rings that collapse.

    One decimal place is about 11 km. That is far finer than an AOR needs: this
    is a shaded region drawn at world scale, not a cadastral boundary, and the
    underlying assignment is per-country anyway. EUCOM publishes its file at
    1:10m, which is ~465 KB of vendored coordinates at two decimals and ~4x
    smaller at one, for no visible difference on the map.
    """
    out: list[list[float]] = []
    for point in ring:
        rounded = [round(point[0], places), round(point[1], places)]
        if not out or out[-1] != rounded:
            out.append(rounded)
    if len(out) > 2 and out[0] != out[-1]:
        out.append(out[0])
    # A ring that collapses to a point or a line at this precision is an islet
    # too small to draw; keeping it costs bytes and renders nothing.
    return out if len(out) >= 4 else []


def command_rings(countries: dict[str, Any], iso_codes: set[str]) -> tuple[list[list[list[float]]], set[str]]:
    """Outer rings of every assigned country. Deliberately not a dissolve.

    A true polygon union would need a geometry library this project does not
    have and does not need: drawing the countries individually renders the same
    area and keeps each country's own outline visible, which is closer to what
    the published map actually shows.
    """
    found: set[str] = set()
    rings: list[list[list[float]]] = []
    for feature in countries["features"]:
        code = feature["properties"].get("ADM0_A3")
        if code not in iso_codes:
            continue
        found.add(code)
        geometry = feature["geometry"]
        raw_rings = (
            [geometry["coordinates"][0]] if geometry["type"] == "Polygon"
            else [polygon[0] for polygon in geometry["coordinates"]]
        )
        for raw in raw_rings:
            simplified = round_ring(raw)
            if simplified:
                rings.append(simplified)
    return rings, found


def fleet_rings(box: dict[str, float]) -> list[list[list[float]]]:
    """A lon/lat box, densified so it curves correctly in any projection."""
    west, east = box["west"], box["east"]
    south, north = box["south"], box["north"]
    step = 2.0
    ring: list[list[float]] = []
    longitude = west
    while longitude < east:
        ring.append([round(longitude, 2), south])
        longitude += step
    ring.append([east, south])
    longitude = east
    while longitude > west:
        ring.append([round(longitude, 2), north])
        longitude -= step
    ring.append([west, north])
    ring.append([west, south])
    return [ring]


HEADER = '''/**
 * Areas of responsibility, vendored offline.
 *
 * GENERATED by tools/build_aor_boundaries.py -- do not edit by hand.
 *
 * Combatant-command areas are drawn as the countries their command publicly
 * assigns to them, because that is what the published Unified Command Plan map
 * is: an assignment of states, not a survey of lines. The country outlines come
 * from Natural Earth 1:110m admin-0 (public domain); the assignment, and
 * therefore the boundary, comes from the cited command.
 *
 * Numbered fleet areas are maritime and are published as prose. Each edge is
 * marked `published` where the source names a line, and `indefinite` where it
 * names a landmark or says "approximately". The renderer draws the second kind
 * open and faded, so the map never asserts a line nobody published.
 *
 * Vendored rather than fetched, the same way the coastline artifact is: no
 * runtime third-party request.
 */

export type AorEdgeKind = "published" | "published-numeric" | "indefinite";

export interface AorEdge {
  kind: AorEdgeKind;
  note: string;
}

export interface AorBoundary {
  id: string;
  name: string;
  kind: "combatant-command" | "numbered-fleet";
  /** The sentence that published this area. */
  statement: string;
  source: string;
  archiveSource: string | null;
  sourceName: string;
  year: number;
  /** Rings of [longitude, latitude]. */
  rings: Array<Array<[number, number]>>;
  /** Present for prose extents; null where the area is a country selection. */
  edges: Record<string, AorEdge> | null;
  /**
   * Set where the geometry itself was published by the command, rather than
   * assembled here from a country list. This is the strongest provenance
   * available and it is worth showing.
   */
  geometrySource: string | null;
  caveat: string | null;
  labelAt: [number, number] | null;
}

export const AOR_BOUNDARIES: AorBoundary[] = '''


def emit(out_path: Path, records: list[dict[str, Any]], warnings: list[str]) -> None:
    text = HEADER + json.dumps(records, separators=(",", ":"), ensure_ascii=False) + ";\n"
    if warnings:
        text += "\n// Builder warnings:\n" + "".join(f"//   {w}\n" for w in warnings)
    out_path.write_text(text)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the vendored AOR overlay.")
    parser.add_argument("--out", default=str(ROOT / "src" / "data" / "aor-boundaries.ts"))
    parser.add_argument("--countries", default=None, help="Local Natural Earth admin-0 GeoJSON")
    args = parser.parse_args()

    countries = load_countries(Path(args.countries) if args.countries else None)
    records: list[dict[str, Any]] = []
    warnings: list[str] = []

    for published in PUBLISHED_GEOJSON:
        features = load_published_geojson(published["url"])
        kept: list[list[list[float]]] = []
        excluded: list[str] = []
        for feature in features:
            code = feature_code(feature)
            if code and code in published["exclude"]:
                excluded.append(code)
                continue
            geometry = feature["geometry"]
            rings_to_add = (
                [geometry["coordinates"][0]] if geometry["type"] == "Polygon"
                else [polygon[0] for polygon in geometry["coordinates"]]
            )
            for raw in rings_to_add:
                simplified = round_ring(raw)
                if simplified:
                    kept.append(simplified)
        missing = sorted(set(published["exclude"]) - set(excluded))
        if missing:
            warnings.append(
                f"{published['id']}: expected to exclude {', '.join(missing)} but the published file did not contain it"
            )
        records.append({
            "id": published["id"],
            "name": published["name"],
            "kind": "combatant-command",
            "statement": published["statement"],
            "source": published["source"],
            "archiveSource": published.get("archiveSource"),
            "sourceName": published["sourceName"],
            "year": published["year"],
            "geometrySource": published["geometrySource"],
            "rings": kept,
            "edges": None,
            "caveat": published.get("caveat"),
            "labelAt": published.get("labelAt"),
        })
        print(f"  {published['id']}: {len(features)} published features, "
              f"{len(kept)} rings kept, excluded {excluded or 'nothing'}")

    for command in COMMANDS:
        iso = set(command["iso"])
        rings, found = command_rings(countries, iso)
        missing = sorted(iso - found)
        if missing:
            warnings.append(f"{command['id']}: no basemap country for {', '.join(missing)}")
        records.append({
            "id": command["id"],
            "name": command["name"],
            "kind": "combatant-command",
            "statement": command["statement"],
            "source": command["source"],
            "archiveSource": command.get("archiveSource"),
            "sourceName": command["sourceName"],
            "year": command["year"],
            "rings": rings,
            "edges": None,
            "geometrySource": None,
            "caveat": command.get("caveat"),
            "labelAt": command.get("labelAt"),
        })

    for fleet in PROSE_EXTENTS:
        records.append({
            "id": fleet["id"],
            "name": fleet["name"],
            "kind": fleet.get("kind", "numbered-fleet"),
            "statement": fleet["statement"],
            "source": fleet["source"],
            "archiveSource": fleet.get("archiveSource"),
            "sourceName": fleet["sourceName"],
            "year": fleet["year"],
            "rings": fleet_rings(fleet["box"]),
            "edges": fleet["edges"],
            "geometrySource": None,
            "caveat": fleet.get("caveat"),
            "labelAt": fleet.get("labelAt"),
        })

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    emit(out_path, records, warnings)
    print(f"wrote {out_path} ({out_path.stat().st_size // 1024} KB, {len(records)} areas)")
    for warning in warnings:
        print(f"  warning: {warning}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
