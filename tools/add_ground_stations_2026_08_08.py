#!/usr/bin/env python3
"""Second pass on the ground-station table: the agencies and networks that were
dropped when the first pass ran out of session.

Run once from the repo root:

    python3 tools/add_ground_stations_2026_08_08.py

It is idempotent — a station or link whose id is already present is skipped —
so re-running it after a hand edit does not duplicate anything. It exists as a
script rather than a hand edit because it also stamps ``registryName`` on every
link from the offline SATCAT mirror, which is not something to type 60 times.

Nothing here reaches the network. Every coordinate below was read off the
operator page named in its ``source`` field and is quoted in ``note`` or
``evidence`` where the publisher's own wording matters.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TABLE = ROOT / "data" / "ground_stations.json"
RETRIEVED = "2026-08-08"

# --------------------------------------------------------------------------
# JAXA. The first pass concluded "JAXA publishes no latitude", having read the
# Space Tracking and Communications Center pages, which publish street
# addresses and dish diameters and no coordinates. That conclusion was wrong:
# the Misasa User's Guide points at a coordinates page maintained by the ISAS
# navigation group, and it publishes ITRF2014 positions to a few centimetres.
# --------------------------------------------------------------------------
JAXA_SOURCE = "https://ddor.nav.isas.jaxa.jp/station_coordinates/"
JAXA_SOURCE_NAME = (
    "JAXA Station Coordinates, ISAS navigation group (H. Takeuchi), "
    "last updated 11 January 2026"
)
JAXA_LICENCE = (
    "JAXA / ISAS. Geodetic positions are published facts, cited not reproduced."
)

STATIONS: list[dict] = [
    {
        "id": "jaxa-usuda-64m",
        "name": "Usuda 64 m (DSS-48)",
        "network": "JAXA deep-space network",
        "operator": "JAXA / ISAS",
        "operatorKind": "civil-agency",
        "country": "Japan",
        "latitudeDeg": 36.132403748,
        "longitudeDeg": 138.362773862,
        "altitudeM": 1490,
        "coordinatePrecision": "published-survey",
        "roles": ["deep-space-tracking", "command-and-control"],
        "bands": ["S", "X"],
        "antennaDiameterM": 64,
        "minimumElevationDeg": 5,
        "note": (
            "Geodetic latitude and longitude on GRS80 at epoch 2026.0, published by the ISAS "
            "navigation group in ITRF2014 at epoch 2015.0; the publisher states one-sigma "
            "accuracy of a few centimetres per component. Altitude is the published orthometric "
            "height above the EGM96 geoid (1490.1922 m); the ellipsoidal height is 1532.8122 m. "
            "The same page publishes the antenna's ECEF vector, which reproduces these degrees "
            "to 10 cm. JAXA also gives this antenna the DSN station identifier DSS-48. The "
            "elevation mask is this site's 5-degree assumption, not JAXA's: JAXA publishes a "
            "real per-azimuth downlink horizon mask at UDSC_horizon_mask.xls on the same page."
        ),
        "source": JAXA_SOURCE,
        "sourceName": JAXA_SOURCE_NAME,
        "sourceRetrieved": RETRIEVED,
        "licence": JAXA_LICENCE,
    },
    {
        "id": "jaxa-misasa-54m",
        "name": "Misasa Deep Space Station 54 m (DSS-30)",
        "network": "JAXA deep-space network",
        "operator": "JAXA / ISAS",
        "operatorKind": "civil-agency",
        "country": "Japan",
        "latitudeDeg": 36.140984502,
        "longitudeDeg": 138.35212867,
        "altitudeM": 1613,
        "coordinatePrecision": "published-survey",
        "roles": ["deep-space-tracking", "command-and-control"],
        "bands": ["X", "Ka"],
        "antennaDiameterM": 54,
        "minimumElevationDeg": 7,
        "note": (
            "Geodetic GRS80 at epoch 2026.0; altitude is the published orthometric height above "
            "the EGM96 geoid (1613.380 m), ellipsoidal height 1655.993 m. The publisher is "
            "unusually candid about the error: the 54 m antenna has no S-band receiver, so "
            "conventional S/X geodetic VLBI cannot measure it, and JAXA states it assumes "
            "\"a formal error of about 5-10 cm for the station position errors\". The elevation "
            "mask is JAXA's published antenna drive limit of 7 degrees, not this site's default. "
            "JAXA's Misasa User's Guide gives the site only as 138 deg 21 min E / 36 deg 8 min N; "
            "these are the surveyed figures from the coordinates page the guide points at."
        ),
        "source": JAXA_SOURCE,
        "sourceName": JAXA_SOURCE_NAME,
        "sourceRetrieved": RETRIEVED,
        "licence": JAXA_LICENCE,
    },
    {
        "id": "jaxa-uchinoura-34m",
        "name": "Uchinoura 34 m (DSS-38)",
        "network": "JAXA deep-space network",
        "operator": "JAXA / ISAS",
        "operatorKind": "civil-agency",
        "country": "Japan",
        "latitudeDeg": 31.25430804,
        "longitudeDeg": 131.078392333,
        "altitudeM": 346,
        "coordinatePrecision": "published-survey",
        "roles": ["deep-space-tracking", "tracking-telemetry-command"],
        "antennaDiameterM": 34,
        "minimumElevationDeg": 5,
        "note": (
            "Geodetic GRS80 at epoch 2026.0; altitude is the published orthometric height above "
            "the EGM96 geoid (346.445 m), ellipsoidal height 375.7827 m. The publisher states "
            "one-sigma accuracy of about 3 cm per component and notes this station was not moved "
            "by the earthquakes that shifted Usuda. Bands are not stated on the source page and "
            "are therefore not recorded. JAXA gives this antenna the DSN identifier DSS-38."
        ),
        "source": JAXA_SOURCE,
        "sourceName": JAXA_SOURCE_NAME,
        "sourceRetrieved": RETRIEVED,
        "licence": JAXA_LICENCE,
    },
    {
        "id": "jaxa-uchinoura-20m",
        "name": "Uchinoura 20 m (DSS-37)",
        "network": "JAXA deep-space network",
        "operator": "JAXA / ISAS",
        "operatorKind": "civil-agency",
        "country": "Japan",
        "latitudeDeg": 31.256625132,
        "longitudeDeg": 131.080381009,
        "altitudeM": 362,
        "coordinatePrecision": "published-approximate",
        "roles": ["tracking-telemetry-command"],
        "antennaDiameterM": 20,
        "minimumElevationDeg": 5,
        "note": (
            "The only station on this page for which JAXA publishes the ECEF vector and not the "
            "degrees: X -3586293.8662, Y 4113888.6263, Z 3290452.1716 m. These degrees are that "
            "vector converted to geodetic GRS80 by the ordinary closed-form datum conversion, the "
            "same arithmetic used to turn the DSN handbook's arcseconds into degrees; no position "
            "has been estimated. Recorded as approximate because the publisher says so in as many "
            "words: \"Position accuracy of the Uchinoura 20 m antenna is unknown.\" Altitude is "
            "the ellipsoidal height from the same conversion less the 29.3 m geoid separation "
            "published for the neighbouring 34 m antenna."
        ),
        "source": JAXA_SOURCE,
        "sourceName": JAXA_SOURCE_NAME,
        "sourceRetrieved": RETRIEVED,
        "licence": JAXA_LICENCE,
    },
]


# --------------------------------------------------------------------------
# DLR. The first pass also put DLR in the "publishes no latitude" list. It
# publishes an arcsecond fix, a height and a local gravity value on a page whose
# title is, in German, "Location of the station / coordinates".
# --------------------------------------------------------------------------
STATIONS.append({
    "id": "dlr-gars-ohiggins",
    "name": "GARS O'Higgins",
    "network": "DLR German Antarctic Receiving Station",
    "operator": "German Aerospace Center (DLR) Earth Observation Center",
    "operatorKind": "scientific",
    "country": "Antarctica",
    "latitudeDeg": -63.320800,
    "longitudeDeg": -57.900847,
    "altitudeM": 18,
    "coordinatePrecision": "published-survey",
    "roles": ["data-downlink"],
    "bands": ["L", "S", "X"],
    "antennaDiameterM": 9,
    "note": (
        "Converted from the arcseconds DLR publishes: 63 deg 19' 14.88\" South, 57 deg 54' "
        "03.05\" West, height above sea level 17.56 m. The same page publishes the local "
        "gravity to eight figures, which is a geodetic station's way of saying the position is "
        "surveyed; the datum is not stated. DLR's own page places this station \"in immediate "
        "proximity to the Chilean station General Bernardo O'Higgins\" rather than inside it: "
        "the pin is DLR's civil Earth-observation and VLBI facility, which is what makes it "
        "eligible for this table at all."
    ),
    "source": (
        "https://www.dlr.de/de/eoc/forschung-transfer/forschungsinfrastruktur/"
        "station-gars-ohiggins/stationsbeschreibung/lage-der-station-koordinaten"
    ),
    "sourceName": "DLR EOC, Station GARS O'Higgins: Lage der Station / Koordinaten",
    "sourceRetrieved": RETRIEVED,
    "licence": "DLR. Coordinates are published facts, cited not reproduced.",
})

# --------------------------------------------------------------------------
# Viasat Real-Time Earth. Publishes an antenna-level fix, dish size and bands
# for every site, in prose, on its own product page. Four of the ten are within
# 3 km of a station this table already carries and are recorded in the design
# document rather than drawn twice.
# --------------------------------------------------------------------------
VIASAT_SOURCE = "https://www.viasat.com/government/antenna-systems/real-time-earth/"
VIASAT_SOURCE_NAME = "Viasat, Real-Time Earth: \"Viasat Real-Time Earth deployments\""
VIASAT_LICENCE = "Viasat Inc. Coordinates are published facts, cited not reproduced."

for _id, _name, _country, _lat, _lon, _dish, _bands, _note in [
    ("viasat-rte-accra", "Accra", "Ghana", 5.6, -0.3, 7.3, ["L", "S", "X", "Ka"],
     "Published to one decimal place only, about 11 km, which is why this row is approximate "
     "where the others from the same page are not."),
    ("viasat-rte-guildford", "Guildford", "United Kingdom", 51.24, -0.62, 5.4, ["S", "X"], None),
    ("viasat-rte-hokkaido", "Hokkaido", "Japan", 42.59, 143.45, 7.3, ["S", "X", "Ka"], None),
    ("viasat-rte-pendergrass", "Pendergrass, Georgia", "United States", 34.18, -83.67, 5.4,
     ["S", "X"], None),
    ("viasat-rte-pitea", "Piteaa / Oejebyn", "Sweden", 65.33, 21.42, 7.3, None,
     "Viasat describes this one as an \"X-Y band\" antenna, which names a mount type rather than "
     "a frequency band, so no bands are recorded."),
    ("viasat-rte-ushuaia", "Ushuaia", "Argentina", -54.50, -67.11, 7.3, ["S", "X"],
     "Viasat adds \"(Ka upgradable)\"; the Ka band is not recorded because it is not in service."),
]:
    STATIONS.append({
        "id": _id,
        "name": f"Viasat Real-Time Earth {_name}",
        "network": "Viasat Real-Time Earth",
        "operator": "Viasat Inc.",
        "operatorKind": "commercial",
        "country": _country,
        "latitudeDeg": _lat,
        "longitudeDeg": _lon,
        "coordinatePrecision": "published-approximate",
        "roles": ["data-downlink", "tracking-telemetry-command"],
        **({"bands": _bands} if _bands else {}),
        "antennaDiameterM": _dish,
        "note": (_note + " " if _note else "") + (
            "Viasat publishes these to two decimal places, about 1 km, as part of a sentence "
            "describing the antenna rather than as a survey."
        ),
        "source": VIASAT_SOURCE,
        "sourceName": VIASAT_SOURCE_NAME,
        "sourceRetrieved": RETRIEVED,
        "licence": VIASAT_LICENCE,
    })

# --------------------------------------------------------------------------
# SSC. The stations SSC owns are published with decimal degrees on its own
# network page. Five of the eleven are already in this table from the NASA Near
# Earth Network users' guide; SSC's own figures agree with NASA's to within the
# rounding, which is recorded in the design document as corroboration.
# --------------------------------------------------------------------------
SSC_SOURCE = "https://sscspace.com/services/satellite-ground-stations/our-stations/"
SSC_SOURCE_NAME = "Swedish Space Corporation, \"Our stations\""
SSC_LICENCE = "Swedish Space Corporation. Coordinates are published facts, cited not reproduced."

for _id, _name, _country, _lat, _lon in [
    ("ssc-clewiston", "Clewiston Satellite Station, Florida", "United States", 26.75, -81.05),
    ("ssc-inuvik", "Inuvik Satellite Station", "Canada", 68.32, -133.54),
    ("ssc-irbene", "Irbene Station, Ventspils", "Latvia", 56.56, 21.86),
    ("ssc-punta-arenas", "Punta Arenas Satellite Station", "Chile", -52.93, -70.85),
    ("ssc-stockholm-teleport", "Stockholm Teleport, Agesta", "Sweden", 59.21, 18.08),
]:
    STATIONS.append({
        "id": _id,
        "name": _name,
        "network": "SSC satellite ground station network",
        "operator": "Swedish Space Corporation",
        "operatorKind": "commercial",
        "country": _country,
        "latitudeDeg": _lat,
        "longitudeDeg": _lon,
        "coordinatePrecision": "published-approximate",
        "roles": ["data-downlink", "tracking-telemetry-command"],
        "note": (
            "SSC publishes each station it owns as \"Lat <n>, Long <n>\" to two decimal places, "
            "about 1 km. Its ten collaborative partner stations are named without coordinates."
        ),
        "source": SSC_SOURCE,
        "sourceName": SSC_SOURCE_NAME,
        "sourceRetrieved": RETRIEVED,
        "licence": SSC_LICENCE,
    })

# --------------------------------------------------------------------------
# Telespazio. This is the operator of the antenna farms EUMETSAT names but does
# not locate — Fucino and Cheia for Meteosat, Lario for MTG mission data. It
# publishes a marker position and a street address for each centre.
# --------------------------------------------------------------------------
TPZ_SOURCE = "https://www.telespazio.com/en/business/space-centres-teleports"
TPZ_SOURCE_NAME = "Telespazio (Leonardo Group), \"Space centres and teleports\""
TPZ_LICENCE = "Telespazio S.p.A. Coordinates are published facts, cited not reproduced."
TPZ_NOTE = (
    "Telespazio publishes a map marker and a street address for each centre. The marker carries "
    "seven decimal places, but it is a geocoded site marker rather than an antenna reference "
    "point, so it is recorded as approximate."
)

for _id, _name, _country, _lat, _lon, _extra in [
    ("telespazio-fucino", "Fucino Space Centre", "Italy", 42.0146925, 13.5907857,
     "This is a different antenna farm from the ESA station also at Fucino that this table "
     "already carries: the two published positions are 4.1 km apart. EUMETSAT names Fucino as "
     "the primary ground station for Meteosat Second Generation and a telemetry, tracking and "
     "control station for Meteosat Third Generation, but publishes no coordinate for it, and "
     "its statements are about the satellite series rather than a named spacecraft, so no link "
     "row follows from them. See docs/ground-stations-design.md section 7 question 4."),
    ("telespazio-lario", "Lario Space Centre", "Italy", 46.1596339, 9.4124281,
     "EUMETSAT names Lario as a Meteosat Third Generation mission-data acquisition ground "
     "station and publishes no coordinate for it."),
    ("telespazio-cheia", "Cheia Space Centre", "Romania", 45.4581462, 25.9382467,
     "EUMETSAT names Cheia as a primary ground station for Meteosat Second Generation and a "
     "telemetry, tracking and control station for Meteosat Third Generation, and publishes no "
     "coordinate for it."),
    ("telespazio-scanzano", "Scanzano Space Centre", "Italy", 37.9937494, 13.2882423, None),
    ("telespazio-benavidez", "Benavidez Teleport", "Argentina", -34.4102909, -58.7192104, None),
]:
    STATIONS.append({
        "id": _id,
        "name": _name,
        "network": "Telespazio space centres and teleports",
        "operator": "Telespazio (Leonardo Group)",
        "operatorKind": "commercial",
        "country": _country,
        "latitudeDeg": _lat,
        "longitudeDeg": _lon,
        "coordinatePrecision": "published-approximate",
        "roles": ["data-downlink", "tracking-telemetry-command"],
        "note": TPZ_NOTE + (" " + _extra if _extra else ""),
        "source": TPZ_SOURCE,
        "sourceName": TPZ_SOURCE_NAME,
        "sourceRetrieved": RETRIEVED,
        "licence": TPZ_LICENCE,
    })

# --------------------------------------------------------------------------
# Leaf Space. The Leaf Line network ships its site list as a marker array in the
# page. It is the largest single haul here and also the least reliable — see the
# defects recorded in the design document. Four of the twenty-four published
# markers are not carried: two whose label and coordinate contradict each other,
# and two that are the same site as a station already in the table.
# --------------------------------------------------------------------------
LEAF_SOURCE = "https://leaf.space/leaf-line/"
LEAF_SOURCE_NAME = "Leaf Space, \"Leaf Line\" ground segment network map"
LEAF_LICENCE = "Leaf Space S.r.l. Coordinates are published facts, cited not reproduced."
LEAF_NOTE = (
    "Leaf Space publishes its network as a map marker list, two decimal places, about 1 km. "
    "Five of its twenty-four published markers are not carried by this table; the reasons are "
    "in docs/ground-stations-design.md section 3."
)

for _id, _name, _country, _lat, _lon, _extra in [
    ("leaf-utqiagvik", "Utqiagvik, Alaska", "United States", 71.29, -156.78, None),
    ("leaf-maui", "Maui, Hawaii", "United States", 20.79, -156.33,
     "Leaf publishes this one at longitude +156.33, which is open water in the Philippine Sea "
     "about 3,000 km from the island in its own label. The sign is corrected here and the "
     "correction is stated, on the same footing as the NOAA Fairbanks longitude below."),
    ("leaf-al-ain", "Al Ain", "United Arab Emirates", 24.2, 55.74, None),
    ("leaf-longwood", "Longwood, Saint Helena", "Saint Helena", -15.94, -5.65, None),
    ("leaf-santiago", "Santiago", "Chile", -33.36, -70.77, None),
    ("leaf-talkeetna", "Talkeetna, Alaska", "United States", 62.33, -150.03, None),
    ("leaf-mon-loisir", "Mon Loisir", "Mauritius", -20.13, 57.68, None),
    ("leaf-blonduos", "Blonduos", "Iceland", 65.64, -20.24, None),
    ("leaf-punta-arenas", "Punta Arenas", "Chile", -53.04, -70.84, None),
    ("leaf-nova-scotia", "Nova Scotia", "Canada", 44.68, -63.74, None),
    ("leaf-absheron", "Absheron", "Azerbaijan", 40.46, 49.48, None),
    ("leaf-nangetty", "Nangetty, Western Australia", "Australia", -29.01, 115.34, None),
    ("leaf-peterborough", "Peterborough, South Australia", "Australia", -32.96, 138.84, None),
    ("leaf-kandy", "Kandy", "Sri Lanka", 7.27, 80.72, None),
    ("leaf-awarua", "Awarua", "New Zealand", -46.52, 168.37, None),
    ("leaf-kaspichan", "Kaspichan", "Bulgaria", 43.31, 27.15, None),
    ("leaf-plana", "Plana", "Bulgaria", 42.48, 23.44, None),
    ("leaf-shetland", "Shetland", "United Kingdom", 60.74, -0.85, None),
    ("leaf-la-paz", "La Paz", "Mexico", 24.09, -110.38, None),
]:
    STATIONS.append({
        "id": _id,
        "name": f"Leaf Line {_name}",
        "network": "Leaf Space Leaf Line",
        "operator": "Leaf Space",
        "operatorKind": "commercial",
        "country": _country,
        "latitudeDeg": _lat,
        "longitudeDeg": _lon,
        "coordinatePrecision": "published-approximate",
        "roles": ["data-downlink", "tracking-telemetry-command"],
        "note": LEAF_NOTE + (" " + _extra if _extra else ""),
        "source": LEAF_SOURCE,
        "sourceName": LEAF_SOURCE_NAME,
        "sourceRetrieved": RETRIEVED,
        "licence": LEAF_LICENCE,
    })

# --------------------------------------------------------------------------
# Links. Published relationships, in the publisher's own words.
# --------------------------------------------------------------------------
EUM_TTC = "https://www.eumetsat.int/telemetry-tracking-and-control"
EUM_COLLECT = "https://www.eumetsat.int/collecting-data"
JAXA_MDSS_MISSIONS = "https://www.isas.jaxa.jp/home/great/english/mission_en.html"

LINKS: list[dict] = [
    {
        "stationId": "ksat-svalsat",
        "noradId": 41335,
        "satelliteName": "SENTINEL 3A",
        "relationship": "tracking-telemetry-command",
        "evidence": (
            "EUMETSAT states that \"the Copernicus Sentinel-3A and -3B satellites are controlled "
            "from EUMETSAT's Darmstadt headquarters via a telemetry, tracking and control s-band "
            "service provided by the European Space Agency. The most regularly used ground "
            "stations are located in Kiruna and Svalbard.\""
        ),
        "source": EUM_TTC,
        "sourceName": "EUMETSAT, Telemetry, tracking and control",
        "sourceRetrieved": RETRIEVED,
        "note": (
            "The publisher names the site, not the antenna, and EUMETSAT publishes no coordinate "
            "for it. The pin is the Svalbard antenna whose position NASA's Near Earth Network "
            "users' guide publishes. The table already carries this spacecraft's science downlink "
            "here on a separate ESA citation; this row is the command and telemetry half."
        ),
    },
    {
        "stationId": "ksat-svalsat",
        "noradId": 43437,
        "satelliteName": "SENTINEL 3B",
        "relationship": "tracking-telemetry-command",
        "evidence": (
            "EUMETSAT states that \"the Copernicus Sentinel-3A and -3B satellites are controlled "
            "from EUMETSAT's Darmstadt headquarters via a telemetry, tracking and control s-band "
            "service provided by the European Space Agency. The most regularly used ground "
            "stations are located in Kiruna and Svalbard.\""
        ),
        "source": EUM_TTC,
        "sourceName": "EUMETSAT, Telemetry, tracking and control",
        "sourceRetrieved": RETRIEVED,
        "note": (
            "The publisher names the site, not the antenna, and EUMETSAT publishes no coordinate "
            "for it. The pin is the Svalbard antenna whose position NASA's Near Earth Network "
            "users' guide publishes."
        ),
    },
    {
        "stationId": "noaa-fairbanks-cda",
        "noradId": 46984,
        "satelliteName": "Sentinel-6 Michael Freilich",
        "relationship": "tracking-telemetry-command",
        "evidence": (
            "EUMETSAT states that \"the Copernicus Sentinel-6 Michael Freilich satellite is "
            "controlled from EUMETSAT's Darmstadt headquarters via a combination of the s-band "
            "European ground station service located in Kiruna and the United States' National "
            "Oceanic and Atmospheric Administration's ground stations located in Fairbanks.\""
        ),
        "source": EUM_TTC,
        "sourceName": "EUMETSAT, Telemetry, tracking and control",
        "sourceRetrieved": RETRIEVED,
        "note": (
            "EUMETSAT's Kiruna half of this sentence is not carried. Three different Kiruna "
            "antennas appear in this table under three operators, EUMETSAT says only \"Kiruna\", "
            "and attaching a real relationship to a guessed dish is worse than leaving it out."
        ),
    },
    {
        "stationId": "noaa-fairbanks-cda",
        "noradId": 46984,
        "satelliteName": "Sentinel-6 Michael Freilich",
        "relationship": "data-downlink",
        "evidence": (
            "EUMETSAT states that \"satellite Tracking, Telemetry and Commanding (TT&C) as well "
            "as the mission instrument data (MDA) from the Sentinel-6 satellite (Sentinel-6 "
            "Michael Freilich) are downlinked on every visible orbit at the Ground Stations at "
            "Fairbanks (Alaska, US) and Kiruna (Sweden). The Fairbanks dual frequency ground "
            "station support is provided as a service by NOAA through the partnership of the "
            "Sentinel-6 mission.\""
        ),
        "source": EUM_COLLECT,
        "sourceName": "EUMETSAT, Collecting the data",
        "sourceRetrieved": RETRIEVED,
    },
    {
        "stationId": "jaxa-misasa-54m",
        "noradId": 40319,
        "satelliteName": "HAYABUSA2",
        "relationship": "deep-space-tracking",
        "evidence": (
            "JAXA lists HAYABUSA2 first among the \"spacecrafts currently in operation and "
            "scheduled to be operated at Misasa Deep Space Station\", under the heading "
            "\"Spacecrafts in operation\"."
        ),
        "source": JAXA_MDSS_MISSIONS,
        "sourceName": "JAXA / ISAS, Misasa Deep Space Station: Spacecrafts",
        "sourceRetrieved": RETRIEVED,
    },
    {
        "stationId": "jaxa-misasa-54m",
        "noradId": 43653,
        "satelliteName": "MPO (Mercury Planetary Orbiter)",
        "relationship": "deep-space-tracking",
        "evidence": (
            "JAXA lists \"MPO, Mercury Planetary Orbiter, Launched on October 20, 2018\" among "
            "the \"spacecrafts currently in operation and scheduled to be operated at Misasa "
            "Deep Space Station\", under the heading \"Spacecrafts in operation\"."
        ),
        "source": JAXA_MDSS_MISSIONS,
        "sourceName": "JAXA / ISAS, Misasa Deep Space Station: Spacecrafts",
        "sourceRetrieved": RETRIEVED,
        "note": (
            "JAXA names the orbiter element; the catalogued object is the composite BepiColombo "
            "stack that carries it, which is why the registry name differs from the name JAXA "
            "used. The identification is the publisher's own: the launch date it prints beside "
            "\"MPO\" is BepiColombo's."
        ),
    },
]

#: Pairs of stations closer than the co-location threshold that are genuinely
#: separate antennas rather than one site entered twice. Everything not on this
#: list has to be further apart than ``COLOCATION_KM``, which is what stops the
#: same antenna farm arriving again under a second operator's name.
CO_LOCATED = [
    ["nasa-dsn-madrid-dss63", "nasa-dsn-madrid-dss53",
     "Two antennas of the Madrid Deep Space Communications Complex, 0.5 km apart."],
    ["nasa-dsn-canberra-dss43", "nasa-dsn-canberra-dss34",
     "Two antennas of the Canberra Deep Space Communication Complex."],
    ["jaxa-uchinoura-34m", "jaxa-uchinoura-20m",
     "The 34 m and 20 m antennas of the Uchinoura Space Center, 0.3 km apart."],
    ["jaxa-usuda-64m", "jaxa-misasa-54m",
     "The Usuda 64 m and its Misasa 54 m successor, 1.4 km apart on neighbouring ridges."],
    ["nasa-nsn-wallops-wg1", "noaa-wallops-cda",
     "NASA's Near Space Network antenna and NOAA's command and data acquisition station "
     "are both at Wallops and are published separately by their two operators."],
    ["esa-kiruna-kis", "ssc-esrange-kiruna",
     "ESA's Kiruna station and SSC's Esrange are published separately by their two operators."],
]

COLOCATION_KM = 3.0


def _separation_km(a: dict, b: dict) -> float:
    radius = 6371.0088
    lat1, lat2 = math.radians(a["latitudeDeg"]), math.radians(b["latitudeDeg"])
    delta_lon = math.radians(b["longitudeDeg"] - a["longitudeDeg"])
    inner = (math.sin((lat2 - lat1) / 2) ** 2
             + math.cos(lat1) * math.cos(lat2) * math.sin(delta_lon / 2) ** 2)
    return 2 * radius * math.asin(math.sqrt(inner))


def registry_names() -> dict[int, str]:
    """NORAD id to registry name, from the offline SATCAT mirror.

    Read from the mirror the release pipeline already keeps, never from the
    network: docs/OPEN-WORK.md forbids this tree from touching space-track.org
    or celestrak.org, and a name typed by hand is exactly how 29268 nearly
    shipped as SAPPHIRE when it is KOMPSAT 2.
    """
    mirror = ROOT.parent / "space-teaching-aid" / "runtime" / "spacetrack-mirror" / "satcat-active.json"
    if not mirror.exists():
        mirror = ROOT / "runtime" / "spacetrack-mirror" / "satcat-active.json"
    return {int(row["NORAD_CAT_ID"]): row["SATNAME"] for row in json.loads(mirror.read_text())}


def main() -> None:
    table = json.loads(TABLE.read_text())
    known = {station["id"] for station in table["stations"]}

    added = 0
    for station in STATIONS:
        if station["id"] in known:
            continue
        table["stations"].append(station)
        known.add(station["id"])
        added += 1

    # Co-location guard, applied here as well as in the tests so a bad row
    # cannot even be written.
    declared = {tuple(sorted(pair[:2])) for pair in CO_LOCATED}
    stations = table["stations"]
    for i in range(len(stations)):
        for j in range(i + 1, len(stations)):
            gap = _separation_km(stations[i], stations[j])
            key = tuple(sorted((stations[i]["id"], stations[j]["id"])))
            if gap < COLOCATION_KM and key not in declared:
                raise SystemExit(
                    f"{key[0]} and {key[1]} are {gap:.2f} km apart and not declared co-located. "
                    "Either they are one antenna farm entered twice, or add them to CO_LOCATED "
                    "with the reason."
                )

    registry = registry_names()
    existing_links = {(link["stationId"], link["noradId"], link["relationship"])
                      for link in table["links"]}
    linked = 0
    for link in LINKS:
        key = (link["stationId"], link["noradId"], link["relationship"])
        if key in existing_links:
            continue
        table["links"].append(link)
        existing_links.add(key)
        linked += 1

    # Stamp every link, old and new, with the name its NORAD id resolves to.
    unresolved = []
    for link in table["links"]:
        name = registry.get(link["noradId"])
        if name is None:
            unresolved.append(link["noradId"])
            continue
        link["registryName"] = name
        link["registrySource"] = "space-track.org SATCAT (offline mirror)"
    if unresolved:
        raise SystemExit(
            f"these NORAD ids do not resolve in the offline registry mirror: {sorted(set(unresolved))}. "
            "A link whose object cannot be named is a link that cannot be checked; drop it."
        )

    table["coLocated"] = [
        {"stations": pair[:2], "reason": pair[2]} for pair in CO_LOCATED
    ]
    table["coLocationThresholdKm"] = COLOCATION_KM

    TABLE.write_text(json.dumps(table, indent=2, ensure_ascii=False) + "\n")
    print(f"stations +{added} (now {len(table['stations'])}), "
          f"links +{linked} (now {len(table['links'])}), "
          f"registry names stamped on {len(table['links'])}")


if __name__ == "__main__":
    main()
