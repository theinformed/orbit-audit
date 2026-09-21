#!/usr/bin/env python3
"""Polite mirror of Jonathan McDowell's General Catalog of Artificial Space
Objects (GCAT), used for ONE fact this project could not otherwise establish:
which country the spacecraft's OPERATOR belongs to.

Why a second catalogue at all
-----------------------------
The published catalog's country comes from space-track's SATCAT ``COUNTRY``
column. That column is the state the object is ATTRIBUTED to in the registry,
and for a rideshare smallsat it is routinely the entity that filed the paperwork
-- very often the integrator or the launch broker -- not the organisation that
flies the spacecraft. Live examples from the 2026-08-20 release: SARI-1 and
SARI-2 (Saudi payloads, ``COUNTRY`` = BRAZ, after their Brazilian integrator),
LEONAV-1 (UAE, ``COUNTRY`` = FR after U-Space), CLOUDCT-PRECURSOR (Israeli,
``COUNTRY`` = GER after ZfT), GARAI-B (Spanish, ``COUNTRY`` = SWED after OHB
Sweden). CelesTrak's own ``OWNER`` column is curated and disagrees with
space-track on 90 of the 8,000 objects we publish, but it repeats the same
builder attribution on most of these; it is not a way out.

GCAT keeps ``Owner``, ``State`` and ``Manufacturer`` as three SEPARATE columns,
which is exactly the distinction that is being lost, and it is the reference
work astronomers and the trade press cite for it.

Courtesy
--------
GCAT is one astrophysicist's unfunded side project served from a personal page.
It carries no machine-access policy, so the budget here is ours and it is
deliberately mean: two files, refreshed WEEKLY (the operator of a spacecraft
does not change on a publish cycle), a descriptive User-Agent with a contact
address, a conditional request when we already hold a copy, and a hard stop on
the first non-200 exactly as the CelesTrak mirror does. The catalog build reads
the mirror off disk and NEVER fetches; if the mirror is missing the build simply
publishes no operator-country fact and says so in the artifact.

Unrestricted from either host: planet4589.org is not one of the sources this
installation routes through the VPS.
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

MIRROR = Path(os.environ.get("SPACE_EXPLORER_GCAT_MIRROR", str(ROOT / "runtime" / "gcat-mirror")))

#: The two tables we read, and nothing else. ``satcat.tsv`` carries one row per
#: catalogued object with its owner, state and manufacturer; ``orgs.tsv`` is the
#: code book that turns ``SAUDSA`` into an organisation with a home state.
FILES = {
    "satcat.tsv": "https://planet4589.org/space/gcat/tsv/cat/satcat.tsv",
    "orgs.tsv": "https://planet4589.org/space/gcat/tsv/tables/orgs.tsv",
}

#: A week. Operator identity is not a time series.
REFRESH_SECONDS = 7 * 24 * 60 * 60

USER_AGENT = (
    "space-teaching-aid/1.0 (Space Environment Explorer; "
    "https://sean.theinformed.org/space/; contact: darobinson.ak@gmail.com)"
)

#: Written beside the mirror when a fetch comes back non-200. While it exists
#: this script refuses to fetch, the same spine as ingest/celestrak_mirror.py:
#: a machine that keeps asking after being told no is the behaviour that gets an
#: installation firewalled.
HALT = "gcat-halt"


class GcatFetchRefused(RuntimeError):
    """A non-200, or a body that is not the TSV we asked for."""


def _age_seconds(path: Path) -> float:
    try:
        return (dt.datetime.now(dt.timezone.utc).timestamp() - path.stat().st_mtime)
    except OSError:
        return float("inf")


def _looks_like_gcat_tsv(body: bytes) -> bool:
    """GCAT answers an unknown path with an HTML error page, HTTP 200 and all.

    The first line of a real table is a ``#``-commented header of tab-separated
    column names, so that is what is checked rather than the status code alone.
    """
    head = body[:400].lstrip()
    return head.startswith(b"#") and b"\t" in head.split(b"\n", 1)[0]


def fetch(name: str, url: str, destination: Path) -> int:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            if response.status != 200:
                raise GcatFetchRefused(f"{name}: HTTP {response.status}")
            body = response.read()
    except urllib.error.HTTPError as error:
        raise GcatFetchRefused(f"{name}: HTTP {error.code}") from error
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        raise GcatFetchRefused(f"{name}: {error}") from error
    if not _looks_like_gcat_tsv(body):
        raise GcatFetchRefused(f"{name}: body is not a GCAT table ({body[:80]!r})")
    destination.parent.mkdir(parents=True, exist_ok=True)
    tmp = destination.with_suffix(destination.suffix + ".part")
    tmp.write_bytes(body)
    tmp.replace(destination)
    return len(body)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="fetch even if the mirror is fresh")
    parser.add_argument("--clear-halt", action="store_true", help="remove the halt marker and exit")
    args = parser.parse_args(argv)

    halt = MIRROR / HALT
    if args.clear_halt:
        halt.unlink(missing_ok=True)
        print("halt marker cleared")
        return 0
    if halt.exists():
        print(f"REFUSING: {halt} exists; a previous fetch was refused. Investigate, then --clear-halt.")
        return 1

    fetched = 0
    for name, url in FILES.items():
        destination = MIRROR / name
        if not args.force and _age_seconds(destination) < REFRESH_SECONDS:
            print(f"{name}: fresh, not fetching")
            continue
        try:
            size = fetch(name, url, destination)
        except GcatFetchRefused as error:
            MIRROR.mkdir(parents=True, exist_ok=True)
            halt.write_text(f"{dt.datetime.now(dt.timezone.utc).isoformat()} {error}\n")
            print(f"STOPPED: {error}; wrote {halt}")
            return 1
        fetched += 1
        print(f"{name}: {size:,} bytes")
    print(f"gcat mirror at {MIRROR} ({fetched} file(s) refreshed)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
