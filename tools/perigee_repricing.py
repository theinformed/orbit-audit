#!/usr/bin/env python3
"""Perigee-speed re-pricing of the tangential Delta-v channel — Track T2.

ANALYSIS RE-RUN, NOT A PRODUCTION CHANGE. Nothing here writes a production
artifact, alters production pricing, or touches a published control block. It
re-runs detection over a frozen read-only archive snapshot with the SHIPPED
detector, then prices each detected event three ways and integrates each
pricing through the fuel odometer's own pre-registered rules.

Registered before any result existed in `docs/repricing-preregistration-20260921.md`
(commit 62f98d3). The registration binds this module; where the two disagree the
registration wins and the difference is a defect to report.

The three prices, all from vis-viva (registration §1):

    dv = mu * da / (2 a^2 v)                                    (reg. eq. 2)

    circular  v = v_c = sqrt(mu/a)          -> dv = n da / 2     (shipped)
    perigee   v = v_p = v_c sqrt((1+e)/(1-e))
                                            -> dv_circ * sqrt((1-e)/(1+e))
    apogee    v = v_a = v_c sqrt((1-e)/(1+e))
                                            -> dv_circ * sqrt((1+e)/(1-e))

Perigee is the minimum over burn points and apogee the maximum, so the two
bracket the cost of any single tangential impulse producing the observed `da`.
The event total is re-formed by the pipeline's own unchanged combination rule
(max over in-plane channels, quadrature with the out-of-plane one).

WHAT IS NOT RE-PRICED, per registration §2.4: the plane-change channel (already
at apogee, already the minimum), the eccentricity channel (already below its own
infimum), the apse-line channel (already exact), the combination rule, and every
detection decision — including the 2x-perigee-speed implausibility screen, which
is evaluated on the CIRCULAR price exactly as production does, so the event set
is identical to a production-code re-run's and the comparison is a pricing
comparison rather than a detector comparison.

Three phases:

  detect     Cohort-only full-history re-detection over the frozen snapshot,
             recording for every priced interval its eccentricity, semi-major
             axis and every Delta-v component, plus the exact finite-impulse
             screen of registration §1.4 and the screen-admission delta of §2.3.
  integrate  The odometer's registered rules (tools/fuel_odometer.py, rules 1-8,
             frozen 2026-09-20) applied unmodified to each of the three pricings.
  compare    The side-by-side, including the control arm of registration §4.
"""
from __future__ import annotations

import argparse
from collections import Counter
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
from tools.eol_policy_probe import digest  # noqa: E402
from tools import fuel_odometer as fo  # noqa: E402

KAPPA = fo.KAPPA


# ---------------------------------------------------------------------------
# The three prices
# ---------------------------------------------------------------------------
def repricing_factor(eccentricity: float) -> float:
    """sqrt((1-e)/(1+e)) — registration eq. (5). 1 at e=0, 0.3951 at e=0.73."""
    e = min(max(float(eccentricity), 0.0), 0.999999)
    return math.sqrt((1.0 - e) / (1.0 + e))


def combine(tangential: float, ecc: float, apsidal: float, plane: float) -> float:
    """The pipeline's own rule, unchanged: max over in-plane, quadrature with plane."""
    return math.hypot(max(abs(tangential), ecc, apsidal), plane)


def exact_tangential(a1_km: float, da_metres: float, r_km: float) -> float | None:
    """Registration eq. (7): the exact finite-impulse tangential cost at radius r.

    Returns None where the post-burn orbit does not contain r (the first-order
    relation has been extrapolated past where an impulse at r could act).
    """
    if r_km <= 0.0 or a1_km <= 0.0:
        return None
    a2_km = a1_km + da_metres / 1000.0
    if a2_km <= 0.0:
        return None
    t1 = 2.0 / r_km - 1.0 / a1_km
    t2 = 2.0 / r_km - 1.0 / a2_km
    if t1 <= 0.0 or t2 <= 0.0:
        return None
    return abs(math.sqrt(oe.MU_WGS72 * t2) - math.sqrt(oe.MU_WGS72 * t1)) * 1000.0


def price(interval, cost) -> dict:
    """Every figure this track reports for one priced interval."""
    e = float(interval.eccentricity)
    a_km = float(interval.a_start_km)
    factor = repricing_factor(e)
    tangential = float(cost.tangential)
    ecc = float(cost.eccentricity)
    apsidal = float(cost.apsidal)
    plane = float(cost.plane_change)
    n_rad_s = math.sqrt(oe.MU_WGS72 / a_km**3)
    # The residual `da` the tangential channel was built from, recovered exactly
    # from the shipped first-order relation dv = n da / 2. Not
    # `propulsive_delta_a_metres`, which is the observed-minus-drag figure and
    # includes residuals that never cleared their channel's bar.
    da_metres = 2.0 * tangential / n_rad_s if n_rad_s > 0 else 0.0
    perigee_km = a_km * (1.0 - e)
    v_perigee = math.sqrt(max(oe.MU_WGS72 * (2.0 / perigee_km - 1.0 / a_km), 0.0)) * 1000.0
    total_circ = combine(tangential, ecc, apsidal, plane)
    total_peri = combine(tangential * factor, ecc, apsidal, plane)
    total_apo = combine(tangential / factor, ecc, apsidal, plane)
    ceiling = 2.0 * v_perigee
    return dict(
        eccentricity=e,
        semiMajorAxisKm=a_km,
        repricingFactor=factor,
        propulsiveDeltaAMetres=da_metres,
        tangentialCircularMps=tangential,
        tangentialPerigeeMps=tangential * factor,
        tangentialApogeeMps=tangential / factor,
        planeChangeMps=plane,
        eccentricityChannelMps=ecc,
        apsidalMps=apsidal,
        totalCircularMps=total_circ,
        totalPerigeeMps=total_peri,
        totalApogeeMps=total_apo,
        tangentialIsBindingInPlane=(abs(tangential) >= max(ecc, apsidal)),
        tangentialIsBindingInPlaneAfterRepricing=(abs(tangential * factor) >= max(ecc, apsidal)),
        exactTangentialAtPerigeeMps=exact_tangential(a_km, da_metres, perigee_km),
        exactTangentialAtCircularMps=exact_tangential(a_km, da_metres, a_km),
        implausibilityCeilingMps=ceiling,
        rejectedByCircularPrice=bool(ceiling > 0.0 and total_circ > ceiling),
        wouldPassUnderPerigeePrice=bool(ceiling > 0.0 and total_circ > ceiling
                                        and total_peri <= ceiling),
    )


# ---------------------------------------------------------------------------
# Phase one: re-detection, with every priced interval recorded
# ---------------------------------------------------------------------------
_PRICED: dict[int, tuple] = {}
_ALL: list[dict] = []
_ORIGINAL_DELTA_V = oc.delta_v


def _recording_delta_v(interval, drag, tests):
    """Shipped pricing, unchanged, with the interval kept so it can be re-priced.

    Keyed by `id(cost)` and holding a reference to `cost`, so the key cannot be
    recycled while the mapping lives. Cleared per object.
    """
    cost = _ORIGINAL_DELTA_V(interval, drag, tests)
    record = price(interval, cost)
    _PRICED[id(cost)] = (cost, record)
    _ALL.append(record)
    return cost


def detect(args):
    document, objects = fo.load_catalog(args.catalog)
    ids = sorted({int(o["norad"]) for o in objects})
    if args.limit:
        # Smoke path only. A limited run is never integrated: the receipt says
        # so, and `integrate` refuses a receipt whose cohort is short.
        ids = ids[:args.limit]
    start, cpu = time.monotonic(), time.process_time()
    hashes = {str(Path(m.__file__).relative_to(ROOT)): digest(Path(m.__file__))
              for m in (oc, oe, oc.orbit_history, fo)}
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
    oc.delta_v = _recording_delta_v
    db = oc.open_archive_for_reading(args.archive)
    if db.execute("PRAGMA query_only").fetchone()[0] != 1:
        raise RuntimeError("Archive connection is not read-only")
    facts = {r[0]: dict(zip(("name", "objectType", "launchDate", "country"), r[1:]))
             for r in db.execute("SELECT norad,name,object_type,launch_date,country FROM object")}
    expectations = oc.Expectations.load()
    counts, read, missing = Counter(), 0, []
    screened = dict(intervalsPriced=0, rejectedByCircularPrice=0, wouldPassUnderPerigeePrice=0)
    factor_sample: list[float] = []
    try:
        with gzip.open(args.output, "xt") as out:
            for position, norad in enumerate(ids):
                _PRICED.clear()
                _ALL.clear()
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
                screened["intervalsPriced"] += len(_ALL)
                screened["rejectedByCircularPrice"] += sum(1 for r in _ALL if r["rejectedByCircularPrice"])
                screened["wouldPassUnderPerigeePrice"] += sum(
                    1 for r in _ALL if r["wouldPassUnderPerigeePrice"])
                compact = []
                for e in events:
                    d = e.as_dict()
                    row = {k: d[k] for k in ("startAt", "endAt", "signature", "inclinationDeg",
                                             "deltaV", "regime", "perigeeAltitudeKm",
                                             "apogeeAltitudeKm", "confidence")}
                    row["controlBasis"] = "self-history"
                    held = _PRICED.get(id(e.delta_v))
                    if held is None:
                        raise RuntimeError(
                            f"event on {norad} at {d['startAt']} was not priced through delta_v; "
                            "the recorder missed a code path and the re-pricing would be partial")
                    row["repricing"] = held[1]
                    factor_sample.append(held[1]["repricingFactor"])
                    compact.append(row)
                    counts[e.signature] += 1
                regimes = Counter(i.regime for i in iv)
                record = dict(norad=norad, name=name, objectType=kind, facts=fact,
                              rows=len(rows), intervals=[[i.start_ms, i.end_ms] for i in iv],
                              rowsSha256=hashlib.sha256(
                                  json.dumps(rows, separators=(",", ":")).encode()).hexdigest(),
                              firstEpoch=rows[0][0] if rows else None,
                              lastEpoch=rows[-1][0] if rows else None,
                              regimes=dict(regimes), events=compact)
                out.write(json.dumps(record, separators=(",", ":"), allow_nan=False) + "\n")
                if (position + 1) % 25 == 0:
                    out.flush()
                    print(json.dumps(dict(objects=position + 1, of=len(ids), rows=read,
                                          wallSeconds=round(time.monotonic() - start))), flush=True)
    finally:
        oc.delta_v = _ORIGINAL_DELTA_V
    report = device.report() if device else None
    if device:
        device.__exit__(None, None, None)
    db.close()
    for f, h in hashes.items():
        if digest(ROOT / f) != h:
            raise RuntimeError(f"Source changed during run: {f}")
    snapshot = args.archive.parent / "archive.sha256"
    receipt = dict(complete=True, phase="detect", track="T2-perigee-repricing",
                   registration="docs/repricing-preregistration-20260921.md",
                   archive=str(args.archive),
                   archiveSnapshotSha256=(snapshot.read_text().split()[0]
                                          if snapshot.exists() else None),
                   executionMode=mode, kappa=KAPPA, cohortObjects=len(ids),
                   catalogueObjects=len(document["objects"]), selectedRows=read,
                   cohortLimited=bool(args.limit),
                   objectsWithNoArchiveRows=missing, eventCounts=dict(counts), gpu=report,
                   implausibilityScreen=screened,
                   repricingFactorOverDetectedEvents=_spread(factor_sample),
                   sourceHashes=hashes, analysisSourceSha256=digest(Path(__file__)),
                   catalogueSha256=digest(Path(args.catalog)),
                   extractionSha256=digest(args.output),
                   wallSeconds=time.monotonic() - start, cpuSeconds=time.process_time() - cpu,
                   completedAt=datetime.now(timezone.utc).isoformat())
    Path(str(args.output) + ".receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt), flush=True)


def _spread(values):
    v = sorted(values)
    if not v:
        return None
    return dict(n=len(v), min=v[0], p25=v[len(v) // 4], median=statistics.median(v),
                p75=v[3 * len(v) // 4], max=v[-1], mean=statistics.fmean(v))


# ---------------------------------------------------------------------------
# Phase two: the odometer's registered integration, once per pricing
# ---------------------------------------------------------------------------
ARMS = ("circular", "perigee", "apogee")
ARM_FIELD = {"circular": "totalCircularMps", "perigee": "totalPerigeeMps",
             "apogee": "totalApogeeMps"}


def arm_records(records: dict, arm: str) -> dict:
    """The same event set with `totalMetresPerSecond` set to this arm's price.

    Every downstream rule — the odometer's propulsive-signature set, the
    18-month raising window, rule 7's 2,500 m/s own-propulsion ceiling, the
    rocket equation, the folklore anchor — then reads the arm's price without
    any of them being modified, which is the point.
    """
    out = {}
    for norad, record in records.items():
        events = []
        for e in record["events"]:
            priced = dict(e)
            dv = dict(e["deltaV"])
            dv["totalMetresPerSecond"] = e["repricing"][ARM_FIELD[arm]]
            dv["tangentialMetresPerSecond"] = e["repricing"][
                {"circular": "tangentialCircularMps", "perigee": "tangentialPerigeeMps",
                 "apogee": "tangentialApogeeMps"}[arm]]
            priced["deltaV"] = dv
            events.append(priced)
        out[norad] = dict(record, events=events)
    return out


def integrate(args):
    document, objects = fo.load_catalog(args.catalog)
    receipt = json.loads(Path(str(args.events) + ".receipt.json").read_text())
    if not receipt["complete"] or digest(args.events) != receipt["extractionSha256"]:
        raise RuntimeError("Extraction receipt is incomplete or does not match its file")
    if receipt.get("cohortLimited"):
        raise RuntimeError("Extraction was a limited smoke run; it is not integrable")
    records = {}
    with gzip.open(args.events, "rt") as f:
        for line in f:
            r = json.loads(line)
            records[r["norad"]] = r
    fractions = [(o["launch_mass_kg"] - o["dry_mass_kg"]) / o["launch_mass_kg"]
                 for o in objects if o.get("dry_mass_kg") and o.get("launch_mass_kg")
                 and o["dry_mass_kg"] < o["launch_mass_kg"]]
    ceiling = max(fractions) if fractions else None
    arms = {}
    for arm in ARMS:
        priced = arm_records(records, arm)
        rows = [fo.analyse_object(o, priced.get(int(o["norad"])), plausibility_ceiling=ceiling)
                for o in objects]
        sens = [fo.analyse_object(o, priced.get(int(o["norad"])), sensitivity=True,
                                  plausibility_ceiling=ceiling) for o in objects]
        arms[arm] = dict(rows=rows, summary=fo.summarise(rows, sens))
    per_object = []
    by_norad = {arm: {r["norad"]: r for r in arms[arm]["rows"]} for arm in ARMS}
    for o in objects:
        norad = int(o["norad"])
        row = {"norad": norad, "name": o["name"],
               "electricStationKeeping": by_norad["circular"][norad]["electricStationKeeping"]}
        for arm in ARMS:
            r = by_norad[arm][norad]
            row[arm] = dict(
                totalDeltaVMpsLowerBound=r["totalDeltaVMpsLowerBound"],
                eventsPriced=r.get("eventsPriced"),
                eventsExcludedAsNotOwnPropulsion=len(r.get("eventsExcludedAsNotOwnPropulsion") or []),
                burnedKgLowerBound=r["burnedKgLowerBound"],
                burnedFractionOfLaunchMass=r["burnedFractionOfLaunchMass"],
                propellantRemainingUpperBoundKg=r.get("propellantRemainingUpperBoundKg"),
                raisingBurnVsCapacityRatioBand=((r.get("raisingBurnVsCapacity") or {}).get("ratioBand")),
                explainedFractionOfFolkloreBudget=(r["sanity"] or {}).get(
                    "explainedFractionOfFolkloreBudget"),
                legDeltaVMps=r.get("legDeltaVMps"))
        c = row["circular"]["totalDeltaVMpsLowerBound"]
        p = row["perigee"]["totalDeltaVMpsLowerBound"]
        row["perigeeOverCircularDeltaV"] = (p / c) if c else None
        per_object.append(row)
    events = [e["repricing"] for r in records.values() for e in r["events"]]
    summary = dict(
        schema=1, track="T2-perigee-repricing",
        registration="docs/repricing-preregistration-20260921.md",
        measuredAt=datetime.now(timezone.utc).isoformat(),
        detectionReceipt=receipt,
        catalogue=dict(path=str(args.catalog), sha256=digest(Path(args.catalog)),
                       version=document.get("version"), objects=len(document["objects"]),
                       withNorad=len(objects)),
        sourceHashes={"repricing": digest(Path(__file__)),
                      "reusedOdometer": digest(ROOT / "tools/fuel_odometer.py"),
                      "expectations": digest(ROOT / "data/orbit_manoeuvre_expectations.json")},
        singleEventCeilingMps=fo.SINGLE_EVENT_DELTAV_CEILING_MPS,
        plausibilityCeilingFraction=ceiling,
        perEvent=event_summary(events),
        arms={arm: arms[arm]["summary"] for arm in ARMS},
        perObject=per_object)
    with Path(str(args.output_prefix) + ".jsonl").open("x") as f:
        for row in per_object:
            f.write(json.dumps(fo.round_floats(row), allow_nan=False, separators=(",", ":")) + "\n")
    with Path(str(args.output_prefix) + "-receipt.json").open("x") as f:
        json.dump(fo.round_floats(summary, 8), f, indent=2, allow_nan=False)
    print(json.dumps(fo.round_floats(
        {k: v for k, v in summary.items() if k not in ("perObject", "detectionReceipt")}, 6),
        indent=2))


def event_summary(events):
    """Per-event distribution of the re-pricing, over the detected event set."""
    if not events:
        return None
    circ = [e["totalCircularMps"] for e in events]
    peri = [e["totalPerigeeMps"] for e in events]
    apo = [e["totalApogeeMps"] for e in events]
    ratios = [p / c for p, c in zip(peri, circ) if c > 0]
    ecc = [e["eccentricity"] for e in events]
    exact_gap = [abs(e["exactTangentialAtCircularMps"] - abs(e["tangentialCircularMps"]))
                 / abs(e["tangentialCircularMps"])
                 for e in events
                 if e["exactTangentialAtCircularMps"] is not None and abs(e["tangentialCircularMps"]) > 0]
    exact_gap_peri = [abs(e["exactTangentialAtPerigeeMps"] - abs(e["tangentialPerigeeMps"]))
                      / abs(e["tangentialPerigeeMps"])
                      for e in events
                      if e["exactTangentialAtPerigeeMps"] is not None and abs(e["tangentialPerigeeMps"]) > 0]
    return dict(
        events=len(events),
        totalCircularMps=sum(circ), totalPerigeeMps=sum(peri), totalApogeeMps=sum(apo),
        summedPerigeeOverCircular=(sum(peri) / sum(circ)) if sum(circ) else None,
        perEventRatio=_spread(ratios),
        eccentricity=_spread(ecc),
        repricingFactor=_spread([e["repricingFactor"] for e in events]),
        eventsWhereRepricingChangesTotalAboveOnePercent=sum(
            1 for p, c in zip(peri, circ) if c > 0 and p / c < 0.99),
        eventsWhereTangentialBindsInPlane=sum(1 for e in events if e["tangentialIsBindingInPlane"]),
        eventsWhereTangentialStopsBindingAfterRepricing=sum(
            1 for e in events if e["tangentialIsBindingInPlane"]
            and not e["tangentialIsBindingInPlaneAfterRepricing"]),
        eventsAboveCircularOwnPropulsionCeiling=sum(
            1 for c in circ if c > fo.SINGLE_EVENT_DELTAV_CEILING_MPS),
        eventsAbovePerigeeOwnPropulsionCeiling=sum(
            1 for p in peri if p > fo.SINGLE_EVENT_DELTAV_CEILING_MPS),
        firstOrderRelativeErrorAtCircular=_spread(exact_gap),
        firstOrderRelativeErrorAtPerigee=_spread(exact_gap_peri),
        firstOrderScreenNote=(
            "registration eq. (7) against the shipped first-order relation; a SCREEN, "
            "reported and not acted on in this track"))


# ---------------------------------------------------------------------------
# Phase three: the control arm and the side-by-side
# ---------------------------------------------------------------------------
CONTROL = dict(eventsDetected=5341, eventsPriced=4888, eventsExcluded=4,
               folkloreMedian=0.0181, folkloreAnchored=54, folkloreBelowTenPercent=46,
               totalBurnedKg=130740.9, medianBurnedFraction=0.0598)


def compare(args):
    summary = json.loads(Path(args.receipt).read_text())
    arms = summary["arms"]
    control = dict(
        source="docs/fuel-odometer-20260920.md, measured 2026-09-20",
        expected=CONTROL,
        observedCircularArm=dict(
            eventsDetected=sum(summary["detectionReceipt"]["eventCounts"].values()),
            eventsPriced=sum(r["circular"]["eventsPriced"] or 0 for r in summary["perObject"]),
            eventsExcluded=sum(r["circular"]["eventsExcludedAsNotOwnPropulsion"]
                               for r in summary["perObject"]),
            folkloreMedian=arms["circular"]["folkloreExplainedFraction"]["median"],
            folkloreAnchored=arms["circular"]["folkloreExplainedFraction"]["n"],
            folkloreBelowTenPercent=arms["circular"]["folkloreExplainedFraction"]["belowTenPercent"],
            totalBurnedKg=arms["circular"]["totalBurnedKgLowerBound"],
            medianBurnedFraction=arms["circular"]["medianBurnedFractionLowerBound"]))
    checks = {}
    for k, tol in (("eventsDetected", 0), ("eventsPriced", 0), ("eventsExcluded", 0),
                   ("folkloreMedian", 5e-5), ("folkloreAnchored", 0),
                   ("folkloreBelowTenPercent", 0), ("totalBurnedKg", 0.1),
                   ("medianBurnedFraction", 5e-5)):
        got = control["observedCircularArm"][k]
        checks[k] = dict(expected=CONTROL[k], observed=got,
                         agrees=(got is not None and abs(got - CONTROL[k]) <= tol))
    control["checks"] = checks
    control["reproduced"] = all(c["agrees"] for c in checks.values())
    print(json.dumps(dict(control=control), indent=2))


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="phase", required=True)
    d = sub.add_parser("detect")
    d.add_argument("--archive", type=Path, required=True)
    d.add_argument("--catalog", type=Path, default=ROOT / "data/propulsion-catalog-v1.json")
    d.add_argument("--output", type=Path, required=True)
    d.add_argument("--gpu", action="store_true")
    d.add_argument("--limit", type=int, default=0, help="smoke runs only; never integrated")
    d.set_defaults(func=detect)
    i = sub.add_parser("integrate")
    i.add_argument("--events", type=Path, required=True)
    i.add_argument("--catalog", type=Path, default=ROOT / "data/propulsion-catalog-v1.json")
    i.add_argument("--output-prefix", type=Path, required=True)
    i.set_defaults(func=integrate)
    c = sub.add_parser("compare")
    c.add_argument("--receipt", type=Path, required=True)
    c.set_defaults(func=compare)
    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
