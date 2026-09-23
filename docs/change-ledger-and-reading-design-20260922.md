# The change ledger and the reading — DESIGN ONLY

**Date:** 2026-09-22. **Status:** design; nothing here is built, measured or
registered. **Scope:** an addendum to `docs/orbits-section-design-20260922.md`
(the Orbit-changes section) and `docs/kinematic-reach-design-20260922.md` (the
reach layer, T13, T14). It replaces the section's *Timeline* view with a
**ledger of change episodes** that carry a lifecycle, and it specifies **the
reading**: the structured statement printed at onset and at every state change.
**Inherits unchanged:** the vocabulary gate and never-say list (alarm design
§6–§7, `src/orbit-changes-strings.ts`), the prior-art bans, the fuel policy, and
every reserved operator decision. Every number is quoted from a committed
result with its source, or derived here and labelled *derived*.

**The operator's brief, verbatim:** *"have some sort of ledger people can scroll
through of satellites whose orbits changed and they can click into it and
inspect the change and see it. If it is still changing — like if a change was
initiated but it is continuing to change — it needs to be marked initiated and
then in progress then completed, and each shows the initial and then final,
with final being where it is at right now if it is continuing to burn or where
it ended up. And: if a satellite starts a burn, can we use pattern of life or
our library or our calculations to say ok, this thing started to move — we
think it is going to actually not just do station keeping but move into
another orbit, and then say okay that makes sense, this is a Starlink or USSF
satellite and it is just in a holding pattern and now burning to go to a final
orbit, or actually this one is burning in such a way that we think it might be
getting ready to [reach] X, Y or Z satellite."*

---

## 0. The answer in one paragraph

A **change episode** is the unit, not a point event. It opens when an element
set departs the object's own pre-change baseline beyond a registered floor, it
is **in progress** while the elements are still trending, and it **completes**
when they have held still for a registered dwell. Each state carries an
*initial* (the baseline) and a *current* (the newest element set while open;
the settled state once complete). Routine station-keeping never opens one:
the registered stationed band and the T3 cadence fingerprint are the baseline
it departs from. At onset and at each state change the page prints **the
reading**: the change's *type* from the T13 library with that type's published
agreement figure; the *routine check* from T14 patterns of life and public
operator declarations ("consistent with P, seen N times in this class"); if
not routine, the *reachable set* from the kinematic layer at its ladder stage
with that stage's measured precision; and the fixed denial of everything the
page may not say. Every slot is filled from a measured field by a template;
no text is generated. Where a field is not yet measured the clause prints its
gap in words — **no number until the replay**. The detector this programme
ships is impulsive-event-shaped; the one continuous-thrust instrument it has
(`orbit_campaigns.sustained_thrust`) is confined to the drag regime, so an
electric raise above 1,400 km apogee has **no onset detector today**, and §1.6
says so rather than pretending otherwise.

---

## 1. Change episodes

### 1.1 What exists, and what each episode kind is built from

| Kind | Onset instrument (existing, reused) | Where |
|---|---|---|
| Impulsive, near-GEO | confirmed drift-rate flag chain: departure ≥ max(5σ_ḋ, 0.010) = 0.010 °/day from the trailing baseline, confirmed at the **second** consecutive departing element set, chains merged within 5 d | `tools/proximity_geo.drift_change_flags`; T8d `MERGE_DAYS`/`CONFIRM_DAYS` = 5 |
| Impulsive, outside GEO | the shipped step detector's `candidate` events (κ = 8 on the object's own residual scatter, 2-day persistence, cohort screen; passive control 34 flags in 1,941 intervals) | `pipeline/orbit_campaigns.step_persistence`, `orbit_events.py`; the `manifest.orbitEvents` bundle |
| Continuous raise, drag regime | `sustained_thrust`: ≥ 4 five-day blocks, ≥ 80% agreeing in sign, median block rate > 8 × its own standard error; **gated to apogee ≤ 1,400 km and B\* ≥ 1e-7** (passive sweep 0 claims on 10,020 non-propulsive objects at that point) | `pipeline/orbit_campaigns.sustained_thrust`; `thrust_excess_events` for a day faster than the object's own rate |
| Multi-step campaign | a chain of step events on one object with no gap > 180 d | T8b `CAMPAIGN_MAX_GAP_DAYS`; T13 episode type E2 |
| Routine keeping (must NOT open) | \|ḋ\| stays ≤ 0.020 °/day (the stationed band, 6 × 0.1° / 30 d); N-S keeping at Δi ≥ 5σ_i = 8.35e-4° with no drift change; the 14.00 d E-W line (208 carriers) and 14.00 d N-S line (56 comsats) as the object's own cadence | T13 registration rules G4/G5; T3 |

**Floors are the archive's measured element noise, never assumed:** GEO drift
σ_ḋ = 6.0385e-4 °/day over 3,740,056 samples
(`docs/proximity-20260922-receipt.json` `calibration.sigma_n_deg_per_day`);
LEO σ_n = 6.27e-5 rev/day median, p95 5.40e-3
(`docs/proximity-leo-20260922-receipt.json` `detect.sigmaNRevDay`); the
per-band σ(a) 1.67 m / 0.51 m / 0.10 m / 0.76 m / 12.44 m and σ(i) floored at
the 1e-4° quantum (`docs/orbit-history-design.md` §2, 787 triples). The tails
are the reason no Gaussian κσ is used anywhere here (p99/σ = 116 at GEO, 3,558
below 500 km): every floor is the registered one.

### 1.2 The three states, and what initial and current mean in each

| State | Enters when | `initial` | `current` / `final` |
|---|---|---|---|
| **INITIATED** | the onset instrument confirms (second departing element set; first `candidate` event; `sustained_thrust` first true) | the pre-change baseline the detector itself used: station-segment median λ and ḋ (GEO, `STATION_HALF_WIDTH_DEG` 0.3°, 30 d); the trailing block-median a, i (outside GEO, `BASELINE_BLOCKS` 6 × 5 d) | the confirming element set |
| **IN PROGRESS** | at any re-evaluation after onset the trend test (§1.3) says the elements are still moving, or a further confirmed step arrives inside the campaign window | unchanged | the newest element set — *where it is right now* |
| **COMPLETED** | the trend test has returned "still" for the whole dwell (§1.4) | unchanged | the settled state: new station-segment median λ, ḋ (GEO); block-median a, i over the dwell (outside GEO) |

Two further fields, not states: `closure` ∈ {open, settled, lapsed} and
`reopened` (count). A **lapsed** episode is one whose object stopped being
tracked before it completed (tracking gap ≥ 3 d, `DECLINE_AFTER_TRACKING_GAP`;
decay below 200 km perigee; archive end). It keeps its last state chip, greyed,
with the stamp *tracking ended* — it is never promoted to COMPLETED.

### 1.3 The in-progress test, derived

Two bars, both of which must clear, in the shape `thrust_excess_events`
already uses (a materiality bar and an evidence bar):

| | Near-GEO | Outside GEO |
|---|---|---|
| quantity | drift rate ḋ from the newest fitted window; the slot coordinate λ | daily-median semi-major axis a (and i on the plane channel) |
| trending if | \|ḋ\| > 0.020 °/day (outside the stationed band — the orbit is carrying the object somewhere), **or** a new confirmed flag inside the 5 d merge window | trailing 3-block (15 d) slope of a: \|slope\| > 8 × SE (SE = 1.4826 × MAD of block medians / √n, the module's own estimator) **and** \|slope\| × 15 d ≥ 0.050 km (`DA_FLOOR_KM`); or a new `candidate` step inside 180 d |
| materiality floor, in a | 0.78 km (the 0.010 °/day floor expressed in semi-major axis — T8d §4, *derived*) | 0.050 km |
| re-evaluated | every new element set (median spacing 0.7564 d measured on the near-GEO watch; 0.7721 d live) | every new element set (0.4935 d measured on the LEO band) |

A continuous raise therefore stays IN PROGRESS for the weeks or months the
climb lasts, with `current` advancing each element set; an impulsive change is
INITIATED and, if the object is stationed again in one step (an in-band
correction never opens; a drift start does), it passes to IN PROGRESS while it
drifts and to COMPLETED when the new station forms.

### 1.4 Completion and the dwell, derived from registered constants

| Regime | Dwell | Why this and not a chosen number |
|---|---|---|
| Near-GEO | a new station segment: \|ḋ\| ≤ 0.020 °/day and λ inside ±0.3° for **30 d** | `STATION_MIN_DAYS` — the same rule that defines a station everywhere else in the programme; T11 derived 56.0 d for *tandem* dwell, which is a stricter question |
| Outside GEO | the trend test returns "still" for **3 consecutive blocks (15 d)** | `MINIMUM_BASELINE_BLOCKS` — the shortest baseline the step detector itself will screen against; shorter and the completed state would be measured against noise it cannot yet size |

A confirmed step arriving after COMPLETED but inside the campaign window
(5 d GEO merge for the same chain; 180 d for a campaign) **re-opens** the
same episode (`reopened` += 1) rather than opening a new one. That re-open
count is the false-completion rate of §5, measured rather than guessed.

### 1.5 Relation to the ladder

| Episode kind | Ladder stages it can occupy |
|---|---|
| Impulsive, GEO two-step relocation (T8c C2: 4 d at 0.589 °/day, 126 events) | S1 at onset; S4 or expiry — no S2/S3 exists, the stop **is** the arrival |
| Staged transfer (C5: 76 d, 11 mid-course flags, 160 events) | S1 → S2 at each mid-course step (set shrinks) → S3 at the deceleration → S4 |
| Continuous raise | S1 at onset; the set is recomputed from `current` at every re-evaluation, so the ladder stage can move without a new step — **only** by the S3 rule (rate falling with the propagated stop inside one member's window) |
| LEO altitude-for-node setup (kinematic design §2.3) | S1 for months; the reverse step months later is S2/S3 |

An episode's stage is a field of its record; the reading prints the stage's
own rung precision or its gap, never a borrowed one.

### 1.6 Honest failure modes, in those words

| Failure | Why it happens | What the record does |
|---|---|---|
| **Missed onset** | changes below floor: 33% of T8a's 487 co-locations had no visible initiating flag; a GEO transfer below 0.010 °/day is invisible | an arrival with no open episode is written as an episode whose `onset` is *not observed* and whose initial is the last station — a labelled gap, counted in M8 |
| **Electric orbit raising above the drag regime** | `sustained_thrust` declines above 1,400 km apogee because nothing there guarantees a is being pushed down (triaxial libration, third-body); the step detector saw 91 of SES-12's 2,176 m/s | **no onset instrument exists in the programme today.** Such objects appear only if a step trips; the page says *continuous changes above 1,400 km are not detected by this record*. A registered extension needs a different null (candidate follow-up, §5) |
| **False completion during a pause** | staged transfers coast between steps; a 30 d / 15 d dwell can elapse | re-open rule (§1.4); the rate is measured (M8), and the ledger shows `reopened` |
| **Drag mimicking a lowering** | a sustained fall is what drag does; the LEO in-track detector trips on 87.4% of passives under drag variability (T8b Gate H) | a sustained fall **never** opens an episode (`sustained_thrust` returns false for it, by design); a step lowering below 1,400 km carries the pipeline's own `drag` field and prints *not separable from drag* unless the cohort screen says otherwise |
| **A fit excursion** | the catalogue re-fits, moves the object and puts it back | the 2-day persistence rule already rejects it (`PERSISTENCE_FRACTION` 0.5) |

The T8b in-track flag is **not** an onset source for the ledger: its own
passive control fired at 0.797 of the payload rate (alarm build §7.2). Outside
GEO the ledger opens on the shipped bundle's events only.

---

## 2. The reading

Printed at INITIATED and again at every state change, four lines in a fixed
order. Every slot is a measured field; the strings below are the strings, and
`tools/orbit_changes_strings.py` generates them into `src/orbit-changes-strings.ts`
beside the existing ones so the vocabulary test scans them. **There is no
generated prose and no optional decoration of any kind in v1** — nothing
composes a sentence, so nothing can gate one.

### 2.1 Templates

| Line | Condition | Template (verbatim) | Slot → field |
|---|---|---|---|
| **R1 type** | agreement measured, n ≥ 20 | `Type: {typeLabel}. Agreement with the {labelClass} record: {agreementPercent}% of {typeSupport} matched changes (library {libraryVersion}).` | T13 artifact: `type`, `agreement.labelClass`, `agreement.percent`, `agreement.n`, `version` |
| | n < 20 | `Type: {typeLabel}. Fewer than 20 matched changes; no agreement figure.` | T13 Gate U |
| | library not measured | `Type: not yet labelled. The library's agreement table has not been measured.` | M4 absent |
| **R2 routine** | routine | `Consistent with {patternLabel}, seen {patternCount} times in {classLabel}.` | T14: `pattern.label`, `pattern.count`, `class.label` (regime × era × bus family, or × constellation name family at LEO) |
| | + declared | ` An operator-published planned change covers this epoch ({declaredSource}, published {declaredDate}).` | T16a: `declared.source`, `declared.publishedIso` — shown only if decision 10.9 says so |
| | not routine | `Not consistent with any routine pattern of {classLabel}: {featureLabel} is {featureValue}, outside the class range {classP5}–{classP95}. Routine objects of this class exceed this deviation {falseAlarmPercent}% of the time.` | T14 anomaly: `feature.label/value`, `class.p5/p95`, `falseAlarmRate` |
| | not measured | `Routine check: not yet measured for {classLabel}.` | M5 absent |
| **R3 reach** (printed when R2 is *not routine* or *not measured*) | rung measured | `Reaches the stations of {setSize} catalogued objects within {horizonDays} days ({setSizePlaneCompatible} in a compatible plane). Stage {stage}: {k} of {n} changes of this class at this stage ended within 0.1° of any satellite's station for 30 days or more — {precisionPercent}% (95% interval {wilsonLo}–{wilsonHi}%). No figure exists for any particular satellite.` | reach contract: `setSize`, `setSizePlaneCompatible`, `horizonDays`, `stage`, `stagePrecision.k/n/percent/wilson` |
| | rung not measured | `Reaches the stations of {setSize} catalogued objects within {horizonDays} days ({setSizePlaneCompatible} in a compatible plane). Stage {stage}: no number until the replay.` | M3 absent; today every stage above S1 |
| | S1, class 1, GEO (today) | as "rung measured" with k = 28, n = 822, 3.4%, 2.4–4.9% | frozen model `trigger-time-taxonomy/20260922/1` |
| | LEO in-plane | `Shares a plane with {setSize} catalogued objects; phase inside that plane is reachable within {horizonDays} days. Cross-plane reach is not computed.` | M6 absent by construction |
| **R4 denial** | always | the section's `NOT_THIS` string and both `STRUCTURAL_CAVEATS`, byte for byte | `src/orbit-changes-strings.ts` |

Names in R3's set are listed in the reach view by days-to-reach (decision
10.4: catalogue names as facts); the sentence itself carries counts only.
Registry lines appear nowhere in the reading (10.3 open).

### 2.2 The headline and the delta line (ledger row)

| String | Template |
|---|---|
| headline | `{typeLabel} — {verdictWord}` with `verdictWord` ∈ {`routine for its class`, `not routine`, `routine check not yet measured`} |
| delta, GEO | `drift {initialDrift} → {currentDrift} °/day · longitude {initialLon} → {currentLon}` (drift 3 decimals, longitude 2 decimals E/W) |
| delta, outside GEO | `semi-major axis {initialA} → {currentA} km ({deltaA})` and, only when \|Δi\| ≥ the regime floor, `inclination {initialI} → {currentI}°` (a: 2 decimals ≥ 1 km, metres below; i: 3 decimals) |
| a value below floor | renders as the labelled gap *below the floor*, never 0.000 |

### 2.3 What the reading never says

The never-say list is `NEVER_SAY_TERMS` in `src/orbit-changes-strings.ts` and
the frozen model's `neverSay`; the vocabulary test scans every template above.
In addition: no intent word ("heading for", "targeting", "preparing"); no
cause ("because"); no ownership as explanation — a constellation name may fill
`classLabel` because it is a catalogue fact, and a registry code may not fill
anything; no precision borrowed from another stage or class; no sentence about
the object's own history (gate H). The operator's "we think it is going to
move into another orbit" is rendered as R1 + R2's *not routine* + R3's set —
facts and counts — and nothing else.

---

## 3. The ledger view

**The ledger REPLACES the section's Timeline view** (route `#/orbits/ledger`;
`#/orbits/timeline` stays as an alias). The timeline's three families become
episode material: catalogue events are member steps of episodes; T8a
co-locations and T8b co-orbital stations are COMPLETED episodes with
`closure = settled` and a partner. The density strip (episodes per week per
regime, brush sets the date filter) is kept above the list.

| Element | Rendering |
|---|---|
| list | virtualised, newest-first by `updatedMs`; the index ships the last 12 months and older years load by page on scroll (§4) |
| row | date · state chip · object (name + NORAD) · regime · headline · delta line · stage stamp when R3 applies · `reopened ×N` stamp when > 0 |
| state chip, **form encodes state** | INITIATED = hollow ring; IN PROGRESS = ring half-filled; COMPLETED = filled disc; lapsed = the last chip at `--muted` .6 with the *tracking ended* stamp. Colour: ring stroke `--muted`; IN PROGRESS fill `--cyan` (the token the section already reserves for live readouts); nothing else coloured |
| stamps | the site's `.layer-status` badge: NOT ASSESSABLE, UNDERPOWERED, NOT LABELLED, TRACKING ENDED, DECLARED (when 10.9 permits) |
| filters (sticky row) | state · regime · type · verdict (routine / not routine / unmeasured) · date · object search. **No country or registry filter** (10.3) |
| default filter | recommendation (decision 10.12): near-GEO all + outside-GEO *not routine* and *unmeasured*, with the routine constellation raises one click away and their count printed in the header — volume, not concealment |
| click-through | the object page's **inspect** view at `#/orbits/object/<norad>?episode=<key>` |

**Inspect view.** The element time series (GEO: λ–t strip with ḋ readout;
outside GEO: the small multiples) with: the baseline drawn as a `--muted` band
(initial ± its own scatter); the onset marked; the observed trend since onset
in `--cyan`; the **projected end** for IN PROGRESS episodes from the ladder's
kinematics — GEO: the J22 forward path with the measured +30 d ribbon
(p50 0.408°, p75 0.898°, p95 2.08°, n = 49,318), hatched beyond 30 d *error
not measured beyond 30 days* until M1; continuous raise: the current block rate
extended as a straight line to the ladder horizon, labelled *if the rate
holds*, no ribbon until M2. Beneath it, the reading and its history — each
prior reading greyed above the current one so a reader sees the states pass.
Formatting laws and tokens as the section design §5; nothing decorative.

---

## 4. Data contract

### 4.1 The episode record

| Field | Content |
|---|---|
| `key`, `norad`, `name`, `regime`, `kind` | id; object; regime; impulsive / campaign / continuous / not-observed-onset |
| `state`, `closure`, `reopened`, `stage` | §1.2; ladder stage or `none` |
| `onsetMs`, `updatedMs`, `completedMs` | epochs; `completedMs` null while open |
| `initial` | `{lambdaDeg, driftDegPerDay}` or `{semiMajorAxisKm, inclinationDeg}` with the baseline's own scatter and its window |
| `current` | the same shape from the newest element set (open) or the settled window (completed), with `epochMs` |
| `steps[]` | member event keys (the existing `ChangeRow.key`s) with epoch and Δ |
| `trend` | `{slope, slopeSe, windowDays, trending: bool, test: "geo-band" \| "block-slope"}` |
| `reading` | `{r1, r2, r3, r4}` each `{text, filled: bool, gap: {reason, owed} \| null, earnedBy: {artifact, version, checksum}}` |
| `history[]` | `{ms, state, stage, readingHash}` per state change |
| `reach` | the kinematic layer's per-burn contract (design §2.6) or null |
| `declared` | `{source, publishedIso, kind}` from T16a or null |
| `versions` | `episodeSchema`, `trackerVersion` (rules + floors checksum), `libraryVersion`, `patternsVersion`, `ladderVersion`, `modelVersion` |

A printed precision names the artifact that earned it (`earnedBy`), so a
re-frozen library or ladder table invalidates the clause and not the episode.

### 4.2 Who produces it — recommendation: the release step, stateless

| Option | Verdict | Why |
|---|---|---|
| **`orbit_changes_release.py`, via a new pure module `pipeline/orbit_episodes.py`** | **recommended** | the episode is a *function of the archive up to `now_ms`*: recomputed each run from the registered instruments' outputs, byte-stable, no state file, no concurrent-writer problem — and **the replay is the same function with an injected clock**, so the synthetic exercise and the live product cannot diverge |
| the alarm-lane sidecar | no | it is an alert product behind the spoken gate, unscheduled by operator decision, and its ledger holds spoken rows only; the episode ledger is a record of every change. The lane's rows are **joined** to episodes by (norad, onset) to fill R3 when a class speaks |
| a new tracker with its own timer | no | a second scheduled lane for a quantity the daily release can compute in seconds |

Cost: near-GEO chains over 1,768 objects (the lane measured 74 s for that
read); outside GEO, episodes are grouped from the events the sweep already
produced plus the per-object `sustained_thrust` verdict. CPU, seconds to
minutes, at the tail of `orbit-release`. **No new GPU consumer.** The build
must verify the thrust verdict actually reaches the release bundle; if it does
not, continuous episodes are a labelled gap until it does.

### 4.3 Cadence, payload, gaps

| | |
|---|---|
| tracker re-evaluation | every element set (the state function reads all of them); page freshness = the release cadence (~daily, 20 h gate) — printed in the ledger header as *record to {date}* |
| index | `orbit-episodes-index-<sha>`: last 12 months, ~250 B/row raw; **volume not yet counted** (GEO relocations ≈ 2,956 over the archive; outside-GEO constellation raises could be thousands a year) — the build measures it and, if the 12-month index exceeds ~150 KB gz, drops to 6 months. Older years: `orbit-episodes-<year>-<sha>` on demand |
| per-episode file | `orbit-changes-event-*` gains `baseline`, `trend`, `projectedEnd`, `history` (≈ +1 KB) |
| landing budget | stays inside the section's 320 KB gz |
| labelled gap | any clause whose measurement is absent prints its gap sentence and `gap.owed` names the M-number; the page never computes a precision, a rate or an agreement figure — every number is copied from an artifact with its checksum |

---

## 5. Measurements owed before each clause may print

| # | Measurement | Feeds | State |
|---|---|---|---|
| M0 | class-conditional next-burn size | R3 `withinClassRange` | **landed** (`docs/kinematic-inputs-20260922.json`) |
| M1 | GEO forward error at +60/+90/+180 d | projected end beyond 30 d | in flight |
| M2 | LEO per-object phase-error growth | continuous-raise ribbon | in flight |
| M3 | ladder replay: rung precisions, set sizes, recall, expiry | R3 at S2/S3; `stage` | after T13 |
| M4 | T13 agreement matrix | R1 | registration committed (`d86b93d`) |
| M5 | T14 baselines + anomaly false-alarm rate | R2 | not started |
| M6 | plane-noise floor | any cross-plane set | standing T8b item |
| M7 | GEO dead-payload control | control (a) at GEO | T11b in flight |
| **M8 (new)** | **episode-state classifier on the replay**, per regime and kind: share of INITIATED that reach COMPLETED / lapse / re-open; false-completion rate at the registered dwell and at 2×; median time in each state; onsets missed (arrivals with no open episode); episodes opened on never-manoeuvred objects (must be zero for propulsive kinds — T8b Gate B shape) | every state chip; §1.6 rows | registration owed |
| **M9 (new)** | T16a coverage: share of Starlink-class onsets covered by a published planned change, and the epoch tolerance | R2's declared clause; decision 10.9 | after T16a ingest |
| **M10 (new)** | agreement of episode boundaries with T8b campaign boundaries and T10a transfer phases (boundary, not exact epoch — alarm build §7.3's lesson) | `steps[]`, campaign kind | with M4 |
| candidate | a continuous-thrust onset above 1,400 km apogee with a null that is a guarantee (triaxial + third-body), registered separately | §1.6 row 2 | not promised |

A registration is committed alone before each. Until M8 lands, state chips
render but the header prints *state rates not yet measured*; until M4/M5/M3,
the corresponding line prints its gap.

---

## 6. Operator decisions reserved

10.2–10.8 stand. Added by this design:

| # | Decision | Recommendation |
|---|---|---|
| 10.9 | operator-declared planned changes shown as such | yes, as a source-labelled fact (`DECLARED` stamp + R2's clause); it never changes the state or the type |
| 10.10 | the ledger replaces the timeline (vs. a fifth view) | replace; the timeline's rows are the episodes' steps and a second list of the same events is two ledgers |
| 10.11 | default filter hides routine outside-GEO raises behind a count | yes (§3); the count is printed, nothing is deleted |
| 10.12 | a re-opened episode is one episode | yes; `reopened` is shown and is the false-completion measurement |
| 10.13 | lapsed episodes retained | forever, like alerts (10.7); a lapse is a fact about tracking |
| 10.14 | continuous raises above 1,400 km apogee: labelled gap on the page, or the candidate registration in §5 | the gap now; the registration if the operator wants those objects (electric GEO transfers) in the ledger |

---

## 7. Build order, and what the in-flight build changes now

### 7.1 Changes to make now, so the timeline becomes the ledger without rework

| File | Change now |
|---|---|
| `src/orbit-changes.ts` | add `EpisodeRow` beside `ChangeRow`: `{key, norad, name, regime, kind, state, closure, reopened, stage, onsetMs, updatedMs, completedMs, initial, current, headline, delta, steps: string[]}`; `ChangesIndex.rows` becomes `EpisodeRow[]` with `steps` referencing `ChangeRow.key`s in a sibling `changes[]`; route `ledger` added to `OrbitChangesView` with `timeline` as alias; `state` chip renderer in form (§3) |
| `pipeline/orbit_changes_release.py` | new `pipeline/orbit_episodes.py` (pure: instruments' outputs in, episode records out, `now_ms` injected); the index groups rows into episodes; the T8a/T8b families become COMPLETED episodes; event files gain `baseline`, `trend`, `projectedEnd`, `history`; `reading` present with every clause a gap except R3 at S1 for class 1 |
| `tools/orbit_changes_strings.py` | emit §2.1's templates and §2.2's headline words into the generated string table |
| `tests/orbit-changes-vocabulary.test.ts` | scan the new templates; seed a forbidden word and assert failure first |
| `tests/test_orbit_episodes.py` | fixtures: one impulsive GEO relocation (INITIATED → IN PROGRESS → COMPLETED), one staged transfer with a pause (re-open), one continuous raise (IN PROGRESS across 6 blocks), one E-W keeping cycle (**opens nothing**), one sustained fall (**opens nothing**), one tracking lapse; each asserts the bug first |

### 7.2 Order

| # | Step | Verify by |
|---|---|---|
| 1 | `orbit_episodes.py` + tests; run on a fixture archive **and** on the real archive with `now_ms` injected at 2019-01-01, 2022-01-01 and today | byte-stable across two runs; the fixtures above pass; the three injected clocks reproduce each other's earlier states |
| 2 | index/event artifacts carry episodes; manifest merge unchanged | sizes measured and written into §4.3's table; `publish_data.py` hashes pass |
| 3 | ledger view with chips, filters, density strip, paging | captures at three breakpoints; release-review greps clean; a row for each state visible in the capture |
| 4 | inspect view: baseline band, onset, trend, projected end with the hatched horizon | the T8d stable points reproduce; the ribbon stops at +30 d |
| 5 | reading templates wired; every clause a labelled gap except R3/S1 class 1 | grep proves the page holds no arithmetic on precision, rate or agreement |
| 6 | M8 registration committed alone → replay over 2010–2020 with the injected clock → state rates printed in the header | the receipt's numbers appear verbatim on the page |
| 7 | R1 after M4; R2 after M5 (and M9 for the declared clause, if 10.9 = yes); R3 above S1 after M3 | each clause flips from gap to figure only when its artifact exists, asserted by test |
| 8 | conductor pixel review; deploy per the section design §7 steps 10–11 | captures attached to the change report |

Nothing waits for a scheduled run: step 1's injected clocks are the synthetic
exercise, run now.

---

## 8. Sources of every number

```
docs/orbits-section-design-20260922.md     §2, §3, §5, §6, §7
docs/kinematic-reach-design-20260922.md    §2.2–2.7, §3, §5, §6, §9
docs/alarm-lane-design-20260922.md         §3, §4, §6, §7, §10
docs/alarm-lane-build-20260922.md          §3 (cadence), §6.5, §7.1–7.3, §9
docs/manoeuvre-library-preregistration-20260922.md  §3 floors, §4 rules, §8 gates
docs/kinematic-inputs-20260922.json        M0
docs/proximity-20260922-receipt.json       calibration.sigma_n_deg_per_day
docs/proximity-leo-20260922-receipt.json   detect.sigmaNRevDay, sigmaNP95RevDay
docs/orbit-history-design.md §2, §2.1      per-band σ, the tails
docs/transfer-loss-results-20260922.md     the electric arm (SES-12)
docs/alarm-pattern-results-20260922.md     C2, C5
pipeline/orbit_campaigns.py                sustained_thrust, thrust_excess_events,
                                           window_persistence, the constants
pipeline/orbit_events.py                   DRAG_MODEL_CEILING_KM, MINIMUM_USABLE_BSTAR,
                                           TERMINAL_DECAY_PERIGEE_KM
tools/proximity_geo.py, trigger_alarm.py   floors, station segment, MERGE/CONFIRM
src/orbit-changes.ts, orbit-changes-strings.ts, orbit-changes-policy.ts  the in-flight build
```
Derived here and labelled: the 0.78 km materiality floor; the 15 d slope
window; the 3-block dwell; the index size estimates (to be measured).
