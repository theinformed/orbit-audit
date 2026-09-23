# T16a — registration: operator-derived LEO element sets and Starlink ephemerides, beside the GP archive

**Status:** registration. Committed alone, before any number.
**Date:** 2026-09-22
**Track:** T16(a) of the research programme runbook
(`docs/research-program-runbook-20260921.md`, T16 row, feasibility verdict STRONG).
**Scope:** ingest and archive only. Nothing here is wired into the two-hourly sweep
(`pipeline/orbit_release.py`), into `public/data/`, into `src/`, or into any site surface.
No cron entry and no systemd timer is created by this track. This is an archive beside the
archive; a later registration must name it before anything consumes it.

---

## 1. Why this exists

Every LEO instrument in this programme reads one input: the general-perturbation (GP) element-set
archive at `/home/sdegan/space-orbit-history/orbit-history.sqlite3`, built from Space-Track's
`class/gp` query, whose element sets are fits to **past** radar and optical observations by the US
Space Surveillance Network. `tools/proximity_plane.py` reads it and nothing else
(`SELECT norad, epoch_ms, mean_motion_q, eccentricity_q, inclination_q, raan_q, arg_perigee_q,
mean_anomaly_q FROM element_set`), and every LEO result the programme has published is bounded by
whatever that archive's element-to-element scatter is. That scatter has never been measured here.

Two public sources carry orbit information for the same objects that does **not** come from the
SSN's observation fits:

1. **CelesTrak Supplemental GP (SupGP)** — element sets that CelesTrak fits with SGP4 to
   owner/operator-supplied ephemerides and other public orbital data, published per constellation.
2. **SpaceX public Starlink ephemerides** — tabulated EME2000 state vectors at 60 s over a 72 h
   span, each with a 6x6 covariance, published by the operator.

Both are *operator-derived* and both are *predictions*. Neither is truth. Ingesting them beside the
GP archive is a precondition for two later measurements the programme owes: the LEO burn-detection
floor, and the first measured recall (T16(b)); and it is the nearest available handle on M2 of the
kinematic-reach design (`docs/kinematic-reach-design-20260922.md` §9: *"M2 | per-object LEO
phase-error growth vs sigma_n and drag history | LEO member windows"*), which cannot be read from
a single-source archive because a single source gives no second opinion.

---

## 2. Sources

### 2.1 CelesTrak Supplemental GP

- **Endpoint (the only one this track may build):**
  `https://celestrak.org/NORAD/elements/supplemental/sup-gp.php?FILE=<set>&FORMAT=json`
- **Documentation:** CelesTrak's [supplemental GP
  pages](https://celestrak.org/NORAD/elements/supplemental/) and the
  [GP data format documentation](https://celestrak.org/NORAD/documentation/gp-data-formats.php);
  method and provenance described in Kuciapinski, K. and Kelso, T. S., *Supplemental General
  Perturbations (SupGP) Element Sets for Modern Space Operations and Space Flight Safety*,
  AMOS 2023 (poster), https://amostech.com/TechnicalPapers/2023/Poster/Kuciapinski.pdf.
- **`FILE=` values this track may request.** Only names **verified from a source outside
  celestrak.org** may be requested. Guessing a set name costs a 404, and a 404 is one of the three
  response classes CelesTrak counts toward its firewall threshold. The verified allowlist is:

  | `FILE=` | verified from | regime | SupGP input source (AMOS 2023, Table 1) |
  |---|---|---|---|
  | `starlink` | third-party index and community documentation | LEO | SpaceX-E / SpaceX-SV |
  | `orbcomm` | KStars `kstars/data/satellites.dat` | LEO | Orbcomm-TLE |
  | `glonass` | KStars `kstars/data/satellites.dat` | MEO | GLONASS-RE |
  | `intelsat` | KStars `kstars/data/satellites.dat` | GEO | Intelsat-11P / Intelsat-E |
  | `gps` | KStars `kstars/data/satellites.dat` | MEO | GPS-A / GPS-E |

  Any other value — including `oneweb`, `planet`, `iridium`, `ses`, `telesat`, which AMOS 2023
  Table 1 shows CelesTrak *produces* but whose `FILE=` spelling this track has not verified — is
  **refused offline by the tool**, before a socket can open. Adding one is an amendment to this
  registration and requires a verified spelling, not a plausible one.

- **What CelesTrak states about the data** (AMOS 2023, verbatim where quoted):
  - *"Each day, CelesTrak checks known sources of publicly available orbital data and produces GP
    data from that data using Satellite Tool Kit (STK)."* — cadence is daily, per set.
  - *"Supplemental GPEs will have a 'C' in this field (to identify the source as CelesTrak)"*,
    where regular Space-Track GPEs carry `U`. This is a **checkable provenance flag inside the
    record**, not an inference: `CLASSIFICATION_TYPE`.
  - *"SupGP data is fitted from the current epoch forward, as opposed to GP data which is fit to
    past observations."* — this is the grounds for the prediction-vs-observation flag in §5, and it
    is the provider's own statement, not our assumption.
  - *"Unlike in the standard GP queries, it is possible to get multiple SupGP elements for a single
    object."* — the dedupe key therefore **cannot** be `(NORAD, EPOCH)` alone; see §5.3.
  - Post-manoeuvre element sets are marked `[PM]` at the end of the satellite name (TLE line 0).
  - Element set number is used to trace an element set back to its source data (e.g. GPS week and
    time of applicability).
  - Coverage as of that paper: SupGP data for 69% of operational satellites. That is a 2023 figure
    and is **not** treated here as a current census.

### 2.2 SpaceX public Starlink ephemerides

- **Manifest:** `https://api.starlink.com/public-files/ephemerides/MANIFEST.txt` — one filename per
  line.
- **File:** `https://api.starlink.com/public-files/ephemerides/<name from manifest>`
- **Filename shape:** `MEME_<serial>_STARLINK-<spacecraft>_<code>_Operational_<code>_UNCLASSIFIED.txt`.
  **The filename carries no NORAD catalogue number.** The join to the catalogue is by
  `OBJECT_NAME` against `runtime/spacetrack-mirror/gp-active.json`, which is a *name* join and is
  therefore fallible; unresolved names are counted and reported, never silently dropped.
- **File format** (as published; field meanings are the operator's labels, not our derivation):
  ```
  created:YYYY-MM-DD HH:MM:SS UTC
  ephemeris_start:... ephemeris_stop:... step_size:60
  ephemeris_source:blend
  UVW
  <YYYYDDDHHMMSS.sss> <x> <y> <z> <vx> <vy> <vz>        km, km/s, MEME (J2000)
  <7 covariance values>
  <7 covariance values>
  <7 covariance values>
  ... repeating 4-line records ...
  ```
  The 21 covariance values are the lower triangle of a 6x6 position/velocity covariance, in the
  order `C11; C21 C22; C31 C32 C33; C41 C42 C43 C44; C51 ... C55; C61 ... C66`, in the frame the
  file labels `UVW`. **The identification of index 1/2/3 with radial/in-track/cross-track is an
  assumption carried from the label, not a fact this track has verified.** It is recorded as an
  assumption and reported as such; §6.5 gives the check that would discharge it.

### 2.3 What is NOT a source for this track

Space-Track's own Starlink ephemeris holdings are **not** fetched by this track. The GP side of the
comparison uses the existing hourly mirror `runtime/spacetrack-mirror/gp-active.json` and the
existing archive — no second poller is created against Space-Track, whose one-query-per-hour
ceiling and personal-identity boundary (`enforce_entity_boundary()` in
`ingest/spacetrack_ingest.py`, host `bigmem-PC`) are account-suspension-grade constraints.

---

## 3. Route

| Source | Fetched from | Why |
|---|---|---|
| CelesTrak SupGP | **`vps` only** (`openclaw-ash-1`), direct, no proxy, no VPN | Standing route rule: CelesTrak is reached direct from the VPS and never from `pc`, bigmem, a home connection, a VPN, CI, or a developer workstation — not even a reachability check. The rule is about not associating a home address with CelesTrak access, and a probe creates that association irreversibly. |
| Starlink ephemerides | **`pc`** | api.starlink.com carries no such rule, and the data is large; `vps` is capacity-capped (18 GiB free at registration) and must not hold it. |

**The data lands on `pc`.** The CelesTrak body is written to a small staging directory on `vps`,
transferred to `pc`, and **removed from `vps` in the same run**. `vps` retains only the request
ledger line and the halt marker — bookkeeping, not data.

The tool enforces the route in code, before any socket is created:
`fetch-supgp` refuses to run on any host but `openclaw-ash-1`; `fetch-starlink` refuses to run
anywhere but the `pc` host. A refusal is offline and costs no request.

---

## 4. Fetch etiquette

### 4.1 What CelesTrak documents, and which of it binds this track

From CelesTrak's usage policy and GP data documentation (last reviewed against the live pages
2026-09-03; recorded in `docs/CELESTRAK-COMPLIANCE.md`):

- download only data you need, when you will use it, and **only once per actual update**;
- use current documented `https://celestrak.org` endpoints, not legacy URLs or redirects;
- **stop machine-to-machine querying immediately on every non-200 response and report to a human**;
- stop on server errors as well as client errors — 50x is a recovery signal, not permission to retry;
- avoid overlapping bulk sets, especially Active plus a large subset such as Starlink;
- enforcement, since 2026-03-26: **one download per update** for large GP groups beginning with
  Active and Starlink, with a deliberate HTTP 403 for a repeat before the data changes;
- published limit: **50 responses of HTTP 301, 403 or 404 within any 2-hour window**, after which
  the address is sent to the firewall. 50x responses and transport failures do not count toward it.

**Owner directive, standing:** an IP ban is irreversible. No part of this design may assume access
can be regained by appeal, waiting, changing route, or using another address.

### 4.2 The T16a budget — stricter than the published limit, by design

The published limit is a wall, not a target. This track's own ceiling:

| Rule | Value |
|---|---|
| Host gate | `openclaw-ash-1` only, checked before any socket |
| Set allowlist | the five verified `FILE=` names in §2.1; anything else refused offline |
| **One request per set per rolling 24 h** | the sets are produced daily; asking twice a day is asking for data that has not changed |
| Requests per process | **4 maximum**, hard backstop after the per-set gate |
| Gap between requests in one run | **10 s** |
| Retries | **none** — ever, for any status or transport failure |
| Redirects | **not followed**; a redirect is a halt |
| Proxy | `HTTP_PROXY`/`HTTPS_PROXY` are **not honoured**; the opener is built without proxy handlers |
| Body ceiling | **32 MiB**; over is a halt |
| Attempt timestamp | persisted to disk **before** the socket opens, so a crash cannot buy a free retry |
| Conditional requests | `If-None-Match` / `If-Modified-Since` sent **verbatim** whenever a validator is held for that set, bound to the cached body by sha256 |
| Halt | any non-200 (except a 304 answering a conditional **we** sent), any redirect, any transport failure, an empty or oversized body, invalid JSON, or a body that is not a JSON array — writes a permanent marker; every later run is socket-free until a human clears it with a recorded reason |
| Wasted-request ledger | every body's sha256 and byte count recorded per set; a byte-identical repeat is logged as a wasted request and counted |

**Conditional requests are shipped and are expected to be inert.** CelesTrak's PHP endpoints were
measured on 2026-08-27 to send neither `ETag` nor `Last-Modified`, so no 304 is obtainable today.
This track records the response headers of every SupGP 200 so that the measurement is re-made on a
different endpoint family rather than assumed from the `gp.php` result. Until a validator is
observed, this lane is **not** described as "using conditional requests".

**Relationship to the site's CelesTrak mirror.** `ingest/celestrak_mirror.py` remains the only
*scheduled* CelesTrak caller and the only one the site depends on. T16a is a manually driven
research lane with its own ledger, its own halt marker and its own state directory; it never reads,
writes, or clears the mirror's state, and it never requests a `gp.php` URL. Because both lanes
share one address, an operator run of T16a **must first read the mirror's 24 h attempt count** and
must not push the combined 24 h total above the mirror's own watchdog ceiling of 7. The tool prints
the combined figure and requires it as an explicit argument, so it cannot be skipped by accident.

### 4.3 Starlink ephemeris etiquette

SpaceX publishes these files openly and anonymously. **No published rate limit for
`api.starlink.com/public-files/` was located.** That is stated as an unknown, not read as
permission:

| Rule | Value |
|---|---|
| Host gate | `pc` only |
| Manifest | at most **one fetch per 8 h** (the set is refreshed roughly three times a day) |
| Ephemeris files per run | **250 maximum**, sampled deterministically from the manifest by a seeded, recorded rule — never the whole 11k-file set |
| Gap between file requests | **0.5 s** |
| Retries | **none** |
| Redirects | not followed |
| Conditional requests | `If-Modified-Since` / `If-None-Match` sent when a validator is held |
| Body ceiling | 32 MiB per file |
| Halt | as §4.2 — any non-200 except an answered 304, any transport failure, an empty or oversized body |

### 4.4 The request ledger

Every outbound attempt by either lane, successful or not, appends one line to
`<root>/ledger/requests.jsonl` **before** the socket opens and is completed after the response:

```
{"lane":"supgp","set":"starlink","url":"<full url>","host":"openclaw-ash-1",
 "startedAt":"2026-09-22T18:40:00.123456+00:00","status":200,"bytes":6123456,
 "sha256":"...","elapsedMs":812,"validatorsSent":{},"validatorsSeen":{},
 "outcome":"ok","note":null}
```

The ledger is the etiquette evidence. A claim of compliance that cannot be read off this file is
not evidence.

---

## 5. Storage layout, beside the GP archive

The GP archive root is `/home/sdegan/space-orbit-history/` on `pc` (ext4 SSD). The supplemental
archive sits beside it, on the same filesystem, as a **separate root** so that no failure, lock, or
schema change here can touch the archive every published result depends on:

```
/home/sdegan/space-supplemental-history/
  supgp/
    raw/<YYYY>/<MM>/sup-gp-<set>-<YYYYMMDDTHHMMSSZ>.json.gz   verbatim response body, gzipped
    supgp.sqlite3                                              parsed element sets
  starlink/
    raw/<YYYY>/<MM>/<DD>/MANIFEST-<YYYYMMDDTHHMMSSZ>.txt.gz
    raw/<YYYY>/<MM>/<DD>/<manifest filename>.gz                PRIVATE — never republished
    starlink.sqlite3                                           parsed headers + covariance summaries
  ledger/
    requests.jsonl        one line per outbound attempt (§4.4)
    captures.jsonl        one line per ingest run, including runs that added nothing
  state/
    last-request-at.json  per-set attempt timestamps, written before the socket
    validators.json       per-set ETag / Last-Modified, bound to the body by sha256
    bodies.json           per-set sha256 + byte count of the last body (wasted-request ledger)
  HALTED.json             permanent halt marker, when halted
```

Nothing in this tree is inside the repository, so nothing can be committed by accident; the
repository's `.gitignore` already excludes `runtime/` and `public/data/`, and this root is outside
both.

### 5.1 `supgp.sqlite3`

```sql
CREATE TABLE element_set_sup (
  norad            INTEGER NOT NULL,
  epoch_ms         INTEGER NOT NULL,
  element_set_no   INTEGER NOT NULL,     -- traces back to the SupGP source datum
  set_name         TEXT    NOT NULL,     -- the FILE= value, e.g. 'starlink'
  object_name      TEXT,                 -- carries the '[PM]' post-manoeuvre marker verbatim
  object_id        TEXT,
  mean_motion      REAL, eccentricity REAL, inclination REAL,
  raan             REAL, arg_perigee  REAL, mean_anomaly REAL,
  bstar            REAL, ndot REAL, nddot REAL, rev_at_epoch INTEGER,
  -- provenance, §5.2
  source           TEXT NOT NULL,        -- 'celestrak-supgp'
  fetched_at_ms    INTEGER NOT NULL,
  body_sha256      TEXT NOT NULL,        -- links the row to the exact raw file it came from
  classification   TEXT,                 -- verbatim CLASSIFICATION_TYPE; 'C' for SupGP
  operator_derived INTEGER NOT NULL,     -- 1 iff classification == 'C'
  prediction       INTEGER NOT NULL,     -- 1 for SupGP: fitted forward from epoch
  covariance       INTEGER NOT NULL,     -- 0: a SupGP element set carries no covariance
  originator       TEXT,
  ingest_host      TEXT NOT NULL,
  PRIMARY KEY (norad, epoch_ms, element_set_no, set_name)
) WITHOUT ROWID;
```

### 5.2 Provenance fields — what each one is grounded in

| Field | Value for SupGP | Value for Starlink ephemeris | Grounds |
|---|---|---|---|
| `source` | `celestrak-supgp` | `spacex-starlink-ephemeris` | the URL that produced the bytes |
| `fetched_at_ms` | run clock at the moment the socket opened | same | the request ledger line |
| `body_sha256` | sha256 of the exact response body on disk | same | recomputable from the raw file; a row whose hash does not match a stored file is an error |
| `operator_derived` | 1 | 1 | **measured from the record**: `CLASSIFICATION_TYPE == 'C'`, the provider's own marker, not an assumption about the set name. A SupGP record arriving with `U` is counted and flagged, not silently relabelled. |
| `prediction` | 1 | 1 | the provider's statement that SupGP is fitted forward from epoch; the ephemerides are a 72 h forward tabulation with `ephemeris_start` in the near past |
| `covariance` | 0 | 1 | present in the bytes or not |
| `classification` | verbatim | n/a | |
| `element_set_no` | verbatim | n/a | traces the element set to its source datum |
| `ingest_host` | hostname of the parsing host | same | |

The **same six provenance fields** are recorded for the GP side whenever a GP record is copied into
a comparison output, with `operator_derived = 0`, `prediction = 0`, `covariance = 0`, and
`classification = 'U'` — so that a downstream reader can never confuse the two archives by
accident, and so that a mixed set carries the distinction per row rather than per file.

### 5.3 Deduplication

**The GP archive's key `(norad, epoch_ms)` is wrong for SupGP** and using it would silently drop
data: CelesTrak states that multiple SupGP element sets can exist for one object at one time,
because several sources may cover it or a source may publish several epochs. The key here is
`(norad, epoch_ms, element_set_no, set_name)`, inserted with `INSERT OR IGNORE`, and every run
records `records_read`, `elements_new`, `duplicates = records_read - elements_new` in
`ledger/captures.jsonl`, **including runs that add nothing** — a gap in the archive must be
provable rather than inferred from missing rows.

A second, distinct case is recorded rather than merged: two records with the same
`(norad, epoch_ms, element_set_no, set_name)` but **different element values** would mean the
provider changed an element set in place. The tool counts these as `collisions` and refuses to
overwrite; a non-zero collision count is a finding, not a warning to suppress.

### 5.4 `starlink.sqlite3`

One row per ingested ephemeris file (header provenance, resolved NORAD or null, record count,
`created`, `ephemeris_start`, `ephemeris_stop`, `step_size`, `ephemeris_source`, `covariance_frame`,
`body_sha256`), plus one row per sampled lead time per file carrying the covariance diagonal in the
file's own frame order (`c11`, `c22`, `c33` and the velocity diagonal), at fixed lead times
`0, 1, 3, 6, 12, 24, 48, 72 h` after `ephemeris_start`. The full 60 s tabulation is **not**
expanded into the database — it stays in the gzipped raw file.

---

## 6. Redistribution posture

**Derived facts only. No raw redistribution, from either source, to anywhere.**

- **Raw Starlink ephemeris files and the manifest stay private on `pc`**, under
  `/home/sdegan/space-supplemental-history/starlink/raw/`. They are not copied to `vps`, not placed
  under `public/data/`, not committed, and not attached to any publication. What may leave is a
  derived statistic — a quantile, a count, a distribution — never a file, a state vector table, or a
  reconstructed ephemeris.
- **Raw SupGP bodies stay private on `pc`** for the same reason and by the same rule. The existing
  archive already refuses to persist `TLE_LINE1`/`TLE_LINE2` at scale on the stated grounds that
  doing so would make this installation look like a data clearinghouse; that reasoning applies with
  at least equal force to operator-derived element sets.
- **Space-Track's user agreement is internally inconsistent** on what a recipient may redistribute.
  This track therefore takes the conservative reading and republishes nothing raw from any orbital
  source, and continues the existing USSPACECOM / 18 SDS attribution wherever a derived fact is
  published — attribution is a condition of use, not a courtesy.
- **CelesTrak attribution** accompanies any published derived fact that used SupGP data, naming
  CelesTrak as the producer and the operators as the originators of the underlying ephemerides.
- No part of this track publishes a per-operator or per-nation narrative. Counts and quantiles are
  grouped by constellation because the sets are published that way, and for no other reason.

---

## 7. The first measurement

**A same-object, same-epoch comparison of SupGP against GP elements.** Registered here in full,
before any of it is run.

### 7.1 Statistic

For each object present in both a SupGP set and the GP snapshot
`runtime/spacetrack-mirror/gp-active.json`:

1. Let `t*` be the **SupGP element set's own epoch**. This is the comparison time; there is exactly
   one per object per SupGP element set.
2. Propagate the SupGP element set to `t*` with SGP4 from its published TLE lines. (At `t*` this is
   the element set's own epoch, so the propagation span is zero.)
3. Propagate the GP element set for the same NORAD number to `t*` with SGP4 from **its** published
   TLE lines. The span is `dt = t* - epoch_GP`, signed, and is recorded per object.
4. Both states are TEME position/velocity. Form the RTN basis **from the GP state**
   (`R = r/|r|`, `N = (r x v)/|r x v|`, `T = N x R`) and project the difference
   `d = r_SupGP - r_GP` onto it:
   - `dR` = radial difference, metres
   - `dT` = along-track difference, metres
   - `dN` = cross-track difference, metres (reported for completeness; the registered headline is
     along-track and radial)
5. Report, **per constellation** (per SupGP `FILE=` set), the quantiles
   `p05, p25, p50, p75, p95` of `|dR|` and `|dT|`, with `n`, alongside the quantiles of `|dt|`.

The frame convention, the sign convention and the choice of `t*` are fixed here so that they cannot
be chosen after seeing the numbers.

### 7.2 Cuts, fixed in advance

- `|dt| <= 24 h`. Objects whose nearest GP element set is older than that are excluded and
  **counted**; the excluded count is reported per set.
- Objects whose SGP4 propagation returns a non-zero error code on either side are excluded and
  counted by error code.
- Objects whose GP record carries `DECAY_DATE` non-null are excluded.
- A set with fewer than **30** surviving objects gets counts only. **No quantiles are printed for
  n < 30.**
- Where a SupGP set contains several element sets for one object, the one with the **latest epoch**
  is used, and the number of objects for which this choice was made is reported.

### 7.3 The Starlink covariance quantiles

For the sampled ephemeris files, at each fixed lead time `0, 1, 3, 6, 12, 24, 48, 72 h` after
`ephemeris_start`, report the quantiles `p05, p25, p50, p75, p95` of `sqrt(c11)`, `sqrt(c22)`,
`sqrt(c33)` in metres, with `n` files contributing at each lead. These are the operator's **formal**
one-sigma position uncertainties in the file's own `UVW` frame. §7.4 states what they are not.

### 7.4 Floors — what this measurement cannot resolve, stated before it runs

1. **The GP set-to-set floor.** Two consecutive GP element sets for the same object, propagated to
   the same time, do not agree. That disagreement is the floor below which a SupGP-minus-GP
   difference is not a resolvable difference. It is measured in the same run, on the same objects,
   from the archive `element_set` table: the two most recent GP element sets before `t*` are both
   propagated to `t*` and differenced by the identical §7.1 procedure. Its quantiles are printed
   beside the SupGP-GP quantiles, and **the comparison is read against that floor, never against
   zero.**
2. **The epoch-gap floor.** The difference grows with `|dt|`, because the GP side is being
   propagated. The quantiles are therefore reported **binned by `|dt|`** (`0-2 h`, `2-6 h`,
   `6-12 h`, `12-24 h`) as well as pooled. A pooled number alone would confound the two archives'
   disagreement with one archive's propagation.
3. **The model floor — the one that bounds the whole measurement.** Both sides are SGP4 mean
   elements in TEME. Neither is a position measurement. **This measurement cannot say which source
   is more accurate**; it measures a *disagreement*, and a disagreement attributes to neither side.
   The word "error" is not used for it in the results document. Deciding which side is closer to
   truth requires an external precise orbit determination product, which is T16(b) and is not this
   registration.
4. **The quantisation floor.** Where archive-reconstructed elements are used (floor 1 only; the
   SupGP-GP comparison uses published TLE lines on both sides), the archive stores angles at
   `1e-4` degrees and mean motion at `1e-8` rev/day. At a LEO radius of about 6,900 km a
   `0.5e-4` degree rounding in mean anomaly is about **6 m** along-track, and the mean-motion
   rounding contributes well under a metre over a 12 h span. The floor-1 quantiles are therefore
   not meaningful below roughly **10 m** and this is printed with them.
5. **The sampling floor.** Per-constellation `n` is printed with every quantile. The Starlink
   covariance sample is 250 files out of about 11,000 and is a **sample**, drawn by a recorded
   deterministic rule; it is not a census of the constellation and is not described as one.
6. **The covariance floor.** The SpaceX covariance is the operator's formal covariance of a blended
   solution. It has not been validated against independent tracking by anyone in this programme, and
   a formal covariance is a statement about a filter, not about reality. Two specific things are
   reported rather than smoothed over: (a) the axis-order assumption of §2.2 is unverified, and the
   quantiles are labelled by **column index** as well as by the frame's published axis name;
   (b) if the terminal-lead covariance values are found to be identical across files — which would
   mean a fixed default rather than a propagated covariance — that is reported as a finding and the
   affected leads are excluded from any interpretation. The check that would discharge (a) is a
   direct one: an axis whose variance grows fastest with lead time is the in-track axis for any
   near-circular orbit under along-track error growth; if the published label and the measured
   growth ordering agree, the assumption is discharged, and if they disagree, the label is reported
   and nothing is relabelled.

### 7.5 What a result here would and would not license

A measured SupGP-GP disagreement well **above** the GP set-to-set floor would license one statement:
that the two archives disagree by more than the GP archive disagrees with itself, at a stated lead,
for a stated constellation. That is a precondition for T16(b), not a substitute for it. It licenses
no claim about detection, recall, precision, manoeuvre identification, or any instrument's floor
until a registration says how it is consumed.

A disagreement **at or below** the floor would be equally informative and is not a failed result: it
would say the operator-derived sets add nothing the GP archive's own scatter does not already
contain, for that constellation, at that lead — and it would close the cheapest arm of T16.

---

## 8. Deliverables of this track

1. This registration, committed alone.
2. `tools/supgp_ingest.py` — host-gated fetch, offline parse/ingest, offline comparison — with a
   Starlink ephemeris reader, and `tests/test_supgp_ingest.py` running offline on fixtures under
   the repository's existing `python3 -m unittest discover -s tests -p 'test_*.py'`. Every guard
   test is negative-controlled: the same scenario is re-run with the guard disabled and asserted to
   reproduce the bad behaviour, because a guard test that never reaches its code path passes for
   the wrong reason.
3. One real fetch of each source under §4, stored under §5, and the §7 measurement, reported in
   `docs/t16a-results-<date>.md` with a machine-readable `docs/t16a-results-<date>.json` receipt in
   the shape the programme already uses (`study`, `registration`, `registrationCommit`, `generated`,
   `host`, `archive`, `runs`, `sourceSha256`).
4. A T16 row in `docs/research-program-runbook-20260921.md`.

## 9. What this track does not do

- It does not add a cron entry, a systemd timer, or any scheduled caller.
- It does not modify `ingest/celestrak_mirror.py`, `ingest/spacetrack_ingest.py`,
  `pipeline/orbit_release.py`, `pipeline/orbit_history.py`, or the archive database.
- It does not write to `src/`, `data/`, `public/`, `runtime/`, or any site surface.
- It does not publish any raw file from either source.
- It does not claim a recall, a precision, a detection floor, or an accuracy ranking. Those are
  T16(b) and are unmeasured.
