# Long-arc drift v4 — nightly website lane

Source implementation, 2026-09-12; **not installed or deployed**. This section
supersedes the manual v1 design retained below as development history.

## Shipped window and statistic

Each nightly run recomputes the full raw-element catalogue, statelessly, with
`end` at the current UTC midnight. The **test window is the trailing 120 complete
UTC days**. The preceding 240 days are optional context, never a flag requirement.
120 days gives 24 five-day blocks: a sustained-trend question complementary to
adjacent-fit steps, with enough observations for robust fitting. It sacrifices
short-campaign sensitivity deliberately. It is not the 2024 acceptance window.

Raw fits reduce first to daily medians, then window-aligned five-day medians.
Fits need at least 12 blocks AND 80% of the window's possible blocks (therefore
20 of 24 for the shipped test), with observations in the outer 10% at each end.
Every raw test-window fit must have perigee <800 km and eccentricity <0.05 to
enter the drag regime. Maxima are retained before medians, so a regime crossing
cannot be hidden by reduction. Missing coverage is a gap, never a negative result.

The v4 score is positive semi-major-axis slope divided by
`max(robust residual scatter, 0.001 km) / observed span`; threshold remains **5**.
Theil–Sen uses deterministic per-NORAD pairs, up to 4,000; float64 NumPy/CuPy
arithmetic is shared. This score is not a Gaussian probability. No B*, drag
prediction, cohort adjustment, or trailing-fit availability enters the decision.
Eccentricity, inclination and slope changes are diagnostics only.

Each run measures one fitted in-gate object-window per object. Passive types
are DEBRIS and ROCKET BODY; payloads are PAYLOAD; UNKNOWN is in neither rate.
`labelPolicy.propulsionLabelPermitted` requires this run's own **exact one-sided
95% passive binomial upper bound <0.001** AND **payload observed rate / that
upper bound >=10**. Restricted/manual samples cannot open it. This is a
bound-aware comparison, not a joint confidence bound on the ratio. No threshold
or window is changed to rescue a failed run. Zero denominators mean unmeasured.

Raw detections remain in the controls for audit. Published object `flag` is true
only for a qualifying PAYLOAD rise when the lane gate passes. Otherwise all
flags are suppressed and `blockingReason` explains the closed gate. Shared
catalogue errors and related debris families can weaken binomial independence.
The physical inference is propulsion by elimination, not independent burn truth.

## Schedule, artifacts and consumer wiring

`deploy/systemd/orbit-drift.service` runs `.venv-gpu/bin/python -m
pipeline.orbit_drift --build-cache --backend gpu --devices 0`, Nice=15, idle I/O,
single-threaded BLAS, 7200-second timeout. The explicit SSD DB root prevents a
nightly fallback onto the cold HDD. GPU ceiling remains **1335 MiB
(1,399,848,960 bytes)**. No automatic CPU fallback or retry raises that ceiling.

The new timer is **05:40 UTC nightly** (01:40 EDT / 00:40 EST), persistent,
30-second accuracy. It avoids even-hour :25 release starts and :17 ingest plus
six-minute jitter. A normal 10–15-minute pass clears the next ingest; long tails
can still overlap. Priority and memory bounds contain that contention. The
7200-second backstop also accommodates the 39-minute historical v4 evaluation.
`orbit-release.timer` is unchanged and was confirmed active after verification.

The builder writes `public/data/artifacts/orbit-drift-<hash>.json` plus deterministic
gzip through `build_release.write_artifact`, then atomically replaces
`pipeline/.cache/orbit-drift-manifest.json`. Only a completed report and successful
GPU-session cleanup can advance the fragment. The artifact carries method/config,
window, controls, labelPolicy, generation date, and compact per-object records.

Fragment investigation: `build_release` already merges the dict returned by
`orbit_release.publish`; that function formerly read only the step fragment.
The minimal change reads the independent drift fragment too, validates referenced
file existence, and preserves the previous published drift record if the new
fragment is absent/invalid. Step rebuilds never write drift's fragment. Neither
`build_release` nor the archive sweep/columnar implementation changes. The regular
publisher copies the generic path/hash record and its gzip to the VPS; only
`orbit-history-*` is excluded from that copy, so drift follows the existing lane.

`main.ts` passes a manifest-path loader into the history browser. Each selected
object receives a **Long-arc drift** card, independent of step-shard availability.
A passed payload flag earns “sustained orbit-raising over N days, +X m/day” and the
physical warrant; suppressed rises carry no propulsion claim. Above-gate rises
read “solar-radiation-pressure regime rise”, “GEO libration”, or “HEO lunisolar”,
explicitly ambiguity labels rather than demonstrated causes. Gaps show their text.
No-step-event wording no longer contradicts the independent drift result.

The existing inference chapter teaches the method, the three failed designs,
and blind spots, then loads **the same artifact's current controls**. No new
hash routes. Missing/unreadable artifacts are explicit, with no inherited gate.
Drift uses `--oh-drift` with literal `#57c7b3` fallback, separate from step amber,
and appears in the signature legend. DOM tests cover the actual Python-emitted
fixture shape, including the gap and suppressed rise.

## Shipped-config full-catalogue control — 2026-09-12

**FAIL / UNMEASURABLE; flags suppressed.** End 2026-09-12 exclusive, test
2026-05-15 through 2026-09-11; optional context starts 2025-09-17.

| Quantity | Measured |
|---|---:|
| Catalogue objects examined | 68,657 |
| Raw rows / temporal blocks | 8,457,916 / 850,993 |
| Test-fitted objects | 0 |
| Coverage gaps (insufficient blocks/coverage) | 68,657 |
| Passive detections / eligible object-windows | 0 / 0 |
| Payload detections / eligible object-windows | 0 / 0 |
| Passive exact 95% upper bound | unmeasurable |
| Bound-aware separation | unmeasurable |
| Published propulsion flags | 0 |

This is inadequate coverage, **not zero measured false alarms**. The successful
2024 result (0/4,107 passive, 56/7,059 payload, 0.729/1,000 upper bound, 10.88×)
is historical evidence only and authorizes none of this release's wording.
Independent raw-row spot checks found only 34 observed test days for ISS (25544)
and STARLINK-11341 (61696), spanning August 7–September 11; neither can qualify.

GPU 0 pipeline time **254.674 s**; whole command **259.77 s**, CPU 202.16 s user
+26.51 s system; peak RSS **259,876 KiB**. In-process GPU peak **249,561,088 bytes**,
no telemetry error or shrinking. **No fit kernels ran in this full-catalogue pass**:
all arcs failed coverage. A separate offline real-GPU parity fixture passed and
exercised kernels; full-catalogue GPU fitting on this window remains unproven.

The run was isolated from publication:

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 nice -n 15 ionice -c 3 \
  .venv-gpu/bin/python -m pipeline.orbit_drift --build-cache \
  --backend gpu --devices 0 --end 2026-09-12 \
  --data-root /tmp/drift-website-work/release \
  --fragment-path /tmp/drift-website-work/fragment.json
```

Artifact: `orbit-drift-0e2cfa641e374f4d.json`, **12,902,991 bytes**, gzip **243,714 bytes**.
SHA-256 `0e2cfa641e374f4d2dd98ec13bcb2ea1a2552d6bbd5bf1bbcd6eced69f8fb355`.
Metrics and fragment are in `/tmp/drift-website-work/`; the normal usage receipt
was written to **state/space-orbit-drift-usage.jsonl**, unchanged for the VPS registry.

## Validation receipts

- Python orbit suite: **614 tests run: 610 passed and four expected GPU opt-in skips**
  (228.960 s on the shared tree). Separate real-GPU drift fixture: 1 passed.
  The final fragment-failure regressions also passed in the eight-test publication suite.
- Drift publication tests cover strict/inclusive gate boundaries, restricted
  population refusal, payload-only flags, gaps, content hashes, gzip, independent
  fragment merge, previous-artifact fallback, staging copy, retention and the
  publisher's default `public/data` destination.
- Full TypeScript suite: **129 files / 2,462 tests passed; one suite blocked**.
  `tests/orbit-verdict.test.ts` cannot load its pre-existing dated input,
  `public/data/artifacts/orbit-events-b3112145df7493d8.json`, which has been pruned
  locally/on the VPS and returns 404 at the site's immutable URL. No substitute
  input or weakened test was used. The full-suite-green requirement remains open.
- `tsc --noEmit` and `systemd-analyze verify` for the two new units passed.
  No Playwright/Chromium was run. Logs are in `/tmp/drift-website-work/`.

## Lifecycle and operator checks

Consumers: browser object cards and inference chapter, through the release
manifest. Current references are the published manifest AND pending drift fragment.
Each JSON artifact is bounded to **32 MiB**. This lane retains at most **16 artifact
files / 256 MiB**, including gzip; superseded files get 72-hour grace. Before a
new publication it removes only its own old unreferenced artifacts and refuses
admission if protected files leave insufficient budget. Generic publisher pruning
may remove unreferenced files sooner; referenced live files survive. A failed
fragment never causes the builder to evict a current reference. Preview safely:

```bash
.venv-gpu/bin/python -m pipeline.orbit_drift --build-cache --backend gpu --devices 0 --dry-run
.venv-gpu/bin/python -m pipeline.orbit_drift --retention-dry-run
.venv-gpu/bin/python -m pipeline.orbit_drift --ledger-retention-dry-run
```

Private fit scratch retains the existing 512 MiB database limit / 1 GiB peak
provision, deleted on ordinary exit. The nightly raw scientific report is a
private anonymous temporary file, bounded to 256 MiB and closed on success/failure;
it does not accumulate JSONL outputs. One current verification release/log set
under `/tmp/drift-website-work` is retained for operator review (64 MiB budget),
then is regenerable and removable. The stable GPU ledger retains newest 4,096
lines / 4 MiB. The existing GPU venv and process-local kernel cache are unchanged.

Unproven: live scheduled firing, synthetic systemd exercise, deployment and browser
pixel review (no Chromium/Playwright used); full-catalogue GPU fit cost once coverage
qualifies; independent per-object propulsion truth, campaign timing, raising-population
recall, and generalization from fitted windows. Station-keeping, lowering,
above-gate behaviour and GEO relocations remain blind spots. No timer was installed
or started and no site was deployed.

---

## Historical manual v1 design (superseded above)

# Long-arc drift verification lane

Status: built, manual, **GPU fitting awaits Sean's authorization**. No publisher,
`src/`, ingest, timer, service or existing detector changes. Entry point:
`python -m pipeline.orbit_drift`. This emits a standalone scientific JSONL report;
nothing on the site consumes it yet. The self-history step detector remains intact.

## Method and interpretation

- Read raw `element_set` rows through `orbit_campaigns.open_archive_for_reading()`,
  resolving the SSD archive with `orbit_history.archive_db_path()`. Missing archive
  fails before the opener's create-on-missing fallback. Per-NORAD, epoch-keyset pages
  finish their transactions before reduction/fit. No cold-shard or tier-2 substitution.
- Compute UTC **one-day medians** of semi-major axis (Kozai mean, km), eccentricity
  and inclination (degrees). Raw reduction is shared CPU code; the bounded fit and
  residual medians are CuPy on GPU. With three daily fits a single bad fit is rejected;
  one or two daily fits cannot offer that guarantee. RAAN, argument of perigee and mean
  anomaly need angular/phase treatment and are not outputs of this initial lane.
- Fit a median pair slope from **4,000 uniformly sampled unordered pairs with
  replacement**, using NumPy PCG64 seeded only by NORAD. If all pairs fit the budget,
  enumerate them. Indices are generated once on CPU for either backend. No global
  RNG, O(n²) pair array, or pair sharing across objects. Float64 everywhere. Residual
  scatter is `1.4826 * median(abs(residual - median(residual)))` in element units.
- Explicit half-open window `[start, end)`, default minimum 60 occupied daily blocks,
  80% day coverage, and observations within the outer 10% at each window end. These
  guards apply equally to targets and peers. Sparse arcs are labelled gaps. This is a
  common requested window with coverage guards, not proof of identical observing days.
- Cohort: other eligible objects, **excluding the target**, in the same fixed
  50 km median-perigee and 4° median-inclination bin over that same window. At least
  eight peers. Bin edges are floor multiples; near-boundary objects can have different
  peers. Geometry uses the daily series, not current catalog metadata. On two GPUs,
  all fits rejoin before comparison, so cohorts are never restricted to a GPU shard.
- Signed z = `(object slope - median peer slope) / scale`. Scale is the maximum of
  peer slope MAD × 1.4826, object residual scatter / observed span, and a resolution
  guard / span (0.001 km, 1e-8 eccentricity, 1e-4 degrees respectively). Flags require
  `abs(z) >= 5`. These are **robust standardized scores, not Gaussian significance
  probabilities**. The 1 m semi-major-axis guard is conservative, not a calibrated
  physical threshold. Control density, band widths, coverage and threshold are explicit
  `Config` fields in every report and require empirical calibration.
- `departureLowerBound` is `max(0, abs(slope departure) - 5*scale) * observed span`,
  in element units. It is an operational lower-bound framing, **not** a statistical
  confidence bound, delta-v estimate or propulsion attribution. Daily blocks preserve
  temporal resolution; a single long-window line does **not** determine exact onset
  or cessation. Narrower, independently controlled windows can investigate timing later.

The fixed estimator is retained, but its premise needs precision: ordinary Theil–Sen
has about a **29.3%** point-contamination breakdown point, not 50%. A median has 50%
breakdown among its inputs; corrupting one point corrupts many pair slopes. Bounded
random sampling adds sampling variability, which is deterministic here, rather than
upgrading that guarantee. [scikit-learn's estimator documentation](https://scikit-learn.org/stable/auto_examples/linear_model/plot_theilsen.html).

Cohort differencing removes a shared trend, not every non-propulsive cause. Different
area-to-mass ratios, attitude, eccentricity, fit quality and natural perturbations can
still produce differences. A payload-dominated cohort can absorb common operation.
The passive control is what will reveal these limitations on real data.

## False alarms and reproducibility

The final JSONL record reports measured passive (`DEBRIS`, `ROCKET BODY`) and payload
rates, pooled across the **any-element per-object** flag, and separately by element.
The denominator is eligible, controlled **object-windows**, never raw fits, pairs or
self-history intervals. Missing controls are excluded and counted as gaps. Reports
include flagged objects, rate per object-window, occupied object-days, descriptive
annualized flags, and the **same Jeffreys 95% interval function used by
`control_rates_by_object`**. Zero flags never imply zero uncertainty. Overlapping runs
must not be pooled as independent trials. No existing lane's calibration is inherited;
`sufficientToLabel` stays false in this verification release.

Science records exclude clocks, backend, device assignment and chunk size. Runtime,
backend and GPU measurements go to stderr and the usage ledger separately. Stable
archive rows + same population/window/config + pinned dependencies yield byte-identical
CPU reports across runs and chunk sizes. Concurrent corrections *inside* the requested
window can change input between pages: this reader intentionally does not hold a
long-lived snapshot that retains WAL pages. Use a closed archive window for verification.
`--only`/`--limit` restrict the control population too; reports from tiny slices are
runtime fixtures, not population calibration.

## GPU budget and observability

Default ceiling **1430 MiB = 1,499,463,680 bytes**, below **decimal 1.5 GB**.
`--vram-ceiling-mib` may lower it to 320–1430 MiB; it cannot raise the hard maximum.
Each selected GPU has a private CuPy memory pool. Admission takes the **minimum** of
CUDA and `nvidia-smi` free memory (WSL CUDA overreports free VRAM), subtracts headroom,
and reserves the larger of 256 MiB or measured context + 64 MiB **outside** the pool.
A conservative array estimate shrinks object chunks before work; pool OOM halves them
again. One-object OOM, missing telemetry or lost headroom fails explicitly; no CPU
substitution or ceiling increase. Pool limits only decrease during a session.
[CuPy documents why a pool ceiling must account separately for context memory](https://docs.cupy.dev/en/stable/user_guide/memory.html).

Exact pool high-water tracks every allocator call, including transient arrays and
cached blocks. Device-wide VRAM growth is sampled every 100 ms and at boundaries.
`accountedPeakBytes` is the maximum of observed device growth and measured context plus
pool high-water. Device sampling can include another process's allocations and cannot
prove the absence of shorter driver-level peaks; unpooled module overhead under a real
fit still needs measurement. Excess measured growth aborts; allocation-pressure retries
shrink chunks under the existing cap. **Full-fit compliance is not yet verified.**

`--devices 0` runs one card. `--devices 0,1` dispatches at most one chunk per device
concurrently, in NORAD order, merging in that same order. It never auto-selects a card
that merely appears free. Sean's permission to use a card remains required.

Every GPU session writes start and completion/failure receipts with `ts`, `durationMs`,
`resource: gpu-direct`, device, process, outcome and measurements. This includes context
residency through the CPU comparison pass. A writable ledger is required before CUDA.
Ledger: `state/space-orbit-drift-usage.jsonl` (or `SPACE_GPU_USAGE_DIR`). The VPS
`infrastructure/gpu-consumers.json` now carries `space-orbit-drift`; the reviewable
source row is `ops/orbit-drift-gpu-consumer.json`. `callerEvidence` uses the supported
`bigmem-file-grep` checker. `resource: ["gpu-direct"]` makes the row visible on
`/brain/gpu`. **The ledger is truthfully declared `bigmem-local`: live usage spans are
not yet pulled onto that page.** No puller, cron or service deployment was authorized.

## Environment and operation

Isolated `.venv-gpu`, 352 MiB measured; pinned in `requirements-orbit-drift-gpu.txt`:
NumPy 1.26.4, cupy-cuda13x 13.6.0, fastrlock 0.8.3, CUDA runtime 13.1.80 and NVRTC
13.1.115. CuPy 14 requires newer NumPy, so the compatible 13.6 build was selected.
Only the two required CUDA component wheels were added. The loader uses these local
libraries without altering system Python, global loader configuration or another venv.
CUDA 12 fallback was unnecessary because CUDA 13 imported and allocated successfully.
[CuPy installation reference](https://docs.cupy.dev/en/stable/install.html).

Safe inspection, no archive/CUDA access:

```bash
.venv-gpu/bin/python -m pipeline.orbit_drift --dry-run \
  --start 2025-01-01 --end 2026-01-01 --backend gpu --devices 0
```

Bounded CPU verification (not population calibration):

```bash
OPENBLAS_NUM_THREADS=1 .venv-gpu/bin/python -m pipeline.orbit_drift \
  --backend cpu --start 2025-01-01 --end 2026-01-01 \
  --only 40000,40001,40002,40003 --chunk-size 8 --output /tmp/drift-verification.jsonl
```

GPU fitting and parity are **not authorized yet**. After Sean releases a card, the
same command with `--backend gpu --devices 0` runs the GPU verification path.
`ORBIT_DRIFT_GPU_TEST=1` enables the real fixture test with `rtol=1e-10, atol=1e-10`
on slopes/scatters in native units; it also checks GPU chunk-size equality. Never
set that switch as part of an ordinary CPU test run.

## Storage ownership and lifecycle

- Raw archive: read only; this lane never prunes it. Raw page ≤4096 rows by default,
  one day ≤4096 fits (explicit failure beyond cap), window ≤3660 days, object chunk
  ≤256, sampled pairs ≤16000 (default 4000). Resident cost depends on these limits,
  not total archive length. One/two GPU futures only.
- Scratch: `run()` owns a private `TemporaryDirectory`, SQLite fits/object facts with
  a 4 MiB page cache, disk order statistics and 512 MiB hard database page budget.
  Temporary sorting can additionally occupy up to the stored cohort size; provision
  **1 GiB peak scratch**. No persistent checkpoint. Completion/ordinary failure
  closes and removes the private directory. SIGKILL may leave an orphan: inspect its
  owning process and path before removal; never delete another running job's scratch.
- Scientific report: human verification is the sole consumer; explicit `--output`
  refuses overwrite, stops at **256 MiB**, and one report is the retained current
  reference per manual comparison. `--dry-run` exposes budgets without reads/writes.
  Keep at most the current CPU/GPU comparison pair (512 MiB); after review delete the
  superseded regenerable pair. An exception can leave a partial report: only a file
  with its final `kind: controls` record **and exit zero** is complete. There is no
  scheduled accumulating writer or publisher to mistake it for a release.
- GPU receipts: latest **4096 lines / 4 MiB**, one ledger file, no backup generations.
  Trim only superseded telemetry automatically on the next receipt under `flock`;
  retain newest lines including this session. Current runs remain attributable by
  timestamp/device/PID. Use `--ledger-retention-dry-run` to inspect the count/byte cleanup plan
  without writes; the next receipt applies the same policy under its file lock. VPS row expressly
  declares the local reader gap, rather than claiming a nonexistent mirror.
- Dependencies: one `.venv-gpu`, **512 MiB / 10,000 files** budget, retained while these
  exact pinned dependencies are current. Installs use `--no-cache-dir`; no pip archive.
  Superseded venvs are regenerable, but remove only when no drift process uses them.
  CuPy uses `CUPY_CACHE_IN_MEMORY=1`; compiled NVRTC kernels are process-local
  and discarded on exit, with no persistent compilation-cache writer.

## Measured acceptance, 2026-09-12 UTC

- GPU 0 allocation-only smoke: **8 MiB allocation**, **237 MiB context**, **245 MiB
  accounted / observed peak increase**, against a **512 MiB** smoke ceiling. Pool
  high-water **8 MiB**, pool limit **211 MiB**. **2.040 s** GPU session including
  setup/measurement/cleanup. Both RTX 4080 devices enumerated. No fit/kernel pass.
- Bounded real archive, SSD **WAL**, 2025-01-01 through 2026-01-01, NORAD 40000–40031,
  chunk 8: **32 objects, 19,575 raw rows, 7,230 daily blocks, 17 fitted objects,
  1.027 s** CPU pipeline wall time. All 32 objects lacked either sufficient coverage
  or a sufficiently populated cohort; no real passive false-alarm rate is claimed.
- Existing orbit suite: **499 passed**; new suite **20 passed / 1 intentional
  GPU skip**. Tests cover byte identity across runs/chunks, seeded pair bounds,
  segmentation/padding, page-crossing day medians, shared drag vs injected drift,
  leave-one-out cohort counts and bands, coverage gaps, passive Jeffreys reporting,
  two-device dispatch with CPU oracles, OOM shrinking, ledger failures/retention and
  cleanup. CPU admission, registry evidence and smoke dry-run guards also pass.

Outstanding: real GPU fixture parity; kernel compilation and sort workspace behavior;
full-fit peak VRAM, throughput, two-card behavior on real devices; archive-wide passive
calibration and any operational labelling threshold. No full archive pass, GPU fit,
deploy, timer start, unit change or browser launch was performed.
