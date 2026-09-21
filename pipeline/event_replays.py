#!/usr/bin/env python3
"""Build the measured replay payloads that the Historical events page animates.

Why this file exists
--------------------
The events page used to animate every event with the SAME three CSS custom
properties -- a blob that narrowed, a line that lengthened, and a saturation
filter -- driven by four hand-authored 0..1 numbers per milestone. Nothing in
it was measured, and because the markup was identical for every event the
animation could not distinguish the Quebec blackout from a Starlink launch.
It was decoration standing where evidence belongs.

This module replaces that for the event where this project already HOLDS the
measurements. It performs the reduction on bigmem and writes the result into
``data/events.json`` as a per-event ``replay`` block, so the existing release
path publishes it with no change to ``pipeline/build_release.py``.

## starlink-2022: the launch is the controlled experiment

Forty-nine spacecraft went up together on 2022-02-03 into the same ~210 km
insertion orbit on the same vehicle. A modest storm arrived. Some climbed out
and some did not. There is no confound to argue about: same hardware, same
epoch, same altitude, two outcomes. The animation is simply every catalogued
member of that launch drawn against time.

**What the archive actually contains, and what it does not.** Space-track's
2022 bulk element-set bundle holds 21 objects under international designator
2022-010, not 49. Eleven of them are still producing element sets at the end of
2022 having climbed to about 538 km; ten stop between 2022-02-06 and 2022-02-15
with perigee falling through 135-155 km. The public record is that 38 of the 49
reentered, so the 28 that this archive never names are objects that reentered
before a permanent catalogue number was assigned to them. The page says so.
Drawing 21 traces and captioning them "the 49 satellites" would be exactly the
kind of quiet overclaim this site exists to avoid.

**Altitude here is derived, not ranged.** Each point is computed from the
Brouwer mean elements inside one published element set: the Kozai mean motion
is converted to the semi-major axis with the standard SGP4 initialisation
correction (a1/delta1/a0/delta0 below), and perigee and apogee follow from
a(1-e) and a(1+e) against a spherical Earth of radius 6378.137 km. That is the
conventional reading of a TLE and it is not a measured range to the spacecraft,
so the payload carries ``method`` and the page prints it.

**Nothing is interpolated.** The published series is thinned by SELECTING the
real element set nearest each grid time and carrying its true epoch, never by
averaging or interpolating between two of them. A grid time with no element set
within half the grid spacing produces no sample. This follows the rule the
environment-history modules already hold: a genuinely missing time stays
missing.

The driver trace is GFZ Potsdam's Kp and ap for the same window -- one small
JSON request, no authentication -- so the page can show that the storm which
did this peaked at Kp 5.33. That is a G1, the mildest storm level NOAA names.
The lesson is the size of the consequence against the size of the cause, and it
only lands because the number is the real one.

## gannon-2024, halloween-2003, quebec-1989

Three more events now carry replays, built by the same rules: every drawn point
is one real sample carrying its own timestamp, a gap stays a gap, and each
series says which of `measurement` and `model` it is. What differs between them
is the EVIDENCE CLASS, and the page shows that difference rather than smoothing
it away.

    gannon-2024      a measured curve (Swarm-C's own accelerometer) against a
                     model curve (WAM-IPE) sampled at the same point, plus the
                     model's disagreement with its own six-hour-old forecast.
    halloween-2003   three instruments, three cadences, one logarithmic axis,
                     because the separations ARE the lesson.
    quebec-1989      one measured index, and a drawn mechanism that never
                     pretends to be a measurement of anything.

INTERPRETER. `gannon-2024` needs `netCDF4` and `cdflib`, which on bigmem live in
`/home/sdegan/hfenv`, not in the system interpreter. Both are imported inside
the builder that needs them so the other three events run anywhere:

    /home/sdegan/hfenv/bin/python -m pipeline.event_replays --event gannon --write

Run:  python3 -m pipeline.event_replays --write
"""

from __future__ import annotations

import argparse
import base64
import json
import math
import re
import subprocess
import sys
import urllib.request
import zipfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
EVENTS_PATH = ROOT / "data" / "events.json"
BULK_2022 = Path("/mnt/d/space-orbit-history/bulk/tle2022.txt.zip")
BULK_MEMBER = "tle2022.txt"
CACHE_DIR = ROOT / "pipeline" / ".cache" / "event-replays"

# International designator prefix for the 2022-02-03 Starlink Group 4-7 launch.
LAUNCH_DESIGNATOR = "22010"

EARTH_RADIUS_KM = 6378.137
# SGP4/WGS-72 constants, in the Earth-radii/minute units the initialisation uses.
XKE = 0.07436691613317342          # sqrt(GM) in er^1.5 / min
J2 = 1.082616e-3
CK2 = 0.5 * J2                     # k2 with aE = 1

GFZ_KP_URL = "https://kp.gfz.de/app/json/"


def semi_major_axis_er(mean_motion_rev_day: float, ecc: float, inc_deg: float) -> float:
    """Recover the SGP4 semi-major axis (Earth radii) from a TLE's Kozai mean motion.

    Taking a = (mu/n^2)^(1/3) straight off the published mean motion is wrong by
    one to two kilometres in low orbit, because the TLE carries the Kozai mean
    motion rather than the Brouwer one. At a 140 km perigee that is roughly a
    percent of the number the page is about to draw, so the standard SGP4
    initialisation correction is applied instead of being waved away.
    """
    n0 = mean_motion_rev_day * 2.0 * math.pi / 1440.0   # rad/min
    cosio = math.cos(math.radians(inc_deg))
    x3thm1 = 3.0 * cosio * cosio - 1.0
    beta0 = math.sqrt(max(1.0 - ecc * ecc, 1e-12))
    a1 = (XKE / n0) ** (2.0 / 3.0)
    delta1 = 1.5 * CK2 * x3thm1 / (a1 * a1 * beta0 ** 3)
    a0 = a1 * (1.0 - delta1 / 3.0 - delta1 * delta1 - (134.0 / 81.0) * delta1 ** 3)
    delta0 = 1.5 * CK2 * x3thm1 / (a0 * a0 * beta0 ** 3)
    return a0 / (1.0 - delta0)


def epoch_to_datetime(two_digit_year: int, day_of_year: float) -> datetime:
    year = 2000 + two_digit_year if two_digit_year < 57 else 1900 + two_digit_year
    return datetime(year, 1, 1, tzinfo=timezone.utc) + timedelta(days=day_of_year - 1.0)


def extract_launch_elsets(designator: str = LAUNCH_DESIGNATOR) -> dict[int, list[dict]]:
    """Stream the local bulk archive for one launch. Makes no network request."""
    if not BULK_2022.is_file():
        raise SystemExit(f"bulk archive missing: {BULK_2022}")
    pattern = f"^1 [0-9 ]{{5}}U {designator}"
    command = (
        f"nice -n 15 unzip -p {BULK_2022} {BULK_MEMBER} | grep -A1 -E '{pattern}'"
    )
    proc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, text=True)
    objects: dict[int, list[dict]] = {}
    line1 = None
    assert proc.stdout is not None
    for raw in proc.stdout:
        line = raw.rstrip("\n").rstrip("\\")
        if line.startswith("1 ") and len(line) >= 60:
            line1 = line
        elif line.startswith("2 ") and line1 is not None and len(line) >= 63:
            try:
                norad = int(line1[2:7])
                intl = line1[9:17].strip()
                epoch = epoch_to_datetime(int(line1[18:20]), float(line1[20:32]))
                inc = float(line[8:16])
                ecc = float("0." + line[26:33].strip())
                mean_motion = float(line[52:63])
            except ValueError:
                line1 = None
                continue
            a_km = semi_major_axis_er(mean_motion, ecc, inc) * EARTH_RADIUS_KM
            objects.setdefault(norad, []).append({
                "intl": intl,
                "epoch": epoch,
                "perigee": a_km * (1.0 - ecc) - EARTH_RADIUS_KM,
                "apogee": a_km * (1.0 + ecc) - EARTH_RADIUS_KM,
            })
            line1 = None
    proc.wait()
    for rows in objects.values():
        rows.sort(key=lambda row: row["epoch"])
    return objects


def select_on_grid(rows: list[dict], grid: list[datetime], tolerance_hours: float) -> list[list]:
    """Thin one object's element sets by SELECTION, never by interpolation.

    For each grid time the nearest real element set within ``tolerance_hours`` is
    kept, carrying its own true epoch. Grid times with nothing near them yield
    nothing, so a gap in the catalogue stays a gap on the chart instead of being
    bridged by a straight line the archive never supported.
    """
    if not rows:
        return []
    tolerance = timedelta(hours=tolerance_hours)
    start = grid[0]
    samples: list[list] = []
    taken: set[int] = set()
    index = 0
    for moment in grid:
        while index + 1 < len(rows) and rows[index + 1]["epoch"] <= moment:
            index += 1
        candidates = [index, min(index + 1, len(rows) - 1)]
        best = min(candidates, key=lambda i: abs(rows[i]["epoch"] - moment))
        if abs(rows[best]["epoch"] - moment) > tolerance or best in taken:
            continue
        taken.add(best)
        row = rows[best]
        samples.append([
            round((row["epoch"] - start).total_seconds() / 3600.0, 3),
            round(row["perigee"], 1),
            round(row["apogee"], 1),
        ])
    return samples


def build_grid(start: datetime, end: datetime) -> tuple[list[datetime], float]:
    """Three-hourly through the crisis fortnight, then daily through the climb-out.

    The decay happens over about ten days and the recovery over about ten weeks,
    so a single cadence either loses the event or bloats the artifact. The break
    is at the point where every object that is going to reenter already has.
    """
    grid: list[datetime] = []
    dense_until = start + timedelta(days=16)
    moment = start
    while moment <= dense_until:
        grid.append(moment)
        moment += timedelta(hours=3)
    while moment <= end:
        grid.append(moment)
        moment += timedelta(days=1)
    return grid, 12.0


def fetch_kp_window(start: datetime, end: datetime) -> dict:
    """GFZ Potsdam Kp and ap for the window. Cached; one request per index."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = f"{start:%Y%m%d}-{end:%Y%m%d}"
    cache = CACHE_DIR / f"gfz-kp-{stamp}.json"
    if cache.is_file():
        return json.loads(cache.read_text())
    out: dict = {}
    for index in ("Kp", "ap"):
        url = (
            f"{GFZ_KP_URL}?start={start:%Y-%m-%dT%H:%M:%S}Z"
            f"&end={end:%Y-%m-%dT%H:%M:%S}Z&index={index}"
        )
        with urllib.request.urlopen(url, timeout=60) as response:
            payload = json.loads(response.read())
        out.setdefault("datetime", payload["datetime"])
        out[index] = payload[index]
    cache.write_text(json.dumps(out))
    return out


def build_starlink_replay() -> dict:
    objects = extract_launch_elsets()
    if not objects:
        raise SystemExit("no 2022-010 element sets found in the local archive")

    start = datetime(2022, 2, 3, 0, 0, tzinfo=timezone.utc)
    # Thirty days. The whole event -- insertion, storm, every loss, and enough
    # of the climb-out to show where the survivors went -- happens inside the
    # first four weeks. A longer window spent two thirds of the picture's width
    # on three lines drifting quietly upward, which pushed the part that
    # matters into the left quarter of the frame.
    end = datetime(2022, 3, 5, 0, 0, tzinfo=timezone.utc)
    grid, tolerance = build_grid(start, end)

    # An object counts as reentered when the catalogue stops producing element
    # sets for it inside the storm window. This is the catalogue's own statement
    # that it no longer has the object, not an inference from altitude, and the
    # cutoff sits three weeks after the last decay stops so nothing borderline
    # is being sorted by a threshold that happens to fall between two traces.
    reentry_cutoff = datetime(2022, 3, 1, tzinfo=timezone.utc)

    entries = []
    for norad, rows in sorted(objects.items()):
        samples = select_on_grid(rows, grid, tolerance)
        if len(samples) < 2:
            continue
        last_epoch = rows[-1]["epoch"]
        reentered = last_epoch < reentry_cutoff
        entries.append({
            "norad": norad,
            "intl": rows[0]["intl"],
            "outcome": "lost" if reentered else "raised",
            "elsetCount": len(rows),
            "firstEpoch": rows[0]["epoch"].strftime("%Y-%m-%dT%H:%M:%SZ"),
            "lastEpoch": last_epoch.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "lastPerigeeKm": round(rows[-1]["perigee"], 1),
            "samples": samples,
        })

    lost = [entry for entry in entries if entry["outcome"] == "lost"]
    raised = [entry for entry in entries if entry["outcome"] == "raised"]

    # The driver strip runs the full width of the chart, so the index window
    # matches the replay window rather than just the storm. A flat Kp trace
    # either side of the disturbance is part of the point being made.
    kp = fetch_kp_window(start, end + timedelta(days=1))
    driver_hours = [
        round((datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ")
               .replace(tzinfo=timezone.utc) - start).total_seconds() / 3600.0, 3)
        for stamp in kp["datetime"]
    ]

    return {
        "kind": "orbit-decay",
        "status": "observed",
        "title": "Every catalogued member of one launch, drawn from its own element sets",
        "startsAt": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "endsAt": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "axis": {"label": "Altitude", "unit": "km", "min": 120, "max": 460},
        "objects": entries,
        "counts": {
            "catalogued": len(entries),
            "lost": len(lost),
            "raised": len(raised),
            "launched": 49,
            "publiclyReportedLost": 38,
        },
        "driver": {
            "label": "Kp",
            "source": "GFZ Potsdam",
            "hours": driver_hours,
            "kp": kp["Kp"],
            "ap": kp["ap"],
            # The peak over the FIRST FORTNIGHT, not over the whole 45-day
            # chart. A larger storm happens in March, well after every loss,
            # and quoting that number as "the storm that did this" would be
            # wrong by a month.
            "peakKp": max(
                value for hour, value in zip(driver_hours, kp["Kp"])
                if 0.0 <= hour <= 336.0
            ),
            "peakKpWindow": "2022-02-03 to 2022-02-17",
        },
        "provenance": {
            "elements": "space-track.org bulk element-set archive for 2022, held on bigmem",
            "elementsNote": (
                "Sean's own space-track account, downloaded once under space-track's "
                "instruction to hold the history locally. The series is republished as "
                "a derived altitude curve, not as element sets."
            ),
            "driver": "GFZ Potsdam Kp/ap index service",
            "method": (
                "Perigee and apogee are derived from the Brouwer mean elements in each "
                "published element set: the Kozai mean motion is converted to the "
                "semi-major axis with the SGP4 initialisation correction, then a(1-e) "
                "and a(1+e) are taken against a spherical Earth of radius 6378.137 km."
            ),
            "catalogueStart": (
                "The catalogue publishes no element sets for the eleven survivors "
                "before 8 February, so their traces begin there rather than at "
                "launch. The ten that were lost are catalogued from 5-6 February."
            ),
            "limitation": (
                "These are derived orbital altitudes, not measured ranges to the "
                "spacecraft, and the catalogue carries 21 of the 49 objects launched. "
                "The 28 not shown reentered before a permanent catalogue number was "
                "assigned. No point is interpolated: each is one real element set, "
                "selected as the nearest to a grid time, carrying its own epoch."
            ),
        },
    }



# ---------------------------------------------------------------------------
# Kyoto Dst, shared by two of the events
# ---------------------------------------------------------------------------
KYOTO_DST = "https://wdc.kugi.kyoto-u.ac.jp/dst_final/{year:04d}{month:02d}/index.html"
KYOTO_MISSING = 9999


def _kyoto_dst(year: int, month: int) -> list[tuple[float, int]]:
    """One month of final hourly Dst as (unix seconds, nT). Cached on disk.

    The page is fixed-width text and SPLITTING IT ON WHITESPACE IS WRONG. The
    field is four characters, so three consecutive values below -999 print as
    `-353-341-335` with no separator, and a naive split silently returns 22
    values for a day instead of 24 -- shifting every later hour. Great storms
    are exactly the months where that happens, which is to say every month this
    project cares about. A regular expression for a signed integer recovers the
    right values because the minus sign itself is the delimiter, and the count
    is then asserted rather than assumed.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache = CACHE_DIR / f"kyoto-dst-{year:04d}{month:02d}.json"
    if cache.is_file():
        rows = json.loads(cache.read_text())
        return [(row[0], row[1]) for row in rows]

    url = KYOTO_DST.format(year=year, month=month)
    with urllib.request.urlopen(url, timeout=90) as response:
        page = response.read().decode("latin-1")
    if "Hourly Equatorial Dst Values" not in page:
        raise SystemExit(f"{url} did not return a Kyoto Dst table")

    out: list[tuple[float, int]] = []
    for line in page.splitlines():
        numbers = re.findall(r"-?\d+", line)
        if len(numbers) != 25:
            continue
        day = int(numbers[0])
        if not 1 <= day <= 31:
            continue
        try:
            midnight = datetime(year, month, day, tzinfo=timezone.utc).timestamp()
        except ValueError:
            continue
        for hour, text in enumerate(numbers[1:]):
            value = int(text)
            if value == KYOTO_MISSING:
                continue
            out.append((midnight + hour * 3600.0, value))
    days = {datetime.fromtimestamp(stamp, timezone.utc).day for stamp, _ in out}
    if len(out) < 24 * (len(days) or 1) * 0.9 or not days:
        raise SystemExit(f"{url} parsed to {len(out)} hours over {len(days)} days")
    out.sort()
    cache.write_text(json.dumps(out))
    return out

# ---------------------------------------------------------------------------
# gannon-2024: the atmosphere swells, and a spacecraft feels it
# ---------------------------------------------------------------------------
"""
WHY THIS EVENT GETS A REPLAY AT ALL

`docs/gannon-storm-module-design.md` §7 already established that this project
holds the one thing the Gannon storm needs: 96 hourly WAM-IPE frames, 9-12 May
2024, on /mnt/d. What it did not have was a MEASUREMENT to put beside them, and
§V5 could only cite published accelerometer densities rather than draw them.

It can now. ESA/TU Delft publish Swarm-C's thermospheric density -- derived from
the spacecraft's own calibrated non-gravitational accelerations, which is to say
from the drag it actually felt -- as a free CC-BY daily product at ten-second
cadence. So this replay draws two things on one axis:

    MEASURED   what Swarm-C felt at its own altitude, orbit-averaged.
    MODEL      what NOAA's operational forecast said the density was at the
               SAME place, altitude and time, sampled along the same track.

Those are the same physical quantity at the same point, so putting them on one
axis is a fair comparison rather than a rhetorical one. They do not agree, and
the disagreement is the lesson: the forecast under-called the peak and then held
the atmosphere inflated for about a day after the spacecraft says it had
recovered. For anyone screening conjunctions off a drag model, that is the whole
point of the picture.

THE MODEL CURVE'S OWN UNCERTAINTY, WHICH IS NOT OPTIONAL

§7.2 measured something that must travel with any WAM number: WAM runs four
cycles a day, most valid times are covered by more than one cycle, and through
the storm the cycles disagree with each other -- by 2.5x on 12 May 12Z. The
archive's 96 frames are all "freshest covering cycle, lead 0-5 h". The 52
`cross-cycle-probes` frames are the PREVIOUS cycle's forecast for those same
valid times. Both are drawn: the fresh cycle as the line, the six-hour-old
forecast as a whisker at every cycle boundary. The design document forbids
averaging them, because the average is a trajectory neither run produced.

THE CANONICAL DEFINITION, TAKEN FROM THE DESIGN DOCUMENT AND NOT REINVENTED

§7.3 fixes it: area-weighted by cos(lat); cells with den <= 0 excluded; freshest
covering cycle; quiet baseline = the 24-hour mean of 2024-05-09; peak searched
over the full window. On that definition the global mean at 400 km peaks at
2.63x and undershoots to 0.64x, and this module reproduces both or fails loudly.
"""

WAM_DIR = Path("/mnt/d/space-explorer/wam-gannon")
WAM_PROBE_DIR = WAM_DIR / "cross-cycle-probes"
SWARM_DIR = Path("/mnt/d/space-explorer/swarm-gannon")

# Swarm's density product carries CDF's 1e31 fill. It arrives as an ordinary
# float, exactly like SuperMAG's 999999, and an unguarded mean over one fill
# value produces a 1e28 kg/m^3 thermosphere. Anything outside this window is
# not a density.
SWARM_DENSITY_MIN = 1e-16
SWARM_DENSITY_MAX = 1e-9

# One Swarm orbit, to the nearest ten seconds. The along-track density swings by
# a factor of several within a single orbit purely from latitude and local time,
# so a raw ten-second series says nothing about the storm. Averaging over
# exactly one revolution removes that structure and leaves the thing the storm
# changed. 5,640 s is Swarm's period at this altitude.
SWARM_ORBIT_SECONDS = 5640

# The map: 8 degrees of longitude by 6 of latitude, every second hour. Native is
# 4 x 2 degrees hourly, which is 12 times the bytes for a field whose storm
# signal is thousands of kilometres across.
MAP_LON_STRIDE = 2
MAP_LAT_STRIDE = 3
MAP_HOUR_STRIDE = 2
# log2(ratio) from -1.5 to +3.5 in 254 steps: 0.35x to 11.3x. 255 means the
# cell had no valid density -- WAM's polar rows are zero-filled and a zero is
# not a thin atmosphere.
MAP_LOG2_MIN = -1.5
MAP_LOG2_SPAN = 5.0
MAP_NODATA = 255
# The ratio is quantised onto 32 levels rather than 256, and this is the single
# biggest lever on the artifact's size. MEASURED on the built payload: 256
# levels cost 50.3 kB gzipped, 64 cost 26.9, 32 cost 17.2 -- a two-thirds saving
# for a step of 0.16 octaves, about twelve per cent in density, on a field the
# renderer then bilinearly interpolates across a twentyfold upscale. Coarsening
# the grid or the cadence instead would have cost real resolution for less: half
# the frames only saves half, and half the longitudes saves less than that.
MAP_LEVELS = 32

EARTH_KM = 6378.137


def _valid_time(path: Path) -> datetime:
    """The valid UTC in a WAM filename. The files carry no global attributes."""
    stamp = re.search(r"(\d{8})_(\d{6})\.nc$", path.name)
    if not stamp:
        raise SystemExit(f"cannot read a valid time from {path.name}")
    return datetime.strptime(stamp.group(1) + stamp.group(2), "%Y%m%d%H%M%S").replace(
        tzinfo=timezone.utc
    )


def _cycle_of(path: Path) -> int:
    """Which of the four daily cycles produced this frame, from the filename."""
    stamp = re.search(r"\.t(\d{2})z\.", path.name)
    if not stamp:
        raise SystemExit(f"cannot read a cycle from {path.name}")
    return int(stamp.group(1))


def _wam_frames() -> list[tuple[datetime, int, Path]]:
    frames = [(_valid_time(p), _cycle_of(p), p) for p in sorted(WAM_DIR.glob("*.nc"))]
    if len(frames) != 96:
        raise SystemExit(f"expected 96 WAM frames, found {len(frames)}")
    frames.sort()
    return frames


def _probe_frames() -> dict[datetime, Path]:
    """The previous cycle's forecast for a valid time, keyed by that valid time.

    `chk_06_20240511_120000.nc` is the 06Z cycle's +6 h frame for 11 May 12Z,
    whose freshest cycle is 12Z. Where two probes exist for one valid time the
    OLDER cycle is kept, because the widest honest spread is the one worth
    showing and hiding the wider of two disagreements would be the exact move
    this module exists to refuse.
    """
    out: dict[datetime, tuple[int, Path]] = {}
    for path in sorted(WAM_PROBE_DIR.glob("chk_*.nc")):
        cycle = int(path.name.split("_")[1])
        when = _valid_time(path)
        held = out.get(when)
        if held is None or cycle < held[0]:
            out[when] = (cycle, path)
    return {when: path for when, (_, path) in out.items()}


def _read_swarm() -> dict:
    """Swarm-C density, altitude and position for the storm week, fill removed."""
    import cdflib  # noqa: PLC0415 -- only this event needs a CDF reader

    times: list = []
    fields: dict[str, list] = {"density": [], "altitude": [], "latitude": [], "longitude": []}
    archives = sorted(SWARM_DIR.glob("SW_OPER_DNSCACC_2__*.ZIP"))
    if not archives:
        raise SystemExit(f"no Swarm density archives under {SWARM_DIR}")
    for archive in archives:
        with zipfile.ZipFile(archive) as bundle:
            member = next(name for name in bundle.namelist() if name.endswith(".cdf"))
            scratch = CACHE_DIR / "_swarm.cdf"
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            scratch.write_bytes(bundle.read(member))
        handle = cdflib.CDF(str(scratch))
        times.append(np.array(cdflib.cdfepoch.to_datetime(handle.varget("time"))))
        for name in fields:
            fields[name].append(np.array(handle.varget(name), dtype=float))
    stamps = np.concatenate(times)
    order = np.argsort(stamps)
    stamps = stamps[order]
    joined = {name: np.concatenate(parts)[order] for name, parts in fields.items()}
    density = joined["density"]
    good = (density > SWARM_DENSITY_MIN) & (density < SWARM_DENSITY_MAX)
    return {
        "seconds": stamps.astype("datetime64[s]").astype(np.int64),
        "good": good,
        **joined,
    }


def _sample_wam(den, hlevs, lats, lons, lat_deg, lon_deg, alt_km) -> float:
    """Trilinear read of one WAM frame at a point, wrapping in longitude.

    Nearest-neighbour would quantise the model curve onto a 4-degree grid and
    put a staircase in a comparison whose whole subject is a smooth difference.
    """
    level = int(np.clip(np.searchsorted(hlevs, alt_km) - 1, 0, len(hlevs) - 2))
    fh = (alt_km - hlevs[level]) / (hlevs[level + 1] - hlevs[level])
    row = int(np.clip(np.searchsorted(lats, lat_deg) - 1, 0, len(lats) - 2))
    fa = (lat_deg - lats[row]) / (lats[row + 1] - lats[row])
    step = float(lons[1] - lons[0])
    east = lon_deg % 360.0
    col = int(np.clip(np.searchsorted(lons, east) - 1, 0, len(lons) - 1))
    col_next = (col + 1) % len(lons)
    fo = (east - lons[col]) / step
    value = 0.0
    for dh, wh in ((0, 1.0 - fh), (1, fh)):
        for da, wa in ((0, 1.0 - fa), (1, fa)):
            value += wh * wa * (
                (1.0 - fo) * den[level + dh, row + da, col]
                + fo * den[level + dh, row + da, col_next]
            )
    return float(value)

def build_gannon_replay() -> dict:
    import netCDF4  # noqa: PLC0415 -- only this event reads WAM's netCDF

    frames = _wam_frames()
    probes = _probe_frames()
    start = datetime(2024, 5, 8, tzinfo=timezone.utc)
    end = datetime(2024, 5, 13, tzinfo=timezone.utc)

    first = netCDF4.Dataset(frames[0][2])
    hlevs = np.array(first.variables["hlevs"][:], dtype=float)
    lats = np.array(first.variables["lat"][:], dtype=float)
    lons = np.array(first.variables["lon"][:], dtype=float)
    first.close()
    level_400 = int(np.argmin(np.abs(hlevs - 400.0)))
    weight = np.cos(np.radians(lats))

    swarm = _read_swarm()
    half_orbit = SWARM_ORBIT_SECONDS // 2

    # ---- pass one: read every frame once ---------------------------------
    # 96 frames at 4.4 MB each. Each is opened exactly once and everything that
    # needs it -- the global mean, the map tile, the along-track sample -- is
    # taken in that one pass.
    global_mean: dict[datetime, float] = {}
    along_track: dict[datetime, float] = {}
    measured: dict[datetime, tuple[float, float, int]] = {}
    tiles: dict[datetime, np.ndarray] = {}

    for when, _cycle, path in frames:
        dataset = netCDF4.Dataset(path)
        den = np.array(dataset.variables["den"][0], dtype=float)
        dataset.close()

        plane = den[level_400]
        valid = plane > 0.0
        # cos(lat) weighting, and the zero-filled polar rows excluded rather
        # than averaged in as a very thin atmosphere.
        rows = np.where(valid.any(axis=1), np.sum(plane * valid, axis=1) / np.maximum(valid.sum(axis=1), 1), np.nan)
        keep = np.isfinite(rows)
        global_mean[when] = float(np.sum(rows[keep] * weight[keep]) / np.sum(weight[keep]))
        tiles[when] = plane[::MAP_LAT_STRIDE, ::MAP_LON_STRIDE].copy()

        centre = np.datetime64(when.replace(tzinfo=None)).astype("datetime64[s]").astype(np.int64)
        window = (
            swarm["good"]
            & (swarm["seconds"] >= centre - half_orbit)
            & (swarm["seconds"] <= centre + half_orbit)
        )
        count = int(window.sum())
        if count < 300:
            continue
        index = np.where(window)[0]
        measured[when] = (
            float(swarm["density"][index].mean()),
            float(swarm["altitude"][index].mean() / 1000.0),
            count,
        )
        # Every tenth sample: at ten-second cadence a full orbit is 564 points
        # and the model field it is being read out of is 4 degrees wide, so
        # fifty-odd reads already resolve everything the grid can express.
        thinned = index[::10]
        along_track[when] = float(np.mean([
            _sample_wam(den, hlevs, lats, lons,
                        swarm["latitude"][i], swarm["longitude"][i],
                        swarm["altitude"][i] / 1000.0)
            for i in thinned
        ]))

    # ---- baselines --------------------------------------------------------
    # The design document's rule, not a new one: the quiet baseline is the
    # 24-hour mean of 9 May, the last full day before the shock.
    quiet_day = [when for when in global_mean if when.date() == date(2024, 5, 9)]
    if len(quiet_day) != 24:
        raise SystemExit(f"quiet baseline wants 24 frames on 9 May, has {len(quiet_day)}")
    model_baseline = float(np.mean([global_mean[when] for when in quiet_day]))

    # Swarm's own baseline is the same 24 hours, so both ratios are against the
    # same piece of wall clock even though they are different quantities.
    swarm_quiet = [measured[when][0] for when in sorted(measured) if when.date() == date(2024, 5, 9)]
    track_quiet = [along_track[when] for when in sorted(along_track) if when.date() == date(2024, 5, 9)]
    swarm_baseline = float(np.mean(swarm_quiet))
    track_baseline = float(np.mean(track_quiet))

    def hours(when: datetime) -> float:
        return round((when - start).total_seconds() / 3600.0, 3)

    # ---- the two curves ---------------------------------------------------
    measured_series = [
        [hours(when), round(measured[when][0] / swarm_baseline, 4), round(measured[when][0] * 1e13, 4)]
        for when in sorted(measured)
    ]
    model_series = [
        [hours(when), round(along_track[when] / track_baseline, 4), round(along_track[when] * 1e13, 4)]
        for when in sorted(along_track)
    ]

    # ---- the whiskers: WAM against its own six-hour-old forecast -----------
    spread = []
    for when in sorted(probes):
        if when not in along_track:
            continue
        dataset = netCDF4.Dataset(probes[when])
        den = np.array(dataset.variables["den"][0], dtype=float)
        dataset.close()
        centre = np.datetime64(when.replace(tzinfo=None)).astype("datetime64[s]").astype(np.int64)
        window = (
            swarm["good"]
            & (swarm["seconds"] >= centre - half_orbit)
            & (swarm["seconds"] <= centre + half_orbit)
        )
        index = np.where(window)[0][::10]
        if len(index) < 30:
            continue
        stale = float(np.mean([
            _sample_wam(den, hlevs, lats, lons,
                        swarm["latitude"][i], swarm["longitude"][i],
                        swarm["altitude"][i] / 1000.0)
            for i in index
        ]))
        spread.append([hours(when), round(stale / track_baseline, 4)])

    # ---- the map ----------------------------------------------------------
    # Per-cell ratio against the same cell's 9 May mean, so the diurnal bulge
    # -- which is not the storm -- divides out and what is left is what the
    # storm did.
    quiet_tile = np.zeros_like(tiles[quiet_day[0]])
    quiet_count = np.zeros_like(quiet_tile)
    for when in quiet_day:
        tile = tiles[when]
        quiet_tile += np.where(tile > 0, tile, 0.0)
        quiet_count += (tile > 0).astype(float)
    quiet_tile = np.where(quiet_count > 0, quiet_tile / np.maximum(quiet_count, 1), np.nan)

    map_times = [when for index, when in enumerate(sorted(tiles)) if index % MAP_HOUR_STRIDE == 0]
    encoded_frames = []
    for when in map_times:
        tile = tiles[when]
        with np.errstate(divide="ignore", invalid="ignore"):
            ratio = np.where((tile > 0) & np.isfinite(quiet_tile) & (quiet_tile > 0), tile / quiet_tile, np.nan)
            level = (np.log2(ratio) - MAP_LOG2_MIN) / MAP_LOG2_SPAN
        step = 254.0 / (MAP_LEVELS - 1)
        byte = np.where(
            np.isfinite(level),
            np.round(np.clip(np.round(level * (MAP_LEVELS - 1)), 0, MAP_LEVELS - 1) * step),
            MAP_NODATA,
        ).astype(np.uint8)
        encoded_frames.append(base64.b64encode(byte.tobytes()).decode("ascii"))

    peak_when = max(global_mean, key=lambda when: global_mean[when])
    trough_when = min(global_mean, key=lambda when: global_mean[when])
    peak_measured = max(measured, key=lambda when: measured[when][0])

    driver = _supermag_driver(start, end)

    return {
        "kind": "thermosphere-inflation",
        "status": "measured-and-model",
        "title": "The air at 480 km, as a spacecraft felt it and as the forecast called it",
        "startsAt": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "endsAt": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "axis": {"label": "Density, relative to the quiet day", "min": 0.3, "max": 5.2},
        "series": {
            "measured": {
                "label": "Swarm-C, measured",
                "detail": f"accelerometer-derived density at {np.mean([m[1] for m in measured.values()]):.0f} km, averaged over one revolution",
                "evidence": "measurement",
                "baselineSi": swarm_baseline,
                "points": measured_series,
            },
            "model": {
                "label": "WAM-IPE, forecast",
                "detail": "the same model field read at Swarm-C's own latitude, longitude and altitude",
                "evidence": "model",
                "baselineSi": track_baseline,
                "points": model_series,
                "spread": spread,
            },
        },
        "map": {
            "label": "Density at 400 km, relative to the same place on the quiet day",
            "evidence": "model",
            "lonCount": int(len(lons[::MAP_LON_STRIDE])),
            "latCount": int(len(lats[::MAP_LAT_STRIDE])),
            "lonStart": float(lons[0]),
            "lonStep": float(lons[1] - lons[0]) * MAP_LON_STRIDE,
            "latStart": float(lats[0]),
            "latStep": float(lats[1] - lats[0]) * MAP_LAT_STRIDE,
            "log2Min": MAP_LOG2_MIN,
            "log2Span": MAP_LOG2_SPAN,
            "noData": MAP_NODATA,
            "hours": [hours(when) for when in map_times],
            "frames": encoded_frames,
        },
        "driver": driver,
        "findings": {
            "globalPeak": round(global_mean[peak_when] / model_baseline, 3),
            "globalPeakAt": peak_when.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "globalTrough": round(global_mean[trough_when] / model_baseline, 3),
            "globalTroughAt": trough_when.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "measuredPeak": round(measured[peak_measured][0] / swarm_baseline, 3),
            "measuredPeakAt": peak_measured.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "measuredAltitudeKm": round(float(np.mean([m[1] for m in measured.values()])), 1),
            "worstSpread": _worst_spread(model_series, spread),
            "worstSpreadAt": _worst_spread_at(model_series, spread, start),
        },
        "provenance": {
            "measured": (
                "Swarm-C thermospheric density (ESA product DNSCACC_2_, processed by TU Delft), "
                "derived from the spacecraft's calibrated non-gravitational accelerations at "
                "ten-second cadence and averaged here over one full revolution."
            ),
            "model": (
                "NOAA SWPC Whole Atmosphere Model-Ionosphere Plasmasphere Electrodynamics "
                "(WAM-IPE) Forecast System, fixed-height density product, archived hourly."
            ),
            "cycleRule": (
                "Every model frame is the freshest cycle covering its valid time, at zero to "
                "five hours of lead. WAM runs four cycles a day; the whisker at each six-hour "
                "boundary is the PREVIOUS cycle's forecast for that same moment. The two are "
                "never averaged, because the average is a trajectory neither run produced."
            ),
            "driver": driver["citation"],
            "method": (
                "Both curves are the same quantity at the same point: mass density, sampled at "
                "Swarm-C's latitude, longitude and altitude, averaged over the same revolution. "
                "The model field is read trilinearly from WAM's 4 x 2 degree, 10 km grid. Each "
                "curve is divided by its own 9 May mean, so the comparison is of shape and "
                "amplitude and does not depend on either source's absolute calibration."
            ),
            "limitation": (
                "The model curve is a forecast, not an analysis: WAM-IPE assimilates no "
                "thermospheric density, so nothing here corrects it toward the spacecraft. The "
                "measured curve is one spacecraft on one orbit plane at two fixed local times, "
                "not a global average. The map is model output at a single altitude and carries "
                "no measurement anywhere in it."
            ),
            "drag": (
                "Atmospheric drag is proportional to density, so the ratio on this axis is also "
                "the ratio of the drag force on anything at that altitude. Turning that into a "
                "decay rate needs a ballistic coefficient this page does not have, so the ratio "
                "is quoted and the metres per day are not."
            ),
        },
    }


def _spread_pairs(model_series: list, spread: list) -> list[tuple[float, float, float]]:
    """(hour, fresh cycle, previous cycle) wherever both exist for one moment."""
    fresh = {row[0]: row[1] for row in model_series}
    return [(hour, fresh[hour], stale) for hour, stale in spread if hour in fresh]


def _worst_spread(model_series: list, spread: list) -> float | None:
    pairs = _spread_pairs(model_series, spread)
    if not pairs:
        return None
    return round(max(max(a / b, b / a) for _, a, b in pairs), 2)


def _worst_spread_at(model_series: list, spread: list, start: datetime) -> str | None:
    pairs = _spread_pairs(model_series, spread)
    if not pairs:
        return None
    hour = max(pairs, key=lambda row: max(row[1] / row[2], row[2] / row[1]))[0]
    return (start + timedelta(hours=hour)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _supermag_driver(start: datetime, end: datetime) -> dict:
    """The auroral electrojet, decimated for plotting and never redistributed.

    SuperMAG's own position, checked with JHU/APL and recorded in
    `ingest/supermag_ingest.py`, is that a derived VISUALISATION may be
    published with citation and the SERIES may not be redistributed. So this
    calls the module's `published_series()` -- which exists precisely to make
    the allowed thing the easy one -- twice: once at full cadence to find the
    true extremum, once decimated to what a chart can actually draw.
    """
    sys.path.insert(0, str(ROOT))
    from ingest.supermag_ingest import published_series  # noqa: PLC0415

    full = published_series(start, end, cadence_minutes=1)
    plotted = published_series(start, end, cadence_minutes=10)
    lows = [(row["t"], row["sml"]) for row in full["samples"] if row["sml"] is not None]
    peak_at, peak = min(lows, key=lambda row: row[1])
    points = [
        [round((datetime.strptime(row["t"], "%Y-%m-%dT%H:%M:%SZ")
                .replace(tzinfo=timezone.utc) - start).total_seconds() / 3600.0, 3),
         round(row["sml"], 1)]
        for row in plotted["samples"] if row["sml"] is not None
    ]
    return {
        "label": "SML",
        "name": "Westward auroral electrojet",
        "unit": "nT",
        "evidence": "measurement",
        "source": "SuperMAG (JHU/APL)",
        "points": points,
        "peak": round(peak, 1),
        "peakAt": peak_at,
        "citation": full["citation"],
        "usage": full["usage"],
    }

# ---------------------------------------------------------------------------
# halloween-2003: one flare, three arrivals, three clocks
# ---------------------------------------------------------------------------
"""
The single most operationally important fact about space weather is that it is
not one event. One eruption on the Sun sends three different things at Earth and
they arrive hours and days apart, so the warning you get, the thing you can do
about it, and the system that suffers are all different for each.

28 October 2003 is the clean case, because all three are large and all three are
measured by instruments whose archives are public and free:

    LIGHT       X-rays, 0.1-0.8 nm, GOES-12 XRS, one-minute.
                Travels at c. Nothing warns you; it arrives with the news.
    PARTICLES   protons above 10 MeV, GOES-11 EPS, five-minute.
                A fraction of c, guided along the interplanetary field. Tens of
                minutes to hours.
    FIELD       the ring current, as Dst, Kyoto WDC, hourly.
                The CME's own bulk speed. Most of a day, then days to recover.

THE TIME AXIS IS LOGARITHMIC, AND THAT IS THE WHOLE DESIGN

Eight minutes and three days on one linear axis puts the flare inside the width
of the axis line. On a logarithmic axis from one minute to five days every
arrival is legible at its own scale and the SEPARATIONS are what the eye reads,
which is the lesson. The zero of that axis is the moment the flare's light left
the Sun, which is not observed: it is the observed X-ray peak minus 499 seconds,
the light travel time over one astronomical unit. That subtraction is stated on
the page rather than folded in silently, and it is the only derived time here.

WHAT IS NOT CLAIMED

The CME's departure is not drawn. Associating a particular CME with a particular
flare and back-projecting its launch needs coronagraph data this project does not
hold, and the answer would be a fit rather than a measurement. What IS drawn is
when the field arrived, taken from Dst crossing -50 nT, which is a threshold on a
published index and nothing more.
"""

GOES_DIR = Path("/mnt/d/space-explorer/halloween-2003")
NCEI_GOES = "https://www.ncei.noaa.gov/data/goes-space-environment-monitor/access/avg"

# 0.1-0.8 nm is the channel every flare class is defined on: X1 is 1e-4 W/m^2.
HALLOWEEN_XRS = ("2003", "10", "goes12", "g12_xrs_1m_20031001_20031031.nc")
HALLOWEEN_EPS = ("2003", "10", "goes11", "g11_eps_5m_20031001_20031031.nc")

LIGHT_SECONDS_1AU = 499.005          # IAU 2012: 1 au / c, to the millisecond.
# The flare has begun when the 0.1-0.8 nm flux has doubled over the quiet
# active-region background. Any onset rule is a choice, so it is stated, and
# this one is checkable: it puts the start of the 28 October flare at 09:52 UT
# against NOAA's published 09:51, which is one minute of agreement on a
# one-minute instrument.
ONSET_MULTIPLE = 2.0
PFU_ALERT = 10.0                     # NOAA's S1 threshold, protons > 10 MeV.
DST_STORM = -50.0                    # where Kyoto's own scale calls it a storm.


def _goes_file(year: str, month: str, craft: str, name: str,
               cache_dir: Path = GOES_DIR) -> Path:
    """One NCEI GOES month, cached on /mnt/d. Fetched once, never in a loop.

    `cache_dir` defaults to the Halloween directory the first caller created.
    A second flare event passes its own so that two events never share a
    directory and one cannot silently serve the other a file for the wrong
    month if a name ever collides.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / name
    if path.is_file() and path.stat().st_size > 100_000:
        return path
    url = f"{NCEI_GOES}/{year}/{month}/{craft}/netcdf/{name}"
    with urllib.request.urlopen(url, timeout=180) as response:
        body = response.read()
    # NCEI answers 200 with an HTML error page for a wrong path, which is the
    # trap `ingest/supermag_ingest.py` documents for a different service. A
    # netCDF file starts with CDF or the HDF5 signature; an apology does not.
    if not (body.startswith(b"CDF") or body.startswith(b"\x89HDF")):
        raise SystemExit(f"{url} returned {len(body)} bytes that are not netCDF")
    path.write_bytes(body)
    return path


def _goes_series(path: Path, variable: str) -> tuple[np.ndarray, np.ndarray]:
    import netCDF4  # noqa: PLC0415

    dataset = netCDF4.Dataset(path)
    stamps = np.array(dataset.variables["time_tag"][:], dtype=float) / 1000.0
    values = np.array(dataset.variables[variable][:], dtype=float)
    dataset.close()
    # GOES writes its own fill as a large negative number; a negative irradiance
    # is not a small one.
    values[values <= 0] = np.nan
    return stamps, values


def _log_thin(seconds: np.ndarray, values: np.ndarray, t0: float,
              target: int = 420) -> list[list[float]]:
    """Thin onto a log-uniform time grid by SELECTING real samples.

    The chart's x-axis is logarithmic, so a linear decimation spends almost
    every point in the last day and leaves the flare with three. This keeps the
    nearest REAL sample to each of `target` log-spaced times, carrying its own
    timestamp, and drops a grid time with nothing near it rather than inventing
    one. No value on the chart is an average of two measurements.
    """
    minutes = (seconds - t0) / 60.0
    keep = np.isfinite(values) & (minutes > 0.2)
    minutes, values = minutes[keep], values[keep]
    if minutes.size == 0:
        return []
    grid = np.logspace(np.log10(0.5), np.log10(minutes.max()), target)
    out: list[list[float]] = []
    taken: set[int] = set()
    for want in grid:
        index = int(np.argmin(np.abs(minutes - want)))
        if index in taken:
            continue
        # Half a decade of tolerance: past the flare the cadence is coarse
        # relative to the log spacing and a strict window would empty the tail.
        if abs(minutes[index] - want) > max(want * 0.5, 1.0):
            continue
        taken.add(index)
        out.append([round(float(minutes[index]), 3), float(values[index])])
    out.sort()
    return out


def _flare_clock(xrs_seconds: np.ndarray, xrs: np.ndarray,
                 day: datetime, span_days: float = 2.0) -> dict:
    """Peak, onset and light-departure for one flare, from the X-ray lane alone.

    Extracted from `build_halloween_replay` when a second flare event arrived,
    so that both charts anchor their axis by exactly the same rule rather than
    by two copies of it that could drift apart. The rule is stated in
    `ONSET_MULTIPLE` above and it is checkable: it puts the 28 October 2003
    flare at 09:52 UT against NOAA's 09:51, and the 14 July 2000 flare at
    10:05 UT against NOAA's 10:03.

    Anchoring on the ONSET rather than the peak is deliberate and was paid for
    once. Anchored on the peak, the X-ray lane opens at maximum because the
    whole rise sits at negative time on a logarithmic axis, and the
    light-travel mark then lands on a flat line where it means nothing.
    """
    start = day.timestamp()
    window = (xrs_seconds >= start) & (xrs_seconds < start + span_days * 86400)
    peak_index = int(np.nanargmax(np.where(window, xrs, np.nan)))
    flare_peak = xrs_seconds[peak_index]
    background = float(np.nanmedian(
        xrs[(xrs_seconds > flare_peak - 4 * 3600) & (xrs_seconds < flare_peak - 3 * 3600)]))
    threshold = background * ONSET_MULTIPLE
    onset_index = peak_index
    while onset_index > 0 and (np.isnan(xrs[onset_index]) or xrs[onset_index] > threshold):
        onset_index -= 1
    return {
        "peakIndex": peak_index,
        "peakAt": flare_peak,
        "peakFlux": xrs[peak_index],
        "background": background,
        "onsetAt": xrs_seconds[onset_index],
        "departure": xrs_seconds[onset_index] - LIGHT_SECONDS_1AU,
    }


def build_halloween_replay() -> dict:
    xrs_path = _goes_file(*HALLOWEEN_XRS)
    eps_path = _goes_file(*HALLOWEEN_EPS)
    xrs_seconds, xrs = _goes_series(xrs_path, "xl")
    eps_seconds, protons = _goes_series(eps_path, "p3_flux_ic")

    # The axis is anchored on the flare ONSET minus the light travel time; the
    # rule and the reason it is not the peak now live in `_flare_clock`, which
    # the Bastille Day chart shares so the two cannot drift apart.
    clock = _flare_clock(xrs_seconds, xrs, datetime(2003, 10, 28, tzinfo=timezone.utc))
    flare_peak = clock["peakAt"]
    flare_class = clock["peakFlux"]
    flare_onset = clock["onsetAt"]
    departure = clock["departure"]

    dst = _kyoto_dst(2003, 10) + _kyoto_dst(2003, 11)
    dst_points = [
        [round((stamp - departure) / 60.0, 2), value]
        for stamp, value in dst
        if departure < stamp <= departure + 5 * 86400
    ]

    proton_points = _log_thin(eps_seconds, protons, departure)
    xray_points = _log_thin(xrs_seconds, xrs, departure)

    # ---- the three arrivals, each from its own instrument ------------------
    proton_window = (eps_seconds > flare_onset) & (eps_seconds < flare_onset + 2 * 86400)
    alert = np.where(proton_window & (protons > PFU_ALERT))[0]
    proton_alert = eps_seconds[alert[0]] if alert.size else None
    proton_peak_index = int(np.nanargmax(np.where(proton_window, protons, np.nan)))

    storm = [stamp for stamp, value in dst if stamp > flare_onset and value <= DST_STORM]
    dst_min_at, dst_min = min(
        ((stamp, value) for stamp, value in dst if flare_onset < stamp < flare_onset + 5 * 86400),
        key=lambda row: row[1],
    )

    def since(stamp: float) -> float:
        return round((stamp - departure) / 60.0, 2)

    arrivals = [
        {
            "id": "light",
            "label": "Light",
            "detail": "the X-ray flux lifts off the background",
            "minutes": since(flare_onset),
            "value": f"{LIGHT_SECONDS_1AU / 60:.1f} min · one au ÷ c",
            "note": (
                "This one is not a warning. The X-rays and the news of the flare are the same "
                "photons, and the ionosphere below them starts absorbing HF the moment they "
                "land. The mark sits where the lane lifts off because that is what subtracting "
                "the light travel time means — it is arithmetic, not a measurement."
            ),
        },
        {
            "id": "flarePeak",
            "label": "Flare peak",
            "detail": "X-rays, 0.1-0.8 nm",
            "minutes": since(flare_peak),
            "value": f"{_flare_class(flare_class)} · {flare_class:.2e} W m⁻²",
            "note": (
                "The whole of the radio blackout is over before anything else has arrived. "
                "By the time an operator has finished diagnosing the HF outage, the particles "
                "are still on their way."
            ),
        },
    ]
    if proton_alert is not None:
        arrivals.append({
            "id": "protons",
            "label": "Particles",
            "detail": "protons above 10 MeV",
            "minutes": since(proton_alert),
            "value": f"crosses {PFU_ALERT:.0f} pfu",
            "note": (
                "Fast enough to be an hour behind the light and slow enough that the hour is "
                "usable. This is the window in which a polar route is turned and an EVA is held."
            ),
        })
    arrivals.append({
        "id": "protonPeak",
        "label": "Particle peak",
        "detail": "protons above 10 MeV",
        "minutes": since(eps_seconds[proton_peak_index]),
        "value": f"{protons[proton_peak_index]:,.0f} pfu",
        "note": "An S4 event on NOAA's scale, and still the fourth largest of the space age.",
    })
    if storm:
        arrivals.append({
            "id": "field",
            "label": "Field",
            "detail": "Dst crosses −50 nT",
            "minutes": since(storm[0]),
            "value": "storm main phase",
            "note": (
                "The cloud itself, arriving with its magnetic field. Nineteen hours is an "
                "unusually fast transit; the ordinary figure is two to three days."
            ),
        })
    arrivals.append({
        "id": "fieldMin",
        "label": "Field minimum",
        "detail": "Dst",
        "minutes": since(dst_min_at),
        "value": f"{dst_min:.0f} nT",
        "note": (
            "Two and a half days after the light, and the recovery takes a week. The three "
            "clocks never resynchronise."
        ),
    })

    return {
        "kind": "three-clocks",
        "status": "observed",
        "title": "One eruption, three arrivals, three clocks",
        "originAt": datetime.fromtimestamp(departure, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "originLabel": "Light leaves the Sun",
        "minMinutes": 0.5,
        "maxMinutes": 5 * 24 * 60,
        "lanes": [
            {
                "id": "xray",
                "label": "X-ray irradiance",
                "unit": "W m⁻²",
                "scale": "log",
                "min": 1e-7,
                "max": 3e-3,
                "instrument": "GOES-12 XRS, 0.1–0.8 nm, one-minute",
                "evidence": "measurement",
                "points": xray_points,
                "guides": [{"value": 1e-4, "label": "X1"}, {"value": 1e-5, "label": "M1"}],
            },
            {
                "id": "protons",
                "label": "Protons > 10 MeV",
                "unit": "pfu",
                "scale": "log",
                "min": 0.1,
                "max": 1e5,
                "instrument": "GOES-11 EPS, five-minute",
                "evidence": "measurement",
                "points": proton_points,
                "guides": [{"value": 10, "label": "S1"}, {"value": 10_000, "label": "S4"}],
            },
            {
                "id": "dst",
                "label": "Dst",
                "unit": "nT",
                "scale": "linear",
                "min": -400,
                "max": 60,
                "instrument": "Kyoto WDC, final, hourly",
                "evidence": "measurement",
                "points": dst_points,
                "guides": [{"value": -50, "label": "storm"}, {"value": -250, "label": "severe"}],
            },
        ],
        "arrivals": arrivals,
        "provenance": {
            "xray": "GOES-12 X-Ray Sensor, one-minute averages, NOAA NCEI (US Government, public domain).",
            "protons": "GOES-11 Energetic Particle Sensor, five-minute averages, corrected integral channel above 10 MeV, NOAA NCEI.",
            "dst": (
                "Final Dst, World Data Centre for Geomagnetism, Kyoto. Kyoto's terms permit "
                "non-commercial use; this site carries no advertising and no paid tier."
            ),
            "origin": (
                "The zero of the axis is the observed X-ray ONSET minus 499.005 seconds, the "
                "light travel time over one astronomical unit. Onset is the last minute before "
                "the peak at which the 0.1-0.8 nm flux was still below twice the quiet "
                "active-region background, which places it at 09:52 UT against NOAA's published "
                "09:51 for this flare. The 499 seconds is the only quantity on this chart that "
                "was calculated rather than observed, and the light mark therefore sits where "
                "the X-ray lane lifts off by construction rather than by coincidence."
            ),
            "method": (
                "Every plotted point is one real sample, selected as the nearest to a "
                "log-spaced grid time and carrying its own timestamp. Nothing is averaged "
                "between two measurements and a grid time with no sample near it draws nothing."
            ),
            "limitation": (
                "Three instruments, three cadences, one axis. The X-ray sensor saturates in the "
                "largest flares of this same active region — the 4 November event ran off the "
                "top of this channel and its class is an extrapolation, which is why the 28 "
                "October flare and not the famous one is drawn here. The proton flux is measured "
                "at geostationary altitude, inside the magnetosphere, and is not the flux at the "
                "top of the atmosphere. No coronagraph data is held, so no CME departure is drawn."
            ),
        },
    }


def _flare_class(watts: float) -> str:
    """GOES flare class from 0.1-0.8 nm irradiance: X1 is 1e-4 W/m^2."""
    for letter, floor in (("X", 1e-4), ("M", 1e-5), ("C", 1e-6), ("B", 1e-7)):
        if watts >= floor:
            return f"{letter}{watts / floor:.1f}"
    return f"A{watts / 1e-8:.1f}"

# ---------------------------------------------------------------------------
# bastille-2000: the same three clocks, running at completely different rates
# ---------------------------------------------------------------------------
"""
14 July 2000 is the SECOND event on this page drawn as three clocks, and it is
here because the first one is not a template.

Read on its own, the Halloween chart invites the wrong generalisation -- that
the gaps between light, particles and field are a property of the Sun, roughly
the same every time, something an operator could learn once. They are not. They
depend on where on the disk the eruption happened, on how well the
interplanetary field connected Earth to the acceleration site, and on how fast
the cloud was. The spread between two great events is enormous:

                                 28 Oct 2003        14 Jul 2000
    light -> protons at S1       2 h 22 min         40 min
    peak proton flux             29,500 pfu         24,000 pfu
    light -> deepest Dst         60 h               38 h
    depth of the storm           -383 nT            -300 nT

Every number in both columns is measured, by the same two instrument classes,
out of the same two public archives, and the two charts are drawn by the same
code on the same axis. Putting them next to each other is the only way this
page can say "the warning interval is not a constant" and have the reader
check it on the page itself.

Bastille Day is also the cleaner instrument story of the two. Both the X-rays
and the protons come from GOES-8, NOAA's primary spacecraft that day, so the
two upper lanes are one instrument package rather than two spacecraft assumed
to agree. The archived 0.1-0.8 nm peak is 5.75e-4 W/m^2, which is X5.7 -- the
class NOAA published for this flare, recovered from the file rather than copied
from a headline.

WHY THIS ONE DOES NOT USE THE "Dst CROSSES -50" MARK

The Halloween chart marks the field's arrival with the first hour Dst went
below -50 nT. Applied here that rule fires at 15 July 13:00 UT, seven hours
before the cloud arrived, on a small separate disturbance that recovered inside
the hour. Rather than tune the threshold per event -- which would make the rule
mean whatever each event needed it to mean -- this event marks two EXTREMA,
which need no threshold at all:

    the sudden commencement   the largest Dst in the twelve hours before the
                              minimum. The index goes POSITIVE (+7 nT at 15:00
                              UT on 15 July) because the shock squeezes the
                              magnetosphere inward before anything drains it.
    the minimum               -300 nT, 16 July 00:00 UT.

Both are stated with the window they were taken over, and neither can drift
with a constant somebody chose.
"""

BASTILLE_DIR = Path("/mnt/d/space-explorer/bastille-2000")
# GOES-8 was NOAA's primary spacecraft in July 2000 and carries both lanes.
BASTILLE_XRS = ("2000", "07", "goes08", "g08_xrs_1m_20000701_20000731.nc")
BASTILLE_EPS = ("2000", "07", "goes08", "g08_eps_5m_20000701_20000731.nc")
BASTILLE_DAY = datetime(2000, 7, 14, tzinfo=timezone.utc)
# The window the sudden commencement is taken as the maximum over, ending at
# the minimum. Twelve hours is long enough to contain the shock at any transit
# speed this storm could have had, and short enough that it cannot reach back
# into the quiet field of the previous day.
SC_WINDOW_HOURS = 12.0


def build_bastille_replay() -> dict:
    xrs_seconds, xrs = _goes_series(
        _goes_file(*BASTILLE_XRS, cache_dir=BASTILLE_DIR), "xl")
    eps_seconds, protons = _goes_series(
        _goes_file(*BASTILLE_EPS, cache_dir=BASTILLE_DIR), "p3_flux_ic")

    clock = _flare_clock(xrs_seconds, xrs, BASTILLE_DAY)
    flare_onset = clock["onsetAt"]
    flare_peak = clock["peakAt"]
    flare_class = clock["peakFlux"]
    departure = clock["departure"]

    dst = _kyoto_dst(2000, 7)
    dst_points = [
        [round((stamp - departure) / 60.0, 2), value]
        for stamp, value in dst
        if departure < stamp <= departure + 5 * 86400
    ]

    proton_points = _log_thin(eps_seconds, protons, departure)
    xray_points = _log_thin(xrs_seconds, xrs, departure)

    proton_window = (eps_seconds > flare_onset) & (eps_seconds < flare_onset + 2 * 86400)
    alert = np.where(proton_window & (protons > PFU_ALERT))[0]
    proton_alert = eps_seconds[alert[0]] if alert.size else None
    proton_peak_index = int(np.nanargmax(np.where(proton_window, protons, np.nan)))

    # ---- the two Dst extrema, each over a window that is printed -----------
    storm_window = [row for row in dst
                    if flare_onset < row[0] < flare_onset + 5 * 86400]
    dst_min_at, dst_min = min(storm_window, key=lambda row: row[1])
    commencement = [row for row in storm_window
                    if dst_min_at - SC_WINDOW_HOURS * 3600 <= row[0] <= dst_min_at]
    sc_at, sc_value = max(commencement, key=lambda row: row[1])

    def since(stamp: float) -> float:
        return round((stamp - departure) / 60.0, 2)

    arrivals = [
        {
            "id": "light",
            "label": "Light",
            "detail": "the X-ray flux lifts off the background",
            "minutes": since(flare_onset),
            "value": f"{LIGHT_SECONDS_1AU / 60:.1f} min · one au ÷ c",
            "note": (
                "The same arithmetic as the Halloween chart and the same answer, because the "
                "speed of light does not care which storm it is. This is the only one of the "
                "six marks below whose position was fixed before the event happened."
            ),
        },
        {
            "id": "flarePeak",
            "label": "Flare peak",
            "detail": "X-rays, 0.1-0.8 nm",
            "minutes": since(flare_peak),
            "value": f"{_flare_class(flare_class)} · {flare_class:.2e} W m⁻²",
            "note": (
                "A third the size of the Halloween flare, and it did more damage sooner. "
                "Active region 9077 sat almost exactly at the centre of the visible disk, "
                "which is the worst geometry for Earth: radiation, particles and cloud were "
                "all aimed down the same line at us."
            ),
        },
    ]
    if proton_alert is not None:
        arrivals.append({
            "id": "protons",
            "label": "Particles",
            "detail": "protons above 10 MeV",
            "minutes": since(proton_alert),
            "value": f"crosses {PFU_ALERT:.0f} pfu",
            "note": (
                "Forty minutes after the light, while the flare was still brightening. On "
                "the Halloween chart the same threshold is crossed 2 h 22 min after the "
                "light. That gap between the two events is the whole of the usable warning: "
                "here there is barely any, and the operator learns about the flare and is "
                "already standing in the radiation storm."
            ),
        })
    arrivals.append({
        "id": "protonPeak",
        "label": "Particle peak",
        "detail": "protons above 10 MeV",
        "minutes": since(eps_seconds[proton_peak_index]),
        "value": f"{protons[proton_peak_index]:,.0f} pfu",
        "note": (
            "An S4 event on NOAA's scale. It is the flux, not the flare class, that decides "
            "whether a polar route is turned or an EVA is held — and the flux peaked more "
            "than a day after the flare itself was over."
        ),
    })
    arrivals.append({
        "id": "commencement",
        "label": "Shock",
        "detail": f"largest Dst in the {SC_WINDOW_HOURS:.0f} h before the minimum",
        "minutes": since(sc_at),
        "value": f"{sc_value:+d} nT",
        "note": (
            "The index goes the WRONG WAY first. A shock arriving at the magnetosphere "
            "compresses it, and a compressed field measured from the ground is a STRONGER "
            "field, so Dst rises before it falls. Anyone watching one number for 'is it bad "
            "yet' sees it improve at the moment the cloud lands."
        ),
    })
    arrivals.append({
        "id": "fieldMin",
        "label": "Field minimum",
        "detail": "Dst",
        "minutes": since(dst_min_at),
        "value": f"{dst_min:.0f} nT",
        "note": (
            "Thirty-eight hours after the light. The Halloween storm took sixty hours to "
            "reach its own floor. Same three clocks, twenty-two hours of difference in when "
            "the last one strikes, which is why the interval is something you measure every "
            "time rather than something you look up."
        ),
    })

    return {
        "kind": "three-clocks",
        "status": "observed",
        "title": "The same three arrivals, on a completely different schedule",
        "originAt": datetime.fromtimestamp(departure, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "originLabel": "Light leaves the Sun",
        "minMinutes": 0.5,
        "maxMinutes": 5 * 24 * 60,
        "lanes": [
            {
                "id": "xray",
                "label": "X-ray irradiance",
                "unit": "W m⁻²",
                "scale": "log",
                "min": 1e-7,
                "max": 3e-3,
                "instrument": "GOES-8 XRS, 0.1–0.8 nm, one-minute",
                "evidence": "measurement",
                "points": xray_points,
                "guides": [{"value": 1e-4, "label": "X1"}, {"value": 1e-5, "label": "M1"}],
            },
            {
                "id": "protons",
                "label": "Protons > 10 MeV",
                "unit": "pfu",
                "scale": "log",
                "min": 0.1,
                "max": 1e5,
                "instrument": "GOES-8 EPS, five-minute",
                "evidence": "measurement",
                "points": proton_points,
                "guides": [{"value": 10, "label": "S1"}, {"value": 10_000, "label": "S4"}],
            },
            {
                "id": "dst",
                "label": "Dst",
                "unit": "nT",
                "scale": "linear",
                "min": -350,
                "max": 60,
                "instrument": "Kyoto WDC, final, hourly",
                "evidence": "measurement",
                "points": dst_points,
                "guides": [{"value": -50, "label": "storm"}, {"value": -250, "label": "severe"}],
            },
        ],
        "arrivals": arrivals,
        "provenance": {
            "xray": (
                "GOES-8 X-Ray Sensor, one-minute averages, NOAA NCEI (US Government, public "
                "domain). GOES-8 was NOAA's primary spacecraft in July 2000. The archived peak "
                "is 5.75e-4 W m⁻²; this page prints X5.8 because it rounds, and NOAA published "
                "X5.7 because the class is conventionally truncated. One digit of convention on "
                "one measurement — the number in the file is the same either way."
            ),
            "protons": (
                "GOES-8 Energetic Particle Sensor, five-minute averages, corrected integral "
                "channel above 10 MeV, NOAA NCEI. The same spacecraft as the X-ray lane above "
                "it, which is one fewer cross-calibration to take on trust."
            ),
            "dst": (
                "Final Dst, World Data Centre for Geomagnetism, Kyoto. Kyoto's terms permit "
                "non-commercial use; this site carries no advertising and no paid tier."
            ),
            "origin": (
                "The zero of the axis is the observed X-ray ONSET minus 499.005 seconds, the "
                "light travel time over one astronomical unit. Onset is the last minute before "
                "the peak at which the 0.1-0.8 nm flux was still below twice the quiet "
                "active-region background, which places it at 10:05 UT against NOAA's published "
                "10:03 for this flare — two minutes of agreement on a one-minute instrument."
            ),
            "method": (
                "Every plotted point is one real sample, selected as the nearest to a "
                "log-spaced grid time and carrying its own timestamp. Nothing is averaged "
                "between two measurements and a grid time with no sample near it draws nothing."
            ),
            "limitation": (
                "The two Dst marks here are extrema over stated windows, not threshold "
                "crossings. The 'crosses −50 nT' rule the Halloween chart uses fires seven "
                "hours early on this storm, on a small separate disturbance that recovered "
                "inside the hour, so it is not used and no per-event threshold was invented to "
                "replace it. As on the other chart, the proton flux is measured at "
                "geostationary altitude, inside the magnetosphere, and is not the flux at the "
                "top of the atmosphere; no coronagraph data is held, so no CME departure is "
                "drawn."
            ),
        },
    }


# ---------------------------------------------------------------------------
# quebec-1989: the rate, the index, and the mechanism
# ---------------------------------------------------------------------------
"""
The first draft of this event drew Kyoto's hourly Dst and said, correctly, that
the project held no one-minute magnetogram for March 1989. That was wrong, and
finding out it was wrong changed the event.

**Ottawa's magnetic observatory ran through the whole storm at one-minute
cadence, the record is definitive, and it is free.** OTT sits at 45.4 N, about
200 km from Montreal and on the same side of the continent as the transmission
corridor that failed. The World Data Centre for Geomagnetism in Edinburgh serves
it as plain CSV with no authentication, and Natural Resources Canada -- who
operate the observatory -- serve the same samples over FDSN.

That matters because **Dst is not the quantity that breaks a power grid.** Dst is
an hourly average of the ring current: a measure of how FAR the field has moved.
What drives a geomagnetically induced current is dB/dt: how FAST it is moving,
because Faraday's law has a time derivative in it and an hourly mean has had the
derivative averaged out of it. A site that teaches space weather with Dst alone
teaches the wrong index.

WHAT THE DATA SAYS, WHICH IS BETTER THAN THE STORY

At Ottawa the horizontal field moved 1.4 nT in a typical quiet minute. In the
minute Hydro-Quebec separated -- 07:44 UT on 13 March 1989, 02:44 in Montreal --
it moved 435. The two minutes either side were 154 and 224. Meanwhile Dst stood
at -143 nT, less than a quarter of the way to the -589 it would not reach for
another seventeen hours.

AND WHAT IT DOES NOT SAY, WHICH THE PAGE MUST ALSO CARRY

435 nT/min is not the largest excursion of the storm. Ottawa saw 546 nT/min at
21:51 that evening and 556 nT/min at 01:21 the next morning, and the lights did
not go out again. So the honest lesson is not "big dB/dt breaks grids". It is
that dB/dt is the right quantity to watch and it is still not sufficient: what
happened at La Grande depended on the rate a thousand kilometres north of this
magnetometer, on the geology under the lines, and on what state the network was
already in. The chart draws the whole storm rather than the blackout minute
alone, so a reader can see that for themselves rather than take it on trust.
"""

QUEBEC_BLACKOUT = datetime(1989, 3, 13, 7, 44, tzinfo=timezone.utc)   # 02:44 EST

# The mechanism animation and the narration that runs over it. The script is the
# same file `tools/narrate.py` rendered from, and the section boundaries are the
# ones Manim actually produced, so the transcript on the page is what the video
# says at the second it says it rather than an approximation typed afterwards.
MECHANISM_STEM = "quebec-1989-gic-chain"
MECHANISM_SCRIPT = ROOT / "narration" / "quebec-mechanism.json"
MECHANISM_MARKS = ROOT / "media" / f"{MECHANISM_STEM}.marks.json"

WDC_MINUTE = (
    "https://wdcapi.bgs.ac.uk/data/text-data/minute/{code}"
    "?start_dt={start:%Y-%m-%dT%H:%M:%S}&end_dt={end:%Y-%m-%dT%H:%M:%S}"
    "&file_format=csv&orientation=original&months_per_page=1&page=1"
)
# The observatory's own fill. A 99999 nT horizontal field is not a large one.
WDC_FILL = 90_000.0


def _wdc_minute_series(code: str, start: datetime, end: datetime) -> list[tuple[float, float, float]]:
    """Definitive one-minute X and Y from the WDC, as (unix seconds, X, Y).

    Cached, so the service is asked once per window ever. The check is on
    CONTENT and not on the status code, because this class of archive answers
    200 with a well-formed header over a body of fill values -- INTERMAGNET's
    own GIN does exactly that for this date, and a consumer that trusts the
    header publishes a storm made entirely of 99999.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache = CACHE_DIR / f"wdc-{code}-{start:%Y%m%d}-{end:%Y%m%d}.json"
    if cache.is_file():
        return [tuple(row) for row in json.loads(cache.read_text())]

    url = WDC_MINUTE.format(code=code, start=start, end=end)
    with urllib.request.urlopen(url, timeout=180) as response:
        body = response.read().decode("utf-8")
    if "data quality: definitive" not in body or "cadence: PT1M" not in body:
        raise SystemExit(f"{url} did not return definitive one-minute data")

    rows: list[tuple[float, float, float]] = []
    lines = [line for line in body.splitlines() if line and not line.startswith("#")]
    header = lines[0].split(",")
    xi, yi, ti = header.index("X"), header.index("Y"), header.index("datetime")
    for line in lines[1:]:
        parts = line.split(",")
        try:
            x, y = float(parts[xi]), float(parts[yi])
            when = datetime.strptime(parts[ti], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        except (ValueError, IndexError):
            continue
        if abs(x) > WDC_FILL or abs(y) > WDC_FILL:
            continue
        rows.append((when.timestamp(), x, y))
    expected = int((end - start).total_seconds() // 60)
    if len(rows) < expected * 0.9:
        raise SystemExit(f"{code} returned {len(rows)} usable minutes of {expected}")
    cache.write_text(json.dumps(rows))
    return rows


def _mechanism_video() -> dict:
    """The mechanism animation's manifest, assembled from the two files that made it."""
    marks = json.loads(MECHANISM_MARKS.read_text())
    lines = {row["id"]: row["text"] for row in json.loads(MECHANISM_SCRIPT.read_text())["lines"]}
    return {
        "stem": MECHANISM_STEM,
        "durationSeconds": marks["durationSeconds"],
        "width": marks["width"],
        "height": marks["height"],
        "caption": (
            "The chain, drawn: a field that moves, an electric field in the rock, a current up "
            "a transformer neutral, a core saturating on half of every cycle, the harmonics that "
            "makes, and the relays that answered them. Rendered with Manim; narrated in Sean's "
            "own voice from a written script."
        ),
        "transcript": [
            {"at": round(section["start"], 1), "text": lines[section["id"]]}
            for section in marks["sections"] if section["id"] in lines
        ],
    }


def build_quebec_replay() -> dict:
    start = datetime(1989, 3, 12, 12, tzinfo=timezone.utc)
    end = datetime(1989, 3, 15, tzinfo=timezone.utc)

    magnetogram = _wdc_minute_series("ott", datetime(1989, 3, 12), datetime(1989, 3, 16))
    stamps = np.array([row[0] for row in magnetogram])
    north = np.array([row[1] for row in magnetogram])
    east = np.array([row[2] for row in magnetogram])

    # |dB_H/dt| from consecutive minutes. Both horizontal components together,
    # because the induced electric field does not care which way the horizontal
    # field swung -- only how fast. A sample whose predecessor is not exactly
    # one minute earlier yields nothing rather than a rate over an unknown gap.
    step = np.diff(stamps)
    rate = np.hypot(np.diff(north), np.diff(east))
    rate_at = stamps[1:]
    contiguous = np.isclose(step, 60.0)

    window = (rate_at >= start.timestamp()) & (rate_at <= end.timestamp()) & contiguous
    minutes_from_start = np.round((rate_at[window] - start.timestamp()) / 60.0).astype(int)
    values: list[float | None] = [None] * (int((end - start).total_seconds() // 60) + 1)
    for slot, value in zip(minutes_from_start, rate[window]):
        if 0 <= slot < len(values):
            values[slot] = round(float(value), 1)

    quiet = rate[contiguous & (rate_at < datetime(1989, 3, 13).timestamp())]
    peak_index = int(np.argmax(np.where(window, rate, -1.0)))
    blackout_index = int(np.argmin(np.abs(rate_at - QUEBEC_BLACKOUT.timestamp())))

    dst = [row for row in _kyoto_dst(1989, 3)
           if start.timestamp() <= row[0] <= end.timestamp()]
    if len(dst) < 50:
        raise SystemExit(f"March 1989 Dst returned {len(dst)} hours in the window")
    minimum_at, minimum = min(dst, key=lambda row: row[1])
    at_blackout = min(dst, key=lambda row: abs(row[0] - QUEBEC_BLACKOUT.timestamp()))

    def hours(stamp: float) -> float:
        return round((stamp - start.timestamp()) / 3600.0, 4)

    return {
        "kind": "gic-chain",
        **({"video": _mechanism_video()} if MECHANISM_MARKS.is_file() else {}),
        "status": "measured-and-mechanism",
        "title": "The rate, not the depth: Ottawa's magnetometer in the minute the lights went out",
        "startsAt": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "endsAt": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "rate": {
            "label": "Rate of change of the horizontal field",
            "short": "|dB/dt|",
            "unit": "nT/min",
            "evidence": "measurement",
            "station": "Ottawa (OTT) · 45.40°N 75.55°W · about 200 km from Montréal",
            "instrument": "definitive one-minute magnetogram, World Data Centre for Geomagnetism (Edinburgh)",
            "max": 600,
            "stepMinutes": 1,
            "values": values,
            "quietMedian": round(float(np.median(quiet)), 2),
            "peak": round(float(rate[peak_index]), 1),
            "peakAt": datetime.fromtimestamp(rate_at[peak_index], timezone.utc)
                              .strftime("%Y-%m-%dT%H:%M:%SZ"),
            "atBlackout": round(float(rate[blackout_index]), 1),
        },
        "index": {
            "label": "Dst",
            "unit": "nT",
            "evidence": "measurement",
            "instrument": "World Data Centre for Geomagnetism, Kyoto — final hourly Dst",
            "min": -620,
            "max": 60,
            "points": [[hours(stamp), value] for stamp, value in dst],
        },
        "marks": [
            {
                "id": "blackout",
                "hours": hours(QUEBEC_BLACKOUT.timestamp()),
                "at": QUEBEC_BLACKOUT.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "label": "Hydro-Québec separates",
                "detail": "02:44 EST · six million people · ninety-two seconds",
                "value": f"{rate[blackout_index]:.0f} nT/min · Dst {at_blackout[1]} nT",
            },
            {
                "id": "minimum",
                "hours": hours(minimum_at),
                "at": datetime.fromtimestamp(minimum_at, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "label": "Dst minimum",
                "detail": "the deepest hourly Dst in the index's record",
                "value": f"{minimum} nT",
            },
        ],
        "gapHours": round((minimum_at - QUEBEC_BLACKOUT.timestamp()) / 3600.0, 1),
        "ratioAtBlackout": round(float(rate[blackout_index]) / float(np.median(quiet))),
        "provenance": {
            "rate": (
                "Ottawa magnetic observatory, operated by the Geological Survey of Canada "
                "(Natural Resources Canada). Definitive one-minute X and Y, obtained from the "
                "World Data Centre for Geomagnetism, Edinburgh. Published here only as a "
                "derived rate curve, on the same non-commercial footing this project already "
                "applies to INTERMAGNET and to Kyoto: fine for a non-profit teaching site, and "
                "the first thing to re-source if that ever changes."
            ),
            "index": (
                "Final hourly Dst, World Data Centre for Geomagnetism, Kyoto. Non-commercial "
                "use; this site carries no advertising and no paid tier."
            ),
            "method": (
                "Each point is the magnitude of the change in the horizontal field between two "
                "consecutive one-minute samples, √(ΔX² + ΔY²). Nothing is smoothed, and a minute "
                "whose predecessor is missing draws nothing rather than a rate across a gap."
            ),
            "blackoutTime": (
                "02:44:17 EST on 13 March 1989, from Hydro-Québec's account of the separation "
                "and the subsequent North American Electric Reliability Council review. It is a "
                "reported wall-clock time, not something measured here."
            ),
            "limitation": (
                "This is the rate at Ottawa, not at La Grande, and the currents that mattered "
                "flowed a thousand kilometres further north through very old, very resistive "
                "Canadian Shield rock. It is also not the largest rate of the storm: Ottawa saw "
                "556 nT/min the following morning with no second collapse. Rate is the right "
                "quantity to watch and it is not by itself sufficient — the state of the network "
                "when the rate arrives matters as much. Nothing here is a measurement of a "
                "geomagnetically induced current, because none was being made in Québec that night."
            ),
            "animation": (
                "The mechanism panel is a drawn schematic, rendered with Manim from the sequence "
                "described in the published post-mortems. It is a labelled diagram of a causal "
                "chain, not a recording of one, and no part of it is footage."
            ),
        },
    }

# ---------------------------------------------------------------------------
# stpatricks-2015: a fast wind does nothing until the field turns south
# ---------------------------------------------------------------------------
"""
The four events before this one all begin at the Sun. Every one of them teaches
something about what LEAVES the Sun and how long it takes to get here. None of
them can answer the question a reader is left holding afterwards, which is the
one an operator actually has to answer:

    the cloud has arrived. Is this going to be a storm or not?

Speed does not tell you. On 17 March 2015 the solar wind was still speeding up
for a full day AFTER the storm had bottomed out and begun to recover. The
quantity that decides it is the direction of the magnetic field the cloud is
carrying. Earth's own field points north at the equator; when the arriving
field points SOUTH the two are antiparallel at the dayside and can reconnect,
which is what opens the magnetosphere and lets energy in. When it points north
a fast, dense, otherwise identical cloud slides past and does comparatively
little.

This chart is three measured lanes on one linear UTC axis:

    Bz (GSM)     the arriving field's north-south component. Negative is south.
    flow speed   how fast the cloud is going.
    SYM/H        the one-minute ring-current index: how much energy is now
                 stored in the current that circles the Earth. Down is a storm.

and four marks, each of which is an EXTREMUM of a measured series rather than a
threshold somebody chose:

    the shock          SYM/H reaches its MAXIMUM, +67 nT. The index goes UP.
    the field's floor  Bz reaches its minimum, about -26 nT.
    the storm's floor  SYM/H reaches its minimum, about -234 nT, nine and a
                       half hours after Bz did.
    peak speed         the wind is at its fastest a DAY after the storm bottomed.

That last pair is the whole lesson, and it is why this event earns a picture
none of the other five have: cause and effect are visibly separated, in the
right order, with the wrong-looking quantity peaking last.

WHY THE STORM READS -234 HERE AND -223 IN THE LITERATURE

SYM/H is a one-minute index and Dst is an hourly one. They are built from
different station sets and they are not the same number. Papers on this storm
quote Dst = -223 nT; the one-minute SYM/H minimum in the same window is -234 nT.
Both are correct and the page says which one it is drawing.

WHAT OMNI IS, AND THE ONE DERIVED QUANTITY ON THE CHART

The top two lanes are not measured at Earth. They are measured by spacecraft at
the first Lagrange point, about 1.5 million km upstream, and NASA's OMNI
service TIME-SHIFTS each one-minute average forward to the nose of Earth's bow
shock so that it lines up with what the magnetosphere actually met. That shift
is a calculation -- typically half an hour to an hour at these speeds -- and it
is the only derived quantity on the chart. It is stated on the page rather than
folded in silently, exactly as the light-travel subtraction is on the two flare
charts.

THINNING WITHOUT HIDING ANYTHING

One minute over two and a half days is 3,600 samples a lane, which is more than
the artifact should carry three times over. The published record is one bin of
ten minutes: the real sample NEAREST the bin centre, plus the smallest and the
largest real sample inside that bin. Nothing is averaged, so the drawn line is
a measurement; and because the band carries the true range, the thinning cannot
hide an excursion the way plain decimation would. A bin whose samples are all
fill produces no record at all, so a hole in the archive stays a hole -- and
this window has real ones: 39 of the 360 speed bins and 22 of the 360 field
bins have no valid sample at all, and are drawn as breaks in the stroke.
"""

OMNI_DIR = Path("/mnt/d/space-explorer/omni-hro")
OMNI_URL = ("https://spdf.gsfc.nasa.gov/pub/data/omni/high_res_omni/"
            "monthly_1min/omni_min{year:04d}{month:02d}.asc")

# Column positions in the High Resolution OMNI 1-minute record, counted from
# zero, as published at
# https://spdf.gsfc.nasa.gov/pub/data/omni/high_res_omni/hroformat.txt
# The file is fixed-width, but every field is separated by at least one space
# in this product, so it is split on whitespace and the field COUNT is
# ASSERTED. A short record means the format changed, and a format change must
# stop the build rather than shift every column silently by one.
OMNI_FIELDS = 46
OMNI_YEAR, OMNI_DOY, OMNI_HOUR, OMNI_MINUTE = 0, 1, 2, 3
OMNI_BZ_GSM = 18
OMNI_SPEED = 21
OMNI_SYMH = 41
# OMNI's fill values, one per field width. A fill is not a small number, and
# 9999.99 nT of southward field would be the largest ever recorded.
OMNI_FILL = {OMNI_BZ_GSM: 9999.0, OMNI_SPEED: 99999.0, OMNI_SYMH: 99999.0}

STPATRICK_START = datetime(2015, 3, 16, 12, tzinfo=timezone.utc)
STPATRICK_END = datetime(2015, 3, 19, 0, tzinfo=timezone.utc)
STPATRICK_BIN_MINUTES = 10


def _omni_month(year: int, month: int) -> tuple[np.ndarray, dict[int, np.ndarray]]:
    """One month of OMNI 1-minute records, cached on /mnt/d.

    Returns the record times as unix seconds and the three columns this page
    draws, with OMNI's fill values already turned into NaN so that a gap can
    only ever propagate as a gap.
    """
    OMNI_DIR.mkdir(parents=True, exist_ok=True)
    path = OMNI_DIR / f"omni_min{year:04d}{month:02d}.asc"
    if not path.is_file() or path.stat().st_size < 1_000_000:
        url = OMNI_URL.format(year=year, month=month)
        with urllib.request.urlopen(url, timeout=600) as response:
            body = response.read()
        # SPDF answers 200 with an HTML directory page for a path that does not
        # exist -- the same "200 is not success" trap the Kyoto and INTERMAGNET
        # readers in this file already carry.
        if body.lstrip()[:1].isdigit() is False:
            raise SystemExit(f"{url} returned {len(body)} bytes that do not begin a data record")
        path.write_bytes(body)

    rows: list[list[str]] = []
    for line in path.read_text().splitlines():
        fields = line.split()
        if not fields:
            continue
        if len(fields) != OMNI_FIELDS:
            raise SystemExit(
                f"{path.name}: a record has {len(fields)} fields, expected {OMNI_FIELDS}; "
                "the HRO format has changed and every column index here is now suspect")
        rows.append(fields)
    table = np.array(rows, dtype=float)

    years = table[:, OMNI_YEAR].astype(int)
    if (years != years[0]).any():
        raise SystemExit(f"{path.name} spans more than one year")
    origin = datetime(int(years[0]), 1, 1, tzinfo=timezone.utc).timestamp()
    seconds = (origin
               + (table[:, OMNI_DOY] - 1) * 86400.0
               + table[:, OMNI_HOUR] * 3600.0
               + table[:, OMNI_MINUTE] * 60.0)

    columns: dict[int, np.ndarray] = {}
    for index, fill in OMNI_FILL.items():
        values = table[:, index].copy()
        values[np.abs(values) >= fill] = np.nan
        columns[index] = values
    return seconds, columns


def _tidy(value: float, decimals: int) -> float | int:
    """Round to a stated precision, and drop a trailing `.0` that costs bytes.

    This artifact is fetched EAGERLY by every visitor on first paint, so its
    size is a cost the whole site pays. `1005.0` and `67.0` are two wasted
    characters each and there are several thousand of them. The precision each
    lane is rounded to is far finer than one pixel of its own chart -- 0.1 nT
    on a lane 150 px tall spanning 60 nT is a hundredth of a pixel -- so this
    throws away nothing a reader could have seen.
    """
    rounded = round(float(value), decimals)
    return int(rounded) if rounded == int(rounded) else rounded


def _bin_extremes(seconds: np.ndarray, values: np.ndarray, start: float, end: float,
                  bin_seconds: float, decimals: int = 2) -> tuple[list[list[float]], int, int]:
    """Thin one-minute samples into bins without inventing a value.

    Each published record is

        [minutes from the window start, the real sample NEAREST the bin centre,
         the smallest real sample in the bin, the largest real sample in the bin]

    Nothing is averaged: the drawn line is a measurement carrying its own
    timestamp, and the band around it is the true range that plain decimation
    would have thrown away. A bin with no finite sample produces no record, so
    a hole in the archive stays a hole rather than being bridged.

    Returns the records, the number of empty bins, and the number of bins.
    """
    total = int(round((end - start) / bin_seconds))
    order = np.argsort(seconds)
    seconds, values = seconds[order], values[order]
    edges = np.searchsorted(seconds, [start + index * bin_seconds for index in range(total + 1)])
    out: list[list[float]] = []
    empty = 0
    for index in range(total):
        lo, hi = int(edges[index]), int(edges[index + 1])
        sample = values[lo:hi]
        stamps = seconds[lo:hi]
        good = np.isfinite(sample)
        if not good.any():
            empty += 1
            continue
        sample, stamps = sample[good], stamps[good]
        centre = start + (index + 0.5) * bin_seconds
        nearest = int(np.argmin(np.abs(stamps - centre)))
        out.append([
            _tidy((stamps[nearest] - start) / 60.0, 1),
            _tidy(sample[nearest], decimals),
            _tidy(sample.min(), decimals),
            _tidy(sample.max(), decimals),
        ])
    return out, empty, total


def _extreme(seconds: np.ndarray, values: np.ndarray, start: float, end: float,
             largest: bool) -> tuple[float, float]:
    """The single largest or smallest real sample in the window, and its time."""
    window = (seconds >= start) & (seconds < end) & np.isfinite(values)
    if not window.any():
        raise SystemExit("no finite samples in the window")
    picked = values.copy()
    picked[~window] = -np.inf if largest else np.inf
    index = int(np.argmax(picked) if largest else np.argmin(picked))
    return seconds[index], float(values[index])


def build_stpatrick_replay() -> dict:
    seconds, columns = _omni_month(2015, 3)
    start = STPATRICK_START.timestamp()
    end = STPATRICK_END.timestamp()
    bin_seconds = STPATRICK_BIN_MINUTES * 60.0
    span_minutes = int(round((end - start) / 60.0))

    bz = columns[OMNI_BZ_GSM]
    speed = columns[OMNI_SPEED]
    symh = columns[OMNI_SYMH]

    def stamp(at: float) -> str:
        return datetime.fromtimestamp(at, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def since(at: float) -> float:
        return round((at - start) / 60.0, 1)

    lanes = []
    # The last field is the precision each lane is published at, chosen so that
    # one unit of it is a fraction of a pixel on that lane's own chart.
    for identifier, label, unit, series, low, high, guides, instrument, decimals in (
        ("bz", "IMF Bz (GSM)", "nT", bz, -30.0, 30.0,
         [{"value": 0.0, "label": "north / south"}],
         "ACE and Wind at L1, one-minute, time-shifted to the bow shock nose by NASA OMNI", 1),
        ("speed", "Solar-wind speed", "km/s", speed, 250.0, 750.0,
         [{"value": 500.0, "label": "fast"}],
         "ACE and Wind plasma instruments, one-minute, same OMNI time shift", 0),
        ("symh", "SYM/H", "nT", symh, -260.0, 100.0,
         [{"value": 0.0, "label": "quiet"}, {"value": -200.0, "label": "severe"}],
         "SYM/H, one-minute, Kyoto WDC, carried in the OMNI record", 0),
    ):
        points, empty, total = _bin_extremes(seconds, series, start, end, bin_seconds, decimals)
        lanes.append({
            "id": identifier,
            "label": label,
            "unit": unit,
            "scale": "linear",
            "min": low,
            "max": high,
            "instrument": instrument,
            "evidence": "measurement",
            "points": points,
            "guides": guides,
            "emptyBins": empty,
            "binCount": total,
        })

    # ---- the marks: four extrema, no thresholds ---------------------------
    shock_at, shock_value = _extreme(seconds, symh, start, end, largest=True)
    bz_at, bz_value = _extreme(seconds, bz, start, end, largest=False)
    symh_at, symh_value = _extreme(seconds, symh, start, end, largest=False)
    speed_at, speed_value = _extreme(seconds, speed, start, end, largest=True)

    lag_hours = round((symh_at - bz_at) / 3600.0, 1)
    speed_lag_hours = round((speed_at - symh_at) / 3600.0, 1)

    marks = [
        {
            "id": "shock",
            "label": "Shock",
            "detail": "SYM/H at its maximum in the window",
            "minutes": since(shock_at),
            "at": stamp(shock_at),
            "value": f"{shock_value:+.0f} nT",
            "note": (
                "The cloud's leading shock squeezes the magnetosphere inward, and a compressed "
                "field measured from the ground is a STRONGER field. The storm index therefore "
                "goes up at the moment the storm arrives. Nothing has gone in yet."
            ),
        },
        {
            "id": "bzMin",
            "label": "Field turns south",
            "detail": "Bz at its minimum",
            "minutes": since(bz_at),
            "at": stamp(bz_at),
            "value": f"{bz_value:.1f} nT",
            "note": (
                "Now the arriving field is antiparallel to Earth's at the dayside and the two "
                "can reconnect. This is the moment energy starts going in, and it is the only "
                "quantity on this chart whose sign decides whether there is a storm at all."
            ),
        },
        {
            "id": "symhMin",
            "label": "Storm floor",
            "detail": "SYM/H at its minimum",
            "minutes": since(symh_at),
            "at": stamp(symh_at),
            "value": f"{symh_value:.0f} nT",
            "note": (
                f"{lag_hours:.1f} hours after the field turned south. The ring current is an "
                "accumulation, not a reading: it keeps deepening for as long as the door is "
                "open, so the worst moment is hours after the cause that made it."
            ),
        },
        {
            "id": "speedMax",
            "label": "Fastest wind",
            "detail": "flow speed at its maximum",
            "minutes": since(speed_at),
            "at": stamp(speed_at),
            "value": f"{speed_value:.0f} km/s",
            "note": (
                f"{speed_lag_hours:.0f} hours AFTER the storm bottomed out, with the index "
                "already recovering. If speed were the thing that mattered the worst of this "
                "storm would be here, at the right-hand edge, and it is not."
            ),
        },
    ]
    marks.sort(key=lambda mark: mark["minutes"])

    return {
        "kind": "southward-turning",
        "status": "observed",
        "title": "A fast wind does nothing until the field turns south",
        "startAt": stamp(start),
        "endAt": stamp(end),
        "spanMinutes": span_minutes,
        "binMinutes": STPATRICK_BIN_MINUTES,
        "lanes": lanes,
        "marks": marks,
        "findings": {
            "lagHours": lag_hours,
            "speedLagHours": speed_lag_hours,
            "bzMin": round(bz_value, 1),
            "symhMin": round(symh_value, 0),
            "shockPeak": round(shock_value, 0),
            "speedMax": round(speed_value, 0),
        },
        "provenance": {
            "field": (
                "Interplanetary magnetic field Bz in GSM coordinates and solar-wind flow "
                "speed, one-minute, from the High Resolution OMNI data set. The OMNI data were "
                "obtained from the GSFC/SPDF OMNIWeb interface at https://omniweb.gsfc.nasa.gov. "
                "The upstream measurements in this window are ACE (magnetic field: Smith; "
                "plasma: McComas) and Wind (magnetic field: Lepping; plasma: Ogilvie)."
            ),
            "symh": (
                "SYM/H, the one-minute longitudinally symmetric disturbance index, produced by "
                "the World Data Centre for Geomagnetism, Kyoto, and carried inside the OMNI "
                "record. It is NOT Dst: Dst is hourly and built from a different station set. "
                "Papers on this storm quote a minimum Dst of −223 nT; the one-minute SYM/H "
                "minimum drawn here is −234 nT. Both are right, and this page says which it is."
            ),
            "shift": (
                "The top two lanes are measured about 1.5 million km upstream at the first "
                "Lagrange point, not at Earth. OMNI time-shifts each one-minute average forward "
                "to the nose of Earth's bow shock using the measured flow and the observed "
                "orientation of the field's phase front. That shift — half an hour to an hour "
                "at these speeds — is the only derived quantity on this chart."
            ),
            "method": (
                f"Ten-minute bins. Each record is the real sample nearest the bin centre, "
                "carrying its own timestamp, plus the smallest and largest real sample inside "
                "the bin, which the chart draws as the band. Nothing is averaged and nothing is "
                "interpolated; a bin with no valid sample produces no record, so a gap in the "
                "archive is drawn as a gap. Values are published to 0.1 nT for the field and to "
                "1 unit for the speed and the index — in each case a small fraction of one pixel "
                "on the lane that draws them."
            ),
            "licence": (
                "OMNI is a NASA product and is freely available; NASA asks that its use be "
                "acknowledged in the wording carried above, and that the principal "
                "investigators who supplied the upstream data be credited, which is why they "
                "are named rather than summarised as 'L1 monitors'."
            ),
            "limitation": (
                "Bz here is what the field did UPSTREAM. How much of it actually got in depends "
                "on the reconnection rate, which nobody measures directly, so this chart shows "
                "the cause and the consequence and does not draw the coupling between them. The "
                "plasma instruments are also incomplete over this window and the gaps are left "
                "empty; the magnetic field and SYM/H lanes are nearly continuous. Finally, one "
                "storm cannot prove a rule: it is a clean, large, well-measured demonstration "
                "of a relationship established over decades of events, not the evidence for it."
            ),
        },
    }


BUILDERS = {
    "starlink-2022": build_starlink_replay,
    "gannon-2024": build_gannon_replay,
    "halloween-2003": build_halloween_replay,
    "bastille-2000": build_bastille_replay,
    "quebec-1989": build_quebec_replay,
    "stpatricks-2015": build_stpatrick_replay,
}


def _summarise(event_id: str, replay: dict) -> None:
    print(f"--- {event_id}  kind={replay['kind']} status={replay['status']}")
    if event_id == "starlink-2022":
        counts, driver = replay["counts"], replay["driver"]
        print(f"    catalogued={counts['catalogued']} lost={counts['lost']} "
              f"raised={counts['raised']} peakKp={driver['peakKp']}")
    elif event_id == "gannon-2024":
        found = replay["findings"]
        print(f"    measured peak {found['measuredPeak']}x at {found['measuredPeakAt']} "
              f"({found['measuredAltitudeKm']} km)")
        print(f"    model global-mean peak {found['globalPeak']}x at {found['globalPeakAt']}, "
              f"trough {found['globalTrough']}x at {found['globalTroughAt']}")
        print(f"    worst cross-cycle disagreement {found['worstSpread']}x at {found['worstSpreadAt']}")
        print(f"    SML peak {replay['driver']['peak']} nT at {replay['driver']['peakAt']}")
        print(f"    map {len(replay['map']['frames'])} frames of "
              f"{replay['map']['lonCount']}x{replay['map']['latCount']}")
    elif event_id in ("halloween-2003", "bastille-2000"):
        for arrival in replay["arrivals"]:
            print(f"    {arrival['label']:<15} +{arrival['minutes']:>9.2f} min  {arrival['value']}")
    elif event_id == "quebec-1989":
        for mark in replay["marks"]:
            print(f"    {mark['label']:<24} {mark['at']}  {mark['value']}")
        print(f"    the index bottomed out {replay['gapHours']} h after the failure")
    elif event_id == "stpatricks-2015":
        for mark in replay["marks"]:
            print(f"    {mark['label']:<18} {mark['at']}  {mark['value']}")
        for lane in replay["lanes"]:
            print(f"    lane {lane['id']:<6} bins={len(lane['points']):>4} of {lane['binCount']}"
                  f"  empty={lane['emptyBins']}")
        found = replay["findings"]
        print(f"    Bz min -> SYM/H min: {found['lagHours']} h; "
              f"peak speed {found['speedLagHours']} h after the floor")
    print(f"    payload bytes={len(json.dumps(replay, separators=(',', ':')))}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build measured event replays.")
    parser.add_argument("--event", default="all", choices=["all", *BUILDERS],
                        help="which event to rebuild (default: all)")
    parser.add_argument("--write", action="store_true",
                        help="merge the replay into data/events.json")
    args = parser.parse_args()

    wanted = list(BUILDERS) if args.event == "all" else [args.event]
    built = {event_id: BUILDERS[event_id]() for event_id in wanted}
    for event_id, replay in built.items():
        _summarise(event_id, replay)

    if not args.write:
        print("(dry run; pass --write to merge into data/events.json)")
        return

    # Read, merge, write -- and merge only the events actually rebuilt, so
    # rebuilding one event never drops another's replay from the artifact.
    bundle = json.loads(EVENTS_PATH.read_text())
    known = {event["id"] for event in bundle["events"]}
    missing = set(built) - known
    if missing:
        raise SystemExit(f"not present in data/events.json: {sorted(missing)}")
    for event in bundle["events"]:
        if event["id"] in built:
            event["replay"] = built[event["id"]]
    EVENTS_PATH.write_text(json.dumps(bundle, indent=2) + "\n")
    print(f"wrote {EVENTS_PATH} ({EVENTS_PATH.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
