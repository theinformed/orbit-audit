# Orbit-history browser — implementation and operating record

## 2026-09-12 — nightly long-arc drift v4 (source only; not deployed)

The new `orbit-drift.service` / `.timer` recomputes the trailing 120 complete UTC
days nightly at 05:40 UTC on GPU 0, with its own full-catalogue control. It writes
`orbit-drift-<hash>.json` plus a separate manifest fragment; the small merge in
`orbit_release.publish` carries `orbitDrift` into the existing publish cycle.
Object cards and the inference chapter consume that same artifact and label gate;
`--oh-drift` has its own legend entry and literal fallback. Step history can be
unavailable while the drift card still renders. No new routes or sweep changes.

**Measured shipped window: gate closed/unmeasurable.** For 2026-05-15 to 2026-09-12
exclusive, all 68,657 objects have insufficient coverage; passive 0/0, payload 0/0,
upper bound and separation unmeasurable. All propulsion flags are suppressed.
The 2024 10.88× result is not inherited. Full design, artifact hash, isolated-run
receipt, lifecycle and unproven items: [orbit-drift.md](orbit-drift.md).
No deployment or timer installation/start; `orbit-release.timer` remains active.

## 2026-09-11 — resumable release tail (source change; not deployed)

The sweep's end cursor now hands off to a checkpointed tail: cohort batches,
event-card batches, shard-local series reads and writes, drag calculations,
artifact verification, then the atomic manifest fragment. Version 4 in-flight
sweeps migrate to version 5 without losing their pass or cursor. The systemd
timeout remains 9000 seconds. See [design, fixture evidence and operating
limits](orbit-tail-resumption.md).

## 2026-09-08 — four bounds that were computed and not applied

Five defects fixed in one pass. They are not five unrelated bugs: four of them
are the same shape, and that shape is worth naming because it will recur.

**The shape: a bound that is computed, published, and not applied.** Something
measures a limit correctly, writes it into the artifact, and then the code that
should refuse to cross it never reads it. Nothing errors. The number is right on
the page and wrong in the decision.

### 1. The 2V ceiling reached readers

`delta_v()` has flagged a physically impossible cost since 2026-09-03: no
impulse can change a bound orbit by more than twice the speed at perigee, that
being the cost of reversing the velocity outright. The cohort lane and the
thrust lane both dropped an interval that breached it. **The self-history lane
computed the same field and never looked at it** — and that is the lane that
judges roughly 11,739 of the published events against the cohort lane's ~12.

Measured on the live 4 September artifact before the fix: five of 1,500 events
cost more than twice their own perigee speed, and because `summaries` sorts by
descending Δv, **the top five rows of the page were all physically impossible** —
MOHAMMED VI-B at 49,317 m/s across its object row, 22,252 m/s in its single
worst event against a 15,077 m/s ceiling.

**Rule: a physical bound belongs at every call site that prices a change, or in
`delta_v` itself. If you add a gate to one lane, grep for the other callers in
the same commit.** The drop is now counted and reported on stderr; a bound that
removes data owes the reader a number.

### 2. Significance was standing in for separation

The acceptance criterion for the word *manoeuvre* has always had two halves: the
false-alarm upper bound below 1 per 1,000, and the payload rate still clear of
the passive floor — the second half being what stops the target from being met
by a detector tightened until it flags nothing.

The second half was encoded as a pooled two-proportion z at p < 0.01. **That is
not the same question.** Against 89.1 M passive and 62.5 M payload intervals the
pooled z is about 459, and the same test stays significant for a rate ratio of
**1.001**. It measures the size of the archive, not the quality of the detector.

Now required as an effect size: the Jeffreys *lower* bound on the payload rate
must stand 10× clear of the Jeffreys *upper* bound on the passive rate — bound
against bound, for the same reason the false-alarm half uses a bound. If
flag-producing noise acts on both classes, the share of payload flags it can
account for is at most passive/payload; 10× holds that share under one in ten.

**The threshold was not fitted to the data.** On the current bundle the ratio is
**2.161 and fails**. A threshold chosen to make today's numbers pass would have
been about 2×, and a coin flip is not what a reader is owed by a claim about one
specific event. Enforced at the producer (`orbit_campaigns.control_rates_by_object`)
as well as the release layer, so the requirement lives where the control is
computed.

### 3. `controlBasis` was published and read by nothing

Two detectors with different blanks and different κ both rendered "the detector
flagged N of M", and the reader could not tell whose false-alarm rate was being
quoted. The field naming the lane was published on every event and declared
three times in the UI types, with zero readers. The card now names the detector,
and falls back to a generic phrase rather than guessing when a record carries no
basis.

### 4. The UI failed open where the pipeline failed closed

The pipeline allowed the manoeuvre vocabulary to an **allowlist** of one type
(PAYLOAD). The UI denied a **denylist** of two (DEBRIS, ROCKET BODY). Space-Track
also publishes UNKNOWN, TBA and OTHER; all three fell through and were drawn as
manoeuvre-capable.

**Rule: when two sides of a boundary encode the same policy, they must encode it
the same way round. An allowlist on one side and a denylist on the other is a
guarantee that they will diverge the first time the vocabulary grows.**

### 5. Not a bound — an overclaim, in three places

The inference chapter said a flag on a spent stage is a false alarm "with
certainty" and "by construction"; the discovery page said such a signature is
"wrong by construction". A fragment genuinely cannot burn — but that a given
object *is* a fragment is the **catalogue** talking, and an entry can be wrong or
out of date. The refusal is unchanged and still absolute; only its warrant is
now stated honestly.

The test suite pinned the phrase "wrong by construction", so it would have
passed forever on the overclaim. It now asserts the claim, the hedge, **and the
absence of the old phrase**.

### What to check before shipping a change to this subsystem

- Every field the pipeline publishes: does anything read it? A published field
  with no reader is either a missing feature or dead weight; decide which.
- Every bound the pipeline computes: does every call site apply it?
- Every policy encoded twice: are both sides the same way round?
- Every claim in reader-facing prose: is it warranted by evidence, or by a
  catalogue lookup being described as a law of nature?
- Every acceptance criterion: is each half actually encoded, and does the
  encoding ask the same question the criterion asks?

## 2026-09-04 — detector completion (supersedes the calibration claims below)

The immutable measurement snapshot contains 216,116,471 directly counted
element sets across 68,573 objects; the maintained summary row still reported
182,461,955, so the direct count is the archive-size authority for this run.
The latest completed capture was `2026-09-04T11:21:07.133000+00:00`, while the
forward-most fitted element epoch was `2026-09-10T03:47:38.554000+00:00`.

The cohort window now ends at the newest completed archive capture, not at the
largest element epoch. The latter can be several days in the future, and had
silently reduced a nominal seven-day control to roughly seven hours. The fresh
window is `2026-08-28T11:21:07Z` through `2026-09-04T11:21:07Z`:
360,886 usable intervals, including 98,707 passive controls. It flags 2,314
passive intervals (Jeffreys upper bound 0.02440) and 10,501 of 248,728 payload
intervals (`z = 26.481`), so its own label gate remains closed. The balanced
production path took 4,724.7 seconds.
Production uses exactly two fork workers,
several ordered chunks, and preserves input order; small calls and platforms
without `fork` remain sequential. A redundant serial timing run was stopped
after 1 hour 55 minutes when another bounded site build began on bigmem. A
contiguous two-worker full-archive reference then reached its 90-minute limit;
exact serial/parallel event order remains covered in the focused suite.

Self-history now requires every tripped channel to survive a full two observed
days. A channel with only a short follow-up is declined, and one persistent
channel can no longer carry a transient channel into the event's signature or
Delta-v. The complete passive control selected `κ = 32` for those self-history
steps while the separately controlled cohort remains at `κ = 8`. The
fixture-proven but live-unproven thrust-excess lane stays pinned to its original
`κ = 8`; calibrating the step detector does not silently tune it. The
self-history ascending-node implementation uses only the residual after
predicted J2 drift, only at least one degree from either equatorial singularity,
and a 1.5-times channel threshold. The complete experimental control still
produced 63,190 passive node trips, so the predeclared acceptance rule keeps the
self-history node lane explicitly disabled. The independently controlled cohort
node screen remains enabled. Argument of perigee remains disabled and mean
anomaly remains excluded. On the full immutable archive snapshot, the accepted
four-worker self-history sweep scanned all 68,573 objects (61,154 with a usable
baseline) in 2,704.1 seconds. The parent reported 523.9 MB peak resident memory;
the complete transient unit, including its workers, peaked at 10.2 GiB. It measured
39,908 passive flags in 89,124,529 intervals, rate 0.00044778 and Jeffreys 95%
`[0.00044340, 0.00045219]`; payloads measured 190,056 flags in 62,535,308
intervals, rate 0.00303918 and Jeffreys 95%
`[0.00302556, 0.00305284]` (`z = 403.734`, approximate `p = 0`, rate ratio
6.787). The accepted rerun retained 89,241 events and 7,934 summaries for the
8,000-object catalogue and contains no self-history node events.

The operating point came from a predeclared curve rather than from trying one
value until the gate happened to open. On 2,000 deterministically spaced
objects, `κ = 24` technically passed with a passive Jeffreys upper bound of
0.0009078, only 9.2% below the limit. `κ = 32` lowered the sample upper bound
to 0.0004642 while retaining 9,527 payload flags and `z = 104.828`. On the
separate operator-published positive-control curve it still found 18 events,
one fewer than at `κ = 8`. The accepted complete sweep's current
coverage-aware table contains 34 published events: 18 of 27 scorable events
detected, 9 missed and 7 pending. The sample selected the candidate; the full
archive control above is the acceptance result.

The current focused detector suite passes all 180 Python tests. The current
frontend suite passes 116 files / 2,249 tests, and the TypeScript project check
passes. Full Python discovery ran 1,808 tests with 7 skips: 19 failures were
unrelated live catalogue, mirror, or curated-override coverage drift, while the
remaining reachability failure reproduced in a clean status-empty baseline
worktree.

The label gate is detector-specific. A payload event may use *manoeuvre* only
when the passive control for the lane that judged that event has an upper bound
strictly below 1 per 1,000 and the payload excess is significant. Cohort and
self-history events cannot borrow one another's calibration; debris and rocket
bodies can never receive manoeuvre wording. The top-level policy bit remains a
conservative compatibility value and is true only when both lanes pass, while
new records carry `controlBasis` and `manoeuvreLabelPermitted` themselves. The
browser shows both blanks and both payload separations rather than averaging
two different instruments into one tidy number.

The deterministic evidence card now follows that same per-event policy. A
permitted payload is described as a manoeuvre inferred from public elements,
while its cause and Delta-v remain explicitly inferential and lower-bound; an
unpermitted event remains a candidate; a passive-object flag says plainly that
it is a false alarm by construction. `node-change` and `thrust-excess` have
semantic colours, the Starlink and OneWeb expectation rows name
`thrust-excess` directly, and the compatibility synonym has been removed. The
thrust-excess detector itself was deliberately not tuned: the archive still
contains no live positive campaign on which tuning could be justified.

**Written:** 2026-08-07. **Revised the same night**, after a 2004–2025 back-fill
landed 15.5 million element sets in the archive and broke three of this
document's assumptions at once. Sections marked **REVISED** supersede what they
replace; the rest still stands.

**Historical status at the 2026-08-07 writing:** pipeline, artifacts, narrative
lane and browser module were built and tested (315 Python tests, 21 browser
tests), while `src/main.ts` and `index.html` still needed the patches in §3.
That wiring was subsequently completed; the 2026-09-04 section above is the
current status.

---

## 0. REVISED — what the back-fill changed, and the outage it caused

The archive was hours old when everything below §1 was designed, and every
design decision in it was correct *for that archive*. Then
`pipeline/orbit_history_backfill.py` imported the whole of 2024 — **15,423,857
element sets across 29,215 objects** — and three things followed.

**It took the live site down for four hours, and that is the most important
thing in this document.** `orbit_release.publish()` ran inside the five-minute
publish cycle and scanned the whole archive on every one. `load_intervals`
materialises one Python object per consecutive pair of element sets; at a few
thousand element sets that cost 1.6 s, and at 15.5 million it cost **9.3 GB
resident and over five minutes**. `space-explorer-data.service` hit its 240 s
`TimeoutStartSec`, was SIGKILLed, and every subsequent cycle died the same way,
so the site served four-hour-old data for every layer, not just this one.

The lesson is not "the archive got big", because it will get bigger:

> **A job whose cost scales with the whole history must not run on a timer whose
> period is set by how often the newest data arrives.**

Element sets arrive hourly. Manoeuvre history therefore changes hourly at most,
and recomputing twenty-two years of it twelve times an hour was waste even while
it was still affordable. So:

| | Before | After |
|---|---|---|
| Where the archive is scanned | inside the five-minute publish cycle | `orbit-release.timer`, hourly |
| Publish-cycle wall clock | **> 5 min, SIGKILLed at 240 s** | **58.5 s, exit 0** |
| Publish-cycle peak RSS | **9.3 GB** | **317 MB** |
| What the publish cycle does with the archive | scans it | never opens it |

`publish()` now reads `pipeline/.cache/orbit-manifest.json` — paths and digests
only, no bundle contents — verifies every artifact it names is still on disk,
and returns the manifest fragment. If the fragment is missing, stale or names a
file `prune_data.py` has since removed, it *raises*, which runs
`build_release.py`'s existing degrade path and preserves the previous manifest
records. **`build_release.py` needed no change at all**, which was the point:
several agents are in that file.

A unit test replaces `orbit_release.open_archive` with something that fails the
test if it is called, then asserts the publish still succeeds. The regression
cannot come back quietly.

**There is a kill switch, and clearing it is a human decision.**
`SPACE_EXPLORER_DISABLE_ORBIT_HISTORY=1` was set on
`space-explorer-data.service` during the incident, and it is still set. Its own
comment in `build_release.py` says *"Remove once the heavy work runs on its own
timer and streams the archive instead of loading it."* **That condition is now
met** — but re-enabling a layer that took the site down is not something a
future agent should do silently. It is one command:

```bash
sudo systemctl revert space-explorer-data.service   # or edit the Environment= line
sudo systemctl daemon-reload
```

While it is set, the publish cycle prints `orbit history disabled by
SPACE_EXPLORER_DISABLE_ORBIT_HISTORY=1` and preserves whatever was published
before, which is the correct place to sit.

**One asymmetry in that degrade path was worth fixing.** `build_release.py`
preserves `orbitEvents` and `orbitDrag` with `prior_artifact_record` and
explicitly skips `orbitHistory`, because a 256-shard record is not a
`path`+`sha256` and that helper cannot see inside it. The shards were still on
disk and still correct; the manifest simply stopped naming them, and every plot
vanished for the cycle. `orbit_release.previous_records()` now supplies them, so
the fix lives in this module rather than in the file several agents are in.

**Second: the heavy pass is now streaming.** `pipeline/orbit_campaigns.py` walks
`element_set` in primary-key order — which is `(norad, epoch_ms)`, so the scan
arrives already grouped by object — and holds one object at a time. Measured
over the whole archive: **53 MB resident**, against 9.3 GB for the pass it
replaces. It is also the only shape in which the longitudinal questions can be
answered at all, because a cadence needs one object over many months.

**Third: two detectors now, not one.** They answer different questions and
neither subsumes the other:

* the **cohort** detector (`orbit_events.py`) judges an object against its
  neighbours at the same altitude and inclination *at the same moment*. It works
  on an object's first day and is the only thing that covers a new launch. It
  now runs over a **seven-day window** rather than the whole archive, which
  loses it nothing — a cohort is a statement about one moment.
* the **self-history** detector (`orbit_campaigns.py`) judges an object against
  what that object normally does. It needs history and it is what Sean's
  questions actually require.

Where both see the same interval the self-history one wins, because its
expectation was measured from this object rather than from its neighbours, so
its residual — and therefore its Δv — is the better number.

Companion to `docs/orbit-history-design.md`, which specifies the archive and the
first-generation detectors. That document is still the authority on storage,
retention and the measured noise floor. This one covers what sits on top: what
*kind* of change an event is, what it cost, what is ordinary for the object, and
how a visitor is told.

---

## 1. Files added

| File | What it is |
|---|---|
| `pipeline/orbit_events.py` | Deterministic classification, Δv, cohort screen, expectations, controls |
| `pipeline/orbit_narrative.py` | Deterministic evidence card, and the gate on the model's prose |
| `pipeline/orbit_release.py` | The three published artifacts |
| `pipeline/enrich_orbit_events.py` | The local-model lane, on the `enrich_qwen.py` contract |
| `data/orbit_manoeuvre_expectations.json` | What is ordinary per object class, derived or cited |
| `data/orbit_manoeuvre_truth.json` | Operator-published manoeuvres — the positive control |
| `src/orbit-history.ts` | Types, selection, plot geometry. No DOM, so it is testable |
| `src/orbit-history-browser.ts` | The browser itself; `mountOrbitHistoryBrowser(host, options)` |
| `src/orbit-history.css` | Its styles, kept out of `styles.css` which another agent owns |
| `tests/test_orbit_events.py` | 63 tests, no network |
| `tests/orbit-history.test.ts` | 21 tests |
| **`pipeline/orbit_campaigns.py`** | **REVISED §0.** The self-history detector, the streaming whole-archive pass, cadence, repeat clusters, unusual-for-itself, decay trend, coverage-aware ground-truth scoring, backfill-aware maturity, and the read-only archive opener |
| **`tests/test_orbit_campaigns.py`** | **38 tests, no network**, including one that fails if `publish()` ever opens the archive again |
| **`deploy/systemd/orbit-release.{service,timer}`** | The hourly job that does the expensive half |

**One existing file changed**, minimally and additively: `pipeline/build_release.py`
gains a single 14-line block immediately before `manifest_bytes = canonical_json(manifest)`.
It imports `pipeline.orbit_release` inside the `try`, so a missing archive, a
mid-roll archive, or running on a machine without `/mnt/d` cannot stop a publish
cycle — the same degrade-don't-die posture `drap` and `aurora` already use, and
the inconsistency `docs/OPEN-WORK.md` §1.3 complains about in GloTEC.

Nothing else in `build_release.py` was touched.

---

## 2. Artifacts

| Manifest key | Prefix | Size today (gzip) |
|---|---|---|
| `orbitHistory` | `orbit-history-NNN` | 256 shards, 402 KB total, largest 2.1 KB |
| `orbitEvents` | `orbit-events` | 40 KB |
| `orbitDrag` | `orbit-drag` | 2.8 KB |

Those were the sizes on an archive hours old. **Measured on a year of archive:**

| Manifest key | Content | Size |
|---|---|---|
| `orbitHistory` | 256 shards, 8,242 objects, decimated series **plus the full event record for each object** | **72 MB gzipped total, ~280 KB per shard** — and a visitor fetches exactly one |
| `orbitEvents` | 1,500 headline rows, 4,724 per-object summary rows, controls, ground truth, maturity | **~1 MB gzipped** |
| `orbitDrag` | 16 shells, Kp, density, method | 48 KB |

**CORRECTED 2026-08-09, measured on the release actually on disk** (`20260809T044819Z`,
9,055 objects, 6,644 summary rows). The two figures above are both low, and the shard
figure is low by five times:

| Manifest key | Measured | Was claimed |
|---|---|---|
| `orbitEvents` | 21.3 MB raw, **2.4 MB gzipped** | ~1 MB gzipped |
| `orbitHistory` shard 0 | 12.1 MB raw, **1.4 MB gzipped** (41 objects, 42,529 samples) | ~280 KB |

So opening the browser and then opening one object costs about **3.8 MB on the wire**,
against 1.71 MB for a whole cold visit to the site. That is still the right side of the
button and the wiring spends it exactly once, but it is not "the same order as the
satellite catalogue" — it is more than twice a whole visit, and it will grow as the
back-fill fills in. If it needs to come down, the lever is the events bundle: the
population table needs every one of the 6,644 `objects` rows it sorts, but the 1,500
headline `events` rows travel with them and are only ever read as a fallback for an
object whose shard is missing. Splitting those into a second artifact is a pipeline
change, not a frontend one.

Two things follow, and both are wired:

* **The events bundle is fetched when the dialog opens, not at manifest load.**
  1 MB is the same order as the entire satellite catalogue and must not be spent
  on every visitor for a feature behind a button. §3.2 has the patch. Most of it
  is the 4,724 per-object rows, which is the honest cost of a *sortable*
  population view: it sorts what it holds.
* **A shard changes only when its data changes.** The plot grid is anchored to
  absolute time (`epoch // grid`), not to "twelve hours since the last sample I
  kept". The running form makes the retained series depend on where the walk
  started, so one element set arriving an hour early reshuffles everything after
  it, all 256 shards get new content-addressed filenames every cycle, and 72 MB
  an hour is written and shipped for data that did not change. That is the
  self-invalidating cache key `docs/OPEN-WORK.md` lists as one of this
  codebase's four defect classes, and it was live here until it was measured.

`python3 -m pipeline.orbit_release --dry-run` reports current sizes and peak
resident memory without writing anything.

`orbitHistory` is a list of shard records rather than a single `path`+`sha256`.
Both deploy scripts discovered records **only at the top level**, and the two
resulting failures were asymmetric and both bad: `publish_data.py` would have
staged none of the 256 shards, which surfaces as a 404 in a visitor's browser
rather than as an error in the pipeline; and `prune_data.py` would have treated
every live shard as unreferenced and deleted it out from under the site.

Both now walk one level into any list of records that carries the same
`path`+`sha256` contract — a small additive change to each, general rather than
special-cased on `orbitHistory`, so a future layer that shards works for free.
Covered by two new tests in `tests/test_publish_data.py`, including that a
genuine orphan is still pruned.

A shard carries **no `generatedAt` and no `coverage`**. Artifacts are
content-addressed, so any field that changes when the data has not would mint
256 new files every five-minute publish cycle — about 150,000 files a day, all
identical in substance. Shard hashes are asserted stable across two consecutive
runs on unchanged input. Coverage and generation time live once, in the events
bundle, which the browser loads before it asks for any shard.

---

## 3. The two patches

> **APPLIED 2026-08-09**, and the patches below were not sufficient. Wiring them
> as written produced a browser that loaded, rendered and lied, because the
> events bundle the pipeline publishes is not the shape `src/orbit-history.ts`
> declared. Four mismatches, all verified against the artifact on disk before
> anything was changed:
>
> 1. **`maturity.observationSpanDays` does not exist in any published bundle.**
>    `pipeline/orbit_campaigns.py` — the code that actually publishes — emits
>    `longestSingleObjectDays` / `captureLedgerDays`; the declared name comes
>    from `pipeline/orbit_events.py:archive_maturity()`, a path that no longer
>    reaches the artifact. The status tile read "Archive watching for —", and
>    worse, the `undefined` was the seed of a `Math.max` reduce inside
>    `selectPopulation`, so `longestObserved` was `NaN`, every `NaN < requirement`
>    was false, and **the maturity gate was switched off entirely** — silently,
>    in the direction of answering questions the archive could not answer.
>    Now read through `archiveSpanDays()`, which prefers
>    `longestSingleObjectDays` per OPEN-WORK §0's rule that the capture ledger
>    stopped being a maturity measure when the back-fill landed.
> 2. **`groundTruth.inArchiveWindow` does not exist either** — it is `scorable`.
>    The tile read "none in window" permanently; it now reads 15 / 21. Read
>    through `scorableBurns()`.
> 3. **`bundle.events` is not `OrbitEventRecord[]`.** `_slim()` in
>    `pipeline/orbit_release.py` strips `card`, `deltaV`, `drag`,
>    `spaceWeather`, `expectation` and `tests` before publishing the headline
>    list. `renderEvidenceCard` dereferences all of them, so the fallback path
>    for an object with no published shard would have thrown inside the dialog.
>    There is now an `OrbitHeadlineEvent` type and a `renderHeadlineCard` that
>    renders what a headline event actually carries, and says what it is missing.
> 4. **`shardCount` was read off the bundle**, which has never carried one, so
>    the hard-coded 256 fallback was doing all the work and was right only by
>    coincidence. It now arrives through `OrbitHistoryBrowserOptions.shardCount`
>    from `manifest.orbitHistory.shardCount`.
>
> None of the four had a test over it, because there was no DOM test for
> `orbit-history-browser.ts` — `tests/orbit-history.test.ts` covers the data
> layer only. That gap is the reason all four survived.
>
> **CLOSED 2026-09-03** by `tests/orbit-history-browser.test.ts`, 19 tests under
> jsdom. It mounts the real module against `tests/fixtures/orbit-history-live.json`,
> trimmed out of the bundle and shard the live site was serving — real key names,
> real values, six real objects — rather than against the types, because a test
> written to `src/orbit-history.ts`'s interfaces could not have caught any of the
> four: the interfaces were the thing that was wrong.
>
> Mutation-tested rather than assumed. Restoring the exact wiring above —
> reading `observationSpanDays`, and dropping the finite check on the `Math.max`
> seed — fails three of the nineteen: the status tile stops carrying the
> `longestSingleObjectDays` figure the artifact publishes, and a 21-day view
> renders a table on a young archive instead of saying which day it starts
> working. Mismatch 3 is held by a fixture object whose shard events are cut
> back to the pre-2026-08-09 marker keys, so the `_slim()`ed headline fallback
> is exercised for real rather than simulated; mismatch 4 by mounting with no
> `shardCount` at all.
>
> One caution for anyone extending it. The `undefined`/`NaN` sweep over the
> rendered subtree must NOT use word boundaries. `textContent` concatenates
> siblings with nothing between them, so a dt/dd pair reads "Perigee
> nowundefined km" and `\bundefined\b` does not match it — written that way the
> sweep sat green through a deliberately planted missing field, which is exactly
> what it exists to catch.

### 3.1 `index.html`

Add a button inside the satellite card, next to the existing ground-track
button at line ~164:

```html
<button class="ground-track-open" id="orbit-history-open">Open orbit history →</button>
```

And a dialog beside the `ground-track-dialog` block at line ~386, following the
same structure exactly:

```html
<dialog class="site-dialog orbit-history-dialog" id="orbit-history-dialog"
        aria-labelledby="orbit-history-title">
  <form method="dialog">
    <button class="dialog-close" value="close" aria-label="Close orbit history">×</button>
    <p class="dialog-kicker">ORBITAL HISTORY · INFERRED FROM PUBLIC ELEMENTS</p>
    <h1 id="orbit-history-title">How this orbit has changed</h1>
    <p class="dialog-lead" id="orbit-history-lead">
      Element sets archived on this machine, the changes that cleared the catalogue's
      own fit noise, and what each would have cost.
    </p>
    <div id="orbit-history-host"></div>
    <p class="dialog-caveat">
      These are fitted mean elements published every few hours, not measurements of where
      a satellite is. What we can see is how the fit moved. Nothing here is a report of
      what an operator did.
    </p>
    <div class="dialog-actions"><button value="close" class="primary-button">Back to the globe</button></div>
  </form>
</dialog>
```

### 3.2 `src/main.ts`

Import beside the existing `mountGroundTrackMap` import (line ~17):

```ts
import { mountOrbitHistoryBrowser } from "./orbit-history-browser";
import type { OrbitEventsBundle, OrbitHistoryShard } from "./orbit-history";
```

A field on the explorer class, beside the other bundles:

```ts
private orbitEvents: OrbitEventsBundle | null = null;
```

Load it wherever the other manifest-driven bundles are loaded. It is optional:
the manifest key is absent whenever the archive was unavailable, and the button
should simply not appear.

**REVISED — load it when the dialog opens, not when the page does.** The bundle
is about **1 MB gzipped** on a year of archive (897 KB of per-object rows for
4,724 objects, plus the headline event list), because a sortable population view
genuinely needs every row it sorts. That is the same order as the entire
satellite catalogue, and it must not be spent on every visitor for a feature
behind a button. The manifest key alone decides whether the button appears; the
bytes are fetched on first open and cached.

```ts
// Manifest only — no fetch. The key is absent whenever the archive was
// unavailable, and then the button simply never appears.
byId("orbit-history-open").hidden = !manifest.orbitEvents;
```

A handler beside `openGroundTrackMap` (registered near line ~690):

```ts
byId("orbit-history-open").addEventListener("click", () => void this.openOrbitHistory());

private async openOrbitHistory(): Promise<void> {
  const satellite = this.selectedSatellite;
  const record = this.manifest.orbitEvents;
  if (!satellite || !record) return;
  // Fetched here rather than at manifest load: about 1 MB gzipped, for a
  // feature behind a button.
  this.orbitEvents ??= await this.loadArtifact<OrbitEventsBundle>(record.path);
  const shards = this.manifest.orbitHistory?.shards ?? [];
  mountOrbitHistoryBrowser(byId("orbit-history-host"), {
    bundle: this.orbitEvents,
    initialNorad: satellite.id,
    // The manifest owns the content-addressed paths; the browser never guesses one.
    loadShard: async (index) => {
      const record = shards.find((entry) => entry.shard === index);
      if (!record) return null;
      return this.loadArtifact<OrbitHistoryShard>(record.path);
    },
    onSelect: (norad) => this.selectSatelliteById(norad),
  });
  byId<HTMLDialogElement>("orbit-history-dialog").showModal();
}
```

`loadArtifact` is whatever the class already uses to fetch a manifest-referenced
JSON artifact; the browser deliberately takes a callback rather than fetching,
so `main.ts` keeps ownership of caching and of `ArtifactRefreshController`.

### 3.3 `deploy/systemd`

Two units, neither urgent, both additive:

```ini
# orbit-narrative.timer -- OnCalendar=*-*-* 05:15:00
ExecStart=/usr/bin/python3 -m pipeline.enrich_orbit_events --max-events 12
```

Once a day is right. Writing one narrative costs tens of seconds of local GPU on
the same server Bob answers from, the events do not change minute to minute, and
`enrich_orbit_events` already skips any event whose cached narrative still
validates. It honours the shared `qwen-endpoint-unreachable` marker, so a lane
that finds the endpoint down stops the other lane knocking too.

The roll and capture units are `docs/orbit-history-design.md` §7.1 and §7.2 and
are the sibling agent's to wire.

---

## 4a. REVISED — what a visitor sees now that the archive holds a year

Everything in §4 below was written against an archive that had been watching for
under an hour, and it is kept because the reasoning is still right for a young
archive and will be right again for any new machine this is stood up on. What
follows supersedes its table.

The archive now holds **the whole of 2024 — 15,423,857 element sets across
29,215 objects — plus live hourly capture from 2026-08-07**, with a real hole
between the two. Earlier years are still importing.

| View | §4 said | Now |
|---|---|---|
| Biggest Δv spenders | works | works, over a year and a population |
| Deorbiting | works | works, with a measured rate per object and an upper bound on time left |
| Unusual for its class | works | works, **plus** unusual *for the object itself*, which no class file can encode |
| Corrected most often | refuses, needs a week | **works.** A measured cadence: median days between corrections, its spread, and corrections per year |
| Same correction repeatedly | refuses, needs three weeks | **works.** Repeat clusters: same signature, cost inside a tolerance band, with their own spacing |
| Per-object plots | two points and a line | a year of twelve-hourly points, undecimated around each marked change |
| Storm density enhancement | refuses | still refuses on the live window; the 2024 window can support it once the quiet/disturbed split is chosen from Kp rather than from the midpoint |
| Manoeuvre *labels* | withheld | **still withheld.** See §5a |

The refusals that remain are still designed states with a reason and a "needs
N days", and they are now decided **per object** rather than from the archive-wide
capture ledger. That distinction was live and wrong: the ledger read a few hours
while the archive held a year, so every longitudinal view was switched off in
front of the data that answers it.

## 4. What a visitor sees today, and what changes as the archive fills

The archive has been **watching for under an hour** — five captures, 32,260
element sets, 543 usable consecutive pairs across 563 objects, and **not one
object with more than two element sets.**

That last fact is the one that shapes the whole design. The detectors in
`orbit_history.py` need eight or more intervals *for a single object* before
they will say anything, so on this archive they return nothing at all, today and
for several more days. The browser is built on a **cohort** statistic instead:
compare an object against others at the same perigee altitude and inclination
over the same hours. That needs many objects at one moment rather than one
object over many months, which is exactly what an hours-old archive holds. It is
why there is something real to look at on day one.

| View | Today | In a month |
|---|---|---|
| Biggest Δv spenders | **Works.** One pair of element sets already gives a cost | Same, over a real population |
| Deorbiting | **Works** | Same, with rates instead of single differences |
| Unusual for its class | **Works.** The comparison is against a published expectation, not against history | Same, plus per-object history |
| Corrected most often | **Refuses**, and says it needs about a week | Works |
| Same correction repeatedly | **Refuses**, and says it needs about three weeks — geostationary east-west cycles run one to four weeks | Works |
| Per-object plots | Two points and a line | Weeks of daily samples with marked events |
| Storm density enhancement | **Refuses**: needs a quiet window and a disturbed window inside the same archive | Works on the first real storm |
| Manoeuvre *labels* | **Withheld** — see §5 | Withheld until the control says otherwise |

Every refusal is a designed state with an explicit reason and an explicit "needs
N days", drawn from `archive_maturity()`. `selectPopulation` returns the reason
rather than an empty list, and the browser renders it as a panel. **Nothing here
should ever look broken; it should look like it is telling you what it does not
yet know.**

---

## 5a. REVISED — the false-alarm rate, now measured on four and a half million control intervals

§5 measured the cohort detector on 148 control intervals and could not separate
payloads from debris: z = 1.76, p ≈ 0.08, intervals overlapping. The archive now
supports a measurement four orders of magnitude larger, on the self-history
detector, over the whole of 2024 plus live capture.

**One streaming pass, 15 min 29 s wall clock, 137.8 MB peak resident**, over
37,279 objects, 28,647 of which had enough of their own history for a baseline.

| Population | Objects | Intervals | Flags | Rate per 1,000 | Jeffreys 95% | Flags per object-year |
|---|---|---|---|---|---|---|
| **Cannot manoeuvre** (debris, spent stages) | 11,615 | 4,517,562 | 9,420 | **2.09** | 2.04 – 2.13 | 1.09 |
| **Payloads** | 11,609 | 6,932,474 | 74,623 | **10.76** | 10.69 – 10.84 | 7.66 |

**Payloads are flagged 5.16× more often than objects with no propulsion, and
this time the difference is not close: z = 168, p indistinguishable from zero.**
That is the statement §5 could not make. It is the difference between a detector
that might be working and one that demonstrably responds to something only
spacecraft with engines do.

**The label still does not ship.** `sufficientToLabel` is `false`, and the
blocking reason is now a number rather than an absence:

> the upper bound on the false-alarm rate is 2.1 per 1,000 intervals, above the
> design target of 1 per 1,000

The design target in `docs/orbit-history-design.md` §3.7 is ≤ 1 per 1,000. We are
at 2.09 with a 95% upper bound of 2.13 — a factor of two away, not the factor of
forty-three §5 recorded. Every event still carries `confidence="candidate"`, the
browser still appends "(candidate)", and the evidence card quotes **the control
that judged that event** rather than whichever control was handy.

### How the rate came down, and what it was not

From 13.9 per 1,000 to 2.09, on the same 203,719-interval sample, **with κ fixed
at 8 throughout**. Nothing here is a threshold that was tuned until the answer
looked better; each step is a physical statement that turned out to be true.

| Change | Passive rate per 1,000 |
|---|---|
| Catalogue-wide noise floor, local-median baseline | 13.9 |
| **Noise floor measured from the object's own residuals** | 8.4 |
| **+ the change must still be there two days later** | 3.4 |
| **+ a change the previous element set moved the other way is a fit returning to trend** | 1.83 |

* **The catalogue's noise floor is a payload's noise floor.** It was measured on
  787 triples of the live catalogue. A tumbling fragment with a poor radar cross
  section is fitted far more loosely than that, and holding it to a payload's
  floor called 1.39% of its intervals manoeuvres. Each object's floor is now the
  robust scale of its own residuals, with the catalogue figure as a lower bound —
  so the change can only ever make the detector more conservative.
* **Propellant does not un-burn.** A manoeuvre moves the orbit and the orbit
  stays moved; a loose fit moves one element set and the next one puts it back.
  Accumulating the residual forward for two days and requiring half of it to
  survive is the single most effective thing in this module.
* **A loose fit produces two flags, not one** — the excursion and the return.
  The forward test rejects the excursion, because the return cancels it, and
  *accepts the return*, whose own step is followed by a level that stays put
  forever, since it is the trend the object was always on. The signature of a
  return is an immediately preceding residual of the opposite sign and comparable
  size. Propellant cannot produce that pattern: a burn is not preceded by an
  equal and opposite burn one element set earlier.

The honest cost of the persistence test: a change in the last two days of an
object's coverage, or immediately before a gap, has nothing after it to be
persistent *in*, and is declined rather than guessed at. A reboost on the
archive's final day is missed. That is the right way round — the alternative is a
detector whose newest and most eye-catching claims are its least tested.

### 5a.1 The positive control now scores

§5 recorded all 32 published manoeuvres as pending, every one predating the
archive. Five of them fall inside 2024.

| Object | Published | Type | Operator's Δv | Detected Δv | Ratio |
|---|---|---|---|---|---|
| ISS (ZARYA) | 2024-03-14 13:11 GMT | reboost | **1.58 m/s** | **1.71 m/s** | 1.08 |
| ISS (ZARYA) | 2024-04-26 | reboost | not published | 0.61 m/s | — |
| ISS (ZARYA) | 2024-05-24 | reboost (two burns) | not published | 1.30 m/s | — |
| ISS (ZARYA) | 2024-06-08 15:52 GMT | reboost | **1.00 m/s** | **1.11 m/s** | 1.11 |
| ISS (ZARYA) | 2024-11-19 03:24 GMT | debris avoidance | not published | 0.69 m/s | — |
| SENTINEL-2A | 2024-11-19 | debris avoidance | not published | **not detected** | — |
| SENTINEL-2B | 2024-12-25 | debris avoidance | not published | unscorable | — |

**Detection rate 5 of 6 scorable, 83%; 5 of 5 on the ISS.**

The 2024-04-26 and 2024-05-24 rows were added to
`data/orbit_manoeuvre_truth.json` *after* the detection run, from the titles of
NASA's own handbook documents, without looking at what the detector had found.
Both were already flagged. That is as close to a blind test as this feature can
manage, and it is worth more than the two Δv agreements: those confirm the
magnitude, this confirms the detector is not being fitted to its own answers.
Their Δv is `null` because the handbook PDFs are image-only and this machine has
no OCR — a plausible-looking number in the file whose entire job is to be the
truth would be the worst possible bug. The two ISS figures are the ones worth
dwelling on: NASA's numbers come from the SAMS accelerometers *on board the
station*, and ours come from mean elements fitted by somebody else. They agree
to **8% and 11%**, both high, both in the direction a lower-bound estimator
should err — the published figure is the burn, ours is the cheapest manoeuvre
consistent with the element change plus whatever drag the baseline did not
absorb.

The Sentinel-2A miss is honest and expected: a Sentinel-2 collision-avoidance
manoeuvre is centimetres per second, comfortably inside the fit noise of a
786 km orbit. The detector should miss it and does.

**Scorability is now decided per object**, against that object's own contiguous
observation runs, and that correction was forced by the back-fill.
`orbit_events.score_against_ground_truth` decides it from the archive's global
first and last epoch, which was right when the archive was one continuous run of
hours. The archive now holds 2024 and a few hours of 2026 with a nineteen-month
hole between, so a 2026-04 reboost sits inside the global window while the
archive holds nothing whatever near it. Scored globally it counts as a **miss**
and the detection rate falls because of a gap rather than because of the
detector. All 28 remaining entries are recorded as
`archive-holds-no-elements-here`.

## 5. The false-positive position, stated plainly

**No event is labelled a manoeuvre, and the browser says so at the top of the
panel before a visitor reads anything else.**

Measured on the live archive at κ = 8, counting only propulsive claims:

| | flags | intervals | rate | 95% interval |
|---|---|---|---|---|
| Objects that **cannot** manoeuvre (debris, spent stages) | 2 | 148 | 1.35 % | 0.28 – 4.26 % |
| Payloads | 17 | 374 | 4.55 % | 2.77 – 7.02 % |

The payload rate is 3.4× the control rate, and **that difference is not yet
statistically significant**: z = 1.76, p ≈ 0.08 on a pooled two-proportion test.
The intervals overlap. `labelPolicy.manoeuvreLabelPermitted` is therefore
`false`, the browser appends "(candidate)" to every signature, and the evidence
card carries the control numbers verbatim.

Two things about that table are worth stating rather than burying:

* The intervals are **Jeffreys**, not Wald. With two flags on a hundred and
  fifty intervals a point estimate means very little, and at zero flags Wald
  would return `[0, 0]` — a claim of a false-alarm rate of exactly zero from a
  control that cannot support it. That is the single most misleading number this
  module could publish, so the estimator that cannot produce it is the one used.
* The passive control **fell from 6 flags to 2 through physics, not through
  threshold tuning.** κ stayed at 8 throughout. What removed the four was
  removing natural perturbations that were being tested against zero — see §6.

The design target in `docs/orbit-history-design.md` §3.7 is ≤ 1 false positive
per 1,000 intervals. The current upper bound is 43 per 1,000. `sufficientToLabel`
additionally requires at least 200 control intervals, so the gate cannot open on
a lucky run of a thin control.

### The positive control

`data/orbit_manoeuvre_truth.json` holds **32 operator-published manoeuvres** —
20 ISS reboosts, debris-avoidance manoeuvres and deboosts with GMT ignition
times and Δv measured by the station's own accelerometers; the Aeolus assisted
re-entry burns; Terra's constellation exit; Meteosat-8's graveyard raise;
Sentinel and Swarm manoeuvre dates.

**All 32 are `pending`, and none is a miss.** Every one predates the archive,
and `score_against_ground_truth` records an event the archive cannot contain as
pending rather than as a failure — scoring those would be scoring the calendar,
and the number would improve on its own without the detector improving at all.

The table's value is that **it starts scoring by itself.** NASA has published
one PDF per ISS reboost since 2010 and does so roughly monthly; the next one
lands inside the archive window with nobody doing anything. When it does, the
site can say the one genuinely credible thing this feature is capable of: *this
change was detected from public orbital elements and independently reported by
the operator*, with the citation on the card. `renderEvidenceCard` already draws
that block when `groundTruth` is non-null.

Where a source publishes a date and no Δv — which is every Sentinel, Swarm,
Terra, Meteosat and ERS entry — **the Δv is null.** A plausible-looking number
in the file whose whole job is to be the truth would be the worst possible bug.

---

## 6. Four physics errors the live data caught

Recorded because `docs/OPEN-WORK.md` asks for defect classes, and because each
had a plausible first implementation that a test over synthetic data would have
passed.

**Testing an element against zero.** Luni-solar gravity tips a geostationary
orbit's plane by ~0.85°/yr, which is 0.0023°/day against a measured
geostationary inclination floor of 1.7e-4°. Tested against zero that is a
17σ event *every day on every geostationary object*, and the first run duly
reported north-south station-keeping on **INTELSAT 4-F1**, launched in 1971 and
dead for decades, and on the **apogee kick motor of METEOSAT 2**. Fixed with a
bound — `|di/dt| ≤ ω(i + i_pole)` by the triangle inequality — chosen over a
model because a bound cannot be got backwards and a model's sign convention can.

**Triaxial libration at GEO.** The same trap in semi-major axis. The Earth's
equatorial ellipticity accelerates an uncontrolled geostationary object in
longitude by up to 0.0018 °/day², which is **140 m/day of semi-major axis with
nobody burning anything** — 11σ against the 12.44 m geostationary floor, every
day. Six "east-west station-keeping" events at 141–180 m were natural drift.
A real east-west correction is a few cm/s, which is 1–3 **km** of semi-major
axis, so the bound loses nothing real: CHINASAT 16's 2,152 m step survives it.

**Comparing raw rates across unequal spacing.** The cohort statistic originally
compared per-day rates. An interval spanning twenty minutes turns a metre of fit
noise into kilometres per day, and a handful of those set the geostationary
cohort's robust scale to ~144 km/day — against which a real 2.7 km/day burn
scored z = 0.02 and was silently discarded. The screen had stopped working for
every object in the shell while still returning numbers. Now the cohort compares
**normalised deviations**, each object against its own natural floor, which is
dimensionless and spacing-independent.

**Billing an operator for a channel that never tripped.** The Δv total summed
residuals from all three elements including ones that had failed their own
significance test. METEOSAT 2's apogee kick motor was billed 0.11 m/s, of which
0.1115 came from an untripped inclination residual while the tangential part it
was actually flagged on was 0.005 m/s. Evidence and cost now come from the same
test.

A fifth, not a physics error but the same shape: **maturity was keyed on the
span of the epochs held rather than on the capture ledger.** After one hour of
capture the epoch span read as *seventeen days*, because one snapshot of the
catalogue already contains element sets days old and occasionally epochs stamped
in the future. The storm density estimator saw "seventeen days", ran a
twelve-thousand-object comparison of the archive against itself, and spent
**36 seconds of a 240-second publish budget** to produce a ratio of one. The
whole build now takes 1.6 s.

---

## 7. Known gaps

**Closed since this section was written:**

* The `build_release.py` → publish path **has now been run end-to-end**, in both
  states: with the fragment absent (degrades, prints the warning, preserves the
  previous manifest records, 58.5 s / 317 MB, exit 0) and with it present.
* **Cadence and station-keeping-regularity detection is implemented**, in
  `pipeline/orbit_campaigns.py`. `cadence_of()` gives median days between
  corrections, the robust spread of that spacing, a regularity figure that is
  `MAD / median`, and corrections per year; `repeat_clusters()` groups changes
  by signature and by cost inside a tolerance band. Both refuse below three
  corrections inside one run of coverage rather than dividing by a very small
  number, and neither ever measures a spacing across an archive gap.
* **The `measured-false-alarm-rate` capability was hard-wired `available:
  False`** — a branch that could never become true, which is one of the four
  defect classes `docs/OPEN-WORK.md` names. It is read from the control now.

**Still open:**

* **A continuously-thrusting satellite has no step to find, and this detector
  finds steps.** STARLINK-3005 gives 789 usable intervals over 349 days in its
  operational shell and **zero events**: its electric propulsion holds altitude
  by thrusting more or less all the time, so there is no discontinuity, and the
  self-history baseline correctly absorbs the maintained rate as "what this
  object normally does". The honest reading is that the detector reports what it
  can see, and for this class the visible thing is not a burn but a *decay rate
  that is too small for the altitude* — the object is not falling as fast as its
  ballistic coefficient says it should. That is a different statistic and it is
  not built. Until it is, an electric-propulsion satellite will show a clean
  plot and no events, and the interface should not let that read as "does
  nothing".

* **The offline build takes about twenty minutes and peaks at 1.65 GB.**
  Measured twice: 22 min 21 s / 1,456 MB, then 20 min 36 s / 1,652 MB on a
  busier machine. Fine for an hourly `Nice=15`, `IOSchedulingClass=idle` job,
  and five to six times better than the 9.3 GB it replaces — but **writing each
  shard as it is built and releasing it did not lower the peak**, which is worth
  recording because it was the obvious guess and it was wrong. The peak is
  reached *before* the shard loop, by `series` (8,242 objects of decimated
  samples, held as dicts) and `records` (40,871 events, each with its full
  evidence card). Streaming the writes still earns its place — without it those
  256 shards sit on top of that peak for the whole write loop — but the next
  real reduction has to come from `series`: samples as tuples rather than dicts,
  or a coarser grid. A shard cannot be written before every object has been
  read, because its members are spread across the whole primary-key range, so
  `series` genuinely has to exist whole.

* **The false-alarm rate is 2.09 per 1,000 against a target of 1 per 1,000**, so
  no event may be labelled a manoeuvre. The remaining factor of two is the real
  engineering target now, and the residuals that survive all three physical tests
  look like genuine element-set discontinuities — the catalogue re-fitting on a
  changed arc, which produces a step that persists and is not distinguishable
  from a burn in the elements alone. If that is what they are, no amount of work
  on the elements will remove them and the next gain has to come from somewhere
  else: a second source, or the class expectations, or the positive control.
* **The positive control has four scorable entries.** Three ISS events and one
  Sentinel-2A. Extending `data/orbit_manoeuvre_truth.json` with 2024-dated
  operator publications is now the highest-value hour anybody can spend on this
  feature: every entry added inside the back-filled year scores immediately,
  where every entry added for 2025 or 2026 sits unscorable until the back-fill
  reaches it or live capture catches up.
* **Only 2024 is imported.** 2004–2023 and 2025 are still running. Each year that
  lands multiplies the control and adds scorable ground truth.
* **Dst and F10.7 are not ingested.** `space_weather_gaps()` publishes what each
  would add rather than leaving them silently missing. F10.7 matters most: the
  ESA propellant guidelines show drag make-up at a fixed 786 km altitude moving
  by a factor of twenty across a solar cycle, and without F10.7 the quiet-time
  baseline drifts with the cycle and has to be re-derived by hand each year.
* **`CATALOGUE_NOISE_FLOOR` should be recomputed from the archive** after ~30
  days, per `docs/orbit-history-design.md` §6. Every floor in this module is
  built on it.
* **The `orbitDrag` shells are thin** — two shells met the 20-object minimum.
  This improves on its own.
