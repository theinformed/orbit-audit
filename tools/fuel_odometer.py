#!/usr/bin/env python3
"""The fuel odometer: propulsion catalogue x detected manoeuvre ledger.

Two phases, deliberately separate so the expensive one runs once:

  detect     Re-detect the FULL history of every catalogued NORAD with current
             code, over a frozen read-only archive snapshot, cohort-only
             (`stream_object_rows(only=...)`). Never reads a published artifact.
  integrate  Walk each object's retained events through the rocket equation
             from launch mass, with an Isp band instead of a point estimate.

PRE-REGISTERED RULES, frozen in this module before the cohort run. Every
alternative below is reported alongside its primary, so none of them can be
selected after seeing an outcome.

1. Propulsive events are those whose signature is not in the repository's
   existing `orbit_events.NON_PROPULSIVE_SIGNATURES` (drag decay, re-entry
   decay, not-separable, and unclassified-change). That set is pre-existing
   project doctrine, not a choice made for this study. The `unclassified-change`
   inclusion is reported as a labelled sensitivity for every object.
2. An event is priced on the RAISING leg's Isp only when BOTH hold: its start is
   at or before launch + 18 calendar months, AND its signature is one of
   orbit-raising, along-track-raise or inclination-change - the transfer-orbit
   signatures. Everything else, including station-keeping detected during the
   same early window, is priced on the station-keeping leg. The 18-month
   boundary is the same station-acquisition rule the EOL study registered.
   A satellite whose catalogue names no raising leg prices everything on the
   station-keeping leg.
3. Mass integrates sequentially, event by event:
   m_i = m_(i-1) * exp(-dv_i / (Isp_i * g0)), starting at the catalogued launch
   mass. Two parallel integrations carry the Isp band's two ends. A LOW Isp
   burns MORE mass, so the low-Isp integration is the band's high-burn edge.
4. DIRECTIONALITY. Detected Delta-v is a LOWER bound (the cheapest manoeuvre
   consistent with the element change), and the step detector misses burns
   entirely. Therefore burned propellant is a LOWER BOUND at BOTH ends of the
   Isp band; the band is the Isp uncertainty only, never an upper bound on fuel
   spent. Where dry mass is known, propellant REMAINING is an UPPER BOUND, and
   only the high-Isp (low-burn) edge is quotable as that bound.
5. Any archive coverage hole inside an object's observed span makes its
   cumulative sum an "at least" figure. Every object carries its hole count and
   hole days; no cadence is fitted across a hole and no hole is interpolated.
6. The station-keeping sanity anchor compares priced station-keeping-era
   Delta-v against 50 m/s/yr * GAP-AWARE observed years on station. Observed
   years never use calendar span across a hole.
7. NOT EVERY DETECTED DELTA-V IS THE SATELLITE'S OWN FUEL. Two classes are
   excluded from the primary integration, both for physical reasons stated
   before the run, and both listed per object in the output so nothing is
   silently dropped:
     (a) any event starting before the catalogued launch date - an element
         pair that predates the satellite cannot be its manoeuvre;
     (b) any single event whose Delta-v exceeds 2,500 m/s. The largest burn a
         GEO satellite performs with its own propulsion is the apogee kick out
         of a standard transfer orbit, about 1,500-1,800 m/s. An interval
         priced above 2,500 m/s is a launch-vehicle burn sequence, a
         mis-associated element set, or a fit artefact, not one satellite burn.
   The unfiltered integration is reported for EVERY object as `withoutCeiling`,
   so the effect of this rule is always visible and never chosen after the fact.
8. PLAUSIBILITY IS CHECKED, NOT ENFORCED. The largest propellant fraction in
   this catalogue's own dry-mass rows is computed at run time and used as a
   plausibility ceiling; an object whose integrated burn exceeds it is FLAGGED,
   never corrected, because the correct reading is that its detected Delta-v is
   over-priced, not that it carried impossible propellant.

Analysis only. No archive writes, no production artifacts, no network.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pipeline import orbit_campaigns as oc, orbit_events as oe  # noqa: E402
from tools.eol_policy_probe import DAY_MS, epoch, iso, digest  # noqa: E402
from tools.eol_three_arm_study import months_after, interval_objects  # noqa: E402

G0 = 9.80665
NSK_FOLKLORE_MPS_PER_YEAR = 50.0
RAISING_WINDOW_MONTHS = 18
KAPPA = 32
GEO_REGIMES = ("GEO", "near-GEO")
RAISING_SIGNATURES = frozenset({"orbit-raising", "along-track-raise", "inclination-change"})
SINGLE_EVENT_DELTAV_CEILING_MPS = 2500.0
LAUNCH_VEHICLE_NOTE = ("single-interval Delta-v above the largest burn a satellite's own "
                       "propulsion can deliver; launch vehicle, mis-association or fit artefact")
ELECTRIC_WORDS = ("electric", "ion", "hall", "arcjet", "xips", "spt-", "plasma", "krypton", "xenon", "argon")


def round_floats(node, places=6):
    """Seventeen significant digits on a lower bound is not extra knowledge."""
    if isinstance(node, dict):
        return {k: round_floats(v, places) for k, v in node.items()}
    if isinstance(node, list):
        return [round_floats(v, places) for v in node]
    if isinstance(node, float):
        return round(node, places)
    return node


def load_catalog(path):
    document = json.loads(Path(path).read_text())
    return document, [o for o in document["objects"] if o.get("norad")]


# --------------------------------------------------------------------------
# Phase one: cohort-only re-detection over a frozen snapshot
# --------------------------------------------------------------------------
def detect(args):
    document, objects = load_catalog(args.catalog)
    ids = sorted({int(o["norad"]) for o in objects})
    start, cpu = time.monotonic(), time.process_time()
    hashes = {str(Path(m.__file__).relative_to(ROOT)): digest(Path(m.__file__))
              for m in (oc, oe, oc.orbit_history)}
    device = None
    mode = "cpu"
    if args.gpu:
        from pipeline import orbit_sweep_gpu as gpu
        if not os.environ.get("CUDA_VISIBLE_DEVICES"):
            raise RuntimeError("--gpu requires a broker-assigned CUDA_VISIBLE_DEVICES")
        gpu._USAGE_LEDGER = Path(str(args.output) + ".gpu-usage.jsonl")
        hashes[str(Path(gpu.__file__).relative_to(ROOT))] = digest(Path(gpu.__file__))
        device = gpu.Execution((0,), 320)
        device.__enter__()
        mode = "gpu"
    db = oc.open_archive_for_reading(args.archive)
    if db.execute("PRAGMA query_only").fetchone()[0] != 1:
        raise RuntimeError("Archive connection is not read-only")
    facts = {r[0]: dict(zip(("name", "objectType", "launchDate", "country"), r[1:]))
             for r in db.execute("SELECT norad,name,object_type,launch_date,country FROM object")}
    expectations = oc.Expectations.load()
    counts, read, missing = Counter(), 0, []
    with gzip.open(args.output, "xt") as out:
        for position, norad in enumerate(ids):
            groups = list(oc.stream_object_rows(db, only=[norad], page_rows=8192))
            rows = [r for _, group in groups for r in group]
            read += len(rows)
            fact = facts.get(norad, {})
            name = fact.get("name") or f"OBJECT {norad}"
            kind = fact.get("objectType") or "UNKNOWN"
            iv = oc.intervals_from_rows(norad, name, kind, rows)
            if not rows:
                missing.append(norad)
            events = oc.detect_object_events(iv, kappa=KAPPA, expectations=expectations,
                                             gpu_executor=device) if iv else []
            compact = []
            for e in events:
                d = e.as_dict()
                compact.append({k: d[k] for k in ("startAt", "endAt", "signature", "inclinationDeg",
                                                  "deltaV", "regime", "perigeeAltitudeKm",
                                                  "apogeeAltitudeKm", "confidence")})
                compact[-1]["controlBasis"] = "self-history"
                counts[e.signature] += 1
            regimes = Counter(i.regime for i in iv)
            record = dict(norad=norad, name=name, objectType=kind, facts=fact,
                          rows=len(rows), intervals=[[i.start_ms, i.end_ms] for i in iv],
                          rowsSha256=hashlib.sha256(json.dumps(rows, separators=(",", ":")).encode()).hexdigest(),
                          firstEpoch=rows[0][0] if rows else None,
                          lastEpoch=rows[-1][0] if rows else None,
                          regimes=dict(regimes), events=compact)
            out.write(json.dumps(record, separators=(",", ":"), allow_nan=False) + "\n")
            if (position + 1) % 25 == 0:
                out.flush()
                print(json.dumps(dict(objects=position + 1, of=len(ids), rows=read,
                                      wallSeconds=round(time.monotonic() - start))), flush=True)
    report = device.report() if device else None
    if device:
        device.__exit__(None, None, None)
    db.close()
    for f, h in hashes.items():
        if digest(ROOT / f) != h:
            raise RuntimeError(f"Source changed during run: {f}")
    snapshot = args.archive.parent / "archive.sha256"
    receipt = dict(complete=True, phase="detect", archive=str(args.archive),
                   archiveSnapshotSha256=(snapshot.read_text().split()[0]
                                          if snapshot.exists() else None),
                   executionMode=mode, kappa=KAPPA, cohortObjects=len(ids),
                   catalogueObjects=len(document["objects"]), selectedRows=read,
                   objectsWithNoArchiveRows=missing, eventCounts=dict(counts), gpu=report,
                   sourceHashes=hashes, analysisSourceSha256=digest(Path(__file__)),
                   catalogueSha256=digest(Path(args.catalog)),
                   extractionSha256=digest(args.output),
                   wallSeconds=time.monotonic() - start, cpuSeconds=time.process_time() - cpu,
                   completedAt=datetime.now(timezone.utc).isoformat())
    Path(str(args.output) + ".receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt), flush=True)


# --------------------------------------------------------------------------
# Phase two: the rocket equation, with bands and bounds
# --------------------------------------------------------------------------
def isp_band(leg):
    """(low, high) seconds, or None when the catalogue names no Isp at all."""
    if not leg:
        return None
    band = leg.get("isp_range_s")
    if band and len(band) == 2 and all(isinstance(x, (int, float)) and x > 0 for x in band):
        return (float(min(band)), float(max(band)))
    point = leg.get("isp_s")
    if isinstance(point, (int, float)) and point > 0:
        return (float(point), float(point))
    return None


def electric(leg):
    text = ((leg or {}).get("type", "") + " " + ((leg or {}).get("thruster_model") or "")).lower()
    return any(word in text for word in ELECTRIC_WORDS)


def coverage(intervals):
    """Gap-aware exposure. Holes are counted and named, never interpolated."""
    iv = interval_objects(dict(intervals=intervals))
    segments = oc._segments(iv)
    observed = sum(i.span_days for i in iv)
    holes = [dict(fromAt=iso(a[1]), toAt=iso(b[0]), days=(b[0] - a[1]) / DAY_MS)
             for a, b in zip(segments, segments[1:])]
    span = ((segments[-1][1] - segments[0][0]) / DAY_MS) if segments else 0.0
    return dict(segments=[[iso(a), iso(b)] for a, b in segments], observedDays=observed,
                calendarSpanDays=span, holeCount=len(holes), holeDays=sum(h["days"] for h in holes),
                holes=holes, coverageFraction=(observed / span) if span else None)


def observed_days_between(intervals, start, end):
    return sum(max(0, min(end, b) - max(start, a)) for a, b in intervals) / DAY_MS


def burn(events, launch_t, sk, raising):
    """Sequential rocket-equation integration at both ends of the Isp band."""
    low = high = 1.0          # mass fraction remaining, low-Isp and high-Isp
    boundary = months_after(launch_t, RAISING_WINDOW_MONTHS) if launch_t is not None else None
    curve, spend, legs, leg_dv = [], 0.0, Counter(), Counter()
    for e in events:
        dv = e["deltaV"]["totalMetresPerSecond"]
        t = epoch(e["startAt"])
        on_raising_leg = (boundary is not None and t <= boundary and raising is not None
                          and e["signature"] in RAISING_SIGNATURES)
        band = raising if on_raising_leg else sk
        legs["raising" if on_raising_leg else "stationKeeping"] += 1
        leg_dv["raising" if on_raising_leg else "stationKeeping"] += dv
        low *= math.exp(-dv / (band[0] * G0))
        high *= math.exp(-dv / (band[1] * G0))
        spend += dv
        curve.append(dict(at=e["startAt"], signature=e["signature"], deltaVMps=dv,
                          cumulativeDeltaVMps=spend, leg="raising" if on_raising_leg else "stationKeeping",
                          ispSeconds=list(band), massFractionRemaining=[high, low]))
    return dict(fractionRemainingHighIsp=high, fractionRemainingLowIsp=low,
                totalDeltaVMps=spend, curve=curve, legCounts=dict(legs),
                legDeltaVMps=dict(leg_dv))


def analyse_object(entry, record, sensitivity=False, plausibility_ceiling=None):
    launch = entry.get("launch_date") or (record or {}).get("facts", {}).get("launchDate")
    try:
        launch_t = epoch(launch) if launch else None
    except ValueError:
        launch_t = None
    sk, raising = isp_band(entry.get("sk_propulsion")), isp_band(entry.get("raising_propulsion"))
    mass = entry.get("launch_mass_kg")
    dry = entry.get("dry_mass_kg")
    events = sorted(record["events"], key=lambda e: e["startAt"]) if record else []
    usable = [e for e in events if e["signature"] not in oe.NON_PROPULSIVE_SIGNATURES]
    if sensitivity:
        usable = [e for e in events if e["signature"] != "drag-decay"
                  and e["signature"] not in ("re-entry-decay", "drag-and-thrust-not-separable")]
    # Rule 7: events that cannot be this satellite's own propulsion.
    rejected = []
    kept = []
    for e in usable:
        reason = None
        if launch_t is not None and epoch(e["startAt"]) < launch_t:
            reason = "starts-before-catalogued-launch-date"
        elif e["deltaV"]["totalMetresPerSecond"] > SINGLE_EVENT_DELTAV_CEILING_MPS:
            reason = "single-event-delta-v-above-ceiling"
        (rejected if reason else kept).append(
            dict(e, exclusionReason=reason) if reason else e)
    cov = coverage(record["intervals"]) if record else None
    out = dict(schema=1, norad=int(entry["norad"]), name=entry["name"], bus=entry.get("bus"),
               cospar=entry.get("cospar"), launchDate=launch, launchMassKg=mass, dryMassKg=dry,
               confidence=entry["confidence"], catalogueNote=entry.get("note"),
               retirement=entry.get("retirement"),
               skPropulsion=entry.get("sk_propulsion"), raisingPropulsion=entry.get("raising_propulsion"),
               ispBandSeconds=list(sk) if sk else None,
               raisingIspBandSeconds=list(raising) if raising else None,
               ispUnresolved=bool(sk and sk[1] / sk[0] > 1.5),
               electricStationKeeping=electric(entry.get("sk_propulsion")),
               stepDetectorBlindToContinuousBurns=electric(entry.get("sk_propulsion")),
               archivePresent=bool(record and record["rows"]),
               archiveRows=(record or {}).get("rows", 0),
               regimes=(record or {}).get("regimes", {}),
               firstEpoch=iso(record["firstEpoch"]) if record and record["firstEpoch"] else None,
               lastEpoch=iso(record["lastEpoch"]) if record and record["lastEpoch"] else None,
               coverage=cov, eventsDetected=len(events),
               eventsPropulsive=len(usable),
               signatureCounts=dict(Counter(e["signature"] for e in events)),
               burnedKgLowerBound=None, burnedKgIspBand=None, burnedFractionOfLaunchMass=None,
               propellantRemainingUpperBoundKg=None, sanity=None,
               cumulativeIsAtLeast=True,
               boundsNote=("Detected Delta-v is a cheapest-consistent lower bound and the step "
                           "detector misses burns; burned propellant is a lower bound at BOTH ends "
                           "of the Isp band, and remaining propellant is an upper bound."))
    if not (mass and sk and record):
        out["excluded"] = ("no-launch-mass" if not mass else
                           "no-catalogued-isp" if not sk else "no-archive-record")
        return out
    out["excluded"] = None
    out["eventsExcludedAsNotOwnPropulsion"] = [
        dict(at=e["startAt"], signature=e["signature"],
             deltaVMps=e["deltaV"]["totalMetresPerSecond"],
             perigeeAltitudeKm=e["perigeeAltitudeKm"], apogeeAltitudeKm=e["apogeeAltitudeKm"],
             inclinationDeg=e["inclinationDeg"], reason=e["exclusionReason"])
        for e in rejected]
    out["deltaVMpsExcludedAsNotOwnPropulsion"] = sum(
        e["deltaV"]["totalMetresPerSecond"] for e in rejected)
    out["singleEventCeilingMps"] = SINGLE_EVENT_DELTAV_CEILING_MPS
    integrated = burn(kept, launch_t, sk, raising)
    unfiltered = burn(usable, launch_t, sk, raising)
    out["withoutCeiling"] = dict(
        events=len(usable), totalDeltaVMpsLowerBound=unfiltered["totalDeltaVMps"],
        burnedKgIspBand=[mass * (1 - unfiltered["fractionRemainingHighIsp"]),
                         mass * (1 - unfiltered["fractionRemainingLowIsp"])],
        burnedFractionOfLaunchMass=[1 - unfiltered["fractionRemainingHighIsp"],
                                    1 - unfiltered["fractionRemainingLowIsp"]],
        note="every detected propulsive event, launch-vehicle and artefact events included")
    out["totalDeltaVMpsLowerBound"] = integrated["totalDeltaVMps"]
    out["legCounts"] = integrated["legCounts"]
    burned_low = mass * (1 - integrated["fractionRemainingHighIsp"])
    burned_high = mass * (1 - integrated["fractionRemainingLowIsp"])
    out["burnedKgLowerBound"] = burned_low
    out["burnedKgIspBand"] = [burned_low, burned_high]
    out["burnedFractionOfLaunchMass"] = [burned_low / mass, burned_high / mass]
    out["massKgBand"] = [mass - burned_high, mass - burned_low]
    out["massBandWidthKg"] = burned_high - burned_low
    out["eventsPriced"] = len(kept)
    out["legDeltaVMps"] = integrated["legDeltaVMps"]
    out["burnedKgByLeg"] = {}
    for name in ("raising", "stationKeeping"):
        dv = integrated["legDeltaVMps"].get(name, 0.0)
        band = (raising if name == "raising" and raising else sk)
        out["burnedKgByLeg"][name] = [mass * (1 - math.exp(-dv / (band[1] * G0))),
                                      mass * (1 - math.exp(-dv / (band[0] * G0)))]
        out["burnedKgByLeg"][name + "Note"] = ("first-order: each leg priced on its own Isp from "
                                               "launch mass, so the two legs do not add exactly")
    if plausibility_ceiling:
        out["plausibilityCeilingFraction"] = plausibility_ceiling
        out["burnedFractionExceedsCataloguePlausibility"] = burned_low / mass > plausibility_ceiling
    out["massCurve"] = [dict(at=p["at"], signature=p["signature"], leg=p["leg"],
                             cumulativeDeltaVMps=p["cumulativeDeltaVMps"],
                             massKgBand=[mass * p["massFractionRemaining"][1],
                                         mass * p["massFractionRemaining"][0]])
                        for p in integrated["curve"]]
    if dry and dry < mass:
        capacity = mass - dry
        out["propellantCapacityKg"] = capacity
        out["propellantRemainingUpperBoundKg"] = capacity - burned_low
        out["burnedFractionOfCapacityLowerBound"] = burned_low / capacity
        out["burnedFractionOfCapacityIspBand"] = [burned_low / capacity, burned_high / capacity]
        out["remainingExceedsCapacity"] = burned_high > capacity
        raising_burn = out["burnedKgByLeg"]["raising"]
        out["raisingBurnVsCapacity"] = dict(
            raisingBurnKgBand=raising_burn,
            capacityKg=capacity,
            ratioBand=[raising_burn[0] / capacity, raising_burn[1] / capacity],
            note=("A catalogued 'dry mass' for a GEO comsat is often beginning-of-life mass in "
                  "GEO rather than true dry mass; where it is, this ratio should approach 1 and "
                  "is a direct check on the transfer-phase odometer."))
    # --- sanity anchor: priced station-keeping Delta-v vs the 50 m/s/yr rule ---
    geo = sum(v for k, v in out["regimes"].items() if k in GEO_REGIMES) > 0
    boundary = months_after(launch_t, RAISING_WINDOW_MONTHS) if launch_t is not None else None
    last = record["lastEpoch"]
    station_start = max(boundary or record["firstEpoch"], record["firstEpoch"])
    station_days = observed_days_between(record["intervals"], station_start, last) if last else 0.0
    station_years = station_days / 365.25
    station_dv = sum(e["deltaV"]["totalMetresPerSecond"] for e in usable
                     if boundary is None or epoch(e["startAt"]) > boundary)
    expected = NSK_FOLKLORE_MPS_PER_YEAR * station_years
    out["sanity"] = dict(
        isGeo=geo, observedStationYears=station_years,
        calendarStationYears=((last - station_start) / DAY_MS / 365.25) if last else None,
        stationKeepingDeltaVMpsLowerBound=station_dv,
        deltaVPerObservedYearMps=(station_dv / station_years) if station_years > 0 else None,
        folkloreExpectedDeltaVMps=expected,
        explainedFractionOfFolkloreBudget=(station_dv / expected) if expected > 0 else None,
        holesCrossed=cov["holeCount"],
        flag=None)
    fraction = out["sanity"]["explainedFractionOfFolkloreBudget"]
    if not geo:
        out["sanity"]["flag"] = "not-geo-folklore-does-not-apply"
    elif fraction is None:
        out["sanity"]["flag"] = "no-observed-station-exposure"
    elif out["electricStationKeeping"]:
        out["sanity"]["flag"] = "electric-station-keeping-step-detector-blind"
    elif fraction < 0.1:
        out["sanity"]["flag"] = "far-below-folklore-detection-gap"
    elif fraction > 2.0:
        out["sanity"]["flag"] = "far-above-folklore-examine"
    else:
        out["sanity"]["flag"] = "within-order-of-folklore"
    # --- cross-prediction for the drift and A/m routes ---
    years = station_years if station_years > 0 else None
    out["crossPrediction"] = dict(
        basis="burned mass / launch mass / gap-aware observed station years",
        fractionalMassLossPerYear=([burned_low / mass / years, burned_high / mass / years]
                                   if years else None),
        deltaVMpsPerObservedYear=out["sanity"]["deltaVPerObservedYearMps"],
        massLossKgPerYearBand=([burned_low / years, burned_high / years] if years else None),
        directionality="lower bound; undetected burns and sub-threshold keeping are excluded",
        atLeastBecauseOfCoverageHoles=cov["holeCount"] > 0)
    annual = []
    if record["firstEpoch"] and last:
        for year in range(datetime.fromtimestamp(record["firstEpoch"] / 1000, timezone.utc).year,
                          datetime.fromtimestamp(last / 1000, timezone.utc).year + 1):
            a, b = epoch(f"{year}-01-01"), epoch(f"{year + 1}-01-01")
            days = observed_days_between(record["intervals"], a, b)
            dv = sum(e["deltaV"]["totalMetresPerSecond"] for e in usable if a <= epoch(e["startAt"]) < b)
            annual.append(dict(year=year, observedDays=days, events=sum(1 for e in usable
                               if a <= epoch(e["startAt"]) < b),
                               deltaVMpsLowerBound=dv if days else None))
    out["annualTrajectory"] = annual
    return out


def summarise(rows, sensitivity_rows):
    priced = [r for r in rows if r["burnedKgLowerBound"] is not None]
    geo = [r for r in priced if r["sanity"]["isGeo"]]
    anchored = [r for r in geo if r["sanity"]["explainedFractionOfFolkloreBudget"] is not None
                and not r["electricStationKeeping"]]
    fractions = sorted(r["sanity"]["explainedFractionOfFolkloreBudget"] for r in anchored)
    with_dry = [r for r in priced if r.get("propellantCapacityKg")]
    retirees = [r for r in priced if (r.get("retirement") or {}).get("status") == "graveyard"]
    sensitivity = {r["norad"]: r for r in sensitivity_rows}
    return dict(
        catalogueObjects=len(rows),
        pricedObjects=len(priced),
        excluded=dict(Counter(r["excluded"] for r in rows if r["excluded"])),
        objectsWithoutArchiveRows=sum(1 for r in rows if not r["archivePresent"]),
        objectsWithNoPropulsiveEvents=sum(1 for r in priced if r["eventsPropulsive"] == 0),
        objectsWithCoverageHoles=sum(1 for r in priced if r["coverage"]["holeCount"] > 0),
        ispUnresolvedObjects=sum(1 for r in rows if r["ispUnresolved"]),
        objectsWithExcludedEvents=sum(1 for r in priced if r["eventsExcludedAsNotOwnPropulsion"]),
        eventsExcludedAsNotOwnPropulsion=sum(len(r["eventsExcludedAsNotOwnPropulsion"]) for r in priced),
        excludedEventReasons=dict(Counter(x["reason"] for r in priced
                                          for x in r["eventsExcludedAsNotOwnPropulsion"])),
        objectsAbovePlausibilityCeiling=sum(1 for r in priced
                                            if r.get("burnedFractionExceedsCataloguePlausibility")),
        objectsAbovePlausibilityCeilingWithoutCeilingRule=sum(
            1 for r in priced if r.get("plausibilityCeilingFraction")
            and r["withoutCeiling"]["burnedFractionOfLaunchMass"][0] > r["plausibilityCeilingFraction"]),
        electricStationKeepingObjects=sum(1 for r in rows if r["electricStationKeeping"]),
        totalBurnedKgLowerBound=sum(r["burnedKgLowerBound"] for r in priced),
        medianBurnedFractionLowerBound=(statistics.median(
            r["burnedFractionOfLaunchMass"][0] for r in priced) if priced else None),
        geoObjects=len(geo), folkloreAnchoredObjects=len(anchored),
        folkloreExplainedFraction=dict(
            n=len(fractions),
            median=statistics.median(fractions) if fractions else None,
            quartiles=[fractions[len(fractions) // 4], fractions[3 * len(fractions) // 4]] if len(fractions) >= 4 else None,
            range=[fractions[0], fractions[-1]] if fractions else None,
            belowTenPercent=sum(1 for x in fractions if x < 0.1),
            aboveTwice=sum(1 for x in fractions if x > 2.0)),
        sanityFlags=dict(Counter(r["sanity"]["flag"] for r in priced)),
        dryMassObjects=len(with_dry),
        dryMassCapacityExceeded=sum(1 for r in with_dry if r["remainingExceedsCapacity"]),
        graveyardRetirees=len(retirees),
        retireeBurnedFractionOfLaunchMass=dict(
            n=len(retirees),
            median=statistics.median(r["burnedFractionOfLaunchMass"][0] for r in retirees) if retirees else None,
            maxHighIspEdge=max((r["burnedFractionOfLaunchMass"][1] for r in retirees), default=None)),
        unclassifiedChangeSensitivity=dict(
            description="Same integration including unclassified-change events (project doctrine "
                        "excludes them from propulsive claims); reported so the exclusion is visible.",
            extraEvents=sum(sensitivity[r["norad"]]["eventsPropulsive"] - r["eventsPropulsive"] for r in priced),
            totalBurnedKgLowerBound=sum(sensitivity[r["norad"]]["burnedKgLowerBound"] or 0 for r in priced),
            medianRatio=statistics.median(
                [(sensitivity[r["norad"]]["burnedKgLowerBound"] or 0) / r["burnedKgLowerBound"]
                 for r in priced if r["burnedKgLowerBound"] > 0] or [float("nan")])))


def integrate(args):
    document, objects = load_catalog(args.catalog)
    receipt = json.loads(Path(str(args.events) + ".receipt.json").read_text())
    if not receipt["complete"] or digest(args.events) != receipt["extractionSha256"]:
        raise RuntimeError("Cohort extraction receipt is incomplete or does not match its file")
    records = {}
    with gzip.open(args.events, "rt") as f:
        for line in f:
            r = json.loads(line)
            records[r["norad"]] = r
    fractions = [(o["launch_mass_kg"] - o["dry_mass_kg"]) / o["launch_mass_kg"]
                 for o in objects if o.get("dry_mass_kg") and o.get("launch_mass_kg")
                 and o["dry_mass_kg"] < o["launch_mass_kg"]]
    ceiling = max(fractions) if fractions else None
    rows = [analyse_object(o, records.get(int(o["norad"])), plausibility_ceiling=ceiling)
            for o in objects]
    sens = [analyse_object(o, records.get(int(o["norad"])), sensitivity=True,
                           plausibility_ceiling=ceiling) for o in objects]
    summary = dict(schema=1, measuredAt=datetime.now(timezone.utc).isoformat(),
                   detectionReceipt=receipt,
                   catalogue=dict(path=str(args.catalog), sha256=digest(Path(args.catalog)),
                                  version=document.get("version"), policy=document.get("policy"),
                                  objects=len(document["objects"]), withNorad=len(objects)),
                   sourceHashes={"integration": digest(Path(__file__)),
                                 "reusedProbe": digest(ROOT / "tools/eol_policy_probe.py"),
                                 "reusedStudy": digest(ROOT / "tools/eol_three_arm_study.py"),
                                 "expectations": digest(ROOT / "data/orbit_manoeuvre_expectations.json")},
                   preRegisteredRules=__doc__,
                   singleEventCeilingMps=SINGLE_EVENT_DELTAV_CEILING_MPS,
                   plausibilityCeilingFraction=ceiling,
                   plausibilityCeilingSource=("largest propellant fraction among the catalogue's "
                                              f"{len(fractions)} dry-mass rows"),
                   **summarise(rows, sens))
    with Path(str(args.output_prefix) + ".jsonl").open("x") as f:
        for r in rows:
            f.write(json.dumps(round_floats(r), allow_nan=False, separators=(",", ":")) + "\n")
    with Path(str(args.output_prefix) + "-receipt.json").open("x") as f:
        json.dump(summary, f, indent=2, allow_nan=False)
    print(json.dumps({k: v for k, v in summary.items()
                      if k not in ("detectionReceipt", "preRegisteredRules")}, indent=2))


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="phase", required=True)
    d = sub.add_parser("detect", help="cohort-only full-history re-detection")
    d.add_argument("--archive", type=Path, required=True)
    d.add_argument("--catalog", type=Path, default=ROOT / "data/propulsion-catalog-v1.json")
    d.add_argument("--output", type=Path, required=True)
    d.add_argument("--gpu", action="store_true")
    d.set_defaults(func=detect)
    i = sub.add_parser("integrate", help="rocket-equation integration with Isp bands")
    i.add_argument("--events", type=Path, required=True)
    i.add_argument("--catalog", type=Path, default=ROOT / "data/propulsion-catalog-v1.json")
    i.add_argument("--output-prefix", type=Path, required=True)
    i.set_defaults(func=integrate)
    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
