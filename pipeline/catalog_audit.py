#!/usr/bin/env python3
"""Deterministic factual-consistency audit of the published satellite catalog.

Why this module exists
----------------------
On 2026-08-07 the detail card for SKYTERRA 1 -- a geostationary L-band
mobile-satellite spacecraft -- told visitors it was "a NASA Earth-observing
mission carrying multiple instruments", owned by NASA, flying in the Telesat
fleet.  Four fields, four wrong answers, presented with no hedging at all.

Nothing in the pipeline could have noticed.  The classifier is a chain of
unanchored substring tests, and ``"TERRA" in "SKYTERRA 1"`` is true.  The
release then shipped whatever the chain produced, because no stage ever asked
whether the resulting claim was consistent with the object's own registry
record or with the orbit it is actually in.

This module is that missing stage.  It is deliberately, entirely
deterministic:

* Every check is computed from the published artifact plus the offline
  space-track and CelesTrak mirrors.  No network, no model, no judgement.
* A language model may only be asked to *triage* -- ``--triage-queue`` writes
  a queue of suspicions to a side file for a reviewer to read.  Its output
  never enters the artifact and never suppresses a deterministic finding.  If
  the endpoint is down the audit is unaffected; see the triage-prompt builder
  at the bottom of this module.
* Findings carry the evidence that produced them, so a reviewer can disagree
  with the rule rather than having to re-derive the fact.

The registries are honest about their own limits and so is this module.
space-track and CelesTrak tell you *who registered an object, when it launched,
and where it is*.  Neither tells you what a spacecraft is **for**, or who
commercially operates it.  Those are exactly the two fields the site got wrong,
so no check here can confirm a mission or an operator.  Every check is a
*contradiction detector*: it can prove a published claim disagrees with
authoritative data, or that a claim rests on no evidence at all.  It can never
prove a claim right.  That asymmetry is the point -- a claim with no supporting
evidence should not be displayed as fact, whether or not it happens to be true.
"""

from __future__ import annotations

import argparse
import ast
import collections
import dataclasses
import datetime as dt
import json
import math
import os
import re
import sys
from pathlib import Path
from typing import Any, Iterable, Sequence

ROOT = Path(__file__).resolve().parents[1]
BUILD_RELEASE_SOURCE = ROOT / "pipeline" / "build_release.py"
OVERRIDES_PATH = ROOT / "data" / "satellite_overrides.json"
SPACETRACK_MIRROR = Path(
    os.environ.get("SPACE_EXPLORER_SPACETRACK_MIRROR", ROOT / "runtime" / "spacetrack-mirror")
)
CELESTRAK_MIRROR = Path(
    os.environ.get("SPACE_EXPLORER_CELESTRAK_MIRROR", ROOT / "runtime" / "celestrak-mirror")
)

EARTH_RADIUS_KM = 6378.137

# ---------------------------------------------------------------------------
# Severity
# ---------------------------------------------------------------------------
# "contradiction" -- authoritative data disagrees with what the site displays,
#                    or the site asserts a specific fact resting on a
#                    coincidental substring.  These are wrong, not uncertain.
# "unsupported"   -- the site asserts something specific that no cached
#                    authoritative source supports.  It may be true; the site
#                    has no basis for saying it.
# "review"        -- plausible but unusual; a human should look.
SEVERITIES = ("contradiction", "unsupported", "review")


@dataclasses.dataclass(frozen=True)
class Finding:
    check: str
    severity: str
    norad_id: int
    name: str
    detail: str
    evidence: dict[str, Any] = dataclasses.field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


# ---------------------------------------------------------------------------
# Name tokenisation -- the heart of the over-match check
# ---------------------------------------------------------------------------
# Spacecraft names are punctuation-separated token strings: "SENTINEL-2A",
# "GOES 16", "TECHDEMOSAT-1 (TDS-1)".  A rule keyed on "TERRA" is meant to
# match the token TERRA, not the letters t-e-r-r-a wherever they land.  The
# whole SKYTERRA class of defect is the difference between those two things,
# so the token boundary is computed here once and reused by every check.
_TOKEN_SPLIT = re.compile(r"[^A-Z0-9]+")


def name_tokens(name: str) -> list[str]:
    """Uppercase alphanumeric tokens of a spacecraft name, in order."""
    return [token for token in _TOKEN_SPLIT.split(name.upper()) if token]


def normalise_fragment(fragment: str) -> list[str]:
    """A rule fragment reduced to the token sequence it is trying to match.

    ``"GPS "``, ``"SES-"`` and ``"SUOMI NPP"`` are all written with the
    punctuation the author used to fake a boundary; that punctuation is exactly
    what this normalisation removes, because the boundary is now enforced
    properly by :func:`fragment_matches_tokens`.
    """
    return [token for token in _TOKEN_SPLIT.split(fragment.upper()) if token]


_SERIES_SUFFIX = re.compile(r"^\d+[A-Z]?$")


def fragment_matches_tokens(fragment: str, tokens: Sequence[str]) -> bool:
    """True when the fragment appears as a whole token (or token run).

    One deliberate relaxation: a programme name followed immediately by its
    series number inside a single token -- ``COSMIC2``, ``FORMOSAT7`` -- is a
    real boundary, because the digits are the flight number and upstream simply
    omitted the separator.  ``SKYTERRA`` is not: ``TERRA`` sits at the *end* of
    the token, and the letters before it are somebody else's brand.  Requiring
    the fragment to start the token is what separates the two.
    """
    wanted = normalise_fragment(fragment)
    if not wanted:
        return False
    span = len(wanted)
    for i in range(len(tokens) - span + 1):
        window = list(tokens[i : i + span])
        if window == wanted:
            return True
        if window[:-1] == wanted[:-1] and window[-1].startswith(wanted[-1]):
            remainder = window[-1][len(wanted[-1]) :]
            if _SERIES_SUFFIX.match(remainder):
                return True
    return False


def fragment_matches_substring(fragment: str, name: str) -> bool:
    """The production rule: unanchored, case-insensitive substring."""
    return fragment.upper() in name.upper()


# ---------------------------------------------------------------------------
# Rule extraction -- read the production rules instead of restating them
# ---------------------------------------------------------------------------
# Restating build_release's pattern tuples here would drift the first time
# someone edits classify().  Parsing them out of the source means the audit
# always tests the rules that actually shipped.  There is a unit test asserting
# this extraction still finds the known rule strings.


def _string_literals(node: ast.AST) -> list[str]:
    return [
        child.value
        for child in ast.walk(node)
        if isinstance(child, ast.Constant) and isinstance(child.value, str)
    ]


def extract_name_rule_fragments(source_path: Path = BUILD_RELEASE_SOURCE) -> dict[str, list[str]]:
    """Every substring fragment the classifier keys a claim on, by origin.

    Returns ``{"classify": [...], "owner_organization": [...],
    "identify_constellation": [...]}``.  These are the strings whose accidental
    mid-word matches produce confidently wrong mission, organisation and fleet
    fields.
    """
    tree = ast.parse(source_path.read_text())

    # Module-level tuples of strings, so a rule written as
    # `contains(upper, WEATHER_TOKENS)` is read as the fragments it names.
    #
    # 2026-08-19: the tokens moved out of `classify_detailed` into named
    # constants so the SatNOGS lane could COUNT how many objects each rule
    # claims. This extractor read only inline tuple literals, so the moment they
    # moved it returned an EMPTY list for `classify` -- and `check_substring_overmatch`
    # went on reporting a clean sweep while examining nothing at all. That is the
    # silent-pass failure this file's own comment says has already happened four
    # times here; the fifth was caught by the one test that names a known
    # fragment, which is why that test is worth more than it looks.
    constants: dict[str, list[str]] = {}
    for node in tree.body:
        declared = (
            node.targets if isinstance(node, ast.Assign)
            else [node.target] if isinstance(node, ast.AnnAssign) else []
        )
        names = [target.id for target in declared if isinstance(target, ast.Name)]
        if names and getattr(node, "value", None) is not None:
            literals = _string_literals(node.value)
            if literals:
                for name in names:
                    constants[name] = literals

    def _fragments_of(argument: ast.AST) -> list[str]:
        if isinstance(argument, ast.Name):
            return list(constants.get(argument.id, []))
        return _string_literals(argument)

    fragments: dict[str, list[str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in {
            "classify",
            "classify_detailed",
            "owner_organization",
        }:
            found: list[str] = []
            for call in ast.walk(node):
                if (
                    isinstance(call, ast.Call)
                    and isinstance(call.func, ast.Name)
                    and call.func.id == "contains"
                    and len(call.args) == 2
                ):
                    found.extend(_fragments_of(call.args[1]))
            fragments[node.name] = sorted(set(found) | set(fragments.get(node.name, ())))
            if node.name == "classify_detailed":
                # classify() is a thin wrapper; the rules live in the detailed
                # form. Report them under the name the audit and its tests use.
                fragments["classify"] = sorted(set(found) | set(fragments.get("classify", ())))
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            # CONSTELLATION_PATTERNS carries a type annotation, so it is an
            # AnnAssign, not an Assign. Handling only Assign silently returned
            # no fleet fragments at all -- a check that looked like it ran and
            # never examined anything, which is the exact defect class this
            # project has already produced four times.
            declared = node.targets if isinstance(node, ast.Assign) else [node.target]
            targets = [t.id for t in declared if isinstance(t, ast.Name)]
            if "CONSTELLATION_PATTERNS" in targets and node.value is not None:
                patterns: list[str] = []
                for element in ast.walk(node.value):
                    if isinstance(element, ast.Tuple) and len(element.elts) == 2:
                        label, pattern_tuple = element.elts
                        if isinstance(label, ast.Constant) and isinstance(pattern_tuple, ast.Tuple):
                            patterns.extend(_string_literals(pattern_tuple))
                fragments["identify_constellation"] = sorted(set(patterns))
    return fragments


def extract_operator_prefixes(source_path: Path = BUILD_RELEASE_SOURCE) -> list[str]:
    """The operator-family prefixes in ``OPERATOR_SECTORS``.

    These attach a sector and an operator, so they are a claim-bearing rule and
    the audit must count them as evidence. Read from the source for the same
    reason as everything else here: a table the audit does not know about is a
    table the audit reports as unsupported.
    """
    tree = ast.parse(source_path.read_text())
    for node in ast.walk(tree):
        declared = (
            node.targets if isinstance(node, ast.Assign)
            else [node.target] if isinstance(node, ast.AnnAssign)
            else []
        )
        if not any(isinstance(t, ast.Name) and t.id == "OPERATOR_SECTORS" for t in declared):
            continue
        prefixes: list[str] = []
        for element in ast.walk(node.value):
            if isinstance(element, ast.Tuple) and element.elts:
                first = element.elts[0]
                if isinstance(first, ast.Constant) and isinstance(first.value, str):
                    prefixes.append(first.value)
        return sorted(set(prefixes))
    return []


def extract_exact_name_rules(source_path: Path = BUILD_RELEASE_SOURCE) -> list[re.Pattern[str]]:
    """The whole-name regexes that classify individually source-cited programmes.

    ``UFO 2``, ``TACSAT-4``, ``ATHENA-FIDUS``, ``ASBM-1`` and the SDA number
    block are classified by exact ``fullmatch`` rules, each documented with a
    government or operator citation in
    ``docs/satellite-catalog-classification.md``. They are the strongest
    evidence in the pipeline and must count as such here, or the audit reports
    its own best-sourced records as unsupported.
    """
    tree = ast.parse(source_path.read_text())
    patterns: list[re.Pattern[str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Call):
            continue
        call = node.value
        func = call.func
        is_compile = (
            isinstance(func, ast.Attribute) and func.attr == "compile"
            and isinstance(func.value, ast.Name) and func.value.id == "re"
        )
        names = [t.id for t in node.targets if isinstance(t, ast.Name)]
        if not is_compile or not any(n.endswith(("_NAME", "_NAMES")) for n in names):
            continue
        literals = _string_literals(call.args[0]) if call.args else []
        for literal in literals:
            try:
                patterns.append(re.compile(literal))
            except re.error:
                continue
    return patterns


def load_override_fragments(path: Path = OVERRIDES_PATH) -> dict[str, dict[str, Any]]:
    """The curated override table, keyed by the substring it matches on.

    Reads the same merged table the release is built from -- base file plus
    every `satellite_overrides_*.json` partition -- so the audit cannot grade a
    release against a smaller rule set than the one that built it. The argument
    is kept, and honoured, because a test points it at a fixture.
    """
    if path != OVERRIDES_PATH:
        return json.loads(path.read_text())
    from pipeline.build_release import load_overrides

    return load_overrides(path.parent)


# ---------------------------------------------------------------------------
# Orbit regime vs mission -- the check that would have caught SKYTERRA 1
# ---------------------------------------------------------------------------
# The rules themselves live in `pipeline/build_release.py`, because the builder
# now *enforces* them: a name-pattern claim that its own orbit contradicts is
# withdrawn at build time rather than published and flagged afterwards. One
# definition, imported rather than restated, so the audit can never grade a
# release against rules the release was not built with.
from pipeline.build_release import REGIME_MISSION_RULES  # noqa: E402


def regime_from_elements(period_minutes: float | None, apogee_km: float | None, perigee_km: float | None,
                         inclination_deg: float | None, eccentricity: float | None) -> str | None:
    """The published classifier's regime rule, recomputed from registry values.

    Mirrors ``build_release.derive_orbit`` so a disagreement means the *inputs*
    disagree, not the definitions.
    """
    if period_minutes is None or apogee_km is None or perigee_km is None:
        return None
    if eccentricity is None:
        semimajor = (apogee_km + perigee_km) / 2 + EARTH_RADIUS_KM
        if semimajor <= 0:
            return None
        eccentricity = (apogee_km - perigee_km) / (2 * semimajor)
    inclination_deg = 0.0 if inclination_deg is None else inclination_deg
    near_geo = 1380 <= period_minutes <= 1500
    if near_geo and eccentricity < 0.15 and inclination_deg < 20:
        return "GEO"
    if near_geo and eccentricity < 0.15 and inclination_deg >= 20:
        return "IGSO"
    if eccentricity >= 0.25 or (apogee_km > 40000 and perigee_km < 30000):
        return "HEO"
    if apogee_km < 2000:
        return "LEO"
    if perigee_km >= 2000 and apogee_km < 35000:
        return "MEO"
    return "OTHER"


# ---------------------------------------------------------------------------
# Fleet / operator expectations
# ---------------------------------------------------------------------------
# A constellation label is an *operator* claim, and operators have registry
# footprints.  Telesat is Canadian; every Telesat spacecraft in the registry is
# registered CA.  A "Telesat" object registered US is either a mislabel or a
# genuinely unusual case worth a human look -- either way the site should not
# assert it silently.  Codes are space-track/CelesTrak OWNER codes.
FLEET_OWNER_CODES: dict[str, frozenset[str]] = {
    "Starlink": frozenset({"US"}),
    "OneWeb": frozenset({"UK", "US"}),
    "Telesat": frozenset({"CA"}),
    "Intelsat": frozenset({"ITSO", "US", "UK", "LUXE"}),
    "Eutelsat": frozenset({"EUTE", "FR", "UK"}),
    "SES": frozenset({"SES", "LUXE", "O3B"}),
    "O3b / mPOWER": frozenset({"O3B", "SES", "LUXE"}),
    "Inmarsat": frozenset({"IM", "UK"}),
    "Iridium": frozenset({"IRID", "US"}),
    "Globalstar": frozenset({"GLOB", "US"}),
    "Orbcomm": frozenset({"US"}),
    "GPS": frozenset({"US"}),
    "Galileo": frozenset({"ESA", "EU", "EUTE", "FR", "IT", "GER"}),
    "GLONASS": frozenset({"CIS"}),
    "BeiDou": frozenset({"PRC"}),
    "QZSS": frozenset({"JPN"}),
    "NavIC": frozenset({"IND", "ISRO"}),
    "GOES": frozenset({"US"}),
    "JPSS": frozenset({"US"}),
    "DMSP": frozenset({"US"}),
    "Metop": frozenset({"EUME", "ESA"}),
    "Meteosat": frozenset({"EUME", "ESA"}),
    "Himawari": frozenset({"JPN"}),
    "Fengyun": frozenset({"PRC"}),
    "Yaogan": frozenset({"PRC"}),
    "Sentinel": frozenset({"ESA", "EU", "EUME", "FR", "IT", "GER", "UK", "SPN"}),
    "Swarm": frozenset({"ESA"}),
    "WGS": frozenset({"US"}),
    "MUOS": frozenset({"US"}),
    "AEHF": frozenset({"US"}),
    "SBIRS": frozenset({"US"}),
    "PWSA Transport Layer": frozenset({"US"}),
    "SkySat": frozenset({"US"}),
    "Spire": frozenset({"US"}),
    "Flock / PlanetScope": frozenset({"US"}),
    "ICEYE": frozenset({"FIN", "US"}),
    "Capella": frozenset({"US"}),
    "Project Kuiper": frozenset({"US"}),
    "Qianfan": frozenset({"PRC"}),
    "Guowang": frozenset({"PRC"}),
}

# Organisation strings the pipeline can attach, and the registry owner codes
# under which that attribution is even possible.  NASA does not register
# spacecraft under PRC; EUMETSAT does not register under US.
ORG_OWNER_CODES: dict[str, frozenset[str]] = {
    "NASA": frozenset({"US", "ISS"}),
    "NOAA / NASA": frozenset({"US"}),
    "NOAA": frozenset({"US"}),
    "USGS / NASA": frozenset({"US"}),
    "NASA / ESA": frozenset({"US", "ESA"}),
    "EUMETSAT": frozenset({"EUME", "ESA"}),
    "ESA / European Union": frozenset({"ESA", "EU", "FR", "IT", "GER", "UK", "SPN", "EUME"}),
    "European Union / ESA": frozenset({"ESA", "EU", "FR", "IT", "GER", "UK", "SPN", "EUME"}),
    "JAXA": frozenset({"JPN"}),
    "Japan Meteorological Agency": frozenset({"JPN"}),
    "SpaceX": frozenset({"US"}),
    "Eutelsat OneWeb": frozenset({"UK", "US", "EUTE"}),
    "U.S. Space Force": frozenset({"US"}),
    "U.S. Navy": frozenset({"US"}),
    "U.S. Navy / Naval Research Laboratory": frozenset({"US"}),
    "Space Development Agency": frozenset({"US"}),
    "Space Norway": frozenset({"NOR"}),
    "International Space Station partners": frozenset({"ISS", "US", "CIS", "JPN", "ESA", "CA"}),
}

# Specific assertions a description can make, and the token evidence that would
# justify making them about this particular object.  A description that names
# NASA about an object whose name, owner and category groups contain nothing
# NASA-ish is asserting a fact the site cannot source.
DESCRIPTION_CLAIMS: tuple[tuple[str, str, tuple[str, ...], frozenset[str]], ...] = (
    # (regex, human label, name tokens that would justify it, owner codes)
    (r"\bNASA\b", "NASA", ("TERRA", "AQUA", "HST", "HUBBLE", "TESS", "FERMI", "SMAP",
                           "CYGNSS", "LANDSAT", "ICESAT", "CALIPSO", "CLOUDSAT",
                           "SUOMI", "NPP", "GRACE", "SWIFT", "NUSTAR", "CHANDRA"),
     frozenset({"US"})),
    (r"\bNOAA\b", "NOAA", ("NOAA", "GOES", "JPSS", "SUOMI", "NPP", "DSCOVR"), frozenset({"US"})),
    (r"\bEUMETSAT\b", "EUMETSAT", ("METOP", "METEOSAT", "MSG", "MTG"), frozenset({"EUME", "ESA"})),
    (r"\bCopernicus\b", "Copernicus", ("SENTINEL",),
     frozenset({"ESA", "EU", "EUME", "FR", "IT", "GER", "UK", "SPN"})),
    (r"\bHubble Space Telescope\b", "Hubble", ("HST", "HUBBLE"), frozenset({"US"})),
    (r"\bStarlink\b", "Starlink", ("STARLINK",), frozenset({"US"})),
    (r"\bOneWeb\b", "OneWeb", ("ONEWEB",), frozenset({"UK", "US"})),
    (r"\bIridium\b", "Iridium", ("IRIDIUM",), frozenset({"IRID", "US"})),
    (r"\bGlobal Positioning System\b", "GPS", ("GPS", "NAVSTAR"), frozenset({"US"})),
    (r"\bGalileo\b", "Galileo", ("GALILEO", "GSAT"), frozenset({"ESA", "EU", "FR", "IT", "GER"})),
    (r"\bGLONASS\b", "GLONASS", ("GLONASS", "COSMOS"), frozenset({"CIS"})),
    (r"\bBeiDou\b", "BeiDou", ("BEIDOU",), frozenset({"PRC"})),
    (r"\bWideband Global SATCOM\b", "WGS", ("WGS",), frozenset({"US"})),
    (r"\bSpace Development Agency\b", "SDA", ("SDA", "PRAETORIAN"), frozenset({"US"})),
    (r"\bInternational Space Station\b", "ISS", ("ISS", "ZARYA"),
     frozenset({"ISS", "CIS", "US"})),
)

# Phrases that assert instrument-level or programme-level specifics.  Used for
# ranking boilerplate: a generic sentence repeated 4,000 times is honest; a
# sentence naming an agency and its instruments repeated across unrelated
# objects is the SKYTERRA failure at scale.
SPECIFICITY_MARKERS: tuple[str, ...] = (
    "carrying multiple instruments",
    "carrying sensors",
    "multiple instruments",
    "energy balance",
    "ultraviolet, visible",
    "water cycle",
    "land cover",
    "cross-linked",
    "inter-satellite",
    "optical inter-satellite links",
)

# The sentence build_release emits when it genuinely knows nothing.  It is the
# one description that is allowed to be shared by thousands of objects.
HONEST_UNKNOWN_PREFIX = "The public catalog does not provide a verified mission description"
TEMPLATE_HEDGE = "Its specific purpose should be confirmed against an owning-organization mission page."


# ---------------------------------------------------------------------------
# Registry loading
# ---------------------------------------------------------------------------


def _to_float(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(result) else result


def _date_gap_days(left: str, right: str) -> int | None:
    try:
        a = dt.date.fromisoformat(left[:10])
        b = dt.date.fromisoformat(right[:10])
    except ValueError:
        return None
    return abs((a - b).days)


def _to_int(value: Any) -> int | None:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


@dataclasses.dataclass
class Registry:
    """Everything the offline mirrors know, indexed by NORAD catalog ID."""

    spacetrack_satcat: dict[int, dict[str, Any]] = dataclasses.field(default_factory=dict)
    celestrak_satcat: dict[int, dict[str, Any]] = dataclasses.field(default_factory=dict)
    celestrak_groups: dict[str, set[int]] = dataclasses.field(default_factory=dict)
    cached_group_names: tuple[str, ...] = ()

    def owner_codes(self, norad_id: int) -> dict[str, str]:
        """Registry owner attribution from each source that has this object."""
        codes: dict[str, str] = {}
        st = self.spacetrack_satcat.get(norad_id)
        if st and st.get("COUNTRY"):
            codes["spacetrack"] = str(st["COUNTRY"]).strip()
        ct = self.celestrak_satcat.get(norad_id)
        if ct and ct.get("OWNER"):
            codes["celestrak"] = str(ct["OWNER"]).strip()
        return codes

    def groups_for(self, norad_id: int) -> set[str]:
        return {name for name, ids in self.celestrak_groups.items() if norad_id in ids}


def load_registry(
    spacetrack_dir: Path = SPACETRACK_MIRROR, celestrak_dir: Path = CELESTRAK_MIRROR
) -> Registry:
    registry = Registry()

    st_path = spacetrack_dir / "satcat-active.json"
    if st_path.exists():
        for row in json.loads(st_path.read_text()):
            norad = _to_int(row.get("NORAD_CAT_ID") or row.get("OBJECT_NUMBER"))
            if norad is not None:
                registry.spacetrack_satcat[norad] = row

    ct_path = celestrak_dir / "satcat-active.json"
    if ct_path.exists():
        for row in json.loads(ct_path.read_text()):
            norad = _to_int(row.get("NORAD_CAT_ID"))
            if norad is not None:
                registry.celestrak_satcat[norad] = row

    names: list[str] = []
    for path in sorted(celestrak_dir.glob("group-*.json")):
        group = path.stem[len("group-") :]
        names.append(group)
        ids: set[int] = set()
        try:
            rows = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        for row in rows if isinstance(rows, list) else []:
            norad = _to_int(row.get("NORAD_CAT_ID"))
            if norad is not None:
                ids.add(norad)
        registry.celestrak_groups[group] = ids
    registry.cached_group_names = tuple(names)
    return registry


def load_catalog(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text())
    if not isinstance(data, dict) or "satellites" not in data:
        raise ValueError(f"{path} is not a published catalog artifact")
    return data


def resolve_catalog_path(explicit: Path | None) -> Path:
    """Find the catalog the site is actually serving."""
    if explicit is not None:
        return explicit
    # public/data is what the running site serves; dist/data is the last built
    # tree; runtime/data is a historical staging copy. Newest wins.
    for manifest_path in (
        ROOT / "public" / "data" / "manifest.json",
        ROOT / "dist" / "data" / "manifest.json",
        ROOT / "runtime" / "data" / "manifest.json",
    ):
        if not manifest_path.exists():
            continue
        manifest = json.loads(manifest_path.read_text())
        entry = manifest.get("catalog")
        if not entry:
            continue
        candidate = manifest_path.parent / entry["path"]
        if candidate.exists():
            return candidate
    raise FileNotFoundError("no published catalog artifact found; pass --catalog")


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------


def check_owner_disagreement(records: list[dict[str, Any]], registry: Registry) -> list[Finding]:
    """Published registry attribution vs both mirrors."""
    findings: list[Finding] = []
    for record in records:
        norad = record["id"]
        published = str(record.get("ownerCode") or "").strip()
        codes = registry.owner_codes(norad)
        disagreeing = {source: code for source, code in codes.items() if code and code != published}
        if not disagreeing:
            continue
        # The two registries genuinely attribute some objects differently --
        # AMAZONAS 2 is BRAZ to space-track and SPN to CelesTrak, because one
        # records the launching state and the other the operator's home. When
        # the site agrees with one of them it has not made an error; it has
        # silently picked a side, which the visitor cannot see. That is a
        # review item. Disagreeing with *every* source is a real defect.
        agrees_with_someone = any(code == published for code in codes.values())
        findings.append(
            Finding(
                check="owner-disagreement",
                severity="review" if agrees_with_someone else "contradiction",
                norad_id=norad,
                name=record["name"],
                detail=f"published ownerCode {published!r} disagrees with registry: "
                + ", ".join(f"{k}={v!r}" for k, v in sorted(disagreeing.items()))
                + ("; the site silently picked one registry's attribution" if agrees_with_someone else ""),
                evidence={"published": published, **codes},
            )
        )
    return findings


def check_identity_disagreement(records: list[dict[str, Any]], registry: Registry) -> list[Finding]:
    """Name, international designator and launch date vs both mirrors."""
    findings: list[Finding] = []
    for record in records:
        norad = record["id"]
        st = registry.spacetrack_satcat.get(norad, {})
        ct = registry.celestrak_satcat.get(norad, {})

        published_cospar = str(record.get("cosparId") or "").strip()
        for source, row, key in (("spacetrack", st, "OBJECT_ID"), ("celestrak", ct, "OBJECT_ID")):
            value = str(row.get(key) or "").strip()
            if published_cospar and value and value != published_cospar:
                findings.append(
                    Finding(
                        check="cospar-disagreement",
                        severity="contradiction",
                        norad_id=norad,
                        name=record["name"],
                        detail=f"published cosparId {published_cospar!r} != {source} {value!r}",
                        evidence={"published": published_cospar, source: value},
                    )
                )

        published_launch = str(record.get("launchDate") or "").strip()
        for source, row, key in (("spacetrack", st, "LAUNCH"), ("celestrak", ct, "LAUNCH_DATE")):
            value = str(row.get(key) or "").strip()[:10]
            if not published_launch or not value or value == published_launch:
                continue
            # A one-day gap is the launch-site local date against UTC, which is
            # a convention difference, not an error. Anything wider is a real
            # disagreement about when the thing flew.
            gap = _date_gap_days(published_launch, value)
            findings.append(
                Finding(
                    check="launch-date-disagreement",
                    severity="review" if gap is not None and gap <= 1 else "contradiction",
                    norad_id=norad,
                    name=record["name"],
                    detail=f"published launchDate {published_launch!r} != {source} {value!r}"
                    + (" (one day; local-date vs UTC convention)" if gap == 1 else ""),
                    evidence={"published": published_launch, source: value, "gapDays": gap},
                )
            )

        # Upstream names differ constantly in ways that carry no information --
        # "CALSPHERE 4(A)" vs "CALSPHERE 4A", "OSCAR 7" vs "OSCAR 7 (AO-7)".
        # Comparing raw strings produced 1,439 findings that all said the same
        # empty thing. What matters for identity is the token multiset, which
        # is punctuation- and order-insensitive; only a genuine token
        # difference means the two registries think this is a different object.
        published_tokens = set(name_tokens(record["name"]))
        for source, row, key in (("spacetrack", st, "OBJECT_NAME"), ("celestrak", ct, "OBJECT_NAME")):
            value = str(row.get(key) or "").strip()
            if not value or not published_tokens:
                continue
            registry_tokens = set(name_tokens(value))
            if published_tokens & registry_tokens:
                continue
            findings.append(
                Finding(
                    check="name-disagreement",
                    severity="review",
                    norad_id=norad,
                    name=record["name"],
                    detail=f"published name shares no token with {source} name {value!r}",
                    evidence={"published": record["name"], source: value},
                )
            )
    return findings


def check_orbit_disagreement(records: list[dict[str, Any]], registry: Registry) -> list[Finding]:
    """Regime derived from published elements vs regime derived from SATCAT.

    Both sides use ``derive_orbit``'s thresholds, so a disagreement is a data
    disagreement, not a definitional one.
    """
    findings: list[Finding] = []
    for record in records:
        norad = record["id"]
        row = registry.celestrak_satcat.get(norad) or registry.spacetrack_satcat.get(norad)
        if not row:
            continue
        regime = regime_from_elements(
            _to_float(row.get("PERIOD")),
            _to_float(row.get("APOGEE")),
            _to_float(row.get("PERIGEE")),
            _to_float(row.get("INCLINATION")),
            None,
        )
        if regime is None or regime == record.get("orbit"):
            continue
        # SATCAT rounds to whole km and 0.01 min; only report a disagreement
        # that is not explainable by that rounding.
        period = _to_float(row.get("PERIOD"))
        published_period = _to_float(record.get("periodMinutes"))
        if period is not None and published_period is not None and abs(period - published_period) > 1.0:
            findings.append(
                Finding(
                    check="orbit-disagreement",
                    severity="review",
                    norad_id=norad,
                    name=record["name"],
                    detail=f"published orbit {record.get('orbit')!r} (period {published_period}) vs "
                    f"registry-derived {regime!r} (period {period})",
                    evidence={"publishedOrbit": record.get("orbit"), "registryOrbit": regime},
                )
            )
    return findings


def check_regime_mission(records: list[dict[str, Any]], registry: Registry) -> list[Finding]:
    """An object's orbit contradicting the mission the site claims for it.

    The release now *publishes* the strong cases as a `contestedAttribution`
    annotation the visitor can read. So the finding this check reports is no
    longer "the orbit disagrees" -- it is **"the orbit disagrees and the card
    does not say so"**. An object that already carries the annotation is not a
    finding; the audit and the site are showing the same thing, which was the
    point. The weaker rules, which are deliberately kept off the card, still
    surface here as a review queue.
    """
    findings: list[Finding] = []
    lookup = {
        (orbit, mission): (severity, annotate, why)
        for orbit, mission, severity, annotate, _strength, why in REGIME_MISSION_RULES
    }
    for record in records:
        rule = lookup.get((record.get("orbit"), record.get("mission")))
        if rule is None:
            continue
        severity, annotate, why = rule
        published = [
            note for note in (record.get("contestedAttribution") or [])
            if isinstance(note, dict) and note.get("kind") == "orbit-inconsistent"
        ]
        if annotate and published:
            continue
        if annotate:
            severity = "contradiction"
            why = "The release should carry an orbit-inconsistent annotation for this object and does not. " + why
        findings.append(
            Finding(
                check="regime-mission-contradiction",
                severity=severity,
                norad_id=record["id"],
                name=record["name"],
                detail=f"{record['orbit']} orbit (period {record.get('periodMinutes')} min, "
                f"inclination {record.get('omm', {}).get('INCLINATION')}deg) described as "
                f"mission={record['mission']!r}. {why}",
                evidence={
                    "orbit": record.get("orbit"),
                    "mission": record.get("mission"),
                    "periodMinutes": record.get("periodMinutes"),
                    "purpose": record.get("purpose"),
                },
            )
        )
    return findings


def check_fleet_overmatch(records: list[dict[str, Any]], registry: Registry) -> list[Finding]:
    """A named constellation whose registry owner is inconsistent with that operator."""
    findings: list[Finding] = []
    for record in records:
        fleet = record.get("constellation")
        if not fleet:
            continue
        allowed = FLEET_OWNER_CODES.get(fleet)
        if allowed is None:
            continue
        codes = registry.owner_codes(record["id"])
        observed = {code for code in codes.values() if code}
        if not observed:
            observed = {str(record.get("ownerCode") or "").strip()}
        if observed & allowed:
            continue
        name_supports = fragment_matches_tokens(fleet.split(" / ")[0], name_tokens(record["name"]))
        findings.append(
            Finding(
                check="fleet-overmatch",
                severity="unsupported" if name_supports else "contradiction",
                norad_id=record["id"],
                name=record["name"],
                detail=f"assigned to fleet {fleet!r} (operators registered {sorted(allowed)}) but this "
                f"object is registered {sorted(observed)}"
                + ("" if name_supports else "; the spacecraft name carries no token supporting that fleet"),
                evidence={
                    "constellation": fleet,
                    "registryOwners": sorted(observed),
                    "expectedOwners": sorted(allowed),
                    "sourceGroups": record.get("sourceGroups"),
                },
            )
        )
    return findings


def check_substring_overmatch(
    records: list[dict[str, Any]],
    registry: Registry,
    rule_fragments: dict[str, list[str]] | None = None,
    overrides: dict[str, Any] | None = None,
) -> list[Finding]:
    """A published claim resting on a fragment that matched inside a word.

    This is the SKYTERRA 1 defect stated exactly: the pipeline decides what a
    spacecraft is by asking ``fragment in name``, so ``"TERRA" in "SKYTERRA 1"``
    makes an L-band mobile-communications satellite a NASA Earth-observing
    mission.  Every rule that fired without a token boundary is reported, with
    the field it corrupted.
    """
    rule_fragments = rule_fragments if rule_fragments is not None else extract_name_rule_fragments()
    overrides = overrides if overrides is not None else load_override_fragments()
    exact_rules = extract_exact_name_rules()
    findings: list[Finding] = []

    sources: list[tuple[str, Iterable[str], str]] = [
        ("classify", rule_fragments.get("classify", []), "mission/sector"),
        ("owner_organization", rule_fragments.get("owner_organization", []), "organization"),
        ("identify_constellation", rule_fragments.get("identify_constellation", []), "constellation"),
        ("satellite_overrides.json", list(overrides), "purpose/organization/mission"),
        ("OPERATOR_SECTORS", extract_operator_prefixes(), "sector/operator"),
    ]

    for record in records:
        name = record["name"]
        tokens = name_tokens(name)

        # Does this record claim anything specific at all? A record that says
        # "mission unclassified" and shows the registry owner is making no
        # claim that can rest on a bad match.
        claims_mission = record.get("mission") not in (None, "", "other")
        claims_fleet = bool(record.get("constellation"))
        claims_operator = bool(record.get("organization")) and record.get("organization") not in (
            record.get("ownerLabel"),
            record.get("ownerCode"),
        )
        # CelesTrak category membership is real evidence -- for the claim it
        # actually supports. Being in the `telesat` group says something about
        # which fleet an object flies in; it says nothing about whether the
        # spacecraft is a NASA Earth-science mission. Treating group membership
        # as blanket cover is how SKYTERRA 1 would slip past this check while
        # still displaying "NASA" and "Earth observation".
        if record.get("sourceGroups"):
            claims_fleet = False
        if not (claims_mission or claims_fleet or claims_operator):
            continue

        # A build that records how it decided is taken at its word for the two
        # strongest mechanisms. Older artifacts have no such field, so the
        # exact-name regexes are re-checked directly below and the audit still
        # works on them.
        if record.get("classificationBasis") in {"norad-id", "exact-name", "source-group"}:
            continue
        if any(pattern.fullmatch(name.upper()) for pattern in exact_rules):
            continue

        # Evidence that could legitimately support it: a rule fragment matching
        # a whole token of this spacecraft's own name, or CelesTrak having put
        # this object in one of its own category groups.
        supporting = [
            fragment
            for _origin, fragments, _field in sources
            for fragment in fragments
            if fragment_matches_tokens(fragment, tokens)
        ]
        if supporting:
            continue
        # A group-derived mission is source-backed by CelesTrak's own curation.
        if record.get("sourceGroups") and not (claims_mission or claims_operator):
            continue

        # Nothing supports it. Say where it most likely came from.
        offenders = [
            (origin, fragment, field)
            for origin, fragments, field in sources
            for fragment in fragments
            if fragment_matches_substring(fragment, name) and not fragment_matches_tokens(fragment, tokens)
        ]
        if offenders:
            detail = "; ".join(
                f"the only trace of this claim is {origin} fragment {fragment!r} matching inside a "
                f"word, which is what sets {field}"
                for origin, fragment, field in offenders
            )
            severity = "contradiction"
        else:
            detail = (
                "asserts a mission, fleet or operator with no supporting evidence: no rule fragment "
                "matches a token of this name and the object is in no cached CelesTrak category group"
            )
            severity = "unsupported"
        findings.append(
            Finding(
                check="substring-overmatch",
                severity=severity,
                norad_id=record["id"],
                name=name,
                detail=detail,
                evidence={
                    "tokens": tokens,
                    "fragments": [fragment for _, fragment, _ in offenders],
                    "mission": record.get("mission"),
                    "organization": record.get("organization"),
                    "constellation": record.get("constellation"),
                    "purpose": record.get("purpose"),
                },
            )
        )
    return findings


def describe_specificity(text: str) -> list[str]:
    """The specific claims a description makes, if any."""
    claims: list[str] = []
    for pattern, label, _tokens, _owners in DESCRIPTION_CLAIMS:
        if re.search(pattern, text):
            claims.append(label)
    claims.extend(marker for marker in SPECIFICITY_MARKERS if marker in text.lower())
    return claims


# A description that carries a source URL is answerable to that URL, and the
# registry is not the arbiter of it. FORMOSAT-7/COSMIC-2 is a joint Taiwan-US
# programme, so its description correctly names NOAA while the registry records
# only ROC/TWN; TDRS is a NASA relay programme whose spacecraft names contain no
# NASA token. Both are right, and both look unsupported to a registry-only test.
#
# This is a deliberate narrowing of what these two checks police: they hunt
# *unsourced* specificity. A cited claim that is nonetheless wrong is a review
# problem for a human, which is what `boilerplate_ranking()` exists to make
# readable -- every distinct description with its claims, in one list.
def _claim_is_cited(record: dict[str, Any]) -> bool:
    return str(record.get("purposeSource") or "").startswith("http")


def check_shared_specific_description(records: list[dict[str, Any]], registry: Registry) -> list[Finding]:
    """Identical description text asserting specifics across distinct objects.

    A generic hedged sentence shared by four thousand objects is honest.  The
    same sentence naming an agency and its instruments, attached to objects with
    different owners and different orbits, is the failure mode: it reads as a
    fact about *this* spacecraft while being a fact about a template.
    """
    by_text: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for record in records:
        by_text[str(record.get("purpose") or "")].append(record)

    findings: list[Finding] = []
    for text, group in by_text.items():
        if len(group) < 2 or text.startswith(HONEST_UNKNOWN_PREFIX):
            continue
        claims = describe_specificity(text)
        if not claims:
            continue
        owners = sorted({str(r.get("ownerCode") or "") for r in group})
        orbits = sorted({str(r.get("orbit") or "") for r in group})
        # Four thousand Starlink spacecraft sharing one Starlink sentence is
        # not a defect: every one of them is named STARLINK and registered US,
        # so the shared sentence is supported for each member individually.
        # The defect is a member of the group for which the shared claim has
        # no evidence -- one SKYTERRA 1 sitting inside the TERRA template.
        for record in group:
            if _claim_is_cited(record):
                continue
            tokens = set(name_tokens(record["name"]))
            codes = {code for code in registry.owner_codes(record["id"]).values() if code}
            codes |= {str(record.get("ownerCode") or "").strip()}
            unsupported = [
                label
                for pattern, label, justifying, owner_codes in DESCRIPTION_CLAIMS
                if re.search(pattern, text) and not (tokens & set(justifying)) and label in claims
            ]
            if not unsupported:
                continue
            wrong_country = any(
                not (codes & owner_codes)
                for pattern, label, _justifying, owner_codes in DESCRIPTION_CLAIMS
                if label in unsupported
            )
            findings.append(
                Finding(
                    check="shared-specific-description",
                    severity="contradiction" if wrong_country else "unsupported",
                    norad_id=record["id"],
                    name=record["name"],
                    detail=f"carries a description asserting {unsupported}, shared verbatim by "
                    f"{len(group)} distinct objects spanning owners {owners} and orbits {orbits}, "
                    f"with nothing in this object's own name to support it",
                    evidence={
                        "sharedBy": len(group),
                        "claims": claims,
                        "unsupportedClaims": unsupported,
                        "owners": owners,
                        "orbits": orbits,
                        "purpose": text,
                    },
                )
            )
    return findings


def check_unsupported_specificity(records: list[dict[str, Any]], registry: Registry) -> list[Finding]:
    """A named organisation or programme with no registry evidence for it.

    Two independent tests, both computable offline:

    * the ``organization`` field names a body that does not register spacecraft
      under this object's registry owner code; and
    * the description names a programme or agency and the object's own name
      carries no token from that programme, its owner code is wrong for it, and
      no cached CelesTrak category group backs it up.
    """
    findings: list[Finding] = []
    for record in records:
        norad = record["id"]
        codes = {code for code in registry.owner_codes(norad).values() if code}
        if not codes:
            codes = {str(record.get("ownerCode") or "").strip()}
        tokens = set(name_tokens(record["name"]))

        organisation = str(record.get("organization") or "")
        expected = ORG_OWNER_CODES.get(organisation)
        if expected is not None and not (codes & expected):
            findings.append(
                Finding(
                    check="unsupported-organization",
                    severity="contradiction",
                    norad_id=norad,
                    name=record["name"],
                    detail=f"OWNER / OPERATOR displayed as {organisation!r}, which registers spacecraft "
                    f"under {sorted(expected)}; this object is registered {sorted(codes)}",
                    evidence={"organization": organisation, "registryOwners": sorted(codes)},
                )
            )

        purpose = "" if _claim_is_cited(record) else str(record.get("purpose") or "")
        for pattern, label, justifying_tokens, owner_codes in DESCRIPTION_CLAIMS:
            if not re.search(pattern, purpose):
                continue
            if tokens & set(justifying_tokens):
                continue
            if codes & owner_codes:
                # Right country, wrong or absent programme evidence.  Cannot
                # call it a contradiction; it is still an unsourced specific.
                severity = "unsupported"
                reason = "no token in the spacecraft name supports it"
            else:
                severity = "contradiction"
                reason = f"and this object is registered {sorted(codes)}, not {sorted(owner_codes)}"
            findings.append(
                Finding(
                    check="unsupported-specificity",
                    severity=severity,
                    norad_id=norad,
                    name=record["name"],
                    detail=f"description names {label!r} but {reason}",
                    evidence={"claim": label, "registryOwners": sorted(codes), "purpose": purpose},
                )
            )
    return findings


CHECKS = (
    check_owner_disagreement,
    check_identity_disagreement,
    check_orbit_disagreement,
    check_regime_mission,
    check_fleet_overmatch,
    check_substring_overmatch,
    check_shared_specific_description,
    check_unsupported_specificity,
)


def run_audit(catalog: dict[str, Any], registry: Registry) -> list[Finding]:
    records = catalog["satellites"]
    findings: list[Finding] = []
    for check in CHECKS:
        findings.extend(check(records, registry))
    return findings


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def summarise(findings: Sequence[Finding], catalog: dict[str, Any]) -> dict[str, Any]:
    records = catalog["satellites"]
    by_check: dict[str, int] = collections.Counter(f.check for f in findings)
    by_severity: dict[str, int] = collections.Counter(f.severity for f in findings)
    objects_by_severity = {
        severity: len({f.norad_id for f in findings if f.severity == severity}) for severity in SEVERITIES
    }
    affected = {f.norad_id for f in findings}
    contradicted = {f.norad_id for f in findings if f.severity == "contradiction"}
    return {
        "catalogObjects": len(records),
        "totalAvailable": catalog.get("totalAvailable"),
        "taxonomyVersion": catalog.get("taxonomyVersion"),
        "upstreamAsOf": catalog.get("upstreamAsOf"),
        "findings": len(findings),
        "byCheck": dict(sorted(by_check.items())),
        "bySeverity": dict(by_severity),
        "objectsWithAnyFinding": len(affected),
        "objectsBySeverity": objects_by_severity,
        "objectsContradicted": len(contradicted),
        "contradictionRate": round(len(contradicted) / len(records), 5) if records else 0.0,
    }


def worst_offenders(findings: Sequence[Finding], limit: int = 40) -> list[dict[str, Any]]:
    """Objects ranked by how many independent checks contradict them."""
    weight = {"contradiction": 3, "unsupported": 2, "review": 1}
    scores: dict[int, dict[str, Any]] = {}
    for finding in findings:
        entry = scores.setdefault(
            finding.norad_id,
            {"noradId": finding.norad_id, "name": finding.name, "score": 0, "checks": []},
        )
        entry["score"] += weight[finding.severity]
        if finding.check not in entry["checks"]:
            entry["checks"].append(finding.check)
    ranked = sorted(scores.values(), key=lambda e: (-e["score"], e["noradId"]))
    return ranked[:limit]


def boilerplate_ranking(catalog: dict[str, Any], limit: int = 25) -> list[dict[str, Any]]:
    """Every description string, by how many distinct objects carry it."""
    by_text: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for record in catalog["satellites"]:
        by_text[str(record.get("purpose") or "")].append(record)
    rows = []
    for text, group in by_text.items():
        rows.append(
            {
                "count": len(group),
                "claims": describe_specificity(text),
                "honestUnknown": text.startswith(HONEST_UNKNOWN_PREFIX),
                "hedged": TEMPLATE_HEDGE in text,
                "distinctOwners": len({r.get("ownerCode") for r in group}),
                "distinctOrbits": len({r.get("orbit") for r in group}),
                "text": text,
            }
        )
    rows.sort(key=lambda r: (-(len(r["claims"]) > 0 and not r["hedged"]), -r["count"]))
    return rows[:limit]


# ---------------------------------------------------------------------------
# Optional model triage -- suspicions only, never corrections
# ---------------------------------------------------------------------------


def model_triage_prompts(findings: Sequence[Finding], catalog: dict[str, Any], limit: int = 200) -> list[dict[str, Any]]:
    """Build a review queue a model *could* be asked to comment on.

    Deliberately returns data, not model output.  The deterministic audit above
    already decided what is wrong; a model can only add a human-readable
    suspicion for a reviewer.  If the local endpoint is down -- it was, for the
    whole of the sweep this module was written for -- nothing here changes, and
    no caller may treat an empty triage as an all-clear.
    """
    by_id = {record["id"]: record for record in catalog["satellites"]}
    queue: list[dict[str, Any]] = []
    seen: set[int] = set()
    for finding in findings:
        if finding.severity != "contradiction" or finding.norad_id in seen:
            continue
        seen.add(finding.norad_id)
        record = by_id.get(finding.norad_id, {})
        queue.append(
            {
                "noradId": finding.norad_id,
                "name": finding.name,
                "displayed": {
                    "mission": record.get("mission"),
                    "organization": record.get("organization"),
                    "constellation": record.get("constellation"),
                    "purpose": record.get("purpose"),
                },
                "registry": {
                    "ownerCode": record.get("ownerCode"),
                    "orbit": record.get("orbit"),
                    "periodMinutes": record.get("periodMinutes"),
                    "launchDate": record.get("launchDate"),
                    "sourceGroups": record.get("sourceGroups"),
                },
                "deterministicFinding": finding.detail,
            }
        )
        if len(queue) >= limit:
            break
    return queue


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def render_markdown(summary: dict[str, Any], findings: Sequence[Finding], catalog: dict[str, Any],
                    registry: Registry) -> str:
    lines: list[str] = []
    lines.append("# Catalog accuracy audit")
    lines.append("")
    lines.append(f"- catalog objects: {summary['catalogObjects']:,} of {summary['totalAvailable']:,} available")
    lines.append(f"- taxonomy version: {summary['taxonomyVersion']}")
    lines.append(f"- cached CelesTrak category groups: {len(registry.cached_group_names)} "
                 f"({', '.join(registry.cached_group_names) or 'none'})")
    lines.append(f"- objects with at least one finding: {summary['objectsWithAnyFinding']:,}")
    lines.append(f"- objects with a contradiction: {summary['objectsContradicted']:,} "
                 f"({summary['contradictionRate'] * 100:.2f}%)")
    lines.append("")
    lines.append("## Findings by check")
    lines.append("")
    lines.append("| check | findings |")
    lines.append("|---|---:|")
    for check, count in summary["byCheck"].items():
        lines.append(f"| `{check}` | {count:,} |")
    lines.append("")
    lines.append("## Worst offenders")
    lines.append("")
    lines.append("| NORAD | name | score | checks |")
    lines.append("|---:|---|---:|---|")
    for entry in worst_offenders(findings):
        lines.append(f"| {entry['noradId']} | {entry['name']} | {entry['score']} | "
                     f"{', '.join(entry['checks'])} |")
    lines.append("")
    lines.append("## Description reuse")
    lines.append("")
    lines.append("| objects | owners | orbits | specific claims | text |")
    lines.append("|---:|---:|---:|---|---|")
    for row in boilerplate_ranking(catalog):
        lines.append(
            f"| {row['count']:,} | {row['distinctOwners']} | {row['distinctOrbits']} | "
            f"{', '.join(row['claims']) or '-'} | {row['text'][:90]}... |"
        )
    return "\n".join(lines) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=None, help="published catalog artifact")
    parser.add_argument("--json", dest="json_out", type=Path, default=None, help="write findings as JSON")
    parser.add_argument("--markdown", type=Path, default=None, help="write a Markdown report")
    parser.add_argument("--triage-queue", type=Path, default=None,
                        help="write the model-triage review queue (data only; no model is called)")
    parser.add_argument("--check", action="append", default=None, help="restrict to named checks")
    parser.add_argument("--fail-on-contradiction", action="store_true",
                        help="exit non-zero when any contradiction is found")
    args = parser.parse_args(argv)

    catalog_path = resolve_catalog_path(args.catalog)
    catalog = load_catalog(catalog_path)
    registry = load_registry()

    findings = run_audit(catalog, registry)
    if args.check:
        wanted = set(args.check)
        findings = [f for f in findings if f.check in wanted]
    summary = summarise(findings, catalog)

    print(f"catalog: {catalog_path}")
    print(json.dumps(summary, indent=2))

    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(
            {"summary": summary, "findings": [f.as_dict() for f in findings]}, indent=1) + "\n")
    if args.markdown:
        args.markdown.parent.mkdir(parents=True, exist_ok=True)
        args.markdown.write_text(render_markdown(summary, findings, catalog, registry))
    if args.triage_queue:
        args.triage_queue.parent.mkdir(parents=True, exist_ok=True)
        args.triage_queue.write_text(json.dumps(model_triage_prompts(findings, catalog), indent=1) + "\n")

    if args.fail_on_contradiction and summary["objectsContradicted"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
