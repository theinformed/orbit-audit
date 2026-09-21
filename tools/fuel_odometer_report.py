#!/usr/bin/env python3
"""Render the fuel-odometer results: bounds stated as bounds, gaps stated as gaps."""
from pathlib import Path
import argparse
import json
import statistics

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--prefix', type=Path, default=ROOT/'docs/fuel-odometer-20260920')
prefix = parser.parse_args().prefix
s = json.loads(Path(str(prefix)+'-receipt.json').read_text())
rows = [json.loads(x) for x in Path(str(prefix)+'.jsonl').read_text().splitlines()]
det = s['detectionReceipt']
lines = []


def out(text=''):
    lines.append(text)


def f(x, places=1):
    if x is None:
        return '—'
    if isinstance(x, bool):
        return 'yes' if x else 'no'
    if isinstance(x, int):
        return f'{x:,}'
    return f'{x:,.{places}f}'


def pct(x, places=1):
    return '—' if x is None else f'{100*x:.{places}f}%'


def band(pair, places=1):
    return '—' if not pair else f'{f(pair[0],places)}–{f(pair[1],places)}'


def table(headers, data):
    out('| '+' | '.join(headers)+' |')
    out('| '+' | '.join('---' for _ in headers)+' |')
    for row in data:
        out('| '+' | '.join(map(str, row))+' |')
    out()


priced = [r for r in rows if r['burnedKgLowerBound'] is not None]
geo = [r for r in priced if r['sanity']['isGeo']]
anchored = [r for r in geo if r['sanity']['explainedFractionOfFolkloreBudget'] is not None
            and not r['electricStationKeeping']]
dry = [r for r in priced if r.get('propellantCapacityKg')]
retirees = [r for r in priced if (r.get('retirement') or {}).get('status') == 'graveyard']
fk = s['folkloreExplainedFraction']

out('# The fuel odometer: what the manoeuvre ledger says each satellite has burned')
out()
out('Measured 2026-09-20 UTC. Catalogue × detected-manoeuvre ledger, integrated through the '
    'rocket equation. Every number below is a **lower bound** or an explicit band; nothing here '
    'is a fuel gauge.')
out()
out('## The verdict, stated first')
out()
out(f"For the **{f(len(anchored))}** chemically-station-kept GEO satellites where the comparison is "
    f"meaningful, the detected station-keeping Delta-v accounts for a median of "
    f"**{pct(fk['median'],2)}** of the ~50 m/s/yr north-south-keeping rule of thumb — "
    f"**{f(fk['belowTenPercent'])} of {f(fk['n'])}** fall below 10%, and **none** exceed twice it. "
    f"This is a statement about our detection recall, not about how much fuel these satellites "
    f"burn. Routine station-keeping corrections are mostly below the detector's threshold, so the "
    f"station-keeping odometer reads **far too low, by construction**.")
out()
raised = sorted((r['raisingBurnVsCapacity']['ratioBand'][0], r) for r in dry
                if r['raisingBurnVsCapacity']['raisingBurnKgBand'][0] > 0)
strong = [x for x, _ in raised if x >= 0.5]
weak = [x for x, _ in raised if x < 0.5]
out('The transfer phase is the opposite story. Where a satellite raised itself out of a transfer '
    'orbit, the detector catches the apogee burns cleanly: the largest genuine single burns in '
    'this cohort cluster at 1,430–1,502 m/s, exactly the textbook apogee kick out of a standard '
    f"transfer orbit. **{f(len(raised))}** satellites both show a detected transfer burn and carry "
    f"a catalogued dry mass. For **{f(len(strong))}** of them the integrated transfer burn recovers "
    f"**{pct(min(strong))} to {pct(max(strong))}** of the catalogued launch-to-dry mass drop; the "
    f"remaining **{f(len(weak))}** recover only {pct(min(weak))}–{pct(max(weak))}, which is what a "
    'transfer that the archive only partly watched looks like — their coverage and event lists are '
    'in the JSONL. The odometer works where the burns are large and fails where they are small, '
    'and that is the single most useful thing this run establishes.')
out()
out(f"Across the whole cohort the integrated burn is **at least {f(s['totalBurnedKgLowerBound'])} kg** "
    f"of propellant over {f(len(priced))} satellites, median **{pct(s['medianBurnedFractionLowerBound'],2)}** "
    'of launch mass. Every one of those sums crosses at least one archive coverage hole, so every '
    'one of them is an "at least".')
out()
out('## Directionality, because it changes what every number means')
out()
table(['Quantity', 'Direction', 'Why'],
      [['Detected Delta-v per event', 'Lower bound',
        'The detector prices the cheapest manoeuvre consistent with the element change'],
       ['Events detected', 'Lower bound',
        'Sub-threshold, continuous and geometrically ambiguous burns are never counted'],
       ['Propellant burned', 'Lower bound at BOTH ends of the Isp band',
        'A lower-bound Delta-v cannot produce an upper-bound mass; the band is Isp uncertainty only'],
       ['Propellant remaining (21 objects with dry mass)', 'Upper bound',
        'Capacity minus a lower-bound burn; quote only the high-Isp edge'],
       ['Remaining fraction for the other 130', 'Not computed',
        'No dry mass, so no capacity, so no remaining-fraction claim is made']])
out('An Isp band is **not** an error bar on the fuel. A satellite whose catalogue entry is '
    'unresolved between a 210 s monopropellant and a 615 s arcjet gets both integrations and a '
    'flag; the midpoint of that band is not knowledge and is never reported as one.')
out()
out('## Cohort and detection')
out()
table(['Stage', 'Count'],
      [['Catalogue objects (`data/propulsion-catalog-v1.json`)', f(s['catalogue']['objects'])],
       ['Objects carrying a NORAD id — the detection cohort', f(s['catalogue']['withNorad'])],
       ['Archive rows re-detected for that cohort', f(det['selectedRows'])],
       ['Objects with no archive rows at all', f(len(det['objectsWithNoArchiveRows']))],
       ['Events detected (all signatures)', f(sum(det['eventCounts'].values()))],
       ['Propulsive events priced', f(sum(r['eventsPriced'] for r in priced))],
       ['Events excluded as not the satellite’s own propulsion', f(s['eventsExcludedAsNotOwnPropulsion'])],
       ['Objects with at least one coverage hole', f(s['objectsWithCoverageHoles'])],
       ['Objects with no propulsive event at all', f(s['objectsWithNoPropulsiveEvents'])]])
out('Detection re-ran the current post-56eef64 detector over the whole history of each catalogued '
    'NORAD, cohort-only, on the frozen read-only archive snapshot the EOL study also used. No '
    'published artifact was read: the published event list caps at 1,500 events catalogue-wide. '
    'Detection ran on CPU at nice 19 — 151 objects cost '
    f"{f(det['wallSeconds'])} s wall and {f(det['cpuSeconds'])} s CPU, so no GPU slot was taken.")
out()
table(['Signature', 'Events'], sorted(((k, f(v)) for k, v in det['eventCounts'].items()),
                                      key=lambda kv: -int(kv[1].replace(',', ''))))
out()
out('### The four events that are not this satellite’s fuel')
out()
data = [[r['norad'], r['name'], r['launchDate'], x['at'][:19], x['signature'], f(x['deltaVMps']),
         f(x['perigeeAltitudeKm']), f(x['apogeeAltitudeKm']), f(x['inclinationDeg'], 2), x['reason']]
        for r in priced for x in r['eventsExcludedAsNotOwnPropulsion']]
table(['NORAD', 'Name', 'Launch', 'Event', 'Signature', 'Δv m/s', 'Perigee km', 'Apogee km',
       'Incl °', 'Excluded because'], data)
out('These are visible in the data, not inferred: a 9,700 m/s "manoeuvre" three days before launch '
    'between an 840 km sun-synchronous orbit and a transfer orbit is a mis-associated element set; '
    'a 5,400 m/s step out of a 364 × 14,408 km 50.8° orbit on launch day is a Briz-M burn '
    'sequence. The cohort’s largest genuine satellite burn is 1,502 m/s, so the 2,500 m/s ceiling '
    f"sits in a clean gap. Without this rule **{f(s['objectsAbovePlausibilityCeilingWithoutCeilingRule'])}** "
    'objects would integrate to more propellant than any satellite in this catalogue carries '
    f"(the catalogue’s own maximum propellant fraction is **{pct(s['plausibilityCeilingFraction'])}** "
    f"of launch mass, from its {f(s['dryMassObjects'])} dry-mass rows). With it, "
    f"**{f(s['objectsAbovePlausibilityCeiling'])}** exceed that ceiling. Every object’s unfiltered "
    'integration is still published in the JSONL as `withoutCeiling`.')
out()
out('## Sanity anchor 1 — station-keeping against the 50 m/s/yr rule of thumb')
out()
table(['Statistic', 'Value'],
      [['Objects anchored (GEO, chemical station-keeping, observed exposure)', f(fk['n'])],
       ['Median fraction of the folklore budget explained', pct(fk['median'], 2)],
       ['Quartiles', band([100*x for x in fk['quartiles']], 2)+' %' if fk['quartiles'] else '—'],
       ['Range', band([100*x for x in fk['range']], 2)+' %'],
       ['Below 10% of the folklore budget', f(fk['belowTenPercent'])],
       ['Above twice the folklore budget', f(fk['aboveTwice'])]])
out('Observed years are **gap-aware**: they sum observed interval days from the end of the '
    '18-month station-acquisition window, never the calendar span across a hole. The 84 '
    'electrically station-kept satellites are excluded from this anchor entirely — a continuous '
    'low-thrust burn produces no step for a step detector to find, so their station-keeping '
    'odometer is not merely low, it is structurally blind. Cross-reference the drift lane.')
out()
out('The eight objects that come closest to the rule of thumb:')
out()
data = [[r['norad'], r['name'], f(r['sanity']['stationKeepingDeltaVMpsLowerBound']),
         f(r['sanity']['observedStationYears'], 2), f(r['sanity']['deltaVPerObservedYearMps'], 2),
         pct(r['sanity']['explainedFractionOfFolkloreBudget'])]
        for r in sorted(anchored, key=lambda r: -r['sanity']['explainedFractionOfFolkloreBudget'])[:8]]
table(['NORAD', 'Name', 'SK Δv m/s (≥)', 'Observed station yr', 'Δv/yr m/s (≥)',
       'Folklore budget explained'], data)
out()
out('## Sanity anchor 2 — the transfer burn against catalogued mass')
out()
out('A catalogued "dry mass" for a GEO communications satellite is very often the beginning-of-life '
    'mass **in GEO**, after the apogee burn, rather than a true structural dry mass. Where that is '
    'what the number means, the launch-to-dry difference is the transfer propellant, and the ratio '
    'below should approach 1. This is the only direct, per-object check the odometer has.')
out()
data = [[r['norad'], r['name'], f(r['launchMassKg'], 0), f(r['dryMassKg'], 0),
         f(r['propellantCapacityKg'], 0), band(r['raisingBurnVsCapacity']['raisingBurnKgBand']),
         band([100*x for x in r['raisingBurnVsCapacity']['ratioBand']])+' %',
         r['confidence']]
        for r in sorted(dry, key=lambda r: -r['raisingBurnVsCapacity']['ratioBand'][0])
        if r['raisingBurnVsCapacity']['raisingBurnKgBand'][0] > 0]
table(['NORAD', 'Name', 'Launch kg', 'Dry kg', 'Capacity kg', 'Detected transfer burn kg',
       'Ratio to capacity', 'Catalogue confidence'], data)
out(f"The remaining {f(sum(1 for r in dry if r['raisingBurnVsCapacity']['raisingBurnKgBand'][0] == 0))} "
    'dry-mass objects show a zero transfer burn: their archive history begins after the transfer '
    'was over, or they never had one (the two LEO objects). A zero here is missing observation, '
    'not a satellite that reached orbit for free.')
out()
over = [r for r in dry if r['remainingExceedsCapacity']]
if over:
    out('**One object integrates past its catalogued capacity.** '
        + '; '.join(f"{r['name']} (NORAD {r['norad']}) burns at least {f(r['burnedKgLowerBound'])} kg "
                    f"against a catalogued capacity of {f(r['propellantCapacityKg'],0)} kg, "
                    f"{pct(r['burnedKgLowerBound']/r['propellantCapacityKg'])} of it" for r in over)
        + '. That is a single-digit percentage overshoot on a quantity built from a lower-bound '
          'Delta-v and a catalogued mass whose semantics are not guaranteed, which reads as close '
          'agreement rather than as a contradiction — but it is reported as an overshoot, not '
          'quietly clipped, and its `propellantRemainingUpperBoundKg` is therefore negative in '
          'the JSONL.')
    out()
out('## Sanity anchor 3 — the sourced graveyard retirees')
out()
out(f"**{f(len(retirees))}** catalogue objects carry a sourced graveyard-disposal record. Their "
    f"burned fraction of launch mass has a median of "
    f"**{pct(s['retireeBurnedFractionOfLaunchMass']['median'],2)}** and a maximum of "
    f"**{pct(s['retireeBurnedFractionOfLaunchMass']['maxHighIspEdge'])}** at the high-burn edge of "
    'the Isp band — comfortably below any published propellant fraction, as it must be for a '
    'lower-bound odometer. This anchor can only ever falsify, never confirm: a retiree that '
    'integrated to more than its tank would have proved the method wrong, and none does.')
out()
data = [[r['norad'], r['name'], (r.get('retirement') or {}).get('retired_year') or '—',
         f(r['launchMassKg'], 0), band(r['burnedKgIspBand']),
         band([100*x for x in r['burnedFractionOfLaunchMass']], 2)+' %',
         f(r['signatureCounts'].get('geo-graveyard-raise', 0)),
         f(r['coverage']['holeCount'])]
        for r in sorted(retirees, key=lambda r: -r['burnedFractionOfLaunchMass'][0])]
table(['NORAD', 'Name', 'Retired', 'Launch kg', 'Burned kg (≥)', 'Of launch mass',
       'Graveyard raises detected', 'Holes'], data)
out()
out('## Isp unresolved: the bands the catalogue refuses to collapse')
out()
data = [[r['norad'], r['name'], r['bus'], band(r['ispBandSeconds'], 0)+' s',
         band(r['burnedKgIspBand']), f(r['massBandWidthKg']), f(r['eventsPriced'])]
        for r in sorted(rows, key=lambda r: r['norad']) if r['ispUnresolved']]
table(['NORAD', 'Name', 'Bus', 'Isp band', 'Burned kg (≥)', 'Band width kg', 'Events priced'], data)
unresolved = [r for r in rows if r['ispUnresolved'] and r['burnedKgLowerBound']]
widest = max(unresolved, key=lambda r: r['burnedKgIspBand'][1]/max(r['burnedKgIspBand'][0], 1e-9))
tightest = min(unresolved, key=lambda r: r['burnedKgIspBand'][1]/max(r['burnedKgIspBand'][0], 1e-9))
out('The A2100 bus documents both hydrazine monopropellant motors and electric thrusters for orbit '
    'maintenance, and the catalogue deliberately refuses to guess which flew on a given unit. The '
    'band is wide because the knowledge is absent, and the width is the honest report of that '
    'absence. Which way it hurts depends on the Delta-v: a burn large enough to empty most of a '
    'tank empties it at either Isp, so the ABSOLUTE band narrows as Delta-v grows, while the '
    f"RELATIVE band is worst where Delta-v is small. {widest['name']}'s burned mass is uncertain by "
    f"a factor of {widest['burnedKgIspBand'][1]/widest['burnedKgIspBand'][0]:.2f}; "
    f"{tightest['name']}'s by "
    f"{100*(tightest['burnedKgIspBand'][1]/tightest['burnedKgIspBand'][0]-1):.1f}%. "
    'A midpoint would hide both.')
out()
out('## Cross-prediction for the other two fuel routes')
out()
out('Every object carries a `crossPrediction` block for the quantum-drift (Route 2) and A/m-trend '
    '(Route 3) comparisons: predicted **fractional mass loss per year**, as a band, plus Δv per '
    'observed year and kg per year. All three are lower bounds, and each carries '
    '`atLeastBecauseOfCoverageHoles` — which is true for every object in this cohort.')
out()
rates = [(r['crossPrediction']['fractionalMassLossPerYear'][0], r) for r in priced
         if r['crossPrediction']['fractionalMassLossPerYear']]
rates.sort(key=lambda x: -x[0])
table(['Statistic', 'Value'],
      [['Objects with a fractional-mass-loss prediction', f(len(rates))],
       ['Median fractional mass loss per year (lower edge)',
        pct(statistics.median(x for x, _ in rates), 4)],
       ['Maximum', pct(rates[0][0], 3)+f"  ({rates[0][1]['name']})"],
       ['Minimum', pct(rates[-1][0], 4)+f"  ({rates[-1][1]['name']})"]])
out('A route that predicts a *larger* annual mass loss than this odometer is not contradicting it: '
    'this odometer misses burns. A route that predicts a *smaller* one is in genuine tension and '
    'should be examined.')
out()
out('## Limitations a reviewer will go for first')
out()
for text in [
    'Detection recall is the dominant error and it is one-sided. Station-keeping corrections at '
    'GEO are a few m/s; the detector needs a step that stands out against a fitted baseline. The '
    '1.8% median folklore fraction is the size of that miss, measured.',
    'Electric propulsion is invisible to a step detector by construction. 84 of 151 catalogued '
    'satellites station-keep electrically. For those, only the transfer phase is measurable at '
    'all, and even that is only measurable when it was chemical.',
    'Coverage holes are universal here: every object crosses at least one, median '
    f"{statistics.median(r['coverage']['holeCount'] for r in priced):.0f} holes, median coverage "
    f"fraction {statistics.median(r['coverage']['coverageFraction'] for r in priced if r['coverage']['coverageFraction']):.2f}. "
    'Sums are "at least" sums and observed years are gap-aware, but a hole that swallowed a burn '
    'is invisible either way.',
    'Launch mass, dry mass and Isp are catalogue values, '
    f"{sum(1 for r in rows if r['confidence'] == 'class-prior')} of {len(rows)} in the detection "
    'cohort at class-prior confidence. The '
    'rocket equation propagates a wrong Isp linearly into mass; it propagates a wrong launch mass '
    'proportionally. The confidence field travels with every row for exactly this reason.',
    '"Dry mass" is semantically unstable across sources — structural dry mass for some objects, '
    'beginning-of-life mass in GEO for others. Sanity anchor 2 depends on which one a given row '
    'means, and the catalogue does not always say.',
    'The 2,500 m/s single-event ceiling and the 18-month raising window are declared rules, not '
    'measured constants. Both are published with the unfiltered alternative alongside, but a '
    'reviewer is entitled to ask what a 2,000 m/s or 3,000 m/s ceiling would do — for this cohort, '
    'nothing, because the gap between 1,502 and 2,622 m/s is empty.',
    'A per-event mass decrement assumes each detected interval is one burn. A detected interval '
    'that contains several burns, or one burn split across two intervals, still sums correctly in '
    'Delta-v but the sequential exponential is only first-order in that case.',
    'Nothing here is validated against an operator-published propellant figure. The anchors are '
    'internal consistency checks against catalogue mass and a rule of thumb, which is weaker than '
    'ground truth and should not be described as calibration.',
]:
    out('- '+text)
out()
out('## Per-object results')
out()
out('Burned mass is the lower bound at the high-Isp edge; the band is the Isp range. "Holes" is '
    'the number of archive coverage gaps inside the object’s observed span — any non-zero value '
    'makes that row’s cumulative burn an "at least". Years covered is gap-aware observed exposure.')
out()
data = []
for r in sorted(rows, key=lambda r: (-(r['burnedKgLowerBound'] or -1), r['norad'])):
    cov = r['coverage'] or {}
    data.append([r['norad'], r['name'], r['confidence'],
                 f(r['launchMassKg'], 0),
                 f(r['burnedKgLowerBound']) if r['burnedKgLowerBound'] is not None else '—',
                 band([100*x for x in r['burnedFractionOfLaunchMass']], 2)+' %'
                 if r['burnedFractionOfLaunchMass'] else '—',
                 f(r['massBandWidthKg']) if r.get('massBandWidthKg') is not None else '—',
                 f((cov.get('observedDays') or 0)/365.25, 1),
                 f(r.get('eventsPriced', 0)),
                 f(cov.get('holeCount', 0)),
                 f(r['propellantRemainingUpperBoundKg']) if r['propellantRemainingUpperBoundKg'] is not None else '—',
                 r['sanity']['flag'] if r['sanity'] else '—'])
table(['NORAD', 'Name', 'Catalogue confidence', 'Launch kg', 'Burned kg (≥)', 'Of launch mass',
       'Band width kg', 'Years covered', 'Events priced', 'Holes', 'Remaining kg (≤)',
       'Sanity flag'], data)
out('## Reproduction and provenance')
out()
out('Analysis only: new files, a read-only archive snapshot opened through '
    '`orbit_campaigns.open_archive_for_reading`, no production artifact, no timer, no network, no '
    'deploy. The pre-registered rules are frozen in the module docstring and reproduced verbatim '
    'in the receipt’s `preRegisteredRules` field.')
out()
table(['Input', 'SHA-256'],
      [['Frozen archive snapshot', det.get('archiveSnapshotSha256') or 'not recorded'],
       ['Propulsion catalogue', s['catalogue']['sha256']],
       ['Cohort extraction', det['extractionSha256']],
       ['Odometer module at detection', det['analysisSourceSha256']],
       ['Odometer module at integration', s['sourceHashes']['integration']],
       ['Reused EOL probe helpers', s['sourceHashes']['reusedProbe']],
       ['Reused EOL three-arm helpers', s['sourceHashes']['reusedStudy']],
       ['Manoeuvre expectations', s['sourceHashes']['expectations']]]
      + [[f'Detector source `{k}`', v] for k, v in det['sourceHashes'].items()])
out('```bash\nnice -n 19 ionice -c 3 .venv-gpu/bin/python tools/fuel_odometer.py detect \\\n'
    '  --archive /tmp/eol-study-20260920/archive.sqlite3 \\\n'
    '  --output /tmp/odometer-20260920/cohort-events.jsonl.gz\n\n'
    'nice -n 19 .venv-gpu/bin/python tools/fuel_odometer.py integrate \\\n'
    '  --events /tmp/odometer-20260920/cohort-events.jsonl.gz \\\n'
    '  --output-prefix docs/fuel-odometer-20260920\n\n'
    '.venv-gpu/bin/python tools/fuel_odometer_report.py\n```')
out()
out('Artifacts: [per-object JSONL](fuel-odometer-20260920.jsonl), '
    '[receipt](fuel-odometer-20260920-receipt.json), '
    '[module](../tools/fuel_odometer.py), [report renderer](../tools/fuel_odometer_report.py), '
    '[tests](../tests/test_fuel_odometer.py). The JSONL carries, per object: the full mass curve '
    'sample (one point per priced event, with the mass band), the annual Δv trajectory, the '
    'coverage segments and holes, the excluded events with their reasons, the unfiltered '
    'integration, the per-leg split, and the cross-prediction block — enough for a site page to be '
    'precomputed without re-reading the archive.')
Path(str(prefix)+'.md').write_text('\n'.join(lines)+'\n')
print('Report written', str(prefix)+'.md')
