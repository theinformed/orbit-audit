#!/usr/bin/env python3
"""T16b truth-set acquisition: fetch the precise-orbit products and the
labelled-manoeuvre tables the measurement is registered against, and write a
manifest that records exactly what was fetched.

Nothing here measures anything. It downloads published products into a private
directory outside the repository (the labelled set is CC BY 4.0 and is not
redistributed here) and records, per file, the source URL, the byte count and
the SHA-256, so every later number can name the bytes it came from.

Sources, all anonymous and verified reachable before the registration was
written:

  s1      Copernicus Sentinel-1 precise orbit ephemerides, product type
          AUX_POEORB, Earth Explorer XML ("EOF"), EARTH_FIXED frame, UTC
          time tags, 10 s sampling, one file per day with ~26 h validity.
          Registry of Open Data on AWS, bucket `s1-orbits`.
  s3a     CNES/SSALTO precise orbit ephemerides for Sentinel-3A, SP3-c,
  s3b     ITRF, TAI time tags, 60 s sampling, ~10 d per file, distributed
          by the International DORIS Service data centre (IGN FTP).
  ids     IDS/DORIS mission-reported manoeuvre histories for the same two
          Sentinel-3 spacecraft (the source the labelled set parses).
  madleo  MAD-LEO annotation tables (CSV only; the multi-gigabyte evidence
          parquets are not needed because the element sets under test come
          from this programme's own archive).

Usage:
  truthset_fetch.py --what s1 --start 2023-01-01 --end 2024-01-01
  truthset_fetch.py --what s3a --start 2023-01-01 --end 2024-01-01
  truthset_fetch.py --what madleo
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from ftplib import FTP
from pathlib import Path

# Installation-specific locations. Each is named by an environment variable
# and falls back to a placeholder that cannot resolve, so an unconfigured
# checkout fails with the name of the variable it needs instead of reading
# whatever happens to sit at somebody else's path.
OUT_DEFAULT = Path(os.environ.get("ORBIT_TRUTHSET_ROOT",
                                  "truthset.not-configured"))

S1_BUCKET = "https://s1-orbits.s3.us-west-2.amazonaws.com"
S1_PREFIX = "AUX_POEORB/S1A_OPER_AUX_POEORB_"

IDS_FTP_HOST = "doris.ign.fr"
IDS_FTP_DIR = "/pub/doris/products/orbits/ssa"
IDS_MAN_URL = "https://ids-doris.org/documents/BC/satellites/{code}man.txt"

# figshare file ids of the MAD-LEO annotation tables (deposit 33446503 v1)
MADLEO_FILES = {
    "docs__metadata.md": 68257465,
    "mission_reported__annotations__event_windows.csv": 68257468,
    "mission_reported__annotations__maneuver_annotations.csv": 68257471,
    "mission_reported__annotations__stable_windows.csv": 68257477,
    "mission_reported__annotations__stable_windows_matched.csv": 68257474,
}
MADLEO_URL = "https://ndownloader.figshare.com/files/{fid}"

# Earth orientation: polar motion and UT1-UTC, without which the TEME -> ITRF
# rotation carries an error of the same order as the shortest-horizon result.
EOP_URL = "https://datacenter.iers.org/data/9/finals2000A.all"

# SP3 product version to take, per spacecraft: 30 is the POE-G standard, the
# one the distributor's own README marks "current (recommended)".
SP3_VERSION = "30"

USER_AGENT = "space-teaching-aid-truthset/1 (research; contact via repository)"


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def http_get(url: str, dest: Path, tries: int = 3) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    last = None
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                data = resp.read()
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
            return
        except Exception as exc:                      # noqa: BLE001
            last = exc
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"could not fetch {url}: {last}")


def http_text(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return resp.read().decode("utf-8", "replace")


def list_bucket(prefix: str) -> list[tuple[str, int]]:
    """Every key under a prefix, with its size, following continuations."""
    keys: list[tuple[str, int]] = []
    token = None
    while True:
        url = f"{S1_BUCKET}/?list-type=2&max-keys=1000&prefix={prefix}"
        if token:
            url += "&continuation-token=" + urllib.parse.quote(token, safe="")
        body = http_text(url)
        for match in re.finditer(r"<Contents>(.*?)</Contents>", body, re.S):
            block = match.group(1)
            key = re.search(r"<Key>(.*?)</Key>", block)
            size = re.search(r"<Size>(\d+)</Size>", block)
            if key and size:
                keys.append((key.group(1), int(size.group(1))))
        more = re.search(r"<IsTruncated>(.*?)</IsTruncated>", body)
        if not more or more.group(1) != "true":
            break
        nxt = re.search(r"<NextContinuationToken>(.*?)</NextContinuationToken>", body)
        if not nxt:
            break
        token = nxt.group(1)
    return keys


_S1_NAME = re.compile(
    r"S1A_OPER_AUX_POEORB_OPOD_(\d{8}T\d{6})_V(\d{8}T\d{6})_(\d{8}T\d{6})\.EOF$")


def s1_keys_for(start: dt.date, end: dt.date) -> list[tuple[str, dt.datetime, dt.datetime, dt.datetime]]:
    """POEORB keys whose validity interval intersects [start, end)."""
    out = []
    seen: dict[str, tuple] = {}
    for key, _size in list_bucket(S1_PREFIX):
        m = _S1_NAME.search(key)
        if not m:
            continue
        made = dt.datetime.strptime(m.group(1), "%Y%m%dT%H%M%S")
        v0 = dt.datetime.strptime(m.group(2), "%Y%m%dT%H%M%S")
        v1 = dt.datetime.strptime(m.group(3), "%Y%m%dT%H%M%S")
        if v1.date() < start or v0.date() >= end:
            continue
        # the mid-point day is the day this file is the primary product for;
        # keep the most recently produced file for each such day.
        day = (v0 + (v1 - v0) / 2).date().isoformat()
        prev = seen.get(day)
        if prev is None or made > prev[1]:
            seen[day] = (key, made, v0, v1)
    for day in sorted(seen):
        key, made, v0, v1 = seen[day]
        out.append((key, made, v0, v1))
    return out


def ftp_list(code: str) -> list[str]:
    with FTP(IDS_FTP_HOST, timeout=120) as ftp:
        ftp.login()
        ftp.cwd(f"{IDS_FTP_DIR}/{code}")
        return ftp.nlst()


def ftp_get(code: str, name: str, dest: Path, tries: int = 4) -> None:
    """One file over anonymous FTP, with retries.

    The data connection to this host times out occasionally under a long
    sequential pull; a partial file is removed before the retry so a
    truncated arc can never be parsed as a complete one.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    last = None
    for attempt in range(tries):
        try:
            with FTP(IDS_FTP_HOST, timeout=120) as ftp:
                ftp.login()
                ftp.cwd(f"{IDS_FTP_DIR}/{code}")
                with dest.open("wb") as fh:
                    ftp.retrbinary(f"RETR {name}", fh.write)
            # a compressed arc that does not decompress is a truncated
            # transfer that looked like a success; it must not survive to be
            # parsed as a short arc.
            if dest.suffix == ".Z":
                subprocess.run(["gzip", "-t", str(dest)], check=True,
                               capture_output=True)
            return
        except Exception as exc:                      # noqa: BLE001
            last = exc
            dest.unlink(missing_ok=True)
            time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"could not fetch {code}/{name}: {last}")


_SP3_NAME = re.compile(r"^ssa(\w{3})(\d{2})\.b(\d{5})\.e(\d{5})\.")


def _yyddd(text: str) -> dt.date:
    year = int(text[:2])
    year += 2000 if year < 80 else 1900
    return dt.date(year, 1, 1) + dt.timedelta(days=int(text[2:]) - 1)


def sp3_names_for(code: str, start: dt.date, end: dt.date) -> list[tuple[str, dt.date, dt.date]]:
    out = []
    for name in ftp_list(code):
        m = _SP3_NAME.match(name)
        if not m or m.group(2) != SP3_VERSION:
            continue
        b, e = _yyddd(m.group(3)), _yyddd(m.group(4))
        if e < start or b >= end:
            continue
        out.append((name, b, e))
    return sorted(out, key=lambda row: row[1])


def record(manifest: list[dict], path: Path, url: str, extra: dict | None = None) -> None:
    row = {
        "file": path.name,
        "url": url,
        "bytes": path.stat().st_size,
        "sha256": sha256_of(path),
        "fetchedUtc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
    }
    if extra:
        row.update(extra)
    manifest.append(row)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--what", required=True,
                    choices=("s1", "s3a", "s3b", "ids", "madleo", "eop"))
    ap.add_argument("--start", default="2023-01-01")
    ap.add_argument("--end", default="2024-01-01")
    ap.add_argument("--out", type=Path, default=OUT_DEFAULT)
    args = ap.parse_args(argv)

    start = dt.date.fromisoformat(args.start)
    end = dt.date.fromisoformat(args.end)
    out = args.out
    manifest: list[dict] = []

    if args.what == "s1":
        target = out / "eof" / "s1a"
        target.mkdir(parents=True, exist_ok=True)
        keys = s1_keys_for(start, end)
        print(f"s1a AUX_POEORB: {len(keys)} daily products in "
              f"[{start}, {end})", flush=True)
        for i, (key, made, v0, v1) in enumerate(keys, 1):
            dest = target / Path(key).name
            url = f"{S1_BUCKET}/{key}"
            if not dest.exists():
                http_get(url, dest)
            record(manifest, dest, url, {
                "validityStartUtc": v0.isoformat(),
                "validityStopUtc": v1.isoformat(),
                "creationUtc": made.isoformat(),
                "latencyDays": round((made - v1).total_seconds() / 86400.0, 3),
            })
            if i % 25 == 0:
                print(f"  {i}/{len(keys)}", flush=True)

    elif args.what in ("s3a", "s3b"):
        code = args.what
        target = out / "sp3" / code
        target.mkdir(parents=True, exist_ok=True)
        names = sp3_names_for(code, start, end)
        print(f"{code} SP3 v{SP3_VERSION}: {len(names)} arcs in "
              f"[{start}, {end})", flush=True)
        for name, b, e in names:
            dest = target / name
            if not dest.exists():
                ftp_get(code, name, dest)
            record(manifest, dest,
                   f"ftp://{IDS_FTP_HOST}{IDS_FTP_DIR}/{code}/{name}",
                   {"arcStart": b.isoformat(), "arcEnd": e.isoformat()})

    elif args.what == "ids":
        target = out / "ids"
        target.mkdir(parents=True, exist_ok=True)
        for code in ("s3a", "s3b"):
            url = IDS_MAN_URL.format(code=code)
            dest = target / f"{code}man.txt"
            http_get(url, dest)
            record(manifest, dest, url)

    elif args.what == "eop":
        target = out / "eop"
        target.mkdir(parents=True, exist_ok=True)
        dest = target / "finals2000A.all"
        http_get(EOP_URL, dest)
        record(manifest, dest, EOP_URL)

    elif args.what == "madleo":
        target = out / "madleo"
        target.mkdir(parents=True, exist_ok=True)
        for name, fid in MADLEO_FILES.items():
            url = MADLEO_URL.format(fid=fid)
            dest = target / name
            if not dest.exists():
                http_get(url, dest)
            record(manifest, dest, url, {"figshareFileId": fid,
                                         "licence": "CC BY 4.0",
                                         "doi": "10.6084/m9.figshare.33446503.v1"})

    man_path = out / f"manifest-{args.what}.json"
    man_path.parent.mkdir(parents=True, exist_ok=True)
    man_path.write_text(json.dumps({
        "what": args.what,
        "start": args.start,
        "end": args.end,
        "files": manifest,
        "totalBytes": sum(r["bytes"] for r in manifest),
    }, indent=2) + "\n")
    print(f"{len(manifest)} files, "
          f"{sum(r['bytes'] for r in manifest) / 1e6:.1f} MB -> {man_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
