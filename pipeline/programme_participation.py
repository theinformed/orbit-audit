"""Publicly documented programme participation: one spacecraft, more than one mission.

The catalog's ``owner`` field can hold exactly one organisation, and its
``mission`` field exactly one purpose. Neither can express the arrangement that
is genuinely common in orbit: a commercial communications satellite that also
carries a government sensor, a navigation constellation that also relays
distress beacons, a government programme that buys capacity on somebody else's
spacecraft. That is the gap this table fills, and it is why the field is worth
publishing rather than folding into ``purpose``.

**Everything here is reported, never inferred.** Each entry records a
*published* statement that a named spacecraft participates in a named
programme, and carries the URL of the page that says so. There is no rule, no
heuristic and no orbital analysis anywhere on this path: nothing in this module
looks at an element set, and nothing looks at a spacecraft *name*. See
``docs/mission-speculation-design.md`` §1.6 for the boundary this respects — the
site does not deduce relationships between spacecraft, and a hosted-payload
feature is only on the right side of that line while every entry is a citation.

Two deliberate constraints, both enforced by :func:`validate_participation`:

1. **Attachment is by NORAD catalog ID only.** No prefix, no token, no name
   matching of any kind. `docs/catalog-accuracy-audit.md` §5A.2a records the
   residual defect class that token-boundary matching cannot catch — a real
   token belonging to the wrong programme — and this table would be unusually
   exposed to it. The 26 original Iridium block-1 spacecraft still on orbit are
   named exactly like the 80 Iridium NEXT spacecraft that carry the Aireon
   payload; any name rule attaches an aircraft-tracking receiver to sixteen
   satellites launched in the 1990s that do not have one. Keying on catalog ID
   makes that class of error unreachable rather than unlikely.
2. **Every catalog ID is stamped with the registry name it resolved to**, in
   ``noradNames``, and ``tests/test_programme_participation.py`` re-checks all
   of them against the offline registry mirror. Hand-written IDs have their own
   failure mode: ``29268`` was once written for SAPPHIRE and the registry calls
   it KOMPSAT 2 (§5A.2).

The cost of NORAD-keying is that a newly launched member of a participating
family does not inherit the entry until somebody adds its catalog ID. That is
the intended trade: a list that is occasionally incomplete is honest, and a rule
that occasionally over-claims is not.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PARTICIPATION_PATH = ROOT / "data" / "programme_participation.json"

# How a spacecraft takes part in a programme that is not its owner's. The set is
# closed: a kind outside it is a hard error rather than a pass-through, because
# "what kind of sharing is this" is the whole teaching point of the field and an
# unrecognised value would render as an unexplained word on a public card.
PARTICIPATION_KINDS: dict[str, str] = {
    # A separate payload belonging to somebody else, flying on this spacecraft.
    "hosted-payload": "hosted payload",
    # No separate box. A share of the spacecraft's own payload -- so many
    # transponders, so much bandwidth -- is assigned to a different programme.
    # This is how the Global Broadcast Service rides Wideband Global SATCOM, and
    # it is invisible from the outside in a way a hosted payload is not.
    "allocated-capacity": "allocated capacity on its own payload",
    # No hardware is shared. A programme buys or leases the use of capacity on a
    # spacecraft it does not own. This is the CBSP case, and it is the one form
    # of sharing that is invisible from the object itself.
    "leased-capacity": "leased capacity",
    # Two organisations' primary payloads share one bus, launched and operated as
    # one spacecraft, with neither payload subordinate to the other.
    "shared-bus": "shared bus",
    # A scientific instrument flying as a guest on another agency's spacecraft.
    "guest-instrument": "guest instrument",
    # The spacecraft is one organisation's, but a partner nation or agency funded
    # part of the system and holds access to it under a published agreement.
    "international-partnership": "international partnership",
}

# Whether the shared use is still running. "ended" matters: CHIRP finished its
# demonstration years ago and the host is still flying, and a card that implies
# an ended payload is live is wrong in the same way a stale mission label is.
PARTICIPATION_STATUS = ("operational", "ended", "unstated")

_SLUG = re.compile(r"^[a-z0-9][a-z0-9-]*$")

_REQUIRED_TEXT = (
    "programmeId",
    "programme",
    "sponsor",
    "operator",
    "participation",
    "note",
    "programmeSummary",
    "sourceName",
)


def load_participation(path: Path | None = None) -> dict[str, Any]:
    """Read the curated table from disk. No network, no derivation."""
    return json.loads((path or PARTICIPATION_PATH).read_text())


def validate_participation(table: dict[str, Any]) -> None:
    """Refuse a table that could attach a programme claim to the wrong object.

    Deliberately raises rather than warning, for the same reason
    :func:`build_release.validate_overrides` does: "this spacecraft carries a
    payload for a foreign government's broadcast programme" is a high-
    consequence sentence, and the cheapest place to stop a wrong one is before
    it is published.
    """
    if not isinstance(table, dict):
        raise ValueError("programme participation table must be an object")
    seen_pairs: set[tuple[int, str]] = set()
    programmes: dict[str, tuple[str, str, str]] = {}
    for key, entry in table.items():
        if key.startswith("$"):  # reserved for file-level metadata
            continue
        if not isinstance(entry, dict):
            raise ValueError(f"participation {key!r}: entry must be an object")
        # Attachment is by catalog ID and nothing else. There is no name
        # matching on this path at all, so there is no boundary rule to get
        # wrong and no token that can belong to two programmes at once.
        if entry.get("match") != "norad":
            raise ValueError(
                f"participation {key!r}: match must be 'norad'; programme claims attach by "
                "catalog ID only, never by spacecraft name"
            )
        # A programme can be thoroughly documented and still name no spacecraft.
        # The Navy's Commercial Broadband Satellite Program buys capacity as a
        # service: the provider is public, the contract is public, and which
        # spacecraft carries the traffic at any moment is not. Guessing at the
        # objects would be the inference this whole table exists to avoid, and
        # dropping the programme would hide the most interesting case of the
        # lot, so it is published attached to nothing, with the reason.
        unattached = bool(entry.get("participantsNotPublic"))
        if unattached and not str(entry.get("participantsNote") or "").strip():
            raise ValueError(
                f"participation {key!r}: participantsNotPublic requires a participantsNote "
                "saying what the public record does and does not identify"
            )
        norad = entry.get("norad")
        if not isinstance(norad, list) or not all(isinstance(v, int) for v in norad):
            raise ValueError(f"participation {key!r}: 'norad' must be a list of integers")
        if not norad and not unattached:
            raise ValueError(
                f"participation {key!r}: 'norad' is empty; set participantsNotPublic if the "
                "public record genuinely does not identify the spacecraft"
            )
        if norad and unattached:
            raise ValueError(
                f"participation {key!r}: participantsNotPublic contradicts the catalog IDs listed"
            )
        names = entry.get("noradNames")
        if not isinstance(names, list) or len(names) != len(norad):
            raise ValueError(
                f"participation {key!r}: 'noradNames' must line up one-to-one with 'norad'; "
                "every catalog ID is stamped with the registry name it was resolved from"
            )
        if len(set(norad)) != len(norad):
            raise ValueError(f"participation {key!r}: repeats a catalog ID")
        for field in _REQUIRED_TEXT:
            if not str(entry.get(field) or "").strip():
                raise ValueError(f"participation {key!r}: {field} is required")
        if entry["participation"] not in PARTICIPATION_KINDS:
            raise ValueError(
                f"participation {key!r}: unknown participation kind {entry['participation']!r}; "
                f"expected one of {sorted(PARTICIPATION_KINDS)}"
            )
        if entry.get("status", "unstated") not in PARTICIPATION_STATUS:
            raise ValueError(f"participation {key!r}: unknown status {entry.get('status')!r}")
        if not _SLUG.match(str(entry["programmeId"])):
            raise ValueError(f"participation {key!r}: programmeId must be a lowercase slug")
        # No citation, no entry. This is the same bar `validate_overrides()`
        # holds for a curated description, and it is the entire defence against
        # this feature becoming inference wearing a citation's clothes.
        for field in ("source", "programmeSource"):
            if not str(entry.get(field) or "").startswith(("https://", "http://")):
                raise ValueError(
                    f"participation {key!r}: {field} must be a public URL a reader can check"
                )
        # A claim can rest on more than one page -- an official programme fact
        # sheet that names the arrangement, plus a reference that names the
        # spacecraft. Both travel with the record rather than one being dropped.
        for extra in entry.get("additionalSources", ()):
            if not isinstance(extra, dict) or not str(extra.get("name") or "").strip():
                raise ValueError(f"participation {key!r}: each additional source needs a name")
            if not str(extra.get("url") or "").startswith(("https://", "http://")):
                raise ValueError(f"participation {key!r}: each additional source needs a URL")
        programme_id = str(entry["programmeId"])
        signature = (
            str(entry["programme"]),
            str(entry.get("abbreviation") or ""),
            str(entry["programmeSummary"]),
        )
        if programmes.setdefault(programme_id, signature) != signature:
            raise ValueError(
                f"participation {key!r}: programme {programme_id!r} is described differently here "
                "than in another entry; one programme has one description"
            )
        for catalog_id in norad:
            pair = (catalog_id, programme_id)
            if pair in seen_pairs:
                raise ValueError(
                    f"participation {key!r}: catalog ID {catalog_id} is already claimed for "
                    f"programme {programme_id!r}"
                )
            seen_pairs.add(pair)


def published_entry(entry: dict[str, Any]) -> dict[str, Any]:
    """The shape a single participation takes on a published catalog record."""
    return {
        "programmeId": entry["programmeId"],
        "programme": entry["programme"],
        "abbreviation": entry.get("abbreviation"),
        "sponsor": entry["sponsor"],
        "operator": entry["operator"],
        "participation": entry["participation"],
        "definiteArticle": bool(entry.get("definiteArticle")),
        # The human words for the kind live beside the machine value so the
        # interface never has to keep its own copy of this vocabulary.
        "participationLabel": PARTICIPATION_KINDS[entry["participation"]],
        "status": entry.get("status", "unstated"),
        "note": entry["note"],
        "source": entry["source"],
        "sourceName": entry["sourceName"],
        "additionalSources": list(entry.get("additionalSources", ())) or None,
    }


def participation_index(table: dict[str, Any]) -> dict[int, list[dict[str, Any]]]:
    """Catalog ID -> the programmes that ID is published as taking part in.

    Built once per release rather than per object, and keyed on the only
    identifier that cannot be ambiguous.
    """
    index: dict[int, list[dict[str, Any]]] = {}
    for key, entry in table.items():
        if key.startswith("$") or not isinstance(entry, dict):
            continue
        record = published_entry(entry)
        for catalog_id in entry["norad"]:
            index.setdefault(int(catalog_id), []).append(record)
    for entries in index.values():
        entries.sort(key=lambda item: (item["programme"], item["participation"]))
    return index


def programme_catalog(
    table: dict[str, Any], index: dict[int, list[dict[str, Any]]] | None = None
) -> list[dict[str, Any]]:
    """One row per programme, for a browser facet that filters by programme.

    Published alongside the satellites so the interface can offer the filter
    without scanning 8,000 records to discover which programmes exist, and so
    the count beside each name is computed once, by the pipeline, from the same
    table that produced the per-object field.
    """
    rows: dict[str, dict[str, Any]] = {}
    for key, entry in table.items():
        if key.startswith("$") or not isinstance(entry, dict):
            continue
        programme_id = str(entry["programmeId"])
        row = rows.setdefault(
            programme_id,
            {
                "programmeId": programme_id,
                "programme": entry["programme"],
                "abbreviation": entry.get("abbreviation"),
                "summary": entry["programmeSummary"],
                "sponsor": entry["sponsor"],
                "source": entry["programmeSource"],
                "participationKinds": [],
                "objects": 0,
                # False where the programme is documented but the public record
                # does not say which spacecraft take part. The interface should
                # still list it, with the reason, rather than silently omitting
                # a programme this site cannot point at.
                "participantsPublished": True,
                "participantsNote": None,
            },
        )
        if entry.get("participantsNotPublic"):
            row["participantsPublished"] = False
            row["participantsNote"] = entry["participantsNote"]
        if entry["participation"] not in row["participationKinds"]:
            row["participationKinds"].append(entry["participation"])
    for entries in (index or {}).values():
        for record in entries:
            row = rows.get(record["programmeId"])
            if row is not None:
                row["objects"] += 1
    for row in rows.values():
        row["participationKinds"].sort()
    return sorted(rows.values(), key=lambda row: row["programme"])


# The one sentence a reader needs in order to understand the field at all: most
# people arrive believing one satellite means one owner and one job.
PARTICIPATION_LEDE = (
    "A spacecraft can be owned and operated by one organisation and still carry, or be "
    "contracted to serve, another organisation's mission."
)


def participation_disclosure(entries: list[dict[str, Any]], operator: str) -> str:
    """The visible prose, generated from the structured field.

    Generated rather than hand-written for the reason
    :func:`build_release.contested_caveat` is: the prose and the machine-readable
    field can then never drift apart, and it is belt-and-braces. ``programmes``
    is published for the interface to render properly, but until it does, this
    sentence is the only thing the reader sees, and a disclosure that exists only
    in a field nothing renders is not a disclosure.
    """
    if not entries:
        return ""
    parts = [f" {PARTICIPATION_LEDE}"]
    for position, record in enumerate(entries):
        name = record["programme"]
        if record.get("abbreviation"):
            name = f"{name} ({record['abbreviation']})"
        # "a payload for the Global Broadcast Service" reads correctly and "a
        # payload for the Aireon" does not, so the entry says which it is
        # rather than the sentence guessing from the words.
        if record.get("definiteArticle"):
            name = f"the {name}"
        tense = "carried" if record["status"] == "ended" else "carries"
        if record["participation"] == "leased-capacity":
            tense = "provided" if record["status"] == "ended" else "provides"
            shape = f"{tense} leased capacity to {name}"
        elif record["participation"] == "allocated-capacity":
            shape = f"{tense} {name} on an allocated share of its own payload"
        elif record["participation"] == "shared-bus":
            shape = f"shares its bus with the {name} payload"
        elif record["participation"] == "guest-instrument":
            shape = f"{tense} the {name} instrument as a guest payload"
        elif record["participation"] == "international-partnership":
            shape = f"is part of {name}, which partner nations funded and share access to"
        else:
            shape = f"{tense} a payload for {name}"
        ended = " This arrangement has ended." if record["status"] == "ended" else ""
        # The operator is named once. A satellite carrying three programmes
        # should not repeat "this spacecraft is operated by" three times.
        opening = (
            f" Operated by {operator}, this spacecraft also"
            if position == 0
            else " It also"
        )
        parts.append(
            f"{opening} {shape}, sponsored by {record['sponsor']}. "
            f"{record['note']} Published by {record['sourceName']}.{ended}"
        )
    return "".join(parts)
