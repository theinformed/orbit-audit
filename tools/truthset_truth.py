#!/usr/bin/env python3
"""T16b: parsers for the precise-orbit truth products and the Earth-orientation
series, and the frame chain that puts a propagated element set into the same
frame as the truth.

Two products, two formats, one output shape:

  AUX_POEORB (Sentinel-1)  Earth Explorer XML, `EARTH_FIXED` frame, UTC time
                           tags, metres and metres per second, 10 s sampling.
  POE SP3-c (Sentinel-3)   SP3-c, ITRF, TAI time tags, kilometres and
                           decimetres per second, 60 s sampling, one ~10 day
                           arc per file, Unix-compressed.

Both are read into the same arrays: UTC milliseconds, Earth-fixed position in
metres, Earth-fixed velocity in metres per second.

The frame chain for the comparison runs the other way — the propagator gives
TEME of date, and TEME is rotated to the product's frame:

  TEME --(GMST at UT1, about Z)--> PEF --(polar motion)--> ITRF

Both Earth-orientation terms are applied rather than neglected, because
neglecting them is not small at the scales this measurement reports:
|dUT1| up to 0.9 s is 0.9 x 15.041 arcsec = 13.5 arcsec, which at r = 7.2e6 m
is r*theta = 470 m; polar motion at 0.3 arcsec is 10 m. What is left after
applying both is the kinematic equation-of-equinoxes term omitted by the
GMST rotation, below 0.003 arcsec, i.e. about 0.1 m. Every one of those is
r*theta with theta in radians, derived here, not a quoted tolerance.
"""
from __future__ import annotations

import datetime as dt
import re
import subprocess
from pathlib import Path

import numpy as np

# WGS-84 as the products use it; the value is only ever used to turn a state
# vector into a semi-major axis for the manoeuvre screen.
MU_M3_S2 = 3.986004418e14
OMEGA_EARTH = 7.292115e-5          # rad/s, Earth rotation rate about Z
ARCSEC = np.pi / 648000.0

# TAI - UTC over the registered span. SP3 time tags are TAI; the registered
# span (calendar 2023) sits entirely inside the 37 s era, which began
# 2017-01-01 and has not been added to since.
LEAP_ERAS = (
    (dt.datetime(2017, 1, 1, tzinfo=dt.timezone.utc), 37.0),
    (dt.datetime(2015, 7, 1, tzinfo=dt.timezone.utc), 36.0),
    (dt.datetime(2012, 7, 1, tzinfo=dt.timezone.utc), 35.0),
    (dt.datetime(2009, 1, 1, tzinfo=dt.timezone.utc), 34.0),
    (dt.datetime(2006, 1, 1, tzinfo=dt.timezone.utc), 33.0),
    (dt.datetime(1999, 1, 1, tzinfo=dt.timezone.utc), 32.0),
)


def tai_minus_utc(when: dt.datetime) -> float:
    for start, offset in LEAP_ERAS:
        if when >= start:
            return offset
    raise ValueError(f"no leap-second era registered for {when.isoformat()}")


_EPOCH = dt.datetime(1970, 1, 1, tzinfo=dt.timezone.utc)
_DAY_CACHE: dict[str, int] = {}


def iso_to_ms(text: str) -> int:
    """'2022-12-11T22:59:42.000000' -> UTC milliseconds.

    Hand-rolled because this runs over millions of tags and
    `datetime.fromisoformat` costs about an order of magnitude more.
    """
    day = text[:10]
    base = _DAY_CACHE.get(day)
    if base is None:
        base = int((dt.datetime(int(day[:4]), int(day[5:7]), int(day[8:10]),
                                tzinfo=dt.timezone.utc) - _EPOCH).total_seconds()) * 1000
        _DAY_CACHE[day] = base
    hh = int(text[11:13]); mm = int(text[14:16]); ss = int(text[17:19])
    frac = 0
    if len(text) > 19 and text[19] == ".":
        frac = int(round(float(text[19:]) * 1000.0))
    return base + (hh * 3600 + mm * 60 + ss) * 1000 + frac


_OSV = re.compile(
    r"<UTC>UTC=([0-9T:\-.]+)</UTC>.*?"
    r'<X unit="m">(-?[\d.eE+]+)</X>\s*'
    r'<Y unit="m">(-?[\d.eE+]+)</Y>\s*'
    r'<Z unit="m">(-?[\d.eE+]+)</Z>\s*'
    r'<VX unit="m/s">(-?[\d.eE+]+)</VX>\s*'
    r'<VY unit="m/s">(-?[\d.eE+]+)</VY>\s*'
    r'<VZ unit="m/s">(-?[\d.eE+]+)</VZ>', re.S)


def parse_eof(path: Path):
    """One AUX_POEORB file -> (t_ms, pos_m, vel_mps), Earth-fixed."""
    text = path.read_text(errors="replace")
    frame = re.search(r"<Ref_Frame>(.*?)</Ref_Frame>", text)
    if frame and frame.group(1).strip() not in ("EARTH_FIXED", "ITRF"):
        raise ValueError(f"{path.name}: unexpected frame {frame.group(1)}")
    rows = _OSV.findall(text)
    if not rows:
        raise ValueError(f"{path.name}: no state vectors")
    t = np.fromiter((iso_to_ms(r[0]) for r in rows), dtype=np.int64, count=len(rows))
    vals = np.array([[float(x) for x in r[1:]] for r in rows], dtype=np.float64)
    return t, vals[:, 0:3], vals[:, 3:6]


def _zcat(path: Path) -> str:
    """Unix-compressed (.Z) text. Python's standard library cannot read LZW,
    so the system decompressor does it; the call is recorded here rather than
    hidden behind a shell pipeline elsewhere."""
    if path.suffix == ".Z":
        out = subprocess.run(["gzip", "-dc", str(path)], check=True,
                             capture_output=True)
        return out.stdout.decode("ascii", "replace")
    return path.read_text(errors="replace")


def parse_sp3(path: Path):
    """One SP3-c arc -> (t_ms, pos_m, vel_mps), Earth-fixed.

    Positions are kilometres and velocities decimetres per second in the SP3-c
    default, which is what these files use (the header's own %f/units block and
    the magnitudes agree: a LEO speed reads as about 7e4 dm/s).
    """
    text = _zcat(path)
    times: list[int] = []
    pos: list[tuple[float, float, float]] = []
    vel: list[tuple[float, float, float]] = []
    frame_ok = False
    cur_ms = None
    cur_p = None
    for line in text.splitlines():
        if line.startswith("#c") or line.startswith("#a") or line.startswith("#d"):
            frame_ok = "ITRF" in line
        elif line.startswith("*  ") or line.startswith("* "):
            parts = line[1:].split()
            year, mon, day, hh, mm = (int(parts[0]), int(parts[1]), int(parts[2]),
                                      int(parts[3]), int(parts[4]))
            sec = float(parts[5])
            tai = dt.datetime(year, mon, day, hh, mm, tzinfo=dt.timezone.utc)
            utc = tai + dt.timedelta(seconds=sec - tai_minus_utc(tai))
            cur_ms = int(round((utc - _EPOCH).total_seconds() * 1000.0))
            cur_p = None
        elif line.startswith("P") and cur_ms is not None:
            x, y, z = (float(line[4:18]), float(line[18:32]), float(line[32:46]))
            cur_p = (x * 1000.0, y * 1000.0, z * 1000.0)
        elif line.startswith("V") and cur_ms is not None and cur_p is not None:
            vx, vy, vz = (float(line[4:18]), float(line[18:32]), float(line[32:46]))
            times.append(cur_ms)
            pos.append(cur_p)
            vel.append((vx * 0.1, vy * 0.1, vz * 0.1))
            cur_p = None
    if not frame_ok:
        raise ValueError(f"{path.name}: header does not declare ITRF")
    if not times:
        raise ValueError(f"{path.name}: no state vectors")
    return (np.asarray(times, dtype=np.int64),
            np.asarray(pos, dtype=np.float64),
            np.asarray(vel, dtype=np.float64))


def load_truth(paths, kind: str):
    """Every arc of one spacecraft, de-duplicated and sorted by epoch."""
    parse = parse_eof if kind == "eof" else parse_sp3
    ts, ps, vs = [], [], []
    for path in sorted(paths):
        t, p, v = parse(path)
        ts.append(t); ps.append(p); vs.append(v)
    t = np.concatenate(ts); p = np.concatenate(ps); v = np.concatenate(vs)
    order = np.argsort(t, kind="stable")
    t, p, v = t[order], p[order], v[order]
    keep = np.ones(t.size, dtype=bool)
    keep[1:] = np.diff(t) != 0
    return t[keep], p[keep], v[keep]


# ---------------------------------------------------------------------------
# Earth orientation
# ---------------------------------------------------------------------------
def parse_eop(path: Path):
    """IERS finals2000A.all -> (mjd, x_p arcsec, y_p arcsec, UT1-UTC s).

    Fixed-column format: MJD in columns 8-15, the Bulletin-A pole in 19-27 and
    38-46, and UT1-UTC in 59-68. Rows whose prediction fields are blank are
    dropped rather than defaulted.
    """
    mjd, xp, yp, dut1 = [], [], [], []
    for line in path.read_text(errors="replace").splitlines():
        if len(line) < 68:
            continue
        try:
            m = float(line[7:15])
            x = float(line[18:27])
            y = float(line[37:46])
            d = float(line[58:68])
        except ValueError:
            continue
        mjd.append(m); xp.append(x); yp.append(y); dut1.append(d)
    return (np.asarray(mjd), np.asarray(xp), np.asarray(yp), np.asarray(dut1))


class EarthOrientation:
    """Linear interpolation of (x_p, y_p, UT1-UTC) in MJD."""

    MJD_UNIX_EPOCH = 40587.0

    def __init__(self, path: Path):
        self.mjd, self.xp, self.yp, self.dut1 = parse_eop(path)
        if self.mjd.size < 2:
            raise ValueError(f"{path}: no usable Earth-orientation rows")

    def at_ms(self, t_ms):
        mjd = self.MJD_UNIX_EPOCH + np.asarray(t_ms, dtype=np.float64) / 86400000.0
        lo, hi = self.mjd[0], self.mjd[-1]
        if np.any(mjd < lo) or np.any(mjd > hi):
            raise ValueError("Earth-orientation series does not cover the span")
        return (np.interp(mjd, self.mjd, self.xp),
                np.interp(mjd, self.mjd, self.yp),
                np.interp(mjd, self.mjd, self.dut1))


def pef_to_itrf(r_pef, xp_arcsec, yp_arcsec):
    """Polar motion, to first order in the pole coordinates.

    W = R2(-x_p) R1(-y_p); for angles of 0.3 arcsec = 1.5e-6 rad the second
    order term is r*theta^2 = 1.6e-5 m and is dropped deliberately.
    """
    r = np.asarray(r_pef, dtype=np.float64)
    xp = np.asarray(xp_arcsec, dtype=np.float64) * ARCSEC
    yp = np.asarray(yp_arcsec, dtype=np.float64) * ARCSEC
    x, y, z = r[..., 0], r[..., 1], r[..., 2]
    return np.stack((x + xp * z, y - yp * z, z - xp * x + yp * y), axis=-1)


def rtn_basis(r_ecef, v_ecef):
    """Radial / along-track / cross-track unit vectors, in ECEF components.

    The products give Earth-fixed velocities, so the inertial velocity used to
    define the orbit plane is v_i = v + omega x r with omega about Z.
    """
    r = np.asarray(r_ecef, dtype=np.float64)
    v = np.asarray(v_ecef, dtype=np.float64)
    vi = v.copy()
    vi[..., 0] = v[..., 0] - OMEGA_EARTH * r[..., 1]
    vi[..., 1] = v[..., 1] + OMEGA_EARTH * r[..., 0]
    radial = r / np.linalg.norm(r, axis=-1, keepdims=True)
    cross = np.cross(r, vi)
    cross = cross / np.linalg.norm(cross, axis=-1, keepdims=True)
    along = np.cross(cross, radial)
    return radial, along, cross


def semi_major_axis_m(r_ecef, v_ecef):
    """Osculating semi-major axis from an Earth-fixed state (inertial speed)."""
    r = np.asarray(r_ecef, dtype=np.float64)
    v = np.asarray(v_ecef, dtype=np.float64)
    vi = v.copy()
    vi[..., 0] = v[..., 0] - OMEGA_EARTH * r[..., 1]
    vi[..., 1] = v[..., 1] + OMEGA_EARTH * r[..., 0]
    rn = np.linalg.norm(r, axis=-1)
    vn = np.linalg.norm(vi, axis=-1)
    return 1.0 / (2.0 / rn - vn * vn / MU_M3_S2)
