#!/usr/bin/env python3
"""The synthetic exercise of `docs/alarm-lane-design-20260922.md` section 11.6.

The estate rule is that a lane which would run later is exercised NOW. This
driver runs the sidecar of `tools/alarm_lane.py` over a REPLAY of a historical
window with an INJECTED CLOCK, at each of several OPERATING POINTS from
`tools/alarm_lane_curve.py`, and compares the alerts it raises against the
committed outcome record. **No timer and no cron entry is installed by this
module or by any other part of the lane**, and nothing it writes reaches any
site surface.

THE WINDOW RULE, fixed before any number was computed and outcome-blind: the
replay covers the decade with the MOST confirmed drift changes, which
`docs/trigger-alarm-results-20260922.md` section 3.1 reports as the 2010s
(71,661 of 226,422 flag chains). The window is chosen on ALERT VOLUME and on
nothing about what those alerts turned into, so it cannot flatter the
precision it measures.

THE TICK is the derived cadence of design section 2.3 -- one median
element-set spacing, measured on the element sets the lane actually reads --
and not a period anyone chose. The extra latency the tick adds is measured
here and reported, because a cadence that costs warning time should be seen
to cost it.

WHAT THIS REPLAY CANNOT DO, said plainly: the frozen partition was fitted on
the whole 1959-2026 primary arm, which CONTAINS this window. The replay is
therefore IN SAMPLE for the taxonomy. It proves that the sidecar reproduces
the offline detector, that the gate withholds what it should, that the ledger
and its audit work end to end, and that the alert volume and lead time are
what the frozen artifact and the operating-point curve say. It is NOT an
out-of-sample estimate of precision, and the out-of-sample figure remains the
object-disjoint one in the results document.

    python3 tools/alarm_lane_replay.py --work <alarm lane work dir> \\
        --settings everything,high-confidence
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

_REPO = Path(__file__).resolve().parents[1]
for _p in (str(_REPO / "tools"),):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import proximity_geo as pg            # noqa: E402
import trigger_alarm as ta            # noqa: E402
import alarm_lane as al               # noqa: E402

DAY_MS = pg.DAY_MS

WINDOW_RULE = (
    "the decade with the most confirmed drift changes, per "
    "docs/trigger-alarm-results-20260922.md section 3.1 (the 2010s, 71,661 of "
    "226,422 flag chains). Chosen on ALERT VOLUME, which is outcome-blind, "
    "and fixed before any figure in this replay existed.")
WINDOW_START = "2010-01-01T00:00:00+00:00"
WINDOW_END = "2020-01-01T00:00:00+00:00"

IN_SAMPLE_NOTE = (
    "The frozen partition was fitted on the whole 1959-2026 primary arm, "
    "which contains this window, so every precision figure measured here is "
    "IN SAMPLE for the taxonomy. The out-of-sample figure is the "
    "object-disjoint one in the results document and nothing here replaces "
    "it.")


def percentiles(values, ps=(5, 25, 50, 75, 95)):
    v = np.asarray([x for x in values if x is not None and np.isfinite(x)],
                   dtype=np.float64)
    if v.size == 0:
        return {"n": 0, "label": "NOT ASSESSABLE -- no values; a labelled gap"}
    return {"n": int(v.size),
            **{f"p{p}": float(np.percentile(v, p)) for p in ps}}


# ==========================================================================
def run_setting(args, model, curve, source, flags, events, setting_name,
                cadence, tick_days, say):
    """One end-to-end replay at one operating point: its own state file, its
    own ledger, its own audit."""
    setting = (al.operating_setting(curve, setting_name)
               if setting_name else None)
    tag = setting_name or "everything"
    work = Path(args.work)
    work.mkdir(parents=True, exist_ok=True)
    ledger = work / f"alarm-lane-replay-{tag}-ledger.jsonl"
    state_path = work / f"alarm-lane-replay-{tag}-state.json"
    for p in (ledger, state_path):
        if p.exists():
            p.unlink()

    start = al._ms(args.start)
    end = al._ms(args.end)
    # the occupancy table is advanced forward only, so each setting gets its
    # own; `at` consumes element sets at or before the query and can never
    # contain the future
    occupancy = ta.OccupancySweep(source.series_by_norad)
    state = al.load_state(state_path, model, cadence)
    clock = al.Clock(start)
    car = al.Sidecar(model, source, clock, state, events=events, flags=flags,
                     occupancy=occupancy, setting=setting, tick_days=tick_days)
    watch = car.watch()

    if args.warm_start:
        # the lane is modelled as ALREADY RUNNING at the window's start: every
        # chain that closed before it was announced then. A cold start would
        # announce fifty years of chains in one firing, which is a real
        # behaviour but not the one this replay is measuring.
        state["lastAnnouncedMsByNorad"] = {str(int(n)): start for n in watch}
    state["replay"] = {"windowRule": WINDOW_RULE, "start": args.start,
                       "end": args.end, "tickDays": tick_days,
                       "warmStart": bool(args.warm_start),
                       "setting": tag, "inSampleNote": IN_SAMPLE_NOTE}

    ledger.write_text(json.dumps(al.LEDGER_PROVENANCE, sort_keys=True) + "\n")
    records = []
    ticks = 0
    last_tick = start
    now = start
    step = tick_days * DAY_MS
    t_start = time.time()
    while now <= end:
        clock.set(now)
        fired = car.fire()
        if fired:
            records.extend(fired)
            al.ledger_append(ledger, fired)
        ticks += 1
        if ticks % 500 == 0:
            say(f"[{tag}] tick {ticks} at {al._iso(now)[:10]}: "
                f"{len(records)} assessments, "
                f"{sum(1 for r in records if r['spoken'])} alerts")
        last_tick = now
        now += step
    say(f"[{tag}] {ticks} ticks, {len(records)} assessments, "
        f"{sum(1 for r in records if r['spoken'])} alerts raised, "
        f"{time.time() - t_start:.0f}s")
    al.save_state(state, state_path)

    resolutions = al.resolve_ledger(records, events)
    al.ledger_append(ledger, resolutions)
    audit = al.audit_ledger(records + resolutions, model)

    lag = [(float(r["announcedAtMs"]) - float(r["tAnnounceMs"])) / DAY_MS
           for r in records if r.get("announcedAtMs")]
    by_id = {r["alertId"]: r for r in records}
    observed = []
    for res in resolutions:
        if res["state"] != "arrival":
            continue
        rec = by_id[res["alertId"]]
        observed.append({
            "class": rec.get("class"), "spoken": bool(rec.get("spoken")),
            "norad": rec["norad"], "tTrigIso": rec["tTrigIso"],
            "leadFromAnnounceRuleDays": float(res["leadDays"]),
            "leadFromActualAnnouncementDays":
                (float(res["arrivalMs"]) - float(rec["announcedAtMs"])) / DAY_MS,
        })

    per_class = {}
    for rec in records:
        key = "not-assessable" if rec.get("class") is None else int(rec["class"])
        row = per_class.setdefault(key, {"assessed": 0, "spoken": 0,
                                         "withdrawn": 0, "belowEvidence": 0,
                                         "arrivals": 0, "leads": [],
                                         "actualLeads": []})
        row["assessed"] += 1
        row["spoken"] += 1 if rec["spoken"] else 0
        row["withdrawn"] += 1 if rec.get("withdrawn") else 0
        row["belowEvidence"] += 1 if rec.get("evidenceFailures") else 0
    for o in observed:
        key = "not-assessable" if o["class"] is None else int(o["class"])
        row = per_class[key]
        row["arrivals"] += 1
        row["leads"].append(o["leadFromAnnounceRuleDays"])
        row["actualLeads"].append(o["leadFromActualAnnouncementDays"])

    classes = []
    for key in sorted(per_class, key=lambda k: (isinstance(k, str), str(k))):
        row = per_class[key]
        n, k = row["assessed"], row["arrivals"]
        lo, hi = ta.wilson(k, n) if n else (float("nan"), float("nan"))
        entry = {
            "class": key,
            "assessedInReplay": n,
            "spokenInReplay": row["spoken"],
            "withdrawnInReplay": row["withdrawn"],
            "belowEvidenceInReplay": row["belowEvidence"],
            "arrivalsInReplay": k,
            "precisionInReplay": (k / n) if n else None,
            "wilson95": [float(lo), float(hi)] if n else None,
            "underpowered": bool(n < al.MIN_SUPPORT_FOR_A_RATE),
            "leadDaysFromAnnounceRule": percentiles(row["leads"]),
            "leadDaysFromActualAnnouncement": percentiles(row["actualLeads"]),
        }
        if isinstance(key, int):
            frozen = al.model_class(model, key)
            entry["frozenFigure"] = {
                "n": frozen["n"], "positives": frozen["positives"],
                "precision": frozen["precision"],
                "wilson95": frozen["wilson95"],
                "arrivalDays": frozen["arrivalDays"],
                "label": ("earned on the whole 1959-2026 primary arm; printed "
                          "beside the replay's own figure, never instead")}
            point_row = al.setting_class_row(setting, key)
            if point_row is not None:
                entry["curveFigure"] = {
                    "alerts": point_row["alerts"],
                    "arrivals": point_row["arrivals"],
                    "precision": point_row["precision"],
                    "wilson95": point_row["wilson95"],
                    "leadDaysP50": point_row["leadDays"].get("p50"),
                    "alertsPerYear2010s": point_row["alertsPerYear2010s"],
                    "mayBeSpoken": point_row["mayBeSpoken"],
                    "label": ("what the operating-point curve says this "
                              "setting is worth over the whole archive; the "
                              "replay's own numbers are beside it")}
                entry["mayBeSpoken"] = al.class_may_be_spoken(
                    model, key, dict(point_row, settingName=tag))[0]
            else:
                entry["mayBeSpoken"] = al.class_may_be_spoken(model, key)[0]
        classes.append(entry)

    subset = write_committed_subset(args, tag, ledger, records, resolutions)
    return {
        "setting": tag,
        "settingPoint": (setting or {}).get("point"),
        "settingTradeoff": (setting or {}).get("tradeoff"),
        "ticks": ticks,
        "lastTickMs": last_tick,
        "counters": dict(state["counters"]),
        "assessments": len(records),
        "alertsRaised": sum(1 for r in records if r["spoken"]),
        "withdrawn": sum(1 for r in records if r.get("withdrawn")),
        "belowEvidence": sum(1 for r in records if r.get("evidenceFailures")),
        "notAssessable": sum(1 for r in records if not r["assessable"]),
        "announcementLagDays": percentiles(lag),
        "announcementLagNote": (
            "the delay between the announce time the detector defines and the "
            "tick on which the lane actually spoke. It is the cost of the "
            "derived cadence, measured rather than assumed. A setting with a "
            "persistence requirement above one adds its own wait on top, and "
            "that wait is in this number too."),
        "classes": classes,
        "observedArrivals": observed,
        "audit": audit,
        "auditReport": al.audit_report(audit),
        "fidelity": (verify_against_offline(args, model, records, start,
                                            last_tick, tag, say)
                     if args.verify_against else None),
        "ledger": {"path": str(ledger),
                   "rows": len(records) + len(resolutions) + 1,
                   "sha256": al.sha256_file(ledger)},
        "committedSubset": str(Path(subset).name),
    }


# ==========================================================================
def verify_against_offline(args, model, records, start, last_tick, tag, say):
    """Does the sidecar, driven by a clock, reproduce the offline detector?

    The offline trigger table is the one the frozen figures were measured on.
    Restricted to the span the replay actually covered -- chains that closed
    after the warm start and became announceable at or before the last tick --
    it should hold exactly the triggers the replay assessed, with exactly the
    same class for each. Any residual must be EXPLAINED, not tolerated."""
    import pickle
    with open(Path(args.verify_against) / "t8d-triggers.pkl", "rb") as fh:
        blob = pickle.load(fh)
    bundle = blob["bundle"]
    triggers, feats, outs = (bundle["triggers"], bundle["features"],
                             bundle["outcomes"])
    idx = [i for i in range(len(triggers))
           if triggers[i].eligible and outs[i]["resolvable"]
           and triggers[i].tTrig > start
           and triggers[i].tTrig + ta.CONFIRM_DAYS * DAY_MS <= last_tick]
    say(f"[{tag}] offline primary-arm triggers the replay should have seen: "
        f"{len(idx)}")
    offline_labels = al.classify([feats[i] for i in idx], model)
    offline = {(int(triggers[i].norad), int(triggers[i].tTrig)): int(c)
               for i, c in zip(idx, offline_labels)}
    live = {(int(r["norad"]), int(r["tTrigMs"])): r.get("class")
            for r in records if r["assessable"]}
    gaps = {(int(r["norad"]), int(r["tTrigMs"])): r["gapReason"]
            for r in records if not r["assessable"]}
    same = set(offline) & set(live)
    agree = sum(1 for k in same if offline[k] == live[k])
    missing = sorted(set(offline) - set(live))
    explained = [gaps[k] for k in missing if k in gaps]
    extra = sorted(set(live) - set(offline))
    by_key = {(int(t.norad), int(t.tTrig)): i for i, t in enumerate(triggers)}
    extra_unresolvable = sum(
        1 for k in extra
        if by_key.get(k) is not None and not outs[by_key[k]]["resolvable"])
    kinds = sorted({r.split(" is ")[0].split(" of ")[0] for r in explained})
    return {
        "offlineTriggers": len(offline),
        "liveAssessments": len(live),
        "inBoth": len(same),
        "classAgreements": agree,
        "classDisagreements": len(same) - agree,
        "onlyOffline": len(missing),
        "explainedByLabelledGaps": len(explained),
        "labelledGapReasonKinds": kinds,
        "unexplainedOnlyOffline": len(missing) - len(explained),
        "onlyLive": len(extra),
        "onlyLiveBecauseNotResolvableOffline": extra_unresolvable,
        "unexplainedOnlyLive": len(extra) - extra_unresolvable,
        "note": ("the offline table is the population every frozen figure was "
                 "measured on. The only differences are the design's own "
                 "labelled-gap rule, which the offline measurement does not "
                 "apply, and triggers the offline table drops as not "
                 "resolvable -- a property that needs 210 days of future "
                 "element sets and that NO LIVE LANE CAN KNOW."),
    }


def write_committed_subset(args, tag, ledger, records, resolutions):
    """The full replay ledger is large and this repository is a teaching-aid
    source tree, not an archive. What is committed is every SPOKEN alert,
    every withdrawal, every row that an arrival resolved, and a seeded uniform
    sample of the rest -- with the full file's row count and sha256 in the
    provenance record.

    The sampling rule reads only whether the row was spoken or withdrawn, so
    **the alerts are complete rather than sampled** and every precision an
    alert could quote can be recomputed from the committed file."""
    rng = np.random.default_rng(ta.SEED)
    arrived = {r["alertId"] for r in resolutions if r["state"] == "arrival"}
    keep, others = [], []
    for r in records:
        if r["spoken"] or r.get("withdrawn") or r["alertId"] in arrived:
            keep.append(r)
        else:
            others.append(r)
    sampled = 0
    if others:
        sampled = min(args.sample, len(others))
        picks = sorted(rng.choice(len(others), size=sampled, replace=False))
        keep.extend(others[i] for i in picks)
    kept = {r["alertId"] for r in keep}
    keep_res = [r for r in resolutions if r["alertId"] in kept]
    # the rendered text of a row that was never spoken is a labelled gap
    # reconstructible from `gapReason`, and it is most of the file's bytes
    keep = [r if r.get("spoken") else dict(r, text=None) for r in keep]
    out = Path(args.out) / f"alarm-lane-replay-{args.date}-{tag}-ledger.jsonl"
    prov = dict(al.LEDGER_PROVENANCE)
    prov["setting"] = tag
    prov["subsetOf"] = {
        "path": str(ledger),
        "rows": len(records) + len(resolutions) + 1,
        "sha256": al.sha256_file(ledger),
        "assessmentsInFull": len(records),
        "spokenKept": sum(1 for r in records if r["spoken"]),
        "withdrawnKept": sum(1 for r in records if r.get("withdrawn")),
        "arrivalRowsKept": len(arrived),
        "otherAssessments": len(others),
        "otherAssessmentsSampled": sampled,
        "rule": ("every spoken alert, every withdrawal, every assessment an "
                 "arrival resolved, plus a seed-%d uniform sample of %d of "
                 "the %d others. The sampling rule reads only whether the row "
                 "was spoken or withdrawn, so the alerts are complete rather "
                 "than sampled. The rendered text of a row that was never "
                 "spoken is dropped; it is a labelled gap reconstructible "
                 "from `gapReason`." % (ta.SEED, sampled, len(others)))}
    prov["replayReceipt"] = f"alarm-lane-replay-{args.date}-receipt.json"
    with open(out, "w") as fh:
        fh.write(json.dumps(prov, sort_keys=True) + "\n")
        for r in sorted(keep, key=lambda r: (r["tTrigMs"], r["norad"])):
            fh.write(json.dumps(r, sort_keys=True, allow_nan=False) + "\n")
        for r in keep_res:
            fh.write(json.dumps(r, sort_keys=True, allow_nan=False) + "\n")
    return out


# ==========================================================================
def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--model", default=str(al.MODEL_PATH))
    p.add_argument("--curve", default=str(al.CURVE_PATH))
    p.add_argument("--settings", default="everything,high-confidence")
    p.add_argument("--work", required=True,
                   help="the alarm lane's working directory")
    p.add_argument("--out", default=str(_REPO / "docs"))
    p.add_argument("--date", default="20260922")
    p.add_argument("--start", default=WINDOW_START)
    p.add_argument("--end", default=WINDOW_END)
    p.add_argument("--tick-days", type=float, default=None,
                   help="override the derived cadence; normally absent")
    p.add_argument("--warm-start", action="store_true", default=True)
    p.add_argument("--cold-start", dest="warm_start", action="store_false")
    p.add_argument("--verify-against", default=None,
                   help="the trigger-time predictor's working directory; when "
                        "given, the replay is checked against the offline detector")
    p.add_argument("--sample", type=int, default=1000)
    args = p.parse_args(argv)

    t0 = time.time()

    def say(m):
        print(f"  [{time.time() - t0:8.1f}s] {m}", flush=True)

    model = al.load_model(args.model)
    curve = al.load_operating_points(args.curve, model)
    say(f"frozen model {model['modelVersion']} "
        f"checksum {al.model_checksum(model)[:16]}")
    say(f"curve {curve['curveVersion']} "
        f"checksum {al.model_checksum(curve)[:16]}")

    source = al.ExtractSource()
    say(f"{len(source.series_by_norad)} element histories in memory")
    flags = al.MemoisedFlags(source.series_by_norad)
    events = al.load_event_record()

    spacing = al.measured_epoch_spacing_days(
        list(source.series_by_norad.values()))
    cadence = al.derive_cadence(
        spacing,
        spacing_source=(f"measured over all {len(source.series_by_norad)} "
                        f"watched objects' element sets"))
    tick_days = float(args.tick_days if args.tick_days
                      else cadence["workFloorDays"])
    cadence["replayTickDays"] = tick_days
    cadence["replayTickSource"] = ("the derived work floor" if not args.tick_days
                                   else "supplied on the command line")
    say(f"derived cadence: work floor {cadence['workFloorDays']:.4f} d, "
        f"tick {tick_days:.4f} d")

    runs = []
    for name in [n.strip() for n in args.settings.split(",") if n.strip()]:
        runs.append(run_setting(args, model, curve, source, flags, events,
                                name, cadence, tick_days, say))

    receipt = {
        "artifact": "alarm-lane-replay-receipt",
        "schema": 1,
        "design": al.DESIGN,
        "status": ("SYNTHETIC EXERCISE. Nothing is deployed, nothing is "
                   "scheduled, no timer or cron entry exists, nothing is on "
                   "any site surface, and no alert left this machine."),
        "windowRule": WINDOW_RULE,
        "window": {"start": args.start, "end": args.end,
                   "tickDays": tick_days,
                   "warmStart": bool(args.warm_start)},
        "inSampleNote": IN_SAMPLE_NOTE,
        "model": {"version": model["modelVersion"],
                  "checksum": al.model_checksum(model)},
        "curve": {"version": curve["curveVersion"],
                  "checksum": al.model_checksum(curve),
                  "monotonicityNote": curve.get("monotonicityNote"),
                  "recallNote": curve.get("recallNote"),
                  "tradeoffNote": curve.get("tradeoffNote")},
        "cadence": cadence,
        "clock": {"mode": "injected", "start": args.start, "end": args.end},
        "settingsExercised": [r["setting"] for r in runs],
        "runs": runs,
        "caveats": list(al.CAVEATS),
        "neverSay": list(al.NEVER_SAY),
        "reservedDecisions": dict(al.RESERVED_DECISIONS),
        "reservedNote": al.RESERVED_NOTE,
        "host": "pc",
        "executionMode": "CPU, one core",
        "wallSeconds": time.time() - t0,
    }
    out = Path(args.out) / f"alarm-lane-replay-{args.date}-receipt.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipt, indent=1, sort_keys=True) + "\n")
    say(f"receipt: {out}")

    for run in runs:
        print()
        print(run["auditReport"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
