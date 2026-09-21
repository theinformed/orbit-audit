"""Independent corroboration of the published solar-wind sample.

Why this module exists
----------------------

Until 2026-08-07 the publisher selected the current solar-wind and IMF sample
with a single rule::

    active = lambda row: bool(row.get("active")) and int(row.get("overall_quality") or 0) == 0

That trusts one spacecraft's own opinion of itself.  During the May 2024 Gannon
storm DSCOVR's Faraday cup went **silently** wrong: from 2024-05-11 13:43 UT it
reported ~475 km/s and ~2 cm^-3 while ACE and OMNI reported 770-1000 km/s and
16-29 cm^-3, and ``overall_quality`` still read ``0`` -- "nominal" -- for 549 of
those minutes (measured, see ``docs/gannon-storm-module-design.md`` §4.1.1 and
the reconstruction in ``tests/test_solar_wind_guard.py``).

The consequence for this site is not cosmetic.  Dynamic pressure goes as
``n * V**2``, so halving V and dividing n by eight understates Pdyn by a factor
of ~30.  ``shue_boundary()`` scales the subsolar magnetopause standoff as
``Pdyn ** (-1/6.6)``, so the site would have drawn an *expanded* magnetosphere
during the most severe compression event in twenty years, and every honesty
label would have said the data was nominal.

Design contract
---------------

1. **A source's self-assessment is evidence, never proof.**  Upstream quality
   flags are recorded in the verdict and shown to the visitor, but they cannot
   on their own promote a sample to "corroborated".

2. **Corroboration means a different spacecraft.**  Two products derived from
   the same instrument do not corroborate each other.  Callers declare the
   spacecraft; the guard groups by it and refuses to count a source against
   itself.

3. **Physics is a second opinion on the instrument.**  Absolute plausibility
   bounds catch absurd values; step coherence between the plasma instrument and
   the magnetometer catches a plasma instrument that has stopped tracking the
   real wind while the field says nothing happened.

4. **A real shock must survive the guard.**  Rate-of-change alone is never a
   rejection.  A large plasma step is accepted when the *magnetic field* moves
   with it, which is what a real MHD discontinuity does, and disputed only when
   the field stays flat, which no MHD discontinuity does.

5. **Disagreement is published, not resolved silently.**  Every check's numbers
   travel into the artifact so the failure is visible to a visitor, not only to
   a log reader.

Nothing here performs I/O.  ``assess_solar_wind`` is a pure function of the
samples handed to it, which is why the May 2024 event can be replayed through
exactly the code that runs in production.
"""

from __future__ import annotations

import bisect
import datetime as dt
import math
import statistics
from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

__all__ = [
    "PlasmaSample",
    "FieldSample",
    "Thresholds",
    "GuardCheck",
    "SourceComparison",
    "GuardVerdict",
    "DEFAULT_THRESHOLDS",
    "assess_solar_wind",
    "assess_imf",
    "FieldVerdict",
    "rtsw_plasma_samples",
    "rtsw_field_samples",
    "active_spacecraft",
    "assess_rtsw",
    "PublishDecision",
    "dynamic_pressure_npa",
    "alfven_speed_kps",
    "expected_proton_temperature_k",
]


# --------------------------------------------------------------------------
# Inputs
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class PlasmaSample:
    """One minute of solar-wind plasma moments from one spacecraft.

    ``spacecraft`` is the physical platform (``"DSCOVR"``, ``"ACE"``,
    ``"IMAP"``...).  ``product`` names the processing chain that produced it, so
    two doors onto the same instrument can be told apart.  ``source_quality`` is
    whatever flag the upstream published; it is reported, never trusted alone.
    """

    spacecraft: str
    observed_at: dt.datetime
    speed_kps: float | None = None
    density_cm3: float | None = None
    temperature_k: float | None = None
    product: str = ""
    source_quality: int | None = None
    source_active: bool | None = None


@dataclass(frozen=True)
class FieldSample:
    """One minute of interplanetary magnetic field from one spacecraft.

    The magnetometer is a *different instrument* from the Faraday cup even when
    it flies on the same spacecraft, which is what makes the step-coherence
    check in this module meaningful for a single-spacecraft failure.
    """

    spacecraft: str
    observed_at: dt.datetime
    bt_nt: float | None = None
    bz_gsm_nt: float | None = None
    product: str = ""
    source_quality: int | None = None


@dataclass(frozen=True)
class Thresholds:
    """Every number the guard decides with, in one reviewable place.

    Justification for each value is in the module docstring of the constant
    ``DEFAULT_THRESHOLDS`` below and in ``docs/SCIENTIFIC-LAYERS.md``.
    """

    # --- absolute physical plausibility (absurdity bounds, not storm limits) --
    speed_min_kps: float = 200.0
    speed_max_kps: float = 2500.0
    density_min_cm3: float = 0.01
    density_max_cm3: float = 200.0
    temperature_min_k: float = 3.0e3
    temperature_max_k: float = 3.0e6
    bt_min_nt: float = 0.1
    bt_max_nt: float = 200.0
    dynamic_pressure_min_npa: float = 0.005
    dynamic_pressure_max_npa: float = 300.0

    # --- window construction -------------------------------------------------
    window_minutes: int = 61
    min_window_samples: int = 10
    max_sample_age_minutes: int = 90

    # --- cross-source agreement ---------------------------------------------
    speed_relative_tolerance: float = 0.25
    speed_absolute_tolerance_kps: float = 40.0
    density_ratio_tolerance: float = 5.0

    # --- step coherence ------------------------------------------------------
    step_window_minutes: int = 15
    step_speed_fraction: float = 0.15
    step_density_fraction: float = 0.50
    step_field_fraction: float = 0.10
    step_scan_hours: int = 24

    # --- advisory internal consistency --------------------------------------
    temperature_ratio_advisory: float = 10.0


DEFAULT_THRESHOLDS = Thresholds()
"""Chosen values and why.

Absolute bounds are deliberately *absurdity* bounds -- wide enough that no real
event is ever clipped by them.  They exist to catch a stuck register or a unit
error, and they explicitly do **not** catch the Gannon failure, which sat
comfortably inside every one of them.  That is the point: bounds alone are not
a guard.

* ``speed 200-2500 km/s``.  The slowest sustained solar wind measured at 1 AU is
  around 230-250 km/s and OMNI's 1-minute record low is near 200 km/s.  The
  fastest 1-minute OMNI value on record is 1189 km/s (2003-10-29); shock transit
  speeds inferred for the August 1972 and 1859 Carrington events reach roughly
  2000-2850 km/s.  2500 km/s is therefore beyond anything measured in situ.
* ``density 0.01-200 cm^-3``.  Quiet wind is 3-10 cm^-3; the densest CME sheaths
  and filament material observed at 1 AU reach ~100-150 cm^-3.
* ``temperature 3e3-3e6 K``.  Quiet 3e4-1e5 K; cold magnetic-cloud interiors
  reach a few 1e3 K; shocked sheaths reach ~2e6 K.
* ``|B| 0.1-200 nT``.  The Gannon peak was 74.5 nT and March 1989 reached ~90 nT.
* ``Pdyn 0.005-300 nPa``.  The Gannon peak was ~70 nPa, about 47x quiet.

``speed_relative_tolerance = 0.25`` and ``density_ratio_tolerance = 5.0`` are
measured, not assumed.  Comparing 61-minute medians of DSCOVR against ACE over
2024-05-02..05 (quiet) and 2024-05-10 00:00 -> 2024-05-11 13:43 (the storm's
healthy phase, shock included), the speed disagreement stays below 0.11 at the
99th percentile, while the faulted interval never falls below 0.37.  The gap is
where the threshold sits.  The fixture in ``tests/data`` reproduces the ends of
that range on the production code path: 0.029 quiet, 0.009 across the genuine
shock, 0.400 in the sustained fault.

Density is intrinsically noisier between two L1 monitors tens of Earth radii
apart -- a factor of 2 is routine -- so a factor of 5 is required before density
alone is called a disagreement.  That headroom is not theoretical: on 2026-08-07
the live SWPC feed carried SOLAR1 at 5.8 cm^-3 and IMAP at 20.3 cm^-3 in the same
hour, a factor of 3.5 between two healthy instruments, while their speeds agreed
to 2%.  A re-measurement on 2026-08-08 found ACE at 4.3 cm^-3 against IMAP at
28.0 cm^-3 in one hour -- a factor of 6.5 between two instruments both reporting
nominal, with speeds agreeing to 2% -- which is why density is not allowed to
condemn a source on its own.

**Density does not catch Gannon, and it is not asked to.**  The instantaneous
DSCOVR/ACE density discrepancy reached roughly a factor of 14 at its worst
(~2 cm^-3 against ~29 cm^-3), but over the 61-minute medians the guard actually
compares, the sustained-fault window is a factor of 3.0 -- *below* this
threshold.  Speed does all the real work in the cross-source check; density is a
corroborating signal that widens the evidence, never the primary one.  An earlier
draft of this docstring claimed the density check caught Gannon "comfortably";
that was wrong at the window the guard uses, and the correction is recorded here
rather than removed.

``min_window_samples = 10`` because L1 telemetry is bursty.  IMAP delivered
1,201 samples in 24 hours on 2026-08-07 but only 8 in one particular hour, and a
witness that reports ten minutes' worth of data in the comparison window is
still a witness.

``window_minutes = 61``.  A single minute cannot separate a real transient from
an instrument fault: at 1-minute resolution the healthy DSCOVR/ACE speed
disagreement reaches 0.49 across the shock, which overlaps the faulted range.
An hour-long median removes the convection-lag difference between two spacecraft
that are physically separated while preserving a sustained bias.  The cost is
that the guard needs about an hour to become confident about a *new* fault; it
reports ``uncorroborated`` rather than ``ok`` until then.

``step_field_fraction = 0.10``.  Across every MHD discontinuity that changes the
bulk plasma appreciably, ``|B|`` changes too: fast and slow shocks compress or
rarefy the field with the plasma; a tangential discontinuity conserves total
pressure ``p + B^2/2mu0``, so a large density fall at constant temperature must
be balanced by a field *rise*; a rotational discontinuity conserves ``|B|``,
``n`` and ``V`` together.  A plasma instrument that drops density eightfold and
speed by 37% while the magnetometer on the same spacecraft moves 2% is not
observing an MHD structure.  At the genuine 2024-05-10 17:05 shock the field
stepped by far more than 10%, so this rule stays silent there by construction.
"""


# --------------------------------------------------------------------------
# Physics helpers
# --------------------------------------------------------------------------


def dynamic_pressure_npa(density_cm3: float | None, speed_kps: float | None) -> float | None:
    """Proton ram pressure in nPa.  Same constant the publisher already uses."""
    if density_cm3 is None or speed_kps is None:
        return None
    return 1.6726e-6 * density_cm3 * speed_kps**2


def alfven_speed_kps(bt_nt: float | None, density_cm3: float | None) -> float | None:
    """V_A = B / sqrt(mu0 * n * m_p), reduced to 21.8 * B[nT] / sqrt(n[cm^-3])."""
    if bt_nt is None or density_cm3 is None or density_cm3 <= 0:
        return None
    return 21.8 * bt_nt / math.sqrt(density_cm3)


def expected_proton_temperature_k(speed_kps: float | None) -> float | None:
    """Empirical solar-wind speed/temperature relation.

    Lopez & Freeman (1986), as restated by Elliott et al. (2012): the ordinary
    (non-transient) solar wind has a tight relation between bulk speed and
    proton temperature.  Used here only as an *advisory* signal, because
    magnetic-cloud ejecta are legitimately far colder than the relation predicts
    and would otherwise be rejected as faulty during exactly the events this
    site is for.
    """
    if speed_kps is None or speed_kps <= 0:
        return None
    if speed_kps < 500.0:
        return max(1.0, (0.031 * speed_kps - 5.1) ** 2 * 1.0e3)
    return max(1.0, (0.51 * speed_kps - 142.0) * 1.0e3)


# --------------------------------------------------------------------------
# Outputs
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class GuardCheck:
    name: str
    outcome: str  # "pass" | "fail" | "advisory" | "skipped"
    detail: str
    numbers: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {"check": self.name, "outcome": self.outcome, "detail": self.detail, **({"numbers": self.numbers} if self.numbers else {})}


@dataclass(frozen=True)
class SourceComparison:
    spacecraft: str
    product: str
    samples: int
    speed_kps: float | None
    density_cm3: float | None
    speed_difference_fraction: float | None
    density_ratio: float | None
    agrees: bool | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "spacecraft": self.spacecraft,
            "product": self.product or None,
            "windowSamples": self.samples,
            "speedKps": _round(self.speed_kps, 1),
            "densityCm3": _round(self.density_cm3, 2),
            "speedDifferenceFraction": _round(self.speed_difference_fraction, 3),
            "densityRatio": _round(self.density_ratio, 2),
            "agrees": self.agrees,
        }


@dataclass(frozen=True)
class GuardVerdict:
    """What the publisher should do, and everything the visitor should be told."""

    verdict: str  # "ok" | "uncorroborated" | "disputed" | "rejected" | "substituted"
    publish_plasma: bool
    publish_derived: bool
    resolved_spacecraft: str
    resolved_label: str
    speed_kps: float | None
    density_cm3: float | None
    temperature_k: float | None
    notice: str
    checks: tuple[GuardCheck, ...]
    comparisons: tuple[SourceComparison, ...]
    thresholds: Thresholds
    fault_onset: dt.datetime | None = None
    """Earliest time from which this spacecraft's plasma may not be trusted.

    History before it is still publishable -- the storm's earlier hours are real
    and belong on the page.  Everything from here on is withheld.
    """

    @property
    def degraded(self) -> bool:
        return self.verdict in {"disputed", "rejected", "substituted"}

    def as_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "publishesValue": self.publish_plasma,
            "publishesDerivedPressure": self.publish_derived,
            "resolvedSpacecraft": self.resolved_spacecraft,
            "notice": self.notice,
            "faultOnset": None if self.fault_onset is None else self.fault_onset.isoformat().replace("+00:00", "Z"),
            "checks": [check.as_dict() for check in self.checks],
            "crossChecks": [comparison.as_dict() for comparison in self.comparisons],
            "thresholds": {
                "speedRelativeTolerance": self.thresholds.speed_relative_tolerance,
                "speedAbsoluteToleranceKps": self.thresholds.speed_absolute_tolerance_kps,
                "densityRatioTolerance": self.thresholds.density_ratio_tolerance,
                "windowMinutes": self.thresholds.window_minutes,
                "stepWindowMinutes": self.thresholds.step_window_minutes,
                "stepFieldFraction": self.thresholds.step_field_fraction,
                "plausibleSpeedKps": [self.thresholds.speed_min_kps, self.thresholds.speed_max_kps],
                "plausibleDensityCm3": [self.thresholds.density_min_cm3, self.thresholds.density_max_cm3],
                "plausibleTemperatureK": [self.thresholds.temperature_min_k, self.thresholds.temperature_max_k],
                "plausibleBtNt": [self.thresholds.bt_min_nt, self.thresholds.bt_max_nt],
                "plausibleDynamicPressureNpa": [self.thresholds.dynamic_pressure_min_npa, self.thresholds.dynamic_pressure_max_npa],
            },
        }


# --------------------------------------------------------------------------
# Internals
# --------------------------------------------------------------------------


def _round(value: float | None, digits: int) -> float | None:
    return None if value is None else round(value, digits)


def _as_utc(value: dt.datetime) -> dt.datetime:
    if value.tzinfo is None:
        # A naive timestamp here would be localised to the host timezone, and
        # bigmem-PC runs EDT.  Refuse rather than silently shift by four hours;
        # pipeline/thermosphere.py has the same trap recorded against it.
        raise ValueError("solar-wind guard requires timezone-aware timestamps")
    return value.astimezone(dt.timezone.utc)


def _median(values: Iterable[float]) -> float | None:
    collected = [value for value in values if value is not None and math.isfinite(value)]
    if not collected:
        return None
    return float(statistics.median(collected))


@dataclass(frozen=True)
class _Window:
    spacecraft: str
    product: str
    samples: int
    speed_kps: float | None
    density_cm3: float | None
    temperature_k: float | None
    quality_flags: tuple[int, ...]


class _Index:
    """Samples grouped by spacecraft and sorted once, so window slicing is a bisect.

    Without this the guard is O(samples) per window and the replay harness --
    which evaluates thousands of epochs -- becomes minutes rather than seconds.
    Production calls it once per publish cycle, but the same cost applies.
    """

    def __init__(self, rows: Sequence[Any]) -> None:
        self.by_spacecraft: dict[str, list[Any]] = {}
        self.all: list[Any] = []
        for row in rows:
            stamp = _as_utc(row.observed_at)
            self.by_spacecraft.setdefault(row.spacecraft, []).append((stamp, row))
            self.all.append((stamp, row))
        for bucket in self.by_spacecraft.values():
            bucket.sort(key=lambda item: item[0])
        self.all.sort(key=lambda item: item[0])
        self._keys = {name: [item[0] for item in bucket] for name, bucket in self.by_spacecraft.items()}
        self._all_keys = [item[0] for item in self.all]

    def slice(self, spacecraft: str | None, start: dt.datetime, end: dt.datetime) -> list[Any]:
        if spacecraft is None:
            keys, bucket = self._all_keys, self.all
        else:
            keys = self._keys.get(spacecraft)
            bucket = self.by_spacecraft.get(spacecraft)
            if keys is None or bucket is None:
                return []
        low = bisect.bisect_right(keys, start)
        high = bisect.bisect_right(keys, end)
        return [item[1] for item in bucket[low:high]]

    def spacecraft_names(self) -> list[str]:
        return sorted(self.by_spacecraft)


def _window(
    index: _Index,
    spacecraft: str,
    end: dt.datetime,
    minutes: int,
) -> _Window:
    inside = index.slice(spacecraft, end - dt.timedelta(minutes=minutes), end)
    products = sorted({row.product for row in inside if row.product})
    return _Window(
        spacecraft=spacecraft,
        product=products[0] if len(products) == 1 else ", ".join(products),
        samples=len(inside),
        speed_kps=_median(row.speed_kps for row in inside),
        density_cm3=_median(row.density_cm3 for row in inside),
        temperature_k=_median(row.temperature_k for row in inside),
        quality_flags=tuple(sorted({row.source_quality for row in inside if row.source_quality is not None})),
    )


def _field_window(
    index: _Index,
    spacecraft: str | None,
    end: dt.datetime,
    minutes: int,
) -> tuple[float | None, float | None, int]:
    inside = index.slice(spacecraft, end - dt.timedelta(minutes=minutes), end)
    return _median(row.bt_nt for row in inside), _median(row.bz_gsm_nt for row in inside), len(inside)


def _bounds_check(
    label: str,
    value: float | None,
    low: float,
    high: float,
    unit: str,
) -> tuple[bool, str]:
    if value is None:
        return True, f"{label} unavailable"
    if value < low or value > high:
        return False, f"{label} {value:g} {unit} is outside the physically plausible range {low:g}-{high:g} {unit}"
    return True, f"{label} {value:g} {unit} is inside {low:g}-{high:g} {unit}"


# --------------------------------------------------------------------------
# The guard
# --------------------------------------------------------------------------


def assess_solar_wind(
    *,
    primary_spacecraft: str,
    plasma: Sequence[PlasmaSample],
    field_samples: Sequence[FieldSample] = (),
    now: dt.datetime,
    thresholds: Thresholds = DEFAULT_THRESHOLDS,
) -> GuardVerdict:
    """Decide whether the primary spacecraft's plasma sample may be published.

    ``plasma`` may contain samples from any number of spacecraft at any cadence;
    the guard groups them itself.  ``now`` is the reference time the window ends
    at -- in production the observation time of the sample the publisher wants
    to ship, in the replay harness the time being replayed.
    """
    now = _as_utc(now)
    checks: list[GuardCheck] = []
    plasma_index = _Index(plasma)
    field_index = _Index(field_samples)

    primary = _window(plasma_index, primary_spacecraft, now, thresholds.window_minutes)
    # The publishable sample is the newest one that actually carries moments,
    # not simply the newest row: a single missing minute must not be read as a
    # failure of the instrument.
    oldest_allowed = now - dt.timedelta(minutes=thresholds.max_sample_age_minutes)
    instant = [
        row
        for row in plasma
        if row.spacecraft == primary_spacecraft
        and oldest_allowed <= _as_utc(row.observed_at) <= now
        and row.speed_kps is not None
        and row.density_cm3 is not None
    ]
    instant.sort(key=lambda row: _as_utc(row.observed_at))
    newest = instant[-1] if instant else None

    speed = newest.speed_kps if newest else None
    density = newest.density_cm3 if newest else None
    temperature = newest.temperature_k if newest else None

    # ---- 0. the source's own opinion, recorded but not trusted --------------
    checks.append(
        GuardCheck(
            name="upstream-self-report",
            outcome="advisory",
            detail=(
                f"{primary_spacecraft} reports quality flag(s) {list(primary.quality_flags) or 'none'}. "
                "This is recorded for the reader and is never sufficient on its own: during the "
                "May 2024 Gannon storm DSCOVR reported nominal quality for 549 minutes while its "
                "plasma speed was wrong by a factor of about two."
            ),
            numbers={"qualityFlags": list(primary.quality_flags)},
        )
    )

    # ---- 1. absolute physical plausibility ---------------------------------
    bt_now, _bz_now, _field_count = _field_window(field_index, None, now, thresholds.window_minutes)
    pressure = dynamic_pressure_npa(density, speed)
    bound_results = [
        _bounds_check("speed", speed, thresholds.speed_min_kps, thresholds.speed_max_kps, "km/s"),
        _bounds_check("density", density, thresholds.density_min_cm3, thresholds.density_max_cm3, "cm^-3"),
        _bounds_check("temperature", temperature, thresholds.temperature_min_k, thresholds.temperature_max_k, "K"),
        _bounds_check("|B|", bt_now, thresholds.bt_min_nt, thresholds.bt_max_nt, "nT"),
        _bounds_check("dynamic pressure", pressure, thresholds.dynamic_pressure_min_npa, thresholds.dynamic_pressure_max_npa, "nPa"),
    ]
    failed_bounds = [detail for ok, detail in bound_results if not ok]
    checks.append(
        GuardCheck(
            name="physical-bounds",
            outcome="fail" if failed_bounds else "pass",
            detail="; ".join(failed_bounds) if failed_bounds else "every reported quantity is inside its physically plausible range",
            numbers={
                "speedKps": _round(speed, 1),
                "densityCm3": _round(density, 2),
                "temperatureK": _round(temperature, 0),
                "btNt": _round(bt_now, 2),
                "dynamicPressureNpa": _round(pressure, 3),
            },
        )
    )

    # ---- 2. internal consistency, advisory ---------------------------------
    expected_t = expected_proton_temperature_k(speed)
    v_alfven = alfven_speed_kps(bt_now, density)
    mach = speed / v_alfven if speed is not None and v_alfven else None
    consistency_notes: list[str] = []
    if expected_t and temperature:
        ratio = temperature / expected_t
        if ratio > thresholds.temperature_ratio_advisory or ratio < 1.0 / thresholds.temperature_ratio_advisory:
            consistency_notes.append(
                f"proton temperature is {ratio:.1f}x the Lopez-Freeman speed/temperature relation "
                "(normal inside cold magnetic-cloud ejecta, so advisory only)"
            )
    if mach is not None and mach < 1.0:
        consistency_notes.append(
            f"Alfven Mach number {mach:.2f} < 1: sub-Alfvenic solar wind at 1 AU is rare but real "
            "and did occur during the May 2024 storm, so advisory only"
        )
    checks.append(
        GuardCheck(
            name="internal-consistency",
            outcome="advisory" if consistency_notes else "pass",
            detail="; ".join(consistency_notes) if consistency_notes else "speed, temperature, density and field magnitude are mutually consistent",
            numbers={
                "expectedTemperatureK": _round(expected_t, 0),
                "alfvenSpeedKps": _round(v_alfven, 1),
                "alfvenMachNumber": _round(mach, 2),
            },
        )
    )

    # ---- 3. step coherence: a real shock moves the field too ---------------
    step_outcome, step_check = _step_coherence(plasma_index, field_index, primary_spacecraft, now, thresholds)
    checks.append(step_check)
    step_at = _parse_rtsw_time(step_check.numbers.get("at")) if step_outcome == "incoherent" else None

    # ---- 4. cross-source corroboration -------------------------------------
    others = [name for name in plasma_index.spacecraft_names() if name != primary_spacecraft]
    comparisons: list[SourceComparison] = []
    for spacecraft in others:
        window = _window(plasma_index, spacecraft, now, thresholds.window_minutes)
        if window.samples < thresholds.min_window_samples or window.speed_kps is None:
            continue
        speed_difference = None
        density_ratio = None
        agrees: bool | None = None
        if primary.speed_kps is not None and window.speed_kps > 0:
            speed_difference = abs(primary.speed_kps - window.speed_kps) / window.speed_kps
            tolerance = max(
                thresholds.speed_relative_tolerance,
                thresholds.speed_absolute_tolerance_kps / window.speed_kps,
            )
            agrees = speed_difference <= tolerance
        if primary.density_cm3 and window.density_cm3 and window.density_cm3 > 0:
            density_ratio = primary.density_cm3 / window.density_cm3
            if density_ratio > thresholds.density_ratio_tolerance or density_ratio < 1.0 / thresholds.density_ratio_tolerance:
                agrees = False
        comparisons.append(
            SourceComparison(
                spacecraft=spacecraft,
                product=window.product,
                samples=window.samples,
                speed_kps=window.speed_kps,
                density_cm3=window.density_cm3,
                speed_difference_fraction=speed_difference,
                density_ratio=density_ratio,
                agrees=agrees,
            )
        )

    witnesses = [row for row in comparisons if row.agrees is not None]
    disagreeing = [row for row in witnesses if row.agrees is False]
    agreeing = [row for row in witnesses if row.agrees is True]

    if not witnesses:
        cross_check = GuardCheck(
            name="cross-source",
            outcome="skipped",
            detail=(
                "no second spacecraft had enough samples in the comparison window, so this sample is "
                "published without independent corroboration"
            ),
            numbers={"witnesses": 0},
        )
    elif not disagreeing:
        cross_check = GuardCheck(
            name="cross-source",
            outcome="pass",
            detail=(
                f"{len(agreeing)} independent spacecraft ("
                + ", ".join(row.spacecraft for row in agreeing)
                + ") agree with "
                + primary_spacecraft
                + " within tolerance"
            ),
            numbers={"witnesses": len(witnesses), "agreeing": len(agreeing)},
        )
    else:
        worst = max(disagreeing, key=lambda row: row.speed_difference_fraction or 0.0)
        cross_check = GuardCheck(
            name="cross-source",
            outcome="fail",
            detail=(
                f"{primary_spacecraft} reads {primary.speed_kps:.0f} km/s where {worst.spacecraft} reads "
                f"{worst.speed_kps:.0f} km/s over the same hour"
                + (f" ({worst.speed_difference_fraction:.0%} apart)" if worst.speed_difference_fraction is not None else "")
            ),
            numbers={
                "witnesses": len(witnesses),
                "disagreeing": len(disagreeing),
                "primarySpeedKps": _round(primary.speed_kps, 1),
                "primaryDensityCm3": _round(primary.density_cm3, 2),
            },
        )
    checks.append(cross_check)

    # ---- 5. verdict ---------------------------------------------------------
    return _decide(
        primary_spacecraft=primary_spacecraft,
        primary=primary,
        speed=speed,
        density=density,
        temperature=temperature,
        checks=tuple(checks),
        comparisons=tuple(comparisons),
        disagreeing=disagreeing,
        agreeing=agreeing,
        witnesses=witnesses,
        failed_bounds=failed_bounds,
        step_outcome=step_outcome,
        step_at=step_at,
        disagreement_at=(
            min(
                filter(
                    None,
                    (
                        _disagreement_onset(plasma_index, primary_spacecraft, row.spacecraft, now, thresholds)
                        for row in disagreeing
                    ),
                ),
                default=None,
            )
            if disagreeing
            else None
        ),
        now=now,
        thresholds=thresholds,
    )


def _step_at(
    plasma: _Index,
    field_samples: _Index,
    spacecraft: str,
    boundary: dt.datetime,
    thresholds: Thresholds,
) -> tuple[str, dict[str, Any]] | None:
    """Classify the plasma/field behaviour across one candidate step boundary."""
    span = thresholds.step_window_minutes
    after = _window(plasma, spacecraft, boundary + dt.timedelta(minutes=span), span)
    before = _window(plasma, spacecraft, boundary, span)
    bt_after, _, field_after_count = _field_window(
        field_samples, spacecraft, boundary + dt.timedelta(minutes=span), span
    )
    bt_before, _, field_before_count = _field_window(field_samples, spacecraft, boundary, span)
    if field_before_count < 3 or field_after_count < 3:
        # Fall back to any magnetometer if the primary spacecraft carries none.
        bt_after, _, field_after_count = _field_window(
            field_samples, None, boundary + dt.timedelta(minutes=span), span
        )
        bt_before, _, field_before_count = _field_window(field_samples, None, boundary, span)

    if (
        before.speed_kps is None
        or after.speed_kps is None
        or before.speed_kps <= 0
        or bt_before is None
        or bt_after is None
        or bt_before <= 0
        or field_before_count < 3
        or field_after_count < 3
        or before.samples < 3
        or after.samples < 3
    ):
        return None

    speed_step = abs(after.speed_kps - before.speed_kps) / before.speed_kps
    density_step = (
        abs(after.density_cm3 - before.density_cm3) / before.density_cm3
        if before.density_cm3 and after.density_cm3 is not None and before.density_cm3 > 0
        else 0.0
    )
    field_step = abs(bt_after - bt_before) / bt_before
    # Both moments must move before a step is even considered.  Requiring
    # speed AND density is what keeps this rule silent in ordinary wind:
    # replaying 2024-05-02..05 (quiet) and 2024-05-10 00:00 -> 2024-05-11 13:43
    # (storm, shock included), an OR rule found 25 flat-field steps, almost all
    # of them harmless quiet-wind density fluctuations; the AND rule found
    # exactly one, at 2024-05-11 13:40, which is the real DSCOVR failure.
    if speed_step < thresholds.step_speed_fraction or density_step < thresholds.step_density_fraction:
        return None

    numbers = {
        "at": boundary.isoformat().replace("+00:00", "Z"),
        "speedStepFraction": _round(speed_step, 3),
        "densityStepFraction": _round(density_step, 3),
        "fieldStepFraction": _round(field_step, 3),
        "speedBeforeKps": _round(before.speed_kps, 1),
        "speedAfterKps": _round(after.speed_kps, 1),
        "densityBeforeCm3": _round(before.density_cm3, 2),
        "densityAfterCm3": _round(after.density_cm3, 2),
        "btBeforeNt": _round(bt_before, 2),
        "btAfterNt": _round(bt_after, 2),
    }
    kind = "coherent" if field_step >= thresholds.step_field_fraction else "incoherent"
    return kind, numbers


def _step_coherence(
    plasma: _Index,
    field_samples: _Index,
    spacecraft: str,
    now: dt.datetime,
    thresholds: Thresholds,
) -> tuple[str, GuardCheck]:
    """Distinguish a genuine MHD discontinuity from a plasma-instrument fault.

    A naive "the value changed too fast" rule would reject exactly the shock
    arrivals this site exists to show, so the rule is not about the size of the
    step at all: it is about whether the *magnetic field* stepped with it.

    The check looks at the **most recent significant plasma step** in the scan
    window rather than only at the last half hour.  That matters because a
    plasma instrument that jumps to a wrong value and then sits there is quiet
    again within thirty minutes; what stays true is that the last time its
    numbers moved, nothing in the magnetic field moved with them.  Trust is
    restored only by a later step that the field does corroborate.
    """
    span = thresholds.step_window_minutes
    boundary = now - dt.timedelta(minutes=span)
    earliest = now - dt.timedelta(hours=thresholds.step_scan_hours)
    latest: tuple[str, dict[str, Any]] | None = None
    while boundary >= earliest:
        found = _step_at(plasma, field_samples, spacecraft, boundary, thresholds)
        if found is not None:
            latest = found
            break
        boundary -= dt.timedelta(minutes=5)

    if latest is None:
        return "quiet", GuardCheck(
            name="step-coherence",
            outcome="pass",
            detail=(
                f"no plasma step larger than {thresholds.step_speed_fraction:.0%} in speed or "
                f"{thresholds.step_density_fraction:.0%} in density in the last {thresholds.step_scan_hours} hours"
            ),
        )

    kind, numbers = latest
    if kind == "coherent":
        return "coherent", GuardCheck(
            name="step-coherence",
            outcome="pass",
            detail=(
                f"the most recent plasma step ({numbers['speedStepFraction']:.0%} in speed, "
                f"{numbers['densityStepFraction']:.0%} in density, at {numbers['at']}) was matched by a "
                f"{numbers['fieldStepFraction']:.0%} step in the magnetic field magnitude; that is what a real "
                "interplanetary shock or discontinuity does, so it is accepted"
            ),
            numbers=numbers,
        )
    return "incoherent", GuardCheck(
        name="step-coherence",
        outcome="fail",
        detail=(
            f"the most recent plasma step ({numbers['speedStepFraction']:.0%} in speed, "
            f"{numbers['densityStepFraction']:.0%} in density, at {numbers['at']}) left the magnetic field magnitude "
            f"unchanged ({numbers['fieldStepFraction']:.0%}); no MHD discontinuity changes the plasma that much "
            "without moving |B|, so the plasma instrument is the more likely explanation"
        ),
        numbers=numbers,
    )


def _disagreement_onset(
    index: _Index,
    primary_spacecraft: str,
    witness: str,
    now: dt.datetime,
    thresholds: Thresholds,
    horizon_hours: int = 48,
) -> dt.datetime | None:
    """Walk backwards to find when the primary and a witness first diverged.

    A cross-source disagreement does not date itself the way a step does, but it
    can be dated cheaply: step the comparison window back until the two agree
    again.  This matters because NOAA's propagated driver series carries 48
    hours of history and the browser prefers it over the headline sample -- the
    truncation has to cut at the real onset, not merely at "an hour ago".
    """
    cursor = now
    earliest = now - dt.timedelta(hours=horizon_hours)
    onset: dt.datetime | None = None
    while cursor >= earliest:
        primary = _window(index, primary_spacecraft, cursor, thresholds.window_minutes)
        other = _window(index, witness, cursor, thresholds.window_minutes)
        if (
            other.samples < thresholds.min_window_samples
            or other.speed_kps is None
            or primary.speed_kps is None
            or other.speed_kps <= 0
        ):
            break
        difference = abs(primary.speed_kps - other.speed_kps) / other.speed_kps
        tolerance = max(
            thresholds.speed_relative_tolerance,
            thresholds.speed_absolute_tolerance_kps / other.speed_kps,
        )
        if difference <= tolerance:
            break
        onset = cursor - dt.timedelta(minutes=thresholds.window_minutes)
        cursor -= dt.timedelta(minutes=15)
    return onset


def _mutual_quorum(rows: Sequence[SourceComparison], thresholds: Thresholds) -> list[SourceComparison]:
    """The largest set of witnesses that agree with *each other*.

    Two independent spacecraft that agree with one another and disagree with the
    primary out-vote it.  A single dissenting witness does not: with exactly two
    readings there is no basis for deciding which instrument is at fault, and
    preferring a source by fixed rank would just encode a guess.  ACE SWEPAM is a
    1997 instrument with its own failure modes; DSCOVR has been right and ACE
    wrong on other occasions.  So one witness produces "disputed" and no value;
    two agreeing witnesses produce a substitution that says so in words.
    """
    best: list[SourceComparison] = []
    for anchor in rows:
        if anchor.speed_kps is None or anchor.speed_kps <= 0:
            continue
        cluster = [
            other
            for other in rows
            if other.speed_kps is not None
            and abs(other.speed_kps - anchor.speed_kps)
            <= max(
                thresholds.speed_relative_tolerance * anchor.speed_kps,
                thresholds.speed_absolute_tolerance_kps,
            )
        ]
        if len(cluster) > len(best):
            best = cluster
    return best


def _decide(
    *,
    primary_spacecraft: str,
    primary: _Window,
    speed: float | None,
    density: float | None,
    temperature: float | None,
    checks: tuple[GuardCheck, ...],
    comparisons: tuple[SourceComparison, ...],
    disagreeing: list[SourceComparison],
    agreeing: list[SourceComparison],
    witnesses: list[SourceComparison],
    failed_bounds: list[str],
    step_outcome: str,
    step_at: dt.datetime | None,
    disagreement_at: dt.datetime | None,
    now: dt.datetime,
    thresholds: Thresholds,
) -> GuardVerdict:
    # Where the untrustworthy stretch begins.  A step the magnetometer did not
    # corroborate dates itself precisely.  A cross-source disagreement does not,
    # so the whole comparison window is treated as suspect, which is the
    # conservative direction.
    onset_candidates = [candidate for candidate in (step_at, disagreement_at) if candidate is not None]
    onset_candidates.append(now - dt.timedelta(minutes=thresholds.window_minutes))
    fault_onset = min(onset_candidates)

    def verdict(
        name: str,
        publish: bool,
        derived: bool,
        notice: str,
        *,
        spacecraft: str = primary_spacecraft,
        label: str | None = None,
        values: tuple[float | None, float | None, float | None] | None = None,
    ) -> GuardVerdict:
        chosen = values if values is not None else (speed, density, temperature)
        return GuardVerdict(
            verdict=name,
            publish_plasma=publish,
            publish_derived=derived,
            resolved_spacecraft=spacecraft,
            resolved_label=label or spacecraft,
            speed_kps=chosen[0] if publish else None,
            density_cm3=chosen[1] if publish else None,
            temperature_k=chosen[2] if publish else None,
            notice=notice,
            checks=checks,
            comparisons=comparisons,
            thresholds=thresholds,
            fault_onset=None if name in {"ok", "uncorroborated"} else fault_onset,
        )

    if failed_bounds:
        return verdict(
            "rejected",
            False,
            False,
            f"Withheld: {primary_spacecraft}'s reported solar wind is physically implausible ({failed_bounds[0]}).",
            label=f"{primary_spacecraft} (withheld)",
        )

    if speed is None or density is None:
        return verdict(
            "rejected",
            False,
            False,
            f"Withheld: {primary_spacecraft} published no usable plasma moments.",
            label=f"{primary_spacecraft} (withheld)",
        )

    if disagreeing:
        # Two or more independent spacecraft agreeing with each other, and
        # disagreeing with the primary, out-vote the primary.  One witness does
        # not: with exactly two readings there is no basis for deciding which
        # instrument is at fault, and preferring a source by fixed rank would
        # encode a guess.  ACE SWEPAM is a 1997 instrument that has its own
        # failure modes; DSCOVR was right and ACE wrong on other occasions.
        quorum = _mutual_quorum(disagreeing, thresholds)
        if len(quorum) >= 2:
            substitute_speed = _median(row.speed_kps for row in quorum)
            substitute_density = _median(row.density_cm3 for row in quorum)
            names = ", ".join(row.spacecraft for row in quorum)
            return verdict(
                "substituted",
                True,
                True,
                (
                    f"{primary_spacecraft} disagrees with {names}, which agree with each other, so the "
                    f"published solar wind comes from {names} instead. "
                    f"{primary_spacecraft} read {primary.speed_kps:.0f} km/s; the others read {substitute_speed:.0f} km/s."
                ),
                spacecraft=names,
                label=f"{names} (substituted for {primary_spacecraft})",
                values=(substitute_speed, substitute_density, None),
            )
        worst = max(disagreeing, key=lambda row: row.speed_difference_fraction or 0.0)
        return verdict(
            "disputed",
            False,
            False,
            (
                f"Solar-wind speed and density are withheld: {primary_spacecraft} reads "
                f"{primary.speed_kps:.0f} km/s while {worst.spacecraft} reads {worst.speed_kps:.0f} km/s over the "
                f"same hour, and there is no third spacecraft to break the tie. Dynamic pressure and the "
                f"magnetopause standoff derived from it are not published for this sample."
            ),
            label=f"{primary_spacecraft} vs {worst.spacecraft} (disputed)",
        )

    if step_outcome == "incoherent" and not agreeing:
        return verdict(
            "disputed",
            False,
            False,
            (
                f"Solar-wind speed and density are withheld: {primary_spacecraft}'s plasma moments stepped sharply "
                "while the magnetic field did not move, which no interplanetary shock or discontinuity does, and no "
                "second spacecraft is reporting to settle it. Dynamic pressure and the magnetopause standoff derived "
                "from it are not published for this sample."
            ),
            label=f"{primary_spacecraft} (disputed)",
        )

    if step_outcome == "incoherent" and agreeing:
        # A live, independent spacecraft that currently agrees is stronger
        # evidence than a historical step the magnetometer did not corroborate.
        # The failed step check still travels into the artifact.
        return verdict(
            "ok",
            True,
            True,
            (
                f"Corroborated: {primary_spacecraft} agrees with "
                + ", ".join(row.spacecraft for row in agreeing)
                + " within tolerance over the last hour, which settles an earlier plasma step that the magnetometer "
                "did not corroborate."
            ),
        )

    if not witnesses:
        return verdict(
            "uncorroborated",
            True,
            True,
            (
                f"Published from {primary_spacecraft} alone: no second spacecraft was reporting in the comparison "
                "window, so this value has not been independently corroborated."
            ),
            label=f"{primary_spacecraft} (uncorroborated)",
        )

    return verdict(
        "ok",
        True,
        True,
        (
            f"Corroborated: {primary_spacecraft} agrees with "
            + ", ".join(row.spacecraft for row in agreeing)
            + " within tolerance over the last hour."
        ),
    )


def guard_summary(verdict: GuardVerdict) -> dict[str, Any]:
    """The block the publisher embeds in the artifact."""
    return verdict.as_dict()


# --------------------------------------------------------------------------
# Interplanetary magnetic field
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class FieldVerdict:
    verdict: str
    publish_field: bool
    resolved_spacecraft: str
    resolved_label: str
    bt_nt: float | None
    bz_gsm_nt: float | None
    notice: str
    comparisons: tuple[SourceComparison, ...]

    @property
    def degraded(self) -> bool:
        return self.verdict in {"disputed", "rejected"}

    def as_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "publishesValue": self.publish_field,
            "resolvedSpacecraft": self.resolved_spacecraft,
            "notice": self.notice,
            "crossChecks": [comparison.as_dict() for comparison in self.comparisons],
        }


IMF_RELATIVE_TOLERANCE = 0.35
IMF_ABSOLUTE_TOLERANCE_NT = 2.0
"""How far two L1 magnetometers may disagree on |B| before the value is disputed.

Magnetometers are far better behaved than Faraday cups -- DSCOVR's magnetometer
was healthy throughout the Gannon storm while its plasma instrument was not --
but they are not immune, and the site's Shue boundary depends on Bz as well as
on dynamic pressure.  The live SWPC real-time feed on 2026-08-07 carried
SOLAR1, ACE and IMAP simultaneously with hourly-median |B| of 3.05, 3.39 and
3.26 nT, a spread of 11%; the tolerance is set at 35% or 2 nT, whichever is
larger, so ordinary spatial separation between L1 monitors never disputes.
"""


def assess_imf(
    *,
    primary_spacecraft: str,
    field_samples: Sequence[FieldSample],
    now: dt.datetime,
    thresholds: Thresholds = DEFAULT_THRESHOLDS,
) -> FieldVerdict:
    """Cross-check the magnetometer sample the publisher wants to ship.

    Same posture as ``assess_solar_wind``: the upstream's own quality flag is
    never sufficient, corroboration means a different spacecraft, and a
    disagreement withholds the value rather than silently picking a side.
    """
    now = _as_utc(now)
    index = _Index(field_samples)
    oldest_allowed = now - dt.timedelta(minutes=thresholds.max_sample_age_minutes)
    usable = [
        row
        for row in index.slice(primary_spacecraft, oldest_allowed, now)
        if row.bt_nt is not None and row.bz_gsm_nt is not None
    ]
    newest = usable[-1] if usable else None
    bt = newest.bt_nt if newest else None
    bz = newest.bz_gsm_nt if newest else None

    if bt is None or bz is None:
        return FieldVerdict(
            "rejected",
            False,
            primary_spacecraft,
            f"{primary_spacecraft} (withheld)",
            None,
            None,
            f"Withheld: {primary_spacecraft} published no usable magnetic field sample.",
            (),
        )
    if not (thresholds.bt_min_nt <= bt <= thresholds.bt_max_nt) or abs(bz) > thresholds.bt_max_nt:
        return FieldVerdict(
            "rejected",
            False,
            primary_spacecraft,
            f"{primary_spacecraft} (withheld)",
            None,
            None,
            (
                f"Withheld: {primary_spacecraft} reports |B| = {bt:g} nT, outside the physically plausible "
                f"{thresholds.bt_min_nt:g}-{thresholds.bt_max_nt:g} nT range."
            ),
            (),
        )

    primary_bt, _, primary_count = _field_window(index, primary_spacecraft, now, thresholds.window_minutes)
    comparisons: list[SourceComparison] = []
    for spacecraft in index.spacecraft_names():
        if spacecraft == primary_spacecraft:
            continue
        other_bt, _, count = _field_window(index, spacecraft, now, thresholds.window_minutes)
        if count < thresholds.min_window_samples or other_bt is None or other_bt <= 0 or primary_bt is None:
            continue
        difference = abs(primary_bt - other_bt) / other_bt
        tolerance = max(IMF_RELATIVE_TOLERANCE, IMF_ABSOLUTE_TOLERANCE_NT / other_bt)
        comparisons.append(
            SourceComparison(
                spacecraft=spacecraft,
                product="",
                samples=count,
                speed_kps=None,
                density_cm3=other_bt,
                speed_difference_fraction=difference,
                density_ratio=None,
                agrees=difference <= tolerance,
            )
        )

    disagreeing = [row for row in comparisons if row.agrees is False]
    agreeing = [row for row in comparisons if row.agrees is True]
    if disagreeing and not agreeing:
        worst = max(disagreeing, key=lambda row: row.speed_difference_fraction or 0.0)
        return FieldVerdict(
            "disputed",
            False,
            primary_spacecraft,
            f"{primary_spacecraft} vs {worst.spacecraft} (disputed)",
            None,
            None,
            (
                f"IMF magnitude and Bz are withheld: {primary_spacecraft} reads {primary_bt:.1f} nT while "
                f"{worst.spacecraft} reads {worst.density_cm3:.1f} nT over the same hour. The magnetopause "
                "standoff that depends on Bz is not published for this sample."
            ),
            tuple(comparisons),
        )
    if not comparisons:
        return FieldVerdict(
            "uncorroborated",
            True,
            primary_spacecraft,
            f"{primary_spacecraft} (uncorroborated)",
            bt,
            bz,
            (
                f"Published from {primary_spacecraft} alone: no second magnetometer was reporting in the "
                "comparison window."
            ),
            (),
        )
    return FieldVerdict(
        "ok",
        True,
        primary_spacecraft,
        primary_spacecraft,
        bt,
        bz,
        "Corroborated: " + ", ".join(row.spacecraft for row in agreeing) + f" agree with {primary_spacecraft} on |B|.",
        tuple(comparisons),
    )


# --------------------------------------------------------------------------
# Adapter for NOAA SWPC's real-time solar-wind feeds
# --------------------------------------------------------------------------


def _parse_rtsw_time(value: Any) -> dt.datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=dt.timezone.utc)


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def rtsw_plasma_samples(rows: Any) -> list[PlasmaSample]:
    """Convert ``json/rtsw/rtsw_wind_1m.json`` rows into guard inputs.

    That one file already carries every L1 monitor SWPC is receiving -- on
    2026-08-07 it held SOLAR1 (SWFO-L1), ACE and IMAP simultaneously, each with
    a full set of proton moments, with only one marked ``active``.  The guard
    therefore gets an independent second and third opinion out of a file the
    publisher already fetches, at no extra cost to NOAA.
    """
    samples: list[PlasmaSample] = []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        observed_at = _parse_rtsw_time(row.get("time_tag"))
        if observed_at is None:
            continue
        samples.append(
            PlasmaSample(
                spacecraft=str(row.get("source") or "unknown"),
                observed_at=observed_at,
                speed_kps=_number(row.get("proton_speed")),
                density_cm3=_number(row.get("proton_density")),
                temperature_k=_number(row.get("proton_temperature")),
                product="NOAA SWPC RTSW 1-minute plasma",
                source_quality=None if row.get("overall_quality") is None else int(_number(row.get("overall_quality")) or 0),
                source_active=bool(row.get("active")),
            )
        )
    return samples


def rtsw_field_samples(rows: Any) -> list[FieldSample]:
    """Convert ``json/rtsw/rtsw_mag_1m.json`` rows into guard inputs."""
    samples: list[FieldSample] = []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        observed_at = _parse_rtsw_time(row.get("time_tag"))
        if observed_at is None:
            continue
        samples.append(
            FieldSample(
                spacecraft=str(row.get("source") or "unknown"),
                observed_at=observed_at,
                bt_nt=_number(row.get("bt")),
                bz_gsm_nt=_number(row.get("bz_gsm")),
                product="NOAA SWPC RTSW 1-minute magnetometer",
                source_quality=None if row.get("overall_quality") is None else int(_number(row.get("overall_quality")) or 0),
            )
        )
    return samples


def active_spacecraft(rows: Any, fallback: str = "unknown") -> str:
    """The spacecraft SWPC currently designates ``active``, newest row wins."""
    best: tuple[dt.datetime, str] | None = None
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict) or not row.get("active"):
            continue
        observed_at = _parse_rtsw_time(row.get("time_tag"))
        if observed_at is None:
            continue
        if best is None or observed_at > best[0]:
            best = (observed_at, str(row.get("source") or fallback))
    return best[1] if best else fallback


def _base_wind_predicate(row: dict[str, Any]) -> bool:
    return bool(
        row.get("active")
        and int(row.get("overall_quality") or 0) == 0
        and row.get("proton_speed") is not None
        and row.get("proton_density") is not None
    )


def _base_imf_predicate(row: dict[str, Any]) -> bool:
    return bool(
        row.get("active")
        and int(row.get("overall_quality") or 0) == 0
        and row.get("bz_gsm") is not None
    )


def _before_onset(base: Any, onset: dt.datetime | None) -> Any:
    if onset is None:
        return lambda row: False

    def predicate(row: dict[str, Any]) -> bool:
        observed = _parse_rtsw_time(row.get("time_tag"))
        return bool(base(row) and observed is not None and observed < onset)

    return predicate


@dataclass(frozen=True)
class PublishDecision:
    """One object the publisher can act on, plus the block it must publish."""

    wind: GuardVerdict
    imf: FieldVerdict
    wind_label: str
    imf_label: str
    assessed_at: dt.datetime

    @property
    def publish_wind(self) -> bool:
        return self.wind.publish_plasma

    @property
    def publish_imf(self) -> bool:
        return self.imf.publish_field

    @property
    def degraded(self) -> bool:
        return self.wind.degraded or self.imf.degraded

    def _age_bounded(self, base: Any) -> Any:
        """Keep the publisher's chosen row identical to the one the guard judged.

        ``newest()`` in the publisher has no time bound, so a single row carrying
        a bogus far-future timestamp would be selected as "current" no matter how
        old the rest of the feed was. Bounding the predicate to the window the
        guard actually assessed closes that without touching ``newest()``.
        """
        oldest = self.assessed_at - dt.timedelta(minutes=DEFAULT_THRESHOLDS.max_sample_age_minutes)
        newest = self.assessed_at + dt.timedelta(minutes=5)

        def predicate(row: dict[str, Any]) -> bool:
            observed = _parse_rtsw_time(row.get("time_tag"))
            return bool(base(row) and observed is not None and oldest <= observed <= newest)

        return predicate

    def wind_row_predicate(self) -> Any:
        """Predicate for the *headline* solar-wind row.

        When the guard withholds, this returns ``False`` for every row, which is
        what removes the value, the derived dynamic pressure and the Shue
        standoff in one place instead of four.  It deliberately does not fall
        back to the newest pre-fault row: a healthy reading from an hour ago
        presented as the current state is exactly the confident-wrong-number
        failure the guard exists to prevent.
        """
        if not self.publish_wind:
            return lambda row: False
        return self._age_bounded(_base_wind_predicate)

    def wind_series_predicate(self) -> Any:
        """Predicate for the plotted history.

        History from before the fault is real and stays on the page; everything
        from the fault onward is dropped, so the trace ends where the instrument
        stopped being believable instead of continuing with a wrong value.
        """
        if self.publish_wind:
            return _base_wind_predicate
        return _before_onset(_base_wind_predicate, self.wind.fault_onset)

    def imf_row_predicate(self) -> Any:
        if not self.publish_imf:
            return lambda row: False
        return self._age_bounded(_base_imf_predicate)

    def imf_series_predicate(self) -> Any:
        if self.publish_imf:
            return _base_imf_predicate
        return _before_onset(_base_imf_predicate, None)

    def truncate_driver_series(self, rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
        """Trim NOAA's propagated-solar-wind series at the fault onset.

        This matters more than the headline value.  SWPC derives the propagated
        series from whichever L1 monitor is currently ``active``, so a faulty
        plasma instrument poisons it too -- and the browser prefers this series
        over the headline sample when it draws the Shue boundary.  Guarding only
        the headline would have left the wrong magnetosphere on screen.
        """
        if self.publish_wind or self.wind.fault_onset is None:
            return list(rows)
        onset = self.wind.fault_onset
        kept: list[dict[str, Any]] = []
        for row in rows:
            observed = _parse_rtsw_time(row.get("observedAt"))
            if observed is not None and observed >= onset:
                continue
            kept.append(row)
        return kept

    def notice(self) -> str:
        parts = [self.wind.notice]
        if self.imf.notice and self.imf.verdict != "ok":
            parts.append(self.imf.notice)
        return " ".join(parts)

    def observed_at(self, row: Any, verdict: GuardVerdict | FieldVerdict) -> str:
        """A *valid* timestamp for the sample, whether or not it was published.

        The publisher used to write ``str(row.get("time_tag") or "")``, which is
        an empty string as soon as no row is selected -- exactly what withholding
        does.  The browser renders that field with
        ``new Date(observedAt).toISOString()``, and in JavaScript
        ``new Date("")`` is an Invalid Date whose ``toISOString()`` raises
        ``RangeError``.  The weather panel would therefore have thrown while
        rendering, so the guard firing during a severe storm would have taken out
        the very page it was protecting.  The frontend is not this change's to
        edit, and it should not have to defend against its own publisher.

        The value returned when a sample is withheld is the **fault onset**: the
        last moment this instrument was believable.  That is the honest answer to
        "when is this from", and it makes the page's own staleness indicator age
        the reading instead of presenting withheld data as current.

        The format deliberately matches SWPC's own ``time_tag`` -- naive, no
        offset -- so this field stays uniform.  Note a **pre-existing** defect
        that is not this module's to fix: SWPC publishes these stamps without a
        timezone, and JavaScript parses a naive ISO datetime as *local* time, so
        the page labels a browser-local time "UTC" and is wrong by the visitor's
        offset for every solar-wind sample, guarded or not.  Fixing it means
        normalising the whole field to ``...Z`` in the publisher, which changes a
        value other consumers read, so it is recorded here rather than changed
        as a side effect of this guard.
        """
        stamp = row.get("time_tag") if isinstance(row, dict) else None
        if stamp:
            return str(stamp)
        moment = getattr(verdict, "fault_onset", None) or self.assessed_at
        return _as_utc(moment).strftime("%Y-%m-%dT%H:%M:%S")

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": 1,
            "assessedAt": self.assessed_at.isoformat().replace("+00:00", "Z"),
            "degraded": self.degraded,
            "notice": self.notice(),
            "method": (
                "The published solar-wind and IMF sample is cross-checked against every other L1 monitor "
                "NOAA SWPC is receiving, against absolute physical plausibility bounds, and against the "
                "magnetic field's own behaviour across any sharp plasma step. The upstream's own quality "
                "flag is recorded but is never sufficient on its own."
            ),
            "solarWind": self.wind.as_dict(),
            "imf": self.imf.as_dict(),
            "withheld": sorted(
                ([] if self.publish_wind else ["solarWind.speedKps", "solarWind.densityCm3", "solarWind.temperatureK", "solarWind.dynamicPressureNpa", "magnetopause.subsolarStandoffRe", "magnetopause.flaringAlpha"])
                + ([] if self.publish_imf else ["imf.btNt", "imf.bzGsmNt"])
            ),
        }


def assess_rtsw(wind_rows: Any, mag_rows: Any, now: dt.datetime) -> PublishDecision:
    """Assess NOAA SWPC's real-time solar-wind and magnetometer feeds.

    ``wind_rows`` and ``mag_rows`` are the decoded bodies of
    ``json/rtsw/rtsw_wind_1m.json`` and ``json/rtsw/rtsw_mag_1m.json``.  Both
    already contain every L1 monitor SWPC receives, so the corroboration costs
    NOAA nothing extra.  ``now`` should be wall-clock UTC: anchoring the
    comparison window to the present is also what makes a wholly stale feed fall
    out as ``rejected`` rather than being republished as current.
    """
    plasma = rtsw_plasma_samples(wind_rows)
    fields = rtsw_field_samples(mag_rows)
    wind_primary = active_spacecraft(wind_rows)
    imf_primary = active_spacecraft(mag_rows)
    wind_verdict = assess_solar_wind(
        primary_spacecraft=wind_primary,
        plasma=plasma,
        field_samples=fields,
        now=now,
    )
    imf_verdict = assess_imf(primary_spacecraft=imf_primary, field_samples=fields, now=now)
    return PublishDecision(
        wind=wind_verdict,
        imf=imf_verdict,
        wind_label=wind_verdict.resolved_label,
        imf_label=imf_verdict.resolved_label,
        assessed_at=_as_utc(now),
    )
