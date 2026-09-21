"""Geomagnetic storm indices: Dst, IMF clock angle, and the coupling functions.

This module exists because the Space Environment Explorer was **two fields**
away from being able to tell the whole storm story, and both of them were
essentially free:

* **IMF `By` was already being downloaded and then thrown away.**  NOAA's
  propagated solar-wind product publishes
  `[time_tag, speed, density, temperature, bx, by, bz, bt, vx, vy, vz,
  propagated_time_tag]` and `pipeline/build_release.py` kept three of those
  columns.  Keeping the rest costs nothing and unlocks the **IMF clock angle**,
  which is the switch that governs dayside reconnection, and therefore unlocks
  every published solar-wind/magnetosphere coupling function.
* **`Dst` is one new endpoint per evidence class**, and all three are cheap.

`docs/magnetosphere-realism-design.md` is the specification; every formula
below carries its citation, and every constant in it was checked against the
primary source before it was written down.

## The three Dst series are three different kinds of evidence

They are published as three separate traces and **must never be merged into
one**.  `docs/SCIENTIFIC-LAYERS.md` forbids collapsing evidence classes, and
here the distinction is the lesson rather than a technicality: the visitor sees
a nowcast issued about 70 minutes ahead of real time, then watches it graded in
public, twice, at four minutes and at fifty.

| Slot | Series | Class |
| --- | --- | --- |
| Live nowcast, with forward lead | NOAA Geospace SWMF `dst_sm` | Model / Forecast |
| Live observed check | USGS `Dst3` | Observed |
| The recognisable index | WDC Kyoto quicklook, hourly, via NOAA SWPC | Observed |

The two live series are US Government work in the public domain.  Kyoto's index
is used only where its familiarity is the point, and it carries
`doi:10.17593/14515-74000` at every appearance; Kyoto's own version document
says the real-time index *"is intended for monitoring purposes only and not for
scientific analysis"* and that provisional-to-final revisions of 20-30 nT
happen, so the quicklook series is labelled accordingly.

## Traps that were paid for once already

* `elements=DST` is a dead channel on the USGS service.  The live ones are
  `Dst3` and `Dst4`, case-sensitive.  `Dst3` is USGS-only (HON, SJG, GUA) and
  runs about fourteen minutes fresher than the four-observatory `Dst4`.
* **The USGS archive fails silently.**  A request outside its ~30-day rolling
  window returns HTTP 200 with every value `null`.  `parse_usgs_dst` therefore
  asserts a non-null count and returns nothing rather than an empty-but-present
  series - this project has a documented defect class of branches whose inputs
  are only populated on a non-error path.
* USGS `OPTIONS` and `HEAD` both 404.  Plain GETs only.
* The SWPC feeds have been seen in two JSON shapes (a header row plus value
  rows, and a list of objects).  Both are accepted; neither is assumed.

Nothing in this module retries a failed fetch.  Upstream calls are made by the
caller and passed in, so the tests here run with no network at all.
"""

from __future__ import annotations

import datetime as dt
import math
from typing import Any, Callable, Sequence

# --------------------------------------------------------------------------
# Endpoints
# --------------------------------------------------------------------------

#: One-minute **modelled** Dst from the same operational NOAA Geospace/SWMF run
#: whose magnetopause driver, cut planes and RBE electron fields this site
#: already ingests.  It is the run's own `dst_sm` log variable and runs roughly
#: 70 minutes into the future.  Path trap: `/products/geospace/` is a different
#: directory and holds only the propagated solar wind; this file is under
#: `/json/geospace/`.
NOAA_MODEL_DST = "https://services.swpc.noaa.gov/json/geospace/geospace_dst_1_hour.json"

#: One-minute **observed** Dst from the USGS geomagnetism programme, about four
#: minutes behind real time.  US public domain, CORS-open, no key.
USGS_DST = (
    "https://geomag.usgs.gov/ws/data/"
    "?id=USGS&elements=Dst3,Dst4&format=json&sampling_period=60"
)

#: Hourly Kyoto quicklook Dst, republished by NOAA SWPC.  Cite WDC Kyoto.
KYOTO_DST = "https://services.swpc.noaa.gov/products/kyoto-dst.json"

KYOTO_CITATION = "WDC for Geomagnetism, Kyoto - quicklook Dst, doi:10.17593/14515-74000"
KYOTO_STATUS_NOTE = (
    "Quicklook: Kyoto states the real-time index is for monitoring only, not for "
    "scientific analysis, and that provisional-to-final revisions of 20-30 nT occur."
)


# --------------------------------------------------------------------------
# Physical constants
# --------------------------------------------------------------------------

#: Dynamic-pressure constant in the pure-proton (OMNI) convention,
#: `P[nPa] = 1.6726e-6 n[cm^-3] v[km/s]^2`.  Tsyganenko's own models use the
#: helium-corrected `1.937e-6`; the two are kept apart deliberately because
#: feeding a proton-only pressure to a Tsyganenko model makes it 16% low.
PROTON_DYNAMIC_PRESSURE_CONSTANT = 1.6726e-6
TSYGANENKO_DYNAMIC_PRESSURE_CONSTANT = 1.937e-6

#: `B^2 / 2 mu0` with B in nT and the result in nPa.
MAGNETIC_PRESSURE_NPA_PER_NT2 = 1e-18 / (2 * 4e-7 * math.pi) * 1e9

#: Dessler-Parker-Sckopke: `E_ring = |Dst| * 2 pi B0 Re^3 / mu0`.
#: With the modern IGRF dipole B0 = 30,100 nT this is 3.892e13 J per nT.  The
#: older 0.311 G figure gives 4.021e13 and 30,000 nT gives 3.879e13, so the
#: commonly quoted ~4e13 J/nT is safe to about 3%.
DPS_DIPOLE_SURFACE_FIELD_NT = 30100.0
EARTH_RADIUS_M = 6.371e6
DPS_JOULES_PER_NT = (
    # 1e-9 converts the Dst the caller passes in from nT to T; without it this
    # constant is joules per tesla and the published energy is out by 1e9.
    1e-9 * 2 * math.pi * (DPS_DIPOLE_SURFACE_FIELD_NT * 1e-9) * EARTH_RADIUS_M**3 / (4e-7 * math.pi)
)

#: Energy of the external part of Earth's dipole field, for the "what fraction
#: of the whole magnetosphere is this?" readout.
DIPOLE_EXTERNAL_FIELD_ENERGY_J = (
    4 * math.pi * (DPS_DIPOLE_SURFACE_FIELD_NT * 1e-9) ** 2 * EARTH_RADIUS_M**3 / (3 * 4e-7 * math.pi)
)

#: Observed cross-polar-cap potential saturates near 200-250 kV while the Boyle
#: regression is linear, so it is published with its saturation line attached
#: rather than silently clipped.
BOYLE_SATURATION_KV = 250.0

#: How far past "now" the modelled Dst is allowed to run. The operational run
#: publishes roughly 70 minutes of forward lead; three hours is a generous
#: ceiling that costs a few kilobytes and never truncates the nowcast.
MODEL_FORWARD_WINDOW_HOURS = 3.0

#: Newell coupling band scale: the published quiet-to-extreme ladder, used as a
#: "how hard is this being driven" colour scale and nothing else.
#:
#: ⚠️ These are **representative conditions, not a fixed-speed Bz sweep.**  The
#: source states an IMF Bz beside each value but not the solar-wind speed, and
#: the values cannot be reproduced at any single speed: recovering v from each
#: pair with By = 0 gives roughly 406, 451, 550, 700 and 1000 km/s as the
#: ladder climbs.  So the *values* are usable as bands and the *Bz labels* are
#: not a lookup table.  `tests/test_storm_indices.py` pins that relationship so
#: a future reader cannot quietly turn the ladder back into a Bz mapping.
NEWELL_CALIBRATION = [
    {"label": "very quiet", "value": 0, "representativeBzNt": 3.0},
    {"label": "quiet", "value": 4773, "representativeBzNt": -2.0},
    {"label": "moderate", "value": 10123, "representativeBzNt": -5.0},
    {"label": "storm", "value": 27421, "representativeBzNt": -15.0},
    {"label": "severe", "value": 60036, "representativeBzNt": -30.0},
    {"label": "extreme", "value": 153333, "representativeBzNt": -60.0},
]

NEWELL_CALIBRATION_NOTE = (
    "A band scale of representative disturbed conditions, not a lookup table on "
    "IMF Bz: each published value implies a different solar-wind speed, rising "
    "from about 400 km/s at the quiet end to about 1000 km/s at the extreme end."
)


# --------------------------------------------------------------------------
# Derived quantities
# --------------------------------------------------------------------------


def dynamic_pressure_npa(density_cm3: float | None, speed_kps: float | None) -> float | None:
    """Solar-wind dynamic pressure in the pure-proton OMNI convention."""
    if density_cm3 is None or speed_kps is None:
        return None
    if not math.isfinite(density_cm3) or not math.isfinite(speed_kps):
        return None
    if density_cm3 < 0 or speed_kps <= 0:
        return None
    return PROTON_DYNAMIC_PRESSURE_CONSTANT * density_cm3 * speed_kps**2


def magnetic_pressure_npa(bt_nt: float | None) -> float | None:
    """Upstream IMF magnetic pressure, the `Pm` term the cusped magnetopause
    models add to `Pdyn` before raising it to a power."""
    if bt_nt is None or not math.isfinite(bt_nt):
        return None
    return MAGNETIC_PRESSURE_NPA_PER_NT2 * bt_nt * bt_nt


def clock_angle_rad(by_nt: float | None, bz_nt: float | None) -> float | None:
    """IMF clock angle, measured from GSM north, with the branch fix.

    `atan(|By|/Bz)` and `atan2(By, Bz)` agree from 0 to pi and diverge from pi
    to 2 pi (Lockwood 2022), so a naive implementation gets **northward** IMF
    wrong - which is most of the time, and therefore most of the quiet-time
    display.  The correction below is the one carried by OvationPyme's
    `calc_coupling`, the lineage behind NOAA's operational aurora forecast.
    """
    if by_nt is None or bz_nt is None:
        return None
    if not math.isfinite(by_nt) or not math.isfinite(bz_nt):
        return None
    transverse = math.hypot(by_nt, bz_nt)
    if transverse <= 0:
        return None
    bz_safe = bz_nt if bz_nt != 0 else 0.001
    angle = math.atan2(by_nt, bz_safe)
    if transverse * math.cos(angle) * bz_nt < 0:
        angle += math.pi
    return angle


def clock_angle_degrees(by_nt: float | None, bz_nt: float | None) -> float | None:
    angle = clock_angle_rad(by_nt, bz_nt)
    return None if angle is None else math.degrees(angle) % 360.0


def newell_coupling(
    speed_kps: float | None, by_nt: float | None, bz_nt: float | None
) -> float | None:
    """Newell et al. (2007) universal coupling function `dPhi_MP/dt`.

    `v^(4/3) BT^(2/3) sin^(8/3)(theta_c/2)`, deliberately **unnormalised**: its
    units are literally `(km/s)^(4/3) nT^(2/3)`.  It accounted for 57.2% of the
    variance across ten magnetospheric state variables against 50.9% for
    Kan-Lee and 48.8% for vBs, which is why it is the primary live number here.
    doi:10.1029/2006JA012015.
    """
    angle = clock_angle_rad(by_nt, bz_nt)
    if angle is None or speed_kps is None or speed_kps <= 0:
        return None
    transverse = math.hypot(by_nt, bz_nt)  # type: ignore[arg-type]
    return speed_kps**1.33333 * abs(math.sin(angle / 2.0)) ** 2.66667 * transverse**0.66667


def akasofu_epsilon_gw(
    speed_kps: float | None,
    bx_nt: float | None,
    by_nt: float | None,
    bz_nt: float | None,
) -> float | None:
    """Akasofu's epsilon in gigawatts (Perreault & Akasofu 1978; Akasofu 1981).

    Uses the **full** IMF magnitude, not the transverse component.  Akasofu's
    own thresholds are <10 GW quiet, >100 GW substorm, >1 TW storm.

    Shown for historical context only.  Koskinen & Tanskanen (2002) call its
    definition "somewhat unclear" with a "lack of physical foundation";
    Lockwood (2019) identified an outright error in its theoretical basis; and
    Finch & Lockwood (2007) showed it performs measurably worse than other
    coupling functions on all timescales.  Newell is the primary number.
    """
    angle = clock_angle_rad(by_nt, bz_nt)
    if angle is None or speed_kps is None or bx_nt is None or speed_kps <= 0:
        return None
    magnitude = math.sqrt(bx_nt**2 + by_nt**2 + bz_nt**2)  # type: ignore[operator]
    return 0.019889 * speed_kps * magnitude**2 * math.sin(angle / 2.0) ** 4


def boyle_cross_polar_cap_kv(
    speed_kps: float | None,
    bx_nt: float | None,
    by_nt: float | None,
    bz_nt: float | None,
) -> float | None:
    """Boyle, Reiff & Hairston (1997) cross-polar-cap potential, uncapped.

    The regression is linear and **will overpredict badly** under strong
    driving - it gives 409 kV and 831 kV where the observed potential saturates
    near 200-250 kV.  The uncapped value is returned so the caller can draw the
    saturation line explicitly instead of hiding the disagreement.
    """
    angle = clock_angle_rad(by_nt, bz_nt)
    if angle is None or speed_kps is None or bx_nt is None or speed_kps <= 0:
        return None
    magnitude = math.sqrt(bx_nt**2 + by_nt**2 + bz_nt**2)  # type: ignore[operator]
    return 1e-4 * speed_kps**2 + 11.7 * magnitude * abs(math.sin(angle / 2.0)) ** 3


def ring_current_energy_joules(dst_nt: float | None) -> float | None:
    """Dessler-Parker-Sckopke ring-current energy from Dst.

    `E = |Dst| * 2 pi B0 Re^3 / mu0`.  Only the depressed (negative) branch is
    physical as a ring-current energy: a positive Dst is a compression
    signature carried by the Chapman-Ferraro current, not a ring current, so
    this returns 0 there rather than a fictitious energy.

    The honest error bar is close to a factor of two and the caller is expected
    to say so: the induced contribution from inside the solid Earth is about
    28%, the magnetotail carries roughly a quarter of the depression, and DPS
    counts kinetic energy only while Joule heating dominates the storm's actual
    energy budget.
    """
    if dst_nt is None or not math.isfinite(dst_nt):
        return None
    return DPS_JOULES_PER_NT * max(0.0, -dst_nt)


def pressure_corrected_dst(
    dst_nt: float | None, dynamic_pressure_npa_value: float | None
) -> dict[str, float] | None:
    """Both standard `Dst* = Dst - b sqrt(Pdyn) + c` corrections, side by side.

    O'Brien & McPherron (2000) use b = 7.26, c = 11; Burton et al. (1975)
    convert to b = 15.8, c = 20.  Both vanish at nominal solar wind and
    **disagree by 18 nT at a 10 nPa shock**, which is exactly when the
    correction matters.  Publishing one of them as *the* correction would hide
    a real, teachable disagreement, so both are returned.
    """
    if dst_nt is None or dynamic_pressure_npa_value is None:
        return None
    if dynamic_pressure_npa_value < 0:
        return None
    root = math.sqrt(dynamic_pressure_npa_value)
    return {
        "obrienMcPherronNt": dst_nt - 7.26 * root + 11.0,
        "burtonNt": dst_nt - 15.8 * root + 20.0,
    }


# --------------------------------------------------------------------------
# Parsers
# --------------------------------------------------------------------------


def _parse_time(value: Any) -> dt.datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = dt.datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def _iso_z(value: dt.datetime) -> str:
    return value.astimezone(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _records(raw: Any) -> list[dict[str, Any]]:
    """Accept both SWPC JSON shapes without assuming either.

    Some SWPC products are `[[header...], [row...], ...]` and some are a list
    of objects.  The Dst products have been seen in both shapes, so neither is
    hard-coded; an unrecognised payload yields no records rather than an
    exception, and the caller's own emptiness check decides what to do.
    """
    if not isinstance(raw, list) or not raw:
        return []
    if isinstance(raw[0], dict):
        return [row for row in raw if isinstance(row, dict)]
    if isinstance(raw[0], list):
        headers = [str(value) for value in raw[0]]
        return [dict(zip(headers, row)) for row in raw[1:] if isinstance(row, list)]
    return []


def _finite(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def parse_swpc_dst(raw: Any) -> list[dict[str, Any]]:
    """Parse either SWPC Dst product into `[{"at", "dstNt"}, ...]`, sorted."""
    samples: dict[dt.datetime, float] = {}
    for record in _records(raw):
        at = _parse_time(record.get("time_tag"))
        value = _finite(record.get("dst"))
        if at is None or value is None:
            continue
        samples[at] = value
    return [{"at": _iso_z(at), "dstNt": samples[at]} for at in sorted(samples)]


def parse_usgs_dst(raw: Any, element: str = "Dst3") -> list[dict[str, Any]]:
    """Parse the USGS geomagnetism web service timeseries for one element.

    Returns an empty list when the requested element is absent **or when every
    sample is null**.  That second case is not hypothetical: the service's
    archive is a ~30-day rolling window and a request outside it answers HTTP
    200 with a full-length array of nulls.  A caller that trusted the status
    code would publish a present-but-empty observed trace, which is worse than
    publishing nothing.
    """
    if not isinstance(raw, dict):
        return []
    times = raw.get("times")
    series = raw.get("values")
    if not isinstance(times, list) or not isinstance(series, list):
        return []
    chosen: dict[str, Any] | None = None
    for candidate in series:
        if not isinstance(candidate, dict):
            continue
        identifier = str(candidate.get("id") or "")
        metadata = candidate.get("metadata")
        reported = str(metadata.get("element") or "") if isinstance(metadata, dict) else ""
        if element in {identifier, reported}:
            chosen = candidate
            break
    if chosen is None:
        return []
    values = chosen.get("values")
    if not isinstance(values, list) or len(values) != len(times):
        return []
    samples: list[dict[str, Any]] = []
    for time_text, value in zip(times, values):
        at = _parse_time(time_text)
        number = _finite(value)
        if at is None or number is None:
            continue
        samples.append({"at": _iso_z(at), "dstNt": number})
    if not samples:
        return []
    return samples


def thin_series(
    samples: Sequence[dict[str, Any]],
    *,
    cadence_minutes: int,
    history_hours: float,
    now: dt.datetime,
) -> list[dict[str, Any]]:
    """Keep the newest sample in each cadence bucket inside the history window.

    Buckets are floor divisions of the absolute epoch, not of a rounded local
    value, so a sample never changes bucket because the window moved - this
    project has a recorded defect class of rounded buckets that are unstable
    exactly where the data sits.
    """
    if cadence_minutes <= 0:
        raise ValueError("cadence_minutes must be positive")
    cutoff = now - dt.timedelta(hours=history_hours)
    buckets: dict[int, tuple[dt.datetime, dict[str, Any]]] = {}
    for sample in samples:
        at = _parse_time(sample.get("at"))
        if at is None or at < cutoff:
            continue
        bucket = int(at.timestamp() // (cadence_minutes * 60))
        previous = buckets.get(bucket)
        if previous is None or at >= previous[0]:
            buckets[bucket] = (at, sample)
    return [item[1] for _, item in sorted(buckets.items())]


# --------------------------------------------------------------------------
# Storm phase
# --------------------------------------------------------------------------

#: The three phases are phases of the **Dst curve**, so the classifier reads
#: the curve and nothing else.  Thresholds are the conventional ones: a storm
#: is customarily counted from Dst <= -30 nT, moderate at -50, intense at -100.
STORM_PHASE_RULE = (
    "Deterministic classification of the Dst trace. Initial phase: a rise of at "
    "least 10 nT above the median of the preceding six hours, with no storm "
    "minimum yet reached. Main phase: Dst at or below -30 nT and still falling "
    "over the last hour. Recovery: a minimum of -30 nT or deeper has already "
    "been reached and Dst is rising. Quiet otherwise. No model and no language "
    "model is consulted."
)

#: ⚠️ The absolute thresholds are defined on the **Kyoto** index, and different
#: station sets carry different baselines: on 2026-08-08 the USGS Dst3 series
#: read +20.5 nT at the same moment Kyoto read +7. Classifying an absolute
#: level from the wrong series therefore labels a quiet day a sudden
#: commencement, which is why the initial-phase test is written as a *rise
#: above a local baseline* rather than a level, and why the classifier prefers
#: the Kyoto trace when one is available and records which trace it used.
STORM_PHASE_BASELINE_NOTE = (
    "Storm thresholds are defined on the Kyoto Dst index. Other station sets "
    "(such as USGS Dst3) carry their own baselines and can differ by 10-15 nT "
    "at the same instant, so the phase is classified from the Kyoto trace where "
    "one is available and the series used is named alongside the label."
)

STORM_INTENSITY_THRESHOLDS_NT = {"weak": -30.0, "moderate": -50.0, "intense": -100.0, "severe": -250.0}


def _sample_at(samples: Sequence[dict[str, Any]], at: dt.datetime) -> float | None:
    """Value of the sample closest to `at` from at or before it."""
    best: tuple[dt.datetime, float] | None = None
    for sample in samples:
        moment = _parse_time(sample.get("at"))
        value = _finite(sample.get("dstNt"))
        if moment is None or value is None or moment > at:
            continue
        if best is None or moment > best[0]:
            best = (moment, value)
    return None if best is None else best[1]


def _median(values: Sequence[float]) -> float | None:
    ordered = sorted(values)
    if not ordered:
        return None
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


def classify_storm_phase(
    samples: Sequence[dict[str, Any]],
    *,
    now: dt.datetime,
    window_hours: float = 24.0,
    series_name: str | None = None,
) -> dict[str, Any]:
    """Label the Dst trace's storm phase with a rule, not a judgement.

    Returns `phase`, the window minimum with its time, an intensity word, and
    the rule text itself, so the interface can show the reader the rule it is
    being shown the output of.
    """
    window = [
        sample
        for sample in samples
        if (moment := _parse_time(sample.get("at"))) is not None
        and moment >= now - dt.timedelta(hours=window_hours)
        and moment <= now
        and _finite(sample.get("dstNt")) is not None
    ]
    if not window:
        return {
            "label": "unknown",
            "rule": STORM_PHASE_RULE,
            "baselineNote": STORM_PHASE_BASELINE_NOTE,
            "series": series_name,
            "reason": "no Dst samples inside the classification window",
            "minimumNt": None,
            "minimumAt": None,
            "baselineNt": None,
            "intensity": None,
        }
    ordered = sorted(window, key=lambda sample: str(sample["at"]))
    minimum = min(ordered, key=lambda sample: float(sample["dstNt"]))
    minimum_value = float(minimum["dstNt"])
    minimum_at = _parse_time(minimum["at"])
    latest_value = float(ordered[-1]["dstNt"])
    latest_at = _parse_time(ordered[-1]["at"])
    hour_ago = _sample_at(ordered, latest_at - dt.timedelta(hours=1)) if latest_at else None

    intensity = None
    for label in ("severe", "intense", "moderate", "weak"):
        if minimum_value <= STORM_INTENSITY_THRESHOLDS_NT[label]:
            intensity = label
            break

    # A sudden commencement is a *step*, not a level: the level depends on which
    # station set produced the index. The baseline is the median of the six
    # hours ending one hour ago, so the rise being tested is a rise this trace
    # made rather than an offset this trace was born with.
    baseline = _median([
        float(sample["dstNt"])
        for sample in ordered
        if (moment := _parse_time(sample["at"])) is not None
        and latest_at is not None
        and latest_at - dt.timedelta(hours=7) <= moment <= latest_at - dt.timedelta(hours=1)
    ])

    if minimum_value > STORM_INTENSITY_THRESHOLDS_NT["weak"]:
        rising = hour_ago is None or latest_value >= hour_ago
        if baseline is not None and latest_value - baseline >= 10.0 and rising:
            phase, reason = (
                "initial",
                f"a rise of {latest_value - baseline:.0f} nT above the preceding baseline, "
                "with no storm minimum reached",
            )
        else:
            phase, reason = "quiet", "no Dst depression at or below -30 nT in the window"
    elif latest_value <= STORM_INTENSITY_THRESHOLDS_NT["weak"] and hour_ago is not None and latest_value < hour_ago:
        phase, reason = "main", "Dst at or below -30 nT and still falling"
    elif minimum_at is not None and latest_at is not None and latest_at > minimum_at and latest_value > minimum_value:
        phase, reason = "recovery", "storm minimum already reached and Dst is rising"
    else:
        phase, reason = "main", "Dst at or below -30 nT with no established recovery"

    return {
        "label": phase,
        "rule": STORM_PHASE_RULE,
        "baselineNote": STORM_PHASE_BASELINE_NOTE,
        "series": series_name,
        "reason": reason,
        "minimumNt": round(minimum_value, 2),
        "minimumAt": minimum["at"],
        "baselineNt": None if baseline is None else round(baseline, 2),
        "intensity": intensity,
    }


# --------------------------------------------------------------------------
# Artifact assembly
# --------------------------------------------------------------------------


def derive_driver_terms(record: dict[str, Any]) -> dict[str, Any]:
    """Coupling terms for one propagated solar-wind sample.

    Every value here is a deterministic function of columns NOAA already
    publishes; nothing is fetched and nothing is assumed.
    """
    speed = _finite(record.get("speed"))
    density = _finite(record.get("density"))
    bx = _finite(record.get("bx"))
    by = _finite(record.get("by"))
    bz = _finite(record.get("bz"))
    bt = _finite(record.get("bt"))
    pressure = dynamic_pressure_npa(density, speed)
    return {
        "dynamicPressureNpa": pressure,
        "magneticPressureNpa": magnetic_pressure_npa(bt),
        "transverseImfNt": None if by is None or bz is None else math.hypot(by, bz),
        "clockAngleDeg": clock_angle_degrees(by, bz),
        "newellCoupling": newell_coupling(speed, by, bz),
        "epsilonGw": akasofu_epsilon_gw(speed, bx, by, bz),
        "boyleCpcpKv": boyle_cross_polar_cap_kv(speed, bx, by, bz),
    }


def build_storm_indices(
    *,
    model_dst_raw: Any,
    usgs_dst_raw: Any,
    kyoto_dst_raw: Any,
    driver: dict[str, Any] | None,
    now: dt.datetime,
    model_history_hours: float = 3.0,
    observed_history_hours: float = 48.0,
    kyoto_history_hours: float = 168.0,
) -> dict[str, Any]:
    """Assemble the `geomagnetic-storm-indices` block.

    `driver` is the newest propagated solar-wind record (NOAA's own column
    names), or `None` when the solar-wind guard has withheld it.  A missing
    driver produces a block with no derived coupling rather than a block with
    invented coupling: a missing panel is honest, a frozen one is not.
    """
    # The modelled series legitimately extends into the future, so its window
    # is [now - model_history_hours, now + MODEL_FORWARD_WINDOW_HOURS]. Passing
    # the lead as the window *end* without widening the span would have kept
    # only the forward half and left the panel with no modelled history to
    # grade -- exactly the "filter that silently excludes" shape this project
    # has shipped before.
    model = thin_series(
        parse_swpc_dst(model_dst_raw),
        cadence_minutes=1,
        history_hours=model_history_hours + MODEL_FORWARD_WINDOW_HOURS,
        now=now + dt.timedelta(hours=MODEL_FORWARD_WINDOW_HOURS),
    )
    observed = thin_series(
        parse_usgs_dst(usgs_dst_raw, "Dst3"),
        cadence_minutes=5,
        history_hours=observed_history_hours,
        now=now,
    )
    observed_four = thin_series(
        parse_usgs_dst(usgs_dst_raw, "Dst4"),
        cadence_minutes=5,
        history_hours=observed_history_hours,
        now=now,
    )
    kyoto = thin_series(
        parse_swpc_dst(kyoto_dst_raw),
        cadence_minutes=60,
        history_hours=kyoto_history_hours,
        now=now,
    )

    latest_model = model[-1] if model else None
    latest_observed = observed[-1] if observed else None
    latest_kyoto = kyoto[-1] if kyoto else None

    # The forward lead is what makes the modelled series worth showing, so it
    # is measured rather than asserted: the run's own newest valid time minus
    # the moment this bundle was built.
    lead_minutes = None
    if latest_model is not None:
        latest_model_at = _parse_time(latest_model["at"])
        if latest_model_at is not None:
            lead_minutes = round((latest_model_at - now).total_seconds() / 60.0, 1)

    observed_latency_seconds = None
    if latest_observed is not None:
        observed_at = _parse_time(latest_observed["at"])
        if observed_at is not None:
            observed_latency_seconds = round((now - observed_at).total_seconds())

    derived: dict[str, Any] | None = None
    drivers_block: dict[str, Any] | None = None
    if driver:
        terms = derive_driver_terms(driver)
        speed = _finite(driver.get("speed"))
        drivers_block = {
            "observedAt": _iso_z(_parse_time(driver.get("time_tag")) or now),
            "propagatedArrivalAt": (
                _iso_z(arrival)
                if (arrival := _parse_time(driver.get("propagated_time_tag"))) is not None
                else None
            ),
            "speedKps": _round(speed, 2),
            "densityCm3": _round(_finite(driver.get("density")), 3),
            "temperatureK": _round(_finite(driver.get("temperature")), 0),
            "bxNt": _round(_finite(driver.get("bx")), 2),
            "byNt": _round(_finite(driver.get("by")), 2),
            "bzGsmNt": _round(_finite(driver.get("bz")), 2),
            "btNt": _round(_finite(driver.get("bt")), 2),
            "vxKps": _round(_finite(driver.get("vx")), 1),
            "vyKps": _round(_finite(driver.get("vy")), 1),
            "vzKps": _round(_finite(driver.get("vz")), 1),
            "dynamicPressureNpa": _round(terms["dynamicPressureNpa"], 4),
            "magneticPressureNpa": _round(terms["magneticPressureNpa"], 5),
        }
        derived = {
            "clockAngleDeg": _round(terms["clockAngleDeg"], 1),
            "transverseImfNt": _round(terms["transverseImfNt"], 3),
            "newellCoupling": _round(terms["newellCoupling"], 1),
            "newellUnits": "(km/s)^(4/3) nT^(2/3), unnormalised as published",
            "newellCitation": "Newell et al. (2007) JGR 112 A01206, doi:10.1029/2006JA012015",
            "newellCalibration": NEWELL_CALIBRATION,
            "newellCalibrationNote": NEWELL_CALIBRATION_NOTE,
            "epsilonGw": _round(terms["epsilonGw"], 3),
            "epsilonNote": (
                "Akasofu 1981. Shown for historical context only: Lockwood (2019) "
                "identified an error in its theoretical basis and Finch & Lockwood "
                "(2007) found it performs worse than other coupling functions."
            ),
            "boyleCpcpKv": _round(terms["boyleCpcpKv"], 1),
            "boyleSaturationKv": BOYLE_SATURATION_KV,
            "boyleNote": (
                "The Boyle regression is linear; the observed cross-polar-cap "
                "potential saturates near 200-250 kV. The uncapped value is "
                "published so the saturation line can be drawn rather than hidden."
            ),
        }
        if speed is not None:
            derived["speedKps"] = _round(speed, 2)

    # The ring current is derived from the OBSERVED index where one exists, and
    # from the modelled one only as a fallback, because the DPS relation is a
    # statement about a measured surface depression.
    energy_source = "usgs-dst3-observed" if latest_observed else ("noaa-geospace-modelled" if latest_model else None)
    energy_dst = (
        latest_observed["dstNt"] if latest_observed else (latest_model["dstNt"] if latest_model else None)
    )
    ring_energy = ring_current_energy_joules(energy_dst)

    block: dict[str, Any] = {
        "kind": "geomagnetic-storm-indices",
        "status": "model-and-observed",
        "validAt": _iso_z(now),
        "drivers": drivers_block,
        "derived": derived,
        "dst": {
            "modelled": {
                "status": "model",
                "label": "MODELLED Dst - a physics-model estimate, not a measurement",
                "source": "NOAA Geospace SWMF dst_sm (US Government work, public domain)",
                "url": NOAA_MODEL_DST,
                "cadenceMinutes": 1,
                "latestNt": _round(latest_model["dstNt"], 2) if latest_model else None,
                "latestAt": latest_model["at"] if latest_model else None,
                "forwardLeadMinutes": lead_minutes,
                "note": (
                    "The same operational Geospace/SWMF run whose magnetopause driver, "
                    "cut planes and RBE electron fields this site already ingests."
                ),
                "series": model,
            },
            "observed": {
                "status": "observed",
                "label": "OBSERVED Dst3 - three USGS observatories (HON, SJG, GUA)",
                "source": "USGS Geomagnetism Program (US Government work, public domain)",
                "url": USGS_DST,
                "cadenceMinutes": 1,
                "publishedCadenceMinutes": 5,
                "latestNt": _round(latest_observed["dstNt"], 2) if latest_observed else None,
                "latestAt": latest_observed["at"] if latest_observed else None,
                "latencySeconds": observed_latency_seconds,
                "note": (
                    "Dst3 uses a USGS-only station set and runs about fourteen minutes "
                    "fresher than the four-observatory Dst4; the two differ by a couple "
                    "of nT because they are different station sets, not because either "
                    "is wrong."
                ),
                "series": observed,
                "dst4Series": observed_four,
                "dst4LatestNt": _round(observed_four[-1]["dstNt"], 2) if observed_four else None,
                "dst4LatestAt": observed_four[-1]["at"] if observed_four else None,
            },
            "kyoto": {
                "status": "observed",
                "label": "Kyoto quicklook Dst, hourly - the index the world quotes",
                "source": "WDC for Geomagnetism, Kyoto, republished by NOAA SWPC",
                "url": KYOTO_DST,
                "cadenceMinutes": 60,
                "latestNt": _round(latest_kyoto["dstNt"], 2) if latest_kyoto else None,
                "latestAt": latest_kyoto["at"] if latest_kyoto else None,
                "citation": KYOTO_CITATION,
                "statusNote": KYOTO_STATUS_NOTE,
                "series": kyoto,
            },
            "separationNote": (
                "Three series, three evidence classes, never merged. The modelled "
                "series runs ahead of real time and the two observed series catch up "
                "to it at about four minutes and about fifty."
            ),
        },
        "ringCurrent": {
            "status": "model-derived",
            "energyJoules": None if ring_energy is None else round(ring_energy, -10),
            "energySourceSeries": energy_source,
            "energyDstNt": _round(energy_dst, 2),
            "method": (
                "Dessler-Parker-Sckopke: E = |Dst| * 2 pi B0 Re^3 / mu0 with "
                f"B0 = {DPS_DIPOLE_SURFACE_FIELD_NT:.0f} nT, i.e. "
                f"{DPS_JOULES_PER_NT:.3e} J per nT of depression."
            ),
            "joulesPerNt": DPS_JOULES_PER_NT,
            "dipoleExternalFieldEnergyJ": DIPOLE_EXTERNAL_FIELD_ENERGY_J,
            "relation": (
                "Dst is not merely correlated with the ring current: the "
                "Dessler-Parker-Sckopke relation makes the low-latitude surface "
                "depression proportional to the total kinetic energy of the trapped "
                "particle population. Reading Dst IS reading the ring current."
            ),
            "uncertainty": (
                "Good to about a factor of two. About 28% of the measured depression "
                "is induced inside the solid Earth; the magnetotail carries roughly a "
                "further quarter; and DPS counts particle kinetic energy only, while "
                "ionospheric Joule heating dominates the storm's actual energy budget "
                "(~81% of dissipation during the April 2023 main phase)."
            ),
            "pressureCorrectedDst": (
                pressure_corrected_dst(
                    energy_dst,
                    drivers_block["dynamicPressureNpa"] if drivers_block else None,
                )
                if drivers_block
                else None
            ),
            "pressureCorrectionNote": (
                "Two standard corrections for the compression contribution are "
                "published side by side. O'Brien & McPherron (2000) and Burton et al. "
                "(1975) agree at nominal solar wind and disagree by 18 nT at a 10 nPa "
                "shock. Neither is presented as the correction."
            ),
            "compositionModel": (
                "The operational run's ring-current module is configured with a fixed "
                "80% H+ / 20% O+ composition and a 10-hour decay timescale."
            ),
            "compositionReality": (
                "O+ carries 6% of ring-current energy density when quiet and 21% when "
                "active, exceeds 50% in great storms, and reached over 65% at L = 5-7 "
                "in March 1991 (Daglis et al. 1999). The energy is unambiguously "
                "solar; during a big storm most of the particles carrying it came from "
                "Earth's own atmosphere."
            ),
        },
        "phase": classify_storm_phase(
            # Kyoto first: the published storm thresholds are defined on that
            # index, and USGS Dst3 sits on a different baseline (it read +20.5
            # nT at the same moment Kyoto read +7 on 2026-08-08), so ranking it
            # first would label quiet days as storms.
            kyoto or model or observed,
            now=now,
            series_name=(
                "kyoto-quicklook" if kyoto else ("noaa-geospace-modelled" if model else
                                                 ("usgs-dst3" if observed else None))
            ),
        ),
        "limitations": [
            "The modelled series is a physics-model estimate that runs ahead of real "
            "time. It is not a measurement and is never merged with the observed ones.",
            "The Kyoto quicklook index is explicitly for monitoring only; its final "
            "values are routinely revised by 20-30 nT.",
            "1-minute SYM-H is not available from any live public feed. Storm replay "
            "of an archived event gets a better index than this live page does.",
            "The NOAA G-scale shown elsewhere on this site is Kp-based and cannot "
            "resolve storm onset; Dst is the physical measure.",
        ],
    }
    return block


def _round(value: float | None, digits: int) -> float | None:
    if value is None or not math.isfinite(value):
        return None
    rounded = round(value, digits)
    return rounded if digits > 0 else float(rounded)


def fetch_storm_sources(
    fetch_json: Callable[[str, int], Any],
    *,
    max_age_seconds: int = 4 * 60,
) -> dict[str, Any]:
    """Fetch the three Dst products, tolerating any one of them being down.

    The caller supplies the fetcher, which is expected to stop on a non-200
    rather than retry - NOAA and USGS both publish a cadence and this project
    has been firewalled once already for ignoring an error response.  A source
    that fails is recorded as absent, and the artifact simply omits that trace.
    """
    results: dict[str, Any] = {"errors": {}}
    for key, url in (("model", NOAA_MODEL_DST), ("usgs", USGS_DST), ("kyoto", KYOTO_DST)):
        try:
            results[key] = fetch_json(url, max_age_seconds)
        except Exception as error:  # noqa: BLE001 - one dead source must not stop a publish
            results[key] = None
            results["errors"][key] = str(error)
            print(f"WARNING: storm index source unavailable ({key}): {error}")
    return results


def storm_source_records(block: dict[str, Any]) -> list[dict[str, Any]]:
    """Rows for the release's `sources` list, one per Dst series present."""
    rows: list[dict[str, Any]] = []
    dst = block.get("dst") or {}
    for key, product, status in (
        ("modelled", "Dst (NOAA Geospace SWMF, modelled)", "model"),
        ("observed", "Dst3 (USGS, observed)", "observed"),
        ("kyoto", "Dst (WDC Kyoto quicklook, hourly)", "observed"),
    ):
        entry = dst.get(key) or {}
        if entry.get("latestAt") is None:
            continue
        row = {
            "product": product,
            "url": entry.get("url"),
            "status": status,
            "observedAt": entry.get("latestAt"),
        }
        if entry.get("citation"):
            row["citation"] = entry["citation"]
        rows.append(row)
    return rows


__all__ = [
    "BOYLE_SATURATION_KV",
    "DPS_JOULES_PER_NT",
    "KYOTO_DST",
    "NOAA_MODEL_DST",
    "USGS_DST",
    "akasofu_epsilon_gw",
    "boyle_cross_polar_cap_kv",
    "build_storm_indices",
    "STORM_PHASE_BASELINE_NOTE",
    "classify_storm_phase",
    "clock_angle_degrees",
    "clock_angle_rad",
    "derive_driver_terms",
    "dynamic_pressure_npa",
    "fetch_storm_sources",
    "magnetic_pressure_npa",
    "newell_coupling",
    "parse_swpc_dst",
    "parse_usgs_dst",
    "pressure_corrected_dst",
    "ring_current_energy_joules",
    "storm_source_records",
    "thin_series",
]
