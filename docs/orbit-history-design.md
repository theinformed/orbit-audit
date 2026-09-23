# Orbital history: archive, detection, and browser

**Written:** 2026-08-07. **Status:** archive implemented and running; detection
implemented and unit-tested but *not calibrated*; browser designed, not built.

The feature Sean asked for: pick a satellite, see how its orbit has changed,
and work out *why* — drag, a burn, station-keeping — from the elements alone.

The urgent half is the archive. `ingest/spacetrack_ingest.py` pulls the full GP
set once an hour and overwrites `runtime/spacetrack-mirror/gp-active.json`.
Nothing was keeping the old one. Every hour that passed was an hour of orbital
history gone for good, and the *live* stream cannot be back-filled: our
published cadence is one GP query per hour and `gp_history` is limited to one
call per lifetime. So the archive was built and started first, before any of
the analysis it enables.

**Corrected 2026-08-07:** the archive as a whole *can* be back-filled, from a
route this document did not know about. space-track publishes the full history
as yearly zip bundles on a separate cloud share and its own documentation asks
callers to use those instead of the API for large date ranges. See
`docs/orbit-history-backfill.md`. One calendar year — 2024, 15.4 million
element sets across 29,215 objects — is imported, which is what made the
per-object detectors in `pipeline/orbit_campaigns.py` possible and what turned
the ground-truth table from entirely pending into something that scores. §5.3's
"We cannot check it against the real May 2024 elements" is likewise no longer
true.

Nothing in this work makes a network request. Every number below was measured
against files already on this disk.

---

## 0. What exists now

| | |
|---|---|
| `pipeline/orbit_history.py` | archive, detectors, cold-shard codec, retention. New file. |
| `tests/test_orbit_history.py` | 77 tests, no network, `python3 -m unittest` |
| `/mnt/d/space-orbit-history/orbit-history.sqlite3` | live archive |
| `/mnt/d/space-orbit-history/cold/` | monthly cold shards |

The archive has caught **two real consecutive hourly fetches** (2026-08-07
20:20Z and 22:22Z) and holds 32,260 element sets over 31,697 objects. The
second capture added 563 rows and rejected 31,128 duplicates without being
told which was which — which is the property that makes it safe to hang off a
timer.

**It only advances when someone runs it by hand.** Wiring it to the ingest
timer is one line and it is §7.1. Until that is done, the loss described at the
top of this document is still happening. Nothing else here is urgent.

Also not done, deliberately, and specified in §7: the `build_release.py`
integration and the browser itself.

---

## 1. Storage

### 1.1 What the upstream actually is

Measured on `runtime/spacetrack-mirror/gp-active.json`, 2026-08-07:

| | |
|---|---|
| file size | **36,007,802 bytes** (34.3 MiB); next hour, 36,000,940 |
| records | **31,697**; next hour, 31,691 |
| gzip -9 of the whole file | **4,720,815 bytes** |
| object types | 18,443 PAYLOAD, 9,881 DEBRIS, 2,199 ROCKET BODY, 1,174 UNKNOWN |

Naively keeping each hourly file:

* raw: 864 MB/day, **316 GB/year**
* gzipped: 113 MB/day, **41.3 GB/year**

Both are absurd, because **the overwhelming majority of each hourly file is the
same element sets we already had.** An object gets a new element set every few
hours, not every hour, so an hourly snapshot is mostly a re-send.

### 1.2 How much is actually new per hour

This was estimated first and then measured, and **the estimate was wrong by a
factor of four**. Both are recorded, because the way it was wrong is a trap
anyone reading this data will fall into.

**The estimate, and why it was wrong.** `GP_ID` is a global monotonic counter,
and across the snapshot it advances 1,884,463 over 391.57 h — 4,813/hour. Two
things make that useless as a rate for *our* query: the counter spans the whole
space-track GP universe including classes we never request, and, worse,
**`CREATION_DATE` is a file-generation stamp, not the publication of a new
element set.** Proof from the two snapshots: of the 4,965 records carrying the
creation batch stamped two hours before the second fetch, **4,426 (89%) held an
epoch the previous snapshot already had.** They were re-served, not re-fitted.
Counting creation batches counts re-serving.

**The measurement.** Two consecutive hourly captures, 2026-08-07 20:20:09Z and
22:22:06Z, 2.033 h apart, kept and diffed on `(NORAD_CAT_ID, EPOCH)`:

| | |
|---|---|
| records in each file | 31,697 → 31,691 |
| **new element sets** | **563** |
| distinct objects involved | 563 (exactly one new element set each) |
| objects that vanished | 6 |
| rate over that window | **277/hour** |

**But that window was quiet, and saying "277/hour" would be misleading.** The
element sets do not arrive smoothly. The epoch-age histogram of the second
snapshot, in one-hour bins:

| age | 0–3 h | 4–7 h | 8–11 h | 12–15 h | 16–19 h | 20–23 h |
|---|---|---|---|---|---|---|
| objects | **40** | **12,420** | 3,465 | 2,529 | 3,920 | 2,853 |

Almost nothing is newer than four hours old: 18 SDS fits in waves and there is a
roughly four-hour latency before a fitted epoch reaches the catalogue. The two
captures happened to straddle a trough.

**The number to design against is the 24-hour total: 25,227 objects carry an
epoch under 24 h old, so the archive gains ≈ 25,000 element sets per day, an
average of 1,051 per hour, delivered in bursts.** That is a slight
under-count — an object re-fitted twice in a day appears once — so it is a
measured lower bound, which is the safe direction for a storage estimate.

**A limitation of the cadence, not of the archive:** polling hourly and seeing
only each object's latest element set means a re-fit inside the same hour is
lost. Given the four-hour latency and roughly one element set per object per
day, this is small, but it is not zero and nothing can recover it without
exceeding the published GP rate — the one thing that would cost Sean a trip
through his chain of command. It is recorded rather than hidden.

### 1.3 The format

Three tiers. Everything on `/mnt/d` — the 3.7 TB spinning disk with 3.3 TB
free — never on the SSD, whose remaining 426 GB belongs to the model weights.

**Tier 1 — `element_set`, full fidelity, bounded window.** One SQLite table,
`WITHOUT ROWID`, primary key `(norad, epoch_ms)`. The clustering is the design:
an object's whole history is physically contiguous, so "plot this satellite over
time" is a single sequential read, while "sweep the population for a storm
signature" is one ordered scan. `sqlite3` is in the standard library, which
matters because this pipeline runs on system `python3` with no virtualenv and
no `pip`.

`PRAGMA journal_mode=TRUNCATE`, not WAL. `/mnt/d` is a **v9fs** mount and WAL
needs a shared-memory index that 9p does not coordinate reliably between
processes. Measured on this machine, the safe choice costs nothing:

| journal mode | 31,697 inserts | +4,400 rows | re-insert 31,697 dupes | full scan |
|---|---|---|---|---|
| wal | 0.24 s | 0.07 s | 0.03 s | 0.05 s |
| **truncate** | **0.16 s** | **0.11 s** | **0.03 s** | **0.05 s** |
| delete | 0.17 s | 0.11 s | 0.03 s | 0.04 s |

**What that choice costs, and how it is paid for.** A rollback journal has one
property WAL does not: **a reader blocks a writer.** A writer takes RESERVED,
then PENDING, then EXCLUSIVE, and PENDING waits for every SHARED lock to drain
— so one long-lived reader stops all writing, and while that writer sits at
PENDING it also stops all *new* reading. There are three programs on this one
file: the hourly capture (writer, 40-80 s, irreplaceable data), the bulk
back-fill (writer, hours) and the hourly release rebuild (reader, tens of
minutes). The reader is the one that had to give way, and it does so in two
ways, both measured on 2026-08-08 against the live 46.8 M-row archive:

- **Every whole-archive scan is paged** by `orbit_history.paged_element_sets`,
  which resumes at `WHERE (norad, epoch_ms) > (last seen)` and ends its read
  transaction every 250,000 rows. A single page holds the lock for 0.2-3 s
  against the 32-45 minutes one cursor used to hold it. Key-set paging, not
  `LIMIT/OFFSET`: `prune_hot` deletes rows, and a delete ahead of an OFFSET
  cursor makes the scan skip a row. The property relied on is only that
  **nothing ever UPDATEs an `element_set` row**, so a primary key is fixed for
  as long as the row exists.
- **The writer waits fifteen minutes, not one**
  (`DEFAULT_BUSY_TIMEOUT_SECONDS`). Even with the main scan paged, the
  archive's own aggregates are single statements that cannot be: `COUNT(*)`
  over `element_set` is 103 s, `archive_stats` 147 s, `orbit_release.coverage`
  291 s. Sixty seconds could not survive the cheapest of those.

Before the change, with the old code running, a writer asking for the lock with
a 60 s timeout won **0 of 6** attempts over six minutes. This is why the
capture's failure is now `orbit_history.starved_capture_report` — naming the
hour, the mirror's mtime and the fact that the hour is unrecoverable — rather
than a bare `sqlite3.OperationalError`.

**Tier 2 — `element_set_daily`, one element set per object per UTC day,
forever.** The one nearest 12:00 UTC (nearest-noon rather than first-of-day, so
the daily sample is not biased towards objects re-fitted just after midnight).

**Be honest about what this tier does and does not buy.** At the measured
cadence — 563 new element sets across 563 distinct objects, so 1.00 per object
per interval — tier 2 is very nearly the same size as tier 1. It is not a
compression win today. It earns its place for two other reasons: it is the
**forever, indexed, queryable** copy that survives tier-1 pruning, so the
browser never has to decompress a whole month of cold shard to draw one
satellite; and it makes the shipped resolution **independent of the upstream
cadence**, so if 18 SDS ever starts publishing hourly the page payload does not
quadruple.

**Tier 3 — cold shards, full fidelity, forever.** One file per UTC month,
`orbit-history-YYYY-MM.ohz`. Rows ordered by `(norad, epoch_ms)`, split into
columns, each column delta-encoded **against that object's previous row**,
zig-zag varint, then zlib −9. Delta-within-object is where the compression is:
a LEO object's semi-major axis moves a few metres between element sets, so the
quantised delta is a short varint instead of a ten-digit absolute.

### 1.4 Quantisation

Scales chosen so the stored integer is **exact** for every value space-track
actually publishes, verified against all 31,697 records:

| field | scale | upstream decimals | note |
|---|---|---|---|
| mean motion | 1e-8 rev/day | 8 | |
| eccentricity | 1e-8 | 8 | |
| inclination, RAAN, argp, M | 1e-4 deg | 4 | |
| B* | 1e-12 | 14 published | range −3.5366 … +1.0986 |
| n-dot | 1e-8 rev/day² | 8 | |
| n-ddot | 1e-13 rev/day³ | 13 | almost always 0, costs 0 bytes in SQLite |
| epoch | 1 ms | µs published | see below |

Epoch is the one lossy field. The TLE epoch format (`YYDDD.DDDDDDDD`) resolves
0.86 ms, so 1 ms storage is at the source's own resolution; the ≤0.5 ms rounding
is **3.8 mm** of along-track position at 7.5 km/s. Recorded here rather than
buried, because someone will eventually diff our archive against space-track and
find it.

**What is deliberately *not* stored:** `TLE_LINE0/1/2`, `GP_ID`, `FILE`. Those
are verbatim upstream records. USSPACECOM's blanket redistribution approval
covers basic SSA data with citation; mirroring the upstream text at scale is
what makes an installation look like a clearinghouse, which the approval does
not cover. A test asserts they never appear. `ELEMENT_SET_NO` is dropped for a
duller reason: space-track returns 999 for every single record.

Missing values stay missing. A B* that is absent and a B* of zero are different
physical statements, and the schema keeps them different.

### 1.5 Measured sizes

Tier 1, from SQLite's own `dbstat` on the 31,697 real rows:

| table | bytes | cells | bytes/cell |
|---|---|---|---|
| `element_set` | 1,994,752 | 31,697 | **62.9** |
| `object` | 2,396,160 | 32,278 | 74.2 |

The `object` table is one row per object — names, COSPAR ID, type, RCS, country,
launch date — 2.4 MB for the whole catalogue, and it grows only when new objects
appear, not hourly.

Tier 3, measured on **real** multi-epoch data. The `pipeline/.cache/` directory
holds 31 previously-fetched GP group files (already on disk, no network), which
combined with the space-track snapshot give **15,773 objects with 2–3 distinct
epochs, 32,340 rows**:

| shard content | rows | bytes | bytes/row |
|---|---|---|---|
| first epoch of each object only (no delta possible) | 15,773 | 458,852 | 29.09 |
| all epochs | 32,340 | 848,328 | 26.23 |
| **marginal cost of a delta row (~24 h spacing)** | **16,567** | **389,476** | **23.51** |

And the same measurement on the **two real consecutive hourly snapshots**, which
is the case that actually matters:

| shard content | rows | bytes | bytes/row |
|---|---|---|---|
| the prior element set of each affected object | 563 | 18,474 | 32.81 |
| prior + new | 1,126 | 31,065 | 27.59 |
| **marginal cost of an hour-spaced delta row** | **563** | **12,591** | **22.36** |

Hour-spaced deltas are slightly cheaper than day-spaced ones (22.36 against
23.51), which is what the physics predicts — less has moved.

**The headline compression ratio, measured rather than estimated.** Over that
2.033 h window the archive grew by 12,591 bytes of cold shard, or **6,195 bytes
per hour**, against **4,720,815 bytes** for a gzipped copy of the snapshot
covering the same hour:

| approach | bytes per hour of new information | ratio |
|---|---|---|
| raw hourly snapshot | 36,007,802 | 5,813× |
| gzipped hourly snapshot | 4,720,815 | **762×** |
| **this design (cold shard)** | **6,195** | 1× |

Per-column cost of that mixed set, so the next person can see where the bytes
are before trying to save them:

| column | B/row | | column | B/row |
|---|---|---|---|---|
| B* | 3.92 | | eccentricity | 2.18 |
| epoch | 3.84 | | n-dot | 1.96 |
| mean anomaly | 2.98 | | inclination | 1.29 |
| mean motion | 2.95 | | rev at epoch | 1.12 |
| arg of perigee | 2.94 | | norad | 0.13 |
| RAAN | 2.78 | | n-ddot, ingest hour | 0.06 |

**Headroom I did not take, and why.** Mean anomaly, RAAN and argument of
perigee are ~8.7 B/row combined and are almost entirely predictable: M advances
by n·Δt, and RAAN and argp by their J2 secular rates. Delta-coding against those
*physical predictors* rather than against the previous value would plausibly
save 4 B/row, about 15%. I did not do it, because the predictor must produce
bit-identical results in the encoder and the decoder, which means integer-only
arithmetic and a new class of silent corruption if it ever drifts. 0.9 GB/year
on a 3.3 TB disk does not buy that risk. The option is recorded, with the
measurement behind it, if it ever does.

### 1.6 Growth, in real bytes

At the measured 25,227 element sets/day:

| | per day | per year |
|---|---|---|
| Tier 1 (62.9 B/row, 400-day window) | 1.59 MB | 0.58 GB → **plateaus at 0.64 GB** |
| Tier 2 (62.9 B/row, forever) | 1.59 MB | **0.58 GB** |
| Tier 3 (22.4 B/row, forever) | 0.56 MB | **0.21 GB** |
| `object` table | — | one-off 2.4 MB, then negligible |
| Kp archive (96 samples/day) | 3 KB | 1 MB |
| **total that grows forever** | **2.15 MB/day** | **0.79 GB/year, plus a fixed 0.64 GB** |

After ten years: about **8.5 GB**, on a disk with 3.3 TB free — 0.25% of it.
Against the naive alternatives:

| approach | per year | ratio |
|---|---|---|
| raw hourly snapshots | 316 GB | 400× |
| gzipped hourly snapshots | 41.3 GB | 52× |
| **this design, all tiers** | **0.79 GB** | 1× |
| this design, tier 3 alone (the full-fidelity forever copy) | 0.21 GB | 197× better than gzip |

The instantaneous ratio in §1.5 is 762× because it compares only new information
against a whole re-sent snapshot; the annual figures above include the two
indexed SQLite tiers, which pay for random access rather than for bytes. Both
numbers are real, and they answer different questions.

### 1.7 Retention

The rule this project already uses — `deploy/prune_data.py` takes
`--max-age-hours` from `pipeline/publish_vps.sh`, with a different value local
versus remote — is that **the policy is visible at the call site**. `roll()`
follows it: `retain_days` is a required keyword argument with no default in the
function, and the CLI default (400) lives in the argument parser where the
operator can read it.

`roll()` does four things, always in this order:

1. **Decimate** every UTC day that has settled. A day is left alone for
   `DECIMATION_SETTLE_DAYS = 2`, because 18 SPCS does publish element sets
   whose epoch is already a day or two old, and decimating a day while it can
   still gain members picks the wrong representative.
2. **Export** every complete UTC month. The current month is never exported —
   it is still filling.
3. **Verify** each shard by decoding it and comparing row for row against the
   database it came from. Only then is `verified_ms` recorded.
4. **Prune** tier 1 past the retention window.

Three interlocks, each of which exists because the obvious implementation
silently destroys data:

* `prune_hot()` **refuses** to delete any UTC day that is not both decimated
  and inside a verified shard, and names the day that stopped it. `force=True`
  exists for the one legitimate case — deliberately discarding data — and is
  named so nobody reaches for it by accident.
* **A month whose start predates the prune watermark is never re-exported.**
  Without this, the sequence *export whole month → prune part of it → next roll
  re-exports from what is left* overwrites the only full-fidelity copy with a
  truncated one. A row *count* is not sufficient to detect this, which is the
  form the guard first took and which a review caught: late-arriving element
  sets push the count back above the shard's, re-arming the rewrite. The
  watermark (`meta.pruned_before_ms`, monotonic, updated by every prune
  including a forced one) cannot be fooled that way. A month that only *gains*
  element sets is still re-exported, because a shard growing is always safe.
* **A shard is verified before it replaces the previous one, not after.**
  Verifying post-swap means a bad encode has already destroyed the good shard
  by the time it is detected, while the ledger still describes the file that is
  gone. And a verified ledger row can never be downgraded to an unverified one.
* **The prune interlock reads the shard file, not just the ledger.** It checks
  the file exists and that its SHA-256 still matches what was recorded. A
  ledger row is a claim; the disk is the evidence.

All of these are covered by tests, along with the settle window and the
re-decimation of a day that gains a late element set.

400 days rather than 365 so a year-long comparison never straddles the edge of
the window.

---

## 2. The noise floor, measured

**A detector that cannot state its false-positive behaviour is not ready to be
shown to the public.** So this comes before the detectors.

GP/TLE mean elements are *fitted*, not measured. Element-set-to-element-set
scatter is real and it is not Gaussian. It was measured, not assumed.

**Method.** Take every object with three distinct epochs (**787** objects,
built from the local GP caches plus the space-track snapshot — all the same 18
SDS element sets, nothing fetched). Predict the middle element set by linear
interpolation between its neighbours, and divide the residual by
√(1 + f² + (1−f)²), which undoes the interpolation's own error propagation. What
is left is one sample of the element-to-element scatter, with any smooth trend
removed.

| perigee band | n | σ(a) | σ(e) | σ(i) |
|---|---|---|---|---|
| < 500 km | 89 | **1.67 m** | 1.2e-6 | 7.1e-5° |
| 500–800 km | 129 | **0.51 m** | 6.3e-7 | 6.2e-5° |
| 800–1500 km | 66 | **0.10 m** | 4.6e-7 | 5.9e-5° |
| MEO | 53 | **0.76 m** | 4.5e-7 | 6.1e-5° |
| GEO and above | 450 | **12.44 m** | 1.1e-6 | 1.67e-4° |

Three things worth reading off that table:

* **GP mean elements are astonishingly precise in a differential sense.** Metre
  and sub-metre semi-major-axis repeatability in LEO. A 100 m change in a — a
  tangential Δv of only 4.5–5.2 cm/s across the 800–1500 km band — is a 1,000σ
  event against that band's floor. This is the reason the feature is possible
  at all.
* **Low LEO looks noisier than high LEO**, which is backwards for a pure
  measurement error. It is not error: real drag *curvature* over the sampling
  interval contaminates a second-difference estimator. So the < 500 km figure is
  an **upper bound** on the noise, which is the conservative direction.
* **Inclination scatter sits at the 1e-4° publication quantum in every band.**
  The published inclination is rounded more coarsely than it is noisy. σ(i) is
  therefore floored at the quantum, not at the measurement.

### 2.1 The tails, which are the whole problem

The distribution is violently heavy-tailed. Ratio of the 99th percentile to σ:

| band | p95/σ | p99/σ |
|---|---|---|
| < 500 km | 23 | **3,558** |
| 500–800 km | 23 | 109 |
| 800–1500 km | 41 | 961 |
| GEO+ | 56 | 116 |

For a Gaussian those numbers would be 1.96 and 2.58.

**A Gaussian-calibrated threshold is therefore meaningless here**, and quoting
one would be dishonest. Empirically, applying a κ·σ threshold to that measured
sample:

| κ | observed exceedance (all bands, n = 787) | Gaussian would predict |
|---|---|---|
| 5 | 27.3 % | 5.7e-7 |
| 8 | 23.6 % | 1.2e-15 |
| 12 | 19.1 % | 3.6e-33 |
| 20 | 14.1 % | ~0 |
| 50 | 5.3 % | 0 |

Raising κ by a factor of ten cuts the flag rate by a factor of four. This is
the single most important fact in this document: **the fitted-element residual
distribution has no useful tail decay, so no single-threshold detector on a
single object can be made clean by turning the knob.** The exceedances at large
κ are not error at all — a large share of them are real manoeuvres, since the
sample is 450 GEO payloads that station-keep and 337 LEO payloads. But we
cannot tell which from one object in isolation, and that is exactly the point.

**Consequence for the design:** discrimination has to come from *controls*
— the same object over time, and the neighbouring population at the same moment
— not from the threshold.

---

## 3. Detection

Implemented in `pipeline/orbit_history.py`. Everything works on first
differences of a per-object series, converted to per-day rates.

### 3.1 What is differenced

Semi-major axis is derived as the **Kozai mean** a = (μ/n²)^⅓ using **WGS-72**
μ = 398600.8 km³/s², because that is the gravity model the elements were fitted
with — using WGS-84 instead biases a by tens of metres. This is not the
osculating a and not the Brouwer a; the J2 short-period correction between them
is very nearly constant for a given object and cancels in first differences.
A test pins the result against space-track's own published `SEMIMAJOR_AXIS` for
VANGUARD 1 (8613.401 km).

Pairs more than **3 days** apart are dropped. Across a longer gap a step and a
slow trend are not distinguishable, and reporting one as the other is precisely
the failure this design exists to avoid.

### 3.2 J2 is removed before anything is tested

Nodal regression and apsidal precession are secular, predictable, and not
manoeuvres. RAAN and argument of perigee are **never** tested raw. Both are
reduced to residuals against

    Ω̇ = −(3/2) n J₂ (R_E/p)² cos i
    ω̇ =  (3/4) n J₂ (R_E/p)² (5cos²i − 1)

A test drives a textbook 98.2° sun-synchronous orbit through 40 element sets, in
which RAAN wraps through 360° repeatedly, and asserts the residual stays under
0.01°/day and that **zero** events are produced. A second test pins Ω̇ against
the sun-synchronous rate, +0.9856°/day.

### 3.3 The noise estimate, per object, per candidate

For each candidate interval:

* **Robust scale by MAD** (× 1.4826), not standard deviation — one manoeuvre in
  the window would inflate a standard deviation enough to hide itself.
* **Leave-one-out**: the candidate is excluded from its own scale and centre
  estimate. A test drives a step 50× the noise and confirms it is still found;
  without leave-one-out it masks itself.
* **Floored at the measured catalogue scatter for that altitude band** (the
  table in §2), scaled by √2/Δt because a rate over a short span divides the
  scatter by the span and two element sets each carry it. Without this floor, an
  object whose recent window happens to be unusually quiet gets a threshold of
  millimetres and every subsequent element set looks like a burn. This is a real
  failure mode, and it is what the floor is for.

### 3.4 Manoeuvre

A step in a, e or i exceeding κ·σ with κ = 8 by default. Reports, per element
tripped: the delta in metres (or degrees), σ in the same units, the z-score, and
an impulsive Δv estimate Δv = ½·n·Δa — described as a *lower bound*, since any
non-tangential thrust needs more.

Tests cover: a clean step is found; pure Gaussian noise gives nothing; a smooth
drag decay gives nothing (a step, not a trend, is the signature — otherwise
every decaying LEO object reads as burning continuously); a short series returns
nothing rather than a guess.

### 3.5 Drag

A sustained, negative, *accelerating* trend in a. Drag is the only common
perturbation that removes energy secularly, so a negative median rate that is
significant against the object's own scatter is the signature; the curvature —
the decay steepening as it goes — separates it from a slow sequence of
retrograde burns. Reports median decay in m/day, its standard error
(1.2533σ/√N for a median), whether the second half is steeper than the first,
perigee altitude, and median B*.

### 3.6 Station-keeping

Small, repeated, roughly periodic corrections. Runs the manoeuvre detector at a
lower κ = 6, then requires ≥4 corrections whose **inter-arrival coefficient of
variation is below 0.6**. That regularity is the entire discriminator against a
run of unrelated manoeuvres, and a test with corrections at irregular intervals
confirms it is rejected.

There is a test that matters more than the positive one: a 3e-6 rev/day GEO
nudge moves a by 84 m, inside the 12.4 m GEO scatter times the κ the detector
requires, and the detector is asserted to stay **silent**. Silence is the honest
answer when the evidence is not there. (A realistic GEO east-west correction —
about 10 cm/s — moves a by ~2.8 km, 200× the scatter, and is found easily.)

### 3.7 The false-positive rate, and how it gets measured

**The control set is free and already in the archive: debris and spent rocket
bodies cannot manoeuvre.** The live catalogue carries **9,881 DEBRIS and 2,199
ROCKET BODY** objects. Every manoeuvre the detector reports on one of them is,
by construction, a false positive — measured against the same fits, the same
tracking outages, the same space weather, and the same epoch spacing as the
payloads it is judging.

`false_positive_rate(connection, kappa=…)` does exactly this and returns
control objects, control intervals, flags, and the rate per interval.

**It has not been run yet, because the archive is one capture old.** That is the
honest state, and it is why:

* every `Event` this module produces carries `confidence="candidate"` and
  nothing else — the field exists so that a better label has to be *earned*;
* **no manoeuvre inference may be shown to a visitor until this number exists**
  and is displayed next to it.

The gate to open the feature: run it once ~30 days of archive exist, and again
each month. Design target ≤ 1 false positive per 1,000 element-set intervals on
the passive control, after the cohort screen in §3.8. If the measurement does
not reach that, the honest response is to raise κ, add the persistence
requirement below, or ship the plots without the labels — not to relabel the
threshold.

Two strengtheners already designed, not yet built, both of which need archive
depth to calibrate:

* **Persistence.** A genuine step changes the *level*; a bad fit reverts. Require
  the step to survive into the next element set. The two tests are not
  independent (bad fits are correlated), so the joint rate must be measured, not
  multiplied.
* **Cohort control** (§3.8), which is the one that actually matters.

### 3.8 The cohort screen

Every `Event` currently carries `"cohortScreened": false`, because the screen
needs the population, not one object. The design:

For a candidate on object X in interval [t₀,t₁], take the cohort of objects
within **±25 km of perigee altitude and ±2° of inclination** and compute the
same statistic over the same interval. A manoeuvre requires X to trip **while
the cohort median z-score stays below 1**.

This is what kills the two false-positive sources a single-object threshold
cannot touch: a catalogue-wide re-fit or process change at 18 SDS, and a
geomagnetic storm that bends *every* object in a shell at once. It is also the
same computation as §5, run at a different scale — one screen, two features.

---

## 4. The browser

### 4.1 Entry and layout

The satellite card gains an **Orbit history** section. Opening it fetches that
object's history shard and shows stacked small multiples on one shared time
axis, with a brush to zoom:

1. **Perigee and apogee altitude (km)**, drawn as a filled band. The most
   physically legible view, and where a Hohmann-style raise is obvious.
2. **Semi-major axis residual (m)** after removing the fitted secular trend.
   This is the panel where steps live. Y-axis in metres, because the whole point
   is that the noise floor is metres.
3. **Inclination (deg)** — plane changes and GEO north-south keeping.
4. **Eccentricity.**
5. **B\*** on a log axis — the fitted drag term, and an independent witness
   whenever the drag story is the one being told.
6. **Context strip: archived Kp**, as bars on the same time axis.

Panels 2–5 carry a faint grey band: the **cohort median ±IQR** for objects at
the same altitude and inclination. This is the single most important element of
the whole design, because it makes the discrimination *visible* rather than
asserted. Everything at this altitude bent down together → weather. Only this
one stepped → something the operator did.

### 4.2 Events

Vertical rules across all panels, colour-coded: manoeuvre candidate (amber),
drag episode (blue shading over the interval), station-keeping cadence (small
regular ticks). Clicking opens an evidence card. A worked example of the exact
wording:

> ### Manoeuvre — inferred, not confirmed
>
> Between **2026-08-07 04:12 UTC** and **2026-08-07 11:47 UTC** the semi-major
> axis rose by **412 m** (± 6 m). That is **68×** this satellite's typical
> element-to-element scatter over the past 30 days.
>
> If that came from a single tangential burn, it would be about **22 cm/s** —
> a lower bound, since any other thrust direction needs more.
>
> **What makes this look deliberate:** of **214** objects within 25 km of the
> same altitude and 2° of the same inclination, **none** showed a comparable
> change in the same interval. Drag and geomagnetic heating act on a whole
> shell at once; this did not.
>
> **What else could produce this signature:** a re-fit after a tracking gap (the
> previous element set was 3.1 days old), an unmodelled solar-radiation-pressure
> event, or a catalogue correlation error between two nearby objects.
>
> **How confident is this?** This is a *candidate*. Over the last 30 days this
> detector flagged **N** intervals on objects that physically cannot manoeuvre —
> debris and spent rocket stages — out of **M** examined, so roughly **N/M** of
> flags like this one are expected to be wrong.
>
> *We infer this from public orbital elements. We are not told what any
> operator did, and this site never claims to be.*

### 4.3 The wording rules

Non-negotiable, and enforced in the copy, not left to the writer's judgement:

* Never "this satellite performed a burn". Always "consistent with",
  "the evidence is", "we infer".
* Every inference carries its **evidence**, its **noise floor**, its **control**,
  and at least one **alternative explanation**.
* Every inference carries the **measured** false-positive rate. If the number
  does not exist yet, the label does not ship — the plot does, unlabelled.
* Never the word "confirmed", and never an operator's name attached to an act.
* Drag events say "consistent with atmospheric drag", never "re-entry
  predicted", and never a date.

This is the same contract as `docs/SCIENTIFIC-LAYERS.md`; the history feature
should be added to it.

### 4.4 Coverage honesty

The archive begins 2026-08-07. Before that there is nothing, and the UI must say
so in the same voice the environment layers already use — reuse
`exact_frame_coverage()`'s vocabulary and emit a `noDataInterval` with reason
`before-bigmem-accumulation`. Gaps from a missed capture get `snapshot-gap`.
**Never interpolate across a gap**, and never let a line segment imply data
between two points that are three days apart. The plot must show the element
sets as points, with segments only where the spacing justifies them.

Also worth surfacing on the card, because it is the honest framing of the whole
feature: *"These are fitted mean elements published every few hours, not
measurements of where the satellite is. What we can see is how the fit moved."*

### 4.5 Payload sizing

Doing this naively fails. A year of one object at 4 element sets/day is 1,460
rows; all 8,000 catalogue objects at that resolution is ~64 MB gzipped, which is
not a page load.

The split that works, and it falls straight out of the tiering:

* **Plots use tier 2** — one sample per object per day. Measured, not
  estimated: encoding day index, mean motion, eccentricity, inclination and B*
  with the same delta-varint-deflate codec over the 32,340 real multi-epoch
  rows gives **8.06 bytes per object-day** (6.71 without B*). So 8,000 objects
  × 365 days = **23.5 MB compressed**. Shard by `norad % 256` → **256
  artifacts of ~92 KiB**, fetched lazily when the visitor opens the panel.

  Daily resolution is ample for the plot: with a metre-level noise floor, a
  400 m step is unmistakable in a daily series. Exact epochs come from the
  event list, which is full precision.

  This grows linearly — 3 years is 70 MB total, 275 KiB per shard. When that
  starts to hurt, decimate the *browser* tier to weekly beyond one year. The
  archive itself keeps everything; only the shipped resolution drops.
* **Events use tier 1** — full precision, exact epochs. Events are rare, so the
  whole catalogue's event list for a year is a few hundred KB. One artifact.
* **Population/storm data** is its own small artifact (§5).

All three go through `write_artifact()` unchanged: content-addressed,
`.json` + `.json.gz`, SHA-256 in the manifest, and `deploy/publish_data.py`
picks them up automatically from the `path`+`sha256` contract.

---

## 5. The storm tie-in

This is the part worth building first after the archive, and it delivers the
teaching payoff that `docs/OPEN-WORK.md` §1.1 was blocked on — **without
needing `pymsis` at all.**

### 5.1 The physics, and why the naive version fails

A geomagnetic storm heats the thermosphere, density rises, and hundreds of LEO
objects decay faster at once. From drag,

    ȧ = −(C_D A/m) ρ √(μ a)

so ȧ depends on the **ballistic coefficient** as much as on ρ. Plotting raw
median ȧ per shell against Kp therefore mixes a changing population into a
density signal.

### 5.2 The quantity to actually plot

Per object, compute its own baseline ȧ_quiet over a geomagnetically quiet
reference window, then report the **ratio ȧ(t)/ȧ_quiet**. The ballistic
coefficient cancels exactly, and what is left is

    ȧ(t)/ȧ_quiet = ρ(t)/ρ_quiet

**The shell median of that ratio is an empirical measurement of thermospheric
density enhancement, made with satellites.** That is a genuinely strong piece of
teaching material: the site would not be illustrating the February 2022 Starlink
loss with a diagram, it would be *measuring the same effect* from its own
archive. NRLMSIS then becomes an optional comparison curve rather than a
prerequisite.

### 5.3 The validation case: Gannon, May 2024

**KANOPUS-V 3's decay went from ~38 m/day to ~180 m/day at ~475 km during the
May 2024 Gannon storm — a factor of 4.7.** Because decay is linear in neutral
density and the ballistic coefficient cancels in the ratio, that 4.7 *is* a
measured density enhancement, obtained from orbital elements alone. NRLMSIS 2.1
gives 2.06× for the same conditions; the empirical models are documented as
under-predicting storm-time density (CCMC assessment, Wang et al. 2026, 151
storms across five missions).

That is the target this estimator has to hit, and it is a far better calibration
than tuning thresholds against intuition. `density_enhancement()` is tested
against a synthetic 30-object population reproducing exactly those two decay
rates at that altitude, and recovers **4.7 ± 0.3** with a standard error under
0.3; the same estimator returns 1.0 ± 0.15 over a quiet period.

**We cannot check it against the real May 2024 elements.** Our archive begins
2026-08-07, and space-track's historical bulk classes are a different,
rate-limited product this installation does not use. The check that *can* be
run is the forward one: the next storm the archive sees.

Two notes for whoever builds the Gannon teaching module:

* **`pipeline/thermosphere.py:decay_rate_km_per_day()` is the forward version of
  this physics** — density in, decay rate out — while `orbit_history.rates()` is
  the inverse, decay rate measured out of the elements. They share the km/day
  sign convention (negative = decaying), so a model density can be checked
  against a measured decay and vice versa. They are not interchangeable and
  neither should call the other; the point is that the two numbers must agree.
* **The population signal is the teaching payload, not the single track.** One
  satellite is an anecdote. The storm bent *every* object in the shell at once,
  and that is both the stronger evidence and the better lesson.

### 5.4 The trap that ate a day of someone else's work

Neutral density swings by about a **factor of two between the day and night
sides**. A before/after comparison built from single points 12 hours apart
measures the diurnal cycle, not the storm — and it will happily produce a
plausible-looking ratio while doing it.

Two defences, both implemented:

* **`min_span_orbits`.** `rates()` will refuse an interval spanning fewer than
  `ORBIT_AVERAGING_MINIMUM = 3` complete revolutions when asked, and both
  `detect_drag()` and the population estimators ask. Over three or more
  revolutions the rate is orbit-averaged and the diurnal term is integrated
  out. Manoeuvre detection deliberately leaves the guard off: a step is
  instantaneous and wants the shortest interval available.
* **Ratios are formed per object against its own baseline, then combined** —
  never as a ratio of two population medians. A changing mix of objects between
  the two windows would otherwise read as a change in the atmosphere. And
  because the passive population is spread across all RAANs, it is spread
  across all local solar times, so the shell median has no local-time
  preference left in it.

A third defence is refusal: a quiet baseline that is not actually decaying
(ȧ ≥ 0) is discarded rather than divided by, since dividing by noise invents a
ratio. A test confirms that a population of non-decaying tracers yields no
shells at all rather than a spread of meaningless numbers.

### 5.5 How it is computed

`population_decay()` is implemented and does the binning:

* **Bin on perigee altitude, not semi-major axis.** Drag does its work at
  perigee. 50 km shells from 150 to 1,400 km.
* **Restrict to DEBRIS and ROCKET BODY.** They are clean ballistic tracers and
  they cannot manoeuvre. The same control set as §3.7, doing double duty:
  null hypothesis for the detector, tracer population for the density estimate.
  A test confirms an orbit-raising payload dropped into the population does not
  move the shell median.
* Report per shell: object count, median decay in m/day, and the standard error
  of the median (1.2533σ/√N).

### 5.6 The expected signal-to-noise

With N ≈ 500 passive objects in a populated shell and a per-object ratio scatter
of ~50%, the standard error of the shell median is
1.2533 × 0.5/√500 ≈ **2.8%**. A 20% density enhancement is therefore a **7σ**
population detection, and storm-time enhancements are considerably larger than
20%. The population signal is far easier than the single-object one — which is
the pedagogical point, and worth saying out loud on the page.

### 5.7 The geomagnetic side has a problem, and it is now half-fixed

**The site's Kp series is a rolling 24-hour window.** `build_space_weather()`
publishes `geomagnetic.series` as 24 samples at 15-minute buckets, and nothing
retains it. Ap exists only as a **three-day forecast** from the SWPC outlook.
**Dst is not ingested at all. F10.7 is not ingested at all.**

Left alone, the orbit archive would outlive the only geomagnetic time series the
site has, and the correlation this whole section rests on would be
uncomputable. So `capture_geomagnetic()` snapshots the Kp window on every
capture into a `geomagnetic` table, keyed on `(index_name, observed_ms)` so the
overlap deduplicates itself. It reads the artifact this pipeline already wrote —
no network, and it degrades to zero rather than raising if the artifact is
missing or malformed. 25 samples archived on the first run.

Still open, and needing Sean's word because they are new upstream endpoints:

* **F10.7** — `services.swpc.noaa.gov/json/f107_cm_flux.json`, already noted as
  verified-reachable in `docs/space-weather-teaching-spec.md`. It is the *other*
  driver of thermospheric density and the correlation is weaker without it.
* **Dst** — the better index for storm-time ring-current energy input.
* **Ap observed**, not just forecast.

None of these are needed for the feature to work; all three make it better.

### 5.8 Confounders to state on the page

1. **Local solar time** — the day/night density factor of two. See §5.4. This
   is the one that has already caught someone on this project, and the only one
   with code defending against it.
2. Manoeuvring payloads — excluded by the passive-only restriction.
3. Eccentric orbits sample a range of altitudes; binning on perigee is right but
   not perfect.
4. Element-set spacing varies per object, so the per-interval weighting is not
   uniform.
5. Latitudinal density variation is averaged over by the orbit, not removed.
6. The quiet-baseline window must be chosen from Kp, and it moves with the solar
   cycle. Re-derive it annually.

---

## 6. Honest limits of what was measured

* The noise floor comes from **787 three-epoch triples**, mostly payloads,
  spanning 1–2 days. It is a real measurement and it is not a large one. It
  should be recomputed from the archive itself once ~30 days exist, per object
  and per band, and `CATALOGUE_NOISE_FLOOR` updated.
* The delta-compression figure is measured on two real consecutive hourly
  snapshots (22.36 B/row) and cross-checked against ~24-hour spacing
  (23.51 B/row). Not estimated.
* **The 25,227 element-sets-per-day rate rests on a single 24-hour window** —
  the epoch-age histogram of one snapshot. The publication pattern is bursty
  and almost certainly varies with the day of the week and with tracking load,
  so treat it as one sample, not a constant. `archive_stats()` and the `capture`
  ledger answer it directly and continuously once the timer is wired; check it
  against this figure after a week.
* The first estimate of that rate was **four times too high**, because it
  counted `CREATION_DATE` batches as new element sets. Anyone re-deriving a rate
  from this data should diff on `(NORAD_CAT_ID, EPOCH)` and nothing else.
* **The false-positive rate is not measured.** §3.7 is a procedure, not a result.
* The **4.7× Gannon recovery** in §5.3 is measured against a synthetic
  population built to those published decay rates, not against the real May
  2024 elements, which this installation does not hold and must not fetch.

---

## 7. What must be wired up — deliberately not done here

No existing file was modified. These four steps are all that stand between the
current state and a running archive plus a shipped feature.

### 7.1 Capture, on the ingest timer — do this first

The archive currently only advances when someone runs it by hand. Add an
`ExecStartPost` to `deploy/systemd/spacetrack-ingest.service`, so capture
happens immediately after each fetch and nothing else needs to change:

```ini
ExecStartPost=/usr/bin/python3 -m pipeline.orbit_history --capture \
    --from-manifest /home/sdegan/space-teaching-aid/runtime/data
```

`--from-manifest` exists because the artifacts are content-addressed, so their
filenames change on every publish and systemd cannot glob (it does not run a
shell). It reads `manifest.json` the way `deploy/publish_data.py` does, and
returns nothing rather than raising if the manifest is missing or broken — a
space-weather problem must never stop the orbital capture, which is the half
that cannot be back-filled.

`ExecStartPost` runs even when the ingest script short-circuits without
fetching. That is fine and intended: capture is idempotent, and re-inserting
31,697 duplicate rows measures at 0.03 s.

Then:

```bash
sudo systemctl daemon-reload
sudo systemctl start spacetrack-ingest.service
python3 -m pipeline.orbit_history --status
```

Alternative if touching the ingest unit is unwelcome: a separate
`orbit-history-capture.timer` at `*:35:00`. Slightly worse — it can miss a fetch
that arrives late — but it leaves the space-track path untouched, which has a
value of its own.

### 7.2 Rolling and retention, on the daily path

Once a day, ideally not inside the 5-minute publish cycle, whose
`TimeoutStartSec` is 240 s for build *and* publish:

```bash
python3 -m pipeline.orbit_history --roll --retain-days 400
```

Put the retention number on the command line, not in the module — same
convention as `deploy/prune_data.py --max-age-hours 168` in
`pipeline/publish_vps.sh`. A `orbit-history-roll.timer` with
`OnCalendar=*-*-* 04:30:00` is the natural home.

### 7.3 `build_release.py` integration

Three new artifacts, all through the existing idiom — build a dict, call
`write_artifact(data_root, prefix, bundle)`, add `{"path", "sha256", …}` to the
manifest. Nothing downstream needs changing; `deploy/publish_data.py` discovers
records by the `path`+`sha256` contract, and `deploy/prune_data.py` keeps
anything the manifest references.

| manifest key | prefix | content | size |
|---|---|---|---|
| `orbitHistory` | `orbit-history-NNN` | 256 shards of tier-2 daily series, `norad % 256` | ~92 KiB each |
| `orbitEvents` | `orbit-events` | full-precision events with evidence | few hundred KB |
| `orbitDrag` | `orbit-drag` | daily shell medians, density ratios, archived Kp | tens of KB |

Wrap each in `publish_timed_environment_artifact()` so a bad archive read
preserves the prior artifact instead of killing the publish cycle — the
inconsistency `docs/OPEN-WORK.md` §1.3 complains about in GloTEC, avoided here
by copying the sibling that already gets it right.

**Watch the 240 s budget, and measure it rather than guessing.** On the live
archive: a full ordered scan of tier 2 takes **0.030 s**, while 4,000
per-object queries take **6.18 s** — 1.54 ms each, almost all of it v9fs
round-trip cost, and that is with barely any rows to return. At 8,000 objects
the per-object pattern spends ~12 s in query overhead alone before the archive
has any depth. Read tier 2 in one ordered scan and build all 256 shards in a
single pass.

### 7.4 The gate on the inference labels

Before any manoeuvre or drag label is shown to a visitor:

```bash
python3 -m pipeline.orbit_history --false-positive-rate --fpr-limit 2000
```

Publish the number next to the inference. If the archive is too shallow, the
plots ship and the labels do not. **This is the one step that must not be
skipped**, and it is the reason `confidence` is hard-wired to `"candidate"`
today.

### 7.5 Smaller follow-ups

* Recompute `CATALOGUE_NOISE_FLOOR` from the archive after ~30 days.
* Implement the cohort screen (§3.8) and flip `cohortScreened` to true.
* Add F10.7 and Dst ingest (§5.5) — needs Sean's call on new endpoints.
* Add the history feature to `docs/SCIENTIFIC-LAYERS.md`, and fold it into the
  **Data & methods** card that `docs/OPEN-WORK.md` §2.3 already wants.
